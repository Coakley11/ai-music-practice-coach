# Interactive Fingering Instructor - bounded Stage B

Stage A integration: origin/dev verified at
18ee27b3f61ea4057acbdd1efb993039f75044a4 after fresh regression and browser gates.
Stage B branch: feature/ami-fingering-stage-b-20261113, isolated D: worktree.
Stage B is local only: no push, merge or deployment is authorized/performed.

## Model, verified data and boundaries

Only explicitly identified Yamaha YAS-280 alto, standard factory keywork.
Nine added written pitches join G4/A4/B4, for twelve total. States below describe
finger controls, not mechanically linked pad-open/closed positions. Auxiliary
controls are released in every supported basic fingering.

| New written pitch / MIDI | Sounding pitch / MIDI | Pressed controls |
|---|---|---|
| D4 / 62 | F3 / 53 | L1 L2 L3 R1 R2 R3 |
| E4 / 64 | G3 / 55 | L1 L2 L3 R1 R2 |
| F4 / 65 | Ab3 / 56 | L1 L2 L3 R1 |
| C5 / 72 | Eb4 / 63 | L2 |
| D5 / 74 | F4 / 65 | L1 L2 L3 R1 R2 R3 O |
| E5 / 76 | G4 / 67 | L1 L2 L3 R1 R2 O |
| F5 / 77 | Ab4 / 68 | L1 L2 L3 R1 O |
| G5 / 79 | Bb4 / 70 | L1 L2 L3 O |
| A5 / 81 | C5 / 72 | L1 L2 O |

L1/L2/L3 are left index/middle/ring; R1/R2/R3 right index/middle/ring;
O is the octave-thumb control. Every unlisted control is released. C4=MIDI60.
All sounding notes are exactly nine semitones below written pitches via existing
alto/pitch helpers. No alternative fingering is inferred from pitch alone.

Bare D/E/F/G/A/B use the disclosed written-octave-4 default. C needs C5 explicitly;
C4 and B5 remain unsupported. For verified pairs, low/high mean written octave
4/5, explicitly labelled in the response; conflicting numbered/register language
is refused. More ambiguous registers receive clarification. Unsupported models,
modified keywork, other saxophone types and specialized techniques remain out of
scope. Ordinary flute/clarinet/trumpet technique owners remain intact.

## Source evidence and status

Primary: Yamaha YAS-280 model-linked Saxophones Owner's Manual, VDZ0080 /
POCP-C0, published 03/2022, printed fingering chart pp.10-11 and its legend:
https://usa.yamaha.com/files/download/other_assets/6/335916/saxophones_en_om_c0.pdf
Model applicability listing:
https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/downloads.html

The manual chart pages and all nine corresponding basic Yamaha guide images were
visually inspected. Guide:
https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play002.html
Exact per-note GIF locators are stored in fingering_records.json (source charts
are not embedded or copied into the app). Independent authored corroboration:
https://www.wfg.woodwind.org/sax/sax_bas_1.html
https://www.wfg.woodwind.org/sax/sax_bas_2.html

The independent test fixture yas280_stage_b_oracle.json is a separate manual/
reference transcription, not generated from production records. External source
inspection/hashes: D:/AMIWorktrees/flexible-evidence-20261112/fingering-b-source-review.

Status: manufacturer/reference-supported. No teacher review, actual-horn test,
intonation measurement or performance assessment occurred. The application makes
no claim that moving the octave thumb alone guarantees a particular sounding
note or provides sufficient embouchure/breath instruction.

## Comparisons and canonical practice handoffs

Five documented pairs: D4/D5, E4/E5, F4/F5, G4/G5 and A4/A5. Each is exactly 12
semitones, retains main-key states and changes the documented octave-thumb
control. C5/D5 is not an octave and changes multiple controls; it is not offered
as an octave pair. Staff and both diagrams are generated from their actual
verified records. Original reusable renderer; no manually duplicated diagrams.

Read-only comparison, difference, keys and staff answers retain exercise/history.
Pair lookup context is distinct from the stored exercise. An explicit "in the
exercise" explanation reads the actual stored events/control differences.
Explicit instrument selection comes first; deictic follow-ups bind the identified
pair despite sidebar changes. Context uses the established account/workspace
owner stamps and is cleared on owner changes.

