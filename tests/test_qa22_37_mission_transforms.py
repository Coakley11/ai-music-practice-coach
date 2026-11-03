"""Issues 35/36: Reverse Order is an exact retrograde (pitches AND durations); Sequence Up/Down follow the active scale."""
import unittest
from fractions import Fraction as F

from improvisation_motif import sync_motif_midi, transform_motif
from melodic_rhythm_engine import events_from_json
from mission_degree_shift import shift_midis_by_degree

E_MAJOR = {4, 6, 8, 9, 11, 1, 3}


def _engine_motif(notes, durs, rests_after=None):
    """Build a motif with engine rhythm events: ``durs`` per note (beats); ``rests_after`` {note_index: beats}."""
    events, t, n = [], F(0), 0
    for i, d in enumerate(durs):
        events.append({"on": str(t), "dur": str(F(d)), "w": str(F(d)), "rest": False, "tup": None, "ts": False, "n": n})
        t += F(d); n += 1
        if rests_after and i in rests_after:
            r = F(rests_after[i])
            events.append({"on": str(t), "dur": str(r), "w": str(r), "rest": True, "tup": None, "ts": False, "n": None})
            t += r
    return sync_motif_midi({
        "chord": "E", "notes": list(notes), "rhythm": "x", "rhythm_key": "engine", "pattern_type": "auto",
        "rhythm_events": events, "rhythm_symbols": ["♩"] * len(notes), "cell_rhythm_symbols": [],
        "rhythm_meta": {"engine": "melodic_rhythm_engine", "id": "t", "meter": "4/4", "level": "Beginner", "group": 0,
                        "bars": 2, "unit_bars": 2, "roles": None},
        "meter": "4/4",
    })


def _pairs(m):
    ev = [e for e in events_from_json(m["rhythm_events"]) if not e.rest]
    return [(n, e.duration) for n, e in zip(m["notes"], ev)]


class TestReverseOrder(unittest.TestCase):
    def test_issue_example_exact_reversal(self):
        m = _engine_motif(["E", "G#", "E", "G#", "G#", "G#"], [1] * 6)
        r = transform_motif(m, "invert", key_center="E")
        self.assertEqual(r["notes"], ["G#", "G#", "G#", "E", "G#", "E"])
        self.assertEqual(r["midi"], list(reversed(m["midi"])))

    def test_twice_restores_everything(self):
        m = _engine_motif(["E", "G#", "B", "G#", "E"], [2, 1, 1, F(1, 2), F(1, 2)], rests_after={1: 1})
        once = transform_motif(m, "invert", key_center="E")
        twice = transform_motif(once, "invert", key_center="E")
        self.assertEqual(twice["notes"], m["notes"])
        self.assertEqual(twice["midi"], m["midi"])
        self.assertEqual(twice["rhythm_events"], m["rhythm_events"])

    def test_each_pitch_keeps_its_own_duration(self):
        m = _engine_motif(["E", "G#", "B", "G#"], [2, 1, F(1, 2), F(1, 2)])
        r = transform_motif(m, "invert", key_center="E")
        self.assertEqual(list(reversed(_pairs(m))), _pairs(r))

    def test_total_duration_and_rests_preserved(self):
        m = _engine_motif(["E", "G#", "B"], [1, 1, 1], rests_after={0: 1})
        r = transform_motif(m, "invert", key_center="E")
        ev_m, ev_r = events_from_json(m["rhythm_events"]), events_from_json(r["rhythm_events"])
        self.assertEqual(sum(e.duration for e in ev_m), sum(e.duration for e in ev_r))
        self.assertEqual([e.rest for e in ev_r], list(reversed([e.rest for e in ev_m])))
        # onsets are contiguous with no gaps/overlaps
        t = F(0)
        for e in ev_r:
            self.assertEqual(e.onset, t)
            t += e.duration
        self.assertEqual([e.note for e in ev_r if not e.rest], [0, 1, 2])

    def test_accidentals_not_respelled_into_other_notes(self):
        m = _engine_motif(["E", "F#", "G#", "A", "B"], [1] * 5)
        r = transform_motif(m, "invert", key_center="E")
        self.assertEqual(r["notes"], ["B", "A", "G#", "F#", "E"])


class TestSequenceFollowsScale(unittest.TestCase):
    def test_e_major_steps_not_semitones(self):
        # E G# E G# G# G#  ->  F# A F# A A A (scale degrees, not +1 semitone)
        up = shift_midis_by_degree([64, 68, 64, 68, 68, 68], E_MAJOR, +1)
        self.assertEqual(up, [66, 69, 66, 69, 69, 69])
        self.assertEqual(shift_midis_by_degree(up, E_MAJOR, -1), [64, 68, 64, 68, 68, 68])

    def test_motif_level_sequence_up_down_keep_rhythm(self):
        m = _engine_motif(["E", "G#", "E", "G#"], [1, 1, 2, 0 + F(1, 1)])
        up = transform_motif(m, "sequence_up", key_center="E", level="Beginner")
        self.assertEqual(up["notes"], ["F#", "A", "F#", "A"])
        self.assertEqual(up["rhythm_events"], m["rhythm_events"])
        dn = transform_motif(m, "sequence_down", key_center="E", level="Beginner")
        self.assertEqual(dn["notes"], ["D#", "F#", "D#", "F#"])

    def test_octave_wrap_in_scale(self):
        self.assertEqual(shift_midis_by_degree([71], {0, 2, 4, 5, 7, 9, 11}, +1), [72])
        self.assertEqual(shift_midis_by_degree([60], {0, 2, 4, 5, 7, 9, 11}, -1), [59])


if __name__ == "__main__":
    unittest.main()
