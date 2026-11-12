# Local flute and clarinet technique milestone

## Integration completed first

Remote dev was initially b25cafc1, then advanced during verification to c35e14c1 with Issue 69 karaoke/transposition work. The pre-push guard stopped before any write. A clean merge preserved both histories as **f40f28390dbfb90c872a9e2232ecb202726d4eda**. A normal push advanced origin/dev from c35e14c1 to f40f2839; fetch and ls-remote independently verified that exact SHA. No force push or deployment occurred.

Current-dev integration verification: baseline 1,767 passed, 4 failed, 289 subtests; integrated candidate 1,915 passed, the same 4 failed, 289 subtests. Exact comparison: 1,769 shared IDs, zero changed outcomes, two obsolete guide-tone-only IDs replaced by Slice 2b's mixed-plan expectation. Incoming Issue 69 key/karaoke tests, billing entitlements, Backing, Composition, Practice Key, Key Cycling, M1b/M1c/M1d, notation, warmups and scope contracts were included or retained from the preceding matched safety checks. The unchanged full eight-instrument Slice 2b oracle matrix had already passed; its eight expensive matrix cases were deselected in the final combination run, while all other chordline tests ran. All 15 real-app scenarios then passed on the combined application. No new regression was found.

The four reproducible current-dev failures remain:

- tests/test_backing_context.py::TestBackingContext::test_custom_progression_context
- tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam
- tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog
- tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present

Evidence: D:/AMIWorktrees/flexible-evidence-20261112/current-integration-comparison.json, current-baseline.json, current-candidate.json and current-integration-smoke/results.json. Earlier b25cafc1 checks and failures are retained separately. No untracked prototype or task-generated runtime trace entered dev.

## Local implementation and profile audit

This milestone starts from verified dev f40f2839 on **feature/ami-flute-clarinet-20261112**, in D:/AMIWorktrees/flute-clarinet-20261112. It is authorized for a local commit only.

Previously supported: strict-register standalone scales/arpeggios/long tones, flute high/low requests, Advanced permutations, full tone warmups and Beginner clarinet warmups. Previously missing: explicit octave endpoints, clarinet break versus twelfth drills, instrument-specific coordination recipes and their natural-language refinements. Existing full-warmup generation remains unchanged.

No new competing range or transposition table was added. Existing exercise_adapt, scale_pattern_harmony, notation profiles and warmup_engine.Player remain authoritative. Exact written-minus-sounding offset: flute 0, standard Bb clarinet 2 semitones. Overall written ranges are flute MIDI60-96 and clarinet52-96. Strict modeled level windows are:

| Instrument | Beginner | Intermediate | Advanced |
|---|---|---|---|
| Flute | 67-84 | 62-91 | 60-96 |
| Bb clarinet | 55-76 | 52-86 | 52-91 |

These are application comfort policies, not universal physical or pedagogical limits. The new patterns never widen them. Deliberately requested Advanced work uses Advanced windows without changing the sidebar's level.

instrument_technique.py provides small written-pitch recipes; flexible_single.py delegates to it and shares a single package/render/verify/history path. The existing pipeline, account/workspace scope, ABC writer, accidental/octave conventions and exact snapshots are retained. Song/span and explicit scale-pattern requests retain their existing owners. No model call or alternative fingering engine was added.

## Actual bounded exercises

| Request/type | Actual musical behavior |
|---|---|
| High-register flute | Existing profile-based short high-register drill; upper range depends on the selected level |
| Three low-register long tones | Exactly three distinct sustained pitches within the level's lower window, with breath rests; count parsing now allows the register phrase |
| Flute low D to high D octave jumps | Written/concert D4-D5, MIDI62-74, disclosed octave endpoints; repeated pairs, full-bar breath rest |
| Difficult flute fingering exercise | Original short coordination cells alternate lower/upper octave notes and neighboring chromatic changes; Advanced sixteenths, conservative initial tempo, rests; no alternate fingerings prescribed |
| Intermediate flute tone warmup | Existing full long-tone/scale warmup with explicit Intermediate level |
| Clarinet F-to-F octave exercise | Written F4-F5, MIDI65-77; sounding Eb4-Eb5, MIDI63-75; 12-semitone octave, not a twelfth |
| Clarinet register break | Written A4-Bb4-B4-C5 cells around the actual Bb4-B4 boundary; higher/lower changes neighboring notes while preserving that boundary |
| Challenging clarinet fingering | Original grouped throat-to-clarion coordination patterns across the boundary; Advanced sixteenths, with breath rest |
| Clarinet twelfths | Default written G3-D5, MIDI55-74; sounding F3-C5, MIDI53-72; exactly 19 semitones |
| Beginner clarinet warmup | Existing full warmup route and Beginner profile; generic new octave drill defaults to G3-G4 so it fits the modeled Beginner window |

For these fixed-pitch technical drills, note names are explicitly **written pitches**, unlike named concert keys in ordinary key-based exercises. The Practice Key and all unrelated settings remain untouched. Notation still uses its resolved written key signature and writes necessary accidentals for the exact requested notes. F4-F5 is refused at Beginner because no such octave fits MIDI55-76; it is not silently moved or widened.

