# AMI flexible standalone exercises - bounded vertical slice

Base: fetched `origin/dev` at `b25cafc1` on November 11, 2026. Development branch: `feature/ami-flexible-single-20261111`; worktree: `D:/AMIWorktrees/flexible-single-20261111`.

## Recovery

Claude's `6127f304` worktree still exists. Its only tracked feature changes beyond dev are the three Slice 2b commits `adf67c66`, `032e8d17`, `2b053a7a`; the final commit merges newer dev. Those three feature commits applied cleanly to current dev as `e81676c0`, `ba9e8a80`, `5cc363fe`. Current dev did not contain Slice 2b. Existing source worktrees, untracked evidence and unrelated changes were preserved.

Read the Slice 1/2a/2b implementation, Slice 2 proposal and existing oracle, conversational and navigation tests. Slice 2b provides chart-timed arpeggios, approach notes, whole forms, mixed plans, start-tone/approach/level revisions, exact history, explanations and unsupported-chord rests. The unverified historical browser observation concerned Alto / Intermediate / Blue Bossa Explain. Verification results are recorded below after execution.

Parallel M1c/M1d scale-pattern worktrees and Key Cycling/notation worktrees were inventoried. This change does not edit their engines, UI, TAB or Key Cycling code.

## Implementation

`flexible_single` is a small deterministic request adapter before the warmup router. It reuses the existing Player, chord-tone reader, scale spelling, Note/Built model, ABC writer, verifier, account/workspace scope and warmup history. It makes no model/API call. A single request has one exercise and one play by default; no routine time budget or allocation. A full warmup continues through Adaptive Warmups.

Supported standalone vocabulary: major and natural-minor scales; a specified number (1-12 where register allows) of long tones; major/minor triad, major-seventh, dominant-seventh and minor-seventh arpeggios; Advanced finger-buster permutations. Keys are concert keys, disclosed alongside the written key. Directions, low/middle/high registers, tempo, repetition count, ordinary note values and staccato/tenuto/accent controls are supported within the bounded grammar. Unsupported vocabulary/techniques receive a refusal instead of substitute music.

A finger-buster uses sixteenths, alternating extremes, octave-or-wider leaps where the profile permits, and changing arpeggio/scale permutations. It is not an ordinary ascending scale with an Advanced label. It does not claim instrument-specific alternate fingerings.

Revisions reuse the same scoped version store: descending/ascending, slower/faster or numeric tempo, register, increased level, rhythm-only difficulty, instrument adaptation, repetitions and basic articulations. Explain reads the stored pitches without a new version. Undo/redo restore complete stored plans, including notation. Unsupported revisions preserve the current plan.

Full warmups use canonical Practice Focus categories: Tone selects long tones/scales; Technique selects scales/intervals/articulation; Articulation selects articulation/scales; Melody selects scales/intervals; Harmony selects chart-derived guide tones/arpeggios and requests an active chart if unavailable. Explicit family requests take priority.

The submit authority signature now includes the content-derived plan ID. Version count/cursor alone can collide between fresh plans. This closes a stale-card identity risk; it does not by itself prove the cause of the historical browser observation.

## Profile audit and range policy

No competing profile table was added. Existing `exercise_adapt.SPECS`, `scale_pattern_harmony` exact offsets/overall ranges, `written_music_context`, `notation_profile` and `warmup_engine.Player.window` remain authoritative. Offsets are written minus sounding, including octave.

| Instrument | Written overall MIDI range | Offset |
|---|---:|---:|
| Flute | 60-96 | 0 |
| Piano | 21-108 | 0 |
| Soprano sax | 58-89 | 2 |
| Alto sax | 58-89 | 9 |
| Tenor sax | 58-89 | 14 |
| Baritone sax | 58-89 | 21 |
| Bb clarinet | 52-96 | 2 |
| Bb trumpet | 54-84 | 2 |

Standalone drills intersect the existing level window with a low/high octave or middle window. They never widen a Beginner window to make a key fit. If a complete tonic-to-tonic octave cannot fit, they refuse and ask for a different key/register. Existing full-warmup fit-window expansion is unchanged and remains a separate policy review item. The range table is a conservative existing application policy, not a claim of every player's absolute physical limits (for example baritone low-A extensions are not modeled).

Independent tests use fixed concert pitch-class sets, exact 9/14-semitone sax expectations and an ABC tokenizer with standard scientific octaves. They compare actual stored pitches and notation, rather than accepting the generator's own validation flags. The shared verifier additionally checks durations, notation, range and sounding pitch classes. Arpeggios supply their chord pitch-class set to the same verifier; dominant sevenths are not incorrectly checked as major scales.

Musical reference checks: Yamaha explains sax transposition and its official digital sax manual explicitly lists tenor -14 and alto -9: https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play003.html and https://europe.yamaha.com/en/download/files/2165802/ . Texas A&M's open theory text documents flute range, alto sixths and tenor ninths: https://odp.library.tamu.edu/stepstomusictheory/chapter/transposing-instruments/ . Yamaha's trumpet guide confirms that fixed tube length gives a harmonic ladder, not arbitrary intervals: https://www.yamaha.com/en/musical_instrument_guide/trumpet/mechanism/mechanism002.html . No new trumpet partial generator is claimed.

## Deliberate next-stage gaps

Bass has a notation profile, but no verified exercise-adaptation spec, full exact-offset/range entry or string/fret realization; bass requests are refused here. Clarinet register-break/twelfth drills and ordinary octave-specific requests, trumpet valve/partial/lip-slur patterns, alternate fingerings, mixed/swing/triplet rhythms, slur/dynamics instructions and duration-driven standalone exercises need separately reviewed implementations. General full-warmup register overrides are explicitly declined. Wider intervals/start-on-third/chromatic approaches remain supported where the existing song engine supports them; they are not newly claimed for standalone drills.

Song-specific requests continue to the existing authoritative chart engines. This slice does not add named-song resolution, invent verse/bridge sections, or claim arbitrary standalone chord-to-song adaptation. Recommended next stage: consolidate the standalone adapter with existing scale/arpeggio request models, extend validated revisions, then add clarinet break and verified trumpet partial patterns as separate instrument slices; bass requires its missing authoritative profile and string/fret layer first.

## Verification record

Pending final test and browser results. No push, merge into dev or deployment is authorized or performed.

Checkpoint on November 12, 2026: the production pipeline and permanent tests passed 254 focused tests under isolated Python 3.12.8 with the declared dependencies (Streamlit 1.61.0). Real-app browser and matched baseline verification continue before final sign-off. Generic instrument/register requests now use a short five-note drill rather than requiring a full octave.
