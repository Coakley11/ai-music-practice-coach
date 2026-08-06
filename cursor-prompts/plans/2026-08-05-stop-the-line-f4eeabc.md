# STOP-THE-LINE — Cloud deploy f4eeabc (FAILED_LIVE)

**Last updated:** 2026-08-05

## Deploy verification

| Field | Status |
|--------|--------|
| Cloud SHA | `f4eeabc272e4ee070de4b5a68e36ac7e7d3032c9` — **VERIFIED** (`[music_deploy] branch=dev preflight=OK`) |
| Functional commit | `69f54b7` — pre-widget generated key bootstrap |
| Classification | **FAILED_LIVE** |
| Early bootstrap wiring | **PRESENT** (`pre_widget_bootstrap_consumers` before auth) |
| Full-app late projection / rerun interference | **CONFIRMED** (Cloud logs) |
| Style Jam key editing | **Unresolved** |
| Generator key editing | **Unresolved** |
| Hevenu sidebar authority | **Unresolved** |
| Practice in Backing Jam | **Unresolved** |
| Next deployment | **BLOCKED** until full-runtime harness passes |

## Primary live pattern (run_seq 7, 10, 11, 15, 16)

```
[mission_backing_handoff] queued seq=1 lick=False mode=mission_backing
[music_projection] widgets_locked=True result=REQUIRES_PRE_WIDGET_ACTIVATION rollback_mode=full deferred_projection=True
[music_run] BEFORE_RERUN caller_function=_tab_entry_modes reason=direct_st_rerun
```

Note: `handoff_mode=mission_backing` in traces means `with_practice_lick=False`, not necessarily `backing_source=mission`.

## Root cause (code audit — not yet patched)

1. **Late workflow activation during Entry & Jam render** — `_on_entry_mode_change` → `activate_workflow_for_entry_mode` → `activate_workflow` → `commit_staged_workflow` → `project_active_blob_to_legacy_session` while `widgets_likely_instantiated` is true (sidebar sets lock before Creative body). This raises `RequiresPreWidgetActivation` with **`rollback_mode=full`** (not generated-key defer).

2. **Spurious backing queue** — `commit_staged_workflow` rollback path calls `queue_pending_backing_workflow_handoff` **without** `arm_pending_backing_handoff_consume`. Bootstrap consume clears pending as `not_consume_armed`; the same entry/tab activation can re-queue **`seq=1`** on the next run.

3. **`st.rerun` attribution** — `music_run_boundary` records **`caller_function=_tab_entry_modes`** only for **direct** `st.rerun()` inside `_tab_entry_modes` (Generate progression ~705, Generate jam session ~827). Not from `request_app_rerun` (skipped in stack). Parent tab sync rerun uses `request_app_rerun` and would not show `_tab_entry_modes`.

4. **Not** the explicit Mission Backing button path on Style Jam / Generator (`on_click=on_open_backing` only queues when `_improv_open_backing` runs).

## Harness gate (safety branch)

- `streamlit_creative_full_production_harness.py` + `tests/test_streamlit_creative_full_production_harness_apptest.py`
- Run: `python -m pytest tests/test_streamlit_creative_full_production_harness_apptest.py -v`
- **Repro confirmed:** `test_repro_entry_mode_switch_queues_unarmed_backing` (matches Cloud seq=1 + `REQUIRES_PRE_WIDGET_ACTIVATION` + bootstrap `not_consume_armed`)
- **Gates still xfail:** entry-mode must not queue backing; Style Jam C→D under full shell; late `activate_workflow_for_entry_mode` while locked
- Must flip xfail → pass before any production fix ships.

## Production freeze

No narrow production patches on `dev` until harness proofs pass. Work on `safety/stop-the-line-2026-08-05`.
