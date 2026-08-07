"""Harmonic spelling and authoritative practice key regression tests."""

from __future__ import annotations

import unittest

from harmonic_spelling import (
    build_scale_suggestion_for_chord,
    harmonic_reference_for_chord,
    spelled_chord_root_from_symbol,
)
from improvisation_intelligence import chord_coach_insight
from mission_pitch_spelling import chord_coach_insight_for_mission
from musical_context_authority import (
    resolve_authoritative_practice_key,
    sidebar_key_list_mode,
    song_catalog_context_owns_practice_key,
)


class TestGMMinorSpelling(unittest.TestCase):
    def test_gm_scales_use_bb_not_a_sharp(self) -> None:
        insight = chord_coach_insight("Gm", key_center="Gm")
        joined = " ".join(" ".join(s.notes) for s in insight.scale_suggestions)
        self.assertIn("Bb", joined)
        self.assertNotIn("A#", joined)

    def test_g_dorian_spelling(self) -> None:
        sug = build_scale_suggestion_for_chord("G dorian", chord_symbol="Gm", reference_key="Gm")
        self.assertIn("Bb", " ".join(sug.notes))


class TestEMinorDiatonicSpelling(unittest.TestCase):
    def test_e_dorian(self) -> None:
        from improvisation_intelligence import build_scale_suggestion

        sug = build_scale_suggestion("E dorian", reference_key="Em")
        self.assertEqual(sug.notes, ["E", "F#", "G", "A", "B", "C#", "D"])

    def test_e_melodic_minor(self) -> None:
        from improvisation_intelligence import build_scale_suggestion

        sug = build_scale_suggestion("E melodic minor", reference_key="Em")
        self.assertEqual(sug.notes[-1], "D#")
        self.assertNotIn("Eb", sug.notes)

    def test_f_sharp_minor_dorian_uses_sharps(self) -> None:
        from improvisation_intelligence import build_scale_suggestion

        sug = build_scale_suggestion("F# dorian", reference_key="F#m")
        joined = " ".join(sug.notes)
        self.assertIn("F#", joined)
        self.assertIn("C#", joined)


class TestBbSpelling(unittest.TestCase):
    def test_bb7_root_stays_bb(self) -> None:
        self.assertEqual(spelled_chord_root_from_symbol("Bb7"), "Bb")
        self.assertEqual(harmonic_reference_for_chord("Bb7", song_display_key="Ebm"), "Bb")

    def test_bb_mixolydian_not_a_sharp(self) -> None:
        insight = chord_coach_insight("Bb7", key_center="Ebm")
        labels = " ".join(s.label for s in insight.scale_suggestions)
        self.assertNotIn("A# Mixolydian", labels)
        self.assertIn("Bb Mixolydian", labels)

    def test_bb_mixolydian_notes(self) -> None:
        sug = build_scale_suggestion_for_chord("Bb mixolydian", chord_symbol="Bb7", reference_key="Ebm")
        self.assertIn("Bb Mixolydian", sug.label)
        self.assertIn("Eb", " ".join(sug.notes))

    def test_mission_insight_bb7(self) -> None:
        insight = chord_coach_insight_for_mission("Bb7", song_display_key="Ebm", song_key_center="Ebm")
        labels = " ".join(s.label for s in insight.scale_suggestions)
        self.assertIn("Bb", labels)
        self.assertNotIn("A# Mixolydian", labels)


class TestMinorKeyAuthority(unittest.TestCase):
    def test_ebm_practice_mode(self) -> None:
        session = {"display_key": "Ebm", "concert_key": "Ebm", "song": "Hevenu"}
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "minor")
        self.assertIn("minor", pk.practice_label().lower())

    def test_missions_tab_not_major_jam_sidebar(self) -> None:
        session = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_intelligence_tab": "Missions",
            "display_key": "Ebm",
            "studio_page": "creative",
        }
        self.assertTrue(song_catalog_context_owns_practice_key(session))
        self.assertEqual(sidebar_key_list_mode(session), "minor")


class TestBMajorContrast(unittest.TestCase):
    def test_b_major_uses_sharps_in_scales(self) -> None:
        insight = chord_coach_insight("B", key_center="Ebm")
        labels = " ".join(s.label for s in insight.scale_suggestions)
        self.assertIn("major scale", labels.lower())
        self.assertNotIn("Cb", labels)


if __name__ == "__main__":
    unittest.main()
