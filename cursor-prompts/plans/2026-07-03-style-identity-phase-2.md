# Style Identity & Creative Engine — Phase 2

**Last updated:** 2026-07-03

## Goal

A musician should immediately recognize the style without looking at the label. Mood, Style, Feel, Intensity, and Groove all materially affect generated audio for catalog songs, custom progressions, and Creative Lab.

## Architecture (style-first merge)

```
BackingMusicalProfile (canonical)
  → style_recipe_id + style_pattern_for_recipe()   [backing_style_recipes.py]
  → _base_style_flags + _feel_modifiers + mood/intensity
  → apply_profile_to_synthesis() replaces rhythm grid
  → _song_backing_profile() arrangement hints only (outro fade, section intensity)
  → synthesize_chords_to_numpy loop
```

**Rule:** When user selects an explicit groove (not Auto), `style_locked=True` suppresses song-title pattern overrides. Song profiles add flavor, not identity.

## Phase 2 deliverables (this sprint)

### 1. Canonical style recipes
- `style_pattern_for_recipe()` — Pop, Rock, Jazz Swing, Bossa, Funk, Blues grids in one module
- `_base_style_flags()` — per-style swing, pocket, bass_mode, comp_mode, comp_wave, syncopation
- `_feel_modifiers()` — maps `groove_feel` time_feel text to synthesis scalars

### 2. Profile expansion
- `resolve_feel_for_style()` — feel from profile or groove_feel
- Session mood/intensity merge when BackingContext lacks them (catalog + CPL)
- Full `BackingMusicalProfile` passed through `_cached_backing_wav` → `generate_backing_track`

### 3. Song override cap
- Removed duplicate style branches from `_song_backing_profile()`
- Song-flag pattern overrides gated by `not style_locked`
- Dedicated Pop groove branch in `_style_patterns()`

### 4. Harmony / bass identity
- Blues shuffle bass line + dominant voicings
- Rock power-chord comping + sine wave
- Style-specific bass duration (Blues 0.55, Rock 0.44, Funk 0.32)

### 5. Tests
- Same progression (Em7–Am7–D7–Gmaj7) differs across 6 styles
- Funk Heavy/Energetic vs Light/Dreamy
- Jazz Relaxed vs Energetic
- Song override blocked when style locked

## Acceptance listening tests

1. Play Em7 | Am7 | D7 | Gmaj7 in Pop, Rock, Jazz Swing, Bossa, Funk, Blues — each recognizable blind
2. Funk + Heavy + Energetic vs Funk + Light + Dreamy — immediately obvious
3. Jazz Swing + Relaxed vs Jazz Swing + Energetic — groove density differs
4. Bossa + Dreamy vs Bossa + Heavy — space vs drive
5. Catalog song (e.g. Shape of You) with explicit Funk — funk grid, not song groove_based override

## Not in Phase 2

- Stems / multitrack export instrumentation
- Reference-based loudness normalization
- New timbres beyond organ/sine/noise

## Files touched

- `backing_style_recipes.py` — recipes, patterns, feel, style-first merge
- `backing_musical_profile.py` — session/ctx mood merge, feel resolution
- `backing_audio.py` — style_locked, Pop branch, blues/rock voicing+bass, song override cap
- `streamlit_music_practice_app.py` — pass full musical_profile to cache/generation
- `tests/test_backing_musical_profile.py` — Phase 2 acceptance tests
