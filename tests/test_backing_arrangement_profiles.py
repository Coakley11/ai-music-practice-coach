"""Song arrangement profiles (A3): data table, never musical-session facts."""

from __future__ import annotations

import unittest

import numpy as np

import backing_arrangement_profiles as ap
import backing_audio as ba


def _events(sections_and_chords):
    return [{"chord": c, "section": s, "bar_in_section": 0, "section_bars": 1} for s, c in sections_and_chords]


class TableTests(unittest.TestCase):
    def test_table_is_sound(self) -> None:
        self.assertEqual(ap.validate_arrangements(), [])

    def test_validation_rejects_session_owned_and_unknown_fields(self) -> None:
        bad = (
            ap.SongArrangement("bad key", ap._any("x"), ap.Tweak(set={"key": "D"})),
            ap.SongArrangement("bad bpm", ap._any("x"), ap.Tweak(at_least={"bpm": 120})),
            ap.SongArrangement("typo", ap._any("x"), ap.Tweak(flags=("vocal_balad",))),
        )
        problems = ap.validate_arrangements(bad)
        self.assertEqual(len(problems), 3)
        self.assertIn("musical session", problems[0])
        self.assertIn("musical session", problems[1])
        self.assertIn("unknown field", problems[2])

    def test_no_profile_field_is_session_owned(self) -> None:
        self.assertFalse(ap.PROFILE_FIELDS & ap.SESSION_OWNED_FIELDS)


class ResolutionTests(unittest.TestCase):
    def test_unknown_song_gets_the_style_defaults(self) -> None:
        p = ba._song_backing_profile("Untitled", "Nobody", "Pop groove")
        for k, v in ap.DEFAULT_PROFILE.items():
            self.assertEqual(p[k], v, k)

    def test_groove_song_and_ballad_song_differ(self) -> None:
        groove = ba._song_backing_profile("Shape of You", "Ed Sheeran", "Pop groove")
        ballad = ba._song_backing_profile("The Scientist", "Coldplay", "Ballad")
        self.assertTrue(groove["groove_based"] and groove["ghost_snare"])
        self.assertLess(groove["pocket_offset"], 0)  # pushed
        self.assertTrue(ballad["piano_centric"] and ballad["vocal_ballad"])
        self.assertGreater(ballad["pocket_offset"], 0)  # laid back
        self.assertEqual(ballad["keys_level"], 1.25)
        self.assertLess(groove["strings_level"], ballad["strings_level"])

    def test_style_tweaks_refine_only_the_chosen_style(self) -> None:
        jazz = ba._song_backing_profile("Autumn Leaves", "", "Jazz swing")
        bossa = ba._song_backing_profile("Autumn Leaves", "", "Bossa nova")
        self.assertTrue(jazz["ride_jazz"])
        self.assertGreaterEqual(jazz["swing"], 0.07)
        self.assertFalse(bossa["ride_jazz"])
        self.assertEqual(bossa["swing"], 0.0)

    def test_match_alternatives_and_excludes(self) -> None:
        self.assertTrue(ba._song_backing_profile("Story", "Taylor Swift", "Ballad")["acoustic_unplugged"])
        self.assertFalse(ba._song_backing_profile("Wave", "", "Ballad")["latin_relaxed"])
        self.assertTrue(ba._song_backing_profile("Wave", "Jobim", "Ballad")["latin_relaxed"])
        self.assertFalse(ba._song_backing_profile("Hevenu Shalom Aleichem", "", "Ballad")["jewish_traditional"])
        self.assertTrue(ba._song_backing_profile("Shalom Aleichem", "", "Ballad")["jewish_traditional"])

    def test_section_lifts(self) -> None:
        p = ba._song_backing_profile("Heal the World", "Michael Jackson", "Ballad")
        self.assertAlmostEqual(ap.apply_section_lifts(p, "verse", "Verse 1", 1.0), 0.90)
        self.assertAlmostEqual(ap.apply_section_lifts(p, "outro", "Final Chorus", 1.0), 1.10)
        self.assertAlmostEqual(ap.apply_section_lifts(p, "outro", "Ending", 1.0), 0.88)
        plain = ba._song_backing_profile("Untitled", "", "Ballad")
        self.assertEqual(ap.apply_section_lifts(plain, "chorus", "Final Chorus", 0.7), 0.7)

    def test_profile_resolution_does_not_mutate_defaults(self) -> None:
        p = ba._song_backing_profile("Shape of You", "Ed Sheeran", "Pop groove")
        p["hat_open_ands"].append(3.5)
        self.assertEqual(ap.DEFAULT_PROFILE["hat_open_ands"], [])
        self.assertEqual(ba._song_backing_profile("Untitled", "", "Pop groove")["hat_open_ands"], [])


class OwnershipTests(unittest.TestCase):
    """The arrangement changes how the chart is played, never the chart, key or tempo."""

    def test_song_arrangement_keeps_length_and_harmony_timeline(self) -> None:
        ev = _events([("Verse 1", "C"), ("Pre-Chorus", "Am"), ("Chorus 1", "F"), ("Final Chorus", "G")])
        plain, sr = ba.synthesize_chords_to_numpy(ev, bpm=96, loops=1, style="Ballad", song_title="Untitled")
        song, sr2 = ba.synthesize_chords_to_numpy(
            ev, bpm=96, loops=1, style="Ballad", song_title="Heal the World", song_artist="Michael Jackson"
        )
        self.assertEqual((len(plain), sr), (len(song), sr2))
        self.assertFalse(np.array_equal(plain, song))
        # Same bar grid the chord timeline uses: 4 bars at 96 BPM (+1 s tail).
        bar = ba.meter_timing(96, "4/4").bar_sec
        self.assertEqual(len(song), int(sr * bar * 4) + sr)


if __name__ == "__main__":
    unittest.main()
