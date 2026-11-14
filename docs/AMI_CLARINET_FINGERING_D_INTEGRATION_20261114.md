# Clarinet Stage D current-dev integration receipt

Accepted feature: `c05621d16e5c085638028a811461ea1d72181750`.
Fresh current dev: `f3d33016b262715a510ebf6c69f5a15201e91f5b`.
Clean merge candidate: `38294198e0d5196913e1f21f2070ce6a16f66601`.
Branch: `integration/ami-clarinet-fingering-d-20261114`.

The merge has no conflicts. All 26 accepted feature file blobs are identical;
all 16 files changed by the four newer dev commits are preserved exactly.
No existing worktree or other agent's changes were replaced.

## Matched regression

Python exactly 3.12.8. Tests/browsers run sequentially. The previous 96-file
integrated trumpet manifest is retained and adds the newer Tone Sustain test
module: 97 baseline files. The integration adds the permanent clarinet module:
98 files. Fresh baseline: **3,681 passed, nine failed, 3,116 passing subtests**,
13 warnings, 950.63 seconds. Candidate: **3,764 passed, the same nine failed,
3,116 passing subtests**, 13 warnings, 897.13 seconds.

Strict comparison: **3,690 shared IDs unchanged**, **83 new cases passed**;
no missing IDs, changed phase outcomes or collection errors; exact terminal
failure ledger and Python executable match. All 101 frozen validation-source
hashes remain unchanged.

## Why nine baseline failures rather than the earlier six

The Stage C current-dev comparison expanded the prior 72-file test scope by
23 new/changed dev modules. The three additional reported failures were already
present on clean `4301efe1`, before applying trumpet Stage C or clarinet Stage D:

- `tests/test_composition_activation_nav.py::TestNavButtonKeys::test_jam_sets_entry_mode`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_armed_renders_exactly_one_synced_score`
- `tests/test_cs_fa_phrase_editor_single_score.py::TestPhraseEditorSingleScore::test_unarmed_renders_exactly_one_static_score`

The Jam source assertion expects the old `Style Jam Mode` assignment. The test
was introduced in `c5809ca0`; blame attributes the button's current
`request_song_aware_coaching` call to `5bd8d47c6`. This is an existing stale
source assertion, not a fingering change.

Both phrase-editor failures are `FileNotFoundError`: the installed Streamlit
AppTest resolves `tests/_cs_fa_editor_harness.py` relative to the test module's
`tests` directory, producing `tests/tests/_cs_fa_editor_harness.py`. That relative
path was introduced in `4b27847a6`. These are existing harness-path failures;
no actual phrase-editor score result is inferred from them. The fresh baseline
and candidate reproduce all three, alongside the prior six. Unrelated
Composition source/tests are unchanged by this integration.

The complete nine-ID ledger and phase comparison are in
`D:/AMIWorktrees/flexible-evidence-20261112/clarinet-d-current-comparison.json`;
source history evidence is `clarinet-d-baseline-failure-provenance.json`.

## Merged-app browser

**Passed, exit 0: 50 requests and 30 visual scenarios**, desktop and 390 pixels.
All seven source-supported records, actual staff/accidentals, thumb/main-hole,
register/little-finger states, all three twelfths, separate break, practical
questions, model/octave clarification, bounded handoffs/revisions, read-only
explanations and exact Undo/Redo passed. Existing SAX/trumpet/ordinary clarinet,
keyed scale/arpeggio and bass/TAB owners passed. Permanent matched tests cover
account/workspace isolation. No forbidden Anthropic API call was recorded.

The first launch safely refused occupied port 8602. The next run passed most
scenarios but its browser unexpectedly closed during a late model follow-up;
that incomplete run is retained and is not counted as acceptance. With source
unchanged and RAM recovered, a complete fresh retry passed all scenarios.
Final evidence: `clarinet-d-integrated-browser-retry/` and sibling log.

Both gates passed. A normal ancestry-safe push is authorized, conditional on
remote dev still matching the validated baseline. No force push or deployment.

## Bounds and safety

The accepted seven-note YCL-255 Boehm pilot is unchanged: separate thumb hole
and register key, chosen basic little-finger actions, written/concert major-second
transposition, three 19-semitone twelfths and a distinct one-semitone Bb4-B4
break. Original diagrams, native staff, bounded exercise handoffs, read-only
explanations, exact Undo/Redo and account/workspace isolation are retained.
No altissimo, unsupported models/systems, alternates or detailed physical method
was added. No paid Anthropic call, billing change, force push or deployment.

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112`:
`clarinet-d-current-baseline.{json,log}`, `clarinet-d-current-candidate.{json,log}`,
`clarinet-d-current-comparison.json`, `clarinet-d-integration-source-freeze.json`,
`clarinet-d-integrated-browser-final/` and its sibling log.
