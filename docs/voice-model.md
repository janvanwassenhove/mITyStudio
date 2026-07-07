# Voice model & safety rules

## Objects

- **VoiceRecording** — an audio file in `voices/recordings/`, added by upload
  or live microphone recording. Registered as a `voice_recording` asset with
  duration/sample-rate metadata. Original files are never modified.
- **VoiceProfile** — a reusable singing voice, stored in SQLite and mirrored
  as a `voice_profile` asset. Fields: name, source_recording_ids,
  consent_confirmed, consent_notes, performer_alias, vocal_range,
  language_notes, quality_score, status, usage_restrictions, created_at.

## Safety rules (enforced in code, not just documented)

1. Recordings **never** become voice profiles automatically.
2. `POST /api/voice/profiles` returns **403** unless `consent_confirmed=true`
   (`tests/test_voice_and_vocals.py::test_voice_profile_requires_consent`).
3. Consent metadata (`consent_notes`, who/when/how) is stored with the profile.
4. A profile is only used when the user (or a validated chat operation)
   explicitly assigns it to a vocal track; `assign_voice_profile` re-checks
   consent at assignment time.
5. The LLM planning context only lists profiles with confirmed consent, and
   the applier rejects any profile id not in the registry.
6. No features exist to imitate known artists or third parties; adding a
   third-party voice requires that person's consent recorded in
   `consent_notes` / `usage_restrictions`.

## SingingVoiceEngine contract (Phase 23 adapter interface)

`app/services/vocal_engine.py` defines the interface every engine must obey:

```
render(project: SongProject, track: Track, out_path: Path) -> VocalRenderResult
  # inputs available on the objects: voice_profile_id, lyrics (with syllables
  # on note events), melody notes, bpm, key, expression via track effects
  # outputs: WAV stem at out_path, lyrics alignment (line/word timings),
  # render_log, warnings
```

Registration point: `get_engine(name)` — real engines are added there.
Requirements for a real engine adapter:

- must receive a voice profile with `consent_confirmed=true`, else refuse
- must produce the same alignment schema (see below) so karaoke keeps working
- must never write outside `stems/{project_id}/`
- the **mock engine stays available as fallback** when the real engine or its
  dependencies are missing

### The singing pipeline (current best setup)

For fluent, on-pitch vocals every stage matters:

1. **Vocal melody generation** (`generate_vocal_melody`): exactly **one note
   per syllable**, phrased per lyric line with breaths between lines, contour
   arcs resolving to chord tones. Rap mode: tight 1-3 pitch flow, rhythm-led.
2. **Neural voice cloning** (XTTS-v2): each lyric line is spoken in the
   voice cloned from the profile's source recording. Lines are cached.
3. **Syllable-to-note alignment**: the spoken line is split into syllable
   segments (energy-valley cuts near text-proportional positions); each
   segment is time-stretched onto its exact note and pitch-mapped to the note
   frequency with a 35 ms glide-in and delayed vibrato on long notes.
   Unvoiced frames (consonants) keep their natural pitch → words stay crisp.
   Rap style skips pitch-mapping entirely (natural voice, rhythm-locked).
4. Vocal stems are normalized to sit on top of the mix; autotune/reverb etc.
   can be added as track effects.

Recording tips for best cloning: 10–30 s of clean, dry, single-speaker audio
(no music underneath), normal speaking or sustained singing, in the language
of the lyrics.

### Going further (upgrade ladder)

- **RVC voice conversion** (train a per-voice model, ~10 min of recordings,
  GPU): convert a well-sung base vocal into the target voice — best timbre
  fidelity. Fits behind `SingingVoiceEngine` as a post-processor.
- **DiffSinger-class SVS**: true singing synthesis (phoneme+pitch score in,
  singing out) — highest ceiling, heaviest integration.

### Engines

- **MockSingingVoiceEngine (formant)** — default. Formant-synthesized vowels
  from lyric syllables with vibrato and consonant bursts. Clearly synthetic.
- **RecordingVoiceEngine (AI voice from your recording)** — used automatically
  when the vocal track has a **consented voice profile** with source
  recordings: a voiced segment of the recording is pitch-shifted to every
  melody note, so the vocal carries the recorded voice's timbre. Consent is
  re-checked at render time; without a usable pitched recording it falls back
  to the formant engine with a warning. No neural cloning is involved.

### Recorded takes (live singing on a track)

Vocal tracks can carry **sample clips** pointing at voice recordings — the
Track inspector's "Record take" button records the microphone and drops the
take at the playhead. Takes are mixed into the vocal stem at render time, so
vocal effects (reverb, robot, telephone, chorus…) apply to them too.

## Lyrics alignment schema

Stored at `projects/{id}/lyrics_alignment.json`, served in the
PlaybackManifest:

```json
[{"line_id": "...", "section_id": "...", "text": "...",
  "start_time": 12.3, "end_time": 15.1, "confidence": 0.9,
  "words": [{"word": "We're", "start_time": 12.3, "end_time": 12.6,
             "linked_note_id": "..."}]}]
```

Word timings come from melody notes (one syllable per note, words consume
notes per their syllable count); lines without matching notes fall back to an
even spread across their section with `linked_note_id: null`.
