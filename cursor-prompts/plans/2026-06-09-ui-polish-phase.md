# UI polish phase — branded headers, layout, readability

**Last updated:** 2026-06-09  
**Priority:** **P0 — immediate** (start here)  
**Status:** ACTIVE  
**Policy:** **Visual/layout only** — separate UI-only commit(s). Do **not** mix with persistence or nav fixes.

**Frozen:** Tests **A–E** passed. **Do not touch:** persistence, cloud restore, AMI return, Practice sync, Backing sync, active song restore, transposing sync, or canonical state modules unless `?dev=1` trace proves regression.

**Baseline:** [docs/MUSIC_PERSISTENCE_BASELINE.md](../../docs/MUSIC_PERSISTENCE_BASELINE.md)

---

## Goal

Restore polished, branded Music Studio UI without touching sync architecture.

---

## Architecture preservation (mandatory)

Preserve the **exact current** page architecture and persistence architecture.

| Category | Do not move or modify |
|----------|------------------------|
| Page routing | `streamlit_music_practice_app.py` dispatch, `studio_page` routing, `studio_nav_history.py` |
| Restore | `apply_music_disk_state`, `prepare_music_workspace`, workspace restore protocol |
| Cloud sync | `music_persistent_state.py`, `suite_user_persistence.py`, save/build envelopes |
| AMI return | `applied_math_return_insight.py`, `music_coach_context.py` source_state apply/build |
| Nav ownership | `_suite_page_user_nav`, page owner flags, `after_studio_page_change`, deferred saves |
| Active song | `active_song_state.py` and canonical Practice/Backing/Studio nav modules |

**UI changes = rendering / CSS / layout only.**

| Allowed | Examples |
|---------|----------|
| CSS / HTML / theme | `app_ui.py`, `portfolio_polish.py`, per-page style injectors |
| Layout | Column/expander/tab order without new session writes |
| Display badges | Read existing written-key state for label text only |
| Nav visibility | Re-show Upload/Multitrack in sidebar/menu UI — **no** routing/ownership handler changes |

Cursor rule: `.cursor/rules/ui-polish-architecture-preservation.mdc`

---

## P0 — Decorative page headers & branding

Bring back colorful **script-style header words** at the top of main studio pages (stylized text, colors, stronger page identity).

**Pages that should have polished headers again:**

| Page | Header identity |
|------|-----------------|
| Song Selection | Catalog / picker branding |
| Practice | Practice / music coaching |
| Backing Track | Backing / audio studio |
| Creative / Custom Progression | Creative lab |
| Karaoke | Microphone / stage |
| Upload / Multitrack | Upload / analysis |
| Other main studio pages | Match prior branded headers where they existed |

**Also restore logos/icons in headers:**

- Practice — practice/music icon
- Backing — backing/audio icon
- Creative — creative/lab icon
- Karaoke — microphone/stage icon
- Upload — upload/multitrack icon

**UI files likely involved (inspect only until implementation):** `app_ui.py`, `portfolio_polish.py`, per-page render modules, `streamlit_music_practice_app.py` header injectors.

**Constraint:** Header restore must not change `studio_page`, cloud save payloads, or workspace restore paths.

---

## P1 — Upload / Multitrack navigation access

Ensure **Upload / Multitrack** (`analysis` / `multitrack` studio pages) is **visible and accessible** again in sidebar Pages and quick-nav.

- If hidden during sync fixes, restore nav entry without changing persistence.
- Verify page loads and header branding matches P0.

---

## P2 — Practice page layout

- [ ] Reduce scrolling on Practice page
- [ ] Improve **Practice Control Center** layout (tabs, density, grouping)
- [ ] Improve **chart/TAB** presentation
- [ ] Add clearer **“Written charts ON”** / **“Concert charts”** badge or status line (UI only — do not change `show_chart_in_instrument_key` save path)

---

## P3 — Song cards & readability

- [ ] Improve **song cards** and **active song display** (Practice, Backing, Song Selection)
- [ ] Clean remaining **gray text / readability** issues (sidebar + main panels)
- [ ] Consistent Active Song Hub actions across catalog and custom sources

---

## P4 — Deploy shell cleanup

- [ ] Remove temporary green deploy verification banner when Cloud `dev` confirmed (`ui-nav-deploy-marker`)
- [ ] Mobile tuning for floating history buttons and sidebar Pages rail

---

## Out of scope (do not change in UI polish commits)

- Page routing code, restore code, cloud sync code, AMI return code, navigation ownership code, active-song state code
- All Tests **A–E** persistence paths (page, Practice, Backing, active song, written-key, transposing, AMI return)
- `music_persistent_state.py`, `active_song_state.py`, `practice_state.py`, `backing_track_state.py`, `studio_nav_state.py`, `suite_resume_launch.py` (logic paths)
- **P1** Back/Forward navigation stack/handler fixes — [deferred audit plan](./2026-06-09-back-forward-nav-audit.md)

---

## Recommended commit split

| Commit | Contents |
|--------|----------|
| **UI polish 1** | Decorative headers + logos/icons + Upload/Multitrack nav visibility |
| **UI polish 2** | Practice layout, chart/TAB, written-key badge, song cards |
| **P1 nav fix** (only after deferred audit fails) | Isolated Back/Forward — never mixed with UI polish |

---

## Verification (UI-only)

1. Hard refresh `?dev=1` on Streamlit Cloud `dev`.
2. Visit each main studio page — confirm branded header + icon restored.
3. Confirm Upload/Multitrack reachable from sidebar.
4. Run **Tests A–E smoke** (copy Test D + Test E compare blocks) — all fields unchanged after UI-only deploy.
5. No new `page_overwrite_source`, `active_song_dirty`, or `save_overwrite_detected` regressions.

---

## Sign-off

| Item | Pass? | Notes |
|------|-------|-------|
| Decorative headers | | |
| Page icons/logos | | |
| Upload/Multitrack nav | | |
| Practice scroll/layout | | |
| Written charts badge | | |
| Song cards | | |
| Readability | | |
| A–E persistence smoke | | |
