# Flagship coaching quality standard

**Last updated:** 2026-08-01  
**Phase 1:** **Complete** — architecture stable; all future work is **content quality**  
**Status:** **FROZEN foundation** — required for every new flagship song profile  
**Future evolution:** [2026-07-29-progress-aware-coaching-vision.md](./2026-07-29-progress-aware-coaching-vision.md) (vision only; do not redesign this framework)

## Architecture policy

**Phase 1 of the coaching system is complete.** The framework is stable. Do not redesign routing, schema, or UI surfaces unless a regression fix is required.

**Ongoing work = handcrafted content:** write exceptional, song-specific masterclass profiles in `song_performance_profiles.py` — **one flagship at a time**, each passing final quality review before it is considered done.

Prefer a **smaller library of outstanding flagships** over many thin entries.

## The handcrafted principle

The architecture is reusable; the **experience must never feel templated**.

Every flagship song should feel like an **experienced musician sat down and personally wrote a lesson for that specific song** — not like someone filled in a form. Reusable code behind the scenes is fine; interchangeable prose in front of the musician is not.

**Long-term product goal:** Coaching becomes one of the **defining features** of the Music Practice Coach. Someone opens the app, reads the coaching for a song, and immediately feels they are working with an outstanding private instructor.

## Purpose

Flagship song coaching should read like **masterclass notes from a private instructor**, not chart documentation or template fragments. A musician should be able to read the coaching for California Dreamin', Hotel California, or Perfect and immediately know which song they're in.

## Educational feature completion — three pillars (all coaching surfaces)

Use this checklist for **every new or revised educational feature** (Live Coach, Harmony Map, Missions, Phrase & Motif, Deep Harmonic Analyzer, Practice coaching, Composition Studio examples, future AI coaching). A feature is not complete until all three pass.

### 1. Theory correctness

- Scale names, displayed notes, and underlying interval definitions **match** (single pipeline: `build_scale_suggestion` / `music_theory`).
- Chord tones, extensions, and avoid-note advice match **classified chord quality** and **key-signature spelling** (`display_key` / chart key for the musician).
- Terminology is musically accurate (guide tones, tensions, modes, “Mission” vs “Motif”, etc.).

### 2. Educational correctness

- Generated or suggested examples **clearly teach** the concept on screen (not generic filler).
- Copy reads like an **experienced private teacher** — purposeful, not template soup.
- Advice matches **level** (Beginner / Intermediate / Advanced) and **focus** (rhythm, harmony, scales, etc.).

### 3. Consistency

- Same theory pipeline and spelling rules across **all coaching surfaces** for the same chord/key/instrument context.
- UI language matches the feature (e.g. Missions → “Mission Example”; Phrase & Motif → “Motif”).
- Behavior is predictable when the user changes chord, section, or setup controls.

**Depth-first audits:** Improve one surface at a time to this standard before scattering small fixes app-wide.  
**Current pass:** Live Coach + Harmony Map (2026-08-01).

## The three questions (every profile must answer these)

For each flagship song, coaching must address:

1. **What is happening musically?** — form, mood, harmonic motion, groove, dramatic arc  
2. **How should I play it?** — technique tied to musical purpose, not isolated commands  
3. **What should I be feeling and listening for?** — interpretation, attention, emotional intent  

These three are **woven together** in natural prose — never separated into disconnected bullet lists like "Play softly" / "Watch dynamics."

## Explain why, not only what

| Avoid | Prefer |
|-------|--------|
| "Play softly." | "Keep the accompaniment in the background so the melody feels intimate—the piano should support the story rather than become the focus." |
| "Increase dynamics." | "Allow the energy to build naturally into the chorus. Imagine the emotion becoming harder to contain rather than simply playing louder." |
| "Steady rhythm." | "The half-bar bass steps will tempt you to rush when the lyric feels urgent—practice them as a walk you could hum slowly." |

## One voice, one song

- Every flagship song gets its **own personality and vocabulary**.  
- Reject phrases reused across songs ("keep a steady rhythm," "play smoothly," "focus on transitions").  
- If two songs could share the same paragraph unchanged, rewrite one of them.  
- `interpretation` fields hold the song's unique worldview; `lessons.journey` carries that voice through the form.

## Profile schema (`song_performance_profiles.py`)

