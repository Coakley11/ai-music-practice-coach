# Manual / advanced chord editor — widget-safe section editor

**Date:** 2026-08-28  
**Branch:** `cursor/composition-usability-layout-0398` (Composition testing follow-up; do not merge to `dev`)

## Problem

The hosted Composition app crashed in `_render_chord_refinement_panel` when this ran after the refine selectbox existed in the same run:

```python
session_state[f"composer_refine_intent_{section_id}"] = nxt
```

Streamlit raises `StreamlitAPIException` because that key is widget-owned.

The Manual / advanced expander was still a Custom-like append/paste grid, not a focused editor for the selected section’s existing progression.

## Fix

1. **Widget ownership** — canonical `composer_refine_intent_value_{section_id}`, widget `composer_refine_intent_widget_{section_id}`, pending `composer_refine_intent_pending_{section_id}`. `prepare_refine_intent_widget` applies pending **before** the selectbox. `Try another` only queues pending.
2. **Section editor** — `composition_chord_editor.py` drafts the selected-section timeline: location (bar/beat/duration), replace, quality/extensions, insert with timing, key-aware suggestions with chromatic warnings, undo/cancel/preview, accept via `apply_section_chords`.
3. **Harness** — `composition_chord_editor_harness.py` + `tests/test_composition_chord_editor.py` open the editor, change refinement, Try another, switch sections, refresh, cold-restore.

## Out of scope

Custom Page workflow, song-source ownership, Custom backing navigation, merge to `dev`, production deploy.
