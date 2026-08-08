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

**Status (trace @ safety `837c800`, preview):** **Column A — save-side startup suppression**, not hydration.

**Trace fingerprint (Hevenu + Log nav before failed save):**

- Live/canonical page = `log`, song = Hevenu, `page_change_origin=user_navigation`, `page_user_nav=true`, rev **894**.
- Durable cloud rev **894** still **Creative + Hevenu** (hydration faithful).
- `latest_serialize_payload` / `latest_save_complete` = **NULL**; blocked **before payload build**.
- `block_reason` / `force_save_early_return_reason` = **`startup_suppression_armed_page_change`**.
- Simultaneously: `restore_finalized_stage=late_end_of_run`, but **`startup_suppression_released=NULL`**, **`startup_restore_in_progress=true`**, **`startup_suppression_armed=true`**, `startup_fingerprint_matches=false` (post-nav canonical diff — not restore noise).

**First incorrect boundary:** Startup restore reached finalize, but **suppression lifecycle did not release** when canonical fingerprint no longer matched hydrated (legitimate user page nav). Late guard **deferred** full finalize for queued user page without releasing; full finalize **else** branch left restore in progress and suppression armed.

**Fix (this branch, `music_startup_save_suppression.py` + deferred flush origin):**

1. On finalize **mismatch** after restore apply → `_release_startup_suppression_after_restore_mismatch` (release without discarding user edits; queued nav uses `_apply_queued_page_startup_release`).
2. Late `run_late_startup_restore_guard` **defer** path → mark restore finalized and release for genuine queued user page (no Creative re-stamp via full finalize).
3. `_release_startup_for_queued_page_change` → post-finalize / page-only / queued-target normalized compare fallbacks.
4. `should_suppress` `page_change` → auto-release if restore finalized and user nav still blocked.
5. `maybe_flush_deferred_page_change_save` → **`user_navigation`** when `_suite_page_user_nav` (not `reconciliation`).

**Regression tests:** `tests/test_startup_suppression_release_lifecycle.py` (+ existing queued-page / cold-reboot tests).

**Verify on next preview:** After Hevenu hydrate @ Creative → nav Log → boundary trace shows `serialize_payload != NULL`, `save_complete != NULL`, durable page advances to Log at rev > 894.

### H — Specialized vs generic Backing entry (safety @ post-9a3131f)

**Symptom:** Mission / Jam / Style Jam / Song-Based → Backing opened **regular catalog** Backing.

**First incorrect classifier:** `hydrate_backing_source_for_page()` treated `BACKING_INTENT_RESTORE_LAST` the same as explicit generic catalog entry (`generic_entry or intent == restore_last` → `release_specialized_backing_for_generic_navigation`). Streamlit calls hydrate **twice** per Backing run (early app hydrate + backing page render); the first call consumes `from_creative`, the second defaults intent to `restore_last` and **released** sealed mission/jam context before render.

**Fix:** Generic reset only when `BACKING_GENERIC_CATALOG_ENTRY_KEY` / `BACKING_ENTRY_GENERIC_CATALOG` is set (`mark_generic_catalog_backing_entry`). Specialized handoffs use `mark_specialized_backing_handoff_entry` / `from_creative`. `navigate_studio_page` marks generic only for ordinary top-level nav (not in-flight Creative handoff).

**Tests:** `tests/test_backing_entry_classification.py`.

### I — Jam key widget mutation on Missions tab (safety @ post-6bb4f56)

**Symptom:** `StreamlitAPIException` entering Missions after Jam Generator; Practice/Concert Key stuck on Jam tonic (E major); sidebar key changes ignored.

**Widget key(s):** `display_key` (primary stack trace at `generated_jam_key_context.py` ~104); also `improv_entry_mode` in `_deactivate_entry_jam_transient_for_missions`.

**First illegal writer:** `deactivate_generated_jam_key_ownership(..., pre_widget=True)` assigned `session["display_key"]` after sidebar widgets rendered. `pre_widget=True` bypassed the widget lock check.

**Lifecycle:** Sidebar hydrates @ ~10033; user switches Creative tab Jam → Missions same run; `_tab_missions` → `reconcile_missions_workflow_context` → deactivate restored snapshot via direct widget writes.