```text
interpretation/          # Song-level worldview (used everywhere)
  emotional_character      # What is happening emotionally?
  listen_for               # What should the ear track?
  build_where / relax_where
  accompaniment            # Role of the player
  rush_prone               # Where tempo slips
  key_transitions          # Woodshed spots
  master_challenge         # The big performance question

lessons/<level>/<instrument>/
  card_summary             # Active Song card + chart subtitle (~20–40 sec read)
  challenge_summary        # One-line card "Challenge" (musician language)
  harmony_summary          # One-line card "Harmony" (listening/feel)
  opening                  # Coach tab hook (one clear idea)
  coach_context            # Optional: 1–2 sentences of musical context (Coach tab only)
  journey[]                # In song order when rendered; use section for repeats
    section                # Optional: "Verse 1", "Verse 3" — overrides role-only match
    role                   # _role:intro | verse | chorus | ...
    heading                # Short lesson title (overlay + practice page)
    body                   # Woven: musical context + how + feel/listen
  closing                  # "Before you leave the practice room"

practice_focus/            # Scan line for Active Song card
harmony_tips/              # Optional section-level listening hints
```

## Lesson arc through the form

Each `journey` step should match the section's **musical job**:

| Section | Teaching focus |
|---------|----------------|
| Intro | Prepare the player — mood, tempo, space |
| Verse | Feel, groove, intimacy |
| Chorus | Energy, expression, lift (often harmonic, not just louder) |
| Instrumental | Phrasing, dynamics, narrative deepening |
| Outro | Satisfying close — how the song walks away |

The journey should read as **one continuous lesson**, not independent tips pasted together.

## Consistency across the app

All surfaces pull from the same profile via `song_performance_coaching.py`:

| Surface | API |
|---------|-----|
| Active Song card summary | `instructor_card_summary()` (~20–40 sec; never full interpretation essay) |
| Active Song practice focus | `practice_focus_for_song()` |
| Chart header subtitle | `musician_summary_paragraph()` → card summary + key line |
| Coach tab | `masterclass_lesson_markdown()` — song-order journey |
| Section overlay | `section_coaching_for_song()` + `section_lesson_heading()` |
| Practice page section focus | Same as overlay |
| Harmony hints | `harmony_tip_for_song()` |

Generic fallbacks in `musician_coaching.py` exist only for **non-flagship** songs.

## Clarity over volume

Avoid overexplaining. **One memorable paragraph is often more valuable than five paragraphs of technical advice.**

Prioritize:

- **Clarity** — plain language, one clear idea per beat  
- **Musicality** — why the music wants what it wants  
- **Inspiration** — copy that makes someone want to pick up their instrument  

Cut anything that repeats, generalizes, or reads like documentation. If a journey step doesn't earn its length, shorten it.

## Final quality review (required before a flagship is “complete”)

Every flagship must pass this review — read aloud, slowly, as if speaking to a student:

| Question | Pass? |
|----------|-------|
| Does this sound like something a **great private teacher** would actually say? | |
| Does it teach **interpretation** as well as technique? | |
| Does it explain **why** the player should approach the music this way? | |
| Does it capture the **unique personality** of this song? | |
| Would this advice **clearly belong to this song** and not another one? | |
| Is the language **simple, encouraging, and enjoyable** to read? | |
| Does it **inspire someone to start playing**? | |

If any answer is no, revise the profile before merge. Do not ship “good enough.”

## Authoring checklist (before merging a new flagship)

- [ ] Read the full Coach tab aloud — does it sound like one teacher wrote it?  
- [ ] Swap the song title in three random sentences — does it break? (It should.)  
- [ ] Every journey `body` weaves musical context + technique + listening  
- [ ] No bullet-list interpretation block in user-facing copy  
- [ ] `opening` and `closing` bookend the lesson  
- [ ] Beginner level is simpler but still song-specific (not generic strum advice)  
- [ ] Tests in `test_song_performance_coaching.py` cover the new song  
- [ ] Compare side-by-side with an existing flagship — voices must differ clearly  
- [ ] **Final quality review** table above — all questions pass  
- [ ] Nothing feels templated; prose could not be copy-pasted to another song  

## Current flagship library

California Dreamin', Perfect, Shallow, Hotel California, All of Me, Say

## Adding a new flagship

1. Write the full profile in `song_performance_profiles.py` (handcrafted — not assembled from shared snippets)  
2. Register title in `CURATED_PERFORMANCE` (via normalized key)  
3. Add tests asserting song-specific voice (not generic phrases)  
4. Smoke-test: Active Song card, Coach tab, one section overlay, Practice page  
5. Complete **final quality review** — only then mark the song complete  
