# Troubleshooting

## Timeline is slow / freezes during playback
Fixed in the current version: the playhead is updated via direct DOM
transforms (no re-renders) and note layouts are precomputed once per project
change. If you still see jank, lower the zoom slider (fewer pixels per beat)
and hard-refresh the browser tab (Ctrl+F5) to clear stale hot-reload state.

## UI shows errors after a backend upgrade
Old project data in an open browser tab can miss new fields. Hard-refresh
(Ctrl+F5); the backend migrates projects on load, and the UI guards against
missing fields.

## "FluidSynth is not installed or not on PATH"
Instrument stems need the FluidSynth CLI.
Windows: `choco install fluidsynth`. Verify with `fluidsynth --version`,
then restart the backend. The rest of the studio (samples, vocals, export of
those) works without it.

## "no SoundFont file found"
Put at least one `.sf2` in `soundfonts/` and click **Rescan** in the Asset
Library. A General MIDI bank (e.g. FluidR3_GM.sf2) gives the best fallback
results; per-track SoundFonts can be assigned via chat
("assign …" ) or the project API.

## "MP3 export unavailable"
MP3 needs `ffmpeg` with libmp3lame on PATH. WAV export still succeeds; the
export job carries a warning naming the gap.

## Instrument stems sound wrong / use a weird instrument
Tracks without an explicit SoundFont fall back to the first available one
(see render warnings, e.g. "using fallback soundfont '12-string.sf2'").
Assign a proper SoundFont per track, or add a GM bank to `soundfonts/`.

## Chat replies "(mock planner) I can create songs …"
The mock provider only understands keyword commands (create/tempo/key/
lyrics/add section/drums/bass/chords/melody). For free-form planning,
configure a real provider in Settings (Anthropic, needs
`pip install anthropic` in the backend venv + an API key).

## Vocal stem is silent
The vocal track has no melody notes. Ask the chat to "add lyrics about …"
(which generates a melody with syllables) or generate a melody onto the vocal
track first.

## Assets show "(missing)"
The file was moved/deleted outside the studio. Metadata is kept; restore the
file and rescan to clear the flag. The registry never deletes entries.

## Playback is silent in the browser
The transport clock always runs, but audio needs rendered stems (render all
stems in the Export tab, then press play — "n/m stems loaded" appears in the
transport bar). Browsers also require a user gesture before audio starts.

## Reset generated data
Stop the backend and delete `analysis-cache/` (registry + analyses),
`stems/`, `midi/`, `exports/` as needed. Never required for original assets;
rescan rebuilds the registry.
