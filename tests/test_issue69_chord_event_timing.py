"""Issue 69 Part E: chord events keep their positions through a key change.

A chart cell is not a bar. Say's Verse is written ``Bb:2|Eb:2p`` - two chords inside one
measure, the second pushed - and *Kiss Me*'s grid was corrected for the same reason
(``86487bcf`` "the bar grid is the recording's, not a half-bar grid"). A test that
assumed one chord per bar would pass while the Current Chord pointed at the wrong beat.

So these assert the event stream: how many events a cell produces, which beat each lands
on, whether the push survives, and that transposing changes the chord names and nothing
about the timing.

The expected chord names are the ones in the report: Say's four-chord loop reads
``D - G - Bm - A`` in D major, which is I - IV - vi - V of D, the same degrees as
``Bb - Eb - Gm - F`` in the song's own B flat.
"""

from __future__ import annotations

import unittest

from chord_events import section_chord_list_to_events
from music_theory import semitone_distance, transpose_chord

SAY_VERSE = ["Bb:2|Eb:2p", "Gm:2|F:2p"]


def transpose_cells(cells, from_key, to_key):
    """Move the chord symbols in subdivided cells, leaving the timing syntax alone."""
    steps = semitone_distance(from_key, to_key)
    out = []
    for cell in cells:
        moved = []
        for token in cell.split("|"):
            symbol, sep, tail = token.partition(":")
            new = transpose_chord(symbol, steps, reference_key=to_key)
            moved.append(f"{new}{sep}{tail}" if sep else new)
        out.append("|".join(moved))
    return out


def positions(events):
    return [(e.get("bar"), e.get("beat"), e.get("chord"), bool(e.get("push")))
            for e in events]


class SaysVerseIsTwoChordsToABar(unittest.TestCase):
    def setUp(self):
        self.events = section_chord_list_to_events("Verse 1", SAY_VERSE,
                                                   time_signature="4/4")

    def test_two_cells_produce_four_events(self):
        self.assertEqual(len(SAY_VERSE), 2)
        self.assertEqual(len(self.events), 4,
                         "a chart cell here is half a bar, not a bar")

    def test_each_event_lands_on_the_beat_the_chart_asks_for(self):
        self.assertEqual(positions(self.events), [
            (1, 1.0, "Bb", False),
            (1, 3.0, "Eb", True),
            (2, 1.0, "Gm", False),
            (2, 3.0, "F", True),
        ])

    def test_the_pushed_chords_are_the_second_in_each_bar(self):
        pushed = [e["chord"] for e in self.events if e.get("push")]
        self.assertEqual(pushed, ["Eb", "F"])


class TransposingMovesTheChordsAndNotTheClock(unittest.TestCase):
    """The property the Current / Next Chord depends on."""

    def setUp(self):
        self.original = section_chord_list_to_events(
            "Verse 1", SAY_VERSE, time_signature="4/4")
        self.in_d = section_chord_list_to_events(
            "Verse 1", transpose_cells(SAY_VERSE, "Bb", "D"), time_signature="4/4")

    def test_the_reported_loop_reads_d_g_bm_a(self):
        self.assertEqual([e["chord"] for e in self.in_d], ["D", "G", "Bm", "A"])

    def test_the_event_count_is_unchanged(self):
        self.assertEqual(len(self.in_d), len(self.original))

    def test_every_bar_and_beat_is_unchanged(self):
        self.assertEqual([(e.get("bar"), e.get("beat")) for e in self.in_d],
                         [(e.get("bar"), e.get("beat")) for e in self.original])

    def test_the_pushes_are_unchanged(self):
        self.assertEqual([bool(e.get("push")) for e in self.in_d],
                         [bool(e.get("push")) for e in self.original])

    def test_the_same_holds_for_the_key_the_defect_showed(self):
        """Bb -> C is the entry key that produced Csus4/D on screen."""
        in_c = section_chord_list_to_events(
            "Verse 1", transpose_cells(SAY_VERSE, "Bb", "C"), time_signature="4/4")
        self.assertEqual([e["chord"] for e in in_c], ["C", "F", "Am", "G"])
        self.assertEqual([(e.get("bar"), e.get("beat")) for e in in_c],
                         [(e.get("bar"), e.get("beat")) for e in self.original])


