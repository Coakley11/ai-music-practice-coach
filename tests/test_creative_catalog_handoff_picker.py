"""Catalog Song Selection → Creative handoff (Say saved, new pick, enter Creative)."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from active_song_state import write_canonical_active_song_state
from creative_catalog_handoff_test_support import (
    assert_catalog_parent_chain_agrees,
    collect_handoff_identity,
    progression_fingerprint,
    record_handoff_phase_trace,
    say_stale_progression_fingerprint,
)
from creative_lifecycle_harness_support import (
    HEVENU_PICK,
    HEVENU_TITLE,
    PK_SAY_POP,
    harmony_map_focus_chord,
    mission_select_single_chord,
    restore_song_based_tab,
    seed_say_song_based_creative_state,
    simulate_picker_to_creative_handoff,
)
from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
from song_catalog.catalog import format_pick_key
from songs.state import ACTIVE_CATALOG_PICK_KEY

PK_OTHER = format_pick_key("Pop", "Song B — Artist B")
SAY_FP = say_stale_progression_fingerprint(144)

CATALOG = {
    "Pop": {
        "Say — John Mayer": {
            "title": "Say",
            "artist": "John Mayer",
            "key": "G",
            "genre": "Pop",
            "sections": {"Chorus": ["G", "C", "Em", "D"]},
        },
        "Song B — Artist B": {
            "title": "Song B",
            "artist": "Artist B",
            "key": "C",
            "genre": "Pop",
            "sections": {"Verse": ["C", "F", "G"]},
        },
    },
    "Jewish": {
        "Hevenu Shalom Aleichem — Traditional": {
            "title": HEVENU_TITLE,
            "artist": "Traditional",
            "key": "Dm",
            "genre": "Jewish",
            "sections": {"Verse": ["Dm", "Gm", "A7", "Dm"]},
        },
    },
}


def _stale_canonical_say_session() -> dict:
    session: dict = {}
    seed_say_song_based_creative_state(session, say_pick=PK_SAY_POP, section_count=144)
    write_canonical_active_song_state(
        session,
        {
            "pick_key": PK_SAY_POP,
            "selected_song": copy.deepcopy(session["selected_song"]),
            "music_source": "catalog",
            "display_key": "G",
        },
        reason="harness_stale_canonical",
        apply_global_controls_to_session=False,
    )
    session["_cloud_workspace_restored_this_run"] = True
    session["_music_restore_phase_complete"] = True
    session["_music_startup_restore_finalized"] = True
    session["_music_workspace_blob_hydrated"] = True
    session["_script_run_seq"] = 1
    record_handoff_phase_trace(session, "seed_stale_say_canonical", pick=PK_SAY_POP)
    return session


def _enter_song_based_tab(session: dict) -> None:
    session["improv_entry_mode"] = "Song-Based Improvisation"
    session["improv_intelligence_tab"] = "Entry & Jam"
    try:
        from music_workflow_creative_nav import ensure_creative_tab_workflow_before_widgets

        ensure_creative_tab_workflow_before_widgets(session)
    except ImportError:
        pass
    record_handoff_phase_trace(session, "song_based_tab")


def _simulate_refresh(session: dict) -> None:
    session["_script_run_seq"] = int(session.get("_script_run_seq") or 0) + 1
    session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
    session.pop("_music_canonical_prepared_for_run", None)
    from music_persistent_state import prepare_canonical_music_page_state
    from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers

    run_pre_widget_application_consumers(session)
    prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
    record_handoff_phase_trace(session, "refresh_simulation")


class TestCreativeCatalogHandoffPicker(unittest.TestCase):
    def test_say_saved_select_hevenu_creative_handoff(self) -> None:
        session = _stale_canonical_say_session()
        record_handoff_phase_trace(session, "after_picker_choice", pick=HEVENU_PICK)
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        ident = assert_catalog_parent_chain_agrees(session, HEVENU_PICK)
        self.assertEqual(ident["selected_song_title"], HEVENU_TITLE)
        self.assertNotEqual(ident["progression_fingerprint"], SAY_FP)
        self.assertNotEqual(ident["progression_chord_count"], 144)

    def test_hevenu_saved_select_other_catalog_song(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)
        session["studio_page"] = "picker"
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_OTHER)
        ident = assert_catalog_parent_chain_agrees(session, PK_OTHER)
        self.assertEqual(ident["selected_song_title"], "Song B")
        self.assertNotEqual(ident["progression_fingerprint"], SAY_FP)

    def test_song_based_tab_after_switch(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        _enter_song_based_tab(session)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)

    def test_refresh_retains_new_song(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        _simulate_refresh(session)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)

    def test_mission_tab_return_retains_pick(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        mission_select_single_chord(session, chord="Dm", section="Verse")
        restore_song_based_tab(session)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)

    def test_harmony_tab_return_retains_pick(self) -> None:
        session = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        harmony_map_focus_chord(session, chord="Gm", section="Verse")
        restore_song_based_tab(session)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)

    def test_reselect_original_say_restores_say_snapshot(self) -> None:
        session = _stale_canonical_say_session()
        say_fp_before = progression_fingerprint(session.get("improv_song_concert_sections") or {})
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=HEVENU_PICK)
        assert_catalog_parent_chain_agrees(session, HEVENU_PICK)
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_SAY_POP)
        ident = assert_catalog_parent_chain_agrees(session, PK_SAY_POP)
        self.assertEqual(ident["selected_song_title"], "Say")
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, "song_based_improvisation", ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(str(blob.song_id or ""), PK_SAY_POP)
        if say_fp_before:
            self.assertEqual(ident["progression_fingerprint"], say_fp_before)


if __name__ == "__main__":
    unittest.main()
