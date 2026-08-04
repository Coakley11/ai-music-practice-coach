# Opus audit: Creative & Backing workflow state architecture

**Last updated:** 2026-08-04  
**Baseline commits (do not regress):** `114567e` (perf gates), `0d980b6` / `a90f14d` (workflow envelope + nav)  
**Verdict:** The app **cannot yet guarantee** one visible page = one consistent musical workflow. Multiple co-equal authorities, partial envelope adoption, and unordered hydrate/restore paths explain observed hybrid states.

---

## Phase 1 — Architectural audit

### 1. State authorities (inventory)

| Authority | Primary keys / modules | Owns |
|-----------|------------------------|------|
| **Global practice key** | `display_key`, `concert_key`, `_pending_display_key`, `practice_key`, `songs/key_state.py`, `session_widget_safe.py` | Sidebar + many renderers |
| **Authoritative practice key (partial)** | `musical_context_authority.AuthoritativePracticeKey`, `resolve_authoritative_practice_key` | Tonic+mode label; not wired everywhere |
| **Fixed practice key mode** | `practice_key_mode.py`, `fixed_practice_key_family_id` | Song catalog key family |
| **Generated jam key** | `generated_jam_key_context.py`, `_generated_jam_key_owner_active` | D major / major sidebar during generator/style jam |
| **Workflow musical snapshots** | `workflow_musical_authority.WORKFLOW_MUSICAL_STATES_KEY`, `ACTIVE_WORKFLOW_OWNER_KEY` | Per-workflow blobs (song/style/generator/mission_jam partial) |
| **Active musical workflow envelope** | `active_musical_workflow_envelope.py` | Mission-centric validation/reconcile; **4 call sites** |
| **Backing workflow envelope** | `backing_workflow_context.BACKING_WORKFLOW_ENVELOPE_KEY` | Backing handoff metadata; built from `BackingContext` |
| **Backing context** | `backing_context.BACKING_CONTEXT_KEY`, `build_*_context` | Progression, style, keys for backing page |
| **Mission practice context** | `improv_mission_practice_context`, `mission_practice_context.py` | Mission type, chord parse, seal, fingerprint |
| **Mission config canonical** | `creative_mission_config_persistence`, CWS Item 2 | `ii_selected_*`, mission pick |
| **Mission artifacts canonical** | `creative_mission_artifact_persistence`, CWS Item 3 | Example, motif, lick |
| **Mission workflow guard (partial)** | `mission_workflow_context.py` | Blocks generated sections on Missions tab only |
| **Creative session** | `creative_session_state.py` | tool_type, entry_mode parallel to widgets |
| **Creative workspace state** | `creative_workspace_state_persistence.py` | Cloud canonical merge + **startup projection** |
| **Page snapshots** | `studio_page_persistence.py` | Per-page session slices on nav |
| **Active song / catalog** | `active_song_state.py`, `songs/music_source.py` | Pick key, sections, metadata, style hints |
| **Backing session route** | `backing_session_route.py` | backing_session_type, song_source_type |
| **Studio nav / page** | `studio_page`, `studio_nav_state.py` | Active page |
| **Pending upload analysis** | `mission_pending_upload_*`, `pending_upload_route_precedence.py` | Route lock, envelope, audio refs |
| **Analysis session** | `analysis_session_persistence.py` | Last result, restore once (perf gate) |
| **Performance route gates** | `music_route_gates.py` | Skip hydrate/catalog; **no musical consistency** |
| **Spelling** | `harmonic_spelling.py`, `mission_pitch_spelling.py` | Chord vs song reference key |

**Structural issue:** There is **no single active-workflow pointer** consumed by all renderers. `ACTIVE_WORKFLOW_OWNER_KEY` and envelopes can disagree with live `display_key`, `improv_entry_mode`, `backing_context.source`, and canonical projections in the same rerun.

---

### 2. Direct-read bypasses (fresh repo scan)

