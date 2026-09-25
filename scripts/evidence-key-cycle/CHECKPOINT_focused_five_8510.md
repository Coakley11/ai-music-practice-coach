# Checkpoint — focused key-cycle proofs (8510)

- **When:** 2026-09-25 (local)
- **Worktree:** `ai-music-practice-coach-backing-key-cycle`
- **Branch:** `feature/backing-advanced-key-cycling`
- **Transition product SHA:** `d29d4ce` / `d29d4ce1c0a5051b5dabef3ee78a7369e99ff578`
- **Prior chord-sync checkpoint:** `c0a3d03`
- **Port:** 8510 left running for manual review; cycling Off; `KC_SHORT_PASS_*` unset; no leftover proof jobs

## Product fixes in `d29d4ce`

1. **Manual Next must load the new key** — intentional advance (`priorArmedNext` / expected next) is not liveHandoff; resume keeps same-URL; restart loads `@0`.
2. **Natural one-step** — `onEnded` refuses stale next; final key `stopAtFinalKey`.
3. **Playing-ack skip refuse** — no Fm→Am absolute align.

## Browser proofs (separate from unit)

| Check | Result | Evidence |
|-------|--------|----------|
| 3 Chord sync | PASS @ `c0a3d03` | `chord_sync_handoff_8510.json` |
| 4 Final-key stop + Next wrap | PASS | `final_key_stop_next_8510.json` |
| 5 Pending / Play restart | PASS | `pending_play_restart_8510.json` |
| Brief chord agree (post-commit) | PASS | `brief_chord_agree_after_next_8510.json` — Manual Next Bm→Am then natural Am→Gm; buf=sounding; Current/Next match timeline |

## Unit (separate)

- `tests/test_backing_key_cycle_temporary_session.py` — 47 passed on `d29d4ce` lineage (`unit_suite_d29d4ce.txt`)

## Leave state

- 8510 up, cycling Off, `KC_SHORT_PASS_*` unset
- Written/shape deferred; no merge/push/PR
