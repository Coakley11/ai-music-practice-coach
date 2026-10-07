# Practice Melody bug-fix batch — evidence

Produced while addressing the 6-item manual-testing feedback batch against
the `dev`-merged integration build (branch `integration/practice-melody-dev`,
worktree `ai-music-practice-coach-practice-melody-integ`).

## Item 2 — Practice navigation action on Backing

Code fix: `streamlit_music_practice_app.py`'s `_render_backing_return_source_action()`
previously hard-returned (suppressing the "Return to source" button entirely)
whenever `ctx.source == "regular_song"` — the common case for a Catalog song.
The underlying label/navigation logic (`return_to_source_button_label()`,
`practice_loop_backing_is_active()`, `target_page_for_backing_context()`,
`prepare_return_to_backing_source()` in `backing_source_navigation.py`) was
already fully correct and already returned `"Return to Practice"` plus
navigated to the Practice page — it just never got a chance to render for a
regular Catalog song, which is the common path through a Practice ->
"Loop X in Backing Track" handoff. The fix only bypasses that early return
when `practice_loop_backing_is_active(session)` is true; every other guard
(entry_jam/mission/song_improv, Creative/Custom/Composition return actions)
is untouched. The label itself now uses `feature_label("practice", ...)` so
it carries the app's canonical Practice icon (🎯), matching every other
`return_to_source_button_label()` branch's icon convention.

Regression coverage: `tests/test_practice_loop_section_backing.py::
TestCatalogPracticeLoopBacking::test_return_goes_to_practice` updated to
assert the icon-prefixed label; full file still 12/12 passing.

## Items 5/6 — chords above the generated melody notation

This was **already implemented**, not a new feature: `practice_melody_notation.py`
has passed `chords=list(section.chords)` into the shared
`composition_melody_notation.build_abc_from_melody_events()` builder (the
same ABC pipeline behind the existing Notation/TAB tool) since Practice
Melody's early slices. That builder places ABC chord-symbol annotations
(`"Chord"note`) at the correct per-measure onsets, which abcjs renders as
text above the staff natively — no new rendering code needed.

Verified two ways:
- Direct Python check: `practice_melody_full_song_abc(melody)` on a
  deterministic fixture produces
  `"C"c2 g e c2 e2 | "Am"c8 | "F"A4 f2 a2 | "G"g2 e2 B4 | ...` — chord
  symbols correctly interleaved per measure, matching the song's own
  progression (`C, Am, F, G | F, C, G, Am`).
- Live browser, on the `dev`-merged build: `desktop-A2-backing-c.png` (this
  folder) shows the Generated Practice Melody panel on Backing with
  **C, C, Csus4, Csus4, Csus4/D, Csus4/D** chord symbols rendered above the
  correct corresponding measures of notation.

## Item 3 — editable Backing scope after a Practice handoff

Code: unchanged — already correct. `_apply_pending_backing_scope()` only
*seeds* `backing_track_scope` / `backing_track_single_section` /
`backing_track_multi_sections` once (it pops the pending keys so they can't
re-apply on a later rerun), and the Practice Melody panel's displayed
section(s) (`_pmb_display_sections` in `streamlit_music_practice_app.py`)
are read fresh from the *live* `playback_scope` / `selected_section_names`
on every render — not a frozen snapshot of what Practice handed off. So
changing Backing's own scope radio after arriving from Practice already
flows straight through.

Regression coverage: `tests/test_backing_scope_widget_lifecycle.py` (5/5
passing) exercises this reconcile-order contract directly.

## Item 4 — chord highlighting coexists with the melody panel

No code change needed: the melody's `pm-current-measure` highlighting script
(`render_abc()`'s `measure_sync` branch) lives in its **own**
`components.html()` iframe, separate from Backing's lead-sheet iframe
(`live_follow_along_component_html()`). It only *reads* the lead sheet's
`#live-audio` element's `currentTime` via `timeupdate` — it never mutates
that element or any state the lead-sheet highlighting depends on. Opening
the Practice Melody panel cannot disable or replace the existing
chord-chart follow-along by construction.

Live confirmation of the two paired highlights advancing *simultaneously*
during playback was attempted but not conclusively captured in this
session, for the same reasons already documented in
`scripts/evidence-practice-melody-f2/README.md` (cross-iframe Frame-object
staleness / environment Chromium instability) — this is a carried-over,
already-disclosed limitation, not a new one.

## Item 1 — "All the Things You Are" -> "Say" song-identity bug

**Not reproduced.** See the final report for the full writeup: extensive
browser reproduction attempts (17+ Practice Key changes across both
same-titled catalog records, fresh sessions each time) never triggered it.
One architectural hardening fix to `songs/state.py get_song_context()` was
attempted and reverted after it broke 11 unrelated, legitimate tests
(explicit Custom -> Catalog source-switch flows rely on the exact fallback
behavior that fix removed). Separately discovered: 9+ pre-existing failing
tests in `test_music_source_ownership.py`, `test_cpl_set_active_song.py`,
`test_backing_source_navigation.py`, and
`test_creative_backing_stabilization_pass8.py` — all in the song/source
ownership-resolution area, present identically on this feature branch's
`dev` base *and* current `dev` tip (confirmed via a clean `git diff`), so
not introduced by Practice Melody. Flagged as a separate, pre-existing issue
cluster warranting its own dedicated investigation.
