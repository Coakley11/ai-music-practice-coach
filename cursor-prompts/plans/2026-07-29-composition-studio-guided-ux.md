# Composition Studio — Guided Songwriting UX (design proposal)

**Last updated:** 2026-07-29  
**Status:** Superseded step order — see [six-phase songwriting plan](./2026-07-29-composition-studio-six-phase-songwriting.md) (Structure before Chords; Review as Phase 6)  
**Supersedes (partially):** Sprint A workspace layout in [2026-07-29-composition-studio-v1-architecture.md](./2026-07-29-composition-studio-v1-architecture.md)  
**Branch:** `dev` after Sprint A (`5c49432`) + egress (`52ab408`)

---

## Why redesign now

Sprint A proved the **technical foundation** (document, snapshot, preview, library). Hands-on use showed the **experience** still reads as “Custom Progression Lab plus extras”:

- Three-column **form + chord grid + lanes** mirrors CPL’s builder mental model.
- **Seed chips** feel like alternate entry fields, not a creative journey.
- **Structure** and **chords** compete for attention before the user has a clear **song vision**.

**Custom Progression Lab** owns: *I have chords → jam → backing → practice.*

**Composition Studio** must own: *I want an **original song** → guided decisions → finished composition.*

This proposal replaces the Sprint A **layout and navigation** with a **step-based coach workflow**. Backend concepts (`CompositionDocument`, `build_composition_snapshot`, proposal cards, preview) stay; the **shell** changes.

---

## Product promise (one sentence)

**An experienced songwriter sits beside you and walks you through five creative decisions—vision, harmony, melody, words, and form—one at a time, with hear-before-you-keep experimentation.**

---

## CPL vs Composition Studio (user-facing)

| | Custom Progression Lab | Composition Studio |
|--|------------------------|-------------------|
| **Opening question** | “What chords are you working with?” | “What kind of song are you writing?” |
| **Success** | Great progression + backing | A **song** you wrote (vision → form) |
| **UI metaphor** | Builder / lab bench | **Guided session** with a coach |
| **Chord UI** | Primary, always visible | Step 2 only; hidden elsewhere |
| **AI role** | Secondary (future / analysis) | **Coach** in every step (explain + suggest) |
| **Exit** | Backing, Practice, improv | Save song (Practice/Backing later) |

Cross-link in nav copy: CPL subtitle *“Progressions & jam”* · Composition *“Write a song from scratch.”*

---

## Entry (before Step 1)

### Resume or begin

```
┌─────────────────────────────────────────────────────────┐
│  Composition Studio                                      │
│  Write an original song—with a coach, one step at a time. │
├─────────────────────────────────────────────────────────┤
│  [ Begin a new song ]     [ Continue: "Working Title" ] │
│  My compositions ▾                                       │
└─────────────────────────────────────────────────────────┘
```

- **No** CPL-style chord chips on this screen.
- Optional: “I already have a chord sketch” → still starts at **Step 1**, then Step 2 opens with paste prefilled (not a separate product path).

### Document state: `workflow`

Add to document (design only; schema when implementing):

```json
"workflow": {
  "current_step": "vision | chords | melody | lyrics | structure",
  "completed_steps": ["vision"],
  "locks": {
    "vision": true,
    "chords": false,
    "melody": false,
    "lyrics": false,
    "structure": false
  }
}
```

- **Lock** = user explicitly confirmed that step (“This is my progression”, “Lock melody for this section”).
- User may **unlock** a step with confirmation (warn: later steps may need review).
- **Jump back** to any completed step; **forward** only to current or next unlocked step (soft gate, not a prison—see Non-linear rules).

---

