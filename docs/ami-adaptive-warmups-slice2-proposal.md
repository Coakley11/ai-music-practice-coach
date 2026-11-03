# AMI adaptive warmups — Slice 2 proposal: song-aware improvisation warmups

Status: **proposal only. Nothing in this document is implemented.** Slice 1 (long tones, scales, intervals, articulation, versioned plan, conversational
revisions, undo/redo) is the base. Slice 2 needs approval before any code is written.

## 1. What the musician should be able to say

* "Warm me up for soloing over Blue Bossa."
* "Give me a guide-tone warmup for the chorus."
* "Prepare me for improvising over these chord changes."
* "Give me an advanced exercise using thirds, sevenths and chromatic approaches."
* Then, by talking: "only the bridge", "just the first four bars", "thirds only", "add chromatic approaches", "make it more advanced",
  "make the second exercise slower", "undo that" — the Slice 1 revision and undo/redo machinery applies unchanged.

## 2. The promise AMI may make (and the only one)

Every song-specific statement on the card is **derived from the chart's own harmonic timeline** and shown next to the notes (the chord symbol above
each bar or half-bar, the chord's third and seventh named). If a chart cannot be read, a chord cannot be spelled, or a section has fewer chords than the
exercise needs, AMI says exactly that and builds the ordinary Slice 1 warmup — it never implies chord awareness it did not use. This is already true
today: a Slice 1 request that names a song or soloing gets an ordinary warmup and says "I can't tailor a warmup to a song's chords yet".

## 3. Inputs, all read-only

| Need | Existing building block |
|---|---|
| active song, section, concert key, chords per bar | `chart_context_reader.resolve_coach_chart_snapshot` (authoritative; owner- and workspace-checked as the exercises already are) |
| chords per half-bar (split measures) and per-chord scales | `scale_pattern_harmony` (`KeyScale`, `Segment`) and `scale_pattern_chords.generate` |
| third / seventh pitch classes of a chord, spelled in the chord's key | `exercise_span._guide_pcs`, `exercise_bridge` guide-tone logic (Slice 4 span exercises) |
| written pitch, instrument range, transposition | Slice 1 `warmup_engine` (`make_player`, `playable_written_range`, exact offsets) |
| notation, durations, rests, slurs, articulation | the shared ABC writer + Slice 1 `render` / `verify` |

Nothing writes the Practice Key, Backing, Key Cycling, Composition, Missions or the practice log.

## 4. The harmonic timeline (new, small, central)

`warmup_timeline.py`: `Timeline = [Seg(chord, start_beat, beats, bar)]` for the chosen section (or the whole chorus), in **concert pitch**, from the
snapshot. It owns: split measures (two chords in a bar = two 2-beat segments), repeats/endings as the chart states them, an unreadable-chord list
(slash chords, alterations the spelling engine cannot yet name), and the section's length in bars. Everything else asks the timeline; nothing else
parses chord symbols. The stored warmup keeps the timeline it was built from (song, section, chords, hash), so undo/redo, "next exercise" and
reload work even after the musician changes songs, and a "rebuild for the current chart" revision is an explicit, visible step.

## 5. Exercise family A — guide-tone preparation

