"""Shallow and Shape of You play their complete form at Intermediate.

Intermediate trims a song's form (two choruses, one pre-chorus, final outro),
which dropped Shallow's Chorus 1 / Chorus 2 (16 of its 80 bars) and Shape of
You's Pre-Chorus 2 (8 of its 92 bars) from backing, the Lead Sheet and every
timeline built from them. Both songs now declare ``full_form_levels`` so
Intermediate keeps every authored section; other songs and Beginner keep
their trimmed forms.
"""

from __future__ import annotations

import unittest

from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from practice_studio import active_song_card_details
from song_catalog.catalog import load_song_catalog

SHALLOW_FORM = [
    "Intro", "Verse 1", "Refrain 1", "Verse 2", "Refrain 2",
    "Chorus 1", "Bridge", "Gaga build-up", "Chorus 2", "Outro",
]
SHAPE_FORM = [
    "Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2",
    "Pre-Chorus 2", "Chorus 2", "Bridge", "Final Chorus",
]


def _song(prefix: str) -> dict:
    _library, picker, *_ = load_song_catalog()
    for songs in picker.values():
        for label, data in songs.items():
            if label.startswith(prefix):
                return data
    raise AssertionError(f"{prefix!r} missing from the catalog")


def _beats(sections: dict) -> float:
    return sum(s.weight for bars in sections.values() for t in bars for s in parse_subdivisions(t))


def _level(song: dict, level: str) -> tuple[list[str], dict]:
    view, sections = resolve_level_chart(song, level)
    return list(view.get("section_order") or sections), sections


def _section_spans(order: list[str], sections: dict) -> dict[str, tuple[float, float]]:
    """Section -> (start beat, beats) on the one-pass timeline."""
    spans, cursor = {}, 0.0
    for name in order:
        beats = _beats({name: sections[name]})
        spans[name] = (cursor, beats)
        cursor += beats
    return spans


class ShallowFullFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.song = _song("Shallow ")
        cls.order, cls.sections = _level(cls.song, "Intermediate")

    def test_intermediate_plays_every_section(self) -> None:
        self.assertTrue(keeps_full_form(self.song, "Intermediate"))
        self.assertEqual(self.order, SHALLOW_FORM)
        self.assertEqual(list(self.sections), SHALLOW_FORM)
        self.assertEqual(_beats(self.sections), 320.0)

    def test_restored_choruses_sit_in_the_form(self) -> None:
        spans = _section_spans(self.order, self.sections)
        self.assertEqual(spans["Chorus 1"], (156.0, 32.0))   # bar 40, after Refrain 2's held D
        self.assertEqual(spans["Chorus 2"], (256.0, 32.0))   # bar 65, after the Gaga build-up
        self.assertEqual(spans["Outro"], (288.0, 32.0))

    def test_timing_inside_sections_is_unchanged(self) -> None:
        events = sections_dict_to_events(self.sections, time_signature="4/4", section_order=self.order)
        self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        self.assertEqual(
            [(e["chord"], e["duration_beats"]) for e in events[:3]],
            [("Em", 2.0), ("D", 1.5), ("G", 0.5)],
        )
        self.assertEqual(self.sections["Refrain 2"][-1], "D")
        self.assertEqual(self.sections["Chorus 1"], self.sections["Chorus 2"])

    def test_beginner_form_keeps_the_choruses(self) -> None:
        # Not touched by full_form_levels. Its Refrains used to fill both chorus
        # slots, so Beginner never reached a Chorus; they now follow their verses.
        order, _ = _level(self.song, "Beginner")
        self.assertEqual(
            order,
            ["Intro", "Verse 1", "Refrain 1", "Chorus 1", "Verse 2", "Refrain 2", "Chorus 2", "Outro"],
        )


class ShapeOfYouFullFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.song = _song("Shape of You ")
        cls.order, cls.sections = _level(cls.song, "Intermediate")

    def test_intermediate_plays_every_section(self) -> None:
        self.assertTrue(keeps_full_form(self.song, "Intermediate"))
        self.assertEqual(self.order, SHAPE_FORM)
        self.assertEqual(_beats(self.sections), 368.0)

    def test_restored_pre_chorus_keeps_half_bars_and_pushes(self) -> None:
        spans = _section_spans(self.order, self.sections)
        self.assertEqual(spans["Pre-Chorus 2"], (160.0, 32.0))   # bar 41, after Verse 2
        self.assertEqual(spans["Chorus 2"], (192.0, 64.0))
        self.assertEqual(self.sections["Pre-Chorus 2"], ["Bm:2|Em:2p", "G:2|A:2p"] * 4)
        events = sections_dict_to_events(
            {"Pre-Chorus 2": self.sections["Pre-Chorus 2"]}, time_signature="4/4", section_order=["Pre-Chorus 2"],
        )
        self.assertEqual(
            [(e["chord"], e["duration_beats"], bool(e.get("push"))) for e in events[:4]],
            [("Bm", 2.0, False), ("Em", 2.0, True), ("G", 2.0, False), ("A", 2.0, True)],
        )

    def test_beginner_form_is_unchanged(self) -> None:
        order, _ = _level(self.song, "Beginner")
        self.assertEqual(order, ["Verse 1", "Pre-Chorus 1", "Chorus 1", "Verse 2", "Chorus 2"])


class ScopeTests(unittest.TestCase):
    def test_other_songs_keep_their_intermediate_trim(self) -> None:
        perfect = _song("Perfect ")
        self.assertFalse(keeps_full_form(perfect, "Intermediate"))
        order, _ = _level(perfect, "Intermediate")
        self.assertNotIn("Chorus 3", order)

    def test_advanced_always_keeps_the_full_form(self) -> None:
        self.assertTrue(keeps_full_form({}, "Advanced"))
        self.assertFalse(keeps_full_form({}, "Intermediate"))

    def test_song_card_lists_the_full_form(self) -> None:
        card = active_song_card_details(_song("Shallow "), "Intermediate")
        steps = [s.strip() for s in str(card.get("section_summary") or "").split("→")]
        # The card drops section numbers: both choruses appear, between Refrain 2 and the Outro.
        self.assertEqual(len(steps), len(SHALLOW_FORM))
        self.assertEqual(steps.count("Chorus"), 2)


if __name__ == "__main__":
    unittest.main()
