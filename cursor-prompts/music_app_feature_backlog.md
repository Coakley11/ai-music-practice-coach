# Feature Backlog — AI Music Practice Coach

**Last updated:** 2026-06-09 (Tests A–E frozen)

Ideas not yet scheduled. Prioritized loosely by value. See [music_app_roadmap.md](./music_app_roadmap.md) for master plan.

---

## Current Priorities

*Tests **A–E** are **passed** and **frozen** on `dev`. See [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md).*

*Active: **P0 UI polish first** — Back/Forward audit **P1 later**. See [music_app_tasks.md](./music_app_tasks.md).*

| Priority | Phase | Plan |
|----------|-------|------|
| **P0** (immediate) | UI polish — headers, icons, Practice layout, badges, song cards; **visual/layout only** | [2026-06-09-ui-polish-phase.md](./plans/2026-06-09-ui-polish-phase.md) |
| **P1** (later) | Back/Forward nav audit — manual first; fix only if broken; not blocking unless app use impaired | [2026-06-09-back-forward-nav-audit.md](./plans/2026-06-09-back-forward-nav-audit.md) |

---

## Next Features

### UI polish (scheduled — UI-only commits)

- Restore decorative **script-style page headers** + per-page logos/icons (Practice, Backing, Creative, Karaoke, Upload)
- Restore **Upload / Multitrack** sidebar/quick-nav access
- Practice: reduce scroll, Control Center layout, chart/TAB presentation
- **Written charts ON** / **Concert charts** status badge
- Song cards + active song display; gray readability cleanup

### Navigation & shell

- **Back/Forward audit** — manual first; trace `nav_history_stack`, `back_button_clicked`, etc. if gaps found
- Sidebar Pages: remember expanded/collapsed per user (already session-persisted; consider default expanded for new users)
- Keyboard shortcuts: Alt+← / Alt+→ for history
- Breadcrumb trail showing page history stack (debug / power users)
- Deep link to specific Practice tab or Backing scope via URL params

### Cross-device persistence (post A–E)

- Conflict resolution UI when cloud vs local diverge (suite-wide)

### Practice page

- Section Focus: auto-map type labels to first matching section key
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

### Creative Progressions

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
