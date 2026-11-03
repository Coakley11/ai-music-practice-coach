"""Issues 37-39: context-aware Mission chord-scale choice, exact one-degree Sequence through the Mission's own
collection, stable key signature, and pitch agreement between score / Notes / MIDI."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from abc_pitch_decoder import decode_abc_midis  # noqa: E402
from chord_scale_selection import SCALES, scale_label_for, scale_pcs_for, select_mission_scale  # noqa: E402
from improvisation_missions import (  # noqa: E402
    apply_mission_motif_transform,
    ensure_mission_sheet_music_authority,
    load_mission_example,
    mission_scale_label,
)
from mission_degree_shift import shift_midis_by_degree  # noqa: E402
from test_move_mission_by_degree import CHORD_TONES, _setup  # noqa: E402

SCALAR = "Only scalar runs"
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _midi(name, octave=4):
    n = name.replace("♯", "#").replace("♭", "b")
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[n[0]]
    return 12 * (octave + 1) + base + n.count("#") - n.count("b")


def _names(midis):
    return [NAMES[m % 12] for m in midis]


class TestScaleChoiceIsContextual(unittest.TestCase):
    def test_plain_dominant_resolving_to_minor_by_level_and_feel(self):
        def pick(**kw):
            return select_mission_scale("B7", key_center="Em", next_chord="Em7", **kw)["label"]

        self.assertEqual(pick(level="Beginner", style=""), "B Mixolydian")                  # level alone never adds colour
        self.assertEqual(pick(level="Intermediate", style=""), "B Phrygian dominant")       # resolving to minor
        self.assertEqual(pick(level="Advanced", style="Jazz"), "B altered")                 # deliberate: jazz + minor target
        self.assertEqual(pick(level="Advanced", style="Blues"), "B Mixolydian")             # a Blues Mission never turns altered
        self.assertEqual(pick(level="Advanced", style="Rock"), "B Mixolydian")

    def test_dominant_resolving_to_major_stays_conventional(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            r = select_mission_scale("B7", key_center="E", next_chord="Emaj7", level=level, style="Jazz")
            self.assertEqual(r["label"], "B Mixolydian")

    def test_chord_symbol_alterations_always_win(self):
        self.assertEqual(select_mission_scale("B7#5", key_center="E")["label"], "B whole-tone")
        self.assertEqual(select_mission_scale("B7alt", key_center="Em")["label"], "B altered")
        self.assertEqual(select_mission_scale("B7#11", key_center="E")["label"], "B Lydian dominant")

    def test_chord_tone_missions_get_no_scale(self):
        for m in ("Improvise using only chord tones", "Target only guide tones (3rds & 7ths)", "Play one chorus without scalar runs"):
            self.assertIsNone(select_mission_scale("B7", key_center="Em", next_chord="Em", level="Advanced", style="Jazz", mission=m))

    def test_spelling_matches_the_spec(self):
        self.assertEqual(select_mission_scale("B7alt", key_center="Em")["notes"], ["B", "C", "D", "Eb", "F", "G", "A"])
        self.assertEqual(select_mission_scale("B7", key_center="E", level="Beginner")["notes"], ["B", "C#", "D#", "E", "F#", "G#", "A"])
        self.assertEqual(select_mission_scale("B7", key_center="Em", next_chord="Em", level="Intermediate")["notes"],
                         ["B", "C", "D#", "E", "F#", "G", "A"])
        self.assertEqual(sorted(scale_pcs_for("whole_tone", "B7")), sorted((11 + s) % 12 for s in SCALES["whole_tone"]))
        self.assertEqual(scale_label_for("diminished_half_whole", "B7"), "B half-whole diminished")


class TestSequenceThroughOwnCollection(unittest.TestCase):
    def _shift(self, notes, pcs, d):
        return _names(shift_midis_by_degree([_midi(n, 4) for n in notes], pcs, d))

    def test_b_mixolydian(self):
        pcs = scale_pcs_for("mixolydian", "B7")
        self.assertEqual(self._shift(["B", "D#", "F#"], pcs, +1), ["C#", "E", "G#"])
        self.assertEqual(self._shift(["B", "D#", "F#"], pcs, -1), ["A", "C#", "E"])

    def test_b_altered(self):
        pcs = scale_pcs_for("altered", "B7")
        self.assertEqual(self._shift(["B", "Eb", "F"], pcs, +1), ["C", "F", "G"])
        self.assertEqual(self._shift(["B", "Eb", "F"], pcs, -1), ["A", "D", "D#"])

    def test_b7_chord_tones(self):
        pcs = {11, 3, 6, 9}
        self.assertEqual(self._shift(["B", "D#", "F#"], pcs, +1), ["D#", "F#", "A"])
        self.assertEqual(self._shift(["B", "D#", "F#"], pcs, -1), ["A", "B", "D#"])

    def test_up_then_down_restores(self):
        for key in ("mixolydian", "altered", "phrygian_dominant", "whole_tone", "diminished_half_whole"):
            pcs = scale_pcs_for(key, "B7")
            phrase = [m for m in (_midi("B", 4), _midi("F#", 5), _midi("A", 4)) if m % 12 in pcs]
            self.assertTrue(phrase)
            self.assertEqual(shift_midis_by_degree(shift_midis_by_degree(phrase, pcs, +1), pcs, -1), phrase)


class TestScalarMissionEndToEnd(unittest.TestCase):
    def _run(self, level, style, key="Em", chord="B7"):
        s, ctx = _setup(SCALAR, chord, key, level=level)
        ctx.style_label = style
        s["genre"] = style
        ctx.sections = {"A": [chord, "Em7"]}
        s["home_sections"] = ctx.sections
        from improvisation_intelligence_ui import _run_mission_example_generate

        _run_mission_example_generate(s, "normal")
        return s, ctx

    def test_scale_is_stored_labelled_and_all_notes_belong_to_it(self):
        for level, style, want in (("Beginner", "", "mixolydian"), ("Advanced", "Jazz", "altered"), ("Advanced", "Blues", "mixolydian")):
            with self.subTest(level=level, style=style):
                s, ctx = self._run(level, style)
                ex = load_mission_example(s, ctx)
                self.assertEqual(ex.motif.get("mission_scale_key"), want)
                label, reason = mission_scale_label(ex)
                self.assertTrue(label.startswith("B "), label)
                self.assertTrue(reason)
                self.assertTrue({m % 12 for m in ex.motif["midi"]} <= scale_pcs_for(want, "B7"))

    def test_sequence_and_reverse_keep_scale_and_key_signature(self):
        s, ctx = self._run("Advanced", "Jazz")
        ex0 = load_mission_example(s, ctx)
        k0 = [ln for ln in ex0.abc.splitlines() if ln.startswith("K:")]
        pcs = scale_pcs_for("altered", "B7")
        for op in ("sequence_up", "sequence_down", "invert", "invert"):
            apply_mission_motif_transform(s, ctx, op, bpm=100)
            ex = load_mission_example(s, ctx)
            self.assertEqual(ex.motif.get("mission_scale_key"), "altered")
            self.assertTrue({m % 12 for m in ex.motif["midi"]} <= pcs, (op, ex.motif["notes"]))
            self.assertEqual([ln for ln in ex.abc.splitlines() if ln.startswith("K:")], k0)   # K never follows the chord/scale
            self.assertEqual(decode_abc_midis(ex.abc), list(ex.motif["midi"]))
        self.assertEqual(ex.motif["midi"], ex0.motif["midi"])                                 # up/down and reverse x2 restore


class TestKeySignatureAndPitchAgreement(unittest.TestCase):
    def test_b7_in_e_minor_chord_tones_exact(self):
        s, ctx = _setup(CHORD_TONES, "B7", "Em", level="Advanced")
        ex = load_mission_example(s, ctx)
        self.assertEqual([ln for ln in ex.abc.splitlines() if ln.startswith("K:")], ["K:Em"])
        self.assertTrue({m % 12 for m in ex.motif["midi"]} <= {11, 3, 6, 9})                 # B D# F# A
        self.assertEqual(decode_abc_midis(ex.abc), list(ex.motif["midi"]))
        if 3 in {m % 12 for m in ex.motif["midi"]}:
            self.assertIn("^D", ex.abc)                                                       # D# is NOT in E minor: explicit sharp
        self.assertNotIn("^F", ex.abc)                                                        # F# is in the signature

    def test_written_alto_key_signature_and_pitches(self):
        s, ctx = _setup(CHORD_TONES, "B7", "Em", level="Advanced", instrument="Saxophone", transposing="Alto saxophone (Eb)")
        ex = ensure_mission_sheet_music_authority(s, load_mission_example(s, ctx), improv_ctx=ctx, instrument="Saxophone", bpm=100)
        self.assertEqual([ln for ln in ex.abc.splitlines() if ln.startswith("K:")], ["K:C#m"])
        self.assertEqual(ex.motif["chord"], "G#7")                                            # written chord label
        self.assertEqual(decode_abc_midis(ex.abc), list(ex.motif["midi"]))
        self.assertTrue({(m + 3) % 12 for m in ex.motif["midi"]} <= {11, 3, 6, 9})            # sounding pitches = B7 tones

    def test_reverse_order_on_written_chart_is_a_pure_reordering(self):
        s, ctx = _setup(CHORD_TONES, "C7", "Fm", level="Advanced", instrument="Saxophone", transposing="Tenor saxophone (Bb)")
        ex0 = ensure_mission_sheet_music_authority(s, load_mission_example(s, ctx), improv_ctx=ctx, instrument="Saxophone", bpm=100)
        apply_mission_motif_transform(s, ctx, "invert", bpm=100)
        ex1 = ensure_mission_sheet_music_authority(s, load_mission_example(s, ctx), improv_ctx=ctx, instrument="Saxophone", bpm=100)
        self.assertEqual(ex1.motif["notes"], ex0.motif["notes"][::-1])
        self.assertEqual(ex1.motif["midi"], ex0.motif["midi"][::-1])
        apply_mission_motif_transform(s, ctx, "invert", bpm=100)
        ex2 = ensure_mission_sheet_music_authority(s, load_mission_example(s, ctx), improv_ctx=ctx, instrument="Saxophone", bpm=100)
        self.assertEqual((ex2.motif["notes"], ex2.motif["midi"]), (ex0.motif["notes"], ex0.motif["midi"]))


if __name__ == "__main__":
    unittest.main()
