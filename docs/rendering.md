# Rendering pipeline

```
SongProject
 ├─ MIDI generation      midi/{project}/         (mido, one file per track + full song)
 ├─ instrument stems     stems/{project}/        (FluidSynth CLI + .sf2 per track)
 ├─ sample stems         stems/{project}/        (numpy: placement, loop, gain, fades)
 ├─ vocal stems          stems/{project}/        (MockSingingVoiceEngine + alignment)
 ├─ effects              applied during mixdown  (gain/pan/delay/reverb/distortion)
 ├─ mixdown              volume/pan/mute/solo → stereo sum → normalize/limit
 └─ export               exports/{project}/      (WAV always, MP3 via ffmpeg)
```

## Endpoints (in pipeline order)

| Endpoint | What it does |
|---|---|
| `POST /api/projects/{id}/midi/export` | tracks → MIDI files |
| `POST /api/projects/{id}/render/instrument-stems` | MIDI + SoundFont → WAV per track |
| `POST /api/projects/{id}/render/sample-stems` | sample clips → WAV per sample track |
| `POST /api/projects/{id}/vocals/render` | vocal tracks → mock vocal WAV + lyrics alignment |
| `POST /api/projects/{id}/render/apply-effects` | reports effect chains (applied non-destructively at mixdown) |
| `GET /api/projects/{id}/stems/{track_id}/file` | serve a stem for playback |

All render results are written under `stems/`, registered as `rendered_stem` /
`vocal_stem` assets, and referenced in `project.stems` with a
`source_fingerprint` — unchanged tracks are skipped on re-render, changed
tracks re-render automatically (the mix export calls all of this itself).

## SoundFont selection

Each instrument track can set `instrument_config.soundfont_asset_id` (via the
chat operation `assign_soundfont` or the project API). Tracks without one fall
back to the first available SoundFont, preferring filenames that look like
General MIDI banks (`gm`, `general`, `fluidr3`, `musescore`). A warning names
the fallback used. Missing FluidSynth or missing SoundFonts produce per-track
errors, never crashes.

FluidSynth invocation: `fluidsynth -ni -g 0.7 -r 44100 -F out.wav font.sf2 in.mid`

## Effects (v1)

Implemented in pure numpy (`app/services/render/effects.py`): `gain`
(gain_db), `pan` (position −1..1, constant-power), `delay` (time_seconds,
feedback, mix), `reverb` (mix, decay; comb-bank), `distortion` (drive, mix,
tanh). `eq` and `compressor` are **documented placeholders** — identity plus a
warning. Chains apply in order at mixdown; stems on disk stay dry.

## Waveforms

After each render, per-stem peak arrays (200 buckets) are cached at
`projects/{id}/waveforms.json` and served in the PlaybackManifest, so the
timeline draws waveforms without decoding audio in the browser.
