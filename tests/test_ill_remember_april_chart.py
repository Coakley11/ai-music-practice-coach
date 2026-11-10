"""I'll Remember April (Gene de Paul): the COMPLETE 48-bar ABA chart in G, three levels, backing length.

Sources (secondary, no score copied): Jazzomat Weimar chord changes of Clifford Brown's and Sonny Rollins's solos
(per-bar, 48-bar A-B-A), jazzstandards.com's harmonic analysis (false key change to Bb, apparent E major, return via
Am7-D7) and Jazzadvice (ABA, 48 bars, four bars of Gmaj7 opening).  Some online charts show only 32 bars: this test pins the
full form.  The Latin-feel/swing change is arrangement-dependent and is not charted.  Not checked by ear.
"""
from __future__ import annotations

import copy
import io
import unittest
import wave

from backing_audio import generate_backing_track
from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import transpose_sections_dict
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

ORDER = ["A", "Bridge", "A2"]
A_ADV = ["Gmaj7"] * 4 + ["Gm7"] * 4 + ["Am7", "D7", "Bm7b5", "E7b9", "Am7", "D7", "Gmaj7", "Gmaj7"]
A_INT = ["Gmaj7"] * 4 + ["Gm7"] * 4 + ["Am7", "D7", "Bm7b5", "E7", "Am7", "D7", "Gmaj7", "Gmaj7"]
A_BEG = ["G"] * 4 + ["Gm"] * 4 + ["Am", "D7", "Bm", "E7", "Am", "D7", "G", "G"]
BRIDGE = ["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Cm7", "F7", "Bbmaj7", "Bbmaj7", "Am7", "D7", "Gmaj7", "Gmaj7", "F#m7", "B7", "Emaj7", "Am7|D7"]
BRIDGE_BEG = ["Cm", "F7", "Bb", "Bb", "Cm", "F7", "Bb", "Bb", "Am", "D7", "G", "G", "F#m", "B7", "E", "Am|D7"]
CHARTS = {
    "Advanced": {"A": A_ADV, "Bridge": BRIDGE, "A2": A_ADV},
    "Intermediate": {"A": A_INT, "Bridge": BRIDGE, "A2": A_INT},
    "Beginner": {"A": A_BEG, "Bridge": BRIDGE_BEG, "A2": A_BEG},
}


def rec():
    rows = [r for r in curated_song_records() if r["title"] == "I'll Remember April"]
    assert len(rows) == 1, rows
    return copy.deepcopy(rows[0])


class IllRememberAprilChart(unittest.TestCase):
    def test_single_jazz_entry_with_metadata(self) -> None:
        r = rec()
        self.assertEqual((r["artist"], r["genre"], r["key"]), ("Gene de Paul", "Jazz", "G"))
        self.assertIn("Gene de Paul", r["composer"])
        ext = r["extensions"]
        self.assertEqual((ext["time_signature"], ext["default_groove"], ext["default_bpm"]), ("4/4", "Jazz swing", 160))
        self.assertEqual(list(r["section_order"]), ORDER)
        self.assertIn("NOT", ext["arrangement_notes"])  # the Latin/swing feel change is documented as not charted

    def test_every_level_plays_the_complete_48_bar_form(self) -> None:
        r = rec()
        for level, chart in CHARTS.items():
            view, secs = resolve_level_chart(copy.deepcopy(r), level)
            order = list(view.get("section_order") or secs)
            self.assertEqual(order, ORDER, level)
            self.assertEqual({n: secs[n] for n in order}, chart, level)
            self.assertEqual([len(secs[n]) for n in order], [16, 16, 16], level)

    def test_major_to_minor_opening_and_the_two_a_sections_match(self) -> None:
        self.assertEqual(A_ADV[:8], ["Gmaj7"] * 4 + ["Gm7"] * 4)
        self.assertEqual(CHARTS["Advanced"]["A"], CHARTS["Advanced"]["A2"])

    def test_bridge_false_key_change_to_bb_apparent_e_major_and_return(self) -> None:
        self.assertEqual(BRIDGE[:4], ["Cm7", "F7", "Bbmaj7", "Bbmaj7"])
        self.assertEqual(BRIDGE[4:8], BRIDGE[:4])
        self.assertEqual(BRIDGE[8:12], ["Am7", "D7", "Gmaj7", "Gmaj7"])
        self.assertEqual(BRIDGE[12:], ["F#m7", "B7", "Emaj7", "Am7|D7"])
        self.assertEqual([s.weight for s in parse_subdivisions("Am7|D7")], [2.0, 2.0])

    def test_beginner_one_complete_chorus_with_simple_but_valid_chords(self) -> None:
        for name in ORDER:
            self.assertEqual([("|" in c) for c in CHARTS["Beginner"][name]], [("|" in c) for c in CHARTS["Advanced"][name]], name)
            for cell in CHARTS["Beginner"][name]:
                self.assertNotRegex(cell, r"maj7|m7|b5|b9")

    def test_events_validate_at_every_level(self) -> None:
        r = rec()
        for level in CHARTS:
            view, secs = resolve_level_chart(copy.deepcopy(r), level)
            order = list(view.get("section_order") or secs)
            events = sections_dict_to_events({n: secs[n] for n in order}, time_signature="4/4", section_order=order)
            self.assertEqual(validate_chord_events(events, time_signature="4/4"), [], level)

    def test_transposition_for_practice_key_and_transposing_instruments(self) -> None:
        # alto written key = concert + 9 -> E; tenor/soprano = concert + 2 -> A; flute and guitar concert G
        for target in ("G", "E", "A", "C"):
            s = transpose_sections_dict(CHARTS["Advanced"], "G", target) if target != "G" else CHARTS["Advanced"]
            self.assertEqual([len(s[n]) for n in ORDER], [16, 16, 16], target)
        alto = transpose_sections_dict(CHARTS["Advanced"], "G", "E")
        self.assertEqual(alto["A"][:5], ["Emaj7"] * 4 + ["Em7"])
        tenor = transpose_sections_dict(CHARTS["Advanced"], "G", "A")
        self.assertEqual(tenor["Bridge"][:4], ["Dm7", "G7", "Cmaj7", "Cmaj7"])

    def test_advanced_backing_length_is_48_bars(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Advanced")
        chords = [c for n in ORDER for c in secs[n]]
        self.assertEqual(len(chords), 48)
        wav = generate_backing_track(chords, bpm=160, loops=1, style="Jazz swing", level="Advanced", song_title="I'll Remember April", song_artist="Gene de Paul")
        with wave.open(io.BytesIO(wav)) as w:
            dur = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(dur, 48 * meter_timing(160, "4/4").bar_sec + 1.0, delta=0.4)


if __name__ == "__main__":
    unittest.main()
