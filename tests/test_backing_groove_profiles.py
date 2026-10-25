"""Catalog songs resolve to a groove profile for their style, not one generic loop.

Measured before: Shallow (Ballad) vs Shape of You (Pop groove) rhythm envelopes
correlated 0.48, and 0.98 once Shallow inherited a Pop Feel -- the recipe owned
the grid and song data could only tint it. Jobim bossas resolved to Jazz swing
and several ballads to Rock / Pop groove because the genre map ran first.
"""

from __future__ import annotations

import logging
import unittest

import numpy as np

import backing_audio as ba
from backing_arrangement_profiles import song_groove_profile_id, validate_arrangements
from backing_groove_profiles import (
    GROOVE_PROFILES,
    STYLE_DEFAULT_PROFILES,
    resolve_groove_profile,
    validate_groove_profiles,
)
from backing_musical_profile import resolve_backing_musical_profile
from songs.playback_defaults import default_groove_for_song

logging.disable(logging.CRITICAL)

_BARS = (
    [("G", "Intro", i) for i in range(2)]
    + [("G", "Verse 1", i) for i in range(4)]
    + [("C", "Chorus 1", i) for i in range(4)]
)
EVENTS = [
    {"chord": c, "section": s, "bar_in_section": i, "section_bars": 4 if s != "Intro" else 2}
    for c, s, i in _BARS
]
SHALLOW = ("Shallow", "Lady Gaga / Bradley Cooper")
SHAPE = ("Shape of You", "Ed Sheeran")


def _render(title, artist, style, *, bpm=96, events=EVENTS, strings=False, layers=("rhythm",)):
    prof = resolve_backing_musical_profile(style=style, tempo=bpm)
    audio, sr = ba.synthesize_chords_to_numpy(
        events, bpm=bpm, style=style, song_title=title, song_artist=artist,
        musical_profile=prof, strings=strings, layers=list(layers),
    )
    return audio, sr


def _envelope(audio, sr):
    hop = int(sr * 0.010)
    return np.sqrt(np.convolve(audio ** 2, np.ones(hop) / hop, mode="same"))[::hop]


def _corr(a, b):
    n = min(len(a), len(b))
    return float(np.corrcoef(a[:n], b[:n])[0, 1])


class RegistryTests(unittest.TestCase):
    def test_registry_and_song_table_are_sound(self) -> None:
        self.assertEqual(validate_groove_profiles(), [])
        self.assertEqual(validate_arrangements(), [])
        for style, pid in STYLE_DEFAULT_PROFILES.items():
            self.assertIn(pid, GROOVE_PROFILES, style)

    def test_songs_name_their_own_profile(self) -> None:
        self.assertEqual(song_groove_profile_id(*SHALLOW), "cinematic_ballad")
        self.assertEqual(song_groove_profile_id(*SHAPE), "dance_pop")
        self.assertEqual(song_groove_profile_id("Autumn Leaves", "Jazz Standard"), "")


class ResolutionTests(unittest.TestCase):
    def test_a_song_profile_only_refines_its_own_style(self) -> None:
        self.assertEqual(resolve_groove_profile("Ballad", song_profile_id="cinematic_ballad").id, "cinematic_ballad")
        # The user picked Pop groove for Shallow: the style's own profile, not the ballad.
        self.assertEqual(resolve_groove_profile("Pop groove", song_profile_id="cinematic_ballad").id, "pop_backbeat")

    def test_style_defaults_and_other_meters(self) -> None:
        self.assertEqual(resolve_groove_profile("Jazz swing").id, "jazz_ride")
        self.assertEqual(resolve_groove_profile("Bossa nova").id, "bossa_clave")
        self.assertEqual(resolve_groove_profile("Funk groove").id, "funk_rnb")
        self.assertIsNone(resolve_groove_profile("Ballad", time_signature="6/8"))
        self.assertIsNone(resolve_groove_profile("Blues groove"))


class GridTests(unittest.TestCase):
    def test_cinematic_ballad_holds_back_until_the_chorus(self) -> None:
        g = GROOVE_PROFILES["cinematic_ballad"]
        intro = g.bar_grid({}, "intro", bpm=96)
        verse = g.bar_grid({}, "verse", bpm=96)
        chorus = g.bar_grid({}, "chorus", bpm=96)
        self.assertEqual(intro["kick_beats"], [])
        self.assertEqual(verse["snare_beats"], [])
        self.assertEqual(chorus["snare_beats"], [2.0])  # half-time backbeat
        self.assertGreater(len(chorus["kick_beats"]), len(verse["kick_beats"]))
        self.assertLess(g.dynamics("verse"), g.dynamics("chorus"))

    def test_dance_pop_is_tresillo_with_offbeat_accents(self) -> None:
        g = GROOVE_PROFILES["dance_pop"]
        verse = g.bar_grid({}, "verse", bpm=96)
        self.assertEqual(verse["kick_beats"], [0.0, 1.5, 3.0])
        self.assertEqual(verse["snare_beats"], [1.0, 3.0])
        self.assertGreater(g.hat_accent(0.5), g.hat_accent(0.0))

    def test_tempo_variants(self) -> None:
        rock = GROOVE_PROFILES["rock_drive"]
        self.assertEqual(rock.bar_grid({}, "verse", bpm=120)["snare_beats"], [1.0, 3.0])
        self.assertEqual(rock.bar_grid({}, "verse", bpm=176)["snare_beats"], [2.0])


