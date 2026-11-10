"""Follow-up B: a single-chord bar with an explicit beat weight ("D:4") is the chord D, never a chord named "D:4"."""
import unittest

from chord_subdivisions import chord_stream
from improvisation_motif import section_harmony_rows


class TestChordStream(unittest.TestCase):
    def test_single_bar_weight_is_stripped(self):
        self.assertEqual(chord_stream(["D:4", "C:4", "Am:4", "G"]), ["D", "C", "Am", "G"])

    def test_subdivided_unchanged(self):
        self.assertEqual(chord_stream(["G:3.5|C:0.5p", "Bm:2|Em:2p"]), ["G", "C", "Bm", "Em"])

    def test_slash_and_extended_chords_keep_their_names(self):
        self.assertEqual(chord_stream(["C/E:4", "F#m7b5:2", "N.C."]), ["C/E", "F#m7b5", "N.C."])


class TestMissionChordMap(unittest.TestCase):
    def test_say_chord_map_has_no_beat_suffix(self):
        from song_catalog.lyric_chord_charts import SAY_MAIN_LOOP

        rows = section_harmony_rows({"Verse": list(SAY_MAIN_LOOP)})
        for _label, clean, raw in rows:
            for c in clean + raw:
                self.assertNotIn(":", c)
        self.assertEqual(rows[0][1], ["Bb", "Eb", "Gm", "F"])


if __name__ == "__main__":
    unittest.main()
