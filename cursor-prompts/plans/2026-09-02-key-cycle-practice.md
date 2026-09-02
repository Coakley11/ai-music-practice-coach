# Key Cycle Practice — FUTURE FEATURE

**Status:** Future roadmap only. **Do not implement** transport, temporary playback keys, chart cycling, or persistence during current Creative/Backing stabilization.

**Not part of** Creative/Backing human-acceptance (H1–H9, Owner, 17-gate, A–N).

**Shipped now:** documentation + an **inert** Advanced Settings visual placeholder (`key_cycle_practice_preview.py`). The placeholder must stay disabled until this plan is deliberately opened.

**First real implementation later:** a narrow prototype on **one ordinary Catalog Backing** workflow, in the **shared** Backing playback/transport architecture. Only after that prototype is proven may the same engine be exposed on other Backing surfaces.

---

## Product idea

Add **Key Cycle Practice** to every Backing workflow so a musician can practice the same song, progression, section, mission, composition, or other Backing material automatically through multiple keys **without** manually changing the song’s Practice Key after every repetition.

Example: Shape of You, base Practice Key **B minor**, Scope **Verse**, Loops **2**, Key Cycle **Half steps**:

- Verse ×2 — B minor
- Verse ×2 — C minor
- Verse ×2 — C♯ minor / D♭ minor
- … continues until the player stops/resets the Key Cycle session

This is a serious instrumental practice feature: one form/progression, systematically through many keys, with accompaniment.

---

## Available everywhere Backing exists

Ultimately available on every Backing surface:

- ordinary Catalog song Backing
- Custom Progression Backing
- Composition Backing
- SBI Backing
- Missions Backing
- Jam Session Generator Backing
- Style Jam Backing
- other specialized Backing workflows
- future Backing workflows

**Do not** implement separate independent versions per page. Build **one** shared Key Cycle / Backing transport capability that each surface uses.

---

## UI location

Backing → **Advanced playback settings**, near style, meter, scope, loops.

Control: **Key Cycle Practice**

Options:

- Off
- Half steps
- Whole steps

Default: **Off**. If Off, existing Backing behavior must remain completely unchanged.

---

## Half-step mode

Advance the **temporary playback key** by **+1 semitone** after the currently selected scope and loop count have completed.

Example starting B minor: B minor → C minor → C♯/D♭ minor → D minor → D♯/E♭ minor → E minor → F minor → F♯/G♭ minor → G minor → G♯/A♭ minor → A minor → A♯/B♭ minor → B minor …

Cycles indefinitely through all 12 pitch classes until stopped or reset.

**Mode is preserved.** Minor remains minor. Major remains major.

---

## Whole-step mode

Advance by **+2 semitones** after each completed scope/loop unit.

Example from C: C → D → E → F♯ → G♯ → A♯ → C …

This is a **literal whole-step cycle**. It does **not** mean moving among scale degrees such as C–D–E–F–G–A.

Major remains major. Minor remains minor. Continues until stopped/reset.

---

## Scope + loop interaction

Key Cycle must use whatever Backing **Scope** and **Loop** settings the musician already selected. It does **not** invent a new scope system.

- Scope = Verse, Loops = 2, Half steps → Verse ×2 in each temporary key, then advance.
- Scope = Entire Song: play the full song/form in the current temporary key, then advance.
- Scope = Chorus: play the selected Chorus according to its loop count, then advance.

---

## Critical architectural rule: this does **not** transpose the actual song

Key Cycle Practice is a **temporary playback/practice transformation**.

It must **not** permanently change:

- Global Active Source
- active song
- canonical Practice Key
- Original Key
- Custom canonical song
- Composition canonical source
- SBI source identity
- Mission owner
- saved progression
- sidebar canonical Practice Key
- blue source/backing-card base Practice Key

Example: Shape of You canonical Practice Key = B minor. Cycle has temporarily reached E minor. The actual song is **still** Shape of You / B minor. The app has **not** permanently transposed Shape of You into E minor.

Keep separate state, conceptually:

- `base_practice_key`
- `cycle_playback_key`
- `cycle_semitone_offset`
- `cycle_mode`
- `cycle_enabled`

The temporary cycle key must **never** be written into canonical source ownership.

**Do not** implement Key Cycle by repeatedly setting Practice Key to C, then C♯, then D, …