## Global shell (all steps)

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Song title · Step indicator · ▶ Play (contextual) · Save         │
├──────────────┬───────────────────────────────┬───────────────────┤
│  JOURNEY     │  STEP WORKSPACE               │  COACH            │
│  (fixed)     │  (one step dominant)          │  (conversation)   │
│              │                               │                   │
│  1 Vision ✓  │                               │  Explained        │
│  2 Chords ●  │                               │  proposals        │
│  3 Melody    │                               │  Try · Apply      │
│  4 Lyrics    │                               │                   │
│  5 Structure │                               │                   │
└──────────────┴───────────────────────────────┴───────────────────┘
```

- **Journey rail (left):** 5 steps, status icons (empty · in progress · locked complete). Click to revisit completed steps.
- **Step workspace (center):** Only the active step’s tools—no chord grid on Melody step.
- **Coach (right):** Step-aware prompts, “What if…?” chips, proposal stack. Same component across steps; **context** from `build_composition_snapshot`.

### Transport

- **Play** always audible for **current step context**:
  - Vision: optional style reference loop (tempo/style only) or disabled until chords exist.
  - Chords: progression for active section or “sketch section”.
  - Melody: harmony + melody overlay.
  - Lyrics: optional rhythm-only or hum track (later).
  - Structure: full song order.

### Persistence of Sprint A assets

| Keep (engine) | Retire from default UI |
|---------------|-------------------------|
| `CompositionDocument`, library, preview | 3-column CPL-like layout |
| Snapshot builder | Lane tabs (chords/rhythm/structure) |
| Chord entry model (Step 2 internal) | Seed chip grid as primary entry |
| Section instances in data model | Structure-first editing before Step 5 |

---

## Step 1 — Song Vision

### Goal

Establish **creative direction** the coach (and rule engine / AI) uses everywhere else. No chord grid.

### User sees

- **Style** — cards or select (Jazz, Pop, Rock, Blues, Folk, Worship, Film, …).
- **Mood** — chips + free text (melancholy, hopeful, gritty, …).
- **Feeling / intent** — short text: “What should the listener feel?”
- **Song idea** — paragraph: theme, story, image, title idea.
- **Optional:** tempo feel (ballad / mid / uptempo), key preference (“bright”, “dark” → suggests key later).

### Coach behavior

- Reflects back: “So we’re aiming for a **jazz ballad**, **melancholy**, about **distance**—got it.”
- Optional button: **“Help me clarify my vision”** → AI questions or 2–3 reframed vision summaries (user picks one, edits).
- **No** chord or melody generation on this screen.

### Completion

**Continue to chords →** sets `workflow.locks.vision = true`, writes `metadata` + `global` defaults (style, mood, BPM band), `origin.seed_summary`.

### Empty states

First-time users never see an empty chord editor. They see vision questions and one primary CTA.

---

## Step 2 — Chord Progression

### Goal

Compose (with coach) a **harmonic foundation** for the song—not a multi-section production chart yet. Think **harmonic sketch** that can later map to Verse/Chorus.

### Phase A — Sketch (default)

- One **primary section** label: “Song sketch” or “Verse idea” (not full form yet).
- **Coach-first panel:**
  - “Suggest 3 progressions for my vision”
  - Each card: chord symbols + **why** (tension, release, color, style fit).
  - **Try** (play) · **Use this** · **Blend with mine**
- **User path:** manual entry still available but **secondary** (“Add a chord myself”) collapsed or subordinate—not the hero UI.

### Phase B — Refine

- Bar timeline (reuse CPL HTML **only here**).
- **What if:** reharm, substitution, modulate, “more jazzy”, “simpler”.
- Compare queue (2–4 progressions).

### Lock progression

**“Lock this progression”** button:

- Sets `workflow.locks.chords = true`.
- Stores canonical sketch in document (sections + chords).
- Coach: “Harmony locked. Ready to write a melody that lives on these changes.”

### Unlock

Warning: melody/lyrics suggestions may shift if harmony changes.

### Rhythm

BPM, meter, groove live **here** (supporting harmony audition)—not a separate “rhythm lane” tab.

---

## Step 3 — Melody

### Goal

**Melody only**—full center column; no chord editor (harmony read-only strip).

### User sees

- Read-only **locked progression** (compact timeline + play).
- **Melody workspace:** phrase blocks per “sketch section” (Sprint B engine).
- Piano-roll optional later; v1 = phrases + optional simple note entry.

### Coach

- “Generate 3 melody ideas for this progression”
- Each: notation summary + **why it fits** ( chord tones, tension notes, contour ).
- **Compare:** step through with shared transport.
- User writes own phrase alongside.

### Lock

Per-section or whole-sketch: **“Lock melody”** when satisfied.

---

## Step 4 — Lyrics

### Goal

Words that fit **vision + melody + style**.

### User sees

- Locked harmony + melody summary (read-only, expandable).
- Lyric editor (lines / stanza).
- Syllable/scansion hints (display-first; not auto-rewrite without consent).

### Coach

- Brainstorm themes aligned with Step 1 vision.
- “Suggest lines for this melody” (proposals per line or stanza).
- Revise: clearer, more poetic, tighter rhyme—always as cards.

### Lock

**“Lock lyrics”** for sketch section or song.

---

## Step 5 — Song Structure

### Goal

Turn sketch into **form**: Intro, Verse, Chorus, Bridge, Outro, order, repeats.

### User sees

- **Form builder:** add/reorder sections (Sprint A structure logic, new presentation).
- Map sketch chords/melody/lyrics → sections (duplicate sketch to Verse/Chorus, then edit deltas).
- Full-song **Play**.

### Coach

- “Suggest a form for a pop ballad with this material”
- Pacing notes: “Bridge before final chorus adds contrast because…”

### Done

**“Mark song ready”** (draft → ready) — library status; future Practice/Backing hooks.

---

## Coach panel (cross-cutting UX)

### Always

- Speaks in **second person** to the user as co-writer.
- **Proposals only** — Try · Apply · Dismiss.
- Every suggestion includes **musical_effect** tags + short **reasoning**.

### Step-specific starter chips

| Step | Example chips |
|------|----------------|
| Vision | Clarify mood · Suggest title ideas · What key fits this mood? |
| Chords | 3 progressions · More tension · Simpler · Jazzier substitutions |
| Melody | 3 hooks · Answer the chord changes · More lyrical contour |
| Lyrics | Theme brainstorm · Fix this line · Match syllables to melody |
| Structure | Pop form · Add a bridge? · Shorten intro |

### Without API key

Same cards; reasoning from **local theory** templates (already planned).

---

## Non-linear rules (avoid wizard fatigue)

1. **Within a step:** explore freely (play, compare, undo).
2. **Across steps:** completed steps clickable; editing a locked earlier step requires **unlock** with one-line consequence.
3. **Skip ahead (advanced):** “I’m ready to jump to lyrics” allowed if user confirms they accept empty melody (coach warns).
4. **Not** a single long form—all steps remain separate screens sharing one document.

This replaces the earlier architecture note that discouraged “lane order.” **Guided steps** are explicit product choice for Composition Studio only; CPL unchanged.

---

## Mobile / narrow

- Journey rail → **horizontal stepper** or dropdown (“Step 2 of 5: Chords”).
- Coach → bottom sheet.
- Play sticky footer.

---

## What Sprint B becomes (after UX approval)

| Phase | Deliverable |
|-------|-------------|
| **B0 — Guided shell** | Journey rail, step routing, locks, Step 1 Vision UI, Step 2 coach-first chords (manual subordinate), remove CPL-like default layout |
| **B1 — Melody step** | Step 3 workspace + compare play |
| **B2 — Lyrics step** | Step 4 |
| **B3 — Structure step** | Step 5 + map sketch → form |
| **C — AI** | OpenAI proposals per step (can parallel B1+ with rule-based stubs first) |

**Pause** melody/lyrics/AI feature code until **B0** design is approved and implemented.

---

## Acceptance criteria (UX review)

1. New user can explain what Composition Studio does in one sentence **without** mentioning “chords grid.”
2. First screen is **vision**, not chord buttons.
3. CPL and Composition feel **distinct** in a 30-second side-by-side screenshot test.
4. User can complete Vision → lock chords → hear progression **without** seeing Verse/Chorus structure UI.
5. Coach panel is present on every step with explain-first proposals (stub text OK in B0).
6. “Custom Progression Lab” is never linked as “go there to edit chords” from Composition mid-flow (optional footer link only).

---

## Open questions for product sign-off

1. **Strict order** vs allow **Structure** before **Lyrics** for instrumental writers?
2. Single **harmonic sketch** vs **per-section** chords from Step 2 onward?
3. **Instrument** from global studio bar visible during composition, or composition-local “writing instrument” (piano/voice/guitar)?
4. Step 1: require all fields or minimum (style + one sentence idea)?

---

## Notes

- Technical architecture (document, snapshot, egress, library) remains valid.
- Update [music_app_tasks.md](../music_app_tasks.md) when B0 is scheduled.
