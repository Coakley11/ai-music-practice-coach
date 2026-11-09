"""Issue 62 — per-layer chord highlighting stays on one musical timeline.

These are timeline tests. They prove the *arithmetic* every layer strip uses is shared,
contiguous and drift-free, and they state the one external condition that arithmetic
depends on (gapless looping — Issue 59). They do not prove what a browser paints; that
still needs a running-app check.
"""

from __future__ import annotations

import unittest

from multitrack_layer_chords import (
    CONCERT_INSTRUMENTS,
    WRITTEN_INSTRUMENTS,
    chord_index_at,
    layer_chart_key,
    layer_chord_timeline,
    layer_key_label,
    project_chords_for_layer,
)

# The user's example progression, in concert pitch.
CONCERT = ["Em6", "C7", "B7", "Em6"]
BAR = 2.0  # seconds per bar
COUNT_IN = 4.0  # two bars of count-in


class OneSharedTimeline(unittest.TestCase):
    def test_cells_are_contiguous_with_no_gap_or_overlap(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=3, count_in_sec=COUNT_IN)
        self.assertEqual(len(cells), len(CONCERT) * 3)
        for earlier, later in zip(cells, cells[1:]):
            self.assertEqual(earlier["end"], later["start"])

    def test_nothing_is_highlighted_during_the_count_in(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=1, count_in_sec=COUNT_IN)
        self.assertEqual(chord_index_at(cells, 0.0), -1)
        self.assertEqual(chord_index_at(cells, COUNT_IN - 0.01), -1)
        self.assertEqual(chord_index_at(cells, COUNT_IN), 0)

    def test_every_chord_change_lands_on_its_own_bar(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=1, count_in_sec=COUNT_IN)
        for i, chord in enumerate(CONCERT):
            mid = COUNT_IN + i * BAR + BAR / 2
            self.assertEqual(cells[chord_index_at(cells, mid)]["chord"], chord)

    def test_loop_boundaries_do_not_accumulate_drift(self):
        loops = 8
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=loops, count_in_sec=COUNT_IN)
        # Absolute positions, so pass 8 is as exact as pass 1.
        for pass_no in range(loops):
            first_of_pass = cells[pass_no * len(CONCERT)]
            self.assertAlmostEqual(
                first_of_pass["start"], COUNT_IN + pass_no * len(CONCERT) * BAR, places=6
            )
            self.assertEqual(first_of_pass["chord"], CONCERT[0])
            self.assertEqual(first_of_pass["pass"], pass_no + 1)

    def test_restart_maps_back_to_the_first_bar(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=2, count_in_sec=COUNT_IN)
        self.assertEqual(chord_index_at(cells, COUNT_IN + 0.01), 0)

    def test_after_the_last_bar_nothing_is_highlighted(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=1, count_in_sec=COUNT_IN)
        self.assertEqual(chord_index_at(cells, cells[-1]["end"] + 0.01), -1)

    def test_all_layers_share_identical_cell_windows(self):
        """Flute, alto sax and guitar must refer to the same musical position."""
        windows = []
        for inst in ("Flute", "Alto saxophone (Eb)", "Guitar"):
            chords = project_chords_for_layer(
                CONCERT, concert_key="Em", instrument=inst, session_state={}
            )
            cells = layer_chord_timeline(
                chords, bar_duration=BAR, loops=2, count_in_sec=COUNT_IN
            )
            windows.append([(c["start"], c["end"], c["bar"], c["pass"]) for c in cells])
        self.assertEqual(windows[0], windows[1])
        self.assertEqual(windows[1], windows[2])


