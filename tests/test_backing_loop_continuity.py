"""A repeated backing pass must stay in time, and the chord strip must agree.

``synthesize_chords_to_numpy`` allocates one second of decay headroom past the
music and never trims it. Repeating that buffer verbatim produced two faults at
once, from the same cause:

* a full second of silence at every loop boundary; and
* a chord strip that drifted one second further behind the audio on every lap,
  because ``layer_chord_timeline`` lays its cells out continuously at
  ``index * bar_duration`` - the musical length, with no gap between passes.

By lap seven the drift is six seconds and the highlighted chord is simply wrong.
``backing_loop.seamless_tile`` makes the audio lap exactly the musical length,
which is what the strip already assumes, so both faults close together.
"""

import unittest

import numpy as np

from backing_loop import loop_boundary_report, musical_sample_count, seamless_tile
from multitrack_layer_chords import chord_index_at, layer_chord_timeline

SR = 44100


def _pass_with_tail(
    musical_sec: float,
    tail_sec: float = 1.0,
    sr: int = SR,
    tail_level: float = 0.001,
) -> np.ndarray:
    """One rendered pass: music, then a decay tail, as the synth emits.

    ``tail_level`` is the tail's peak relative to the music. The real renderer's
    jazz/pop tail measures about 0.001 of full scale (-59 dB), which is the
    default here; a sustained pad is modelled by raising it.
    """
    n = int(round(musical_sec * sr))
    t = np.arange(n) / sr
    music = 0.8 * np.sin(2 * np.pi * 220.0 * t)
    k = int(round(tail_sec * sr))
    if k <= 0:
        return music
    tail = 0.8 * tail_level * np.exp(-np.arange(k) / (0.15 * sr))
    return np.concatenate([music, tail])


class TestTheLoopHasNoGap(unittest.TestCase):
    def setUp(self):
        self.musical = 4.0
        self.y = _pass_with_tail(self.musical)
        self.n = musical_sample_count(total_beats=8, bpm=120)  # 8 beats @120 = 4.0 s

    def test_the_musical_sample_count_matches_the_music(self):
        self.assertEqual(self.n, int(round(self.musical * SR)))

    def test_a_plain_tile_repeats_the_silence(self):
        old = np.tile(self.y, 3)
        # Silence sits just before each join at a multiple of the padded length.
        mag = np.abs(old)
        thr = mag.max() * 0.001
        join = len(self.y)
        nz = np.nonzero(mag[:join] > thr)[0]
        gap = (join - 1 - nz[-1]) / SR
        self.assertGreater(gap, 0.9)

    def test_seamless_tile_removes_the_gap_at_every_join(self):
        out = seamless_tile(self.y, 4, musical_samples=self.n)
        mag = np.abs(out)
        thr = mag.max() * 0.001
        for lap in range(1, 4):
            with self.subTest(join=lap):
                join = lap * self.n
                nz = np.nonzero(mag[:join] > thr)[0]
                gap = (join - 1 - nz[-1]) / SR
                self.assertLess(gap, 0.01)

    def test_every_lap_is_exactly_the_musical_length(self):
        for loops in (2, 3, 5):
            with self.subTest(loops=loops):
                out = seamless_tile(self.y, loops, musical_samples=self.n)
                tail = len(self.y) - self.n
                self.assertEqual(len(out), self.n * loops + tail)

    def test_the_final_decay_is_kept(self):
        out = seamless_tile(self.y, 3, musical_samples=self.n)
        rep = loop_boundary_report(out, musical_samples=self.n, sr=SR)
        self.assertGreater(rep["trailing_silence_sec"], 0.0)
        self.assertLess(rep["trailing_silence_sec"], 1.01)


