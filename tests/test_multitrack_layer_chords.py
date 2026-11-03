"""Multitrack: each recording layer reads the progression in ITS player's chords, while the backing and
the recording stay in concert pitch.
"""
import re
import unittest

from multitrack_layer_chords import (
    CONCERT_INSTRUMENTS,
    WRITTEN_INSTRUMENTS,
    chord_index_at,
    concert_bar_chords,
    concert_sections_for_backing,
    default_layer_instrument,
    layer_chart_key,
    layer_chord_strip_html,
    layer_chord_timeline,
    layer_instrument,
    layer_instrument_options,
    layer_key_label,
    project_chords_for_layer,
    transport_clock_script,
)

CONCERT = ["Am", "Am", "Am", "Am", "Em", "Em", "Am", "D7", "Am"]


class TestPerLayerChordNames(unittest.TestCase):
    def test_concert_pitch_instruments_read_the_sounding_chords(self):
        for inst in ("Flute", "Piano", "Voice", "Bass", "Violin"):
            with self.subTest(inst=inst):
                self.assertEqual(project_chords_for_layer(CONCERT, concert_key="Am", instrument=inst), CONCERT)
                self.assertEqual(layer_chart_key("Am", inst), ("Am", "concert"))
                self.assertEqual(layer_key_label("Am", inst), "Concert key: Am")

    def test_alto_saxophone_reads_its_written_chords(self):
        # The assignment's example: concert C minor backing, alto layer reads A minor.
        self.assertEqual(layer_chart_key("Cm", "Alto saxophone (Eb)"), ("Am", "written"))
        self.assertEqual(layer_key_label("Cm", "Alto saxophone (Eb)"), "Written key: Am")
        self.assertEqual(
            project_chords_for_layer(["Cm", "Fm", "G7"], concert_key="Cm", instrument="Alto saxophone (Eb)"),
            ["Am", "Dm", "E7"],
        )

    def test_every_written_instrument_transposes_and_keeps_the_chord_quality(self):
        for inst in WRITTEN_INSTRUMENTS:
            with self.subTest(inst=inst):
                key, mode = layer_chart_key("Cm", inst)
                self.assertEqual(mode, "written")
                self.assertNotEqual(key, "Cm")
                out = project_chords_for_layer(["Cm", "G7"], concert_key="Cm", instrument=inst)
                self.assertTrue(out[0].endswith("m"), out)
                self.assertTrue(out[1].endswith("7"), out)

    def test_layers_can_show_different_representations_at_the_same_time(self):
        flute = project_chords_for_layer(CONCERT, concert_key="Am", instrument="Flute")
        alto = project_chords_for_layer(CONCERT, concert_key="Am", instrument="Alto saxophone (Eb)")
        tenor = project_chords_for_layer(CONCERT, concert_key="Am", instrument="Tenor saxophone (Bb)")
        self.assertEqual(flute, CONCERT)
        self.assertNotEqual(alto, flute)
        self.assertNotEqual(tenor, alto)
        self.assertEqual(len(flute), len(alto), len(tenor))

    def test_guitar_layer_follows_capo_shape_when_shape_mode_is_on(self):
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        session = {CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: "D"}
        key, mode = layer_chart_key("C", "Guitar", session)
        self.assertEqual(mode, "shape")
        self.assertEqual(key, "D")
        self.assertEqual(layer_key_label("C", "Guitar", session), "Shape key: D")
        self.assertEqual(layer_chart_key("C", "Guitar", {}), ("C", "concert"))      # capo off: concert

    def test_a_written_layer_does_not_depend_on_the_global_written_chart_checkbox(self):
        from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY

        for flag in (True, False, None):
            session = {CHART_IN_INSTRUMENT_KEY_KEY: flag}
            self.assertEqual(layer_chart_key("Cm", "Alto saxophone (Eb)", session)[0], "Am")
            self.assertEqual(layer_chart_key("Cm", "Flute", session)[0], "Cm")


class TestLayerInstrumentSelection(unittest.TestCase):
    def test_slot_defaults_are_sensible_and_valid(self):
        for slot, want in (
            ("Guitar", "Guitar"),
            ("Bass", "Bass"),
            ("Piano / Keys", "Piano"),
            ("Vocals", "Voice"),
            ("Sax / winds", "Alto saxophone (Eb)"),
            ("Extra layer", "Piano"),
        ):
            self.assertEqual(default_layer_instrument(slot), want)
            self.assertIn(want, layer_instrument_options())

    def test_sax_layer_follows_the_players_own_saxophone_type(self):
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)"}
        self.assertEqual(default_layer_instrument("Sax / winds", session), "Tenor saxophone (Bb)")

    def test_an_explicit_pick_wins_and_a_bad_one_is_ignored(self):
        self.assertEqual(layer_instrument({"mt_layer_instrument_Extra layer": "Flute"}, "Extra layer"), "Flute")
        self.assertEqual(layer_instrument({"mt_layer_instrument_Extra layer": "Kazoo"}, "Extra layer"), "Piano")
        self.assertEqual(layer_instrument(None, "Vocals"), "Voice")

    def test_options_cover_concert_and_written_families_without_duplicates(self):
        opts = layer_instrument_options()
        self.assertEqual(len(opts), len(set(opts)))
        self.assertTrue(set(CONCERT_INSTRUMENTS) <= set(opts))
        self.assertTrue(set(WRITTEN_INSTRUMENTS) <= set(opts))


