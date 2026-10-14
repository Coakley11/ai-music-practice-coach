"""MC3.3 — note sequences show bar lines at the real measure boundaries."""

from __future__ import annotations

import logging
import unittest
from fractions import Fraction as F

from phrase_measure_format import (
    format_phrase_notes_by_measure,
    phrase_measure_groups,
    phrase_note_measures,
    phrase_notes_html,
)

logging.disable(logging.CRITICAL)
HALF = "𝅗𝅥"  # the half-note symbol the motif engine writes


def phrase(notes, durations, *, meter="4/4", rests=(), triplet=(), timeline=None):
    """Motif with engine rhythm events; ``rests`` are (onset, duration) gaps inserted in order."""
    events, pos, n = [], F(0), 0
    rest_at = {F(on): F(d) for on, d in rests}
    for i, dur in enumerate(durations):
        while pos in rest_at:
            events.append({"on": str(pos), "dur": str(rest_at[pos]), "w": str(rest_at[pos]), "rest": True, "n": None})
            pos += rest_at.pop(pos)
        d = F(dur)
        tup = [3, 2] if i in triplet else None
        events.append({"on": str(pos), "dur": str(d), "w": str(d * 3 / 2 if tup else d), "rest": False,
                       "tup": tup, "ts": bool(tup) and (i - 1) not in triplet, "n": n})
        pos += d
        n += 1
    motif = {
        "notes": list(notes),
        "display": " – ".join(notes),
        "meter": meter,
        "rhythm_events": events,
        "rhythm_meta": {"engine": "melodic_rhythm_engine", "meter": meter},
    }
    if timeline is not None:
        motif["chord_timeline"] = timeline
    return motif


class TestMeasureBoundaries(unittest.TestCase):
    def test_four_four_quarters(self) -> None:
        m = phrase("C D E F G A B C".split(), [1] * 8)
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E – F | G – A – B – C")

    def test_mixed_quarter_two_eighths_half(self) -> None:
        # ♩ ♪♪ 𝅗𝅥 = one bar of 4/4 with four notes, then ♩ ♩ 𝅗𝅥.
        m = phrase("C D E F G A B".split(), [1, F(1, 2), F(1, 2), 2, 1, 1, 2])
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E – F | G – A – B")

    def test_triplets_do_not_create_fake_boundaries(self) -> None:
        # Three eighth-note triplets fill one beat; with three quarters the bar is complete.
        m = phrase("C D E F G A B C D".split(), [F(1, 3)] * 3 + [1, 1, 1] + [1, 1, 2], triplet={0, 1, 2})
        self.assertEqual(phrase_note_measures(m), [0, 0, 0, 0, 0, 0, 1, 1, 1])
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E – F – G – A | B – C – D")

    def test_held_notes_keep_their_measure(self) -> None:
        m = phrase("C D E F G".split(), [4, 1, 1, 1, 1])  # a whole note, then four quarters
        self.assertEqual(format_phrase_notes_by_measure(m), "C | D – E – F – G")
        # A note that sounds past the barline still belongs to the bar it starts in.
        tied = phrase("C D E F".split(), [1, 1, 3, 1])
        self.assertEqual(phrase_note_measures(tied), [0, 0, 0, 1])

    def test_whole_bar_rest_is_kept_as_a_measure(self) -> None:
        m = phrase("C D E F".split(), [2, 2, 2, 2], rests=((4, 4),))
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D | rest | E – F")

    def test_three_four(self) -> None:
        m = phrase("C D E F G A B".split(), [1, 1, 1, 1, 1, 1, 3], meter="3/4")
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E | F – G – A | B")

    def test_six_eight(self) -> None:
        m = phrase("C D E F G A".split(), [F(1, 2)] * 6, meter="6/8")
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E – F – G – A")
        m2 = phrase("C D E F G A G".split(), [F(1, 2)] * 6 + [F(3)], meter="6/8")
        self.assertEqual(format_phrase_notes_by_measure(m2), "C – D – E – F – G – A | G")

    def test_two_chords_in_one_bar_and_one_chord_over_two_bars(self) -> None:
        # Dm7 + G7 share bar 1, Cmaj7 fills bars 2–3: bars follow the rhythm, not the chords.
        timeline = [
            {"first_note": 0, "last_note": 1, "first_bar": 0, "bars": 1},
            {"first_note": 2, "last_note": 3, "first_bar": 0, "bars": 1},
            {"first_note": 4, "last_note": 8, "first_bar": 1, "bars": 2},
        ]
        m = phrase("D F G B C E G B C".split(), [1, 1, 1, 1, 1, 1, 1, 1, 4], timeline=timeline)
        self.assertEqual(format_phrase_notes_by_measure(m), "D – F – G – B | C – E – G – B | C")

    def test_timeline_without_rhythm_never_guesses(self) -> None:
        one_bar_each = {
            "notes": ["C", "E", "G", "F", "A"],
            "chord_timeline": [
                {"first_note": 0, "last_note": 2, "first_bar": 0, "bars": 1},
                {"first_note": 3, "last_note": 4, "first_bar": 1, "bars": 1},
            ],
        }
        self.assertEqual(format_phrase_notes_by_measure(one_bar_each), "C – E – G | F – A")
        multi_bar = dict(one_bar_each, chord_timeline=[
            {"first_note": 0, "last_note": 4, "first_bar": 0, "bars": 2},
        ])
        self.assertIsNone(phrase_measure_groups(multi_bar))
        self.assertEqual(format_phrase_notes_by_measure(multi_bar), "C – E – G – F – A")

    def test_single_chord_rhythm_symbols(self) -> None:
        # Older single-chord Mission examples carry one rhythm symbol per note.
        six_quarters = {"notes": ["A♯", "G", "F", "A♯", "D", "D"], "rhythm_symbols": ["♩"] * 6}
        self.assertEqual(format_phrase_notes_by_measure(six_quarters), "A♯ – G – F – A♯ | D – D")
        mixed = {"notes": list("CDEFGAB"), "rhythm_symbols": ["♪", "♪", "♩", HALF, "♩.", "♪", HALF]}
        self.assertEqual(format_phrase_notes_by_measure(mixed), "C – D – E – F | G – A – B")
        three_four = {"notes": list("CDEFG"), "meter": "3/4", "rhythm_symbols": ["♩", "♩", "♩", "♩", HALF]}
        self.assertEqual(format_phrase_notes_by_measure(three_four), "C – D – E | F – G")
        unknown = {"notes": list("CDE"), "rhythm_symbols": ["♩", "?", "♩"]}
        self.assertEqual(format_phrase_notes_by_measure(unknown), "C – D – E")  # never guess

    def test_no_rhythm_means_no_bar_lines(self) -> None:
        self.assertEqual(format_phrase_notes_by_measure({"notes": ["C", "D", "E", "F", "G", "A", "B", "C"]}),
                         "C – D – E – F – G – A – B – C")


