# AMI proficiency-aware written note assistance - 2026-11-14

Local fix branch `fix/ami-level-note-names-20261114`. Based on combined UI/flute candidate `3edef0772f31854fdd44400d9146d237008d99f7`. No push, merge or deployment is authorized for this correction. Implementation and acceptance are complete locally. The integrated baseline differs from the tested combined source only by its acceptance receipt.

## Cause and presentation boundary

`musical_idea_engine.play_summary` produces bar-by-bar text from a composition; `musical_idea_knowledge` includes that presentation in practice steps. Other instructors also include inline written-note lists and per-note jazz timeline descriptions. These are explanatory transcriptions, not the canonical notes or harmonic timeline.

The fix retains canonical notes, ABC, timing, range, key, transposition, chord changes, fingering diagrams and technique instructions. It moves redundant transcription into an explicit written-note assistance view. Rows come from actual written events or the existing stored written projection: note spelling and octave, rests, duration, measure, beat and chord labels. New rows do not generate music, infer missing chords, truncate the exercise to eight names, or create musical history entries.

## Defaults and explicit control

The live selected `level` controls the default. Beginner shows note-name assistance; Intermediate and Advanced leave it off and display the staff. Complexity requested in a question does not replace the selected level as display authority. The visible Show note names checkbox can reveal or hide the assistance. Explicit preferences survive level changes within the session and use the existing account/workspace ownership purge.

Read-only requests include Show me the note names, Hide the note names, What are the notes in measure 4, and Explain the notes in this exercise. Measure queries filter the stored written events; an unavailable measure is reported without inventing notes. Show/hide and measure queries preserve music and Undo/Redo history. Legacy revisions and Undo/Redo derive assistance from their stored written version. Warmup queries resolve the current navigation view.

## Validation

Final focused acceptance: **39 passed**, including **20 new independent cases**, existing warmup navigation and submit integration. A subsequent conversation/ownership check passed **109 cases** after the exact new owner-scoped display snapshot key was added to the existing write-isolation allowlist; foreign-state assertions remain unchanged. The adapter regression verifies presentation rows survive filtered diagnostics and remain independent of later mutation.

Actual-app full workflow: **12 requests passed** at desktop and 390px, including Beginner scale/default level change, explicit show/hide and measure query, read-only explanation, Advanced jazz lick, saxophone slower revision/exact Undo/Redo, and an actual selected Blue Bossa / Kenny Dorham whole-song Intermediate guide exercise. A final native width adjustment fixed an observed label-clipping case; the final-source follow-up passed **four label/default observations** (Beginner/Intermediate at both widths), and the focused tests reran. The staff remains primary, with existing readable horizontal score scrolling. Earlier adapter and catalog-checker failures remain in evidence. The first full regression also remains: 3,938 passed, the nine baseline failures plus the expected new-key allowlist mismatch, and one skip. No production code changed to resolve that test-contract mismatch.

[Beginner assistance](note-name-display/mobile-beginner.png), [same scale with Intermediate default](note-name-display/mobile-intermediate.png), [Advanced jazz lick](note-name-display/mobile-advanced-jazz-lick.png), [Intermediate song-aware exercise](note-name-display/mobile-song-aware.png), [machine acceptance](note-name-display/acceptance.json). Images are actual viewport captures; full-workflow images precede only the final checkbox-width polish, while Beginner/Intermediate defaults are captured after that polish.

Final Python 3.12.8 full matched regression: **3,939 passed, exactly the same nine baseline failures and one environment skip, 3,116 passing subtests**, 11 warnings in **554.76 seconds** across 104 files. All **3,929 shared IDs retain their phase outcomes**, all **20 added cases pass**, with no missing IDs, collection errors, Python drift or changes to **2,163 frozen source files**. Pytest exits 1 for the existing failures; the strict baseline comparator exits 0. The exact failure ledger is included in machine acceptance. The baseline is the 103-file validated combined integration (3,919 passed, nine failed, one skipped), whose source is identical to remote integration `2313403a36e8867377f718524905a7a8df00df49`.

External evidence: `D:/AMIWorktrees/flexible-evidence-20261112/ami-note-display-*`; final full run uses `ami-note-display-regression-final.{json,log}`. Earlier failed runs, test data and source ledgers remain preserved. No paid API call, billing change or deployment was made.

## Limits

Older stored plans without a complete written event view may not provide assistance until a verified exercise is available; toggling visibility never reconstructs or regenerates their music. The adapter requires canonical written events, a verified structured written projection or an exact matching stored-plan score. It does not parse arbitrary free-form ABC or improvise note names from prose. A new score without verified event metadata clears stale assistance rather than borrowing names from an earlier score. Chord-scale rationale, scale collection definitions, brief note examples, fingering labels and meaningful technique prose remain visible; only redundant transcription is moved. The existing staff renderer and its internal horizontal scrolling remain unchanged.
