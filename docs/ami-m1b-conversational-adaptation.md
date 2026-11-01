# AMI M1b — instrument changes, section retargeting, explanations, and the experimental Claude interpretation layer

Status: implemented locally on `feature/ami-m1b-instrument-section-explain`; **not pushed**. Everything here works on the structured working scale
pattern (M1d/M1c) and creates a new version of it, so undo and redo work. Nothing below makes an API call unless the experimental layer is explicitly
enabled (it is off by default, developer-only).

## What the musician can say

| Request | What AMI does |
|---|---|
| "Make this exercise suitable for flute", "Change it from alto saxophone to tenor saxophone", "Play it on soprano saxophone instead", "Adapt this pattern for piano" | Keeps the *sounding* line and writes it for the new instrument (`exercise_adapt.change_instrument`). |
| "Keep the same exercise, but change the instrument", "…for a saxophone" | Asks which instrument (soprano / alto / tenor / baritone); the next message ("tenor") answers it. |
| "Apply it to the chorus", "Change it to Verse 2", "Use the chord changes from Section B" | Rebuilds the same recipe over that section's real chords, split bars and durations (`retarget_section`). Asks when the name is ambiguous. |
| "Why do those notes work over these chords?", "Which notes are chord tones?", "Show me the guide tones", "Explain the chromatic approaches", "Why did you use those intervals?", "How would I use this when improvising?", "What did the last change do?" | Explains from the stored exercise (`exercise_explain`); never creates a version. |

## Instrument changes — the contract

* Verified instruments only: flute, piano, soprano / alto / tenor / baritone saxophone, trumpet, clarinet. Anything else is named and refused; nothing is guessed.
* The target's written context comes from the app's own `build_written_music_context` fed an **isolated mapping**, so the app's global Instrument / Saxophone
  type selections are never read or written (browser-verified).
* Every note keeps its concert pitch, rhythm, chord, articulation and accent. The written pitch is the sounding pitch plus the instrument's exact offset
  (flute 0, piano 0, alto +9, tenor +14, soprano +2, trumpet +2, clarinet +2, baritone +21), octave included, and is held inside the instrument's range.
* If the line does not fit the range, the whole line moves by whole octaves (smallest verified shift) and the answer says **"Octave adjustment: … N octaves up/down"**.
* If no octave fits (a two-octave line into a one-and-a-half-octave window), the **same recipe** (interval shape, approaches, rhythm, harmony) is rebuilt in the new
  register and the answer says **"Re-voiced"**; the rhythm, chords and number of notes must be identical or nothing changes.
* Key-based patterns adapt to every instrument. **Chord-following patterns cannot be built for piano** (the engines' piano window cannot hold a four-note cell
  over the chords; asking for chord changes on piano already returns a key-based pattern today), so that adaptation is refused with the reason.

## Section retargeting — the contract

* Needs a chord-following exercise. A key-based pattern is not tied to chords, so it is **never relabelled** for another section.
* The chart is read the way the first answer read it (`resolve_coach_chart_snapshot`), in the Practice Key. If the Practice Key changed since the exercise was
  built, nothing is moved. Same section, or a section with identical chords, is a clear no-change.
* The recipe (shape, approaches, syncopation …) carries over; the notes are regenerated from each chord's scale, so no note is kept from the old section. The
  section's own length (up to 16 bars) and chord durations are used.

## Notation fix found while testing (affects dev as well)

`composition_to_abc` wrote each note relative to the key signature only. ABC accidentals are absolute and last to the bar line, so a note that relied on the key
signature after an explicit natural/sharp/flat earlier in the same bar was displayed one semitone off (e.g. `=e'` then `e'` for E♭ in C minor), and E♯ in a flat
key came out as a double sharp. It now tracks the accidentals in force per bar and octave. `tests/test_ami_abc_accidentals.py` reads the ABC back with an
independent reader for every instrument, both kinds of pattern and every M1c recipe: 19 of those cases fail on current dev without the fix.

## Known, reported, NOT changed: the coach's staff is drawn one octave high

`abc_pitch_for_spelled_note` writes scientific C4 as ABC `c`, which abcjs draws as C5. Composition notation compensates (`COMPOSITION_ABC_OCTAVE_SHIFT = -1`);
the Music Coach writer does not, so every coach pattern is drawn one octave above the pitch AMI stored (measured with abcjs: first flute note pitch 14 = C6,
stored C5). Changing it moves every coach notation and invalidates golden tests, so it is left for an explicit decision; a strict `xfail` test documents it.

## The experimental Claude interpretation layer (M1b-4)

Off by default. All of these must hold before anything is sent: `AMI_CLAUDE_ENABLED` true, `AMI_CLAUDE_INTERPRET_ENABLED` true, developer mode, the developer
toggle, a priced model, an API key, and budget/session-cap room in the same fail-closed ledger as the coaching enrichment.

* It is only asked when the fixed rules could not parse the sentence, there is a working scale pattern, and the sentence is not a request for a new exercise.
* Claude receives only the sentence, the exercise's recipe / kind / instrument / bar count / section **name**, the available section **names**, and the last three
  request texts. No notes, chords, lyrics, account or workspace data.
* It answers in a closed vocabulary (JSON schema with enums): shape, interval_advance, wider, narrower, simplify_notes, approach / approach_more / approach_off,
  anticipate, displace, sync_more / sync_less / new_rhythm, harder / easier, instrument, section, explain (+ "keep" constraints and a clarify code). No free text is shown.
* `claude_interpret.validate` rejects: unknown operations or arguments, conflicting pairs, mixed kinds (instrument / section / explain never combine with others),
  more than three operations, a violated "keep …" (rhythm, notes, instrument, section, tempo), a section not on the chart, anticipation on a key-based pattern.
* The accepted operations are carried out by the same engines as typed requests (`revise`, `change_instrument`, `retarget_section`, `explain`), with the same
  contracts, and the answer begins "I read that as: …". Failure, rejection, budget or API trouble leave today's deterministic answer.
* `scripts/ami_interpret_experiment.py` is the controlled experiment: dry by default; live only with `AMI_INTERPRET_LIVE=1 … --approve-spend`, capped at 10
  requests / $1.00 / $0.05 per request, no SDK retries, abort on the first error.

### Using Claude for richer explanations (design only, not built)

Deterministic explanations are exact but plain. A language-model paraphrase could be added with the same discipline as the coaching enrichment: send the
stored facts (chord → scale → notes with roles), require every concrete musical token to be marked and validated against those facts, reject the whole answer on
any violation, and keep the deterministic text as the fallback. It needs a separate approval and budget.

## Limits

* Chord-following → piano is refused; baritone saxophone is supported by offset but has the narrowest verified window.
* "Re-voiced" changes the exact pitches (not the shape, rhythm or harmony) and is always announced.
* Sentences that combine an instrument and a section ("play it on alto over the chorus") are asked one at a time.
* Explanations describe what is stored; they do not judge taste ("is this good?").
* The interpretation layer cannot make the engines do anything they cannot (dynamics, slurs, swing feel, new songs).
