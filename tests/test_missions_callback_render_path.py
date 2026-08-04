"""Real widget callback + second render for Missions example buttons."""

from __future__ import annotations

import unittest
from unittest import mock

import streamlit

import improvisation_intelligence_ui as ui
from improvisation_intelligence_ui import (
    MISSIONS_GENERATE_CONTEXT_KEY,
    _on_mission_gen_normal,
    _on_mission_gen_new_idea,
    _stash_missions_generate_context,
)
from improvisation_missions import MISSION_EXAMPLE_GEN_DIAG_KEY, MISSION_EXAMPLE_KEY
from tests.test_missions_generate_new_idea_double_render import (
    _ctx,
    _render_missions,
    _session,
)


class TestMissionsCallbackRenderPath(unittest.TestCase):
    def test_generate_callback_without_home_sections_uses_stashed_context(self) -> None:
        session = _session()
        session.pop("home_sections", None)
        ctx = _ctx()
        section_map = {"Chorus": ["Em"]}
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Chorus", ["Em"])],
            mission=session["improv_mission_pick"],
            cur_chord="Em",
            section_label="Chorus",
            chord_idx=0,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        with mock.patch.object(streamlit, "session_state", session, create=True):
            _on_mission_gen_normal()
        self.assertIsInstance(session.get(MISSION_EXAMPLE_KEY), dict)
        self.assertFalse((session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}).get("abort"))

    def test_callback_then_second_render_shows_new_notes(self) -> None:
        session = _session()
        ctx = _ctx()
        section_map = {"Chorus": ["Em"]}
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Chorus", ["Em"])],
            mission=session["improv_mission_pick"],
            cur_chord="Em",
            section_label="Chorus",
            chord_idx=0,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        with mock.patch.object(streamlit, "session_state", session, create=True):
            _on_mission_gen_normal()
        session[ui.MISSION_EXAMPLE_FRESH_RUN_KEY] = True
        first = _render_missions(session)
        notes1 = first.notes_display()
        self.assertTrue(notes1)

        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=section_map,
            mission=session["improv_mission_pick"],
            cur_chord="Em",
            section_label="Chorus",
            chord_idx=0,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        with mock.patch.object(streamlit, "session_state", session, create=True):
            _on_mission_gen_new_idea()
        session[ui.MISSION_EXAMPLE_FRESH_RUN_KEY] = True
        second = _render_missions(session)
        notes2 = second.notes_display()
        self.assertNotEqual(notes1, notes2)

    def test_generate_context_required_when_session_sections_missing(self) -> None:
        session = _session()
        session.pop("home_sections", None)
        session.pop(MISSIONS_GENERATE_CONTEXT_KEY, None)
        ui._run_mission_example_generate(session, "normal")
        self.assertEqual((session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}).get("abort"), "no_chords")


if __name__ == "__main__":
    unittest.main()
