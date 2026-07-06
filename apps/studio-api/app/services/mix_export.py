"""FinalMixExportService: combine all stems into the final stereo song.

Pipeline: validate → resolve active tracks → ensure stems fresh (render where
safe) → load stems → apply effect chains → apply volume/pan/mute/solo →
align to project duration → sum → normalize/limit → WAV (+ MP3 via ffmpeg)
→ register as exported_mix assets.
"""
from __future__ import annotations

import json
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from ..config import get_config
from ..db import get_db
from ..models.song import SongProject, new_id, now_iso
from . import asset_repo, project_repo, vocal_engine
from .audio_io import AudioReadError, read_audio, resample_linear, to_stereo, write_wav
from .capabilities import ffmpeg_path
from .render import sample_renderer, soundfont_renderer
from .render.effects import apply_effect_chain
from .render.soundfont_renderer import SAMPLE_RATE, track_fingerprint

log = logging.getLogger(__name__)


class ExportJob(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    status: str = "pending"   # pending | running | completed | failed
    requested_formats: list[str] = Field(default_factory=lambda: ["wav"])
    output_files: list[str] = Field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _save_job(job: ExportJob) -> None:
    get_db().execute(
        "INSERT INTO export_jobs (id, project_id, data) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
        (job.id, job.project_id, job.model_dump_json()))
    get_db().commit()


def list_jobs(project_id: str) -> list[ExportJob]:
    rows = get_db().execute(
        "SELECT data FROM export_jobs WHERE project_id=?", (project_id,)).fetchall()
    jobs = [ExportJob.model_validate_json(r["data"]) for r in rows]
    jobs.sort(key=lambda j: j.started_at or "", reverse=True)
    return jobs


def ensure_stems(project: SongProject, job: ExportJob) -> None:
    """Render missing/stale stems where safe; collect warnings/errors."""
    cfg = get_config()

    def stale(track, stem_type) -> bool:
        stem = next((s for s in project.stems if s.track_id == track.id
                     and s.stem_type == stem_type), None)
        if stem is None:
            return True
        if not (cfg.root / stem.path).exists():
            return True
        return stem.source_fingerprint != track_fingerprint(project, track)

    from .midi_export import exportable_tracks
    needs_instruments = any(
        stale(t, "instrument") for t in exportable_tracks(project)
        if t.track_type not in ("lead_vocal", "backing_vocal"))
    if needs_instruments:
        r = soundfont_renderer.render_instrument_stems(project)
        job.warnings.extend(r["warnings"])
        job.errors.extend(r["errors"])

    if any(stale(t, "sample") for t in project.tracks
           if t.track_type == "sample" and any(c.clip_type == "sample" for c in t.clips)):
        r = sample_renderer.render_sample_stems(project)
        job.warnings.extend(r["warnings"])
        job.errors.extend(r["errors"])

    if any(stale(t, "vocal") for t in project.tracks
           if t.track_type in ("lead_vocal", "backing_vocal")):
        r = vocal_engine.render_vocal_stems(project)
        job.warnings.extend(r["warnings"])
        job.errors.extend(r["errors"])


def mixdown(project: SongProject, job: ExportJob) -> np.ndarray:
    cfg = get_config()
    total = max(int(project.duration_seconds() * SAMPLE_RATE), SAMPLE_RATE)
    master = np.zeros((total, 2), dtype=np.float32)
    any_solo = any(t.solo for t in project.tracks)
    mixed_count = 0

    for track in project.tracks:
        audible = track.solo if any_solo else not track.mute
        if not audible:
            job.warnings.append(f"track {track.name!r} excluded "
                                f"({'not soloed' if any_solo else 'muted'})")
            continue
        stems = [s for s in project.stems if s.track_id == track.id]
        if not stems:
            if track.clips:
                job.warnings.append(f"track {track.name!r} has no rendered stem")
            continue
        for stem in stems:
            path = cfg.root / stem.path
            if not path.exists():
                job.errors.append(f"stem missing on disk: {stem.path}")
                continue
            try:
                data, rate = read_audio(path)
            except AudioReadError as e:
                job.errors.append(str(e))
                continue
            data = to_stereo(data)
            data = resample_linear(data, rate, SAMPLE_RATE)
            data, fx_warnings = apply_effect_chain(data, SAMPLE_RATE, track.effects)
            job.warnings.extend(f"{track.name}: {w}" for w in fx_warnings)
            # volume + constant-power pan
            data = data * track.volume
            angle = (np.clip(track.pan, -1, 1) + 1) * np.pi / 4
            data[:, 0] *= np.cos(angle) * np.sqrt(2)
            data[:, 1] *= np.sin(angle) * np.sqrt(2)
            # align to project duration
            if len(data) < total:
                data = np.vstack([data, np.zeros((total - len(data), 2), np.float32)])
            master += data[:total]
            mixed_count += 1

    if mixed_count == 0:
        raise MixdownError(
            "no stems available to mix — render stems first "
            "(instruments require FluidSynth + a SoundFont)")

    # master bus processing
    master, master_warnings = apply_effect_chain(
        master, SAMPLE_RATE, project.mix_settings.master_effects)
    job.warnings.extend(f"master: {w}" for w in master_warnings)
    master *= project.mix_settings.master_volume
    peak = float(np.max(np.abs(master)))
    if project.mix_settings.normalize and peak > 0:
        target = 0.94
        if peak > target:
            master *= target / peak
            job.warnings.append(f"master normalized (peak was {peak:.2f})")
    elif project.mix_settings.limiter and peak > 0.99:
        master = np.tanh(master * 0.9) / np.tanh(0.9)
        job.warnings.append("soft limiter applied to prevent clipping")
    return master


class MixdownError(Exception):
    pass


def encode_mp3(wav_path: Path, mp3_path: Path) -> bool:
    ff = ffmpeg_path()
    if ff is None:
        return False
    proc = subprocess.run(
        [ff, "-y", "-v", "error", "-i", str(wav_path),
         "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        capture_output=True, text=True, timeout=600)
    return proc.returncode == 0 and mp3_path.exists()


def _register_export_asset(rel_path: str, project: SongProject) -> None:
    from ..models.asset import Asset
    cfg = get_config()
    path = cfg.root / rel_path
    existing = asset_repo.get_asset_by_relative_path(rel_path)
    asset_repo.upsert_asset(Asset(
        id=existing.id if existing else uuid.uuid4().hex,
        asset_type="exported_mix", filename=path.name,
        original_path=str(path), relative_path=rel_path,
        extension=path.suffix.lower(),
        file_size=path.stat().st_size if path.exists() else 0,
        source="export", analysis_status="not_applicable",
        generated_description=f"final mix of {project.title!r}"))


def export_mix(project: SongProject, formats: list[str]) -> ExportJob:
    cfg = get_config()
    job = ExportJob(project_id=project.id, requested_formats=formats,
                    status="running", started_at=now_iso())
    _save_job(job)
    try:
        errors = project_repo.validate_references(project)
        if errors:
            raise MixdownError("project validation failed: " + "; ".join(errors))

        ensure_stems(project, job)
        master = mixdown(project, job)

        out_dir = cfg.exports_dir / project.id
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        from .midi_export import _safe_name
        base = f"{_safe_name(project.title)}_{stamp}_{job.id[:6]}"

        if "wav" in formats:
            wav_path = out_dir / f"{base}.wav"
            write_wav(wav_path, master, SAMPLE_RATE)
            rel = wav_path.relative_to(cfg.root).as_posix()
            job.output_files.append(rel)
            _register_export_asset(rel, project)

        if "mp3" in formats:
            wav_src = out_dir / f"{base}.wav"
            temp_wav = None
            if not wav_src.exists():
                temp_wav = out_dir / f"{base}_tmp.wav"
                write_wav(temp_wav, master, SAMPLE_RATE)
                wav_src = temp_wav
            mp3_path = out_dir / f"{base}.mp3"
            if encode_mp3(wav_src, mp3_path):
                rel = mp3_path.relative_to(cfg.root).as_posix()
                job.output_files.append(rel)
                _register_export_asset(rel, project)
            else:
                job.warnings.append(
                    "MP3 export unavailable: ffmpeg (with libmp3lame) not "
                    "found or encoding failed — WAV export is unaffected")
            if temp_wav and temp_wav.exists():
                temp_wav.unlink()

        job.status = "completed" if job.output_files else "failed"
        if not job.output_files:
            job.errors.append("no output files were produced")
        project.render_status = "exported"
        project_repo.save_project(project)
    except MixdownError as e:
        job.status = "failed"
        job.errors.append(str(e))
    except Exception as e:  # never lose the job record
        log.exception("export failed")
        job.status = "failed"
        job.errors.append(f"unexpected error: {e}")
    job.completed_at = now_iso()
    _save_job(job)
    return job


# --- Phase 21: project package export -------------------------------------

def export_package(project: SongProject) -> ExportJob:
    """Archive project JSON, lyrics, alignment, MIDI, stems and final mixes
    into exports/{project_id}/package/ plus a ZIP. Never touches originals."""
    import shutil
    import zipfile

    cfg = get_config()
    job = ExportJob(project_id=project.id, requested_formats=["package"],
                    status="running", started_at=now_iso())
    _save_job(job)
    try:
        pkg_dir = cfg.exports_dir / project.id / "package"
        if pkg_dir.exists():
            shutil.rmtree(pkg_dir)  # regenerated content only, safe to replace
        pkg_dir.mkdir(parents=True)

        (pkg_dir / "project.json").write_text(
            project.model_dump_json(indent=2), encoding="utf-8")

        if project.lyrics.lines:
            lines = []
            current_section = None
            for l in project.lyrics.lines:
                if l.section_id != current_section:
                    current_section = l.section_id
                    section = project.get_section(l.section_id)
                    lines.append(f"\n[{section.name if section else 'Section'}]")
                lines.append(l.text)
            (pkg_dir / "lyrics.txt").write_text(
                "\n".join(lines).strip() + "\n", encoding="utf-8")

        align_src = cfg.projects_dir / project.id / "lyrics_alignment.json"
        if align_src.exists():
            shutil.copy2(align_src, pkg_dir / "lyrics_alignment.json")

        for sub, items in (("midi", project.midi_files.values()),
                           ("stems", (s.path for s in project.stems))):
            dest = pkg_dir / sub
            for rel in items:
                src = cfg.root / rel
                if src.exists():
                    dest.mkdir(exist_ok=True)
                    shutil.copy2(src, dest / Path(rel).name)
                else:
                    job.warnings.append(f"{sub} file missing, not packaged: {rel}")

        mixes = [a for a in asset_repo.list_assets("exported_mix")
                 if a.relative_path.startswith(f"exports/{project.id}/")
                 and not a.is_missing and Path(a.original_path).exists()]
        if mixes:
            (pkg_dir / "mix").mkdir(exist_ok=True)
            for a in mixes:
                shutil.copy2(a.original_path, pkg_dir / "mix" / a.filename)
        else:
            job.warnings.append("no final mix found — export a mix first to include it")

        zip_path = cfg.exports_dir / project.id / f"{project.id}_package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in pkg_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(pkg_dir))
        job.output_files.append(zip_path.relative_to(cfg.root).as_posix())
        job.status = "completed"
    except Exception as e:
        log.exception("package export failed")
        job.status = "failed"
        job.errors.append(str(e))
    job.completed_at = now_iso()
    _save_job(job)
    return job
