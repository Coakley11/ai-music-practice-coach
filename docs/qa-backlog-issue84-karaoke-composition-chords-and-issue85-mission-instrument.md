# QA backlog: Issue 84 (Karaoke plays the wrong song's chords) and Issue 85 (Mission Practice keeps Guitar)

Recorded 2026-11-22 from the owner's report. **Nothing here is implemented or investigated yet.**
Ordered by the owner: Issue 84 is investigated before Issue 85, because it may affect the
music actually performed. Both are queued behind the Custom editor (Option A) and My Uploaded
Melodies Slice 1 work.

Screenshots: the owner referred to screenshots, but none reached the working session that
wrote this entry. Attach them here (or link them) when available.

---

## Issue 84 — OPEN / HIGH PRIORITY — Karaoke Now Singing uses another song's chords (and possibly audio)

**Observed.** During a Karaoke Set, the Composition song **Jazz tune** was shown as Now Singing
(Song 3 of 3), but the chord progression shown belonged to the Custom song **Blues in F minor**:
Fm6, D♭7, C7, Fm7 and B♭7. Jazz tune was tried in both **F** and **C**; the wrong progression
appeared both times. Blues in F minor may have been the ordinary active Custom song.

**Reproduction (to confirm).**
1. Make **Blues in F minor** (Custom) the active song outside Karaoke.
2. Build a Karaoke Set whose third entry is **Jazz tune** (Composition); start the set.
3. Let it advance (and also tap) to Jazz tune; sing it at **F**, then again at **C**.
4. Compare what is shown and what is heard against Jazz tune's saved chords.

**Investigation requirements.**
- Reproduce Jazz tune in F and C with Blues in F minor active outside Karaoke.
- Trace the song source that generates the **actual audio take**, not only the labels.
- Compare, for the same moment: the saved Composition's chords, the Karaoke entry, the
  rendered audio, the singing panel and the Lead Sheet.
- Now Singing must stay authoritative for the performed song.
- An ordinary active Custom song, or the Now Editing song, must never supply the chords of a
  Composition Karaoke entry.
- Regression coverage for Catalog, Custom and Composition source switching inside a set,
  including automatic advancement.

**Acceptance.** Do not fix only the visible chord labels: the played harmony must be confirmed
correct (audio take built from Jazz tune's own chords, in the sung key). Stays **OPEN** until
both the audio and the displayed harmony are verified.

**Related.** Earlier Karaoke identity work: Now Editing vs Now Singing separation (Cloud
2026-11-18), the stale card-control retune guard and one end signal per song (dev 88f6b3fe).
The Custom editor / active-song separation (Option A, branch
`fix/custom-load-selected-activation-20261122`) changes which chart the active Custom slot holds,
and must be re-checked against this issue once it lands.

---

## Issue 85 — OPEN / MEDIUM PRIORITY — Mission Practice keeps Guitar after switching to Alto Saxophone

**Observed (Blackbird Mission Practice).**
- Guitar was selected first; the instrument was then switched to **Alto Saxophone**.
- The key was changed to **C♯**.
- The Mission summary still reported **Instrument: Guitar**.
- **Guitar TAB** stayed visible.
- The summary showed **A♯m7♭5** while the mission targeted **C♯**.

**Investigation requirements.**
- Mission Practice reflects the instrument selected now.
- Guitar TAB is hidden for saxophone and every other non-guitar instrument.
- Correct written notation and transposition for Alto Saxophone (E♭ instrument).
- Also verify Tenor and Soprano Saxophone (B♭), Flute (C) and Guitar.
- Verify the chord independently of the mission's target note: a C♯ target note does not
  mean the chord must be C♯ (A♯m7♭5 may be legitimate - confirm against the song's harmony
  at that point).
- Preserve concert pitch, written pitch, key signatures and enharmonic spelling.
- Desktop and mobile (390 px) regression tests.

**Status.** **OPEN**, medium priority, after Issue 84.
