# Completed Features — AI Music Practice Coach

**Last updated:** 2026-08-17

---

## Current Priorities

*See [music_app_tasks.md](./music_app_tasks.md) — Practice Focus System is active on `feature/practice-focus-system`.*

---

## Next Features

*See [music_app_feature_backlog.md](./music_app_feature_backlog.md).*

---

## Long-Term Vision

*See [music_app_roadmap.md](./music_app_roadmap.md).*

---

## Completed Features

### Practice Focus System — Phase 3B Custom + Arrangement advisory (2026-08-17)

- [x] Custom Progression Lab Focus exercises (`practice_focus_custom.py` + `generate_exercises_markdown`)
- [x] Same progression + different Focus → different drills; explicit request precedence; same-rerun
- [x] Arrangement Assistant Focus suggestions are advisory only (no arrangement mutation)
- [x] Section deep-practice exercise text consumes Focus lines
- [x] Deeper Creative Focus work + Motif Sequence UI remain deferred; Backing Focus card remains optional/deferred
- **Branch:** `feature/practice-focus-system` (not merged to `dev`; clean park checkpoint)
- Tests: `tests/test_practice_focus_phase3b_custom.py`
- Evidence: `scripts/evidence-practice-focus-custom/`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Practice Focus System — Phase 3A Practice Coach & Adaptive Weakness (2026-08-16)

- [x] Focus-aware timed session builder (`build_focus_timed_session`) drives Timed Session Planner + Practice-page time ratios + weekly 30-min plan
- [x] Same instrument/song + change-only Focus yields visibly different session blocks (Guitar Strumming/Timing/Harmony; Sax Tone/Articulation/Phrasing)
- [x] Same-rerun Focus change rebuilds session plan; historical Focus diversifies without overriding current Focus
- [x] Adaptive Weakness Detection ranks measured scores with Focus relevance; never invents Focus-only defects; severe non-Focus still surfaces
- [x] Creative audits + Motif Sequence full-staff feature + optional Backing Focus coaching documented in plan
- **Branch:** `feature/practice-focus-system` (not merged to `dev`)
- Tests: `tests/test_practice_focus_phase3a_session_weakness.py`
- Evidence: `scripts/evidence-practice-focus-session/`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Practice Focus System — Phase 2D Multitrack (2026-08-16)

- [x] Snapshot Practice Focus at Multitrack ensemble analysis start
- [x] Focus rewrites coaching/tips without mutating measured onset/RMS comparisons or score fields
- [x] Capability map: onset/RMS measured; stroke/resonance/chord identity unsupported
- [x] Dashboard + project history preserve frozen Focus
- **Branch:** `feature/practice-focus-system` (not merged to `dev`)
- Tests: `tests/test_practice_focus_phase2d_multitrack.py`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Practice Focus System — Phase 2C Practice Log / Practice Coach (2026-08-16)

- [x] New log entries freeze exact Practice Focus; old rows stay missing when missing
- [x] Weekly Analyze My Practice receives structured Focus history (exact vs coarse vs missing)
- [x] Current Focus informs next steps without rewriting historical interpretation
- [x] Log cards show frozen historical Focus captions
- **Branch:** `feature/practice-focus-system` (not merged to `dev`)
- Tests: `tests/test_practice_focus_phase2c_log.py`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Practice Focus System — Phase 2B Upload / AI Coach (2026-08-16)

- [x] Snapshot Practice Focus at analysis start; historical results stay immutable
- [x] Supported mission metrics are unioned (never removing explicit user metrics)
- [x] Coach summary and next exercises follow Focus; severe non-focus scores still surface
- [x] Dashboard shows `Practice Focus at analysis: …` or `Not recorded`
- **Branch:** `feature/practice-focus-system` (not merged to `dev`)
- Tests: `tests/test_practice_focus_phase2b_upload.py`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Practice Focus System — Phase 2A AMI + Practice page (2026-08-16)

