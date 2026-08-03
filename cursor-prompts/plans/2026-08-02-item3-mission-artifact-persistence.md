# Item 3 — Mission artifact persistence contract

**Last updated:** 2026-08-02  
**Status:** Implemented on `dev` (Phase 1 Item 3)  
**Owner:** `creative_workspace_state` via `creative_mission_artifact_persistence.py`

---

## Canonical fields (`creative_workspace_state`)

| Key | Artifact |
|-----|----------|
| `improv_motif` | Phrase & Motif motif object (notes, rhythm, display, chord, …) |
| `improv_motif_output_mode` | `none` / `notation` / `tab` |
| `improv_motif_abc` | Cached ABC (rebuild allowed from motif on restore) |
| `improv_motif_tab` | Cached guitar TAB |
| `improv_mission_example` | Full generated mission example blob (motif SSOT inside) |
| `improv_mission_variant` | Example variant (`normal` / `easier` / `harder` / `new`) |
| `improv_mission_new_nonce` | New-idea generation counter |
| `improv_mission_practice_lick` | Mission Backing Jam handoff payload |

## Absent vs cleared

| State | Meaning |
|-------|---------|
| Key **absent** from CWS | Never saved; UI may show local-only defaults (no cloud write) |
| Key **present** with `[]` / `{}` / empty outputs | Explicit user/system cleared state — authoritative |
| Partial motif with `notes` | Saved selection — must restore exactly |

Mission config changes (Item 2) may **pop** session example keys; canonical example removal is explicit via `clear_mission_example_from_canonical` (future Item 2/3 boundary — not auto on pick today).

## User actions → save reason

| Action | `save_reason` | Interaction (representative) |
|--------|---------------|------------------------------|
| Generate / New / Harder / Easier motif | `creative_motif_change` | `motif_generate_chord`, `motif_new`, … |
| Motif transform / notation / TAB | `creative_motif_change` | `motif_transform_*`, `motif_notation_output` |
| Motif chord tile (Phrase tab) | `creative_motif_change` | `motif_chord_tile_select` |
| Generate / Easier / Harder / New idea example | `creative_mission_example_change` | `mission_example_generate_*` |
| Open Mission Backing with practice lick | `creative_mission_practice_lick_change` | `store_practice_lick_for_backing` |

Each user action: **one** cloud save transaction; gather skips stale session fields on user save reasons; same-run passive autosync suppressed (shared `_creative_mission_user_save_this_run`).

## Restore / projection

On cloud restore + `prepare_creative_workspace_state`:

1. `project_mission_artifacts_from_canonical(overwrite=True)`
2. `snapshot_hydrated_mission_artifacts`
3. Phrase & Motif tab re-projects at render when selector hydration complete
4. `hydrate_creative_workspace_after_restore` may rebuild ABC/TAB from motif when outputs missing

**Forbidden on restore:** new random motif/example phrase for the same saved blob.

## Passive startup protection

- `note_passive_mission_artifact_persist` compares canonical vs hydrated snapshot on autosave
- Violation: `CREATIVE_MISSION_ARTIFACT_PASSIVE_STARTUP_WRITE`
- `startup_write_attempted` remains tied to passive flag only (Item 2 pattern)

## Frozen (do not modify in Item 3)

Item 1 selectors, Item 2 mission config, Studio page pipeline, backing, strict egress / revision / Supabase confirmation.

---

## Live acceptance (Item 3)

Same account, Streamlit Cloud `dev`, `?dev=1`:

1. **Phrase & Motif** — generate motif → hard refresh → same motif display/notes.
2. **Missions** — Generate example → refresh → same example motif/variant (not regen).
3. **Mission Backing** — store practice lick → Backing page → refresh → same lick payload.
4. Dev: `violations=[]`, `startup_write_attempted=false` after user saves; artifact canonical = hydrated = session.
5. Cold incognito — artifacts restore with mission/target/metrics from Items 1–2 unchanged.
