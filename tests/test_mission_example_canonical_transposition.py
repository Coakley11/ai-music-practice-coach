"""The Mission example is derived from an immutable canonical copy, never from its previous projection.

Before: every Practice Key change transposed the *previous* copy by an ascending 0-11 interval, so
G -> A -> Bb -> G (2 + 1 + 9 = 12 semitones) came back one octave higher.
"""

from __future__ import annotations

import copy
import unittest

from improvisation_intelligence_ui import _run_mission_example_generate
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    _CANON_KEY,
    _nearest_steps,
    load_mission_example,
    transpose_stored_mission_example,
    transpose_stored_mission_practice_lick,
)
from improvisation_intelligence import ImprovSessionContext


def _session(instrument: str = "Piano", key: str = "G", chord: str = "G") -> dict:
    return {
        "song": "Shallow", "artist": "Lady Gaga", "display_key": key, "concert_key": key, "instrument": instrument,
        "level": "Intermediate", "focus": "Improvisation",
        "improv_active_mission": "Improvise using only chord tones", "improv_mission_pick": "Improvise using only chord tones",
        "home_sections": {"Verse 1": [chord]}, "improv_mission_chord_options": [chord], "ii_selected_chord_index": 0,
        "ii_selected_chord": chord, "ii_selected_section": "Verse 1", "backing_track_bpm": 100, "creative_workspace_state": {},
    }


def _shape(session: dict) -> dict:
    ex = session[MISSION_EXAMPLE_KEY]
    m = ex["motif"]
    return {
        "midi": list(m.get("midi") or []), "notes": list(m.get("notes") or []),
        "rhythm": (m.get("rhythm_key"), tuple(m.get("rhythm_symbols") or ())),
        "bars": ex["abc"].count("|"),
    }


def _walk(session: dict, keys: list[str]) -> list[dict]:
    cur = session["concert_key"]
    out = []
    for k in keys:
        transpose_stored_mission_example(session, from_key=cur, to_key=k)
        session["concert_key"] = session["display_key"] = cur = k
        out.append(_shape(session))
    return out


