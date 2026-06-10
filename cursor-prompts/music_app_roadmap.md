# AI Music Practice Coach — Master Roadmap

**Last updated:** 2026-06-09 · **Branch:** `dev` · **Entry app:** `streamlit_music_practice_app.py` · **Persistence baseline:** [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md)

This is the master planning document. Related files:

| File | Purpose |
|------|---------|
| [music_app_tasks.md](./music_app_tasks.md) | Active work and near-term execution |
| [music_app_feature_backlog.md](./music_app_feature_backlog.md) | Queued ideas and enhancements |
| [music_app_completed_features.md](./music_app_completed_features.md) | Shipped capabilities by area |

---

## Current app status

**Product:** Streamlit-based music practice studio (Daniel Cohen AI Music Practice Coach v19) with nine workspaces, catalog + custom songs, backing synthesis, practice coaching, recording analysis, and optional cloud persistence.

**Stack:** Python 3, Streamlit, librosa, custom WAV backing engine, optional Supabase suite storage, optional OpenAI.

**Deployment:** Daily work on `origin/dev` (Streamlit Cloud dev app). Production `main` may lag behind `dev` for navigation UI and recent fixes — see [docs/DEV_WORKFLOW.md](../docs/DEV_WORKFLOW.md).

**Studio pages (all implemented):**

| ID | UI label | Status |
|----|----------|--------|
| `practice` | Practice | Live |
| `picker` | Song Selection | Live |
| `backing` | Backing Track | Live |
| `custom` | Custom Progression | Live |
| `creative` | Creative Lab | Live |
| `multitrack` | Multitrack | Live |
| `analysis` | Upload Analysis | Live |
| `log` | Practice Log | Live |
| `openai` | OpenAI | Live (API key required) |

---

## Major completed milestones

1. **Multi-page studio shell** — Global instrument / level / focus / display key; per-page local state; back/forward history with floating nav.
2. **Song catalog & Active Song Hub** — Curated library, search, filters, favorites, user chart overrides, lyrics/cues editor.
3. **Practice Control Center** — Six-tab practice workspace (Coach, Timing, Chart/TAB, Lyrics, Transpose, Tuner).
4. **Backing Track Studio** — BPM/groove/meter, section scope, HRI humanization, follow-along, cached generation.
5. **Custom Progression Lab** — Build-by-click progressions; active custom source for practice/backing.
6. **Creative Lab + Improvisation Intelligence** — Multi-tab improv coach, harmony map, missions, motif tools.
7. **Upload Analysis & Multitrack** — Single/multitrack recording analysis, mission scoring, HTML mixer export.
8. **Karaoke / Voice mode** — Performance setlist, auto-advance backing, lyric-focused UI.
9. **Instrument & key system** — Transposing instruments, written key charts, guitar capo, voice wording.
10. **Persistence** — Local JSON state, optional Supabase full-session sync, suite activity logging.
11. **UI theme bundle** — `app_ui.py` studio panels, genre/instrument card modifiers, per-page style injectors.
12. **Phase C cross-device sync (A–D)** — Canonical modules + `?dev=1` trace; manual Tests A–D **passed** on `dev` (2026-06-09, Test D v25 `f153204`).

---

## Cross-device persistence acceptance (manual, `?dev=1`)

| Test | Scope | Status | Deploy marker / commit |
|------|--------|--------|-------------------------|
| **A** | Studio **page** sync (phone ↔ Dell) | **PASSED** | v14 `454e0af` |
| **B** | **Practice** field sync (section focus, groove, minutes) | **PASSED** | `97fad4a` |
| **C** | **Backing** content sync (BPM, scope, loops, groove, meter) | **PASSED** | v18 `fdf9800` |
| **D** | **Active song** + display key + instrument + page + written-key + transposing subtype | **PASSED** | v25 `f153204` |
| **E** | AMI return restores song/key/instrument/written-key/subtype/page + practice/backing | **IN PROGRESS** | v26 trace — [plan](./plans/2026-06-09-test-e-ami-return.md) |

**Policy (accepted 2026-06-09, updated after Test D pass):** Tests **A–D are frozen**. Do not modify page / Practice / Backing / active-song cloud persistence unless a new `?dev=1` trace proves regression. Baseline notes: [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md). **Next focus:** Test E manual sign-off, then UI polish (separate commit).

**Trace:** Music persistence sidebar (`?dev=1`) — Test D compare, **Transposing save (last cloud write)**, workspace restore, Backing device compare.

