"""Hotfix: Missions tab must not late-restore workflow snapshots into widget keys."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from music_workflow_pending_activation import (
    PENDING_WORKFLOW_ACTIVATION_KEY,
    consume_pending_workflow_activation,
    peek_pending_workflow_activation,
    queue_pending_workflow_activation,
    request_or_activate_workflow,
)
from workflow_musical_authority import (
    WORKFLOW_MUSICAL_STATES_KEY,
    restore_workflow_snapshot,
    switch_workflow_owner,
)


class TestMissionsWorkflowHotfix(unittest.TestCase):
    def test_tab_missions_does_not_call_snapshot_restore_or_switch_owner(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        start = text.index("def _tab_missions(")
        end = text.index("\ndef ", start + 1)
        body = text[start:end]
        self.assertNotIn("restore_workflow_snapshot", body)
        self.assertNotIn("switch_workflow_owner", body)
        self.assertNotIn("activate_workflow(", body)

    def test_render_lab_after_radio_does_not_restore_snapshot(self) -> None:
        root = Path(__file__).resolve().parents[1] / "improvisation_intelligence_ui.py"
        text = root.read_text(encoding="utf-8")
        radio_idx = text.index('key="improv_intelligence_tab"')
        after_radio = text[radio_idx:]
        self.assertNotIn("restore_workflow_snapshot", after_radio)

    def test_switch_owner_does_not_fallback_song_snapshot(self) -> None:
        root = Path(__file__).resolve().parents[1] / "workflow_musical_authority.py"
        text = root.read_text(encoding="utf-8")
        fn_start = text.index("def switch_workflow_owner")
        fn_body = text[fn_start : fn_start + 2500]
        self.assertNotIn('restore_workflow_snapshot(session, "song_based_improvisation")', fn_body)

    def test_guarded_restore_defer_display_key_when_widgets_locked(self) -> None:
        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "D",
            WORKFLOW_MUSICAL_STATES_KEY: {
                "song_based_improvisation": {
                    "display_key": "Em",
                    "concert_key": "Em",
                    "sections": {"A": ["Em"]},
                }
            },
        }
        ok = restore_workflow_snapshot(session, "song_based_improvisation")
        self.assertTrue(ok)
        self.assertEqual(session.get("display_key"), "D")
        from songs.key_state import PENDING_DISPLAY_KEY

        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "Em")
        blocked = session.get("_music_workflow_pending_blocked_restore_keys") or []
        keys = {b.get("key") for b in blocked if isinstance(b, dict)}
        self.assertIn("display_key", keys)

    def test_late_request_queues_pending_activation(self) -> None:
        session: dict = {"_streamlit_widgets_locked_this_run": True}
        status = request_or_activate_workflow(
            session,
            target_owner="mission_jam",
            activation_source="test_late",
            active_creative_view="Missions",
        )
        self.assertEqual(status, "queued")
        pending = peek_pending_workflow_activation(session)
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(pending.get("target_owner"), "mission_jam")

    def test_pending_consumed_exactly_once(self) -> None:
        session: dict = {
            "song": "Hevenu",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Song-Based Improvisation",
            "display_key": "D",
            "concert_key": "D",
            WORKFLOW_MUSICAL_STATES_KEY: {
                "mission_jam": {
                    "display_key": "Em",
                    "concert_key": "Em",
                    "sections": {"A": ["Em"]},
                    "improv_active_mission": "A",
                },
                "jam_session_generator": {
                    "tonic_key": "D",
                    "mode": "major",
                },
            },
        }
        queue_pending_workflow_activation(
            session,
            target_owner="mission_jam",
            activation_source="test_consume",
            active_creative_view="Missions",
            navigation_intent="creative_missions",
        )
        first = consume_pending_workflow_activation(session)
        self.assertIn(first, {"applied", "skipped"})
        if first == "applied":
            self.assertIsNone(peek_pending_workflow_activation(session))
            second = consume_pending_workflow_activation(session)
            self.assertEqual(second, "skipped")

    def test_generator_d_major_to_missions_restores_song_key_via_activation(self) -> None:
        from music_workflow_activation import ActivateWorkflowRequest, activate_workflow
        from music_workflow_state_store import get_active_workflow_pointer

        session: dict = {
            "song": "Hevenu Shalom Aleichem",
            "active_catalog_pick_key": "Hevenu Shalom Aleichem",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "D",
            "display_key": "D",
            "concert_key": "D",
            WORKFLOW_MUSICAL_STATES_KEY: {
                "song_based_improvisation": {
                    "display_key": "Em",
                    "concert_key": "Em",
                    "sections": {"Verse": ["Em", "Am"]},
                },
                "mission_jam": {
                    "display_key": "Em",
                    "concert_key": "Em",
                    "sections": {"Verse": ["Em", "Am"]},
                    "improv_active_mission": "A",
                },
            },
        }
        with mock.patch(
            "music_workflow_mission_bootstrap.ensure_mission_blob_from_song",
            side_effect=lambda s, sid: None,
        ):
            activate_workflow(
                session,
                ActivateWorkflowRequest(
                    target_owner="mission_jam",
                    activation_source="test_hevenu_missions",
                    navigation_intent="creative_missions",
                    active_creative_view="Missions",
                ),
            )
        ptr = get_active_workflow_pointer(session)
        self.assertIsNotNone(ptr)
        assert ptr is not None
        self.assertEqual(ptr.workflow_owner, "mission_jam")
        practice = str(session.get("concert_key") or session.get("display_key") or "")
        self.assertIn("m", practice.lower(), msg=f"expected minor song key, got {practice!r}")

    def test_switch_owner_queues_when_locked_instead_of_crashing(self) -> None:
        session: dict = {
            "_streamlit_widgets_locked_this_run": True,
            "display_key": "D",
            WORKFLOW_MUSICAL_STATES_KEY: {
                "mission_jam": {"display_key": "Em", "concert_key": "Em", "sections": {}},
            },
        }
        switch_workflow_owner(session, "mission_jam")
        self.assertIsNotNone(session.get(PENDING_WORKFLOW_ACTIVATION_KEY))
        self.assertEqual(session.get("display_key"), "D")


if __name__ == "__main__":
    unittest.main()
