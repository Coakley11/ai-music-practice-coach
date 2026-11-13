# Bass TAB integration receipt ? 13 November 2026

Approved feature: `18a6fda040985ff00c90eefed2ec7ce9904aea8b`.
Clean current dev baseline: `d258b3b27418e8d9d325789e4fcee07e8d4fda57`.
Merge candidate: `9f745f9b77bda2bcaaa6bc2b28d4b502f03750fe`.
No code conflict or newer remote commits at initial fetch. No production deployment.

## Exact comparison

Python 3.12.8, isolated data, paid Anthropic transport disabled. The clean
baseline at the exact current dev revision already records 2456 passed,
six failed, 2654 passing subtests. Candidate product tests: 2487 passed,
the same six failed, 2654 passing subtests, including all 31 TAB tests.
All 2462 shared product test IDs have unchanged outcomes, no missing IDs or
collection errors. External pytest root prefixes alone are normalized.
The six existing failures concern two Backing custom-progression contexts,
Backing refresh ownership, canonical insight metrics, Song Card guidance and
a Missions stub without `st.empty`; no new product failure/error IDs.
The candidate broad log additionally includes a supplemental harness with
89 passes/seven failures caused by its own incorrect comfort-window assertion.
That harness was revised: its next version needed optional-window handling.
Both attempts are preserved, not counted as product regressions or passes.
The corrected version passes 96/96 on baseline and candidate, using the
engine's disclosed chart window plus independent hard playable limits and
ABC harmony/timing verification. 2558 shared IDs including the original
supplemental harness have identical outcomes. No source fix was needed.

## Eight formerly deselected cases ? now actually run

File: `tests/test_ami_warmup_chordlines.py`.
Function: `test_every_note_of_every_arpeggio_and_approach_line_agrees_with_the_independent_oracle`.
Exact parameter IDs: `[flute]`, `[alto]`, `[tenor]`, `[soprano]`, `[baritone]`,
`[clarinet]`, `[trumpet]`, `[piano]`.

These overlap shared notation, instrument transposition and song-aware exercise
rendering, but do not exercise session ownership or the bass string model.
They independently read every ABC note at its harmonic beat across six songs,
14 sections, all three levels and every declared chord/approach variant:
322 passages per instrument, 2576 passages per run. All eight original cases
passed on the exact clean dev baseline (135.71 seconds) and merge candidate
(144.50 seconds). Their runs deselect the other 107 tests in that file because
those are already in the broad suite. No formerly deferred case is reported
as passed without execution. The supplemental 96 cases are additional coverage.

## Real application acceptance

Completed candidate runs: desktop 15/15; mobile 6/6 at 390?844.
The actual SVGs are checked for native staff pitch, selected fret/string,
rational onset/duration, rests/repeated notes, bars, G-D-A-E ordering,
collision-free paired systems and contained scrolling to the last event.
Covers all requested revisions, exact Undo/Redo, explicit string/position,
warmup navigation, Blue Bossa and Satin Doll split-bar changes. Existing
account/workspace isolation tests are in the matched suite. Mobile chart
selection temporarily uses the existing desktop catalog helper, then returns
to the phone viewport for notation checks; no mobile picker repair is claimed.

All evidence is preserved under `D:/AMIWorktrees/flexible-evidence-20261112`:
`tab-integration-final`, `tab-integration-comparison.json`,
`tab-integration-desktop`, `tab-integration-mobile`,
`tab-original-eight-baseline`, `tab-original-eight-candidate`,
`tab-matrix-v3-baseline`, `tab-matrix-v3-candidate`.
Own servers/process trees only are closed; unrelated files/worktrees remain.
No paid API invocation, force push or deployment. Final normal dev push and
remote SHA are verified separately in the execution receipt.
