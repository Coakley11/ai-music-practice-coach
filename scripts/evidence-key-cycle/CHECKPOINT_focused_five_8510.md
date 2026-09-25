# Checkpoint — focused key-cycle proofs (8510)

- **When:** 2026-09-25 (local)
- **Worktree:** `ai-music-practice-coach-backing-key-cycle`
- **Branch:** `feature/backing-advanced-key-cycling`
- **Committed SHA (chord-sync check 3):** `c0a3d03` / `c0a3d03ad9941bb1173f1b13a3c031d5e23acf82`
- **Tested tree for checks 4–5:** `c0a3d03` **+ uncommitted** `backing_key_cycle.py` (Manual Next liveHandoff / restart_load / onEnded one-step / playing-ack skip refuse) and focused proof scripts — **not pushed**
- **Port:** 8510 left running; cycling Off; `KC_SHORT_PASS_*` unset; no leftover proof jobs

## Product fixes (uncommitted on top of `c0a3d03`)

1. **Manual Next must load the new key** — `applyCmd` was updating `state.nextSounding` to +2 *before* the liveHandoff check, so Python-ahead (Bm→Am) looked like stale Python and `reject_handoff` kept the prior buffer. Capture `priorArmedNext` / `expectedNextInSequence(browser)` and treat intentional advance as not liveHandoff. Resume keeps same-URL; restart loads `@0`.
2. **Natural one-step** — `onEnded` refuses stale `nextSounding` ≠ expected next; ignore no-duration ended; final key uses `stopAtFinalKey`.
3. **Playing-ack skip refuse** — absolute align must not jump Fm→Am; only expected-next advance or same-key confirm.

## Browser proofs (separate from unit)

| Check | Result | Evidence |
|-------|--------|----------|
| 1 Pop→Bossa no Play | PASS (prior) | `pop_to_bossa_auto_8510.json` |
| 2 Verse→V+C no Play | PASS (prior) | `verse_to_vc_auto_8510.json` |
| 3 Chord sync natural handoff | **PASS** @ `c0a3d03` | `chord_sync_handoff_8510.json` — Bm mid-pass → Am; Current/Next matched timeline |
| 4 Final-key stop + Next wrap | **PASS** | `final_key_stop_next_8510.json` — Manual Next to Ebm; natural Ebm→Dbm; final stop retained Dbm/`atFinal`; no delayed restart; Next wraps to Bm @ t&lt;8. Setup: ordinary Manual Next + natural endings (no seek). Diag: `diag_fm_am_skip_8510.json` sequence `Bm,Am,Gm,Fm,Ebm,Dbm`; natural **Fm→Ebm** (not Am) |
| 5 Pending until Play / Play restarts first | **PASS** | `pending_play_restart_8510.json` — direction pending while mid=`Gm`; Play → `Bm` @ `t_early≈1.04` |

### Check 4 — Fm→Am root cause (evidence, not assumption)

First failing operation was **Manual Next applyCmd `reject_handoff` / `applyCmd_reject_stale_python`**: labels advanced (e.g. to Am/Fm) while the audible buffer stayed on the prior key (`bufKey` mismatch, sometimes `dur=0`). Natural end then swapped from the **wrong** buffer / armed neighbor, which looked like Fm→Am. Not a duplicate-event automation flake once buffer identity was traced.

## Unit (separate)

- `test_playing_ack_refuses_skip_ahead_of_expected` — PASS
- `test_natural_advance_stops_at_final_key_without_wrap` — PASS

## Leave state

- 8510 up, cycling Off, `KC_SHORT_PASS_*` unset
- Written/shape deferred; no merge/push/PR; no new manual-review request
