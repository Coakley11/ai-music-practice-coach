# AMI M1c — advanced scale patterns, revised through conversation

Status: implemented locally on `feature/ami-m1c-advanced-patterns` (not integrated). Deterministic only: no Claude API call is made or needed.

## What the player can do

On a scale pattern (key-based or chord-following) that is the working exercise:

| Say | What changes | What is kept |
|---|---|---|
| “Change it to thirds / fourths / fifths”, “make the intervals wider”, “give me a more advanced interval pattern”, “use a mix of thirds and fourths” | the pitches (interval cell) | rhythm, chords, key, instrument, tempo |
| “Simplify the notes”, “make the intervals narrower” | pitch complexity, in order: approaches, cell, shape | everything else |
| “Add chromatic approaches”, “…from below / above”, “make the line more chromatic”, “remove the chromatic approaches” | some weak notes become half-step approaches | rhythm |
| “Make the rhythm more syncopated”, “use more offbeats”, “add some rhythmic displacement”, “keep the same notes but change the rhythm”, “straighten the rhythm” | the rhythm | pitch order |
| “Add anticipations of the next chord” (chord-following only) | the note before each chord change | everything else |
| “Make it more advanced / easier” | the next step of a deterministic walk (below) | the interval shape the player chose |

Every request can be undone and redone exactly; tempo changes, accents and articulation still work between them and survive them.

## Architecture

* `scale_pattern_recipe.py` — the `Recipe` (level, subdivision, interval shape and tier, approach side/density, syncopation level, displacement, anticipation), the difficulty walk (`advance` / `ease`), and the request parser (`parse_pattern_change`). No music is generated here.
* `scale_pattern_transforms.py` — the layers applied to the concert-pitch line, in a fixed order: `add_approaches` (pitch only) → `retime` (rhythm only: syncopation, displacement) → `anticipate` (explicit request only), plus `verify`, which re-checks a finished line from its tags alone.
* `exercise_scale_pattern.py` — `regenerate(parent, recipe)` builds the pattern from the parent's own song, section, key, instrument and tempo; `revise` applies a request and returns the answer; the recipe is stored in `provenance["recipe"]`.
* `exercise_revision.py` — routes a pattern request on the working scale pattern before general routing, pushes the new version on the history stack.
* `musical_idea_engine._degree_cycle` — new interval-cell names only (`thirds_triad`, `thirds_stack`, `fourths_step`, `fourths_stack`, `fifths_step`, `thirds_fourths`); every existing name keeps its exact cell.

The first answer to “give me a scale pattern …” is still produced by the M1d path, unchanged.

## Musical rules

* **Intervals** are counted in scale steps within the chord's scale (chord-following) or the Practice Key's own scale (key-based). A few are not perfect (an augmented fourth in every diatonic scale, a diminished fourth from the root of an altered scale); the answer names them.
* **Chromatic approaches** go on the weak note immediately before a chord tone (chord-following: root/3rd/5th/7th/6th of that chord; key-based: a tonic-triad tone of the key) that falls on a strong beat — beats 1 and 3 and every chord change, or every beat at the higher density. They come from the side the line was already moving from, unless the player names a side. They are a half step from the target, spelled sharp rising / flat falling (also in the written staff of a transposing instrument), inside the instrument's range, and resolve straight to the target — across a chord change as well. A key-based pattern says its approaches target the key, not chords.
* **Syncopation** re-times the same pitches: a held note starts on the “and” (eighth-note patterns keep every pitch; sixteenth-note patterns have no room, so the later notes of each chord segment are left out and the answer says how many). Quarter-note (Beginner) patterns are not syncopated silently. **Displacement** starts each chord segment one subdivision late with a rest and leaves out what no longer fits; a rest never separates an approach note from its target (the approach moves with it). Syncopation and displacement never change the harmony.
* **Anticipation** is separate, explicit, and only for chord-following patterns: the first note of the next chord is played an eighth early (the “and of 4” before a change on beat 1; the “and of 2” before a change on beat 3), tagged, listed in the answer, with the chord symbols left where the chart changes them. A boundary where it cannot be notated, or would remove the note the previous anticipation leads to, is skipped and reported.
* **Difficulty** is `Recipe.score()`-monotonic: quarter→eighth, intermediate→advanced, interval cell tier, sixteenth notes, chromatic approaches, light syncopation, approaches on every beat, full syncopation, displacement. The first four steps are exactly the M1d ladder (Beginner, Intermediate, Advanced, Advanced+, Advanced++). A step the instrument's range cannot hold is skipped and said so; the interval shape is never replaced.

## Intentional changes from M1d

* “Make it harder” no longer stops at Advanced++; it continues (approaches, syncopation, displacement) until the recipe is exhausted, then says it is the hardest version. The M1d rungs themselves are unchanged.
* Requests M1d answered with “I can't do that yet” (thirds / fourths, chromatic approaches, syncopation, new rhythm on the same notes) are now carried out on scale patterns. They are unchanged for every other kind of exercise.

## Limits

* Chord-following patterns: 4/4 and 3/4; the same instruments as M1d (flute, piano, alto/tenor/soprano sax, trumpet, clarinet).
* No ties across the bar line, no dotted values, no 32nd notes, no triplet syncopation; no enclosures, bebop scales or longer vocabulary (the answer says chromatic approaches are the jazz vocabulary offered so far).
* Slurs and dynamics are still not notated on scale patterns.
* A request that names features in the very first sentence (“… with chromatic approaches”) gets the plain pattern first and a line saying how to add them.
* Playback: the AMI card has no audio; nothing here changes Missions playback.
* Repeating the same revision ("Undo that" twice, the same pattern request) is no longer swallowed by the duplicate-send guard: revision requests now carry `revision|version|cursor` in the exercise-authority signature.
