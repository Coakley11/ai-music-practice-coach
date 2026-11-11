"""Body and Soul: the full 32-bar AABA chart, replacing a 16-bar skeleton.

The old chart was two 8-bar sections, 16 bars in all, and it was wrong in three
separate ways:

* the A section opened on ``Dbmaj7`` - the tonic - where the tune opens on
  ``Ebm7``, the ii of Db;
* the ``E7 - Amaj7`` and ``Abm7 - Db7 - Gbmaj7`` material in that A section is
  **bridge** harmony. The bridge modulates to D major, so that material had been
  placed in the wrong section;
* the form is 32-bar AABA, so a 16-bar chart cannot state it at all.

Reference arrangement, named and kept consistent: the **iReal Pro chart** (Jazz
1460 playlist) as catalogued bar by bar at jazzchanges.app/body-and-soul. The
same page carries a **Coleman Hawkins 1939** transcription from the Weimar Jazz
Database, which reharmonises heavily and has one garbled bar; its substitutions
are deliberately not merged. The Library of Congress National Recording
Preservation Board essay on the tune independently describes the same Db-major
setting, Eb-minor opening and D-major bridge, and jazzstandards.com gives the
32-bar AABA form.

Beat divisions: the source gives chords per bar but not beat positions. Two-chord
bars split 2+2 and four-chord bars take a beat each, which are the standard
readings; the three-chord bars use the conventional 2+1+1 and are the only
inferred divisions. No push is written anywhere, because the source gives none.

No score was copied and no melody is reproduced. Not checked by ear.
"""
from __future__ import annotations

import copy
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

TITLE, ARTIST = "Body and Soul", "Jazz Standard"
SECTIONS = ["A1", "A2", "Bridge", "A3"]


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST)
    )


class TheFormIsThirtyTwoBarAABA(unittest.TestCase):
    def test_four_eight_bar_sections_in_order(self) -> None:
        r = rec()
        self.assertEqual(list(r.get("section_order") or r["sections"]), SECTIONS)
        for name in SECTIONS:
            self.assertEqual(len(r["sections"][name]), 8, name)

    def test_every_level_carries_the_complete_chorus(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            self.assertEqual(list(secs), SECTIONS, level)
            self.assertEqual(sum(len(v) for v in secs.values()), 32, level)

    def test_beginner_is_not_abridged_by_dropping_an_a_section(self) -> None:
        """full_form_levels guards this; without it Beginner came out 16 bars."""
        r = rec()
        self.assertIn("Beginner", r["extensions"].get("full_form_levels") or [])
        _v, secs = resolve_level_chart(r, "Beginner")
        self.assertEqual(len([n for n in secs if n.startswith("A")]), 3)


class TheHarmonyMatchesTheReference(unittest.TestCase):
    def test_the_a_section_opens_on_the_two_chord_not_the_tonic(self) -> None:
        r = rec()
        for name in ("A1", "A2", "A3"):
            first = str(r["sections"][name][0])
            self.assertTrue(first.startswith("Ebm7"), f"{name} opens {first!r}")
            self.assertFalse(first.startswith("Dbmaj7"),
                             f"{name} still opens on the tonic")

    def test_the_two_five_one_lands_in_bars_two_three_and_seven_eight(self) -> None:
        a1 = rec()["sections"]["A1"]
        self.assertEqual(a1[1], "Ebm7|Ab7")          # ii - V
        self.assertTrue(a1[2].startswith("Dbmaj7"))  # I
        self.assertEqual(a1[6], "Bbm7:2|Ebm7:1|Ab7:1")
        self.assertTrue(a1[7].startswith("Db6"))     # I again

    def test_the_bridge_is_in_d_major_and_turns_back_to_db(self) -> None:
        bridge = rec()["sections"]["Bridge"]
        self.assertTrue(bridge[0].startswith("Dmaj7"))
        self.assertEqual(bridge[3], "Dmaj7")
        self.assertIn("C7", bridge[7])
        self.assertIn("Bb7", bridge[7], "the last bridge bar turns back to Db")

    def test_the_bridge_harmony_is_no_longer_in_an_a_section(self) -> None:
        r = rec()
        for name in ("A1", "A2", "A3"):
            cells = " ".join(str(c) for c in r["sections"][name])
            for stray in ("Amaj7", "Gbmaj7", "E7"):
                self.assertNotIn(stray, cells, f"{name} still has {stray}")

    def test_the_first_and_second_endings_differ(self) -> None:
        r = rec()
        self.assertNotEqual(r["sections"]["A1"][7], r["sections"]["A2"][7])
        self.assertIn("A7", r["sections"]["A2"][7], "the 2nd ending sets up D major")
        self.assertEqual(r["sections"]["A3"][7], "Db6", "the last A resolves")

    def test_no_push_is_written(self) -> None:
        import chord_subdivisions as cs

        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, chords in secs.items():
                for tok in chords:
                    for sub in cs.parse_subdivisions(tok, beats_per_bar=4):
                        self.assertFalse(sub.push, f"{level} {name}: {tok!r}")


class TheBeatDivisionsAreSound(unittest.TestCase):
    def test_every_bar_fills_its_meter_at_every_level(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, chords in secs.items():
                ev = section_chord_list_to_events(name, chords, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

    def test_two_chord_bars_split_the_bar_equally(self) -> None:
        ev = section_chord_list_to_events("A1", ["Ebm7|Bb7b13"], time_signature="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"], e["chord"]) for e in ev],
                         [(1.0, 2.0, "Ebm7"), (3.0, 2.0, "Bb7b13")])

    def test_four_chord_bars_take_a_beat_each(self) -> None:
        ev = section_chord_list_to_events("A1", ["Db6|Gb7|Fm7b5|Bb7"],
                                          time_signature="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"]) for e in ev],
                         [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (4.0, 1.0)])

    def test_three_chord_bars_use_the_conventional_two_one_one(self) -> None:
        ev = section_chord_list_to_events("A1", ["Bbm7:2|Ebm7:1|Ab7:1"],
                                          time_signature="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"], e["chord"]) for e in ev],
                         [(1.0, 2.0, "Bbm7"), (3.0, 1.0, "Ebm7"), (4.0, 1.0, "Ab7")])

    def test_most_bars_carry_more_than_one_chord(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Advanced")
        cells = [str(c) for ch in secs.values() for c in ch]
        split = [c for c in cells if "|" in c]
        self.assertEqual(len(cells), 32)
        self.assertGreaterEqual(len(split), 25, "the tune's harmonic rhythm is dense")


class EveryChordVoices(unittest.TestCase):
    def test_no_cell_fails_to_voice_or_loses_its_root(self) -> None:
        from backing_audio import chord_notes
        import chord_subdivisions as cs

        pcs = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
               "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10,
               "Bb": 10, "B": 11}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, chords in secs.items():
                for tok in chords:
                    for sub in cs.parse_subdivisions(tok, beats_per_bar=4):
                        notes = chord_notes(sub.chord)
                        self.assertTrue(notes, f"{level} {name}: {sub.chord!r}")
                        root = sub.chord.split("/")[0]
                        root = root[:2] if len(root) > 1 and root[1] in "#b" else root[:1]
                        if root in pcs:
                            self.assertIn(pcs[root] % 12, {n % 12 for n in notes},
                                          f"{level} {name}: {sub.chord!r} lost its root")


if __name__ == "__main__":
    unittest.main()
