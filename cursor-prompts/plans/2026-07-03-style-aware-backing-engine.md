# Style-Aware Backing Engine — Architecture & Phased Plan

**Last updated:** 2026-07-03  
**Status:** Phase 1 foundation started  
**Scope:** Real musical style generation (not labels/metadata)

---

## Audit summary

### Controls that **do** affect generated audio today

| Control | Where | Effect |
|---------|-------|--------|
| **Groove style** (`backing_groove_style`) | `backing_audio._style_patterns`, `_voicing_for_comp`, `_bass_motion_pitch`, `_groove_time` | Different drum grids, bass/comp timing, swing, pocket |
| **Level** (Beginner/Intermediate/Advanced) | `_voicing_for_comp` | Voicing density / note count |
| **BPM** | `meter_timing`, bar length, some song-profile tweaks | Tempo, bar duration |
| **Time signature** | `_style_patterns` meter branches | 4/4 vs 6/8 vs 12/8 grids |
| **Section name** | `_section_intensity`, arrangement overlay | Per-bar volume multipliers |
| **HRI humanize level** | `harmonic_rhythm_intelligence` | Chord *timing* shifts (not timbre) |
| **Song title/artist** | `_song_backing_profile` (hardcoded overrides) | Often dominates style — pop-soul, anthem-rock, etc. |

### Controls stored but **barely / not** affecting audio

| Control | Gap |
|---------|-----|
| **Mood** (Bright/Mellow/Dark/Energetic/Dreamy/Gritty) | UI + progression gen only; **not** passed to synth until Phase 1 |
| **Groove intensity** (Light/Medium/Heavy) | Maps to HRI humanize only — **not** drum/bass density |
| **Creative Feel tags** | Display/coaching only |
| **Blues** (Creative style) | Previously mapped to Pop groove — **fixed** in Phase 1 |
| **Practice groove** (`practice_groove_style`) | `groove_feel.py` text guidance; separate from backing unless synced |
| **Difficulty** | Progression simplification only |
| **Instrument palette** | Generic sine/organ/noise — no distinct instruments |

---

## Target architecture

```
UI / BackingContext / Creative session
        ↓
resolve_backing_musical_profile()   ← backing_musical_profile.py
        ↓
BackingMusicalProfile { style, mood, intensity, tempo, key, progression, ... }
        ↓
apply_profile_to_synthesis()      ← backing_style_recipes.py
        ↓
song_profile flags + rhythm patterns (drum/bass/comp grids)
        ↓
synthesize_chords_to_numpy()      ← backing_audio.py (render loop)
        ↓
WAV output
```

**Principles:**
- One canonical profile object drives generation and cache signatures.
- Style recipes own rhythm grids and groove-character flags.
- Mood + intensity are **modifiers** layered on style (not separate labels).
- Song-specific overrides remain, but style/mood/intensity must be audible without them.

---

## Phased plan

### Phase 1 — Foundation (started 2026-07-03)

- [x] `backing_musical_profile.py` — profile dataclass + resolvers
- [x] `backing_style_recipes.py` — recipes, mood/intensity modifiers, Blues groove
- [x] Wire profile into `synthesize_chords_to_numpy` / `generate_backing_track`
- [x] Pass mood/intensity through Backing Studio signature + cache
- [x] Add **Blues groove** to `GROOVE_STYLE_CHOICES`
- [x] Tests: `tests/test_backing_musical_profile.py`

### Phase 2 — Style recipe depth

- Extract all `_style_patterns` + `_song_backing_profile` style branches into recipes
- Distinct instrument timbres per style (ride cymbal vs cross-stick vs open hat)
- Walking bass algorithm for Jazz; bossa bass clave; funk syncopation
- A/B perceptual tests: Funk vs Bossa vs Swing vs Blues vs Ballad

### Phase 3 — Mood / intensity as first-class arrangement

- Mood affects register, pad sustain, reverb tail, harmonic density
- Intensity affects drum layer count, ghost notes, comp voicing count
- Creative handoff: mood + intensity always in profile from `BackingContext`

### Phase 4 — Instrumentation & stems

- Separate drum / bass / comp buffers
- Optional stem export for multitrack mixer
- Style-specific instrument combinations (e.g. jazz = ride + walking bass + rootless comp)

### Phase 5 — Production polish

- Reduce song-title hardcoding; move to data-driven `song_groove_overrides.json`
- User-facing “compare styles” preview on Backing Studio
- Regression suite with audio fingerprint hashes per style profile

---

## Phase 1 files

| File | Role |
|------|------|
| `backing_musical_profile.py` | Canonical profile + session/context resolvers |
| `backing_style_recipes.py` | Style recipes, mood/intensity modifiers |
| `backing_audio.py` | Profile merge before render loop |
| `streamlit_music_practice_app.py` | Mood/intensity in signature + generation |
| `songs/playback_defaults.py` | Blues groove in dropdown |
| `tests/test_backing_musical_profile.py` | Profile + recipe + audio diff tests |
