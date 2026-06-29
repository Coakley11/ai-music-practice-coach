# AMI Analyze My Practice — full practice-history synthesis

**Last updated:** 2026-06-29 · **Branch:** `dev`

## Goal

Make **Analyze My Practice** produce a real progress report by combining saved practice evidence (logs, upload analyses, tone takes, export metadata) without raw audio/base64.

## Shipped

- `practice_history_synthesis.py` — payload builder, 10-section progress report, safety scan, diagnostics
- `practice_log_ami.py` — delegates to synthesis; backward-compatible keys for handoff
- `music_ami_instant_solver.py` — `practice_history_analysis` intent → local progress report markdown
- `practice_log_ui.py` — progress report panel, AMI synthesis diagnostics in `?dev=1`
- `tests/test_practice_history_synthesis.py` — 14 tests

## Payload sections

- `practice_log_summary` — entries, focus counts, time by instrument/song
- `upload_analysis_summary` — saved analysis summaries (primary playing evidence)
- `tone_history_summary` — tone take aggregates (from media catalog)
- `multitrack_export_summary` — metadata only; analyzed vs waiting for analysis
- `safety_checks` / `diagnostics` / `progress_report`

## Product rules

- Multitrack exports are **not** playing-quality evidence unless a saved Upload Analysis exists
- No raw audio, base64, or blob fields in AMI payload
- Deleted/tombstoned catalog rows excluded via existing `media_state` normalizers

## Follow-up

- AMI solver in Applied Math repo: consume new payload sections in Command Center answer
- Optional: link practice log entries to upload/tone/export IDs at save time
