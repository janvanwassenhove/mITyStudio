# mITyStudio

A local-first AI music generation studio: chat plans structured song data,
the backend validates it, rendering engines turn it into MIDI, SoundFont
instrument stems, sample stems, (mock) vocal stems, effects, a synchronized
multitrack timeline with karaoke lyrics — and a combined WAV/MP3 export.

**Core principle:** the LLM never generates audio. It emits structured
operations; the backend validates them against the asset registry; renderers
produce the sound.

## Quick start

```powershell
.\run-backend.ps1     # FastAPI on http://127.0.0.1:8000 (docs at /docs)
.\run-frontend.ps1    # Vue studio on http://localhost:5173
.\run-tests.ps1       # pytest + vue-tsc
```

Optional but recommended: **FluidSynth** on PATH (SoundFont rendering) and
**ffmpeg** on PATH (MP3 export + wide audio decoding).

## Typical workflow

1. Drop `.sf2` files in `soundfonts/`, audio in `samples/`, scores in
   `scores/` → Asset Library → **Rescan**.
2. Create a project, then chat: *“create a punk song called Basement Nights
   at 168 bpm in E minor”*, *“add lyrics about basement shows”*.
3. Export tab → **Render all stems** → **Export combined song** (WAV/MP3).
4. Play in the timeline; karaoke tab highlights lyrics in sync.
5. **Export project package** for a ZIP with project JSON, lyrics + timing,
   MIDI, stems and final mixes.

The chat uses a deterministic mock planner out of the box (no API key).
Configure a real LLM (Anthropic) under Settings; keys stay in a git-ignored
local file / environment variable.

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | stack choices, repo inventory |
| [docs/project-structure.md](docs/project-structure.md) | folder layout, data ownership |
| [docs/local-development.md](docs/local-development.md) | dev setup, tests |
| [docs/assets.md](docs/assets.md) | asset registry, scanning rules |
| [docs/song-model.md](docs/song-model.md) | SongProject + PlaybackManifest |
| [docs/rendering.md](docs/rendering.md) | MIDI/stem/effects pipeline |
| [docs/voice-model.md](docs/voice-model.md) | voice safety, consent, engine contract |
| [docs/export.md](docs/export.md) | mix + package export |
| [docs/troubleshooting.md](docs/troubleshooting.md) | common issues |

## Status (v1)

Works end-to-end: asset scanning (3k+ samples), chat song creation, MIDI
export, FluidSynth instrument stems, sample stems, mock vocal stems with
karaoke timing, effects (gain/pan/delay/reverb/distortion), mixer, combined
WAV+MP3 export, package export. Mocked/placeholder: singing voice (tone
synth), EQ/compressor, MusicXML/GuitarPro/MuseScore import. See the docs for
the full list of limitations.
