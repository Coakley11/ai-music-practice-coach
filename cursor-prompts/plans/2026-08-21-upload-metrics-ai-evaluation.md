# Upload + Metrics & AI evaluation context

**Branch:** `feature/upload-metrics-ai-evaluation`  
**Base:** `origin/dev` @ `d759dc6`  
**Date:** 2026-08-21

## Goal

Keep existing Upload core performance analysis (scores, radar, deep dive, tips, audio features). Add a durable **recording analysis-context snapshot** so the AI Coach is context-aware: workflow, recording type, instruments, song source, Evaluating Criteria, Practice Focus, mission, multitrack role.

## SSOT

- `recording_analysis_context.py` — snapshot schema, build/apply/persist, mission defaults, coach emphasis notes
- `upload_analysis_setup_ui.py` — Workflow → Recording Type (gated) → instruments → song source
- `upload_analysis_modes.py` — workflow labels + type options helper

## Behavior

1. Workflow first (Single vs Multitrack) gates Recording Type options.
2. Setup collects instruments, song source type/id/name, Practice Focus (read from active), Evaluating Criteria (existing Metrics & AI).
3. Mission handoff auto-sets Single + Solo Performance + song/instrument/mission.
4. `analyze_recording` keeps baseline scores; categories / summary / practice plan gain context emphasis.
5. Snapshot persists on result + media catalog + upload history compact keys.
6. Historical reload restores snapshot into Upload setup (ownership rule).
7. **Change criteria** navigates to Creative → Metrics & AI.
8. **Open Upload Analysis** uses `open_upload_analysis_from_metrics` and preserves prepared recording.

# Correct behavior notes (2026-08-21 follow-up)
# - Ordinary Upload must keep Workflow/Recording Type editable.
# - Mission Recording is an explicit Single Recording type.
# - Auto-prefill only for genuine Creative Mission handoff (`_mission_upload_analysis_handoff`).
# - Ambient analysis_sync_creative_mission / active mission must not lock Upload.
