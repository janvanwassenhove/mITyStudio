# Desktop app (Electron)

## Architecture

```
apps/desktop/
├── electron/main.js       boot: splash → first-run setup → bootstrap → backend → window
├── electron/bootstrap.js  first-run env: venv from bundled Python, core deps,
│                          ffmpeg/FluidSynth download (win), workspace seed
├── electron/backend.js    spawns uvicorn from the per-machine venv, health-gated
├── electron/updater.js    electron-updater against GitHub Releases
├── splash.html/setup.html boot UI + first-run workspace picker
└── build/                 icon, mac entitlements, notarize hook (TODO-gated)
```

**Deliberate design (per Phase 0 findings):** no PyInstaller sidecar. The
installer ships a *minimal* Python runtime (python-build-standalone) plus the
backend source; the **first run creates a venv in the user profile and pip-
installs the core dependencies** (~1–2 min). This keeps installers small,
solves the CUDA/MPS/CPU torch-wheel problem per machine instead of per
installer, and works with Applio's checkout-plus-own-venv layout.

Tiers installed per machine:
1. **Core** (first run, automatic): FastAPI backend, rendering, samples,
   PSOLA/WORLD vocals. Everything works except neural voice.
2. **Voice AI** (on demand): torch matched to the detected device
   (`nvidia-smi` → cu124 index; Apple Silicon → default wheels with MPS;
   else CPU) + `requirements-voice.txt` (XTTS stack), then Applio for
   training. Device detection is surfaced honestly in the splash:
   “GPU found — fast training available” vs the CPU warning.

Audio tools: on Windows the bootstrap downloads ffmpeg (gyan.dev) and
FluidSynth (GitHub release) into the profile and passes
`MITY_FFMPEG_PATH`/`MITY_FLUIDSYNTH_PATH` to the backend; on macOS it uses
PATH and tells the user to `brew install ffmpeg fluidsynth` when missing.

The backend serves the built frontend itself (`MITY_UI_DIST`) so the window
is a single origin — no CORS, no proxy.

## Building

```powershell
# local dev shell (uses the repo venv + built UI)
cd apps/studio-ui && npm run build
cd ../desktop && npm install && npm run dev

# local unpacked build (no installer): npm run dist:dir
# full installers: npm run dist  (needs runtime/ + seed/, see CI)
```

CI (`.github/workflows/release.yml`): tag `v*` → matrix build on
`windows-latest` + `macos-latest` → downloads the Python runtime and the seed
GM soundfont → `electron-builder --publish always` attaches `.exe`/`.dmg` to
the GitHub Release → auto-generated release notes. `electron-updater` checks
the same Releases feed at app start.

## Manual prerequisites (flagged, not automatable)

- **Windows code signing**: paid OV/EV certificate → set `CSC_LINK` +
  `CSC_KEY_PASSWORD` secrets. Unsigned builds trigger SmartScreen
  “unknown publisher” until reputation accrues.
- **macOS notarization**: paid Apple Developer account → set `APPLE_ID`,
  `APPLE_APP_PASSWORD`, `APPLE_TEAM_ID` secrets and add `@electron/notarize`;
  the `build/notarize.js` hook activates automatically. Unnotarized builds
  need right-click → Open.

## Known-unverified: macOS

The `.dmg` builds in CI, but **MPS behavior of the RVC/XTTS stack has not
been exercised on real Mac hardware** — PyTorch MPS support for these
workloads can silently fall back to CPU. Treat Mac voice *training* as
unvalidated until tested on an actual machine; core studio + inference are
expected to work but carry the same caveat. (Development machine is
Windows/NVIDIA.)
