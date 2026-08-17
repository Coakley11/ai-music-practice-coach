"""Phase 2C: Practice Log + Practice Coach historical Practice Focus."""

from __future__ import annotations

import copy
import unittest
from datetime import date

from practice_focus_history import (
    FOCUS_SOURCE_COARSE,
    FOCUS_SOURCE_EXACT,
    FOCUS_SOURCE_MISSING,
    aggregate_practice_focus_history,
    compact_focus_fields_for_ami,
    compact_practice_focus_coach_block,
    exact_practice_focus_from_entry,
    filter_entries_for_period,
    log_entry_focus_caption,
    preserve_historical_focus_on_update,
    resolve_entry_historical_focus,
)
from practice_history_synthesis import (
    build_practice_log_ami_summary,
    build_practice_progress_report,
    format_progress_report_markdown,
)
from practice_log_state import (
    build_practice_log_prefill,
    migrate_practice_log_entry,
)
from practice_setup_globals import set_active_focus


def _entry(
    *,
    sid: str,
    instrument: str,
    focus: str = "",
    focus_area: str = "",
    minutes: int | None = 20,
    day: str = "2026-08-10",
    notes: str = "",
    hard: str = "",
) -> dict:
    row: dict = {
        "session_id": sid,
        "date": day,
        "instrument": instrument,
        "instrument_family": instrument,
        "notes": notes,
        "what_was_hard": hard,
        "active_song": "Test Song",
    }
    if minutes is not None:
        row["duration_minutes"] = minutes
        row["minutes"] = minutes
    if focus:
        row["focus"] = focus
        row["practice_focus"] = focus
    if focus_area:
        row["focus_area"] = focus_area
    return migrate_practice_log_entry(row)


class TestPhase2CImmutability(unittest.TestCase):
    def test_tone_log_survives_articulation_change(self) -> None:
        session = {"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"}
        prefill = build_practice_log_prefill(session)
        entry = migrate_practice_log_entry({**prefill, "session_id": "t1", "duration_minutes": 20})
        frozen = copy.deepcopy(entry)
        set_active_focus(session, "Articulation", source="test")
        self.assertEqual(session["focus"], "Articulation")
        self.assertEqual(frozen["focus"], "Tone")
        self.assertEqual(frozen["practice_focus_snapshot"]["practice_focus"], "Tone")
        self.assertIn("Tone", log_entry_focus_caption(frozen))
        self.assertNotIn("Articulation", log_entry_focus_caption(frozen))

    def test_same_rerun_new_entry_uses_new_focus(self) -> None:
        session = {"instrument": "Saxophone", "focus": "Tone", "level": "Intermediate"}
        set_active_focus(session, "Phrasing", source="test")
        prefill = build_practice_log_prefill(session)
        self.assertEqual(prefill["focus"], "Phrasing")
        self.assertEqual(prefill["practice_focus_snapshot"]["practice_focus"], "Phrasing")


