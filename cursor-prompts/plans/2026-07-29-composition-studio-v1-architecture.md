# Song Composer / Composition Studio — V1 architecture

**Last updated:** 2026-07-29  
**Status:** Sprint A in progress (core page + document + preview landed on `dev`)  
**Branch target:** `dev`  
**Related:** Custom Progression Lab (`custom`), Creative Lab motifs, `custom_song_library.py`, backing engine

---

## Product philosophy (north star)

**Metaphor:** an experienced composer sitting beside the musician — not a clerk handing over a checklist.

| Principle | What it means in product |
|-----------|---------------------------|
| **User is the composer** | AI proposes, explains, and auditions; the user commits every note, chord, and line. |
| **Start anywhere** | Composition begins from whatever the user already has — one seed is enough; the studio grows around it. |
| **Everything stays connected** | Melody, harmony, rhythm, lyrics, and form share one **musical snapshot**; suggestions in any lane read the full picture and adapt when anything changes. |
| **Explain, don’t dump** | Every option carries **musical reasoning** (tension, color, voice leading, cadence, contrast) — assistant **and** teacher. |
| **Explore, don’t optimize** | No single “correct” answer; **What if…?** is a first-class interaction (reharm, modulate, change meter, shift mood). |
| **Composition is a first-class object** | The document is the hub for future Practice, Backing, Recording, Coach, and performance — V1 nails creation; hooks are designed in from day one. |

**Anti-pattern:** lane tabs that feel like “Step 1 chords → Step 2 melody → Step 3 lyrics.” Tabs are **views** on one living song, not a form sequence.

---

## Product intent

An **AI-assisted creative composition workspace** where ideas co-evolve. Not a song editor — a place to **develop** music with constant **play → compare → keep** loops.

**Differentiator from Custom Progression Lab:** CPL is harmony-first for practice/improv/backing. Composition Studio is **song-first** and **seed-first**: melody, harmony, groove, words, title, emotion, or style can all be the spark.

---

## 0. Start from any seed (V1 entry)

### Seed types

| Seed | User brings | Studio initializes |
|------|-------------|-------------------|
| **Melody** | Notes, hum-described contour, or motif from Creative Lab | Section + phrases; harmony/rhythm/lyrics empty; AI prioritizes harmonization |
| **Chords** | Progression (paste or build) | Sections + chord timeline; melody/lyrics open |
| **Rhythm / groove** | BPM, meter, style feel | Global rhythm locked; harmony/melody suggestions respect grid |
| **Lyric** | Line, stanza, or theme | Lyrics lane + inferred syllable/meter hints; melody phrasing suggestions follow text |
| **Title** | Working title | Metadata + optional AI “what might this song be about?” |
| **Emotion / mood** | e.g. “bittersweet”, “triumphant” | `metadata.mood` drives color of all suggestions |
| **Style only** | e.g. “jazz ballad” | Style + default form template (editable); empty lanes with style-aware prompts |
| **Blank + intent** | Natural language in composer chat | Parse intent → set metadata + optional template; never auto-fill without proposals |

### Entry UX (not a wizard)

**“What do you have so far?”** — single screen with:

- Quick chips: *Melody · Chords · Groove · Lyrics · Title · Mood · Style · Just exploring*
- One **free-text** box: “I want to write a jazz ballad about distance.”
- Optional **paste** areas (chords, lyric, ABC/motif) revealed by chip

Result: one `CompositionDocument` with `origin` recorded:

```json
"origin": {
  "seed_type": "style_intent | melody | chords | rhythm | lyrics | title | mood | mixed",
  "seed_summary": "user-facing description",
  "seed_payload": { }
}
```

**Sprint A** implements seed capture + document bootstrap (AI expansion can wait until Sprint C; rule-based “first section + style defaults” is enough to validate flow).

---

## 1. Ideal workflow

### Core loop (composer-at-the-piano)

```text
Listen / imagine
    → Change something (any lane) OR ask "What if…?"
    → See explained options (not opaque lists)
    → Play (section or experiment sandbox)
    → Keep, blend, or keep exploring
    → Autosave
```

Lanes are **where you look**, not **what you must finish in order**.

### Coupling rule (musical connectivity)

When **any** committed field changes, invalidate dependent suggestion caches and refresh the **composition snapshot** used by AI and analysis:

| Change | Downstream that must re-read state |
|--------|-------------------------------------|
| Melody | Chord suggestions, reharm experiments, lyric stress hints |
| Harmony | Melodic suggestions, tension/release analysis, groove emphasis |
| Groove / meter | Rhythmic melody variants, lyric scansion, chord duration feel |
| Lyrics | Melodic phrasing, syllable fit, rhyme-aware line variants |
| Structure | Context window for all section-scoped suggestions |

