# AMI Adaptive Licks Slice 1 — local acceptance, 14 November 2026

Implemented on `feature/ami-adaptive-licks-slice1-20261114`, based on `f8a5b43ced70e6fb59b51d8c8da27695e5ca12b5`. This feature is local only: no push, merge or deployment is authorized or performed.

## Approved integrations completed

Normal, ordered pushes preserved the newer recorder work at `e41232060ad61e67cc904c1228d2c941906952af` and all twelve affected files byte for byte:

- Note-name integration: `543863fb5d95bd9b62c5622f2d8a00aef03edb4c`, exact remote head verified after push.
- Saxophone Stage F plus acceptance receipt: `f8a5b43ced70e6fb59b51d8c8da27695e5ca12b5`, exact remote head verified after push. Tested music merge was `f7d94f9ac7f1b6c4c242313be9c414e7f2b4a0fc`; the receipt adds documentation only.

Combined integration: 3,999 passed, the same nine failures and one skip as the clean recorder baseline (3,954 passed); 45 new passes, 3,964 shared IDs unchanged. Instrument gates passed 398 cases, isolated note gate 109, installed-Chrome recorder asset-failure check one. Real-app integration verification completed 51 requests, with notation, note display, fingering and desktop/mobile checks. Stage F is capability metadata and a closed development foundation; ordinary D4/D5 thumb changes do not establish overtone support or physical teacher validation. See [integration receipt](AMI_NOTE_STAGE_F_INTEGRATION_20261114.md).

## Implementation and reuse

`music_coach_ami/adaptive_cells.py` adds exact-count cells and bounded sequencing through the existing flexible-single route. It reuses the existing Note/Built types, profile ranges, serializer, renderer, verifier, interval definitions, key-cycle helpers, shared package and exercise history. No new pitch engine, transport, dependencies, profile tables or pipeline implementation was introduced. Existing specialized instrument owners retain priority for their established requests; bare legacy interval handling is corrected after those owners.

Counts mean pitched attacks, including repetitions; rests and duration do not change the count. Supported counts are 1–12 when the entire cell fits. Diatonic sequencing preserves degrees; literal key transposition preserves chromatic offsets. Key changes use inline ABC signatures and the live Advanced Playback enharmonic preferences without changing playback or cycling settings. A whole cell may move an octave to fit, with disclosure; individual pitches are never silently clamped and keys are not dropped. Infeasible requests refuse atomically.

Actual public-pipeline examples, independently decoded and matched exactly to native browser ABC:

| Request | Written notes, Flute Intermediate, G |
|---|---|
| Four-note lick | G4 A4 B4 D5 |
| Five-note jazz lick | G4 B4 D5 F#5 A5 |
| Six-note blues lick | G4 Bb4 C5 Db5 D5 F5 |

The jazz cell is a ninth-arpeggio pattern. Seven-degree movement of the four-note seed begins G–A–B–D, A–B–C–E, B–C–D–F#, C–D–E–G. Ascending, descending and up/down work; whole-scale traversal includes the octave tonic. Changing to thirds changes the degree pattern while retaining the requested count.

Literal half-step traversal: G, Ab, A, Bb, B, C, Db, D, Eb, E, F, F#. Whole steps: G, A, B, Db, Eb, F (six distinct keys). Fourths: G, C, F, Bb, Eb, Ab, Db, F#, B, E, A, D. Explicit key lists remain a separate operation. These spellings reflect the default Playback preferences; supported practical enharmonic substitutions are disclosed.

Bare sixths in G now use the actual flute register G4–D6, with coherent scale-degree pairs and a return. Thirds, fourths, fifths, sixths and octaves use existing interval definitions. Beginner coverage is bounded and stated; an explicitly requested complete traversal that cannot fit refuses rather than truncating. The actual selected proficiency controls range, not exercise complexity. Unknown levels refuse. Instrument projection tests cover flute and piano at zero offset, soprano/clarinet/trumpet +2 written semitones, alto +9, tenor +14, baritone +21 and bass +12, including octave-sensitive enharmonics.

## Conversation, display and state

Musical revisions retain exact count, timing and selected-instrument context unless explicitly changed. The original cell is a stored, nonrecursive snapshot. “Show first lick” selects a read-only view; Explain describes that view without rebuilding music or adding history. Undo/Redo restore the exact saved versions. Original-pitch recall can retain subsequent rhythm and articulation choices. Tests forbid rebuilding during read-only original review.

