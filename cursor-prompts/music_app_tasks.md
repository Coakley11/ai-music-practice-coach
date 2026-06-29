# Current Tasks — AI Music Practice Coach

**Last updated:** 2026-06-29

Actionable work items. Master context: [music_app_roadmap.md](./music_app_roadmap.md).  
**Persistence baseline (frozen A–E):** [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md)

---

## Current Priorities

### P0 — Tone & Tuner History (Practice page)

**Plan:** [plans/2026-06-27-tone-tuner-history-sprint.md](./plans/2026-06-27-tone-tuner-history-sprint.md)

- [x] `tone_takes[]` catalog schema + tombstones + merge
- [x] Save tone take after sustain analysis; lazy audio via `music-media`
- [x] Instrument-filtered library + All instruments + note/quality filters
- [x] Written + concert note fields for transposing instruments
- [x] AMI summaries in Analyze My Practice (no raw audio)
- [x] `?dev=1` diagnostics + `tests/test_media_tone_catalog.py`

**Acceptance:** Record/save Flute + Tenor Sax takes; switch instrument → correct default history; play/delete; AMI summarizes by instrument.

### P0 — AMI Analyze My Practice synthesis

**Plan:** [plans/2026-06-29-ami-practice-history-synthesis.md](./plans/2026-06-29-ami-practice-history-synthesis.md)

- [x] Full practice-history payload (logs + upload analyses + tone takes + export metadata)
- [x] 10-section local progress report + instant solver route
- [x] Analyzed vs unanalyzed export distinction (exports not playing evidence alone)
- [x] Safety checks + `?dev=1` AMI synthesis diagnostics on Practice Log
- [x] `tests/test_practice_history_synthesis.py`

**Acceptance:** Analyze My Practice synthesizes cross-source evidence; no raw audio in payload; report shows improvements, needs work, and next steps.

### P0 — Uploads + Multitrack persistence (media layer sprint)

**Practice Log v1 baseline:** quick save, refresh/delete persistence, search/filter, instrument/key labels, AMI handoff title — working.

**Goal:** Uploads and Multitrack as persistent, cross-device music memory (like Practice Log).

**Plan (audit complete):** [plans/2026-06-27-uploads-multitrack-persistence-sprint.md](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md)

Implementation order:

- [x] **B** — `media_state.py` + `media_persistence.py` (canonical model, tombstones, merge; no blobs in workspace envelope) — scaffold + tests
- [ ] **C** — Upload auto-catalog + legacy `upload_history` migration + storage refs
- [ ] **D** — Multitrack catalog + slot/control fix + storage refs
- [ ] **E** — AMI payload: `uploaded_recordings` + `multitrack_sessions`; **Command Center solver** references recordings (local synthesis shipped; external solver TBD)
- [ ] **F** — UI lists, notes, delete; `?dev=1` media diagnostics
- [ ] **G** — Tests + focused commits per step

**Acceptance:** phone↔Dell upload/multitrack sync; delete tombstones; refresh survival; Analyze My Practice includes media summaries.

### P1 — AMI improvements (ongoing)

Music Coach AMI: expand send context (song, section, mission, analysis, practice history, **upload/multitrack summaries**); music analysis router/solvers; teaching-style answers. Return restore already strong (Test E).

**Sync audit (2026-06-11):** See Command Center [plans/2026-06-11-ami-enhancement-roadmap.md](../../daniel-ai-command-center/cursor-prompts/plans/2026-06-11-ami-enhancement-roadmap.md). Upload/multitrack metadata → dedicated media channel (not main envelope) — see media sprint plan above.

### P1 — UI polish (ongoing)

**Frozen:** Tests **A–E** passed — do not reopen persistence without `?dev=1` trace regression.  
**Plan:** [plans/2026-06-09-ui-polish-phase.md](./plans/2026-06-09-ui-polish-phase.md)