**Envelope usage (production):** `build_active_workflow_envelope` / `reconcile_mission_workflow_envelope` appear only in:
- `improvisation_intelligence_ui.py` (Missions tab entry)
- `backing_source_navigation.py` (return to mission detail)
- `active_musical_workflow_envelope.py` (self)

**High-risk bypass clusters** (read legacy globals without envelope or owner check):

| Area | Files / patterns | Risk |
|------|------------------|------|
| **Backing build** | `backing_context.py` (`_display_keys_from_session`, `build_entry_jam_context`, `build_song_improv_context`, `open_backing_from_creative`) | Generator/style/song/mission contexts mixed; catalog snapshot on every open |
| **Backing render** | `streamlit_music_practice_app.py` (backing page), `backing_context_ui.py`, `backing_musical_state.py` | Multiple key lines; partial major_jam fix |
| **Creative lab** | `improvisation_intelligence_ui.py` (most tabs), `improvisation_missions.py` `load_mission_example` | Example load without owner fingerprint gate at load time |
| **Canonical projection** | `creative_mission_artifact_persistence.project_*`, `creative_mission_config_persistence.project_*`, `creative_workspace_state_persistence` startup | Stale Ab example restored while UI shows B |
| **Section maps** | `resolve_improv_sections`, `improv_generated_sections`, `home_sections`, `improv_song_concert_sections` | Entry jam sections on Missions |
| **Style** | `improv_style_meta`, `improv_style`, `improv_jam_style`, `mission_song_backing_style.py` | Jewish ballad on Bossa generator |
| **Sidebar key** | `songs/key_state.py`, `creative_key_sync.py`, `practice_key_state.py` | Major list while song is minor |
| **Notation** | `improvisation_missions.refresh_mission_example`, `rebuild_mission_outputs`, ABC paths | B → Eb/Gb if reference key wrong |
| **Handoff** | `mission_analysis_ui`, `mission_pending_upload_persistence` | Seal chord vs selected chord |
| **Nav** | `backing_source_navigation.restore_session_widgets_from_backing_context`, `merge_live_practice_into_creative_session` | Overwrites widgets after envelope reconcile |
| **Cloud** | `music_persistent_state.apply_music_disk_state`, `suite_user_persistence` hydrate | Full blob apply before workflow owner reconstructed |

**Scale:** `display_key` / `concert_key` direct reads appear in **80+ production modules**; envelope in **~4**. `SOURCE_SCAN_BYPASS_PATHS` in `active_musical_workflow_envelope.py` is necessary but **not sufficient**.

---

### 3. Transition ordering (trace summary)

| Transition | Current order (simplified) | Failure mode |
|------------|----------------------------|--------------|
| Generator → Missions | Tab render → `switch_workflow_owner(mission_jam)` → reconcile envelope | Jam keys/style remain in session if switch skipped (other entry paths); `improv_style_meta` not cleared |
| Missions → Generator | Entry mode radio → partial snapshot | Song sections still in `home_sections`; mission example in session |
| Missions → Mission Backing | `open_backing_from_creative(mission)` → catalog snapshot → build_mission_context → activate/generated hooks | Catalog style refresh; wrong concert if major_jam stale |
| Backing → Mission | Nav → `prepare_return_to_mission_detail` OR lick button (deduped) | `merge_live_practice` may overwrite key; canonical re-project |
| Style Jam → Backing | `build_entry_jam_context` + `resolve_entry_jam_entry_mode` | Wrong entry if widget/session disagree → Generator backing |
| Song-Based → Backing | `build_song_improv_context` | Full progression vs single-chord if mission fields leak |
| Mission take → Upload Analysis | `persist_mission_pending_upload_handoff` + route lock | Session-only lock lost if cloud route not in saved envelope |
| Browser refresh | `prepare_music_workspace` → `apply_music_disk_state` → page snapshot hydrate → artifact projection | **Pending upload route vs studio_page** race; mission artifacts before workflow owner |
| Cross-device | Cloud CAS hydrate | Stale device blocked (good) but **older mission example** can still apply if canonical newer |

**Two owners active:** Possible when `backing_context.source=entry_jam` while `improv_intelligence_tab=Missions`, or `generated_jam_owns_practice_key` true during Missions render before reconcile runs.

