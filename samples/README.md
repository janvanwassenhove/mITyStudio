# Samples Directory

Place your audio samples (`.wav`, `.mp3`, `.flac`) in this directory. They are
**not** shipped with the project — add your own after installation.

## How it works

- Drop sample files here (subfolders are fine).
- In the app, open **Assets → Samples** and click **Rescan folders**, then
  **Auto-tag all samples** to analyse BPM, key and type so they become
  searchable in the Samples browser and usable on sample tracks.
- Analysis results are cached in `analysis-cache/` and a generated
  `sample_metadata.json` — both are local-only and git-ignored.

## Where to find free samples

- **Freesound** — https://freesound.org (check each license)
- **Cymatics free packs** — https://cymatics.fm/pages/free-download-vault
- **Looperman** — https://www.looperman.com (loops & one-shots)

Only add samples you have the right to use. Nothing in this folder is tracked
by git except this README.
