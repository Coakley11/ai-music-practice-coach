# Music Phase C — Canonical Page State Protocol

**Last updated:** 2026-06-08  
**Status:** In progress — `active_song_state.py`, `studio_nav_state.py`, `practice_state.py`, `backing_track_state.py` wired  
**Reference:** `baseball-stat-app/docs/BASEBALL_PAGE_STATE_PROTOCOL.md`  
**Phase B (shipped):** `docs/MUSIC_PHASE_B_PROTOCOL.md`

---

## Scope (this phase)

Phase C migrates Music workspace fields into canonical `{module}_state.py` blobs with dirty flags, prepare/flush lifecycle, cloud restore protection, and AMI return hooks.

**Shipped in v24 (first slice):**

| Module | Session key | Envelope field | Scope |
|--------|-------------|----------------|-------|
| `studio_nav_state.py` | `studio_nav_state` | `music_workspace_state.studio_page` | `studio_page` ownership |
| `active_song_state.py` | `active_song_state` | `music_workspace_state.active_song` | pick_key, display_key, instrument, level, focus |

**Shipped in v25 (second slice):**

| Module | Session key | Envelope field | Scope |
|--------|-------------|----------------|-------|
| `practice_state.py` | `practice_state` | `music_workspace_state.practice_filters` | groove, section focus, notation prefs, last mode |

**Shipped in v27 (durable practice restore):**

| Fix | Detail |
|-----|--------|
| Autosave guard | `commit_practice_state_from_session` preserves canonical groove/minutes unless locally dirty |
| Widget bind | `coerce_practice_groove_for_widget` / `prepare_practice_minutes_for_widget` prefer canonical over song/slider defaults |
| Restore hook | `prepare_practice_page()` runs immediately after cloud apply in `apply_music_disk_state` |
| Force save | `practice_edit` bypasses post-restore autosave block |
| Trace | `?dev=1` practice restore fields (canonical, envelope, cloud payload, widget, dirty, save reason) |

**Shipped in v28 (third slice):**

| Module | Session key | Envelope field | Scope |
|--------|-------------|----------------|-------|
| `backing_track_state.py` | `backing_track_state` | `music_workspace_state.backing_filters` | scope, sections, loops, BPM, groove, meter, volume |

**Queued (not started):** `creative_state`, `karaoke_state`, `upload_state`, `practice_log_state`

**Watch item (non-blocker):** First phone→Dell instrument/setup edit may not sync immediately; monitor on next acceptance pass.

---

## Lifecycle

```
Startup   → prepare_music_workspace()           # Phase B cloud/disk sync
         → prepare_canonical_music_page_state()  # Phase C reconcile (nav + song + practice)
Before UI → prepare_studio_nav() + prepare_active_song_context() + prepare_practice_page() + prepare_backing_page()
Practice  → prepare_practice_page() again before Practice widgets
Backing   → prepare_backing_page() before song-default sync and Backing widgets
User edit → on_change → flush_*_edits_and_save(reason="*_edit")  # song_edit, practice_edit, backing_edit
Page nav  → navigate_studio_page() → claim_studio_page_ownership() → force_save(page_change)
Cloud     → apply_cloud_*_if_allowed() — blocked when *_state_dirty
AMI return → apply_*_source_state_from_ami() via music_coach_context
?dev=1    → Phase C panels in music_persistence_trace sidebar
```

---

## Required module API

Each `{module}_state.py` exports:

| Function | Purpose |
|----------|---------|
| `prepare_*()` | Reconcile session keys vs canonical blob; respect dirty |
| `write_canonical_*_state()` | Single write path |
| `commit_*_from_session()` | Autosave path (no new local edit) |
| `flush_*_edits()` / `flush_*_and_save()` | User edit → force save |
| `is_*_locally_dirty()` / `mark_*_local_edit()` / `clear_*_local_edit()` | Cloud protection |
| `apply_cloud_*_if_allowed()` | Restore from disk/cloud blob |
| `apply_*_source_state_from_ami()` | AMI return |
| `render_*_state_debug()` | `?dev=1` sidebar |

---

## Integration (`music_persistent_state.py`)

- `_WORKSPACE_KEYS = ("active_song_state", "studio_nav_state", "practice_state", "backing_track_state")`
- `build_music_disk_state()` commits all canonical blobs
- `apply_music_disk_state()` restores nav, song, practice, and backing modules
- Force-save bypass: `song_edit`, `practice_edit`, `backing_edit`, `page_change`, insight reasons

---

## Acceptance matrix (A–E)

| ID | Scenario | active_song | studio_nav | practice | backing |
|----|----------|-------------|------------|----------|---------|
| A | Local edit survives prepare | ✓ | ✓ | ✓ | ✓ |
| B | Phone ↔ Dell cloud restore | ✓ | ✓ | ✓ | ✓ |
| C | Stale cloud blocked when dirty | ✓ | ✓ | ✓ | ✓ |
| D | Page nav does not clear filters | ✓ | n/a | ✓ | ✓ |
| E | AMI return restores context | ✓ | ✓ | ✓ | ✓ |

Tests: `tests/test_active_song_state.py`, `tests/test_studio_nav_state.py`, `tests/test_practice_state.py`, `tests/test_backing_track_state.py`

---

## Deploy marker

`studio-nav-stable-v28-phase-c-backing-track-state` (`music_persistence_trace.MUSIC_PERSIST_DEPLOY_VERSION`)
