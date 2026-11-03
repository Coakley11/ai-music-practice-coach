"""Issues 22/23: Practice Melody follows each chord's own scale and prepares/resolves tensions; shapes the line."""
import unittest

from chord_scale_selection import blue_note_pcs, chord_scale_name, chord_scale_pcs
from music_theory import pitch_class_from_spelled_note, spell_chord_tones
from practice_melody_generator import generate_practice_melody

NN = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
A, B_, C_, D, E, F, FS, G, GS = 9, 11, 0, 2, 4, 5, 6, 7, 8


def pcs(chord):
    return {pitch_class_from_spelled_note(t) % 12 for t in spell_chord_tones(chord)}


def _melody(chords, key, level="Intermediate", style="Blues", seed=1, tempo=100.0):
    return generate_practice_melody(
        song_id="t", song_title="t", sections={"A": chords}, section_order=["A"], key_center=key,
        level=level, tempo_bpm=tempo, style=style, seed=seed,
    )


def _events(m):
    return [e for sec in m.sections for e in sec.events]


class TestChordScales(unittest.TestCase):
    def test_am6_is_dorian_with_f_sharp_as_chord_tone(self):
        self.assertIn(FS, pcs("Am6"))
        self.assertEqual(chord_scale_name("Am6", "Am"), "dorian")
        self.assertIn(FS, chord_scale_pcs("Am6", "Am"))
        self.assertNotIn(F, chord_scale_pcs("Am6", "Am"))

    def test_plain_minor_seventh_in_minor_key_stays_aeolian(self):
        self.assertEqual(chord_scale_name("Am7", "Am"), "aeolian")
        self.assertIn(F, chord_scale_pcs("Am7", "Am"))

    def test_d7_has_no_g_sharp_unless_the_symbol_asks(self):
        self.assertEqual(chord_scale_name("D7", "Am"), "mixolydian")
        self.assertNotIn(GS, chord_scale_pcs("D7", "Am"))
        self.assertIn(GS, chord_scale_pcs("D7#11", "Am"))
        self.assertEqual(chord_scale_name("D7#11", "Am"), "lydian_dominant")

    def test_altered_colour_only_when_written(self):
        self.assertEqual(chord_scale_name("G7", "C"), "mixolydian")
        self.assertEqual(chord_scale_name("G7alt", "C"), "altered")
        self.assertEqual(chord_scale_name("E7b9", "Am"), "phrygian_dominant")
        self.assertEqual(chord_scale_name("C+", "C"), "whole_tone")

    def test_ii_V_I_modes(self):
        self.assertEqual([chord_scale_name(c, "C") for c in ("Dm7", "G7", "Cmaj7")], ["dorian", "mixolydian", "ionian"])

    def test_half_diminished_and_diminished(self):
        self.assertEqual(chord_scale_name("Bm7b5", "C"), "locrian")
        self.assertEqual(chord_scale_name("Cdim7", "C"), "diminished_whole_half")

    def test_every_scale_contains_every_chord_tone(self):
        for chord in ("Am6", "Fm6", "C6", "Am7", "D7", "Bm7b5", "Cdim7", "Cmaj7", "E7b9", "D7#11", "Gsus4", "Am(maj7)", "C69"):
            with self.subTest(chord=chord):
                self.assertTrue(pcs(chord) <= set(chord_scale_pcs(chord, "Am")), chord)

    def test_blues_colour_only_in_blues_style(self):
        self.assertEqual(blue_note_pcs("D7", "Pop"), [])
        self.assertTrue(blue_note_pcs("D7", "Blues"))


