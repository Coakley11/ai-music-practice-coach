"""C1b progression-aware voicing: voice leading, bass continuity, split-bar
integration, repeated phrases, and difficulty differentiation.
"""
from __future__ import annotations

import time
import unittest

from guitar_voicing_engine import (
    GuitarVoicingEvent,
    build_level_guitar_voicings,
    _top_k_candidates,
    _transition_cost,
    _shape_to_candidate,
    _VoicingCandidate,
)
from music_theory import pitch_class_from_spelled_note

OPEN_PC = [4, 9, 2, 7, 11, 4]
PC_NAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _bass_pc(shape: str) -> int | None:
    for i, ch in enumerate(shape):
        if ch != "x":
            return (OPEN_PC[i] + int(ch)) % 12
    return None


def _position(shape: str) -> int:
    fretted = [int(ch) for ch in shape if ch not in ("x", "0")]
    return min(fretted) if fretted else 0


def _n_sounding(shape: str) -> int:
    return sum(1 for ch in shape if ch != "x")


# ---------------------------------------------------------------------------
# Voice-leading quality
# ---------------------------------------------------------------------------

class TestVoiceLeadingQuality(unittest.TestCase):
    """DP should produce smoother voice leading than greedy per-chord."""

    DESCENDING_BASS = ["C", "C/B", "Am", "Am/G", "F", "G"]
    POP = ["G", "D/F#", "Em", "C"]
    JAZZ_II_V_I_IV = ["Dm7", "G7", "Cmaj7", "Fmaj7"]

    def _total_position_change(self, evs: list[GuitarVoicingEvent]) -> int:
        total = 0
        for i in range(1, len(evs)):
            total += abs(evs[i].position - evs[i - 1].position)
        return total

    def test_descending_bass_line_intermediate(self):
        evs = build_level_guitar_voicings(self.DESCENDING_BASS, level="Intermediate")
        bass_pcs = [_bass_pc(ev.shape) for ev in evs]
        self.assertEqual(bass_pcs[0], 0, "C bass")
        self.assertEqual(bass_pcs[1], 11, "C/B bass = B")
        self.assertEqual(bass_pcs[2], 9, "Am bass = A")
        self.assertEqual(bass_pcs[3], 7, "Am/G bass = G")

    def test_descending_bass_line_advanced(self):
        evs = build_level_guitar_voicings(self.DESCENDING_BASS, level="Advanced")
        bass_pcs = [_bass_pc(ev.shape) for ev in evs]
        self.assertEqual(bass_pcs[0], 0)
        self.assertEqual(bass_pcs[1], 11)
        self.assertEqual(bass_pcs[2], 9)
        self.assertEqual(bass_pcs[3], 7)

    def test_pop_progression_smooth_position(self):
        evs = build_level_guitar_voicings(self.POP, level="Intermediate")
        pos_change = self._total_position_change(evs)
        self.assertLessEqual(pos_change, 10, "Position jumps should be modest")

    def test_jazz_ii_v_i_intermediate_voice_leading(self):
        evs = build_level_guitar_voicings(self.JAZZ_II_V_I_IV, level="Intermediate")
        for ev in evs:
            self.assertGreaterEqual(_n_sounding(ev.shape), 4)
        pos_change = self._total_position_change(evs)
        self.assertLessEqual(pos_change, 12)

    def test_jazz_ii_v_i_advanced_drops(self):
        evs = build_level_guitar_voicings(self.JAZZ_II_V_I_IV, level="Advanced")
        labels = {ev.label for ev in evs}
        self.assertTrue(
            labels & {"drop-2", "shell", "extended voicing", "barre"},
            f"Expected advanced-style labels, got {labels}",
        )


# ---------------------------------------------------------------------------
# Bass-line continuity
# ---------------------------------------------------------------------------

class TestBassContinuity(unittest.TestCase):

    def test_slash_bass_accuracy(self):
        chords = ["C", "C/B", "Am", "Am/G", "F", "G"]
        for level in ("Intermediate", "Advanced"):
            evs = build_level_guitar_voicings(chords, level=level)
            self.assertEqual(_bass_pc(evs[1].shape), 11, f"C/B @{level}")
            self.assertEqual(_bass_pc(evs[3].shape), 7, f"Am/G @{level}")

    def test_d_fsharp_bass(self):
        evs = build_level_guitar_voicings(["G", "D/F#", "Em"], level="Intermediate")
        bass = _bass_pc(evs[1].shape)
        self.assertEqual(bass, 6, "D/F# bass should be F#")


