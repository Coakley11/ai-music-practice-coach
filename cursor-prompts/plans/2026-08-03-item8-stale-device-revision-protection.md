# Phase 1 Item 8 — Stale-device revision protection & overwrite prevention

**Last updated:** 2026-08-03  
**Status:** **LIVE ACCEPTED & FROZEN** — phone current-device save + stale Dell **TEST A/B/C** passed on `dev` @ build **`8ef698e`**.  
**Acceptance baseline (do not regress without `?dev=1` proof):** `4a446a0` (atomic CAS), `62bf143` (applied revision hydrate), `4192fa2` (nested CAS filter), **`8ef698e`** (logical revision unification + Item 8 diagnostics).

**Prerequisites (frozen — do not redesign):**

| Layer | Live-accept / freeze anchor |
|-------|-----------------------------|
| Items 1–5 | Through `b989516`; doc `cc00cda` |
| Item 6 Dell → phone | **FROZEN** @ **317** |
| Item 7 phone → Dell (stale reader hydrate) | **FROZEN** @ **319** — [contract](./2026-08-03-item7-phone-dell-cross-device-persistence.md) |
| **Item 8** stale write + recovery | **FROZEN** @ **`8ef698e`** — live path through cloud **325** after TEST C |
| Monotonic `workspace_revision`, strict egress, startup suppression, Items 1–4 save reasons | Accepted architecture — no fork |

**Phase 2** Style Identity engine may proceed per [tasks](../music_app_tasks.md); Item **8** implementation and `?dev=1` Item 8 panel are **frozen** like Items 1–7.

---

## Purpose

Prove that a device holding **stale local workspace state** at revision **L** (where **L < cloud R**) **cannot silently upsert** and clobber a **newer cloud document** at **R** written by another device or session.

Item 8 is the **write-side** cross-device gate. Items **6–7** proved **read** paths (network hydrate wins). Item 8 proves **save** paths reject or defer stale writes until the device reconciles with cloud.

---

## Live acceptance (2026-08-03) — **PASS**

**Environment:** Streamlit Cloud `dev`, Daniel workspace, **`?dev=1`**, build **`8ef698e`**.

| Scenario | Result | Summary |
|----------|--------|---------|
| Phone current-device save | **PASS** | Nested CAS @ blob **321** → `response_row_count=1`, confirmed @ applied **323** |
| **TEST A** Stale Dell | **PASS** | Dell applied **321**, cloud **323**; `stale_write_blocked=true`; no overwrite |
| **TEST B** Authoritative reader | **PASS** | Phone refresh @ **323**; Harmony unchanged; TEST A did not mutate cloud |
| **TEST C** Recovery | **PASS** | Dell refresh @ **323**; save @ expected **323** → candidate **325**; confirmed |

**Implementation notes (frozen):**

- `music_metrics_logical_revision.resolve_logical_stored_revision` — single logical revision; top-level used only when consistent with blob.
- CAS filter path matches logical source (`music_workspace_state` nested path when top-level absent/stale).
- Successful writes sync `metrics.workspace_revision` + blob surfaces via `sync_metrics_revision_surfaces`.
- Item 8 dev panel: `logical_revision_source`, `selected_cas_filter_path`, `violations_current_attempt`, `cas_http_trace`.

**Do not:** weaken atomic CAS, restore unconditional upsert, or change Items 1–7 ownership without unfreeze.

---

## Distinction from Items 6–7

| Item | Question answered |
|------|-------------------|
| **6–7** | After remote save @ **R**, does the other device **read** **R** correctly without spurious startup write? |
| **8** | With local state still at **L < R**, does a **local user save attempt** **fail closed** (no confirmed upsert @ stale revision) and leave cloud @ **R** intact? |

---

## Authoritative failure / success signals (reference)

### Stale writer attempt (device behind cloud)

| Signal | Expected (pass) |
|--------|-----------------|
| `cloud_write_succeeded` / `cloud_confirmed` | **false** OR blocked pre-upsert |
| Authoritative **cloud revision after attempt** | Still **R** |
| `stale_write_blocked` / `conflict_detected` | **true** when CAS rejects |

### Current-device save (synchronized writer)

| Signal | Expected (pass) |
|--------|-----------------|
| `conditional_write_rows_affected` | **1** |
| `cloud_confirmed` | **true** |
| `logical_revision_source` + filter path | Align with stored row |

---

## Live-test script (reference — passed 2026-08-03)

See **Live acceptance** table above. Legacy rev-319 script preserved in git history; baseline after phone PASS was cloud **R=323**, TEST C exit **325**.

---

## Save / write contract (frozen)

- Music cloud writes: `save_current_state_conditional_cas` only (no merge-duplicates upsert for music full_session).
- Pre-save: `prepare_music_conditional_write` + logical revision from full metrics row.
- Diagnostics: `collect_phase1_item8_stale_write_certification`, `phase1_item8_stale_write_certification.py`.

**Existing hooks:**

- `music_metrics_logical_revision.py`, `music_workspace_conditional_cloud_write.py`, `suite_storage_supabase.py`
- `workspace_revision.py`, `music_device_applied_revision.py`
- `music_egress_strict_save.py`, `music_workspace_cloud_save`

---

## Out of scope (unchanged)

- Full conflict-merge UX / version history (v1 = block or resync-then-save)
- `main` merge unless explicit release
