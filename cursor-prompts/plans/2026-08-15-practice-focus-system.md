# Practice Focus System

**Last updated:** 2026-08-16  
**Active branch:** `feature/practice-focus-system`  
**Base:** current clean `origin/dev` (`870a365899d3207982d0c2834f8c9bf2092e9931`)  
**Do not merge to `dev` until explicit approval.**

Parked (do not touch, merge, reset, rebase, or use as a base):

- `feature/creative-backing-stabilization` @ `44403d43785a0bdd29c0762f98155efd393ccb70`

---

## Product goal

Make **Practice Focus** a meaningful app-wide coaching variable rather than a selector/label.

If the user chooses `Practice Focus = Strumming`, relevant surfaces should behave like a strumming coach. If they choose `Tone`, like a tone coach. Focus is a **bias** (priority, weighting, recommendations), not a prison (still mention catastrophic non-focus issues; still answer unrelated factual questions directly).

Practice Focus must **not** own song, Practice/Concert Key, Written Key, Guitar Shape, backing source, generated Jam state, or Mission harmony.

Instrument ≠ focus. Same guitar + Strumming vs Melody should coach very differently.

---

## Branch rules

| Item | Value |
|------|--------|
| `origin/dev` SHA | `870a365899d3207982d0c2834f8c9bf2092e9931` |
| Parked Creative SHA | `44403d43785a0bdd29c0762f98155efd393ccb70` |
| Practice Focus base SHA | `870a365899d3207982d0c2834f8c9bf2092e9931` |
| New branch | `feature/practice-focus-system` |
| Contains unmerged Creative commits? | **No** (`44403d4` is not an ancestor of HEAD) |

Push Practice Focus work only to `feature/practice-focus-system`.

Do **not** solve remaining Creative/Backing live items here:

1. Style Jam Backing ephemeral BPM/Meter/Advanced settings final live verification
2. Jam Generator Backing generated-key change final verification
3. Mission example heading using Written/Guitar Shape chord domain
4. Mission Backing transposing/reprojecting the existing example when Practice Key / instrument / Written Key / Guitar Shape changes

---

## Audit (current `dev` / this branch base)

### Canonical coaching Practice Focus

- **Session key:** `focus` (`practice_setup_globals.GLOBAL_FOCUS_KEY`)
- **SSOT getters/setters:** `get_active_focus` / `set_active_focus` / `set_active_instrument` / `valid_focus_for`
- **Option lists:** `practice_setup_controls.FOCUS_OPTIONS_BY_INSTRUMENT` + `focus_options_for_instrument()`
- **Sidebar widget:** `streamlit_music_practice_app.py` `key="focus"`
- **Instrument change:** if current focus is not in the new instrument list, **silently set to `opts[0]`** (Guitar Strumming → Saxophone **Tone**). Deterministic; keep this class of policy.
- **Persistence:** stored with global controls / `active_song_state` (`instrument`, `level`, `focus`). Survives rerun, refresh, navigation, workspace save.

Guitar defaults (first = default): Strumming, Rhythm Guitar, Chord Transitions, …  
Saxophone default: Tone.

Phase 1 **appends** shared coaching focuses (Timing, Melody, Harmony, Improvisation, Technique, Phrasing, Rhythm, Tone) **without changing the first/default option**.

### Do not conflate these other “focus” systems

| Name | Meaning |
|------|---------|
| `practice_focus_section` / `practice_focus_sections` | Verse/Chorus/Full Song **scope**, not coaching focus |
| `youtube_links.focus_options_for_instrument` | Duplicate incompatible list for YouTube search only — **not SSOT** |
| `mission_evaluation_focus` | Mission recording analysis dimensions |
| Practice Log `focus_area` | Coarse taxonomy (`tone`, `timing/rhythm`, `chords`, …) |
| Song-card `practice_focus` | Curated prose from song coaching profiles |
| Improvisation Intelligence “focus” strings | Mission/level vocabulary |
| Composition `focus_lane` | Unrelated composition snapshot lane |

### Where `focus` was read vs ignored (pre–Phase 2)

**Reads (often weakly / as a label):** sidebar; AMI `CoachContext.practice_focus`; Practice page `_focus_area()` buckets (Guitar Strumming often fell through to generic technique copy); Practice Log prefill (`focus` + mapped `focus_area`); some Creative snapshots as a global session field.

**Mostly ignored for real coaching:** Upload / AI Coach metric selection (**no snapshot** on `last_analysis_result`); Multitrack analysis; Backing instructional layer; Missions/Creative coaching; weekly Practice Coach analysis (uses coarse `focus_area` more than exact Practice Focus); Composition.

### Persistence / snapshots (pre–Phase 1)

