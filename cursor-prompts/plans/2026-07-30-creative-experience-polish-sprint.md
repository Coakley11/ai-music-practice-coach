# Creative Experience polish sprint

**Last updated:** 2026-07-30  
**Status:** Shipped on `dev` (local) — catalog/custom picker, Deep Harmonic coach UX, mission → backing handoff  
**Branch:** `dev`

## Goals

1. **Song Catalog ↔ Custom Songs** — independent last-selection memory; instant restore on toggle.
2. **Deep Harmonic Analyzer** — coach voice (instrument, level, focus, song); readable layout.
3. **Creative Missions → Backing Studio** — single selected chord loops with transferred tempo/style/key.
4. **Vision** — Creative evolves toward AI music coach (improvise, accompany, compose, hear harmony).

## Shipped (this sprint)

- `songs/music_source.py` — `LAST_CUSTOM_STATE_KEY`, pending catalog switch, reconcile fix, restore custom/catalog
- `music_persistent_state.py` — apply pending catalog switch before widgets
- `streamlit_music_practice_app.py` — `music_picker_shows_custom_hub` for UI routing
- `deep_harmonic_analyzer.py` — coach opening, practice plan, level-gated depth
- `improvisation_intelligence_ui.py` — Deep Harmonic expanders + callout styling; mission chord list for backing
- `backing_context.py` — mission single-chord progression + section dict for generation
- `tests/test_creative_experience_polish.py`

## Follow-ups

- Manual acceptance: Song Selection toggle Custom ↔ Catalog on phone + desktop
- Mission → Backing: confirm autoplay + single-chord loop in Backing UI
- Deep Harmonic: optional AI rewrite layer (CS-C) on top of rule-based coach
- Long-term: unified Creative coach dialogue (see backlog)

## Notes

Does not modify persistence Tests A–E restore paths except picker reconcile ordering.
