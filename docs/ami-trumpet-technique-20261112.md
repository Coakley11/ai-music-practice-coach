# Local Bb trumpet technique milestone

## Flute/clarinet integration

Fetched dev at f40f2839. A clean isolated integration candidate at 2a0474b2 preserved that ancestry and excluded every untracked runtime trace. Final regression: 1,950 passed, 4 existing failures, 289 subtests; exact comparison with the unchanged f40f2839 baseline: 1,917 shared IDs and zero changed outcomes. Two obsolete clarinet refusal cases had been replaced by supported musical tests. Additional Mission handoff/catalog/isolation checks passed 14/14 on both baseline and candidate. All 26 real-app flute/clarinet checks passed again. The eight unchanged expensive Slice 2b song-oracle matrix cases remained covered by their prior full pass and were deselected in this surrounding regression run.

A normal non-force push advanced origin/dev to **2a0474b2170a325bc6f4922125d4f9c7969c12f2**; fetch and ls-remote verified it. No deployment occurred. The four known baseline failures are the two custom-progression context IDs in test_backing_context.py, refresh-restores-custom in test_backing_handoff_authority.py, and missing ami_insight metadata in test_music_canonical_insight_submit.py. None was introduced by this integration. Evidence: fc-integration-final.json, fc-integration-comparison.json, fc-missions-baseline/candidate.json and fc-integration-browser/parser results under D:/AMIWorktrees/flexible-evidence-20261112.

## Trumpet branch and architecture

Local branch: feature/ami-trumpet-20261112; worktree D:/AMIWorktrees/trumpet-technique-20261112; base 2a0474b2. This milestone is authorized for a local commit only.

trumpet_technique.py is a bounded deterministic adapter before the existing standalone instrument adapter. It uses the existing Player, canonical context/Practice Focus, shared package/render/verifier path and account/workspace-scoped warmup history. It does not add a competing profile/history system or call a model. Fixed harmonic drills have their own intent; song/span and explicit scale-pattern ownership is retained. Existing flute, clarinet, saxophone, arpeggio, warmup and song routes remain in place.

## Profile and authoritative partial audit

