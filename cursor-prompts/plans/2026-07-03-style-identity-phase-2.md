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

## Phase 2B — obvious-by-ear timbre pass (2026-07-03)

Phase 2 differences were spectrally real but too subtle. 2B adds dedicated
drum voices and comp articulation so each style reads as a distinct kit.

### Drum voices (backing_audio.py)
- `_add_kick()` — pitch-swept sine body + click transient, `punch` per style
- `_add_snare()` — noise burst + tonal shell, `crack` per style
- `_add_ride()` — inharmonic metallic ping + sizzle (Jazz/Blues ride cymbal)
- `_add_noise_hit(tone=)` — pitched shimmer mix for hats/cross-stick
- `_style_drum_character()` — per-style kick punch, snare crack, hat tone,
  ride usage, volume balance

### Style character (measured spectral fingerprint)
| Style | Kit character |
|-------|---------------|
| Rock | brightest, hardest kick/snare, highest crest |
| Funk | short punchy stabs (highest crest), tight hats |
| Jazz | ride cymbal, soft kit, walking-bass low-end |
| Bossa | soft cross-stick, gentle kit |
| Blues | ride + shuffle, warm |
| Pop | clean, even, straight |

### Comp articulation
- Funk: very short 16th stabs; Rock: palm-mute power push; Jazz: light/soft;
  Bossa: soft held; Blues: warm sustained; Pop: clean even

### Tests
- `test_style_timbre_fingerprints_differ` — spectral centroid / crest / low-end
  prove Rock/Funk brighter+punchier, Jazz warmer; ≥5 distinct signatures

## Phase 2C — exaggerate arrangement identity (2026-07-03)

Phase 2B timbre helped but arrangement density still too similar. 2C makes
each style's *feel* unmistakable even if slightly cartoonish.

### Exaggerated rhythm grids (`style_pattern_for_recipe`)
| Style | Bass | Comp | Drums |
|-------|------|------|-------|
| Pop | sparse root-fifth (2) | light offbeats (2) | straight 8th hats |
| Rock | eighth pump (8) | power every beat (4) | four-on-floor kick + ghost |
| Jazz | walking quarters (4) | 2 sparse hits | ride spang-a-lang, no snare |
| Bossa | syncopated (4) | 5 syncopated chords | cross-stick only, no hats/snare |
| Funk | 16th bass (13) | 6 syncopated stabs | 8 ghost notes |
| Blues | shuffle quarters (4) | full triplet grid (6) | ride shuffle + ghosts |

### Arrangement mix (`_style_arrangement_character`)
- Rock: bass ×1.35, comp ×1.45, short punchy notes
- Jazz: bass ×1.25 walking, comp ×0.50 (very light)
- Funk: comp ×1.55, bass dur 0.18 beat (staccato 16ths)
- Pop: bass ×0.82, comp ×0.68 (clean/supportive)
- Blues: sustained shuffle comp ×1.12

### Drum exaggeration
- Jazz ride ×5.5 with spang-a-lang accents; snare suppressed
- Bossa cross-stick ×2.8; hats and snare suppressed
- Rock kick/snare ×1.55–1.65
- Funk ghost notes ×1.6

### Bass lines (`_bass_motion_pitch`)
- Jazz chromatic walk · Funk 16th syncopation · Bossa root-5-octave
- Rock root-fifth pump · Blues flat-7 shuffle · Pop root-fifth only

### Tests
- `test_style_bass_density_differs`, `test_jazz_has_ride_not_snare`,
  `test_bossa_cross_stick_carries_pulse`
