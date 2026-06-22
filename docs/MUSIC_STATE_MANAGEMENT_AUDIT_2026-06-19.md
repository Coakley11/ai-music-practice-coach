# Music App — State Management Audit

**Date:** 2026-06-19  
**Deploy marker (post-audit):** `music-state-restore-v11`  
**Scope:** Architecture audit + Priority 1–2 foundation fixes  
**Goal:** Restore once → user wins → defaults only when workspace is truly empty

---

## Executive summary

Music does **not** have a few isolated bugs. It has **multiple independent persistence layers** that all read/write overlapping session keys at different times in the Streamlit rerun cycle. Fixing one layer (e.g. genre touch guards) often exposes failures in another (e.g. active song canonical prepare clobbering instrument changes).

### Shared root cause

> **There is no single “restore phase complete” boundary.** Cloud full-session restore, page snapshot restore, canonical `prepare_*` reconciliation, widget priming, and cold-start defaults all run repeatedly across reruns without a unified rule: *after restore, user edits always win.*

The most damaging mechanism was **`reset_page_snapshot_tracker()` at the top of every script run**, which forced `handle_studio_page_transition()` to treat every rerun as a fresh page load and re-apply stale page snapshots — overwriting genre filters, creative mode, backing transport keys, etc.

Secondary root cause: **`prepare_active_song_context()` cleared `local_edit` when `_cloud_workspace_restored_this_run`**, then re-applied cloud canonical globals — making instrument/level/focus appear to “work once then stop.”

---

## 1. State systems inventory

| # | System | Primary modules | What it persists | When it runs |
|---|--------|-----------------|------------------|--------------|
| A | **Cloud full-session restore** | `suite_user_persistence.sync_workspace_protocol`, `suite_cloud_state` | Entire disk state blob (core + session + workspace envelope) | `prepare_music_workspace()` — twice per run (early + post-AMI) |
| B | **Legacy restore_once** | `suite_user_persistence.restore_once` | Same blob, alternate path | Documented in older audits; largely superseded by A |
| C | **apply_music_disk_state** | `music_persistent_state.py` | core, session `_PERSIST_KEYS`, `_studio_page_snapshots`, CPL widgets, active_song_state | During A; also manual apply |
| D | **Page snapshots** | `studio_page_persistence.py` | Per-page whitelisted keys in `_studio_page_snapshots` | On page nav, autosave flush, **every rerun (bug)** via tracker reset |
| E | **Active song canonical blob** | `active_song_state.py` | `active_song_state` meta + globals (instrument, level, focus, display_key, pick_key) | `prepare_canonical_music_page_state()` before widgets |
| F | **Studio nav canonical** | `studio_nav_state.py` | `studio_page`, nav history | prepare + restore |
| G | **Practice / backing canonical** | `practice_state.py`, `backing_track_state.py` | Page-specific durable prefs | prepare + build_music_disk_state commits |
| H | **Custom song / CPL** | `custom_progression_lab.py`, `custom_song_library.py` | `cpl_*`, `_cpl_widget_state`, cloud library merge | Restore + widget export/import |
| I | **Widget priming** | `practice_setup_controls.py`, backing prepare_* | Prefixed keys (`::qc_instrument`) + global keys | Before widget render |
| J | **Autosave / force save** | `build_music_disk_state`, `force_autosave` | Re-serializes A+C+D into cloud/disk | End of rerun, user actions, page_change |
| K | **Cold-start defaults** | `ensure_master_song_initialized`, ephemeral Say pin | Say / Practice when “empty” | Early + post-nav startup |
| L | **Multitrack blobs** | `multitrack_session_persistence.py` | `mt_tracks` in session + multitrack page snapshot | Upload save, restore |
| M | **AMI return / resume** | `applied_math_return_insight.py`, `suite_resume_launch.py` | Insight keys, deferred nav | Between early and late prepare |

---

## 2. Keys written by multiple systems

