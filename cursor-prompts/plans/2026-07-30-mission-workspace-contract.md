# Mission Workspace Contract (long-term design)

**Last updated:** 2026-08-01  
**Status:** **Frozen** — implementation complete on `dev` (`4106a86`); manual cross-device sign-off pending.  
**Code:** `improvisation_mission_persistence.py`, `improvisation_missions.py`, `music_persistent_state._PERSIST_KEYS`, `studio_page_persistence` creative/backing snapshots.

---

## Intent

A Mission behaves like a **document in the user’s workspace**. Wherever they sign in, they continue exactly where they left off—refresh, close/reopen, or another device must not force regenerating work.

There is **one active Mission workspace per account**. **Latest saved state wins** (no conflict resolution or version history for v1).

---

## What the workspace must restore

| Area | Session / canonical keys (representative) |
|------|-------------------------------------------|
| Mission selection | `improv_active_mission`, `improv_mission_pick` |
| Song / section / chord | Active song hub + `ii_selected_*`, `improv_mission_progression` |
| Instrument / level / focus | Global musician settings (same as rest of app) |
| Generated example | `improv_mission_example` (full blob) |
| Difficulty variant | `variant` inside example + `improv_mission_variant` |
| Practice handoff | `improv_mission_practice_lick` |
| Backing transport | `backing_track_*` + fields mirrored into practice lick on persist |
| Workspace stamp | `improv_mission_workspace_updated_at` |
| Creative canonical | `creative_session` (tool_type `mission`) |

Mission Backing Jam must restore the **same practice session** (lick, BPM, groove, meter, loops)—not rebuild a new phrase.

---

## Single source of truth: motif

The stored **`motif` object** inside `improv_mission_example` / `improv_mission_practice_lick` is authoritative.

**Must render from motif (never regenerate the phrase on restore):**

- Notes and rhythm display  
- Sheet music (ABC via `build_motif_notation_abc`)  
- Guitar TAB (`build_motif_guitar_tab`)  
- Playback (ABC / abcjs)  
- Future: MIDI export, MusicXML export  

Allowed on restore: **rebuild notation/TAB at current BPM** from the same motif (`rebuild_mission_outputs` / `mission_example_for_display`).  
Forbidden on restore: new `generate_motif_for_chord` / new random seed for the same saved example.

---

## Persistence architecture (do not fork)

Missions use the **same cloud workspace** as the rest of Music Practice Coach:

1. **`_PERSIST_KEYS`** — mission keys in the workspace envelope (`build_music_disk_state` / cloud full session).  
2. **Page snapshots** — `creative` + `backing` whitelists in `studio_page_persistence.py`.  
3. **`sync_mission_workspace_before_persist`** — before every disk/cloud save; stamps `improv_mission_workspace_updated_at`.  
4. **`prepare_music_workspace`** — `cloud_first=True`; **`music_mission_cloud_drift`** triggers content resync when cloud mission state differs.  
5. **`apply_cloud_mission_state_if_allowed`** — overlay cloud mission slice on workspace restore (latest wins).

Do **not** introduce a separate Mission-only database, file, or sync channel.

---

## Cross-device behavior

- Laptop saves → phone opens same account → **same mission, example, lick, BPM, notation**.  
- Phone saves → laptop refresh → **updated** mission state from cloud.  
- User should feel like **opening the same project on another device**, not starting a new session.

**Manual acceptance (sign-off):**

- [ ] Refresh Creative → Missions → exact same generated example  
- [ ] Refresh Mission Backing Jam → exact same practice session  
- [ ] Laptop → phone sync (generate harder → jam → BPM 70 → autosave → phone)  
- [ ] Phone → laptop sync (new idea → BPM 85 → autosave → laptop refresh)  
- [ ] Notation, playback, TAB match stored motif (no new phrase)

---

## Future features (same workspace)

Build on this contract—**extend keys or catalog entries**, do not new persistence paths:

| Feature | Direction |
|---------|-----------|
| **Full Creative page workspace** | `creative_workspace_persistence.py` — tabs, Phrase & Motif blobs, Harmony Map picks, Deep Harmonic step/section idx (2026-08-01) |
| **Lick Library** | User-curated entries referencing saved `motif` blobs (+ metadata) in workspace or media catalog |
| **Favorite licks** | Flag on library entries or mission examples |
| **Practice history** | Append-only log keyed to motif fingerprint + mission id |
| **Composition Studio** | Handoff imports motif + ABC as inspiration seed |
| **AI feedback on past licks** | AMI context includes stored motif + mission metadata |

Interactive Mission Practice workspace (loop counter, note highlight, rep counts) remains UI on top of the same motif + backing transport—see product backlog.

---

## Related plans

- [2026-07-30-creative-experience-polish-sprint.md](./2026-07-30-creative-experience-polish-sprint.md) — Missions UX + Backing Jam  
- [2026-06-29-creative-backing-track-routing.md](./2026-06-29-creative-backing-track-routing.md) — backing context handoff  
- [music-persistence-audit-2026-06-08.md](./music-persistence-audit-2026-06-08.md) — global persistence baseline  