The new recipe module supplies bounded note lists to the existing fs.build,
we.Note/Built/_fill_bar, render/verify, fs.package and wp._commit paths. It does
not add a pitch, notation, transposition or history engine. Undo/Redo uses the
existing exact stored versions, including handoffs to/from ordinary warmups.

- Initial octave jump: G4-G5, half notes at 60 BPM; A4-A5 uses Intermediate
  metadata to fit the existing level window (no sidebar level change).
- Slower changes tempo only; repetition changes repeat count only (1-12).
  A one-jump pattern repeated four times means four actual octave jumps.
- Harder: G4-G5-G4-G5 in quarters, preserving tempo, direction, repeats and model.
- Easier: the same pair in half notes. Descending reverses the actual pitch order.
- G upper lead-in: G4-E5-F5-G5, quarters; all four displayed records are verified.
  Other upper lead-in recipes remain explicitly unavailable.
- Gradual ascent: D4-E4-F4-G4-A4-B4-C5-D5 in quarters, including the actual
  C5-to-D5 multi-control/register transition. This is a bounded natural-note
  progression, not a claim of a full scale or a complete technique curriculum.

Only half/quarter notes and the verified recipes are accepted. Other instrument,
key/register substitution, advanced rhythm and unsupported pitches refuse without
changing the stored exercise/history. Legacy B4 lead-in remains G4-A4-B4-B4;
other single-note lead-in recipes are not silently expanded.

## Visual instruction and accessibility

Original data-driven labelled P/R schematics, descriptive pressed/released lists,
SVG title/description, figure focus and keyboard source links. Native ABCJS staff
and comparison figures share the existing locally scrollable notation iframe.
Diagrams stack vertically for mobile; no physical key-placement accuracy is
claimed. Examples are generated from records under fingering-stage-b-examples/.
Final responsive/native staff/browser acceptance is recorded below.

## Verification receipt

Focused compatibility: 492 passed, covering original/new fingering tests,
saxophone conversation and advanced jazz, trumpet, flute and clarinet technique.

Real-app browser acceptance: exit 0, 35 requests, 26 actual diagram scenarios
(all nine new notes at desktop 1440px/mobile 390px, plus both G/A pairs at both
widths). Actual ABCJS pitch positions matched independent written-note positions;
all seven control states/fills matched the independent source oracle. Minimum
label size 12px, width 280px, no page/iframe horizontal overflow; keyboard focus
and source-link navigation passed. D4/G5 native staff+diagram and the mobile A5
comparison diagram were visually inspected and readable. Comparisons stack in
the locally scrollable iframe, so both diagrams remain available without forcing
the page wider. Evidence: fingering-b-browser-8597/{results.json,*-visual.json,
*-diagram.png,*-staff-diagram.png} in the evidence root. Owned server/browser
closed after success. The original port8596 attempt safely refused another
agent's server before creating/attaching a browser; it is not acceptance proof.

The browser checked lower/upper comparisons, cross-note conversational focus,
exercise handoff, slower, four repetitions, harder/easier, descending/ascending,
actual key changes, exact Undo/Redo, verified upper-G lead-in, gradual ascent,
unsupported/ambiguous pitches, model and alternate-fingering refusals, non-octave
refusal, read-only lookup with a different stored plan, sidebar context and
ordinary trumpet routing. Unit tests additionally cover five octave pairs,
account/workspace isolation and shared warmup handoffs. Paid Anthropic transport
was blocked and no forbidden-call marker occurred; no billing/deploy action.

The complete run exposed one additional actual regression: the new instruction
used British "practise", violating the established American-English source test.
The partial full run is retained as fingering-b-final-stopped.log; its fail-fast
reproduction fingering-b-isolate reported exactly that new failure after 360
passes. It was corrected to "practice". The affected wording/Stage B run then
passed 74 tests and 10 subtests (fingering-b-wording-fixed).

The 35-request/26-diagram browser acceptance preceded the later application
wording and generic-owner corrections. The final-source short browser probe additionally verifies pair
staff/diagrams, handoff, slowing and exact Undo/Redo after full comparison.
The first completed full Stage B run then found six new failures in ordinary
saxophone octave/register exercises (all new fingering tests passed). Generic
unbound requests had been intercepted for model identification. Evidence is
preserved as fingering-b-generic-owner-failed-regression.{json,log} and its exact
comparison. The entry rule was narrowed so generic saxophone technique requests
retain their established owner unless note/key/fingering intent or identified
fingering context applies. Three permanent regression cases were added. The final
browser probe also starts with an actual ordinary sax octave request before model
identification, checking the original owner. None of these six were reclassified
as baseline failures. The affected owner/notation/technique run passed 311 tests
and 10 subtests after correction.

