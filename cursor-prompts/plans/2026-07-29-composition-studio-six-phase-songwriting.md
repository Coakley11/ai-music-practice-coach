# Composition Studio — Six-Phase Songwriting UX

**Last updated:** 2026-07-29  
**Status:** CS-B4 shipped — coach-first Lyrics phase on `dev`; CS-B5 Review next  
**Branch:** `dev`  
**Supersedes step order in:** [2026-07-29-composition-studio-guided-ux.md](./2026-07-29-composition-studio-guided-ux.md) (structure moved before chords; Review added)  
**Technical foundation:** [2026-07-29-composition-studio-v1-architecture.md](./2026-07-29-composition-studio-v1-architecture.md) · Sprint A (`5c49432`)

---

## Product promise

**An experienced songwriter sits beside you and helps you create an original song from scratch—one creative decision at a time.**

Every screen answers **“What should I create next?”** not **“What settings do you want to edit?”**

---

## CPL vs Composition Studio

| | Custom Progression Lab | Composition Studio |
|--|------------------------|-------------------|
| **Metaphor** | Lab bench / jam pad | Guided songwriting session |
| **Opening question** | “What chords are you working with?” | “What kind of song do you want to write?” |
| **Success** | Great progression + backing | A **complete original song** |
| **Chord UI** | Primary, always visible | Phase 3 only; coach-guided |
| **Structure** | Implicit (one progression) | Designed **before** harmony (Phase 2) |
| **Exit** | Backing, Practice, improv | Review → save → future Practice/Backing |

Nav copy: CPL *“Progressions & jam”* · Composition *“Write a song from scratch.”*

---

## What Sprint A already gives us (keep)

| Asset | Module | Reuse in guided UX |
|-------|--------|-------------------|
| `CompositionDocument` | `composition_document.py` | Single song object across all phases |
| Library save/load | `composition_session_state.py` | Resume / My compositions |
| Preview audio | `composition_preview.py` | Phase 3+ play loops |
| Musical snapshot | `composition_snapshot.py` | Future AI coach context |
| Section CRUD | `composition_document.py` | Phase 2 structure builder |
| Chord entry / paste | CPL helpers (Phase 3 only) | Hidden from other phases |

**Retire from default UI:** CPL-like 3-column layout, seed chip grid as primary entry, chord grid visible before vision.

---

## Global shell (all phases)

```
┌──────────────────────────────────────────────────────────────────┐
│  Working title · Phase indicator · ▶ Play · Save                  │
├──────────────┬───────────────────────────────┬───────────────────┤
│  JOURNEY     │  PHASE WORKSPACE              │  COACH            │
│  (left rail) │  (one phase dominant)         │  (conversational) │
│              │                               │                   │
│  1 Vision ●  │                               │  Warm prompts     │
│  2 Structure │                               │  Explain-first    │
│  3 Chords    │                               │  stubs → AI later │
│  4 Melody    │                               │                   │
│  5 Lyrics    │                               │                   │
│  6 Review ✓  │                               │                   │
└──────────────┴───────────────────────────────┴───────────────────┘
```

### Document `workflow` extension

```json
"workflow": {
  "current_phase": "vision | structure | chords | melody | lyrics | review",
  "completed_phases": ["vision"],
  "locks": {
    "vision": false,
    "structure": false,
    "chords": false,
    "melody": false,
    "lyrics": false
  }
}
```

- **Soft gates:** user can revisit completed phases; editing an earlier phase shows a one-line consequence warning.
- **Skip ahead (advanced):** allowed with explicit confirm (e.g. instrumental writer skips lyrics).
- **No AI required** for v1 — coach panel uses warm copy + rule-based stubs; proposal card shape reserved for Sprint C.

---

## Phase 1 — Song Vision

**Goal:** Begin a creative session—not a settings form.

### Conversational prompts (center column)

1. What kind of song do you want to write?
2. What emotion should listeners feel?
3. What genre are you aiming for?
4. What artists or songs inspire this idea?
5. What energy level are you looking for? (ballad / mid-tempo / driving)

Free-text **song idea** paragraph: theme, story, image, working title.

### Musical basics (after creative questions—not first)

- Practice key (dropdown)
- Tempo (BPM or feel band)
- Time signature

### Coach panel

- Reflects back: “So we're writing a **melancholy pop ballad** inspired by **Adele**, about **distance**—got it.”
- Stub chips: *Help me clarify · Suggest a title · What key fits this mood?* (no chord generation here)

### Completion

**Continue to structure →** writes `metadata` (mood, genre, references, energy), `global` (key, bpm, meter), `origin.seed_summary`.

---

## Phase 2 — Song Structure

**Goal:** Design form **before** writing chord progressions.

### Visual form builder

Default template by genre (editable):

`Intro → Verse → Pre-Chorus → Chorus → Verse → Chorus → Bridge → Chorus → Outro`

User can:

- add / remove sections
- reorder (drag or up/down)
- duplicate (e.g. Verse 1 → Verse 2)
- rename labels

Each section starts as an **empty slot** (no chords yet)—only name + order + optional repeat count.

### Coach panel

- “Suggest a form for a pop ballad with your vision” (stub → AI later)
- Pacing notes as explain cards

### Completion

**Continue to chords →** locks structure order; creates empty section instances in document.

---

## Phase 3 — Chord Progressions

