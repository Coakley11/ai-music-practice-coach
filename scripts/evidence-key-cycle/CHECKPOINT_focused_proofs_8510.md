# Checkpoint — focused browser proofs (8510)

Branch: `feature/backing-advanced-key-cycling`
Base: `0227624` / prior WIP `446c532`

## Browser proofs (independent evidence)

| Check | Result | Evidence | Notes |
|---|---|---|---|
| BPM audible replace (UI→Play) | PASS | `bpm_audible_replace_8510_run8_final.json` | Shared-path rerun after Resume fixes |
| Fresh-session refresh + Resume | PASS | `fresh_session_resume_8510_run10_final.json` | Continue-play rebuild when prepared bag empty |
| Verse+Chorus natural handoff | PASS | `vc_natural_handoff_8510_run4.json` | Lead sheet + labels agree; one advance |
| Pop→Blues→Pop run22 | accepted earlier | (prior) | Not re-run |

## Unit tests

`tests/test_backing_key_cycle_temporary_session.py` — 41 passed (includes refresh Resume → CONTINUE_PLAY).

## Product fixes in this checkpoint

- Fresh-session Resume rebuilds audible buffer via continue-play / WAV cache (not label-only).
- Sticky Resume until Pause; Restart oneshot (sticky restart broke long V+C).
- Pause/Resume control uses visible label; live playback label sync.
- Resume kick loads src + unmute; forceRetry includes resume/restart.

## Manual review leave

8510: cycling Off, `KC_SHORT_PASS_*` unset, no proof jobs. `dev` untouched.
