"""Reverse Order is an exact retrograde at EVENT level (notes, MIDI, durations, rests, ABC, Notes to Play), in concert and
Alto written pitch, and written chords keep chord-tone spelling (G#7 -> B#, not C)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from abc_pitch_decoder import decode_abc_events  # noqa: E402
from improvisation_missions import (  # noqa: E402
    apply_mission_motif_transform,
    ensure_mission_sheet_music_authority,
    load_mission_example,
)
from melodic_rhythm_engine import events_from_json  # noqa: E402
from test_move_mission_by_degree import CHORD_TONES, _setup  # noqa: E402


def _snapshot(s, ctx, inst):
    ex = ensure_mission_sheet_music_authority(s, load_mission_example(s, ctx), improv_ctx=ctx, instrument=inst, bpm=100)
    m = ex.motif
    ev = [(e.onset, e.duration, e.rest) for e in events_from_json(m["rhythm_events"])] if m.get("rhythm_events") else []
    return {"notes": list(m["notes"]), "midi": list(m["midi"]), "events": ev, "abc": decode_abc_events(ex.abc), "ex": ex}


def _mirror(events):
    total = max((o + d for o, d, _r in events), default=0)
    return sorted(((total - o - d, d, r) for o, d, r in events), key=lambda x: x[0])


class TestReverseIsExactRetrograde(unittest.TestCase):
    CASES = (
        ("concert", "Piano", None),
        ("alto written", "Saxophone", "Alto saxophone (Eb)"),
    )

    def test_every_layer_reversed_and_twice_restores(self):
        for label, inst, ttype in self.CASES:
            for level in ("Beginner", "Advanced"):
                with self.subTest(case=label, level=level):
                    s, ctx = _setup(CHORD_TONES, "B7", "Em", level=level, instrument=inst, transposing=ttype)
                    a = _snapshot(s, ctx, inst)
                    apply_mission_motif_transform(s, ctx, "invert", bpm=100)
                    b = _snapshot(s, ctx, inst)
                    self.assertEqual(b["notes"], a["notes"][::-1])                         # note names: whole sequence reversed
                    self.assertEqual(b["midi"], a["midi"][::-1])                           # sounding/stored MIDI
                    self.assertEqual([m for m, _d in b["abc"] if m is not None], a["midi"][::-1])   # the drawn score
                    self.assertEqual([m for m, _d in b["abc"] if m is not None], b["midi"])
                    self.assertEqual(b["events"], _mirror(a["events"]))                    # durations/rests mirrored
                    self.assertEqual(sum(d for _m, d in b["abc"]), sum(d for _m, d in a["abc"]))
                    self.assertEqual([d for m, d in b["abc"] if m is None], [d for m, d in a["abc"] if m is None][::-1])
                    apply_mission_motif_transform(s, ctx, "invert", bpm=100)
                    c = _snapshot(s, ctx, inst)
                    for k in ("notes", "midi", "events", "abc"):
                        self.assertEqual(c[k], a[k], k)

    def test_the_reported_phrase_shape(self):
        # D# D# B A D# D# reversed is D# D# A B D# D# (a palindromic frame around the swapped middle), not A B D# D#...
        seq = ["D#", "D#", "B", "A", "D#", "D#"]
        self.assertEqual(seq[::-1], ["D#", "D#", "A", "B", "D#", "D#"])


class TestWrittenChordToneSpelling(unittest.TestCase):
    def test_g_sharp_7_uses_b_sharp_not_c(self):
        from harmonic_spelling import spell_pitch_classes_for_chord

        self.assertEqual(spell_pitch_classes_for_chord([8, 0, 3, 6], "G#7"), ["G#", "B#", "D#", "F#"])
        self.assertEqual(spell_pitch_classes_for_chord([11, 3, 6, 9], "B7"), ["B", "D#", "F#", "A"])
        self.assertEqual(spell_pitch_classes_for_chord([2, 6, 9, 0], "D7"), ["D", "F#", "A", "C"])

    def test_alto_written_example_spells_b_sharp_and_stays_exact(self):
        for seed_level in ("Beginner", "Intermediate", "Advanced"):
            s, ctx = _setup(CHORD_TONES, "B7", "Em", level=seed_level, instrument="Saxophone", transposing="Alto saxophone (Eb)")
            snap = _snapshot(s, ctx, "Saxophone")
            self.assertNotIn("C", snap["notes"], snap["notes"])                              # B# written as B#
            self.assertTrue(set(snap["notes"]) <= {"G#", "B#", "D#", "F#"}, snap["notes"])
            self.assertEqual([m for m, _d in snap["abc"] if m is not None], snap["midi"])    # B# still decodes to the right pitch


if __name__ == "__main__":
    unittest.main()
