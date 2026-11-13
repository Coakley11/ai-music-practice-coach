"""Pure engine tests for the Custom Progressions "Suggested Next Chord" suggestions."""

from __future__ import annotations

import unittest

from custom_chord_suggest import suggest_next_chord as sug


def _c(*a, **k):
    return sug(*a, **k)["chord"]


class TestProductOwnerExamples(unittest.TestCase):
    def test_pop_empty_verse_opens_on_tonic(self) -> None:
        r = sug("C", "major", "Pop", "Verse 1", [])
        self.assertEqual(r["chord"], "C")
        self.assertEqual(r["roman"], "I")
        self.assertIn("C major", r["reason"])

    def test_pop_loop_is_completed(self) -> None:
        r = sug("C", "major", "Pop", "Verse", ["C", "G", "Am"])
        self.assertEqual(r["chord"], "F")
        self.assertEqual(r["roman"], "IV")
        self.assertIn("I–V–vi–IV", r["reason"])
        self.assertIn("completes", r["reason"])

    def test_jazz_two_five_resolves_to_one(self) -> None:
        r = sug("C", "major", "Jazz", "Verse", ["Dm7", "G7"])
        self.assertEqual(r["chord"], "Cmaj7")
        self.assertEqual(r["intent"], "resolve")
        self.assertIn("G7 (V7)", r["reason"])
        self.assertIn("ii–V–I", r["reason"])

    def test_jazz_applied_dominant_chain(self) -> None:
        r = sug("C", "major", "Jazz", "Verse", ["Cmaj7", "A7"])
        self.assertEqual(r["chord"], "D7")
        self.assertEqual(r["roman"], "V7/V")
        self.assertIn("G7", r["reason"])
        self.assertIn("A7 (V7/ii)", r["reason"])


class TestOpenings(unittest.TestCase):
    def test_chorus_after_verse_on_tonic_does_not_just_repeat_the_tonic_opening(self) -> None:
        r = sug("C", "major", "Pop", "Chorus", [], [("Verse", ["C", "G", "Am", "F"])])
        self.assertIn(r["chord"], ("F", "Am"))
        self.assertIn("contrasts", r["reason"])

    def test_bridge_opens_on_contrasting_degree(self) -> None:
        r = sug("C", "major", "Pop", "Bridge", [], [("Verse", ["C", "F"]), ("Chorus", ["F", "G"])])
        self.assertNotEqual(r["chord"], "C")

    def test_section_after_dominant_ending_resolves_home(self) -> None:
        r = sug("C", "major", "Pop", "Chorus", [], [("Verse", ["C", "Am", "F", "G"])])
        self.assertEqual(r["chord"], "C")
        self.assertIn("dominant", r["reason"])

    def test_jazz_may_open_on_two_or_one(self) -> None:
        r = sug("C", "major", "Jazz", "Verse", [])
        self.assertEqual(r["chord"], "Cmaj7")
        self.assertIn("Dm7", [a["chord"] for a in r["alternatives"]])

    def test_minor_key_opens_on_minor_tonic(self) -> None:
        r = sug("A", "minor", "Pop", "Verse", [])
        self.assertEqual(r["chord"], "Am")
        self.assertEqual(r["roman"], "i")

    def test_key_with_minor_token_infers_mode(self) -> None:
        self.assertEqual(_c("Am", None, "Pop", "Verse", []), "Am")

    def test_blues_opens_on_dominant_one(self) -> None:
        self.assertEqual(_c("C", "major", "Blues", "Verse", []), "C7")
        self.assertEqual(_c("A", "minor", "Blues", "Verse", []), "Am7")


class TestStyles(unittest.TestCase):
    def test_blues_form_positions(self) -> None:
        r = sug("C", "major", "Blues", "Verse", ["C7"])
        self.assertEqual(r["chord"], "F7")
        self.assertIn("12-bar", r["reason"])
        r = sug("C", "major", "Blues", "Verse", ["C7", "F7", "C7"], bars=8)
        self.assertEqual(r["chord"], "G7")  # bar 9 is V7
        r = sug("C", "major", "Blues", "Verse", ["C7", "F7", "C7", "G7"], bars=9)
        self.assertEqual(r["chord"], "F7")  # bar 10 is IV7
        self.assertEqual(r["intent"], "continue")

    def test_blues_twelve_bars_is_complete(self) -> None:
        r = sug("C", "major", "Blues", "Verse", ["C7", "F7", "C7", "G7", "F7", "C7", "G7"], bars=12)
        self.assertTrue(r["complete"])
        self.assertIsNone(r["chord"])
        self.assertIn("12-bar", r["reason"])

    def test_blues_in_a_flat_key_spelled_with_flats(self) -> None:
        self.assertEqual(_c("Bb", "major", "Blues", "Verse", ["Bb7"]), "Eb7")

    def test_rock_modal_movement(self) -> None:
        r = sug("C", "major", "Rock", "Verse", ["C", "Bb"])
        self.assertEqual(r["chord"], "F")
        self.assertIn("I–bVII–IV", r["reason"])

    def test_ballad_prefers_stepwise_movement(self) -> None:
        self.assertEqual(_c("C", "major", "Ballad", "Verse", ["C", "Em"]), "F")

    def test_pop_does_not_use_sevenths_unless_the_user_does(self) -> None:
        self.assertEqual(_c("C", "major", "Pop", "Verse", ["C", "Am"]), "F")
        self.assertEqual(_c("C", "major", "Pop", "Verse", ["Cmaj7", "Am7"]), "Fmaj7")

    def test_style_changes_the_answer(self) -> None:
        chords = ["C", "Am"]
        pop = _c("C", "major", "Pop", "Verse", chords)
        jazz = _c("C", "major", "Jazz", "Verse", chords)
        self.assertNotEqual(pop, jazz)
        self.assertEqual(jazz, "Dm7")


