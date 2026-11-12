# Flexible AMI continuation verification - November 12, 2026

Branch: `feature/ami-flexible-single-20261111`, isolated worktree `D:/AMIWorktrees/flexible-single-20261111`. Production integration checkpoint: `aba86683`; recovered Slice 2b commits: `e81676c0`, `ba9e8a80`, `5cc363fe`. Fetched origin/dev again before final reporting: `b25cafc1`. No push, merge or deployment.

## Preservation and integration

The complete initial nine-file task state and binary tracked diff were saved under `D:/AMIWorktrees/flexible-evidence-20261112/prechange` before checkpointing. Other worktrees and other sessions' untracked files were preserved. The old component prototype `scripts/ami_flexible_acceptance.py` remains untracked and is not used as real-app evidence. The task-generated runtime trace `scripts/evidence-creative-backing/pk-write.jsonl` is also excluded from commits.

This is production code. `pipeline.run_coach_submit` invokes `flexible_single.handle` before the existing warmup route. The actual Streamlit application uses this pipeline. Standalone plans use the existing account/workspace-scoped warmup store, Player profiles, pitch/ABC writer and verifier. No competing history or note engine was added.

Exact production files changed relative to dev:

- `music_coach_ami/flexible_single.py`: deterministic standalone request/revision adapter.
- `music_coach_ami/pipeline.py`: production routing and conversation recording.
- `music_coach_ami/exercise_context.py`: content-derived plan identity and active standalone context in submission signatures.
- `music_coach_ami/submit_diagnostics.py`: existing developer diagnostics expose standalone/history state.
- `music_coach_ami/warmup_engine.py`: existing verifier accepts the requested chord pitch-class set; recovered chart-family integration.
- `music_coach_ami/warmup_plan.py`: recovered song plans, canonical focus selection, standalone ownership guard, exact song-request transition and single-pass allocation/revisions.
- `music_coach_ami/warmup_song.py`: recovered Slice 2b chart/timeline support.
- `music_coach_ami/warmup_chordline.py`: recovered Slice 2b arpeggio/approach generation, reused without duplication.

## Real-app browser evidence

