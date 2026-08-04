# Music app route performance baseline (dev)

Under `?dev=1`, route wall times accumulate in session:

- `_music_dev_route_baselines` — last run per route (wall_ms, spans, counters)
- `_music_dev_route_history` — rolling samples for p50/p95

## Priority route IDs

| Route ID | User action |
|----------|-------------|
| `studio.creative` | Creative page render |
| `creative.improv_intelligence` | Improvisation Intelligence lab |
| `studio.backing` | Backing Studio page |
| `studio.analysis` | Upload Analysis page |

Tab-level spans appear in DEV perf captions on Missions (`_tab_missions`).

## Before/after workflow

1. Deploy build with `?dev=1`.
2. Run each priority route 5–10 times; note p50/p95 from DEV route caption.
3. Compare `prev_wall_ms` delta on consecutive runs (repeat hydrated page).

Counters (`_music_dev_perf_counters`): `page_snapshot_save_skipped`, `missions_artifact_project_skipped`, `inactive_heavy:*`.

Seed file: capture manually from deployed session export if needed; runtime session is authoritative.

Last updated: 2026-08-04