class TestTimeline(unittest.TestCase):
    def test_one_cell_per_played_bar_including_repeats(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=2.0, loops=3, count_in_sec=0.0)
        self.assertEqual(len(cells), len(CONCERT) * 3)
        self.assertEqual([c["bar"] for c in cells[:3]], [1, 2, 3])
        self.assertEqual(cells[len(CONCERT)]["pass"], 2)

    def test_count_in_delays_every_bar_and_highlights_nothing_while_it_runs(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=2.0, loops=1, count_in_sec=4.0)
        self.assertEqual(cells[0]["start"], 4.0)
        for t in (0.0, 1.0, 3.99):
            self.assertEqual(chord_index_at(cells, t), -1, t)
        self.assertEqual(chord_index_at(cells, 4.0), 0)

    def test_cells_are_contiguous_and_cover_the_whole_session(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=1.5, loops=2, count_in_sec=3.0)
        for a, b in zip(cells, cells[1:]):
            self.assertAlmostEqual(a["end"], b["start"], places=4)
        self.assertAlmostEqual(cells[-1]["end"], 3.0 + len(CONCERT) * 2 * 1.5, places=4)

    def test_tempo_change_moves_every_boundary(self):
        slow = layer_chord_timeline(CONCERT, bar_duration=3.0, loops=1)
        fast = layer_chord_timeline(CONCERT, bar_duration=1.0, loops=1)
        self.assertEqual(chord_index_at(slow, 3.5), 1)
        self.assertEqual(chord_index_at(fast, 3.5), 3)

    def test_after_the_last_bar_nothing_is_current(self):
        cells = layer_chord_timeline(CONCERT, bar_duration=1.0, loops=1)
        self.assertEqual(chord_index_at(cells, len(CONCERT) + 0.1), -1)

    def test_degenerate_inputs_are_safe(self):
        self.assertEqual(layer_chord_timeline([], bar_duration=2.0), [])
        self.assertEqual(layer_chord_timeline(CONCERT, bar_duration=0), [])
        self.assertEqual(chord_index_at([], 1.0), -1)


class TestConcertRecovery(unittest.TestCase):
    """The page chart may be written/shape; the sounding progression must be recovered from it."""

    CHART = {"Verse": ["Am", "Dm"], "Chorus": ["E7", "Am"]}

    def test_chart_sections_are_unprojected_when_no_canonical_concert_map_exists(self):
        bars = concert_bar_chords(None, chart_sections=self.CHART, chart_key="Am", concert_key="Cm")
        self.assertEqual(bars, ["Cm", "Fm", "G7", "Cm"])            # alto written Am -> concert Cm

    def test_same_key_is_a_no_op(self):
        bars = concert_bar_chords(None, chart_sections=self.CHART, chart_key="Am", concert_key="Am")
        self.assertEqual(bars, ["Am", "Dm", "E7", "Am"])

    def test_selected_sections_limit_the_bars(self):
        bars = concert_bar_chords(
            None, chart_sections=self.CHART, selected_sections=["Chorus"], chart_key="Am", concert_key="Am"
        )
        self.assertEqual(bars, ["E7", "Am"])

    def test_backing_sections_are_concert_so_the_audio_is_never_transposed(self):
        out = concert_sections_for_backing(None, self.CHART, chart_key="Am", concert_key="Cm")
        self.assertEqual(out, {"Verse": ["Cm", "Fm"], "Chorus": ["G7", "Cm"]})

    def test_round_trip_display_matches_the_original_chart_for_that_instrument(self):
        # chart (alto written Am) -> concert -> projected back for an alto layer == the original chart
        bars = concert_bar_chords(None, chart_sections=self.CHART, chart_key="Am", concert_key="Cm")
        back = project_chords_for_layer(bars, concert_key="Cm", instrument="Alto saxophone (Eb)")
        self.assertEqual(back, ["Am", "Dm", "E7", "Am"])


class TestStripHtml(unittest.TestCase):
    def _html(self, **kw):
        cells = layer_chord_timeline(["Am", "D7"], bar_duration=2.0, count_in_sec=2.0)
        args = {"layer_id": "Sax / winds", "key_label": "Written key: Am", "instrument": "Alto saxophone (Eb)"}
        args.update(kw)
        return layer_chord_strip_html(cells, **args)

    def test_chords_key_label_and_instrument_are_rendered(self):
        out = self._html()
        self.assertIn(">Am<", out)
        self.assertIn(">D7<", out)
        self.assertIn("Written key: Am", out)
        self.assertIn("Alto saxophone (Eb)", out)

    def test_it_reads_the_shared_transport_clock_and_never_plays_audio(self):
        out = self._html()
        self.assertIn("__mtClock", out)
        self.assertIn("window.parent", out)
        self.assertIn("c.playing", out)                      # only advances while the transport plays
        self.assertNotIn("<audio", out)                      # the strip is display-only
        self.assertNotIn("new Audio", out)

    def test_the_id_is_safe_and_unique_per_layer(self):
        a = self._html(layer_id="Sax / winds")
        b = self._html(layer_id="Piano / Keys")
        self.assertIn('id="mtc-Sax___winds"', a)
        self.assertIn('id="mtc-Piano___Keys"', b)
        self.assertNotIn("Sax / winds", re.findall(r'id="[^"]*"', a)[0])

    def test_empty_range_says_so_instead_of_breaking(self):
        out = layer_chord_strip_html([], layer_id="x", key_label="Concert key: C", instrument="Flute")
        self.assertIn("No chords in the selected range.", out)

    def test_transport_publishes_the_same_clock_key(self):
        self.assertIn("__mtClock", transport_clock_script())
        self.assertIn("mtPublishClock", transport_clock_script())


if __name__ == "__main__":
    unittest.main()
