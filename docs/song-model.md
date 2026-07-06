# Song model & PlaybackManifest

## SongProject

Stored as `projects/{id}/project.json`. The single structured source of truth:
the LLM plans against it, renderers consume it, the UI visualizes it.

```
SongProject
├── id, title, style, bpm, key, time_signature
├── sections[]        Section: name, start_bar, length_bars, energy, description
├── tracks[]          Track
│   ├── track_type    drums|bass|guitar|keys|synth|strings|brass|sample|lead_vocal|backing_vocal|fx
│   ├── instrument_config   soundfont_asset_id, bank, program, is_drum_kit
│   ├── clips[]       Clip: clip_type midi|sample|vocal, start_beat, duration_beats
│   │   ├── note_events[]   NoteEvent: midi_note, pitch, start_beat (clip-relative),
│   │   │                   duration_beats, velocity, articulation, lyric_syllable
│   │   └── sample opts     source_asset_id, gain_db, loop, fade_in/out_seconds
│   ├── effects       EffectChain (gain|pan|eq|compressor|reverb|delay|distortion)
│   ├── volume, pan, mute, solo
│   └── voice_profile_id    (vocal tracks)
├── lyrics            LyricsDocument: language, lines[{section_id, text}]
├── source_assets[], mix_settings, render_status
├── stems[]           StemRef: track_id, stem_type, path, source_fingerprint
└── midi_files        track_id -> midi path
```

### Conventions

- All positions are in **beats** (floats) except sections, which are in bars.
- Note `start_beat` is **clip-relative**; the timing service produces absolute
  beat/second values.
- `pitch` is derived from `midi_note` if omitted.

### Validation

Two layers, both must pass before saving:
1. **Structural** (Pydantic): ranges (midi_note 0–127, velocity 1–127,
   bpm 20–400), time-signature format, notes within clip bounds,
   non-overlapping sections, unique track ids.
2. **Referential** (registry): soundfont/sample/voice-profile references must
   exist, be the right type and not be missing on disk.

## PlaybackManifest

`GET /api/projects/{id}/playback-manifest` returns everything the frontend
needs to draw and play the song — the frontend never computes timing itself.

Contains: bpm, time signature, beats_per_bar, total_bars, duration_seconds;
sections/clips/notes each with `start_seconds`/`end_seconds`; track list with
mixer state; stems; per-stem waveform peak metadata; lyrics alignment;
section markers; mix settings.

Timing math lives in `app/services/timing.py`
(bars→beats→seconds using bpm and time signature).

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/projects` | create |
| `GET /api/projects` | list summaries |
| `GET /api/projects/{id}` | full document |
| `PUT /api/projects/{id}` | replace (validated) |
| `POST /api/projects/{id}/validate` | referential validation report |
| `GET /api/projects/{id}/playback-manifest` | timing manifest |
