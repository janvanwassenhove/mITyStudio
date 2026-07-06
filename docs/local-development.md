# Local development

## Prerequisites

- Python 3.11+ (3.12 tested)
- Node 20+ (22 tested)
- Optional but recommended:
  - **FluidSynth** on PATH — required for SoundFont instrument rendering
    (`choco install fluidsynth` on Windows)
  - **ffmpeg** on PATH — required for MP3 export and decoding non-WAV audio

## Backend (FastAPI)

```powershell
cd apps/studio-api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Health check: http://127.0.0.1:8000/api/health
API docs (Swagger): http://127.0.0.1:8000/docs

### Backend tests

```powershell
cd apps/studio-api
.venv\Scripts\python -m pytest tests -q
```

Tests run against an isolated temp workspace (via the `MITY_ROOT` env var) —
they never touch your real assets.

## Frontend (Vue 3 + Vite)

```powershell
cd apps/studio-ui
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
npm run typecheck  # vue-tsc
npm run build      # production build
```

## Workspace root

All asset folders (`scores/`, `soundfonts/`, `samples/`, `voices/`, …) live at
the repository root. The backend auto-detects the root from its own location;
set `MITY_ROOT` to override.

## Secrets

LLM API keys are stored in `apps/studio-api/local_settings.json`
(git-ignored) or environment variables. Never commit keys.
