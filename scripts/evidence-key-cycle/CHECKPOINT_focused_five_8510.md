# Checkpoint — focused key-cycle proofs (8510)

- **When:** 2026-09-25 (local)
- **Worktree:** `ai-music-practice-coach-backing-key-cycle`
- **Branch:** `feature/backing-advanced-key-cycling`
- **Final SHA (transition fixes + checks 4–5):** `d29d4ce` / `d29d4ce1c0a5051b5dabef3ee78a7369e99ff578`
- **Prior chord-sync checkpoint:** `c0a3d03`
- **Port:** 8510 left running for manual review; cycling Off; `KC_SHORT_PASS_*` unset; no leftover proof jobs

## Product fixes in `d29d4ce`

1. **Manual Next must load the new key** — `applyCmd` was updating `state.nextSounding` to +2 *before* the liveHandoff check, so Python-ahead (Bm→Am) looked like stale Python and `reject_handoff` kept the prior buffer. Capture `priorArmedNext` / `expectedNextInSequence(browser)` and treat intentional advance as not liveHandoff. Resume keeps same-URL; restart loads `@0`.
2. **Natural one-step** — `onEnded` refuses stale `nextSounding` ≠ expected next; ignore no-duration ended; final key uses `stopAtFinalKey`.
3. **Playing-ack skip refuse** — absolute align must not jump Fm→Am; only expected-next advance or same-key confirm.

## Browser proofs (separate from unit)

| Check | Result | Evidence |
|-------|--------|----------|
| 1 Pop→Bossa no Play | PASS (prior) | `pop_to_bossa_auto_8510.json` |
| 2 Verse→V+C no Play | PASS (prior) | `verse_to_vc_auto_8510.json` |
| 3 Chord sync natural handoff | **PASS** @ `c0a3d03` | `chord_sync_handoff_8510.json` |
| 4 Final-key stop + Next wrap | **PASS** | `final_key_stop_next_8510.json` |
| 5 Pending until Play / Play restarts first | **PASS** | `pending_play_restart_8510.json` |
| Brief post-commit chord agree | see `brief_chord_agree_after_next_8510.json` | Manual Next + one natural handoff |

### Check 4 — Fm→Am root cause

First failing operation was **Manual Next applyCmd `reject_handoff`**: labels advanced while the audible buffer stayed on the prior key. Natural end then swapped from the wrong buffer.

## Unit (separate)

- `tests/test_backing_key_cycle_temporary_session.py` focused suite on `d29d4ce`

## Leave state

- 8510 up, cycling Off, `KC_SHORT_PASS_*` unset
- Written/shape deferred; no merge/push/PR
