"""SongProject domain model — the structured song representation that the
LLM plans against, renderers consume, and the UI visualizes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TrackType = Literal["drums", "bass", "guitar", "keys", "synth", "strings",
                    "brass", "sample", "lead_vocal", "backing_vocal", "fx"]

INSTRUMENT_TRACK_TYPES = {"drums", "bass", "guitar", "keys", "synth",
                          "strings", "brass", "fx"}
VOCAL_TRACK_TYPES = {"lead_vocal", "backing_vocal"}

ClipType = Literal["midi", "sample", "vocal"]

EffectType = Literal["gain", "pan", "eq", "compressor", "reverb", "delay",
                     "distortion"]

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def midi_to_pitch_name(midi_note: int) -> str:
    return f"{_NOTE_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


class NoteEvent(BaseModel):
    id: str = Field(default_factory=new_id)
    pitch: str = ""                      # e.g. "C4"; derived from midi_note if empty
    midi_note: int = Field(ge=0, le=127)
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    velocity: int = Field(default=96, ge=1, le=127)
    articulation: str = ""
    lyric_syllable: str = ""

    @model_validator(mode="after")
    def _fill_pitch(self) -> "NoteEvent":
        if not self.pitch:
            self.pitch = midi_to_pitch_name(self.midi_note)
        return self


class Clip(BaseModel):
    id: str = Field(default_factory=new_id)
    section_id: str = ""
    clip_type: ClipType = "midi"
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    note_events: list[NoteEvent] = Field(default_factory=list)
    source_asset_id: str | None = None   # sample asset for sample clips
    # sample clip playback options
    gain_db: float = 0.0
    loop: bool = False
    fade_in_seconds: float = Field(default=0.0, ge=0)
    fade_out_seconds: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _check(self) -> "Clip":
        if self.clip_type == "sample" and not self.source_asset_id:
            raise ValueError("sample clip requires source_asset_id")
        for n in self.note_events:
            if n.start_beat >= self.duration_beats:
                raise ValueError(
                    f"note {n.id} starts at beat {n.start_beat}, beyond clip "
                    f"duration {self.duration_beats}")
        return self


class Effect(BaseModel):
    id: str = Field(default_factory=new_id)
    effect_type: EffectType
    enabled: bool = True
    params: dict[str, float] = Field(default_factory=dict)


class EffectChain(BaseModel):
    effects: list[Effect] = Field(default_factory=list)


class InstrumentConfig(BaseModel):
    soundfont_asset_id: str | None = None
    bank: int = 0
    program: int = Field(default=0, ge=0, le=127)  # General MIDI program
    is_drum_kit: bool = False                       # route to MIDI channel 10


class Track(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    track_type: TrackType
    instrument_config: InstrumentConfig = Field(default_factory=InstrumentConfig)
    clips: list[Clip] = Field(default_factory=list)
    effects: EffectChain = Field(default_factory=EffectChain)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    mute: bool = False
    solo: bool = False
    # vocal tracks
    voice_profile_id: str | None = None


class Section(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    start_bar: int = Field(ge=0)
    length_bars: int = Field(gt=0)
    energy: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = ""


class LyricsLine(BaseModel):
    id: str = Field(default_factory=new_id)
    section_id: str = ""
    text: str


class LyricsDocument(BaseModel):
    id: str = Field(default_factory=new_id)
    language: str = "en"
    lines: list[LyricsLine] = Field(default_factory=list)

    def sections(self) -> list[str]:
        return sorted({l.section_id for l in self.lines if l.section_id})


class MixSettings(BaseModel):
    master_volume: float = Field(default=1.0, ge=0.0, le=2.0)
    normalize: bool = True
    limiter: bool = True
    master_effects: EffectChain = Field(default_factory=EffectChain)


class StemRef(BaseModel):
    """A rendered stem registered on the project."""
    track_id: str
    stem_type: Literal["instrument", "sample", "vocal"]
    path: str                 # relative to workspace root
    asset_id: str | None = None
    rendered_at: str = Field(default_factory=now_iso)
    source_fingerprint: str = ""   # hash of track content when rendered


class SongProject(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    style: str = ""
    bpm: float = Field(default=120.0, gt=20, lt=400)
    key: str = "C major"
    time_signature: str = "4/4"
    sections: list[Section] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)
    lyrics: LyricsDocument = Field(default_factory=LyricsDocument)
    source_assets: list[str] = Field(default_factory=list)
    mix_settings: MixSettings = Field(default_factory=MixSettings)
    render_status: str = "not_rendered"
    stems: list[StemRef] = Field(default_factory=list)
    midi_files: dict[str, str] = Field(default_factory=dict)  # track_id -> rel path
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @field_validator("time_signature")
    @classmethod
    def _check_ts(cls, v: str) -> str:
        parts = v.split("/")
        if len(parts) != 2 or not all(p.isdigit() and int(p) > 0 for p in parts):
            raise ValueError(f"invalid time signature {v!r}, expected e.g. '4/4'")
        return v

    @model_validator(mode="after")
    def _check_structure(self) -> "SongProject":
        section_ids = {s.id for s in self.sections}
        track_ids = set()
        for t in self.tracks:
            if t.id in track_ids:
                raise ValueError(f"duplicate track id {t.id}")
            track_ids.add(t.id)
            for c in t.clips:
                if c.section_id and c.section_id not in section_ids:
                    raise ValueError(
                        f"clip {c.id} on track {t.name!r} references unknown "
                        f"section {c.section_id}")
        # overlapping sections
        spans = sorted((s.start_bar, s.start_bar + s.length_bars, s.name)
                       for s in self.sections)
        for (a_start, a_end, a_name), (b_start, _, b_name) in zip(spans, spans[1:]):
            if b_start < a_end:
                raise ValueError(
                    f"sections {a_name!r} and {b_name!r} overlap")
        return self

    @property
    def beats_per_bar(self) -> float:
        num, den = self.time_signature.split("/")
        return int(num) * 4.0 / int(den)

    def total_bars(self) -> int:
        by_sections = max((s.start_bar + s.length_bars for s in self.sections),
                          default=0)
        bpb = self.beats_per_bar
        by_clips = 0
        for t in self.tracks:
            for c in t.clips:
                end_bar = (c.start_beat + c.duration_beats) / bpb
                by_clips = max(by_clips, int(end_bar) + (end_bar % 1 > 0))
        return max(by_sections, by_clips)

    def duration_beats(self) -> float:
        return self.total_bars() * self.beats_per_bar

    def duration_seconds(self) -> float:
        return self.duration_beats() * 60.0 / self.bpm

    def get_track(self, track_id: str) -> Track | None:
        return next((t for t in self.tracks if t.id == track_id), None)

    def get_section(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.id == section_id), None)

    def touch(self) -> None:
        self.updated_at = now_iso()