- **Current focus:** global user setting. OK.
- **Upload:** did **not** snapshot Practice Focus at analysis time.
- **Practice Log:** partial — stores exact `focus` on new prefills plus coarse `focus_area`. `_normalize_focus_area` did not map Strumming → `timing/rhythm`. Old rows without `focus` must stay missing.

### Creative on this branch

Safe now: audit, central context plumbing, prompt/guidance that does not depend on unmerged Creative/Backing ownership.

Defer until parked branch is accepted: canonical Creative/Backing ownership, key/session handoffs, Mission backing architecture, generated-session state, Backing persistence, anything that would duplicate `44403d4`.

### Composition

Unfinished. Identify hooks only; do not rebuild Composition in this project.

---

## Architecture (Phase 1)

| Module | Role |
|--------|------|
| `practice_setup_globals` | Store of the **selected** `focus` string (unchanged ownership) |
| `practice_focus_policy.py` | Structured profiles: category, priorities, metrics, exercises, Creative/Backing ideas, AMI language, instrument overlays |
| `practice_focus_context.py` | `PracticeFocusContext` from live session — **coaching only** |
| `practice_focus_snapshot.py` | Frozen dict for logs/uploads/analyses; missing → absent, never invented |

**Current vs historical**

- Current: session `focus` + `resolve_practice_focus_context`
- Historical: `practice_focus_snapshot` copied at write time

**Instrument compatibility**

Keep if still in the new instrument’s option list; otherwise first option of the new instrument (Saxophone → Tone). Do not silently keep Guitar `Strumming` on saxophone.

**AI prompt helper**

`format_focus_prompt_block(instrument, focus, role=ami|analysis|history)` — bias, not prison.

**Evaluation weighting (consumed in later phases)**

baseline metrics + focus-required metrics (`preferred_metric_ids`) + performance-detected important issues. Do not fabricate unsupported dimensions.

---

## Implementation phases

### Phase 1 — Foundation (this slice)

- [x] Audit
- [x] Policy / context / snapshot modules
- [x] Additive shared focuses (defaults unchanged)
- [x] Log prefill snapshot + migrate wrap of existing `focus` only
- [x] AMI `CoachContext.extra` plumbing (`practice_focus_prompt`)
- [x] Upload history compact keys for snapshot fields
- [x] Tests: profiles, Guitar/Sax, Harmony vs Melody, fallback, snapshot immutability

### Phase 2 — Highest-value coaching surfaces

1. [x] **Phase 2A (2026-08-16):** AMI + Practice page consume `PracticeFocusContext` / policy via `practice_focus_coaching.py`. Same instrument + same song + change-only Focus produces different AMI plans and Practice drills. Factual theory (e.g. C major notes) is not hijacked. Upload / Log / Multitrack still deferred.
2. [x] **Phase 2B (2026-08-16):** Upload / AI Coach snapshots Practice Focus at analysis start (`practice_focus_evaluation.py`). Focus unions supported mission metrics, emphasizes measured score keys, rewrites coach summary/next exercises, and keeps historical results immutable. Severe non-focus issues still surface. Unsupported measurements are not fabricated. **Deferred:** real-audio `analyze_recording` smoke test (needs `librosa` + WAV fixture).
3. [x] **Phase 2C (2026-08-16):** Practice Log + weekly Practice Coach (`practice_focus_history.py`). Exact Focus frozen on new logs; weekly analysis aggregates exact Focus vs coarse `focus_area` vs missing; current Focus informs next steps without rewriting historical interpretation.
4. [x] **Phase 2D (2026-08-16):** Multitrack ensemble analysis (`practice_focus_multitrack.py`). Snapshots Focus; coaching uses measured onset/RMS only; no stroke/resonance/chord invention. **Deferred:** full-audio `analyze_multitrack` smoke test (needs `librosa` + fixtures).

### Phase 3 — Practice Coach / Weaknesses first; Creative audit; Backing optional

**Product rule (2026-08-16):** Backing Track Focus coaching is **optional / user-invoked**, not automatic. Backing stays neutral by default. Do not auto-impose Focus drills on every Backing session. Future UX: e.g. “Practice this track with my Focus” or a collapsed optional coaching card. **Not implemented in Phase 3A/3B** — documented only; remains deferred until after Creative/Backing reconciliation.

5. [x] **Phase 3A (2026-08-16):** Practice Coach & Session + Adaptive Weakness Detection
   - `build_focus_timed_session` / `practice_page_time_ratios` in `practice_focus_coaching.py`
   - Timed Session Planner + Practice-page time blocks + weekly 30-min plan consume Focus structure
   - Current Focus owns the session; historical Focus may diversify drills only
   - `practice_focus_weaknesses.py` ranks measured scores (severity + Focus relevance + severe floor); never invents Focus-only defects
   - Creative Lab Adaptive Weakness Detection uses the ranker + last Upload scores when present
   - Tests: `tests/test_practice_focus_phase3a_session_weakness.py`
   - Evidence: `scripts/evidence-practice-focus-session/`
