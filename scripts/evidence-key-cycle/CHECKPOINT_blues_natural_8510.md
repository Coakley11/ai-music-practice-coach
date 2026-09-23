# Checkpoint — Blues feel + natural/refresh (8510)

**Date:** 2026-09-23
**Branch:** feature/backing-advanced-key-cycling
**SHA:** 21b7ef09719d955a057d91896508c74ee202e7da
**App:** http://127.0.0.1:8510 left running; cycling Off; KC_SHORT_PASS_* unset.

## Product fixes (this pass)

1. **Blues nested profile was Pop** — `resolve_backing_musical_profile_from_context` preferred catalog `ctx.style` (Pop) over the session Feel argument. Explicit non-Auto style now wins. Offline synth Pop vs Blues corr ≈ -0.13. `generate_saved` now shows nested=`Blues groove`.
2. **Cycle Off/On remount** — Advanced/Play remounts defaulted the radio to Off and called `stop_key_cycle`, dropping the dual-buffer. User toggles (on_change) or `force_off` still stop; spurious remount Off is ignored.
3. **STOPPED + explicit Play** — persistent player refused commands while `status=stopped` even after arming Play. Explicit restart / arrangement-replace flags now allow publish.

## Units (separate from browser)

- `tests/test_backing_musical_profile.py` + `tests/test_backing_key_cycle_temporary_session.py`: **59 passed**

## Browser (finish_five run12) — do not merge with units

| Check | Result |
|-------|--------|
| BPM 140→72 timing/replace | **pass** (wav_ratio≈1.92, set_src/replace) — was closed; re-opened by play publish fix |
| Feel Blues UI commit | pass |
| Feel Blues gen_groove | **Blues groove** (was null via audio_ready masking generate_saved) |
| Feel Blues src≠Pop | **fail** — generate_saved Blues but currentSrc not replaced |
| Verse+Chorus scope | fail (no chorus cross this run) |
| Pause ordinary | mixed — run11 full pass; run12 click reached handler but cycle/live desync |
| Natural handoff | fail (timeout run12; run11 quality wav mismatch) |
| Refresh soft | **pass** (run12) |
| Refresh new session + Resume plays key | fail (Resume click reached=false) |

## Caption / BPM replace

BPM replace proof in run12 **passed**. Caption checks not re-opened beyond that.

## Uncommitted (product + proofs)

- `backing_musical_profile.py`
- `backing_key_cycle.py` (Pause transport preserved; remount Off + STOPPED play)
- `tests/test_backing_musical_profile.py`
- `scripts/proof_kc_finish_five_8510.py` (+ prior pause/proof dirties)

Written/instrument/shape still deferred. No push/merge/PR.
