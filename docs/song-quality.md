# Song generation quality — implementation brief

Working document for the next quality push on chat-driven song generation.
Companion to [singing-quality.md](singing-quality.md), which is the equivalent
roadmap for the vocal pipeline. Written in English to match the rest of `docs/`
and the codebase.

**Goal:** chat-generated songs that are (a) genuinely genre-aware, (b) always
structurally complete, (c) mixed and polished only where it earns its place —
and an agent that is provably aware of every studio capability.

---

## 1. Audit findings (measured, not assumed)

These were verified against the current code and are the factual basis for the
plan.

| # | Finding | Evidence |
|---|---------|----------|
| F1 | **`project.bpm` is used 0 times in `music_gen.py`.** Generators emit beat patterns only; tempo never changes the arrangement (no half-time, no hat-subdivision shift, no fill density by tempo). | grep: 0 occurrences |
| F2 | **Genre matching is exact string equality.** `_ROCKY = ("punk","rock","metal","grunge")` and `if style in _ROCKY`. Any multi-word style falls through to the generic pattern. | `rock`→ROCKY, but `pop punk`, `bossa nova`, `deep house`, `synthwave`, `happy bossa nova pop` → **generic** |
| F3 | **Only 3 style families exist** (rock / dance / jazz) + generic. No latin, funk, soul, reggae, hip-hop, country/folk, ambient, ballad, synthwave. | `music_gen.py` |
| F4 | **No operation can set clip fades.** `fade_in_seconds` / `fade_out_seconds` exist on `Clip` but only `split_clip` ever writes them. The agent cannot do fades at all. | `operation_applier.py` |
| F5 | **No master/mix operation.** `mix_settings.master_volume` is unreachable from chat. | `operation_applier.py` |
| F6 | **Effect list in the prompt is incomplete:** 7 of 11 `EffectType` values documented; `robot`, `telephone`, `chorus`, `autotune` missing. | `song.py` vs `operation_planner.py` |
| F7 | **7 operations have no documented params:** `remove_track`, `update_section`, `update_effect`, `render_stems`, `render_mix`, `import_score`, `arrange_from_score`. The model sees the names (from `_OP_TYPES`) but not how to call them. | diff of `OperationType` vs prompt block |
| F8 | **No completeness validation after ops.** Nothing checks that every section has parts. The only post-pass is `ensure_vocal_melodies` (vocals only). A truncated LLM plan silently yields a half song. | `routes_chat.py` |
| F9 | **Instrumentation does not vary per section.** `_generate` with `section:"all"` applies the same part to every section, so everything plays everywhere. | `operation_applier._generate` |
| F10 | **No genre→tempo guidance** in the planner prompt; tempo choice relies purely on model world-knowledge. | `operation_planner.py` |

**Root cause of "the agent isn't aware of all capabilities" (F6/F7):** the
prompt contains a *hand-maintained* operation list that has drifted from
`OperationType`. Nothing keeps them in sync.

---

## 2. Assets we already have (do not rebuild)

- **Deterministic seeding:** `_rng(project, section, salt) = random.Random(f"{project.id}:{section.id}:{salt}")`. Regeneration is reproducible → A/B comparison and the metrics ledger are viable out of the box.
- **`Section.energy` is already honoured** for density/velocity inside parts (21 usages). The missing piece is *which instruments play*, not how busy they are.
- **Typed operation interface:** `ChatOperation` + Pydantic validation is already a strict tool schema. No protocol layer needed.
- **Deterministic asset RAG:** `asset_retrieval.py` (lexical + musical constraints). Previously investigated and deliberately chosen over embeddings/MCP.
- **Background-job precedent:** `_refine_part_in_background` (threading; `db.get_db` is `threading.local`, so worker threads are safe).
- **Proven measure-driven loop:** `singing_metrics.py` + `tools/validate_singing.py` + `tools/singing-validation.jsonl` took clone pitch error from 81.6 → 32.3 cents. **This is the pattern to copy for arrangement/mix.**
- **Built-in synth engine** (new): every instrument renders with zero setup, so generation quality is no longer gated on the user's SoundFont library.

---

## 3. Architecture decision

**No MCP.** MCP exposes tools to an *external* LLM client. Here the backend
calls the model and the tools are already a validated typed interface. It would
add a network layer without improving a single note. Reconsider later only as a
*product* feature ("drive mITyStudio from Claude Desktop") — a distribution
decision, not a quality one.

**Multi-agent: yes, but as a fixed pipeline — not a swarm.** Control flow stays
deterministic Python; the LLM is called only where musical judgment is needed.
The real structural win is **output-token budget**: today one call must plan
*and* write the whole song, which is the direct cause of "not always a complete
song" (F8). Per-part agents each get their own budget, and parts are
independent → parallelisable.

**Agentic loop: yes, but driven by measured signals, not model opinion.** A
critique loop without an objective signal just iterates on vibes. We have hard
signals available: completeness, key adherence, note density/gaps, and per-stem
peak/clipping (already computed in the renderer).

