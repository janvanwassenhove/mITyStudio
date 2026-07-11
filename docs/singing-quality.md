# Singing quality: where it comes from and the road to "ElevenLabs-class"

## The honest physics of the problem

The vocal chain is: **source singing → timbre conversion (RVC)**.

RVC (the trained per-voice model) is already strong — it faithfully transfers
the *timbre* of Elke/limme onto whatever it is fed. What it cannot fix is the
**source**: if the input phonation is robotic, the output is a robotic voice
that *sounds like* the right person.

Today's source is XTTS **speech**, time-stretched and pitch-mapped onto the
melody (WORLD vocoder). Speech stretched onto sung notes has three inherent
artifacts: slow-motion vowels on sustained notes, TTS speech prosody (no
breath support, no sung vowel color), and pitch pushed far from the spoken
register. That is the ceiling the current sound is hitting — not a bug, a
technique limit. Even ElevenLabs does not offer singing TTS; the products
that reach "AI cover" quality all use **real human singing as the source**.

## Quality ladder

### T0 — correctness (DONE)
- Silent-stem bug fixed (RVC collapsed sparse timelines; now converts dense
  line audio), silence-guard, vocal engine versioning, per-language
  syllabification (EN/NL/FR/DE), XTTS language passthrough.

### T1 — Sing it yourself → your AI voice (DONE, highest quality available)
Record a take onto the vocal lane (🎙 in the transport or Track tab; the
**Karaoke view is the guide** — lyrics + timing on screen). Takes on a track
with a voice profile are now **automatically RVC-converted to that voice**
at render. Real human phonation + trained timbre = the same pipeline behind
convincing "AI covers", and by far the closest thing to ElevenLabs quality
that runs locally. Practical recipe:
1. Give the melody a listen (▶), open Lyrics → Karaoke.
2. Record the take while singing along (any voice — pitch/timing matter,
   timbre does not).
3. Press ▶ — the take renders through the trained model of the selected
   profile.

### T2 — synthetic singing naturalness (LARGELY DONE)
For the fully-automatic path (no user singing):
1. **Sustain looping** (DONE): sustained notes keep onset/coda at natural
   speech rate and ping-pong-loop the vowel core with jitter — no more
   slow-motion vowels. Measured: clone pitch error 81.6 → 48.8 cents,
   frames-on-pitch 43% → 50%.
2. **Consonant-anchored alignment** (DONE, part of 1).
3. **Breaths** (DONE): soft inhale before each phrase with room for one.
   Phrase-level dynamics/velocity mapping still open.
4. **Backing-vocal harmony** (DONE): backing vocals sing a diatonic third
   above the lead at lower velocity instead of a unison double.
5. **Delivery styles** (DONE): sing / soft (airy, breathy) / powerful
   (belted, deep vibrato) / rap — per track, in Add Track and the Track tab.
6. **NEXT — RVC pitch fidelity**: validation shows the RVC stage now adds
   pitch noise (clone 48.8 cents → clone+rvc ~115). Tune f0 handling
   (f0_method/protect, or post-RVC pitch correction toward the melody).
7. Also open: robustness fixes shipped alongside — LLM lyric sheets split
   across sections automatically, singing falls back to sequential matching
   when lyric sections don't line up with melodies, chat auto-sings any
   vocal track whose lyric sections lack a melody.

### T3 — true singing synthesis as source (the real jump)
Integrate a dedicated SVS engine (e.g. **DiffSinger via OpenUtau**) as an
alternative `SingingVoiceEngine`: it *sings* natively from notes + phonemes
(correct sung vowels, breath, vibrato), then RVC converts to the user's
timbre. Caveats to scope first: voicebank availability per language (EN
bases exist; NL/FR/DE are thinner), phonemizers per language, license per
voicebank, GPU load. This is the tier that makes the *automatic* path sound
genuinely human.

### T4 — optional cloud engine
A commercial singing/voice API behind the same engine interface, for users
who accept non-local processing. Off by default (local-first principle).

## The recording wizard's role
The wizard exists to make **RVC training material** better: 10+ minutes,
all vowels, both registers, dynamics (that's why the minutes meter and the
vowel/siren/head-voice exercises exist). Better training data → better
timbre transfer in every tier above. It does not change the source-singing
problem — that's T1/T3.

## Languages
- XTTS speaks EN/NL/FR/DE (and more); `lyrics.language` flows through.
- Syllabification is language-aware (`lyric_text.py`, accented vowels).
- Validation (below) runs per language: `validate_singing.py <profile> nl`.

## How we test and validate
1. **Objective metrics** — `tools/validate_singing.py` renders a fixed
   phrase through every engine (formant / clone / clone+RVC) and reports:
   `voiced_ratio` (catches silent/dead output), `median_cents_error` +
   `within_50_cents` vs the target melody (pitch correctness),
   `spectral_flatness` (buzziness), levels, render time. Results append to
   `tools/singing-validation.jsonl` so changes are comparable over time.
   Run it after every vocal-pipeline change; regressions in voiced_ratio or
   pitch accuracy are a hard stop.
2. **Unit gates** — `tests/test_singing_metrics.py` keeps the metrics
   honest; the pipeline tests (silence guard, dense RVC) keep correctness.
3. **Listening protocol** — metrics rank, ears decide: for each change,
   listen to the 3 validation WAVs (analysis-cache/validation/) and score
   1–5 for naturalness/intelligibility/identity; note the score in the
   jsonl entry. Same phrases every time, per language.
