"""Issues 32-34, 37: selected written chord == example chord; sounding (concert) pitches stay in the concert chord."""
import unittest

from improvisation_missions import load_mission_example
from instrument_transposition import SAXOPHONE_TYPES, TRANSPOSING_SEMITONE_STEPS, written_key_for_type
from music_theory import transpose_chord

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from test_move_mission_by_degree import CHORD_TONES, PENT, _setup  # noqa: E402

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PC = {n: i for i, n in enumerate(NAMES)}
PC.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})
CHORD_PCS = {"m6": (0, 3, 7, 9), "m7": (0, 3, 7, 10), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11)}


def _pc(note):
    return PC[note.replace("♯", "#").replace("♭", "b")]


class TestWrittenKeyMissionExample(unittest.TestCase):
    def test_example_chord_is_the_selected_written_chord_and_concert_pitches_fit(self):
        cases = [("Em", "E", "m6"), ("Am", "A", "m7"), ("G", "G", "7")]
        for typ in SAXOPHONE_TYPES:
            steps = TRANSPOSING_SEMITONE_STEPS[typ]          # concert -> written semitones
            for concert_key, root, qual in cases:
                concert_chord = root + qual if qual != "7" else root + "7"
                written_chord = transpose_chord(concert_chord, steps % 12, reference_key=written_key_for_type(concert_key, typ))
                with self.subTest(sax=typ, concert=concert_chord, written=written_chord):
                    s, ctx = _setup(CHORD_TONES, written_chord, concert_key, transposing=typ)
                    ex = load_mission_example(s, ctx)
                    self.assertEqual(ex.chord, written_chord)                      # label is the written chord
                    self.assertEqual(ex.motif.get("chord"), written_chord)
                    self.assertNotEqual(ex.chord, concert_chord) if steps % 12 else None
                    # sounding pitches (written - steps) are chord tones of the CONCERT chord
                    concert_pcs = {(PC[root] + t) % 12 for t in CHORD_PCS[qual]}
                    sounding = {(_pc(n) - steps) % 12 for n in ex.motif["notes"]}
                    self.assertTrue(sounding <= concert_pcs, (sounding, concert_pcs))

    def test_concert_chart_unchanged_when_written_key_off(self):
        s, ctx = _setup(PENT, "Em6", "E")
        ex = load_mission_example(s, ctx)
        self.assertEqual(ex.chord, "Em6")
        self.assertEqual(ex.concert_key, "E")


if __name__ == "__main__":
    unittest.main()
