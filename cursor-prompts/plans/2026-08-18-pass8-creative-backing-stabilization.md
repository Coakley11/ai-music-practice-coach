# Pass 8 — Creative / Backing stabilization (uncommitted)

**Last updated:** 2026-08-23  
**Branch:** `feature/creative-backing-stabilization`  
**Do not commit / push / merge to `dev` until the full matrix is green.**  
**Parked:** Practice Focus @ `542cf415643c0e98558c4cc6033ac2910a10bb63` (untouched)

Working tree sits on committed tip `533d60fb52e6525babac6e1cb75769566ef7008f`.

**Persistence contract (refresh / reboot):** [2026-08-23-persistence-contract-refresh-reboot.md](./2026-08-23-persistence-contract-refresh-reboot.md) — refresh is **not** leave; Creative selections, instrument/Written/Shape, Backing type+settings, and Practice Key editability must survive refresh/reboot. Live gates **P1–P9**.

---

# Current Priorities

## Frozen (do not reopen unless the matrix proves a regression)

- **Case A — Catalog Backing BPM lifecycle:** Default 96 → Current 110 survives rerun + refresh; true leave reseeds source. Current = `_backing_play_session.overrides.bpm`.
- **Mission B:** Mission Backing Practice Key Dm → Em (`concertEm` / `soundingEm`); Return-to-Mission first chord click C#m → Selected Mission Chord C#m immediately.
- **Jam key isolation:** Generated Jam F# → Shape of You Missions/SBI → Sounding / Practice Key Dm (`leak=False`).

## Active gate — generated Jam BPM

1. New generated-Jam Backing initializes source/default/Current/slider/card/banner from sealed generated BPM (e.g. 98), **not** catalog 96.
2. Existing Jam Current (e.g. 111) uses the same play-session Current model as Case A.
3. Refresh seeds the slider from Current **before** widget create.
4. Second generated Jam (e.g. 127) must not inherit prior 111 or catalog 96.
5. Entry Style Jam uses the same source-BPM path (e.g. 130 → edit 115 → refresh 115).

First 98→96 writer (fixed): `_source_defaults_from_session` preferred a leftover/expired catalog bag `defaults.bpm` (96) over sealed generated `ctx.bpm` (98) while minting a **new** Jam play session. Catalog pick BPM must not be authoritative for `entry_jam`.

## Next — active-source-change restore epoch (required before final matrix)

Implement **after** generated Jam BPM is live-green. Do not reopen frozen Case A / Mission B unless this exposes a real regression.

### Product rule (conditional restore)

> **SAME ACTIVE SOURCE:** top-level Backing resumes the last valid Backing session.  
> **DIFFERENT ACTIVE SOURCE:** old restore context is invalid; top-level Backing initializes **regular** Backing for the newly active source.

"Active source" includes at least:

- catalog song identity
- custom song / custom progression identity

The last Backing session is restored **only** while the user's active base source has not changed. An explicit active-source change creates a **new Backing-restore epoch**.

Do **not** solve this by making top-level Backing always open regular Catalog Backing.

### Navigation change vs source change

These are not the same event.

**NAVIGATION ONLY** (active source unchanged):

- Mission Backing for Clocks → Upload → Practice → Backing  
  → restore last valid Clocks Backing (Mission)

- Clocks Jam Generator Backing → Upload → Backing  
  → restore that Jam Generator session

**SOURCE CHANGE** (explicit pick / custom activation):

- Mission or Jam Backing for Clocks → Songs → select Love Story → Backing  
  → **regular Love Story Backing**, Practice Key = Love Story's own current key (e.g. C major)

Do not expire/clear the restore pointer merely because the user visits another page. Invalidate it because `old_source_identity != new_source_identity`.

### Restore eligibility invariant

Anchor each remembered Backing session to the active source at creation:

- `active_source_identity_at_creation` / `backing_restore_epoch`

```
restore_eligible =
  (last_backing_anchor_source == current_active_source)
```

If false: do not restore; initialize regular Backing for the current active source.

Generated Jam may have its own generated key/BPM/source identity, but **restore eligibility** is still associated with the active-source epoch in which it became the current Backing session. A stale generated Jam must not outrank a newly selected song.

### Invalidate at the source-change boundary (not downstream)

Preferred architecture:

1. user explicitly changes active source
2. detect `old_source_identity != new_source_identity`
3. invalidate old Backing restore eligibility / play session
4. establish new active source owner
5. persist new source Practice Key / context
6. subsequent Backing navigation initializes regular Backing for the new source

