# One Music Generation Engine & Coaching Profile

**Date:** 2026-07-31  
**Status:** Architectural principle — incremental implementation  
**Agent rules:** [unified-motif-engine.mdc](../../.cursor/rules/unified-motif-engine.mdc), [single-source-of-truth.mdc](../../.cursor/rules/single-source-of-truth.mdc) (always applied)  
**Related:** [2026-07-30-mission-workspace-contract.md](./2026-07-30-mission-workspace-contract.md), [2026-07-29-flagship-coaching-quality-standard.md](./2026-07-29-flagship-coaching-quality-standard.md), [theory-playback-separation.mdc](../../.cursor/rules/theory-playback-separation.mdc)

---

## Single Source of Truth

Every major musical concept has **one canonical implementation**. Pages consume shared services; they do not duplicate the same logic.

| Concept | Canonical owner |
|---------|-----------------|
| Music theory | `music_theory` pipeline (normalize → classify → spell) |
| Key spelling | `spell_note_in_key`, `respell_note_for_key` |
| Motif generation | `motif_engine` + `improvisation_motif` |
| Mission persistence | [Mission workspace contract](./2026-07-30-mission-workspace-contract.md) |
| AI coaching profile | Metrics & AI — persistent profile (planned) |
| Upload analysis | Today's performance review; inherits profile |
| Playback transport | One transport model (backing / multitrack) |
| ABC / TAB / MIDI / sheet | Same **motif object** → all outputs |

**Long-term goal:** Improve one engine or service → every page benefits automatically.

---

## Platform vision

A **unified music-learning platform**: Missions, Phrase & Motif, Composition Studio, Practice, Upload Analysis, and AI Coach are experiences on shared infrastructure—not isolated features.

```
                    ┌─────────────────────────────┐
                    │   One Music Gen Engine      │
                    │  improvisation_motif +      │
                    │  music_theory + notation    │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
   Mission constraints      Creative / composition      Coach example
   (teach one concept)      constraints (ideas/songs)   (on demand)
         │                         │                         │
         ▼                         ▼                         ▼
     Missions              Phrase & Motif              AI Coach (optional)
                           Composition Studio          Practice examples
```

---

## Part A — Engine responsibilities

Single implementation for:

| Capability | Owner |
|------------|--------|
| Phrase / motif notes | `improvisation_motif` |
| Rhythm patterns & tiers | `improvisation_motif` |
| Beginner / Intermediate / Advanced + easier/harder | `improvisation_motif` |
| Chord quality & chord tones | `music_theory` + `chord_tone_names` |
| Key spelling for all displays | `spell_note_in_key` |
| ABC / TAB / MIDI / sync | `improvisation_motif` |
| Public API | `motif_engine.generate_musical_phrase` |

Playback may use internal representations; **musician-facing text** always follows the active key signature.

### Page purposes (constraints only)

#### Missions — teach one musical concept

Mission → constraint set → engine → example that **proves** the lesson.

| Mission theme | Constraint intent |
|---------------|-------------------|
| Chord tones only | Pitch set = chord tones |
| Guide tones | Primarily 3rds & 7ths |
| Target 9ths | Emphasize 9th targets |
| Rhythmic variation | Rhythm-led, non-repeating cells |
| Motif development | Repeat/variate core cell |
| Dominant tension | Dom-appropriate vocabulary |
| Beat-1 resolution | Land strong tones on downbeats |

Implemented: `improvisation_mission_rules.apply_mission_rules` (extend as missions grow).

#### Phrase & Motif — idea generator

Same engine; **creative** objective. Current: Generate, New, Harder, Easier (level-relative).

**Roadmap buttons / intents:** more lyrical, more rhythmic, more bluesy, more jazz vocabulary, continue this idea, contrasting idea.

Transforms always apply to **active motif**: invert, sequence up/down, rhythmic variation.

#### Composition Studio — complete songs

Replace parallel **text-only** melody hints with engine output + **songwriting constraints**:

- Verse melody, chorus hook, bridge idea
- Singable range, hook repetition
- Pre-chorus tension, style match, harmony fit

Same engine; composition recipe module (future: `composition_motif_constraints.py` calling `motif_engine`).

#### AI Coach — analyze first

```
Recording → mission_analysis / LLM coaching → feedback
                    ↓ (when helpful)
              motif_engine example (“try this line”)
```

Coach **analyzes**; engine **demonstrates**. Do not merge into one “generative coach.”

#### Practice

Performance examples via `kind="practice"` constraints (shared engine).

### Migration checklist

- [x] Missions + Phrase & Motif share core generator + mission rules
- [x] Theory pipeline + key spelling centralized
- [x] `motif_engine.py` facade + tests
- [ ] All new Creative calls via `motif_engine.generate_musical_phrase`
- [ ] Phrase & Motif stylistic intents (lyrical, bluesy, …)
- [ ] Composition Studio melody phases → engine + songwriting constraints
- [ ] AI Coach: explicit “generate example” path only post-analysis
- [ ] `composition_motif_constraints` (name TBD) — no duplicate generators

---

## Part B — Coaching profile vs today’s upload

### Two questions, two pages

| | **AI Improvisation Metrics & AI** | **Mission Upload Analysis** |
|---|-----------------------------------|-----------------------------|
| Question | How should the AI coach me over time? | How did I do on *this* recording? |
| Horizon | Weeks / months | Today |
| Persists | Global coaching profile | Per-upload result |
| Content | Skills emphasis, strictness, tone, depth, long-term goals | Mission completion, strengths, fixes, next practice |

**Complement, not duplicate:** Upload inherits profile for **weighting and voice**; today’s **Practice Mission** drives primary scoring.

Example: Profile = rhythm highest, harmony second, detailed teacher tone. Mission = chord tones only. Upload answers “Did I use chord tones?” first, then frames feedback with rhythm-first long-term priorities.

### Profile schema (sketch) — `improv_coaching_profile`

```json
{
  "skill_priorities": {
    "rhythm": 0.35,
    "harmony": 0.25,
    "phrasing": 0.15,
    "creativity": 0.15,
    "ear_training": 0.05,
    "motif_development": 0.05
  },
  "feedback_depth": "detailed",
  "coaching_tone": "teacher",
  "strictness": "medium",
  "long_term_goals": ["bebop vocabulary", "rhythmic creativity"],
  "preferences": {
    "compare_to_reference_artists": true,
    "assign_homework_after_upload": true
  }
}
```

### Upload flow (target)

1. Score **today’s mission** (primary weights from `improv_active_mission` → metric map).
2. Blend **profile** priorities into feedback ordering and depth.
3. UI: mission completion headline → strengths → improve → next steps.
4. Remove duplicate full metric multiselect on Upload (optional advanced dimensions only).

### Implementation phases

| Phase | Deliverable |
|-------|-------------|
| 1 | Architecture docs + rules + `motif_engine` (done) |
| 2 | `improvisation_coaching_profile.py` + persistence + Metrics tab UI |
| 3 | Upload Analysis mission-first UX |
| 4 | `merge_mission_and_profile()` in `mission_analysis.py` + tests |
| 5 | LLM prompts use profile tone/goals |

### Tests

- Profile round-trip persistence
- Upload on chord-tone mission → chord-tone metric dominates
- Rhythm-heavy profile → rhythm called out even on harmony-focused mission (secondary)

---

## Notes

- **Practice Mission** (Creative checklist string) ≠ **MISSION_GOALS** metric ids — map explicitly (`LEGACY_MISSION_TO_IDS`).
- Engine improvements must never require parallel updates in Composition hint strings—migrate hints to generated phrases over time.
