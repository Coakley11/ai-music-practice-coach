"""Mission example across a Practice Key change, Return to Mission and Return to Creative.

* A Practice Key change must carry the instrument outputs with the staff: Guitar TAB and the Piano guide were
  cleared (and never rebuilt) when the stored example was transposed.
* "Return to Creative" from Mission Backing closes the example (Generate is needed for the next one) but keeps
  the selected chord and the Practice Key; "Return to Mission" is a different path and is not touched.
"""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _run_mission_example_generate
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    _instrument_outputs_for_transposed,
    close_active_mission_example,
    transpose_stored_mission_example,
)
from music_workflow_pending_creative_return import PENDING_CREATIVE_RETURN_KEY, consume_pending_creative_return_handoff


def _session(instrument: str) -> dict:
    return {
        "song": "Shape", "artist": "Artist", "display_key": "Am", "concert_key": "Am", "instrument": instrument,
        "level": "Intermediate", "focus": "Improvisation",
        "improv_active_mission": "Improvise using only chord tones", "improv_mission_pick": "Improvise using only chord tones",
        "home_sections": {"Verse 1": ["Am"]}, "improv_mission_chord_options": ["Am"], "ii_selected_chord_index": 0,
        "ii_selected_chord": "Am", "ii_selected_section": "Verse 1", "backing_track_bpm": 100, "creative_workspace_state": {},
    }


def _ctx(instrument: str) -> ImprovSessionContext:
    return ImprovSessionContext(song_title="Shape", artist="Artist", key_center="Am", display_key="Am", instrument=instrument,
                                level="Intermediate", focus="Improvisation", sections={"Verse 1": ["Am"]})


class TestInstrumentOutputsFollowTheKey(unittest.TestCase):
    def test_guitar_tab_is_rebuilt_and_transposed_with_the_staff(self) -> None:
        session = _session("Guitar")
        _run_mission_example_generate(session, "normal")
        before = session[MISSION_EXAMPLE_KEY]
        self.assertTrue(before["tab"])
        self.assertTrue(transpose_stored_mission_example(session, from_key="Am", to_key="Gm"))
        after = session[MISSION_EXAMPLE_KEY]
        self.assertTrue(after["tab"], "TAB must not be cleared by a Practice Key change")
        self.assertNotEqual(after["tab"], before["tab"])
        self.assertEqual(after["piano_html"], "")
        self.assertTrue(after["abc"].count("K:Gm"))                                # staff and TAB moved together
        self.assertNotEqual(after["motif"]["notes"], before["motif"]["notes"])

    def test_piano_guide_is_rebuilt_with_the_staff(self) -> None:
        session = _session("Piano")
        _run_mission_example_generate(session, "normal")
        before = session[MISSION_EXAMPLE_KEY]
        self.assertTrue(before["piano_html"])
        self.assertTrue(transpose_stored_mission_example(session, from_key="Am", to_key="Gm"))
        after = session[MISSION_EXAMPLE_KEY]
        self.assertTrue(after["piano_html"], "the Piano guide must not be cleared by a Practice Key change")
        self.assertNotEqual(after["piano_html"], before["piano_html"])
        self.assertEqual(after["tab"], "")

    def test_repeated_key_changes_keep_the_outputs(self) -> None:
        session = _session("Guitar")
        _run_mission_example_generate(session, "normal")
        for src, dst in (("Am", "Gm"), ("Gm", "Em"), ("Em", "Am")):
            self.assertTrue(transpose_stored_mission_example(session, from_key=src, to_key=dst))
            self.assertTrue(session[MISSION_EXAMPLE_KEY]["tab"], (src, dst))

    def test_the_stored_flags_decide_when_the_payload_has_no_instrument(self) -> None:
        motif = {"notes": ["A", "C", "E"], "midi": [57, 60, 64], "chord": "Am", "meter": "4/4", "rhythm_symbols": ["♩"] * 3}
        tab, guide = _instrument_outputs_for_transposed({"motif": motif, "show_tab": True, "chord": "Am", "concert_key": "Am"})
        self.assertTrue(tab)
        self.assertEqual(guide, "")
        tab, guide = _instrument_outputs_for_transposed({"motif": motif, "show_piano": True, "chord": "Am", "concert_key": "Am"})
        self.assertEqual(tab, "")
        self.assertTrue(guide)
        self.assertEqual(_instrument_outputs_for_transposed({"motif": motif, "chord": "Am"}), ("", ""))
        self.assertEqual(_instrument_outputs_for_transposed({"motif": {}, "show_tab": True}), ("", ""))
        # the live instrument wins over the flags the example was built with
        tab, guide = _instrument_outputs_for_transposed({"motif": motif, "show_tab": True, "chord": "Am"}, {"instrument": "Piano"})
        self.assertEqual(tab, "")
        self.assertTrue(guide)