class SuspendedAndSlashChordsSurviveTheMove(unittest.TestCase):
    """Say's Intro is where the reported chord actually lives."""

    INTRO = ["Bb", "Bbsus4", "Bb", "Bbsus4/C",
             "Bb", "Bbsus4", "Bb", "Bbsus4/C"]

    def test_the_intro_in_d_major(self):
        moved = transpose_cells(self.INTRO, "Bb", "D")
        self.assertEqual(moved, ["D", "Dsus4", "D", "Dsus4/E",
                                 "D", "Dsus4", "D", "Dsus4/E"])

    def test_the_reported_pair_from_one_source_chord(self):
        """Both screenshots, from the same chart cell, under the two owners."""
        self.assertEqual(
            transpose_chord("Bbsus4/C", semitone_distance("Bb", "C"),
                            reference_key="C"), "Csus4/D")
        self.assertEqual(
            transpose_chord("Bbsus4/C", semitone_distance("Bb", "D"),
                            reference_key="D"), "Dsus4/E")

    def test_the_slash_bass_moves_with_the_root(self):
        for target, want in (("C", "Csus4/D"), ("D", "Dsus4/E"), ("Eb", "Ebsus4/F")):
            with self.subTest(target=target):
                self.assertEqual(
                    transpose_chord("Bbsus4/C", semitone_distance("Bb", target),
                                    reference_key=target), want)

    def test_the_intro_events_are_one_per_cell_here(self):
        """The Intro genuinely is one chord per cell - the Verse is not. Both matter."""
        events = section_chord_list_to_events("Intro", self.INTRO,
                                              time_signature="4/4")
        self.assertEqual(len(events), len(self.INTRO))
        self.assertTrue(all(e.get("beat") == 1.0 for e in events))


class TheCueTextAndTheEventsAgree(unittest.TestCase):
    """The cue line names the Verse loop; both must land on the same four chords."""

    def test_cue_and_events_give_the_same_four_chords_in_d(self):
        from musician_coaching import transpose_lyric_cue

        cue = ("Instrumental — B♭ · E♭ · Gm · F")
        moved = transpose_lyric_cue(cue, catalog_key="Bb", practice_key="D")
        from_cue = [p.strip() for p in moved.split("—", 1)[1].split("·")]

        events = section_chord_list_to_events(
            "Verse 1", transpose_cells(SAY_VERSE, "Bb", "D"), time_signature="4/4")
        from_events = [e["chord"] for e in events]

        self.assertEqual(from_cue, ["D", "G", "Bm", "A"])
        self.assertEqual(from_events, ["D", "G", "Bm", "A"])
        self.assertEqual(from_cue, from_events,
                         "the cue text and the chord events must agree")


class KissMesGridIsItsOwn(unittest.TestCase):
    """The second song, read from the catalog rather than assumed."""

    @classmethod
    def setUpClass(cls):
        from song_catalog.catalog import curated_song_records

        cls.record = next(
            (r for r in curated_song_records()
             if str(r.get("title") or "") == "Kiss Me"), None)

    def test_the_song_is_there_with_its_own_original_key(self):
        self.assertIsNotNone(self.record, "Kiss Me is not in the catalog")
        self.assertEqual(str(self.record.get("key") or ""), "Eb")

    def test_its_sections_produce_events_at_the_charted_beats(self):
        sections = self.record.get("sections") or {}
        self.assertTrue(sections, "Kiss Me has no sections")
        for name, cells in list(sections.items())[:4]:
            with self.subTest(section=name):
                events = section_chord_list_to_events(name, cells,
                                                      time_signature="4/4")
                self.assertGreaterEqual(len(events), len(cells))
                for event in events:
                    self.assertGreaterEqual(float(event.get("beat") or 0), 1.0)

    def test_transposing_kiss_me_preserves_its_timing(self):
        sections = self.record.get("sections") or {}
        name, cells = next(iter(sections.items()))
        before = section_chord_list_to_events(name, cells, time_signature="4/4")
        after = section_chord_list_to_events(
            name, transpose_cells(cells, "Eb", "G"), time_signature="4/4")
        self.assertEqual([(e.get("bar"), e.get("beat")) for e in after],
                         [(e.get("bar"), e.get("beat")) for e in before])
        self.assertEqual([bool(e.get("push")) for e in after],
                         [bool(e.get("push")) for e in before])
        self.assertNotEqual([e.get("chord") for e in after],
                            [e.get("chord") for e in before])


if __name__ == "__main__":
    unittest.main()
