# Phase 1 Item 4 — Key, section, and Creative context snapshots

**Last updated:** 2026-08-03  
**Status:** **LIVE-ACCEPTED — FROZEN** on Streamlit Cloud `dev` (rev **315** sign-off)  
**Acceptance commits:** `5edb81c` (persistence), `aa77e58` (dev panel), `d97da03` (passive audit), `c72a879` (panel fields)  
**Frozen prerequisites (commits through `616f4e4`):** Items 1–3 live-accepted; global Display-key pipeline; startup display-key queue; Mission Backing handoff; strict egress / revision / Supabase confirmation architecture.

**Do not redesign** Item 4 behavior, save reasons, ownership table, passive hydration protections, or run-scoped diagnostics without `?dev=1` regression proof and explicit unfreeze.

---

## Purpose

Persist enough **Creative working context** to reopen Creative tools with the same meaningful state, without creating competing global SSOTs. Generated artifacts keep **historical** context from creation time; **current** context may change independently.

---

## Field audit (current codebase)

| Field / concept | Owner | Classification | Written | Hydrated | Passive write risk |
|-----------------|-------|------------------|---------|----------|-------------------|
| `display_key` (global) | `active_song_state` + session bar | Global canonical | `mark_display_key_changed`, `flush_global_control_edits` | Cloud/disk restore, sidebar | **Frozen** explicit save only |
| `concert_key` / `practice_concert_key` | Practice globals | Global canonical | Practice helpers | Restore | Medium if Creative hydrates |
| `instrument`, `level`, `focus` | `active_song_state` / session | Global canonical | Sidebar globals | Restore | Blocked from Creative projection |
| Song identity (`pick_key`, `selected_song`) | `active_song_state` | Active-song canonical | Song pick / catalog | Restore | Low |
| `improv_intelligence_tab`, `improv_entry_mode`, lab modes | `creative_workspace_state` | Item 1 selector canonical | User tab/tool handlers | `project_creative_selectors_from_canonical` | Suppressed post-restore |
| `improv_mission_pick`, progression, chord options | `creative_workspace_state` | Item 2 mission config | Mission pick/metrics handlers | `project_mission_config_from_canonical` | Suppressed |
| `ii_selected_section`, `ii_selected_chord_index`, `ii_selected_chord`, `ii_selected_chord_label` | `creative_workspace_state` | Item 2 target tuple (atomic) | `handle_user_mission_target_selection` → `creative_mission_target_change` | Mission config projection | Suppressed unless user |
| `improv_ai_metric_ids`, `analysis_criteria_locked` | `creative_workspace_state` | Item 2 metrics | `creative_mission_metrics_change` | Mission config projection | Suppressed |
| `improv_motif`, example, practice lick blobs | `creative_workspace_state` | Item 3 artifacts (+ embedded `key_center` / `display_key` at creation) | Artifact save reasons | Artifact projection | Suppressed |
| `harmony_map_section`, `harmony_map_chord` | `creative_workspace_state` | **Item 4 current context** | Harmony Map chord buttons | Page snapshot + CWS gather | Was dirty-only; now explicit save |
| `creative_session` blob | `creative_workspace_state` | **Item 4 tool/session context** (derived/historical key fields inside blob) | `sync_creative_session_from_session` before persist | `hydrate_creative_session_for_page` | Must not overwrite global key when sidebar authoritative |
| `improv_generated_sections`, `improv_style_meta`, `improv_jam_session` | `creative_workspace_state` | Item 4 jam/style context | Jam/style generators | Creative workspace apply | Render sync only |
| `deep_harmony_lesson_step`, DHA section idx | `creative_workspace_state` | Item 4 analyzer context | User step navigation | Selector/CWS hydrate | Passive suppressed |
| `_improv_mission_section_map` | Session (render) | Derived render | Mission UI build | Rebuilt from progression | Not cloud canonical |
| Mission example `display_key` / lick `key_center` | Inside artifact blob | **Historical artifact snapshot** | At generation (`store_mission_practice_lick_for_backing`, example build) | Artifact projection | Must not back-propagate to global |
| Backing subview / page | `studio_nav_state` + handoff | Item 3 navigation | Mission Backing handoff | Page restore | Separate from Item 4 |

---

## Authoritative owners (must not fork)

| Domain | SSOT |
|--------|------|
| Instrument, Level, Focus, global Display key | Global session + `active_song_state` |
| Song identity & song-scoped chart data | `active_song_state` |
| Creative tab/tool selectors | Item 1 canonical fields in `creative_workspace_state` |
| Mission pick, target tuple, metrics | Item 2 fields in `creative_workspace_state` |
| Motif / example / practice lick | Item 3 fields in `creative_workspace_state` |
| Harmony Map selection, jam/style blobs, `creative_session` workflow | Item 4 fields in `creative_workspace_state` (no duplicate tuple) |

---

## Canonical Item 4 snapshot fields

Reused keys (no duplicates):

- `harmony_map_section`, `harmony_map_chord`
- `creative_session` (tool_type, entry_mode, sections, mission_id, intelligence_tab; key fields are **historical** copies only)
- `improv_generated_sections`, `improv_style_meta`, `improv_jam_session`
- `deep_harmony_lesson_step`, `improv_deep_harmony_dha_section_idx`

Mission **target tuple** remains the four flat Item 2 keys — Item 4 diagnostics reference them but do not duplicate storage.

---

## Current context vs historical artifact

