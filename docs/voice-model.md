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

### v1 engine: MockSingingVoiceEngine

Synthesizes a soft harmonic tone with vibrato per melody note — audible in
mixes, correct timing, no cloning. Real voice synthesis is intentionally out
of scope for v1.

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