Sidebar instrument, Practice Key, cycle and transport settings are unchanged. State tests allow only the pre-existing diagnostic workflow read counter to increment; stored blobs, writes and revisions remain exact. A UI level change alone does not change notes or timing; the next musical revision uses the selected level/range.

The integrated note-name policy remains authoritative: Beginner assistance, Intermediate/Advanced hidden by default, explicit show/hide preserved, read-only controls without musical history. Staff, useful instructions and fingering support remain. Intermediate/Advanced do not acquire redundant bar-by-bar text lists. Shared notation retains beam grouping and per-cell slurs; slurs do not cross cells.

## Verification

Python 3.12.8. Final frozen full gate: **4,065 passed, same nine failures, same one skip, 3,116 passing subtests**, 19 warnings, 830.36 seconds. All **66 new cases passed**. Against the validated integrated baseline, all 4,009 shared IDs are unchanged. Against the same clean recorder baseline, all 3,964 shared IDs are unchanged and 111 additional cases pass. No collection errors, new failures, changed failure/subfailure ledger, skip drift or Python drift. All 2,174 feature source hashes and all 2,171 integrated source hashes remain unchanged after verification. Pytest exits 1 for the existing failures; strict differential comparison exits 0.

An existing UUID-dependent composition-phrasing intermittent failure was reproduced on the clean baseline (seeds 63 and 86) with identical candidate output. Both full gates use the same external deterministic UUID input control around the original composition fixture, keeping every original assertion enabled. Product and test sources were not altered to hide that intermittency. Raw uncontrolled failures and reproduction proof remain in the external evidence directory.

Permanent tests include literal pitches/counts, independent ABC event/timing decoding, diatonic movement, each key traversal, original recall, refusal atomicity, selected level, all sax subtypes and other instrument projections, transposition preferences, slurs, history, note controls and existing specialized gates.

Real production app: **32 workflow requests plus six final explanation requests passed**. Native ABCJS audio events independently checked written pitches, onset and duration; warnings zero. Native beam/slur checks passed. The final four-note, jazz, blues and interval ABC is identical to the 32-request browser evidence after explanatory-copy polishing. Paid API calls were blocked throughout.

Actual desktop/mobile captures are included below. Mobile scores use the existing internal scrolling for long or wide music; twelve keys do not fit simultaneously on one phone. The last-key target was measured at y=398–406 within the 460px iframe after scrolling to y=810 (content height 1,270). The four-note and jazz mobile captures have the sidebar overlaying the score and are retained only in external raw evidence; they are not presented as unobstructed layout proof. The included final-key mobile capture has the sidebar closed. Existing browser retries and initial fixture-assumption failures are preserved externally; the successful final gates are identified explicitly.

- [Desktop explained four-note cell](ami-adaptive-licks-slice1/desktop-explained-four-note-cell.png)
- [Mobile final key reached, sidebar closed](ami-adaptive-licks-slice1/mobile-last-key-reachable.png)
- [Mobile five-note jazz cell](ami-adaptive-licks-slice1/five-note-jazz-mobile.png)
- [Range-checked sixths](ami-adaptive-licks-slice1/range-checked-sixths-desktop.png)
- [Actual example data and ABC](ami-adaptive-licks-slice1/actual-examples.json)
- [Strict dual-baseline comparison, including existing failure IDs](ami-adaptive-licks-slice1/regression-comparison.json)
- [Native staff verification](ami-adaptive-licks-slice1/native-acceptance.json)
- [Final explanation and mobile reachability](ami-adaptive-licks-slice1/final-explain-acceptance.json)

Raw logs, full per-request state records, freezes and UUID proof are retained at `D:/AMIWorktrees/flexible-evidence-20261112`. Owned browsers and servers were closed; unrelated agents' work and the dirty original C: checkout were not modified.

## Limits and next slice

Slice 1 covers the registered major/natural-minor and minor-blues cells, straight whole/half/quarter/eighth/sixteenth values and per-cell slurs. Unsupported custom ties, dotted rhythms, tuplets, swing, custom rest patterns, other modes or hand-specific instructions explicitly refuse. Arbitrary recorded/notated motif import is not added. Complete range feasibility remains mandatory, including when a chromatic sequence requires disclosed whole-cell octave repositioning. The existing writer may substitute practical keys for theoretical spellings. Existing advanced jazz engines remain in place.

Whole-song harmonic adaptation is not implemented. [Slice 2 proposal](AMI_ADAPTIVE_LICKS_SLICE_2_PROPOSAL_20261114.md) defines a separate approval boundary around authoritative chart snapshots, chord timing, adaptation policies and required validation. No feature publication or deployment is part of this milestone.
