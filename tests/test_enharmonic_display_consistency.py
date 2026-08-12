"""Enharmonic spelling consistency for Original / Practice / Concert key displays."""

from __future__ import annotations

import unittest


class FormatKeyLabelPreservesSpellingTests(unittest.TestCase):
    def test_flat_keys_stay_flat(self) -> None:
        from custom_progression_lab import format_key_label
        from music_theory import display_key_label

        cases = {
            "Ab": "Ab major",
            "Eb": "Eb major",
            "Bb": "Bb major",
            "Db": "Db major",
            "Gb": "Gb major",
            "Abm": "Ab minor",
            "Ebm": "Eb minor",
        }
        for raw, expected in cases.items():
            self.assertEqual(display_key_label(raw), expected, raw)
            self.assertEqual(format_key_label(raw), expected, raw)

    def test_sharp_keys_stay_sharp(self) -> None:
        from custom_progression_lab import format_key_label
        from music_theory import display_key_label

        cases = {
            "F#": "F# major",
            "C#": "C# major",
            "G#": "G# major",
            "F#m": "F# minor",
            "C#m": "C# minor",
        }
        for raw, expected in cases.items():
            self.assertEqual(display_key_label(raw), expected, raw)
            self.assertEqual(format_key_label(raw), expected, raw)

    def test_theory_pc_still_normalizes_but_labels_do_not(self) -> None:
        from music_theory import chord_root_for_theory, display_key_label, normalize_root

        self.assertEqual(normalize_root("Ab"), "G#")
        self.assertEqual(chord_root_for_theory("Ab"), "G#")
        self.assertEqual(display_key_label("Ab"), "Ab major")


class PracticeKeyPitchClassFallbackTests(unittest.TestCase):
    def test_coerce_preserves_ab_not_g_sharp(self) -> None:
        from music_theory import coerce_key_to_mode

        self.assertEqual(coerce_key_to_mode("Ab", "major"), "Ab")
        self.assertEqual(coerce_key_to_mode("G#", "major"), "G#")
        self.assertEqual(coerce_key_to_mode("F#", "major"), "F#")
        self.assertEqual(coerce_key_to_mode("Db", "major"), "Db")

    def test_display_key_options_prefer_authoritative_spelling(self) -> None:
        from music_theory import display_key_options

        opts = display_key_options("Ab")
        self.assertEqual(opts[0], "Ab")
        self.assertIn("G#", opts)
        opts_fs = display_key_options("F#")
        self.assertEqual(opts_fs[0], "F#")


class AuthoritativePracticeKeyLabelTests(unittest.TestCase):
    def test_original_and_practice_labels_preserve_ab(self) -> None:
        from musical_context_authority import AuthoritativePracticeKey

        auth = AuthoritativePracticeKey(
            practice_tonic="Ab",
            practice_mode="major",
            original_tonic="Ab",
            original_mode="major",
            source="test",
        )
        self.assertEqual(auth.practice_label(), "Ab major")
        self.assertEqual(auth.original_label(), "Ab major")
        self.assertNotIn("G#", auth.practice_label())
        self.assertNotIn("G#", auth.original_label())


class ActiveSongBadgePathTests(unittest.TestCase):
    def test_format_key_label_path_matches_sidebar_ab(self) -> None:
        """Regression for Ab card badges flipping to G# while sidebar stayed Ab."""
        from custom_progression_lab import format_key_label

        original_key = "Ab"
        practice_key = "Ab"
        self.assertEqual(format_key_label(original_key), "Ab major")
        self.assertEqual(format_key_label(practice_key), "Ab major")

    def test_practice_key_round_trip_ab_c_ab(self) -> None:
        from custom_progression_lab import format_key_label
        from music_theory import display_key_options

        original = "Ab"
        opts = display_key_options(original)
        self.assertIn("Ab", opts)
        self.assertIn("C", opts)
        self.assertEqual(format_key_label("C"), "C major")
        self.assertEqual(format_key_label("Ab"), "Ab major")


class KeyDisplayDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_flag_pitch_class_respell_risk(self) -> None:
        from key_display_diagnostics import build_key_display_diagnostics

        session = {
            "instrument": "Piano",
            "display_key": "Ab",
            "concert_key": "Ab",
            "selected_song": {"title": "Test", "key": "Ab", "pick_key": "test_ab"},
            "active_catalog_pick_key": "test_ab",
            "active_song_state": {
                "pick_key": "test_ab",
                "display_key": "Ab",
                "instrument": "Piano",
            },
        }
        diag = build_key_display_diagnostics(session)
        self.assertEqual(diag["practice_concert"]["raw"], "Ab")
        self.assertEqual(diag["practice_concert"]["display_label"], "Ab major")
        self.assertEqual(diag["practice_concert"]["pitch_class_normalized"], "G#")
        self.assertTrue(diag["practice_concert"]["pitch_class_respelling_would_occur"])


class TransposingDomainSeparationTests(unittest.TestCase):
    def test_concert_ab_written_bb_for_clarinet(self) -> None:
        from instrument_transposition import written_key_for_instrument
        from music_theory import display_key_label

        session = {
            "instrument": "Clarinet",
            "selected_transposing_instrument": "Bb Clarinet",
            "display_key": "Ab",
        }
        written = written_key_for_instrument("Ab", "Clarinet", session)
        self.assertEqual(display_key_label("Ab"), "Ab major")
        self.assertEqual(written, "Bb")
        self.assertEqual(display_key_label(written), "Bb major")


if __name__ == "__main__":
    unittest.main()