The existing trumpet profile is standard **Bb trumpet**, written two semitones above sounding pitch. Overall written range: MIDI54-84 (F#3-C6). Existing level windows are Beginner58-74, Intermediate55-79 and Advanced54-84. The new drills never expand those windows. Other trumpet types are not silently treated as Bb.

Audited [Yamaha harmonic-series diagrams](https://www.yamaha.com/en/musical_instrument_guide/trumpet/mechanism/mechanism002.html) establish the three supported fixed valve settings. Targets for partials **2,3,4,5,6,8** are:

| Fixed setting | Written target pitches |
|---|---|
| Open | C4, G4, C5, E5, G5, C6 |
| Valve 1 pressed | Bb3, F4, Bb4, D5, F5, Bb5 |
| Valve 2 pressed | B3, F#4, B4, D#5, F#5, B5 |

The source's pedal/fundamental region and natural seventh are not enabled here. Valve 1 lowers the tube's series by a tone; valve 2 by a semitone. These are charted tempered targets, not a claim that acoustic partials are perfectly in tune. Intonation/slide corrections require individual listening. The original three manufacturer diagrams were visually inspected and retained in trumpet-reference outside the repository. No chart image was copied into the product.

Beginner selection is capped at partials 2-4, with two adjacent partials by default. Intermediate and Advanced use the larger audited set only where their level window permits it. Low/middle/upper placement means a subset of this setting's verified series, not access to every physical trumpet note. The subset does not include the instrument's lowest valve combinations.

## Implemented exercises

- A single lip-slur request returns one short stored drill, with notated phrase groups and full-bar breath rests, not a ten-minute routine. Beginner open C4-G4 sounds Bb3-F4. Valve-2 B3-F#4 sounds A3-E4; valve-1 Bb3-F4 sounds Ab3-Eb4.
- Plain ascending/descending exercises use real ordered partial changes. Advanced finger-busters use changing skip/permutation patterns over the available series, sixteenths and conservative initial tempo, rather than a renamed scale. Open Advanced targets can include C6 only within its modeled window.
- Fixed-valve flexibility and smooth-without-valve-change requests use the same harmonic constraints. The response names the held valve setting, written pitches, sounding offset, partial numbers, style, tempo and actual duration.
- Upper-register preparation is a short three-stage warmup: low pair, middle pair and level-appropriate upper preparation, each separated by breath rests. It does not claim to extend a player's range. A generic complete trumpet warmup remains on the existing multi-exercise Adaptive Warmups route. Duration-driven harmonic routines remain unsupported.
- Slurred phrases and slurred pairs carry actual notation groups. Tongued/staccato/tenuto/accent variations preserve pitches but are explicitly labelled fixed-valve tongued drills; their score does not falsely retain lip-slur markings.

How-to text requests comfortable tone, steady playing and all notated rests, and instructs the player to stop/rest if effort increases. No mouthpiece-pressure, tension, embouchure diagnosis or unsupported range-development instruction is generated.

## Conversational contract

Easier/harder, lower/higher, another partial, ascending/descending, a different verified valve, note values/BPM, harder rhythm, tonguing/slur variations and explicit articulation are supported within the same stored exercise. Valve changes retain a valid partial relationship and rebuild exact written/sounding notes. Rhythm-only/articulation-only edits preserve pitches and valve selection. Unsupported valve settings, partial 7, pedals, unverified trumpet types, incompatible instrument changes or out-of-window revisions preserve the complete snapshot and history. Explain describes fixed-tube harmonic work and the current slur/tongued style without creating a version. Undo/Redo restore exact plans, including note order, valve, partials, rhythm, staff, slur groups and tempo.

Explicit Bb-trumpet and level requests take priority over the sidebar without editing unrelated settings. Otherwise the selected instrument and proficiency apply. Tone focus supplies sustained default note values; explicit rhythm overrides that default. An explicit lip-slur request takes precedence over generic articulation-family preference.

## Independent validation and acceptance

Python is exactly 3.12.8 in the existing isolated venv with unchanged declared dependencies. The baseline is the exact clean integration candidate 2a0474b2 just validated and pushed to dev, recorded in fc-integration-final.json.

Broader local regression: **1,993 passed, 4 unchanged baseline failures, 289 subtests**, 8 unchanged expensive matrix cases deselected. Exact comparison: **1,953 shared IDs, zero changed outcomes, zero introduced failing IDs**. The only baseline-only ID is the now-obsolete blanket refusal for a trumpet open-valve lip slur; it is replaced by positive and negative musical tests. See trumpet-candidate.json and trumpet-comparison.json. The already-passed full Slice 2b matrix is preserved as prior evidence rather than redundantly rerun.

Final narrow refinements made direction changes affect real note order, selected the explicit Beginner middle register, and accepted hyphenated open-valve wording. Final focused verification after these refinements: **124 passed** in 10.31 seconds, comprising 48 trumpet cases, 37 flute/clarinet cases and 39 retained flexible-exercise cases. The broader run precedes these narrow refinements; it is not presented as a repeated monolithic run of the final source. See trumpet-final-focused-v2.json.

The independent test validator in tests/trumpet_oracle.py does not import the production harmonic table. It computes nearest tempered targets from harmonic frequency ratios (partials 2,3,4,5,6,8), independently applied valve shifts and fixed audited level windows; it also reads ABC, verifies written-minus-sounding offset, and counts real slur groups. A level/setting/direction matrix passes. Negative mutations of notes, valve setting, sounding offset, slur marks and range are detected. Permanent tests cover all user example requests, actual descending reversal, low/middle/upper placement, another partial, safer easier transitions, rhythm-only preservation, tongued/slur labels, three-stage preparation versus ordinary full warmup, unsupported settings, complete snapshot restoration and account/workspace ownership changes.

Real-app acceptance: **23/23 passed**, recorded in trumpet-browser/results.json (22 main cases) and trumpet-browser-probe/results.json (one final hyphenated request). Each run starts a newly verified loopback-only real Streamlit app and an isolated headless Chrome, refuses an occupied port, keeps isolated data, blocks paid transport and observes the actual pipeline/card/ABCJS result without seeding state or replacing solvers. Actual drawn staff heads match stored scientific octaves, and independent ABC parsing matches written pitches. ABCJS recognizes matching slur starts/ends for slurred variants and none for tongued variants. Beginner open C4-G4 slur curves were visually inspected in the captured score.

Browser checks include all six supplied trumpet requests, adding a partial, descending real notes, lower placement, valve 1/2 selection, harder rhythm, easier level, read-only Explain, staccato versus paired slurs, exact Undo/Redo, upper-preparation stages, ordinary full warmup routing, explicit trumpet override while flute remains globally selected, and unsupported-valve snapshot preservation. All paired written/sounding notes keep the exact two-semitone offset. Scope is tested through production session mappings, not live cloud multi-account authentication. Audio was not auditioned.

All evidence remains under D:/AMIWorktrees/flexible-evidence-20261112, with logs, backend snapshots, actual card text/screenshots, renderer observations and server identities. Heavy browser/pytest jobs ran sequentially; RAM, disk and Git state were monitored. Only this session's completed browser/server trees were closed. Other worktrees, runtime traces, backups and Cursor databases were preserved. No paid API call or billing/authentication change occurred. The trumpet milestone remains local and has not been pushed, merged or deployed.

## Remaining limits and next bass milestone

Only open, valve 1 and valve 2 are enabled. No other combination, alternate fingering, pedal, partial 7, altissimo or non-Bb trumpet support is claimed. Exact acoustic intonation, slide motion, embouchure instruction, triplets/swing and timed harmonic routines are outside this bounded milestone. Valid modeled notes do not establish that a given musician can play them comfortably; the application does not diagnose performance and audio playback was not auditioned.

Bass remains separate and unimplemented. Recommended next bounded stage: reconcile a standard four-string E-A-D-G profile with existing notation and written/sounding octave conventions; independently audit sounding open-string pitches, range and fretboard tuning; then add conservative position-bound bass-register/octave/coordination exercises with explicit string/fret feasibility, limited shifts and exact history. Validate real bass-clef staff positions and octave sounding against an independent oracle before enabling generation. Expanded tunings, five/six-string instruments and technique-specific claims need separate capabilities. Saxophone register/articulation expansion remains a later distinct milestone.
