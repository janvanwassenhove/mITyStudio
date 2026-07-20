from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import get_config
from ..models.song import SongProject
from ..services import midi_export, project_repo
from ..services.project_repo import ProjectNotFound
from ..services.render import sample_renderer, soundfont_renderer

router = APIRouter(prefix="/api/projects", tags=["render"])


def _load(project_id: str) -> SongProject:
    try:
        return project_repo.load_project(project_id)
    except ProjectNotFound:
        raise HTTPException(404, "project not found")


@router.post("/{project_id}/midi/export")
def export_midi(project_id: str) -> dict:
    project = _load(project_id)
    try:
        outputs = midi_export.export_project_midi(project)
    except midi_export.MidiExportError as e:
        raise HTTPException(422, str(e))
    project_repo.save_project(project)
    return {"midi_files": outputs, "count": len(outputs)}


@router.post("/{project_id}/render/instrument-stems")
def render_instrument_stems(project_id: str) -> dict:
    project = _load(project_id)
    results = soundfont_renderer.render_instrument_stems(project)
    project_repo.save_project(project)
    return results


@router.post("/{project_id}/render/sample-stems")
def render_sample_stems(project_id: str) -> dict:
    project = _load(project_id)
    results = sample_renderer.render_sample_stems(project)
    project_repo.save_project(project)
    return results


@router.post("/{project_id}/render/auto")
def auto_render(project_id: str) -> dict:
    """Render whatever is missing or stale (instruments, samples, vocals) in
    one call — used by the frontend before playback so the user never has to
    render manually. Up-to-date stems are skipped via fingerprints."""
    from ..services.mix_export import ExportJob, ensure_stems
    project = _load(project_id)
    before = {(s.track_id, s.stem_type, s.source_fingerprint, s.rendered_at)
              for s in project.stems}
    job = ExportJob(project_id=project_id)  # collector for warnings/errors
    ensure_stems(project, job)
    project_repo.save_project(project)
    after = {(s.track_id, s.stem_type, s.source_fingerprint, s.rendered_at)
             for s in project.stems}
    return {"changed": before != after,
            "stems": len(project.stems),
            "warnings": job.warnings,
            "errors": job.errors}


@router.post("/{project_id}/render/apply-effects")
def apply_effects(project_id: str) -> dict:
    """Effects are applied non-destructively during mixdown; this endpoint
    reports which effect chains would apply and validates them."""
    project = _load(project_id)
    from ..services.render.effects import PLACEHOLDER_EFFECTS
    report = []
    for t in project.tracks:
        enabled = [e for e in t.effects.effects if e.enabled]
        if enabled:
            report.append({
                "track": t.name,
                "effects": [e.effect_type for e in enabled],
                "placeholders": [e.effect_type for e in enabled
                                 if e.effect_type in PLACEHOLDER_EFFECTS],
            })
    return {"tracks_with_effects": report,
            "note": "effects are applied during mixdown (non-destructive)"}


from pydantic import BaseModel, Field


class PreviewNote(BaseModel):
    midi_note: int = Field(ge=0, le=127)
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    velocity: int = Field(default=100, ge=1, le=127)


class InstrumentPreviewRequest(BaseModel):
    soundfont_asset_id: str | None = None
    bank: int = 0
    program: int = Field(default=0, ge=0, le=127)
    is_drum_kit: bool = False
    synth_patch: str = ""          # built-in synth patch id (bypasses FluidSynth)
    bpm: float = Field(default=120, gt=20, lt=400)
    notes: list[PreviewNote] = Field(max_length=512)


def _preview_with_synth(req: "InstrumentPreviewRequest") -> FileResponse:
    """Audition a built-in synth patch — no FluidSynth/SoundFont required."""
    import uuid as _uuid

    import numpy as np

    from ..services.audio_io import write_wav
    from ..services.render import synth_engine

    patch_id = req.synth_patch or (req.soundfont_asset_id or "").split("synth:")[-1]
    if req.is_drum_kit:
        patch_id = "drum_kit"
    patch = synth_engine.get_patch(patch_id) or synth_engine.get_patch("keys_piano")
    sr = synth_engine.SAMPLE_RATE
    spb = 60.0 / req.bpm
    end_beat = max((n.start_beat + n.duration_beats for n in req.notes), default=1)
    total = int((end_beat * spb + 2.0) * sr)
    out = np.zeros(total, dtype=np.float32)
    for n in req.notes:
        start = int(n.start_beat * spb * sr)
        mono = synth_engine.render_note(patch, n.midi_note,
                                        n.duration_beats * spb, n.velocity, sr)
        hi = min(start + len(mono), total)
        out[start:hi] += mono[:hi - start]
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out /= peak
    cache = get_config().analysis_cache_dir / "previews"
    cache.mkdir(parents=True, exist_ok=True)
    wav_path = cache / f"{_uuid.uuid4().hex[:12]}.wav"
    write_wav(wav_path, out.reshape(-1, 1), sr)
    return FileResponse(wav_path, media_type="audio/wav", filename="preview.wav")


