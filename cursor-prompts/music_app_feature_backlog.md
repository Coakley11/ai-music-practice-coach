# Feature Backlog — AI Music Practice Coach

**Last updated:** 2026-07-30 (Tests A–E frozen)

Ideas not yet scheduled. Prioritized loosely by value. See [music_app_roadmap.md](./music_app_roadmap.md) for master plan.

---

## Current Priorities

*Tests **A–E** are **passed** and **frozen** on `dev`. See [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md).*

*Active: **P0 media persistence sprint** — see [music_app_tasks.md](./music_app_tasks.md) and [2026-06-27-uploads-multitrack-persistence-sprint.md](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md).*

| Priority | Phase | Plan |
|----------|-------|------|
| **P0** (immediate) | Uploads + Multitrack persistence, cross-device sync, AMI media summaries | [2026-06-27-uploads-multitrack-persistence-sprint.md](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md) |
| **P1** | UI polish — headers, icons, Practice layout, badges, song cards; **visual/layout only** | [2026-06-09-ui-polish-phase.md](./plans/2026-06-09-ui-polish-phase.md) |
| **P2** (later) | Back/Forward nav audit | [2026-06-09-back-forward-nav-audit.md](./plans/2026-06-09-back-forward-nav-audit.md) |

---

## Next Features

### UI polish (scheduled — UI-only commits)

- Restore decorative **script-style page headers** + per-page logos/icons (Practice, Backing, Creative, Karaoke, Upload)
- Restore **Upload / Multitrack** sidebar/quick-nav access
- Practice: reduce scroll, Control Center layout, chart/TAB presentation
- **Written charts ON** / **Concert charts** status badge
- Song cards + active song display; gray readability cleanup

### Command Center integration

- [x] Music-side resume payloads + Continue card builders (`music_resume_payload.py`, `music_command_center.py`)
- [x] App Directory workstream soft-entry URLs
- [ ] Command Center homepage UI (external repo)
- See [plans/2026-07-03-command-center-music-integration.md](./plans/2026-07-03-command-center-music-integration.md)

### Navigation & shell

- **Back/Forward audit** — manual first; trace `nav_history_stack`, `back_button_clicked`, etc. if gaps found
- Sidebar Pages: remember expanded/collapsed per user (already session-persisted; consider default expanded for new users)
- Keyboard shortcuts: Alt+← / Alt+→ for history
- Breadcrumb trail showing page history stack (debug / power users)
- Deep link to specific Practice tab or Backing scope via URL params

### Cross-device persistence (post A–E)

- **Uploads + Multitrack media channel** — in sprint; see [plan](./plans/2026-06-27-uploads-multitrack-persistence-sprint.md)
- Conflict resolution UI when cloud vs local diverge (suite-wide)

### Practice page

- Section Focus: auto-map type labels to first matching section key
- **Progress-aware coaching** — adapt flagship copy from logs/analysis; same teacher voice ([vision](./plans/2026-07-29-progress-aware-coaching-vision.md))
- Loop practice mode: repeat section N times with count-in
- Split-hand piano suggestions for intermediate+
- Print-friendly practice sheet PDF export
- Compare beginner vs full chart side-by-side

### Backing Track Studio

- More groove templates per genre (funk, bossa, ballad swing)
- Stem export (bass-only, drums-only) from backing engine
- Tap-tempo BPM detect from user recording
- Backing preview before full render (low-latency sketch)

### Karaoke

- Real-time pitch scoring (`karaoke_mode` stubs)
- Lyric teleprompter font size presets per device
- Duet mode (two vocal queues)
- Background video / YouTube sync timestamp

### Upload & Multitrack

- Dedicated chord recognition from audio (noted as future in `recording_analysis.py`)
- Onset-level timing report export
- Multitrack: record all layers in one Streamlit session without reload
- Share mixed export via cloud link

### Song Selection

- Playlist folders / tags for catalog songs
- Bulk import user songs (MusicXML, ChordPro)
- Community chart sharing (moderated)
- Audio preview clips per catalog entry

### Active Song Hub

- “Similar songs” recommendations from catalog metadata
- Last practiced timestamp on hero card
- Quick transpose presets (+1/-1 semitone buttons on hub)

### Song Composer / Composition Studio

