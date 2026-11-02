"""Issue 24: generated Mission exercises stay in each melodic instrument's comfortable written register."""
import os
import sys
import unittest

from improvisation_missions import load_mission_example
from instrument_register_fit import comfortable_written_range, fit_midis_to_register, fit_motif_to_instrument

sys.path.insert(0, os.path.dirname(__file__))
from test_move_mission_by_degree import CHORD_TONES, MOTIF, PENT, _setup  # noqa: E402

WINDS = ["Flute", "Clarinet", "Trumpet", "Saxophone", "Alto Saxophone", "Tenor Saxophone", "Baritone Saxophone"]


class TestFit(unittest.TestCase):
    def test_whole_phrase_octave_shift_preserves_pitch_class_and_intervals(self):
        src = [81, 84, 88, 91]
        out = fit_midis_to_register(src, 60, 81)
        self.assertEqual([m % 12 for m in out], [m % 12 for m in src])
        self.assertEqual([b - a for a, b in zip(out, out[1:])], [b - a for a, b in zip(src, src[1:])])
        self.assertTrue(60 <= min(out) and max(out) <= 81)
        self.assertEqual(len({a - b for a, b in zip(src, out)}), 1)          # one common shift

    def test_phrase_wider_than_register_never_goes_below_the_floor(self):
        src = [50, 90]
        out = fit_midis_to_register(src, 60, 81)
        self.assertEqual([b - a for a, b in zip(out, out[1:])], [40])
        self.assertEqual(len({o - s for o, s in zip(out, src)}), 1)
        self.assertEqual(out, [62, 102])         # raised an octave+: floor protected over ceiling

    def test_already_comfortable_is_untouched(self):
        self.assertEqual(fit_midis_to_register([65, 69, 72], 60, 81), [65, 69, 72])

    def test_chordal_instruments_are_not_fitted(self):
        for inst in ("Guitar", "Piano", "Bass", "Voice"):
            self.assertIsNone(comfortable_written_range(inst, "Beginner"))
        motif = {"notes": ["A"], "midi": [90]}
        self.assertEqual(fit_motif_to_instrument(motif, "Guitar")["midi"], [90])

    def test_flute_floor_is_c4_and_ordinary_ceiling_is_below_the_extreme(self):
        lo, hi = comfortable_written_range("Flute", "Beginner")
        self.assertEqual(lo, 60)
        self.assertLessEqual(hi, 84)
        self.assertGreater(comfortable_written_range("Flute", "Advanced")[1], hi)


class TestMissionExamplesStayInRange(unittest.TestCase):
    def test_every_wind_level_and_mission(self):
        for inst in WINDS:
            for lvl in ("Beginner", "Intermediate"):
                lo, hi = comfortable_written_range(inst, lvl)
                for mission in (CHORD_TONES, PENT, MOTIF):
                    with self.subTest(inst=inst, level=lvl, mission=mission[:24]):
                        s, ctx = _setup(mission, "Am7", "A", instrument=inst, level=lvl)
                        from practice_melody_session import instrument_register_args

                        args = instrument_register_args(s, inst)
                        offset = int(args.get("written_offset") or 0)                # concert chart: compare in written pitch
                        lo, hi = comfortable_written_range(str(args.get("instrument") or inst), lvl)
                        midis = [m + offset for m in load_mission_example(s, ctx).motif["midi"]]
                        self.assertGreaterEqual(min(midis), lo)      # never below the instrument's floor
                        span = max(midis) - min(midis)
                        if span <= (hi - lo) - 11:                    # an octave placement exists
                            self.assertLessEqual(max(midis), hi)
                        else:                                          # too wide for the comfortable window
                            self.assertLessEqual(max(midis), comfortable_written_range(inst, "Advanced")[1])

    def test_pitch_classes_match_the_note_names(self):
        from improvisation_motif import _midi_from_note

        s, ctx = _setup(MOTIF, "Am7", "A", instrument="Flute", level="Beginner")
        m = load_mission_example(s, ctx).motif
        self.assertEqual([x % 12 for x in m["midi"]], [_midi_from_note(n, 4) % 12 for n in m["notes"]])


if __name__ == "__main__":
    unittest.main()


class TestConcertChartUsesSoundingRange(unittest.TestCase):
    """A concert-pitch chart must not be fitted against the written-pitch range."""

    def test_hint_shifts_the_window_down_by_the_transposition(self):
        motif = {"notes": ["A"] * 3, "midi": [60, 64, 67]}
        written = fit_motif_to_instrument(dict(motif, _register_hint={"instrument": "Alto saxophone (Eb)", "written_offset": 0}), "Saxophone", "Beginner")
        concert = fit_motif_to_instrument(dict(motif, _register_hint={"instrument": "Alto saxophone (Eb)", "written_offset": 9}), "Saxophone", "Beginner")
        lo_w, hi_w = comfortable_written_range("Alto saxophone (Eb)", "Beginner")
        self.assertGreaterEqual(min(written["midi"]), lo_w)
        self.assertGreaterEqual(min(concert["midi"]) + 9, lo_w)       # written pitch of the concert phrase is inside the written range
        self.assertLessEqual(max(concert["midi"]) + 9, hi_w)

    def test_end_to_end_concert_chart_alto(self):
        s, ctx = _setup(CHORD_TONES, "Am7", "A", instrument="Saxophone", level="Beginner")
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        s[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Alto saxophone (Eb)"      # chart left in concert pitch
        from improvisation_intelligence_ui import _run_mission_example_generate

        _run_mission_example_generate(s, "normal")
        midis = load_mission_example(s, ctx).motif["midi"]
        lo, hi = comfortable_written_range("Alto saxophone (Eb)", "Beginner")
        self.assertGreaterEqual(min(midis) + 9, lo)
        self.assertLessEqual(max(midis) + 9, hi)
