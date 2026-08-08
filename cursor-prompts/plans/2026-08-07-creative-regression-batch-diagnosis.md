# Creative regression batch diagnosis (dev @ ee6b5cb)

**Branch:** `safety/creative-regression-2026-08-07-ee6b5cb`  
**Frozen (do not reopen without trace):** `creative_return_route`, `backing_session_launch_id`, run-scoped `_music_user_navigated_page_this_run`, canonical Creative selector projection, Full Song/section behavior.

## A / B — Jam Generator key → Missions / Song-Based / staff

**Symptom:** Sidebar Dm, Missions caption `Practice Key: Eb`, staff may show wrong signature.

**First authoritative writer for Eb on Missions:** `creative_key_sync.entry_jam_practice_key_authority_active()` stays true because stale `improv_jam_key` / `improv_entry_mode == Jam Session Generator` while tab is Missions. `_authoritative_practice_chart_key()` → `resolve_creative_tab_practice_key_token()` → Eb major.

**Sidebar Dm:** `sidebar_key_identity` / active `mission_jam` workflow blob (different priority order).

**Fix (safety branch):** `_catalog_song_workflow_owns_practice_key()` gate in `entry_jam_practice_key_authority_active`; mission reconcile clears jam keys + `deactivate_generated_jam_key_ownership`.

## B — Generate Example mutates Bb7 → B7 → C7

**Cause:** `_run_mission_example_generate` re-runs `_ensure_chord_selection` after sealed snap; `update_mission_example_on_blob` updated symbol without `selected_chord_index` → legacy projection desync → index walks flat progression.

**Fix:** Skip `_ensure_chord_selection` when generate context is sealed; still **read** session authority via `resolve_authoritative_chord_selection` (stale snap must not override live Bb7). Sync blob `selected_chord_index` on example save.

**Staff / key signature:** Missions caption uses `_authoritative_practice_chart_key` (same path as Eb leak). `_render_section_chord_map` uses `improv_ctx.key_center` for spelling — after jam reclaim, both should follow Dm; add manual smoke for sharps→flats workflow switch.

## C / D — Mission → Backing / Return to Mission

**Fix:** `apply_sealed_mission_return_destination()` applies alignment + session fields from `MISSION_CANONICAL_RETURN_DESTINATION_KEY`; `prepare_return_to_mission_detail()` uses it instead of generic envelope reconcile that could drift chord/mission. Sealed destination still set on each backing handoff consume (`seal_mission_return_destination_from_handoff`).

## E — Song-Based Open in Backing Studio

**Cause:** `_improv_open_backing` checked stale `improv_entry_mode == Jam Session Generator` before Song-Based path → `creative_source = entry_jam` and/or guards blocked.

**Fix:** Resolve `creative_source` from active workflow pointer + tab before entry mode; `song_based_improvisation` forces Song-Based handoff.

## F — Top-level page lost on browser refresh

**Answer (trace-proven):** The correct page was often **live in session** (`studio_page=practice`, etc.) but **autosave re-stamped Creative** into the durable payload. `_resolve_live_studio_page_for_save()` treated `_suite_last_persisted_page=creative` as authoritative whenever `_suite_page_user_nav` was cleared after nav save, so passive `autosave`/`practice_edit`/… saves wrote **Creative** into `core` / `music_workspace_state` / `studio_nav_state` even while the user was on Practice/Songs/Backing/Log/Compose. After refresh, hydration faithfully restored **Creative**.

**Fix:** Prefer **live** `session["studio_page"]` for all save reasons when set; only fall back to `_suite_last_persisted_page` when live page is empty. Stamp `_suite_last_persisted_page` when page_change save is deferred. Run-scoped user nav marker unchanged.

**Prior hydration tweak** (`hydrated_page_over_stale_canonical`) remains a secondary guard, not the primary fix.

## Tests

`tests/test_creative_regression_batch_2026_08_07.py` + existing lifecycle tests.

## Promotion

Preview on safety branch only — **do not merge to `origin/dev` until manual dev smoke passes.**

---

## G — Shared workspace boundary (Hevenu + Log repro, post-`a824bbc`)

**Live symptom:** Active song **and** studio page revert together after browser refresh (e.g. Hevenu + Log → Say + Practice). That pattern points to **one envelope** never reaching durable storage (or hydration loading an older revision), not independent nav vs song projection bugs.

**Binary question (must be answered with trace before the next fix):**

> Immediately before refresh, does durable storage contain **Hevenu + current page**, or still **Say + Practice**?

**Trace tooling (no behavior change):**

- `music_workspace_boundary_trace.py` — append-only `_music_workspace_boundary_trace` events at `force_save_*`, `serialize_payload`, `hydrate_raw_picked`, `save_complete` / `save_blocked`.
- Dev sidebar: **Workspace boundary trace** expander under `?dev=1` persistence panel (plus existing `_music_workspace_save_transaction` / startup suppression diag).

**Code-backed hypotheses (unit tests in `tests/test_workspace_boundary_hevenu_log_trace.py`):**

| If durable before refresh | Then |
|---------------------------|------|
| Still Say + Practice | **A / B / D** — save pipeline: live session diverged but writes blocked or stale envelope materialized (`startup_canonical_unchanged` on `song_edit` while `startup_fingerprint_matches` stays true; deferred `page_change` flush uses `reconciliation` origin → blocked as non–`user_navigation`). |
| Hevenu + Log | **C** — hydration / workspace id / revision selection (inspect earliest `hydrate_raw_picked` before `prepare_studio_nav`). |

**Manual repro checklist (preview + `?dev=1`):**

1. Hydrate Say + Practice → change song to Hevenu → nav to Log → wait for autosave.
2. Before refresh: copy **Binary question** JSON from boundary trace + last `serialize_payload` / `save_*` events + `force_save_block_reason`.
3. Refresh: first `hydrate_raw_picked` payload page/song/rev vs account `workspace_id`.

**Status:** Trace landed on safety branch; **no save/hydration fix** until preview trace confirms which column in the table above applies.

**Prior item F (`a824bbc` autosave page):** May still matter for stale Creative in passive autosave, but does **not** explain song + page reverting together unless the whole workspace write never commits.