# ---------------------------------------------------------------------------
# Split-bar integration
# ---------------------------------------------------------------------------

class TestSplitBarIntegration(unittest.TestCase):

    def test_split_bar_produces_sub_voicings(self):
        evs = build_level_guitar_voicings(["C:2|G:2", "Am", "F"], level="Intermediate")
        self.assertEqual(len(evs), 3)
        self.assertIsNotNone(evs[0].sub_voicings)
        self.assertEqual(len(evs[0].sub_voicings), 2)
        self.assertEqual(evs[0].sub_voicings[0].chord, "C")
        self.assertEqual(evs[0].sub_voicings[1].chord, "G")

    def test_split_bar_voice_leading_with_context(self):
        evs = build_level_guitar_voicings(["Am", "C:2|G:2", "F"], level="Intermediate")
        self.assertEqual(len(evs), 3)
        split = evs[1]
        self.assertIsNotNone(split.sub_voicings)
        c_pos = split.sub_voicings[0].position
        g_pos = split.sub_voicings[1].position
        self.assertLessEqual(abs(c_pos - g_pos), 4,
                             "Split-bar sub-chords should be close in position")

    def test_split_bar_3_1_split(self):
        evs = build_level_guitar_voicings(["Dsus4:3|Gadd9:1"], level="Intermediate")
        self.assertEqual(len(evs), 1)
        self.assertIsNotNone(evs[0].sub_voicings)
        self.assertEqual(len(evs[0].sub_voicings), 2)

    def test_non_split_chord_has_no_sub_voicings(self):
        evs = build_level_guitar_voicings(["C", "Am"], level="Intermediate")
        for ev in evs:
            self.assertIsNone(ev.sub_voicings)

    def test_mixed_split_and_normal(self):
        chords = ["C", "Am:2|G:2", "F", "Dm:1|G:3"]
        evs = build_level_guitar_voicings(chords, level="Intermediate")
        self.assertEqual(len(evs), 4)
        self.assertIsNone(evs[0].sub_voicings)
        self.assertIsNotNone(evs[1].sub_voicings)
        self.assertIsNone(evs[2].sub_voicings)
        self.assertIsNotNone(evs[3].sub_voicings)


# ---------------------------------------------------------------------------
# Repeated phrase consistency
# ---------------------------------------------------------------------------

class TestRepeatedPhraseConsistency(unittest.TestCase):

    def test_repeated_sequence_same_voicings(self):
        chords = ["C", "Am", "F", "G", "C", "Am", "F", "G"]
        for level in ("Beginner", "Intermediate", "Advanced"):
            evs = build_level_guitar_voicings(chords, level=level)
            first_half = [(ev.shape) for ev in evs[:4]]
            second_half = [(ev.shape) for ev in evs[4:]]
            self.assertEqual(first_half, second_half,
                             f"Repeated CAFG should match @{level}")

    def test_non_repeated_chords_independent(self):
        chords = ["C", "Am", "Dm", "G"]
        evs = build_level_guitar_voicings(chords, level="Intermediate")
        self.assertEqual(len(evs), 4)


# ---------------------------------------------------------------------------
# Difficulty differentiation
# ---------------------------------------------------------------------------

