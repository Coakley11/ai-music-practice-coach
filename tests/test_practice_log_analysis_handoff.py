"""Practice Analysis Command Center handoff and content cleanup tests."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from practice_history_synthesis import (
    _clip_summary_at_sentence,
    _count_analyzed_multitrack_exports,
    _format_recommended_focus,
    _format_recording_type_label,
    _format_tone_cents_phrase,
    _format_tone_trend_line,
    build_log_page_analysis_summary,
    build_practice_progress_report,
    format_instrument_display_name,
    scan_ami_payload_for_forbidden_data,
    store_latest_practice_analysis,
)
from practice_log_analysis_handoff import (
    PRACTICE_ANALYSIS_CC_ROUTE,
    PRACTICE_ANALYSIS_CC_TITLE,
    enrich_practice_analysis_handoff_context,
    submit_practice_analysis_command_center_handoff,
)


class TestPracticeAnalysisContentCleanup(unittest.TestCase):
    def test_huge_cents_flagged_not_displayed_normally(self) -> None:
        phrase = _format_tone_cents_phrase(-1134.5)
        self.assertIn("wrong note or octave", phrase)
        self.assertNotIn("-1134.5", phrase)
        line = _format_tone_trend_line(
            {
                "instrument": "Saxophone",
                "note": "F#4",
                "recent_mean_cents": -1134.5,
                "older_mean_cents": -900.0,
                "mean_cents_delta": -234.5,
            }
        )
        self.assertIn("wrong note or octave", line)
        self.assertNotIn("-1134.5", line)

    def test_specific_sax_type_when_available(self) -> None:
        name = format_instrument_display_name(
            "Saxophone",
            payload={
                "practice_log_summary": {
                    "practice_time_by_instrument": {"Tenor Saxophone": 40, "Saxophone": 5}
                }
            },
        )
        self.assertEqual(name, "Tenor Saxophone")

    def test_recording_type_labels_humanized(self) -> None:
        self.assertEqual(_format_recording_type_label("single_recording"), "Single recording")
        self.assertEqual(_format_recording_type_label("multitrack_mix"), "Multitrack mix")
        self.assertEqual(_format_recording_type_label("multitrack_export"), "Multitrack export")

    def test_summary_clips_at_sentence_boundary(self) -> None:
        text = (
            "Timing is improving steadily. Tone fades at phrase ends, especially on long notes, "
            "and articulation could be cleaner on fast passages, with occasional rushing into downbeats."
        )
        clipped = _clip_summary_at_sentence(text, max_len=90)
        self.assertFalse(clipped.endswith(","))
        self.assertTrue(clipped.endswith(".") or clipped.endswith("!") or clipped.endswith("?"))

    def test_focus_deduped_and_punctuation_clean(self) -> None:
        focus = _format_recommended_focus(
            ["tone", "strumming", "pitch (32).", "tone (68)..", "intonation"],
            is_wind=True,
        )
        self.assertNotIn("strumming", focus.lower())
        self.assertNotIn("(32)", focus)
        self.assertNotIn("..", focus)
        self.assertIn("pitch/intonation", focus.lower())

    def test_analyzed_export_count_from_upload_source(self) -> None:
        payload = {
            "multitrack_export_summary": {"analyzed_export_count": 0, "export_count_total": 0},
            "upload_analysis_summary": {
                "recent_analyses": [
                    {"source": "multitrack_export", "export_id": "exp-42", "coach_summary": "Good timing."}
                ]
            },
        }
        self.assertEqual(_count_analyzed_multitrack_exports(payload), 1)
        report = build_practice_progress_report(payload)
        self.assertIn("**1** analyzed multitrack export", report.get("evidence_used", ""))

    def test_log_page_summary_avoids_raw_enum_labels(self) -> None:
        payload = {
            "practice_log_summary": {
                "entry_count_total": 1,
                "window_days": 14,
                "practice_time_by_instrument": {"Tenor Saxophone": 25},
                "focus_area_counts": {"tone": 1},
            },
            "upload_analysis_summary": {
                "analysis_count_total": 1,
                "recent_analyses": [
                    {
                        "song_title": "Say",
                        "recording_type": "single_recording",
                        "coach_summary": "Timing is improving. Tone fades at phrase ends on long notes.",
                    }
                ],
            },
            "tone_history_summary": {"tone_take_count_total": 0},
            "multitrack_export_summary": {"export_count_total": 0, "analyzed_export_count": 0},
        }
        payload["progress_report"] = build_practice_progress_report(payload)
        summary = build_log_page_analysis_summary(payload)
        combined = " ".join(summary.values())
        self.assertNotIn("single_recording", combined)
        self.assertIn("Single recording", combined)
        self.assertIn("Tenor Saxophone", summary["practice_summary"])


class TestPracticeAnalysisHandoff(unittest.TestCase):
    def test_enrich_handoff_context_fields(self) -> None:
        payload = {
            "progress_report": {"executive_summary": "test"},
            "log_page_summary": {"practice_summary": "summary"},
            "recent_sessions": [{"session_id": "s1"}],
            "safety_checks": {"raw_audio_excluded": True, "base64_excluded": True, "blob_fields_excluded": True},
        }
        ctx = enrich_practice_analysis_handoff_context(payload)
        self.assertEqual(ctx["analysis_type"], PRACTICE_ANALYSIS_CC_ROUTE)
        self.assertEqual(ctx["title"], PRACTICE_ANALYSIS_CC_TITLE)
        self.assertIn("progress_report", ctx)
        self.assertIn("practice_history_payload", ctx)
        self.assertTrue(ctx["raw_audio_excluded"])

    def test_submit_handoff_success_only_when_writes_succeed(self) -> None:
        session: dict = {}
        fake_payload = {
            "practice_log_summary": {"entry_count_total": 1, "window_days": 14, "session_count": 1},
            "upload_analysis_summary": {"analysis_count_total": 0},
            "tone_history_summary": {"tone_take_count_total": 0},
            "multitrack_export_summary": {},
            "progress_report": {"executive_summary": "ok", "evidence_used": "Evidence used"},
            "log_page_summary": build_log_page_analysis_summary(
                {
                    "practice_log_summary": {"entry_count_total": 1, "window_days": 14},
                    "upload_analysis_summary": {"analysis_count_total": 0},
                    "tone_history_summary": {"tone_take_count_total": 0},
                    "multitrack_export_summary": {},
                }
            ),
            "safety_checks": {"raw_audio_excluded": True, "base64_excluded": True, "blob_fields_excluded": True},
        }

        def _ok_handoff(**kwargs):
            ctx = kwargs.get("context") or {}
            self.assertEqual(ctx.get("analysis_type"), PRACTICE_ANALYSIS_CC_ROUTE)
            self.assertIn("progress_report", ctx)
            return {
                "duplicate": False,
                "continue_title": PRACTICE_ANALYSIS_CC_TITLE,
                "question_id": "q-test",
                "resume_key": "ai:practice_log_analysis:q-test",
                "handoff_success": True,
                "context": ctx,
            }

        with patch("practice_log_ami.build_practice_log_ami_payload", return_value=fake_payload):
            with patch("suite_analytical_question.submit_practice_log_analysis_handoff", side_effect=_ok_handoff):
                with patch("suite_analytical_question.build_submit_context", side_effect=lambda *a, **k: k["context_extra_builder"]()):
                    with patch("music_coach_context.build_source_state", return_value=None):
                        result = submit_practice_analysis_command_center_handoff(MagicMock(), session)
        self.assertTrue(result.get("handoff_success"))

    def test_submit_handoff_failure_does_not_claim_sent(self) -> None:
        session: dict = {}
        fake_payload = {
            "practice_log_summary": {"entry_count_total": 1, "window_days": 14},
            "upload_analysis_summary": {"analysis_count_total": 0},
            "tone_history_summary": {"tone_take_count_total": 0},
            "multitrack_export_summary": {},
            "progress_report": {"executive_summary": "ok"},
            "log_page_summary": {},
            "safety_checks": {"raw_audio_excluded": True, "base64_excluded": True, "blob_fields_excluded": True},
        }

        with patch("practice_log_ami.build_practice_log_ami_payload", return_value=fake_payload):
            with patch(
                "suite_analytical_question.submit_practice_log_analysis_handoff",
                return_value={
                    "duplicate": False,
                    "handoff_success": False,
                    "handoff_error": "Supabase not configured",
                    "continue_title": PRACTICE_ANALYSIS_CC_TITLE,
                },
            ):
                with patch("suite_analytical_question.build_submit_context", side_effect=lambda *a, **k: k["context_extra_builder"]()):
                    with patch("music_coach_context.build_source_state", return_value=None):
                        result = submit_practice_analysis_command_center_handoff(MagicMock(), session)
        self.assertFalse(result.get("handoff_success"))
        status = session.get("latest_practice_analysis_handoff_status") or {}
        self.assertFalse(status.get("success"))
        self.assertFalse(status.get("sent_at"))

    def test_handoff_payload_excludes_raw_audio(self) -> None:
        ctx = enrich_practice_analysis_handoff_context(
            {
                "progress_report": {"executive_summary": "ok"},
                "practice_log_summary": {},
                "upload_analysis_summary": {},
                "tone_history_summary": {},
                "multitrack_export_summary": {},
                "safety_checks": {"raw_audio_excluded": True},
            }
        )
        violations = scan_ami_payload_for_forbidden_data(ctx)
        self.assertEqual(violations, [])

    def test_submit_practice_log_analysis_passes_action_url_and_status(self) -> None:
        from suite_analytical_question import PRACTICE_LOG_ANALYSIS_TITLE, submit_practice_log_analysis_handoff

        recorded: list[tuple] = []

        def _fake_record(app, event, **kwargs):
            recorded.append((app, event, kwargs))

        ctx = {
            "user_request": "analyze_practice",
            "analysis_type": "practice_history_analysis",
            "progress_report": {"executive_summary": "ok"},
            "practice_history_payload": {"practice_log_summary": {}},
            "log_page_summary": {"practice_summary": "summary"},
            "practice_log_summary": {"session_count": 2, "total_minutes": 60},
        }
        with patch("suite_activity_client.record_activity", _fake_record):
            with patch("suite_activity_client.last_record_trace", return_value={"recorded": True, "supabase_write_ok": True}):
                with patch("suite_analytical_question._upsert_applied_intelligence_resume", return_value=True):
                    with patch("suite_analytical_question._upsert_music_practice_log_resume", return_value=True):
                        with patch("suite_analytical_question._store_practice_analysis_context_blob", return_value=True):
                            with patch("suite_analytical_question._stage_practice_analysis_instant_insight", return_value="pa:run-test"):
                                with patch("suite_analytical_question._recent_duplicate_send", return_value=False):
                                    result = submit_practice_log_analysis_handoff(
                                    source_page="log",
                                    question="Analyze my practice history",
                                    context=ctx,
                                    session_state={},
                                )
        self.assertTrue(recorded)
        _, _, kwargs = recorded[0]
        self.assertTrue(str(kwargs.get("action_url") or "").strip())
        self.assertEqual(kwargs.get("resume_title"), PRACTICE_LOG_ANALYSIS_TITLE)
        metrics = kwargs.get("metrics") or {}
        self.assertEqual(metrics.get("analysis_type"), "practice_history_analysis")
        saved = metrics.get("saved_item_payload") or {}
        self.assertIn("progress_report", saved)
        self.assertIn("practice_history_payload", saved)
        self.assertTrue(result.get("handoff_success"))
        self.assertEqual(result.get("continue_title"), PRACTICE_LOG_ANALYSIS_TITLE)
        self.assertTrue(str(result.get("analysis_run_id") or "").strip())
        self.assertEqual(result.get("insight_id"), "pa:run-test")
        self.assertNotIn("__ctx_json__", str(kwargs.get("resume_subtitle") or ""))
        self.assertIn("suite_practice_analysis_run_id", str(kwargs.get("action_url") or ""))
        self.assertIn("suite_ami_insight=pa%3Arun-test", str(kwargs.get("action_url") or ""))

    def test_store_handoff_status_reflects_success_flag(self) -> None:
        session: dict = {}
        store_latest_practice_analysis(
            session,
            {"practice_log_summary": {"entry_count_total": 1, "window_days": 14}},
            handoff_result={"duplicate": False, "question_id": "q1"},
            handoff_success=False,
        )
        status = session.get("latest_practice_analysis_handoff_status") or {}
        self.assertFalse(status.get("success"))
        self.assertFalse(status.get("sent_at"))

    def test_second_handoff_updates_existing_resume_item_without_failure(self) -> None:
        from suite_analytical_question import submit_practice_log_analysis_handoff

        ctx = {
            "user_request": "analyze_practice",
            "analysis_type": "practice_history_analysis",
            "progress_report": {"executive_summary": "run 2"},
            "practice_history_payload": {"practice_log_summary": {"entry_count_total": 2}},
            "log_page_summary": {"practice_summary": "updated"},
            "practice_log_summary": {"session_count": 2, "total_minutes": 60},
        }
        upsert_calls: list[tuple[str, str]] = []

        def _fake_music_upsert(payload, *, action_url):
            upsert_calls.append(("music", str(payload.get("resume_key") or "")))
            return True

        def _fake_ai_upsert(payload, *, action_url):
            upsert_calls.append(("applied_intelligence", str(payload.get("resume_key") or "")))
            return True

        stored_blobs: list[dict] = []

        def _fake_store_blob(payload):
            stored_blobs.append(dict(payload.get("context") or {}))
            return True

        def _fake_insight(payload):
            run_id = str(payload.get("analysis_run_id") or "")
            return f"pa:{run_id}" if run_id else "pa:test"

        with patch("suite_analytical_question._recent_duplicate_send", return_value=False):
            with patch("suite_activity_client.record_activity"):
                with patch(
                    "suite_activity_client.last_record_trace",
                    return_value={"recorded": True, "supabase_write_ok": True},
                ):
                    with patch(
                        "suite_analytical_question._upsert_music_practice_log_resume",
                        side_effect=_fake_music_upsert,
                    ):
                        with patch(
                            "suite_analytical_question._upsert_applied_intelligence_resume",
                            side_effect=_fake_ai_upsert,
                        ):
                            with patch(
                                "suite_analytical_question._store_practice_analysis_context_blob",
                                side_effect=_fake_store_blob,
                            ):
                                with patch(
                                    "suite_analytical_question._stage_practice_analysis_instant_insight",
                                    side_effect=_fake_insight,
                                ):
                                    first = submit_practice_log_analysis_handoff(
                                    source_page="log",
                                    question="Analyze my practice history",
                                    context={**ctx, "progress_report": {"executive_summary": "run 1"}},
                                    session_state={},
                                )
                                second = submit_practice_log_analysis_handoff(
                                    source_page="log",
                                    question="Analyze my practice history",
                                    context=ctx,
                                    session_state={},
                                )
        self.assertTrue(first.get("handoff_success"))
        self.assertTrue(second.get("handoff_success"))
        self.assertEqual(first.get("resume_key"), second.get("resume_key"))
        self.assertTrue(str(first.get("resume_key") or "").startswith("ai:practice_log_analysis:"))
        self.assertEqual(upsert_calls.count(("music", first.get("resume_key"))), 2)
        self.assertEqual(upsert_calls.count(("applied_intelligence", first.get("resume_key"))), 2)
        self.assertEqual(len(stored_blobs), 2)
        self.assertEqual(stored_blobs[-1].get("progress_report", {}).get("executive_summary"), "run 2")
        self.assertNotEqual(first.get("analysis_run_id"), second.get("analysis_run_id"))
        self.assertNotEqual(first.get("action_url"), second.get("action_url"))

    def test_duplicate_cooldown_still_refreshes_blob_and_resume(self) -> None:
        from suite_analytical_question import submit_practice_log_analysis_handoff

        ctx = {
            "user_request": "analyze_practice",
            "progress_report": {"executive_summary": "cooldown refresh"},
            "practice_log_summary": {"session_count": 1},
        }
        recorded: list[tuple] = []

        def _fake_record(app, event, **kwargs):
            recorded.append((app, event, kwargs))

        with patch("suite_analytical_question._recent_duplicate_send", return_value=True):
            with patch("suite_activity_client.record_activity", side_effect=_fake_record):
                with patch("suite_activity_client.last_record_trace", return_value={"recorded": True, "supabase_write_ok": True}):
                    with patch("suite_analytical_question._upsert_applied_intelligence_resume", return_value=True):
                        with patch("suite_analytical_question._upsert_music_practice_log_resume", return_value=True) as music_upsert:
                            with patch("suite_analytical_question._store_practice_analysis_context_blob", return_value=True) as store_blob:
                                with patch("suite_analytical_question._stage_practice_analysis_instant_insight", return_value="pa:cooldown"):
                                    result = submit_practice_log_analysis_handoff(
                                    source_page="log",
                                    question="Analyze my practice history",
                                    context=ctx,
                                    session_state={"_ami_last_send": {"question_id": "x", "submitted_at": "2026-06-29T00:00:00+00:00"}},
                                )
        self.assertTrue(result.get("duplicate"))
        self.assertTrue(result.get("handoff_success"))
        self.assertTrue(result.get("activity_recorded"))
        self.assertEqual(recorded[0][1], "practice_log_analysis")
        metrics = recorded[0][2].get("metrics") or {}
        self.assertTrue(str(metrics.get("resume_key") or "").startswith("ai:practice_log_analysis:"))
        self.assertTrue(str(metrics.get("activity_sort_at") or "").strip())
        music_upsert.assert_called_once()
        store_blob.assert_called_once()
        self.assertNotIn("409", str(result.get("handoff_error") or ""))

    def test_hydrate_prefers_analysis_run_id_blob(self) -> None:
        from suite_analytical_question import hydrate_applied_intelligence_session

        class _SS(dict):
            pass

        st = type("St", (), {"session_state": _SS(), "query_params": {}})()
        st.query_params = {
            "suite_practice_analysis_run_id": "run-new",
            "suite_ai_question_id": "q-old",
            "suite_ai_question": "Analyze my practice history\n__ctx_json__:{\"stale\": true}",
        }
        fresh_ctx = {"progress_report": {"executive_summary": "fresh run"}, "analysis_run_id": "run-new"}
        with patch(
            "suite_analytical_question.load_analytical_question_payload",
            return_value={"context": fresh_ctx, "source_state": {}},
        ):
            hydrate_applied_intelligence_session(st)
        self.assertEqual(st.session_state.get("_suite_practice_analysis_run_id"), "run-new")
        self.assertNotIn("__ctx_json__", str(st.session_state.get("ps_library_problem") or ""))
        loaded = __import__("json").loads(st.session_state.get("_suite_ai_context") or "{}")
        self.assertEqual(loaded.get("progress_report", {}).get("executive_summary"), "fresh run")

    def test_practice_log_card_subtitle_includes_updated_line(self) -> None:
        from suite_analytical_question import practice_log_analysis_card_subtitle

        subtitle = practice_log_analysis_card_subtitle(
            {
                "report_generated_at": "2026-06-29T13:28:00+00:00",
                "context": {
                    "practice_log_summary": {
                        "session_count": 2,
                        "total_minutes": 60,
                        "practice_time_by_instrument": {"tenor_saxophone": 60},
                        "practice_time_by_song": {"Say": 45},
                    }
                },
            }
        )
        self.assertIn("Top song: Say", subtitle)
        self.assertIn("Updated", subtitle)
        self.assertIn("ET", subtitle)
        self.assertIn("Jun 29, 2026", subtitle)
        self.assertNotIn("Guitar / Say", subtitle)
        self.assertNotIn("__ctx_json__", subtitle)

    def test_mixed_instruments_subtitle_shows_multiple(self) -> None:
        from suite_analytical_question import practice_log_analysis_card_subtitle

        subtitle = practice_log_analysis_card_subtitle(
            {
                "report_generated_at": "2026-06-29T13:28:00+00:00",
                "context": {
                    "practice_log_summary": {
                        "practice_time_by_instrument": {"Tenor Saxophone": 30, "Guitar": 30},
                        "practice_time_by_song": {"Say": 45},
                    }
                },
            }
        )
        self.assertIn("Multiple instruments", subtitle)
        self.assertNotIn("Guitar / Say", subtitle)

    def test_single_dominant_instrument_subtitle(self) -> None:
        from suite_analytical_question import practice_log_analysis_card_subtitle

        subtitle = practice_log_analysis_card_subtitle(
            {
                "report_generated_at": "2026-06-29T13:28:00+00:00",
                "context": {
                    "practice_log_summary": {
                        "practice_time_by_instrument": {"Tenor Saxophone": 90, "Guitar": 10},
                        "practice_time_by_song": {"Say": 45},
                    }
                },
            }
        )
        self.assertIn("Main instrument: Tenor Saxophone", subtitle)

    def test_eastern_time_june_uses_edt_offset(self) -> None:
        from activity_time import format_eastern_time_label, parse_activity_timestamp

        dt = parse_activity_timestamp("2026-06-29T13:28:00+00:00")
        assert dt is not None
        label = format_eastern_time_label(dt)
        self.assertIn("9:28 AM ET", label)
        self.assertNotIn("+00:00", label)

    def test_handoff_metrics_include_resume_key_and_sort_at(self) -> None:
        from suite_analytical_question import _build_practice_log_activity_metrics

        payload = {
            "question_id": "q1",
            "resume_key": "ai:practice_log_analysis:q1",
            "analysis_run_id": "run123",
            "report_generated_at": "2026-06-29T01:42:00+00:00",
            "context": {"user_request": "analyze_practice"},
        }
        metrics = _build_practice_log_activity_metrics(
            payload,
            extra_metrics={"analysis_run_id": "run123"},
            action_url="https://example.test/ami?suite_practice_analysis_run_id=run123",
        )
        self.assertEqual(metrics.get("resume_key"), "ai:practice_log_analysis:q1")
        self.assertEqual(metrics.get("activity_sort_at"), "2026-06-29T01:42:00+00:00")
        self.assertIn("continue_action_url", metrics)

    def test_clean_analytical_question_display_strips_ctx_json(self) -> None:
        from suite_analytical_question import clean_analytical_question_display

        raw = "Analyze my practice history\n__ctx_json__:{\"foo\": 1}"
        self.assertEqual(clean_analytical_question_display(raw), "Analyze my practice history")


if __name__ == "__main__":
    unittest.main()
