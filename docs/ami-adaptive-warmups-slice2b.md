# AMI adaptive warmups — Slice 2b: chord-tone arpeggios, approach notes, whole form, mixed plans (local candidate)

Status: implemented and verified locally on `feature/ami-warmups-slice2b`, based on `origin/dev` `36a86c35` (which already contains Slice 2a). Not pushed, merged
or deployed. Claude-assisted planning (Slice 2c) is **not** started; this slice makes no API request and the Claude layer is unchanged and unwired.

## What the musician can say

"Give me an arpeggio warmup over Blue Bossa." · "Give me a guide-tone exercise followed by arpeggios." · "Warm me up over the whole song." · "Prepare me for improvising
over the entire chorus." · "Warm me up for soloing over Blue Bossa." (a mixed plan) · then: "Make the arpeggio exercise more advanced." · "Start each arpeggio on the
third." · "Add approaches from below." · "Use an enclosure before the next chord." · "Only the bridge." · "Use the first eight bars." · "Make the second exercise slower." ·
"Explain why these notes work." · "Undo that." · "Redo."

A song-aware exercise is requested with the word *warmup* (or a guide-tone / "prepare me for soloing" phrasing). A plain "give me a chord tone exercise over Cm7" or an
enclosure over a named chord still belongs to the existing exercise code, untouched.

## The two new exercise families (`warmup_chordline.py`)

Both are built on Slice 2a's chart snapshot, harmonic timeline (split bars included) and chord reading. No chord symbol is parsed anywhere new.

**Chord tones (`chord_tones`).** Each chord's own tones — root, third, fifth (when the symbol has one and it can be written), seventh, or a sixth chord's sixth in the
seventh's place; a triad has three — played as an arpeggio over exactly that chord's beats. Direction (up / down), shape (straight, up-and-back, skipping 1-5-3-7,
zig-zag 1-7-3-5), start tone (root / third / fifth / seventh, or the one that connects best to the previous chord), articulation (slurred pairs, accent on each
chord arrival) and rhythm (quarters for a Beginner, eighths above) come from the level's variants or from the musician's words. A straight arpeggio that runs past the
chord's last tone continues into the next octave when the player's window allows (R-3-5-R'), otherwise the figure repeats.

**Approach notes (`approach_notes`).** At each chord change the line lands on a deliberately chosen chord tone of the new chord (its third, seventh, root or fifth, or
whichever voice-leads best); the last beat(s) of the old chord approach it: chromatic from below, chromatic from above, diatonic (the scale note below, from the existing
chord-scale reader), a double-chromatic run, or an enclosure (above then below). Rules enforced in code and by the independent oracle:

* an approach note is never a chord tone of the chord it leaves or of the chord it enters (a neighbour that is would not be an approach); when the usual neighbour is a
  chord tone the other side is used **and the answer says so**;
* the approach resolves by one or two semitones onto the target, on the exact beat the chart changes chord (halfway through a split bar: beat 3);
* the last chord approaches the first, ready for the repeat (said in the answer), when the two chords differ;
* an unsupported chord (diminished, sus, unreadable, un-writable) is rested for its exact time, is never approached or left by an approach, and is named with its bar;
* a chord too short to hold the approach, or one with no usable target, gets no approach and says why; a chord without the asked-for target (a triad has no seventh)
  is approached on its third, and says so;
* approach spelling follows how approaches are read (C♯ leading up to D, E♭ falling to D; never a double accidental).

Every candidate line is a complete checked sequence of pitches; one dynamic-programming pass picks start tones and octaves for the whole exercise (smooth leaps, a
seventh falling onto the next third rewarded, a "smoother" switch that weights leaps harder).

## Whole form and sections

"The whole song / form / chorus" builds the chart's **own** sections in the order it lists them, excluding intros, outros, codas, tags, turnarounds and breaks, as a derived
section stored beside the real ones (the originals and the chart revision hash are untouched). A section the chart itself names Head / Chorus / Form / Tune is used on its
own. A form longer than 64 bars is refused with the reason. Nothing is invented or repeated that the chart does not contain. "Only the bridge", "the first eight bars" and
any section name of the song (`A3`, `B (Bridge)`) work on the whole plan, and a section the song does not have is said, not silently replaced.

## Mixed plans and the order of exercises

"Warm me up for soloing over X" is now a mixed plan chosen by level: Beginner — guide tones and arpeggios; Intermediate and Advanced — one short scale in the Practice Key,
guide tones, arpeggios and approach notes. Named exercises replace the default and keep the order the musician spoke them in ("a guide-tone exercise followed by
arpeggios"); exclusions are honoured ("no scales"); a stated length is honoured, and the plan says how long it actually plays.

## Conversation

New operations, each scoped to the intended exercises and exactly undoable: start tone for the arpeggios; approach kind (adding the approach-note exercise when absent);
the whole song; and "more advanced / easier" on an exercise **kind** ("the arpeggio exercise" — every variant of it) or a numbered exercise, which re-builds that exercise at the
next level (its rhythm, tempo and shapes, on the same chords) rather than only speeding it up. New variants of a kind inherit that kind's level. Unrelated exercises are
byte-identical after every operation, the explanation covers chord tones and each approach with its target, and anything unsupported is refused in words with the plan
unchanged.

## Verification

* `warmup_chordline.verify` ties the stored rows note-for-note to the notation and checks every role against the chart's own chord (`chord_tone_roles` on the sounding pitch),
  every approach run's landing, target, beat and geometry.
* `tests/song_oracle.py` (own chord reader and ABC tokenizer, no shared code) checks 3,128 builds — six real songs plus derived whole forms × eight instruments × three levels × every
  variant of both exercises — with zero problems, plus mutation tests proving it fails on wrong music.
* Real-app browser acceptance reads the drawn staff of every card and runs the oracle on the cards' own ABC (chord qualities taken from the app's printed labels, roots from the catalog).

## Not in this slice

Claude-assisted planning (2c); a "Play with Backing" action; named-song resolution; non-4/4 charts; repeats and endings beyond what the chart's bar slots express; extension and
alteration tones (9ths, 11ths, 13ths) in the arpeggios; triplet and swing rhythms.
