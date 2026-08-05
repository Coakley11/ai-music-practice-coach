"""Practice in Backing Jam deferred handoff integration."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from mission_backing_alignment import build_mission_backing_alignment_payload
from music_workflow_pending_backing_handoff import (
    PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY,
    PENDING_BACKING_WORKFLOW_KEY,
    consume_pending_backing_workflow_handoff,
    queue_pending_backing_workflow_handoff,
    request_pending_backing_handoff_rerun,
    should_request_backing_handoff_rerun,
)


class TestPracticeInBackingJamHandoff(unittest.TestCase):
    def test_queue_preserves_with_practice_lick_and_mode(self) -> None:
        session: dict = {"_creative_mission_widgets_instantiated": True}
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=1,
            song_title="Song",
            with_practice_lick=True,
        )
        req = queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            mission_alignment=align,
        )
        self.assertTrue(req["with_practice_lick"])
        self.assertEqual(req["handoff_mode"], "practice_in_jam")
        self.assertIn("lick=1", req["consume_token"])

    def test_mission_backing_and_practice_in_jam_have_distinct_tokens(self) -> None:
        session: dict = {}
        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=False,
        )
        q1 = queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            mission_alignment=align,
        )
        align2 = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=True,
        )
        q2 = queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            mission_alignment=align2,
        )
        self.assertNotEqual(q1["consume_token"], q2["consume_token"])

    def test_consume_applies_practice_lick_once_and_navigates(self) -> None:
        session: dict = {
            "studio_page": "creative",
            "improv_mission_practice_lick": {"motif": {"notes": ["Bb", "D", "F"]}, "bpm": 100},
        }
        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=0,
            song_title="Song",
            with_practice_lick=True,
        )
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            mission_alignment=align,
        )
        token = session[PENDING_BACKING_WORKFLOW_KEY]["consume_token"]
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                with mock.patch("backing_context.open_backing_from_creative"):
                    with mock.patch("mission_backing_handoff_persistence.arm_mission_backing_handoff_page_change"):
                        phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertEqual(session.get(PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY), token)
        self.assertIsNone(session.get(PENDING_BACKING_WORKFLOW_KEY))

    def test_consume_not_marked_consumed_if_navigation_fails(self) -> None:
        session: dict = {"studio_page": "creative"}

        def _nav(ss, page):
            ss["studio_page"] = "creative"

        align = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="C",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=True,
        )
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
            mission_alignment=align,
        )
        with mock.patch("studio_nav_history.navigate_studio_page", side_effect=_nav):
            with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
                activate.return_value = mock.Mock(ok=True, trace={})
                with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                    with mock.patch("backing_context.open_backing_from_creative"):
                        phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "skipped")
        self.assertIsInstance(session.get(PENDING_BACKING_WORKFLOW_KEY), dict)
        self.assertIsNone(session.get(PENDING_BACKING_WORKFLOW_CONSUMED_TOKEN_KEY))

    def test_rerun_guard_allows_one_rerun_per_seq(self) -> None:
        session: dict = {}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
        )
        self.assertTrue(should_request_backing_handoff_rerun(session))
        self.assertFalse(should_request_backing_handoff_rerun(session))

    def test_guard_reject_retains_pending_without_bare_rerun(self) -> None:
        session: dict = {}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
            with_practice_lick=True,
        )
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=False):
            self.assertFalse(request_pending_backing_handoff_rerun(st_mock, session))
        st_mock.rerun.assert_not_called()
        self.assertIsNotNone(session.get(PENDING_BACKING_WORKFLOW_KEY))

    def test_open_mission_backing_source_has_no_mutable_align(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        tab = text[text.index("def _tab_missions(") : text.index("\n    if not example:", text.index("def _open_mission_backing"))]
        self.assertNotIn("ensure_mission_handoff_aligned", tab)


if __name__ == "__main__":
    unittest.main()
