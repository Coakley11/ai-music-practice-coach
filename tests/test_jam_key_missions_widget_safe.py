"""Jam key ownership must not assign widget-bound session keys after sidebar render."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from generated_jam_key_context import (
    GENERATED_JAM_KEY_CONTEXT_KEY,
    SONG_PRACTICE_KEY_SNAPSHOT_KEY,
    activate_generated_jam_key_ownership,
    deactivate_generated_jam_key_ownership,
    generated_jam_owns_practice_key,
)
from mission_workflow_context import reconcile_missions_workflow_context
from songs.key_state import PENDING_DISPLAY_KEY


def _hevenu_session(*, jam_tonic: str = "E") -> dict[str, Any]:
    return {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_key": jam_tonic,
        "display_key": jam_tonic,
        "concert_key": jam_tonic,
        "active_catalog_pick_key": "Traditional::Hevenu Shalom Aleichem",
        "song": "Hevenu Shalom Aleichem",
        SONG_PRACTICE_KEY_SNAPSHOT_KEY: {
            "display_key": "Dm",
            "concert_key": "Dm",
            "practice_concert_key": "Dm",
        },
    }


class _TrackDisplayAssigns(dict):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.display_assigns: list[Any] = []

    def __setitem__(self, key: str, val: Any) -> None:
        if key == "display_key":
            self.display_assigns.append(val)
        super().__setitem__(key, val)


class JamKeyMissionsWidgetSafeTests(unittest.TestCase):
    def test_deactivate_locked_does_not_assign_display_key_directly(self) -> None:
        session = _hevenu_session()
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = {
            "key_owner": "jam_session_generator",
            "entry_mode": "Jam Session Generator",
        }
        session["_streamlit_widgets_locked_this_run"] = True
        ok = deactivate_generated_jam_key_ownership(session, pre_widget=True)
        self.assertTrue(ok)
        self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)
        self.assertEqual(session.get("concert_key"), "Dm")
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "Dm")
        self.assertEqual(session.get("display_key"), "E")

    def test_deactivate_without_pre_widget_defers_when_locked(self) -> None:
        session = _hevenu_session()
        session[GENERATED_JAM_KEY_CONTEXT_KEY] = {"key_owner": "jam_session_generator"}
        session["_streamlit_widgets_locked_this_run"] = True
        self.assertFalse(deactivate_generated_jam_key_ownership(session))
        self.assertIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)

    def test_missions_reconcile_locked_no_streamlit_assign_to_display_key(self) -> None:
        session = _TrackDisplayAssigns(_hevenu_session())
        activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator", practice_key="E")
        session["_streamlit_widgets_locked_this_run"] = True
        session["display_key"] = "E"
        session.display_assigns.clear()
        improv_ctx = mock.Mock(
            sections={"Verse": ["Dm"]},
            section_order=["Verse"],
            song_title="Hevenu Shalom Aleichem",
            key_center="Dm",
            display_key="Dm",
        )
        reconcile_missions_workflow_context(
            session,
            improv_ctx,
            mission="chord_tones",
            cur_chord="Dm",
            section_label="Verse",
        )
        self.assertEqual(session.display_assigns, [])
        self.assertNotIn(GENERATED_JAM_KEY_CONTEXT_KEY, session)

    def test_jam_to_missions_restores_song_snapshot_via_pending(self) -> None:
        session = _hevenu_session()
        activate_generated_jam_key_ownership(session, entry_mode="Jam Session Generator", practice_key="E")
        session["_streamlit_widgets_locked_this_run"] = True
        deactivate_generated_jam_key_ownership(session, pre_widget=True)
        self.assertFalse(generated_jam_owns_practice_key(session))
        self.assertEqual(session.get(PENDING_DISPLAY_KEY), "Dm")


if __name__ == "__main__":
    unittest.main()
