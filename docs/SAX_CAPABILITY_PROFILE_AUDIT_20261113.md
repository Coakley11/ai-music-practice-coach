# Saxophone capability-profile audit and bounded proposal

Read-only audit, 2026-11-13. No range, fingering, altissimo or overtone generator
changes are authorized or implemented in the advanced-jazz milestone.

## Existing authorities

- `exercise_adapt.SPECS`: soprano/alto/tenor/baritone identity, notation name and
  transposing-type label; no horn model, keywork or fingering system.
- `scale_pattern_harmony._OFFSETS`: written minus sounding 2/9/14/21
  semitones for soprano/alto/tenor/baritone, including octaves.
- `_PLAYABLE_WRITTEN`: generic conservative Bb3-F6 (MIDI 58-89) for all four.
  This is the accepted application cap, not a claim that every model's physical
  endpoints are identical. Some notation comfort profiles extend below written
  Bb3; the hard range adapter currently clamps those passages.
- `warmup_engine._WINDOWS['sax']`: Beginner D4-G5, Intermediate C4-C6,
  Advanced Bb3-F6, with narrower register policies in flexible exercises.
- `sax_technique`: a verified fixed written C#5/D5 coordination cell, ordinary
  slurs/staccato/accents and supported rhythm units. It has no audio validation
  of voicing, tonguing, fingering choice, response or intonation. Unsupported
  specialized requests currently refuse explicitly.

## Primary references and model differences

1. [Yamaha YAS-26 specifications](https://usa.yamaha.com/musical-instruments/brass-woodwinds/products/saxophones/yas-26/specs.html)
   list Front F auxiliary keywork. The page does not list a high-F-sharp key.
   Absence from a specification is not proof that every historical specimen has
   identical equipment; verify exact model/revision before assigning capability.
2. [Yamaha YAS-280 specifications](https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yas-280/specs.html)
   list high F-sharp and Front F. This supports model-specific keywork metadata,
   not a generic saxophone cap increase or a guarantee of player facility.
3. [Yamaha YSS-875EX/875EXHG specifications](https://usa.yamaha.com/products/musical_instruments/winds/saxophones/yss-875ex/specs.html)
   distinguish high-F-sharp/front-F from the HG versions' additional high-G key.
   A soprano subtype alone cannot safely infer that extra key.
4. [Yamaha YBS-62 II specifications](https://uk.yamaha.com/en/musical-instruments/brass-woodwinds/products/saxophones/ybs-62-03/specs.html)
   list low A, high F-sharp and Front F, with E-flat key identity. The current
   generic application range deliberately does not expose low A. The US site's
   newer YBS-62 table was inconsistent about key identity during this audit;
   cross-check model/revision/region rather than automatically importing it.
5. [SELMER Supreme alto specifications](https://www.selmer.fr/en-int/products/saxophone-alto-supreme)
   specify a low-B-flat/high-F-sharp range. This is model evidence, not evidence
   that the player's unspecified alto or an alternate fingering works that way.
6. [Woodwind Fingering Guide, lower altissimo table](https://www.wfg.woodwind.org/sax/sax_alt_4.html)
   includes source-attributed alternatives and instrument/dynamic qualifications.
   It is useful provenance for expert review; a fingering table alone does not
   establish the response, voicing prerequisite, intonation or reliable tempo of
   a generated exercise. No fingering recipes were copied into the application.
7. [Eugene Rousseau, Saxophone High Tones, publisher listing](https://www.halleonard.com/product/40163/saxophone-high-tones)
   confirms an authored resource on range extension. The listing and limited
   preview do not constitute a review of the complete pedagogical method.
   Obtain an authorized source and expert review before extracting any recipe.

These references were checked online during this audit. No purchase, billing
change or external message was made. Product specifications may change; retain
source URLs, retrieval date, exact model/region/revision and reviewed evidence.

## Proposed future capability schema

Keep written/sounding projection separate from physical keywork and technique.
A reviewed model profile should record exact horn identity/revision, physical
written endpoints, front-F/high-F-sharp/high-G/low-A availability where verified,
source provenance and confidence. A separate technique profile should record
supported target/register, prerequisites, reviewed fingering variants with
context and alternatives, teacher sign-off, and conservative practice limits.
Unknown capabilities should remain unknown, not be inferred from Advanced level.
The current generic profile remains the default unless a matching reviewed
profile is explicitly selected.

## Validation and implementation gates

- Resolve contradictory manufacturer data manually before profile activation.
- Verify each fingering/technique with a qualified player on the specified horn;
  document response, transition reliability, intonation and setup dependence.
- For overtone studies, distinguish the fingered fundamental from the intended
  sounding partial in the event model and notation; ordinary pitch events do
  not currently represent that relationship or verify its performance.
- For altissimo preparation, establish expert-reviewed prerequisites and a
  bounded progression separately from merely raising the MIDI range limit.
- For alternate fingerings, model key combinations, passage context and
  alternatives explicitly. Never derive them from a pitch-class lookup.
- Add independent concert/written/octave, range, notation, refusal, history,
  workspace and browser checks. Audio/tuner evidence should be identified as
  human validation unless an actual calibrated assessment system is added.

Likely risks: wrong model/revision, conflating comfort and physical ranges,
incorrect octave transposition, ambiguous fingering symbols, unsupported double
accidentals or notation, pedagogically unsuitable progression, and falsely
claiming that notation playback verifies saxophone performance.

Recommendation: first consolidate provenance and capability selection behind the
existing conservative adapter, without changing generators. A separately
approved teacher-reviewed pilot can then address register transitions or overtone
preparation. Altissimo and alternate-fingering generation require their own
approval, validated profiles and acceptance criteria.


## Capability-foundation follow-up

The local foundation (AMI_SAX_CAPABILITY_FOUNDATION_20261113.md) keeps the audited
engines unchanged, corrects the offset table identifier to _OFFSETS accessed via
exact_offset, and adds documentary metadata plus unimplemented-technique gates.
The US archived-model YBS-62II source at
https://usa.yamaha.com/products/musical_instruments/winds/saxophones/ybs-62_03/specs.html
was rechecked and explicitly identifies Eb, low A, high F# and front F. This does
not authorize importing contradictory data from the similarly named newer page.
The interactive fingering roadmap is planning only; no recipes were imported.
