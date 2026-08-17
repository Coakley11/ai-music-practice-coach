# Current Tasks — AI Music Practice Coach

**Last updated:** 2026-08-16 (Practice Focus Phase 3A Practice Coach + Adaptive Weakness on `feature/practice-focus-system`; Creative/Backing parked @ `44403d4`) Master context: [music_app_roadmap.md](./music_app_roadmap.md).  
**Persistence baseline (frozen A–E):** [docs/MUSIC_PERSISTENCE_BASELINE.md](../docs/MUSIC_PERSISTENCE_BASELINE.md)

---

## Current Priorities

### P0 — Practice Focus System (active)

**Plan:** [plans/2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md)  
**Branch:** `feature/practice-focus-system` from `origin/dev` (`870a365`). **Do not merge to `dev` until approved.**  
**Parked:** `feature/creative-backing-stabilization` @ `44403d43785a0bdd29c0762f98155efd393ccb70` — do not touch or use as base.

**Goal:** Practice Focus is an app-wide coaching variable (bias, not prison): AMI, Practice, Upload, Log, Multitrack, Practice Coach/Session, Adaptive Weaknesses; Backing Focus coaching is **optional** (documented, not auto). Deeper Creative waits for the parked branch. Composition is hook-only.

- [x] Branch from clean `origin/dev` (not Creative stabilization)
- [x] Audit existing `focus` storage, widgets, persistence, lookalikes
- [x] Phase 1 foundation: `practice_focus_policy` / `practice_focus_context` / `practice_focus_snapshot` + tests
- [x] Phase 2A: AMI + Practice page consume policy/context (`practice_focus_coaching.py`); same-rerun Focus change; C-major factual guardrail
- [x] Phase 2B: Upload / AI Coach snapshot + supported metric emphasis (`practice_focus_evaluation.py`)
- [x] Phase 2C: Practice Log + weekly Practice Coach analysis (`practice_focus_history.py`)
- [x] Phase 2D: Multitrack Focus snapshot + supported ensemble emphasis (`practice_focus_multitrack.py`)
- [x] Phase 3A: Practice Coach & Session + Adaptive Weakness Detection (`practice_focus_weaknesses.py`); Creative audit + Motif Sequence spec; Backing optional documented
- [ ] Phase 3B+: optional Backing Focus card + Custom tools (later)
- [ ] Phase 4: Creative integration after parked branch is accepted (incl. Motif Sequence staff view)
- [ ] Phase 5: Composition (later)

### P0 — Mission Take → Upload Analysis durable handoff (queued)

**Plan:** [plans/2026-08-04-mission-take-upload-analysis-persistence.md](./plans/2026-08-04-mission-take-upload-analysis-persistence.md)

**Goal:** Missions **Analyze This Take** → Upload Analysis must survive refresh, reboot, and Dell ↔ phone on the same account/workspace — with dry mic as authoritative analysis source, optional mixed preview asset, full pending-analysis envelope, CAS lifecycle, and explicit clear.

- [ ] Authoritative `pending_upload_analysis` envelope (metadata in workspace; no WAV blobs in JSON)
- [ ] Dry audio → workspace-scoped object storage + fingerprint dedupe
- [ ] Optional mixed-preview asset (labeled; AI defaults to dry)
- [ ] Same-device refresh/reboot → Upload Analysis + editable pre-analysis state
- [ ] Cross-device hydrate → route to Upload Analysis when pending handoff exists
- [ ] Criteria/metrics edits persist pre-run; take-only metrics ≠ global AI Metrics
- [ ] Lifecycle: prepared → restored/editable → running → completed; **Clear prepared take**
- [ ] CAS / stale-device: newer envelope wins (consume Item 8 APIs — **do not modify frozen Item 8**)
- [ ] Tests: handoff, refresh, reboot, Dell↔phone, isolation, dedupe, stale block, clear
- [ ] `?dev=1` diagnostics: take id, asset fingerprints/refs, revision, hydrate/write results

**Commits:** isolate from speed pass and from Phase 2A UI hotfixes where practical.

### P0 — Navigation & page-load speed pass (queued)

**Plan:** [plans/2026-08-04-music-navigation-speed-pass.md](./plans/2026-08-04-music-navigation-speed-pass.md)

**Goal:** Measure and reduce real navigation latency (Creative, Missions, Backing, Upload Analysis, sidebar) — route gating, lazy Creative tabs, play-only backing generation, deferred Upload Analysis preprocessing, no navigation-only cloud writes.