class TestCloseActiveMissionExample(unittest.TestCase):
    def _open_session(self) -> dict:
        session = _session("Piano")
        _run_mission_example_generate(session, "normal")
        session[MISSION_PRACTICE_LICK_KEY] = {"motif": {"notes": ["A"], "midi": [57]}, "chord": "Am", "key_center": "Am"}
        session["_studio_page_snapshots"] = {
            "creative": {MISSION_EXAMPLE_KEY: copy.deepcopy(session[MISSION_EXAMPLE_KEY]), "display_key": "Am"},
            "backing": {MISSION_PRACTICE_LICK_KEY: {"motif": {"notes": ["A"]}}, MISSION_EXAMPLE_KEY: {"mission": "m"}},
        }
        return session

    def test_closing_removes_every_copy_but_keeps_the_context(self) -> None:
        from creative_mission_artifact_persistence import canonical_mission_artifact_value

        session = self._open_session()
        self.assertIsNotNone(canonical_mission_artifact_value(session, MISSION_EXAMPLE_KEY))
        self.assertTrue(close_active_mission_example(session))
        for key in (MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY, "_mission_example_output_fp", "_mission_example_artifact_id"):
            self.assertNotIn(key, session)
        self.assertIsNone(canonical_mission_artifact_value(session, MISSION_EXAMPLE_KEY))
        for snap in session["_studio_page_snapshots"].values():
            self.assertNotIn(MISSION_EXAMPLE_KEY, snap)
            self.assertNotIn(MISSION_PRACTICE_LICK_KEY, snap)
        self.assertEqual(session["_studio_page_snapshots"]["creative"]["display_key"], "Am")   # rest of the snapshot untouched
        self.assertEqual((session["ii_selected_chord"], session["ii_selected_section"], session["display_key"], session["concert_key"]),
                         ("Am", "Verse 1", "Am", "Am"))
        self.assertEqual(session["improv_active_mission"], "Improvise using only chord tones")  # which Mission is chosen is context

    def test_closing_twice_is_harmless(self) -> None:
        session = self._open_session()
        self.assertTrue(close_active_mission_example(session))
        self.assertFalse(close_active_mission_example(session))


class TestReturnToCreativeFromBacking(unittest.TestCase):
    def _consume(self, source: str) -> tuple[dict, str]:
        session = _session("Piano")
        _run_mission_example_generate(session, "normal")
        session["_studio_page_snapshots"] = {"creative": {MISSION_EXAMPLE_KEY: copy.deepcopy(session[MISSION_EXAMPLE_KEY])}}
        session[PENDING_CREATIVE_RETURN_KEY] = {"request_seq": 1, "consume_token": "t-" + source,
                                                "sealed_context": {"display_key": "Am", "concert_key": "Am"}}
        with mock.patch("backing_source_navigation.prepare_return_to_backing_source", return_value="creative"), mock.patch(
            "backing_context.get_backing_context", return_value=SimpleNamespace(source=source)
        ):
            phase = consume_pending_creative_return_handoff(session)
        return session, phase

    def test_return_to_creative_from_mission_backing_closes_the_example(self) -> None:
        session, phase = self._consume("mission")
        self.assertEqual(phase, "applied")
        self.assertNotIn(MISSION_EXAMPLE_KEY, session)
        self.assertNotIn(MISSION_EXAMPLE_KEY, session["_studio_page_snapshots"]["creative"])
        self.assertEqual((session["ii_selected_chord"], session["display_key"], session["concert_key"]), ("Am", "Am", "Am"))
        self.assertEqual(session["studio_page"], "creative")

    def test_return_to_creative_from_other_backing_leaves_mission_state_alone(self) -> None:
        session, phase = self._consume("song_improv")
        self.assertEqual(phase, "applied")
        self.assertIn(MISSION_EXAMPLE_KEY, session)


if __name__ == "__main__":
    unittest.main()
