# AMI adaptive warmups — Slice 1 (local candidate)

Status: implemented and verified locally on `feature/ami-warmups-slice1`. Not pushed, merged or deployed.

## What the musician can do

* Ask for a warmup in their own words: instrument (and saxophone type), Beginner / Intermediate / Advanced, length, key, and what to include or leave out
  ("Give me a five-minute flute long-tone warmup", "an advanced saxophone scale warmup", "two-note exercises for articulation",
  "an intermediate warmup focused on thirds and fourths", "a warmup that improves finger technique", "a warmup with no long tones").
* See the whole plan (one staff per exercise, the tempo, bars, seconds per play, plays and rests) or step through it with **Next exercise** /
  **Previous exercise** / **Whole warmup** (buttons on the card, or typed).
* Change it by talking: shorter / longer / "make it 5 minutes", more advanced / easier, remove the long tones (or any family, or "exercise 2"),
  add more articulation work (or a scale, interval or long-tone exercise), make one exercise slower / faster / "set exercise 3 to 80 BPM",
  change the interval exercise to fourths, "undo that", "redo".

The explicit request decides the content. Asking for long tones gives long tones only; "no long tones" excludes them. A request that names no
families gets a balanced mix chosen from the level, with the Practice Focus giving the favoured families more of the time.

## What is built

| Family | Exercise | Notation |
|---|---|---|
| Long tones | Sustained whole notes on scale degrees, a breath bar after every pair; hold of about 4 / 5 / 6 s by level | whole notes and rests |
| Scale | The key's scale up and down, 1–2 octaves, a ladder of passes (tongued → slurred → faster) on their own bars | quarters / eighths / sixteenths, slurs |
| Intervals | Diatonic seconds … octaves, up then down (pairs; four-note cells at Advanced) | slurred pairs |
| Articulation | Tonguing on one note, two-note slurred/tongued pairs, slur-two-tongue-two, legato / staccato / accent / tenuto | slurs, staccato, accent, tenuto |

Every exercise is written in the pitch the player **reads**, then verified before it is shown: bars add up, every note is inside the instrument's
playable written range and the level's window, every note belongs to the key, the sounding line is the written line minus the instrument's exact
offset (octave included), and the shared ABC writer's own validation passes. A key that would need double accidentals (a concert F# for an alto
reads as D# major) is written in its enharmonic key.

## Duration, exactly

For each exercise: `seconds per play = beats × 60 / tempo`; `time = plays × seconds per play + (plays − 1) × 8 s of rest`.
Between exercises 10 s are allowed to breathe and turn. The plan total is the sum, and it is held within 8% (or 20 s) of the requested length
by choosing the number of plays (1–6) and, if needed, adding or dropping variants. The answer tells the player how many times to play each one.

## The versioned record

One record per browser session, `_ami_conv_warmup`, shaped as one warmup session containing its exercises (ready for a later practice-log entry,
which this slice does not touch). Up to 12 complete plans, a cursor for exact undo/redo, a view (whole plan or one exercise) and an *active* flag.
It is purged with the rest of the conversation on sign-out, account switch and workspace switch (`session_scope`), and reads are owner-checked.
A new ordinary exercise makes that exercise the thing the conversation is about; "undo that" then belongs to it.

## What is deliberately not done

* No song awareness: a request that names a song or soloing gets an ordinary warmup and says so. Guide tones, chord-tone patterns and improvisation
  preparation over a chart are the next slice.
* Revisions that are not in the supported list (accents, syncopation, "make it fourths" on a scale ...) are refused in words; the warmup is unchanged.
* Piano gets scales, intervals and articulation on a treble staff (no long tones); guitar, violin, voice and other unverified instruments are refused.
* The practice log, Composition, Missions, Backing, Key Cycling, the Practice Key and the global instrument / saxophone selections are not read for
  writing or changed.

## Claude planning (prepared, not wired)

`warmup_interpret.py` lets Claude turn a sentence the rules misread ("not much on long tones") into a **closed-vocabulary** plan request
(families, exclusions, intervals, articulation patterns, minutes, level, emphasis, focus). It is validated deterministically, merged so the rules win
where they were explicit, and handed to the same engines. It is developer-only, off by default, uses the same gates and fail-closed ledger as the
exercise interpretation layer, and is **not called by the live warmup path**. `scripts/ami_warmup_planning_experiment.py` is the prepared evaluation:
dry by default; live only with `AMI_WARMUP_LIVE=1 … --approve-spend`, through the **direct Messages API**, capped at 10 requests and $1 (worst case
about $0.0056 a request, about $0.06 for all ten) with a per-request ceiling and abort on the first API error.
