# Resume handoff — 2026-09-22 (caption pending verified)

## Repo
- Worktree: `C:\Users\danie\Documents\GitHub\ai-music-practice-coach-backing-key-cycle`
- Branch: `feature/backing-advanced-key-cycling`
- Base: `801bc09` + dirty WIP (caption pending content-match + arrangement replace)
- No push / PR / merge; `dev` / Creative untouched

## 8510
- Running (restarted after caption fix)
- Data dir: `_runtime_key_cycle_8510`
- Cycling: **Off** (leave script after proofs)
- `KC_SHORT_PASS_*`: unset

## Verified (browser) — caption pending

`proof_kc_caption_pending_8510.py` **run14** → `caption_pending_8510.json` **ok=true**

| Check | Result |
|-------|--------|
| Baseline working line 96/Pop | PASS |
| Pending after BPM 140 | PASS |
| Pending after Blues | PASS |
| After Play: **140 BPM (4/4, Blues)** | PASS |
| Pending cleared after Play | PASS |

**Product fix:** Pending clears when audible Tempo/Feel **content** matches selection after Play. URL-ready lag no longer re-forces Pending via `_mismatch`. Units: `TestPendingClearsOnlyWhenApplied` (5).

## Hang diagnosis (run12)

Blocked step: `play_apply.wait_kc_audio` — BPM/feel UI never committed (DOM≠session). Fixed proof commits (mouse Tempo + feel desync). Do not blind-restart long runs; read `hang.blocked_step`.

## Still WIP — `proof_kc_finish_five_8510.py`

run5/run6 **ok=false**. Outstanding:

1. BPM 140 vs 72 — generate bytes scale, but audible buffer/timeline often sticky or second Play leaves empty `src` (arrangement replace)
2. Feel Blues replace (needs Pop→Blues; load must change `src`)
3. Verse+Chorus highlight cross before natural key change
4. Pause/Resume both surfaces without fallback (`__kcPauseApplies`)
5. Natural handoff + one unmuted player
6. Refresh Held/Resume at cycle key start

Written/instrument/shape: deferred.

## Exact next step
1. Fix dual-buffer replace so Play at a new BPM loads the new WAV + follow timeline (see `_kc_force_arrangement_replace` / `needsReplace`).
2. Re-run `proof_kc_finish_five_8510.py` (no SHORT env).
3. Checkpoint when finish_five browser ok; leave cycling Off.