class CatalogStyleTests(unittest.TestCase):
    def test_jobim_is_bossa_and_ballads_are_ballads(self) -> None:
        infer = ba.infer_groove_style
        jobim = {"title": "Wave", "artist": "Antonio Carlos Jobim", "genre": "Jazz", "composer": "Antonio Carlos Jobim"}
        self.assertEqual(default_groove_for_song(jobim, infer_fn=infer), "Bossa nova")
        swing = {"title": "Satin Doll", "artist": "Duke Ellington", "genre": "Jazz"}
        self.assertEqual(default_groove_for_song(swing, infer_fn=infer), "Jazz swing")
        pinned = {"title": "Yesterday", "genre": "Rock", "extensions": {"default_groove": "Ballad"}}
        self.assertEqual(default_groove_for_song(pinned, infer_fn=infer), "Ballad")
        self.assertEqual(default_groove_for_song({"title": "X", "genre": "Rock"}, infer_fn=infer), "Rock groove")

    def test_regular_backing_uses_the_songs_own_groove_not_its_genre(self) -> None:
        """Shallow (genre Pop, a Ballad) used to get "Pop groove" from its genre."""
        from backing_context import _canonical_active_song_groove
        from song_catalog.catalog import load_song_catalog

        _lib, picker, *_ = load_song_catalog()
        found = {}
        for genre, songs in picker.items():
            for label, data in songs.items():
                for title in ("Shallow", "Shape of You", "Wave"):
                    if label.startswith(title + " ") and title not in found:
                        found[title] = (data.get("pick_key") or f"{genre}\x1f{label}", data.get("genre"))
        expected = {"Shallow": "Ballad", "Shape of You": "Pop groove", "Wave": "Bossa nova"}
        for title, (pick, genre) in found.items():
            session = {"active_catalog_pick_key": pick, "selected_song": {"pick_key": pick, "title": title, "genre": genre}}
            self.assertEqual(_canonical_active_song_groove(session), expected[title], title)
        self.assertEqual(set(found), set(expected))


class RenderTests(unittest.TestCase):
    def test_shallow_and_shape_of_you_have_different_rhythm(self) -> None:
        shallow = _envelope(*_render(*SHALLOW, "Ballad"))
        shape = _envelope(*_render(*SHAPE, "Pop groove"))
        self.assertLess(_corr(shallow, shape), 0.35)
        # Even on the same style, the dance-pop song keeps its own groove.
        shallow_pop = _envelope(*_render(*SHALLOW, "Pop groove"))
        self.assertLess(_corr(shallow_pop, shape), 0.6)

    def test_renders_are_repeatable(self) -> None:
        a, _ = _render(*SHAPE, "Pop groove")
        b, _ = _render(*SHAPE, "Pop groove")
        self.assertTrue(np.array_equal(a, b))

    def test_key_change_keeps_the_drum_timing(self) -> None:
        moved = [dict(e, chord={"G": "A", "C": "D"}[e["chord"]]) for e in EVENTS]
        drums_g, sr = ba.synthesize_chords_to_numpy(EVENTS, bpm=96, style="Pop groove", song_title=SHAPE[0], song_artist=SHAPE[1], layers=["rhythm"])
        drums_a, _ = ba.synthesize_chords_to_numpy(moved, bpm=96, style="Pop groove", song_title=SHAPE[0], song_artist=SHAPE[1], layers=["rhythm"])
        self.assertEqual(len(drums_g), len(drums_a))
        self.assertGreater(_corr(_envelope(drums_g, sr), _envelope(drums_a, sr)), 0.9)

    def test_bpm_change_scales_the_same_groove(self) -> None:
        slow, sr = _render(*SHAPE, "Pop groove", bpm=96)
        fast, _ = _render(*SHAPE, "Pop groove", bpm=120)
        self.assertAlmostEqual(len(slow) / len(fast), 120 / 96, delta=0.05)

    def test_strings_do_not_change_the_rhythm_section(self) -> None:
        off, _ = _render(*SHALLOW, "Ballad", strings=False, layers=("rhythm",))
        on, _ = _render(*SHALLOW, "Ballad", strings=True, layers=("rhythm",))
        self.assertTrue(np.array_equal(off, on))


if __name__ == "__main__":
    unittest.main()
