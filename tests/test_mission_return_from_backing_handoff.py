"""Return to Mission deferred handoff from Backing."""

from __future__ import annotations

import unittest
from unittest import mock

from mission_backing_alignment import build_mission_backing_alignment_payload
from mission_return_destination import (
    MISSION_CANONICAL_RETURN_DESTINATION_KEY,
    build_mission_return_destination,
    seal_mission_return_destination,
)
from music_workflow_pending_backing_handoff import (
    consume_pending_backing_workflow_handoff,
    arm_pending_backing_handoff_consume,
    queue_pending_backing_workflow_handoff,
)
from music_workflow_pending_mission_return import (
    PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY,
    PENDING_MISSION_RETURN_KEY,
    consume_pending_mission_return_handoff,
    handle_return_to_mission_click,
    queue_pending_mission_return_from_backing,
    request_pending_mission_return_rerun,
)


class TestMissionReturnFromBackingHandoff(unittest.TestCase):
    def test_backing_consume_seals_canonical_return_destination(self) -> None:
        session: dict = {"studio_page": "creative"}
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="Bb",
            section_label="Verse",
            chord_idx=1,
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
        arm_pending_backing_handoff_consume(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                with mock.patch("backing_context.open_backing_from_creative"):
                    with mock.patch("mission_backing_handoff_persistence.arm_mission_backing_handoff_page_change"):
                        phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        dest = session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY)
        self.assertIsInstance(dest, dict)
        self.assertEqual(dest.get("mission_id"), align["mission_id"])
        self.assertTrue(dest.get("with_practice_lick"))
        self.assertEqual(dest.get("handoff_mode"), "practice_in_jam")
        self.assertIn("return_token", dest)

    def test_practice_in_jam_and_plain_backing_return_tokens_differ(self) -> None:
        session: dict = {}
        a1 = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=False,
        )
        a2 = build_mission_backing_alignment_payload(
            session,
            mission="M",
            cur_chord="Bb",
            section_label="A",
            chord_idx=0,
            song_title="S",
            with_practice_lick=True,
        )
        d1 = build_mission_return_destination(a1, handoff_mode="mission_backing", with_practice_lick=False, request_seq=1)
        d2 = build_mission_return_destination(a2, handoff_mode="practice_in_jam", with_practice_lick=True, request_seq=1)
        self.assertNotEqual(d1["return_token"], d2["return_token"])

    def test_return_consume_restores_missions_tab_and_mission_identity(self) -> None:
        session: dict = {
            "studio_page": "backing",
            MISSION_CANONICAL_RETURN_DESTINATION_KEY: build_mission_return_destination(
                build_mission_backing_alignment_payload(
                    {},
                    mission="Mission A",
                    cur_chord="Bb",
                    section_label="Verse",
                    chord_idx=0,
                    song_title="Tune",
                    with_practice_lick=True,
                ),
                handoff_mode="practice_in_jam",
                with_practice_lick=True,
                request_seq=3,
            ),
        }
        queue_pending_mission_return_from_backing(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                with mock.patch("backing_context.get_backing_context", return_value=None):
                    phase = consume_pending_mission_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertEqual(session.get("improv_active_mission"), "Mission A")
        self.assertEqual(session.get("ii_selected_chord"), "Bb")
        self.assertEqual(session.get("_pending_improv_intelligence_tab"), "Missions")
        self.assertIsNone(session.get(PENDING_MISSION_RETURN_KEY))
        self.assertTrue(session.get(PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY))

    def test_return_not_consumed_when_navigation_fails(self) -> None:
        session: dict = {"studio_page": "backing"}
        seal_mission_return_destination(
            session,
            build_mission_return_destination(
                build_mission_backing_alignment_payload(
                    session,
                    mission="M",
                    cur_chord="C",
                    section_label="A",
                    chord_idx=0,
                    song_title="S",
                ),
                handoff_mode="mission_backing",
                with_practice_lick=False,
                request_seq=1,
            ),
        )
        queue_pending_mission_return_from_backing(session)

        def _nav(ss, page):
            ss["studio_page"] = "backing"

        with mock.patch("studio_nav_history.navigate_studio_page", side_effect=_nav):
            with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
                activate.return_value = mock.Mock(ok=True, trace={})
                with mock.patch("mission_backing_alignment.apply_pending_mission_backing_alignment", return_value=True):
                    phase = consume_pending_mission_return_handoff(session)
        self.assertEqual(phase, "skipped")
        self.assertIsInstance(session.get(PENDING_MISSION_RETURN_KEY), dict)
        self.assertIsNone(session.get(PENDING_MISSION_RETURN_CONSUMED_TOKEN_KEY))

    def test_blocked_rerun_does_not_call_bare_st_rerun(self) -> None:
        session: dict = {MISSION_CANONICAL_RETURN_DESTINATION_KEY: {"mission_id": "M", "return_token": "t"}}
        seal_mission_return_destination(
            session,
            build_mission_return_destination(
                build_mission_backing_alignment_payload(
                    session,
                    mission="M",
                    cur_chord="C",
                    section_label="A",
                    chord_idx=0,
                    song_title="S",
                ),
                handoff_mode="mission_backing",
                with_practice_lick=False,
            ),
        )
        queue_pending_mission_return_from_backing(session)
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=False):
            self.assertFalse(request_pending_mission_return_rerun(st_mock, session))
        st_mock.rerun.assert_not_called()

    def test_click_handler_queues_without_prepare_return_immediate(self) -> None:
        align = build_mission_backing_alignment_payload(
            {},
            mission="M",
            cur_chord="D",
            section_label="Chorus",
            chord_idx=0,
            song_title="S",
        )
        session: dict = {
            "studio_page": "backing",
            MISSION_CANONICAL_RETURN_DESTINATION_KEY: build_mission_return_destination(
                align,
                handoff_mode="mission_backing",
                with_practice_lick=False,
            ),
        }
        st_mock = mock.Mock()
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            with mock.patch("studio_page_persistence.save_page_snapshot"):
                handle_return_to_mission_click(st_mock, session)
        self.assertIsInstance(session.get(PENDING_MISSION_RETURN_KEY), dict)
        st_mock.rerun.assert_not_called()

    def test_return_handlers_use_deferred_click_path(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        text = root.read_text(encoding="utf-8")
        self.assertIn("handle_return_to_mission_click", text)
        block = text.split("def _go_mission_detail", 1)[1].split("def _go_source", 1)[0]
        self.assertIn("handle_return_to_mission_click", block)
        self.assertNotIn("prepare_return_to_mission_detail(st.session_state)", block)
        lick_block = text.split("def _return_to_mission_from_backing", 1)[1].split("\n        _lick_payload", 1)[0]
        self.assertIn("handle_return_to_mission_click", lick_block)
        self.assertNotIn("st.rerun()", lick_block)


if __name__ == "__main__":
    unittest.main()
