# Phase 1 Item 5 — Live acceptance runbook

**Contract:** [2026-08-03-item5-refresh-cold-reboot-persistence.md](./2026-08-03-item5-refresh-cold-reboot-persistence.md)  
**Do not mark Item 5 live-accepted** until **both** tests below pass with **unchanged authoritative revision**.

**Environment:** Streamlit Cloud `dev`, Daniel workspace, URL includes **`?dev=1`**.

**Precondition (both tests):**

- Authoritative cloud revision **315** (or current equivalent — record `loaded_revision` from Item 5 panel).
- Global: **Cm** / **Piano** / **Beginner** / **Left-Hand Patterns**.
- Item 2 tuple: **Melody A** / **Ab** / index **3** / label **Melody A · Ab**.
- Harmony Map: **Melody A** / **G7** (independent from tuple chord).
- Mission **example** and **practice lick** present (`example_present` / `lick_present`).
- Studio: **Backing** → **Mission Backing** (`backing_subview` / `backing_context_source` = **mission**).

---

## TEST A — Hard refresh

1. Open Creative or Backing as needed to confirm state matches preconditions.
2. Expand sidebar **Phase 1 live-path (?dev=1)**.
3. Scroll to **Phase 1 Item 5 — Refresh / cold reboot certification**.
4. Record (screenshot or copy): `certification_run_id`, `loaded_revision`, `restored_*`, `item2_target_tuple`, `item4_harmony_map`, artifact contexts.
5. **Ctrl + Shift + R** (hard refresh).
6. **Do not** click any controls or navigate.
7. Re-open **Phase 1 live-path** → Item 5 panel.

**Expected:**

| Field | Expected |
|-------|----------|
| `fetch_source` | `network` |
| `loaded_revision` / `current_cloud_revision` | Same as step 4 (e.g. **315**) |
| `revision_unchanged` | `True` |
| `revision_reserved_during_startup` | `False` |
| `payload_built_during_startup` | `False` |
| `cloud_write_attempted` / `cloud_upsert_attempted` | `False` |
| `startup_write_attempted` | `False` |
| `item1_violations` … `item4_violations` | `[]` |
| `passive_audit` | May show `semantic_drift_keys`; `would_gather_keys=[]`; `violations_suppressed=context_gather_blocked_for_passive_reason` is **OK** |
| `certification_passed` | `True` |
| Restored globals, tuple, Harmony Map, artifacts | Match step 4 |

---

## TEST B — Cold reboot

1. Note authoritative revision from Test A (or repeat precondition check in normal window).
2. Open **Incognito** (or equivalent empty browser profile).
3. Sign in → open Music app on **`dev`** with **`?dev=1`**.
4. **Do not** change instrument, key, page, or Creative controls.
5. Open Item 5 panel; record same fields as Test A.

**Expected:**

- Same table as Test A.
- `session_start_kind` ideally `cold_reboot` (may show `unknown` if apply-reason heuristics differ — use revision + violation + write flags as primary pass/fail).
- **Backing → Mission Backing** visible without extra navigation.
- Revision unchanged vs pre-incognito record.

---

## Fail policy

If either test fails:

1. Capture Item 5 `certification_failures`, Items 1–4 violation lists, Page cloud durability trace, startup suppression diag.
2. Fix **smallest** hydrate/project/audit gap only — no new save reasons, no “repair save”, no ownership redesign.
3. Re-run **both** tests before sign-off.

**Sign-off:** Update [phase1 remaining](./2026-08-02-phase1-creative-state-persistence-remaining.md) Item 5 ✅ with date, revision, commit SHA.
