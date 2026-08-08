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

**Status:** Existing `tests/test_mission_backing_two_missions_consecutive.py` passes on safety branch. Stale Backing/Return likely downstream of wrong mission chord/key context (B) or handoff not re-sealed when mission pick changes — re-smoke A→B→C on preview after key/generate fixes. Frozen return-route layers unchanged.

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