Implementation: **`build_composition_snapshot(doc)`** — single canonical struct (theory + summary fields) rebuilt on edit; all AI actions and rule-based fallbacks take **only** this snapshot + user prompt.

### “What if…?” (experimentation)

First-class **experiment requests** (chat or chip), each producing a **branch proposal** — not applied until accepted:

| Example prompt | Experiment type | Output |
|----------------|-----------------|--------|
| Reharmonize this melody | `experiment_reharm` | 2–4 harmonic maps + **why** (tension, color) |
| Make it more jazzy | `experiment_style_shift` | chord/melody/groove deltas with reasoning |
| Modulate the chorus | `experiment_modulation` | target key + approach (pivot, direct, etc.) |
| 3/4 instead of 4/4 | `experiment_meter` | meter change preview + rhythmic adaptation notes |
| More dramatic here | `experiment_intensity` | harmony + rhythm + register suggestions |

**Sandbox play:** audition experiments against current section without mutating doc until **Keep this version** (or merge selected lanes).

V1 minimum: chord/melody experiments with explain cards + A/B play; meter/modulation can be **global experiment** with confirm dialog.

### AI interaction contract

- Proposals only; never silent overwrite.
- Each proposal includes **`musical_effect` tags** and **`reasoning`** (1–3 sentences, plain language).
- Actions: **Try** (sandbox play), **Apply**, **Apply to section**, **Save as alternate**, **Dismiss**.
- Multiple valid paths — UI copy reinforces “explore”, not “pick the right one”.

### Audition contract

- **Section play** — current committed state + optional experiment overlay.
- **Compare** — step through alternates with shared transport.
- **Full song** — form order + repeats; cached backing signature.

---

## 2. Page layout (Composition Studio)

New studio page id: **`composer`** (label recommendation: **Composition Studio**).

