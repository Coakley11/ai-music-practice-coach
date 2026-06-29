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
from practice_log_analysis_panel import PRACTICE_ANALYSIS_OPEN_KEY, render_practice_analysis_panel


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

    def expander(self, label, *, expanded=False):
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

    def test_empty_state_when_no_saved_analysis(self) -> None:
        st = _FakeSt()
        render_practice_analysis_panel(st, {})
        self.assertFalse(st.expanders[0][1])
        self.assertEqual(st.expanders[0][0], "Practice Analysis")


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