**Fix:** Deactivate uses `reconcile_practice_key_fields` / `PENDING_DISPLAY_KEY` when widgets locked; mission reconcile uses `safe_session_assign` for jam widget keys; locked path clears `_generated_jam_key_context` without direct `display_key` assignment.

**Tests:** `tests/test_jam_key_missions_widget_safe.py`.

### J — Song section scope invariants (acceptance, safety branch)

**Invariant:** Fresh song-based / catalog Backing / Entry&Jam / section-capable Jam entry → **Full Song** default; user may select a section for that workflow; switching workflows must not inherit stale section; canonical Full Song must not lose to stale `backing_quick_section` on gather/persist.

**Guard:** `reset_backing_playback_scope_to_full_song` + `song_improv_scope_authority.apply_song_improv_entry_defaults` (existing). **Generic catalog Backing** (`release_specialized_backing_for_generic_navigation`) now also resets playback scope so mission/jam **Bridge** does not leak into top-level catalog Backing.

**Tests:** `tests/test_workflow_section_scope_invariants.py`, `tests/test_backing_scope_widget_lifecycle.py`, `tests/test_song_improv_scope_authority.py`.

**Prior item F (`a824bbc` autosave page):** May still matter for stale Creative in passive autosave, but does **not** explain song + page reverting together unless the whole workspace write never commits.

---

### K — Shared key + chord authority + Return (live @ `99046fa`, diagnosis + targeted fixes)

**Acceptance:** Still **FAIL** on preview @ `99046fa`. **Do not promote to `dev`.** Work stays on `safety/creative-regression-2026-08-07-ee6b5cb`.

#### K.1 Trace table — one Hevenu/Missions run (same session snapshot)

| Surface / field | Live symptom (repro) | Value owner (code) | Typical stale value | First diverging writer |
|-----------------|----------------------|--------------------|---------------------|----------------------|
| **Intended canonical** (Hevenu song-based) | D minor everywhere after catalog practice | `song_based_improvisation` blob `keys.*` via `resolve_song_practice_key_token` | — | — |
| `active_song` original key | (catalog) | `songs.key_state.resolve_active_musical_key` → `original_key` | — | — |
| Sidebar Practice / Concert Key | **C major** while Missions **Cm** | `display_key` / `concert_key` widgets + `prime_sidebar_practice_key_from_identity` | Jam-era major tonic `"C"` without mode | **`apply_entry_jam_authoritative_practice_key`** / `to_major_key_preserve_spelling` on jam token; or session `display_key` not reconciled from song blob |
| `resolve_authoritative_practice_key` | Sidebar label mode | `musical_context_authority` (was: jam token **before** song blob when jam fields linger) | `"entry_jam_practice_key"` major projection | **`resolve_creative_tab_practice_key_token`** when `entry_jam_practice_key_authority_active` true; fixed path: **`song_based_blob_practice_key`** when catalog owns |
| Missions header / progression | **Cm** | `resolve_missions_section_map` + mission blob `keys` + `improv_ctx.key_center` from `_coherent_improv_key_pair` | Jam-generated **Cm** progression frozen on `mission_jam` blob | **Mission blob `keys` / section_map** not mirrored from song blob on Missions entry (`mirror_mission_keys_from_song_blob` only on chord mutate, not tab hydrate) |
| Mission sealed key | Cm in specialized Backing | mission blob + `mission_practice_context` | Same as mission blob | Same as mission blob |
| `SongCreativeFocus` | Chord sync | `commit_song_creative_focus` on mission chord mutate | Stale focus if practice-key binding fails | `read_song_creative_focus` → rebuild from **song** blob, not mission |
| `improv_ctx.key_center` | Missions caption | `_authoritative_practice_chart_key` → jam token **then** song token | Major `"C"` or blob **Cm** | Order in `_authoritative_practice_chart_key`; mission ctx built before song reconcile |
| Generic catalog Backing | **D minor** (correct) | `sync_session_practice_key_from_song_blob` on generic entry | — | — |
| Return to Missions after catalog Backing | Missions **Cm**, sidebar **Dm** | Mission blob stale; sidebar synced from song on return | Split authorities | **First:** mission blob not mirrored after song blob updated by catalog Backing |

