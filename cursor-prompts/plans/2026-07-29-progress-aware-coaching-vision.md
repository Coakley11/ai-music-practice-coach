# Progress-aware coaching — future vision

**Last updated:** 2026-07-29  
**Status:** Vision / roadmap only — **do not build until flagship content library is mature**

**Foundation (frozen):** [2026-07-29-flagship-coaching-quality-standard.md](./2026-07-29-flagship-coaching-quality-standard.md)

---

## Goal

Coaching should feel like **ongoing private lessons with the same instructor** — not a static page the user re-reads every session. The teacher remembers what happened last time and adjusts.

Today the system is:

- **Song-aware** — curated masterclass profiles per flagship title  
- **Instrument-aware** — piano / guitar / winds / voice paths  
- **Level-aware** — Beginner / Intermediate / Advanced lesson blocks  

The next evolution is **progress-aware** coaching that adapts over time.

---

## What progress-aware means

### Section struggle → deeper section guidance

If a player repeatedly struggles with the **Intro**, coaching should naturally become more specific about that section (count-in, first chord, tempo lock, mood setup) rather than repeating generic song-level advice.

### Rhythm mastered → shift toward interpretation

If rhythm accuracy is consistently strong (logs, recording analysis, timing missions), coaching should **stop reminding about steady tempo** and move toward expression, dynamics, phrasing, and musical storytelling.

### Performance mode → confidence and consistency

When the user is preparing for a performance (setlist, gig mode, or explicit “performance prep” intent), coaching emphasizes:

- Musical storytelling and arc  
- Confidence under repetition  
- Consistency across full run-throughs  
- Recovery when something slips mid-song  

…rather than basic technique reminders.

### Improvement over time → advancing advice

As the student develops, coaching should **graduate** — same song, same teacher voice, but advice that assumes prior lessons landed. Avoid repeating Beginner framing for a player who has logged dozens of clean passes on the verse.

---

## Continuity across practice sessions

The app should eventually remember (per user, per song, per instrument):

| Memory | Use in coaching |
|--------|-----------------|
| What they struggled with last time | Lead with that section or skill in the next session opener |
| What improved since last session | Acknowledge progress; reduce redundant reminders |
| What still needs attention | Set the session’s primary focus |
| Suggested next practice goal | “Before you leave the practice room” becomes personalized |

**Experience target:** Returning to California Dreamin' on Tuesday feels like the **second lesson** with the same teacher who was there on Monday — not like opening a new help page.

---

## Likely data sources (existing + future)

No new architecture required today; future layers can read from:

- **Practice Log** — sections practiced, duration, focus tags, instrument/key  
- **Upload Analysis / timing missions** — rhythm accuracy, pitch stability, section scores  
- **Tone & Tuner History** — intonation trends  
- **AMI synthesis** — cross-session “needs work” / “improved” narratives (already partially built)  
- **Active Song state** — last section focus, groove, BPM, written key  
- **Performance setlist / karaoke queue** — performance-prep context  

---

## Proposed layering (when we build)

Keep the **frozen** content layer intact; add an **adaptation layer** on top:

```text
song_performance_profiles.py     # Static masterclass — authored, song-specific (FROZEN style)
        ↓
song_performance_coaching.py     # Lookup + woven prose API (FROZEN surface)
        ↓
coaching_adaptation.py (future)  # Progress-aware deltas only
        ↓
musician_coaching.py / UI        # Same surfaces; richer copy when memory exists
```

**Rules for the adaptation layer:**

1. Never replace flagship voice with generic templates — **adapt within the song’s personality**.  
2. Adaptation = emphasis and ordering, not a second authoring system.  
3. Fall back silently to static masterclass when no session memory exists.  
4. Persist coaching memory in the same persistence family as Practice Log / AMI (local + optional cloud).

---

## Example behaviors (illustrative)

**Static (today):**  
> The verse feels reflective and unhurried—keep your strumming in the background…

**Progress-aware (future):**  
> Last session the Intro kept rushing ahead of the vocal—today, stay on the first two bars until they feel settled before you move into the verse. The verse still wants that same unhurried porch feel…

**Static performance prep (future variant):**  
> Before the gig: run Intro → Verse → Chorus once without stopping; your job is consistency of mood, not new ideas.

---

## Phased rollout (suggested, not scheduled)

| Phase | Scope | Depends on |
|-------|--------|------------|
| **0** (now) | Flagship masterclass content library | Quality standard doc |
| **1** | Session memory: last section focus + last log summary in Coach opener | Practice Log |
| **2** | Section weakness hints from upload/timing analysis | Upload Analysis |
| **3** | Graduated advice by level + logged mastery heuristics | Logs + missions |
| **4** | Performance-prep mode copy branch | Setlist / user intent |
| **5** | Full AMI-integrated “next lesson plan” | AMI synthesis |

---

## What not to do before Phase 0 is strong

- Do not add hundreds of thin catalog profiles.  
- Do not bolt LLM-generated coaching onto non-flagship songs without the same quality bar.  
- Do not redesign `song_performance_profiles` schema unless adaptation layer requires optional fields (e.g. `performance_prep`, `graduated` blocks) — prefer overlay over schema churn.

---

## Success criteria (future)

- User quotes coaching that **references their last session** accurately.  
- Repeat visitors see **less repetition** of solved problems.  
- Performance prep sessions feel distinctly different from first-time learning sessions.  
- Flagship voice remains recognizable — progress-aware California Dreamin' still could never be Hotel California.
