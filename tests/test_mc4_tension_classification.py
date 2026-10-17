"""MC4 — non-chord notes: stable colour vs contextual tension vs passing vs outside.

Human review of an Autumn Leaves guide-tone take (C♯m7♭5 → F♯7 → Bm, B minor) found every
in-scale extension praised as a "valid colour tone" — including B over F♯7 (the natural 11th a half
step above the 3rd, A♯), A over C♯m7♭5 (♭13) and G over Bm (♭6). Those depend on placement and
resolution; E over Bm (11th) and 9ths / 13ths over a dominant are stable colours.
"""

from __future__ import annotations

import unittest

from mission_analysis import _chord_tone_growth_line, _looks_like_praise
from mission_span_recording_context import build_timeline
from mission_span_take_evaluation import (
    altered_language_ok,
    build_harmony,
    evaluate_span_take,
    mission_vs_chord_tone_note,
    note_function,
    span_metric_overrides,
    span_note_shares,
)
from tests.test_mc4_span_recording import CONFIRMED, _block, _transcription

AUTUMN = ["C#m7b5", "F#7", "Bm"]
# (note, start beat, beats) — 4/4, one bar per chord.
RESOLVED = [
    ("E5", 0, 1), ("A5", 1, 1), ("G5", 2, 1), ("B5", 3, 1),       # C♯m7♭5: A (♭13) steps down to G (♭5)
    ("A#5", 4, 1), ("G#5", 5, 1), ("B5", 6, 1), ("A#5", 7, 1),    # F♯7: G♯ 9th; B (11th) on beat 3 → A♯
    ("D5", 8, 1), ("E5", 9, 1), ("G5", 10, 1), ("F#5", 11, 1),    # Bm: E (11th); G (♭6) on beat 3 → F♯
]
UNRESOLVED = [
    ("E5", 0, 1), ("A5", 2, 1.5), ("E5", 3.5, 0.5),               # A held on beat 3, then a leap
    ("A#5", 4, 1), ("D#6", 5, 1), ("B5", 6, 1.5), ("E5", 7.5, 0.5),  # D♯ 13th; B held on beat 3, then a leap
    ("D5", 8, 1), ("E5", 9, 1), ("G5", 10, 2),                    # G held to the end of the pass
]
PASSING = [
    ("E5", 0, 1), ("G5", 1, 1), ("B5", 2, 1), ("C#6", 3, 1),
    ("A#5", 4, 1), ("A#5", 5, 0.5), ("B5", 5.5, 0.5), ("C#6", 6, 1), ("E6", 7, 1),  # A♯–B–C♯ off the beat
    ("D5", 8, 1), ("F#5", 9, 1), ("B5", 10, 1), ("D6", 11, 1),
]


def _take(line, *, mission_id="guide_tone_voice_leading"):
    block = _block(AUTUMN, key="Bm", mission_id=mission_id, bpm=126)
    return evaluate_span_take(block, _transcription(line, bpm=126), CONFIRMED)


def _rows(result):
    return {d["chord"]: d for d in result["chord_detail"]}


class TestHarmonicCategory(unittest.TestCase):
    def setUp(self) -> None:
        tl = build_timeline([{"chord": c, "bars": 1} for c in AUTUMN], meter="4/4")
        self.h = build_harmony({"practice_key": "Bm", "timeline": tl})

    def test_autumn_leaves_categories(self) -> None:
        h = self.h
        self.assertEqual(note_function(h, 11, 1), "tension")  # B over F♯7: natural 11th vs A♯
        self.assertEqual(note_function(h, 4, 2), "colour")    # E over Bm: 11th
        self.assertEqual(note_function(h, 7, 2), "tension")   # G over Bm: ♭6
        self.assertEqual(note_function(h, 9, 0), "tension")   # A over C♯m7♭5: ♭13
        self.assertEqual(note_function(h, 6, 0), "colour")    # F♯ over C♯m7♭5: 11th
        self.assertEqual(note_function(h, 1, 2), "colour")    # C♯ over Bm: 9th

    def test_dominant_9th_and_13th_stay_stable(self) -> None:
        h = self.h
        self.assertEqual(note_function(h, 8, 1), "colour")    # G♯ over F♯7: 9th
        self.assertEqual(note_function(h, 3, 1), "colour")    # D♯ over F♯7: 13th
        tl = build_timeline([{"chord": "Dm7", "bars": 1}, {"chord": "G7", "bars": 1}, {"chord": "Cmaj7", "bars": 1}],
                            meter="4/4")
        c = build_harmony({"practice_key": "C", "timeline": tl})
        self.assertEqual(note_function(c, 9, 1), "colour")    # A over G7: 9th
        self.assertEqual(note_function(c, 4, 1), "colour")    # E over G7: 13th
        self.assertEqual(note_function(c, 0, 1), "tension")   # C over G7: 11th against B
        self.assertEqual(note_function(c, 2, 2), "colour")    # D over Cmaj7: 9th
        self.assertEqual(note_function(c, 5, 2), "tension")   # F over Cmaj7: 11th against E

    def test_altered_dominant_language(self) -> None:
        h = self.h
        self.assertEqual(note_function(h, 7, 1), "tension")   # G over F♯7: ♭9, in B harmonic minor
        self.assertEqual(note_function(h, 9, 1), "other")     # A over F♯7: ♯9, not in the chord scale …
        self.assertEqual(note_function(h, 9, 1, altered_ok=True), "tension")  # … unless altered language is in use
        self.assertTrue(altered_language_ok({}, "dominant_tension", "Intermediate"))
        self.assertTrue(altered_language_ok({"style": "Jazz"}, "", "Intermediate"))
        self.assertTrue(altered_language_ok({}, "", "Advanced"))
        self.assertFalse(altered_language_ok({"style": "Pop"}, "chord_tone_targeting", "Intermediate"))


