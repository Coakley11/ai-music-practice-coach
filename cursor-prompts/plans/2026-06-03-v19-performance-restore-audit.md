# v19 audit — Backing speed, reboot restore, capo sync, catalog lock

**Deploy marker target:** `music-persistence-restore-v19`  
**Audit date:** 2026-06-03  
**Branch:** `dev`  
**Baseline:** v18 (`music-persistence-restore-v18`, commit `7e3bde6`)

---

## Priority order (user)

1. Backing Track speed / perceived reliability  
2. Reboot restore (still → Say/Stay + Practice)  
3. Capo Shape Mode sync + shape key as written key everywhere  
4. Catalog ↔ Custom intermittent nav lock  
5. Display key sidebar vs song card mismatch  
6. Remove raw workspace / state dump from normal UI  

**Rule:** Find bottlenecks and exact state writers first; patch smallest scoped files only.

---

## 1. Backing Track speed (TOP)

### User-visible problem

Generate/Play feels broken when it takes many seconds with no clear progress. This is usability, not just correctness.

### Where time is spent (ordered by impact)

| Phase | Location | Typical cost | Notes |
|-------|----------|--------------|-------|
| **Audio synthesis** | `backing_audio.synthesize_chords_to_numpy()` via `generate_backing_track()` → `_cached_backing_wav()` | **2–15+ s** (full song, 44.1 kHz, per-bar loop) | **Largest bottleneck** on cache miss |
| **Post-generate full rerun** | `st.rerun()` after generate (~11530) and play (~11639) | **0.5–3 s** | Re-executes entire app script: sidebar, workspace hook, backing page setup |
| **Humanized sections (HRI)** | `_humanized_backing_sections()` (~11363) | **100–800 ms** first hit | Session-cached via `session_cache_get_or_set("hri_sections")`; still runs before Generate on every backing page visit |
| **Lead sheet HTML** | `full_chord_markdown()` when lead sheet open (~11677) | **200 ms–2 s** | Session-cached `"backing_chart_html"`; large HTML string |
| **Base64 encode** | `prepare_wav_b64()` | **50–400 ms** | Session-cached; usually fast on Play rerun |
| **Timeline build** | `build_chord_event_timeline()` / `_cached_backing_timeline()` | **5–50 ms** | Module cache + cheap |
| **Cloud workspace hook** | `prepare_music_workspace()` → `sync_workspace_protocol()` every script run | **50–500 ms** | See below |
| **Waveform / player prep** | `live_follow_along_component_html()` + b64 embed (~11817) | **100–500 ms** | Runs when audio ready + lead sheet open |

### Caching today

| Layer | Key | Survives `st.rerun()`? | Survives Cloud reboot? |
|-------|-----|------------------------|------------------------|
| Module WAV/timeline | `_BACKING_WAV_CACHE`, `_BACKING_TIMELINE_CACHE` (max 12) | Yes (same worker) | No |
| Session WAV bytes | `_last_backing_wav`, `_last_backing_signature` | Yes | No |
| Session b64 | `session_cache_get("backing_wav_b64", sig)` | Yes | No |
| HRI sections | `session_cache_get("hri_sections", sig)` | Yes | No |
| Chart HTML | `session_cache_get("backing_chart_html", sig)` | Yes | No |

**Gap:** Module cache is lost on Streamlit Cloud worker recycle; session holds WAV but Generate still re-synthesizes when module cache is cold unless signature short-circuit is added.

### Rerun / workspace overhead (every interaction)

```9217:9222:streamlit_music_practice_app.py
    st.session_state.pop("_music_workspace_prepared_for_run", None)
    prepare_music_workspace(
        st,
        song_picker_catalog=SONG_PICKER_CATALOG,
        song_library=SONG_LIBRARY,
    )
```

Each script run **clears** the per-run workspace guard then calls `prepare_music_workspace`. That invokes `sync_workspace_protocol(cloud_first=True)` which:

