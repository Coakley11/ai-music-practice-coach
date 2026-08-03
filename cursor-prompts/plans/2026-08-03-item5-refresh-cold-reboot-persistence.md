# Phase 1 Item 5 — Refresh and cold-reboot persistence

**Last updated:** 2026-08-03  
**Status:** **Next** — contract only (no implementation started)  
**Prerequisites (frozen — do not redesign):**

| Layer | Live-accept commits / anchor |
|-------|------------------------------|
| Studio page persistence | `38664fc`–`ad68e71` (rev **193** baseline) |
| Display-key + startup queue | `616f4e4`, `2aff988`, `f87c1f9` |
| Item 1 selectors | `549578d` |
| Item 2 mission config | `c6c2f41` |
| Item 3 artifacts + Mission Backing handoff | `616f4e4` — [contract](./2026-08-02-item3-mission-artifact-persistence.md) |
| Item 4 context snapshots | **LIVE-ACCEPTED** `5edb81c`, `aa77e58`, `d97da03`, `c72a879` — [contract](./2026-08-03-item4-key-section-creative-context-snapshots.md) |

Items **6–8** (Dell↔phone, stale revision) are **out of scope** for Item 5.

---

## Purpose

Prove that a **fully configured Creative workspace** at a known authoritative cloud revision survives:

1. **Browser hard refresh** (same browser profile; new Streamlit run).
2. **Cold Streamlit reboot** (empty `session_state`; network fetch only — incognito or equivalent).

Without:

- Semantic field drift across Items 1–4,
- Spurious autosave / revision reservation / Supabase upsert,
- Stale diagnostic violations leaking across runs,
- Regression of frozen global ownership (Instrument / Level / Focus / Display key),
- Regression of studio page / Mission Backing / strict egress architecture.

Item 5 is an **integration acceptance gate**, not a new persistence channel.

---

## “Workspace matches pre-refresh” — authoritative checklist

After refresh/reboot, **network** hydration must restore (minimum Daniel acceptance profile):

### Global controls (frozen ownership)

| Field | Expected behavior |
|-------|---------------------|
| `display_key` | Unchanged (e.g. **Cm**) — sidebar authoritative path |
| `instrument`, `level`, `focus` | Unchanged — not rewritten from Creative hydrate |

### Studio navigation (frozen)

| Field | Expected behavior |
|-------|---------------------|
| `studio_page` | Same page family as pre-refresh (Creative / Harmony Map / Backing per test script) |
| Mission Backing handoff state | If test includes handoff, backing subview restores without extra cloud write |

### Item 1 — selectors

| Field | Restored from `creative_workspace_state` |
|-------|------------------------------------------|
| `improv_intelligence_tab`, entry/lab modes | Match pre-refresh canonical |

### Item 2 — mission config + target tuple

| Field | Restored |
|-------|----------|
| `improv_mission_pick`, progression/options | Match |
| `ii_selected_section`, `ii_selected_chord_index`, `ii_selected_chord`, `ii_selected_chord_label` | **Atomic tuple** unchanged |

### Item 3 — artifacts

| Field | Restored |
|-------|----------|
| `improv_motif`, example, practice lick | Present; historical `key_center` / artifact keys unchanged |
| Mission example + lick | `example_present` / `lick_present` true when saved pre-refresh |

### Item 4 — context snapshots

| Field | Restored |
|-------|----------|
| `harmony_map_section`, `harmony_map_chord` | Match (e.g. Melody A / G7) |
| `creative_session.tool_type` | Match (e.g. `song_based_improvisation`) |
| `creative_session` display-key **snapshot** | Match (e.g. **Cm**) — not global SSOT fork |
| Harmony Map vs mission tuple | **Independent** (Item 2 Ab vs Item 4 G7 allowed) |

### Envelope integrity

- Full `creative_workspace_state` retains Items **1–3 required fields** (Item 4 contract envelope guard).
- `fetch_source=network`, `fetched_revision` = pre-refresh authoritative revision (e.g. **315**).
- **No new** `reserved_write_revision`, upsert, or monotonic revision bump during refresh-only run.

### Passive / startup diagnostics (`?dev=1`)

| Signal | Expected on refresh-only |
|--------|---------------------------|
| `startup_write_attempted` | `false` |
| Item 1–4 `violations` | `[]` (run-scoped; no stale leak) |
| Item 4 `passive_audit` | May show semantic drift keys (e.g. `improv_style_meta`) with `would_gather_keys=[]`, `violations_suppressed=context_gather_blocked_for_passive_reason` |
| `passive_save_requested` / `passive_payload_built` / `passive_revision_reserved` / `passive_cloud_write_attempted` | All `false` |

