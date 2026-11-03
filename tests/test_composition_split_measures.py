"""The Composition chord editor can split a bar between two chords, the same way the Custom page does.

One shared definition of the subdivisions (``chord_subdivisions.split_measure_token``) backs both pages,
and the resulting token is the one the chart, notation and playback already understand.
"""
import unittest

from chord_subdivisions import (
    SPLIT_MEASURE_PATTERNS,
    chord_at_beat,
    is_subdivided_bar,
    parse_subdivisions,
    split_measure_token,
)
from composition_chord_manual_editor import (
    chord_timeline,
    split_draft_chord,
    unsplit_draft_chord,
)
from custom_progression_lab import suggest_split_second_chords

DRAFT = [{"chord": "Am", "bars": 1}, {"chord": "F7", "bars": 2}, {"chord": "B7", "bars": 1}]


class TestSharedSplitDefinition(unittest.TestCase):
    def test_every_pattern_has_a_description_and_a_token(self):
        for pattern, label in SPLIT_MEASURE_PATTERNS.items():
            with self.subTest(pattern=pattern):
                self.assertTrue(label)
                token = split_measure_token(pattern, "F7", "B7")
                self.assertTrue(is_subdivided_bar(token), token)
                self.assertAlmostEqual(sum(s.weight for s in parse_subdivisions(token, beats_per_bar=4)), 4.0)

    def test_the_documented_shapes(self):
        self.assertEqual(split_measure_token("2+2", "F7", "B7"), "F7:2|B7:2")
        self.assertEqual(split_measure_token("3+1", "F7", "B7"), "F7:3|B7:1")
        self.assertEqual(split_measure_token("1+3", "F7", "B7"), "F7:1|B7:3")
        self.assertEqual(split_measure_token("4x1", "F7", "B7"), "F7:1|B7:1|F7:1|B7:1")
        self.assertIn("p", split_measure_token("push", "F7", "B7"))          # the push is anticipated

    def test_an_unknown_pattern_or_missing_chord_produces_nothing(self):
        self.assertEqual(split_measure_token("nope", "F7", "B7"), "")
        self.assertEqual(split_measure_token("2+2", "", "B7"), "")

    def test_the_custom_page_writes_through_the_same_helper(self):
        import inspect

        import custom_progression_lab as cpl

        src = inspect.getsource(cpl.cpl_split_measure_at_index)
        self.assertIn("split_measure_token", src)


class TestCompositionDraftSplit(unittest.TestCase):
    def test_split_turns_one_entry_into_a_two_chord_bar(self):
        out = split_draft_chord(DRAFT, 1, pattern="2+2", second_chord="B7")
        self.assertEqual(out[1]["chord"], "F7:2|B7:2")
        self.assertEqual(out[1]["bars"], 1)                                  # a split measure is one bar
        self.assertEqual(out[0], DRAFT[0])                                   # neighbours untouched
        self.assertEqual(out[2], DRAFT[2])
        self.assertEqual(DRAFT[1]["chord"], "F7")                            # the input draft is not mutated

    def test_both_chords_sound_in_the_right_half_of_the_bar(self):
        out = split_draft_chord(DRAFT, 1, pattern="2+2", second_chord="B7")
        token = out[1]["chord"]
        self.assertEqual(chord_at_beat(token, 0.0, beats_per_bar=4), "F7")
        self.assertEqual(chord_at_beat(token, 3.0, beats_per_bar=4), "B7")

    def test_a_first_chord_override_is_honoured(self):
        out = split_draft_chord(DRAFT, 1, pattern="2+2", second_chord="B7", first_chord="Fm7")
        self.assertEqual(out[1]["chord"], "Fm7:2|B7:2")

    def test_bad_input_leaves_the_draft_alone(self):
        for kwargs in (
            {"pattern": "2+2", "second_chord": ""},
            {"pattern": "unknown", "second_chord": "B7"},
        ):
            self.assertEqual(split_draft_chord(DRAFT, 1, **kwargs), DRAFT)
        self.assertEqual(split_draft_chord(DRAFT, 99, pattern="2+2", second_chord="B7"), DRAFT)
        self.assertEqual(split_draft_chord(DRAFT, -1, pattern="2+2", second_chord="B7"), DRAFT)

    def test_unsplit_returns_the_first_chord(self):
        out = split_draft_chord(DRAFT, 1, pattern="3+1", second_chord="B7")
        back = unsplit_draft_chord(out, 1)
        self.assertEqual(back[1]["chord"], "F7")
        self.assertEqual(unsplit_draft_chord(DRAFT, 0), DRAFT)               # not split: no-op

    def test_the_editor_timeline_still_reads_the_split_bar(self):
        out = split_draft_chord(DRAFT, 1, pattern="2+2", second_chord="B7")
        rows = chord_timeline(out, meter="4/4")
        self.assertEqual(rows[1]["chord"], "F7:2|B7:2")
        self.assertEqual(rows[1]["bars"], 1)
        self.assertEqual([r["index"] for r in rows], [0, 1, 2])

    def test_a_split_bar_transposes_as_one_unit(self):
        from music_theory import transpose_sections

        out = split_draft_chord(DRAFT, 1, pattern="2+2", second_chord="B7")
        song = {"original_key": "C", "key": "C", "sections": {"A": [e["chord"] for e in out]}}
        moved = transpose_sections(song, "D")["A"]
        self.assertTrue(is_subdivided_bar(moved[1]))
        self.assertEqual(len(parse_subdivisions(moved[1], beats_per_bar=4)), 2)


class TestSuggestionsAreExplainable(unittest.TestCase):
    def test_each_suggestion_comes_with_a_reason(self):
        out = suggest_split_second_chords(
            current_chord="F7", next_chord="B7", prev_chord="", home_key="A", style="Pop"
        )
        self.assertTrue(out)
        for chord, reason in out:
            self.assertTrue(chord)
            self.assertTrue(reason)

    def test_the_best_suggestion_leads_into_the_next_chord(self):
        out = suggest_split_second_chords(
            current_chord="F7", next_chord="B7", prev_chord="", home_key="A", style="Pop"
        )
        self.assertEqual(out[0][0], "F#7")                                   # V7 of B
        self.assertIn("B7", out[0][1])

    def test_a_jazz_context_offers_ii_v_vocabulary(self):
        out = suggest_split_second_chords(
            current_chord="Am", next_chord="Dm", prev_chord="", home_key="Am", style="Jazz"
        )
        joined = " ".join(r for _c, r in out)
        self.assertIn("ii-V", joined)

    def test_suggestions_are_usable_as_a_split_token(self):
        for chord, _reason in suggest_split_second_chords(
            current_chord="C", next_chord="G", prev_chord="", home_key="C", style="Pop"
        ):
            self.assertTrue(is_subdivided_bar(split_measure_token("2+2", "C", chord)))


if __name__ == "__main__":
    unittest.main()