* Content: the third and seventh of each actual chord, in order, voice-led: at each change choose the octave that minimises the leap, and prefer the
  half-step resolutions that exist in the progression (7th → 3rd of a V→I or ii→V). Spelling follows the chord (the third of Ab7 is C, the seventh
  Gb — never F#).
* Levels. Beginner: one guide tone per chord (3rds, then 7ths on a second pass), whole/half notes, slow. Intermediate: both tones per chord as quarters,
  stepwise connections, two choruses of fewer bars. Advanced: a continuous guide-tone line in eighths with chromatic or enclosure connections between
  chords and a faster tempo; optional "3rd one chorus, 7th the next".
* Time: pass length = section beats × 60 / tempo, exactly as Slice 1 computes it; repetitions fill the requested minutes with rests and transitions.

## 6. Exercise family B — chord tones and approach notes

* Chord tones: 1-3-5-7 arpeggios per chord (up, down, then permuted at higher levels), each chord given exactly the beats the chart gives it.
* Approach notes: a chromatic approach from below or above, a diatonic approach, and (Advanced) a double-chromatic or enclosure **into the next chord's
  chord tone**, landing on the barline or the chord change. Validity rules checked in code: the approach note is not itself a chord tone of the target
  chord, it resolves by step to the target on the next strong position, and it never lands outside the playable written range.
* Timing across split measures: the approach occupies the last subdivision before the change; a two-beat chord leaves two beats for tone plus approach.
* Complexity ladder: rhythm (quarters → eighths → eighth-note triplet pickups), articulation (all slurred → slur two/tongue two → mixed), tempo.

## 7. Planner and revisions

* New families `guide_tones` and `chord_approach` join Slice 1's four. A request is song-aware when the words say so **and** a readable chart exists; the
  plan's header names the song, section, key and bars used. If the musician names a song that is not the active one, AMI asks rather than guesses.
* Revisions (all through the existing `revise` with explicit support checks, anything else refused in words): change section; limit bars; thirds-only /
  sevenths-only; add or remove chromatic approaches; level; tempo (whole or one exercise); remove or add a family; undo/redo (exact — the stored plan
  is complete). Each says what changed and what stayed.
* Mixed plans are normal: a 10-minute "warm me up for soloing over Blue Bossa" can be long tones → a scale in the key → guide tones over the chorus →
  chord tones with approaches, with each song-aware exercise labelled as such.

## 8. Claude-assisted planning (after the deterministic path is solid)

The live evaluation of 2026-11-02 (9 requests, $0.036) showed where it helps and where the closed vocabulary is too small. Slice 2 would extend it, still
validated by deterministic code and never supplying notes, chords, durations or transpositions: a `section` choice from the chart's own section names; a
`length` hint (`short` / `normal` / `long`) because "something quick" produced no minutes; a `progression` flag ("increasingly difficult"); and a
separate **revision** vocabulary (`target` = exercise number or family, `op` from the supported list) so "make the second exercise more challenging, but keep
the first exactly as it is" can be read by Claude instead of declined. Merge policy: the rules win only where they found an explicit instruction (a number,
a level word, a negation); where the rules merely defaulted, Claude's validated reading fills in.

## 9. Tests and acceptance (prepared with the architecture, written before the code)

* **Oracle independent of the generator**: a checker that recomputes every chord's tones from the chord symbol and verifies, for every note, its role
  (guide tone / chord tone / approach) and its resolution; spelling checked per chord.
* **Property tests over the real catalog**: every song × section × instrument (flute, alto, tenor, soprano, baritone, clarinet, trumpet) × level — notes in
  written range, sounding = written − exact offset, bars add up, split-measure beats exact, no exception, honest fallback for unreadable charts.
* **Golden examples** for Blue Bossa, Autumn Leaves, a split-measure ii–V, a minor ii–V–i, a tune with slash chords (expect a stated limitation).
* **Revision/undo/redo**: exact restoration, untouched exercises byte-identical, stale-chart handling, owner and workspace isolation.
* **Browser acceptance** (flute, alto, tenor × three levels): ask, step with Next exercise, revise, undo, switch song and confirm the old warmup still
  shows its own song; rendered staff read from the page against the written ABC; Practice Key, Backing BPM and the global instrument selections unchanged.
* **No billable calls in tests**; the transport is blocked as in Slice 1.

## 10. Proposed delivery, each step stopped for review

1. **2a — timeline + guide tones** (smallest slice that makes the first promise true).
2. **2b — chord tones + approach notes**, then song-aware mixed plans and revisions.
3. **2c — Claude-assisted planning** behind the existing developer gate, using the extended vocabulary, with a fresh capped evaluation.

## 11. Decisions needed from the owner

* Where the song name comes from when it is not the active song (ask each time, or only the active song in 2a).
* Whether a song-aware warmup should offer "Play along with the Backing for this section" (a deliberate hand-off, never automatic).
* Default length for a song-aware warmup (proposed: the Slice 1 default of 10 minutes, one chorus per pass).
* How to treat chords the spelling engine cannot yet name (proposed: state them, skip them, and say how many bars were affected).