---

## Save / write contract (Item 5 adds no new save reasons)

Refresh and cold reboot are **read paths**. Allowed side effects:

- Hydrate canonical → project to session/widgets.
- Startup suppression arm/release per frozen queue.
- Diagnostic journals and run_seq increment.

**Forbidden** on refresh-only (no user interaction):

- New cloud save reasons (including passive autosave upsert).
- Revision reservation when fingerprint / canonical unchanged.
- Mutating `creative_session.updated_at` for hydration-only.
- Gathering Item 1–4 canonical fields on `autosave` when user-event absent (existing gates must hold).

---

## Distinction from Item 4 live-accept

Item 4 proved **Item 4 fields + passive audit** on hard refresh @ rev **315**.  
Item 5 proves the **same refresh discipline** for the **whole frozen Phase 1 Creative stack** (Items 1–4 + globals + page + envelope) across **both** refresh modes, with a written live runbook and automated cold-reboot regression tied to a **full** envelope fixture.

---

## Focused implementation plan (Item 5 only)

**Goal:** Live sign-off + regression lock — minimal code unless a gap is proven.

### Step 1 — Live runbook (manual)

1. On Streamlit Cloud `dev`, `?dev=1`, Daniel workspace: establish state at known rev (post Item 4: tuple + Harmony Map + artifacts + Cm globals).
2. Record dev panel snapshot (Phase 1 expander + Item 4 block): revision, tuple, harmony, artifacts, violations.
3. **Hard refresh** → verify checklist above.
4. **Cold reboot** (incognito or cleared site data, same account) → verify checklist again.
5. Sign off with revision unchanged and `violations=[]`.

### Step 2 — Automated regression (target)

Extend / add tests (names indicative):

- `test_item5_hard_refresh_fixture_restores_full_creative_envelope` — simulate `apply_music_disk_state` / `prepare_creative_workspace_for_render` with rev **315**-style payload; assert no gather on autosave; violations empty.
- `test_item5_cold_reboot_no_upsert_full_envelope` — build on `test_cold_reboot_no_upsert_when_canonical_matches` with Items 1–4 keys populated.
- Optional: single dev diagnostic aggregator **`collect_phase1_item5_refresh_diagnostics`** (read-only) — loaded/final revision, startup suppression, Items 1–4 passive_audit summary — **display only**, no routing changes.

### Step 3 — Fix policy

If live or test fails:

- **Smallest** fix in hydrate/gather/audit only; **no** redesign of Items 1–4 ownership or save reasons.
- Separate commit from Item 5 runbook/doc updates.
- Re-run Item 4 frozen regression suite before re-accept.

### Step 4 — Sign-off artifact

Update [phase1 remaining](./2026-08-02-phase1-creative-state-persistence-remaining.md) Item 5 ✅ with date, revision, and commit SHA. Move summary to [completed features](../music_app_completed_features.md).

---

## Out of scope (Items 6–8)

| Item | Topic |
|------|--------|
| 6 | Dell → phone pull |
| 7 | Phone → Dell pull |
| 8 | Stale-device revision protection / conflict UX |

Do **not** merge `main`. Do **not** start Phase 2 Style Identity engine until Items **5–8** complete.

---

## Code map (read / test only unless gap found)

| Area | Role |
|------|------|
| `suite_user_persistence.py`, `apply_music_disk_state` | Cloud/disk hydrate |
| `music_startup_save_suppression.py`, `display_key_startup_save_queue.py` | Startup write discipline |
| `creative_workspace_state_persistence.py` | `prepare_creative_workspace_for_render`, gather |
| Items 1–4 `*_persistence.py` | Passive audits (frozen semantics) |
| `music_workspace_canonical_fingerprint.py` | Volatile field exclusion |
| `music_phase1_dev_diagnostics.py` | Live evidence |
| `tests/test_music_startup_save_suppression.py` | Cold reboot pattern |

---

## Live acceptance (Item 5)

**Runbook:** [2026-08-03-item5-live-runbook.md](./2026-08-03-item5-live-runbook.md)

Same account, Streamlit Cloud `dev`, `?dev=1`:

1. Pre: user saves at least one Item 1–4 user event so rev is known (e.g. **315**).
2. Hard refresh → full checklist; revision **315**; no upsert.
3. Cold reboot → full checklist; revision **315**; no upsert.
4. All Item passive audits: `startup_write_attempted=false`, `violations=[]`.
5. Document commit SHA at sign-off in tasks + completed features.
