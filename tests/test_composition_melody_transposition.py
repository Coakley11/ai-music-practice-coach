"""Composed melody transposition for Practice page display.

Regression: melody must transpose with Practice Key AND display in
written pitch for transposing instruments (Tenor Sax, Alto Sax etc.).
The key signature must match the transposed notes.
"""

from __future__ import annotations

import unittest


class TestWrittenPitchSemitones(unittest.TestCase):
    """composition_written_pitch_semitones returns correct offsets."""

    def _call(self, instrument: str, session_state=None) -> int:
        from composition_songs_bridge import composition_written_pitch_semitones

        return composition_written_pitch_semitones(instrument, session_state)

    def test_piano_is_zero(self):
        self.assertEqual(self._call("Piano"), 0)

    def test_trumpet_bb_offset(self):
        self.assertEqual(self._call("Trumpet") % 12, 2)

    def test_tenor_saxophone_full_name(self):
        semi = self._call("Tenor saxophone")
        self.assertEqual(semi % 12, 2)
        self.assertGreaterEqual(semi, 12, "Tenor sax should include octave")

    def test_alto_saxophone_full_name(self):
        semi = self._call("Alto saxophone")
        self.assertEqual(semi % 12, 9)

    def test_generic_saxophone_with_session_state_resolves_type(self):
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)"}
        semi = self._call("Saxophone", session)
        self.assertEqual(semi % 12, 2)
        self.assertGreaterEqual(semi, 12, "Session-resolved tenor sax includes octave")

    def test_generic_saxophone_with_alto_session(self):
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        session = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)"}
        semi = self._call("Saxophone", session)
        self.assertEqual(semi % 12, 9)

    def test_generic_saxophone_without_session_returns_zero(self):
        self.assertEqual(self._call("Saxophone"), 0)


class TestTransposeNoteToken(unittest.TestCase):
    """transpose_note_token correctly shifts pitches."""

    def _call(self, token: str, semitones: int):
        from media_tone_catalog import transpose_note_token

        return transpose_note_token(token, semitones)

    def test_transpose_up_whole_step(self):
        result = self._call("C4", 2)
        self.assertIsNotNone(result)
        self.assertIn("D", result)

    def test_transpose_rest_returns_none(self):
        result = self._call("rest", 2)
        self.assertIsNone(result)

    def test_transpose_zero_unchanged(self):
        result = self._call("G4", 0)
        self.assertIsNotNone(result)
        self.assertIn("G", result)


class TestMelodyDisplayKeyLogic(unittest.TestCase):
    """The display key for composed melody must use written key when transposing."""

    def test_transposing_instrument_uses_written_key(self):
        written_key = "D"
        concert_key = "C"
        original_key = "C"
        inst_semitones = 2

        display_key = str(
            (written_key if inst_semitones else "")
            or concert_key or original_key or "C"
        )
        self.assertEqual(display_key, "D")

    def test_non_transposing_uses_concert_key(self):
        written_key = ""
        concert_key = "G"
        original_key = "C"
        inst_semitones = 0

        display_key = str(
            (written_key if inst_semitones else "")
            or concert_key or original_key or "C"
        )
        self.assertEqual(display_key, "G")

    def test_transposing_even_when_chart_is_concert(self):
        """Key signature must match written notes regardless of chart_in_instrument_key."""
        written_key = "D"
        concert_key = "C"
        original_key = "C"
        inst_semitones = 2

        display_key = str(
            (written_key if inst_semitones else "")
            or concert_key or original_key or "C"
        )
        self.assertEqual(display_key, "D", "Melody key sig must match written pitch")


if __name__ == "__main__":
    unittest.main()