---

## High-priority future enhancements

- Stabilize floating back/forward nav across all pages and Streamlit versions (verify on Cloud `dev`).
- Fix Practice **Section Focus** when type labels (e.g. “Verse”) do not resolve to chart section keys (“Verse 1”).
- Expand **OpenAI Coaching hub** beyond “coming soon” cards (active-song coach, session plans).
- **Karaoke vocal scoring** — implement stubs in `karaoke_mode.py` (pitch tracking / score).
- Non-voice **gig setlist** mode (setlist beyond karaoke queue).
- Production merge: ship navigation UI + docs from `dev` → `main` when stable.

---

## Known bugs & technical debt

| Issue | Area | Notes |
|-------|------|-------|
| Back arrow under sidebar / pinning | Navigation | Fixed on `dev` (`9e0728a`); verify deploy marker `nav-back-left-fix-1` |
| Section focus empty panels | Practice | Type label vs section key mismatch; dev warning exists |
| `practice_studio` import fallback | Practice | Degraded resolver if import fails |
| OpenAI page mostly placeholders | OpenAI | Hub links out; many features “coming soon” |
| Karaoke scoring stubs | Karaoke | `record_vocal_score` not implemented |
| HRI profile stubs | Backing | Some artist profiles placeholder |
| Live mic unavailable in some builds | Analysis / Multitrack | Documented graceful fallback |
| `main` branch behind `dev` | Deploy | Navigation UI on `dev` only per DEV_WORKFLOW |

---

## UI improvements (queued)

- Remove temporary deploy verification banner when Cloud `dev` is confirmed stable.
- Consistent Active Song Hub actions across catalog and custom sources.
- Mobile tuning for floating history buttons and sidebar Pages rail.
- Deeper Creative Lab UI for non-improv modes (currently text expanders).
- Tutorial refresh for floating nav + collapsed sidebar defaults.

---

## AI feature ideas

- Active-song OpenAI coach (context: chart, logs, last recording).
- Automated practice session plan from logs + weaknesses.
- Recording comparison narratives across sessions.
- Improv phrase suggestions from live chord + style.
- Song recommendations from practice log + genre preferences.
- Chart simplification / reharmonization suggestions (beginner mode).

---

## Area summaries (implemented today)

### Practice page
Six-tab studio: Coach (plans, chord coach, exercises), Timing (metronome), Chart/TAB (notation), Lyrics (YouTube, sheets), Transpose/Instrument, Tuner. Section focus jump bar; cross-links to picker/backing/creative/custom. Adaptive sheet from catalog, upload, or fallback.

### Backing Track Studio
Playback setup (scope, loops, BPM, groove, meter), HRI, WAV generation + cache, follow-along timeline, form timeline, coaching overlay, voice-aware copy.

### Karaoke
Voice instrument → performance setlist queue, session auto-advance on Backing, countdown, lyric themes, chord strip toggle, skip controls, missing-lyrics CTA.

### Upload & Multitrack
Analysis: upload/live mic, mission goals, librosa coach report, history. Multitrack: six slots, mixer HTML, export WAV, link to analysis.

### Song Selection
Catalog browse/search/filters, active song dropdown, favorites, recent chips, lyrics & cues editor, chart editor, karaoke setlist (voice).

### Active Song Hub
Hero card (keys, BPM, meter, sections), Practice/Backing/Karaoke/Chord Coach actions, edit chart CTA; custom progression variant on CPL.

### Creative Progressions
**Custom:** click-build sections, subdivisions, save/list, harmonic hints. **Creative:** Improvisation Intelligence tabs + text labs (deep harmony, arrangement, weakness, development).

### Instrument modes
Piano, Guitar, Bass, winds, Voice, etc.; per-instrument focus lists; voice body CSS; transposition helpers.

### Written key mode
Display/practice key (concert); transposing instrument sidebar; “chart in written key” toggle; badges on charts.

### Performance setlists
Karaoke Performance Setlist (voice): queue on Song Selection, persisted, session on Backing with auto-generate between songs.

---

## Notes

- When asking Cursor for a **roadmap**, **feature plan**, or **implementation plan**, agents should update all four `cursor-prompts/music_app_*.md` files (see `.cursor/rules/music-app-roadmap-docs.mdc`).
- Long implementation plans: save full content to the appropriate `.md` file under `cursor-prompts/`.
- Tests: `tests/test_studio_navigation.py`, `tests/test_sidebar_nav_collapse.py`, plus domain tests per module.
