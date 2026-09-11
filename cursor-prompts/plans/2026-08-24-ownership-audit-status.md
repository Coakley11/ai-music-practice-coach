# Ownership audit status — Custom / SBI / Mission / reboot

**Last updated:** 2026-08-24  
**Branch:** `feature/creative-backing-stabilization`  
**HEAD:** `b737f743107b3129bdb33bd312524d25a4dbbe31` (dirty WIP beyond chord-owner freeze)  
**Practice Focus:** untouched  
**dev:** untouched — do not merge  
**Acceptance candidate:** none  
**Human retest:** not requested  

## Frozen (accepted on dirty tree — do not reopen unless regression)

1. One-click chord symbol authoritative  
2. Selected index remaps to clicked symbol  
3. Motif heading/generator use selected chord  
4. Explicit clicks validate against LIVE section options  
5. Practice Key changes do not validate against stale maps  
6. Motif register planning shifts by octaves only  
7. Motif/Mission owner tuple live-proven (click / PK / nav / refresh / Mission Backing return)

## Live browser — Custom family (improved; still RED overall)

Walk: `scripts/_walk_ownership_audit_full.py` + focused `scripts/_walk_focus_trial_orig_d.py` @ `:8521`

### Latest focused Trial proof (after Original Key reseed fix)

```
BUILD True — Original Key D major sticks on first set; Save to library OK
Custom SBI Backing: Practice concert key: D major  ← was F#m
Progression: Trial Song
```

| # | Gate | Status | Finding |
|---|---|---|---|
| 1 | Custom owner / Original Key D | **GREEN (focused)** | Reseed gate no longer wipes user C→D; `orig_saved_d=True` |
| 2 | LAST_CUSTOM | **PARTIAL** | Trial title + D home after save/leave |
| 3 | SBI Custom | **PARTIAL** | Trial title; Em chips not always in SBI body text |
| 4 | Open Custom / Return Creative | **PARTIAL** | Passed in full walk earlier |
| 5 | Global Active Custom | **PARTIAL** | Activate works; Shape PK intact still flaky after backing PK edit |
| 6 | Custom SBI Backing PK | **GREEN (focused)** | **D major** (F#m Shape leak fixed in resolver + Original D) |
| 7 | Mission example return | **RED** | Opens Custom fallthrough when GA=Trial; no Return to Mission |
| 8 | Mission Backing transpose | **RED** | Blocked by wrong backing owner |
| 9 | Return Regular Backing | **PASS** (once) | |
| 10 | UI-built reboot | **RED** | Restored Shape Active; lost Trial Custom SBI |
| 11 | Motif visual | **PASS** (surface) | Deeper MIDI/sheet still open |

### Product fixes this pass

- `cpl_page_ui.py` — Original Key reseed only for stale shell vs LAST_CUSTOM; allow user C→D  
- `backing_musical_state.py` — Custom SBI PK rejects live catalog F#m/Dm when home is D  
- Walks hardened for Original Key verify + Mission Jam button + strict reboot  

### Still RED before acceptance URL

1. Mission Backing must win over Custom GA  
2. Return to Mission + example restore  
3. Mission PK transpose note/MIDI/ABC  
4. Custom SBI backing PK edit must not rewrite Shape Global PK (C8 became E)  
5. UI-built reboot restores Trial/Custom SBI tuple  
6. Em Em D D visible progression assert on SBI/Backing card  
7. Motif sheet = MIDI sequence visual audit  

## Automated totals (this session)

| Suite | Result |
|---|---|
| `test_custom_sbi_split_brain` | 6/6 OK |
| `test_chord_owner_first_click` + motif register | OK (frozen) |
| Browser own-audit (prior) | 8/13 — Custom/Mission/reboot still RED |

## Notes

- Save toast text is `Saved **Trial Song** to your library.` (not literal “saved to custom library”).  
- Chord-owner freeze holds; no merge to `dev`.
