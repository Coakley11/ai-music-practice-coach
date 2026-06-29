"""Practice Analysis panel — compact tab, hydration, and open-after-analyze behavior."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from practice_history_synthesis import (
    LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY,
    LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY,
    LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY,
    LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY,
    hydrate_latest_practice_analysis,
    store_latest_practice_analysis,
)
from practice_log_analysis_panel import (
    PRACTICE_ANALYSIS_OPEN_KEY,
    _compact_header,
    render_practice_analysis_panel,
)


class _FakeExpander:
    def __init__(self, label, expanded):
        self.label = label
        self.expanded = expanded

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeSt:
    def __init__(self) -> None:
        self.expanders: list[tuple[str, bool]] = []

    def expander(self, label, *, expanded=False, key=None):
        self.expanders.append((str(label), expanded))
        return _FakeExpander(label, expanded)

    def markdown(self, *_args, **_kwargs) -> None:
        pass

    def caption(self, *_args, **_kwargs) -> None:
        pass

    def info(self, *_args, **_kwargs) -> None:
        pass

    def warning(self, *_args, **_kwargs) -> None:
        pass

    def container(self, *, border=False):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestPracticeLogAnalysisPanel(unittest.TestCase):
    def _rich_payload(self) -> dict:
        return {
            "practice_log_summary": {
                "entry_count_total": 2,
                "window_days": 14,
                "practice_time_by_instrument": {"Tenor Saxophone": 60},
                "focus_area_counts": {"pitch": 2},
            },
            "upload_analysis_summary": {"analysis_count_total": 1},
            "tone_history_summary": {"tone_take_count_total": 1},
            "multitrack_export_summary": {"export_count_total": 0},
            "progress_report": {
                "executive_summary": "You logged 2 sessions.",
                "improvements": ["Timing improved."],
                "upload_analysis_findings": ["Say upload shows steady groove."],
                "tone_tuner_findings": ["Long tones need cleaner center pitch."],
                "recommended_next_practice_plan": ["5 min long tones."],
                "needs_work": ["Pitch on Say."],
                "evidence_used": "Evidence used: **2** practice logs.",
            },
        }

    def test_hydrate_rebuilds_summary_from_full_report(self) -> None:
        session: dict = {
            LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY: {
                "executive_summary": "You logged 2 sessions.",
                "improvements": ["Timing improved on Say."],
                "upload_analysis_findings": ["Say upload shows steady groove."],
                "tone_tuner_findings": ["F#/Gb long tones need cleaner center pitch."],
                "recommended_next_practice_plan": ["5 min long tones on Tenor Saxophone."],
                "needs_work": ["Pitch/intonation on Say."],
                "evidence_used": "Evidence used: **2** practice logs, **1** upload analyses.",
            },
            LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY: {
                "practice_logs": 2,
                "upload_analyses": 1,
                "tone_takes": 0,
                "multitrack_exports": 0,
                "analyzed_exports": 0,
            },
        }
        self.assertTrue(hydrate_latest_practice_analysis(session))
        summary = session.get(LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY)
        self.assertIsInstance(summary, dict)
        self.assertTrue(str(summary.get("practice_summary") or "").strip())

    def test_hydrate_from_storage_loads_disk_keys(self) -> None:
        session: dict = {}
        disk_payload = {
            "session": {
                LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY: {
                    "executive_summary": "Saved from disk.",
                    "improvements": ["Keep logging."],
                },
                LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY: {"practice_logs": 1},
            }
        }
        with patch("suite_user_persistence.load_user_state", return_value=(disk_payload, None)):
            from practice_history_synthesis import hydrate_latest_practice_analysis_from_storage

            self.assertTrue(hydrate_latest_practice_analysis_from_storage(session))
        self.assertIn(LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY, session)

    def test_panel_closed_by_default_on_refresh(self) -> None:
        session: dict = {}
        store_latest_practice_analysis(session, self._rich_payload())
        session[PRACTICE_ANALYSIS_OPEN_KEY] = False
        st = _FakeSt()
        render_practice_analysis_panel(st, session)
        self.assertEqual(len(st.expanders), 1)
        label, expanded = st.expanders[0]
        self.assertIn("Practice Analysis", label)
        self.assertFalse(expanded)

    def test_panel_opens_after_analyze(self) -> None:
        session: dict = {PRACTICE_ANALYSIS_OPEN_KEY: True}
        store_latest_practice_analysis(session, self._rich_payload())
        session[LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY] = "2026-06-29T13:35:00+00:00"
        st = _FakeSt()
        with patch(
            "suite_analytical_question.format_practice_analysis_updated_label",
            return_value="Jun 29, 2026, 9:35 AM ET",
        ):
            render_practice_analysis_panel(st, session)
        self.assertTrue(st.expanders[0][1])

    def test_compact_header_rejects_top_song_label(self) -> None:
        from practice_log_analysis_panel import _compact_header

        session = {
            LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY: {"top_song": "Top song"},
            LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY: "2026-06-29T15:58:00+00:00",
        }
        summary = {"practice_summary": "You worked mostly on **Tenor Saxophone**."}
        with patch(
            "suite_analytical_question.format_practice_analysis_updated_label",
            return_value="Jun 29, 2026, 11:58 AM ET",
        ):
            header = _compact_header(session, summary)
        self.assertNotIn("Top song", header)
        self.assertIn("Last updated", header)
        session = {
            LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY: {
                "top_song": "Say",
                "top_instrument": "Tenor Saxophone",
            },
            LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY: "2026-06-29T15:58:00+00:00",
        }
        summary = {
            "practice_summary": "You worked mostly on **Tenor Saxophone** with focus on pitch.",
            "upload_recording_review": "**Say** (Single recording): Strongest area — timing.",
        }
        with patch(
            "suite_analytical_question.format_practice_analysis_updated_label",
            return_value="Jun 29, 2026, 11:58 AM ET",
        ):
            header = _compact_header(session, summary)
        self.assertIn("Practice Analysis", header)
        self.assertIn("Say", header)
        self.assertNotIn("Top song", header)
        self.assertIn("Tenor Saxophone", header)

    def test_panel_always_visible_with_empty_state(self) -> None:
        st = _FakeSt()
        render_practice_analysis_panel(st, {})
        self.assertEqual(len(st.expanders), 1)
        self.assertEqual(st.expanders[0][0], "Practice Analysis")
        self.assertFalse(st.expanders[0][1])

    def test_log_page_wiring_renders_panel_in_app_not_ui_module(self) -> None:
        from pathlib import Path

        ui_source = (Path(__file__).resolve().parents[1] / "practice_log_ui.py").read_text(encoding="utf-8")
        app_source = (
            Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("render_practice_analysis_panel(st, session_state)", ui_source)
        self.assertIn("log_practice_analysis_panel", app_source)


class TestPracticeAnalysisPersistKeys(unittest.TestCase):
    def test_latest_analysis_keys_in_persist_keys(self) -> None:
        from music_persistent_state import _PERSIST_KEYS

        for key in (
            "latest_practice_analysis_summary",
            "latest_practice_analysis_created_at",
            "latest_practice_analysis_evidence_counts",
            "latest_practice_analysis_full_report",
            "latest_practice_analysis_handoff_status",
        ):
            self.assertIn(key, _PERSIST_KEYS)


if __name__ == "__main__":
    unittest.main()
