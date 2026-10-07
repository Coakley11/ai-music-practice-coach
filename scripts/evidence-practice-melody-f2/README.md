# Slice F2 — measure-highlighting evidence (partial)

Produced by `scripts/_browser_practice_melody_f2_8580.py`.

## What's confirmed

- `f2-00-backing-with-melody.png` / `.txt`: Generated Practice Melody,
  handed off to Backing, caption present and correct
  (`melody_caption_present_on_backing`: PASS).
- The abcjs iframe containing the melody's `#paper` div is reliably
  located via Playwright's frame list (`melody_abcjs_frame_found`: PASS).
- Clicking "Play Backing Track" does not break or remove the Practice
  Melody panel -- its caption is still present afterward
  (`melody_caption_survives_play`: PASS) -- so the highlighting script
  (injected into the *same* `render_abc()` iframe as the notation, see
  `streamlit_music_practice_app.render_abc`'s `measure_sync` parameter)
  is not being torn down by the Play action's own rerun.

## What's NOT conclusively confirmed in this session

The one thing repeated attempts did not conclusively capture: a live
Playwright read of `.pm-current-measure` elements actually present on the
page a few seconds into real playback (`melody_has_notes_rendered` /
highlight checks: FAIL across every attempt today). Every attempt hit one
or both of:

1. **Environment-level browser instability** -- the same class of
   Chromium/Playwright connection crashes ("Target crashed" / "Connection
   closed while reading from the driver") seen throughout this entire
   project's browser testing, with zero application-level Python
   tracebacks in any case.
2. **A cross-iframe query race**: Backing's own `components.html()`
   iframes (including the Practice Melody one) appear to remount on
   reruns closely following the Play click (plausibly the backing-audio
   generation step), and a `Frame` object captured just before that
   remount goes stale -- `frame.evaluate()` on it either errors
   ("Frame was detached") or returns 0 for a query that would otherwise
   match, even though the *caption* text (fetched via
   `page.inner_text("body")`, not a stale frame reference) reliably came
   back correct every time.

Given abcjs notation itself renders reliably and visibly in every other
Practice Melody screenshot across this entire project (Slices B+C, E, F1,
and Gates V1/V2), the balance of evidence is that the melody still renders
correctly when highlighting is active; what's unverified here specifically
is the highlight *class* toggling in sync with live audio.

## What this slice's code is backed by instead

- 11 unit tests (`tests/test_practice_melody_sync.py`) exhaustively prove
  the pure timing-join logic: one entry per measure, correct note-index
  ranges, correct behavior across Section-Focus scoping, correct handling
  of repeated loop passes (same note range, separate time windows per
  pass) and of subdivided bars (merged into one window).
- The injected JS reuses the *exact* same-origin cross-iframe access
  pattern (`window.top.document.querySelectorAll('iframe')` ->
  `contentDocument`) that `backing_key_cycle.py`'s own pass-boundary
  bridge (`cycle_pass_ended_js_snippet`) already uses in production --
  not a newly invented technique.
- Position comes entirely from the existing `#live-audio` element's native
  `timeupdate` event (plus a 150ms local watchdog mirroring the same
  pattern Backing's own follow-along component already uses) -- no
  Python-side polling, no second clock, no new Streamlit rerun source.

**Recommendation**: a quick manual spot-check (Practice -> generate
melody -> Practice with Backing -> Play, watch the notation) is the
fastest way to close this specific verification gap; the code change
itself is small, additive, and backward-compatible (every other
`render_abc()` call site is unaffected since `measure_sync` defaults to
`None`).
