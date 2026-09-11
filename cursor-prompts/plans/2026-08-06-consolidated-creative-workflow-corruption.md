# STOP-THE-LINE — Consolidated Creative workflow corruption

**Last updated:** 2026-08-06  
**Deploy context:** `origin/dev` @ `5049c17` (functional production `f311b93`)  
**Classification:** Cross-workflow canonical-owner and artifact-integrity failure — not isolated UI bugs.

## Executive summary

The live hybrid UI (Hevenu D minor + Style E major attempt + stale Generator Eb + sidebar C major + Jewish-ballad/Bossa labels + Mission scope) is produced by **independent field resolution** from legacy session keys, `backing_context` rebuilders, and heuristics that **do not validate a single owner-bound artifact**. The entry-mode pre-widget fix (`f311b93`) reduced false backing handoffs but **did not** make mixed-owner backing or generation impossible.

---

## Field-by-field trace (reported hybrid)

| Visible field | Likely actual source | Expected owner | Actual owner / contract break |
|---------------|---------------------|----------------|------------------------------|
| Backing source banner `Entry & Jam · …` | `BackingContext.source_label` + transport groove from `_backing_groove_style_from_ctx` | Active generated snapshot | `entry_jam` banner OK; groove may come from **catalog** `_canonical_active_song_groove` when ctx BPM/groove not pinned |
| Card `Jazz Swing · Jam Session Generator` | Backing page workflow card reads `_backing_launch_workflow` / `workflow_type_from_backing_source(entry_mode)` | `style_jam` if user was in Style Jam | **`resolve_entry_jam_entry_mode`** can return `Jam Session Generator` when `improv_jam_session.sections` exists and widget ≠ Style Jam; Style Jam UI also passes `workflow="jam"` on Open Backing row |
| Practice concert key **C major** | `sections_dict_from_backing_context` uses `session.display_key` first (line ~1729); `_live_backing_concert_keys` merges **global** `display_key` with `creative_entry_concert_key` | `style_jam` / `jam_session_generator` blob `keys.practice_*` | **Catalog sidebar** `display_key` (major pitch-class from Hevenu practice UI) wins over widget E / blob Eb minor |
| Progression **Fm7–Bb7–Ebmaj7** (Eb tonal center) | `_entry_jam_sections_dict` → `improv_jam_session.sections` **or** stale `improv_generated_sections`; retranspose uses wrong `practice_key` | Current Style Jam artifact after Generate | **Stale Generator** or prior generation sections; key label not tied to section origin |
| Badges Style/Mood/Groove **Jewish ballad / Mellow** | `build_entry_jam_context`: `improv_mood` default `"Mellow"`; `improv_style` / `improv_jam_style`; `sync_creative_style_jam_meta` falls back **`improv_jam_*` on Style path** (lines 324–327); mission restore **`_mission_jam_style_resolution`** on cloud restore | Style Jam control fingerprint at generate time | **Shared** `improv_style_meta` + catalog song defaults + **un-cleared** Generator widgets |
| Sections **Jewish ballad · … · A (Bossa Nova)** | Section **names** from generated map keys or catalog section titles; Bossa from **`improv_style`** style id (Style Jam session id = style name) | Style Jam `section_map` only | **Mixed** section dict keys + catalog naming |
| Scope (Mission / single chord) | `backing_scope_for_workflow` + `improv_selected_section` / Mission keys | Owner-specific | Mission **`ii_selected_*`** and scope helpers applied while `entry_jam` source active |

---

## Root mechanisms (code-level)

### 1. Backing is assembled, not loaded from one artifact

- `open_backing_from_creative` → `build_entry_jam_context` **recomputes** a `BackingContext` from many session keys (`backing_context.py` ~881–1011).
- **`bound_pick_key`** = `_current_pick_key(session)` → active catalog (**Hevenu**) always bound into generated backing context.
- **`resolve_entry_jam_entry_mode`** (`backing_source_navigation.py` ~1005–1044): if `improv_jam_session` has sections and widget is not exactly `"Style Jam Mode"`, forces **Jam Session Generator** — stale Generator blob while user selects Style Jam.
- **`sections_dict_from_backing_context`**: `practice_key = session.get("display_key") or ctx.concert_key` — **global sidebar** overrides ctx concert key for transpose/display.

### 2. Generate Progression / Generate Jam Session are not generation-intent consumers

