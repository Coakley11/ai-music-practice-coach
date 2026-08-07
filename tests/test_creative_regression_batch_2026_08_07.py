"""Regression batch: jam key leak, page refresh, mission generate chord stability."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from creative_chord_selection_authority import (
    global_chord_index_for_section_chord,
    write_authoritative_chord_selection,
)
from creative_key_sync import entry_jam_practice_key_authority_active, resolve_creative_tab_practice_key_token
from improvisation_intelligence_ui import (
    MISSIONS_GENERATE_CONTEXT_KEY,
    _authoritative_practice_chart_key,
    _run_mission_example_generate,
    _stash_missions_generate_context,
)
from improvisation_motif import flatten_section_map, resolve_improv_sections
from music_persistent_state import begin_script_run_navigation_markers
from music_workflow_mutation import update_mission_example_on_blob
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    WorkflowStateBlob,
    save_workflow_blob,
    set_active_workflow_pointer,
)
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav


def _hevenu_session() -> dict[str, Any]:
    import copy

    sections = {
        "Melody A": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
        "Melody B": ["C#m", "G#7", "Bb7", "F#m", "B", "E", "A", "D"],
    }
    return {
        "studio_page": "creative",
        "improv_intelligence_tab": "Missions",
        "display_key": "Dm",
        "concert_key": "Dm",
        "active_catalog_pick_key": "hevenu_shalom",
        "home_sections": copy.deepcopy(sections),
        "improv_song_concert_sections": copy.deepcopy(sections),
        "instrument": "Guitar",
        "level": "Intermediate",
        "focus": "Improvisation",
    }


def _hevenu_ctx() -> Any:
    from improvisation_intelligence import ImprovSessionContext

    sections = {
        "Melody A": ["C#m", "G#7", "C#m", "F#m", "B", "E", "A", "D"],
        "Melody B": ["C#m", "G#7", "Bb7", "F#m", "B", "E", "A", "D"],
    }
    flat = flatten_section_map(list(sections.items()))
    return ImprovSessionContext(
        song_title="Hevenu Shalom Aleichem",
        artist="Traditional",
        key_center="Dm",
        display_key="Dm",
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=72,
        style_label="",
        progression_flat=flat,
        section_order=list(sections.keys()),
    )


class JamKeyMissionLeakTests(unittest.TestCase):
    def test_missions_tab_reclaims_key_from_stale_jam_fields(self) -> None:
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "Eb",
            "display_key": "Dm",
            "concert_key": "Dm",
            "active_catalog_pick_key": "hevenu_shalom",
        }
        self.assertFalse(entry_jam_practice_key_authority_active(session))
        self.assertEqual(resolve_creative_tab_practice_key_token(session), "")
        chart_key = _authoritative_practice_chart_key(session, "Dm")
        self.assertEqual(chart_key, "Dm")


class PageRefreshPersistenceTests(unittest.TestCase):
    def test_hydrated_backing_wins_over_stale_canonical_after_run_boundary(self) -> None:
        session: dict = {
            "_script_run_seq": 20,
            "studio_page": "backing",
            "_music_hydrated_studio_page": "backing",
            "_music_studio_page_restore_projection_complete": True,
            "_suite_page_overwrite_source": "workspace_blob",
            STUDIO_NAV_STATE_KEY: {"studio_page": "practice", "page": "practice"},
        }
        begin_script_run_navigation_markers(session)
        session["_music_studio_page_restore_projection_complete"] = True
        page = prepare_studio_nav(session)
        self.assertEqual(page, "backing")
        self.assertEqual(session.get("studio_page"), "backing")

    def test_top_level_pages_survive_refresh_hydration_matrix(self) -> None:
        pages = ("practice", "picker", "backing", "log", "creative")
        for want in pages:
            with self.subTest(page=want):
                session: dict = {
                    "_script_run_seq": 2,
                    "studio_page": want,
                    "_music_hydrated_studio_page": want,
                    "_suite_page_overwrite_source": "workspace_blob",
                    STUDIO_NAV_STATE_KEY: {"studio_page": "practice", "page": "practice"},
                }
                begin_script_run_navigation_markers(session)
                session["_music_studio_page_restore_projection_complete"] = True
                got = prepare_studio_nav(session)
                self.assertEqual(got, want)
                self.assertEqual(session.get("studio_page"), want)


class MissionGenerateExampleStabilityTests(unittest.TestCase):
    def test_generate_example_does_not_walk_sealed_chord(self) -> None:
        session = _hevenu_session()
        ctx = _hevenu_ctx()
        section_map = resolve_improv_sections(session, ctx)
        gidx = global_chord_index_for_section_chord(section_map, "Melody B", "Bb7")
        assert gidx is not None
        write_authoritative_chord_selection(
            session, section_map, chord_symbol="Bb7", section_label="Melody B", chord_index=gidx
        )
        _stash_missions_generate_context(
            session,
            improv_ctx=ctx,
            section_map=section_map,
            mission="Target Chord Tones",
            cur_chord="Bb7",
            section_label="Melody B",
            chord_idx=gidx,
            live_inst="Guitar",
            live_level="Intermediate",
            live_focus="Improvisation",
            bpm=72,
        )

        def _fake_generate(*args: Any, **kwargs: Any) -> Any:
            from improvisation_missions import MissionExample

            return MissionExample(
                mission=str(kwargs.get("mission") or ""),
                variant="normal",
                chord=str(kwargs.get("chord") or ""),
                section=str(kwargs.get("section") or ""),
                song_title=ctx.song_title,
                display_key=ctx.display_key,
                instrument="Guitar",
                level="Intermediate",
                focus="Improvisation",
                motif={"display": "test", "notes": [], "rhythm": ""},
                abc="",
                tab="",
                piano_html="",
                why="test",
                practice_steps=[],
                insight=None,
                show_tab=False,
                show_piano=False,
            )

        with patch("improvisation_missions.generate_mission_example", side_effect=_fake_generate):
            for _ in range(3):
                _run_mission_example_generate(session, "normal")
        self.assertEqual(session.get("ii_selected_chord"), "Bb7")
        self.assertEqual(int(session.get("ii_selected_chord_index")), gidx)
        snap = session.get(MISSIONS_GENERATE_CONTEXT_KEY)
        self.assertIsInstance(snap, dict)
        assert isinstance(snap, dict)
        self.assertEqual(snap.get("cur_chord"), "Bb7")


class MissionExampleBlobIndexTests(unittest.TestCase):
    def test_example_save_preserves_chord_index_on_blob(self) -> None:
        session: dict = {
            "II_SELECTED_CHORD_INDEX": 4,
            "ii_selected_chord": "Bb7",
        }
        set_active_workflow_pointer(
            session,
            ActiveWorkflowPointer(workflow_owner="mission_jam", workflow_session_id="m1"),
        )
        save_workflow_blob(
            session,
            WorkflowStateBlob(
                workflow_owner="mission_jam",
                workflow_session_id="m1",
                selected_chord_symbol="Bb7",
                selected_chord_index=4,
                selected_section="Melody B",
            ),
        )
        update_mission_example_on_blob(
            session,
            chord="Bb7",
            example_fingerprint="abc123",
            section="Melody B",
        )
        from music_workflow_state_store import get_workflow_blob

        blob = get_workflow_blob(session, "mission_jam", "m1")
        assert blob is not None
        self.assertEqual(blob.selected_chord_symbol, "Bb7")
        self.assertEqual(blob.selected_chord_index, 4)


if __name__ == "__main__":
    unittest.main()