- [ ] Baseline `?dev=1` route spans (wall ms, cloud R/W, audio builds, projections)
- [ ] Gate heavy work behind active `studio_page` / Creative sub-tab
- [ ] Skip unchanged artifact projection + mission context rebuild
- [ ] Backing WAV only on Play or musical signature change; cache reuse
- [ ] Upload Analysis: lazy take load; preprocess on Run AI only; no backing player
- [ ] Dedupe saves/uploads; preserve CAS fail-closed
- [ ] Before/after report on listed routes

**Commits:** separate from mission handoff persistence where practical.

### P0 — Music workspace persistence & state ownership (active)

**Investigation report:** [plans/2026-08-01-music-workspace-persistence-audit.md](./plans/2026-08-01-music-workspace-persistence-audit.md)

**Goal:** Saved workspace = applied = final UI after refresh, reboot, and Dell ↔ phone. No default song recovery; hydration gate (`fe859a3`) is prerequisite only.

**Delivery commits (in order):**

1. [x] Audit panel + mission fail-closed + capo init guard + `resolve_session_key_from_family` (`c412d7c`)
2. [x] Canonical `creative_workspace_state` save/apply + envelope (`824c961` Phase 0; `66e89b6` Phase 1)
2b. [x] **Phase 1 Creative hardening** (`971c6c4`) — global controls + page paths
3. [x] **Phase 1 studio page persistence (live)** — Backing → Creative, authoritative save/refetch @ **193**, hard refresh hydrates Creative @ **193** (`38664fc`–`ad68e71`, signed off **2026-08-02**)
4. [x] **Phase 1 Creative-state persistence (remaining)** — [plan](./plans/2026-08-02-phase1-creative-state-persistence-remaining.md) — **Items 1–8 live-accepted** (2026-08-03); **Phase 2 gate open**
   - [x] **Item 1** Creative tool/tab selectors — live @ `549578d` (rev **203**, cold session)
   - [x] **Item 2** Mission configuration — live @ `c6c2f41` (mission/target/metrics)
   - [x] **Item 3** Motif / example / practice lick + Mission Backing handoff — **live-accepted** @ `616f4e4` — [contract](./plans/2026-08-02-item3-mission-artifact-persistence.md)
   - [x] **Item 4** Key, section, Creative context snapshots — **live-accepted & frozen** @ `c72a879` (rev **315**) — [contract](./plans/2026-08-03-item4-key-section-creative-context-snapshots.md); doc freeze `cc00cda`
   - [x] **Item 5** Refresh + cold-reboot persistence — **live-accepted & frozen** @ `e36fd40`–`b989516` (rev **315**) — [contract](./plans/2026-08-03-item5-refresh-cold-reboot-persistence.md) | [runbook](./plans/2026-08-03-item5-live-runbook.md)
   - [x] **Item 6** Dell → phone cross-device — **live-accepted & frozen** (rev **317**, 2026-08-03) — [contract](./plans/2026-08-03-item6-dell-phone-cross-device-persistence.md)
   - [x] **Item 7** Phone → Dell cross-device — **live-accepted & frozen** (rev **319**, 2026-08-03) — [contract](./plans/2026-08-03-item7-phone-dell-cross-device-persistence.md)
   - [x] **Item 8** Stale-device revision protection — **live-accepted & frozen** @ **`8ef698e`** (2026-08-03; TEST A/B/C @ cloud **323→325**) — [contract](./plans/2026-08-03-item8-stale-device-revision-protection.md)
5. [ ] Key-family wiring + capo regression suite
6. [ ] Mission spec validation + structured results + 20× strict tests
7. [ ] Practice Tools — single “Metronome, Tuner & Tone” launcher + persistence
8. [ ] Cross-device workspace revision / conflict hardening
9. [ ] Integration verification matrix

### P0 — Composition Studio → `motif_engine` integration (queued)

**Goal:** Wire Composition Studio melody/motif surfaces through the unified `motif_engine` (SSOT) without duplicating notation or coaching logic in page renderers.

**Status:** Not started — Practice Tools responsive launcher (`1196089`) is **complete**; no further Practice Tools UX work in this phase.

**Plan:** Extend [2026-07-29-composition-studio-v1-architecture.md](./plans/2026-07-29-composition-studio-v1-architecture.md) / six-phase plan as implementation proceeds.

### P0 — Style Identity & Creative Engine Phase 2

**Plan:** [plans/2026-07-03-style-identity-phase-2.md](./plans/2026-07-03-style-identity-phase-2.md)