### Desktop workspace

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  Title · key · BPM · meter · mood/style · save · ▶ Play (section | song)    │
├──────────────┬──────────────────────────────────────┬───────────────────────┤
│  FORM        │  FOCUS (lane view — not a checklist)  │  COMPOSER BESIDE YOU  │
│  sections    │  Chords | Melody | Rhythm | Lyrics    │  Chat + What if chips │
│  + map       │  + unified timeline strip             │  Explained proposals  │
│              │                                       │  Try · Apply · Dismiss│
└──────────────┴──────────────────────────────────────┴───────────────────────┘
```

**Center column:** default view is **integrated** where possible — e.g. lyrics adjacent to melody for the same section — even if implemented as tabs initially.

**Right column:** “Composer beside you” — conversational, seed-aware, explains tradeoffs.

### Navigation subtitle

*Original songs — start with any idea, develop the rest.*

---

## 3. Major components

### Shell & routing

| Component | Responsibility |
|-----------|----------------|
| `composition_studio_page.py` | Layout, seed entry, lane views |
| `composition_session_state.py` | Active doc, experiment sandbox, proposal queue |
| `composition_studio_persistence.py` | Page snapshot (new page bucket only) |

### Document & library

| Component | Responsibility |
|-----------|----------------|
| `composition_document.py` | Schema, `origin`, validation, migrations |
| `composition_library.py` | Local + cloud (`item_type`: `composed_song`) |
| `composition_snapshot.py` | **`build_composition_snapshot`** — coupled context for AI + UI analysis |

### Lane editors (V1)

Same as before (structure, chords, melody phrases, rhythm, lyrics) — editors call snapshot builder after commits.

### Audio & preview

| Component | Responsibility |
|-----------|----------------|
| `composition_preview.py` | Preview spec from doc **or experiment overlay** |
| Backing engine + `composition_melody_synth.py` | Audition harmony, groove, melody |

### AI layer

| Component | Responsibility |
|-----------|----------------|
| `composition_ai_context.py` | Snapshot + seed + section focus + experiment type → prompt |
| `composition_ai_actions.py` | Typed actions including **`experiment_*`** |
| `composition_proposals.py` | `{ payload, reasoning, musical_effect[], confidence? }` |

### Proposal card schema (teaching + exploration)

```json
{
  "id": "prop_uuid",
  "action": "suggest_chords | suggest_melody | experiment_reharm | …",
  "title": "Secondary dominants into the IV",
  "musical_effect": ["more_tension", "stronger_cadence", "jazzier_harmony"],
  "reasoning": "Brief explanation a teacher would say at the piano.",
  "payload": { },
  "audition_signature": "hash for cache"
}
```

### Shared UX

| Component | Responsibility |
|-----------|----------------|
| `composition_transport.py` | Play, loop, compare queue |
| `composition_what_if_chips.py` | Contextual chips from snapshot (e.g. reharm available when melody + chords exist) |
| `composition_proposal_cards.py` | Effect tags + reasoning + Try/Apply |

---

## 4. Data model

### Top-level: `CompositionDocument`

Add **`origin`**, **`alternates`** (optional experiment branches V1.1), and **`integration`** stub for future hub:

```json
{
  "schema_version": 1,
  "id": "uuid",
  "title": "Working Title",
  "status": "draft | ready",
  "origin": { "seed_type": "…", "seed_summary": "…", "seed_payload": {} },
  "metadata": { "style": "Jazz", "mood": "reflective", "language": "en" },
  "global": { "original_key_center": "Bb", "time_signature": "4/4", "bpm": 72, "groove_style": "Ballad", "progression_style": "Jazz" },
  "form": { "section_order": [], "sections": {} },
  "integration": {
    "practice_ready": false,
    "backing_preset_id": null,
    "notes_for_coach": ""
  }
}
```

(Sections unchanged — chords, melody phrases, lyrics, rhythm override.)

### Central object (platform vision)

`CompositionDocument` is the **canonical creative artifact**. Future consumers read the same id:

| Consumer | Future behavior |
|----------|-----------------|
| Backing Studio | Open with form + style from `global` |
| Practice | Generated chart/TAB from doc |
| Recording | Scratch over transport |
| Coach / OpenAI | Session notes in `integration.notes_for_coach` |
| Performance | Setlist entry points to composition |

V1: persist `integration` as empty defaults; no routing changes to Tests A–E pages.

---

## 5. AI integration points

### Always pass full snapshot

Never generate “isolated” chord or melody lists. Prompt contract:

1. Current snapshot summary (key, meter, groove, form, active section).
2. Cross-lane content for active section (melody + chords + lyric lines + rhythm).
3. User goal or **experiment type**.
4. Require **≥2 options** with **different musical_effect profiles** when comparing alternatives.

### Teaching-oriented outputs

Encourage vocabulary: tension/release, brightness, voice leading, modal color, cadence strength, rhythmic displacement, contrast between sections.

Rule-based fallback (no API): use theory + tags from `creative_lab_text` / roman numerals to populate `musical_effect` and short templated reasoning.

### Safety

User owns the work; no plagiarized famous hooks; experiments are labeled as proposals.

---

## 6. Version 1 scope

### In scope

- **`composer`** page with seed-first entry (“start from any idea”)
- **`build_composition_snapshot`** + invalidation on any lane edit (foundation for Sprint C)
- Workspace layout + form/chords/rhythm + backing preview (**Sprint A**)
- Melody + lyrics + melody audition (**Sprint B**)
- Explained proposals + What if chips + Try/Apply + compare play (**Sprint C**)
- Library save/load (`composed_song`), undo last apply, `integration` stub

### Out of scope (V1)

- Practice / Backing / Active Song **wiring** (stub only)
- Notation export, DAW-grade editing, collaboration

### Acceptance (updated)

1. User can start from **at least three seed types** (e.g. chords-only, style intent, lyric line) and reach a playable section.
2. After changing melody, chord proposal context **includes** new melody (verified in snapshot tests / dev trace).
3. AI or rule-based proposals show **reasoning + musical_effect** on every card.
4. User can run one **What if** (e.g. reharm or style shift), **Try** audition, then **Apply** or dismiss.
5. Save/reload preserves seed origin and full form.

### Implementation phasing

1. **Sprint A** — Document + `origin` + seed entry UI + snapshot builder (read-only analysis strip) + structure/chords + preview.
2. **Sprint B** — Melody + lyrics + coupling invalidation tests.
3. **Sprint C** — Explained proposals + experiments + What if chips.
4. **Sprint D** — Persistence, polish, library cloud, tests.

---

## 7. Future expansion

(Unchanged direction — composition id threads through Practice, Backing, Recording, Coach, performance; import/export; version branches.)

---

### Egress (`MUSIC_EGRESS_STRICT`)

When Streamlit secret or env `MUSIC_EGRESS_STRICT=1` is set, `music_egress_config.py` enables:

- No Supabase readback after music cloud writes
- Routine **autosave** → local disk only; cloud on `page_change` / explicit edit reasons
- Lazy custom-song cloud merge (loads when Custom Songs library UI opens)
- Saved-item list cap 25 (vs 200)
- Ephemeral keys stripped from page snapshots in persist blobs

Dev: sidebar **Supabase egress (dev)** shows strict on/off.

---

- Snapshot builder is **pure Python** and unit-testable — critical for “everything connected” guarantee.
- Experiment sandbox lives in session (`composer_sandbox_overlay`) until applied.
- Separate page id `composer`; frozen persistence untouched for other pages.

---

## Open decisions

1. **Composition Studio** vs **Song Composer** (recommend **Composition Studio** for “workspace” framing).
2. **`composed_song`** cloud item type (recommend **yes**, separate from CPL).
3. Ship Sprint A–B with **rule-based explained proposals** before OpenAI in Sprint C, or wait — recommend **rule-based stubs in B** so coupling is testable early.
