# Asset Library

The asset registry (SQLite, `analysis-cache/studio.db`) tracks every musical
asset in the workspace. **Original files are never modified, moved or renamed.**

## Asset types

`score`, `soundfont`, `sample`, `voice_recording`, `voice_profile`,
`rendered_stem`, `vocal_stem`, `exported_mix`

## Supported formats

- Scores: `.mid .midi .musicxml .xml .gp3 .gp4 .gp5 .gpx .mscz` (`.pdf` reference only)
- SoundFonts: `.sf2 .sf3` (`.sfz` registered, not yet renderable)
- Samples / voice: `.wav .mp3 .flac .ogg .aiff .aif .m4a`

## How scanning works

`POST /api/assets/rescan` walks `scores/`, `soundfonts/`, `samples/` and
`voices/recordings/`:

- **New files** are registered with a UUID, file facts and a content hash
  (sha256 of size + first/last 64 KB — fast on multi-GB libraries, reliably
  detects audio content changes).
- **Changed files** (hash mismatch) get refreshed facts and
  `analysis_status=pending`; the asset id and all user metadata are preserved.
- **Missing files** are flagged `is_missing=true`; metadata is never deleted.
  If the file returns, the flag clears and identity is preserved.
- User metadata (`tags`, `user_description`, `license_notes`) always survives
  rescans.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/assets[?asset_type=]` | list all assets |
| `GET /api/assets/scores` / `soundfonts` / `samples` / `voice-recordings` | list by type |
| `GET /api/assets/{id}` | single asset |
| `GET /api/assets/{id}/file` | serve original file (preview/download) |
| `POST /api/assets/rescan` | scan folders |
| `PATCH /api/assets/{id}/metadata` | edit tags / description / license notes |
| `POST /api/assets/{id}/analyse` | run sample analysis (Phase 8) |
| `GET /api/assets/search` | search by text/tags/bpm/key/type (Phase 8) |

## Adding assets

Drop files into `scores/`, `soundfonts/`, `samples/` or `voices/recordings/`
and hit **Rescan** in the Asset Library UI (or call the endpoint). Uploads and
live recordings (Phase 15) are saved to `voices/recordings/` and registered
automatically.

## Legacy note

`samples/sample_metadata.json` is a pre-existing file with stale absolute
paths; the studio ignores it and never modifies it.
