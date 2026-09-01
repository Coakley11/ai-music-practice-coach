"""Generate Example must not consume stale backing handoffs or navigate to Backing."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _run_mission_example_generate, _stash_missions_generate_context
from improvisation_missions import MISSION_EXAMPLE_FRESH_RUN_KEY, MISSION_EXAMPLE_KEY
from music_workflow_backing_mixed_context_guard import evaluate_backing_mixed_mission_catalog_context
from music_workflow_pending_backing_handoff import (
    PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY,
    PENDING_BACKING_WORKFLOW_KEY,
    arm_pending_backing_handoff_consume,
    consume_pending_backing_workflow_handoff,
    peek_pending_backing_workflow_handoff,
    queue_pending_backing_workflow_handoff,
)
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from tests.test_missions_generate_new_idea_double_render import _ctx, _session


class TestMissionGenerateExampleNoBackingNavigation(unittest.TestCase):
    def _mission_ready_session(self) -> dict[str, Any]:
        session = _session()
        ctx = _ctx()
        section_map = [("Chorus", ["Em"])]
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
        blob = WorkflowStateBlob(
            workflow_owner="mission_jam",
            workflow_session_id="mission|catalog|test_song",
            keys=KeyAuthority(practice_tonic="E", practice_mode="minor"),
            selected_chord_symbol="Em",
            mission_type=str(session["improv_mission_pick"]),
        )
        save_workflow_blob(session, blob, source="t")
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="mission|catalog|test_song"),
            source="t",
        )
        session.setdefault("studio_page", "creative")
        session.setdefault("improv_intelligence_tab", "Missions")
        return session

    def test_generate_clears_unarmed_stale_pending_handoff(self) -> None:
        session = self._mission_ready_session()
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        self.assertIsNotNone(peek_pending_backing_workflow_handoff(session))
        _run_mission_example_generate(session, "normal")
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")

    def test_consume_skips_when_mission_example_fresh_run(self) -> None:
        session = self._mission_ready_session()
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        arm_pending_backing_handoff_consume(session)
        session[MISSION_EXAMPLE_FRESH_RUN_KEY] = True
        with mock.patch("studio_nav_history.navigate_studio_page") as nav:
            phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "skipped")
        nav.assert_not_called()
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))

    def test_unarmed_pending_not_consumed_on_refresh(self) -> None:
        session: dict = {"studio_page": "creative"}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "skipped")
        activate.assert_not_called()
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))

    def test_generate_produces_example_without_backing_page(self) -> None:
        session = self._mission_ready_session()
        _run_mission_example_generate(session, "normal")
        self.assertIsInstance(session.get(MISSION_EXAMPLE_KEY), dict)
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertNotEqual(session.get("studio_page"), "backing")

    def test_mixed_mission_catalog_context_blocked(self) -> None:
        session = self._mission_ready_session()
        session["studio_page"] = "backing"
        session[MISSION_EXAMPLE_KEY] = {"chord": "Em", "mission": "Rhythm-first, note-second"}
        try:
            from backing_context import BACKING_CONTEXT_KEY, BackingContext, set_backing_context

            set_backing_context(
                session,
                BackingContext(
                    source="regular_song",
                    source_label="Catalog song",
                    active_song_id="test_song",
                    song_title="Test Song",
                    key="Em",
                    display_key="Em",
                    concert_key="Em",
                    bpm=100,
                    style="Pop",
                    groove="Straight",
                ),
            )
        except ImportError:
            session[BACKING_CONTEXT_KEY] = {"source": "regular_song", "source_label": "Catalog song"}
        result = evaluate_backing_mixed_mission_catalog_context(session)
        self.assertTrue(result.blocked)
        self.assertEqual(result.code, "MIXED_BACKING_MISSION_CATALOG_CONTEXT")

    def test_armed_mission_handoff_still_consumes(self) -> None:
        session: dict = {"studio_page": "creative", "improv_entry_mode": "Song-Based Improvisation"}
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        arm_pending_backing_handoff_consume(session)
        self.assertIsNotNone(session.get(PENDING_BACKING_WORKFLOW_CONSUME_ARMED_SEQ_KEY))
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch("backing_context.open_backing_from_creative"):
                phase = consume_pending_backing_workflow_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "backing")

    def test_generate_does_not_write_instantiated_tab_widget(self) -> None:
        class _WidgetLockedSession(dict):
            def __setitem__(self, key: str, value: Any) -> None:
                if key == "improv_intelligence_tab":
                    raise AssertionError(
                        "must not write instantiated widget key improv_intelligence_tab"
                    )
                super().__setitem__(key, value)

        session = _WidgetLockedSession(self._mission_ready_session())
        queue_pending_backing_workflow_handoff(
            session,
            backing_source="mission",
            workflow_owner="mission_jam",
        )
        tab_before = session.get("improv_intelligence_tab")
        from music_workflow_pending_backing_handoff import (
            clear_stale_backing_handoff_for_mission_example_generate,
        )

        clear_stale_backing_handoff_for_mission_example_generate(session)
        self.assertEqual(session.get("improv_intelligence_tab"), tab_before)
        self.assertIsNone(peek_pending_backing_workflow_handoff(session))

        for variant in ("normal", "easier", "harder", "new"):
            locked = _WidgetLockedSession(self._mission_ready_session())
            dict.__setitem__(locked, "_streamlit_widgets_locked_this_run", True)
            _run_mission_example_generate(locked, variant)
            self.assertEqual(locked.get("improv_intelligence_tab"), "Missions")
            self.assertIsInstance(locked.get(MISSION_EXAMPLE_KEY), dict)

    def test_leaving_backing_queues_pending_missions_tab_not_widget(self) -> None:
        class _WidgetLockedSession(dict):
            def __setitem__(self, key: str, value: Any) -> None:
                if key == "improv_intelligence_tab":
                    raise AssertionError(
                        "must not write instantiated widget key improv_intelligence_tab"
                    )
                super().__setitem__(key, value)

        session = _WidgetLockedSession(self._mission_ready_session())
        dict.__setitem__(session, "studio_page", "backing")
        dict.__setitem__(session, "_streamlit_widgets_locked_this_run", True)
        from music_workflow_pending_backing_handoff import (
            clear_stale_backing_handoff_for_mission_example_generate,
        )

        clear_stale_backing_handoff_for_mission_example_generate(session)
        self.assertEqual(session.get("studio_page"), "creative")
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(session.get("_pending_improv_intelligence_tab"), "Missions")
        self.assertEqual(session.get("creative_improv_intelligence_tab"), "Missions")

    def test_generate_keeps_clicked_em_not_stale_index_g(self) -> None:
        session = self._mission_ready_session()
        verse = ["Bm", "Em", "G", "A"]
        session["home_sections"] = {"Verse 1": list(verse)}
        session["improv_mission_chord_options"] = list(verse)
        session["ii_selected_chord"] = "Em"
        session["ii_selected_section"] = "Verse 1"
        session["ii_selected_chord_index"] = 2
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["_mission_chord_click_authority"] = {
            "chord": "Em",
            "section": "Verse 1",
            "chord_index": 1,
            "practice_key": "Bm",
        }
        ctx = ImprovSessionContext(
            song_title="Shape of You",
            artist="Ed Sheeran",
            key_center="Bm",
            display_key="Bm",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Verse 1": list(verse)},
            bpm=100,
            style_label="Pop",
            progression_flat=list(verse),
            section_order=["Verse 1"],
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=[("Verse 1", list(verse))],
            mission=session["improv_mission_pick"],
            cur_chord="Em",
            section_label="Verse 1",
            chord_idx=2,
            live_inst="Piano",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=100,
        )
        _run_mission_example_generate(session, "normal")
        example = session.get(MISSION_EXAMPLE_KEY) or {}
        self.assertEqual(str(example.get("chord") or ""), "Em")
        self.assertNotEqual(str(example.get("chord") or ""), "G")
        self.assertEqual(session.get("ii_selected_chord"), "Em")


if __name__ == "__main__":
    unittest.main()
