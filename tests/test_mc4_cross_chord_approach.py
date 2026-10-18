"""MC4 — cross-chord approach notes (Bm7♭5 → E7 → Am).

Review of an Autumn Leaves take: ``Bm7♭5 — … last D♯ (major 3rd)`` counted D♯ as "outside the chord"
although it sat right before the change and stepped into E, the root of E7. A note near the end of one
chord that steps into a chord tone / stable colour of the next chord, at the change, is an approach —
but only with that evidence: not every chromatic note near a boundary.
"""

from __future__ import annotations

import unittest

from mission_span_take_evaluation import (
    APPROACH_LANDING_BEATS,
    APPROACH_MAX_GAP_BEATS,
    APPROACH_WINDOW_BEATS,
    evaluate_span_take,
    mission_vs_chord_tone_note,
    span_metric_overrides,
)
from tests.test_mc4_span_recording import CONFIRMED, _block, _transcription

CHORDS = ["Bm7b5", "E7", "Am"]
# 4/4, one bar per chord: Bm7♭5 beats 0-4, E7 4-8, Am 8-12. (note, start beat, beats)
BASE_TAIL = [("E5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1), ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)]


def _take(first_bar, *, tail=None):
    block = _block(CHORDS, key="Am", mission_id="guide_tone_voice_leading", bpm=100)
    notes = list(first_bar) + list(BASE_TAIL if tail is None else tail)
    return evaluate_span_take(block, _transcription(sorted(notes, key=lambda n: n[1]), bpm=100), CONFIRMED)


def _row(result, chord):
    return next(d for d in result["chord_detail"] if d["chord"] == chord)


class TestCrossChordApproach(unittest.TestCase):
    def test_chromatic_approach_into_the_next_root(self) -> None:
        # D♯ on beat 4 of Bm7♭5, E (root of E7) on the downbeat of E7.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("D#5", 3, 1)])
        row = _row(r, "Bm7♭5")
        self.assertEqual(row["outside_tone_pct"], 0)
        self.assertEqual(row["passing_tone_pct"], 25)
        self.assertEqual(row["approach_examples"], ["D♯ (chromatic approach to E7 root)"])
        (a,) = row["approach_notes"]
        self.assertEqual((a["note"], a["target"], a["target_role"], a["target_chord"], a["interval"]),
                         ("D♯", "E", "root", "E7", 1))
        self.assertIn("D♯ approached E, the root of E7, by semitone into the chord change.", mission_vs_chord_tone_note(r))

    def test_whole_step_approach_from_above(self) -> None:
        # F♯ is not in Bm7♭5 (natural 5th over a ♭5 chord) and steps down a tone into E at the change.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("F#5", 3, 1)])
        row = _row(r, "Bm7♭5")
        self.assertEqual(row["outside_tone_pct"], 0)
        self.assertEqual(row["approach_examples"], ["F♯ (whole-step approach to E7 root)"])
        self.assertIn("by whole step into the chord change", mission_vs_chord_tone_note(r))

    def test_a_chord_tone_next_to_the_boundary_is_not_relabelled(self) -> None:
        # F is the ♭5 of Bm7♭5: already a chord tone, so it is neither an approach nor outside.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("A4", 2, 1), ("F5", 3, 1)])
        row = _row(r, "Bm7♭5")
        self.assertEqual((row["chord_tone_pct"], row["outside_tone_pct"], row["approach_examples"]), (100, 0, []))

    def test_boundary_note_that_resolves_elsewhere_is_not_credited(self) -> None:
        # D♯ right before the change, but the next note is G♯ (a leap): no approach to anything.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("D#5", 3, 1)], tail=[("G#5", 4, 1), ("B5", 5, 1), ("E6", 6, 1),
                                                                                     ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        row = _row(r, "Bm7♭5")
        self.assertEqual((row["outside_tone_pct"], row["approach_examples"]), (25, []))

    def test_boundary_note_resolving_to_a_non_chord_tone_is_not_credited(self) -> None:
        # D♯ then F: F is the ♭13 of E7 (a tension, not a chord tone / stable colour), and 2 semitones is not a
        # step from D♯ to a valid target anyway.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("A4", 2, 1), ("D#5", 3, 1)], tail=[("F5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1),
                                                                                    ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        self.assertEqual(_row(r, "Bm7♭5")["approach_examples"], [])
        self.assertEqual(_row(r, "Bm7♭5")["outside_tone_pct"], 25)

    def test_an_early_note_is_not_a_boundary_approach_just_because_a_chord_follows(self) -> None:
        # D♯ on beat 1.5 of the bar; the next note is E 2.5 beats later in E7.
        r = _take([("B4", 0, 1), ("D#5", 1.5, 0.5), ("D5", 3.9, 0.1)], tail=[("E5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1),
                                                                             ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        # (a D follows within the chord: D♯ is excused as a passing note of its own chord, and is not an approach)
        row = _row(r, "Bm7♭5")
        self.assertEqual(row["approach_examples"], [])
        r2 = _take([("B4", 0, 1), ("D#5", 1.5, 0.5)], tail=[("E5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1),
                                                           ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        row2 = _row(r2, "Bm7♭5")
        self.assertEqual((row2["approach_examples"], row2["outside_tone_pct"]), ([], 50))   # D♯ 2.5 beats before E: outside

    def test_a_late_target_is_not_an_approach(self) -> None:
        # D♯ on beat 4 but E only arrives 1 beat into E7 (the gap exceeds the limit).
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("A4", 2, 1), ("D#5", 3.0, 0.5)], tail=[("E5", 5.2, 1), ("G#5", 6, 1), ("B5", 7, 1),
                                                                                       ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        self.assertEqual(_row(r, "Bm7♭5")["approach_examples"], [])

    def test_approach_into_the_next_chord_am(self) -> None:
        # E7 → Am: D♯ (major 7th of E7, not a chord tone or stable colour) steps up into E, the 5th of Am.
        r = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("A4", 3, 1)],
                  tail=[("E5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1), ("D#6", 7, 1), ("E6", 8, 1), ("C6", 9, 1), ("A5", 10, 1)])
        row = _row(r, "E7")
        self.assertEqual(row["approach_examples"], ["D♯ (chromatic approach to Am 5th)"])
        self.assertEqual(row["outside_tone_pct"], 0)

    def test_scoring_treats_a_valid_approach_like_other_passing_notes(self) -> None:
        good = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("D#5", 3, 1)])
        bad = _take([("B4", 0, 1), ("D5", 1, 1), ("F5", 2, 1), ("D#5", 3, 1)], tail=[("G#5", 4, 1), ("B5", 5, 1), ("E6", 6, 1),
                                                                                       ("A5", 8, 1), ("C6", 9, 1), ("E6", 10, 1)])
        self.assertGreater(span_metric_overrides(good)["chord_tone_accuracy"], span_metric_overrides(bad)["chord_tone_accuracy"])
        self.assertNotIn("outside the harmony", mission_vs_chord_tone_note(good))
        self.assertIn("Notes outside the harmony", mission_vs_chord_tone_note(bad))

    def test_limits_are_the_documented_ones(self) -> None:
        self.assertEqual((APPROACH_WINDOW_BEATS, APPROACH_LANDING_BEATS, APPROACH_MAX_GAP_BEATS), (1.0, 0.75, 1.5))


if __name__ == "__main__":
    unittest.main()
