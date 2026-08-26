# Human retest embargo — agent status (2026-08-26)

## Embargo

**No human acceptance URL.** Continuing agent browser work until the core checklist is green.

## Root cause of the Shape Songs failure you hit

1. Contaminated proof `data/` left Shape sticky at `Dm` before human open.
2. `set_practice_concert_key` refused writing catalog Original (`Bm`) over sticky (`Dm`) — blocked intentional return to Original.
3. After allowing user restore, a **stale remount/pending write ~1–2s later** wrote `Dm` back over the `Bm` commit (SBI identity / pending_display_key), so the song card stayed on D minor until a full reload.

## Fixes in working tree (uncommitted)

| Area | Change |
|------|--------|
| Original restore | `allow_restore_original` + sidebar_on_change bypass of reseed guard |
| Card SSOT | sticky Practice Key preferred for catalog song card / authoritative key |
| Stale SBI prime | Songs/picker skips forcing SBI blob key over catalog sticky |
| Rollback guard | refuse identity/pending writes that disagree with live; **5s user-commit protect** after sidebar PK |
| Runtime isolation | `MUSIC_APP_DATA_DIR` for proof vs human data stores |
| Harness | `scripts/_walk_core_key_coherence.py` asserts rendered Practice Key badges |

## Browser-green now (isolated `MUSIC_APP_DATA_DIR`)

`scripts/_walk_core_key_coherence.py` → **ALL_PASS=True**

- Shape: fresh B minor → D minor → B minor → D minor (sidebar card badges)
- Perfect: fresh G major → A major (mode preserved)
- Shape reactivate after Perfect: stays minor

Unit: `tests.test_practice_key_state` + `tests.test_display_key_authoritative` → **14 OK**

## Not yet green (blocks human retest)

Still need agent visual browser walk of:

- Custom / LAST_CUSTOM / SBI Active vs Custom ownership
- Custom SBI Backing (Trial Em Em D D)
- Mission + Live Coach one-click chord
- Written Charts projection
- Mission Backing → Return; Return to Regular Backing
- Motif musical sanity
- Refresh + hard reboot from UI-mutated states
- Fresh human runtime (empty store, separate from proof)

## Branch / merge

- Branch: `feature/creative-backing-stabilization`
- **No merge to `dev`**
- Practice Focus untouched
- Changes not committed yet (await your commit request)
