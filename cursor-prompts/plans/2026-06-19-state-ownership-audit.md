# Music App State Ownership Audit (v17 baseline)

**Repo:** ai-music-practice-coach · **Branch:** dev · **Prior deploy:** music-persistence-restore-v16  
**Last updated:** 2026-06-19

---

## Executive summary

Individual bug fixes (v10–v16) improved behavior but remaining failures trace to **split ownership**: the same concern is written by multiple modules, restored at different startup phases, and reconciled with device-local heuristics. v17 applies the smallest lifecycle fixes; full ownership unification is a follow-on refactor.

---

## 1. Source-of-truth table

| Domain | Authoritative owner | Canonical key / blob | Live session keys |
|--------|-------------------|----------------------|-------------------|
| **Active song (identity)** | `songs/state.py` + `active_song_state.py` (split) | `active_song_state` blob + `active_catalog_pick_key` / `selected_song` | `active_catalog_pick_key`, `selected_song`, `active_genre` |
| **Studio page** | `studio_nav_state.py` | `studio_nav_state` + `studio_page` | `studio_page`, `_suite_page_user_nav` |
| **Sounding / practice key** | `songs/key_state.py` | `display_key` in `active_song_state` + session | `display_key`, `_display_key_owner_identity` |
| **Written / chart / shape keys** | `instrument_transposition.py` (derived, not persisted) | Capo + transposing flags in blob | `resolve_practice_keys()` → `chart_key`, `written_key`, capo shape sections |
| **Backing transport** | `backing_track_state.py` | `backing_track_state` blob | `_backing_autoplay`, `backing_transport_status`, `_backing_transport_user_stopped` |
| **Backing BPM** | `backing_track_state.py` (split with per-song slider) | `backing_track_bpm` in blob | `backing_track_bpm`, `backing_track_bpm::<sync_id>` |
| **Practice log** | `practice_log_persistence.py` | Supabase `saved_item` + local file | `practice_history.json` (not in workspace envelope) |
| **Multitrack** | `multitrack_session_persistence.py` | `mt_tracks`, `mixed_track_wav` in workspace extra | `mt_tracks`, `_mt_tracks_persist_blob` |

---

## 2. Writer table (primary paths)

| Domain | Writer | File | When |
|--------|--------|------|------|
| Active song blob | `write_canonical_active_song_state` | active_song_state.py | Every reconcile / save / restore |
| Pick identity | `apply_pick_key` | songs/state.py | User pick, recovery (**risk**), default seed |
| Pick identity (bypass) | direct `ACTIVE_CATALOG_PICK_KEY =` | music_coach_context.py, streamlit karaoke | Coach return, queue advance |
| Display key | sidebar widget, `_push_resolved_display_key_to_session` | key_state.py, active_song_state.py | Widget change, canonical push |
| Studio page | `write_canonical_studio_nav_state` | studio_nav_state.py | Nav, restore, save |
| Studio page (bypass) | direct `studio_page =` | music_source, karaoke_ui, coach | Custom force, karaoke |
| Backing transport | `_begin_backing_performance_follow_along`, `_stop_backing_playback` | streamlit | Play / Stop |
| Backing transport | `prepare_backing_transport_for_session` | backing_track_state.py | **Every rerun** (can clobber Play/Stop intent) |
| Backing BPM | `bind_backing_rendered_widgets_from_canonical` | backing_track_state.py | Page load, restore, **after Stop rerun** |
| Practice log | `save_practice_logs` | practice_log_persistence.py | Log write |
| Multitrack | `build_music_disk_state` encode | music_persistent_state.py | Autosave / force save |

---

## 3. Restore order (startup)

1. `begin_music_script_run` — reset restore-phase trackers (new session)
2. **Pass 1** `prepare_music_workspace` → `apply_music_disk_state` (authoritative cloud/disk)
3. **Pass 1** `prepare_canonical_music_page_state` → `prepare_active_song_context`
4. `complete_music_restore_phase` (conditional)
5. **Pass 2** `prepare_music_workspace` (post-nav)
6. `run_post_nav_music_startup_init` → default seed if `workspace_is_truly_empty`
7. **Pass 2** `prepare_canonical_music_page_state`
8. **`get_song_context`** — after pass 2 (v17: clobber window closed)
9. `ensure_studio_page` / sidebar / page body

**v16 bug (fixed in v17):** pass-1 `get_song_context` ran between steps 3 and 5 — caused Stay clobber during restore.

---

## 4. Cloud sync paths

| Direction | Entry | Payload |
|-----------|-------|---------|
| Build | `build_music_disk_state` | `core`, `session`, `active_song_state`, `studio_nav_state`, `_PERSIST_KEYS` extra |
| Save | `force_autosave` / `autosave_if_changed` | Supabase `full_session` + local disk |
| Load | `prepare_music_workspace` | `load_cloud_full_session` |
| Apply | `apply_music_disk_state` | Layered: workspace → active_song → studio_nav → session keys |

**Duplication risk:** `pick_key` and `display_key` appear in core, blob, envelope, and session — devices can reconcile differently.

---

## 5. Fallback / default paths

| Trigger | Function | Result |
|---------|----------|--------|
| Empty workspace after reboot | `ensure_master_song_initialized` | Stay + `_music_default_song_ephemeral` |
| Ephemeral blocks save | `autosave_music_state`, `force_autosave` | Nothing persisted → reboot empty |
| Stale pick in `get_song_context` | `first_valid_pick_key` | Stay (v16: deferred during restore) |
| No blob page | `resolve_studio_page_for_restore` | `"practice"` |
| Multitrack oversize | `encode_mt_tracks_for_persist` | Slot silently dropped |

---

## 6. Conflicting writers (priority fixes)

1. **`get_song_context` before restore complete** → Stay clobber (v17: move after pass 2)
2. **`prepare_backing_transport` every rerun** → Play wiped (v16: `_backing_play_request`)
3. **Stop without `mark_backing_user_edit`** → BPM re-bound from canonical (v17)
4. **Display key owner gate** → cloud key rejected on other device (v17: owner sync on canonical push)
5. **Direct `active_catalog_pick_key` writes** → identity desync (future: route through `apply_pick_key`)
6. **Dual BPM keys** → slider vs canonical drift (v17: skip bind when user stopped / dirty)

---

## 7. Recommended ownership model (target architecture)

1. **Single write funnel per domain** — no direct session writes outside canonical writers
2. **`active_song_state` owns display_key** — envelope/core derived read-only at build
3. **Last-writer-wins by timestamp** — `active_song_state_last_local_edit_ts` vs cloud `updated_at`
4. **Derived keys never persisted** — always `resolve_practice_keys(concert_key, instrument)`
5. **Backing transport intent enum** — `{stopped, ready, playing}` drives UI + autoplay
6. **One multitrack carrier** — top-level encoded blob only; surface size skips in UI

---

## 8. v17 minimal fixes (this patch)

| Fix | Addresses |
|-----|-----------|
| Move `get_song_context` after post-nav restore | Reboot → Stay + Practice |
| Stop → `mark_backing_user_edit` + skip widget re-bind when stopped | BPM locked, ghost transport |
| `_push_resolved_display_key_to_session` restores owner identity | Dell/phone display key drift |
| Deploy marker `music-persistence-restore-v17` | Trace verification |