| Key(s) | Writers | Conflict |
|--------|---------|----------|
| `studio_page` | core, session, studio_nav_state, page_change stamp, AMI return, resolve_studio_page_for_restore | Reboot → Practice when stale core wins |
| `active_catalog_pick_key`, `selected_song` | core restore, ensure_master, ephemeral pin, apply_pick_key, custom reconcile, active_song prepare | Reboot → Say; custom trapped |
| `active_music_source`, `song_picker_active_source` | music_source reconcile, session restore, CPL activation | Catalog ↔ Custom stuck |
| `instrument`, `level`, `focus` | core, session_extra, active_song_state prepare (apply_globals), sidebar widgets | Controls stuck after restore |
| `display_key` | key_state, active_song prepare, song change, session restore | Previous song key carries over |
| `workspace_genre_filters` | session restore, page snapshot restore, toggle on_click | Genre stuck (v10 touch guard) |
| `improv_intelligence_tab` | session restore, page snapshot, radio on_change | Creative mode stuck |
| `mt_tracks` | session restore, page snapshot, multitrack restore helpers | Phone miss when cloud fails |
| `_backing_autoplay`, `playback_start_time` | backing UI, page snapshot (volatile) | Stop / tempo lock |
| `_studio_page_snapshots` | flush on autosave, cloud restore, save on toggle | Stale snapshots replayed every rerun |

---

## 3. Systems that overwrite user actions

| Mechanism | Symptom | Trigger |
|-----------|---------|---------|
| Page snapshot restore every rerun | Genre, creative mode, backing transport stuck | `reset_page_snapshot_tracker()` line 43 |
| `prepare_active_song_context` clears local_edit on restore run | Instrument/level/focus stuck | `active_song_state.py` (fixed v11) |
| `apply_globals=True` after restore | Sidebar snapback | canonical prepare before sidebar widgets |
| `ensure_master_song_initialized` + ephemeral Say pin | Reboot → Say | cloud has stale pick_key; skip logic sees “restored” |
| `build_music_disk_state` flush_current_page_snapshot | Stale picker snapshot saved mid-rerun | autosave after first genre click |
| Cloud save succeeds on disk only | Multitrack missing on phone | force_autosave returned True (v10 gated) |
| `reconcile_picker_music_source` before widgets | Catalog/custom radio wrong | order vs pending custom activation |

---

## 4. Restores that happen after widgets render

Streamlit reruns top-to-bottom. **Correct order:** restore → prepare (before widgets) → render widgets → commit/autosave.

**Actual problematic order in `streamlit_music_practice_app.py`:**

1. Line ~43: tracker reset (was every run)
2. Line ~1119: **first** `prepare_music_workspace` (cloud restore)
3. Line ~1216: `get_song_context` — uses post-restore or pre-default state
4. Line ~1240: ephemeral Say pin (if not skip)
5. … ~8000 lines of helpers …
6. Line ~9210: AMI hydrate
7. Line ~9191: **second** `prepare_music_workspace` (re-restore)
8. Line ~9211: `run_post_nav_music_startup_init`
9. Line ~9254: `handle_studio_page_transition` (page snapshot)
10. Line ~9522: sidebar instrument/level widgets
11. End: autosave

**After widgets:** autosave, `clear_music_workspace_autosave_block`, insight persist — OK.

**Bug:** Steps 1–9 can repeat clobbering between step 3 helper definitions and step 10 if snapshots re-apply on reruns 2+.

---

## 5. Startup paths that force Say / Practice

| Path | Condition | Result |
|------|-----------|--------|
| `ensure_master_song_initialized` | `music_should_skip_master_song_init` false (cold_start) | DEFAULT_SONG_RECORDS[0] → Say |
| Ephemeral Say pin | not skip + core library mode + non-trusted chart | Say with `_music_default_song_ephemeral` |
| Cloud restore applies stale core | `pick_key: Pop::Say — John Mayer` in cloud blob | Say restored faithfully |
| `skip_master` with `cloud_payload_pick_key` | Any cloud pick_key (including stale Say) | Skips ensure_master but **keeps Say from cloud** |
| `studio_page` default | Missing/empty in blob → `"practice"` | Practice page |
| page_change save while ephemeral | Was blocked v10 for ephemeral; cloud may already contain Say | Persistent stale state |

