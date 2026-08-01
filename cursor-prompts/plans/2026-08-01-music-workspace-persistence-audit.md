# Music workspace persistence & state-ownership audit

**Last updated:** 2026-08-01  
**Branch:** `dev` only  
**Baseline:** Hydration gate shipped (`fe859a3`) — restore must not finalize until `workspace_blob_hydrated` or `workspace_empty_confirmed`.

---

## Executive summary

Hydration ordering was one blocker; the remaining user-visible failures are **post-hydration overwrites**, **split ownership** (widgets vs canonical blobs), **incomplete save envelopes**, and **cross-device dirty/skip paths** that prevent cloud from winning. Chart/key resolver behavior is largely correct once identity exists; do not patch the resolver for empty identity.

---

## 1. Investigation findings (8 questions)

### 1. Fields absent from the saved envelope

| Domain | Gap |
|--------|-----|
| **Practice Tools** | `practice_active_tool`, metronome/tuner/tone widget settings are **not** in `_PERSIST_KEYS` or `practice_state` canonical blob. Only `studio_page_persistence` **page snapshot** (`practice` → `practice_active_tool`) — lost if save runs off-Practice or snapshot not flushed. |
| **Creative (unified)** | No single `creative_workspace_state` object. ~40 keys scattered across `_PERSIST_KEYS`, `CREATIVE_WORKSPACE_KEYS`, and page snapshots (`creative`, `backing`). |
| **Practice Tools (combined UI)** | No `practice_workspace_state` / `selected_time_pitch_mode` — requested consolidation not implemented. |
| **Workspace revision** | No monotonic `workspace_revision` in envelope; reliance on cloud `updated_at` + session `_suite_applied_cloud_ts` — stale tabs can still race. |
| **Overwrite trace** | No persisted `field_name: saved → applied → final` trail (dev-only target). |

### 2. Fields saved but not restored (or restore skipped)

| Field / domain | Mechanism |
|----------------|-----------|
| **Creative mission/motif** | Keys exist in `_PERSIST_KEYS` and restore via `session_extra` loop in `apply_music_disk_state`. **Separate** path `apply_cloud_creative_state_if_allowed` may no-op when `is_mission_workspace_locally_dirty`. |
| **Practice filters** | `apply_cloud_practice_state_if_allowed` skips when `is_practice_locally_dirty` — second device can keep stale local slice. |
| **Active song / transposing** | `apply_cloud_active_song_state_if_allowed` skips when `is_active_song_locally_dirty`. |
| **Studio nav** | `apply_cloud_studio_nav_state_if_allowed` skips on `_suite_page_user_nav` or local dirty. |
| **Capo** | Saved in `_PERSIST_KEYS` + `active_song_state`; apply can be **deferred** via `TRANSPOSING_WIDGET_SESSION_KEYS` then `finalize_transposing_receive_restore` — if capo not in active_song meta, only flat session keys apply. |

### 3. Fields restored then overwritten (primary reboot/refresh bugs)

| Field | Overwrite stage | Code locus |
|-------|-----------------|------------|
| **studio_page** | Default `"practice"` when blob page empty; `ensure_studio_page` / `handle_studio_page_transition` after restore; `_suite_page_user_nav` preserving wrong pre-restore page | `studio_nav_state.resolve_studio_page_for_restore` → default `practice`; early nav before hydrate |
| **pick_key / song** | `run_post_nav_music_startup_init` → `ensure_master_song_initialized` when `music_should_skip_master_song_init` false | `music_persistent_state.run_post_nav_music_startup_init` |
| **guitar capo shape / enabled** | `build_capo_context` → `init_capo_session_state` → `sync_capo_from_practice_display_key` runs while `CAPO_ENABLED_KEY` still false → shape set to concert key or **G default** | `guitar_capo.py` |
| **practice_key_mode / family** | Non-authoritative apply **skips** incoming fixed family when local widget already set (`practice_key_mode`, `fixed_practice_key*` continue guards) | `apply_music_disk_state` ~2245–2273 |
| **practice_focus_section** | `prepare_practice_page` merges live widget over canonical when mismatch | `practice_state.prepare_practice_page` |
| **practice_active_tool** | `studio_page_state` / page init `setdefault("practice_active_tool", "")` before snapshot hydrate | `studio_page_state.py`, `ensure_page_initialized` |
| **Creative tabs/mode** | Widget keys re-seeded from Streamlit defaults on rerun before `restore_page_snapshot` | page snapshot order vs sidebar render |

### 4. Why navigation returns to Practice

1. `resolve_studio_page_for_restore`: if `blob_page` empty → **`return "practice", "default"`** even when user had a saved page in snapshots only (not promoted to core/envelope).
2. `apply_saved_music_context(..., apply_studio_page=False)` — page depends on later blob merge; race if downstream clears blob.
3. Post-restore **`handle_studio_page_transition`** / **`ensure_studio_page`** run **after** workspace block; may normalize to practice.
4. Incomplete hydrate (pre-`fe859a3`) finalized restore with empty envelope → inspector showed no page.

### 5. Why Creative workspace does not persist