5b. [x] **Phase 3B (2026-08-17):** Safe completed surfaces only — Custom tools + Arrangement Assistant advisory bias
   - `practice_focus_custom.py` adapter (central policy; no new rulebook)
   - CPL `generate_exercises_markdown` + Custom page expander: same progression, different Focus → different drills; explicit request precedence; same-rerun
   - Arrangement Assistant: Focus suggestion section is advisory only (no arrangement rewrite)
   - Practice `section_deep_practice` exercise text consumes Focus lines
   - **Not implemented (deferred):** Deep Harmony, Harmony Map, Motif & Phrasing, Motif Sequence UI, Missions/Style Jam/Jam Generator, optional Backing Focus card, Composition
   - Tests: `tests/test_practice_focus_phase3b_custom.py`
   - Evidence: `scripts/evidence-practice-focus-custom/`
   - **Checkpoint:** park `feature/practice-focus-system` after acceptance; return to Creative/Backing @ `44403d4`
6. Backing **optional** Focus coaching card (deferred — product rule above)
7. Custom tools deeper polish (later if needed)
8. Other completed surfaces with natural hooks

### Phase 3B parking note

After Phase 3B acceptance, **temporarily park** `feature/practice-focus-system` at its Phase 3B tip. Do **not** merge to `dev` unless explicitly requested. Resume `feature/creative-backing-stabilization` @ `44403d4` for remaining live acceptance items, then reconcile Practice Focus with accepted Creative architecture for Phase 4.

### Phase 3A — Creative integration audits (implement later; parked branch safe)

Creative/Backing ownership remains parked at `feature/creative-backing-stabilization` @ `44403d43785a0bdd29c0762f98155efd393ccb70`. Do not cherry-pick ownership modules into this branch.

| Surface | Safe now | Deferred until Creative reconciliation |
|---------|----------|----------------------------------------|
| **Deep Harmony** | Read-only Focus prompt/coaching overlay that changes *what is taught* about the same progression (Harmony→function/guide tones; Melody→targets/contour; Phrasing→arrival/space; Timing→harmonic rhythm; Strumming→change accents). Underlying chords unchanged. | Any state that depends on Creative workspace ownership, key projection handoffs, or Mission/Jam session keys from `44403d4` |
| **Harmony Map** | Coaching overlay: what to notice (function vs targets vs phrase boundaries vs harmonic rhythm). Map harmony stays canonical. | Section/chord selection persistence, projection ownership |
| **Motif & Phrasing** | Prompt-level Focus bias for exercises on the *current motif object* (preserve motif; change coaching). | Motif ownership / Written Key / Guitar Shape projection paths from parked branch |
| **Creative Arrangement Assistant** | **Phase 3B shipped:** advisory Focus suggestion section only (no arrangement rewrite). | Arrangement document ownership / Creative session envelope / auto-apply |

#### NEW Motif feature — Expand Motif as a Sequence (roadmap — do not lose)

**Status:** Spec only on this branch. Deep implementation deferred if it conflicts with parked Creative projection architecture.

**UX (wording TBD):** `Expand Motif as a Sequence` / `Show Motif Pattern on Staff`

**Behavior (v1):**
1. Take the **current motif** (pitches + rhythm — not pitch names alone).
2. Build an **ascending diatonic sequence** through the current scale/key (preserve interval/scale-degree shape and rhythm per unit).
3. Display as **full staff notation** (multi-measure exercise), not a short motif card.
4. Use existing key/spelling utilities (`spell_note_in_key`, motif engine outputs). No hardcoded C-major arithmetic.
5. Concert motif remains canonical; player-facing Concert / Written Key / Guitar Shape projection must not double-transpose — **wire after Creative stabilization reconciliation**.
6. Playback optional for v1.

**Future options (design for, do not build yet):** descending; through progression; rhythmic displacement; transpose by interval; range limit.

**Example (keep explicit):**

Current motif: `G – A – B – D`  
Ascending diatonic sequence (C major illustration):  
`G – A – B – D` / `A – B – C – E` / `B – C – D – F` / `C – D – E – G` / `D – E – F – A` …  
If original rhythm is eighth · eighth · quarter · quarter, each sequenced unit retains that rhythm.

**Integration point:** `motif_engine` / `improvisation_motif` transform on the active motif object → ABC/staff renderer already used by Phrase & Motif. UI button on Motif & Phrasing page only after parked Creative ownership is accepted if projection is required.

### Phase 4 — Creative (after parked branch)

