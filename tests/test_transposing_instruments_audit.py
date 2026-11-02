"""Transposing-instrument audit: written key, written pitch and the instrument label agree."""

from __future__ import annotations

import unittest

from composition_songs_bridge import composition_written_pitch_semitones
from instrument_transposition import (
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    instrument_display_name,
    selected_transposing_type,
    written_key_for_instrument,
)

SAX = {
    "Soprano saxophone (Bb)": ("Gm", 2, "Soprano"),
    "Alto saxophone (Eb)": ("Dm", 9, "Alto"),
    "Tenor saxophone (Bb)": ("Gm", 14, "Tenor"),   # written a major ninth above concert
    "Baritone saxophone (Eb)": ("Dm", 21, "Baritone"),  # written a major thirteenth above
}


class TestWrittenKeys(unittest.TestCase):
    def test_f_minor_concert_for_every_saxophone(self) -> None:
        for sax_type, (written, _pitch, _name) in SAX.items():
            with self.subTest(sax=sax_type):
                ss = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: sax_type}
                self.assertEqual(written_key_for_instrument("Fm", "Saxophone", ss), written)

    def test_the_tenor_is_g_minor_not_d_minor(self) -> None:
        # D minor is the *alto/baritone* answer; a tenor chart in D minor would be a wrong-sax bug
        ss = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)"}
        self.assertEqual(written_key_for_instrument("Fm", "Saxophone", ss), "Gm")

    def test_bb_and_c_instruments(self) -> None:
        for inst in ("Trumpet", "Clarinet"):
            self.assertEqual(written_key_for_instrument("Fm", inst, {}), "Gm", inst)
            self.assertEqual(written_key_for_instrument("Eb", inst, {}), "F", inst)
        for inst in ("Flute", "Piano", "Guitar", "Voice", "Bass"):
            self.assertEqual(written_key_for_instrument("Fm", inst, {}), "Fm", inst)

    def test_major_keys(self) -> None:
        tenor = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)"}
        alto = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)"}
        self.assertEqual(written_key_for_instrument("C", "Saxophone", tenor), "D")
        self.assertEqual(written_key_for_instrument("Bb", "Saxophone", tenor), "C")
        self.assertEqual(written_key_for_instrument("C", "Saxophone", alto), "A")
        self.assertEqual(written_key_for_instrument("Eb", "Saxophone", alto), "C")

    def test_the_label_and_the_key_come_from_the_same_selected_type(self) -> None:
        for sax_type, (written, _pitch, name) in SAX.items():
            ss = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: sax_type}
            chosen = selected_transposing_type(ss, "Saxophone")
            self.assertEqual(chosen, sax_type)
            self.assertIn(name, instrument_display_name(chosen, "Saxophone"))
            self.assertEqual(written_key_for_instrument("Fm", "Saxophone", ss), written)

    def test_an_unset_generic_saxophone_defaults_to_the_alto_consistently(self) -> None:
        ss: dict = {}
        chosen = selected_transposing_type(ss, "Saxophone")
        self.assertEqual(chosen, "Alto saxophone (Eb)")
        self.assertEqual(written_key_for_instrument("Fm", "Saxophone", ss), "Dm")


class TestWrittenPitchOctaves(unittest.TestCase):
    def test_written_pitch_offsets(self) -> None:
        for sax_type, (_w, semis, _n) in SAX.items():
            ss = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: sax_type}
            self.assertEqual(composition_written_pitch_semitones("Saxophone", ss), semis, sax_type)
        self.assertEqual(composition_written_pitch_semitones("Trumpet", {}), 2)
        self.assertEqual(composition_written_pitch_semitones("Clarinet", {}), 2)
        self.assertEqual(composition_written_pitch_semitones("Flute", {}), 0)
        self.assertEqual(composition_written_pitch_semitones("Piano", {}), 0)

    def test_concert_f4_is_written_d5_on_alto_and_g5_on_tenor(self) -> None:
        # MIDI: F4 = 65. Alto written D5 = 74 (+9); tenor written G5 = 79 (+14)
        self.assertEqual(65 + composition_written_pitch_semitones("Saxophone", {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)"}), 74)
        self.assertEqual(65 + composition_written_pitch_semitones("Saxophone", {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)"}), 79)


if __name__ == "__main__":
    unittest.main()