**A — ONE canonical key for Hevenu/Missions:** **`song_based_improvisation` practice key (e.g. D minor)** when Jam ownership has ended and catalog pick is active. **First writers of wrong C minor / C major:** (1) **mission_jam blob** retaining jam transposition; (2) **sidebar `display_key`** retaining jam **major tonic** (`to_major_key_preserve_spelling`) or unreconciled session fields; (3) **`resolve_authoritative_practice_key`** previously preferring jam tab token over song blob when catalog should own.

**Ownership rule implemented (minimal):** `song_catalog_context_owns_practice_key` → **`resolve_song_practice_key_token`** before jam branch; `ensure_missions_parent_practice_key_hydrated` → **mirror + sync** from song blob when entry jam inactive.

#### K.2 Chord sync matrix (Fm in Missions → Harmony still Cm)

| Step | Owner |
|------|--------|
| Missions tile `on_click` | `apply_atomic_mission_chord_selection` → `mutate_mission_chord_selection` |
| Atomic mutation | mission blob + `commit_song_creative_focus` + `handle_user_mission_target_selection` |
| Canonical pair | `II_SELECTED_*` + `write_authoritative_chord_selection` (harmony_map_* ) |
| Harmony tab read | `hydrate_creative_pages_from_song_focus` → `_ensure_chord_selection` → `_selected_chord` |

**B — ONE canonical chord after Fm click:** **`II_SELECTED_*` as validated by `resolve_authoritative_chord_selection` on the active section_map.** **First surface that diverged:** Harmony Map when **`harmony_map_chord` / focus hydrate** lagged mission blob (mission click did not always call `write_authoritative_chord_selection`). **Fix:** `mutate_mission_chord_selection` now calls **`write_authoritative_chord_selection`** after blob commit.

**Do not** add pairwise tab sync — single canonical path only.

#### K.3 Generate Example after Cm → Fm

| Check | Finding |
|-------|---------|
| UI selected chord | Missions tiles (post-click rerun) |
| Sealed `MISSIONS_GENERATE_CONTEXT_KEY` | Stashed at **render** with `cur_chord`; **popped** on chord change via `_invalidate_mission_chord_dependent_session` |
| Generate callback | `_run_mission_example_generate` |
| Bug | With **`sealed_from_snap`**, generation params could stay on **stale snap `cur_chord` (Cm)** even when authoritative selection was **Fm** (callback runs before restash / auth block skipped if map empty) |
| Symptom | Regenerates Cm or aborts silently when example already matches Cm |

**C — Why Fm generate “does nothing”:** **Stale sealed snap + authoritative chord not applied as final generation input.** **Fix:** final **`read_authoritative_mission_chord_selection`** immediately before generate (overrides snap).

#### K.4 Return to Creative (trace only — frozen layers)

Specialized Backing → **Return to Creative** path (no change unless trace proves break):

1. `handle_return_to_creative_click` → `queue_pending_creative_return_from_backing` → **`seal_creative_return_context_from_backing`**
2. `consume_pending_creative_return_handoff` → **`prepare_return_to_backing_source`** → `CREATIVE_RESTORE_FROM_BACKING_KEY`
3. **`navigate_studio_page("creative")`** + `mark_user_navigated_page_this_run`
4. Post-consume: **`apply_entry_jam_authoritative_practice_key`** if jam still active else **`sync_session_practice_key_from_song_blob`**
5. Rerun: dispatch reads **`studio_page`** + nav history + startup suppression (frozen @ `9a3131f`)

**D — Where to instrument on next failing preview (`?dev=1`):** compare **`sealed_context.creative_tab`**, **`studio_page` after consume**, **`trace_return_before_rerun` dispatch**, and final router page. **First divergence candidates:** (a) consume skipped (`phase=skipped`); (b) **`prepare_return_to_backing_source`** not restoring creative sub-tab; (c) post-rerun dispatch overriding **`creative`** from stale persisted page envelope (persistence frozen unless trace proves regression).

**Return to Mission** (separate): `seal_mission_return_destination` / `apply_sealed_mission_return_destination` — retest after chord/key fixes; not modified in this pass.

