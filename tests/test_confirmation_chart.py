"""Confirmation (Charlie Parker): 32-bar AABA bebop chart in F, three levels, split bars, backing length.

Sources (secondary, no score copied): jazzchanges.app (Brecker solo changes), a guitar transcription of the head, and
Jazzadvice's measure-by-measure analysis.  Published sheets differ in A bars 5, 6 and 8; the chart follows the version
all three describe.  Chords medium-high, timing medium, form high, groove low confidence; not checked by ear.
"""
from __future__ import annotations

import copy
import io
import re
import unittest
import wave

from backing_audio import generate_backing_track
from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import transpose_sections_dict
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["A", "A2", "Bridge", "A3"]
A_HEAD = ["Fmaj7", "Em7b5|A7", "Dm7|G7", "Cm7|F7", "Fm7|Bb7", "Am7b5|D7"]
ADV = {
    "A": A_HEAD + ["G7", "C7"],
    "A2": A_HEAD + ["Gm7|C7", "Fmaj7"],
    "Bridge": ["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Ebm7", "Ab7", "Dbmaj7", "Gm7|C7"],
    "A3": A_HEAD + ["Gm7|C7", "Fmaj7"],
}
BEG = {
    "A": ["F", "Em|A7", "Dm|G7", "Cm|F7", "Fm|Bb7", "Am|D7", "G7", "C7"],
    "A2": ["F", "Em|A7", "Dm|G7", "Cm|F7", "Fm|Bb7", "Am|D7", "Gm|C7", "F"],
    "Bridge": ["Cm", "F7", "Bb", "Bb", "Ebm", "Ab7", "Db", "Gm|C7"],
    "A3": ["F", "Em|A7", "Dm|G7", "Cm|F7", "Fm|Bb7", "Am|D7", "Gm|C7", "F"],
}


def rec():
    rows = [r for r in curated_song_records() if r["title"].lower() == "confirmation"]
    assert len(rows) == 1, rows
    return copy.deepcopy(rows[0])


class ConfirmationChart(unittest.TestCase):
    def test_single_jazz_entry_with_metadata(self) -> None:
        r = rec()
        self.assertEqual((r["artist"], r["genre"], r["key"], r["composer"]), ("Charlie Parker", "Jazz", "F", "Charlie Parker"))
        ext = r["extensions"]
        self.assertEqual((ext["time_signature"], ext["default_groove"], ext["default_bpm"]), ("4/4", "Jazz swing", 176))
        self.assertEqual(ext["chart_confidence"]["form"], "high")
        self.assertEqual(list(r["section_order"]), ORDER)

    def test_levels_exact_and_complete_chorus(self) -> None:
        r = rec()
        for level, chart in (("Beginner", BEG), ("Intermediate", ADV), ("Advanced", ADV)):
            view, secs = resolve_level_chart(copy.deepcopy(r), level)
            order = list(view.get("section_order") or secs)
            self.assertEqual(order, ORDER, level)
            self.assertEqual({n: secs[n] for n in order}, chart, level)
            self.assertEqual(sum(len(secs[n]) for n in order), 32, level)

    def test_harmonic_rhythm_split_bars_weigh_two_beats_each(self) -> None:
        for cell in ("Em7b5|A7", "Dm7|G7", "Cm7|F7", "Fm7|Bb7", "Am7b5|D7", "Gm7|C7"):
            subs = parse_subdivisions(cell)
            self.assertEqual([s.weight for s in subs], [2.0, 2.0], cell)
        self.assertEqual(sum(s.weight for t in ADV["A"] for s in parse_subdivisions(t)), 32.0)

    def test_distinguishing_bar_7_and_8_between_the_first_and_later_a(self) -> None:
        self.assertEqual(ADV["A"][6:], ["G7", "C7"])
        self.assertEqual(ADV["A2"][6:], ["Gm7|C7", "Fmaj7"])
        self.assertEqual(ADV["A3"], ADV["A2"])

    def test_beginner_is_valid_triad_level_harmony_with_the_same_bar_rhythm(self) -> None:
        for name in ORDER:
            self.assertEqual([("|" in c) for c in BEG[name]], [("|" in c) for c in ADV[name]], name)
            for cell in BEG[name]:
                self.assertNotRegex(cell, r"maj7|m7|b5|ø")

    def test_events_validate_at_every_level(self) -> None:
        r = rec()
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, secs = resolve_level_chart(copy.deepcopy(r), level)
            order = list(view.get("section_order") or secs)
            events = sections_dict_to_events({n: secs[n] for n in order}, time_signature="4/4", section_order=order)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)

    def test_transposition_for_practice_key_and_transposing_instruments(self) -> None:
        # alto written key = concert + 9 -> D; tenor/soprano = concert + 2 -> G; flute and guitar stay concert F
        for target in ("F", "D", "G", "Bb"):
            s = transpose_sections_dict(ADV, "F", target) if target != "F" else ADV
            self.assertEqual({n: len(c) for n, c in s.items()}, {n: 8 for n in ORDER}, target)
            self.assertEqual(sum("|" in c for n in ORDER for c in s[n]), sum("|" in c for n in ORDER for c in ADV[n]), target)
        alto = transpose_sections_dict(ADV, "F", "D")
        self.assertEqual(alto["A"][:3], ["Dmaj7", "C#m7b5|F#7", "Bm7|E7"])
        tenor = transpose_sections_dict(ADV, "F", "G")
        self.assertEqual(tenor["A"][:3], ["Gmaj7", "F#m7b5|B7", "Em7|A7"])

    def test_advanced_backing_length_is_32_bars(self) -> None:
        r = rec()
        _v, secs = resolve_level_chart(r, "Advanced")
        chords = [c for n in ORDER for c in secs[n]]
        wav = generate_backing_track(chords, bpm=176, loops=1, style="Jazz swing", level="Advanced", song_title="Confirmation", song_artist="Charlie Parker")
        with wave.open(io.BytesIO(wav)) as w:
            dur = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(dur, 32 * meter_timing(176, "4/4").bar_sec + 1.0, delta=0.4)


if __name__ == "__main__":
    unittest.main()
