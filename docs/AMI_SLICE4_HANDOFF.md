# AMI Slice 4 handoff (guide-tone exercises across harmonic spans)

Branch `feature/ami-span-guide-tones`, worktree `C:/tmp/ai-music-ami4`, based on `origin/dev` `a81e1a85`.
Not pushed, not merged. Read this before touching anything.

## Status of the AMI slices
| Slice | State |
|---|---|
| 1 Bridge to Mission/Motif vocabulary (pentatonic, blues, chord tones, guide tones), canonical `GeneratedExercise` | complete, on `origin/dev` |
| 2 Follow-ups (easier/harder/variation/same rhythm/same notes/move/sequence) | complete, on `origin/dev` |
| 3 Articulation + dynamics | complete, on `origin/dev` (notation only; the AMI card has no audio player) |
| 4 Guide-tone exercises across 2-/3-chord spans + Open in Missions | implemented and tested, **one open browser defect** (below); not integrated |
| 5 Other span vocabularies | not started |
| 6 Span follow-ups | not started |
| 7 Motif developed through a progression | not started |
| 8 Playback | not started |

## What Slice 4 does
Request ("guide-tone line over the next two chords", "voice leading through this ii-V-I", "connect the thirds and sevenths")
-> `exercise_intent.detect_span_request` (span length / relationship / cue) -> `exercise_span.resolve_span` (the same spans the
Missions page offers, via `improvisation_intelligence_ui.resolve_span_options`) -> `mission_span_engine.generate_mission_span_example(
"guide_tone_voice_leading")` -> AMI's own checks (`span_checks`: guide tone on beat 1 of every chord, arrival notes move by a step
or stay, chord assignment, span length) -> canonical `GeneratedExercise` (`chords`, `chord_assignment`) -> card (staff, Guitar TAB
for guitar, explanation read from the engine's evidence) -> **Open in Missions** (`open_exercise_in_missions`) stages the exact
example; nothing is regenerated.

Stated limits (never approximated): other vocabularies across a numbered span; transposing instruments and capo/shape keys
(concert pitch only; written spelling needs a chord-aware respell); a named key that differs from the Practice Key; follow-ups on a
span exercise; articulation/dynamics on a span exercise; the player's level override. Spans are only those the Missions page
offers at the player's level. If the 2/3 chords at the anchor are not a guide-tone span (for example Autumn Leaves in Bm starts
Bm -> Em7), AMI says so and names spans where it does fit.

## Reuse these, do not duplicate
`harmonic_span_analyzer` (spans), `mission_span_engine` (Missions, validation, `generate_mission_span_example`),
`span_motif_engine` (`generate_span_motif`, `develop_span_motif`, `project_span_motif`), `improvisation_motif`
(`build_motif_abc`, `build_motif_guitar_tab`, `chord_tone_names`), `mission_span_ui` / `mission_span_backing` (page, Backing handoff),
`improvisation_missions` (single-chord Missions, `close_active_mission_example`), `music_coach_ami/exercise_*` (intent, context,
bridge, follow-up, expression). Key authority: Slice 1 rules in `exercise_context`. Mission authority now also counts a generated span
example (`improv_span_mission.example`) as deliberate engagement.

## Files changed (vs `origin/dev` a81e1a85)
`music_coach_ami/exercise_span.py` (new), `exercise_intent.py`, `exercise_model.py` (span fields), `exercise_bridge.py` (dispatch),
`exercise_context.py` (span engagement), `exercise_followup.py` (span guard), `musical_idea_knowledge.py` (gate), `entities.py`
("voice leading" is no longer the Voice instrument), `submit_integration.py` + `applied_math_return_insight.py` (Open in Missions button),
`improvisation_intelligence_ui.py` (`resolve_span_options` extracted from `_render_span_picker`; one-shot AMI span pick by chords+section),
`mission_span_ui.py` (`span_mission_context`, `adopt_ami_example_span_id`, adoption of an AMI example),
`tests/test_ami_span_guide_tones.py` (35 tests).

## Tests
`python -m pytest tests/test_ami_*.py tests/test_mc3_multichord_missions.py tests/test_mc32_corrections.py
tests/test_mission_example_key_change_and_returns.py` -> 208 passed. Browser proofs (scratchpad, not in the repo):
`s4_e2e.py` against `serve_plain.sh` servers. Piano, 3 chords (ii-V-I): 19/19. Guitar, 3 chords: 24/25.

## Known failures and the open defect
* **Open defect (Guitar, found last):** AMI -> Open in Missions -> Backing -> change Practice Key up two semitones -> Return to Mission:
  the notes and staff are transposed, but the Missions page "Guitar TAB" under the staff still shows the *original* frets
  (6,5,3...) while Backing shows the right ones (8,7,5...). Piano is clean. The page-generated example passed the same check on the
  earlier branch (key moves down), so first find out whether this is (a) specific to an upward move, or (b) specific to the AMI-opened
  example (suspect the adoption branch in `mission_span_ui.render_span_missions` / `span_example_projection`, and what
  `build_motif_guitar_tab(shown)` receives). Repro: `s4_e2e.py "Give me a guide-tone pattern through the next three chords." Guitar`.
  Do not hide it; fix or document before integration.
* Not run on this branch: the full suite. Known pre-existing failures on `origin/dev` (6 tests, intermittent collection errors) are
  separate follow-up work.
* Known and out of scope: D7 third shows as G-flat in Gm because `project_span_motif` respells by key signature, not chord
  (examples generated directly in Gm spell F-sharp). Also an `Ab` can appear where `G#` would be expected in an engine-made
  chromatic approach note.
* Uncommitted: nothing after the checkpoint commit. Stray `scripts/evidence-creative-backing/*` files are generated by the app during
  runs; never `git add -A`.

## Next slice (5): other vocabularies across spans (needs Daniel's approval first)
Map existing span Missions to AMI vocabulary instead of writing generators: chord tones each chord (`chord_tones_each_chord`),
target each change / resolve to the third (`target_each_change`, `resolve_to_third`), approach and enclosure (`approach_next_chord`,
`enclose_next_target`; single-chord equivalents exist too), ii-V-I resolution (`ii_v_i_resolution`), pentatonic per chord
(`pentatonic_per_chord`). Blues across a span stays unsupported (the engine marks it single-chord-only). Add parser phrases, replace
`span_unsupported`, reuse `resolve_span`/`generate_span_example`/`build_span_exercise` (generalise the vocabulary id and the guide-tone
specific checks) and the same Open in Missions path (the Mission id must be selectable on the span page).

## Conflicts to expect
Composition Studio (AI Lyrics, activation) touches `composition_studio_page.py` only: no overlap. Backing/Mission navigation work
touches `improvisation_missions.py`, `music_workflow_pending_creative_return.py`, `backing_*`: Slice 4 does not edit them, but relies on
`close_active_mission_example` (span example included) and `mission_span_backing`. `improvisation_intelligence_ui.py`
and `mission_span_ui.py` are shared hot files: merge carefully and rerun the span Missions tests.

## How Codex should continue
1. `cd C:/tmp/ai-music-ami4` (branch `feature/ami-span-guide-tones`); keep other worktrees untouched; no push/merge/deploy without Daniel.
2. Preserve CRLF line endings in the files that have them (use a CRLF-aware edit; check `git diff --stat` stays small).
3. Reproduce and fix the Guitar TAB defect above, with a focused regression test, then rerun the 208-test selection and the browser
   proofs (Piano and Guitar, 2 and 3 chords, key changes, Return to Mission / Return to Creative).
4. Report, then wait for approval to integrate (rebase is not allowed on published history; use a normal merge of `origin/dev`).
