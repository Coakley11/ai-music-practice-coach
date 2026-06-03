# Completed Features — AI Music Practice Coach

**Last updated:** 2026-06-03

---

## Current Priorities

*None — this file is the historical record. See [music_app_tasks.md](./music_app_tasks.md) for active work.*

---

## Next Features

*See [music_app_feature_backlog.md](./music_app_feature_backlog.md).*

---

## Long-Term Vision

*See [music_app_roadmap.md](./music_app_roadmap.md).*

---

## Completed Features

### Platform & navigation

- [x] Nine studio pages with `studio_page` routing (`studio_nav_history.py`, `streamlit_music_practice_app.py`)
- [x] Per-page local UI snapshots on navigate; globals (instrument, key, song) preserved (`studio_page_persistence.py`)
- [x] Back/forward page history stacks
- [x] Floating ← Back / Forward → in main content area (`studio_nav_history.py`, `app_ui.py`)
- [x] Collapsible sidebar **☰ Pages** menu (`render_sidebar_studio_nav`)
- [x] Top quick-nav art row (Caveat script labels)
- [x] Cross-page shortcut links on Practice, Backing, etc.
- [x] Scroll anchors + pending scroll script (`studio_scroll_anchors.py`)
- [x] First-run tutorial (8 steps, `app_tutorial.py`)
- [x] Suite deep links / resume launch (`suite_deep_links.py`, `suite_resume_launch.py`)

### Practice page

- [x] Practice Control Center (groove, session length, instrument/level/focus)
- [x] Section Focus jump bar + handoff to Backing
- [x] **Coach** tab: section focus, scale suggestions, coach exercise, chord coach overlay
- [x] **Timing** tab: metronome (full song / section loop), rhythm guide
- [x] **Chart / TAB** tab: chord chart, notation/TAB generation (`practice_notation.py`)
- [x] **Lyrics** tab: YouTube panel, lyric-chord sheets, vocal showcase hints
- [x] **Transpose / Instrument** tab: transpose helpers, capo, flute transposition
- [x] **Tone / Tuner** tab: `tuner_tone_ui.py`, live tuner (`tuner_live.py`)
- [x] Adaptive practice sheet (catalog, upload analysis, fallback progression)
- [x] Beginner arrangement view (`beginner_arrangement.py`)
- [x] Daily time breakdown / practice plan hooks

### Backing Track Studio

- [x] Active song card + canonical BPM/groove/meter on song change
- [x] Playback scope: full song, single section, multi-section loops
- [x] BPM slider, groove style, time signature overrides
- [x] Harmonic Rhythm Intelligence (HRI) humanization (`harmonic_rhythm_intelligence.py`)
- [x] WAV backing generation + session cache (`backing_generation.py`, `studio_cache.py`)
- [x] Inline player + live chord follow-along timeline
- [x] Form timeline / section order tables
- [x] Per-section coaching overlay
- [x] Regeneration warnings on key/meter change
- [x] Voice-mode lyric-focused styling on Backing

### Karaoke

- [x] Voice instrument detection + global vocal-focus CSS
- [x] Karaoke Performance Setlist queue (catalog pick keys)
- [x] Setlist UI on Song Selection (`karaoke_ui.py`)
- [x] Session start → Backing with auto-generate + auto-advance
- [x] Countdown overlay, lyric color theme, chord strip show/hide
- [x] Skip / end controls; audio-ended JS bridge
- [x] Karaoke lyric panel during follow-along (user lyrics)
- [x] Missing-lyrics CTA → picker editor

### Upload & Multitrack

- [x] Upload Analysis page: single recording + multitrack comparison modes
- [x] File upload (WAV/MP3/M4A/OGG/MP4/MOV) + `upload_media.py` prep
- [x] Live mic input (when Streamlit supports it)
- [x] Mission goals + locked criteria (`mission_analysis.py`)
- [x] Librosa analysis: timing, groove, pitch, dynamics, waveform
- [x] Coach report dashboard + mission score breakdown
- [x] Performance history append (`ai_performance_history.py`)
- [x] Multitrack page: six instrument slots, volume/delay/mute/solo
- [x] HTML transport mixer + count-in + mixed WAV export