**Goal:** Harmonize the song—guided, not a blank grid.

### Workflow

1. **Section picker** — work one structure section at a time (or “apply to all Verses”).
2. **Coach-first** — “Suggest 3 progressions for this section” (stub cards with *why* placeholders).
3. **Manual path** — “Add chords myself” secondary (collapsed); bar timeline reuses CPL HTML **only here**.
4. **Compare queue** — Try · Use · Blend (preview wired to `composition_preview`).
5. **What-if stubs** (no AI yet): simpler · more tension · jazzier · modulate (disabled or local-only later).

Rhythm/groove for audition lives here (BPM/meter from Phase 1 editable).

### Completion

**Continue to melody →** marks sections with chord content; empty sections allowed with reminder on Review.

---

## Phase 4 — Melody

**Goal:** Melody framework—no AI generation yet.

### UI

- Read-only harmony strip for active section
- Phrase blocks per section (simple note entry or ABC/motif paste v1)
- Section tabs aligned with Phase 2 structure

### Coach panel

- Stub: “When AI arrives: 3 melody ideas that fit these changes”
- Display-only tips from local rules (chord tones, contour) optional

### Completion

**Continue to lyrics →** melody phrases stored per section (may be partial).

---

## Phase 5 — Lyrics

**Goal:** Words organized by section—ready for future AI suggestions.

### UI

- Section tabs from structure
- Clean stanza/line editor per section
- Read-only chips: vision summary + locked key/tempo

### Coach panel

- Theme brainstorm stubs tied to Phase 1 vision
- Syllable hints display-only (future: AI line suggestions)

### Completion

**Continue to review →**

---

## Phase 6 — Review

**Goal:** Complete song overview—edit anywhere, play through.

### Overview panels

| Panel | Content |
|-------|---------|
| Structure | Full form with completion badges |
| Chords | Per-section progression summary |
| Melody | Phrase summary per section |
| Lyrics | Section lyrics |
| Settings | Key, tempo, meter, vision recap |

### Actions

- Jump to any phase to edit (with soft unlock warning)
- **Play full song** (preview in section order; silence/sketch for empty sections)
- **Mark song ready** → library status `ready` (draft default)
- Save / duplicate / export hooks (Practice/Backing integration later)

---

## Implementation sprints (post-coaching)

| Sprint | Deliverable | AI |
|--------|-------------|-----|
| **CS-B0** | Entry (resume/begin), journey rail, phase routing, Phase 1 Vision UI, remove CPL-like default layout | Stubs |
| **CS-B1** | Phase 2 Structure builder (visual reorder/add/duplicate) | Stubs |
| **CS-B2** | Phase 3 Chords (coach-first, manual secondary, preview) | Stubs |
| **CS-B3** | Phase 4 Melody framework | None |
| **CS-B4** | Phase 5 Lyrics by section | None |
| **CS-B5** | Phase 6 Review + full-song play | None |
| **CS-C** | OpenAI proposals per phase (parallel once B2+ stable) | Live |

**Do not** extend Sprint A layout—replace shell in CS-B0.

---

## Acceptance criteria

1. New user describes Composition Studio in one sentence **without** “chord grid.”
2. First screen is **vision questions**, not chord chips.
3. **Structure appears before chords** in the journey rail.
4. Side-by-side screenshot: CPL vs Composition clearly different in 30 seconds.
5. User can complete Vision → Structure → lock one Verse progression → hear it **without** seeing CPL-style hero chord buttons.
6. Review phase shows all five creative layers in one place.
7. No mid-flow link “edit in Custom Progression Lab” (footer cross-link only).

---

## Creative question per phase (locked)

| Phase | Question |
|-------|----------|
| Song Vision | What kind of song do I want to write? |
| Song Structure | How should the song unfold? |
| Chords | What harmony best supports each section? |
| Melody | What musical idea will people remember? |
| Lyrics | What story or message am I telling? |
| Review | Is this song complete and ready? |

---

## Design decisions (locked 2026-07-29)

| Topic | Decision |
|-------|----------|
| **Minimum Vision fields** | **Genre** + **1–2 sentence song idea** only. Mood, energy, tempo, key, meter suggested automatically; editable later. |
| **Chord scope (CS-B2)** | Repeated sections (Verse 2, Chorus 2) **inherit** from first instance by default; **linked** until user breaks link. |
| **Writing instrument** | **Instrument-agnostic.** Composition creates the song; Practice teaches it on the sidebar instrument. No separate writing-instrument picker. |
| **Instrumental songs** | **Lyrics optional.** `workflow.skip_lyrics` skips Lyrics phase → Review. |
| **Journey rail** | Always visible; current step highlighted; **backward navigation anytime**; forward via Continue (completed phases revisitable). |

---

## Open questions

1. ~~Minimum Phase 1 fields~~ — **Resolved:** genre + song idea only.
2. ~~Per-section vs global chords~~ — **Resolved:** linked inheritance for repeats (CS-B2).
3. ~~Composition instrument~~ — **Resolved:** instrument-agnostic.
4. ~~Instrumental path~~ — **Resolved:** skip lyrics → review.

---

## Notes

- Persistence: new `composer` page bucket only; frozen Tests A–E untouched.
- Coach voice should match flagship songwriting tone (warm, second person)—reuse patterns from `musician_coaching.py` prose style, not chart jargon.