---

### 4. Hydrate / restore precedence (startup & rerun)

Typical Streamlit rerun (not fully ordered in one function):

1. Suite/cloud fetch → `apply_music_disk_state` / workspace envelope  
2. `prepare_music_workspace` / active song restore  
3. `studio_page` resolution (`resolve_studio_page_for_restore`, **pending upload precedence**)  
4. Page enter: `ensure_page_initialized`, `restore_page_snapshot`  
5. Creative: `ensure_creative_improv_initialized`, widget hydrates  
6. **Canonical projection:** `project_mission_config_from_canonical_before_widgets`, `project_mission_artifacts_from_canonical`  
7. Route perf gates (`114567e`): skip catalog restore / analysis restore  
8. Tab render: envelope reconcile (**only on Missions tab today**)  
9. Backing: `reconcile_backing_context`, musical state resolver  

**Conflicts:**
- Step 6 can restore **Ab example** after step 8 cleared it (next rerun).  
- Page snapshot (4) can reintroduce stale `improv_entry_mode` / `display_key` without workflow owner.  
- Item 8 diagnostics and Phase 1 CAS paths must remain untouched; new ordering should wrap, not replace, CAS apply.

---

### 5. Cache / fingerprint correctness

| Cache | Identity includes | Gap |
|-------|-------------------|-----|
| Mission artifact projection FP | Canonical artifact keys | Not chord/section/mission owner in skip check alone |
| Mission example session FP | Output fingerprint | Bypassed on canonical project |
| Backing WAV/timeline (`114567e`) | `_last_backing_signature` | Must include workflow_type + mission chord (partial) |
| `should_skip_mission_artifact_projection` | Canonical FP | Wrong chord can still match if canonical stale |
| Page snapshot dedupe | Page snapshot hash | No workflow owner in hash |
| Creative workspace canonical FP | Noise-stripped workspace | May treat mission+generator as same if keys align |
| Pending upload dry audio | Audio fingerprint | OK; route lock separate issue |

**Performance rule:** Caches must include **`workflow_owner` + `context_revision` + song/generated session id** or hits can serve another workflow’s artifacts/audio.

---

## Phase 2 — Proposed final architecture

### A. `MusicWorkflowStateStore` (durable, scoped)

One store keyed by workflow id:

- `song_based_improvisation/{pick_key}`  
- `mission_jam/{pick_key}` (mission chord index + mission type in blob)  
- `style_jam/{style_session_id}`  
- `jam_session_generator/{jam_id}`  
- `regular_catalog_backing/{pick_key}`  
- `regular_custom_backing/{cpl_id}`  
- `pending_upload_analysis/{take_id}`  

Each blob: practice key object, section map, style/groove/bpm/meter, route/return destinations, mission artifact refs (not inline stale example in session), spelling preference.

**Migrate from:** flat `WORKFLOW_MUSICAL_STATES_KEY` + scattered session keys; keep compatibility read for one release.

### B. Single active pointer

`session["_music_active_workflow"] = { owner, session_id, source_type, context_revision }`  

**Rule:** All renderers call `require_active_workflow(session)` → envelope or fail-closed reconcile. No render-only reads of `display_key` for musical decisions.

### C. Atomic activation API

`activate_workflow(session, target, *, reason)`:

1. Save outgoing blob to store  
2. Deactivate generated jam / mission transient keys  
3. Restore incoming blob  
4. Set active pointer + revision  
5. Invalidate dependent caches (backing audio, artifact projection, notation)  
6. Optional durable save (respect CAS + pending upload lock)  

Replace ad-hoc `switch_workflow_owner` + manual pops.

### D. Practice key object (first-class)

```python
@dataclass
class PracticeKeyAuthority:
    original_tonic: str
    original_mode: str
    practice_tonic: str
    practice_mode: str
    written_tonic: str
    written_mode: str
    owner: str  # workflow id
    source: str
```

Sidebar mode = `practice_mode` from **active workflow**, not `is_creative_major_jam_active` alone.

