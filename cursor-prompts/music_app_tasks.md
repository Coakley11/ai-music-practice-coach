# Current Tasks — AI Music Practice Coach

**Last updated:** 2026-06-03

Actionable work items. Master context: [music_app_roadmap.md](./music_app_roadmap.md).

---

## Current Priorities

### P0 — Deploy & navigation verification

- [ ] Confirm Streamlit Cloud **dev** app branch = `dev` and latest tip deployed (`9e0728a+`)
- [ ] Verify deploy marker `nav-back-left-fix-1` visible after hard refresh
- [ ] Confirm **← Back** visible on left of main panel on Practice, Backing, Song Selection (scroll test)
- [ ] Confirm **Forward →** remains fixed on right while scrolling
- [ ] Remove temporary green deploy banner once verified (`ui-nav-deploy-marker`)

### P1 — Practice reliability

- [ ] Fix Section Focus when label is type-only (“Verse”) vs chart key (“Verse 1”) — empty Coach/Chart panels
- [ ] Add regression test for `practice_resolve_focus_section` mapping
- [ ] Harden `practice_studio` import path (avoid silent fallback resolver)

### P2 — Documentation maintenance

- [x] Create `cursor-prompts/` roadmap system (this commit)
- [ ] Link `README.md` → `cursor-prompts/music_app_roadmap.md`
- [ ] Keep `music_app_*.md` in sync when shipping features

---

## Next Features

*(Pick up after P0–P1 or in parallel if blocked on deploy)*

- [ ] OpenAI hub: implement first real “active song coach” flow (not placeholder card)
- [ ] Karaoke: vocal pitch/score stub → minimal MVP scoring display
- [ ] Non-voice performance setlist (reuse karaoke queue patterns)
- [ ] Creative Lab: interactive UI for Arrangement Assistant (beyond text expander)

---

## Long-Term Vision

- Unified musician profile across suite apps (Supabase user scoping already started)
- Full AI session planner: logs + recordings + active song → daily plan
- Live ensemble mode: multitrack + backing + follow-along in one session view
- Mobile-first practice mode (larger touch targets, simplified nav)
- Teacher/student mode: assign songs, review uploads, comment on charts

---

## Completed Features

Recent task completions (see [music_app_completed_features.md](./music_app_completed_features.md) for full list):

- [x] Floating page history navigation (`5ed9d93`)
- [x] Import fix for `render_floating_nav_history` (`dcb5ad3`)
- [x] Back arrow main-panel positioning + remove main ☰ Pages chip (`9e0728a`)
- [x] Deploy verification marker system (`205c0b7`, `nav-back-left-fix-1`)
- [x] Roadmap documentation system (`cursor-prompts/`)

---

## Notes

- Work on branch **`dev`** only; push `origin/dev` for Streamlit Cloud dev app.
- When a task ships, move detail to `music_app_completed_features.md` and uncheck here.
- For large implementation plans, save the full plan body to a new file under `cursor-prompts/` (e.g. `plans/YYYY-MM-DD-feature-name.md`) and link from this file.