class TestPlacementAndResolution(unittest.TestCase):
    def test_resolved_tensions(self) -> None:
        rows = _rows(_take(RESOLVED))
        self.assertEqual(rows["F♯7"]["tension_examples"], ["B (11th, resolved)"])
        self.assertEqual(rows["F♯7"]["colour_examples"], ["G♯ (9th)"])
        self.assertEqual(rows["Bm"]["colour_examples"], ["E (11th)"])
        self.assertEqual(rows["Bm"]["tension_examples"], ["G (♭6, resolved)"])
        self.assertEqual(rows["C♯m7♭5"]["tension_examples"], ["A (♭6, resolved)"])
        for d in rows.values():
            self.assertEqual(d["outside_tone_pct"], 0)
            self.assertEqual(d["tension_clash_pct"], 0)

    def test_unresolved_strong_beat_tensions_are_clashes(self) -> None:
        rows = _rows(_take(UNRESOLVED))
        self.assertEqual(rows["F♯7"]["tension_examples"], ["B (11th, unresolved)"])
        self.assertEqual(rows["F♯7"]["colour_examples"], ["D♯ (13th)"])
        self.assertEqual(rows["Bm"]["tension_examples"], ["G (♭6, unresolved)"])
        self.assertGreater(rows["F♯7"]["tension_clash_pct"], 0)
        self.assertEqual(rows["F♯7"]["outside_tone_pct"], 0)  # tense, not outside the harmony

    def test_eleventh_as_passing_tone(self) -> None:
        d = _rows(_take(PASSING))["F♯7"]
        self.assertEqual(d["tension_pct"], 0)
        self.assertGreater(d["passing_tone_pct"], 0)

    def test_scoring_follows_resolution_not_mission(self) -> None:
        resolved, unresolved = _take(RESOLVED), _take(UNRESOLVED)
        # Mission Compliance is unchanged by note classification (74 on 0416bda1 for both takes).
        self.assertEqual(resolved["score"], 74)
        self.assertEqual(unresolved["score"], 74)
        # A resolved tension costs no more than a colour tone (plain chord-tone share) …
        self.assertEqual(span_metric_overrides(resolved)["chord_tone_accuracy"], 58.3)
        # … an unresolved strong-beat clash costs extra.
        self.assertLess(span_metric_overrides(unresolved)["chord_tone_accuracy"],
                        span_note_shares(unresolved)["chord"] - 10)


class TestWording(unittest.TestCase):
    def test_mission_note_separates_colour_and_tension(self) -> None:
        text = mission_vs_chord_tone_note(_take(RESOLVED))
        self.assertIn("Some notes were stable colour tones (G♯ (9th), E (11th)), while others functioned as tensions "
                      "that depended on resolution", text)
        self.assertIn("B over F♯7 was an 11th suspension against the 3rd (A♯) — it resolved by step", text)
        self.assertNotIn("valid colour", text)
        self.assertNotIn("lower the broader score", text)
        unresolved = mission_vs_chord_tone_note(_take(UNRESOLVED))
        self.assertIn("it works best when it resolves clearly", unresolved)
        self.assertIn("Unresolved strong-beat clashes lower the broader score further.", unresolved)
        self.assertNotIn("outside the harmony", unresolved)

    def test_growth_line(self) -> None:
        observation, advice = _chord_tone_growth_line(span_note_shares(_take(RESOLVED)))
        self.assertEqual(observation, "Some notes were stable colour tones, while others functioned as tensions "
                                      "that depended on resolution.")
        self.assertNotIn("outside", observation)
        _obs, advice = _chord_tone_growth_line(span_note_shares(_take(UNRESOLVED)))
        self.assertTrue(advice.startswith("Let tensions resolve by step into a chord tone"))
        self.assertFalse(_looks_like_praise(advice))
        met, _a = _chord_tone_growth_line({"chord": 60, "colour": 20, "tension": 20, "mission_score": 100})
        self.assertEqual(met, "You hit the required targets, and some notes were stable colour tones, while others "
                              "functioned as tensions that depended on resolution.")


if __name__ == "__main__":
    unittest.main()
