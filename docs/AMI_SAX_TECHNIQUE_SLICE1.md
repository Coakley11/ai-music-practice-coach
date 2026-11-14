# AMI saxophone articulation and interval technique - Slice 1

Parent and verified remote Bass TAB integration:
`8a810b34491fed11d9b4526ebf1115a680c0f1cb`.
Local branch: `feature/ami-sax-technique-20261113`.
This milestone is local only. No saxophone push, merge into dev or deployment.
The separate TAB integration receipt enumerates the eight original deferred
cases; all eight actually passed on baseline and candidate. No paid API calls.

## Instrument authority and limits

Uses the existing `warmup_engine.Player`, `exercise_adapt.SPECS`, exact offsets
and `scale_pattern_harmony` playable limits. No profile range was expanded.
All four profiles use written Bb3-F6 (MIDI 58-89), treble clef.

| Saxophone | Written minus sounding | Sounding profile range | Written C5 sounds |
|---|---:|---|---|
| Soprano | 2 semitones | Ab3-Eb6 | Bb4 |
| Alto | 9 semitones | Db3-Ab5 | Eb4 |
| Tenor | 14 semitones | Ab2-Eb5 | Bb3 |
| Baritone | 21 semitones | Db2-Ab4 | Eb3 |

Level windows remain Beginner D4-G5 (62-79), Intermediate C4-C6 (60-84),
Advanced Bb3-F6 (58-89), clamped to the exact profile. Standalone middle/low/high
selection narrows these existing windows, never expands them. Delegated legacy
mixed routines retain the existing adaptive fitting policy and its disclosed
window; every pitch still stays within the independent hard Bb3-F6 profile. An Advanced
exercise uses faster/wider coordination without automatically selecting high
register. Existing high-register drills remain supported through their owner.
High F# is not established by these app profiles, even though particular horn
models have that key. No low-A baritone extension, altissimo, overtones,
multiphonics, alternate fingering or reed/tonguing audio model is introduced.