Deeper Mission / Style Jam / Jam Generator / Harmony Map / Live Coach / Motif Sequence implementation against accepted Creative architecture. Reconcile branches carefully; do not cherry-pick `44403d4` internals into this branch.

### Phase 5 — Composition

Later, once Composition itself is sufficiently complete. Clean `PracticeFocusContext` hook is enough for now.

---

## Deferred acceptance (tracked, not blockers)

- Upload full-audio `analyze_recording` smoke test (`librosa` + WAV)
- Multitrack full-audio `analyze_multitrack` smoke test (`librosa` + fixtures)

---

## Files / modules

**New:** `practice_focus_policy.py`, `practice_focus_context.py`, `practice_focus_snapshot.py`, `practice_focus_coaching.py`, `practice_focus_evaluation.py`, `practice_focus_history.py`, `practice_focus_multitrack.py`, `practice_focus_weaknesses.py`, `practice_focus_custom.py`, `tests/test_practice_focus_policy.py`, `tests/test_practice_focus_phase2_ami_practice.py`, `tests/test_practice_focus_phase2b_upload.py`, `tests/test_practice_focus_phase2c_log.py`, `tests/test_practice_focus_phase2d_multitrack.py`, `tests/test_practice_focus_phase3a_session_weakness.py`, `tests/test_practice_focus_phase3b_custom.py`

**Touched in Phase 3B:** `custom_progression_lab.py`, `cpl_page_ui.py`, `creative_lab_text.py`, `practice_studio.py`

**Touched in Phase 3A:** `practice_focus_coaching.py`, `practice_studio.py`, `practice_history_synthesis.py`, `practice_log_insights.py`, `practice_log_coach.py`, `creative_lab_text.py`, `streamlit_music_practice_app.py`

**Touched in Phase 2D:** `recording_analysis.py` (`analyze_multitrack`), `recording_analysis_ui.py`, `streamlit_music_practice_app.py` (Analyze ensemble), `multitrack_history.py`

**Touched in Phase 2C:** `practice_log_state.py`, `practice_log_ami.py`, `practice_history_synthesis.py`, `practice_log_ui.py`, `practice_log_analysis_handoff.py`

**Touched in Phase 2B:** `recording_analysis.py`, `recording_analysis_ui.py`, `streamlit_music_practice_app.py` (analysis run), `upload_history.py`

**Touched in Phase 1:** `practice_setup_controls.py`, `practice_setup_globals.py` (docs), `practice_log_state.py`, `music_coach_ami/context_reader.py`, `upload_history.py`

**Touched in Phase 2A:** `music_coach_ami/practice_plan_knowledge.py`, `music_coach_ami/router.py`, `music_coach_ami/solvers.py`, `music_coach_ami/context_reader.py`, `music_ami_context.py`, `streamlit_music_practice_app.py`

**Do not touch for this project:** Creative/Backing canonical ownership modules on the parked branch; Tests A–E persistence paths; CAS / Item 8.

---

## Creative integration split

**A. Safe now**

- Central context any Creative surface can import
- Prompt/guidance additions that only *read* `PracticeFocusContext`
- Policy tests

**B. Wait for parked branch**

- Anything touching Creative/Backing canonical ownership
- Key/session handoffs
- Mission backing state architecture
- Generated-session state
- Backing persistence architecture
- Remaining live acceptance items listed above

---

## Composition integration points (defer)

Pass `PracticeFocusContext` into future Composition coaching/guidance helpers. Do not rebuild unfinished Composition UX in this phase.

---

## Regression risks

- Must not become a new musical-key/state owner
- Must not change first/default focus per instrument
- Must not rewrite old logs’ missing focus
- Must not fight `youtube_links` duplicate lists (leave YouTube helper as-is)
- Must not conflate `practice_focus_section` (song section) with coaching focus
- Must not duplicate parked Creative stabilization fixes

---

## Test matrix (personas)

| ID | Persona | Phase 1 | Later |
|----|---------|---------|-------|
| A | Guitar / Strumming | policy + log snapshot | AMI, Practice, Upload, Backing |
| B | Sax / Tone | policy + overlays | AMI, Practice, Upload |
| C | Timing on two instruments | policy | AMI/Practice |
| D | Harmony vs Melody | policy difference | AMI/Practice visible difference |
| E | Historical Tone then current Articulation | snapshot immutability | weekly analysis |
| F | Guitar Strumming → Sax | fallback to Tone | UI |

Success criterion: same instrument + same song + same page, change **only** Practice Focus, observe meaningful coaching differences — not just a badge.

---

## Notes

Work on `feature/practice-focus-system` only. Return to parked Creative/Backing stabilization after Practice Focus foundation (and later phases) as scheduled by the user.