## Refinement contract

Supported refinements include higher/lower, slower/faster or numeric BPM, ascending/descending, wider intervals, fewer complete cells, harder/easier, ordinary articulation, note values and repetition counts. Rhythm/articulation-only edits preserve the exact written and sounding note order. Higher/lower on a clarinet break pattern moves its neighboring material rather than falsely relocating the break. Wider flute octaves become explicitly named two-octave jumps; wider clarinet octaves become explicitly named perfect twelfths. Out-of-range or unverified changes preserve the complete stored plan and history.

Explain describes the actual skill and written notes and creates no version. Undo/Redo restore full stored snapshots, including staff, tempo, articulation and technical metadata. Explicit instrument and level requests override the sidebar; otherwise the selected instrument, proficiency and canonical Practice Focus are resolved through the existing context. Explicit articulation overrides Articulation focus. Technical interval/coordination requests take precedence over generic focus family selection.

## Independent musical references

- [Yamaha flute fingering guide](https://www.yamaha.com/en/musical_instrument_guide/flute/play/play002.html): standard written notes and octave-specific fingering charts; no diagram or alternate fingering is copied/generated here.
- [Yamaha clarinet acoustics](https://www.yamaha.com/en/musical_instrument_guide/clarinet/mechanism/mechanism006.html): lower C to upper G illustrates the clarinet's twelfth relationship, rather than an octave.
- [Freund and Cutler, The Clarinet Family](https://timbreandorchestration.org/isfee/extreme-orchestration/woodwinds/clarinet-family): standard Bb clarinet register relationships and the written Bb4-B4 break. Patterns here are original short exercises derived from those facts, not transcriptions of an exercise book.

## Verification

Python is exactly 3.12.8 in the same isolated venv used for integration; declared requirements and dependency versions are unchanged. The clean-dev reference is the exact f40f2839 candidate run that was verified and then pushed to dev (`current-candidate.json`).

The broader local technique run passed **1,940 tests plus 289 subtests**, with the same four baseline failures. Comparison against clean dev: **1,917 shared IDs, zero changed outcomes, zero introduced failing IDs**. The only baseline-only cases are the old blanket refusals for clarinet octaves and clarinet break exercises; the new musical tests replace those expectations. The eight unchanged expensive song-oracle matrix cases were deselected, with their prior passing evidence retained. See `technique-candidate.json` and `technique-comparison.json`.

Final narrow validation then strengthened interval metadata/endpoints, meaningful tempo changes on harder tone-focused octaves, lowercase pitch parsing, malformed endpoint refusal and initial descending requests. The final focused run passed **77 tests** (37 new instrument-technique cases and 40 retained flexible-exercise cases) in 5.76 seconds. These checks cover every subsequently changed technique path; the broader run above precedes those narrow final safeguards and is not presented as a second monolithic run of the final source. See `technique-final-focused-v2.json`.

Actual real-app browser acceptance passed **26/26 scenarios**: 23 exercise/revision/focus/override/warmup cases in `technique-browser/results.json`, then three final parser cases in `technique-parser-browser/results.json`. These use new verified loopback servers and their own headless Chrome sessions, the real app, isolated data and a paid-transport blocker. No UI state was seeded and no note solver replaced. They cover all nine user-supplied flute/clarinet examples, higher/slower/descending/wider/fewer/harder/articulation, read-only Explain, exact Undo/Redo, explicit clarinet override while flute remains selected, and actual written/sounding offsets. Lowercase G-to-G produced written G4-G5 rather than a default F pair; malformed F-to-H preserved the preceding complete plan and history.

Each actual ABCJS score was checked against independent ABC reading and stored scientific written octaves; post-run checks additionally verified all observed drawn note-head positions. Flute coordination and clarinet F4-F5 screenshots were visually inspected. Scope tests independently switch account and workspace ownership and verify that the previous technical plan/explanation cannot leak. Screenshots, panel text, backend records, stage/render journals and server identities are retained beneath D:/AMIWorktrees/flexible-evidence-20261112.

All heavy jobs were sequential, RAM/CPU/disk were monitored, and only this session's browser/server processes were closed. No paid transport invocation occurred. No unrelated worktree, untracked file, backup or Cursor database was changed. The local technique slice has not been pushed, merged or deployed.

## Remaining limits and subsequent instruments

No alternate fingering charts, finger numbers, altissimo, embouchure diagnosis, slur/dynamics model, triplets/swing or duration-driven standalone technique is claimed. Fixed-pitch requests with unverified instructions are refused. A valid modeled pitch/rhythm pattern is not a substitute for individual teacher assessment; audio playback has not been auditioned. Account/workspace tests exercise real production state ownership, not a live cloud multi-account login.

Trumpet still needs reviewed fixed-valve harmonic-partial tables before open-valve lip slurs. Bass needs the missing exact range/tuning/octave profile and feasible string/fret positions. Saxophones retain their separate exact offsets and current Advanced finger-busters; instrument-reviewed articulation/register transitions and alternate-fingering/altissimo support remain separate work. See ami-instrument-technique-next-slice.md. None of those larger generators was implemented in this local milestone.
