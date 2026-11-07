"""The fallback must never quietly restore the gap it exists to remove.

``tile_pass`` is the single entry point both the monitor and the exported mix
use. Whatever happens inside it, one of two things must be true afterwards:
the loop is gapless, or ``diag["ok"]`` is False and the UI says so.
"""

import unittest
from pathlib import Path

import numpy as np

import backing_loop
from backing_loop import musical_sample_count, pass_sample_count, tile_pass

SR = 44100
APP = Path(backing_loop.__file__).resolve().parent / "streamlit_music_practice_app.py"


def pass_with_pad(musical_sec=4.0, pad_sec=1.0, sr=SR, tail_level=0.001):
    """A rendered pass: music, then a quiet decay inside a silent pad."""
    n = int(musical_sec * sr)
    t = np.arange(n) / sr
    music = 0.6 * np.sin(2 * np.pi * 220.0 * t)
    pad = np.zeros(int(pad_sec * sr))
    decay_n = min(len(pad), int(0.35 * sr))
    env = np.exp(-np.linspace(0, 6, decay_n))
    dt = np.arange(decay_n) / sr
    pad[:decay_n] = tail_level * env * np.sin(2 * np.pi * 220.0 * dt)
    return np.concatenate([music, pad])


def worst_join_gap(y, period, reps, sr=SR):
    mag = np.abs(y)
    thr = max(1e-4, float(mag.max()) * 1e-3)
    worst = 0.0
    for i in range(1, reps):
        before = mag[: i * period]
        nz = np.nonzero(before > thr)[0]
        if len(nz):
            worst = max(worst, (i * period - 1 - nz[-1]) / sr)
    return worst


class TestTheGoodPath(unittest.TestCase):
    def test_known_musical_length_uses_overlap_add_and_reports_ok(self):
        y = pass_with_pad()
        out, diag = tile_pass(y, 8, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertEqual(diag["strategy"], "overlap_add")
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.01, diag)

    def test_eight_laps_have_no_gap_anywhere(self):
        y = pass_with_pad()
        n = musical_sample_count(8.0, 120.0)
        out, diag = tile_pass(y, 8, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertLess(worst_join_gap(out, n, 8), 0.01)


class TestTheFallbackIsStillGapless(unittest.TestCase):
    """When beats/bpm cannot locate the music, trim silence - never plain tile."""

    def _check_trim(self, **kw):
        y = pass_with_pad()
        out, diag = tile_pass(y, 6, **kw)
        self.assertEqual(diag["strategy"], "trim_silence", diag)
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.05, diag)
        self.assertTrue(diag["detail"])
        return out, diag

    def test_zero_beats_falls_back_to_trimming(self):
        self._check_trim(musical_samples=0)

    def test_zero_bpm_falls_back_to_trimming(self):
        self._check_trim(musical_samples=0)

    def test_nonsense_beats_falls_back_to_trimming(self):
        self._check_trim(musical_samples=musical_sample_count(9999.0, 120.0))

    def test_the_trimmed_fallback_keeps_the_audible_decay(self):
        """Only silence is dropped: the decay itself must survive."""
        y = pass_with_pad()
        out, _ = tile_pass(y, 2, musical_samples=0)
        self.assertGreater(float(np.abs(out).max()), 0.5)
        lap = len(out) // 2
        self.assertGreater(float(np.abs(out[lap - 2000 : lap]).max()), 1e-5)

    def test_the_fallback_never_repeats_the_pad(self):
        y = pass_with_pad(musical_sec=4.0, pad_sec=1.0)
        out, _ = tile_pass(y, 4, musical_samples=0)
        self.assertLess(len(out) / SR, 18.0)