**Gate:** Phase 1 Items **1–8** are **live-accepted & frozen** on `dev` (Item 8 @ **`8ef698e`**). Phase 2 work may proceed per schedule below; do not modify frozen Item 8 CAS / revision-unification without `?dev=1` regression proof.

**Goal:** Style, mood, feel, intensity, and groove produce unmistakably different musical results for catalog, custom, and Creative Lab backing.

- [x] `style_pattern_for_recipe()` — canonical grids for Pop/Rock/Jazz/Bossa/Funk/Blues
- [x] Style-first merge in `apply_profile_to_synthesis()` (recipe owns rhythm grid)
- [x] `_feel_modifiers()` wired from `groove_feel` time_feel
- [x] Session mood/intensity merge when BackingContext lacks them
- [x] `style_locked` suppresses song-title pattern overrides
- [x] Blues/rock voicing + bass identity
- [x] Full `BackingMusicalProfile` passed to generation cache
- [x] Phase 2 acceptance tests (`tests/test_backing_musical_profile.py`)
- [ ] Live listening validation after deploy

**Acceptance:** Same progression sounds clearly different across 6 styles blind; Funk Heavy/Energetic vs Light/Dreamy obvious; Jazz Relaxed vs Energetic distinct.

### P0 — Phase 2A Mission selection + exact-chord backing (in progress — live acceptance pending)

**Plan:** [plans/2026-08-03-phase-2a-mission-exact-chord-backing.md](./plans/2026-08-03-phase-2a-mission-exact-chord-backing.md)

**Live acceptance:** Pending user sign-off on **`227a55b`** (`phase2a-live-only-mix-v3`, `improv_mission_live`, audible mixed preview + dev route markers). Do not mark Phase 2A complete until deployed checklist passes.

- [x] Authoritative `MissionPracticeContext` (type + chord + transport) persisted in mission workspace
- [x] Exact-chord backing panel (Play/Stop, tempo, loop, volume, count-in, sounding chord) on Metrics & AI + Upload Analysis
- [x] Mismatch + armed-backing guards; analysis enrichment + stale-context warning
- [x] Missions live-only recording + mixed preview hotfix @ **`227a55b`**
- [ ] **Live smoke:** route markers, no upload on Missions, Performance + Backing audible, rerun-stable mixed preview
- [ ] Live smoke: Metrics → Upload → score on sealed chord; Backing Jam handoff arms context


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

### P1 — Command Center ↔ Music integration

**Plan:** [plans/2026-07-03-command-center-music-integration.md](./plans/2026-07-03-command-center-music-integration.md)

**Design rule:** Continue cards (top) = specific resumable task restore; App Directory (bottom) = general workstream entry. Workspace isolation required.

- [x] `music_resume_payload.py` — canonical resume envelope per task type
- [x] `music_command_center.py` — Continue card builder + App Directory workstream cards
- [x] Practice + Backing continue restore (song, instrument, key, BPM, page, scope/sections)
- [x] Creative + Multitrack + tone/upload continue restore (payload fields + apply)
- [x] App Directory soft-entry URLs (`suite_entry_mode=workstream`, no stale pick_key)
- [x] Workspace isolation tests (coakley11 ≠ daniel) — `tests/test_music_command_center.py`
- [ ] Command Center homepage card UI + storage (external `daniel-ai-command-center` repo)
- [ ] Live Continue / App Directory acceptance on Streamlit Cloud

**Acceptance:** Continue Shape of You / Tenor Sax / Bm / 90 BPM opens Music with exact state; App Directory opens current workspace without blank generic state.

### P1 — Composition Studio polish (active — highest priority)

**Plan:** [plans/2026-07-29-composition-studio-six-phase-songwriting.md](./plans/2026-07-29-composition-studio-six-phase-songwriting.md)  
**Shipped:** CS-B0–B5 — full six-phase guided songwriting on `dev` (Vision → Review).