#### K.5 Tests added (post-proof)

- `tests/test_creative_regression_batch_2026_08_07.py` — song blob **Dm** vs display **C** authority; generate uses **F#m** over stale snap **C#m**
- Existing: `test_song_creative_focus_cross_tab_sync.py`, `test_creative_chord_authority_lifecycle.py`, `test_creative_return_from_backing_widget_lifecycle.py`

**Frozen (unchanged):** `9a3131f`, `6bb4f56`, `74591f6`, `78ff42a`, return-route core.

---

### L — Progression collapse to single chord (live @ `870b594`)

**Symptom:** Sidebar **D minor** correct; all Creative chord surfaces show only **Cm** (one tile / one-chord “progression”).

**Critical distinction:** **Section progression** (N chords) vs **selected target chord** (one highlight). Mission backing may use a one-chord loop; Creative tabs must not.

#### L.1 Trace table — first collapse

| # | Surface | Owner | Collapsed value | First diverging writer |
|---|---------|--------|-----------------|-------------------------|
| 1 | Raw catalog progression | `resolve_catalog_song_for_pick` / song row | Full Melody A/B | — |
| 2 | Before Creative reconcile | `improv_song_concert_sections` / song blob | Full (until corrupt) | — |
| 3 | **`improv_song_concert_sections`** | Session | **`{section: [Cm]}`** | **`restore_workflow_blob_to_session`** projecting **`mission_jam` blob.section_map** (one-chord mission slice) **or** stale slice already in blob |
| 4 | `concert_song_sections_from_session` | `improvisation_motif` | Accepts #3 as authoritative | **No degeneracy guard** (unlike `_song_improv_sections_dict`) |
| 5 | `resolve_improv_sections` / `resolve_missions_section_map` | All Creative tabs | One chord | Reads #3 |
| 6 | `improv_mission_chord_options` | `_ensure_chord_selection` | Can mirror flat list length | Secondary |
| 7 | Mission blob `section_map` | `build_mission_context` / backing | One chord for **backing only** | Must not round-trip to #3 |

**A — First collapse to `[Cm]`:** **`improv_song_concert_sections`** (and then every tab via **`concert_song_sections_from_session`**) when a **one-chord mission/backing slice** is written into the field that should hold the **full song progression**. Primary writer: **legacy blob projection** after **`mutate_mission_chord_selection`** (`project_active_blob_to_legacy_session` → `restore_workflow_blob_to_session`). Secondary: **`reconcile_missions_workflow_context`** overwriting **`home_sections`** from stale **`improv_ctx.sections`** before resolving catalog sections.

**Fix (safety branch post-`870b594`):**

- `rehydrate_full_song_concert_sections` — refuse ≤1 total chords; prefer song blob / catalog / `home_sections` (same policy as `_song_improv_sections_dict`).
- `concert_song_sections_from_session` — route through that guard.
- `_concert_sections_for_legacy_projection` — never project degenerate mission blob map onto session.
- Mission chord mutate + Missions hydrate — rehydrate full sections after selection.
- Reconcile — **`home_sections`** from **`resolve_missions_section_map`**, not stale **`improv_ctx`**.

**Test:** `MissionProgressionCollapseGuardTests.test_mission_chord_select_does_not_collapse_full_progression`.

#### L.2 Return-to-Creative (instrumentation @ `870b594`, no routing change)

Use one failing click; read **`[creative_return_trace]`** then **`[studio_page_route_trace]`** in order:

| Step | Phase | What to verify |
|------|--------|----------------|
| 1 | `ON_RETURN_BUTTON_CLICK_RECEIVED` | Click entered |
| 2 | `ON_RETURN_HANDOFF_QUEUED` | `sealed_creative_tab`, `sealed_source` |
| 3 | `ON_RETURN_CONSUME_PHASE` | `consume_phase` applied/skipped; `studio_page_after_consume`; `user_nav_marker_*` |
| 4 | `ON_RETURN_CLICK_AFTER_CONSUME` | `consume_phase` echo |
| 5 | `RETURN_CLICK_BEFORE_RERUN` | `studio_page`, `user_nav_page_this_run_scoped`, nav/workspace pages |
| 6 | Next run dispatch | `[studio_page_route_trace]` creative branch / `DISPATCH_RESYNC_*` |