class PerLayerChordSymbols(unittest.TestCase):
    def test_concert_instruments_read_the_sounding_chords(self):
        for inst in ("Flute", "Piano"):
            self.assertIn(inst, CONCERT_INSTRUMENTS)
            self.assertEqual(
                project_chords_for_layer(
                    CONCERT, concert_key="Em", instrument=inst, session_state={}
                ),
                CONCERT,
            )
            self.assertEqual(layer_chart_key("Em", inst, {})[1], "concert")
            self.assertIn("Concert key", layer_key_label("Em", inst, {}))

    def test_alto_saxophone_reads_transposed_written_chords(self):
        self.assertIn("Alto saxophone (Eb)", WRITTEN_INSTRUMENTS)
        written = project_chords_for_layer(
            CONCERT, concert_key="Em", instrument="Alto saxophone (Eb)", session_state={}
        )
        chart, mode = layer_chart_key("Em", "Alto saxophone (Eb)", {})
        self.assertEqual(mode, "written")
        # Eb alto reads a major sixth above concert: concert E minor → C# minor.
        self.assertNotEqual(written, CONCERT)
        self.assertEqual(len(written), len(CONCERT))
        self.assertIn("Written key", layer_key_label("Em", "Alto saxophone (Eb)", {}))
        self.assertNotEqual(chart, "Em")

    def test_tenor_and_alto_read_different_written_chords(self):
        alto = project_chords_for_layer(
            CONCERT, concert_key="Em", instrument="Alto saxophone (Eb)", session_state={}
        )
        tenor = project_chords_for_layer(
            CONCERT, concert_key="Em", instrument="Tenor saxophone (Bb)", session_state={}
        )
        self.assertNotEqual(alto, tenor)

    def test_every_supported_layer_instrument_projects_without_error(self):
        for inst in list(CONCERT_INSTRUMENTS) + list(WRITTEN_INSTRUMENTS):
            chords = project_chords_for_layer(
                CONCERT, concert_key="Em", instrument=inst, session_state={}
            )
            self.assertEqual(len(chords), len(CONCERT), inst)
            self.assertTrue(all(chords), inst)


class GaplessLoopingIsRequired(unittest.TestCase):
    """The timeline assumes one loop lasts exactly ``bars x bar_duration``.

    The strip highlights by absolute elapsed audio time (the transport publishes
    ``audioCtx.currentTime - countInStartedAt``). So if the audio adds any extra time per
    repetition — the one-second decay buffer Issue 59 identified — the audible chord falls
    behind the highlight by that much on every pass. Chord sync past the first loop is only
    correct once looping is gapless, which is why Issue 59 is a dependency of this work and
    not an unrelated fix.
    """

    @staticmethod
    def _drift_after(loops: int, *, gap_per_loop: float) -> float:
        """How far the audible chord lags the highlight after ``loops`` repetitions."""
        return loops * gap_per_loop

    def test_gapless_audio_keeps_the_highlight_exact(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=4, count_in_sec=COUNT_IN)
        self.assertEqual(self._drift_after(4, gap_per_loop=0.0), 0.0)
        # With no gap, the start of pass 4 in the audio is also the start of pass 4 here.
        self.assertAlmostEqual(
            cells[3 * len(CONCERT)]["start"], COUNT_IN + 3 * len(CONCERT) * BAR, places=6
        )

    def test_a_one_second_loop_gap_misaligns_every_later_pass(self):
        # Documents the defect, not an accepted behaviour: one bar is 2 s here, so by the
        # fourth repetition the highlight is a bar and a half ahead of what is sounding.
        drift = self._drift_after(3, gap_per_loop=1.0)
        self.assertAlmostEqual(drift, 3.0)
        self.assertGreater(drift, BAR, "drift exceeds a whole bar — a visibly wrong chord")

    def test_musical_loop_length_is_the_contract(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, loops=2, count_in_sec=COUNT_IN)
        one_pass = cells[len(CONCERT)]["start"] - cells[0]["start"]
        self.assertAlmostEqual(one_pass, len(CONCERT) * BAR, places=6)


class DegenerateInput(unittest.TestCase):
    def test_no_chords_or_no_bar_duration_yields_no_cells(self):
        self.assertEqual(layer_chord_timeline([], bar_duration=BAR), [])
        self.assertEqual(layer_chord_timeline(CONCERT, bar_duration=0), [])
        self.assertEqual(layer_chord_timeline(CONCERT, bar_duration=-1), [])

    def test_zero_or_negative_loops_still_plays_once(self):
        self.assertEqual(len(layer_chord_timeline(CONCERT, bar_duration=BAR, loops=0)), 4)
        self.assertEqual(len(layer_chord_timeline(CONCERT, bar_duration=BAR, loops=-3)), 4)

    def test_negative_count_in_is_clamped_not_subtracted(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=BAR, count_in_sec=-5)
        self.assertEqual(cells[0]["start"], 0.0)

    def test_empty_chord_slots_keep_their_bar(self):
        cells = layer_chord_timeline(["Em6", "", "B7"], bar_duration=BAR)
        self.assertEqual(len(cells), 3)
        self.assertEqual(cells[1]["chord"], "")
        self.assertEqual(cells[1]["bar"], 2)


if __name__ == "__main__":
    unittest.main()
