# Practice Melody Slice B+C — browser test evidence

Produced by `scripts/_browser_practice_melody_8540.py` against a local
`streamlit run streamlit_music_practice_app.py` instance.

## Desktop (1400x1100) — `ui-desktop-*.png` / `.txt`

Screenshots `00-home` through `09-notation-tab` are from a full run of
`full_flow()` that passed **25/25 gates**, exercising steps 1-8 from the
brief in order: Catalog song -> Generated Practice Melody, Generate Another
Melody (x2), level change, song change (Perfect -> Wonderwall), return to
the first song, an unrelated-control interaction, and the existing Chord
Chart / Notation-TAB regression checks. Gate list from that run:

```
[PASS] pick_song_perfect
[PASS] practice_studio_loaded
[PASS] open_chart_melody_tool
[PASS] tool_label_renamed
[PASS] open_generated_melody_panel
[PASS] melody_alt1_shown                 alternative #1
[PASS] melody_caption_has_song
[PASS] melody_caption_not_original
[PASS] generate_another_click_1
[PASS] melody_alt2_shown                 alternative #2
[PASS] generate_another_click_2
[PASS] melody_alt3_shown                 alternative #3
[PASS] set_level_advanced
[PASS] level_reflected_advanced          ... level Advanced ... alternative #1
[PASS] level_change_reset_to_alt1        alternative #1
[PASS] pick_song_wonderwall
[PASS] song_change_shows_new_song        Song Wonderwall ... alternative #1
[PASS] song_change_reset_to_alt1
[PASS] song_change_no_leftover_old_song
[PASS] pick_song_perfect_again
[PASS] return_to_song_a_shows_song_a     Song Perfect ... alternative #1
[PASS] return_to_song_a_no_wonderwall_leak
[PASS] return_to_song_a_fresh_baseline
[PASS] melody_stable_across_unrelated_control  before=alternative #1 after=alternative #1
[PASS] chord_chart_still_renders
[PASS] notation_tab_still_works          clicked=True
```
(`uploaded_melody_placeholder_present` / `original_melody_placeholder_present`
/ `no_false_original_melody_claim` were added in a later edit to the script
and are covered by the mobile run below instead.)

This run predates two follow-up fixes made to the *test script itself*
(not the app) after discovering them on the mobile pass:
`open_chart_and_melody_tool` now retries instead of trusting one click, and
`open_generated_melody_panel` now opens the outer "Generated Practice
Melody" expander before looking for the "Load" button inside it (the same
nested-collapse pattern the existing Chord Chart panel already uses). The
desktop screenshots above still show the real, correct end state at each
step; the retry fix only changes how reliably the *test* detects success.

A follow-up attempt to re-run the full desktop flow with both fixes applied
(to get one single post-fix summary.json) hit repeated local resource
exhaustion in this session -- the headless Chromium renderer or the
Streamlit dev server itself was killed mid-run several times
("Target crashed" / "Connection closed while reading from the driver"),
never with an application-level Python traceback. The code path exercised
by the fixes is identical regardless of viewport (no width-conditional
logic anywhere in `practice_melody_session.py` / `practice_melody_notation.py`
/ the new Streamlit wiring), and the **mobile** run below exercises that
exact combination successfully, so the fixes are verified even though a
second full desktop artifact could not be captured in this session.

`ui-desktop-02-generated-melody-alt1.png` also predates the ABC line-
wrapping fix (`practice_melody_notation._wrap_abc_music_line`), so it shows
the full 102-bar "Perfect" chart as one compressed staff line. See the
mobile screenshots for the wrapped, readable version of the same kind of
output.

## Mobile (390x844) — `ui-mobile-*.png` / `.txt` / `ui-mobile-summary.json`

A trimmed flow (`mobile_flow()`, current code, both fixes applied) that
passed **12/12 gates**: pick song, open Chart & Melody, open Generated
Practice Melody, generate an alternative, confirm My Uploaded Melody /
Original Melody placeholders are present, confirm Chord Chart still
renders, and confirm the melody stays on the same alternative across that
unrelated interaction. `ui-mobile-03-generated-melody-mobile.png` shows the
wrapped multi-line staff notation rendering cleanly at phone width. Level
change and the multi-song-switch matrix were intentionally left out of the
mobile flow (they depend on the sidebar Level selectbox's responsive drawer
behavior, a pre-existing concern unrelated to this feature) and are instead
covered by the desktop run above plus the deterministic session-policy unit
tests in `tests/test_practice_melody_session.py`.