**Self-improvement: the honest version is offline.** A ledger of metrics per run
lets *us* verify whether a change actually improves scores between sessions. Do
**not** let the model rewrite its own prompts at runtime — unmeasurable and
fragile. Optionally capture what the user accepts/edits/discards as a genuine
preference signal.

> **Sequencing rule:** architecture does not fix a broken primitive. While
> `music_gen` cannot tell bossa from punk (F2) and ignores tempo (F1), a
> multi-agent pipeline just produces more expensive mediocrity. **Layer 0 ships
> first.**

---

## 4. Layer 0 — deterministic foundation (no LLM required)

Must work fully with **no API key** — the app is local-first and the mock
provider has to produce a decent song on its own.

**0.1 Genre engine**
- Replace exact membership with **token/substring matching** over a normalised
  style string.
- Expand to a real taxonomy: rock/punk/metal, pop, dance/house/techno/edm,
  latin/bossa/samba, funk, soul/rnb, reggae, hip-hop/trap, jazz/blues/swing,
  country/folk, ambient/cinematic, ballad, synthwave.
- Each family carries a **feel spec**: swing ratio, backbeat placement, hat
  subdivision, syncopation, typical instrumentation, groove template.

**0.2 Tempo awareness**
- Pass tempo into the generators; derive half-time / double-time feel, hat
  subdivision, and fill density from bpm (F1).
- Add a **genre→tempo range table**, used both by the generators and surfaced in
  the planner prompt so `create_song` picks a sane bpm (F10).

**0.3 Structured style fields (key design idea)**
Rather than re-parsing free text everywhere, normalise once into structured
fields on the project (e.g. `genre_family`, `feel`, `swing`, `groove`). The
lexicon fills them deterministically; when an LLM is available the producer call
may set them explicitly. **The model's musical judgment is captured once into
data the deterministic generators consume forever** — this is the clean bridge
between Layer 0 and Layer 2, and keeps offline behaviour good.

**0.4 Capability registry (fixes F6/F7 at the root)**
One registry next to `OperationType` holding, per op: params, when-to-use, and
constraints. The planner prompt is **generated** from it, so it can never drift
again. Same source can feed docs and a test that asserts every op is documented.

**0.5 Missing operations**
- `set_clip_fades` (F4) — intro/outro and transition fades.
- `update_mix` for master settings (F5).
- Complete the effect-type list (F6) and document `update_effect` (F7).

**0.6 Arrangement dynamics (biggest cheap win — F9)**
Vary *which* instruments play per section, driven by `Section.energy` and genre
structure templates: strip back verse 1, build into the chorus, drop out before
the last chorus. Add per-genre structure templates (intro/verse/chorus/bridge/
outro conventions). This is the single largest "sounds professional" lever and
it needs no LLM.

**0.7 Completeness autofill (F8)**
A post-op arrangement pass, mirroring `ensure_vocal_melodies`: detect sections
missing core parts and fill them, then report what was filled in the chat reply.

**0.8 `arrangement_metrics.py`**
The measurement foundation for everything later: completeness per section,
key adherence, note density/silence gaps, structural balance, per-stem peak /
clipping / headroom. No LLM.

---

## 5. Layer 1 — chat stays as it is