class TestGeneratedMelodyFollowsHarmony(unittest.TestCase):
    PROG = ["Am6", "D7", "Am7", "E7", "Am6", "D7", "Am7", "E7"]

    def test_chord_tones_and_scale_tones_only_with_prepared_approaches(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            for seed in range(1, 25):
                m = _melody(self.PROG, "Am", level=level, seed=seed)
                evs = [e for e in _events(m) if not e.is_rest]
                for i, e in enumerate(evs):
                    pc = e.midi % 12
                    chord = e.chord
                    if e.tone_role == "chord_tone":
                        self.assertIn(pc, pcs(chord), (level, seed, chord, NN[pc]))
                    elif e.tone_role == "passing":
                        allowed = set(chord_scale_pcs(chord, "Am", style="Blues")) | set(blue_note_pcs(chord, "Blues"))
                        self.assertIn(pc, allowed, (level, seed, chord, NN[pc]))
                    elif e.tone_role == "approach":
                        nxt = evs[i + 1]
                        self.assertIn(nxt.midi % 12, pcs(nxt.chord), (level, seed))     # resolved onto a chord tone
                        self.assertEqual(min((nxt.midi - e.midi) % 12, (e.midi - nxt.midi) % 12), 1)   # by half step
                        self.assertNotEqual(nxt.chord, chord)                             # only before a chord change

    def test_f_natural_never_replaces_the_sixth_on_am6_and_g_sharp_not_a_passing_tone_on_d7(self):
        for seed in range(1, 40):
            m = _melody(self.PROG, "Am", level="Advanced", seed=seed)
            prev = None
            for e in _events(m):
                if e.is_rest:
                    continue
                if e.chord == "Am6" and e.tone_role in ("passing", "chord_tone"):
                    self.assertNotEqual(e.midi % 12, F, (seed, e.tone_role))
                if e.chord == "D7" and e.tone_role == "passing" and e.midi % 12 == GS:
                    # the blues b5 is allowed only as a chromatic neighbour of the previous note (G or A)
                    self.assertIn(prev % 12, (G, A), seed)
                prev = e.midi

    def test_deterministic_for_a_seed(self):
        a = [(e.midi, e.duration_beats) for e in _events(_melody(self.PROG, "Am", seed=7))]
        b = [(e.midi, e.duration_beats) for e in _events(_melody(self.PROG, "Am", seed=7))]
        self.assertEqual(a, b)

    def test_levels_differ_in_rhythm_density(self):
        def notes(level):
            return sum(len([e for e in _events(_melody(self.PROG, "Am", level=level, seed=s)) if not e.is_rest]) for s in range(1, 16))
        self.assertLess(notes("Beginner"), notes("Intermediate"))
        self.assertLessEqual(notes("Intermediate"), notes("Advanced") + 40)

    def test_rhythms_fill_each_measure_exactly(self):
        for level in ("Beginner", "Advanced"):
            m = _melody(self.PROG, "Am", level=level, seed=3)
            per = {}
            for e in _events(m):
                per[e.measure] = per.get(e.measure, 0.0) + e.duration_beats
            self.assertTrue(all(abs(v - 4.0) < 1e-6 for v in per.values()), per)

    def test_contour_is_not_a_one_way_climb(self):
        down = up = 0
        for seed in range(1, 30):
            evs = [e for e in _events(_melody(self.PROG, "Am", level="Intermediate", seed=seed)) if not e.is_rest]
            for a, b in zip(evs, evs[1:]):
                if b.midi > a.midi:
                    up += 1
                elif b.midi < a.midi:
                    down += 1
        self.assertGreater(down, 0)
        self.assertGreater(up, 0)
        self.assertLess(abs(up - down) / (up + down), 0.35)

    def test_level_register_respected(self):
        lows = {"Beginner": 60, "Intermediate": 57, "Advanced": 55}
        highs = {"Beginner": 74, "Intermediate": 77, "Advanced": 81}
        for level in lows:
            for seed in range(1, 10):
                for e in _events(_melody(self.PROG, "Am", level=level, seed=seed)):
                    if not e.is_rest:
                        self.assertTrue(lows[level] <= e.midi <= highs[level], (level, e.midi))


if __name__ == "__main__":
    unittest.main()
