# Advanced jazz patterns: bounded local milestone

Slice 2 was integrated normally and verified remotely at
`ec7ed8975dc332c483b96a7f941e567527aab07a`. The clean final-source integration run
passed 2,794 tests and 2,654 subtests with the same six baseline failures; all
2,613 shared IDs were unchanged and all 187 Slice 2 additions passed. Its tree
matches approved source 102c953c, including the written-key title fix. The accepted
25-case browser proof applies to that tree, plus four fresh integrated-source
native checks. See `AMI_SAX_SLICE2_INTEGRATION_20261113.md`.

This milestone is on local branch `feature/ami-advanced-jazz-20261113`, in
`D:/AMIWorktrees/advanced-jazz-20261113`, based on that integration. It is not
approved for push, merge or deployment. The final local commit is reported
separately.

## Chord-tone permutations

The new exercise path supports forward/reversed/alternating core-role cells:
1-5-3-7 skipping, 1-7-3-5 zig-zag, and straight ascending/descending cells.
Starting on the third/root/fifth/seventh rotates the selected cell. Straight
cells retain actual ascending/descending pitches after a start-tone revision.
Core permutation order describes harmonic roles, not a false claim that every
attack ascends. Bounded octave placement can improve connections between cells.
The existing shared dynamic-programming voice-leading planner chooses complete
passages; actual leap and boundary statistics are stored and explained.

An explicitly requested 3-5-7-9 cell requires a natural ninth already named by
the authoritative harmony reader on every selected chord. A seventh chord is
not automatically given a ninth; b9/#9 is not silently substituted for natural
9. Default core cells do not add optional scale extensions. Explicit eleventh/
thirteenth pattern requests are outside this bounded slice. Actual named altered
fifths and tensions are identified in note explanations when encountered.
An explicit seventh-chord request refuses a chord without an actual seventh;
a sixth or third does not stand in. Default core exercises can use an explicitly
charted sixth, labelled as such.

All production harmony comes from `warmup_song.build_timeline`, its authoritative
chart snapshot, and `scale_pattern_harmony.chord_tone_roles`/the existing chord
classification. No second chord parser or substituted chart is introduced.

## Chromatic vocabulary and targets

The canonical approach engine is reused for above/below, alternating single
neighbours, double-chromatic figures and two-sided semitone enclosures. Requests
can target the next chord's third or actual seventh. Existing root/fifth target
support is used when preserving those existing arrival roles.

The jazz wrapper explicitly opts into chord-tone neighbours, a policy separate
from the legacy strict non-chord approach path. Every neighbour is labelled as
an actual named tone of the departing chord or as a non-chord note. Enclosures
can legitimately contain a named chord tone; this is never described as an
invented non-chord pitch. All figures must resolve with their actual stated
semitone geometry to the target at the real next harmonic change, including a
split measure. The first chord establishes the line. Unchanged repeated harmony
does not create a fictitious next-change approach, and there is no unresolved
last-to-first tail on a one-pass card.

Untied anticipations place the next chord's actual target early, then repeat it
on the change. They are labelled anticipations, not chord tones of the departing
chord unless they really are common tones. Tied anticipations are not claimed.
The final chord has no dangling anticipation.

Bebop-oriented revisions select a bounded enclosure/approach exercise; they do
not claim to compose a complete bebop solo grammar. Existing musical-idea owners
for lines, licks, phrases, named scales and unqualified old enclosure spans are
preserved. Guide-tone exercises reuse the canonical resolution engine and explain
actual third/upper-member movement and measured leaps rather than promising
that every connection is a semitone.

Adding approaches while keeping targets preserves actual arrival pitches,
including octaves, where the same verified target recipe can represent them.
Unsupported mixed target roles, incompatible sections or an unplayable exact
voicing refuse without mutation.

## Intervals, rhythm and articulation

Chart-constrained interval cells can cycle thirds/fourths or another supported
requested interval. They retain both spelled letter distance and conventional
semitone size. Chord-tone pairs are distinguished from scale intervals and from
connections BETWEEN cells. Wide sixths with local chromatic step resolutions
use the existing within-chord interval-cell engine; these are explicitly distinct
from the next-chord enclosures above.

Unavailable intervals refuse the whole request. For example, complete Blue Bossa
Section A contains G7#5, which cannot supply perfect fourths from the available
core tones. An explicitly requested four-bar subset can support the mixed cell;
there is no silent subset or scale substitution.

Advanced patterns normally use eighth notes, with explicit sixteenth-note
permutation/anticipation templates available. A pitch-preserving rhythm edit
redistributes supported durations separately inside each harmonic segment,
retaining every event, exact pitch order, articulation, tempo and repetition.
Quarter-note events can cross quarter beats while staying inside the correct
chord and measure. No notes are dropped or added to conceal an impossible edit.
If the same event count cannot be represented with supported durations, or the
request needs ties, swing or triplets, the transformation refuses. Mixed
pitch-preserving interval-cell displacement remains outside this slice.

Paired slurs, slur/tongue combinations, staccato and accents use the existing
canonical notation events. This is notation-level technique guidance, not audio
verification of a saxophonist's tonguing, voicing or finger motion.

## Conversation, plans and instruments

A single advanced permutation/enclosure produces one exercise and one chart
pass. A ten-minute jazz improvisation warmup interleaves guide-tone, permutation
and approach variants in an ordered plan. Selected-item references reuse the
existing numeric/name/selection resolver. Current notes and section references
can refer to the last explicitly edited item; without an unambiguous selection,
AMI asks rather than changing the entire plan.

