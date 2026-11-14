# Local Stage E: Yamaha YFL-222 flute fingerings and octave instruction

Clarinet Stage D is integrated and remote dev verified at
`d3f700da51c6ad64f77022ca0a80090005a961aa`. Its integration on current
`f3d33016` preserves all 16 newer-dev file blobs and all accepted D files.
Fresh matched Python 3.12.8 regression: 3,681 baseline / 3,764 candidate passed,
the same nine failures and 3,116 passing subtests; all 3,690 shared IDs unchanged
and 83 clarinet cases passed. The complete merged-app browser retry passed
50 requests and 30 visual scenarios; incomplete earlier runs remain in evidence.
The integration receipt records the three additional composition-related
baseline failures, their source history and their reproduction on clean dev.

Stage E branch: `feature/ami-flute-fingering-stage-e-20261114`, isolated at
`D:/AMIWorktrees/flute-fingering-stage-e-20261114`. Local only: no Stage E push,
merge or deployment. Other worktrees, untracked traces and active work remain
untouched. No paid Anthropic access or billing changes.

## Exact model, source review and status

[Yamaha's model table](https://usa.yamaha.com/musical-instruments/brass-woodwinds/products/flutes/400-300-200-series/)
identifies the YFL-222 with covered/plateau keys, offset G and no split-E
mechanism. The original [Yamaha North American brochure](https://usa.yamaha.com/files/download/brochure/1/1152261/W255UR5_wind_us.pdf),
page 6, was rendered and visually checked to establish its standard C footjoint.
The pilot is this concert C configuration, excluding H/B-foot/Gizmo, open-hole,
split-E, optional/modified keywork and other flute types or models.

Six basic rows were independently transcribed and visually checked from
WFG's [first octave](https://www.wfg.woodwind.org/flute/fl_bas_1.html),
[second octave](https://www.wfg.woodwind.org/flute/fl_bas_2.html) and
[key legend](https://www.wfg.woodwind.org/flute/fl_fing.html).
The primary B-natural thumb lever is a selected permitted option for source
symbol T; the alternate Bb-thumb choice is not enabled. The structured records
and the independent permanent source fixture retain source hashes and row
identity. All diagrams are original; downloaded chart artwork is reference-only.

[UNSW acoustics](https://newt.phys.unsw.edu.au/jw/fluteacoustics.html) independently
corroborates repeating fingerings across these registers and distinguishes
finger actions from air-jet behavior. [VSL notation](https://www.vsl.co.at/academy/woodwinds/concert-flute)
independently establishes non-transposing concert C flute notation in treble clef.
Records are **reference-supported, not teacher-reviewed or physically tested**.
Model applicability is established from standard keywork, not a physical trial.

## Six records and exact finger actions

Every note presses the primary B-natural thumb, LH index/middle/ring and RH Eb
little-finger key. The Bb thumb, LH G# little finger, RH ring, Bb/D/D# trill keys
and low C#/C little-finger controls are released in every selected record.

| Written = concert | MIDI | Additional RH main keys pressed |
| --- | --- | --- |
| E4 | 64 | Index and middle |
| F4 | 65 | Index |
| G4 | 67 | None |
| E5 | 76 | Index and middle |
| F5 | 77 | Index |
| G5 | 79 | None |

Other RH main controls are released. These are exact logical finger actions,
not a representation of every linked pad or the physical placement of the keys.

E4-E5, F4-F5 and G4-G5 each span **12 semitones**, with **identical selected key
states**. The flute has no dedicated octave-key action here. The explanation
separates air/embouchure control from fingering, cites UNSW, avoids detailed
physical prescriptions and never labels flute transitions as trumpet lip slurs.
No general claim that every flute octave uses identical fingerings is made.

## Conversation, exercises and existing owners

Model/keywork questions do not silently confirm identity. Explicit confirmation
binds a conversation-local model, independent of sidebar instrument. Positive
unsupported model/configuration changes retract that supported identity while
retaining flute-only clarification scope. Explicit reconfirmation restores it.

E without a numbered octave shows labelled E4/E5 candidates and asks for the
intended octave. Low E resolves to E4. Higher E uses a labelled E5 candidate
with clarification; context can move a specific E4 lookup to E5. Low/high G,
F5, smooth E4-E5 comparison and lower-case pitches are covered. Unsupported
notes, models, flute types and physical methods leave plans/history unchanged.

A note lookup or explanation is read-only for the practice plan/history. Slow
pair handoffs, four repetitions, slower/easier/harder, descending, explicit
alternation, adding a verified pair, short all-three-pair practice, stored finger
explanation and exact Undo/Redo reuse existing Note/bar filling, native writer,
verifier, single-exercise packaging and shared commit/versioning. A single
request stays one exercise; the short all-pair warmup is one bounded item with
rests. Ordinary full/timed warmups retain their existing owner.

Existing proficiency windows are unchanged: Beginner **67-84**, Intermediate
**62-91**, Advanced **60-96** written MIDI. G4-G5 fits Beginner; E4/F4 handoffs
require explicit Intermediate. Read-only display does not promote level.
Harder changes bounded rhythm/tempo, not range or unverified notes. All pairs
have notated full-bar rests; inter-pair connections are not labelled octaves.

Generic unbound flute fingering/octave drills, keyed scales/arpeggios, advanced
jazz, song-aware work, saxophone/trumpet/clarinet instructions, bass/TAB and
unrelated owners remain available. An existing Intermediate F-scale refusal in
the middle register was independently reproduced without this pilot and retained;
an in-range G-scale handoff passes. Explicit other instruments use AMI's existing
parser before contextual flute routing. Account/workspace stamps are shared.

## Visual and native staff acceptance

Original diagrams show all 15 selected controls, pressed/released letters,
accessible descriptions, focus and source links. Desktop comparisons use two
columns; mobile comparisons stack without shrinking below 300 pixels. Native
staff positions are independently checked: E4/F4/G4 = 2/3/4 and E5/F5/G5 =
9/10/11 in ABCJS diatonic staff coordinates. No transposition is applied.

Python **3.12.8** focused acceptance: **423 passed, 10 passing subtests**, 56.49
seconds, including all 78 flute cases and the existing focused instrument suites.
The first preflights exposed concrete language/owner routing gaps, now covered
permanently; their logs are retained.

Real-app acceptance **passed, exit 0: 46 requests and 24 visual scenarios**.
All six notes and three pair comparisons passed at desktop and 390 pixels,
including exact native staff, all 15 key states/fills, accessible labels/focus,
readable fonts and no horizontal overflow. Conversation, actual revisions,
read-only/exact history, model changes, range refusals and SAX/trumpet/clarinet/
ordinary flute/bass-TAB handoffs passed. No forbidden API call was recorded.

Matched full regression **passed its comparison**: **3,842 passed, the same nine
baseline failures, 3,116 passing subtests**, 13 warnings, **939.28 seconds**.
All **3,773 shared IDs were unchanged** and all **78 added cases passed**; no
missing IDs, collection errors or changes to the **205 distinct source-file hashes**. The baseline is the just-validated
98-file clarinet merge `38294198e0d5196913e1f21f2070ce6a16f66601`;
remote integration differs only by its receipt. Stage E retains those 98 files
and adds the permanent flute module (99 total). All 205 distinct source-file hashes
remained unchanged; every shared ID/phase and the exact nine-failure ledger
matched. See [machine acceptance](fingering-stage-e/acceptance.json).

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112`:
`flute-fingering-focused-owner.{json,log}`, `flute-fingering-browser/`,
`flute-fingering-regression.{json,log}`, `flute-fingering-comparison.json`,
`flute-fingering-source-freeze.json`, `flute-fingering-source-review-20261114/`.
Heavy validation is sequential; only owned servers/contexts are closed.

## Limits and separate follow-up work

Only six basic notes and the selected three octave pairs are enabled. No high
third-register fingerings, alternate thumb choices, multiphonics, extended
techniques, modified model applicability, performance assessment or specialized
physical method is claimed. Source support is not teacher/physical validation.

The user's later navigation-icon/beaming request is being prepared independently
on `fix/ami-navigation-beaming-20261114` from integrated dev, in its own worktree.
It does not alter this milestone's frozen source and requires separate local
acceptance/review. Neither local milestone is authorized for push/merge/deploy.

Future specialized saxophone scope is a [separate proposal](AMI_SAX_ALTISSIMO_OVERTONE_PROPOSAL_20261114.md),
not implemented by Stage E.

Artifacts: [desktop E4 staff and keys](fingering-stage-e/desktop-E4-staff-diagram.png)
and original diagrams [E4](fingering-stage-e/E4.svg), [E5](fingering-stage-e/E5.svg),
[F4](fingering-stage-e/F4.svg), [F5](fingering-stage-e/F5.svg),
[G4](fingering-stage-e/G4.svg), [G5](fingering-stage-e/G5.svg).

Mobile review: [actual E4 staff and keys](fingering-stage-e/mobile-E4-native-staff-and-keys.png).
The complete 390-pixel real-app acceptance is separate from this unobstructed
review capture. The capture reproduces the actual native iframe DOM/SVG at its
measured mobile content width, excluding surrounding Streamlit chrome; no notes,
key states or notation were reconstructed. [Provenance](fingering-stage-e/mobile-capture-provenance.json)
retains viewport/content width and native DOM hash. Long native tune headings
retain the existing horizontally scrollable score behavior; the named note, staff
and all key-action labels are legible. Raw obstructed captures are retained in
evidence rather than shipped as review artifacts.

Hash-ledger clarification: the original freeze had 301 path/hash entries, including
Windows slash/backslash aliases for the same files. All original entries were
verified unchanged, then normalized to 205 distinct source files. The original
ledger remains in evidence; this changes receipt metadata only, not tested code.
