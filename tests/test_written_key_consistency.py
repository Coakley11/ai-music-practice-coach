"""Original / Practice / Written key stay coherent for a transposed song on a transposing instrument.

Blues in F minor played at Practice Key E minor: the Original Key is still F minor, the Practice Key is
E minor, and the written key follows the saxophone the player actually selected. No unrelated key (the
reported stray "C") may appear in any of them.
"""
import unittest

from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SAXOPHONE_TYPES,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    charts_shown_in_key,
    chart_in_instrument_key,
    effective_chart_key,
    selected_transposing_type,
    written_key_for_instrument,
    written_key_for_type,
)

ORIGINAL = "Fm"
PRACTICE = "Em"
# concert E minor as each saxophone reads it
WRITTEN = {
    "Alto saxophone (Eb)": "C#m",
    "Baritone saxophone (Eb)": "C#m",
    "Tenor saxophone (Bb)": "F#m",
    "Soprano saxophone (Bb)": "F#m",
}


def _session(sax, written_on):
    return {
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: sax,
        CHART_IN_INSTRUMENT_KEY_KEY: written_on,
        "original_key": ORIGINAL,
        "concert_key": PRACTICE,
        "display_key": PRACTICE,
    }


class TestWrittenKeyFollowsTheSelectedSaxophone(unittest.TestCase):
    def test_each_saxophone_reads_its_own_written_key(self):
        for sax, want in WRITTEN.items():
            with self.subTest(sax=sax):
                self.assertEqual(written_key_for_type(PRACTICE, sax), want)
                self.assertEqual(written_key_for_instrument(PRACTICE, "Saxophone", _session(sax, True)), want)

    def test_every_supported_saxophone_is_covered(self):
        self.assertEqual(set(SAXOPHONE_TYPES), set(WRITTEN))

    def test_switching_type_moves_the_written_key(self):
        session = _session("Alto saxophone (Eb)", True)
        self.assertEqual(effective_chart_key(PRACTICE, "Saxophone", session), ("C#m", "written"))
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Tenor saxophone (Bb)"
        self.assertEqual(selected_transposing_type(session, "Saxophone"), "Tenor saxophone (Bb)")
        self.assertEqual(effective_chart_key(PRACTICE, "Saxophone", session), ("F#m", "written"))


class TestTheToggleOnlyMovesTheChart(unittest.TestCase):
    def test_charts_follow_the_switch_both_ways(self):
        for sax, written in WRITTEN.items():
            with self.subTest(sax=sax):
                on, off = _session(sax, True), _session(sax, False)
                self.assertTrue(chart_in_instrument_key(on))
                self.assertFalse(chart_in_instrument_key(off))
                self.assertEqual(effective_chart_key(PRACTICE, "Saxophone", on), (written, "written"))
                self.assertEqual(effective_chart_key(PRACTICE, "Saxophone", off), (PRACTICE, "concert"))
                self.assertEqual(charts_shown_in_key(PRACTICE, written, show_in_instrument_key=True), written)
                self.assertEqual(charts_shown_in_key(PRACTICE, written, show_in_instrument_key=False), PRACTICE)

    def test_toggling_repeatedly_is_stable(self):
        session = _session("Alto saxophone (Eb)", False)
        for i in range(8):
            session[CHART_IN_INSTRUMENT_KEY_KEY] = bool(i % 2)
            chart, mode = effective_chart_key(PRACTICE, "Saxophone", session)
            self.assertEqual((chart, mode), ("C#m", "written") if i % 2 else (PRACTICE, "concert"))


class TestNoStrayKeyLeaks(unittest.TestCase):
    def test_the_original_key_is_never_the_practice_or_written_key(self):
        for sax, written in WRITTEN.items():
            with self.subTest(sax=sax):
                session = _session(sax, True)
                self.assertEqual(session["original_key"], ORIGINAL)       # F minor stays F minor
                self.assertNotEqual(session["original_key"], PRACTICE)
                self.assertNotEqual(written, ORIGINAL)

    def test_no_c_major_appears_anywhere_in_this_context(self):
        for sax, written in WRITTEN.items():
            with self.subTest(sax=sax):
                values = {ORIGINAL, PRACTICE, written,
                          effective_chart_key(PRACTICE, "Saxophone", _session(sax, True))[0],
                          effective_chart_key(PRACTICE, "Saxophone", _session(sax, False))[0]}
                self.assertNotIn("C", values)
                self.assertTrue(all(str(v).endswith("m") for v in values), values)   # all minor


if __name__ == "__main__":
    unittest.main()
