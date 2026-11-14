# AMI navigation icons and conventional beaming - 2026-11-14

## Scope and publication status

Separate local branch `fix/ami-navigation-beaming-20261114`, based on integrated dev `d3f700da51c6ad64f77022ca0a80090005a961aa`. This correction does not contain or merge Stage E flute. Neither feature is pushed, merged into dev or deployed. Approval is required before either integration. The original C: worktree and its other work remain untouched.

## Buttons and actual layout

Added existing-family Unicode icons alongside the visible Previous exercise, Next exercise, Whole warmup and Dismiss insight labels, plus the comparable Open full analysis link. Mission actions already use their existing mission flag. Existing keys and actions are preserved. The actual browser exercised Next twice, Previous, Whole warmup, read-only Explain, dismissal and a fresh Explain without changing the stored plan or history.

The navigation buttons measured 40px high at both 1440px desktop and 390px mobile: desktop widths 305px, mobile widths 334px with native stacking. Labels and icons fit without clipping or page overflow. No sizing CSS changes were necessary.

[Desktop navigation](ami-notation-polish/desktop-navigation.png), [390px navigation](ami-notation-polish/mobile-navigation.png), [dismiss button](ami-notation-polish/dismiss-button.png).

## Root cause and shared correction

The canonical event durations were correct. The shared AMI ABC writer separated every short-note token with a space in simple meters, so native ABCJS rendered individual flags. This is a serialization/separator issue, not a canonical rhythm or renderer defect. The corrected `_abc_beam_within_measure` computes exact rational metrical positions and delegates grouping to the existing Composition `join_abc_tokens_with_beams` helper. There is no competing notation engine or renderer option change.

Quarter pulses group two eighths or four sixteenths in the covered simple meters; compound meters use dotted-quarter pulses. Mixed eighth/sixteenth values share a beat, rests and chord-label boundaries interrupt beams, and beat-crossing syncopations do not get joined across that beat. Slurs and articulation decorations remain on their original notes. Canonical accent `!>!` is stripped only from the temporary timing parser before checking for opaque broken-rhythm syntax, so its greater-than sign does not accidentally disable grouping. Serialized accent tokens themselves remain unchanged.

Only separator whitespace changes: pitches, octaves, durations, rests, bar totals, timing, tempo, slurs and articulation are retained. Literal fixture expectations, canonical-event immutability checks and independent native ABCJS before/after event comparisons verify this.

## Actual native before/after evidence

These images contain actual ABCJS native SVG/DOM captured at the measured app iframe width. A temporary clean view removes Streamlit overlay chrome for inspection; it does not reconstruct music or change note styles. Raw captures and native beam/event observations remain in the external evidence folder. Optional ABCJS classes are enabled only in isolated proof views; production options remain unchanged.

- [Desktop eighths](ami-notation-polish/desktop-eight-eighths-before-after.png): four conventional two-note groups in 4/4.
- [390px sixteenths](ami-notation-polish/mobile-four-sixteenths-before-after.png): one four-note double beam.
- [390px slur and double beam](ami-notation-polish/mobile-slur-and-double-beam-before-after.png): slur and beams coexist.
- [Desktop mixed values](ami-notation-polish/desktop-mixed-before-after.png): eighth/sixteenth values remain within beat boundaries.

Twelve independent patterns were verified at both widths (24 before/after conditions): eighths, sixteenths, mixed values, beat boundaries, rests, slurs, canonical accents, 6/8, 3/4, quarters and syncopated crossings. Native pitched-index beam membership, beam levels/SVG geometry and identical before/after events were checked. Actual generated scale, arpeggio, accented saxophone sixteenths, slur revision, articulation warmup and catalog-linked jazz anticipation scores also passed at both widths. Existing internal horizontal score scrolling remains available rather than shrinking notation below readable size.

## Regression acceptance

Final Python 3.12.8 matched comparison **passed**: **3,800 passed, exactly the same nine baseline failures, 3,116 passing subtests**, 11 warnings in **620.19 seconds** across 100 files. All **3,792 shared IDs retained their phase outcomes**, all **17 new cases passed**, with no missing IDs or collection errors and no changes to **204 distinct frozen source files**. The pytest exit is 1 because the nine baseline failures persist; the strict comparison exits 0. The full nine-failure ledger is recorded in the acceptance JSON.

The baseline provenance is explicit: the prior 98-file full run on the clean Clarinet integration plus 19 unchanged existing shared-meter tests run separately on clean integrated dev, under the same Python 3.12.8. This is not presented as one combined baseline process. New independent beaming fixtures add 17 candidate cases. Two existing assertions were updated solely for the intentionally changed ABC whitespace: the staccato/slur assertion and the 24-case legacy scale golden comparison. Original golden fixtures are unchanged; the latter still requires exact headers, identical line structure and every non-space musical token, plus exact practice instructions and answer prefix. Notes, slur and accent assertions remain. The affected scale and beaming modules passed 232 tests before the final full rerun.

Earlier incomplete browser checker runs, the intermediate whitespace-assertion failure and the first full run (3,788 passed, 21 failed, with 12 legacy beam-spacing mismatches) are retained in external evidence as pre-golden files. Application source did not change after the completed browser gate; only the legacy spacing assertion changed. Final acceptance uses the completed navigation-synchronized run and the final matched regression. No paid Anthropic calls or billing changes were made.

## Limits and review boundary

Explicit tuplets, broken-rhythm syntax and unrecognized tokens retain conservative original spacing rather than inferring unsupported timing. Unusual/additive meter grouping requires further explicit metadata and review. This correction covers the shared AMI serializer and its generated outputs; it is not a claim that every unrelated ABC entry point now infers arbitrary grouping. Composition's existing helper and its musical data are unchanged. No additional instrument, fingering, altissimo or overtone feature is implemented here.

External evidence: `D:/AMIWorktrees/flexible-evidence-20261112/ami-notation-polish-*`, including browser cases/results, source freeze and matched regression comparison. The compact [acceptance record](ami-notation-polish/acceptance.json) accompanies the review images.