class TestDisplayedSpelling(unittest.TestCase):
    def test_spelling_and_repeats_are_preserved(self) -> None:
        m = phrase(["Bb", "Bb", "A", "G", "F#", "F#", "G", "A"], [1] * 8)
        shown = ["B♭", "B♭", "A", "G", "F♯", "F♯", "G", "A"]
        self.assertEqual(format_phrase_notes_by_measure(m, shown), "B♭ – B♭ – A – G | F♯ – F♯ – G – A")

    def test_written_key_display_is_used_when_it_matches(self) -> None:
        m = phrase(["Bb", "C", "D", "Eb"], [1] * 4)
        m["display"] = "C – D – E – F"  # written-key projection for a B♭ instrument
        self.assertEqual(format_phrase_notes_by_measure(m), "C – D – E – F")

    def test_html_keeps_each_measure_together(self) -> None:
        m = phrase("C D E F G A".split(), [1, 1, 1, 1, 2, 2])
        out = phrase_notes_html(m, ["C", "D", "E", "F", "G", "A"])
        self.assertEqual(out.count('class="mc-measure" style="white-space:nowrap"'), 2)
        self.assertIn("C – D – E – F</span> | <span", out)


class TestGeneratedPhrases(unittest.TestCase):
    def test_span_mission_and_span_motif_bars_follow_their_rhythm(self) -> None:
        from harmonic_span_analyzer import analyze_harmonic_spans
        from mission_span_engine import MISSIONS_BY_ID, generate_mission_span_example
        from span_motif_engine import build_span_exercise, generate_span_motif

        rows = [("A", ["Gm7", "C7", "Fmaj7", "Cmaj7"], ["Gm7", "C7", "Fmaj7", "Cmaj7"])]
        sp = analyze_harmonic_spans(rows, key_center="F", length=3, source_id="t")[0]
        seed = generate_span_motif(sp, level="Intermediate", variant="normal", instrument="Saxophone")
        motifs = [
            generate_mission_span_example(MISSIONS_BY_ID["target_each_change"], sp, level="Intermediate", style="jazz")["motif"],
            seed,
            build_span_exercise(sp, seed, length="standard", instrument="Saxophone"),
        ]
        for m in motifs:
            groups = phrase_measure_groups(m)
            self.assertIsNotNone(groups, m.get("display"))
            self.assertEqual(sum(len(g) for g in groups), len(m["notes"]))
            self.assertEqual([t for g in groups for t in g], list(m["notes"]))  # order and repeats kept
            text = format_phrase_notes_by_measure(m)
            self.assertEqual(text.count(" | "), len(groups) - 1)


if __name__ == "__main__":
    unittest.main()
