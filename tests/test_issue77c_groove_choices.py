"""Issue 77C: the Multitrack groove list must be the real vocabulary, and the styles must be real.

The page offered seven options from a list written into it while the engine plays eleven. Blues
groove was missing even though ``infer_groove_style`` already resolves a blues song to it, so a
musician heard a real blues under Auto and could neither see that nor ask for it.

The point of this file is that it is **not** a test about labels. ``TheStylesAreMusicallyReal``
renders audio through the actual backing engine and compares it between styles: if a label were
added without the engine playing anything different, those tests fail.
"""

from __future__ import annotations

import hashlib
import unittest


def fingerprint(samples) -> str:
    """A cheap content hash of rendered audio, so two renders can be compared exactly."""
    import numpy as np

    arr = np.asarray(samples, dtype="float32")
    return hashlib.sha1(arr.tobytes()).hexdigest()[:16]


def render(style: str, *, bars: int = 4, bpm: float = 100.0, time_signature: str = "4/4"):
    from backing_audio import backing_bytes_to_float

    chords = ["C7", "F7", "C7", "G7"][:bars]
    events = [{"chord": c, "section": "Blues", "bar_in_section": i, "section_bars": len(chords)}
              for i, c in enumerate(chords)]
    return backing_bytes_to_float(events, bpm=bpm, style=style, level="Intermediate",
                                  time_signature=time_signature)


