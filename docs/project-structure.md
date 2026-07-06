# Project structure

```
mITyStudio2/
├── apps/
│   ├── studio-api/          # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py      # app factory + health endpoint
│   │   │   ├── config.py    # workspace paths (MITY_ROOT override)
│   │   │   ├── db.py        # SQLite (asset registry, settings, profiles, jobs)
│   │   │   ├── models/      # Pydantic domain models
│   │   │   ├── services/    # scanner, timing, renderers, effects, export…
│   │   │   └── api/         # FastAPI routers
│   │   └── tests/
│   └── studio-ui/           # Vue 3 + TypeScript frontend (Vite)
│       └── src/
│           ├── api/         # typed API client
│           ├── components/  # studio components
│           ├── stores/      # Pinia stores
│           └── views/       # routed views
├── scores/                  # user score files (MIDI, MusicXML, GP, PDF…) — never modified
├── soundfonts/              # user .sf2/.sf3 files — never modified
├── samples/                 # user audio samples — never modified
├── voices/
│   ├── recordings/          # uploaded / live-recorded voice audio
│   └── profiles/            # voice profile data (consent-gated)
├── projects/                # one folder per SongProject (project.json + outputs)
├── stems/                   # rendered audio stems per project
├── midi/                    # exported MIDI per project
├── exports/                 # final WAV/MP3 mixes and packages per project
├── analysis-cache/          # SQLite DB + generated analysis (safe to delete)
└── docs/
```

## Data ownership rules

- Files in `scores/`, `soundfonts/`, `samples/`, `voices/recordings/` are
  **user originals**: the studio reads them, never writes, moves or renames.
- Everything the studio generates goes to `projects/`, `stems/`, `midi/`,
  `exports/`, `analysis-cache/`.
- Deleting `analysis-cache/` loses generated metadata (tags, analyses,
  registry) but never original files.