class TestNoOctaveDrift(unittest.TestCase):
    def _fresh(self, inst: str = "Piano") -> tuple[dict, dict]:
        s = _session(inst)
        _run_mission_example_generate(s, "normal")
        return s, _shape(s)

    def test_g_a_bb_g_restores_the_original_pitches_exactly(self) -> None:
        for inst in ("Piano", "Guitar", "Voice"):
            s, orig = self._fresh(inst)
            a, bb, g = _walk(s, ["A", "Bb", "G"])
            self.assertEqual(g["midi"], orig["midi"], inst)
            self.assertEqual(g["notes"], orig["notes"], inst)
            self.assertEqual([m + 2 for m in orig["midi"]], a["midi"], inst)
            self.assertEqual([m + 3 for m in orig["midi"]], bb["midi"], inst)

    def test_many_key_cycles_never_drift(self) -> None:
        s, orig = self._fresh()
        keys = ["A", "Bb", "B", "C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "G", "F#", "A", "G"]
        shapes = _walk(s, keys)
        for k, sh in zip(keys, shapes):
            if k == "G":
                self.assertEqual(sh["midi"], orig["midi"], k)
            self.assertLessEqual(abs(sh["midi"][0] - orig["midi"][0]), 6, k)  # nearest, never an octave away

    def test_the_result_depends_only_on_the_target_key(self) -> None:
        s1, _ = self._fresh()
        s2 = copy.deepcopy(s1)
        _walk(s1, ["A", "Bb", "D", "F#"])
        _walk(s2, ["F#"])
        self.assertEqual(_shape(s1), _shape(s2))

    def test_rhythm_bars_and_chord_are_preserved(self) -> None:
        s, orig = self._fresh()
        chord0 = s[MISSION_EXAMPLE_KEY]["chord"]
        for sh in _walk(s, ["A", "Bb", "G"]):
            self.assertEqual(sh["rhythm"], orig["rhythm"])
            self.assertEqual(sh["bars"], orig["bars"])
        self.assertEqual(s[MISSION_EXAMPLE_KEY]["chord"], chord0)

    def test_the_canonical_copy_is_never_modified_by_projection(self) -> None:
        s, _ = self._fresh()
        canon0 = copy.deepcopy(s[MISSION_EXAMPLE_KEY][_CANON_KEY])
        _walk(s, ["A", "Bb", "E", "G"])
        canon1 = s[MISSION_EXAMPLE_KEY][_CANON_KEY]
        self.assertEqual({k: v for k, v in canon1.items() if k != "shown_fp"},
                         {k: v for k, v in canon0.items() if k != "shown_fp"})
        self.assertEqual(canon1["concert_key"], "G")

    def test_provenance_identity_survives_projection(self) -> None:
        s, _ = self._fresh()
        before = {k: s[MISSION_EXAMPLE_KEY].get(k) for k in ("mission", "variant", "section", "artifact_id")}
        _walk(s, ["A", "Bb", "G"])
        after = {k: s[MISSION_EXAMPLE_KEY].get(k) for k in before}
        self.assertEqual(before, after)

    def test_original_catalog_key_is_never_rewritten(self) -> None:
        s, _ = self._fresh()
        s["song_original_key"] = s["original_key"] = "G"
        _walk(s, ["A", "Bb", "G"])
        self.assertEqual((s["song_original_key"], s["original_key"]), ("G", "G"))

    def test_guitar_tab_and_staff_move_together_and_restore(self) -> None:
        s, _ = self._fresh("Guitar")
        tab0, abc0 = s[MISSION_EXAMPLE_KEY]["tab"], s[MISSION_EXAMPLE_KEY]["abc"]
        _walk(s, ["A"])
        self.assertTrue(s[MISSION_EXAMPLE_KEY]["tab"])
        self.assertNotEqual(s[MISSION_EXAMPLE_KEY]["tab"], tab0)
        self.assertIn("K:A", s[MISSION_EXAMPLE_KEY]["abc"])
        _walk(s, ["Bb", "G"])
        self.assertEqual(s[MISSION_EXAMPLE_KEY]["tab"], tab0)
        self.assertEqual(s[MISSION_EXAMPLE_KEY]["abc"], abc0)

    def test_an_old_save_without_a_canonical_copy_still_transposes(self) -> None:
        s, orig = self._fresh()
        s[MISSION_EXAMPLE_KEY].pop(_CANON_KEY)
        a, = _walk(s, ["A"])
        self.assertEqual(a["midi"], [m + 2 for m in orig["midi"]])
        self.assertIn(_CANON_KEY, s[MISSION_EXAMPLE_KEY])
        g, = _walk(s, ["G"])
        self.assertEqual(g["midi"], orig["midi"])

    def test_a_new_accepted_example_gets_its_own_canon(self) -> None:
        s, _ = self._fresh()
        _walk(s, ["A"])
        _run_mission_example_generate(s, "normal")   # a new exercise replaces it
        canon = s[MISSION_EXAMPLE_KEY][_CANON_KEY]
        self.assertEqual(canon["concert_key"], "A")
        _walk(s, ["G"])
        self.assertEqual(s[MISSION_EXAMPLE_KEY][_CANON_KEY]["concert_key"], "A")


class TestPolicy(unittest.TestCase):
    def test_nearest_signed_shift_and_register_guard(self) -> None:
        self.assertEqual(_nearest_steps("G", "A"), 2)
        self.assertEqual(_nearest_steps("G", "F#"), -1)
        self.assertEqual(_nearest_steps("G", "D"), -5)
        self.assertEqual(_nearest_steps("G", "G"), 0)
        self.assertEqual(_nearest_steps("G", "Db"), 6)
        self.assertEqual(_nearest_steps("C", "G", [86, 88]), -5)      # would pass the top of the range
        self.assertEqual(_nearest_steps("C", "F#", [40, 42]), 6)


class TestLickAndLoad(unittest.TestCase):
    def test_practice_lick_restores_exactly(self) -> None:
        s = _session()
        s[MISSION_PRACTICE_LICK_KEY] = {
            "motif": {"notes": ["G", "B", "D'"], "midi": [55, 59, 62 + 12], "chord": "G", "meter": "4/4",
                      "rhythm_symbols": ["♩"] * 3},
            "chord": "G", "key_center": "G", "abc": "", "tab": "",
        }
        cur = "G"
        for k in ("A", "Bb", "G"):
            self.assertTrue(transpose_stored_mission_practice_lick(s, from_key=cur, to_key=k))
            s["concert_key"] = s["display_key"] = cur = k
        self.assertEqual(s[MISSION_PRACTICE_LICK_KEY]["motif"]["midi"], [55, 59, 74])

    def test_load_overlay_does_not_accumulate(self) -> None:
        s = _session()
        _run_mission_example_generate(s, "normal")
        orig = _shape(s)
        for k in ("A", "Bb", "G"):
            s["concert_key"] = s["display_key"] = k
            ctx = ImprovSessionContext(song_title="Shallow", artist="Lady Gaga", key_center=k, display_key=k,
                                       instrument="Piano", level="Intermediate", focus="Improvisation",
                                       sections={"Verse 1": ["G"]})
            load_mission_example(s, ctx)
        self.assertEqual(_shape(s)["midi"], orig["midi"])


if __name__ == "__main__":
    unittest.main()
