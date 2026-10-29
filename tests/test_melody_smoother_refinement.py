"""Regression tests for melody refinement 'smoother' fix (P8).

The smoother refinement was a no-op because its threshold (>= 5 semitones)
was too high for most generated melodies. The fix lowers it to >= 3 and
uses original midi values to prevent cascading mutation.
"""

from __future__ import annotations

import copy
import unittest


class TestSmootherThresholdLowered(unittest.TestCase):
    """Smoother must modify notes with intervals >= 3 semitones."""

    def _propose(self, events, key="C"):
        from composition_melody_shape import propose_melody_refinement
        return propose_melody_refinement(events, "smoother", key=key)

    def test_three_semitone_leap_is_smoothed(self):
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"midi": 64, "pitch": "E4", "beat": 1, "duration_beats": 1},
            {"midi": 60, "pitch": "C4", "beat": 2, "duration_beats": 1},
        ]
        result = self._propose(events)
        self.assertTrue(result["ok"], "Should modify a 4-semitone leap")
        self.assertFalse(result["unchanged"])
        middle = result["events"][1]
        self.assertEqual(middle["midi"], 60)

    def test_two_semitone_step_is_not_smoothed(self):
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"midi": 62, "pitch": "D4", "beat": 1, "duration_beats": 1},
            {"midi": 64, "pitch": "E4", "beat": 2, "duration_beats": 1},
        ]
        result = self._propose(events)
        self.assertTrue(result.get("unchanged", False),
                        "2-semitone steps should not trigger smoothing")

    def test_old_threshold_five_would_miss_four_semitone_leap(self):
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"midi": 64, "pitch": "E4", "beat": 1, "duration_beats": 1},
            {"midi": 60, "pitch": "C4", "beat": 2, "duration_beats": 1},
        ]
        result = self._propose(events)
        self.assertTrue(result["ok"],
                        "4-semitone interval must now be smoothed (was missed at threshold 5)")

    def test_no_cascading_mutation(self):
        """Each note should be averaged from ORIGINAL neighbors, not already-modified ones."""
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"midi": 67, "pitch": "G4", "beat": 1, "duration_beats": 1},
            {"midi": 60, "pitch": "C4", "beat": 2, "duration_beats": 1},
            {"midi": 67, "pitch": "G4", "beat": 3, "duration_beats": 1},
            {"midi": 60, "pitch": "C4", "beat": 4, "duration_beats": 1},
        ]
        result = self._propose(events)
        self.assertTrue(result["ok"])
        midis = [e["midi"] for e in result["events"]]
        self.assertEqual(midis[1], 60, "avg of original C4(60) and C4(60)")
        self.assertEqual(midis[3], 60, "avg of original C4(60) and C4(60)")

    def test_fewer_than_three_notes_returns_unchanged(self):
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 2},
            {"midi": 72, "pitch": "C5", "beat": 2, "duration_beats": 2},
        ]
        result = self._propose(events)
        self.assertFalse(result["ok"])
        self.assertTrue(result["unchanged"])

    def test_rests_excluded_from_smoothing(self):
        events = [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"pitch": "rest", "beat": 1, "duration_beats": 1, "is_rest": True},
            {"midi": 67, "pitch": "G4", "beat": 2, "duration_beats": 1},
            {"midi": 60, "pitch": "C4", "beat": 3, "duration_beats": 1},
        ]
        result = self._propose(events)
        self.assertTrue(result["ok"])
        rest_ev = [e for e in result["events"] if e.get("is_rest") and e.get("pitch") == "rest"]
        self.assertEqual(len(rest_ev), 1, "Rest should remain unchanged")


class TestOtherRefinementsStillWork(unittest.TestCase):
    """Non-smoother refinements must still produce changes."""

    def _propose(self, events, rid, key="C"):
        from composition_melody_shape import propose_melody_refinement
        return propose_melody_refinement(events, rid, key=key)

    def _base_events(self):
        return [
            {"midi": 60, "pitch": "C4", "beat": 0, "duration_beats": 1},
            {"midi": 62, "pitch": "D4", "beat": 1, "duration_beats": 1},
            {"midi": 64, "pitch": "E4", "beat": 2, "duration_beats": 1},
            {"midi": 65, "pitch": "F4", "beat": 3, "duration_beats": 1},
            {"midi": 67, "pitch": "G4", "beat": 4, "duration_beats": 1},
        ]

    def test_energetic(self):
        result = self._propose(self._base_events(), "energetic")
        self.assertTrue(result["ok"])

    def test_rhythm(self):
        result = self._propose(self._base_events(), "rhythm")
        self.assertTrue(result["ok"])

    def test_simplify(self):
        result = self._propose(self._base_events(), "simplify")
        self.assertTrue(result["ok"])

    def test_emotional(self):
        result = self._propose(self._base_events(), "emotional")
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
