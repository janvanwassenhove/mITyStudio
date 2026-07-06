"""Central configuration: workspace paths and settings.

The workspace root is the repository root containing scores/, soundfonts/,
samples/, voices/, projects/, stems/, midi/, exports/, analysis-cache/.
Override with the MITY_ROOT environment variable (used by tests).
"""
from __future__ import annotations

import os
from pathlib import Path


def _detect_root() -> Path:
    env = os.environ.get("MITY_ROOT")
    if env:
        return Path(env).resolve()
    # this file lives at <root>/apps/studio-api/app/config.py
    return Path(__file__).resolve().parents[3]


class Config:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _detect_root()).resolve()

    @property
    def scores_dir(self) -> Path: return self.root / "scores"
    @property
    def soundfonts_dir(self) -> Path: return self.root / "soundfonts"
    @property
    def samples_dir(self) -> Path: return self.root / "samples"
    @property
    def voices_dir(self) -> Path: return self.root / "voices"
    @property
    def voice_recordings_dir(self) -> Path: return self.root / "voices" / "recordings"
    @property
    def projects_dir(self) -> Path: return self.root / "projects"
    @property
    def stems_dir(self) -> Path: return self.root / "stems"
    @property
    def midi_dir(self) -> Path: return self.root / "midi"
    @property
    def exports_dir(self) -> Path: return self.root / "exports"
    @property
    def analysis_cache_dir(self) -> Path: return self.root / "analysis-cache"
    @property
    def db_path(self) -> Path: return self.analysis_cache_dir / "studio.db"
    @property
    def local_settings_path(self) -> Path:
        return Path(__file__).resolve().parents[1] / "local_settings.json"

    def ensure_dirs(self) -> None:
        for d in (self.scores_dir, self.soundfonts_dir, self.samples_dir,
                  self.voice_recordings_dir, self.voices_dir / "profiles",
                  self.projects_dir, self.stems_dir, self.midi_dir,
                  self.exports_dir, self.analysis_cache_dir):
            d.mkdir(parents=True, exist_ok=True)


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
        _config.ensure_dirs()
    return _config


def reset_config() -> None:
    """Testing hook: force re-detection of MITY_ROOT."""
    global _config
    _config = None