---

## What should change while cycling

While Key Cycle is temporarily in another key, the things necessary to **play and read** that temporary key should change.

Example: base Practice Key B minor, current cycle sounding key E minor.

| Surface | Expected |
|---------|----------|
| Sidebar canonical Practice Key | B minor |
| Blue source/backing card base key | B minor |
| Canonical song | B minor |
| Currently playing Backing/audio | E minor |
| Currently displayed practice chart | E-minor projection |
| Key Cycle indicator | E minor |

The backing must actually **sound** in E minor (not chart-only visual transposition). The temporary playback key must **not** replace the song’s real Practice Key.

---

## Visible Key Cycle status

When active, make temporary transposition obvious:

- Key Cycle Practice: ON
- Base Practice Key: B minor
- Current Playback Key: E minor

If Written Charts or Shape Charts are active, also show current chart key when useful.

This prevents confusing the temporary playback projection with the saved Practice Key.

---

## Charts must follow the temporary playback

Audio and chart must always represent the **same** temporary musical state. Transpose **exactly once**. Do not allow audio = C♯ minor and chart = C minor (or any split).

---

## Transport / session behavior — V1

- **Pause:** preserve current temporary key; preserve position as far as the existing player allows.
- **Resume:** continue in the same temporary key.
- **Stop:** stop playback; preserve the current Key Cycle temporary key for that generated Backing session.
- **Play again:** continue/restart the current practice unit in the **same** temporary key (do not jump back to base).
- When the current scope/loop unit **finishes:** advance to the next temporary key.
- **Reset Key Cycle / regenerate Backing / start a new Backing session:** reset temporary playback key to the canonical base Practice Key.

Fine-tune exact Stop/Resume semantics after using the prototype.

---

## Key Cycle session state

At generation/start, snapshot:

- base Practice Key
- mode
- scope
- loop count
- cycle interval
- enharmonic chart-spelling preferences
- relevant Backing settings

Later unrelated changes elsewhere must not silently rewrite an already-running cycle plan.

V1 session state may remain **transient**. Later decide whether refresh preserves enabled state, offset, temporary key, and cycle position.

**Never** implement persistence by writing the cycle key into the canonical Practice Key.

---

## Enharmonic spelling preferences

Configured **before** starting/generating the Key Cycle session. Chart-spelling only.

Five common enharmonic pitch-class pairs as two-choice toggles (one side default):

- C♯ | D♭
- D♯ | E♭
- F♯ | G♭
- G♯ | A♭
- A♯ | B♭

If the cycle never reaches that chart pitch class, the preference does nothing.

### Mode-aware default spellings

**Major:** C♯/D♭ → D♭; D♯/E♭ → E♭; F♯/G♭ → F♯; G♯/A♭ → A♭; A♯/B♭ → B♭

**Minor:** C♯/D♭ → C♯; D♯/E♭ → D♯; F♯/G♭ → F♯; G♯/A♭ → G♯; A♯/B♭ → B♭

Defaults only; the musician can override any pair before start.

### Spelling does not change pitch

C♯ and D♭ are the same sounding pitch class. Spelling must **never** affect sounding audio pitch.

Internally operate on **pitch class / semitone offset**, not textual key names.

Keep separate: **PITCH** projection vs **SPELLING**.

### Preferences apply to the **chart** key

Not “Concert Practice Key spelling settings.” They are **chart key spelling** settings.

Pipeline:

1. Determine temporary Key Cycle sounding / concert pitch
2. Apply the current instrument/chart projection (Written / Shape / concert)
3. Determine the resulting **chart** pitch class
4. Apply the user’s enharmonic preference for that **chart** pitch class
5. Render the chart using that spelling

Do **not** choose concert spelling first and mechanically transpose that textual spelling. Transpose **pitch** first; choose chart **spelling** afterward.

### One preference table, not one per instrument

Do **not** create concert / tenor / alto / guitar preference tables.

```
chart_spelling_preferences = {
  pitch_class_1: "C#" or "Db",
  pitch_class_3: "D#" or "Eb",
  pitch_class_6: "F#" or "Gb",
  pitch_class_8: "G#" or "Ab",
  pitch_class_10: "A#" or "Bb",
}
```

Then: temporary sounding pitch → projection → chart pitch class → preference lookup → rendered key spelling.