- [x] Shared `practice_focus_coaching.py` consumes policy/context (no musical-state ownership)
- [x] AMI practice-plan intents use timed blocks / priorities / exercises from Practice Focus
- [x] Factual theory path (`What notes are in C major?`) is not hijacked by Strumming
- [x] Practice page drills, guitar copy, warmup/watch-for, and plan steps follow the selected Focus
- [x] Same-rerun Focus change updates AMI/Practice without refresh; Guitar Strumming → Saxophone still falls back to Tone
- **Branch:** `feature/practice-focus-system` (not merged to `dev`)
- Tests: `tests/test_practice_focus_phase2_ami_practice.py`
- Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)

### Phase 1 Creative-state persistence — Item 8 (2026-08-03)

- [x] Atomic conditional music workspace cloud writes (CAS); stale-device block + resync-then-save recovery
- [x] Logical revision unification (`music_metrics_logical_revision`) — blob/top-level sync; nested CAS filter when appropriate
- [x] Phone current-device save **PASS**; Dell stale **TEST A/B/C PASS** @ build **`8ef698e`** (cloud **323→325**)
- [x] Item 8 `?dev=1` panel: `logical_revision_source`, `selected_cas_filter_path`, `cas_http_trace`, `violations_current_attempt`
- **Frozen:** implementation baseline `4a446a0`, `62bf143`, `4192fa2`, **`8ef698e`** — do not weaken CAS or Items 1–7 paths
- Plan: [2026-08-03-item8-stale-device-revision-protection.md](./plans/2026-08-03-item8-stale-device-revision-protection.md)

### Phase 1 Creative-state persistence — Item 7 (2026-08-03)

- [x] Phone writer: Harmony **Ab → G7** @ **319**; Item 2 tuple **Ab** independent; `creative_context_section_change`; strict egress confirmed
- [x] Dell stale reader: hard refresh; `session_start_kind=hard_refresh`; network @ **319**; no Dell write; **G7** + studio **creative** / mission backing context restored; `certification_passed=true`
- **Frozen:** live sign-off rev **319**; contract doc `4c3ce81`
- Plan: [2026-08-03-item7-phone-dell-cross-device-persistence.md](./plans/2026-08-03-item7-phone-dell-cross-device-persistence.md)

### Phase 1 Creative-state persistence — Item 6 (2026-08-03)

- [x] Dell writer: `creative_context_section_change` → Harmony Map **Melody A / Ab**; strict egress @ **317**; globals + Item 2 tuple preserved
- [x] Phone reader: cold reboot; network hydrate @ **317**; no phone write; full Items 1–4 + globals; `certification_passed=true`
- **Frozen:** live sign-off rev **317**; contract doc `2ec5015` (no Item 6 production delta required)
- Plan: [2026-08-03-item6-dell-phone-cross-device-persistence.md](./plans/2026-08-03-item6-dell-phone-cross-device-persistence.md)

### Phase 1 Creative-state persistence — Item 5 (2026-08-03)

- [x] Hard refresh @ rev **315**: authoritative network hydrate; `session_start_kind=hard_refresh`; no startup write / upsert
- [x] Cold reboot (Incognito + `?dev=1`): `session_start_kind=cold_reboot`; lifecycle markers + fetch precedence; full Items 1–4 + globals restore
- [x] Read-only **Item 5 certification panel** + rev-315 fixture; `classification_*` separate from `certification_passed`
- **Frozen commits:** `e36fd40`, `2156bb1`, `b989516`
- Plan: [2026-08-03-item5-refresh-cold-reboot-persistence.md](./plans/2026-08-03-item5-refresh-cold-reboot-persistence.md) | [runbook](./plans/2026-08-03-item5-live-runbook.md)

### Phase 1 Creative-state persistence — Item 4 (2026-08-03)

