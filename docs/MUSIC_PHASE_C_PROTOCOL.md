# Music Phase C — Canonical Page State Protocol

**Last updated:** 2026-06-08  
**Status:** In progress — `active_song_state.py` + `studio_nav_state.py` wired  
**Reference:** `baseball-stat-app/docs/BASEBALL_PAGE_STATE_PROTOCOL.md`  
**Phase B (shipped):** `docs/MUSIC_PHASE_B_PROTOCOL.md`

---

## Scope (this phase)

Phase C migrates Music workspace fields into canonical `{module}_state.py` blobs with dirty flags, prepare/flush lifecycle, cloud restore protection, and AMI return hooks.

**Shipped in v24 (first slice only):**

| Module | Session key | Envelope field | Scope |
|--------|-------------|----------------|-------|
| `studio_nav_state.py` | `studio_nav_state` | `music_workspace_state.studio_page` | `studio_page` ownership |
| `active_song_state.py` | `active_song_state` | `music_workspace_state.active_song` | pick_key, display_key, instrument, level, focus |

**Queued (not started):** `practice_state`, `backing_track_state`, `creative_state`, `karaoke_state`, `upload_state`, `practice_log_state`

---

## Lifecycle

```
Startup   → prepare_music_workspace()           # Phase B cloud/disk sync
         → prepare_canonical_music_page_state()  # Phase C reconcile
Before UI → prepare_studio_nav() + prepare_active_song_context()
User edit → on_change / song pick → flush_active_song_edits_and_save(reason="song_edit")
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

- `_WORKSPACE_KEYS = ("active_song_state", "studio_nav_state")`
- `build_music_disk_state()` commits both canonical blobs
- `apply_music_disk_state()` uses `resolve_studio_page_for_restore` + `apply_cloud_active_song_state_if_allowed`
- `prepare_canonical_music_page_state()` called after `prepare_music_workspace()` in main app
- `flush_active_song_edits_and_save()` uses `song_edit` force-save bypass (suite_user_persistence)

---

## Acceptance matrix (A–E)

| ID | Scenario | active_song | studio_nav |
|----|----------|-------------|------------|
| A | Local edit survives prepare | ✓ | ✓ |
| B | Phone ↔ Dell cloud restore | ✓ | ✓ |
| C | Stale cloud blocked when dirty | ✓ | ✓ |
| D | Page nav does not clear song | ✓ | n/a |
| E | AMI return restores context | ✓ | ✓ |

Tests: `tests/test_active_song_state.py`, `tests/test_studio_nav_state.py`

---

## Deploy marker

`studio-nav-stable-v24-phase-c-song-nav-state` (`music_persistence_trace.MUSIC_PERSIST_DEPLOY_VERSION`)