---

## 6. Priority findings

### P1 — Reboot restore (biggest blocker)
- Cloud blob is source of truth but may contain ** stale Say/Practice from prior ephemeral sessions**
- Custom signals in same payload were not always promoted over catalog Say in core
- Two `prepare_music_workspace` calls with guard/no-op caused ordering bugs
- **Fix direction:** restore once; promote custom over catalog Say; `workspace_is_truly_empty()` before defaults; strip ephemeral pick_key from saves (v10)

### P2 — Controls stuck
- Page snapshot re-apply every rerun
- `prepare_active_song_context` cleared local_edit on restore run (**fixed v11**)
- Need systematic `_user_touched` / `local_edit` guards, not per-key whack-a-mole

### P3 — Catalog ↔ Custom
- `reconcile_picker_music_source` vs pending CPL activation race
- `active_music_source` in session vs `pick_key` custom:: mismatch

### P4 — Display key
- Rule exists in `songs/key_state.py` (`apply_display_key_for_active_song`) but prepare paths may skip `PENDING_DISPLAY_KEY` when canonical overwrites

### P5 — Multitrack cloud
- Same-device: disk + session; phone: cloud-first
- Duplicate base64 in session + snapshot → size limit → silent cloud fail
- v10: require cloud OK for multitrack force-save; always flush multitrack snapshot

### P6 — Backing transport
- Volatile keys in backing snapshot; v10 skips on restore; Stop must clear lead sheet + transport

### P7 — Ghost UI
- Shared `active_song_hub` container → `picker_active_song_hub` (v10) + CSS

---

## 7. Target stable model (v11 foundation)

```
Browser session start
  → begin_music_script_run()        # reset tracker ONLY on new session
  → sync_workspace_protocol()       # authoritative cloud/disk ONCE
  → run_post_nav_startup_init()     # defaults ONLY if workspace_is_truly_empty()
  → handle_studio_page_transition() # hydrate page snapshot ONCE per page
  → complete_music_restore_phase()  # gate: no more snapshot restore this page
  → render widgets
  → user actions win (local_edit / touch guards)
  → autosave commits live state
```

### Rules
1. **Restore once** per browser session (or when cloud newer than applied)
2. **User actions win** after restore phase complete
3. **Defaults only** when `workspace_is_truly_empty()`
4. **Page snapshots** hydrate once per page per session, or on explicit page navigation
5. **Never** `reset_page_snapshot_tracker` on every script rerun

---

## 8. v11 implementation (this pass)

| File | Change |
|------|--------|
| `music_restore_phase.py` | New restore-phase gate module |
| `studio_page_persistence.py` | Hydrate once; complete restore phase after transition |
| `streamlit_music_practice_app.py` | `begin_music_script_run`; ephemeral gated by `workspace_is_truly_empty` |
| `active_song_state.py` | Never clear local_edit on restore run |
| `music_persistent_state.py` | Mark workspace restore applied |

---

## 9. Remaining work (ordered)

1. Consolidate to **single** `prepare_music_workspace` per run (remove early duplicate)
2. Global touch guards for instrument/level/focus in session restore
3. Catalog/custom reconcile after restore phase only
4. Display key: enforce on every `apply_pick_key` / custom activation
5. Multitrack: dedupe blobs in save payload; surface size skip in UI
6. Backing: lock tempo/loops only while `BACKING_AUTOPLAY`; release on Stop
7. Migration: scrub stale Say pick_key from cloud when custom signals present

---

## 10. Success criteria (unchanged)

- [ ] Reboot does not reset to Say/Practice
- [ ] Controls remain editable after restore
- [ ] Catalog ↔ Custom switching works
- [ ] Display key follows active song
- [ ] Multitrack sync reliable or clearly reports limits
- [ ] Backing Stop resets Generate state
- [ ] No major ghost UI

**Do not start AMI Importer until above pass live validation.**
