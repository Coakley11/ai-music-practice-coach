# Handoff to Backing Claude — Perfect (Ed Sheeran), compound-meter comp pattern

**From:** Catalog Accuracy (Perfect investigation, 2026-11-15)
**Branches:** `catalog/perfect-timing` → `catalog/perfect-concert-key` (both local)
**Scope:** one bounded question about the Ballad comp pattern in compound meters.
**Not asking for:** any global backing-engine change, and nothing at all about
tempo, meter, key or the chart. Those are mine and are already corrected.

---

## What I already fixed on the catalog side (so you do not chase it)

Perfect stored `default_bpm=95`, but `songs/meter.py: meter_timing` reads a
compound-meter BPM as the **dotted-quarter pulse** rate
(`bar_sec = (num // 3) * 60 / bpm`). A 6/8 bar is 3 quarter notes but only 2
dotted-quarter pulses, so a quarter-note rate stored there shortens every bar
by exactly 2/3 — the song played **1.5× too fast**. Now `default_bpm=63`
(published marking; a teaching handout independently gives 12/8 at 64).
Bar = **1.9048 s**, pulse = 0.9524 s.

**The engine convention is right and I did not touch it.** Gravity 42,
Champions 65, Hava Nagila 120 and Siman Tov 130 are all consistent with it;
Perfect was the lone outlier.

## What I verified about your groove — it is NOT broken

The 6/8 Ballad pattern is genuinely compound, not a 4/4 backbeat wearing a 6/8
label:

| element | eighths | per bar | real-time interval |
|---|---|---|---|
| kick | `[0]` | 1 | 1.9048 s |
| snare | `[3]` | 1 | 1.9048 s |
| bass | `[0, 3]` | 2 | 0.9524 s |
| comp | `[0, 2, 3, 5]` | 4 | 0.4762 s |
| hats | `[0..5]` | 6 | 0.3175 s |

`metronome_accents("6/8")` is `[1, 4]` — ONE-two-three FOUR-five-six. Every
onset in a rendered verse (82) and chorus (28) lands on the compound grid.
**The pattern was right; only the clock was wrong.**

### Correction to an earlier note of mine

I previously suggested the 6/8 snare was twice the record's backbeat density
and that 12/8's `snare_beats [3, 9]` would be more authentic. **That was
wrong — please disregard it.** The two patterns are *identical in real time*:
12/8 is literally the 6/8 pattern twice over (snare every 1.9048 s on both,
kick every 1.9048 s, bass every 0.9524 s, comp every 0.4762 s). Switching the
song to 12/8 would change nothing audibly, which is a further reason I kept
6/8. There is no snare-density defect. Sorry for the false lead.

---

## The one bounded finding worth your judgement

**The comp pattern skips two of the six eighths in every bar.**

`comp_beats = [0, 2, 3, 5]` covers eighths 1, 3, 4 and 6 and **omits eighths 2
and 5** — the second note of each triplet group:

```
eighth:   1   2   3   |   4   5   6
comp:     X   .   X   |   X   .   X
          ONE     three   FOUR    six
```

Perfect's signature on the record is a **continuous arpeggiated triplet flow** —
a steady 1-2-3, 4-5-6 on the acoustic guitar/piano with no gap on the middle
note of either group. A lesson source calls the feel "swung 12/8". The current
comp instead gives a broken, gapped figure. The hats do fill all six eighths,
but they are percussion, not the harmonic arpeggio the ear follows.

### The question

Is it worth giving a compound-meter Ballad a comp pattern that arpeggiates all
six eighths (`[0, 1, 2, 3, 4, 5]`, probably with a shorter `comp_dur` than the
current 0.55 so the notes do not smear), either:

- **(a)** as the Ballad pattern for compound meters generally — it would also
  affect Gravity, Champions, Hava Nagila and Siman Tov, so it needs your
  judgement about them, **or**
- **(b)** as a song-specific profile for Perfect only, via the
  `SONG_ARRANGEMENTS` mechanism (`song_arrangement_profile` accumulates
  entries, matched on `(("perfect", "ed sheeran"),)`) — the same route
  `section_lifts` already uses, needing no engine change.

I lean to **(b)** on the evidence I have, because I have only verified the
continuous-arpeggio claim for this one song. But the call is yours — you own
reusable backing behaviour, and I have deliberately changed none of it.

### Related, lower confidence

`kick_beats [0]` gives one kick per 1.9048 s, which is sparse for a song whose
chorus has an audible kit entry. Section-aware dynamics may already cover this;
I did not investigate it and am not claiming a defect.

---

## How to reproduce my measurements

```bash
# both branches are local; the second is on top of the first
git worktree add /c/tmp/perfect-key catalog/perfect-concert-key
cd /c/tmp/perfect-key
python -m pytest tests/test_perfect_compound_timing.py tests/test_perfect_concert_key.py -q
```

The compound-grid class is
`tests/test_perfect_compound_timing.py::TestTheGrooveIsGenuinelyCompound`.
Labeled renders (verse/chorus, old vs corrected) are in
`C:\tmp\perfect-listening\`. **Nothing was checked by ear** — the onset and
pitch figures are measurements, not auditory acceptance.
