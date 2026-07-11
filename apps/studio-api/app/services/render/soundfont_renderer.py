"""InstrumentRenderer: MIDI + SoundFont → WAV stem via the FluidSynth CLI.

Missing FluidSynth or a missing SoundFont produces a clear per-track error,
never a crash. Tracks without an explicit SoundFont fall back to the first
available one (documented behavior; a General-MIDI bank works best).
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from ...config import get_config
from ...models.asset import Asset
from ...models.song import SongProject, StemRef, Track
from .. import asset_repo, midi_export
from ..capabilities import fluidsynth_path

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100


class InstrumentRenderer(ABC):
    @abstractmethod
    def render_track(self, project: SongProject, track: Track,
                     midi_path: Path, out_path: Path) -> list[str]:
        """Render one track to a WAV file. Returns warnings."""


# bump when a rendering engine changes so cached stems re-render
ENGINE_VERSION = "7"


def track_fingerprint(project: SongProject, track: Track) -> str:
    """Hash of everything that affects a track's rendered audio."""
    h = hashlib.sha256()
    h.update(ENGINE_VERSION.encode())
    h.update(f"{project.bpm}:{project.time_signature}".encode())
    h.update(track.model_dump_json(exclude={"volume", "pan", "mute", "solo"}).encode())
    return h.hexdigest()[:16]


def _resolve_soundfont(track: Track) -> tuple[Asset | None, list[str]]:
    warnings: list[str] = []
    sf_id = track.instrument_config.soundfont_asset_id
    if sf_id:
        asset = asset_repo.get_asset(sf_id)
        if asset and not asset.is_missing:
            return asset, warnings
        warnings.append(f"soundfont {sf_id} unavailable; falling back")
    # smart matching: pick a font whose preset inventory suits the track type
    from ..sf2_parser import find_best_soundfont
    match = find_best_soundfont(track.track_type)
    if match is not None:
        asset, preset = match
        warnings.append(
            f"auto-matched soundfont {asset.filename!r} "
            f"(preset {preset['name']!r}, bank {preset['bank']}, "
            f"program {preset['program']})")
        return asset, warnings
    fallbacks = [a for a in asset_repo.list_assets("soundfont", include_missing=False)
                 if a.extension in (".sf2", ".sf3")]
    if not fallbacks:
        return None, warnings + ["no soundfont available in soundfonts/"]
    gm = next((a for a in fallbacks
               if any(k in a.filename.lower() for k in ("gm", "general", "fluidr3", "musescore"))),
              fallbacks[0])
    warnings.append(f"using fallback soundfont {gm.filename!r}")
    return gm, warnings


def auto_assign_soundfonts(project: SongProject) -> list[str]:
    """Assign the best-matching SoundFont preset to every instrument track
    that has none. Persists bank/program so MIDI export selects the right
    preset. Returns log messages."""
    from ..sf2_parser import find_best_soundfont
    log_msgs: list[str] = []
    for track in project.tracks:
        cfg = track.instrument_config
        if cfg.soundfont_asset_id or track.track_type in ("sample", "lead_vocal",
                                                          "backing_vocal"):
            continue
        match = find_best_soundfont(track.track_type)
        if match is None:
            continue
        asset, preset = match
        cfg.soundfont_asset_id = asset.id
        cfg.bank = preset["bank"]
        cfg.program = preset["program"]
        cfg.is_drum_kit = track.track_type == "drums"
        log_msgs.append(
            f"{track.name}: auto-assigned {asset.filename!r} → "
            f"{preset['name']!r} (bank {preset['bank']}, program {preset['program']})")
    return log_msgs