Only the requested item is rebuilt. All other rows remain exactly equal,
including notes, rhythm, articulation, instrument, tempo and repetitions.
Selected-item repetitions also remain unchanged, so its actual total duration
may differ from the original target after an edit. Explain reads stored notes,
actual chord functions, targets and timing without adding a version. Undo/Redo
restores exact complete plans under the existing account/workspace owner.
Declined fresh requests retain the exact preceding score and history, with an
explicit no-change message.

All four saxophones use existing verified written Bb3-F6 limits, level windows,
treble notation and written-minus-sounding offsets 2/9/14/21 for soprano/alto/
tenor/baritone. Permutation cells honour explicit initial register requests; an unavailable
complete cell refuses. Canonical guide/approach templates initially use the
verified level range; subsequent whole-octave register movement is supported
where the unchanged line fits. Instrument adaptation
preserves the sounding line when it fits, or reports a whole-octave displacement;
otherwise it refuses. Sidebar Instrument, Saxophone Type, Practice Key and Backing
BPM are not changed by these exercise operations. Other instruments retain their
existing owners; this new conversational path is verified for the four saxophones.

## Capability-profile audit

The read-only proposal is in `SAX_CAPABILITY_PROFILE_AUDIT_20261113.md`. It identifies
existing range/offset authorities and absent model-specific keywork, fingering,
overtone and voicing prerequisites. Primary manufacturer and authored references
are linked there, including model differences and a contradictory manufacturer
specification requiring human cross-checking. The proposal separates physical
keywork from player technique and requires provenance, a matched model/revision,
expert review and independent validation before activating future profiles.

No altissimo, overtone or alternate-fingering generator was implemented. No
physical range was expanded. Those features require separate approval.

## Verification receipt

Development evidence, including failed and intentionally stopped runs, is retained
under D:/AMIWorktrees/flexible-evidence-20261112 and is not counted as completed
release proof. The completed release evidence is recorded below.


### Matched regression

Python 3.12.8, sequential execution: 2,950 passed, six pre-existing failures,
2,743 passing subtests across 67 files; no collection errors or deselections.
All 2,840 shared test IDs have unchanged outcomes; all 116 new test IDs pass.
The complete failure/subtest ledger matches the clean current-development
baseline ec7ed8975dc332c483b96a7f941e567527aab07a. The baseline combines the
65-file integration run and the same-source 40-test advanced-vocabulary run.
Evidence: jazz-release-regression.{json,log}, jazz-release-comparison.json,
sax2-clean-integration.{json,log}, jazz-currentdev-vocabulary-baseline.{json,log}
in D:/AMIWorktrees/flexible-evidence-20261112.

Unchanged failure IDs:

- `tests/test_backing_context.py::TestBackingContext::test_custom_progression_context`
- `tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam`
- `tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog`
- `tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present`
- `tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows`
- `tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander`


### Actual musical excerpts

These are stored generated events, not illustrative replacements. Octaves use
MIDI C4=60; beat numbers here are one-based.

- Blue Bossa, concert Cm9 / alto-written Am9: the skip permutation begins
  A5-E6-C6-G5 (root-fifth-minor third-minor seventh), four eighths on beats
  1, 1.5, 2 and 2.5. The explicit 3-5-7-9 subset begins C4-E4-G4-B4,
  sounding Eb3-G3-Bb3-D4, with the ninth actually named in Cm9. Full-chart
  3-5-7-9 and mixed-third/fourth requests refuse unsupported harmony while
  preserving the previous plan and history.
- All the Things You Are, requested bridge: concert Am7 / tenor-written Bm7
  begins B4-F#5-D5-A4, four eighths with actual root-fifth-minor third-minor
  seventh roles. A subsequent A-section revision uses the selected chart
  section and keeps sidebar controls unchanged.

The independent test oracle checks generated ABC events against actual active
chart timelines, spelled chord roles, exact harmonic durations, chromatic target
geometry, interval sizes and sounding offsets. Its extension parser is test-only;
the production generator continues to use the canonical harmony authorities.

- Satin Doll, soprano: written A4 sounds G4. A sixteenth on bar 1 beat 2.75
  anticipates the actual change from concert Dm7 (written Em7) to G7 (A7),
  repeating untied on beat 3 as the new root.
- Autumn Leaves, baritone: G#4-A4 eighths on bar 1 beats 4 and 4.5 resolve
  to A#4 on bar 2 beat 1, the third of written F#13 (concert A13).
  G#4 is honestly labelled a fifth of departing C#m9; A4 is non-chord.
- Autumn Leaves, alto: B4-G#5-A#4-B4 sixteenths combine an actual major sixth
  with a semitone local approach to the seventh.

### Real-app browser acceptance

All 26 requests passed in jazz-release-browser.log; BROWSER_EXIT=0. Real catalog
controls and fresh native cards covered all four charts, thorough alto/tenor
revisions and representative soprano/baritone cases. Independent ABC, harmony,
timing, written/sounding pitch, native SVG duration, slur and decoration checks
passed. Every before/after sidebar snapshot is equal. Selected edits preserve
untouched rows and repetitions; Explain leaves history unchanged; both Undo/Redo
sequences restore exact plans. Both unsupported-harmony refusals preserve the
preceding score and history.

Named-ninth and soprano screenshots were visually inspected. The soprano capture
shows horizontal clipping in the existing card layout; no responsive-layout
repair is claimed. Native note checks cover the full score. The owned browser
and server exited through runner cleanup; paid Anthropic calls were blocked.
No deployment or new-branch push occurred. See jazz-release-evidence-summary.json.

Timed plans interleave canonical guide practice with permutation/approach
variants; guide rows can reuse the canonical cell. Fresh canonical register
handling and unsupported rhythmic/extension requests remain bounded as described
above. No physical-technique or model-specific fingering validation is claimed.
