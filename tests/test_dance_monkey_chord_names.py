"""Dance Monkey (Tones and I): Advanced Verse 1 bar 7 read ``Emaj7maj7.hit``.

Cause: the Advanced generator replaced ``E.hit`` -> ``Emaj7.hit`` and then ``E`` ->
``Emaj7`` again. The plain-E replacement already turns ``E.hit`` into ``Emaj7.hit`` (the
``.hit`` suffix is untouched), so the special case was removed. Intermediate/Beginner keep
``E.hit`` (single strum on E); Advanced uses Emaj7 on every other E bar of the loop
F#m7 | Dmaj7 | Emaj7 | C#m7 (loop F#m D E C#m is confirmed by the catalog levels). Only the
chord name changes; bars and durations are identical.
"""
from __future__ import annotations

import copy
import re
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records


class DanceMonkeyChordNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Dance Monkey"))

    def test_advanced_verse_hit_bar(self) -> None:
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(
            adv["Verse 1"],
            ["F#m7", "Dmaj7", "Emaj7", "C#m7", "F#m7", "Dmaj7", "Emaj7.hit", "C#m7"],
        )

    def test_lower_levels_keep_plain_hit(self) -> None:
        for level in ("Beginner", "Intermediate"):
            self.assertEqual(
                self.rec["chart_versions"][level]["Verse 1"],
                ["F#m", "D", "E", "C#m", "F#m", "D", "E.hit", "C#m"],
            )

    def test_no_doubled_extensions_and_valid(self) -> None:
        bad = re.compile(r"maj7maj7|m77|7maj7")
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(self.rec, level)
            for name, bars in secs.items():
                for chord in bars:
                    self.assertIsNone(bad.search(chord), (level, name, chord))
            events = sections_dict_to_events(secs, time_signature="4/4", section_order=list(secs))
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)


if __name__ == "__main__":
    unittest.main()