### E. Owner-bound content

Mission example, backing handoff, recording seal, notation input share:

`{ workspace, workflow_owner, session_id, song_id, section, chord_index, chord_symbol, mission_type, artifact_fp }`

Load example only if fingerprint matches active mission context.

### F. Fail-closed render gate

`assert_render_consistent(session, surface)` before:

- Missions UI  
- Mission backing card  
- Mission lick panel  
- Upload Analysis mission banner  

On violation: reconcile once; if still bad → user message + dev panel (no hybrid).

Unified dev panel: merge `active_musical_workflow_envelope` + `backing_workflow_envelope` + `pending_upload_route` + perf counters + **legacy_bypasses_this_run**.

### G. Upload Analysis ownership

Extend existing `pending_upload_route_precedence` + `mission_pending_upload_persistence`:

- Route lock **only** cleared on explicit user nav (already partially implemented)  
- Hydrate **before** studio_page default and **before** mission artifact projection  
- Cross-device: require `music_workspace_state.pending_upload_route` + envelope in cloud payload (tests exist; live refresh still failing → implement stage 8)

---

## Phase 3 — Implementation order (isolated commits)

1. **Audit artifacts:** `music_workflow_state.py` + active pointer + dev panel shell (no behavior change)  
2. **Bypass registry:** runtime counter when legacy keys read on gated surfaces  
3. **Atomic `activate_workflow`**; wire tab/entry/backing handoffs  
4. **PracticeKeyAuthority**; sidebar + progression transpose single path  
5. **Mission alignment:** example load, backing build, seal, notation from one MPC+owner  
6. **Generated isolation:** clear `improv_style_meta`/sections on activate; style owner in build_entry_jam  
7. **Backing consolidation:** single nav registry (extend `0d980b6`); context build from active workflow only  
8. **Upload Analysis refresh/device** (without touching Phase 1 CAS item internals)  
9. **Legacy deprecation:** redirect `display_key` musical reads through authority in top 20 files  
10. **Cache identity:** extend fingerprints; perf gates unchanged (`114567e`)  
11. **Regression test:** full Hevenu sequence (user scenario 1–20)  
12. **Opus adversarial review** on `dev`

---

## Required regression scenario (automation target)

Implement as `tests/test_hevenu_workflow_contamination_e2e.py` (session-level, no Streamlit):

Steps 1–20 from user brief + independent workflow smoke + nav dedupe assertions.

---

## Adversarial review checklist (post-implementation)

| Question | Current (pre-Phase 3) |
|----------|------------------------|
| Two workflow owners active? | **Yes** — possible |
| Renderer bypass envelope? | **Yes** — most paths |
| Stale hydrate overwrite? | **Yes** — canonical/snapshot order |
| Cache cross-workflow? | **Possible** — incomplete identity |
| Mission chord ≠ example ≠ backing? | **Yes** — observed live |
| Key label ≠ progression? | **Yes** — transpose not always coupled |
| Upload Analysis refresh? | **Open** — partial infra |
| Duplicate nav buttons? | **Mostly fixed** `0d980b6`; verify after refactors |

---

## Constraints preserved

- Phase 1 Items 1–8 CAS: no changes to CAS merge semantics in this plan; new layer wraps after apply.  
- Item 8 diagnostics: untouched.  
- `114567e` perf gates: remain; add workflow id to cache keys only.  
- `0d980b6` envelope: evolve into unified model, do not delete without migration.

---

## Commit 1 shipped (2026-08-04)

- Modules: `music_workflow_state_store.py`, `music_workflow_compatibility.py`, `music_workflow_dev_panel.py`, `music_workflow_canonical_persistence.py`
- Session keys: `_music_workflow_state_store`, `_music_active_workflow`
- Dev panel wired once per run after quick nav (`?dev=1` only)
- Tests: `tests/test_music_workflow_state_store.py` (13 cases)
- **Behavior-neutral:** no renderer migration; legacy keys unchanged; canonical gather only on explicit `music_workflow_state_save` reason (not wired to autosave yet)
