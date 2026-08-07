"""Shared SongCreativeFocus — cross-tab chord selection (production paths)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from creative_key_sync import prepare_creative_sidebar_display_key
from creative_lifecycle_harness_support import (
    HEVENU_PICK,
    harmony_map_focus_chord,
    mission_select_single_chord,
    restore_song_based_tab,
    simulate_picker_to_creative_handoff,
    song_based_progression_chord_count,
)
from music_persistent_state import prepare_canonical_music_page_state
from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
from song_creative_focus import (
    hydrate_creative_pages_from_song_focus,
    read_harmony_section_selection,
    read_song_creative_focus,
)
from tests.test_creative_catalog_handoff_picker import CATALOG, _stale_canonical_say_session
from tests.test_song_based_minor_practice_key_lifecycle import (
    PK_SAY,
    _hevenu_song_based_session,
    _simulate_pre_widget_consume,
    _simulate_sidebar_key_change,
)


def _hevenu_ebm_session() -> dict[str, Any]:
    session = _hevenu_song_based_session()
    _simulate_sidebar_key_change(session, "Ebm")
    _simulate_pre_widget_consume(session)
    run_pre_widget_application_consumers(session)
    prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
    return session


class TestSongCreativeFocusCrossTabSync(unittest.TestCase):
    def test_missions_bb7_hydrates_harmony_live_motif(self) -> None:
        session = _hevenu_ebm_session()
        prog_before = song_based_progression_chord_count(session)
        mission_select_single_chord(session, chord="Bb7", section="Verse")
        self.assertEqual(str(session.get("harmony_map_chord") or ""), "Bb7")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Bb7")
        focus = read_song_creative_focus(session)
        self.assertIsNotNone(focus)
        assert focus is not None
        self.assertEqual(str(focus.get("selected_concert_chord") or ""), "Bb7")

        session["improv_intelligence_tab"] = "Harmony Map"
        hydrate_creative_pages_from_song_focus(session, tab="Harmony Map")
        self.assertEqual(str(session.get("harmony_map_chord") or ""), "Bb7")

        session["improv_intelligence_tab"] = "Live Coach"
        hydrate_creative_pages_from_song_focus(session, tab="Live Coach")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Bb7")

        session["improv_intelligence_tab"] = "Phrase / Motif"
        hydrate_creative_pages_from_song_focus(session, tab="Phrase / Motif")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Bb7")

        harmony_map_focus_chord(session, chord="Abm", section="Verse")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Abm")
        session["improv_intelligence_tab"] = "Missions"
        hydrate_creative_pages_from_song_focus(session, tab="Missions")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Abm")

        restore_song_based_tab(session)
        self.assertGreaterEqual(song_based_progression_chord_count(session), prog_before)

    def _assert_chord_everywhere(self, session: dict[str, Any], chord: str, *, section: str = "") -> None:
        self.assertEqual(str(session.get("ii_selected_chord") or ""), chord)
        self.assertEqual(str(session.get("harmony_map_chord") or ""), chord)
        focus = read_song_creative_focus(session)
        self.assertIsNotNone(focus)
        assert focus is not None
        self.assertEqual(str(focus.get("selected_concert_chord") or ""), chord)
        if section:
            self.assertEqual(str(focus.get("selected_section_id") or ""), section)
            self.assertEqual(str(session.get("ii_selected_section") or ""), section)

    def test_harmony_map_g7_syncs_live_motif_missions(self) -> None:
        session = _hevenu_ebm_session()
        harmony_map_focus_chord(session, chord="G7", section="Verse")
        self._assert_chord_everywhere(session, "G7", section="Verse")

        for tab in ("Live Coach", "Phrase / Motif", "Missions", "Harmony Map"):
            session["improv_intelligence_tab"] = tab
            hydrate_creative_pages_from_song_focus(session, tab=tab)
            self._assert_chord_everywhere(session, "G7", section="Verse")

    def test_missions_to_harmony_map_reverse_sync(self) -> None:
        session = _hevenu_ebm_session()
        mission_select_single_chord(session, chord="Cmaj7", section="Verse")
        session["improv_intelligence_tab"] = "Harmony Map"
        hydrate_creative_pages_from_song_focus(session, tab="Harmony Map")
        self._assert_chord_everywhere(session, "Cmaj7", section="Verse")
        local = read_harmony_section_selection(session, "Verse")
        self.assertIsNotNone(local)
        self.assertEqual(local[0], "Cmaj7")

    def test_chord_symbol_preserved_across_tabs(self) -> None:
        session = _hevenu_ebm_session()
        home = dict(session.get("home_sections") or {})
        home["Slash"] = ["D/F#", "G7"]
        session["home_sections"] = home
        session["improv_song_concert_sections"] = home
        harmony_map_focus_chord(session, chord="D/F#", section="Slash")
        self._assert_chord_everywhere(session, "D/F#", section="Slash")
        mission_select_single_chord(session, chord="F#m7", section="Verse")
        session["improv_intelligence_tab"] = "Harmony Map"
        hydrate_creative_pages_from_song_focus(session, tab="Harmony Map")
        self._assert_chord_everywhere(session, "F#m7", section="Verse")

    def test_tab_navigation_does_not_revert_harmony_selection(self) -> None:
        session = _hevenu_ebm_session()
        harmony_map_focus_chord(session, chord="Abm", section="Verse")
        for tab in ("Live Coach", "Missions", "Harmony Map"):
            session["improv_intelligence_tab"] = tab
            hydrate_creative_pages_from_song_focus(session, tab=tab)
        self._assert_chord_everywhere(session, "Abm", section="Verse")

    def test_refresh_retains_focus_and_full_progression(self) -> None:
        session = _hevenu_ebm_session()
        mission_select_single_chord(session, chord="Bb7", section="Verse")
        fp = song_based_progression_chord_count(session)
        session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
        run_pre_widget_application_consumers(session)
        prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
        st = MagicMock(session_state=session)
        prepare_creative_sidebar_display_key(st, session)
        self.assertEqual(str(session.get("ii_selected_chord") or ""), "Bb7")
        self.assertGreaterEqual(song_based_progression_chord_count(session), fp)

    def test_stale_focus_rejected_on_song_switch(self) -> None:
        session = _hevenu_ebm_session()
        mission_select_single_chord(session, chord="Bb7", section="Verse")
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_SAY)
        focus = read_song_creative_focus(session)
        self.assertTrue(focus is None or str(focus.get("selected_concert_chord") or "") != "Bb7")

    def test_per_song_focus_isolation(self) -> None:
        hevenu = _hevenu_ebm_session()
        mission_select_single_chord(hevenu, chord="Bb7", section="Verse")
        say = _stale_canonical_say_session()
        simulate_picker_to_creative_handoff(say, catalog=CATALOG, new_pick=PK_SAY)
        say["improv_entry_mode"] = "Song-Based Improvisation"
        mission_select_single_chord(say, chord="G", section="Full Song")
        self.assertEqual(str(hevenu.get("ii_selected_chord") or ""), "Bb7")
        self.assertEqual(str(say.get("ii_selected_chord") or ""), "G")


if __name__ == "__main__":
    unittest.main()