- [x] Harmony Map → `creative_context_section_change`; `harmony_map_*` in `creative_workspace_state`
- [x] Item 2 target tuple independent; global Cm / Piano / Beginner / Left-Hand Patterns frozen
- [x] Dev panel **Creative context snapshots (Item 4)** @ `aa77e58`; passive audit + run-scoped violations @ `d97da03` / `c72a879`
- [x] Hard refresh @ rev **315**: full restore, `startup_write_attempted=false`, `violations=[]`
- **Frozen commits:** `5edb81c`, `aa77e58`, `d97da03`, `c72a879`
- Plan: [2026-08-03-item4-key-section-creative-context-snapshots.md](./plans/2026-08-03-item4-key-section-creative-context-snapshots.md)

### Phase 1 studio page persistence — live sign-off (2026-08-02)

- [x] Backing → Creative user navigation with startup suppression armed — queued pre-aligned release (`38664fc`–`ad68e71`)
- [x] Authoritative page_change cloud save: upsert + force network refetch @ revision **193**, all page-bearing fields **creative**
- [x] Hard refresh: network hydration @ **193**, `failure_class` null, app remains on **Creative**
- [x] Durability trace retains revision ladder **191 / 192 / 193** for diagnostics (reservation analysis deferred)
- Plan: [2026-08-02-phase1-creative-state-persistence-remaining.md](./plans/2026-08-02-phase1-creative-state-persistence-remaining.md) (next checks)

### Practice Tools — responsive launcher (2026-08-01)

- [x] Grouped Practice Tools launcher + single active-tool workspace (`practice_tools_ui.py`, commit `1196089`)
- [x] `practice_active_tool` page snapshot persistence; legacy tab label migration
- [x] Metronome owned by Timing only; coach setup deduplicated from Practice setup panel
- [x] Tests: `tests/test_practice_tools_ui.py`

### Composition Studio CS-B5 — Review (2026-07-30)

- [x] `composition_review.py` — readiness checklist, harmony/melody/lyrics overviews, whole-song coach
- [x] Review phase UI: cover summary, structure timeline, full-song play, jump to any phase/section
- [x] Mark song ready + readiness gates
- [x] Tests: `tests/test_composition_review.py`

### Composition Studio CS-B4 — coach-first Lyrics (2026-07-30)

- [x] `composition_lyric_suggestions.py` — role/emotion prompts, brainstorm seeds, cross-section theme memory
- [x] Lyrics intent block on sections (`communicate`, `emotion`, `role`, `remember`)
- [x] Coach-first Lyrics phase: section strip, creative questions, brainstorm/explore/compare/write paths
- [x] Lyric editor in expander (secondary); instrumental skip → Review
- [x] Tests: `tests/test_composition_lyric_suggestions.py`

### Composition Studio CS-B3 — coach-first Melody (2026-07-29)

- [x] `composition_melody_suggestions.py` — melodic concepts by feel/style
- [x] Coach-first Melody phase: remember/feel/style, hum-first, explore/compare/write
- [x] Phrase editor in expander (secondary)
- [x] Tests: `tests/test_composition_melody_suggestions.py`

### CPL Custom Chord builder fixes (2026-07-30)

- [x] Root/Bass selectors retain values (exclude builder inputs from ephemeral widget purge)
- [x] Manual chord entry "Use chord" reads from session state
- [x] Removed duplicate manual entry outside + Custom Chord expander
- [x] Quarter-bar (¼) and half-bar (½) duration buttons alongside 1/2/4 bars
- [x] Tests: `tests/test_cpl_timing_panel.py`, `tests/test_cpl_fractional_bars.py`

### Composition Studio Sprint A — document foundation (2026-07-29)

