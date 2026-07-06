# Export

## Combined mix export

`POST /api/projects/{id}/export/mix` with `{"formats": ["wav", "mp3"]}`.

Pipeline (`app/services/mix_export.py`):

1. Validate project references (assets, profiles).
2. Ensure stems are fresh — missing/stale instrument, sample and vocal stems
   are rendered automatically where safe; unrenderable tracks become clear
   per-track errors/warnings on the job.
3. Load every stem for audible tracks (solo wins over mute; muted/unsoloed
   tracks are excluded with a warning).
4. Apply each track's effect chain (non-destructive).
5. Apply track volume and constant-power pan.
6. Align every stem to the project duration and sum to stereo.
7. Apply master volume, then normalization to −0.5 dBFS-ish (0.94 peak) or a
   tanh soft limiter, per `mix_settings`.
8. Write WAV (44.1 kHz stereo 16-bit).
9. Encode MP3 (192 kbps) via ffmpeg if available; if not, the job completes
   with WAV plus a warning naming exactly what is missing.
10. Register outputs as `exported_mix` assets in `exports/{project_id}/`.

Outputs are timestamped + job-id-suffixed — previous exports are never
overwritten.

`GET /api/projects/{id}/exports` lists ExportJobs (status, files, warnings,
errors). `GET /api/projects/{id}/exports/download?path=...` serves files
(path-traversal-guarded to the project's export folder).

## Package export (Phase 21)

`POST /api/projects/{id}/export/package` builds
`exports/{id}/package/` + `{id}_package.zip` containing:

- `project.json` — full song model
- `lyrics.txt` — lyrics grouped by section
- `lyrics_alignment.json` — karaoke timing
- `midi/` — all exported MIDI files
- `stems/` — all rendered stems
- `mix/` — final WAV/MP3 exports

Original assets (scores/soundfonts/samples/voices) are never copied, moved or
modified by any export.

## Frontend

Studio → right panel → **Export** tab: render-all button, WAV/MP3 checkboxes,
combined export, package export, job list with download links and warnings.
