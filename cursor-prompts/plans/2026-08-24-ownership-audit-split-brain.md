# Ownership audit — Creative/Backing split-brain (in progress)

**Last updated:** 2026-08-24  
**Branch:** `feature/creative-backing-stabilization`  
**Base checkpoint:** `b737f74` (persistence) + dirty Motif was already committed; ownership fixes below are WIP on working tree  
**Practice Focus:** untouched  
**dev:** untouched — do not merge  

## Chord first-click + Motif owner (added 2026-08-24)

### Human reports

| Bug | Symptom | First stale owner | Fix (WIP) |
|---|---|---|---|
| Two-click chord | Motif/Mission need second click | Click seal kept **symbol Bb** but **index still G**; `resolve_authoritative` / `resolve_mission_projection_state` replaced Bb with index chord G; Motif tiles lacked `st.rerun()` so highlight lagged | Click **symbol wins**; remap index to symbol; never overwrite symbol with different index chord; chord-tile `st.rerun()` after one click |
| Motif on G while Bb selected | Heading used `motif["chord"]` (stale G) while selection was Bb; notes could be Bb-family | Heading read artifact chord ≠ selected; tile generate didn't always stamp `motif["chord"]`; projection could restore G motif | Heading = **selected** `gen_chord`; retarget/regenerate when mismatch; stamp chord on tile generate; block projecting motif when `motif.chord != ii_selected_chord` |
| PK then click disk lag | After Practice Key change, UI shows Gbm but disk stays Abm | `reconcile_mission_target_identity` validated click against **stale** `improv_mission_chord_options` (Eb map); failed click → fell back to canonical **Abm**; Motif did not stamp live `_improv_mission_section_map` | Explicit click refreshes options from live section map; Motif/Live Coach stamp map+options; never rewrite click to stale canonical |

### Acceptance tuple (one click)

SELECTED TILE = CANONICAL CHORD = PAGE HEADING = GENERATION INPUT = GENERATED MATERIAL = SHEET OWNER

Unit: `tests/test_chord_owner_first_click.py` (includes stale-options→Gbm).  
Live: `scripts/_walk_motif_mission_chord_owner.py` — **all 7 gates PASS** on dirty tree @8521 (Motif first click / after PK / nav / refresh; Mission first click / after PK / after Backing). Shape of You pair was Ebm→Abm (or Dbm→Gbm after PK D), not G/Bb (song map has no G); same one-click owner tuple.

Not a human acceptance candidate yet — still part of the broader Creative/Backing audit; no merge to `dev`.


---

## 1. Human-reported bugs (screenshot subset)

| # | Symptom | Reproduced? | Root cause | Fix status |
|---|---|---|---|---|
| 1 | Custom SBI Backing return path + card = My Progression / C minor | **Yes (code)** | `ensure_custom_progression_for_backing` treated empty My Progression shell as valid (`bool(original_sections)`); remint wiped Trial; PK read used Shape `display_key` | **Fixed in WIP** — substantive check + LAST_CUSTOM install; Custom SBI PK from custom sticky |
| 2 | Trial Song identity + wrong key/material | **Yes (code)** | `sections_dict_from_backing_context(song_improv)` always synced **catalog** Shape charts | **Fixed in WIP** — Custom SBI uses CPL sections |
| 3 | Custom page → My Progression / C + Practice Dm after Trial | **Yes (code)** | `_last_custom_song_state` **not persisted**; reboot lost LAST_CUSTOM; CPL reminted shell; PK contamination | **Fixed in WIP** — persist LAST_CUSTOM; CPL restore via `install_last_custom_into_live_cpl` |
| 4 | SBI Custom “Key D” + Practice concert key Dm | **Yes (code)** | Two PK owners: card sticky/home D vs sidebar `display_key` Shape Dm | **Fixed in WIP** — `_resolve_creative_practice_concert_key` Custom SBI branch |

Unit proof: `tests/test_custom_sbi_split_brain.py` — **6/6 OK** after fixes.

---

## 2. Screenshot → root-cause mapping

```
Route/label: song_improv + custom::  ──► "Return to SBI Custom"
Material:    cpl_active = My Progression shell  ──► title My Progression / empty chords
Practice:    display_key = Shape Dm  ──► Practice concert key Dm / Cm fallthrough
LAST_CUSTOM: Trial Song @ D  ──► present in memory but ignored when shell.original_sections truthy
             and previously NOT on disk after reboot
```

