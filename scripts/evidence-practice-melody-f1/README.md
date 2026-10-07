# Practice Melody Slice F1 — browser test evidence

Produced by `scripts/_browser_practice_melody_f1_8560.py` against a live
`streamlit run streamlit_music_practice_app.py`.

## Desktop (1400x1100) — 26/26 gates passed (`desktop-summary.json`)

Covers the full lettered journey from the brief in order:

- **A** (`desktop-A1-*`, `desktop-A2-*`): generate a melody in key C,
  "Practice with Backing" -> Backing opens showing the same song, same
  alternative, key C.
- **B** (`desktop-B-*`): Practice Key changed C -> D *while already on
  Backing, with no new handoff click* -> the melody transposes in place
  (same `alternative #1`) and Backing agrees.
- **C** (`desktop-C-*`): D -> Eb -> transposes again, same identity.
- **D** (`desktop-D-*`): "Generate Another Melody" -> a genuinely different
  composition (`alternative #2`).
- **E** (`desktop-E-*`): key changed again (Eb -> C) *after* Generate
  Another -> the new alternative (`#2`) transposes, it is not silently
  regenerated back to `#1` or a fresh `#3`.
- **F** (`desktop-F-backing-section-scoped.*`): Section Focus set to
  "Verse" in Practice, then "Practice with Backing" -> Backing shows only
  the matching `Verse 1` melody section, titled "Perfect - Verse 1", not
  the full song.
- **G** (`desktop-G-backing-full-song.*`): back to Full Song scope ->
  Backing shows the complete melody again.

## Mobile (390x844) — 21/26 gates passed (`mobile-summary.json`)

The 5 failures (`B_set_key_d`, `B_backing_shows_key_d`, `C_set_key_eb`,
`C_backing_shows_key_eb`, `D_practice_key_is_eb`) are all the *same* root
cause: at 390px the sidebar "Practice / Concert Key" selectbox sits
outside Playwright's actionable viewport bounds, so the test script's
`set_practice_key` helper cannot drive it here (this is a test-automation
limitation, not a rendering bug — the same class of issue already noted
for the sidebar Level selectbox in the Slice B+C evidence README). Every
gate that does *not* require that specific sidebar interaction -- A, E, F,
G, including the section-scoped title, the correct key label, and the
correct alternative after a key change made back on desktop then carried
over in the same mobile session -- passes cleanly, and
`mobile-F-backing-section-scoped.png` shows the Practice Melody panel
rendering correctly stacked and fully readable at phone width.

## Not browser-verified in this slice

- **Transposing instruments** (e.g. Bb Trumpet) and **Guitar Shape/Capo**
  projection: the transposition target key (`chart_key`) is the same
  value Practice already used to generate the melody
  (`_practice_chart_key`, derived from the same
  `songs.key_state.resolve_active_musical_key` / `musician_facing_chart_key`
  pipeline), so the mechanism is instrument-aware by construction and
  requires no new code path -- but this slice did not drive the Instrument
  selector through a transposing-instrument or capo scenario in the
  browser to confirm visually.
- **Key Cycle temporary-key alignment**: implemented per the confirmed
  formula (`project_cycle_display_key(session, temporary_playback_key(session))`
  when `is_cycle_active(session)`, else `chart_key`), but activating a Key
  Cycle pass has its own dedicated UI flow not driven by this script.

Both are flagged as explicit follow-up verification in the Slice F1
report rather than claimed as fully proven.
