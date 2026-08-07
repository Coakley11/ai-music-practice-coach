"""Song-Based Improvisation Full Song scope + Return to Creative defaults."""

from __future__ import annotations

import copy
import unittest
from typing import Any
from unittest import mock

from backing_context import BackingContext, set_backing_context
from backing_source_navigation import prepare_return_to_backing_source, restore_session_widgets_from_backing_context
from music_workflow_pending_creative_return import (
    PENDING_CREATIVE_RETURN_KEY,
    consume_pending_creative_return_handoff,
)
from practice_studio import PRACTICE_FOCUS_FULL, practice_is_full_song
from song_improv_scope_authority import (
    SONG_IMPROV_PLAYBACK_FULL,
    apply_song_improv_entry_defaults,
    ensure_song_improv_scope_on_entry_mode,
    reset_song_improv_playback_scope,
)
from tests.test_creative_catalog_handoff_picker import CATALOG, PK_OTHER, simulate_picker_to_creative_handoff
from tests.test_song_based_minor_practice_key_lifecycle import _hevenu_song_based_session


def _mission_bridge_session() -> dict[str, Any]:
    session = _hevenu_song_based_session()
    session["ii_selected_section"] = "Bridge"
    session["backing_track_scope"] = "Selected sections"
    session["backing_track_single_section"] = "Bridge"
    session["backing_track_multi_sections"] = ["Bridge"]
    session["practice_focus_section"] = "Bridge"
    session["improv_intelligence_tab"] = "Missions"
    return session


class TestSongImprovScopeAuthority(unittest.TestCase):
    def test_entry_defaults_full_song(self) -> None:
        session = _mission_bridge_session()
        apply_song_improv_entry_defaults(session, source="test")
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))
        self.assertNotIn("backing_track_single_section", session)

    def test_ensure_once_per_run(self) -> None:
        session = _mission_bridge_session()
        session["_script_run_seq"] = 7
        session["improv_entry_mode"] = "Song-Based Improvisation"
        ensure_song_improv_scope_on_entry_mode(session)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))
        session["practice_focus_section"] = "Bridge"
        ensure_song_improv_scope_on_entry_mode(session)
        self.assertEqual(str(session.get("practice_focus_section") or ""), "Bridge")

    def test_full_song_bridge_full_song_toggle(self) -> None:
        from practice_state import coerce_practice_focus_for_widget

        sections = {"Bridge": ["Am", "G"], "Verse": ["C", "G"]}
        from practice_studio import practice_section_options

        choices = practice_section_options(sections)
        session: dict[str, Any] = {"practice_focus_section": PRACTICE_FOCUS_FULL}
        coerce_practice_focus_for_widget(session, choices)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))
        session["practice_focus_section"] = "Bridge"
        coerce_practice_focus_for_widget(session, choices)
        self.assertEqual(str(session.get("practice_focus_section") or ""), "Bridge")
        session["practice_focus_section"] = PRACTICE_FOCUS_FULL
        coerce_practice_focus_for_widget(session, choices)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))

    def test_return_from_song_improv_backing_resets_scope_and_tab(self) -> None:
        session = _mission_bridge_session()
        session["studio_page"] = "backing"
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based",
            active_song_id="Jewish|Hevenu",
            song_title="Hevenu",
            key="C#m",
            display_key="C#m",
            concert_key="C#m",
            bpm=100,
            style="",
            groove="Auto",
            scope="Selected sections",
            section="Bridge",
            sections=["Bridge"],
            entry_mode="Song-Based Improvisation",
        )
        set_backing_context(session, ctx)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            prepare_return_to_backing_source(session)
        self.assertEqual(str(session.get("improv_intelligence_tab") or ""), "Entry & Jam")
        self.assertEqual(str(session.get("improv_entry_mode") or ""), "Song-Based Improvisation")
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)

    def test_consume_return_handoff_song_improv(self) -> None:
        session = _mission_bridge_session()
        session["studio_page"] = "backing"
        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based",
            active_song_id="pick",
            song_title="Song",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=100,
            style="",
            groove="Auto",
            scope="Full song",
            entry_mode="Song-Based Improvisation",
        )
        set_backing_context(session, ctx)
        session[PENDING_CREATIVE_RETURN_KEY] = {
            "request_seq": 1,
            "consume_token": "t2",
            "sealed_context": {},
        }
        with mock.patch(
            "backing_source_navigation.prepare_return_to_backing_source",
            return_value="creative",
        ):
            phase = consume_pending_creative_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))

    def test_catalog_song_change_resets_scope(self) -> None:
        session = _mission_bridge_session()
        home = copy.deepcopy(session.get("home_sections") or {})
        simulate_picker_to_creative_handoff(session, catalog=CATALOG, new_pick=PK_OTHER)
        self.assertEqual(str(session.get("backing_track_scope") or ""), SONG_IMPROV_PLAYBACK_FULL)
        self.assertTrue(practice_is_full_song(session.get("practice_focus_section")))


class TestDiatonicScaleSpellingExtended(unittest.TestCase):
    def test_e_dorian_diatonic(self) -> None:
        from improvisation_intelligence import build_scale_suggestion

        sug = build_scale_suggestion("E dorian", reference_key="Em")
        self.assertEqual(sug.notes, ["E", "F#", "G", "A", "B", "C#", "D"])

    def test_e_melodic_minor_diatonic(self) -> None:
        from improvisation_intelligence import build_scale_suggestion

        sug = build_scale_suggestion("E melodic minor", reference_key="Em")
        self.assertEqual(sug.notes, ["E", "F#", "G", "A", "B", "C#", "D#"])

    def test_g_dorian_still_bb(self) -> None:
        from harmonic_spelling import build_scale_suggestion_for_chord

        sug = build_scale_suggestion_for_chord("G dorian", chord_symbol="Gm", reference_key="Gm")
        self.assertIn("Bb", " ".join(sug.notes))
        self.assertNotIn("A#", " ".join(sug.notes))


if __name__ == "__main__":
    unittest.main()
