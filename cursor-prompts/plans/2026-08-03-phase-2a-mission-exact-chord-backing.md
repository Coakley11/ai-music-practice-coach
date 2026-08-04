# Phase 2A — Mission Selection and Exact-Chord Backing

**Last updated:** 2026-08-03

## Goal

Mission type and the exact clicked chord are the single source of truth from Missions through backing, recording/upload, AI scoring, and cloud restore.

## Deliverables

1. **`mission_practice_context.py`** — `MissionPracticeContext` envelope (mission type, parsed chord, tempo, style/groove, loop/volume/count-in, fingerprint, recording seal).
2. **`mission_exact_chord_backing.py` / `mission_exact_chord_backing_ui.py`** — Play/Stop, tempo, loop, volume, count-in, sounding-chord display on Metrics & AI and Upload Analysis capture.
3. **Guards** — Block analysis when locked mission workflow lacks synced backing; warn on stale context vs recording seal; chord mismatch detection UI vs sounding backing.
4. **Persistence** — `improv_mission_practice_context`, `improv_mission_recording_seal` in mission workspace + disk persist keys.
5. **Integration** — Mission Backing Jam handoff arms context; `enrich_analysis_context` forces single-chord `target_chords` for scoring.

## Acceptance

- Select Chorus **A** on a repeating progression → context, backing panel, and analysis all use that index/chord.
- Press **Play** on exact-chord backing → recording seal + armed state; analysis uses sealed chord.
- Change chord after seal → stale warning on analyze (analysis still allowed with warning).
- UI chord ≠ backing sounding chord → capture/analysis blocked until Play or Backing Jam sync.
- Cloud restore brings back full `improv_mission_practice_context`.

## Tests

- `tests/test_mission_practice_context_phase2a.py`

## Out of scope (2B+)

- Full multitrack mix-down with mission backing stem
- Auto-regenerate global Backing Jam WAV on every chord tile click without user Play
