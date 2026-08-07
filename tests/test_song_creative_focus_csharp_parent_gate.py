"""Preview gate: C# minor parent + G#7 focus (Hevenu transposed progression)."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock

from creative_key_sync import prepare_creative_sidebar_display_key
from creative_lifecycle_harness_support import (
    harmony_map_focus_chord,
    mission_select_single_chord,
    restore_song_based_tab,
    song_based_progression_chord_count,
)
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import (
    MISSIONS_GENERATE_CONTEXT_KEY,
    MISSION_EXAMPLE_GEN_DIAG_KEY,
    _authoritative_practice_chart_key,
    _motif_notation_reference_key,
    _run_mission_example_generate,
)
from improvisation_missions import load_mission_example
from improvisation_motif import flatten_section_map, resolve_improv_sections
from music_persistent_state import prepare_canonical_music_page_state
from music_workflow_pre_widget_bootstrap import run_pre_widget_application_consumers
from song_creative_focus import hydrate_creative_pages_from_song_focus, read_song_creative_focus
from tests.test_creative_catalog_handoff_picker import CATALOG
from tests.test_song_based_minor_practice_key_lifecycle import (
    _hevenu_song_based_session,
    _simulate_pre_widget_consume,
    _simulate_sidebar_key_change,
)

LIVE_FOCUS_CHORD = "G#7"
LIVE_PARENT_KEY = "C#m"
HEVENU_CSHARP_PROGRESSION = ("C#m", "F#m", "G#7", "C#m")


def _c_sharp_minor_hevenu_session() -> dict[str, Any]:
    session = _hevenu_song_based_session()
    _simulate_sidebar_key_change(session, LIVE_PARENT_KEY)
    _simulate_pre_widget_consume(session)
    run_pre_widget_application_consumers(session)
    prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
    st = MagicMock(session_state=session)
    prepare_creative_sidebar_display_key(st, session)
    return session


def _improv_ctx(session: dict[str, Any]) -> ImprovSessionContext:
    from improvisation_intelligence_ui import _authoritative_concert_sections

    sections = _authoritative_concert_sections(session, session.get("home_sections") or {})
    chart_key = _authoritative_practice_chart_key(session, str(session.get("display_key") or "C"))
    return ImprovSessionContext(
        song_title=str(session.get("song") or "Song"),
        artist=str(session.get("artist") or ""),
        key_center=str(session.get("concert_key") or chart_key),
        display_key=chart_key,
        instrument="Guitar",
        level="Intermediate",
        focus="Improvisation",
        sections=sections,
        bpm=100,
        style_label="",
        progression_flat=[],
        section_order=list(sections.keys()),
    )


def _find_chord(session: dict[str, Any], symbol: str) -> tuple[str, int]:
    sections = session.get("improv_song_concert_sections") or {}
    if not isinstance(sections, dict):
        return "", 0
    offset = 0
    for label, chs in sections.items():
        if not isinstance(chs, list):
            continue
        for i, ch in enumerate(chs):
            if str(ch) == symbol:
                return str(label), offset + i
        offset += len(chs)
    return "", 0


class TestSongCreativeFocusCsharpParentGate(unittest.TestCase):
    def test_practice_key_csharp_missions_without_refresh(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        session["improv_intelligence_tab"] = "Missions"
        hydrate_creative_pages_from_song_focus(session, tab="Missions")
        self.assertEqual(_authoritative_practice_chart_key(session, "Dm"), LIVE_PARENT_KEY)

    def test_resolve_improv_sections_match_live_progression(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        ctx = _improv_ctx(session)
        chords = flatten_section_map(resolve_improv_sections(session, ctx))
        for sym in HEVENU_CSHARP_PROGRESSION:
            self.assertIn(sym, chords)

    def test_live_sequence_csharp_parent_gsharp7_focus(self) -> None:
        session = _c_sharp_minor_hevenu_session()
        self.assertEqual(_authoritative_practice_chart_key(session, "Dm"), LIVE_PARENT_KEY)

        session["improv_intelligence_tab"] = "Missions"
        hydrate_creative_pages_from_song_focus(session, tab="Missions")

        g7_section, g7_gidx = _find_chord(session, LIVE_FOCUS_CHORD)
        self.assertTrue(g7_section, msg=f"missing {LIVE_FOCUS_CHORD} in concert map")
        mission_select_single_chord(session, chord=LIVE_FOCUS_CHORD, section=g7_section)
        focus = read_song_creative_focus(session)
        self.assertIsNotNone(focus)
        assert focus is not None
        self.assertEqual(str(focus.get("selected_concert_chord") or ""), LIVE_FOCUS_CHORD)

        session["improv_intelligence_tab"] = "Harmony Map"
        hydrate_creative_pages_from_song_focus(session, tab="Harmony Map")
        self.assertEqual(str(session.get("harmony_map_chord") or ""), LIVE_FOCUS_CHORD)

        f_section, _ = _find_chord(session, "F#m")
        self.assertTrue(f_section)
        harmony_map_focus_chord(session, chord="F#m", section=f_section)
        focus_alt = read_song_creative_focus(session)
        assert focus_alt is not None
        self.assertEqual(str(focus_alt.get("selected_concert_chord") or ""), "F#m")

        harmony_map_focus_chord(session, chord=LIVE_FOCUS_CHORD, section=g7_section)
        focus = read_song_creative_focus(session)
        assert focus is not None
        self.assertEqual(str(focus.get("selected_concert_chord") or ""), LIVE_FOCUS_CHORD)

        ctx = _improv_ctx(session)
        section_map = resolve_improv_sections(session, ctx)
        chords = flatten_section_map(section_map)
        session["improv_intelligence_tab"] = "Live Coach"
        hydrate_creative_pages_from_song_focus(session, tab="Live Coach")
        self.assertEqual(_authoritative_practice_chart_key(session, ctx.display_key), LIVE_PARENT_KEY)
        cur = str(session.get("ii_selected_chord") or session.get("II_SELECTED_CHORD") or "")
        self.assertEqual(cur, LIVE_FOCUS_CHORD)
        analysis_ref = _motif_notation_reference_key(ctx, cur)
        self.assertNotEqual(analysis_ref, LIVE_PARENT_KEY)

        session["improv_intelligence_tab"] = "Phrase / Motif"
        hydrate_creative_pages_from_song_focus(session, tab="Phrase / Motif")
        self.assertEqual(str(session.get("ii_selected_chord") or ""), LIVE_FOCUS_CHORD)
        motif_ref = _motif_notation_reference_key(ctx, LIVE_FOCUS_CHORD)
        self.assertTrue(motif_ref)

        prog_before = song_based_progression_chord_count(session)
        session["improv_mission_pick"] = "Target Chord Tones"
        session["improv_active_mission"] = "Target Chord Tones"
        session[MISSIONS_GENERATE_CONTEXT_KEY] = {
            "mission": "Target Chord Tones",
            "cur_chord": LIVE_FOCUS_CHORD,
            "section_label": g7_section,
            "chord_idx": g7_gidx,
            "live_inst": "Guitar",
            "live_level": "Intermediate",
            "live_focus": "Improvisation",
            "bpm": 100,
            "improv_ctx": {
                "song_title": ctx.song_title,
                "display_key": ctx.display_key,
                "sections": section_map,
            },
        }
        _run_mission_example_generate(session, "normal")
        focus_after = read_song_creative_focus(session)
        assert focus_after is not None
        self.assertEqual(str(focus_after.get("selected_concert_chord") or ""), LIVE_FOCUS_CHORD)
        diag = session.get(MISSION_EXAMPLE_GEN_DIAG_KEY) or {}
        self.assertEqual(str(diag.get("chord") or ""), LIVE_FOCUS_CHORD)
        self.assertEqual(str(diag.get("parent_practice_key") or ""), LIVE_PARENT_KEY)
        loaded = load_mission_example(session, ctx)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(str(loaded.chord or ""), LIVE_FOCUS_CHORD)

        restore_song_based_tab(session)
        self.assertGreaterEqual(song_based_progression_chord_count(session), prog_before)
        self.assertGreaterEqual(song_based_progression_chord_count(session), len(HEVENU_CSHARP_PROGRESSION))

        session.pop("_music_pre_widget_bootstrap_ran_this_run", None)
        run_pre_widget_application_consumers(session)
        prepare_canonical_music_page_state(session, song_picker_catalog=CATALOG, force=True)
        st = MagicMock(session_state=session)
        prepare_creative_sidebar_display_key(st, session)
        self.assertEqual(_authoritative_practice_chart_key(session, "Dm"), LIVE_PARENT_KEY)
        focus_refresh = read_song_creative_focus(session)
        assert focus_refresh is not None
        self.assertEqual(str(focus_refresh.get("selected_concert_chord") or ""), LIVE_FOCUS_CHORD)


if __name__ == "__main__":
    unittest.main()