- [x] `CompositionDocument` model + section CRUD (`composition_document.py`)
- [x] Composer page bucket + library save/load (`composition_session_state.py`)
- [x] Preview audio + musical snapshot (`composition_preview.py`, `composition_snapshot.py`)
- [x] Initial page shell (`composition_studio_page.py`) — **UI to be replaced** by six-phase guided UX
- [x] Tests: `tests/test_composition_document.py`
- [x] Architecture plan: [plans/2026-07-29-composition-studio-v1-architecture.md](./plans/2026-07-29-composition-studio-v1-architecture.md)
- [x] Next UX plan: [plans/2026-07-29-composition-studio-six-phase-songwriting.md](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)

### Flagship masterclass coaching foundation (2026-07-29)

- [x] Curated performance profiles in `song_performance_profiles.py` (6 flagships)
- [x] Unified instructor API: `song_performance_coaching.py` (opener, masterclass markdown, section lessons)
- [x] Musician-facing layer: `musician_coaching.py` — same voice on Active Song card, chart subtitle, Coach tab, Practice page, section overlays
- [x] Woven interpretation prose (musical context + technique + listening — not template bullets)
- [x] Quality standard doc: [plans/2026-07-29-flagship-coaching-quality-standard.md](./plans/2026-07-29-flagship-coaching-quality-standard.md) (**framework frozen**)
- [x] Future vision doc: [plans/2026-07-29-progress-aware-coaching-vision.md](./plans/2026-07-29-progress-aware-coaching-vision.md)
- [x] Tests: `tests/test_musician_coaching.py`, `tests/test_song_performance_coaching.py`, `tests/test_song_coaching.py`
- [x] **Phase 1 complete** — framework stable; handcrafted content standard + final review checklist

### AMI Analyze My Practice synthesis (2026-06-29)

- [x] Full practice-history AMI payload: practice logs, saved upload analyses, tone takes, export metadata
- [x] 10-section progress report (executive summary through evidence used + data safety)
- [x] Multitrack exports as context only unless saved Upload Analysis exists
- [x] No raw audio/base64/blob fields in payload; tombstones excluded
- [x] Local instant solver route + Practice Log progress report panel + `?dev=1` diagnostics
- [x] Plan: [plans/2026-06-29-ami-practice-history-synthesis.md](./plans/2026-06-29-ami-practice-history-synthesis.md)

### Tone & Tuner History (2026-06-27)

- [x] Save tone takes after Practice page sustain analysis (`tone_takes[]` media catalog)
- [x] Instrument-specific default library + All instruments view
- [x] Written/concert note context for transposing instruments
- [x] Lazy audio playback via `media/tone_takes/` + Supabase storage refs
- [x] Delete tombstones; excluded from default history and AMI
- [x] AMI payload: counts, trends, best/worst stability by instrument (metadata only)
- [x] Plan: [plans/2026-06-27-tone-tuner-history-sprint.md](./plans/2026-06-27-tone-tuner-history-sprint.md)

### Practice Log (v1 — 2026-06-27)

- [x] Quick Save with exact instrument labels (Tenor/Alto Saxophone, etc.)
- [x] Refresh + delete persistence (local + Supabase, tombstones)
- [x] Search/filter (song, instrument, focus, keys)
- [x] Practice/Concert + written/shape key display from canonical setup
- [x] Analyze My Practice → AMI / Command Center **Music Practice Log Analysis** handoff
- [x] AMI practice log answer quality (structured patterns + 30-min plan)

### Platform & navigation

- [x] Nine studio pages with `studio_page` routing (`studio_nav_history.py`, `streamlit_music_practice_app.py`)
- [x] Per-page local UI snapshots on navigate; globals (instrument, key, song) preserved (`studio_page_persistence.py`)
- [x] Back/forward page history stacks
- [x] Floating ← Back / Forward → in main content area (`studio_nav_history.py`, `app_ui.py`)
- [x] Command Center Music resume payloads + Continue / workstream deep links (`music_resume_payload.py`, `music_command_center.py`, `suite_deep_links.py`)
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

### Phase 1 Creative-state persistence — Item 1 (2026-08-02)