class TestDifficultyDifferentiation(unittest.TestCase):

    CHORDS = ["Fm7", "Bbm7", "Eb7", "Abmaj7"]

    def test_beginner_prefers_familiar_shapes(self):
        evs = build_level_guitar_voicings(["C", "G", "Am", "F"], level="Beginner")
        shapes = [ev.shape for ev in evs]
        from practice_notation import GUITAR_SHAPES
        for chord, shape in zip(["C", "G", "Am"], shapes[:3]):
            self.assertEqual(shape, GUITAR_SHAPES[chord],
                             f"Beginner {chord} should use stored shape")

    def test_intermediate_uses_voice_leading(self):
        evs = build_level_guitar_voicings(self.CHORDS, level="Intermediate")
        for ev in evs:
            self.assertGreaterEqual(_n_sounding(ev.shape), 4)

    def test_advanced_richer_labels(self):
        evs = build_level_guitar_voicings(self.CHORDS, level="Advanced")
        labels = {ev.label for ev in evs}
        self.assertTrue(
            labels & {"drop-2", "shell", "extended voicing"},
            f"Advanced jazz should have rich labels, got {labels}",
        )


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestPerformance(unittest.TestCase):

    def _measure_ms(self, chords, level, iterations=5):
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            build_level_guitar_voicings(chords, level=level)
            times.append((time.perf_counter() - t0) * 1000)
        return min(times)

    def test_simple_pop_under_200ms(self):
        chords = ["C", "Am", "F", "G", "C", "Am", "F", "G"]
        for level in ("Beginner", "Intermediate", "Advanced"):
            ms = self._measure_ms(chords, level)
            self.assertLess(ms, 200, f"8-chord pop @{level}: {ms:.1f}ms")

    def test_jazz_12_chords_under_300ms(self):
        chords = ["Dm7", "G7", "Cmaj7", "Fmaj7", "Bm7b5", "E7",
                   "Am7", "D7", "Gm7", "C7", "Fmaj7", "Bbmaj7"]
        for level in ("Intermediate", "Advanced"):
            ms = self._measure_ms(chords, level)
            self.assertLess(ms, 300, f"12-chord jazz @{level}: {ms:.1f}ms")

    def test_split_bar_heavy_under_300ms(self):
        chords = ["C:2|G:2", "Am:2|Em:2", "F:3|G:1", "Dm:2|G:2",
                   "C", "Am", "F:2|G:2", "C"]
        ms = self._measure_ms(chords, "Intermediate")
        self.assertLess(ms, 300, f"Split-bar heavy: {ms:.1f}ms")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):

    def test_identical_output_across_runs(self):
        chords = ["Dm7", "G7", "Cmaj7", "Am7", "Dm7", "G7", "Cmaj7"]
        for level in ("Beginner", "Intermediate", "Advanced"):
            v1 = [ev.shape for ev in build_level_guitar_voicings(chords, level=level)]
            v2 = [ev.shape for ev in build_level_guitar_voicings(chords, level=level)]
            self.assertEqual(v1, v2, f"Determinism @{level}")


# ---------------------------------------------------------------------------
# Transition cost unit tests
# ---------------------------------------------------------------------------

class TestTransitionCost(unittest.TestCase):

    def _cand(self, shape: str) -> _VoicingCandidate:
        c = _shape_to_candidate(shape)
        assert c is not None, f"Invalid shape: {shape}"
        return c

    def test_same_shape_bonus(self):
        c = self._cand("x32010")
        cost = _transition_cost(c, c, same_chord=True)
        self.assertGreater(cost, 0, "Identical shape should score positive")
        cost_diff = _transition_cost(c, c, same_chord=False)
        self.assertGreater(cost, cost_diff, "same_chord bonus should apply")

    def test_stepwise_bass_preferred(self):
        c_shape = self._cand("x32010")  # C bass
        cb_shape = self._cand("x20010")  # B bass
        am_shape = self._cand("x02210")  # A bass
        cost_c_cb = _transition_cost(c_shape, cb_shape)
        cost_c_am = _transition_cost(c_shape, am_shape)
        self.assertGreater(cost_c_cb, cost_c_am - 5,
                           "Stepwise C->B should score well")

    def test_position_stability(self):
        low = self._cand("x32010")   # position ~1
        high = self._cand("x57585")  # position ~5
        cost = _transition_cost(low, high)
        same = _transition_cost(low, low, same_chord=False)
        self.assertGreater(same, cost, "Large position jump should cost more")


# ---------------------------------------------------------------------------
# Top-K candidates
# ---------------------------------------------------------------------------

class TestTopKCandidates(unittest.TestCase):

    def test_returns_up_to_k_candidates(self):
        results = _top_k_candidates("Am", "Intermediate")
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 6)

    def test_beginner_includes_stored_shape(self):
        results = _top_k_candidates("C", "Beginner")
        shapes = {_shape_from_cand(c) for _, c in results}
        self.assertIn("x32010", shapes, "Stored C shape should be a candidate")

    def test_unique_shapes(self):
        results = _top_k_candidates("Dm7", "Advanced")
        shapes = [_shape_from_cand(c) for _, c in results]
        self.assertEqual(len(shapes), len(set(shapes)), "No duplicate shapes")


def _shape_from_cand(c: _VoicingCandidate) -> str:
    out = ["x"] * 6
    for s, f in c.frets.items():
        out[s] = str(min(9, max(0, f)))
    return "".join(out)


if __name__ == "__main__":
    unittest.main()