class TestFailureIsReportedNotSwallowed(unittest.TestCase):
    def test_an_internal_error_is_reported_as_not_ok(self):
        y = pass_with_pad()

        def broken(*a, **k):
            raise RuntimeError("boom")

        orig = backing_loop.seamless_tile
        backing_loop.seamless_tile = broken
        try:
            out, diag = tile_pass(y, 4, musical_samples=musical_sample_count(8.0, 120.0))
        finally:
            backing_loop.seamless_tile = orig
        self.assertEqual(diag["strategy"], "plain_tile")
        self.assertFalse(diag["ok"])
        self.assertIn("boom", diag["detail"])
        self.assertEqual(len(out), len(y) * 4)

    def test_a_surviving_gap_is_detected_and_reported(self):
        """The verifier must catch a gap even on the good path."""
        y = pass_with_pad(musical_sec=4.0, pad_sec=1.0)
        out, diag = tile_pass(y, 4, musical_samples=musical_sample_count(10.0, 120.0))
        self.assertEqual(diag["strategy"], "overlap_add")
        self.assertFalse(diag["ok"], diag)
        self.assertGreater(diag["gap_sec"], 0.25)
        self.assertIn("silence remains", diag["detail"])

    def test_every_not_ok_result_carries_an_explanation(self):
        y = pass_with_pad()
        _, diag = tile_pass(y, 4, musical_samples=musical_sample_count(10.0, 120.0))
        self.assertFalse(diag["ok"])
        self.assertTrue(diag["detail"].strip())


class TestSynthesizerCompatibility(unittest.TestCase):
    def test_a_future_unpadded_render_still_tiles_correctly(self):
        """If the sound/drums work removes the pad, this must stay correct."""
        n = musical_sample_count(8.0, 120.0)
        t = np.arange(n) / SR
        y = 0.6 * np.sin(2 * np.pi * 220.0 * t)
        out, diag = tile_pass(y, 4, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertTrue(diag["ok"], diag)
        self.assertEqual(len(out), n * 4)
        np.testing.assert_allclose(out, np.tile(y, 4), atol=1e-6)

    def test_a_longer_pad_is_also_absorbed(self):
        y = pass_with_pad(musical_sec=4.0, pad_sec=2.5)
        out, diag = tile_pass(y, 4, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.01)

    def test_no_pad_and_no_musical_length_is_safe(self):
        n = musical_sample_count(8.0, 120.0)
        t = np.arange(n) / SR
        y = 0.6 * np.sin(2 * np.pi * 220.0 * t)
        out, diag = tile_pass(y, 3, musical_samples=0)
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.01)


