"""Single canonical Creative chord — post-click render and cross-tab authority."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from creative_lifecycle_harness_support import (
    harmony_map_focus_chord,
    mission_select_single_chord,
)
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import (
    II_SELECTED_CHORD,
    II_SELECTED_SECTION,
    _ensure_chord_selection,
    _selected_chord,
)
from improvisation_missions import MISSION_EXAMPLE_KEY, load_mission_example
from improvisation_motif import flatten_section_map, resolve_improv_sections
from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
from song_creative_focus import hydrate_creative_pages_from_song_focus, read_song_creative_focus
from tests.test_song_creative_focus_cross_tab_sync import _hevenu_ebm_session


def _assert_canonical_chord(test: unittest.TestCase, session: dict[str, Any], chord: str, *, section: str = "") -> None:
    test.assertEqual(str(session.get(II_SELECTED_CHORD) or ""), chord)
    test.assertEqual(str(session.get("harmony_map_chord") or ""), chord)
    focus = read_song_creative_focus(session)
    assert focus is not None
    test.assertEqual(str(focus.get("selected_concert_chord") or ""), chord)
    if section:
        test.assertEqual(str(session.get(II_SELECTED_SECTION) or ""), section)
        test.assertEqual(str(focus.get("selected_section_id") or ""), section)


class TestCreativeChordAuthorityLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _hevenu_ebm_session()

    def _ctx(self) -> ImprovSessionContext:
        sections = copy.deepcopy(self.session.get("home_sections") or {})
        return ImprovSessionContext(
            song_title=str(self.session.get("song") or "Song"),
            artist="",
            key_center=str(self.session.get("concert_key") or "Eb"),
            display_key=str(self.session.get("display_key") or "Eb"),
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections=sections,
            bpm=100,
            style_label="",
            progression_flat=[],
            section_order=list(sections.keys()),
        )

    def _section_map(self) -> list[tuple[str, list[str]]]:
        return resolve_improv_sections(self.session, self._ctx())

    def test_ensure_prefers_session_target_over_stale_focus(self) -> None:
        mission_select_single_chord(self.session, chord="Bb7", section="Verse")
        focus = read_song_creative_focus(self.session)
        assert focus is not None
        stale = copy.deepcopy(focus)
        stale["selected_concert_chord"] = "Gm"
        stale["selected_chord_id"] = 0
        from song_creative_focus import SONG_CREATIVE_FOCUS_KEY

        self.session[SONG_CREATIVE_FOCUS_KEY] = stale
        self.session[II_SELECTED_CHORD] = "Abm"
        self.session["ii_selected_chord_index"] = 1
        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        _ensure_chord_selection(self.session, chords, section_map)
        self.assertEqual(str(self.session.get(II_SELECTED_CHORD) or ""), "Abm")

    def test_harmony_g7_all_tabs_same_chord(self) -> None:
        harmony_map_focus_chord(self.session, chord="Bb7", section="Verse")
        _assert_canonical_chord(self, self.session, "Bb7", section="Verse")
        for tab in ("Harmony Map", "Live Coach", "Phrase / Motif", "Missions"):
            self.session["improv_intelligence_tab"] = tab
            hydrate_creative_pages_from_song_focus(self.session, tab=tab)
            section_map = self._section_map()
            chords = flatten_section_map(section_map)
            _ensure_chord_selection(self.session, chords, section_map)
            cur, _ = _selected_chord(self.session, chords)
            self.assertEqual(cur, "Bb7")

    def test_missions_a_harmony_matches(self) -> None:
        mission_select_single_chord(self.session, chord="Abm", section="Verse")
        self.session["improv_intelligence_tab"] = "Harmony Map"
        hydrate_creative_pages_from_song_focus(self.session, tab="Harmony Map")
        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        _ensure_chord_selection(self.session, chords, section_map)
        cur, _ = _selected_chord(self.session, chords)
        self.assertEqual(cur, "Abm")

    def test_live_coach_tile_and_selected_chord_agree(self) -> None:
        from active_musical_workflow_envelope import apply_atomic_mission_chord_selection
        from improvisation_motif import global_chord_index

        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        gidx = 0
        sec = "Verse"
        target = "Abm"
        for si, (label, chs) in enumerate(section_map):
            for ci, ch in enumerate(chs):
                if ch == target:
                    gidx = global_chord_index(section_map, si, ci)
                    sec = label
                    break
        self.session["_streamlit_widgets_locked_this_run"] = True
        apply_atomic_mission_chord_selection(
            self.session,
            chord=target,
            section=sec,
            chord_index=gidx,
            chord_label=f"{sec} · {target}",
            button_key="test_live_fsharpm",
        )
        _ensure_chord_selection(self.session, chords, section_map)
        cur, idx = _selected_chord(self.session, chords)
        self.assertEqual(cur, target)
        self.assertEqual(chords[idx], target)

    def test_mission_chord_change_clears_stale_example_without_refresh(self) -> None:
        mission_select_single_chord(self.session, chord="Ebm", section="Verse")
        ctx = self._ctx()
        self.session[MISSION_EXAMPLE_KEY] = {
            "mission": "Target Chord Tones",
            "chord": "Ebm",
            "section": "Verse",
            "motif": {"display": "old", "notes": [60]},
            "variant": "normal",
        }
        self.session["_streamlit_widgets_locked_this_run"] = True
        mission_select_single_chord(self.session, chord="Bb7", section="Verse")
        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        _ensure_chord_selection(self.session, chords, section_map)
        cur, _ = _selected_chord(self.session, chords)
        self.assertEqual(cur, "Bb7")
        loaded = load_mission_example(self.session, ctx)
        self.assertTrue(loaded is None or str(loaded.chord or "") == "Bb7")

    def test_chord_progression_ebm_bb7_abm(self) -> None:
        sequence = [("Ebm", "Verse"), ("Bb7", "Verse"), ("Abm", "Verse"), ("Ebm", "Verse")]
        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        for sym, sec in sequence:
            harmony_map_focus_chord(self.session, chord=sym, section=sec)
            _ensure_chord_selection(self.session, chords, section_map)
            cur, _ = _selected_chord(self.session, chords)
            self.assertEqual(cur, sym, msg=f"failed at {sym}")

    def test_slash_chord_symbol_exact(self) -> None:
        home = dict(self.session.get("home_sections") or {})
        home["Slash"] = ["D/F#", "G7"]
        self.session["home_sections"] = home
        self.session["improv_song_concert_sections"] = home
        harmony_map_focus_chord(self.session, chord="D/F#", section="Slash")
        self.assertEqual(str(self.session.get(II_SELECTED_CHORD) or ""), "D/F#")
        focus = read_song_creative_focus(self.session)
        assert focus is not None
        self.assertEqual(str(focus.get("selected_concert_chord") or ""), "D/F#")

    def test_refresh_hydration_keeps_canonical_chord(self) -> None:
        harmony_map_focus_chord(self.session, chord="Abm", section="Verse")
        self.session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
        run_pre_widget_application_consumers(self.session)
        section_map = self._section_map()
        chords = flatten_section_map(section_map)
        _ensure_chord_selection(self.session, chords, section_map)
        cur, _ = _selected_chord(self.session, chords)
        self.assertEqual(cur, "Abm")


if __name__ == "__main__":
    unittest.main()