Architectural rule violated: **one coherent tuple** (type + identity + original + practice + mode + progression) must share one owner. UI was composing fields from three owners.

---

## 3. Why prior harnesses were false greens (methodology)

| Pattern | Examples | Effect |
|---|---|---|
| Disk seed / reinforce between kill and start | `_walk_p6_*`, `_walk_p8_*`, `_walk_p9_*`, `_walk_disk_seed_*` | Proves hydrate of forged blob, not UI-saved state |
| Soft OR (UI **or** disk) | P5 `ui_ok or disk_ok`; P6 knobs optional | Disk green while card remints My Progression |
| Kind-only / substring | `song_improv`, `"trial song" in body` | Passes with Trial in sidebar and My Progression on card |
| Alias gates | `_walk_reboot_persistence_ai_p19` P6←F = page family backing | “P6 PASS” without Trial/D/progression |
| Unit hydrate with perfect session | `test_custom_sbi_backing_reboot_hydrate` | Never starts from My Progression shell + LAST_CUSTOM-only |
| Skip GA↔Custom↔SBI | Most walks | Misses Shape Dm contamination onto Trial |

**Invalidated:** prior claims that P1–P9 / reboot / Custom SBI were human-accepted.

---

## 4. Newly discovered (from audit so far — incomplete)

- LAST_CUSTOM absent from `music_persistent_state` `_SESSION_KEYS` (reboot killer)
- Default CPL shell blocks LAST_CUSTOM install
- Custom SBI section sync used catalog charts
- Creative practice key resolver preferred live `display_key` for Custom SBI
- `ensure_all_cpl_sections` **drops** non-form section keys (e.g. `"A"`) — fixtures/data with freeform section names lose chords on structure normalize (product risk if any Custom uses non-editable section names)

Broader A–T browser discovery: **not finished** — do not treat remaining areas as green.

---

## 5. Architectural owners (target)

| Concern | Winning owner |
|---|---|
| Custom page / SBI Custom identity | LAST_CUSTOM → CPL (substantive) |
| Custom SBI Practice Key | `practice_key_by_source[custom::…]` |
| Custom SBI progression | CPL `original_sections` @ Custom Practice Key |
| Global Active Shape | Songs / SBI Active / Missions parent only |
| Catalog `display_key` | Must not paint Custom SBI / Custom page |

Installer: `songs.music_source.install_last_custom_into_live_cpl`.

---

## 6–24. Area audit matrix (WIP)

| Area | Status |
|---|---|
| A Custom page | Partial — LAST_CUSTOM restore + persist; browser not fully green yet |
| B Global Active | Partial — contamination path identified; long session pending |
| C SBI Active | Not re-audited with new browser gate |
| D SBI Custom | Unit green for Trial install; UI walk script added, not yet green-run |
| E Open Custom / Return Creative | Pending |
| F Custom Active from Songs | Pending |
| G Mission | Pending (prior false greens) |
| H Mission Backing transpose | Pending |
| I Return Regular Backing | Pending |
| J Custom SBI Backing | Unit green; strict UI walk pending |
| K Regular Backing | Pending |
| L Jam | Pending |
| M Entry Style | Pending |
| N Live Coach | Pending |
| O Harmony | Pending |
| P Motif | Unit M1–M6 green on `b737f74`; not re-run after ownership WIP |
| Q Written/Shape/instrument | Pending |
| R Refresh | Pending (no disk reinforce) |
| S Real server reboot | Pending (no disk reinforce) |
| T Cross-workflow sessions | Pending |

---

## 25–29. Totals / branch

- Automated (this WIP): `test_custom_sbi_split_brain` 6 OK; prior hydrate/nav/first-click 16 OK regression  
- Browser totals: **not claimed** until strict walks pass without seed/reinforce  
- Branch: `feature/creative-backing-stabilization`  
- Practice Focus untouched  
- `dev` untouched  

## Next work (before any human URL)

1. Run `_walk_custom_sbi_split_brain_ui.py` against WIP Streamlit; fix until green  
2. Extend same strict style to Mission / Jam / Entry / refresh / real reboot  
3. Long Session A/B/C contamination walks  
4. Only then: commit ownership + Motif-adjacent test, clean worktree, ask for human acceptance  
