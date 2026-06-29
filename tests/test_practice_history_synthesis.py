"""Analyze My Practice — full practice-history synthesis tests."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from practice_history_synthesis import (
    ami_payload_diagnostics,
    ami_payload_safety_checks,
    build_log_page_analysis_summary,
    build_multitrack_export_context_summary,
    build_practice_history_ami_payload,
    build_practice_progress_report,
    build_upload_analysis_ami_summary,
    compact_practice_log_for_ami,
    compact_upload_analysis_for_ami,
    format_progress_report_markdown,
    scan_ami_payload_for_forbidden_data,
    store_latest_practice_analysis,
)
from practice_log_state import migrate_practice_log_entry


def _sample_log() -> dict:
    return migrate_practice_log_entry(
        {
            "session_id": "log-1",
            "date": "2026-06-28",
            "instrument": "Tenor Saxophone",
            "active_song": "Say",
            "duration_minutes": 25,
            "focus_area": "tone and timing",
            "notes": "worked on long tones and entrance timing",
            "ratings": {"tone": 4, "focus": 3},
            "updated_at": "2026-06-28T18:00:00+00:00",
        }
    )


def _sample_upload(*, export_id: str = "", source: str = "manual_upload") -> dict:
    row = {
        "recording_id": "rec-1",
        "created_at": "2026-06-28T12:00:00+00:00",
        "song": "Say",
        "instrument": "Tenor Saxophone",
        "duration_seconds": 42.0,
        "legacy_recording_type": "Practice take",
        "analysis_summary": {
            "coach_summary": "Timing is improving; tone fades at phrase ends.",
            "scores": {"timing": 72, "pitch": 65, "tone": 68},
            "weakest_category": "tone",
            "strongest_category": "timing",
            "categories": {
                "timing": {"findings": ["Entrances are steadier"], "tips": ["Loop chorus at 75% tempo"]},
                "tone": {"findings": ["Support drops on long notes"], "tips": ["Long-tone warmup"]},
            },
            "practice_plan": ["5 min long tones", "Record one chorus pass"],
        },
    }
    if source == "multitrack_export":
        row["source"] = "multitrack_export"
        row["export_id"] = export_id or "exp-1"
        row["legacy_recording_type"] = "Multitrack mix"
    return row


def _sample_tone() -> dict:
    return {
        "tone_take_id": "tone-1",
        "created_at": "2026-06-27T10:00:00+00:00",
        "instrument": "Tenor Saxophone",
        "written_note": "F#",
        "concert_note": "A",
        "mean_cents": 14.0,
        "pitch_stability_score": 62.0,
        "playback_status": "playable",
        "local_path": "media/tone/tone-1.wav",
    }


def _sample_tone_improved() -> dict:
    return {
        **(_sample_tone()),
        "tone_take_id": "tone-2",
        "created_at": "2026-06-28T11:00:00+00:00",
        "mean_cents": 6.0,
        "pitch_stability_score": 74.0,
    }


def _sample_export(*, export_id: str = "exp-1") -> dict:
    return {
        "export_id": export_id,
        "export_name": "Say mix v1",
        "song_title": "Say",
        "created_at": "2026-06-28T09:00:00+00:00",
        "track_count": 3,
        "duration_seconds": 55.0,
        "multitrack_id": "mt-1",
        "playback_status": "playable",
        "local_path": "media/exports/exp-1.wav",
    }


class TestPracticeHistorySynthesis(unittest.TestCase):
    def test_compact_practice_log_includes_focus_and_links(self) -> None:
        row = compact_practice_log_for_ami(_sample_log())
        self.assertEqual(row.get("log_entry_id"), "log-1")
        self.assertEqual(row.get("song_title"), "Say")
        self.assertIn("tone", str(row.get("focus_area") or "").lower())
        self.assertEqual(row.get("duration_minutes"), 25)

    def test_upload_analysis_compact_excludes_instrument_when_empty(self) -> None:
        row = _sample_upload()
        row.pop("instrument", None)
        compact = compact_upload_analysis_for_ami(row)
        self.assertNotIn("instrument", compact)
        self.assertEqual(compact.get("source"), "manual_upload")

    def test_upload_analysis_multitrack_export_source(self) -> None:
        compact = compact_upload_analysis_for_ami(_sample_upload(source="multitrack_export"))
        self.assertEqual(compact.get("source"), "multitrack_export")
        self.assertEqual(compact.get("recording_type"), "multitrack_mix")
        self.assertEqual(compact.get("export_id"), "exp-1")
        self.assertTrue(compact.get("coach_summary"))

    def test_upload_summary_aggregates_by_song_and_source(self) -> None:
        uploads = [
            _sample_upload(),
            _sample_upload(source="multitrack_export"),
        ]
        uploads[1]["recording_id"] = "rec-2"
        summary = build_upload_analysis_ami_summary(uploads, window_days=30)
        self.assertEqual(summary.get("analysis_count_total"), 2)
        self.assertIn("Say", summary.get("count_by_song") or {})
        self.assertIn("multitrack_export", summary.get("count_by_source") or {})

    def test_export_summary_distinguishes_analyzed_vs_waiting(self) -> None:
        uploads = [compact_upload_analysis_for_ami(_sample_upload(source="multitrack_export"))]
        exports = [
            _sample_export(export_id="exp-1"),
            _sample_export(export_id="exp-2"),
        ]
        exports[1]["export_id"] = "exp-2"
        exports[1]["export_name"] = "Say mix v2"
        summary = build_multitrack_export_context_summary(exports, uploads, window_days=30)
        self.assertEqual(summary.get("export_count_total"), 2)
        self.assertEqual(summary.get("analyzed_export_count"), 1)
        self.assertEqual(summary.get("unanalyzed_export_count"), 1)
        waiting = summary.get("exports_waiting_for_analysis") or []
        self.assertTrue(any(r.get("export_id") == "exp-2" for r in waiting))
        analyzed = summary.get("exports_with_saved_analysis") or []
        self.assertTrue(all(r.get("usable_as_playing_evidence") for r in analyzed))

    def test_unanalyzed_exports_not_playing_evidence(self) -> None:
        summary = build_multitrack_export_context_summary(
            [_sample_export(export_id="exp-unanalyzed")],
            [],
            window_days=30,
        )
        waiting = summary.get("exports_waiting_for_analysis") or []
        self.assertEqual(len(waiting), 1)
        self.assertFalse(waiting[0].get("usable_as_playing_evidence"))

    def test_payload_excludes_raw_audio_and_base64(self) -> None:
        catalog = {
            "uploaded_recordings": [_sample_upload()],
            "tone_takes": [_sample_tone()],
            "multitrack_exports": [_sample_export()],
        }

        def _fake_media(st=None, window_days=30):
            from media_state import build_media_ami_payload_from_catalog

            return build_media_ami_payload_from_catalog(catalog, window_days=window_days)

        with patch("media_persistence.build_media_ami_payload", _fake_media):
            with patch("media_persistence.load_media_catalog", return_value=catalog):
                payload = build_practice_history_ami_payload({}, entries=[_sample_log()], window_days=14)
        violations = scan_ami_payload_for_forbidden_data(payload)
        self.assertEqual(violations, [])
        safety = payload.get("safety_checks") or {}
        self.assertTrue(safety.get("raw_audio_excluded"))
        self.assertTrue(safety.get("base64_excluded"))
        self.assertTrue(safety.get("payload_size_reasonable"))

    def test_payload_excludes_deleted_tone_take(self) -> None:
        deleted = {**_sample_tone(), "deleted": True}
        catalog = {"uploaded_recordings": [], "tone_takes": [deleted], "multitrack_exports": []}

        def _fake_media(st=None, window_days=30):
            from media_state import build_media_ami_payload_from_catalog

            return build_media_ami_payload_from_catalog(catalog, window_days=window_days)

        with patch("media_persistence.build_media_ami_payload", _fake_media):
            with patch("media_persistence.load_media_catalog", return_value=catalog):
                payload = build_practice_history_ami_payload({}, entries=[], window_days=14)
        th = payload.get("tone_history_summary") or {}
        self.assertEqual(th.get("tone_take_count_total"), 0)

    def test_progress_report_has_required_sections(self) -> None:
        uploads = [compact_upload_analysis_for_ami(u) for u in [_sample_upload(), _sample_upload(source="multitrack_export")]]
        uploads[1]["recording_id"] = "rec-2"
        payload = {
            "practice_log_summary": {
                "entry_count_total": 1,
                "recent_entries": [compact_practice_log_for_ami(_sample_log())],
                "focus_area_counts": {"tone and timing": 1},
                "practice_time_by_instrument": {"Tenor Saxophone": 25},
                "practice_time_by_song": {"Say": 25},
                "window_days": 14,
                "suggested_next_focus": "Loop bridge at 70% tempo",
            },
            "upload_analysis_summary": build_upload_analysis_ami_summary(
                [_sample_upload(), _sample_upload(source="multitrack_export")],
                window_days=30,
            ),
            "tone_history_summary": {
                "tone_take_count_total": 2,
                "improvement_trends_by_instrument_and_note": [
                    {
                        "instrument": "Tenor Saxophone",
                        "note": "F#",
                        "mean_cents_delta": -8.0,
                        "recent_mean_cents": 6.0,
                        "older_mean_cents": 14.0,
                    }
                ],
            },
            "multitrack_export_summary": build_multitrack_export_context_summary(
                [_sample_export(), _sample_export(export_id="exp-2")],
                uploads,
                window_days=30,
            ),
            "safety_checks": ami_payload_safety_checks({}),
        }
        report = build_practice_progress_report(payload)
        for key in (
            "title",
            "executive_summary",
            "practice_activity",
            "upload_analysis_findings",
            "tone_tuner_findings",
            "cross_evidence_connections",
            "improvements",
            "needs_work",
            "recommended_next_practice_plan",
            "evidence_used",
        ):
            self.assertIn(key, report, msg=f"missing section {key}")
        self.assertIn("Progress Report", report.get("title") or "")
        self.assertIn("practice logs", str(report.get("evidence_used") or "").lower())
        md = format_progress_report_markdown(report)
        self.assertIn("Executive Summary", md)
        self.assertIn("Needs Work", md)

    def test_report_connects_focus_to_tone_evidence(self) -> None:
        payload = {
            "practice_log_summary": {
                "entry_count_total": 1,
                "focus_area_counts": {"tone": 2},
                "recent_entries": [],
                "window_days": 14,
            },
            "upload_analysis_summary": {"analysis_count_total": 0, "recent_analyses": []},
            "tone_history_summary": {"tone_take_count_total": 5},
            "multitrack_export_summary": {},
            "safety_checks": ami_payload_safety_checks({}),
        }
        report = build_practice_progress_report(payload)
        cross = " ".join(report.get("cross_evidence_connections") or [])
        self.assertIn("tone", cross.lower())

    def test_report_recommends_analyzing_waiting_exports(self) -> None:
        payload = {
            "practice_log_summary": {"entry_count_total": 0, "recent_entries": [], "window_days": 14},
            "upload_analysis_summary": {"analysis_count_total": 0, "recent_analyses": []},
            "tone_history_summary": {},
            "multitrack_export_summary": {
                "exports_waiting_for_analysis": [{"export_name": "Say mix v2"}],
                "analyzed_export_count": 0,
            },
            "safety_checks": ami_payload_safety_checks({}),
        }
        report = build_practice_progress_report(payload)
        needs = " ".join(report.get("needs_work") or [])
        plan = " ".join(report.get("recommended_next_practice_plan") or [])
        self.assertIn("export", needs.lower())
        self.assertIn("upload analysis", plan.lower())

    def test_diagnostics_counts(self) -> None:
        payload = {
            "practice_log_summary": {"entry_count_total": 4},
            "upload_analysis_summary": {"analysis_count_total": 3},
            "tone_history_summary": {"tone_take_count_total": 7},
            "multitrack_export_summary": {
                "export_count_total": 3,
                "analyzed_export_count": 1,
                "unanalyzed_export_count": 2,
            },
            "safety_checks": ami_payload_safety_checks({}),
        }
        diag = ami_payload_diagnostics(payload)
        self.assertEqual(diag.get("practice_log_entry_count"), 4)
        self.assertEqual(diag.get("saved_upload_analysis_count"), 3)
        self.assertEqual(diag.get("tone_take_count"), 7)
        self.assertEqual(diag.get("analyzed_export_count"), 1)
        self.assertEqual(diag.get("unanalyzed_export_count"), 2)

    def test_instant_solver_practice_history_intent(self) -> None:
        from music_ami_instant_solver import solve_instant_music_insight

        payload = build_practice_progress_report(
            {
                "practice_log_summary": {"entry_count_total": 1, "window_days": 14, "recent_entries": []},
                "upload_analysis_summary": {"analysis_count_total": 1, "recent_analyses": []},
                "tone_history_summary": {},
                "multitrack_export_summary": {},
                "safety_checks": ami_payload_safety_checks({}),
            }
        )
        ctx = {
            "coach_page": "log",
            "practice_log_ami_payload": {"progress_report": payload, "diagnostics": {}},
        }
        result = solve_instant_music_insight("Analyze my practice history", ctx)
        self.assertIsNotNone(result)
        route, answer = result
        self.assertEqual(route.problem_type, "practice_history_analysis")
        self.assertIn("Progress Report", answer.short_answer)

    def test_payload_json_serializable(self) -> None:
        catalog = {
            "uploaded_recordings": [_sample_upload()],
            "tone_takes": [_sample_tone(), _sample_tone_improved()],
            "multitrack_exports": [_sample_export()],
        }

        def _fake_media(st=None, window_days=30):
            from media_state import build_media_ami_payload_from_catalog

            return build_media_ami_payload_from_catalog(catalog, window_days=window_days)

        with patch("media_persistence.build_media_ami_payload", _fake_media):
            with patch("media_persistence.load_media_catalog", return_value=catalog):
                payload = build_practice_history_ami_payload({}, entries=[_sample_log()], window_days=14)
        text = json.dumps(payload, default=str)
        self.assertIn("upload_analysis_summary", text)
        self.assertNotIn("audio_b64", text)


class TestLogPagePracticeAnalysis(unittest.TestCase):
    def _rich_payload(self) -> dict:
        uploads = [compact_upload_analysis_for_ami(u) for u in [_sample_upload(), _sample_upload(source="multitrack_export")]]
        uploads[1]["recording_id"] = "rec-2"
        return {
            "practice_log_summary": {
                "entry_count_total": 2,
                "recent_entries": [compact_practice_log_for_ami(_sample_log())],
                "focus_area_counts": {"tone and timing": 2},
                "practice_time_by_instrument": {"Tenor Saxophone": 50},
                "practice_time_by_song": {"Say": 50},
                "window_days": 14,
                "suggested_next_focus": "Loop bridge at 70% tempo",
            },
            "upload_analysis_summary": build_upload_analysis_ami_summary(
                [_sample_upload(), _sample_upload(source="multitrack_export")],
                window_days=30,
            ),
            "tone_history_summary": {
                "tone_take_count_total": 3,
                "improvement_trends_by_instrument_and_note": [
                    {
                        "instrument": "Tenor Saxophone",
                        "note": "F#",
                        "mean_cents_delta": -8.0,
                        "recent_mean_cents": 6.0,
                        "older_mean_cents": 14.0,
                    }
                ],
            },
            "multitrack_export_summary": build_multitrack_export_context_summary(
                [_sample_export()],
                uploads,
                window_days=30,
            ),
            "safety_checks": ami_payload_safety_checks({}),
            "progress_report": build_practice_progress_report(
                {
                    "practice_log_summary": {"entry_count_total": 2, "window_days": 14},
                    "upload_analysis_summary": {"analysis_count_total": 1, "recent_analyses": uploads[:1]},
                    "tone_history_summary": {"tone_take_count_total": 3},
                    "multitrack_export_summary": {"analyzed_export_count": 1},
                    "safety_checks": ami_payload_safety_checks({}),
                }
            ),
        }

    def test_log_page_summary_includes_required_sections(self) -> None:
        summary = build_log_page_analysis_summary(self._rich_payload())
        for key in (
            "practice_summary",
            "improvement_notes",
            "upload_recording_review",
            "tone_tuner_notes",
            "recommended_next_session",
            "recommended_focus_this_week",
            "evidence_used",
        ):
            self.assertIn(key, summary)
            self.assertTrue(str(summary[key]).strip(), msg=f"empty section {key}")

    def test_sparse_evidence_empty_state(self) -> None:
        summary = build_log_page_analysis_summary(
            {
                "practice_log_summary": {"entry_count_total": 0, "window_days": 14},
                "upload_analysis_summary": {"analysis_count_total": 0},
                "tone_history_summary": {"tone_take_count_total": 0},
                "multitrack_export_summary": {"export_count_total": 0},
            }
        )
        self.assertIn("No saved practice evidence", summary["practice_summary"])
        self.assertIn("Evidence used", summary["evidence_used"])

    def test_store_replaces_previous_summary(self) -> None:
        session: dict = {}
        store_latest_practice_analysis(session, self._rich_payload())
        first = dict(session.get("latest_practice_analysis_summary") or {})
        sparse = {
            "practice_log_summary": {"entry_count_total": 0, "window_days": 14},
            "upload_analysis_summary": {"analysis_count_total": 0},
            "tone_history_summary": {"tone_take_count_total": 0},
            "multitrack_export_summary": {},
        }
        store_latest_practice_analysis(session, sparse, handoff_result={"duplicate": True, "question_id": "q1"}, handoff_success=True)
        second = session.get("latest_practice_analysis_summary")
        self.assertNotEqual(first.get("practice_summary"), second.get("practice_summary"))
        self.assertIn("No saved practice evidence", str(second.get("practice_summary")))
        self.assertTrue(session.get("latest_practice_analysis_handoff_status", {}).get("duplicate"))

    def test_payload_includes_log_page_summary(self) -> None:
        catalog = {
            "uploaded_recordings": [_sample_upload()],
            "tone_takes": [_sample_tone()],
            "multitrack_exports": [],
        }

        def _fake_media(st=None, window_days=30):
            from media_state import build_media_ami_payload_from_catalog

            return build_media_ami_payload_from_catalog(catalog, window_days=window_days)

        with patch("media_persistence.build_media_ami_payload", _fake_media):
            with patch("media_persistence.load_media_catalog", return_value=catalog):
                payload = build_practice_history_ami_payload({}, entries=[_sample_log()], window_days=14)
        self.assertIn("log_page_summary", payload)
        self.assertIn("progress_report", payload)
        self.assertIn("executive_summary", payload["progress_report"])

    def test_log_page_ui_wiring(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        app_source = (root / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        panel_source = (root / "practice_log_analysis_panel.py").read_text(encoding="utf-8")
        ui_source = (root / "practice_log_ui.py").read_text(encoding="utf-8")
        self.assertIn("from practice_log_analysis_panel import render_practice_analysis_panel", app_source)
        self.assertIn("def render_practice_analysis_panel", panel_source)
        self.assertIn("Practice Analysis", panel_source)
        self.assertIn("render_practice_analysis_panel", ui_source)
        self.assertNotIn('expander("Coach notes"', app_source)
        self.assertNotIn("render_practice_progress_report_panel", ui_source)

    def test_submit_analyze_updates_local_summary_and_handoff(self) -> None:
        from unittest.mock import MagicMock

        from practice_log_ui import submit_analyze_practice_to_ami

        session: dict = {}
        fake_payload = {
            **self._rich_payload(),
            "log_page_summary": build_log_page_analysis_summary(self._rich_payload()),
            "safety_checks": {"raw_audio_excluded": True, "base64_excluded": True, "blob_fields_excluded": True},
        }
        handoff_ctx: dict = {}

        def _fake_handoff(**kwargs):
            handoff_ctx.update(kwargs.get("context") or {})
            return {
                "duplicate": False,
                "continue_title": "Music Practice Log Analysis",
                "question_id": "q-test",
                "handoff_success": True,
            }

        with patch("practice_log_ami.build_practice_log_ami_payload", return_value=fake_payload):
            with patch("practice_log_state.load_entries", return_value=[_sample_log()]):
                with patch("suite_analytical_question.build_submit_context", side_effect=lambda *a, **k: k["context_extra_builder"]()):
                    with patch("music_coach_context.build_source_state", return_value=None):
                        with patch(
                            "suite_analytical_question.submit_practice_log_analysis_handoff",
                            side_effect=_fake_handoff,
                        ):
                            submit_analyze_practice_to_ami(MagicMock(), session)
        self.assertIn("latest_practice_analysis_summary", session)
        self.assertIn("latest_practice_analysis_full_report", session)
        self.assertIn("progress_report", handoff_ctx)


if __name__ == "__main__":
    unittest.main()
