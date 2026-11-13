# Interactive Fingering Instructor - bounded Stage A

Base: capability foundation integrated on dev at
c4e47cab849eac74d5f53c7ca95b14af3ebef950. Local branch:
feature/ami-fingering-stage-a-20261113. No Stage A push, merge or deployment.

## Identified model and source-backed records

This pilot supports Yamaha YAS-280 alto saxophone with standard factory keywork
as shown in the model-linked Yamaha manual. No other model is silently selected.
A musician can identify it explicitly in a question or say "I play a Yamaha
YAS-280". Without a confirmed model, AMI asks; it does not infer model from Alto.
Explicit instrument requests take precedence over the sidebar for new lookups.
Deictic follow-ups and revisions remain bound to the identified note/stored
exercise even if the sidebar later changes. A model-identification question
does not confirm a model; explicitly retracting the model clears only lookup
identity and requires reconfirmation, preserving exercise versions. Other models,
modified keywork, registers and fingering variants receive explicit limitations.

| Written pitch | Sounding pitch | Pressed finger controls | Released |
|---|---|---|---|
| G4 (67) | Bb3 (58) | Left index, middle, ring | Right main keys, octave thumb, auxiliary controls |
| A4 (69) | C4 (60) | Left index, middle | Left ring, right main keys, octave thumb, auxiliary controls |
| B4 (71) | D4 (62) | Left index | Left middle/ring, right main keys, octave thumb, auxiliary controls |

C4=MIDI60. Bare G/A/B use a documented written-octave-4 default and the answer
labels/discloses it. High/low or other-octave requests do not fall back to octave4.
Concert-pitch inputs require clarification rather than treating them as written.
The exact written-minus-sounding offset comes from the existing alto profile;
spelling and octave use existing pitch helpers. Fingering notes are fixed written
pitches, independent of Practice Key. Their staff uses written C major for these
natural pitches; no sidebar or Practice Key state is changed.

## Authoritative sources and verification status

- Yamaha YAS-280 downloads page links the applicable Saxophones Owner's Manual:
  https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/downloads.html
- Yamaha Saxophones Owner's Manual, VDZ0080 / POCP-C0, published 03/2022,
  Fingering Chart pp.10-12, with filled/empty key legend:
  https://usa.yamaha.com/files/download/other_assets/6/335916/saxophones_en_om_c0.pdf
- Yamaha Musical Instrument Guide first-octave G/A/B reference diagrams:
  https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play002.html
- Independent authored cross-check: Timothy Reichard, Woodwind Fingering Guide,
  first-octave G4/A4/B4 basic rows and key-naming scheme:
  https://www.wfg.woodwind.org/sax/sax_bas_1.html
  https://www.wfg.woodwind.org/sax/sax_fing.html

The primary manual was downloaded and its chart pages rendered/visually inspected.
The Yamaha reference images were inspected; the written octave and controls were
cross-checked against the authored reference. Production records retain source
URLs, locators, retrieval date and the manual SHA256. A separate test fixture
transcribes expected pitches/pressed controls independently from production.

Status is manufacturer/reference-supported, NOT teacher-reviewed or independently
performance validated. No qualified reviewer or actual horn test is claimed.
The user authorized this distinction for Stage A; advanced altissimo/overtone
instruction still requires the separate evidence and expert gates. No source
chart/image was copied into the product: diagrams are original vector logical
finger-control schematics, not photographs or physical key-placement maps.
Finger-control engagement is distinguished from linked mechanical pad positions.
Source review material remains only in the separate evidence directory.

## Conversation and optional handoff

Lookups, key explanations and staff requests retain model/note context under
existing account/workspace ownership. They create no exercise versions and do
not revise a stored exercise. Unsupported requests preserve the valid state.

An explicit related-practice request creates one short deterministic single drill
through warmup_engine Note/Built, render/verify, flexible_single.package and the
existing version history. Default practice repeats the exact target in quarters.
For B4, two verified lower notes support G4-A4-B4-B4; descending gives B4-B4-A4-G4.
A two-distinct-note lead-in below A4/G4 refuses because the missing lower fingerings
are outside this pilot. A repeated pitch has no directional contour; that edit
refuses instead of inventing one. Slower revisions retain exact pitches; easier
practice uses the target in half notes. Key-change explanations read actual stored
notes/control differences, and remain read-only. Undo/Redo restores stored plans.

No second chord, pitch, transposition, notation or history engine is introduced.
Generic flute/clarinet/trumpet technique owners remain in place. Fixed-note
handoffs cannot silently change instrument, register or key, or add unsupported
fingerings. No altissimo, overtone or alternate-fingering generator is enabled.

## Original diagrams and accessibility