Instrument changes reuse the **same** table against the new chart pitch classes.

### Chords follow the same spelling policy

Header, chord names, progression, sheet notation, mission/example labels, and other rendered harmonic material must use one coherent enharmonic policy. No mixed C♯/D♭ surfaces within the same temporary chart.

### Written / Shape

Preserve existing projection rules. Minor stays minor; major stays major. Preference changes **spelling only**.

Written: concert pitch → Written pitch class → preference for that Written class.

Guitar Shape: sounding pitch → Shape projection → Shape chart pitch class → preference.

---

## Base card and sidebar remain canonical

Example: Shape of You canonical B minor. Cycle sounding C♯/D♭ minor. Tenor chart D♯/E♭ minor. User selected E♭ for A♯/B♭ wait — for D♯/E♭ preference E♭:

- Sidebar canonical Practice Key: B minor
- Blue source/backing card: B minor
- Current sounding Key Cycle key: C♯/D♭ minor
- Current chart key: E♭ minor
- Temporary chart: E♭ minor
- Temporary audio: correct sounding C♯/D♭ concert pitch

---

## Implementation architecture

```
CANONICAL SOURCE MATERIAL
        |
BASE PRACTICE KEY
        |
SCOPE + LOOP PLAN
        |
KEY CYCLE SEMITONE OFFSET
        |
TEMPORARY SOUNDING PLAYBACK KEY
        |
INSTRUMENT / WRITTEN / SHAPE PROJECTION
        |
TEMPORARY CHART PITCH CLASS
        |
ENHARMONIC CHART-SPELLING POLICY
        |
DISPLAYED TEMPORARY CHART
```

The temporary sounding offset must drive **both** Backing/audio and chart projection from the same cycle state. Avoid double transposition.

---

## First implementation plan (when stabilization is accepted)

### Phase 1

Behind a feature flag on **one ordinary Catalog Backing** page.

Support: Off / Half steps / Whole steps; current scope; current loop count; temporary playback/chart key; reset to base key; chart-spelling preferences; Written/Shape optional to defer for the narrowest prototype.

Prove the **transient state model** first.

### Phase 2

Written Chart projection: temporary sounding pitch → Written pitch → chart spelling.

### Phase 3

Guitar Shape projection.

### Phase 4

Expose the same shared system across Custom, Composition, SBI, Missions, Jam, Style Jam, and all other Backing surfaces. **Do not duplicate the engine per workflow.**

---

## Acceptance principles

1. Key Cycle never changes the canonical Practice Key.
2. Key Cycle never changes Global Active Source.
3. Temporary Backing audio and temporary chart always agree.
4. Mode remains correct: major stays major, minor stays minor.
5. Scope and loops finish before advancing to the next key.
6. Half-step mode advances exactly +1 semitone.
7. Whole-step mode advances exactly +2 semitones.
8. Cycle continues until stopped/reset.
9. Pause/Resume preserves current temporary cycle key.
10. New/regenerated/reset session begins again from the base Practice Key.
11. Enharmonic preferences change notation only, not pitch.
12. Enharmonic preferences apply to the final **chart** pitch class after Written/Shape projection.
13. Written Charts use the player’s preference for the Written pitch class.
14. Guitar Shape charts use the player’s preference for the Shape pitch class.
15. Changing instruments uses the same preference table against the new chart pitch classes.
16. Sidebar/base source card remain the canonical Practice Key while Key Cycle is running.
17. The temporary chart clearly identifies the current cycle key.
18. All chart surfaces use a coherent spelling policy; no mixed enharmonic identities.
19. The feature is implemented once in shared Backing architecture.
20. When Key Cycle is Off, existing Backing behavior is unchanged.

---

## Current placeholder (2026-09-02)

`key_cycle_practice_preview.py` + `backing_display.render_backing_advanced_settings_future_previews` render a **Coming soon / Preview — not active yet** control under Advanced playback settings.

The placeholder must **not**:

- change Practice Key
- create temporary playback keys
- transpose audio or charts
- create cycle state
- write session state that affects Backing
- persist anything
- change source ownership
- change scope/loop behavior
- alter Global Active
- hook into transport completion
- add speculative playback architecture
- change existing Backing behavior

Tests: `tests/test_key_cycle_practice_preview.py`.
