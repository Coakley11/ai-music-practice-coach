"""MC4 — "Resolve through a ii–V–I": a tonic landing is graded by what the note is, not just that it is "stable".

Real take (Bm7♭5 → E7 → Am): "The phrase ended on F♯ (6th of Am) — a convincing resolution." and "Resolve into Am
on its 3rd, 5th, 6th, 9th or root." Every one of 6th / 9th / 13th / 7th / major 7th passed like a chord tone.

Hierarchy now (tonic Am): core A, C, E  >  stable colour B (9th), or a natural 6th the tonal language supports
>  everything else (an unsupported natural 6th, major 7th, outside notes).
"""

from __future__ import annotations

import unittest

from mission_span_take_evaluation import Check, _score, evaluate_span_take
from tests.test_mc4_span_recording import CONFIRMED, _block, _transcription

BODY = [("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("A5", 3, 1), ("E5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1), ("D6", 7, 1)]


def _take(landing, *, mission="ii_v_i_resolution", language=None, final=None):
    notes = BODY + [(landing, 8, 1), (landing, 9, 1), (landing, 10, 1), (final or landing, 11, 1)]
    block = _block(["Bm7b5", "E7", "Am"], key="Am", mission_id=mission, bpm=100)
    if language:
        block = dict(block, tonal_language=language)
    return evaluate_span_take(block, _transcription(notes, bpm=100), CONFIRMED)


class TestTonicResolutionHierarchy(unittest.TestCase):
    def test_core_tonic_tones_are_the_strongest_resolution(self) -> None:
        for note, role in (("A5", "root"), ("C6", "3rd"), ("E6", "5th")):
            r = _take(note)
            self.assertEqual(r["score"], 100, note)
            self.assertIn(f"The phrase ended on {note[0]} ({role} of Am) — a convincing resolution.", r["what_worked"], note)
            self.assertIn(f"Am arrived on {note[0]}, the {role}.", r["what_worked"], note)

    def test_the_9th_is_a_softer_stable_colour(self) -> None:
        r = _take("B5")
        self.assertEqual(r["score"], 82)                                                # credited, but below a core tone
        self.assertIn("The phrase ended on B, the 9th of Am — a stable colour rather than a core tonic landing.", r["what_worked"])
        self.assertIn("For a fuller landing, finish on A, C or E.", r["try_next"])
        self.assertFalse(any("convincing resolution" in t for t in r["what_worked"]))

    def test_a_natural_6th_over_a_plain_minor_tonic_is_not_a_convincing_resolution(self) -> None:
        r = _take("F#6")
        self.assertEqual(r["score"], 54)
        self.assertFalse(any("F♯" in t and "convincing" in t for t in r["what_worked"]))
        self.assertIn("The phrase ended on F♯, a natural 6th over Am. That creates a modal colour rather than a full tonic "
                      "landing; resolve next to A, C or E for a stronger finish.", r["try_next"])
        self.assertIn("Resolve into Am on its root, 3rd or 5th; the 9th can work as a softer colour.", r["try_next"])

    def test_the_try_next_list_is_generated_from_the_hierarchy(self) -> None:
        for r in (_take("F#6"), _take("A#5")):
            joined = " ".join(r["try_next"])
            self.assertIn("root, 3rd or 5th", joined)
            self.assertNotIn("6th, 9th", joined)                                          # the old permissive list
            self.assertNotIn("3rd, 5th, 6th", joined)

    def test_a_supported_natural_6th_is_a_valid_contextual_colour(self) -> None:
        for language in ("A Dorian", "A melodic minor"):
            r = _take("F#6", language=language)
            self.assertEqual(r["score"], 82, language)
            self.assertIn("The phrase resolved to F♯, a supported natural-6 colour over Am.", r["what_worked"], language)
            self.assertIn("Am arrived on F♯, a supported natural-6 colour over Am.", r["what_worked"], language)
            self.assertIn("For a fuller landing, finish on A, C or E.", r["try_next"], language)       # still not a core landing
        harmonic = _take("F#6", language="A harmonic minor")                               # harmonic minor does not support it
        self.assertEqual(harmonic["score"], 54)

    def test_a_major_7th_needs_melodic_or_harmonic_language(self) -> None:
        self.assertEqual(_take("G#5")["score"], 54)
        self.assertEqual(_take("G#5", language="A harmonic minor")["score"], 82)

    def test_an_unsupported_note_stays_unsuccessful(self) -> None:
        r = _take("A#5")
        self.assertEqual(r["score"], 54)
        self.assertIn("End the phrase on A, C or E of Am.", r["try_next"])
        self.assertFalse(any("A♯" in t and "resolution" in t for t in r["what_worked"]))

    def test_the_ending_note_decides_the_phrase_ending_not_the_arrival(self) -> None:
        r = _take("A5", final="F#6")                                                       # lands on A, wanders off to F♯
        self.assertIn("Am arrived on A, the root.", r["what_worked"])
        self.assertTrue(any("natural 6th over Am" in t for t in r["try_next"]))
        self.assertLess(r["score"], 100)
        self.assertGreater(r["score"], _take("F#6")["score"])

    def test_score_credit_is_partial_only_when_asked_for(self) -> None:
        full = [Check("a", True, "x"), Check("b", False, "y")]
        self.assertEqual(_score(full), 50)
        self.assertEqual(_score([Check("a", True, "x", credit=0.6), Check("b", False, "y")]), 30)
        self.assertEqual(_score([Check("a", True, "x", weight=0.5)]), 100)                 # old "partial" weights unchanged


class TestOtherMissionsAreUntouched(unittest.TestCase):
    # Scores on the same takes, measured on the commit before this change (37e2cd15).
    PINNED = {
        ("A5", "guide_tone_voice_leading"): 58, ("A5", "resolve_to_third"): 100, ("A5", "common_tone_voice_leading"): 0,
        ("A5", "enclose_next_target"): 0, ("A5", "dominant_tension_resolution"): 0, ("A5", "target_each_chord_change"): 100,
        ("F#6", "guide_tone_voice_leading"): 58, ("F#6", "resolve_to_third"): 33, ("F#6", "common_tone_voice_leading"): 0,
        ("F#6", "enclose_next_target"): 0, ("F#6", "dominant_tension_resolution"): 0, ("F#6", "target_each_chord_change"): 56,
        ("B5", "guide_tone_voice_leading"): 58, ("B5", "resolve_to_third"): 33, ("B5", "target_each_chord_change"): 56,
        ("A#5", "guide_tone_voice_leading"): 58, ("A#5", "resolve_to_third"): 33, ("A#5", "target_each_chord_change"): 56,
    }

    def test_scores_for_other_missions_are_unchanged(self) -> None:
        for (landing, mission), expected in self.PINNED.items():
            self.assertEqual(_take(landing, mission=mission)["score"], expected, f"{mission} / {landing}")


if __name__ == "__main__":
    unittest.main()