class TestSingleAndDegenerateInputs(unittest.TestCase):
    def test_one_loop_is_untouched(self):
        y = pass_with_pad()
        out, diag = tile_pass(y, 1, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertEqual(diag["strategy"], "single")
        self.assertTrue(diag["ok"])
        np.testing.assert_array_equal(out, y)

    def test_empty_audio_is_untouched(self):
        y = np.zeros(0)
        out, diag = tile_pass(y, 4, musical_samples=musical_sample_count(8.0, 120.0))
        self.assertEqual(len(out), 0)
        self.assertTrue(diag["ok"])

    def test_silent_audio_is_tiled_without_a_false_alarm(self):
        y = np.zeros(SR)
        out, diag = tile_pass(y, 4, musical_samples=0)
        self.assertEqual(diag["strategy"], "silent")
        self.assertTrue(diag["ok"], diag)
        self.assertEqual(len(out), SR * 4)


class TestBothCallSitesShareTheFix(unittest.TestCase):
    """The monitor and the exported mix must loop identically."""

    def _app(self):
        return APP.read_text(encoding="utf-8")

    def test_no_bare_tile_of_a_backing_pass_remains(self):
        src = self._app()
        bare = [
            ln.strip()
            for ln in src.splitlines()
            if "np.tile(backing_y" in ln and "tile_backing_pass" not in ln
        ]
        self.assertEqual(len(bare), 1, bare)

    def test_both_loop_sites_use_the_shared_helper(self):
        src = self._app()
        self.assertEqual(src.count("def tile_backing_pass("), 1)
        # the definition plus exactly two call sites: monitor and export
        self.assertEqual(src.count("tile_backing_pass("), 3)

    def test_both_sites_pass_the_songs_own_meter(self):
        """A 3/4 song must not be measured in 4/4 bars."""
        src = self._app()
        self.assertIn("backing_y, loops, events, bpm, time_signature", src)
        self.assertIn("backing_y, mt_loops, _export_events, mt_bpm, mt_time_sig", src)

    def test_the_length_comes_from_bars_not_beats(self):
        """Split measures broke the beats-based formula; guard against a revert."""
        src = Path(backing_loop.__file__).read_text(encoding="utf-8")
        self.assertIn("def pass_sample_count(", src)
        self.assertIn("bar_sec", src)
        app = self._app()
        self.assertIn("pass_sample_count(", app)
        self.assertNotIn("total_beats = sum(", app)

    def test_the_export_path_loops_through_the_helper(self):
        src = self._app()
        idx = src.index("if mt_loops > 1:")
        window = src[idx : idx + 400]
        self.assertIn("tile_backing_pass", window)
        self.assertNotIn("np.tile", window)

    def test_a_degraded_loop_is_surfaced_to_the_user(self):
        src = self._app()
        self.assertIn("def warn_if_backing_loop_degraded(", src)
        # the definition plus one call on each of the two paths
        self.assertEqual(src.count("warn_if_backing_loop_degraded()"), 3)
        self.assertIn("may pause between repeats", src)


class TestTheRealRendererWithSplitMeasures(unittest.TestCase):
    """The renderer gives every chord event a whole bar, whatever its beats.

    A progression with split measures therefore occupies MORE audio than its
    beat count implies. Deriving the fold point from beats folded real music
    onto the next downbeat; these tests pin the bar-based length instead.
    """

    def _render(self, events, bpm, tsig, style="funk"):
        from backing_audio import backing_bytes_to_float

        return backing_bytes_to_float(
            events, bpm=bpm, style=style, level="intermediate", time_signature=tsig
        )

    SPLIT = [
        {"chord": "Dm7", "beats": 2.0},
        {"chord": "G7", "beats": 2.0},
        {"chord": "Cmaj7", "beats": 4.0},
        {"chord": "A7", "beats": 4.0},
        {"chord": "Dm7", "beats": 4.0},
    ]

    def test_bars_not_beats_locate_the_music(self):
        y = self._render(self.SPLIT, 110, "4/4")
        by_bars = pass_sample_count(len(self.SPLIT), 110, "4/4")
        by_beats = musical_sample_count(sum(e["beats"] for e in self.SPLIT), 110)
        self.assertGreater(by_bars, by_beats)
        # bar-based length leaves exactly the renderer's one-second pad
        self.assertAlmostEqual((len(y) - by_bars) / SR, 1.0, delta=0.01)

    def test_the_fold_point_does_not_cut_into_music(self):
        y = self._render(self.SPLIT, 110, "4/4")
        n = pass_sample_count(len(self.SPLIT), 110, "4/4")
        # everything past the fold point is decay, not full-level music
        self.assertLess(float(np.abs(y[n:]).max()), 0.05 * float(np.abs(y).max()))

    def test_split_measures_loop_without_a_gap_or_clipping(self):
        y = self._render(self.SPLIT, 110, "4/4")
        n = pass_sample_count(len(self.SPLIT), 110, "4/4")
        out, diag = tile_pass(y, 8, musical_samples=n)
        self.assertEqual(diag["strategy"], "overlap_add")
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.01, diag)
        self.assertLessEqual(float(np.abs(out).max()), 1.0)

    def test_the_first_lap_is_unchanged_for_split_measures(self):
        y = self._render(self.SPLIT, 110, "4/4")
        n = pass_sample_count(len(self.SPLIT), 110, "4/4")
        out, _ = tile_pass(y, 4, musical_samples=n)
        np.testing.assert_allclose(out[:n], y[:n], atol=1e-9)

    def test_a_beats_based_length_is_rejected_as_implausible(self):
        """The guard must catch the mistake this class exists to document."""
        y = self._render(self.SPLIT, 110, "4/4")
        wrong = musical_sample_count(sum(e["beats"] for e in self.SPLIT), 110)
        out, diag = tile_pass(y, 4, musical_samples=wrong)
        self.assertEqual(diag["strategy"], "trim_silence", diag)
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.05, diag)

    def test_three_four_uses_three_beat_bars(self):
        events = [{"chord": "G", "beats": 3.0}, {"chord": "C", "beats": 3.0},
                  {"chord": "D", "beats": 3.0}, {"chord": "G", "beats": 3.0}]
        y = self._render(events, 120, "3/4", style="pop")
        n = pass_sample_count(len(events), 120, "3/4")
        self.assertAlmostEqual((len(y) - n) / SR, 1.0, delta=0.01)
        out, diag = tile_pass(y, 8, musical_samples=n)
        self.assertTrue(diag["ok"], diag)
        self.assertLess(diag["gap_sec"], 0.01, diag)


if __name__ == "__main__":
    unittest.main()