- **Six-phase guided songwriting UX** — vision → structure → chords → melody → lyrics → review; coach panel; not CPL
- **AI-assisted creative workspace** (later) — explained proposals; **What if…?** experimentation
- Architecture: [plans/2026-07-29-composition-studio-v1-architecture.md](./plans/2026-07-29-composition-studio-v1-architecture.md)
- **Active UX plan:** [plans/2026-07-29-composition-studio-six-phase-songwriting.md](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)
- Prior proposal (superseded step order): [plans/2026-07-29-composition-studio-guided-ux.md](./plans/2026-07-29-composition-studio-guided-ux.md)
- V1: polished workflow + save library; `integration` stub for future Practice/Backing/Coach hub
- **Melody hum capture (flagship)** — natural workflow: build chord progression → Record → section chords loop continuously → hum/sing → pitch + rhythm analysis → editable melody (no manual note entry). Potential flagship for Composition Studio.
- **Melody refinement loop** — after capture or rule-based seed: smoother, more energetic, more rhythmic, simpler, more emotional, larger range, easier to sing (AI + rules hybrid in CS-C; rule-based buttons shipped as scaffold)

### Creative Progressions

- **Level-aware musical example generation (app-wide)** — every auto-generated example adapts to Beginner / Intermediate / Advanced: simpler rhythms and chord-tone lines for beginners; passing tones and variety for intermediate; syncopation, approach notes, and performance-like phrasing for advanced. Surfaces: Practice, Missions (started), TAB, ABC/sheet, Creative exercises, improvisation/harmony examples, Composition Studio suggestions, future AI ideas. Goal: examples feel teacher-written, not generic drills.
- **Creative AI music coach (long-term)** — personal, conversational coach for improv, accompaniment, composition, hearing harmonic movement, and effective practice; adapts to instrument, level, goals, and repertoire (extends Deep Harmonic Analyzer + Missions)
- Import progression from Nashville number chart paste
- MIDI export of custom progression
- CPL → share link / QR for students
- Improv: live MIDI input phrase capture

### Instrument & written key

- Ukulele, Violin, Cello instrument profiles
- Horn transposition quick-reference overlay on chart
- Capo partial-fret suggestions for difficult keys

### Performance setlists

- General-purpose setlist (all instruments) separate from karaoke
- Setlist total duration estimate from BPM + form
- Print setlist PDF for gigs
- Import setlist from CSV

### AI

- **Progress-aware coaching layer** — `coaching_adaptation.py` overlay on frozen masterclass profiles; Practice Log + upload analysis + AMI inputs ([vision](./plans/2026-07-29-progress-aware-coaching-vision.md))
- OpenAI: active-song Q&A with chart + log context
- OpenAI: weekly practice email summary
- OpenAI: generate custom mission criteria from user goal text
- Local LLM fallback when API key absent
- Improv phrase audio playback (TTS or sample library)

### UI

- *(Promoted to P0 — see ui-polish-phase plan)* Decorative headers, page icons, Practice layout, written-key badge, song cards
- Dark/light theme toggle (sidebar is dark; main is light)
- Reduce sidebar clutter: group key + instrument into one collapsible
- Accessibility: ARIA on floating history buttons
- Onboarding wizard for first-time users (beyond tutorial)

### Cloud & suite

- Conflict resolution UI when cloud vs local state diverge
- Practice log sync to Supabase table (not only full_session blob)
- Cross-app resume card on suite home

---

## Long-Term Vision

- **Progress-aware coaching:** teacher remembers last session; emphasizes struggle sections; graduates advice as player improves; performance-prep mode ([plan](./plans/2026-07-29-progress-aware-coaching-vision.md)).
- **Adaptive curriculum:** system learns weak sections from logs/recordings and schedules practice.
- **Ensemble rehearsal room:** remote multitrack + shared backing + chat.
- **Notation editor:** WYSIWYG chart edit rivaling dedicated apps.
- **Marketplace:** user-submitted progressions and backing styles.
- **Native apps:** wrap Streamlit prototype or rebuild core in React + audio engine.

---

## Completed Features

*Shipped items are archived in [music_app_completed_features.md](./music_app_completed_features.md).*

---

## Notes

- Before building, check if feature overlaps existing module (grep `streamlit_music_practice_app.py` dispatch).
- Estimate: **S** = small UI tweak, **M** = new panel/flow, **L** = new module + tests.
- Promote items to `music_app_tasks.md` with owner and target commit when scheduled.