class TestPhase2CAggregation(unittest.TestCase):
    def test_mixed_focus_week_counts_and_minutes(self) -> None:
        rows = [
            _entry(sid="a", instrument="Saxophone", focus="Tone", minutes=20, day="2026-08-10"),
            _entry(sid="b", instrument="Saxophone", focus="Tone", minutes=30, day="2026-08-12"),
            _entry(sid="c", instrument="Saxophone", focus="Timing", minutes=15, day="2026-08-13"),
            _entry(sid="d", instrument="Saxophone", focus="Phrasing", minutes=20, day="2026-08-14"),
        ]
        hist = aggregate_practice_focus_history(rows, current_focus="Articulation")
        self.assertEqual(hist["exact_focus_session_counts"]["Tone"], 2)
        self.assertEqual(hist["exact_focus_recorded_minutes"]["Tone"], 50)
        self.assertEqual(hist["exact_focus_session_counts"]["Timing"], 1)
        self.assertEqual(hist["exact_focus_session_counts"]["Phrasing"], 1)
        self.assertEqual(hist["dominant_exact_focus"], "Tone")
        self.assertTrue(hist["current_differs_from_historical"])

    def test_multiple_instruments_pairings(self) -> None:
        rows = [
            _entry(sid="a", instrument="Saxophone", focus="Tone", minutes=20),
            _entry(sid="b", instrument="Guitar", focus="Strumming", minutes=25),
        ]
        hist = aggregate_practice_focus_history(rows)
        pairs = hist["instrument_focus_session_counts"]
        self.assertIn("Saxophone · Tone", pairs)
        self.assertIn("Guitar · Strumming", pairs)

    def test_missing_historical_focus_not_invented(self) -> None:
        old = migrate_practice_log_entry(
            {"session_id": "old", "instrument": "Saxophone", "notes": "legacy", "duration_minutes": 15}
        )
        self.assertEqual(exact_practice_focus_from_entry(old), "")
        info = resolve_entry_historical_focus(old)
        self.assertEqual(info["source"], FOCUS_SOURCE_MISSING)
        self.assertIn("Not recorded", log_entry_focus_caption(old))
        hist = aggregate_practice_focus_history(
            [old],
            current_focus="Articulation",
        )
        self.assertEqual(hist["sessions_missing_exact_focus"], 1)
        self.assertEqual(hist["exact_focus_session_counts"], {})
        self.assertNotIn("Articulation", hist["exact_focus_session_counts"])

    def test_coarse_only_old_row(self) -> None:
        row = migrate_practice_log_entry(
            {
                "session_id": "coarse",
                "instrument": "Guitar",
                "focus_area": "timing/rhythm",
                "duration_minutes": 20,
                "notes": "old coarse",
            }
        )
        # Ensure no exact focus invented from coarse
        row.pop("focus", None)
        row.pop("practice_focus", None)
        row.pop("practice_focus_snapshot", None)
        info = resolve_entry_historical_focus(row)
        self.assertEqual(info["source"], FOCUS_SOURCE_COARSE)
        self.assertEqual(info["focus_area"], "timing/rhythm")
        self.assertEqual(info["exact_focus"], "")
        self.assertIn("timing/rhythm", log_entry_focus_caption(row))
        self.assertNotIn("Strumming", log_entry_focus_caption(row))

    def test_missing_duration_not_fabricated(self) -> None:
        rows = [
            _entry(sid="a", instrument="Saxophone", focus="Tone", minutes=20),
            _entry(sid="b", instrument="Saxophone", focus="Tone", minutes=0, day="2026-08-11"),
        ]
        # Force a zero-duration entry past migrate defaults for the second row
        rows[1]["duration_minutes"] = 0
        rows[1]["minutes"] = 0
        hist = aggregate_practice_focus_history(rows)
        self.assertEqual(hist["exact_focus_session_counts"]["Tone"], 2)
        self.assertEqual(hist["exact_focus_recorded_minutes"]["Tone"], 20)
        self.assertEqual(hist["sessions_missing_duration"], 1)
        self.assertEqual(hist["recorded_minutes_total"], 20)

    def test_period_filtering_separates_weeks(self) -> None:
        rows = [
            _entry(sid="w1a", instrument="Saxophone", focus="Tone", minutes=20, day="2026-08-03"),
            _entry(sid="w1b", instrument="Saxophone", focus="Tone", minutes=20, day="2026-08-04"),
            _entry(sid="w2a", instrument="Saxophone", focus="Articulation", minutes=20, day="2026-08-10"),
            _entry(sid="w2b", instrument="Saxophone", focus="Articulation", minutes=20, day="2026-08-11"),
        ]
        week1 = aggregate_practice_focus_history(
            rows, start_date="2026-08-03", end_date="2026-08-09"
        )
        week2 = aggregate_practice_focus_history(
            rows, start_date="2026-08-10", end_date="2026-08-16"
        )
        both = aggregate_practice_focus_history(
            rows, start_date="2026-08-03", end_date="2026-08-16"
        )
        self.assertEqual(week1["dominant_exact_focus"], "Tone")
        self.assertEqual(week2["dominant_exact_focus"], "Articulation")
        self.assertEqual(both["exact_focus_session_counts"]["Tone"], 2)
        self.assertEqual(both["exact_focus_session_counts"]["Articulation"], 2)
        self.assertEqual(len(filter_entries_for_period(rows, start_date="2026-08-03", end_date="2026-08-09")), 2)


