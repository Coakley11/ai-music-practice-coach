# Adaptive intervals, scales, licks and sequencing: audit and bounded proposal

Proposal only. No new lick/sequencing feature is implemented or authorized for integration. Inspected combined candidate 3edef0772f31854fdd44400d9146d237008d99f7. This work does not change the approved UI/flute integration or the gated saxophone Stage F scope.

| Capability | Existing implementation | Actual gap / proposed boundary |
| --- | --- | --- |
| Major/minor scales; thirds through sevenths | scale_engine scale spelling and interval-step maps; musical_idea_engine scale patterns; flexible_single and warmup_engine | Preserve diatonic scale membership. Add independent sixth-quality examples, explicit generic octaves and alternating intervals to the next parser/coverage audit. Do not treat every sixth as nine semitones. |
| Directions, rhythm, range, level | Existing request parsers, simple/complex pattern builders, verified player windows, exercise_followup and sax engines | Check exact NL examples and defaults before extending. Advanced patterns already change more than tempo. No broad profile widening. |
| Chord tones, chromatic approaches, enclosures, advanced jazz | warmup_chordline, warmup_song, sax_chart_intervals, jazz_engine, exercise_develop_* and exercise_span | Reuse supported harmonic rules and explicit limitations; chord-tone-only constraints must not silently acquire scale extensions. |
| Stored exercise identity and exact history | GeneratedExercise, conversation_state, warmup_plan, exercise_revision, selected-item revisions | Already implemented for supported owners. A reusable lick cell needs an explicit immutable identity and transformation contract within this architecture, not a new engine. |
| Diatonic sequencing | musical_idea_engine.generate_sequence uses the scale-pattern generator; exercise_followup.do_sequence restates a supported idea one degree up/down with the same rhythm | Already partial support. Whole-scale traversal of an arbitrary stored 1-2-3-5 cell, range endpoints and exact four-note cells require explicit validation. Existing one-degree restatement is not the complete requested traversal. |
| Moving a stored idea | exercise_followup.do_move and _moved_pitches; instrument adaptation and written projection | Movement already exists. Do not equate it with an arbitrary chromatic-key itinerary: half/whole steps, all twelve keys, fourth/fifth circles and explicit key lists need a separate bounded operation preserving semitone structure and spelling preferences. |
| Licks and song motifs | generate_lick and generate_lick_through_section already create motifs and adaptations; motif_meta records core bars/adaptations | Audit and implement exact 4/5/6 pitched-note cell counts independent of duration. Preserve the musician's cell across revisions rather than replacing it with a fresh template. |
| Song timeline and whole form | warmup_song, harmonic timeline, exercise_span, catalog chart/section selection; split-bar rhythm events | Reuse the authoritative timeline. Cell scheduling across short chord spans needs an explicit fit/continuation/rest policy; no invented chords, compressed cells or unlabeled chord-scale assumptions. |
| Conventional beaming | Accepted shared AMI serializer change | Reuse it and retain tuplets/broken-rhythm/unknown-syntax limits. |

## Catalog identity findings

The actual catalog contains Say / John Mayer (trusted core), Blue Bossa / Kenny Dorham, and All the Things You Are with both Jazz Standard and Jerome Kern identities. Say has a real curated chart with split-measure/pushed changes and named sections; do not replace it with a guessed progression. Blue Bossa has a curated 16-bar chart; All the Things You Are has a curated 36-bar chart pack. These are repository identities and chart descriptions, not a claim that every requested section name exists. Ask for selection when title/identity/section is ambiguous, read the current chart and Practice Key, and preserve missing-chart refusals.

## Bounded functional probes on integrated source

API-blocked Python 3.12.8 probes used an explicit Advanced flute / G Practice Key context with **no selected song and no synthetic named chart**. These observations supplement the source audit; they are not end-to-end acceptance of a future feature.

| Request | Observed typed AMI path |
| --- | --- |
| Sixths in G major | Legacy ScalePracticeSolver emitted 28 pitches. Diatonic sixth qualities vary, but the raw ABC starts `g' e''` and extends beyond the existing verified flute range. This legacy range/notation path requires a separate bounded correction and native validation. |
| Ascending thirds / exercise in octaves | The typed route returned no response; the legacy Command Center fallback is not established by this probe. Do not label these exact requests complete. |
| Four-note G-major lick | 32 actual pitched notes; exact four-note count is not honored. |
| Five-note jazz lick | 32 actual pitched notes; exact five-note count is not honored. |
| Six-note blues lick | Five actual pitched notes; exact six-note count is not honored. |
| Four-note lick through the whole scale | A complete-octave/range refusal, rather than the requested preserved-cell traversal. |
| All twelve keys / circle of fourths | No completed itinerary: typed fallback/no working-exercise response. |

Retained evidence: `adaptive-ami-functional-audit.json`, with actual ABC and counts, and its API-blocked driver/log in the evidence root. Existing bounded engine capabilities do not establish that every bare natural-language request reaches those verified paths.

## Proposed next approval slices

0. **Bare-request routing and range:** bring the explicit interval examples into an existing verified generator, with independent diatonic quality/range/native-notation fixtures. Preserve useful refusals; do not silently claim the legacy path is range-verified.
1. **Cell identity and exact counts:** one four-note diatonic lick in one explicit key, with immutable degree and semitone representations, exact pitched-note count, duration/rest metadata and existing history. Independent G-major 1-2-3-5 = G-A-B-D oracle.
2. **Full diatonic traversal:** reuse scale spelling and range validation. Literal subsequent cells A-B-C-E, B-C-D-F#, C-D-E-G; ascending, descending and up/down endpoints without hidden chromatic transposition.
3. **Key itinerary:** separate chromatic operation preserving cell semitone intervals; explicit short key list first, then twelve-key and circles. Read the existing Advanced Playback enharmonic preference; verify staff signatures and each instrument's written/sounding mapping.
4. **Harmonic scheduling:** adapt the same cell across a selected real chart and section using supported, labeled chord-scale rules. Begin with one explicitly selected Blue Bossa chart and one split-measure fixture; add selected All the Things You Are and whole form only after fit and target-alignment proofs. Chord-tone-only impossibilities return a clear limitation.

Each slice requires exact cell identity after conversational revisions, independent interval/count/degree/spelling/timeline fixtures, timing and range checks, read-only Explain, exact Undo/Redo, owner isolation, and actual desktop/390px native notation. Publish or merge only after separate approval. This document is a source audit and proposal; the complete new conversational examples have not yet been accepted as working features.