1. Calls `load_cloud_full_session()` — meta fetch every run; full blob cached in session when `updated_at` unchanged (`suite_cloud_state.py` ~393).
2. After first sync, `should_apply=False` (“already synced”) — **does not re-apply blob** (good).
3. Still pays network/meta + pick/ comparison logic every Generate/Play/nav rerun.

Generate flow also calls `st.rerun()` immediately after synthesis, forcing a **second** full script pass before the user sees the player (`~11546–11630`).

### Exact writers (backing transport)

| Event | Writer | File |
|-------|--------|------|
| Generate click | `_render_backing_step2_playback_action` → `_gen_clicked` | `streamlit_music_practice_app.py` |
| Synthesis | `_cached_backing_wav` → `generate_backing_track` | `streamlit_music_practice_app.py`, `backing_audio.py` |
| Session WAV | `st.session_state["_last_backing_wav"]` | generate block ~11589 |
| Transport status | `BACKING_TRANSPORT_STATUS`, `commit_backing_transport_from_session` | `backing_track_state.py` |
| Play click | `_begin_backing_performance_follow_along` | `streamlit_music_practice_app.py` |
| Cache invalidation | `invalidate_backing_cache`, `note_active_source_change` | `streamlit_music_practice_app.py` |

### Dev timing traces (v19 instrumentation)

Events (session key `_backing_timing_trace`):

- `generate_start` — Generate/karaoke-auto-gen entered  
- `generate_complete` — WAV + b64 ready, before rerun  
- `audio_load_complete` — Player path has b64 / `st.audio` rendered  
- `play_start` — Play button or autoplay handoff  

Shown in **Developer Debug: Backing generation** expander when `?dev=1` on Daniel workspace.

### Recommended patches (smallest scope first)

1. **Session signature short-circuit** — If `_last_backing_signature == _current_backing_signature` and `_last_backing_wav` exists, skip synthesis on Generate (mark cache hit, still refresh transport). *File:* `streamlit_music_practice_app.py` generate block only.  
2. **Skip `st.rerun()` when audio becomes ready in-run** — Restructure so post-generate player renders same run (recompute `_backing_audio_ready` after generate). *File:* `streamlit_music_practice_app.py` backing page section. Medium risk (widget order).  
3. **Defer HRI/chart work** — Run `_humanized_backing_sections` after early exit when signature unchanged and audio ready. *File:* `streamlit_music_practice_app.py`.  
4. **Workspace hook throttle** — Do not pop `_music_workspace_prepared_for_run` every run; or skip `load_cloud_full_session` when `_suite_workspace_synced_music` and no dirty flag. *File:* `music_persistent_state.py` / `suite_user_persistence.py`.  
5. **Persist WAV signature in `backing_track_state` blob** — Cross-device “already generated” hint (optional; large payload concern).

---

## 2. Reboot restore → Say/Stay + Practice

### Symptom

Hard refresh / Streamlit Cloud reboot lands on first catalog song (often **Say** / Stay) and **Practice** page instead of last song/page.

### Root-cause chain (most likely)

```
Cloud/disk restore applies blob
  → pick_key empty or not yet in session when get_song_context runs
  → get_song_context: pk empty → first_valid_pick_key(catalog)  [alphabetical first genre/label]
  → ensure_master_song_initialized (if skip=false & workspace_is_truly_empty)
      → DEFAULT_SONG_RECORDS[0]  [Stay/Say]
  → studio_page defaults to "practice" if not stamped from blob
```

### Exact state writers

| Step | Function | Writes |
|------|----------|--------|
| Workspace sync | `sync_workspace_protocol` → `apply_music_disk_state` | `core`, `session`, `active_song_state`, `studio_page` |
| Post-sync finalize | `_finalize_music_workspace_restore` | custom song, MT layers, page snapshot |
| Default song seed | `run_post_nav_music_startup_init` → `ensure_master_song_initialized` | `selected_song`, `active_catalog_pick_key`, `_music_default_song_ephemeral` |
| Context resolution | `get_song_context` | `apply_pick_key(..., origin="recovery")` when pk missing/stale |
| Page | `apply_saved_music_context`, `restore_current_page_snapshot_if_needed`, `studio_nav_state` | `studio_page` |