class TestMinorKeys(unittest.TestCase):
    def test_minor_loop(self) -> None:
        self.assertEqual(_c("A", "minor", "Pop", "Verse", ["Am", "F", "C"]), "G")

    def test_minor_two_five_resolves_to_minor_one(self) -> None:
        r = sug("A", "minor", "Jazz", "Verse", ["Bm7b5", "E7"])
        self.assertEqual(r["chord"], "Am7")
        self.assertEqual(r["intent"], "resolve")

    def test_minor_dominant_resolves(self) -> None:
        self.assertEqual(_c("A", "minor", "Pop", "Verse", ["Am", "Dm", "E"]), "Am")


class TestStructure(unittest.TestCase):
    def test_full_eight_bar_section_looks_complete(self) -> None:
        r = sug("C", "major", "Pop", "Verse", ["C", "G", "Am", "F"] * 2, bars=8)
        self.assertTrue(r["complete"])
        self.assertIn("complete", r["reason"])
        self.assertTrue(r["alternatives"])

    def test_eight_bars_not_on_a_cadence_is_not_complete(self) -> None:
        r = sug("C", "major", "Pop", "Verse", ["C", "F", "Am", "Dm", "F", "Dm", "F"], bars=8)
        self.assertFalse(r["complete"])

    def test_last_bar_of_period_pulls_to_dominant(self) -> None:
        r = sug("C", "major", "Pop", "Verse", ["C", "Am", "F", "C", "Am", "Dm", "F"], bars=7)
        self.assertEqual(r["chord"], "G")
        self.assertIn("8-bar", r["reason"])

    def test_bridge_closes_on_dominant_to_lead_back(self) -> None:
        r = sug("C", "major", "Pop", "Bridge", ["Am", "F", "Dm"], [("Verse", ["C", "G", "Am", "F"])])
        self.assertEqual(r["chord"], "G")

    def test_ending_settles_on_tonic(self) -> None:
        r = sug("C", "major", "Pop", "Outro", ["Am", "F", "G"], [("Verse", ["C", "G"])])
        self.assertEqual(r["chord"], "C")

    def test_previous_sections_change_the_opening(self) -> None:
        a = _c("C", "major", "Pop", "Chorus", [])
        b = _c("C", "major", "Pop", "Chorus", [], [("Verse", ["C", "G", "Am", "F"])])
        self.assertNotEqual(a, b)

    def test_no_immediate_repetition_and_never_empty(self) -> None:
        for last in ("C", "G", "Am", "F", "Dm", "Em", "Bb", "G7"):
            r = sug("C", "major", "Pop", "Verse", [last])
            self.assertNotEqual(r["chord"], last)
            self.assertTrue(r["reason"])

    def test_subdivision_tokens_and_holds_are_read(self) -> None:
        self.assertEqual(_c("C", "major", "Pop", "Verse", ["C:2|G:2", "%", "Am"]), "F")

    def test_deterministic_and_shape(self) -> None:
        a = sug("D", "major", "Pop", "Verse", ["D", "A"])
        self.assertEqual(a, sug("D", "major", "Pop", "Verse", ["D", "A"]))
        self.assertEqual(
            set(a),
            {"chord", "roman", "reason", "alternatives", "intent", "complete", "position", "role", "style"},
        )
        self.assertIn(a["intent"], ("continue", "tension", "resolve"))

    def test_spelling_follows_the_key(self) -> None:
        self.assertEqual(_c("F", "major", "Pop", "Verse", ["F", "C", "Dm"]), "Bb")
        self.assertEqual(_c("E", "major", "Pop", "Verse", ["E", "B", "C#m"]), "A")

    def test_every_style_role_and_key_yields_a_reasoned_suggestion(self) -> None:
        for style in ("Pop", "Soul/R&B", "Jazz", "Bossa", "Blues", "Funk", "Rock", "Ballad"):
            for role in ("Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Solo", "Outro"):
                for key, mode in (("C", "major"), ("Eb", "major"), ("F#", "minor")):
                    r = sug(key, mode, style, role, [])
                    self.assertTrue(r["chord"], (style, role, key))
                    r2 = sug(key, mode, style, role, [r["chord"]])
                    self.assertTrue(r2["chord"] and r2["reason"], (style, role, key))
                    self.assertNotEqual(r2["chord"], r["chord"])

    def test_reason_roman_agrees_with_analysis(self) -> None:
        from roman_numeral_analysis import analyze_progression

        r = sug("C", "major", "Pop", "Verse", ["C", "G", "Am"])
        self.assertIn(analyze_progression(["C", "G", "Am", r["chord"]], "C")[-1], r["reason"])


if __name__ == "__main__":
    unittest.main()