Single fast call for incremental edits ("add a guitar", "make the chorus
bigger"). Do not route these through the pipeline; latency matters more than
orchestration here.

---

## 6. Layer 2 — song pipeline (only for "make a full song")

Runs as a **background job with progress in the UI** (reuse the
`_refine_part_in_background` pattern; consider an `ExportJob`-style job object).

1. **Producer call** → song spec: sections, tempo, key, instrumentation per
   section, energy curve, `genre_family` + feel fields (0.3). One structured LLM
   call.
2. **Deterministic skeleton** → expand the spec with the existing `generate_*`
   generators. Instant, and complete *by construction*.
3. **Parallel composer calls** → `write_notes` per part, each with its own token
   budget. Independent, so run them concurrently.
4. **Metrics** (no LLM) → `arrangement_metrics` says what is missing or off.
5. **One bounded critic call** → fixes only what the metrics flag; may use
   `add_effect`, `set_clip_fades`, `update_track` levels. Rule: *every effect
   must earn its place*.
6. **Ledger append** → scores for the run.

Hard cap of 1–2 critique rounds; stop as soon as metrics stop improving.

---

## 7. Additional recommendations to carry into the design

**R1 — Never clobber user edits.** The completeness autofill and critic pass
must not overwrite manually edited clips. Add an "authored by user" marker (or
strictly additive semantics). This mirrors the hard-won *stem downgrade guard*
lesson: an automated pass that silently replaced good content caused real damage
before. The user has live projects at stake.

**R2 — Layer 0 must be good without an API key.** Acceptance: with the mock
provider, a full-song request still yields a complete, genre-appropriate,
dynamically arranged song.

**R3 — Explicit cost & latency budgets.** Chat edits stay interactive (target a
few seconds). The full-song job runs in the background with a capped total
number of LLM calls per song. Token usage is already surfaced per reply — keep
that honest.

**R4 — Evaluation harness + golden genre set.** Mirror
`tools/validate_singing.py`: a `tools/validate_arrangement.py` plus a jsonl
ledger, run over a fixed set of prompts across ~8 genres with expected
characteristics (tempo range, groove, instrumentation, structure). Without this
the loop in §6 has nothing to optimise against and "self-improvement" is
theatre.

**R5 — Objective mix targets, not opinions.** Give the critic concrete numbers
(per-stem headroom, vocal-above-bed margin, no clipping) so its judgments are
checkable, plus a hard cap on effects per track to stop it slathering.

**R6 — Define "a full song".** Written acceptance criteria (minimum sections,
minimum duration, every section populated, an intro and an ending) so F8 becomes
testable rather than a matter of taste.

**R7 — Exploit the existing determinism.** Seeding is already stable, so the
same prompt reproduces the same song. Use it for genuine A/B on generator
changes; keep any new randomness seeded the same way.

**R8 — Re-render implications.** Generator changes alter note content, so track
fingerprints change and stems re-render — expected. Do **not** bump
`ENGINE_VERSION` for arrangement changes (that would force a global re-render);
reserve it for actual rendering-engine changes.

**R9 — i18n.** Any new user-facing string needs a key in all four locale files
(en/nl/fr/de), verified at parity.

**R10 — Prefer lexicon-first, LLM-fallback** for style → genre mapping, so the
deterministic path stays offline-capable and the LLM only adds nuance.

---

## 8. Milestones & acceptance — STATUS: all five implemented

| Milestone | Contents | Status |
|---|---|---|
| **M1** | 0.1 genre engine, 0.2 tempo awareness, 0.3 structured style fields | ✅ `services/genres.py` (13 families, token-matched, tempo table); `music_gen` grooves per family (bossa clave, one-drop, trap half-time, funk ghosts, train, sparse…); bpm drives hat subdivision + fill density; `SongProject.genre` pinned by `create_song`. Tests: `test_genres.py` |
| **M2** | 0.4 capability registry, 0.5 missing ops | ✅ `OP_REGISTRY` in `models/operations.py`; prompt block + effect list + tempo table GENERATED; three-way sync test (registry/dispatch/Literal). New ops `set_clip_fades`, `update_mix` |
| **M3** | 0.6 arrangement dynamics, 0.7 completeness autofill, 0.8 metrics | ✅ `services/arrangement.py` (`plays_in_section` template gates `section:"all"`; explicit sections never gated; `fill_new_sections` additive-only in chat); `services/arrangement_metrics.py` (R6 encoded). Tests: `test_arrangement.py` |
| **M4** | R4 harness + ledger | ✅ `tools/validate_arrangement.py` + `tools/arrangement-validation.jsonl`. First run scored 5/8, fixes brought it to **8/8** — the ledger recorded the improvement, proving the loop |
| **M5** | Layer 2 pipeline + bounded critic | ✅ `services/song_pipeline.py`: producer → skeleton → parallel composers (cap 3) → metrics → critic (cap 1 round, metrics-gated, regression-refused) → ledger `analysis-cache/song-pipeline.jsonl`. `POST /projects/{id}/generate-song` (+status). Offline/mock path yields a complete genre-true song (R2). Tests: `test_song_pipeline.py` |

---

## 9. Decisions taken (were open for Fable)

1. **Per-section instrumentation:** automatic from energy + genre template,
   applied only on `section:"all"` bulk generation; explicit per-section
   requests are never gated (user intent wins, R1).
2. **Pipeline job:** background daemon thread + in-memory job registry,
   `POST /projects/{id}/generate-song` / `GET …/{job_id}`. UI progress
   surface is follow-up work (endpoint is poll-ready).
3. **Critique budget:** producer(≤1) + composers(≤1 per track, parallel cap
   3) + critic(≤1 round, entered only when metrics flag issues; a
   completeness regression aborts the round).
4. **Preference store:** not built — revisit only with a concrete UI signal
   (accept/reject per part).
5. **Taxonomy size:** 13 families; grow only when a family needs a genuinely
   different groove template, not per genre name (keywords map many names
   onto one family).
6. **Producer spec:** transient; its durable outputs are the project fields
   themselves (`genre`, bpm, key, sections+energies) — auditable via the
   pipeline ledger entry per run.

## 10. Follow-up (not yet built)

- UI: "Generate full song" button + job progress panel; i18n keys x4.
- Chat routing: let the planner hand a full-song request to the pipeline
  (today chat still runs its Layer-1 flow, which the autofill + metrics
  passes also guard).
- Critic access to per-stem peaks requires a render first — today it runs
  pre-render (clipping data appears once stems exist).
- Vocals in the pipeline: reuse `sing-lyrics` flow after the skeleton when
  the prompt asks for vocals.
