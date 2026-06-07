# Music persistence audit — Phase C (2026-06-08)

**Scenario:** Turn the Lights Back On · Guitar · D Major · Backing Track · custom section (Chorus)

**Goal:** Only **Reset** returns defaults. Refresh, reboot, and phone ↔ Dell should restore the same workspace.

---

## Survives refresh / reboot / cross-device

| Area | State | Mechanism |
|------|-------|-----------|
| **Active song** | Title, artist, `pick_key` | `core` blob → `apply_saved_music_context` |
| **Instrument** | Guitar | `core.instrument` |
| **Display key** | D Major | `core.display_key` → `PENDING_DISPLAY_KEY` |
| **Studio page** | Backing Track (`backing`) | `core.studio_page` + `session.studio_page` |
| **Section focus** | Chorus (practice) | `core.practice_focus_section` + practice page snapshot |
| **Backing scope** | Section vs full song | `backing_track_scope`, `backing_track_single_section`, `backing_track_multi_sections` |
| **Backing BPM / groove** | User settings | `backing_track_bpm`, `backing_groove_style`, etc. |
| **Backing page widgets** | Section picks, volume (page snapshot) | `_studio_page_snapshots["backing"]` |
| **Karaoke queue** | Queue + settings | `karaoke_queue`, countdown, auto-advance |
| **Custom progression** | Active + saved progressions | `cpl_active_progression`, `cpl_saved_progressions` |
| **CPL bar widgets** | Subdivisions, pending chords, edit section | **`_cpl_widget_state`** (Phase C) |
| **Catalog filters** | Search, genre, favorites | `_PERSIST_KEYS` session scalars |
| **Continue workflow** | Backing/practice/chord sessions | Command Center events (not passive `song_selected`) |
| **App Directory** | Current song, instrument | CC `ActivitySnapshot` + disk ingest |

---

## Does NOT survive (by design or gap)

| Area | State | Why |
|------|-------|-----|
| **Backing audio cache** | `_last_backing_wav`, timeline WAV | Regenerated from chart + settings on load |
| **Playback transport** | `playback_start_time`, mid-play position | Ephemeral UI |
| **Improv tile picks** | Dynamic `improv_live_s*_c*` keys | Not whitelisted in page snapshots |
| **Karaoke active session** | Mid-song countdown state | Stopped when non-voice instrument on load (by design) |
| **Chart editor undo stack** | In-memory only | Not persisted |
| **Written-key mode toggle** | If widget-only without session key | Survives only if bound to persisted key (verify in UI) |
| **Instrument / key-only navigation** | No Continue card | Directory shows instrument/key; intentional (Priority A) |

---

## Phase C changes (this pass)

1. **CPL bar widgets** — `export_cpl_widget_state` / `import_cpl_widget_state` in `custom_progression_lab.py`; stored in `session._cpl_widget_state`
2. **Cloud sync** — Synced `suite_user_persistence.py` from Command Center: `pick_restore_session`, local dirty flag, content fingerprint, cloud re-apply when newer
3. **Sync script** — `suite_user_persistence.py` added to `scripts/sync_suite_cloud_modules.py` (Command Center hub)
4. **Non-core songs** — `pick_key` + title recovery in `apply_saved_music_context`; missing catalog entry shows recovery notice (unchanged)

---

## Manual verification checklist

Use **Turn the Lights Back On** scenario:

- [ ] Refresh (F5) — same song, page, key, section, CPL bars
- [ ] Hard refresh — same
- [ ] Reboot Streamlit Cloud — same (requires Supabase `[suite_activity]` secrets)
- [ ] Phone ↔ Dell — cloud banner + matching state
- [ ] Command Center **Continue** — backing/practice workflow (not passive song pick)
- [ ] Command Center **App Directory** — current song + instrument
- [ ] **Reset** — factory defaults only

---

## Deferred

- Legacy Tracker-style **CPL fan simulator sliders** N/A
- Full **written-key mode** audit if widget lacks `key=`
- **Content-addressed** cloud merge (timestamp + fingerprint) — partial via autosave fingerprint in `suite_user_persistence`

**Last updated:** 2026-06-08