The Playwright driver starts a new loopback-only real Streamlit app, refuses an occupied port, verifies health and the exact address, and uses its own isolated headless Chrome. It does not attach to user browser sessions. The launcher blocks paid AMI transport, keeps isolated app data, and only observes pipeline/card state. It never seeds the chart or replaces a solver. Blue Bossa is loaded through the real Song Selection UI. The driver closes its own browser and server tree.

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112/`. Completed cases 01-10 are in `browser-final/results.json`; completed cases 11-15 plus a standalone transition precondition are in `browser-song-verified/results.json`. Together these cover all 15 numbered scenarios, not one uninterrupted run. Earlier failed attempts and their logs/screenshots are retained.

| Scenario | Observed result |
|---|---|
| Beginner flute A-major scale | Exactly MIDI 69,71,73,74,76,78,80,81; slow tempo; real staff |
| Descending, Undo, Redo | Reversed same notes; exact stored snapshots restored |
| Three flute long tones | One exercise with exactly three sustained notes and breath rests |
| Advanced Ab-major-seventh alto finger-buster | Concert PCs 8,0,3,7; sixteenths, changing permutations and octave-or-wider leap; plan Advanced while app remains Intermediate |
| Tenor override with alto selected | Written minus sounding =14 semitones; app selection unchanged |
| Standalone Explain | Correct written pitches; no plan or history mutation |
| High flute then lower | Actual written pitches at least MIDI84 then at most MIDI72, within the supported profiles |
| Alto / Intermediate / Blue Bossa mixed plan | Seven exercises using the selected actual chart; scale, guide-tone, arpeggio and approach families |
| Song Explain | Correct chord-tone/approach explanation after completed rerun; exact plan/history unchanged |
| Difficult Blue Bossa arpeggio | One Advanced chord-tone exercise, one chart pass, independent harmonic-timeline oracle passes with alto offset9 |
| Practice Focus | Actual UI Tone produces long-tones/scales; Articulation produces articulation/scales |

Every rendered score was observed through the actual ABCJS render return and SVG. The driver compares score/input ABC and drawn note counts with independent parsing, and written-note staff positions with scientific octaves where available. A post-run check also confirmed actual drawn note-head positions equal the parsed staff positions for all captured notes. Screenshots and panel text accompany the JSON. Large multi-score screenshots can be clipped by the scrolling layout; DOM/card and rendered-score records are the stronger evidence for those cases. Audio playback was not auditioned.

## Stale Explain diagnosis and narrow corrections

The exact normal-app Explain case records the preceding mixed-plan card immediately after clicking (`EXPLAIN_IMMEDIATE_PREVIOUS_CARD=True`). After the completed Streamlit rerun it records the matching Explain question and proper explanation of chord tones and chromatic approaches, with unchanged plan/history. `cards.jsonl` independently records stage/render events. The historical stale Explain observation is reproduced as a transient unfinished-rerun observation and resolved by waiting for the matching completed request/card. No claim is made that every possible stale-card path was disproved. The earlier content-derived fingerprint correction remains a separate preventive identity fix.

A real product routing issue was also discovered: after a standalone exercise, "Warm me up for soloing over Blue Bossa" fell through because the new-plan guard did not accept that wording. The guard now starts the existing song plan, with permanent regression coverage and a passing browser transition. The exact plain song arpeggio request also needed a narrow route into Slice 2b; it now plays one selected chart timeline rather than inventing harmony or allocating ten minutes.

Two browser-driver defects were fixed separately: selecting an already-selected option does not produce a rerun, and the independent pitch-count helper must strip quoted chord labels before reading slurred notes. Their failed attempts are retained and not counted as passed acceptance.

## Python parity and regressions

The isolated runtime is exactly Python 3.12.8 at `D:/AMIWorktrees/ami-python3128/venv/Scripts/python.exe`, installed from the official Python package into a task-specific directory. Repository `requirements.txt`, pytest and Playwright were installed into that venv. Baseline and candidate use the same executable, dependency versions and deterministic environment gates, with isolated app-data directories. Global Python/PATH/registry were unchanged. `pip check` passed. See `python3128-freeze.txt` and dependency installation evidence.

The clean baseline passed 1,014 tests plus 31 subtests in the core relevant group. Its additional conversation/isolation/UI group passed 123 tests plus 22 subtests and failed one existing test. The final candidate passed **1,293 tests plus 53 subtests**, with the same one failure, in 474.05 seconds.

Exact-ID comparison (`final-candidate-comparison.json`): **1,136 shared IDs, zero changed outcomes, zero introduced failing IDs**, same Python executable. The existing failure is `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`, asserting missing `ami_insight` metadata (`None` versus `abc123`). It fails on clean dev and candidate and was not changed as part of this bounded exercise slice.

There are two baseline-only IDs, both former guide-tone-only expectations in `test_ami_warmup_songs.py`; recovered Slice 2b replaces them with one mixed-plan expectation. The other candidate-only tests are 115 Slice 2b chordline tests and 42 permanent flexible-exercise tests. **All 115 Slice 2b tests and all 42 flexible-exercise tests pass**, including the independent eight-instrument/song/level/variant oracle matrix, negative musical mutations, arpeggios, approaches, guide-tone/mixed plans, whole forms, revisions and history. Every shared core regression also passes.

Baseline collection differences:

- Baseline only: `tests/test_ami_warmup_songs.py::TestCreate::test_the_requests_in_the_brief_build_a_guide_tone_warmup[Warm me up for soloing over Blue Bossa.]`
- Baseline only: `tests/test_ami_warmup_songs.py::TestCreate::test_warm_me_up_for_soloing_over_the_active_song`
- Candidate replacement: `tests/test_ami_warmup_songs.py::TestCreate::test_warm_me_up_for_soloing_over_the_active_song_is_a_mixed_plan`

Final test file paths are saved in `final-test-files.json`; per-ID setup/call/teardown outcomes and errors are in `baseline.json`, `baseline-extra.json` and `final-candidate.json`. Heavy runs were sequential; resource usage was monitored and no unrelated process was stopped. The browser processes were closed before the final regression run.

## Musical boundaries and next slice

The [profile audit](ami-flexible-single-20261111.md) records exact written ranges and sounding offsets: flute0; soprano2; alto9; tenor14; baritone21; Bb clarinet2; Bb trumpet2; piano0. Standalone level/register windows never expand to fit a requested key; an unplayable complete octave is refused. Independent tests check pitch classes, scientific octaves, ABC accidentals, transposition, rhythm-only preservation, complete history restoration, and account/workspace ownership changes. Account/workspace isolation is covered by automated state/lifecycle tests, not a live multi-account cloud login test.

Advanced permutations are playable within the modeled conservative range, not a claim of alternate fingerings, altissimo, teacher-reviewed instrument-specific coordination, or universally suitable tempo. Bass generation, clarinet break/twelfth patterns, trumpet valve/partial lip slurs, detailed fingerings, slurs/dynamics and richer rhythms remain unsupported. Named-song exercises require the actual loaded chart. Full warmups retain their existing fit-window policy, distinct from strict standalone level windows.

The [next instrument-technique proposal](ami-instrument-technique-next-slice.md) separates profile reconciliation, flute tone/register work, ordinary clarinet octaves and reviewed break patterns, verified trumpet harmonic-partial tables, missing bass profile/string-fret realization, and reviewed saxophone coordination/articulation. None of those larger generators is claimed as implemented here.