class TestPhase2CCoachAndMapping(unittest.TestCase):
    def test_current_vs_historical_in_report(self) -> None:
        rows = [
            _entry(
                sid="a",
                instrument="Saxophone",
                focus="Tone",
                minutes=20,
                notes="upper register thinner",
                hard="high notes thin",
            ),
            _entry(sid="b", instrument="Saxophone", focus="Tone", minutes=30, notes="attacks cleaner"),
        ]
        summary = build_practice_log_ami_summary(
            rows,
            window_days=0,
            current_focus="Articulation",
            current_instrument="Saxophone",
        )
        payload = {
            "practice_log_summary": summary,
            "practice_focus_history": summary.get("practice_focus_history"),
            "practice_focus_history_block": compact_practice_focus_coach_block(
                summary.get("practice_focus_history") or {}
            ),
            "current_practice_focus": "Articulation",
            "upload_analysis_summary": {},
            "tone_history_summary": {},
            "multitrack_export_summary": {},
            "safety_checks": {},
        }
        report = build_practice_progress_report(payload)
        activity = " ".join(report.get("practice_activity") or [])
        self.assertIn("Tone", activity)
        self.assertIn("Articulation", activity)
        md = format_progress_report_markdown(report)
        self.assertIn("Historical Practice Focus", md)
        self.assertIn("Tone", md)
        self.assertIn("Articulation", md)
        # Must not reinterpret history as Articulation-only
        hist = summary["practice_focus_history"]
        self.assertEqual(hist["dominant_exact_focus"], "Tone")
        self.assertEqual(hist["current_practice_focus"], "Articulation")

    def test_strumming_exact_and_coarse(self) -> None:
        session = {"instrument": "Guitar", "focus": "Strumming", "level": "Beginner"}
        prefill = build_practice_log_prefill(session)
        self.assertEqual(prefill["focus"], "Strumming")
        self.assertEqual(prefill["focus_area"], "timing/rhythm")
        self.assertEqual(prefill["practice_focus_snapshot"]["practice_focus"], "Strumming")
        entry = migrate_practice_log_entry({**prefill, "session_id": "g1"})
        self.assertEqual(exact_practice_focus_from_entry(entry), "Strumming")
        self.assertEqual(resolve_entry_historical_focus(entry)["source"], FOCUS_SOURCE_EXACT)

    def test_unknown_custom_focus(self) -> None:
        session = {"instrument": "Guitar", "focus": "Qwertyxyz Custom", "level": "Beginner"}
        prefill = build_practice_log_prefill(session)
        self.assertEqual(prefill["focus"], "Qwertyxyz Custom")
        self.assertEqual(
            prefill["practice_focus_snapshot"]["practice_focus"],
            "Qwertyxyz Custom",
        )
        entry = migrate_practice_log_entry({**prefill, "session_id": "u1", "duration_minutes": 15})
        hist = aggregate_practice_focus_history([entry])
        self.assertEqual(hist["exact_focus_session_counts"].get("Qwertyxyz Custom"), 1)
        block = compact_practice_focus_coach_block(hist)
        self.assertIn("Qwertyxyz Custom", block)

    def test_edit_without_focus_change_preserves_snapshot(self) -> None:
        existing = _entry(sid="edit1", instrument="Saxophone", focus="Tone", minutes=20)
        updates = preserve_historical_focus_on_update(
            existing,
            {"notes": "edited notes only", "focus_area": "tone"},
        )
        self.assertEqual(updates["focus"], "Tone")
        self.assertEqual(updates["practice_focus_snapshot"]["practice_focus"], "Tone")
        # Simulate in-memory update path without cloud persistence
        merged = migrate_practice_log_entry({**existing, **updates, "session_id": "edit1"})
        self.assertEqual(merged["focus"], "Tone")
        self.assertEqual(merged["notes"], "edited notes only")

    def test_compact_keeps_exact_focus_separate_from_area(self) -> None:
        entry = _entry(sid="c1", instrument="Guitar", focus="Strumming", minutes=20)
        compact = compact_focus_fields_for_ami(entry)
        self.assertEqual(compact.get("practice_focus"), "Strumming")
        self.assertEqual(compact.get("focus_source"), FOCUS_SOURCE_EXACT)
        self.assertEqual(compact.get("focus_area"), "timing/rhythm")


if __name__ == "__main__":
    unittest.main()
