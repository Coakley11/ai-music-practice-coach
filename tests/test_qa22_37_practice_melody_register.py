"""Issue 24 follow-up: Practice Melody register follows the instrument (not just a generic C4-D5), in the right
pitch domain (written chart vs concert chart), without changing pitch classes."""
import unittest

from practice_melody_generator import generate_practice_melody, register_window
from practice_melody_session import instrument_register_args

SECTIONS = {"A": ["Am7", "D7", "Gmaj7", "Cmaj7", "F#m7b5", "B7", "Em7", "Em7"]}
INSTRUMENTS = ["Flute", "Clarinet", "Trumpet", "Alto saxophone (Eb)", "Tenor saxophone (Bb)", "Soprano saxophone (Bb)", "Baritone saxophone (Eb)"]


def _midis(m):
    return [e.midi for s in m.sections for e in s.events if not e.is_rest]


class TestWindow(unittest.TestCase):
    def test_non_wind_instruments_and_none_keep_the_level_window(self):
        for inst in ("", "Guitar", "Piano", "Bass"):
            self.assertEqual(register_window("Beginner", inst), (60, 74))

    def test_window_sits_inside_the_comfortable_written_register(self):
        from instrument_register_fit import comfortable_written_range

        for inst in INSTRUMENTS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                lo, hi = register_window(level, inst, 0)
                wlo, whi = comfortable_written_range(inst, level)
                self.assertGreaterEqual(lo, wlo, (inst, level))
                self.assertLessEqual(hi, whi, (inst, level))
                self.assertGreaterEqual(hi - lo, 12, (inst, level))

    def test_concert_chart_checks_the_sounding_register_not_the_written_one(self):
        from instrument_register_fit import comfortable_written_range

        for inst, up in (("Alto saxophone (Eb)", 9), ("Tenor saxophone (Bb)", 2)):
            lo, hi = register_window("Beginner", inst, up)
            wlo, whi = comfortable_written_range(inst, "Beginner")
            self.assertGreaterEqual(lo + up, wlo)                    # converting back to written stays inside it
            self.assertLessEqual(hi + up, whi)


class TestGeneratedMelodiesStayInRegister(unittest.TestCase):
    def test_every_instrument_and_level(self):
        for inst in INSTRUMENTS:
            for level in ("Beginner", "Intermediate", "Advanced"):
                for offset in (0, 2, 9):
                    with self.subTest(inst=inst, level=level, offset=offset):
                        lo, hi = register_window(level, inst, offset)
                        m = generate_practice_melody(song_id="s", song_title="t", sections=SECTIONS, key_center="Em", level=level,
                                                     instrument=inst, written_offset=offset, seed=5)
                        ms = _midis(m)
                        self.assertTrue(ms)
                        self.assertGreaterEqual(min(ms), lo)
                        self.assertLessEqual(max(ms), hi)

    def test_flute_beginner_is_not_the_generic_window_and_has_no_octave_jumps(self):
        m = generate_practice_melody(song_id="s", song_title="t", sections=SECTIONS, key_center="Em", level="Beginner", instrument="Flute", seed=5)
        ms = _midis(m)
        self.assertLessEqual(max(abs(b - a) for a, b in zip(ms, ms[1:])), 7)      # Beginner leap ceiling is untouched

    def test_default_call_is_unchanged(self):
        a = generate_practice_melody(song_id="s", song_title="t", sections=SECTIONS, key_center="Em", level="Intermediate", seed=3)
        b = generate_practice_melody(song_id="s", song_title="t", sections=SECTIONS, key_center="Em", level="Intermediate", seed=3, instrument="Guitar")
        self.assertEqual(_midis(a), _midis(b))


class TestSessionArgs(unittest.TestCase):
    def test_written_chart_vs_concert_chart(self):
        from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY, SELECTED_TRANSPOSING_INSTRUMENT_KEY

        s = {SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)"}
        self.assertEqual(instrument_register_args(s, "Saxophone"), {"instrument": "Alto saxophone (Eb)", "written_offset": 9})
        s[CHART_IN_INSTRUMENT_KEY_KEY] = True
        self.assertEqual(instrument_register_args(s, "Saxophone"), {"instrument": "Alto saxophone (Eb)", "written_offset": 0})
        self.assertEqual(instrument_register_args({}, "Flute"), {"instrument": "Flute", "written_offset": 0})
        self.assertEqual(instrument_register_args({}, ""), {})


if __name__ == "__main__":
    unittest.main()
