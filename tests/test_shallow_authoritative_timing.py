"""Acceptance coverage for Shallow's authoritative 159-bar timing map."""

from __future__ import annotations

import unittest

import numpy as np

import backing_audio
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import transpose_chord
from song_catalog.curated_songs import _shallow_chart_pack
from songs.backing_chart import chart_grid_html


PATTERN_A = ["Em", "D:3|G:1", "G", "G"]
PATTERN_B = ["C", "C", "G:3|D:1", "D"]
PATTERN_C = ["G", "D:3|Em:1", "Em", "Em"]


def _playback_events(sections, order):
    return [
        {
            "chord": chord,
            "section": section,
            "bar_in_section": index,
            "section_bars": len(sections[section]),
        }
        for section in order
        for index, chord in enumerate(sections[section])
    ]


def _timed_events(events, bpm):
    beat_seconds = 60.0 / bpm
    timed = []
    for absolute_bar, event in enumerate(events, 1):
        cursor = 0.0
        for sub in parse_subdivisions(event["chord"], beats_per_bar=4):
            timed.append({
                "absolute_bar": absolute_bar,
                "chord": sub.chord,
                "start_time": ((absolute_bar - 1) * 4 + cursor) * beat_seconds,
                "end_time": ((absolute_bar - 1) * 4 + cursor + sub.weight) * beat_seconds,
                "duration": sub.weight * beat_seconds,
                "beat_duration": sub.weight,
            })
            cursor += sub.weight
    return timed


class ShallowTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = _shallow_chart_pack()
        cls.sections = cls.pack["sections"]
        cls.order = cls.pack["section_order"]

    def test_exact_form_and_structural_length(self) -> None:
        expected_lengths = {
            "Intro": 12,
            "Verse 1": 16,
            "Refrain 1": 16,
            "Verse 2": 16,
            "Refrain 2": 17,
            "Chorus 1": 16,
            "Bridge": 16,
            "Gaga build-up": 18,
            "Chorus 2": 16,
            "Outro": 16,
        }
        self.assertEqual(self.order, list(expected_lengths))
        actual_lengths = {name: len(self.sections[name]) for name in self.order}
        self.assertEqual(actual_lengths, expected_lengths)
        self.assertEqual(sum(actual_lengths.values()), 159)

    def test_intro_and_every_recurring_pattern(self) -> None:
        self.assertEqual(self.sections["Intro"], PATTERN_A + PATTERN_B + PATTERN_A)
        verse = PATTERN_A + PATTERN_B + PATTERN_A + PATTERN_B
        for name in ("Verse 1", "Refrain 1", "Verse 2"):
            self.assertEqual(self.sections[name], verse, name)
        for name in ("Chorus 1", "Bridge", "Chorus 2", "Outro"):
            self.assertEqual(self.sections[name][4:8], PATTERN_C, name)
            self.assertEqual(self.sections[name][12:16], PATTERN_C, name)

    def test_refrain_extension_build_up_choruses_and_outro(self) -> None:
        verse = PATTERN_A + PATTERN_B + PATTERN_A + PATTERN_B
        self.assertEqual(self.sections["Refrain 2"], verse + ["D"])
        chorus = (["Am", "Am", "D", "D"] + PATTERN_C) * 2
        self.assertEqual(self.sections["Chorus 1"], chorus)
        self.assertEqual(self.sections["Bridge"], chorus)
        self.assertEqual(self.sections["Chorus 2"], chorus)
        self.assertEqual(self.sections["Outro"], chorus)
        self.assertEqual(
            self.sections["Gaga build-up"],
            ["Em", "Em", "Bm", "Bm", "D", "D", "A", "A"] * 2 + ["A", "A"],
        )

    def test_real_beat_events_are_valid_and_cover_every_bar(self) -> None:
        events = sections_dict_to_events(
            self.sections, time_signature="4/4", section_order=self.order
        )
        self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        self.assertEqual(sum(float(event["duration_beats"]) for event in events), 159 * 4)
        intro_bar_2 = [e for e in events if e["section"] == "Intro" and e["bar"] == 2]
        self.assertEqual(
            [(e["chord"], e["beat"], e["duration_beats"]) for e in intro_bar_2],
            [("D", 1.0, 3.0), ("G", 4.0, 1.0)],
        )

    def test_audio_and_follow_timeline_share_the_same_beat_boundaries(self) -> None:
        events = _playback_events(self.sections, self.order)
        timeline = _timed_events(events, bpm=120)
        bar_2 = [event for event in timeline if event["absolute_bar"] == 2]
        self.assertEqual([(e["chord"], e["start_time"], e["end_time"]) for e in bar_2], [
            ("D", 2.0, 3.5),
            ("G", 3.5, 4.0),
        ])
        self.assertEqual(timeline[-1]["end_time"], 159 * 2.0)
        self.assertEqual(timeline[-1]["absolute_bar"], 159)

        # The synthesizer consumes the same token and retains the same bar grid.
        one_bar = [{"chord": "D:3|G:1", "section": "Intro", "bar_in_section": 1, "section_bars": 12}]
        audio, sample_rate = backing_audio.synthesize_chords_to_numpy(
            one_bar, bpm=120, loops=1, style="Ballad", song_title="Shallow", strings=False
        )
        self.assertAlmostEqual(len(audio) / sample_rate, 3.0, delta=0.05)
        self.assertGreater(float(np.max(np.abs(audio))), 0.0)

    def test_current_next_boundaries_bpm_and_practice_key(self) -> None:
        events = _playback_events({"Intro": self.sections["Intro"]}, ["Intro"])
        slow = _timed_events(events, bpm=60)
        fast = _timed_events(events, bpm=120)
        slow_bar_2 = [e for e in slow if e["absolute_bar"] == 2]
        fast_bar_2 = [e for e in fast if e["absolute_bar"] == 2]
        self.assertEqual([(e["chord"], e["beat_duration"]) for e in fast_bar_2], [("D", 3.0), ("G", 1.0)])
        self.assertEqual(slow_bar_2[0]["duration"], 2 * fast_bar_2[0]["duration"])
        self.assertEqual([e["chord"] for e in fast_bar_2], ["D", "G"])
        self.assertEqual(fast[3]["chord"], "G")

        moved = transpose_chord("D:3|G:1", 2, reference_key="A")
        self.assertEqual(moved, "E:3|A:1")
        self.assertEqual([s.weight for s in parse_subdivisions(moved)], [3.0, 1.0])

    def test_key_cycling_levels_and_lead_sheet_preserve_three_plus_one(self) -> None:
        for level, sections in self.pack["chart_versions"].items():
            token = sections["Intro"][1]
            self.assertEqual([s.weight for s in parse_subdivisions(token)], [3.0, 1.0], level)
        for steps in (-5, 0, 3, 7):
            token = transpose_chord("D:3|Em:1", steps, reference_key="G")
            self.assertEqual([s.weight for s in parse_subdivisions(token)], [3.0, 1.0])

        html = chart_grid_html(["D:3|G:1"], section_name="Intro", beats_per_bar=4)
        self.assertIn("data-beats='3'", html)
        self.assertIn("data-beats='1'", html)
        self.assertIn("flex-basis:75.0000%", html)
        self.assertIn("flex-basis:25.0000%", html)

    def test_strings_on_off_keep_identical_timing(self) -> None:
        events = [{"chord": "D:3|G:1", "section": "Intro", "bar_in_section": 1, "section_bars": 1}]
        off, sr_off = backing_audio.synthesize_chords_to_numpy(
            events, bpm=96, loops=1, style="Ballad", song_title="Shallow", strings=False
        )
        on, sr_on = backing_audio.synthesize_chords_to_numpy(
            events, bpm=96, loops=1, style="Ballad", song_title="Shallow", strings=True
        )
        self.assertEqual(sr_off, sr_on)
        self.assertEqual(len(off), len(on))
        self.assertFalse(np.array_equal(off, on))


if __name__ == "__main__":
    unittest.main()
