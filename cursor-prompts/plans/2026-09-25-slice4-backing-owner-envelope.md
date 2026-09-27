# Slice 4 — Backing owner envelope field map

Last updated: 2026-09-25

Canonical owners (post-handoff, no aliases stored):

| Owner | Legacy `BackingContext.source` | Return |
|-------|--------------------------------|--------|
| `catalog` | `regular_song` | catalog / Songs |
| `sbi_custom` | `song_improv` or `custom_progression` | SBI Custom / Creative / Custom page |
| `entry_jam` | `entry_jam` | Jam / Creative |
| `mission` | `mission` | Mission |
| `composition` | `composition_song` | Composition |

Compatibility aliases normalized **once** at handoff (`normalize_backing_owner`):
`regular_song`→catalog, `custom_progression`/`custom`→sbi_custom, `song_improv`+Custom→sbi_custom, `song_improv`+Active→catalog (Creative return preserved via legacy handoff), `style_jam`/`jam_generator`→entry_jam, `composition_song`→composition.

## Envelope fields (`_backing_owner_envelope`)

`source`, `identity`, `title`, `original_key`, `practice_key`, `sounding_key`, `written_key`, `shape_key`, `capo`, `instrument`, `progression`, `progression_label`, `style`, `tempo`, `meter`, `return_destination`, `entry_mode`, `epoch`

Semantic separation (Slice 3): Original ≠ Practice/Concert ≠ Sounding ≠ Written ≠ Shape.

## Per-source launch map

### Catalog

| Field | Source |
|-------|--------|
| Launch | `rebuild_catalog_backing_from_canonical_pick` / `activate_catalog_ownership` / `open_backing_for_practice_source` |
| Handoff | envelope + `_backing_explicit_handoff_source=regular_song` |
| Identity | catalog `pick_key` (e.g. Perfect) |
| Original | catalog song key |
| Practice | `practice_key_by_source[pick]` |
| Sounding | Practice |
| Written/Shape | instrument / capo derivation |
| Progression | catalog sections transposed to Practice |
| Return | catalog |
| Post-launch guesses removed | LAST_CUSTOM, Jam session, Mission handoff, Composition UUID |

### SBI Custom

| Field | Source |
|-------|--------|
| Launch | `open_backing_from_creative(song_improv)` with Custom preview; `restore_custom_song_backing` |
| Handoff | envelope `sbi_custom`; legacy `song_improv` / `custom_progression` |
| Identity | `custom::` pick / Trial Song |
| Original | Custom `original_key_center` |
| Practice | sticky custom Practice |
| Return | sbi_custom |
| Guesses removed | Perfect Global Active, Catalog G/C |

### Jam / Entry

| Field | Source |
|-------|--------|
| Launch | `open_backing_from_creative(entry_jam)` / `activate_entry_jam_ownership` |
| Handoff | envelope `entry_jam` |
| Identity | generated jam session id / sealed artifact |
| Keys | jam key / style / tempo sealed at launch |
| Return | entry_jam |
| Guesses removed | Trial SBI, Perfect, Mission, stale Jewish Ballad unless current |

### Mission

| Field | Source |
|-------|--------|
| Launch | `stamp_mission_backing_handoff` → `open_backing_from_creative(mission)` |
| Handoff | Mission envelope + Slice 3 HANDOFF_* keys |
| Original / Practice / Sounding / Written | sealed distinctly (e.g. D / F / F / G Bb Clarinet) |
| Return | mission |
| Guesses removed | display_key-as-Practice, SBI/Jam reclaim |

### Composition

| Field | Source |
|-------|--------|
| Launch | `open_backing_for_practice_source` composition path / `build_composition_song_context` |
| Handoff | envelope `composition` |
| Identity | `composition::` UUID |
| Original / Practice | per-UUID composition keys |
| Return | composition |
| Guesses removed | Catalog Global Active G reclaim |

## Post-launch guess sites addressed

1. `open_backing_for_practice_source` — blocks reclaim when envelope owner is specialized.
2. `resolve_backing_pk_control_owner` — envelope first.
3. `build_backing_nav_actions` — return buttons from envelope owner.
4. `on_sidebar_practice_concert_key_change` — `update_envelope_musical_state` only (no owner flip).
5. Refresh — `_backing_owner_envelope` in `music_persistent_state` persist list.
6. Catalog restores — `rebuild_catalog_backing_from_canonical_pick` + `restore_regular_song_backing` stamp envelope.

## Residual guess sites (audited; not fully eliminated)

From field audits ([Slice 4 launch audit](4180aea3-7ea8-46f6-9da2-1d15c75be314), [Audit Backing launch paths](e9042f34-64c9-4565-bca3-fa65b1c7e845)):

| Site | Risk |
|------|------|
| `open_backing_for_creative_source` default → `activate_entry_jam_ownership` | Unresolved Creative still falls through to Jam |
| `_display_keys_from_session` / `_live_backing_concert_keys` | Generic key coupling if envelope missing |
| `build_song_improv_context` LAST_CUSTOM install | Only when envelope not yet stamped |
| Composition written/shape | Still derived at apply; not sealed as separate envelope fields on every path |
| `hydrate_backing_source_for_page` reconcile | Preserve-PK hydrate may consult Global Active when envelope cleared |

Envelope-first paths above make these dormant while a sealed visit is live. Clear envelope only on explicit leave / new owner launch.

## Audit cross-check

Launch chains confirmed:
- Creative → stamp handoff → `open_backing_from_creative` / `activate_*` → `build_*` → envelope stamp
- Songs/Practice → `open_backing_for_practice_source` → catalog/custom/composition → envelope stamp
- Mission → `stamp_mission_backing_handoff` (envelope early) → Creative open (envelope refresh)

## Module

`backing_owner_envelope.py` — stamp / get / update / normalize / coherent_tuple.

Checkpoint: `a9e52a0` (+ follow-up restore_regular stamp if present).
