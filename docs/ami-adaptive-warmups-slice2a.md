# AMI adaptive warmups — Slice 2a: song-aware guide-tone preparation (local candidate)

Status: implemented and verified locally on `feature/ami-warmups-slice2a`. Not pushed, merged or deployed. Slice 2b (chord tones and approach notes) and
Slice 2c (Claude-assisted planning) are not started. Claude interpretation is **not** used by this slice and nothing here makes an API request.

## What the musician can say

"Warm me up for soloing over Blue Bossa." · "Give me a guide-tone exercise over the chorus." · "Practice the thirds and sevenths of these chords." ·
"Give me an advanced jazz guide-tone warmup." Then, by talking: "just the first four bars" (or "the last four bars", "bars 5 to 8"), "only the bridge"
(any section of the song), "use thirds only", "now practice the sevenths", "make the guide-tone movement smoother", "make it more advanced",
"make the second exercise slower", "change it to tenor sax", "explain why those notes work", "undo that", "redo".

## Where the chords come from (read-only)

The coach's own authoritative chart snapshot (`chart_context_reader.resolve_coach_chart_snapshot`, already attached to the page context as
`ctx.extra["chart_snapshot"]`): the active song's sections as charted (`chart_sections_raw`, split bars such as `Dm7|G7` intact), the meter, the Practice Key
(concert) and the song's original key. Nothing is written back; the Practice Key, Backing, Key Cycling, Composition, Missions and the global instrument
selections are not touched. The warmup stores its own copy: song title, every section's bar slots, the Practice Key, the meter, the chart source and a
**chart revision hash**, plus the selected section and bars. Changing the active song later never rewrites an earlier warmup; "only the bridge" on an
earlier warmup uses the stored chart.

If a different song is named ("…over Autumn Leaves" while Blue Bossa is active) AMI asks you to select or activate it first and builds nothing. With no
readable chart: an explicit guide-tone request asks you to select a song; a general "warm me up for soloing" still gets an ordinary Slice 1 warmup that
says it is not tailored to a song. The architecture keeps named-song resolution in one function (`named_song_conflict`) so it can be added later.

## The harmonic timeline and the existing components

No second chord parser. `scale_pattern_harmony.timeline_segments` gives each chord its bar, beat and length (split bars, weights); `_split_chord` /
`_classify` decide the quality; `chord_tone_roles` (computed from the symbol) gives the third and seventh (or sixth). Spelling follows the chord: letters
root+2 (third) and root+6 (seventh), chosen so the **written** tones never need a double accidental (a concert chord whose written root would need one is
respelled enharmonically). Both concert and written spellings are stored. Chord symbols are printed over the staff in the written pitch for the instrument.
Slice 2a writes 4/4 charts (another meter is refused in words).

## Guide-tone lines and voice-leading

For each chord the line holds the third and/or seventh, filling exactly the chord's beats (a split bar's two chords each get their own beats; a note or rest
always starts on the chord change). Octaves come from one Viterbi pass over every note of the exercise: minimise leaps (more strictly for "smoother"), stay
near the middle of the player's level window, and reward a seventh that falls onto the next chord's third by a half step (whole step, less). The result
reports the real resolutions it contains (computed from the written notes, e.g. `Bm7♭5 → E7♯5: A → G♯, half step`).

## Difficulty changes the music

| Level | Tempo | First exercise | Other exercises in the plan |
|---|---|---|---|
| Beginner | ♩ = 52 | thirds only, long notes | sevenths only; both (third first); both (seventh first) |
| Intermediate | ♩ = 72 | both tones, steady quarters (4 notes per 4-beat chord) | thirds with a pulse; sevenths with a pulse; both (seventh first) |
| Advanced | ♩ = 96 | both tones, mixed eighths and quarters (6 notes per chord), accent on every chord arrival | continuous eighths; seventh-first cells; sevenths / thirds in eighths |

A "thirds only" / "sevenths only" choice collapses variants that would be the same music; a short section that cannot fill the requested minutes ends short
and says so (planned playing time is always printed).

## Unsupported chords

Never invented, never silently dropped. `chord_info` reports why: diminished chords, suspended chords (no third), unreadable symbols, qualities outside the
supported kinds, a chord whose tones cannot be written for the instrument without double accidentals, a chord change shorter than the notation allows. In a
section that is at least half supported, those chords get **correctly timed rests with the chord symbol over them**, and the exercise names them and their
bars ("Rests mark chords this version can't write guide tones for: Bdim7 (bar 6: …)"). Triads get their third (flagged: "a triad: only its third is a guide
tone"); sixth chords use the sixth in the seventh's place (flagged). If less than half the harmonic time is supported the chord-aware item is refused with
the chords and bars named, and an ordinary warmup is offered.

## Verification

Each exercise is checked before it is shown (`warmup_song.verify`): bars add up; every note inside the level window and the instrument's playable range;
sounding = written − the instrument's exact offset; **every note is a third / seventh / sixth of the chart's own chord at that beat** (judged on the sounding
pitch by `chord_tone_roles`); a note or rest begins exactly on each chord change; the notation validator passes. The tests add an oracle that shares no code
with the generator (`tests/song_oracle.py`: its own chord reader and ABC tokenizer) and run it over real catalog songs × eight instruments × three levels
× every variant, plus mutation tests proving the oracle fails on wrong music.

## Not in this slice

Chord-tone patterns and approach notes (2b); Claude-assisted planning (2c); a "Play with Backing" action (prepared for, deliberately not built: it must be an
explicit, optional button that never starts playback or changes state by itself); named-song resolution; non-4/4 charts; repeats/endings beyond what the
chart's bar slots already express.