On a genuine identity change, invalidate **current** resume/workflow pointers from the old epoch, including as applicable:

- last-valid-Backing restore pointer
- Mission / SBI / generated-Jam Backing resume pointers
- active Backing play session
- temporary Backing overrides (BPM/style/meter/sections)
- stale source/card/context mirrors
- pending return handoff tied to the old source

Do **not** destructively delete separately persisted library/history content. Old source-specific Creative/Backing state must no longer be reachable as the **CURRENT** Backing restore context.

### Practice Key safety

A stale Backing session from the old source must **never** mutate the new source's Practice Key.

Failure to prevent: Clocks Eb remembered → select Love Story C → click Backing → stale session writes Eb into Love Story. Wrong.

On active-source change: the new source's Practice-Key owner wins immediately. Backing initialization is subordinate to that owner.

### Cases E1–E5 (matrix gate; not optional)

| Case | Sequence | Expected |
|------|----------|----------|
| E1 | Clocks → Mission Backing → Upload → Backing | restore Mission Backing Clocks |
| E2 | Clocks → Mission Backing → Songs → Love Story → Backing | regular Love Story Backing, Practice Key C major; **zero** Clocks Mission/Jam restore |
| E3 | Clocks → Jam Generator Backing → Upload → Backing (restore jam); then Songs → Love Story → Backing | regular Love Story Backing |
| E4 | Love Story → Mission Backing → Songs → Take Me Home, Country Roads → Backing | regular Country Roads Backing, D major |
| E5 | Country Roads → custom progression Trial Song → Backing | regular Trial Song Backing; no Country Roads state |

For every case record: `active_source_identity`, `previous_active_source_identity`, active source type, last Backing source, last Backing anchor source, restore eligible?, actual Backing source selected, Practice-Key owner/value, `play_session_id`, Mission/SBI/generated pointer state.

### Automated regressions (required)

1. same-song navigation restores Mission Backing
2. same-song navigation restores generated Jam Backing
3. selecting a new catalog song invalidates Mission restore
4. selecting a new catalog song invalidates generated Jam restore
5. new song Backing initializes its own Practice Key
6. old source Practice Key cannot overwrite the new song
7. custom progression change invalidates old restore
8. active-source change expires the old Backing play session
9. temporary BPM/style/meter/sections from the old source do not cross the source change
10. switching source twice always uses the latest active source

---

# Next Features

## Final source-transition matrix (Pass 8 gate)

Catalog Backing → SBI Backing → Mission Backing → Entry Style Jam Backing → Jam Generator Backing → Missions → SBI → Catalog Backing

Plus **Cases E1–E5**:

| Case | Sequence | Expected |
|------|----------|----------|
| E1 | Clocks → Mission Backing → Upload → Backing | restore Mission Backing Clocks |
| E2 | Clocks → Mission Backing → Songs → Love Story → Backing | regular Love Story Backing, Practice Key C major |
| E3 | Clocks → Jam Generator Backing → Upload → Backing (restore jam); then Songs → Love Story → Backing | regular Love Story Backing (jam restore invalidated) |
| E4 | Love Story → Mission Backing → Songs → Take Me Home, Country Roads → Backing | regular Country Roads Backing, D major |
| E5 | Country Roads → custom progression Trial Song → Backing | regular Trial Song Backing; no Country Roads state |

At each step capture: route, source kind/identity, play_session_id, active song, Practice-Key owner/value, generated key, instrument, Shape/Written, default BPM, Current BPM, slider BPM, Style, Meter, selected sections, restore eligibility.

Restart Streamlit from the same working tree and repeat abbreviated A–E after the matrix passes.

---

# Long-Term Vision

One Backing play-session architecture for all sources. Pages differ by source identity and constraints, not by parallel Current-BPM systems. Restore eligibility is always source-epoch scoped.

---

# Completed Features

- Catalog Case A Current/default/slider lifecycle (local green; frozen)
- Mission B Practice Key + first-click (local green twice; frozen)
- Generated Jam key isolation vs active-song Practice Key (local green)

---

# Notes

- Do not invent a separate generated-Jam Current BPM system.
- Do not solve source-change by making top-level Backing always open regular catalog Backing.
- Do not destructively delete separately persisted library content; only invalidate **current** restore/workflow pointers.
- Practice Focus remains parked; `dev` and `main` remain untouched.
