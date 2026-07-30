# AI Music Practice Coach — Master Roadmap

**Last updated:** 2026-07-29 · **Branch:** `dev` · **Entry app:** `streamlit_music_practice_app.py` · **Persistence baseline:** [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md)

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
| `composer` | Composition Studio | Live (Sprint A foundation — **guided UX pending**) |

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
12. **Phase C cross-device sync (A–E)** — Canonical modules + `?dev=1` trace; manual Tests A–E **passed** on `dev` (2026-06-09, Test E v26 `1b00d58`).
13. **Flagship masterclass coaching (frozen foundation)** — Song/instrument/level-aware curated profiles; unified instructor voice across Active Song card, Coach tab, Practice page, section overlays ([quality standard](./plans/2026-07-29-flagship-coaching-quality-standard.md)).

---

## Cross-device persistence acceptance (manual, `?dev=1`)

| Test | Scope | Status | Deploy marker / commit |
|------|--------|--------|-------------------------|
| **A** | Studio **page** sync (phone ↔ Dell) | **PASSED** | v14 `454e0af` |
| **B** | **Practice** field sync (section focus, groove, minutes) | **PASSED** | `97fad4a` |
| **C** | **Backing** content sync (BPM, scope, loops, groove, meter) | **PASSED** | v18 `fdf9800` |
| **D** | **Active song** + display key + instrument + page + written-key + transposing subtype | **PASSED** | v25 `f153204` |
| **E** | AMI return restores song/key/instrument/written-key/subtype/page + practice/backing | **PASSED** | v26 `1b00d58` — [plan](./plans/2026-06-09-test-e-ami-return.md) |

**Policy (accepted 2026-06-09):** Tests **A–E are frozen**. Do not modify persistence unless a new `?dev=1` trace proves regression. Baseline: [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md).

**Next focus:** **P1** Composition Studio **CS-B4 Lyrics** ([plan](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)). **P0** [Uploads + Multitrack persistence](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md). **P1** Flagship coaching **content** (not framework). **P1** Command Center homepage UI (external repo; Music-side resume payloads shipped). **P1** [UI polish](./plans/2026-06-09-ui-polish-phase.md) (visual/layout only).

**Trace:** Music persistence sidebar (`?dev=1`) — Test D compare, Test E compare, **Transposing save (last cloud write)**, workspace restore, Local nav checkpoints.

---

## High-priority future enhancements

- **P1 Composition Studio — six-phase songwriting UX** — Replace CPL-like Sprint A UI with guided creative flow: Vision → Structure → Chords → Melody → Lyrics → Review ([plan](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)). Polish workflow before AI composition features.
- **P1 Flagship coaching content** — Expand masterclass profiles in `song_performance_profiles.py`; quality bar: [plan](./plans/2026-07-29-flagship-coaching-quality-standard.md). Prefer fewer, exceptional songs over volume.
- **P2 Progress-aware coaching** — Session memory, struggle/improvement adaptation, performance-prep mode ([vision](./plans/2026-07-29-progress-aware-coaching-vision.md)); build only after flagship library is mature.
- **P0 Uploads + Multitrack persistence** (immediate) — canonical `uploaded_recordings` / `multitrack_sessions`, Supabase Storage refs, tombstone sync, AMI media summaries ([plan](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md)).
- **P1 Command Center ↔ Music** — Music-side Continue payloads + workstream URLs shipped; Command Center homepage card UI pending ([plan](./plans/2026-07-03-command-center-music-integration.md)).
- **P1 UI polish** — decorative headers, logos/icons, Upload/Multitrack nav visibility, Practice layout, written-key badge, song cards — **rendering/CSS/layout only** ([plan](./plans/2026-06-09-ui-polish-phase.md)).
- Fix Practice **Section Focus** when type labels (e.g. “Verse”) do not resolve to chart section keys (“Verse 1”).
- Expand **OpenAI Coaching hub** beyond “coming soon” cards (active-song coach, session plans).
- **Karaoke vocal scoring** — implement stubs in `karaoke_mode.py` (pitch tracking / score).
- Non-voice **gig setlist** mode (setlist beyond karaoke queue).
- Production merge: ship navigation UI + docs from `dev` → `main` when stable.

---

## Known bugs & technical debt

| Issue | Area | Notes |
|-------|------|-------|
| Composition Studio Sprint A UI feels like CPL | Composer | Replace with six-phase guided UX ([plan](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)) |
| Upload/multitrack not cross-device | Upload / Multitrack | Audio embedded in JSON with 512 KB cap; no blob store; history cloud-only |
| Back/Forward nav unverified post-architecture | Navigation | Defer audit unless broken |
| Section focus empty panels | Practice | Type label vs section key mismatch; dev warning exists |
| `practice_studio` import fallback | Practice | Degraded resolver if import fails |
| OpenAI page mostly placeholders | OpenAI | Hub links out; many features “coming soon” |
| Karaoke scoring stubs | Karaoke | `record_vocal_score` not implemented |
| HRI profile stubs | Backing | Some artist profiles placeholder |
| Live mic unavailable in some builds | Analysis / Multitrack | Documented graceful fallback |
| `main` branch behind `dev` | Deploy | Navigation UI on `dev` only per DEV_WORKFLOW |

---

## UI improvements (queued — see [ui-polish-phase plan](./plans/2026-06-09-ui-polish-phase.md))

- Restore decorative script-style **page headers** + per-page **logos/icons** (Song Selection, Practice, Backing, Creative, Karaoke, Upload/Multitrack).
- Restore **Upload / Multitrack** navigation access if hidden.
- Reduce Practice scrolling; improve Control Center + chart/TAB layout.
- **Written charts ON** / **Concert charts** badge; song cards; gray readability fixes.
- Remove temporary deploy verification banner when Cloud `dev` is confirmed stable.
- Mobile tuning for floating history buttons and sidebar Pages rail.

---

## AI feature ideas

- **Progress-aware coaching** — adapt flagship masterclass copy from Practice Log, upload analysis, and AMI synthesis; same teacher voice, personalized emphasis ([vision](./plans/2026-07-29-progress-aware-coaching-vision.md)).
- Active-song OpenAI coach (context: chart, logs, last recording).
- Automated practice session plan from logs + weaknesses.
- Recording comparison narratives across sessions.
- Improv phrase suggestions from live chord + style.
- Song recommendations from practice log + genre preferences.
- Chart simplification / reharmonization suggestions (beginner mode).

---

## Area summaries (implemented today)

### Practice page
Six-tab studio: Coach (masterclass notes + plans, chord coach, exercises), Timing (metronome), Chart/TAB (notation), Lyrics (YouTube, sheets), Transpose/Instrument, Tuner. Section focus jump bar; cross-links to picker/backing/creative/custom. Adaptive sheet from catalog, upload, or fallback. Flagship songs use curated performance profiles ([coaching standard](./plans/2026-07-29-flagship-coaching-quality-standard.md)).

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

### Composition Studio
Sprint A foundation: `CompositionDocument`, library save/load, preview audio, musical snapshot. Current UI still CPL-like — **six-phase guided UX next** ([plan](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)): Vision → Structure → Chords → Melody → Lyrics → Review.

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