### Failure modes

1. **`get_song_context` before restore completes** — v17 deferred to post-`prepare_canonical_music_page_state`; inner `try/except: pass` at ~9266 can swallow errors and skip context. v18 fallback at ~9278 helps but runs only if `_catalog_song_data` unset.  
2. **`first_valid_pick_key`** — `song_catalog/catalog.py` ~450: first genre’s first label (not user’s last song).  
3. **`workspace_is_truly_empty` true after failed restore** — Should be false when `_suite_workspace_sync_attempted` and no restore (`music_restore_phase.py` ~89–93), but empty cloud payload + no pick_key may still allow default init.  
4. **`_music_default_song_ephemeral`** — Blocks cloud save of default; may interact badly with restore diagnostics.  
5. **Silent exception** — `prepare_music_workspace` outer `except: pass` at ~9275 hides restore failures.

### Recommended patches

1. **Never call `get_song_context` fallback to `first_valid_pick_key` when `_suite_last_cloud_fetch_payload` has pick_key** — defer until `active_song_state` hydrated. *Files:* `songs/state.py`, `streamlit_music_practice_app.py`.  
2. **Log (dev) when inner startup `except` fires** — surface `_music_post_nav_startup_error`.  
3. **Gate `ensure_master_song_initialized` on `music_restore_phase_complete` AND confirmed empty payload** — *File:* `music_persistent_state.py`.  
4. **Verify save path writes `core.pick_key` + `music_workspace_state.studio_page`** before reboot test.

---

## 3. Capo / Shape Mode

### Expected model

- **Sounding key** = concert pitch  
- **Shape key** = guitarist’s written/fingered key  
- When capo enabled: **shape key everywhere** a written key would appear (practice, scales, creative, backing, songs, lock-in-the-feel)

### Current state

| Key | Session key | Persisted? |
|-----|-------------|------------|
| Capo enabled | `guitar_capo_enabled` | **No** — not in `_PERSIST_KEYS` or `active_song_state` envelope |
| Sounding key | `guitar_capo_sounding_key` | **No** |
| Shape key | `guitar_capo_shape_key` | **No** |
| Last concert | `guitar_capo_last_concert_key` | **No** |

Partial usage: `build_capo_context()` / `resolve_practice_keys(capo_shape_key=...)` on backing charts; `chart_display_key = _capo_ctx.sounding_key if capo else chart_key` (~11494) — **displays sounding key on chart, not shape key** (wrong vs spec).

### Writers

- UI: `render_guitar_capo_sidebar`, widgets `guitar_capo_*_widget` → `guitar_capo.py`  
- Derived: `instrument_transposition.resolve_practice_keys`  
- Not synced: `_PERSIST_KEYS` in `music_persistent_state.py` ~388–429 omits all capo keys

### Recommended patches

1. Add capo fields to `active_song_state` blob + cloud envelope.  
2. When capo enabled, set display/chart/practice key to **shape key** (not sounding).  
3. Include capo in `build_music_disk_state` / restore in `apply_cloud_active_song_state_if_allowed`.

---

## 4. Catalog ↔ Custom intermittent lock

### Flow

- Toggle: `st.radio` key `song_picker_active_source` → `on_song_picker_source_change` → **`st.rerun()`** always (`songs/music_source.py` ~520, ~530)  
- Custom → catalog: `switch_to_catalog_from_custom`  
- Reconcile before widgets: `reconcile_picker_music_source` / `reconcile_music_picker_source_widget`

### Likely lock causes

1. **Double rerun** — callback rerun + nav rerun race  
2. **`authoritative_restore_in_progress`** blocking contested writes while cloud sync runs  
3. **`queue_custom_active_song_activation`** deferred activation conflicting with picker render  
4. Direct session writes to `active_catalog_pick_key` bypassing canonical writers (see `2026-06-19-state-ownership-audit.md`)

### Recommended patches

