# Music app — navigation & page-load speed pass

**Last updated:** 2026-08-04  
**Branch:** `dev`  
**Status:** Queued (P0, parallel to mission handoff persistence)  
**Baseline:** Phase 1 Items **1–8** frozen @ **`8ef698e`** — no regression to persistence correctness, CAS, or Item 8 diagnostics.  
**Existing probes:** `music_dev_perf.py`, `music_dev_nav.py` (`?dev=1` counters on Missions artifact project).

---

## Problem

Perceived slowness on real navigation:

- Home → Creative
- Creative sub-tab switches (Entry & Jam ↔ Missions ↔ Metrics & AI)
- Creative ↔ Backing Studio / Backing Jam
- Missions → Upload Analysis
- Upload Analysis → Creative
- Major sidebar page changes

Root causes (hypothesis — to validate with measurements):

- Heavy work runs **before** active page/tab is known (`streamlit_music_practice_app.py` top-level).
- Inactive Creative tabs still project artifacts, rebuild mission context, or render hidden widgets.
- Backing WAV generation on reruns without Play or musical input change.
- Redundant cloud fetch/save on page-only navigation.
- Duplicate callback + full rerun chains (Streamlit widgets).
- Upload Analysis initializes backing or preprocesses audio before Run AI.

---

## Goal

Navigation alone must **not**:

- generate backing audio
- preprocess recordings / feature extraction
- run AI preparation
- perform unnecessary cloud writes or CAS revision bumps
- rebuild notation/mission examples when inputs unchanged
- rehydrate identical workspace repeatedly in one session

Target: measurable wall-clock reduction on listed routes with **unchanged** user-visible correctness.

---

## Scope

### A. Route gating (`streamlit_music_practice_app.py`)

- Determine `studio_page` / suite page early; **defer** page bodies until gated.
- Move expensive imports and initialization below the active-page branch.
- Creative: only invoke `render_improvisation_intelligence_lab` path for active sub-tab (already partially via `_normalize_improv_tab_for_render` — audit full tree).
- Do not render hidden recording/audio/metrics/analysis components (Streamlit still executes — remove or guard with early return).

### B. Creative / Improvisation Intelligence

- Lazy expanders: no mission example regeneration if canonical artifact fingerprint unchanged.
- Skip `project_mission_artifacts_from_canonical` when material inputs unchanged (extend dev counters → production guards).
- Mission practice context: rebuild only when chord/mission/transport signature changes.
- Eliminate redundant `st.rerun()` from callbacks where session state suffices.

### C. Backing Studio / Jam

- WAV generation **only** on Play or when `BackingMusicalProfile` / exact-chord signature changes.
- Reuse in-process cache (`mission_exact_chord_backing._WAV_CACHE`, backing generation cache) across harmless reruns.
- Avoid decode/resample/serialize loops for unchanged audio in session.

### D. Upload Analysis

- Prepared take load: metadata + lazy audio fetch only.
- Defer librosa/feature extraction until **Run AI Analysis**.
- Cache preprocessing by audio fingerprint (safe, idempotent).
- Metric/criteria-only changes → no audio reprocessing.
- **No** exact-chord backing player on Upload Analysis (already product rule — enforce in code audit).

### E. Cloud / persistence efficiency

- No save when navigation-only (page owner + deferred save patterns).
- Dedupe equivalent save requests in one rerun.
- Skip upload when fingerprint unchanged (ties to mission handoff persistence plan).
- Preserve stale-device fail-closed behavior — speed pass must not weaken CAS.

### F. Measurements (`?dev=1`)

Extend `music_dev_perf` / nav counters to report per-route spans:

| Route | Metrics |
|-------|---------|
| Initial Creative load | wall ms, cloud R/W, artifact projections, mission context builds |
| Open Missions tab | same + inactive tab work count (target 0) |
| Creative tab switch | same |
| Home → Creative | full app gate |
| → Backing Studio / return | backing builds, audio bytes |
| Missions → Upload Analysis | handoff work, audio upload |
| Upload Analysis criteria change | preprocessing calls (target 0) |
| Refresh with pending take | hydrate ms, fetch count |

Deliver **before/after** table in commit message or plan appendix after first optimization slice lands.

---

## Implementation order (isolated commits)

1. **Instrumentation** — uniform route labels; baseline capture on `dev` (no behavior change).
2. **Main app page gate audit** — move top offenders below `studio_page` switch.
3. **Creative tab lazy render** — guard `_tab_*` dispatch; artifact projection skip.
4. **Backing play-only generation** — audit all `generate_backing_track` / exact-chord call sites.
5. **Upload Analysis defer preprocessing** — fingerprint cache.
6. **Navigation save dedupe** — no-op when disk state unchanged.
7. **Before/after report** — document in this plan + tasks.md Notes.

**Commits:** separate from mission handoff persistence where practical; both P0.

---

## Acceptance

- `?dev=1` route spans show reduced counts on inactive pages (0 heavy components).
- Documented before/after wall-clock on at least 8 routes (local or Streamlit Cloud).
- All existing persistence tests + Phase 1 Item 8 CAS tests still pass.
- No change to frozen Item 8 diagnostic panel fields.

---

## Out of scope (this pass)

- UI polish-only CSS (P1 separate commits).
- Reopening Tests A–E restore architecture.
- New product features unrelated to performance.