class TheListIsTheSharedVocabulary(unittest.TestCase):
    def test_every_supported_groove_is_offered(self) -> None:
        from multitrack_groove_choices import groove_options

        options = groove_options()
        for wanted in ("Auto", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova",
                       "Funk groove", "Blues groove", "Ballad", "Jewish groove", "Jewish hora",
                       "Klezmer groove", "Jewish ballad"):
            self.assertIn(wanted, options)

    def test_it_is_the_shared_definition_not_a_copy(self) -> None:
        from multitrack_groove_choices import groove_options
        from songs.playback_defaults import GROOVE_STYLE_CHOICES

        self.assertEqual(groove_options(), [str(c) for c in GROOVE_STYLE_CHOICES])

    def test_the_page_no_longer_carries_its_own_list(self) -> None:
        from pathlib import Path

        app = (Path(__file__).resolve().parents[1]
               / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("from multitrack_groove_choices import", app)
        self.assertIn("_mt_groove_options = groove_options()", app)

    def test_previously_saved_selections_still_work(self) -> None:
        from multitrack_groove_choices import normalize_selection

        for old in ("Auto", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova",
                    "Funk groove", "Ballad"):
            self.assertEqual(normalize_selection(old), old)

    def test_an_unknown_saved_value_falls_back_to_auto_instead_of_breaking(self) -> None:
        from multitrack_groove_choices import normalize_selection

        self.assertEqual(normalize_selection("Reggae skank"), "Auto")
        self.assertEqual(normalize_selection(None), "Auto")
        self.assertEqual(normalize_selection(""), "Auto")

    def test_case_drift_in_an_older_value_is_tolerated(self) -> None:
        from multitrack_groove_choices import normalize_selection

        self.assertEqual(normalize_selection("jazz swing"), "Jazz swing")
        self.assertEqual(normalize_selection("BLUES GROOVE"), "Blues groove")


class AutoSaysWhatItChose(unittest.TestCase):
    def test_a_blues_song_shows_auto_blues_groove(self) -> None:
        from multitrack_groove_choices import auto_label, resolved_auto_style

        song = {"title": "Blues in F minor", "genre": "Blues"}
        style, evidence = resolved_auto_style(song)
        self.assertEqual(style, "Blues groove")
        self.assertTrue(evidence)
        self.assertEqual(auto_label(song), "Auto — Blues groove")

    def test_the_stored_value_is_still_auto(self) -> None:
        """Showing the resolution must not quietly turn the choice into an explicit style."""
        from multitrack_groove_choices import AUTO, groove_label, normalize_selection

        song = {"title": "Blues in F minor", "genre": "Blues"}
        self.assertEqual(normalize_selection(AUTO), AUTO)
        self.assertIn("Blues groove", groove_label(AUTO, song))
        self.assertEqual(groove_label("Blues groove", song), "Blues groove")

    def test_a_song_with_no_style_evidence_is_not_given_a_genre(self) -> None:
        from multitrack_groove_choices import auto_label, resolved_auto_style

        song = {"title": "Untitled sketch"}
        style, evidence = resolved_auto_style(song)
        self.assertEqual(style, "Pop groove", "the engine's documented last resort")
        self.assertEqual(evidence, "", "nothing about this song implies a style")
        label = auto_label(song)
        self.assertNotIn("Pop groove", label, "a default was announced as if it were a genre")
        self.assertIn("standard groove", label)

    def test_a_jewish_traditional_song_resolves_to_a_jewish_style(self) -> None:
        from multitrack_groove_choices import resolved_auto_style

        style, evidence = resolved_auto_style(
            {"title": "Hava Nagila", "genre": "Jewish Traditional"})
        self.assertIn("Jewish", style)
        self.assertTrue(evidence)


class TheStylesAreMusicallyReal(unittest.TestCase):
    """Rendered audio, not labels: each style must make the engine play something different."""

    def test_each_offered_style_has_its_own_rhythm_in_common_time(self) -> None:
        from multitrack_groove_choices import groove_options, style_has_own_pattern

        for style in groove_options():
            if style == "Auto":
                continue
            self.assertIs(
                style_has_own_pattern(style, "4/4"), True,
                f"{style} is offered but plays the standard pattern in 4/4",
            )

    def test_the_four_styles_the_user_named_render_different_audio(self) -> None:
        """Blues, Jewish hora, Klezmer and Jewish ballad against Pop, through the real engine."""
        reference = fingerprint(render("Pop groove"))
        seen = {"Pop groove": reference}
        for style in ("Blues groove", "Jewish hora", "Klezmer groove", "Jewish ballad"):
            fp = fingerprint(render(style))
            self.assertNotEqual(
                fp, reference,
                f"{style} rendered audio identical to Pop groove - the label would be a lie",
            )
            for other, other_fp in seen.items():
                self.assertNotEqual(
                    fp, other_fp, f"{style} rendered the same audio as {other}")
            seen[style] = fp

    def test_blues_and_jewish_groove_differ_from_each_other(self) -> None:
        self.assertNotEqual(fingerprint(render("Blues groove")),
                            fingerprint(render("Jewish groove")))

    def test_rendering_a_style_does_not_change_its_length(self) -> None:
        """Tempo, meter and chord duration must be untouched by the choice of groove."""
        lengths = {style: len(render(style, bars=4, bpm=100.0, time_signature="4/4"))
                   for style in ("Pop groove", "Blues groove", "Jewish hora", "Klezmer groove")}
        self.assertEqual(len(set(lengths.values())), 1, f"groove changed the duration: {lengths}")


class SixEightIsDescribedHonestly(unittest.TestCase):
    def test_a_style_with_no_distinct_six_eight_pattern_says_so(self) -> None:
        from multitrack_groove_choices import meter_fallback_note, style_has_own_pattern

        # Measured: Blues groove has its own 4/4 pattern and falls back in 6/8.
        self.assertIs(style_has_own_pattern("Blues groove", "4/4"), True)
        if style_has_own_pattern("Blues groove", "6/8") is False:
            note = meter_fallback_note("Blues groove", "6/8")
            self.assertIn("6/8", note)
            self.assertIn("Blues groove", note)
            self.assertIn("standard pattern", note)
        else:  # pragma: no cover - only if 6/8 support is added later
            self.assertEqual(meter_fallback_note("Blues groove", "6/8"), "")

    def test_nothing_is_claimed_where_the_engine_does_deliver(self) -> None:
        from multitrack_groove_choices import meter_fallback_note

        self.assertEqual(meter_fallback_note("Blues groove", "4/4"), "")
        self.assertEqual(meter_fallback_note("Jewish hora", "6/8"), "")
        self.assertEqual(meter_fallback_note("Auto", "6/8"), "")

    def test_the_note_is_silent_when_it_cannot_be_checked(self) -> None:
        import multitrack_groove_choices as mgc

        original = mgc.style_has_own_pattern
        try:
            mgc.style_has_own_pattern = lambda *_a, **_k: None  # type: ignore[assignment]
            self.assertEqual(mgc.meter_fallback_note("Blues groove", "6/8"), "")
        finally:
            mgc.style_has_own_pattern = original


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