1. Trace `_music_picker_source_change_source` and last contested write on lock repro.  
2. Avoid rerun in `on_song_picker_source_change` when state already matches choice (Streamlit widget sync only).  
3. Ensure `USER_CATALOG_SOURCE_CHOICE_KEY` restored from cloud on reboot.

---

## 5. Display key mismatch (sidebar vs song card)

### Owners (contested)

| Surface | Source |
|---------|--------|
| Sidebar widget | `st.session_state["display_key"]` via `sync_display_key_before_widget` |
| Song card | `active_song_card_details` / `resolve_practice_keys` / catalog record key |
| Canonical blob | `active_song_state.display_key` |
| Cloud | `core.display_key`, envelope |
| Owner identity | `DISPLAY_KEY_OWNER_IDENTITY_KEY` (v17 restore on canonical push) |

### Writers

- User change: sidebar `on_change` → `mark_display_key_changed` / `request_display_key`  
- Canonical push: `active_song_state.py` `_restore_display_key_owner_from_context`  
- Catalog switch: `apply_pick_key` may not sync display key to sidebar widget value

### Recommended patch

Single read path for card + sidebar: `effective_display_key(session)` used by both; on canonical push, **prime widget key** before render.

---

## 6. Raw workspace dump in normal UI

### Sources (dev-gated but noisy)

| Panel | Gate | Issue |
|-------|------|-------|
| `render_persistence_trace_sidebar` | `music_developer_mode` | Large trace text areas; embeds Phase C debug |
| `render_music_deploy_probe` | `developer_mode(st)` | **`expanded=True`** by default |
| `render_widget_control_debug` | `_developer_mode_enabled()` | Called **twice** (main ~9682 + inside trace ~1218) |
| `render_active_song_state_debug` | inside trace expander | Dumps `global_control_widget_trace` with canonical dict |
| `suite_egress_trace` | `can_show_developer_tools` | JSON egress events |
| `suite_app_shell` auth panel | `can_show_developer_tools` | `st.json(browser_auth_storage_status)` |

All require Daniel workspace + `?dev=1` (or dev session flag). **Normal users should not see these** unless dev mode leaks via persisted `developer_mode` session flag.

### Recommended patches

1. Remove duplicate `render_widget_control_debug` from trace expander (keep one call site).  
2. Set all dev expanders `expanded=False`.  
3. Never render Phase C / workspace JSON in main content area.  
4. Clear `developer_mode` from default session bootstrap unless query param present.

---

## v19 implementation plan (minimal diffs)

### Phase A — Instrumentation (this pass)

- [ ] `_backing_timing_trace` events in `backing_generation.py`  
- [ ] Wire generate/play/audio paths in `streamlit_music_practice_app.py`  
- [ ] Session signature short-circuit on Generate cache hit  

### Phase B — Backing perceived speed

- [ ] Same-run player after generate (reduce rerun)  
- [ ] Defer HRI when audio ready + signature match  

### Phase C — Reboot restore

- [ ] Harden `get_song_context` against empty pk when cloud has pick_key  
- [ ] Surface startup init exceptions in dev trace  

### Phase D — Capo persistence + shape key display

- [ ] Persist capo in `active_song_state`  
- [ ] Shape key as written key on all listed pages  

### Phase E — Polish

- [ ] Catalog/custom rerun dedupe  
- [ ] Display key single owner  
- [ ] Dev panel cleanup  

---

## Test plan (Streamlit Cloud `dev`)

1. **Backing:** `?dev=1` → Backing → Generate → confirm timing trace; repeat Generate (expect cache hit & <1 s).  
2. **Reboot:** Set non-Say song + Backing page → wait autosave → hard refresh → check deploy marker + song + page.  
3. **Capo:** Dell capo on + shape key → phone refresh → shape key matches.  
4. **Catalog/custom:** Custom → toggle Song Selection 5× → no freeze.  
5. **Display key:** Sidebar key == active song card key.  
6. **Normal UI:** without `?dev=1`, no persistence trace / JSON panels.