- [ ] Restore **decorative script-style page headers** on main studio pages
- [ ] Restore **colorful headers / logos / icons** (Song Selection, Practice, Backing, Creative, Karaoke, Upload/Multitrack)
- [ ] Restore **Upload / Multitrack** nav access (sidebar + quick-nav)
- [ ] Improve **Practice** page layout and readability (less scroll, Control Center, chart/TAB)
- [ ] Add clearer **“Written charts ON”** / **“Concert charts”** badge (display only)
- [ ] Improve **song cards** and **active song display**
- [ ] Clean remaining **gray / readability** issues
- [ ] Remove temporary deploy banner when verified (`ui-nav-deploy-marker`)

**Architecture preservation:** Keep exact current page + persistence architecture. **Do not move or modify:** page routing, restore code, cloud sync, AMI return, navigation ownership, active-song state code. **UI = rendering/CSS/layout only** — `app_ui.py`, display helpers, badges that read (not write) state. Separate UI-only commit(s). See `.cursor/rules/ui-polish-architecture-preservation.mdc`.

### P1 — Back / Forward navigation audit (later — not blocking unless app use impaired)

**Plan:** [plans/2026-06-09-back-forward-nav-audit.md](./plans/2026-06-09-back-forward-nav-audit.md)

Back/Forward may need rebuild or re-validation after architecture changes. **Defer** until after P0 UI polish unless broken nav blocks normal use.

- [ ] Manual audit: Back/Forward across Song Selection, Practice, Backing, Creative, Karaoke, Upload/Multitrack
- [ ] Verify `final_studio_page`, page owner, no stale picker/practice/backing overwrites
- [ ] Verify active song + Practice + Backing state preserved across history nav
- [ ] Confirm **← Back** / **Forward →** placement and scroll behavior on main pages
- [ ] If pass → mark Back/Forward **PASSED** and freeze
- [ ] If fail → **isolated nav fix** commit (not mixed with UI polish; do not reopen Tests A–E unless `?dev=1` trace proves regression)

### P2 — Deploy verification

- [ ] Confirm Streamlit Cloud **dev** deploy marker `cpl-display-key-sync-v27-live-fix` + git commit on `?dev=1` probe
- [ ] **CPL live sync (v27)** — verify after deploy:
  - Display / Practice Key sync Dell → phone (canonical beats session home key on restore)
  - Backing Original Key + default Groove/Style from custom song (not stale catalog G / Pop)
  - Custom → Song Selection switch (no refresh loop; Last Catalog Song card + restore)
  - Backing page: key badges only in blue context strip (Written badge when written mode on)

### P3 — Practice reliability

- [ ] Fix Section Focus when label is type-only (“Verse”) vs chart key (“Verse 1”) — empty Coach/Chart panels
- [ ] Add regression test for `practice_resolve_focus_section` mapping
- [ ] Harden `practice_studio` import path (avoid silent fallback resolver)

---

## Next Features

*(After P0–P1 or in parallel)*

- [ ] OpenAI hub: first real “active song coach” flow (not placeholder card)
- [ ] Karaoke: vocal pitch/score stub → minimal MVP scoring display
- [ ] Non-voice performance setlist (reuse karaoke queue patterns)
- [ ] Creative Lab: interactive UI for Arrangement Assistant (beyond text expander)
- [ ] Link `README.md` → `cursor-prompts/music_app_roadmap.md`

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
- [x] Cross-device Test D active song + key + instrument + page + written-key + subtype (v25 `f153204`)
- [x] Test E AMI return — song/key/instrument/written-key/subtype/page + practice/backing (v26 `1b00d58`, 2026-06-09)
- [x] Floating page history navigation (`5ed9d93`)
- [x] Back arrow main-panel positioning (`9e0728a`)
- [x] Roadmap documentation system (`cursor-prompts/`)

---

## Notes

- Work on branch **`dev`** only; push `origin/dev` for Streamlit Cloud dev app.
- **UI polish** and **nav audit/fix** = separate commits; never mix with persistence.
- When a task ships, move detail to `music_app_completed_features.md` and uncheck here.
- For large implementation plans, save the full plan body under `cursor-prompts/plans/` and link from this file.
