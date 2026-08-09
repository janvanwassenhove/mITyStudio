---
name: desktop-release
description: Cut a mITyStudio desktop release and verify or repair its auto-update chain. Use whenever shipping a new version of this app, bumping the version, publishing a build, or debugging updates that fail for installed users ("update failed"/"update mislukt", stuck on an old version, the About box showing mismatched app/UI versions). Covers this repo's CI workflow, electron-builder config, the ask-first updater, and the packaging guard test.
---

# mITyStudio desktop release

The release procedure for **this repo**. For the general Electron/
electron-updater theory (and the same traps in other projects), see the
`electron-auto-update` skill; this one is about our concrete setup.

Key paths:
- `.github/workflows/release-windows.yml` — builds + publishes on push to master
- `apps/desktop/package.json` — version intent + electron-builder config
- `apps/desktop/electron/updater.js` — ask-first update flow
- `apps/studio-ui/src/composables/updates.ts` + `App.vue` — the update banner
- `apps/studio-api/tests/test_release_packaging.py` — the guard test

---

## Shipping a version

CI publishes on **every push to master** (paths-ignore `**.md`, `docs/**`),
so shipping is usually just merging. The version is assembled in two places:

- `apps/desktop/package.json` `version` holds the **MAJOR.MINOR intent** —
  bump it by hand when features or breaking changes land.
- CI stamps the patch from the run number: `VERSION = MAJ.MIN.<run_number>`,
  applied with `npm version` **before** electron-builder runs, so installer,
  `latest.yml`, tag and release title all match.

Never hand-edit the patch number; it will collide with the run number.

The release must carry three assets: `*.exe`, `*.exe.blockmap`, `latest.yml`.

---

## Verify a release actually updates

Auto-update fails silently, so check the exact URL the updater follows:

```bash
curl -sL https://github.com/janvanwassenhove/mITyStudio/releases/latest/download/latest.yml
```

Then confirm the filename it names returns **200**:

```bash
curl -sIL -o /dev/null -w "%{http_code}\n" \
  "https://github.com/janvanwassenhove/mITyStudio/releases/download/vX.Y.Z/<name-from-latest.yml>"
```

A 404 means the filename trap is back — see below.

**Then check the app's own report**: the About box (ℹ in the title bar) shows
app version, UI build and backend build. If they disagree, the update only
half-applied.

---

## The trap this repo already hit

electron-builder's default `artifactName` contains **spaces**. GitHub stores
the asset with spaces→**dots** while electron-builder writes spaces→**hyphens**
into `latest.yml`, so the updater 404s and every update fails. This broke
every auto-update from the first release until it was found (fix: 45fbef6).

`apps/desktop/package.json` therefore pins, in **both** places:

```json
"artifactName": "mITyStudio-Setup-${version}.${ext}",
"nsis": { "artifactName": "mITyStudio-Setup-${version}.${ext}" }
```

`tests/test_release_packaging.py` fails if that ever regresses — it also
asserts `publish.provider == "github"` and
`nsis.deleteAppDataOnUninstall is False` (in-place updates must keep the
user's workspace: projects, soundfonts, samples, voices).

**Lasting caveat:** releases published before the fix keep their broken
`latest.yml`. A user on one of those needs **one manual install**; auto-update
works on its own afterwards. Say so when handing over a release.

---

## The updater flow here

`updater.js` is deliberately **ask-first** (`autoDownload = false`): it checks
on startup and every 4h, tells the renderer, and only downloads/installs when
the user clicks. The banner in `App.vue` has four states (available →
downloading % → restart & install → error), dismisses per version, prints the
real error text, and on failure links to the release page instead of retrying
the same download.

`canSelfUpdate()` keys off the **preload bridge**, not the user agent — an
Electron-embedded browser without the bridge must get the "view release" path.

Browser/dev builds use `GET /api/updates/check` (backend compares the latest
GitHub tag to `MITY_APP_VERSION`, 1h cache, silent when offline, never nags
from a dev build).

---

## Two backends share this machine

When an update seems not to have taken, first establish **which backend is
running**: the desktop app runs its own bundled venv
(`%APPDATA%/mITyStudio/venv`) while dev work runs the repo venv. A stale
desktop install serves old code even after a "reinstall". The About box
settles it.
