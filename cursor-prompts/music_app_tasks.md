# Current Tasks — AI Music Practice Coach

**Last updated:** 2026-06-09

Actionable work items. Master context: [music_app_roadmap.md](./music_app_roadmap.md).  
**Persistence baseline (frozen A–D):** [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md)

---

## Current Priorities

### P0 — Test E: AMI return context restore

**Frozen:** Tests A–D accepted — do not reopen without `?dev=1` trace regression.  
**Protocol:** [plans/2026-06-09-test-e-ami-return.md](./plans/2026-06-09-test-e-ami-return.md)  
**Deploy marker:** `page-change-save-stamp-v26-test-e-ami-return-trace`

- [x] v26: AMI `build_source_state` / `apply_active_song_source_state_from_ami` include written-key + subtype
- [x] v26: **Test E compare** trace panel (`?dev=1`)
- [ ] Manual sign-off: Photograph/Shape of You + Db/Ebm + Sax Tenor/Alto + Practice or Backing
- [ ] Freeze Test E on pass; UI polish in **separate commit**

### P1 — Deploy & navigation verification

- [ ] Confirm Streamlit Cloud **dev** deploy marker `page-change-save-stamp-v26-test-e-ami-return-trace` after hard refresh
- [ ] Confirm **← Back** visible on left of main panel on Practice, Backing, Song Selection (scroll test)
- [ ] Confirm **Forward →** remains fixed on right while scrolling
- [ ] Remove temporary green deploy banner once verified (`ui-nav-deploy-marker`)

### P2 — Practice reliability

- [ ] Fix Section Focus when label is type-only (“Verse”) vs chart key (“Verse 1”) — empty Coach/Chart panels
- [ ] Add regression test for `practice_resolve_focus_section` mapping
- [ ] Harden `practice_studio` import path (avoid silent fallback resolver)

### P3 — UI / feature polish

- [ ] Sidebar readability and transposing recap styling (ongoing as needed)
- [ ] OpenAI hub: first real “active song coach” flow (not placeholder card)
- [ ] Link `README.md` → `cursor-prompts/music_app_roadmap.md`

---

## Next Features

*(After P0–P1 or in parallel)*

- [ ] Karaoke: vocal pitch/score stub → minimal MVP scoring display
- [ ] Non-voice performance setlist (reuse karaoke queue patterns)
- [ ] Creative Lab: interactive UI for Arrangement Assistant (beyond text expander)
- [ ] Conflict resolution UI when cloud vs local diverge (suite-wide)

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

- [x] Cross-device Test A page sync (v14)
- [x] Cross-device Test B Practice sync (`97fad4a`)
- [x] Cross-device Test C Backing sync (v18 `fdf9800`)
- [x] Cross-device Test D active song + key + instrument + page + written-key + subtype (v25 `f153204`, 2026-06-09)
- [x] Floating page history navigation (`5ed9d93`)
- [x] Back arrow main-panel positioning (`9e0728a`)
- [x] Roadmap documentation system (`cursor-prompts/`)

---

## Notes

- Work on branch **`dev`** only; push `origin/dev` for Streamlit Cloud dev app.
- When a task ships, move detail to `music_app_completed_features.md` and uncheck here.
- For large implementation plans, save the full plan body under `cursor-prompts/plans/` and link from this file.