- [x] **CS-B5** — Review: cover summary, structure/harmony/melody/lyrics overviews, full-song play, readiness checklist, whole-song coach
- [x] **Structure + Melody polish** — visual timeline, tap-to-select, grouped section actions, linked-harmony playback, hear-section, melody refinements, chords-first guidance, hum-record scaffold
- [ ] **Melody Capture sprint** — hum-over-looping-chords → pitch/rhythm → editable melody ([backlog](./music_app_feature_backlog.md#song-composer--composition-studio))
- [ ] **CS-C** — OpenAI proposals per phase (after Melody Capture planning)

**Acceptance:** New user describes Composition Studio without “chord grid”; structure appears before chords; Review shows full song overview.

### P1 — Creative Experience polish (2026-07-30) — **complete**

**Plan:** [plans/2026-07-30-creative-experience-polish-sprint.md](./plans/2026-07-30-creative-experience-polish-sprint.md)

- [x] Song Catalog ↔ Custom Songs — last selection restore on toggle (`LAST_CUSTOM_STATE_KEY`, pending picker switch)
- [x] Deep Harmonic Analyzer — single UI (`deep_harmonic_analyzer_ui.py`); guided lesson; instrument/level/focus personalization; collapsible Go deeper cards; homework

### P1 — Coaching theory & educational consistency (depth-first)

**Checklist (all new coaching features):** [Flagship coaching quality standard — three pillars](./plans/2026-07-29-flagship-coaching-quality-standard.md#educational-feature-completion--three-pillars-all-coaching-surfaces)

- [x] Scale names ↔ displayed notes (`build_scale_suggestion`, natural minor intervals) — 2026-07-31
- [x] **Live Coach + Harmony Map** — chart-key spelling via `coaching_reference_key`; half-dim scale labels; Harmony Map color/stable tones key-aware; Live Coach card fallback bug — 2026-08-01 (`tests/test_harmony_map_coaching.py`)
- [x] **Creative cloud workspace** — full-page keys (tabs, motif, harmony map, DHA progress), chart-key piano keyboard — 2026-08-01 (`creative_workspace_persistence.py`, `tests/test_creative_workspace_persistence.py`)
- [ ] **Creative workspace manual sign-off** — [contract checklist](./plans/2026-07-30-mission-workspace-contract.md#official-manual-sign-off-copy-paste) (Dell ↔ phone)
- [ ] **Practice Chord Coach unification** — in progress (`practice_chord_coach.py`, `tests/test_practice_chord_coach_unification.py`)
- [x] Creative Missions → Backing — chord-by-location selection; Mission Backing Jam; user BPM preserved after handoff; instrument icons on backing card
- [x] Mission examples — level-scaled motifs; relative Harder/Easier; practice lick → Mission Backing Jam; **Mission workspace cloud persistence** ([contract](./plans/2026-07-30-mission-workspace-contract.md), `4106a86`)
- [x] Manual acceptance on Streamlit Cloud (DHA combos, mission BPM, icons) — **signed off 2026-07-30**
- [ ] **Mission persistence cross-device** — manual laptop ↔ phone sign-off per [contract](./plans/2026-07-30-mission-workspace-contract.md)

### P1 — Unified motif engine & coaching profile split

**Plan:** [plans/2026-07-31-unified-motif-engine-and-coaching-profile.md](./plans/2026-07-31-unified-motif-engine-and-coaching-profile.md)

- [x] Architecture — `motif_engine.py` facade, mission rules layer, cursor rules (theory + unified engine)
- [x] Key-signature spelling across Creative coaching displays (`8664228`)
- [ ] Route all new generation through `motif_engine.generate_musical_phrase`
- [ ] Phrase & Motif — stylistic intents (lyrical, rhythmic, bluesy, jazz vocab, continue/contrast idea)
- [ ] Composition Studio melody phase → engine + songwriting constraints (replace parallel hint-only path)
- [ ] AI Coach — analysis-first; engine only for illustrative examples post-feedback
- [ ] **Global coaching profile** — persistent skill priorities, tone, depth, long-term goals (Metrics & AI tab)
- [ ] **Upload Analysis redesign** — mission-first “today’s performance”; inherit profile; remove duplicate metric multiselect
- [ ] `merge_mission_and_profile()` in `mission_analysis.py` + tests

**Acceptance:** Metrics tab = long-term coach settings; Upload = “how did I do today?”; Girl from Ipanema upload respects rhythm-first profile while scoring today’s chord-tone mission.

- [ ] **Creative AI coach** — long-term vision ([backlog](./music_app_feature_backlog.md))

**Acceptance:** Toggle catalog/custom restores correct song; mission “Jam” opens Backing on one chord; Deep Harmonic reads like a private lesson; mission tempo editable after launch.

### P1 — Flagship coaching content (Phase 1 framework **complete**)

**Quality standard:** [plans/2026-07-29-flagship-coaching-quality-standard.md](./plans/2026-07-29-flagship-coaching-quality-standard.md)  
**Future vision (do not build yet):** [plans/2026-07-29-progress-aware-coaching-vision.md](./plans/2026-07-29-progress-aware-coaching-vision.md)

**Goal:** Handcrafted masterclass profiles — **content quality only**. Each flagship passes final quality review before it is considered complete. One song at a time; clarity and inspiration over volume.

**Architecture (frozen — do not redesign):**

- `song_performance_profiles.py` — authored content
- `song_performance_coaching.py` — lookup + woven prose API
- `musician_coaching.py` — UI surfaces + non-flagship fallbacks

**Current flagships (6):** California Dreamin', Perfect, Shallow, Hotel California, All of Me, Say

- [x] Masterclass profile schema + unified instructor voice across Active Song, Coach, Practice, overlays
- [x] Phase 1 coaching framework complete and stable (2026-07-29)
- [x] Handcrafted quality standard + final review checklist documented
- [ ] Deepen existing flagships (more instruments/levels where thin)
- [ ] Add next flagship only when it meets full quality checklist
- [ ] Each new flagship: tests in `tests/test_song_performance_coaching.py`

**Acceptance:** Coach tab reads like one private teacher; swap song title in random sentences and the copy breaks; no generic filler shared across songs.

### P1 — Backing Studio floating nav (restored)

- [x] Floating Back/Forward at mid-viewport (not in-page toolbar)
- [x] Back in sidebar/main gutter; Forward on right edge
- [x] Return to Catalog Song separate on Backing page only
- [ ] Manual acceptance: scroll, song/key/BPM changes, refresh — stable placement

### P1 — Creative → Backing Track routing

**Plan:** [plans/2026-06-29-creative-backing-track-routing.md](./plans/2026-06-29-creative-backing-track-routing.md)

**Goal:** Entry & Jam and Missions **Open Backing Track** applies full Creative settings; re-open updates; clear returns to regular song backing; active song change invalidates stale Creative context.

- [ ] `backing_context.py` — canonical session object + signature + validate/clear
- [ ] Handoff builders: Entry & Jam, Mission, Custom progression (unify CPL)
- [ ] Replace `_improv_open_backing()` scattered keys with `apply_backing_context_to_session`
- [ ] Backing page banner + **Use regular song backing** reset
- [ ] Song-change invalidation hook in `active_song_state`
- [ ] Persistence in workspace envelope; `tests/test_backing_context.py`

**Acceptance:** Create → Entry & Jam or Missions → Open Backing Track reflects Creative settings; reset and song change restore normal backing; existing regular Backing flow unchanged (Tests A–E frozen).

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
- **Progress-aware coaching** — session memory, struggle/improvement adaptation, performance-prep mode ([vision](./plans/2026-07-29-progress-aware-coaching-vision.md))
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
- [x] Flagship masterclass coaching foundation frozen (2026-07-29) — see [plan](./plans/2026-07-29-flagship-coaching-quality-standard.md)

---

## Notes

- **Practice Focus (2026-08-15):** Active on `feature/practice-focus-system`. Parked Creative/Backing @ `44403d4`. Do not merge Practice Focus to `dev` until approved. Plan: [2026-08-15-practice-focus-system.md](./plans/2026-08-15-practice-focus-system.md).
- **Phase 2A (2026-08-04):** **`227a55b`** on `origin/dev` — pending **live acceptance**; queued P0: [mission handoff persistence](./plans/2026-08-04-mission-take-upload-analysis-persistence.md) + [navigation speed pass](./plans/2026-08-04-music-navigation-speed-pass.md).
- **Phase 1 Items 1–8 (2026-08-03):** **Live-accepted & frozen** on `dev` — Item 8 @ **`8ef698e`** (CAS + revision unification; TEST A/B/C). **Phase 2 gate open.** Do not modify frozen persistence/CAS or Item 8 diagnostics without `?dev=1` proof.
- **Phase 1 page save/hydration (2026-08-02):** Accepted on live `dev` — do not regress queued startup release or authoritative page_change path. **Deferred:** align `last_cloud_fetch` vs `fresh_hydration` cache flags (diagnostics only).
- **SSOT + One Music Engine:** New musical logic belongs in canonical modules (`music_theory`, `motif_engine`, mission rules, persistence contracts)—not page files. See [2026-07-31 architecture plan](./plans/2026-07-31-unified-motif-engine-and-coaching-profile.md) and `.cursor/rules/single-source-of-truth.mdc`.
- Work on branch **`dev`** only; push `origin/dev` for Streamlit Cloud dev app. Do not push `main` unless releasing.
- **UI polish** and **nav audit/fix** = separate commits; never mix with persistence.
- When a task ships, move detail to `music_app_completed_features.md` and uncheck here.
- For large implementation plans, save the full plan body under `cursor-prompts/plans/` and link from this file.