Pressed controls use filled blue P markers; released controls use outlined R
markers, so state is not conveyed by color alone. Main keys are grouped and
labelled by hand/finger; octave and auxiliary-control status are explicit.
Figures are keyboard-focusable with accessible names, SVG title/description,
caption relationships and ordinary keyboard-accessible source links. Diagram
styles are scoped and do not alter ABCJS SVGs. Native staff and diagrams share
the existing scrollable card iframe. Minimum diagram width is 280px, with readable
labels at 390px; the existing local score-scroll fix remains intact.

## Bounded next stage

Stage B should extend a small source-backed standard-note set and its octave-key
transitions, with independent review and actual instrument response/intonation
checks before stronger teaching claims. Add model selection and reviewed variants
only with applicability/provenance. Later staff-click lookup should bind the
selected event to its exact written pitch and owner/version. Clarinet systems,
flute registers and trumpet valve/partial data require separate validated records.
Altissimo/overtone/alternate-fingering generation remains a separate approval gate.

## Acceptance receipt

Final-source complete regression: Python 3.12.8, 70 files, 3,073 passed,
6 existing failures, 2,743 passing subtests, 11 warnings (562.62 seconds).
Exact comparison against integrated dev c4e47cab: all 3,033 shared test IDs
unchanged, no missing IDs, all 46 new IDs passed, no collection errors, identical
terminal failure/subtest ledger and Python executable. Receipts are
fingering-final-regression.{json,log} and fingering-final-comparison.json in
D:/AMIWorktrees/flexible-evidence-20261112.

The six unchanged failures are:
- tests/test_backing_context.py::TestBackingContext::test_custom_progression_context
- tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam
- tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog
- tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present
- tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows
- tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander

Final real-app browser acceptance: exit 0; all 35 requests passed. All three
notes passed actual displayed SVG/key-state and native staff-position checks at
1440px desktop and 390px mobile (six visual scenarios). Labels were at least
12px; diagram width at least 280px; no page/iframe horizontal overflow; keyboard
figure focus and source-link Tab navigation passed. Final mobile G4/A4/B4 and
A4 staff/diagram screenshots were visually inspected and readable.

Actual ordinary warmup Next exercise clicks twice matched the corresponding
stored native ABC and displayed no stale fingering diagrams. Conversation tests
covered read-only lookup/history preservation, last-lookup versus stored-exercise
context, model retraction/reconfirmation, unsupported requests, sidebar isolation,
trumpet routing, bounded exercise edits and exact Undo/Redo. Browser evidence:
D:/AMIWorktrees/flexible-evidence-20261112/fingering-final-browser, including
results.json, six *-visual.json receipts and ordinary-navigation.json. The owned
browser/server closed after success. Paid Anthropic transport was blocked; no
forbidden-call marker or browser failure was produced. No billing/deploy action
was performed.

Combined machine-readable receipt: fingering-final-evidence-summary.json in the
evidence root. Stage A is a local implementation only; no push, merge or deploy.


Original standalone diagram examples: fingering-stage-a-examples/G4.svg,
A4.svg and B4.svg. Their matching application figures include source links,
verification status, sounding pitch and limitations beneath the schematic.

Development acceptance: 260 initial focused tests and 238 cross-instrument
focused tests passed; a later 149-test preflight covered model uncertainty and
stored-note context, followed by a 44-test final model/source suite. The first
22-request browser acceptance passed, including all three diagrams at both
widths. These are development evidence; the final-source complete regression
and expanded 35-request browser receipt follow below when complete.

The early fingering-release-regression attempt was intentionally stopped before
completion to clear a retracted model confirmation. Its partial log is retained
as fingering-release-regression-stopped.log and is not release proof. Its missing
completion JSON caused the sequential comparison gate to stop, not an observed
musical regression. All earlier failed/preflight logs remain preserved.


Additional final context checks: a newly looked-up B4 remains the subject of a
read-only key explanation while an older A4 exercise is stored. Naming "the
exercise" explicitly switches the explanation to its actual stored events,
without changing versions. These cases and model retraction/reconfirmation are
included in the expanded 35-request release browser sequence. The final focused
context/owner compatibility run passed 151 tests, including 45 Stage A IDs.

The second partial complete-suite attempt was stopped to add this last-lookup
context check; fingering-release-regression-context-stopped.log is retained.
Neither incomplete run is counted as complete regression evidence. The final
release run uses the fixed source and the same current-dev baseline.


The first completed full-suite development run (fingering-release-regression)
reported nine new ordinary warmup-navigation failures in addition to the six
baseline failures. The new diagram-metadata copy had incorrectly conditioned the
normal card rerun. This was corrected before acceptance; fingering-navigation-
verified passed all 68 affected navigation/lifecycle/Stage A tests, including a
new stale-diagram clearing check. The final complete run is fingering-final-
regression, separately labelled and compared to the same baseline. Final browser
acceptance also clicks the actual Next exercise button twice and checks the
resulting native ABC against stored warmup items. The failed development run
is retained, not silently reclassified as a baseline failure.