1. **Save gating:** `sync_creative_workspace_before_persist` only when `_session_has_creative_workspace` (current page creative/backing **or** keys already in session) — edits made elsewhere may not sync into envelope.
2. **Dirty flags:** local dirty blocks cloud apply on reload (`apply_cloud_creative_state_if_allowed`).
3. **Dual storage:** mission keys in session flat keys + `creative_session` blob — apply order may leave one stale.
4. **Page snapshots** for creative not always flushed before `build_music_disk_state` unless `flush_current_page_snapshot` runs on correct page.

### 6. Why capo/shape falls back to G

1. **`init_capo_session_state(concert_key)`** on every chart build resets sounding/shape when capo disabled.
2. **`default_shape_key_for_sounding`** prefers **G** (lowest fret heuristic).
3. Restore order: chart path runs **before** capo rehydrate from `active_song_state` → enabled=false → shape ← concert (often **G** after family/song defaults).

### 7. Why phone and Dell diverge

1. **Per-device local dirty** (`MISSION_LOCAL_DIRTY`, practice/active_song/studio_nav dirty) suppresses cloud apply.
2. **`workspace already synced`** skip without re-apply on new session (hydration failed path) — device stuck with empty session but cloud has data.
3. **Autosave cooldown** after restore blocks save on one device while other advances cloud.
4. **No workspace_revision** compare on save — last writer wins on `updated_at` only; no conflict UI.
5. **Account/workspace ID** — must verify same Supabase user + app id (`music`); diagnostics needed in dev panel.

### 8. Why mission constraints are violated

1. **`generate_mission_phrase_validated`**: after `max_attempts`, returns **`last` failed candidate** (lines 127–128) — UI treats as success.
2. Some code paths call **`generate_mission_phrase`** without validation.
3. **`validate_mission_motif`** is single-chord; mid-motif chord changes not fully modeled in validator.
4. No structured **`mission_valid` / invalid_note_indices** surfaced to UI.

---

## 2. Required architecture (target)

### Source of truth map

| Domain | Canonical module / key | Widget projection |
|--------|------------------------|-------------------|
| Navigation | `studio_nav_state` + `music_workspace_state.studio_page` | `studio_page` |
| Active song | `active_song_state` + `core.pick_key` | picker / session overlays |
| Musician context | `active_song_state` + instrument keys | sidebar |
| Key family / session key | **new** `session_key_state` + `practice_key_mode` | practice panel widgets |
| Guitar capo | `active_song_state` capo fields + session capo keys | capo UI |
| Creative | **`creative_workspace_state`** (new) | Creative tabs/widgets |
| Mission / motif | nested under creative workspace | improv UI |
| Practice tools | **`practice_workspace_state`** (new) | `practice_tools_ui` |

### Startup order (enforce)

1. Account + workspace ID  
2. Cloud fetch + disk fallback  
3. Schema migration  
4. **`apply_music_disk_state` (authoritative)**  
5. Canonical module apply (active song, nav, practice, creative, capo)  
6. **Initialize missing only** (no default song)  
7. **`resolve_session_key_from_family` + derived musical reconcile**  
8. Widget projection from canonical  
9. Render saved page  
10. Enable autosave when `can_finalize_music_restore` + field audit pass  

### Save order (enforce)

User action → update canonical → validate → bump revision → single envelope → confirm; never autosave widget defaults pre-hydrate.

---

## 3. Delivery commits (focused)

| # | Commit theme | Scope |
|---|--------------|--------|
| 1 | **Audit + diagnostics** | `music_workspace_persistence_audit.py`, `?dev=1` panel, mission validator fail-closed |
| 2 | **Canonical save/apply** | `creative_workspace_state`, `practice_workspace_state`, envelope + apply before widgets |
| 3 | **Navigation + Creative restore order** | page snapshot flush, post-hydrate widget projection, block default song |
| 4 | **Key family + capo** | `resolve_session_key_from_family`, capo init guard, regression tests |
| 5 | **Mission spec + validation** | structured result, per-note harmony, 20× strict mission tests |
| 6 | **Practice Tools UI** | single “Metronome, Tuner & Tone” card + persistence |
| 7 | **Cross-device revision** | monotonic revision, conflict skip diagnostics, stale overwrite guard |
| 8 | **Integration matrix** | refresh/reboot/cross-device manual checklist + automated where feasible |

---

## 4. Verification matrix (manual + automated)

See user message § Verification matrix — not complete until Dell ↔ phone passes with dev audit showing **saved = applied = final** for all tracked fields.

---

## 5. Related files

- `music_persistent_state.py` — `_PERSIST_KEYS`, `build_music_disk_state`, `apply_music_disk_state`
- `creative_workspace_persistence.py`, `improvisation_mission_persistence.py`
- `practice_state.py`, `practice_tools_ui.py`
- `studio_nav_state.py`, `studio_page_persistence.py`
- `guitar_capo.py`, `practice_key_mode.py`
- `motif_engine.py`, `improvisation_mission_specs.py`
- `suite_user_persistence.py` — sync/save/conflict
