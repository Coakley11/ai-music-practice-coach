# Saxophone conversational exercises: local Slice 2

Slice 1 was integrated normally into dev and verified remotely at
`b8704315d4a64a522e16d25762c0937848d7db6d` on 2026-11-13. Its clean integration
matched 2,501 shared test IDs, added 112 passing IDs, retained the same six
baseline failures and passed a four-scenario native-notation browser probe.
See `AMI_SAX_SLICE1_INTEGRATION_20261113.md` for the integration receipt.

This milestone is on local branch `feature/ami-sax-conversation-20261113`, in
`D:/AMIWorktrees/sax-conversation-20261113`. It must not be pushed, merged or
deployed without another approval. The final local commit is reported separately.

## Selected items

A ten-minute advanced alto saxophone technique warmup contains distinct thirds,
fifths, sixths and octave drills. Item numbers accept digits, ordinals, cardinal
words after exercise/item, and last. Exact titles and existing family names work
when unique. A uniquely named old interval can target a change such as fourths
to thirds. This exercise/it can refer to the selected navigation view or last
edited item. Ambiguous family names, absent targets and conflicting numbers ask
for clarification without mutating notes or history.

Supported edits include interval/direction, harder/easier, paired slurs,
staccato, accents, slower/faster, a different bar-safe rhythm with the same
pitches, lower register by a fitting whole-octave shift, and another verified
saxophone. An advanced harder request uses wide coordination intervals and
alternating directions rather than raising the instrument's pitch ceiling.

Only the selected row is rebuilt. Every other row is copied exactly, including
its complete notation, notes, durations, articulation, instrument, tempo and
repetitions. Selected-item repetitions also remain unchanged; the actual total
warmup duration can consequently differ from its original requested target.
The response reports that total. Per-item instrument and level settings are
visible, including a tenor item inside an alto plan.

Each row stores its canonical note events, item options and instrument. Existing
render/range checks run again before an edit is committed. The existing
owner-scoped plan history stores the complete version; Undo/Redo restores exact
plans. Explain reads actual stored notes/settings/harmony and creates no version.
An explicit whole-routine articulation change remains available before custom
item edits. An unqualified ambiguous edit no longer changes every exercise.

## Chart-constrained intervals

The production implementation calls `warmup_song.build_timeline` and
`warmup_chordline.tones_of`, using the authoritative stored chart and its Practice
Key. It adds no chord parser. Split-measure timing comes from the same timeline.

The new recipe builds chord-tone interval PAIRS. Each pair has both the requested
spelled letter distance and conventional semitone size: major/minor thirds and
sixths, perfect fourths/fifths, or octaves. Ascending, descending and alternating
directions are supported. Connections BETWEEN pairs follow the changing harmony
and need not retain the pair interval; the instructions say so. Scale-based
technique remains a separate recipe and is never relabeled chord-following.

Advanced chart cells use sixteenth notes at a bounded practice tempo, wide
intervals and rapid directional changes when requested. Candidate pairs vary
while choosing a near starting point from the previous endpoint. Existing
canonical arpeggio-permutation exercises retain their own owner and behavior.

The chromatic option plays an interval pair followed by a non-chord semitone
neighbour resolving to the first chord tone of that cell. These are explicitly
WITHIN-CHORD approaches, not anticipations of the next harmony. Named extensions
such as a ninth are excluded from the non-chord neighbour choices. Every actual
note is verified at its beat, no note crosses a harmonic boundary, and the
passage fills the selected chart exactly. An unavailable chord/interval refuses
the complete request without changing an existing exercise or history.

The complete Blue Bossa Section A contains G7#5; its available chord tones do
not form perfect fourths. The All the Things You Are bridge has the same limit
on C7#5. Those requests refuse honestly. Explicitly requesting the first four
Blue Bossa bars permits a fourths exercise. Thirds over the All the Things bridge
and sixths over its supported sections are available. Diminished harmony remains
unsupported by the existing authoritative reader; no chord model is invented.

## Profiles and scope

All four saxophones retain the verified written Bb3-F6 hard range and treble
notation. Written-minus-sounding offsets are soprano 2, alto 9, tenor 14 and
baritone 21 semitones, including octaves. Existing level windows are Beginner
D4-G5, Intermediate C4-C6 and Advanced Bb3-F6. Ordinary key drills use narrowed
register windows. Exact sounding adaptation may use the target's complete
verified level window, or an explicitly reported whole-octave displacement;
unavailable passages refuse. Fixed written register-transition cells cannot be
relabelled by adapting them to a different saxophone.

No altissimo, high-F-sharp expansion, alternate fingerings, overtone recipes,
new transport, paid API, dependency or billing changes. No mobile layout redesign
is claimed. Long scores retain the existing notation iframe scrolling.

## Bounded limitations and next work

- Mixed-duration pitch-preserving chart displacement is refused. Generate a
  supported chart cell instead; a rhythm edit never silently moves notes to a
  different chord.
- After individual custom settings, whole-plan musical rewrites are refused;
  name an item. Existing items predating note snapshots require a fresh warmup.
- Approaches resolve locally inside their chord. Next-change interval/approach
  permutations and more authored rhythmic cells are separate future work.
- A register move preserves the same line through whole octaves and refuses if
  it cannot fit; it does not substitute notes to manufacture a lower version.
- Establish authoritative technique-specific, horn-specific profiles and source
  provenance before specialized altissimo preparation, overtone studies or
  alternate fingerings. Build capability/refusal and notation tests first;
  Advanced alone never authorizes those techniques. A nearer bounded follow-up
  is more independently verified chart rhythmic/interval permutations and
  sustained-turn navigation for mixed-instrument routines.

## Verification receipt

