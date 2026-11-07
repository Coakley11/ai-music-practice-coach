"""I'm Yours (Jason Mraz): Advanced bridge chord names were malformed (Gmaj7maj7, Em77).

Cause: the Advanced-level generator replaced ``G|`` -> ``Gmaj7|`` and ``Em|D`` -> ``Em7|D``
and then replaced ``G`` and ``Em`` again, double-applying the extension. The correct
Advanced bridge bars 7-8 are ``Gmaj7|D/F#`` and ``Em7|D`` (the Beginner/Intermediate bars
are ``G|D/F#`` and ``Em|D``; Hooktheory's bridge is I, V6 (D/F#), vi, V, IV with plain
triads, https://www.hooktheory.com/theorytab/view/jason-mraz/im-yours, so the roots,
inversion and split are confirmed and Gmaj7 / Em7 are this catalog's Advanced decorations
for I and vi used on every other Advanced bar). Chord names only; the bars, splits and
durations are unchanged.
"""
from __future__ import annotations

import copy
import re
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

# concert key B (the former G-shape names moved up four semitones: G->B, D->F#, Em->G#m, C->E, A7->C#7)
ADV_BRIDGE = ["Bmaj7", "F#", "G#m7", "F#", "Eadd9", "C#7sus4", "Bmaj7|F#/A#", "G#m7|F#", "Eadd9", "C#7sus4"]


class ImYoursChordNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "I'm Yours"))

    def test_advanced_bridge_exact(self) -> None:
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Bridge"], ADV_BRIDGE)

    def test_other_levels_unchanged(self) -> None:
        _v, inter = resolve_level_chart(self.rec, "Intermediate")
        self.assertEqual(inter["Bridge"][6:8], ["B|F#/A#", "G#m|F#"])
        beg = self.rec["chart_versions"]["Beginner"]["Bridge"]
        self.assertEqual(beg[5:7], ["B|F#/A#", "G#m|F#"])

    def test_no_doubled_extensions_anywhere(self) -> None:
        bad = re.compile(r"maj7maj7|m77|77|add9add9|sus4sus|7sus4sus")
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(self.rec, level)
            for name, bars in secs.items():
                for chord in bars:
                    self.assertIsNone(bad.search(chord), (level, name, chord))
            events = sections_dict_to_events(secs, time_signature="4/4", section_order=list(secs))
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)


if __name__ == "__main__":
    unittest.main()
