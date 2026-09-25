# Checkpoint — backing advanced key cycling / 8510 Pause transport

Date: 2026-09-23
Branch: feature/backing-advanced-key-cycling (worktree)
Base: 21b7ef0

## Root cause (Pause)

1. Chart follow `scrollIntoView` buried the cycle Pause row above the viewport.
2. Capture listeners created in the bridge **iframe realm** did not receive trusted
   mouse/pointer events on the parent document (synthetic `dispatchEvent` still worked).
3. Document `click` on Pause returned early, so click-only paths never toggled.

## Product fix

- `backing_key_cycle.py`: constrain chart scroll to chart host; pin transport row;
  sticky CSS; install capture via `parentWin.eval` (parent main world); bind ver 10;
  mousedown + click with debounce (no click early-return).
- `streamlit_music_practice_app.py`: live-follow highlight scrolls inside shell only.

## Browser (8510) — separate from units

### Transport (verified)

- `scripts/evidence-key-cycle/pause_transport_8510.json` — **ok=true**
  - Pause after Play: both cycle + live → Resume, position retained, unmuted=0
  - Enter Resume: one audible player, both → Pause
  - Pause after BPM replace (canon≈141): both → Resume
- Direct mouse: `pause_direct_mouse.json` ok=true

### finish_five combined (after transport)

- `finish_five_8510.json` — **ok=false**
  - Verse+Chorus scope: **pass**
  - Blues UI commit Pop→Blues: **pass** (`changed=true`); audible buffer still failed
    (`feel_blues_not_in_audible_buffer` — gen_groove null / src unchanged)
  - finish_five Pause used old click helper → `pause_click` setup fail (now wired to
    `click_pause_ordinary`; re-run needed for natural/refresh)
  - Remaining product: `bpm_140_vs_72_timing`, `natural_handoff_timeout`,
    `refresh_soft_hold`, `refresh_disk_new_session`, `resume_position`

## Units

- `tests/test_backing_key_cycle_temporary_session.py` + `sequence_nav.py`: **40 passed**

## Leave state

- 8510 running
- cycling **Off** (set after proofs)
- `KC_SHORT_PASS_*` unset
- Written / instrument / shape deferred
- Caption + BPM dual-buffer replace remain closed