- `improvisation_intelligence_ui.py` ~657–705: button writes `improv_generated_sections` / calls `commit_style_jam_generation` **in render body**, then **`st.rerun()`** — not pre-widget typed intent.
- `commit_style_jam_generation` (`music_workflow_generated_session.py`): **reuses** `workflow_session_id` = `improv_style` style name; **`mutate_active_workflow`** in place when pointer matches — **no mandatory new artifact_id / generation_seq / request token**.
- Legacy keys remain authoritative for backing: `improv_generated_sections`, `improv_jam_session`, `improv_style_meta`.

### 3. Workflow blobs vs legacy dual-write

- `build_workflow_blob_from_legacy` reads **`display_key` / concert_key`** for all owners (`music_workflow_compatibility.py`) — catalog practice key can populate **generated** blob keys.
- Projection to legacy after activation still feeds **`display_key`**, `improv_style_meta`, jam session — owner guard is partial (hydrate guard only on key edit path).

### 4. Song-Based / Mission / Harmony scope bleed

- `_song_improv_sections_dict`: if `improv_song_concert_sections` has **≤1 chord**, does not return early — may fall through; Mission can leave **single-chord** state in session keys used by song improv builders.
- `build_mission_context` progression = **one chord**; Mission restore via `restore_session_widgets_from_backing_context` writes **`ii_selected_chord`** back to session (~1161–1165).
- Song-Based uses `sync_song_improv_sections_to_practice_key` keyed off **`session.display_key`** (major/minor not separated in all paths) — **original D minor vs practice Eb minor** not modeled in backing card.

### 5. Return to Creative Page

- `rehydrate_creative_from_backing_context` restores widgets from **backing_context snapshot**, not from **workflow blob artifact_id** + return token.
- Entry jam branch (~1212+): calls `resolve_entry_jam_entry_mode` again — can **flip** Style ↔ Generator on return.
- **`sync_live_keys_from_backing_context`** may push backing concert key into **global** `display_key`, affecting Hevenu sidebar.

### 6. Mode-aware keys

- `_tonic_mode_from_token` / pitch-class parsers used across compat and generated commits — **Eb major vs E-flat minor** collapse when `display_key` is pitch-class only.
- `creative_entry_concert_key` returns **widget string only** (no mode authority separate from blob).
- `validate_workflow_consistency` already detects **`STYLE_JAM_OPENED_AS_GENERATOR`** and **`GENERATED_JAM_CATALOG_STYLE_LEAK`** but is **diagnostic only** — no fail-closed render block.

---

## Why `f311b93` did not fix this

| Fixed | Not fixed |
|-------|-----------|
| Entry-mode radio → queue workflow activation pre-widget | Backing context still **multi-source rebuild** |
| No false `queue_pending_backing_workflow_handoff` on projection guard for entry activation | Open Backing still **`build_entry_jam_context`**, not artifact handoff |
| Generated-key seq/token idempotency | **Generate** buttons still synchronous + `st.rerun()` |
| | No **WORKFLOW_OWNER_INTEGRITY_FAILURE** fail-closed on backing render |
| | No **SongPracticeSnapshot** / **GeneratedWorkflowSnapshot** enforcement |

---

## Harness gap (committed @ `e14afd7`)

Current full-production harness covers Entry-mode key edits, dual Style/Generator keys, explicit Open Backing, Hevenu **resolver** identity — **not** the 27-step continuous session in this report (Song-Based ↔ Mission ↔ Harmony ↔ Style generate ↔ backing coherence ↔ return ↔ refresh).

---

## Required correction shape (single coherent change — not started)

1. **Snapshots** per owner (song / mission focus / style jam / generator) with artifact_id, revision, generation_seq, return_destination.
2. **Generate** → capture intent only → pre-widget consumer → validate → atomic commit → render from snapshot only.
3. **Backing handoff** → typed payload (owner, session_id, artifact_id, revision, fingerprint, return_destination) → backing page **loads one snapshot**; forbid catalog/legacy fallbacks when snapshot present.
4. **Owner validation gate** before Creative/Backing render → `WORKFLOW_OWNER_INTEGRITY_FAILURE` fail-closed.
5. **Mode-aware keys** in blob + UI (original vs practice tonic/mode).
6. **Harness** — full continuous scenario; **zero XFAIL**.

---

## Next steps (process)

1. Extend harness with continuous scenario (this doc § Full-Production Harness Requirement).
2. Reproduce hybrid card in AppTest (assert owner fields + fail-closed).
3. Implement snapshot + validation layer (minimal production surface).
4. Regression superset ×2; deploy only after harness green + live smoke.

**Do not deploy label/badge/dropdown micro-fixes.**
