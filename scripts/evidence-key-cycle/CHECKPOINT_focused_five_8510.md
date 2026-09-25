# Checkpoint — focused key-cycle proofs (8510)

- **When:** 2026-09-24 (local)
- **Worktree:** `ai-music-practice-coach-backing-key-cycle`
- **Code revision:** checkpoint commit **`35ba7ed`** + uncommitted chord-sync / final-key fixes (see below)
- **Port:** 8510 left running; cycling Off; `KC_SHORT_PASS_*` unset; no leftover proof jobs

## Product fixes since `35ba7ed`

1. **Chord sync (check 3)** — adopt follow timeline with prepared audio; do not clobber audible timeline with lagging Python `followTimeline` / empty arrays; push parent timeline into live-follow iframes; wrap Next Chord via event sequence modulo; promote `nextFollowTimeline` after handoff.
2. **Final-key stop (check 4 path)** — JS `onEnded` refuses seamless wrap to the first key when audible key is sequence-last; Python seals `_kc_hard_stop` on `final_key_stop`; cmd publishes `atFinalKey` and clears wrap `nextUrl` when on last key; `final_key_stop` handoff ack handled.

## Browser proofs (separate from unit)

| Check | Result | Evidence |
|-------|--------|----------|
| 1 Pop→Bossa no Play | PASS (prior) | `pop_to_bossa_auto_8510.json` |
| 2 Verse→V+C no Play | PASS (prior) | `verse_to_vc_auto_8510.json` |
| 3 Chord sync natural handoff | **PASS** | `chord_sync_handoff_8510.json` — Bm still on first sample; post-handoff Am Current/Next matched timeline (`Am`/`Dm`); parent+iframe timelines aligned |
| 4 Final-key stop + Next wrap | **NOT PASS yet** | Natural hops to final still flaky (`Fm→Am` skip); final-key stop JS/Python landed but end-to-end proof not green |
| 5 Pending until Play | **NOT RUN** (blocked on 4) | — |

### Check 3 — Bm advance classification

Prior FAIL: proof waited for Bm after long setup → **ordinary elapsed playback** had already advanced Bm→Am (not an unintended advance). This PASS landed on Bm mid-pass (`still_on_first_key`) and sampled before/after natural Am handoff with sheet open.

## Unit (separate)

- `final_key_without_wrap` — passed
- prepared timeline / settings_pending timeline — passed earlier in session

## Leave state

- 8510 up, cycling Off, `KC_SHORT_PASS_*` unset
- Written/shape deferred; no merge/push
