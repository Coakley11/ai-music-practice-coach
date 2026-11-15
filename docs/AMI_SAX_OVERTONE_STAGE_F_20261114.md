# Saxophone Stage F: gated overtone preparation pilot - 2026-11-14

## Scope and publication boundary

Local branch `feature/ami-sax-overtone-stage-f-20261114`, based on completed UI/flute integration `2313403a36e8867377f718524905a7a8df00df49`. No Stage F push, merge or deployment. Existing instructors, capability foundation, common ranges, parsers, history and specialized refusals are unchanged. The new module is not connected to a user-facing route.

## Published evidence and exact applicability

The documentary model is the existing standard-factory Yamaha YAS-280 alto scope. The existing model-linked Yamaha manual and independent Stage B fixture remain the source of basic D4/D5 controls; no altissimo key combinations are added. Yamaha's official model index lists front F/high F-sharp; direct specification fetch returned 403 on this recheck, so no fresh direct-table inspection is claimed. The physical specimen/revision, keywork modifications, neck, mouthpiece/reed and player response remain unconfirmed.

Sources reviewed:

- [Yamaha harmonics](https://www.yamaha.com/en/musical_instrument_guide/saxophone/trivia/trivia008.html): ideal partials are integer frequency multiples; partial 2 is an octave and 3 a twelfth.
- [Yamaha fingering/overblowing guide](https://www.yamaha.com/en/musical_instrument_guide/saxophone/play/play002.html): general playing/fingering context, not a tested YAS-280 overtone recipe.
- [UNSW saxophone/vocal-tract research](https://newt.phys.unsw.edu.au/jw/SaxTract.html): specialist response depends on player and instrument acoustics; a key list alone is insufficient evidence of facility.
- [WFG lower-altissimo alternatives](https://www.wfg.woodwind.org/sax/sax_alt_4.html): several variants and context-dependent comments; no specific variant is established here as physically validated on this YAS-280 setup.
- [Yamaha YAS-280 specifications](https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/specs.html): official index plus previously registered documentary scope; direct 403 noted above.

No source diagram/artwork is copied into the pilot. Reference-supported information is distinct from expert review and physical testing.

## Tiny structured documentary pilot

The **fingered fundamental is written D4 (MIDI 62), sounding F3 (53)**, using the existing D4 record: LH 1/2/3 and RH 1/2/3 pressed, octave thumb released, no added auxiliary controls. These are basic-fingering reference facts. The following targets describe ideal harmonic relationships, not a validated response instruction:

| Intended partial | Written target | Sounding target | Ideal frequency ratio | Nearest tempered interval |
| --- | --- | --- | --- | --- |
| 2 | D5 (74) | F4 (65) | 2:1 | 12 semitones |
| 3 | A5 (81) | C5 (72) | 3:1 | 19 semitones |

The ideal third harmonic is approximately 1.955 cents above the 19-semitone equal-tempered target. This is a mathematical distinction, not a prediction of a real instrument's intonation. Partial 1 is the fundamental. No higher partial, alternative fundamental or altissimo fingering is enabled.

The frozen representation validates exact written/sounding octaves, the alto nine-semitone offset, integer partials, registered source identities and the existing range. It keeps the fingered D4 reference distinct from ordinary D5/A5 target fingerings. The closed gate reuses `sax_capabilities.validation_requirements`; even submitted review metadata cannot activate a specialist engine.

## Safely bounded ordinary example

`ordinary_register_preview` returns one uncommitted D4-D5 half-note bar through the existing `fingering_transitions.build` / canonical notation and verification path. Written 62/74, sounding 53/65; four quarter beats at 60 BPM take **four seconds**. The selected level is explicit and retains its existing range window.

**The ordinary octave thumb changes. This is an ordinary register-reading/key-change study, not a D4-fingering overtone drill.** No specialized embouchure, voicing or breathing method is prescribed. No session history is created by the preview function.

Actual browser acceptance passed **10 requests**, at desktop and 390px: identified model, ordinary D4/D5 comparison and study, slower revision, exact Undo/Redo, and four unchanged specialist refusals. Native staff positions were independently checked as 1/8, with four-second timing. [Canonical ABC](sax-overtone-stage-f/ordinary-D4-D5-preview.abc) and [actual desktop staff/fundamental view](sax-overtone-stage-f/desktop-ordinary-study-and-fundamental.png) are included. The screenshot is an actual app capture with surrounding page chrome and a partial lower comparison, not a reconstructed score.

## Intended specialist workflow after future approval

Clarify actual horn/setup and exact written octave; retrieve a model-applicable reviewed variant and its limitations; show original control data plus native written/sounding notation; offer only an independently supported exercise; retain the same exercise for conversational edits, read-only Explain and exact Undo/Redo. Reuse the existing records and history engine. Written G6 on alto would sound Bb5, but it remains a candidate research boundary, not an enabled fingering. Written Bb6 would sound Db6 and requires a later separately reviewed scope.

## Required validation before any specialist activation

An independent saxophone teacher/reviewer and a matching physical instrument must verify the specimen/setup, chosen fundamental and controls, intended partial, reliable response, intonation, transitions and prerequisites. Independent checks must cover written/sounding pitch, octave, ideal-versus-real harmonic relationship, range, timing, notation, owner/history isolation and accessible browser display. Source attribution and reproduction permissions must be recorded. A separate approved and independently verified specialized engine is still required; Advanced level and optional keywork do not open the gate.

## Acceptance and remaining limits

Focused Python 3.12.8 acceptance: **398 passed in 51.20 seconds**, including **25 new independent pilot cases** and existing saxophone capability, saxophone fingering, flute, clarinet and trumpet cases. The new oracle supplies literal pitches, controls, ratios, cents and timing; it is not generated by the implementation. The combined base already passed 3,919 tests with exactly the nine current-dev baseline failures and one environment skip. Stage F does not change any existing tracked implementation, so no new shared-generation behavior is claimed.

All **2,160 existing source files remain byte-identical** to the validated integrated base. The complete freeze contains 2,163 files including the three new pilot module/test/fixture files. [Machine acceptance](sax-overtone-stage-f/acceptance.json) records sources, missing review requirements, candidates, actual browser observations and exact ordinary preview. No paid API attempt was observed. No specialized instruction was enabled.

Source support is not teacher or physical validation. No readiness/performance assessment, altissimo diagram, alternate fingering, specialized overtone drill, new range window or public specialist route is delivered. The next approval boundary is review of this documentary pilot and ordinary example; activation requires the separate validation above.

The [adaptive interval/lick audit and proposal](AMI_ADAPTIVE_EXERCISE_GAP_ANALYSIS_20261114.md) is also proposal-only. It records existing capabilities and concrete bare-request/count/traversal gaps without implementing another engine.