The receipts below distinguish the full regression run from final-source display
follow-up checks. Development failures and the deliberately stopped
`sax2-regression` run are preserved and are not counted as final verification.

### Musical examples from actual rendered cards

These are excerpts, all at 80 BPM. Each note below lasts one sixteenth note
(0.25 quarter-note beats); positions are human beat numbers. Full ABC, native SVG
pitch/duration/articulation observations and screenshots are in browser evidence.

| Chart / player | Bar / beats | Concert chord / written symbol | Written notes | Sounding notes |
| --- | --- | --- | --- | --- |
| Blue Bossa / alto fourths, explicitly bars 1-4 | 1 / 1, 1.25, 1.5, 1.75 | Cm9 / Am9 | E5 A5, G4 C5 | G4 C5, Bb3 Eb4 |
| Blue Bossa / alto sixth plus local approach | 1 / 1, 1.25, 1.5, 1.75 | Cm9 / Am9 | C5 A5, Db5 C5 | Eb4 C5, E4 Eb4 |
| All the Things You Are bridge / tenor thirds | 1 / 1, 1.25, 1.5, 1.75 | Am7 / Bm7 | D5 F#5, F#5 A5 | C4 E4, E4 G4 |
| Satin Doll / soprano fourths | 1 / 1, 1.25 | Dm7 / Em7 | D5 G5 | C5 F5 |
| Satin Doll / soprano, split-measure change | 1 / 3, 3.25 | G7 / A7 | E5 A5 | D5 G5 |
| Autumn Leaves / baritone sixth plus local approach | 1 / 1, 1.25, 1.5, 1.75 | Em9 / C#m9 | B4 G#5, A#4 B4 | D3 B3, C#3 D3 |

The Db5-C5 and A#4-B4 figures are explicitly chromatic resolutions, not chord-tone
interval pairs. The first two notes of those cells are the sixths. At beat 3 in
Satin Doll, verification uses G7, not the Dm7 from the first half of the bar.

### Regression and independent checks

Python: 3.12.8, isolated offline data. Full 65-file regression:
**2,791 passed, six known failures, 2,654 passing subtests**, no deselections or
collection errors. Against the clean integrated-dev source at b8704315:
**2,613 shared IDs unchanged**, no missing IDs, **184 new passing IDs**, and exact
failure/error/subtest ledger equality. All eight exhaustive instrument/chart
matrix cases ran and passed. Evidence: `sax2-final-regression.{json,log}` and
`sax2-final-comparison.json` under D:/AMIWorktrees/flexible-evidence-20261112.

The six unchanged failures are:

- tests/test_backing_context.py::TestBackingContext::test_custom_progression_context
- tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam
- tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog
- tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present
- tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows
- tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander

After that full run, visual review led to a display-only correction: adapted
notation titles now name the actual target written key and avoid duplicated
Saxophone prefixes. No generated pitch, timing, range or owner logic changed.
Final-source focused validation: **382 passed**, including all **187 new tests**,
all 112 Slice 1 tests and existing flexible/expression boundary tests. Three new
cases check tenor, soprano and baritone adapted titles against actual written
keys and emitted ABC. Evidence: `sax2-final-source-focused.{json,log}`. The full
suite result above predates only that display correction; it is not presented
as a second full run on the corrected display source.

Independent coverage reads the actual ABC against a separate chord/timeline
oracle. The chart matrix covers four saxophones, four real charts, four interval
sizes and with/without approaches (including 16 expected honest refusals), plus
36 direction/level combinations. Concrete isolation, exact concert adaptation,
register changes, rhythm/articulation preservation, invalid timing, owners and
history are checked separately. The former timed-articulation test now explicitly
asks for the whole routine, consistent with the new ambiguity clarification.


### Final-source browser and safety receipt

**25/25 real-app scenarios passed; recorded browser exit 0.** Evidence:
`sax2-final-source-browser/` and `sax2-final-source-browser-exit.txt`. This includes
actual native SVG notes, durations, accents, staccato and exact slur boundaries,
targeted multi-turn edits, unchanged entire untargeted rows, mixed alto/tenor
items, lower-register movement, read-only Explain, exact Undo/Redo, ambiguous
references, explicit four-bar Blue Bossa fourths/sixths/approaches, All the Things
bridge-to-A section changes, soprano Satin Doll split measures and baritone
Autumn Leaves chromatic sixths. Each request compares immediately captured
before/after Instrument, Saxophone Type, Practice Key and Backing BPM, plus level,
focus and workspace. All comparisons passed. Catalog changes were made through
the normal UI. No state was seeded or musical solver replaced.

Visual QA inspected actual Blue Bossa staff/chord labels and the mixed routine.
It caught the adapted-key title issue, which was corrected and independently
checked in the final-source tests and browser. Long multi-item notation retains
existing iframe scrolling/clipping; no shared layout redesign is claimed.

An earlier full 25-case browser run also passed before that display correction;
`sax2-browser-verified/` is preserved as development evidence. The first
`sax2-browser/` attempt stopped before submitting because its harness requested a
nonexistent Technique dropdown option; changing the harness to the actual
Articulation option resolved it. Neither is substituted for final-source proof.

Summary: `sax2-final-evidence-summary.json`. No final failure or forbidden-API
marker. Python 3.12.8 heavy tests and browsers ran sequentially. RAM, CPU, disk
and Git object usage were checked. Only this task's uniquely identified obsolete
runner tree was stopped; every completed browser closed its own server/browser.
Other processes, dirty shared work, runtime traces, worktrees and backups were
preserved. No dependencies, billing settings, paid calls, force pushes or
deployments. Remote dev was reverified at b8704315; this Slice 2 branch stays local.