@router.post("/preview/instrument")
def preview_instrument(req: InstrumentPreviewRequest) -> FileResponse:
    """Render a short pattern to audition an instrument, loopable in the
    browser. Built-in synth patches render directly (no FluidSynth needed);
    SoundFont presets render through FluidSynth with the exact preset."""
    import subprocess
    import uuid as _uuid

    import mido

    from ..services import asset_repo
    from ..services.capabilities import fluidsynth_path
    from ..services.render.soundfont_renderer import SAMPLE_RATE, _resolve_soundfont
    from ..models.song import Track

    if not req.notes:
        raise HTTPException(422, "no notes to preview")
    if req.synth_patch or (req.soundfont_asset_id or "").startswith("synth:"):
        return _preview_with_synth(req)

    fs = fluidsynth_path()
    if fs is None:
        raise HTTPException(503, "FluidSynth not installed — previews unavailable")
    if not req.notes:
        raise HTTPException(422, "no notes to preview")

    # resolve the soundfont (explicit asset or smart fallback per track type)
    track = Track(name="preview",
                  track_type="drums" if req.is_drum_kit else "keys")
    track.instrument_config.soundfont_asset_id = req.soundfont_asset_id
    track.instrument_config.bank = req.bank
    track.instrument_config.program = req.program
    track.instrument_config.is_drum_kit = req.is_drum_kit
    asset, _warnings = _resolve_soundfont(track)
    if asset is None:
        raise HTTPException(503, "no SoundFont available")

    mid = mido.MidiFile(ticks_per_beat=480)
    t = mido.MidiTrack()
    mid.tracks.append(t)
    t.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(req.bpm), time=0))
    channel = 9 if req.is_drum_kit else 0
    if not req.is_drum_kit and 0 < req.bank < 128:
        t.append(mido.Message("control_change", control=0, value=req.bank,
                              channel=channel, time=0))
    # drums too: the program selects WHICH kit inside bank 128
    t.append(mido.Message("program_change", program=req.program,
                          channel=channel, time=0))
    events = []
    for n in req.notes:
        on = round(n.start_beat * 480)
        off = round((n.start_beat + n.duration_beats) * 480)
        events.append((on, 1, mido.Message("note_on", note=n.midi_note,
                                           velocity=n.velocity, channel=channel, time=0)))
        events.append((max(off, on + 1), 0, mido.Message("note_off", note=n.midi_note,
                                                         velocity=0, channel=channel, time=0)))
    events.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for tick, _, msg in events:
        msg.time = tick - last
        t.append(msg)
        last = tick

    cache = get_config().analysis_cache_dir / "previews"
    cache.mkdir(parents=True, exist_ok=True)
    uid = _uuid.uuid4().hex[:12]
    midi_path = cache / f"{uid}.mid"
    wav_path = cache / f"{uid}.wav"
    mid.save(str(midi_path))
    proc = subprocess.run([fs, "-ni", "-g", "0.8", "-r", str(SAMPLE_RATE),
                           "-F", str(wav_path), str(asset.original_path),
                           str(midi_path)],
                          capture_output=True, text=True, timeout=60)
    midi_path.unlink(missing_ok=True)
    if proc.returncode != 0 or not wav_path.exists():
        raise HTTPException(500, "preview render failed")
    return FileResponse(wav_path, media_type="audio/wav",
                        filename="preview.wav")


@router.get("/{project_id}/stems/{track_id}/file")
def serve_stem(project_id: str, track_id: str, stem_type: str | None = None) -> FileResponse:
    project = _load(project_id)
    stems = [s for s in project.stems if s.track_id == track_id]
    if stem_type:
        stems = [s for s in stems if s.stem_type == stem_type]
    if not stems:
        raise HTTPException(404, "stem not found")
    path = get_config().root / stems[0].path
    if not path.exists():
        raise HTTPException(410, "stem file missing on disk")
    return FileResponse(path, media_type="audio/wav", filename=path.name)
