"""Thinking Out Loud (Ed Sheeran): D concert key, default tempo 79 BPM, not 75.

Sources: Hooktheory TheoryTab (79 BPM, 4/4, D major); Wikipedia infobox (79 BPM);
Musicnotes listings print "around 80". Metadata-only: chart cells untouched.
The chart is stored in the recording's concert key **D major**; the old C
spelling was the capo-2 guitar shape set, which made every transposing
instrument and the backing read a whole tone flat. Cells are unchanged in
count, only transposed.

Form still UNVERIFIED: recording 4:41 = 281 s = ~94 bars at 79 BPM; catalog
has 86/100/143 bars (Advanced adds Turnaround 8, Ending Tag 7, Instrumental 16
without a score). No anticipation/push evidence, none encoded.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

BARS = {"Beginner": 86, "Intermediate": 100, "Advanced": 143}


class ThinkingOutLoudTempoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "Thinking Out Loud")
        )

    def test_bpm_and_meter(self) -> None:
        ext = self.rec["extensions"]
        self.assertEqual(ext["default_bpm"], 79)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertEqual(self.rec["key"], "D")
        self.assertEqual(ext["concert_key"], "D")
        self.assertIn("capo", ext["capo_note"].lower())
        self.assertIn("79 BPM", ext["arrangement_notes"])
        self.assertNotIn("75 BPM", ext["arrangement_notes"])

    def test_cells_unchanged_and_duration(self) -> None:
        for level, n in BARS.items():
            _v, secs = resolve_level_chart(self.rec, level)
            self.assertEqual(sum(len(v) for v in secs.values()), n, level)
        self.assertAlmostEqual(143 * meter_timing(79, "4/4").bar_sec, 143 * 240 / 79, places=6)  # 434 s
        _v, adv = resolve_level_chart(self.rec, "Advanced")
        self.assertEqual(adv["Verse 1"][:4], ["D", "D/F#", "G", "A"])
        self.assertEqual(adv["Pre-Chorus 1"][:3], ["Em", "A", "D"])
        # no capo-shape spelling may survive anywhere in the chart
        for level in BARS:
            _v, secs = resolve_level_chart(self.rec, level)
            flat = [c for v in secs.values() for c in v]
            for stale in ("C/E", "Dm", "Am"):
                self.assertNotIn(stale, flat, f"{level}: stale capo spelling {stale}")


class ThinkingOutLoudFormIntentTests(unittest.TestCase):
    """The mid-form "Ending Tag" is intentional; pin it so it is not "fixed".

    A section named for an ending, sitting between Chorus 1 and Verse 2, reads
    like a defect. It is not. Guitarcoachmag's lesson on the recording describes
    the seven-chord figure (Bm, A, G, D/F#, Em, A7, D in concert D) played
    quickly with a dead hit "before the song returns to the verse", and says it
    repeats three times at the very end. The tag is both a turnaround and the
    ending, so the position is right.
    """

    def test_the_tag_sits_before_verse_2_and_is_also_the_outro(self) -> None:
        rec = copy.deepcopy(
            next(r for r in curated_song_records() if r["title"] == "Thinking Out Loud")
        )
        _v, adv = resolve_level_chart(rec, "Advanced")
        order = list(adv)
        self.assertIn("Ending Tag", order)
        self.assertEqual(order[order.index("Ending Tag") + 1], "Verse 2")
        tag = adv["Ending Tag"]
        self.assertEqual(len(tag), 7, "the figure is seven chords")
        self.assertEqual(tag, ["Bm", "A", "G", "D/F#", "Em", "A", "D"])
        # the Outro is the same figure repeated; the source says three times,
        # this chart has two. Pinned as-is so a change is a deliberate decision.
        self.assertEqual(adv["Outro"], tag * 2)


if __name__ == "__main__":
    unittest.main()