class TestNothingIsDamaged(unittest.TestCase):
    def setUp(self):
        self.y = _pass_with_tail(4.0)
        self.n = int(round(4.0 * SR))

    def test_a_quiet_decay_does_not_raise_the_peak(self):
        out = seamless_tile(self.y, 4, musical_samples=self.n)
        self.assertLessEqual(float(np.abs(out).max()), float(np.abs(self.y).max()) * 1.01)
        self.assertFalse(loop_boundary_report(out, musical_samples=self.n)["clipped"])

    def test_a_loud_sustained_tail_never_clips(self):
        """A pad ringing into the downbeat sums louder; it must still not pass full scale."""
        loud = _pass_with_tail(4.0, tail_level=1.0)      # tail as loud as the music
        out = seamless_tile(loud, 4, musical_samples=self.n)
        self.assertLessEqual(float(np.abs(out).max()), 1.0 + 1e-9)
        self.assertFalse(loop_boundary_report(out, musical_samples=self.n)["clipped"])

    def test_a_loud_tail_is_still_carried_rather_than_cut(self):
        loud = _pass_with_tail(4.0, tail_level=1.0)
        out = seamless_tile(loud, 2, musical_samples=self.n)
        join = self.n
        self.assertGreater(float(np.abs(out[join : join + 1000]).max()), 0.0)

    def test_the_level_of_a_lap_is_unchanged(self):
        out = seamless_tile(self.y, 3, musical_samples=self.n)
        before = float(np.sqrt((self.y[: self.n] ** 2).mean()))
        after = float(np.sqrt((out[: self.n] ** 2).mean()))
        self.assertAlmostEqual(before, after, places=6)

    def test_the_join_introduces_no_discontinuity(self):
        """A click is a jump the waveform would never make on its own.

        The right bound is the signal's own steepest slope, not its median: a
        continuous join that happens to fall on a zero crossing legitimately
        shows the largest step in the cycle.
        """
        out = seamless_tile(self.y, 3, musical_samples=self.n)
        steepest = float(np.abs(np.diff(out[: self.n])).max())
        for lap in (1, 2):
            with self.subTest(join=lap):
                i = lap * self.n
                step = abs(float(out[i]) - float(out[i - 1]))
                self.assertLessEqual(step, steepest * 1.05)

    def test_no_transient_is_doubled_because_the_tail_carries_no_attack(self):
        tail = self.y[self.n :]
        self.assertLess(float(np.abs(tail).max()), 0.05 * float(np.abs(self.y).max()))
        rises = np.diff(np.abs(tail))
        self.assertLessEqual(float(rises.max()), 0.0 + 1e-6)

    def test_the_first_lap_is_bit_identical_to_the_source(self):
        out = seamless_tile(self.y, 3, musical_samples=self.n)
        np.testing.assert_allclose(out[: self.n], self.y[: self.n], rtol=0, atol=0)


class TestFallbacksAreSafe(unittest.TestCase):
    def test_a_single_repetition_is_returned_untouched(self):
        y = _pass_with_tail(2.0)
        np.testing.assert_allclose(seamless_tile(y, 1, musical_samples=len(y) - SR), y)

    def test_a_buffer_with_no_tail_falls_back_to_a_plain_tile(self):
        y = _pass_with_tail(2.0, tail_sec=0.0)
        out = seamless_tile(y, 3, musical_samples=len(y))
        self.assertEqual(len(out), len(y) * 3)

    def test_a_nonsensical_musical_length_does_not_crash(self):
        y = _pass_with_tail(2.0)
        for bad in (0, -5, len(y) + 1000):
            with self.subTest(musical_samples=bad):
                out = seamless_tile(y, 2, musical_samples=bad)
                self.assertGreater(len(out), 0)

    def test_an_empty_buffer_is_returned(self):
        self.assertEqual(len(seamless_tile(np.zeros(0), 3, musical_samples=0)), 0)

    def test_zero_or_negative_loops_behave_as_one(self):
        y = _pass_with_tail(1.0)
        n = int(round(1.0 * SR))
        for loops in (0, -2):
            with self.subTest(loops=loops):
                np.testing.assert_allclose(seamless_tile(y, loops, musical_samples=n), y)


