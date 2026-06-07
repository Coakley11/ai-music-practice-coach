# Music persistence audit — Phase C (2026-06-08)

**Standard scenario:** Turn the Lights Back On · Guitar · D Major · Backing Track · custom section (Chorus)

**Highest-risk scenario:** **Non-core catalog song** — historically reverted to trusted-core defaults (Say, Perfect, Turn the Lights Back On) during init/restore.

**Goal:** Only **Reset** returns defaults. Refresh, reboot, and phone ↔ Dell restore the same workspace. Non-core songs must not be replaced.

---

## Restore path (exact pipeline)

```
App startup (streamlit_music_practice_app.py)
  │
  ├─ 1. restore_music_disk_state_once()
  │      └─ suite_user_persistence.restore_once("music")
  │           ├─ pick_restore_session(disk vs cloud, local_dirty, fingerprint)
  │           └─ apply_music_disk_state(payload)
  │                ├─ apply_saved_music_context(core) → apply_pick_key
  │                │    └─ SUITE_LOCAL_STATE_RESTORED_KEY = True ONLY if apply succeeded
  │                └─ merge session extras (_studio_page_snapshots, _cpl_widget_state, …)
  │
  ├─ 2. finalize_suite_resume_launch("music")  ← query params (suite_pick, suite_page)
  │      Skips disk restore when Continue/deep-link params present
  │
  ├─ 3. _skip_master_song_init guard
  │      True when: pick_key in session OR SUITE_LOCAL_STATE_RESTORED OR restore error
  │      └─ if False → ensure_master_song_initialized(DEFAULT_SONG_RECORDS)  ← trusted-core only
  │
  ├─ 4. Karaoke voice override (if active)
  │
  ├─ 5. get_song_context() → active song metadata
  │
  └─ 6. Trusted-core pin (FIRST RUN ONLY)
         Runs only when NOT _skip_master_song_init AND chart_library_mode=core
         AND song not trusted_core → apply_pick_key(DEFAULT_SONG_RECORDS[0])
         **Fixed 2026-06-08:** uses _skip_master_song_init (not weaker _music_state_restored)
         so restored/user-selected non-core songs are never replaced.
```

---

## Failure modes (audited)

| Symptom | Root cause | Fix / status |
|---------|------------|--------------|
| Non-core → Turn the Lights / Say / Perfect after refresh | Override block at ~1200 ran when `_music_state_restored` false but user had non-core pick_key pending autosave | **Fixed:** guard is `_skip_master_song_init` |
| Restore failed but init skipped | `SUITE_LOCAL_STATE_RESTORED_KEY` set even when `apply_saved_music_context` returned False | **Fixed:** flag only when `applied=True` |
| Song missing from catalog | `apply_saved_music_context` returns False → recovery notice; `ensure_master_song` may set trusted default | By design; user sees warning |
| Resume URL vs disk race | `finalize_suite_resume_launch` skips disk when query params present | Resume params must include pick_key |
| Cloud older than disk | `pick_restore_session` + `local_dirty` | Synced suite_user_persistence |
| Silent restore exception | `_music_restore_error` + dev sidebar warning | Existing |

---

## Survives refresh / reboot / cross-device

| Area | State | Mechanism |
|------|-------|-----------|
| **Active song** | Title, artist, `pick_key` (core **and** non-core) | `core` blob → `apply_saved_music_context` |
| **Instrument** | Guitar, Piano, etc. | `core.instrument` |
| **Display key** | D Major, F Major, etc. | `core.display_key` → `PENDING_DISPLAY_KEY` |
| **Studio page** | Backing Track (`backing`) | `core.studio_page` + `session.studio_page` |
| **Section focus** | Chorus / Verse (practice) | `core.practice_focus_section` + practice page snapshot |
| **Backing scope** | Section vs full song | `backing_track_scope`, `backing_track_single_section`, … |
| **Backing BPM / groove** | User settings | `backing_track_bpm`, `backing_groove_style`, etc. |
| **Backing page widgets** | Section picks, volume | `_studio_page_snapshots["backing"]` |
| **CPL bar widgets** | Subdivisions, pending chords | `_cpl_widget_state` |
| **Continue workflow** | Backing/practice sessions | Command Center events |
| **App Directory** | Current song, instrument | CC disk ingest |

---

## Does NOT survive (by design or gap)

| Area | State | Why |
|------|-------|-----|
| **Backing audio cache** | WAV blobs | Regenerated from chart + settings |
| **Playback transport** | Mid-play position | Ephemeral UI |
| **Improv tile picks** | Dynamic keys | Not in page snapshots |
| **Karaoke mid-session** | Countdown on non-voice load | Stopped by design |
| **Chart editor undo** | In-memory | Not persisted |

---

## Phase C code changes

1. **CPL bar widgets** — `export_cpl_widget_state` / `import_cpl_widget_state`
2. **Cloud sync** — `suite_user_persistence.py` (pick_restore_session, fingerprint, local_dirty)
3. **Non-core override fix** — `_skip_master_song_init` guard on trusted-core pin block
4. **Restore flag fix** — `SUITE_LOCAL_STATE_RESTORED_KEY` only when song apply succeeds
5. **Tests** — `test_non_core_song_scenario_blob`, `test_non_core_restore_failure_does_not_set_restored_flag`

---

## Manual verification checklist

### A — Trusted core (Turn the Lights Back On)

- [ ] Select Turn the Lights Back On · Guitar · D Major · Backing Track · Chorus
- [ ] Refresh (F5) — same song, page, key, section, CPL bars
- [ ] Hard refresh — same
- [ ] Reboot Streamlit Cloud — same (Supabase secrets)
- [ ] Phone ↔ Dell — cloud banner + matching state
- [ ] Command Center **Continue** — backing/practice workflow
- [ ] Command Center **App Directory** — correct song + instrument
- [ ] **Reset** — factory defaults only

### B — Non-core (highest risk)

Pick any catalog song **without** `trusted_core` / verified status (not Say, Perfect, Turn the Lights Back On):

- [ ] Change instrument + display key
- [ ] Open Backing Track; modify BPM/section/groove
- [ ] Refresh / hard refresh / reboot / second device
- [ ] Verify: same non-core song (no fallback to trusted-core defaults)
- [ ] Continue + App Directory point to **that** song

---

## Deferred

- Written-key mode widget audit
- Improv tile persistence
- Content-addressed cloud merge (partial via autosave fingerprint)

**Last updated:** 2026-06-08
