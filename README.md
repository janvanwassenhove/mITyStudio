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
Under Settings you can switch to **Anthropic (Claude)**, **OpenAI (GPT)**, or
**any OpenAI-compatible provider** (OpenRouter, Groq, Mistral, DeepSeek,
local Ollama/LM Studio) via a custom base URL — bring your own key per
provider. Keys stay in a git-ignored local file or come from
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` env vars. See
[docs/llm-providers.md](docs/llm-providers.md).

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | stack choices, repo inventory |
| [docs/project-structure.md](docs/project-structure.md) | folder layout, data ownership |
| [docs/local-development.md](docs/local-development.md) | dev setup, tests |
| [docs/assets.md](docs/assets.md) | asset registry, scanning rules |
| [docs/song-model.md](docs/song-model.md) | SongProject + PlaybackManifest |
| [docs/rendering.md](docs/rendering.md) | MIDI/stem/effects pipeline |
| [docs/llm-providers.md](docs/llm-providers.md) | Claude/GPT/custom providers, key storage |
| [docs/voice-model.md](docs/voice-model.md) | voice safety, consent, engine contract |
| [docs/export.md](docs/export.md) | mix + package export |
| [docs/troubleshooting.md](docs/troubleshooting.md) | common issues |

## Status (v1.1 — "full blown")

Works end-to-end: asset scanning (3k+ samples), chat song creation, MIDI
export with bank/program selection, FluidSynth instrument stems with **smart
SoundFont preset matching** (parses all .sf2 preset headers, picks a real
drum kit / bass / guitar preset per track), sample stems, **formant-synthesis
vocals** (audible vowels from lyric syllables) with karaoke timing, **seven
real effects** (gain, pan, 3-band EQ, compressor, reverb, delay, distortion),
master bus effects, mixer with master strip, **MusicXML/.mxl and Guitar Pro
(.gp3/.gp4/.gp5) import**, sample pitch detection, track inspector with
SoundFont/preset picker and effects editor, in-studio sample browser,
combined WAV+MP3 export, package export. Chat planning runs on the mock
planner, **Anthropic**, **OpenAI** (verified live), or any OpenAI-compatible
endpoint with your own key.

Still simplified: the singing voice is synthetic (formant tones, no cloning —
by design until a consented real engine is integrated), .gpx (GP6) and .mscz
need re-export, live playback requires rendered stems (no realtime synth in
the browser).