class TestTheChordStripAgreesWithTheAudio(unittest.TestCase):
    """The strip assumes a lap is bars x bar_duration. The audio must match."""

    CHORDS = ["Em6", "Em6", "C7", "B7", "Em6", "Em6", "C7", "B7"]

    def _bar(self, bpm, beats_per_bar):
        return beats_per_bar * 60.0 / bpm

    def test_the_padded_audio_drifted_a_second_every_lap(self):
        bar = self._bar(100, 4)
        lap_music = len(self.CHORDS) * bar
        for lap in range(1, 8):
            drift = lap * 1.0
            self.assertAlmostEqual(lap * (lap_music + 1.0) - lap * lap_music, drift, places=6)

    def test_the_drift_reached_six_seconds_and_showed_the_wrong_chord(self):
        bar = self._bar(100, 4)
        cells = layer_chord_timeline(self.CHORDS, bar_duration=bar, loops=8)
        lap_music = len(self.CHORDS) * bar
        audio_t = 6 * (lap_music + 1.0)          # downbeat of lap 7 in the padded audio
        self.assertAlmostEqual(audio_t - 6 * lap_music, 6.0, places=6)
        shown = cells[chord_index_at(cells, audio_t)]["chord"]
        self.assertNotEqual(shown, self.CHORDS[0])

    def test_with_the_fix_every_lap_downbeat_shows_the_first_chord(self):
        for bpm, bpbar, meter in ((100, 4, "4/4"), (120, 3, "3/4"), (160, 4, "4/4")):
            with self.subTest(meter=meter, bpm=bpm):
                bar = self._bar(bpm, bpbar)
                cells = layer_chord_timeline(self.CHORDS, bar_duration=bar, loops=6)
                lap_music = len(self.CHORDS) * bar
                for lap in range(6):
                    t = lap * lap_music + 0.001
                    self.assertEqual(cells[chord_index_at(cells, t)]["chord"], self.CHORDS[0])

    def test_the_last_chord_runs_straight_into_the_first(self):
        bar = self._bar(100, 4)
        cells = layer_chord_timeline(self.CHORDS, bar_duration=bar, loops=3)
        lap_music = len(self.CHORDS) * bar
        just_before = lap_music - 0.001
        self.assertEqual(cells[chord_index_at(cells, just_before)]["chord"], self.CHORDS[-1])
        self.assertEqual(cells[chord_index_at(cells, lap_music + 0.001)]["chord"], self.CHORDS[0])

    def test_the_count_in_offsets_every_lap_equally(self):
        bar = self._bar(100, 4)
        count_in = 2 * bar
        cells = layer_chord_timeline(self.CHORDS, bar_duration=bar, loops=3, count_in_sec=count_in)
        self.assertEqual(chord_index_at(cells, count_in - 0.01), -1)   # silent during count-in
        lap_music = len(self.CHORDS) * bar
        for lap in range(3):
            with self.subTest(lap=lap + 1):
                t = count_in + lap * lap_music + 0.001
                self.assertEqual(cells[chord_index_at(cells, t)]["chord"], self.CHORDS[0])

    def test_a_paused_clock_does_not_advance_the_highlight(self):
        bar = self._bar(100, 4)
        cells = layer_chord_timeline(self.CHORDS, bar_duration=bar, loops=2)
        frozen = 3 * bar + 0.5
        self.assertEqual(chord_index_at(cells, frozen), chord_index_at(cells, frozen))

    def test_a_split_measure_still_occupies_one_bar_of_the_strip(self):
        from chord_subdivisions import parse_subdivisions, split_measure_token

        token = split_measure_token("2+2", "F7", "B7")
        parts = parse_subdivisions(token, beats_per_bar=4)
        self.assertAlmostEqual(sum(p.weight for p in parts), 4.0, places=6)
        bar = self._bar(100, 4)
        cells = layer_chord_timeline(["Am", token, "G7"], bar_duration=bar, loops=2)
        self.assertEqual(len(cells), 6)
        self.assertAlmostEqual(cells[1]["end"] - cells[1]["start"], bar, places=6)


class TestTheRealRendererLosesItsGap(unittest.TestCase):
    """One end-to-end check against real synthesized audio."""

    def test_a_rendered_pass_loops_without_silence(self):
        from backing_audio import backing_bytes_to_float

        events = [{"chord": c, "beats": 4} for c in ["Am", "Dm", "E7", "Am"]]
        bpm = 120
        y = backing_bytes_to_float(
            events, bpm=bpm, style="Pop groove", level="Beginner", time_signature="4/4"
        )
        total_beats = sum(e["beats"] for e in events)
        n = musical_sample_count(total_beats, bpm)
        self.assertLess(n, len(y), "renderer no longer pads; revisit this fix")

        old = np.tile(y, 3)
        new = seamless_tile(y, 3, musical_samples=n)
        self.assertLess(len(new), len(old))
        self.assertAlmostEqual((len(old) - len(new)) / SR, 2.0, places=1)

        mag = np.abs(new)
        thr = mag.max() * 0.001
        nz = np.nonzero(mag[:n] > thr)[0]
        self.assertLess((n - 1 - nz[-1]) / SR, 0.01)
        self.assertLessEqual(float(mag.max()), float(np.abs(y).max()) * 1.01)


if __name__ == "__main__":
    unittest.main()
