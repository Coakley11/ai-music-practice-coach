# AMI note-name and Stage F integration acceptance — 2026-11-14

The level-aware note-name milestone and gated saxophone Stage F foundation integrate without conflicts onto current dev `e41232060ad61e67cc904c1228d2c941906952af`. All twelve files from the three newer recorder-reliability commits remain byte-for-byte intact. The dirty shared C: workspace and other agents' worktrees/processes were preserved.

The note-name integration was normally pushed and verified remotely as `543863fb5d95bd9b62c5622f2d8a00aef03edb4c`. The combined tested Stage F merge is `f7d94f9ac7f1b6c4c242313be9c414e7f2b4a0fc`; this report is its documentation-only acceptance receipt. The exact remote SHA after its authorized publication is recorded in the external `ami-nf-current-remote-verification.json` and reported to the musician. No force push or deployment is used.

## Regression and isolation

Python 3.12.8, sequential execution, separate fresh data namespaces. Clean dev: **3,954 passed, nine failed, one skipped, 3,116 passing subtests** across 104 files. Combined: **3,999 passed, the same nine failures and skip, 3,116 passing subtests** across 106 files. All **3,964 shared IDs** match; **45 new cases pass**. No missing cases, collection errors or Python drift. The strict comparator includes unittest SUBFAILED entries as well as ordinary phase outcomes. Exact failure and skip IDs are in [acceptance.json](ami-note-stage-f-integration/acceptance.json).

The isolated note-name candidate passed **109** conversation/display/owner checks. The standalone Stage F candidate on the same latest baseline passed **398** instrument/fingering checks; the combined candidate passed the same **398**. After all tests and browsers, all **2,171** frozen combined Python/data/web files and **2,168** standalone Stage F files remained unchanged. Newer recorder shell/text/document files were checked separately through Git byte comparisons.

An initial uncontrolled run on the earlier dev head recorded one extra existing song-coach phrasing subtest failure: 21/8 bars without a breath exceeds its 5/2 limit. Fixed UUID inputs 63 and 86 reproduce identical failures and motifs on clean dev and candidate; forty other controlled inputs also match. No song-coach product or test source was changed. The refreshed baseline and candidate control only UUID input within the original composition fixture; every original assertion remains active. All failed logs and full reproduction evidence remain in the external evidence directory. A separate external comparison-log decoder was corrected for Windows CP1252 output; its failed log is retained too.

## Real browser acceptance

**51 real-app requests passed**, plus the newer recorder's actual asset-failure browser test using installed Chrome. Each server/context was isolated, resource-gated and closed after use. No paid API was called.

- Note-name workflow: 18 requests cover Beginner scale assistance, the same Intermediate score hidden, Advanced clean output, explicit show/hide at every level, exact measure requests, read-only Explain, exact Undo/Redo and an Intermediate whole-song exercise using the selected real Blue Bossa chart.
- Additional visual workflow: seven requests verify actual checkbox states at all three levels, four Beginner/Intermediate desktop/mobile default observations, full control labels and reachability of the last bars through the existing mobile horizontal score scroll region. Display-only actions preserve the stored music/history.
- Stage F: ten requests verify ordinary written D4–D5 half notes at 60 BPM, sounding F3–F4, four-second duration, exact history restoration and four unchanged specialized refusals. The octave thumb changes in this existing ordinary exercise; it is not an unchanged-fingering overtone drill.
- Beaming/navigation: eight requests and 24 native before/after conditions retain pitches/timing, conventional eighth/sixteenth beams, slurs, accents, navigation, Explain and dismiss/fresh-submit behavior.
- Four-instrument rendering: eight requests verify actual flute E4, clarinet E3, trumpet C4 and alto saxophone G5 staff positions and fingering SVGs, observed on desktop and mobile.

Actual captures: [Beginner mobile](ami-note-stage-f-integration/mobile-beginner.png), [Intermediate same scale](ami-note-stage-f-integration/mobile-intermediate.png), [last bars reached on mobile](ami-note-stage-f-integration/mobile-score-end.png), [Intermediate desktop](ami-note-stage-f-integration/desktop-intermediate.png), [native beaming fixture](ami-note-stage-f-integration/mobile-native-beaming-fixture.png), [clarinet mobile](ami-note-stage-f-integration/mobile-clarinet.png). The beaming comparison is explicitly a native ABCJS fixture; the other captures come from the real application. Wide scores retain the established accessible horizontal scroll on mobile.

## Musical boundaries

Note assistance remains presentation data derived from the actual written events; underlying notes, chord timing and score content are preserved. Intermediate/Advanced defaults hide redundant note lists, while explicit preferences remain owner-scoped. Stored legacy scores without a verified event view may still lack assistance until a verified exercise is available.

Stage F adds documentary, model-scoped capability metadata and a closed development gate. Specialized altissimo/alternate/overtone generation remains disabled. Automated checks do not establish teacher approval, specimen/setup response or physical-instrument validation. Existing ranges, ordinary fingerings and unsupported behavior are unchanged. No new public specialized solver was activated.

Adaptive Licks Slice 1 is a separate, local-only assignment after these integrations. No adaptive feature is included in this receipt; its publication requires separate approval. Whole-song harmonic cell adaptation remains a future bounded proposal.