Primary context checked against Yamaha:
- [Family transposition](https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play003.html)
- [Saxophone tonguing](https://au.yamaha.com/en/education/greatstart/articles/ensemble-learning/saxophone-tonguing.html)
- [Written C#5/D5 octave boundary: first register](https://www.wfg.woodwind.org/sax/sax_bas_1.html) and [second register](https://www.wfg.woodwind.org/sax/sax_bas_2.html)
- [Model-specific high-F# key](https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/specs.html)

The app's more conservative verified profile remains authoritative; a model's
optional feature is not inferred for the selected generic saxophone.

## Actual musical recipes

- Repeated-note tonguing on a comfortable pitch, with ordinary detached attacks.
- Diatonic articulation scale fragments, with slur-two/tongue-two groups,
  slurred pairs, legato groups of four, ordinary tonguing or staccato.
- Accent on the first of each four-note group; accents and staccato can coexist.
- Diatonic thirds, fourths, fifths, sixths and octaves, in ascending,
  descending or alternating pair directions. Names describe diatonic steps;
  their semitone sizes vary within the major/natural-minor key. Octaves are 12.
- Beginner finger-coordination cells use moderate intervals; Intermediate adds
  octave coordination; Advanced uses wider scale-step pairs with sixteenths.
- Fixed written middle-register cells cross C#5/D5, including chromatic notes.
  They are labeled as register-boundary technique rather than a transposed
  key-scale or a chord-following line. No fingering numbers are prescribed.
- Chromatic neighboring-note coordination cells use real semitone changes.
- Rhythm-only difficulty uses a bar-safe eighth/sixteenth/sixteenth/quarter
  cycle, preserving every pitched note and articulation. Beginner mixed or
  sixteenth-note technique is refused. Whole/half/quarter/eighth/sixteenth
  values use the existing event writer; rests complete bars and mark breathing.

One exercise remains one stored drill. A minute-based warmup uses the existing
allocator, variant/related-key system, repetitions, rests and transitions.
The allocator receives one stream for the explicitly selected articulation,
so successive variants actually change musical material instead of reusing
variant zero from several unrelated legacy pattern labels. General interval
routines use their actual declared thirds/fourths/fifths, and row parameters
are checked against the notated interval.
Full-sized technique items have three practice passes with breath bars, so
longer routines can reach their requested length without inventing a timer.
Titles expose the actual written key where applicable. Plain existing
"two-note exercises" and explicitly mixed-family routines retain their established
adaptive owner, so a request for long tones/scales as well as articulation or
intervals never silently drops those families.

## Concrete staff example

Request: `Give me a beginner alto sax exercise in thirds.` Concert Practice Key C.
Written key A major, 56 BPM, quarter notes, then a whole-bar breath rest:

| Bar/beat | Written staff | Sounding pitch | Articulation |
|---|---|---|---|
| 1/1 | D4 | F3 | start two-note slur |
| 1/2 | F#4 | A3 | end slur |
| 1/3 | E4 | G3 | tongued |
| 1/4 | G#4 | B3 | tongued |
| 2/1 | F#4 | A3 | start two-note slur |
| 2/2 | A4 | C4 | end slur |
| 2/3 | G#4 | B3 | tongued |
| 2/4 | B4 | D4 | tongued |

The ABC body is `(D F) E G | (F A) G B | z4 |` under `K:A`, where the
key signature supplies F#, C# and G#. Accent revisions add valid `!>!`
decorations; staccato uses a dot before each affected note. These marks never
rewrite pitch or duration. Slur IDs are stored with the actual notes.

## Conversation, scope and history

Explicit saxophone/type, level, interval and articulation requests override
Practice Focus for that exercise. A general request uses the selected type and
focus: articulation, tone/register transitions, scales/intervals or technical
coordination. Harmony focus delegates to the existing active-chart engine.
The global instrument and selected saxophone type are never changed by an
exercise-specific override.

Supports harder/easier, slower/faster, interval changes, descending/ascending,
octave jumps, paired slurs, first-note accents, rhythm-only difficulty,
comfortable/lower register and adaptation to another verified saxophone.
An articulation-only or tempo-only revision retains pitches; rhythm-only retains
pitches and marks. Interval changes retain the same number of cells, rhythmic values and marks.
Register changes move the entire stored passage by a playable whole octave or
refuse without a new version; they retain count, timing and articulation.

Instrument adaptation projects the same sounding line through the target's
exact offset. If needed, only a whole-octave shift is allowed and reported.
A fixed C#5/D5 register-boundary cell is not transposed into a different written
boundary: it asks for a fresh drill for the other saxophone.
If no such fit exists in the target level/register, it refuses without changing
history. It never quietly replaces the requested line with another pattern.
Full routine/chart rhythm/register adaptation is deliberately refused here;
the established plan controls remain available for supported tempo, difficulty
and instrument operations. Technique-specific articulation revisions apply to
the whole routine; selected-item technical rewrites are not a new scope in this
slice. Existing plan navigation remains read-only.

Explain reads the stored recipe, notes and markings without adding a version.
Undo/Redo uses the exact existing owner-scoped snapshots for notes, timing,
marks and instrument projection. New account/workspace ownership clears active
context through the existing AMI owner machinery; no new global state is added.

## Song-aware authority

Guide-tone articulation uses the active chart's actual thirds/sevenths.
Chromatic song requests reuse the verified chart-based approach-note engine,
including its true target chord and harmonic beat; they are explicitly approach
lines, not an arbitrary chromatic scale relabeled as chord tones. Existing
song arpeggios remain owned by their established engine. Active section and
Practice Key come from the existing song setup; no second chord parser exists.

A new single song-aware technique request produces one chart pass. Timed
requests still use the adaptive allocator. Exact scale-interval patterns over
chords (for example fourths over the bridge) are not verified by the current
chart engine and are refused, preserving the previous passage and history.
Nonexistent section labels are not invented; the authoritative chart decides
which sections can be selected.

## Playback and explicit boundaries

These are notation and practice instructions, not a claim that playback
reproduces saxophone tonguing, breath/voicing or reed mechanics. No new audio
transport, cursor clock or independent timing engine is added. The existing
canonical durations, rests and event writer own time. Unsupported ties,
triplets, swing, exact endpoint instructions and specialized effects are refused
rather than approximated. Double/triple tonguing and extended techniques need
separate profiles, notation policies and musical verification.

## Validation receipt

Permanent tests: `tests/test_ami_sax_technique.py` (112 passing cases).
Independent concrete checks read actual ABC notes, onsets, rests and durations,
check hard-coded offsets/ranges and diatonic distances, fixed known notes,
actual chart harmony and articulation symbols, focus, routing, property-preserving
revisions and exact owner-scoped history. Sixty pair cases cover four saxophones,
three levels and five interval families. Routine tests require distinct actual
passages/titles and parameters that describe the notes actually played.

Python 3.12.8; exact clean dev baseline `8a810b34491fed11d9b4526ebf1115a680c0f1cb`:

| Run | Passed | Failed | Passing subtests |
|---|---:|---:|---:|
| Clean dev (63 relevant files) | 2495 | 6 | 2654 |
| Final saxophone candidate (64 relevant files) | 2607 | same 6 | 2654 |

All 2501 shared IDs have identical setup/call/teardown outcomes, no baseline IDs
are missing, and terminal failure/error/subtest ledgers match exactly. All 112
new IDs pass; no collection errors. No cases were deselected, including all eight
formerly deferred chord/approach matrices. This is a relevant regression suite,
not a claim of every test in the repository.

The six matching baseline failures are:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`

Earlier focused aggregates passed 693 checks and, after the final chart/owner
corrections, 384 saxophone/expression/song checks. Broad development runs caught
two routing regressions that were fixed before the final matched run: an existing
pentatonic expression line was intercepted by articulation keywords, and a song
section named A3 was misread as a pitch. Both exact legacy IDs now pass, with new
permanent boundary coverage. Unsupported interval/direction revisions over chart
harmony also refuse without changing notes, timing, marks or history.

Full native browser matrix: 24/24 completed, including alto and tenor, soprano
fourths, baritone sixths, slurs, staccato, accents, actual durations, revisions,
read-only Explain, exact Undo/Redo, distinct ten-minute routine passages and
Blue Bossa guide-tone harmony. Visual inspection confirmed readable staff,
slur curves and accents in the Advanced coordination example. The driver checks
native ABCJS pitch, duration, decoration and exact slur start/end positions;
labels or backend snapshots alone cannot pass.

That full matrix predates only the final routing/refusal guards; its technical
passages and notation code are unchanged. Final-source probe: 4/4 passed for alto generation, paired slurs, accents
and actual tenor guide tones over A3 of All the Things You Are. Native staff
pitch, duration, decorations and slur boundaries match the stored passage.
No failure or paid-API marker. Long charts retain the existing iframe scrolling;
this slice does not redesign shared notation layout. Mobile TAB acceptance is recorded separately in the
approved integration receipt (15 desktop and six mobile cases); this saxophone
matrix uses desktop browser layout and makes no new mobile redesign claim.

Final evidence under `D:/AMIWorktrees/flexible-evidence-20261112`:
`sax-clean-dev-baseline`, `sax-local-final`,
`sax-local-final-comparison.json`, `sax-browser-verified`,
`sax-local-final-browser`. Earlier failed/aborted development runs are preserved
and are not counted as completed final verification. Only owned process trees
and test servers were stopped. Available RAM/CPU/disk and Git object usage were
monitored; no unrelated process, file, worktree or backup was removed.
No paid Anthropic call, billing/dependency change, saxophone push, merge into dev
or deployment. Final local commit identity is supplied in the execution report.

## Recommended next milestone

Add selected-item technique revisions and a chart-constrained interval recipe
with independently verified harmonic semantics before widening the specialized
technique vocabulary. Add more authored rhythmic/interval permutations where
canonical notation supports them. Altissimo, overtone studies and alternate
fingerings should be separate later work: establish the player's actual horn
capabilities and authoritative technique-specific profiles first. They must not
be inferred from an Advanced level setting or a generic saxophone profile.
