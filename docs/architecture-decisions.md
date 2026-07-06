# Architecture Decisions — mITyStudio

Date: 2026-07-06 (Phase 0)

## Repository inventory (as found)

| Folder | Contents |
|---|---|
| `scores/` | 2 files: `Linoleum Chords by NOFX.pdf` (reference only), `original.jpg` |
| `soundfonts/` | 196 `.sf2` files (~766 MB) + `README.md` |
| `samples/` | 2969 `.wav` files (~5.1 GB, flat folder) + legacy `sample_metadata.json` (stale absolute paths `C:/sounds/samples`) |
| `midi/` | empty |
| `projects/` | empty |
| `stems/` | empty |
| `voices/`, `exports/`, `analysis-cache/`, `docs/`, `apps/` | **missing — to be created** |

No existing frontend/backend code. Not a git repository.

## Environment

- Windows 11, PowerShell
- Python 3.12.8, Node 22.17.0 / npm 10.9.2
- **FluidSynth** available on PATH (`C:\ProgramData\chocolatey\bin\fluidsynth.exe`)
- **ffmpeg** available on PATH → MP3 encoding is available

## Key decisions

### AD-01: Backend — FastAPI + Pydantic v2 + stdlib sqlite3
FastAPI for the API layer, Pydantic v2 for all domain models and validation.
SQLite via the stdlib `sqlite3` module (no ORM) — the schema is small (assets,
settings, voice profiles, export jobs); raw SQL keeps dependencies minimal.

### AD-02: Projects stored as JSON files, indexed in SQLite
`SongProject` documents live as JSON files in `projects/{project_id}/project.json`
(local-first, human-readable, trivially exportable). SQLite stores the asset
registry and other tabular data. Project listing reads the projects folder.

### AD-03: SoundFont rendering via FluidSynth CLI subprocess
`fluidsynth -ni <sf2> <mid> -F <wav> -r 44100` per instrument track.
Subprocess (not pyfluidsynth ctypes bindings) — more robust on Windows, no
DLL-loading issues, easy to detect absence and fail gracefully.

### AD-04: MIDI via `mido`
`mido` (maintained, pure Python) for MIDI import and export.

### AD-05: Audio I/O via `soundfile` + `numpy`; MP3 via ffmpeg subprocess
`soundfile` (libsndfile) reads/writes WAV/FLAC/OGG (and MP3 with recent
libsndfile). Mixing, gain, pan, fades, normalization are numpy operations at
44.1 kHz stereo float32. MP3 encode/decode falls back to ffmpeg subprocess.
No heavy DSP frameworks in v1.

### AD-06: Sample analysis — lightweight numpy + filename heuristics, no librosa
RMS, peak, duration, channels, silence detection via numpy. BPM/key are first
taken from filename conventions (the library uses names like `... - 140 BPM.wav`,
`808 3 - D#.wav`); a simple autocorrelation BPM estimate is attempted for the
rest. Where unreliable → `null` + warning, per spec. librosa/numba deliberately
avoided (heavy install, slow import, not needed for v1). `analysis_version`
field allows future re-analysis.

### AD-07: Effects v1 — pure numpy DSP
gain, pan, simple feedback delay, Schroeder-style reverb, tanh distortion.
EQ and compressor are documented placeholders (identity + warning) in v1.

### AD-08: Voice — mock engine only, consent-gated profiles
`SingingVoiceEngine` interface with `MockSingingVoiceEngine` that synthesizes
a simple sine/formant tone per melody note (not silence — audible in mixes) and
emits exact lyric timing metadata. Voice profiles require an explicit consent
flag; recordings never auto-become profiles.

### AD-09: LLM — provider interface, mock first
`LlmProvider` interface; `MockLlmProvider` produces deterministic structured
operations. Real adapter (Anthropic) added in Phase 22 behind the same
interface. API keys via environment variables / local settings file
(`.gitignore`d), never committed. The LLM emits `ChatOperation` JSON only;
the backend validates every operation against the asset registry before
applying. The LLM never touches files or audio.

### AD-10: Frontend — Vue 3 + TypeScript + Vite + Pinia + vue-router
Scaffolded manually (no interactive generator). Type check via `vue-tsc`.

### AD-11: Timing is backend-owned
All bar/beat/second math lives in a backend timing service; the frontend
consumes a `PlaybackManifest` and never guesses timing.

### AD-12: Original assets are immutable
Scanner and analysis never modify files under `scores/`, `soundfonts/`,
`samples/`, `voices/`. All generated metadata lives in SQLite /
`analysis-cache/`. Missing files are flagged (`is_missing`), never deleted
from the registry. Legacy `samples/sample_metadata.json` is left untouched
(its paths are stale); the new registry supersedes it.

## Final folder structure

```
apps/studio-api/      FastAPI backend (app/, tests/)
apps/studio-ui/       Vue 3 + TS frontend
scores/ soundfonts/ samples/ voices/{recordings,profiles}/
projects/ stems/ midi/ exports/ analysis-cache/ docs/
```

## Python dependencies (all real, maintained)

fastapi, uvicorn[standard], pydantic, mido, soundfile, numpy, python-multipart,
pytest, httpx, anthropic (Phase 22, optional at runtime)

## Frontend dependencies

vue, vue-router, pinia, typescript, vite, @vitejs/plugin-vue, vue-tsc