### Song Selection

- [x] Curated catalog load + hot reload (`song_catalog/`)
- [x] Search (title, artist, genre, style, level)
- [x] Multi-select genre filters + expander for more genres
- [x] Music source toggle: catalog vs Custom Progression
- [x] Active song dropdown + pick key resolution (`songs/state.py`)
- [x] Recently selected chips (last 3)
- [x] Favorites on active song card
- [x] Developer filters: library mode, chart status, level
- [x] Lyrics & Cues editor (`lyrics_cues_panel.py`)
- [x] Song chart editor + user overrides JSON (`song_chart_editor.py`)

### Active Song Hub

- [x] Catalog hub hero: title, artist, keys, BPM, meter, sections, groove, chart source
- [x] Actions: Favorite, Practice, Backing, Karaoke (voice), Chord Coach
- [x] Edit Song Chart CTA + scroll anchors
- [x] Custom progression hub variant (CPL active)
- [x] Sidebar active source banner + jump to Song Selection

### Creative Progressions

- [x] **Custom Progression Lab:** section builder, chord subdivisions, saved progressions, analysis text, exercises (`custom_progression_lab.py`, `cpl_page_ui.py`)
- [x] Custom source as global active song (`CPL_ACTIVE_KEY`)
- [x] **Creative Lab:** mode selector
- [x] **Improvisation Intelligence:** Entry & Jam, Live Coach, Phrase/Motif, Missions, Harmony Map, Deep Harmony, Metrics & AI (`improvisation_intelligence_ui.py`)
- [x] Deep Harmonic Analyzer, Arrangement Assistant, Weakness Detection, Development Tracking (text labs)
- [x] Cross-links to Practice, Backing, Analysis, Picker, Custom

### Instrument modes

- [x] Global instrument / level / practice focus (`practice_setup_globals.py`, sidebar widgets)
- [x] Per-instrument focus option lists
- [x] Voice mode: `data-vocal-focus` body flag + enlarged lyric CSS
- [x] Instrument-aware chart labels and exercises (`instrument_aware.py`)

### Written key mode

- [x] Concert display / practice key in sidebar (`songs/key_state.py`)
- [x] Transposing instruments: Sax, Trumpet, Clarinet variants (`instrument_transposition.py`)
- [x] “Show chart in written key” toggle + sidebar widgets
- [x] Chart key mode badge on practice charts
- [x] Guitar capo: shape vs sounding key (`guitar_capo.py`)

### Performance setlists

- [x] Karaoke Performance Setlist (voice-only): add/reorder/remove queue
- [x] Queue persistence in `music_persistent_state` (`karaoke_queue`)
- [x] Start session → Backing workflow with auto-advance between songs

### Persistence & cloud

- [x] Local JSON: `data/music_user_state.json` (`music_persistent_state.py`)
- [x] Page snapshots, filters, backing scope, karaoke prefs, improv tabs
- [x] Optional Supabase full-session restore (`suite_cloud_state.py`)
- [x] Suite activity logging on practice log save
- [x] Session reset (preserves chart overrides file)
- [x] Autosave at end of Streamlit run

### AI & coaching

- [x] OpenAI secrets resolution (`openai_secrets_config.py`)
- [x] OpenAI hub page (gated); links to Log, Analysis, Creative
- [x] Practice Log coach + optional OpenAI enhance (`practice_log_coach.py`)
- [x] Rule-based insights + session plan from logs
- [x] Recording analysis coach narratives + mission scoring
- [x] Improvisation missions linked to upload workflow
- [x] Performance history unified store

### UI / theme

- [x] Global `inject_app_theme()` + polish layer (`app_ui.py`)
- [x] Studio brand header, panel shells, genre/instrument card classes
- [x] Per-page CSS: Practice, Backing, Picker, Creative, Custom, Upload, Multitrack
- [x] Karaoke stage scoped styling (`.st-key-karaoke_stage`)
- [x] Sidebar section tones (source, key, library, nav, etc.)
- [x] Studio UI release markers per page

---

## Notes

- Mark new completions here and mirror a one-line summary in `music_app_roadmap.md`.
- Remove items from `music_app_tasks.md` when done.