Final complete regression: Python 3.12.8, 71 files, 3,134 passed, six unchanged
baseline failures, 2,743 passing subtests, 11 warnings, 827.95 seconds.
Exact comparison against clean integrated dev 18ee27b3: 3,077 shared IDs unchanged,
no unexpected missing IDs, all 61 new Stage B IDs and both replacement boundary
cases passed (63 new IDs total), no collection errors, same Python executable,
and identical terminal failure/subtest ledger. Receipts in the evidence root:
fingering-b-final-regression.{json,log} and fingering-b-final-comparison.json.

The six unchanged baseline failures are:
- tests/test_backing_context.py::TestBackingContext::test_custom_progression_context
- tests/test_backing_context.py::TestBackingContext::test_sections_from_custom_progression_ignores_style_jam
- tests/test_backing_handoff_authority.py::TestBackingHandoffAuthority::test_refresh_restores_custom_not_catalog
- tests/test_music_canonical_insight_submit.py::TestMusicCanonicalInsightSubmit::test_metrics_include_ami_insight_when_canonical_present
- tests/test_song_card_guidance.py::TestCardDetailsAndHtml::test_card_html_shows_setup_and_the_four_guidance_rows
- tests/test_tab_missions_render_regression.py::TestTabMissionsRenderRegression::test_tab_missions_body_with_example_and_recording_expander

Final-source browser probe: exit 0, seven requests and four actual G4/G5
comparison-diagram scenarios at desktop/mobile. It passed the ordinary sax octave
owner before model identification, explicit model setup, actual paired staff
positions and diagram controls, canonical handoff, slowing and exact Undo/Redo.
The final mobile G5 diagram was visually inspected and readable. Evidence:
fingering-b-final-browser/{results.json,*-visual.json,*-diagram.png}.
Final application/test/browser hashes match fingering-b-source-snapshot.json.
Neither accepted browser folder contains failure.json or forbidden-api-call.txt;
the owned final server/browser closed after success. No paid calls, billing
changes or deployment occurred.

Combined external receipt: fingering-b-final-evidence-summary.json. Stage B is
locally committed for review only; no push, merge or deployment. Runtime traces
are preserved and excluded from the commit.
Source hashes are retained before/after the wording change in
fingering-b-before-wording-source-snapshot.json,
fingering-b-before-owner-fix-source-snapshot.json and fingering-b-source-snapshot.json;
the final hash check must match the latter.
The Stage B baseline is integrated dev 18ee27b3; its only change from the freshly
tested Stage A ccf70479 candidate is the integration receipt document.

Failed development logs are preserved and not release proof:
fingering-b-first (three failing context cases); fingering-b-preflight (BOM corruption
and non-sax octave owner interception). The 150-test context rerun passed before
the broader preflight exposed those later issues. All were corrected before the
final acceptance gate.

Two old negative inputs were deliberately moved from newly supported A5/high G
to still-unsupported A6/G6. The full comparison must report these two replaced
parameter IDs explicitly rather than count them as unchanged shared tests.

## Recommended Stage C

Recommend a small explicitly identified B-flat trumpet pilot (e.g. Yamaha
YTR-2330) with source-backed basic valve combinations plus harmonic-partial
identity, written/sounding pitch and distinct partial notation. Yamaha's model
manual and authored guide provide a bounded starting point:
https://usa.yamaha.com/products/musical_instruments/winds/trumpets/bb_trumpets/ytr-2330/downloads.html
https://www.yamaha.com/en/musical_instrument_guide/trumpet/play/play002.html
https://www.yamaha.com/en/musical_instrument_guide/trumpet/mechanism/mechanism002.html

This recommendation is based on source coverage and three-valve visual simplicity,
not completed verification of new trumpet records. First verify a tiny standard
note/partial set independently; explain that valve state does not uniquely select
pitch. Keep technique/intonation claims restricted until expert/instrument review.
The existing trumpet deterministic partial exercises are a reuse point.

Later saxophone expansion requires separately identified model/type and exact
transposition; clarinet needs explicit Boehm/other system and register/keywork
records; flute needs octave-dependent records. Staff-click selection should bind
an actual written event to its owner/version. Altissimo, overtone and alternate
fingerings remain separate future approval/verification gates. None implemented.