class SoundFontRenderer(InstrumentRenderer):
    def render_track(self, project: SongProject, track: Track,
                     midi_path: Path, out_path: Path) -> list[str]:
        fs = fluidsynth_path()
        if fs is None:
            raise RenderUnavailable(
                "FluidSynth is not installed or not on PATH. Install it "
                "(e.g. 'choco install fluidsynth') to render SoundFont stems.")
        soundfont, warnings = _resolve_soundfont(track)
        if soundfont is None:
            raise RenderUnavailable(
                "no SoundFont file found — place a .sf2 file in soundfonts/ "
                "and rescan assets")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [fs, "-ni", "-g", "0.7", "-r", str(SAMPLE_RATE),
               "-F", str(out_path), str(soundfont.original_path), str(midi_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 128:
            raise RenderFailed(
                f"FluidSynth failed for track {track.name!r}: "
                f"{(proc.stderr or proc.stdout).strip()[:400]}")
        return warnings


class RenderUnavailable(Exception):
    pass


class RenderFailed(Exception):
    pass


def render_instrument_stems(project: SongProject) -> dict:
    """Render all eligible instrument tracks to WAV stems."""
    cfg = get_config()
    renderer = SoundFontRenderer()
    results: dict = {"rendered": [], "skipped": [], "errors": [], "warnings": []}

    # smart preset matching happens BEFORE MIDI export so bank/program land
    # in the MIDI files
    results["warnings"].extend(auto_assign_soundfonts(project))
    midi_files = midi_export.export_project_midi(project, include_full_song=True)
    eligible = [t for t in midi_export.exportable_tracks(project)
                if t.track_type not in ("lead_vocal", "backing_vocal")]
    if not eligible:
        results["skipped"].append("no instrument tracks with MIDI content")
        return results

    stems_dir = cfg.stems_dir / project.id
    for track in eligible:
        midi_rel = midi_files.get(track.id)
        if not midi_rel:
            results["skipped"].append(f"{track.name}: no MIDI produced")
            continue
        fp = track_fingerprint(project, track)
        existing = next((s for s in project.stems
                         if s.track_id == track.id and s.stem_type == "instrument"), None)
        if existing and existing.source_fingerprint == fp \
                and (cfg.root / existing.path).exists():
            results["skipped"].append(f"{track.name}: up to date")
            continue
        out_path = stems_dir / f"{midi_export._safe_name(track.name)}_{track.id[:8]}.wav"
        try:
            warnings = renderer.render_track(project, track,
                                             cfg.root / midi_rel, out_path)
            results["warnings"].extend(f"{track.name}: {w}" for w in warnings)
        except (RenderUnavailable, RenderFailed) as e:
            results["errors"].append(f"{track.name}: {e}")
            continue
        from .clip_fades import apply_midi_clip_fades
        results["warnings"].extend(
            w for w in apply_midi_clip_fades(project, track, out_path)
            if "skipped" in w)
        rel = out_path.relative_to(cfg.root).as_posix()
        project.stems = [s for s in project.stems
                         if not (s.track_id == track.id and s.stem_type == "instrument")]
        stem = StemRef(track_id=track.id, stem_type="instrument", path=rel,
                       source_fingerprint=fp)
        _register_stem_asset(stem, track.name, "rendered_stem")
        project.stems.append(stem)
        results["rendered"].append({"track": track.name, "path": rel})

    from .waveforms import update_waveform_cache
    update_waveform_cache(project)
    return results


def _register_stem_asset(stem: StemRef, track_name: str, asset_type: str) -> None:
    from ...models.asset import Asset
    cfg = get_config()
    path = cfg.root / stem.path
    existing = asset_repo.get_asset_by_relative_path(stem.path)
    asset_id = existing.id if existing else uuid.uuid4().hex
    asset_repo.upsert_asset(Asset(
        id=asset_id, asset_type=asset_type,  # type: ignore[arg-type]
        filename=path.name, original_path=str(path), relative_path=stem.path,
        extension=path.suffix.lower(),
        file_size=path.stat().st_size if path.exists() else 0,
        source="render", generated_description=f"rendered stem for track {track_name!r}",
        analysis_status="not_applicable"))
    stem.asset_id = asset_id