| Concept | Storage | Mutability |
|---------|---------|------------|
| Current Harmony Map focus | `harmony_map_*` in CWS | User changes → one explicit save |
| Current mission target tuple | Item 2 flat keys | User chord tile → `creative_mission_target_change` |
| Current tool/session workflow | `creative_session` | Updated on persist capture; hydrate must not clobber globals |
| Key at artifact creation | `key_center` / `display_key` inside example & lick blobs | **Immutable** after save; refresh may rebuild notation from motif only |

---

## Save reasons

| Reason | When |
|--------|------|
| `creative_mission_target_change` | User mission chord tile (Item 2 — tuple) |
| `creative_context_section_change` | User Harmony Map chord pick (Item 4) |
| `creative_context_snapshot_change` | Explicit full context snapshot commit (reserved; envelope guard) |

All use: `force_save_music_state` → strict egress → revision reserve → upsert → authoritative confirmation (existing architecture).

Passive `autosave` / restore / render / startup: **no** Item 4 cloud write.

---

## Hydration precedence (restore)

1. Global controls from global SSOT (never from Creative snapshot alone).
2. Active-song canonical identity/data.
3. Item 1 selectors → widgets (one-shot after restore flag).
4. Item 2 mission config + target tuple.
5. Item 3 artifacts.
6. Item 4 context (`harmony_map_*`, `creative_session`, jam/style blobs).
7. UI projection only — no cloud write.

If `user_sidebar_display_key_authoritative` or canonical mission target exists, **`creative_session` hydrate must not overwrite** global display key or target tuple.

---

## Absent vs empty

| Case | Behavior |
|------|----------|
| Key absent from cloud envelope | Do not write empty selector/context fields over hydrated values (existing merge rules). |
| Key present but empty string | Treat as empty; do not gather from session on passive persist. |
| Artifact missing `key_center` | Derive display from motif refresh only; do not change global key. |

---

## Strict egress

Item 4 save reasons are user-force reasons (same class as Items 1–3): no duplicate skip when cloud differs; monotonic revision; confirmation required before dirty clear.

---

## Diagnostics (`?dev=1`)

Block: `creative_context_snapshot` in phase-1 dev panel via `collect_creative_context_snapshot_diagnostics`.

Shows: user interaction, save reason, target tuple (read from canonical), harmony map pair, `creative_session.tool_type`, artifact `key_center` vs global display key, owners, revision, cloud flags, envelope field presence checklist, `startup_write_attempted`, violations.

---

## Violations

| Code | Meaning |
|------|---------|
| `CREATIVE_CONTEXT_PASSIVE_STARTUP_WRITE` | Item 4 field gathered on passive/startup path |
| `CREATIVE_CONTEXT_SNAPSHOT_MUTATED_GLOBAL_KEY` | Hydrate/persist changed global display/practice key from snapshot |
| `CREATIVE_CONTEXT_PARTIAL_SECTION_TUPLE` | Fewer than four target identity keys on user section save |
| `CREATIVE_CONTEXT_MUTATED_ARTIFACT_CONTEXT` | Persist tried to change artifact `key_center` / creation context |
| `CREATIVE_CONTEXT_ARTIFACT_OVERWROTE_GLOBAL` | Artifact restore changed global Instrument/Level/Focus/Display key |
| `CREATIVE_CONTEXT_ENVELOPE_FIELD_DROPPED` | Save payload missing accepted Item 1–3 field present before write |
| `CREATIVE_CONTEXT_CLOUD_CONFIRMATION_MISMATCH` | Confirmation failed (wrapper around existing save tx) |

---

## Acceptance tests (automated)

1. User mission target selection → full tuple + one save (Item 2 test suite — regression).
2. User Harmony Map pick → `creative_context_section_change`, canonical harmony fields, envelope preserved.
3. Global Cm + artifact `key_center=Cm` → no global mutation, no passive save.
4. Artifact created under context A; current context B → artifact blob unchanged.
5. Artifact hydrate does not overwrite global Instrument/Level/Focus/Display key.
6. Item 4 commit retains Item 1–3 keys in blob.
7. Empty/absent merge rules (unit).
8. Startup hydration no write (`startup_write_attempted=false`).
9. Strict egress / revision tests unchanged (regression suite).

---

## Live acceptance (Item 4 focused)

After deploy, on Streamlit Cloud `dev`, `?dev=1`, Daniel workspace:

1. Open Creative → Missions; confirm global **Cm** and mission example/lick from Item 3 still present.
2. Change **Harmony Map** chord (Deep Harmonic / Harmony Map tab if available) or note mission chord tile still uses Item 2 path.
3. Dev panel: `creative_context_snapshot` shows save reason, harmony pair, global key before=after **Cm**, `violations=[]`, envelope checklist all present.
4. Hard refresh: harmony selection + mission tuple + Cm + artifacts restore.
5. `startup_write_attempted=false` on cold load.

---

## Code map

- `creative_context_snapshot_persistence.py` — Item 4 save/gather/guard/diagnostics
- `creative_session_state.py` — hydrate guards (global key + mission tuple)
- `improvisation_intelligence_ui.py` — Harmony Map user handler
- `creative_workspace_state_persistence.py` — gather gate
- `music_egress_config.py`, `music_workspace_cloud_save.py` — save reasons
- `music_phase1_dev_diagnostics.py` — dev block
- `tests/test_creative_context_snapshot_persistence.py`
