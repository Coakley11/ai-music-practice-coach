# Checkpoint — Feel Play replacement (8510)

**Date:** 2026-09-24
**Branch:** feature/backing-advanced-key-cycling
**Exact SHA:** local WIP on top of `764a8595001d92c19171416ab03b44dff065daf6` (uncommitted Feel lag/remount fixes)
**Prior WIP chain:** `e2b0d53` → `bada74e` → `1131827` → `764a859`
**App:** http://127.0.0.1:8510 left running; cycling Off; `KC_SHORT_PASS_*` unset.
**Runtime:** `_runtime_key_cycle_8510_feel`

## Product fixes (Feel Play replace)

Rejecting operations identified (no Feel-only force flag):

1. **Sticky Rock override** — returning to catalog Pop kept a prior Rock play-session override → Pop Play synthesized Rock.
2. **Lagging selectbox → `rendered_widget_wins`** — remount wrote Rock/Blues over committed canonical.
3. **Capture before canon sync on on_change** — preferred stale Blues canon over a fresh Pop widget.
4. **`recover_play_session_overrides_from_backing_context`** — resurrected `ctx.style=Blues` after Pop cleared overrides.
5. **Pass-bridge `st.rerun` while Pending** — natural playing ack aborted the script before Blues Play reached `generate_saved` (run11).
6. **Dirty early-return skipped Pending canon→widget push** — Feel on_change marks dirty; bind never pushed Pop into a lagging Blues selectbox.
7. **Pending flush lag** — Blues widget echoing audible arrangement overwrote Pop canon while Pending.
8. **Post-Play remount on_change** — `_kc_settings_applied_this_play` remount flushed catalog Pop over sealed Blues before `note_` could ignore noise (run21 pop2 miss).

Shared path with BPM: `adopt_explicit_arrangement_url` + `forceArrangementReplace` / `set_src`; Pending bind/flush/coerce prefer canon.

## Why earlier runs landed on Say

`boot_backing` used a vague Shape-of-You click without verifying catalog owner; persisted workspace kept Say (John Mayer) as backing source while Intermediate/82bpm came from that visit. Proof now uses `goto_backing_shape` + owner probe (`active=shape`).

## Units (separate from browser)

- `test_pending_bind_pushes_canon_feel_even_when_dirty` — ok
- `test_flush_pending_rejects_audible_feel_lag` — ok
- `test_pass_bridge_defers_ack_while_settings_pending` — ok
- `test_lagging_feel_widget_does_not_clear_pending_for_canon` — ok

## Browser — Pop→Blues→Pop (one revision)

| Run | Result | Notes |
|-----|--------|-------|
| run15 | fail `feel_pop2_audible` | Shape ok; Blues `generate_saved` ok; pop2 gen Blues (canon flipped) |
| run21 | fail `feel_pop2_audible` | pop1+blues replace/set_src; pop2 already-Pop / no gen (post-Play remount) |
| **run22** | **PASS** | Shape; Pop/Blues/Pop each `generate_saved` + `replace`/`set_src`; matching `cmd_url` |

Evidence: `scripts/evidence-key-cycle/feel_replace_run22.txt`, `feel_replace_8510.json`.

## Still open (no full manual review yet)

1. Transport-label sync (cycle bar vs Live Follow-Along)
2. Fresh-session Resume
3. Verse+Chorus + natural key change
4. Brief BPM replace recheck (shared capture/flush path changed)

Written/instrument/shape deferred. Caption fix preserved. No push/merge/PR.