- [x] Creative tool/tab selectors in `creative_workspace_state` — `creative_tab_tool_persistence.py`, hydration trace, save durability trace
- [x] Live sign-off @ `549578d` — Daniel/music rev **203**, cold incognito session, selectors + globals restore, `startup_write_attempted=false`, `violations=[]`

### Mission workspace persistence & contract (2026-07-30)

- [x] Single Mission workspace per account — latest saved state wins (`improv_mission_workspace_updated_at`)
- [x] Mission keys in `_PERSIST_KEYS` + creative/backing page snapshots (`improvisation_mission_persistence.py`)
- [x] Cross-device drift via `music_mission_cloud_drift` + `apply_cloud_mission_state_if_allowed`
- [x] Practice lick transport (BPM, groove, meter, loops) synced on persist; motif is SSOT for notation/TAB/playback
- [x] Tests: `tests/test_improvisation_mission_persistence.py`
- [x] **Design contract (frozen):** [plans/2026-07-30-mission-workspace-contract.md](./plans/2026-07-30-mission-workspace-contract.md)
- [ ] Manual cross-device sign-off (pending)

### Creative Progressions

- [x] **Custom Progression Lab:** section builder, chord subdivisions, saved progressions, analysis text, exercises (`custom_progression_lab.py`, `cpl_page_ui.py`)
- [x] Custom source as global active song (`CPL_ACTIVE_KEY`)
- [x] **Creative Lab:** mode selector
- [x] **Improvisation Intelligence:** Entry & Jam, Live Coach, Phrase/Motif, Missions, Harmony Map, Deep Harmony, Metrics & AI (`improvisation_intelligence_ui.py`)
- [x] **Deep Harmonic Analyzer (2026-07-30):** one guided-lesson UI for Creative Lab + II; instrument/level/focus personalization; collapsible reference cards; section navigator; homework (`deep_harmonic_analyzer_ui.py`, `deep_harmonic_personalization.py`)
- [x] Mission Backing Jam — single-chord loop, BPM handoff preserves user tempo, instrument icons on backing card; Mission Practice panel + return to Mission
- [x] Mission relative Harder/Easier + practice handoff (`caea38c`)
- [x] Arrangement Assistant, Weakness Detection, Development Tracking (text labs)
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
- [x] Phase C canonical modules: `active_song_state`, `studio_nav_state`, `practice_state`, `backing_track_state`
- [x] `prepare_music_workspace()` + `?dev=1` persistence trace sidebar
- [x] **Manual Test A** — studio page cross-device sync (v14, 2026-06-09)
- [x] **Manual Test B** — Practice field cross-device sync (`97fad4a`, 2026-06-09)
- [x] **Manual Test C** — Backing content cross-device sync (v18 `fdf9800`, 2026-06-09): rendered-widget bind, device-compare trace, user-intent dirty gate
- [x] **Manual Test D** — Active song + display key + instrument + page + written-key + transposing subtype (v25 `f153204`, 2026-06-09): save payload trace + cloud readback, phone hard-refresh pass (Tenor + written charts ON)
- [x] **Manual Test E** — AMI return restores song/key/instrument/written-key/subtype/page + practice/backing (v26 `1b00d58`, 2026-06-09): Test E compare trace; no default song / autosave / page overwrite
- [x] Transposing save diagnostics — `save_*` canonical/payload/readback trace panel (`?dev=1`)
- [x] AMI return trace — Test E compare panel; transposing round-trip in `build_source_state` / `apply_active_song_source_state_from_ami` (v26)
- [x] Written-key + subtype cloud save path — widget → canonical merge at commit (v25)

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

- **Phase 2A Missions live recording/mix @ `227a55b`:** shipped to `origin/dev` 2026-08-04 — **pending live acceptance** (not archived here until sign-off).
- Mark new completions here and mirror a one-line summary in `music_app_roadmap.md`.
- Remove items from `music_app_tasks.md` when done.
