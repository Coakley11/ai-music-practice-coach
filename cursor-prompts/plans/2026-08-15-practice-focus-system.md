# Practice Focus System

**Last updated:** 2026-08-15  
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

1. AMI — consume prompt block in practice-plan / “what should I practice” paths; do not hijack theory questions
2. Practice page — replace weak `_focus_area` fallthrough with policy suggestions
3. Upload / AI Coach — stamp snapshot at analysis start; bias metric selection/weighting/summary
4. Practice Log + weekly analysis — pass historical snapshots into the model; distinguish current vs historical
5. Multitrack — inject context into analysis/guidance where metrics exist

### Phase 3 — Stable instructional layers on current `dev`

6. Backing **coaching/instructions only** (not ownership/state machinery)
7. Custom tools
8. Other completed surfaces with natural hooks

### Phase 4 — Creative (after parked branch)

Deeper Mission / Style Jam / Jam Generator / Harmony Map / Live Coach integration against accepted Creative architecture. Reconcile branches carefully; do not cherry-pick `44403d4` internals into this branch.

### Phase 5 — Composition

Later, once Composition itself is sufficiently complete. Clean `PracticeFocusContext` hook is enough for now.

---

## Files / modules

**New:** `practice_focus_policy.py`, `practice_focus_context.py`, `practice_focus_snapshot.py`, `tests/test_practice_focus_policy.py`

**Touched in Phase 1:** `practice_setup_controls.py`, `practice_setup_globals.py` (docs), `practice_log_state.py`, `music_coach_ami/context_reader.py`, `upload_history.py`

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
