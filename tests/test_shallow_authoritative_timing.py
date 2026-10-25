"""Acceptance coverage for Shallow's authoritative timing map.

Every chord plays for half its originally written length (320 beats, 80 bars;
was 636 beats, 159 bars). Refrain 2's final D, which would end on a half bar,
holds to the barline so Chorus 1 still starts on a downbeat.
"""

from __future__ import annotations

import unittest

import numpy as np

import backing_audio
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import transpose_chord
from song_catalog.curated_songs import _halve_bar_durations, _shallow_chart_pack
from songs.backing_chart import chart_grid_html


# Original patterns (one bar each) and their halved, repacked form.
PATTERN_A = ["Em:2|D:1.5|G:0.5", "G"]           # Em | D:3|G:1 | G | G
PATTERN_B = ["C", "G:1.5|D:2.5"]                # C | C | G:3|D:1 | D
PATTERN_C = ["G:2|D:1.5|Em:0.5", "Em"]          # G | D:3|Em:1 | Em | Em
CHORUS_HALF = ["Am", "D"] + PATTERN_C           # Am | Am | D | D + C


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


def _beats(sections) -> float:
    return sum(
        sub.weight
        for bars in sections.values()
        for token in bars
        for sub in parse_subdivisions(token, beats_per_bar=4)
    )


class HalvingTests(unittest.TestCase):
    def test_every_chord_keeps_half_its_beats(self) -> None:
        self.assertEqual(_halve_bar_durations(["Em", "D:3|G:1", "G", "G"]), PATTERN_A)
        self.assertEqual(_halve_bar_durations(["C", "C", "G:3|D:1", "D"]), PATTERN_B)
        # C | C (two bars of C) becomes one bar of C.
        self.assertEqual(_halve_bar_durations(["C", "C"]), ["C"])

    def test_a_half_bar_remainder_holds_to_the_barline(self) -> None:
        self.assertEqual(_halve_bar_durations(["Am", "Am", "D"]), ["Am", "D"])
        self.assertEqual(_halve_bar_durations(["G", "D"]), ["G:2|D:2"])

    def test_push_arrivals_anticipate_the_named_changes_only(self) -> None:
        pushes = (("B", "E"), ("G", "A"))
        self.assertEqual(
            _halve_bar_durations(["Bm", "Em", "G", "A"], push_arrivals=pushes),
            ["Bm:2|Em:2p", "G:2|A:2p"],
        )
        self.assertEqual(_halve_bar_durations(["Em", "Bm", "D", "A"], push_arrivals=pushes), ["Em:2|Bm:2", "D:2|A:2"])


class ShallowTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = _shallow_chart_pack()
        cls.sections = cls.pack["sections"]
        cls.order = cls.pack["section_order"]

    def test_exact_form_and_structural_length(self) -> None:
        expected_lengths = {
            "Intro": 6,
            "Verse 1": 8,
            "Refrain 1": 8,
            "Verse 2": 8,
            "Refrain 2": 9,
            "Chorus 1": 8,
            "Bridge": 8,
            "Gaga build-up": 9,
            "Chorus 2": 8,
            "Outro": 8,
        }
        self.assertEqual(self.order, list(expected_lengths))
        actual_lengths = {name: len(self.sections[name]) for name in self.order}
        self.assertEqual(actual_lengths, expected_lengths)
        self.assertEqual(sum(actual_lengths.values()), 80)
        # 318 beats from halving 636, plus Refrain 2's 2-beat hold to the barline.
        self.assertEqual(_beats(self.sections), 320.0)

    def test_intro_and_every_recurring_pattern(self) -> None:
        self.assertEqual(self.sections["Intro"], PATTERN_A + PATTERN_B + PATTERN_A)
        verse = PATTERN_A + PATTERN_B + PATTERN_A + PATTERN_B
        for name in ("Verse 1", "Refrain 1", "Verse 2"):
            self.assertEqual(self.sections[name], verse, name)
        for name in ("Chorus 1", "Bridge", "Chorus 2", "Outro"):
            self.assertEqual(self.sections[name][2:4], PATTERN_C, name)
            self.assertEqual(self.sections[name][6:8], PATTERN_C, name)

    def test_refrain_extension_build_up_choruses_and_outro(self) -> None:
        verse = PATTERN_A + PATTERN_B + PATTERN_A + PATTERN_B
        # The trailing pickup D (2 beats) holds to the barline: one more bar of D.
        self.assertEqual(self.sections["Refrain 2"], verse + ["D"])
        chorus = CHORUS_HALF * 2
        self.assertEqual(self.sections["Chorus 1"], chorus)
        self.assertEqual(self.sections["Bridge"], chorus)
        self.assertEqual(self.sections["Chorus 2"], chorus)
        self.assertEqual(self.sections["Outro"], chorus)
        self.assertEqual(self.sections["Gaga build-up"], ["Em", "Bm", "D", "A"] * 2 + ["A"])

    def test_real_beat_events_are_valid_and_cover_every_bar(self) -> None:
        events = sections_dict_to_events(
            self.sections, time_signature="4/4", section_order=self.order
        )
        self.assertEqual(validate_chord_events(events, time_signature="4/4"), [])
        self.assertEqual(sum(float(event["duration_beats"]) for event in events), 80 * 4)
        intro_bar_1 = [e for e in events if e["section"] == "Intro" and e["bar"] == 1]
        self.assertEqual(
            [(e["chord"], e["beat"], e["duration_beats"]) for e in intro_bar_1],
            [("Em", 1.0, 2.0), ("D", 3.0, 1.5), ("G", 4.5, 0.5)],
        )

    def test_audio_and_follow_timeline_share_the_same_beat_boundaries(self) -> None:
        events = _playback_events(self.sections, self.order)
        timeline = _timed_events(events, bpm=120)
        bar_1 = [event for event in timeline if event["absolute_bar"] == 1]
        self.assertEqual([(e["chord"], e["start_time"], e["end_time"]) for e in bar_1], [
            ("Em", 0.0, 1.0),
            ("D", 1.0, 1.75),
            ("G", 1.75, 2.0),
        ])
        self.assertEqual(timeline[-1]["end_time"], 80 * 2.0)
        self.assertEqual(timeline[-1]["absolute_bar"], 80)

        # The synthesizer consumes the same token on the same bar grid.
        one_bar = [{"chord": PATTERN_A[0], "section": "Intro", "bar_in_section": 0, "section_bars": 6}]
        audio, sample_rate = backing_audio.synthesize_chords_to_numpy(
            one_bar, bpm=120, loops=1, style="Ballad", song_title="Shallow", strings=False
        )
        self.assertAlmostEqual(len(audio) / sample_rate, 3.0, delta=0.05)
        self.assertGreater(float(np.max(np.abs(audio))), 0.0)

    def test_bpm_and_practice_key_change_pitch_and_speed_not_beats(self) -> None:
        events = _playback_events({"Intro": self.sections["Intro"]}, ["Intro"])
        slow = _timed_events(events, bpm=60)
        fast = _timed_events(events, bpm=120)
        self.assertEqual([(e["chord"], e["beat_duration"]) for e in fast[:3]], [("Em", 2.0), ("D", 1.5), ("G", 0.5)])
        self.assertEqual(slow[1]["duration"], 2 * fast[1]["duration"])

        moved = transpose_chord("Em:2|D:1.5|G:0.5", 2, reference_key="A")
        self.assertEqual(moved, "F#m:2|E:1.5|A:0.5")
        self.assertEqual([s.weight for s in parse_subdivisions(moved)], [2.0, 1.5, 0.5])

    def test_key_cycling_levels_and_lead_sheet_keep_the_halved_weights(self) -> None:
        for level, sections in self.pack["chart_versions"].items():
            token = sections["Intro"][0]
            self.assertEqual([s.weight for s in parse_subdivisions(token)], [2.0, 1.5, 0.5], level)
            self.assertEqual(sum(len(bars) for bars in sections.values()), 80, level)
        for steps in (-5, 0, 3, 7):
            token = transpose_chord("G:2|D:1.5|Em:0.5", steps, reference_key="G")
            self.assertEqual([s.weight for s in parse_subdivisions(token)], [2.0, 1.5, 0.5])

        html = chart_grid_html(["Em:2|D:1.5|G:0.5"], section_name="Intro", beats_per_bar=4)
        self.assertIn("flex-basis:50.0000%", html)
        self.assertIn("flex-basis:37.5000%", html)
        self.assertIn("flex-basis:12.5000%", html)

    def test_strings_on_off_keep_identical_timing(self) -> None:
        events = [{"chord": PATTERN_A[0], "section": "Intro", "bar_in_section": 0, "section_bars": 1}]
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
