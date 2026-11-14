# Yamaha YCL-255 clarinet fingering and register pilot — local Stage D

Stage C was integrated by a normal ancestry-safe push and verified on remote dev
at `378fad17d3eab15672e309d080f5c7a6db92eb6f`, preserving current dev
`4301efe191a67f813ae922c916b2368bd785dc52` and every newer file unchanged.
Its fresh comparison passed all 3,519 shared IDs unchanged and all 63 added
trumpet cases, with the exact nine current-baseline failures. Its merged-app
browser passed 33 requests and 21 desktop/mobile visual scenarios.

Stage D branch: `feature/ami-clarinet-fingering-stage-d-20261114`, isolated at
`D:/AMIWorktrees/clarinet-fingering-stage-d-20261114`. This milestone is local
only. No Stage D push, merge or deployment is authorized.

## Model and independent evidence

The [Yamaha specification](https://usa.yamaha.com/products/musical_instruments/winds/clarinets/ycl-255/specs.html)
identifies the **YCL-255 B-flat soprano clarinet, standard Boehm system, 17 keys
and six rings**. Exact finger actions were independently transcribed from
Timothy Reichard's [basic chalumeau chart](https://www.wfg.woodwind.org/clarinet/cl_bas_1.html),
[basic clarion chart](https://www.wfg.woodwind.org/clarinet/cl_bas_2.html) and
[key legend](https://www.wfg.woodwind.org/clarinet/cl_fing.html).
[UNSW clarinet acoustics](https://newt.phys.unsw.edu.au/jw/clarinetacoustics.html)
independently explains the register vent, twelfth overblowing, E3/B4 relationship
and the throat-to-clarion break.

The seven exact source rows and key symbols were visually inspected. Downloaded
HTML, reference-only images, hashes, row review and a separate manual
transcription are retained in
`D:/AMIWorktrees/flexible-evidence-20261112/clarinet-fingering-source-review-20261114`.
The permanent [source oracle](../tests/fixtures/ycl255_fingering_oracle.json)
was not derived from exercise output or production control maps. Source chart
artwork is not shipped in the product; all application diagrams are original.

Status is **reference-supported**, with model applicability established from
Yamaha's standard Boehm specification. It is **not teacher-reviewed or physically
tested** on an actual YCL-255. No applicability to Albert/Oehler, other clarinet
keys/types, custom mechanisms or alternate fingerings is assumed.

## Seven notes and selected exact basic fingerings

| Written | Concert | Thumb hole / six main holes | Register key | Other pressed key |
| --- | --- | --- | --- | --- |
| E3 (52) | D3 (50) | All covered | Released | Left little-finger E/B |
| F3 (53) | Eb3 (51) | All covered | Released | Right little-finger F/C |
| G3 (55) | F3 (53) | All covered | Released | None |
| Bb4 (70) | Ab4 (68) | All open | Pressed | Throat A |
| B4 (71) | A4 (69) | All covered | Pressed | Left little-finger E/B |
| C5 (72) | Bb4 (70) | All covered | Pressed | Right little-finger F/C |
| D5 (74) | C5 (72) | All covered | Pressed | None |

All other standard finger controls are released. The numbers are MIDI values.
The left E/B and right F/C choices are selected basic source options, not a claim
that these notes have only one possible fingering. Other little-finger variants,
added throat-tone resonance fingers and specialized alternates are not enabled.
Finger actions are represented separately from pad/linkage states.

## Register relationships and break

The selected **E3-B4, F3-C5 and G3-D5** pairs each span **19 semitones**, an octave
plus a perfect fifth. With these exact selected fingerings, only the register
key changes: the thumb hole, six main holes and chosen little finger retain
their states. This is a bounded observation about these pairs, not a rule for
every clarinet note. The nominal next resonance is approximately three times
the lower frequency; equal-tempered pitch targets are not exact acoustic
measurements.

The **Bb4-B4 break is one semitone**. The register key is already pressed on
basic throat Bb4 and stays pressed. Moving upward covers the thumb and six
main holes, releases the A key and presses the left E/B key; descending reverses
those finger actions. The written B4 following Bb4 in one bar receives a natural
sign. This crossing is distinct from both a twelfth and a 12-semitone octave.

## Diagrams, notation and conversation

Original data-driven diagrams show seven finger holes with **C/O** labels
(covered/open), and register, A, left E/B and right F/C keys with **P/R** labels
(pressed/released). Shapes, labels, accessible descriptions and keyboard focus
supplement color. Comparisons show both records and list exact changes. Native
staff notation uses AMI's existing writer/verifier, fixed written C-major
signature and explicitly labelled concert pitches a major second lower.

The model is explicitly identified in conversation; an Alto Saxophone sidebar
is unchanged by an explicit clarinet request. Instrument-key phrases are
removed before pitch parsing. Low E is labelled E3. B above the break is B4;
"high B" receives a labelled B4 candidate and a numbered-octave clarification,
not a silent assumption that all uses of high B mean B4. Unknown notes/models,
register conflicts, systems and specialized methods preserve stored work.

For a fingering-specific exercise, name a verified written pair or refer to the displayed notes. An ordinary exercise named by key stays with its existing generation engine.

A lookup or explanation is read-only for the current practice plan and its
version history. New successful model-specific lookups select the appropriate
clarinet/saxophone/trumpet lookup context. Owner stamps retain existing account
and workspace isolation. Explanations can follow the most recent read-only
note, while an explicit stored-exercise explanation uses its actual records.

## Exercise handoffs and existing owners

Source-backed recipes use existing `warmup_engine.Note`, bar filling, rendering,
verification, `flexible_single.package` and shared commit/Undo/Redo machinery.
No second notation or versioning engine is introduced. Twelfth pairs have
notated full-bar breath rests between them; connections between different pairs
are not labelled as additional twelfths. Break practice uses verified Bb4/B4
rather than inheriting unverified neighboring fingerings from a generic drill.

Slow E3-B4 handoff, four repetitions, adding F3-C5 and then G3-D5, slower/easier,
descending, read-only finger-change explanation and exact Undo/Redo are bounded
by the registered data. No extra fourth pair or arbitrary transposition is
substituted. A new short register-break warmup uses its separate semitone recipe.

Existing level windows are unchanged: **Beginner 55-76**, Intermediate 52-86,
Advanced 52-91 (written MIDI). Beginner E3/F3 exercise requests are refused with
an explicit Intermediate/G3-D5 alternative, never silently promoted or widened.
G3-D5 and Bb4-B4 fit the existing Beginner window. Read-only E3/F3 staff display
does not claim Beginner playing suitability. Guidance stays conservative and
contains no specialized embouchure or breathing prescription.

Ordinary clarinet scale, octave and technique owners remain available, as do
saxophone fingerings/octaves, trumpet valves/partials/lip slurs, flute, adaptive
warmups, jazz, song-aware work, bass/TAB and unrelated application areas.

## Acceptance

Python: exactly **3.12.8**. Final instrument-complete focused preflight: **505 passed, 10 passing subtests**,
68.93 seconds, including the new clarinet and existing trumpet/saxophone/
instrument/flexible/notation suites. The only first-run failure was a contextual
transposition phrase falling through to an unrelated reply; it is now handled
as an explicit model-pilot refusal, with plan/history preserved.

The initial real desktop/mobile browser **passed, exit 0: 42 requests and 30 visual scenarios**. All seven individual notes, all three twelfth comparisons and the break comparison passed at desktop and 390 pixels. Native staff positions and accidentals, all seven hole/four key states, source-backed control fills, readable labels/fonts, keyboard focus/source links and no horizontal page overflow passed. Native Bb4/B4 rendering was independently observed as staff position 6 / 6 with flat / natural signs.

Conversation acceptance passed model clarification, explicit model, B above break, low E, ambiguous high B, register-key explanation, low-E-to-clarion-B, exercise handoff, four repetitions, adding a verified pair, slower/easier, descending, exact Undo/Redo, read-only actual finger changes, unsupported notes/models/systems/altissimo, Beginner range refusals and supported G3-D5, last read-only note context, saxophone/trumpet handoffs and ordinary clarinet generation. The launcher hard-blocked paid Anthropic access; no forbidden-call evidence was recorded.

A final scope probe then found that a positive unsupported model statement (for example, "I play a Yamaha YCL-450") was ignored while retaining YCL-255 identity. This was corrected before final acceptance: positive unsupported model/system changes retract the supported model while retaining clarinet-only clarification scope, and preserve the practice plan/history. Five permanent cases cover unsupported identities, bare fingering follow-ups and explicit YCL-255 reconfirmation. Unknown-model fingering questions still preserve the existing confirmed context; an identity statement has different meaning. The superseded incomplete full-regression log and the initial browser evidence are preserved.

The identity-corrected browser **passed, exit 0: 46 requests and 30 visual scenarios**, including unsupported identity change, bare clarinet clarification, explicit YCL-255 reconfirmation and verified E3 lookup with the stored score/history unchanged. All prior visual, musical, owner and history scenarios passed again. No forbidden API call was recorded.

Owner review also demonstrated that generic requests containing a key (for example, a warmup in C or jazz exercise in Bb) could be mistaken for note handoffs. Handoff routing now requires explicit note transitions or contextual note references, and leaves ordinary keyed music with its established owner. Permanent cases cover keyed scales, arpeggios, warmups, jazz and chord/song contexts after model identification. The existing Beginner F-concert arpeggio refusal and fresh-generation history semantics were reproduced without the pilot and preserved; an in-range Advanced arpeggio and its actual revision Undo/Redo are tested.

Owner-complete browser **passed, exit 0: 49 requests and 30 visual scenarios**, on its then-frozen source. It repeats every note, twelfth/break comparison, model/ambiguity, handoff/revision, read-only/history, level and instrument-owner scenario. It additionally verifies ordinary keyed clarinet scale generation in C, the unchanged Beginner F-concert arpeggio refusal, and successful Advanced F-concert arpeggio generation. Both positive unsupported-model identity retraction and explicit reconfirmation pass without altering stored score/history. No forbidden API call was recorded.

The preceding owner-complete full regression passed **3,651 tests**, with the
same **nine baseline failures**, 3,116 passing subtests and all 3,582 shared IDs
unchanged; all 78 added cases passed. Its evidence is retained.

The final routing correction uses AMI's existing instrument parser to recognize
explicit changes to bass, guitar, trombone, piano and other instruments before
considering a contextual clarinet handoff. Five additional permanent cases
include actual bass guitar/TAB generation after clarinet identification.

Final instrument-complete browser **passed: 50 requests and 30 visual scenarios**,
including the bass guitar/TAB owner. All seven notes, all three twelfth pairs and
the break comparison passed at desktop and 390 pixels, along with the full
conversation, revision, read-only, isolation and unsupported-request scenarios.
No forbidden API call was recorded. The final focused gate contains **83 new
clarinet cases**.

Final instrument-complete full regression: **3,656 passed, nine unchanged baseline
failures, 3,116 passing subtests**, 11 warnings, **790.93 seconds**. All **3,582
shared IDs are unchanged**, all **83 added cases passed**, with no missing IDs,
collection errors or source changes across the 101 frozen files. The exact nine
failure IDs are recorded in [acceptance.json](fingering-stage-d/acceptance.json).
Application source remained frozen during this sequential gate. The matched baseline is the just-validated
96-file Stage C integration candidate
`1ba9c5df6e5db15c34f500d7e94f1d31232dc616`; integrated dev differs only by its
acceptance receipt. Stage D retains those 96 files and adds the clarinet module
(97 files total). No new or changed shared failure is accepted.

Evidence root: `D:/AMIWorktrees/flexible-evidence-20261112`;
`clarinet-fingering-preflight-instrument-complete.{json,log}`,
`clarinet-fingering-browser-instrument-complete/`,
`clarinet-fingering-regression-instrument-complete.{json,log}`,
`clarinet-fingering-comparison-instrument-complete.json`,
`clarinet-fingering-source-freeze.json`.
Heavy tests/browsers run sequentially with CPU/RAM/disk monitoring; only owned
servers/contexts are closed. Other worktrees, commits, untracked traces and
evidence are preserved. Paid Anthropic access and billing changes are excluded.

## Limits and recommended Stage E

Only the seven basic records, three selected twelfth pairs and one break pair
are enabled. Altissimo, specialized alternates, German/Oehler/Albert, bass/E-flat
or other clarinets, unverified transitions and detailed embouchure/breathing
methods remain outside this pilot. No teacher or performance assessment is
claimed. Existing generic exercises may contain other notes without claiming
these model-specific fingering diagrams.

Stage E should be a separate small, explicitly identified standard flute model
pilot. Independently verify candidate E4/E5, F4/F5 and G4/G5 fingerings and every
required octave/register difference before enabling them. Include actual staff,
original accessible diagrams, source-bounded flexibility handoffs, level limits,
read-only context and exact shared history. Do not add alternate/extended flute
techniques or expand this clarinet milestone into other instruments.

Review artifacts: [mobile throat Bb4](fingering-stage-d/mobile-Bb4.png), [desktop E3 staff and controls](fingering-stage-d/desktop-E3-staff-diagram.png), and original diagrams [E3](fingering-stage-d/E3.svg), [B4](fingering-stage-d/B4.svg), [Bb4](fingering-stage-d/Bb4.svg), [F3](fingering-stage-d/F3.svg), [C5](fingering-stage-d/C5.svg), [G3](fingering-stage-d/G3.svg), [D5](fingering-stage-d/D5.svg).

Capture provenance: the mobile Bb4 image is from the retained owner-complete browser acceptance. The clear desktop E3 staff capture is retained from the initial complete visual run; final native ABC and fingering-record payloads match it exactly, and all renderer/record source hashes are unchanged. Raw captures, including incomplete raster screenshots, remain in the evidence folders.