**B — Likely first divergence (code review; confirm on your trace):**

1. **`consume_phase=skipped`** — no backing context / prepare failed (handoff never applied).
2. **`consume_phase=applied`** but **`RETURN_CLICK_BEFORE_RERUN.studio_page` ≠ `creative`** — consume did not stick before rerun.
3. **`applied` + `studio_page=creative`** but next-run dispatch shows **`music_workspace_state_page` / hydrated page ≠ creative** — **persistence envelope overwrites run-scoped user nav** (frozen @ `9a3131f` unless trace proves regression).
4. Same run: **`RETURN_POST_RERUN_STOP_GUARD`** + `request_app_stop` after failed **`rerun_invoked`** — user stays on Backing without a successful rerun (check `RETURN_CLICK_RERUN_OUTCOME.rerun_invoked` / `fallback_st_rerun`).

Do **not** change `creative_return_route` / launch ID until one of the above is confirmed in JSON.

---

### §M — Jam Session Generator / Style Jam sealed key (2026-08-08)

**Symptom (live):** User requests concert key **C**; UI practice labels show **C**; jam **prompt/metadata** still **Eb**; progression **Fm7 · Bb7 · Ebmaj7**; sidebar **Eb**; **Open in Backing Studio** fails (Style Jam: `detect_cross_owner_handoff_fields` rejects **EBMAJ7** on `style_jam` snapshot).

#### M.1 First divergence table

| Step | Expected | Actual (bug) | First bad writer |
|------|----------|--------------|------------------|
| 1 | Widget / pending hydrate = **C** | `improv_jam_key` often stale **Eb** (`studio_page_state.setdefault`) | Session default vs widget |
| 2 | `consume_pending_generated_progression` reads **C** | Used raw `session["improv_jam_key"]` | **`music_workflow_pending_generated_progression`** |
| 3 | `generate_jam_session(key_center=C)` | OK when #2 correct | — |
| 4 | Sealed `improv_jam_session.key` + `prompt` + sections | **prompt/key stayed Eb** after key-only edit | **`commit_jam_session_generation`** did not re-seal metadata; **`_finalize_generated_key_edit`** only updated meta label |
| 5 | Workflow blob `keys` + `section_map` | Sometimes **C** keys + **Eb** chords | **`build_snapshot_from_session`** overwrote `practice_tonic` from widget while **`section_map` came from blob** |
| 6 | Backing handoff snapshot | Key **C** + progression **Eb** | Snapshot split at #5 → validation / incoherent BackingContext |
| 7 | Sidebar | **C** while jam owns | **Eb** (song/catalog) when **`activate_generated_jam_key_ownership`** missing after jam generate |

**Root cause (minimal):** Generation and key-change paths did not **seal one musical context** (key + progression + jam prompt + blob + sidebar). Artifact builder **re-labeled** key from widgets without matching blob progression.

#### M.2 Fix (safety branch; not promoted to `dev`)

- **`resolve_generated_concert_key_for_owner`** — pending/widget hydrate before generate.
- **`seal_jam_session_musical_context`** + **`finalize_generated_*_key_seal`** — on generate, key edit, blob commit.
- **`build_snapshot_from_session`** — when workflow blob exists, **blob keys are authoritative** (no widget key override).
- **`detect_cross_owner_handoff_fields`** unchanged — fix upstream coherence instead.

**Tests:** `tests/test_generated_jam_style_key_seal_regression.py` (cases A–D).

---

### §N — Musical context coherence audit (2026-08-08) — STOP THE LINE

**Problem class:** Multiple parallel “authorities” (widget key, blob key, session jam dict, snapshot override, sidebar `display_key`, notation reference, Backing hybrid builder) reconstruct **tonic**, **mode**, and **progression** independently. Bare tonic tokens (`Eb`, `C`) propagate without mode, enabling `Eb major → Eb → Eb minor` conflation.

#### N.1 Answers to the eight audit questions

