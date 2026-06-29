# Creative Page → Backing Track routing plan

**Branch:** `dev`  
**Last updated:** 2026-06-29  
**Status:** Design — implement after review

## Problem

Create → **Entry & Jam** and Create → **Missions** both expose **Open Backing Track**, but today the handoff is partial and scattered:

| Current behavior | Gap |
|------------------|-----|
| `_improv_open_backing()` calls `apply_improv_song_source()` + `_improv_apply_playback_from_style()` | Only BPM/groove from `improv_style_meta`; missions/sections/progression not fully applied |
| Custom Progression Lab uses `prepare_cpl_backing_handoff()` | Good precedent — Creative has no equivalent |
| Backing page reads `backing_track_state` + live widget keys | No single “where did these settings come from?” object |
| Active song change detected in `active_song_state` | Does not invalidate Creative override |

**Goal:** One canonical `backing_context` drives Backing Track when opened from Creative; user can reset to regular song backing; song change clears stale Creative context.

---

## Canonical state: `backing_context`

New module: `backing_context.py` (display-only + routing; does **not** replace `backing_track_state` persistence).

**Session key:** `backing_context`  
**Persist:** yes — include in `_PERSIST_KEYS` / workspace envelope (metadata only, no audio).

```python
BackingSource = Literal["regular_song", "entry_jam", "mission", "custom_progression"]

@dataclass
class BackingContext:
    source: BackingSource
    source_label: str          # "Entry & Jam" | "Mission" | "Regular song" | "Custom progression"
    active_song_id: str        # pick_key or custom id (playback_song_id)
    song_title: str
    key: str                   # concert / key center
    display_key: str
    concert_key: str
    bpm: int
    style: str                 # Style jam label or mission style hint
    groove: str
    section: str | None        # single section scope when set
    sections: list[str]        # multi-section names when scope = multiple
    scope: str                 # mirrors backing_track_scope
    loops: int
    progression: list[str]     # flat chord list for generator
    progression_label: str     # "Say · Verse" or "Modal Vamp · Dm"
    duration_bars: int | None
    loop: bool
    mission_id: str | None
    jam_id: str | None         # style jam / entry mode id
    entry_mode: str | None     # Song-Based | Style Jam | Jam Session
    created_at: str            # UTC ISO
    updated_at: str
    source_signature: str      # hash for “did Creative settings change?”
    bound_pick_key: str        # active song when context was opened — for invalidation
```

### `source_signature`

Deterministic hash of fields that affect backing generation:

```
pick_key, source, entry_mode, mission_id, bpm, groove, style, section(s),
progression (joined), improv_style_meta, active CPL revision id
```

Re-opening from Creative with a **different** signature → replace context and re-apply to Backing widgets (requirement 2).

---

## Priority / resolution rules

On **Backing Track page load** (`prepare_backing_page` extension):

```
1. If backing_context.source != regular_song AND context is valid:
     → apply_backing_from_context(session)
2. Elif active_music_source == custom AND cpl active:
     → treat as custom_progression (migrate existing CPL path into context)
3. Else:
     → regular_song — apply_backing_defaults_for_song(active song)
```

### Validity checks (`is_backing_context_valid`)

| Rule | Action |
|------|--------|
| `bound_pick_key != current pick_key` | Invalidate → `clear_backing_context()` → regular song |
| `source == mission` and `mission_id != session.improv_active_mission` | Invalidate |
| `source == custom_progression` and CPL revision id changed without re-handoff | Invalidate |
| User clicked **Use regular song backing** | Clear context → regular song |
| Context older than session but signature matches re-open | Refresh `updated_at` only |

**Active song change** hooks (single place):

- `active_song_state.commit_active_song_state_from_session` after pick_key change
- Song picker apply / `apply_saved_music_context` authoritative restore

Call: `backing_context.invalidate_if_song_changed(session, new_pick_key)`.

---

## Handoff builders (Creative → Backing)

Replace ad-hoc logic in `_improv_open_backing()` with:

### `build_backing_context_from_entry_jam(session) -> BackingContext`

Read from:

- `improv_entry_mode` (Song-Based / Style Jam / Jam Session)
- `improv_song_source` (Active song / Custom progression)
- `improv_style_meta`, `improv_generated_sections`
- `ImprovSessionContext` fields (sections, bpm, display_key, progression_flat)
- Widget keys: `improv_style_bpm`, `improv_groove`, `improv_jam_key`, section pickers

Map scope:

- Full song vs single section from mission/entry UI when present
- Default loops from CPL/active or `BACKING_LOOPS_DEFAULT`

### `build_backing_context_from_mission(session) -> BackingContext`

Read from:

- `improv_active_mission` / `load_mission_example`
- Mission template: section, chord, level, focus, suggested BPM/groove
- Same song source as entry jam

### `apply_backing_context_to_session(session, ctx) -> None`

Single writer to Backing Track — mirrors `prepare_cpl_backing_handoff`:

1. Set `active_music_source` if custom progression
2. `prime_active_song_bpm` / `request_backing_bpm`
3. `request_backing_groove` / scope / section / loops
4. Write `backing_track_state` canonical blob via `write_canonical_backing_state`
5. Set `BACKING_NEEDS_REGEN = True`
6. Store `session["backing_context"] = ctx`

### `open_backing_from_creative(session, *, source: BackingSource)`

```python
ctx = build_backing_context_from_entry_jam(session)  # or mission
ctx = refresh_backing_context_timestamps(ctx)
apply_backing_context_to_session(session, ctx)
navigate_studio_page(session, "backing")
```

**CPL migration:** `prepare_cpl_backing_handoff` becomes thin wrapper → `build_backing_context_from_cpl` + `apply_backing_context_to_session`.

---

## Backing Track UI

### Context banner (top of backing page)

Display-only; reads `backing_context`:

| Source | Example |
|--------|---------|
| Entry & Jam | `Backing source: Entry & Jam · Say · G · 82 BPM` |
| Mission | `Backing source: Mission · ii–V–I drill · 90 BPM` |
| Custom progression | `Backing source: Custom progression · Gmaj7–Em7–Cmaj7–D7` |
| Regular | `Backing source: Regular song · Say · G · 82 BPM` |

Implementation: `render_backing_context_banner(st, session)` in `backing_track_ui.py` (new small module or section in app).

### Reset control

When `source != regular_song`:

- Button: **Use regular song backing**
- Handler: `clear_backing_context(session)` + `restore_regular_song_backing(session)`:
  - Clear Creative override keys (`improv_style_meta` handoff flags optional)
  - `apply_backing_defaults_for_song` for current active song
  - Set `backing_context.source = regular_song`
  - Do **not** navigate away

---

## Files to touch (implementation phase)

| Area | Files |
|------|--------|
| **New** | `backing_context.py` — dataclass, build/apply/clear/validate/signature |
| **Creative handoff** | `streamlit_music_practice_app.py` (`_improv_open_backing`), `improvisation_intelligence_ui.py` |
| **CPL unify** | `custom_progression_lab.py` (`prepare_cpl_backing_handoff`) |
| **Backing load** | `backing_track_state.py` (`prepare_backing_page`), backing page block in `streamlit_music_practice_app.py` |
| **Song change** | `active_song_state.py` — invalidate hook |
| **Persist** | `music_persistent_state.py` — `_PERSIST_KEYS` |
| **UI banner** | new `backing_context_ui.py` or backing page section |
| **Tests** | `tests/test_backing_context.py`, extend `test_backing_page_snapshots.py` |

**Frozen (do not change routing):** `studio_nav_history` navigate/push/pop, `apply_music_disk_state` restore order, Tests A–E.

---

## Test plan

| # | Test |
|---|------|
| 1 | Entry & Jam (Song-Based) → Open Backing applies song, key, BPM, groove, scope |
| 2 | Entry & Jam (Style Jam) → generated progression + meta applied |
| 3 | Mission → Open Backing applies mission section/chord/BPM |
| 4 | Change Entry & Jam settings, Open Backing again → signature changes, widgets update |
| 5 | Change Mission, Open Backing again → new mission context |
| 6 | **Use regular song backing** → context cleared, defaults from active song |
| 7 | Change active song (picker) → stale entry_jam/mission context invalidated |
| 8 | Custom progression handoff → progression in context + backing |
| 9 | Load saved CPL progression → handoff still works via `custom_progression` source |
| 10 | Banner text matches source |
| 11 | Regular backing flow unchanged when no Creative context |

---

## Implementation order

1. **`backing_context.py`** + unit tests (build, signature, validate, clear)
2. **`apply_backing_context_to_session`** — wire to existing backing_track_state writers
3. **Replace `_improv_open_backing`** — entry jam + missions
4. **Refactor CPL** handoff to use same context
5. **Backing banner + reset button**
6. **Song-change invalidation** in active_song_state
7. **Persistence** + smoke Test D/E unchanged

---

## Acceptance

- Create → Entry & Jam or Missions → **Open Backing Track** opens Backing with Creative settings applied.
- Re-open after Creative edits updates Backing (no stale settings).
- **Use regular song backing** restores normal active-song mode.
- Changing active song clears stale Creative override.
- Custom progression path unified; clear returns to regular song backing.
- Existing regular Backing Track behavior preserved.