| # | Question | Answer (first divergence / source) |
|---|----------|-------------------------------------|
| 1 | Canonical context after **Jam C generate** | **Should be:** active `jam_session_generator` **workflow blob** — `keys.practice_tonic/mode` + `section_map` + sealed `improv_jam_session` (post-§M). **Also written:** `_generated_jam_key_context`, `_generated_artifact_last_*`, session widgets. |
| 2 | Where progression stays **Eb** while key is **C** | **First split on Backing open:** `build_entry_jam_context` **hybrid path** — `concert_key` from `creative_entry_concert_key` / `_live_backing_concert_keys` (**C**) while `progression` from `_entry_jam_sections_dict` → stale `improv_jam_session.sections` (**Eb ii–V–I**). Secondary: invalid handoff snapshot **fallback** to `_generated_artifact_last_*` with mismatched revision. **Not** the Jazz template when `key_center=C` (template yields **Dm7–G7–Cmaj7**). |
| 3 | Canonical context after **Hevenu Missions** | **Should be:** `mission_jam` / `song_based_improvisation` blob + `resolve_song_practice_key_token` → **Dm minor** + full `improv_song_concert_sections` / song blob `section_map`. **Selected chord** is separate (`selected_chord_symbol` on mission blob). |
| 4 | Where **Jam Eb** survives Missions transition | **`generated_jam_owns_practice_key`** / `_generated_jam_key_context` / `improv_jam_session` / stale **`improv_style_meta.key`** when `deactivate_generated_jam_key_ownership` did not run or **`resolve_authoritative_practice_key`** still reads **`entry_jam_practice_key`** before song blob. Envelope flag: **`STALE_GENERATED_JAM_KEY_LEAK`**. |
| 5 | Notation staff key signature source | Missions ABC: **`mission_notation_staff_key(song_concert_key=…)`** ← `build_mission_example` / `reconcile_mission_example_abc` using **`ImprovSessionContext.display_key` / `key_center`**, which are built from **`_authoritative_practice_chart_key`** + **`_motif_notation_reference_key`** (chord-local **`harmonic_reference_for_chord`** when a chord is focused). **Not** the workflow blob unless those builders were fed from blob. |
| 6 | Sidebar source | **`display_key` / `concert_key`** widgets ← **`resolve_authoritative_practice_key`** chain: song blob when **`song_catalog_context_owns_practice_key`**, else **`resolve_creative_tab_practice_key_token`** (jam widgets / `_generated_jam_key_context`), else **`resolve_active_musical_key`**. Multiple writers: sidebar callback, **`apply_creative_concert_key`**, **`activate_generated_jam_key_ownership`**, song key edits. |
| 7 | Specialized Backing source | **Preferred:** sealed **`BACKING_OWNER_ARTIFACT_SNAPSHOT`** → `_entry_jam_context_from_owner_snapshot`. **Failure mode:** seal fails → legacy **`build_entry_jam_context`** hybrid (Q2). **Keys** must come from same object as **progression** (snapshot or blob), never widget-only. |
| 8 | Single context without pairwise sync? | **Yes — target model:** `CoherentMusicalContext` from **`resolve_coherent_musical_context`** (active workflow blob: tonic+mode+section_map+selection). All renderers become **read-only consumers**; validators fail closed on hybrid. **`ActiveMusicalWorkflowEnvelope`** already partial (key without section_map) — coherence layer adds progression + validation. |

#### N.2 Consolidation shipped on safety (post-§M, pre-next-preview)

- New **`musical_context_coherence.py`** — blob-resolved context, **`KEY_PROGRESSION_CENTER_MISMATCH`**, owner-leak checks.
- **`build_entry_jam_context`** — generated paths use **coherent blob**; hybrid **C key + Eb progression** raises **`WorkflowOwnerIntegrityError`**; removed stale snapshot **fallback**.
- **`seal_backing_handoff_snapshot_for_creative_open`** — coherence validation before seal.
- **`musical_context_authority.run_musical_context_consistency_checks`** — merges coherence violations.

**Tests:** `tests/test_musical_context_coherence_invariants.py`.

**Frozen:** persistence envelope (`9a3131f`), specialized vs generic Backing entry (`6bb4f56`), Return routing, `detect_cross_owner_handoff_fields`.

**Return:** unchanged; trace still required for click → consume → `studio_page=creative` → rerun → dispatch.

