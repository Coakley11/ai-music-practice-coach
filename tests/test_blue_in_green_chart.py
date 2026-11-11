"""Blue in Green: the 10-bar circular form, replacing an 8-bar two-chord vamp.

The old chart was eight bars of ``Gm7 Gm7 A7#9 A7#9 Gm7 Gm7 Gm7 Gm7`` in Gm.
Bill Evans's own *Kind of Blue* liner note calls the piece "a 10-measure
circular form", so an eight-bar chart cannot be right, and the vamp left out the
tune's harmonic motion entirely.

Reference, named and kept consistent: **Henry Martin's lead sheet**, Example 1 in
his analysis in the *Journal of Jazz Studies* vol. 11 no. 1 (2016) roundtable
"Circular Thinking", as catalogued bar by bar at jazzchanges.app/blue-in-green.
Martin uses the published version deliberately, because Davis plays the tune
freely. Key areas move D minor - Bb - D minor - A minor - D minor.

The **iReal Pro** chart on the same page is a 14-bar version with codas and
differs at several chords (Dm7 for Dm9, Cm7 for Cm9, E7b13 for E7b9, Dm6 for
Dm(maj7), Am7 for Am(maj7)). It is a later reharmonisation and is deliberately
not merged; the Intermediate level reduces Martin's own chords instead of
borrowing iReal's.

Timing: only bars 3 and 4 carry two chords, and the source states they share the
bar equally - so that division is given, not inferred. Bar 10 leads straight
back to bar 1 with no cadence, which is the circular part, so **no turnaround is
appended**.

The four-bar piano introduction is **not charted**: the source describes it only
as following bars 3-10 of the head in reduced form and gives no chords, so
writing one would be invention.

The opening chord is contested and left as Martin gives it: Gm13, against Gm7,
Gm6 or Bbmaj7#11 elsewhere, with Evans's trio versions differing from Davis's.

No score was copied and no melody is reproduced. Not checked by ear.
"""
from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

TITLE, ARTIST = "Blue in Green", "Miles Davis"
HEAD = "Head (10-bar circular form)"
MARTIN = ["Gm13", "A7#5#9", "Dm9|Db7#5#9", "Cm9|F7b9", "Bbmaj7",
          "A7#5#9", "Dmmaj7", "E7b9", "Ammaj7", "Dm7"]


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST)
    )


class TheFormIsTenBars(unittest.TestCase):
    def test_one_section_of_exactly_ten_bars(self) -> None:
        r = rec()
        self.assertEqual(list(r["sections"]), [HEAD])
        self.assertEqual(len(r["sections"][HEAD]), 10)

    def test_every_level_keeps_all_ten_bars(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            self.assertEqual(sum(len(v) for v in secs.values()), 10, level)

    def test_the_old_eight_bar_vamp_is_gone(self) -> None:
        r = rec()
        cells = r["sections"][HEAD]
        self.assertNotEqual(len(cells), 8)
        self.assertNotEqual(cells[:4], ["Gm7", "Gm7", "A7#9", "A7#9"])

    def test_the_key_is_d_minor(self) -> None:
        self.assertEqual(rec()["key"], "Dm")

    def test_no_introduction_is_invented(self) -> None:
        """The source gives the intro's shape but not its chords."""
        r = rec()
        self.assertEqual(len(r["sections"]), 1)
        for name in r["sections"]:
            self.assertNotIn("intro", name.lower())


class TheHarmonyIsMartinsLeadSheet(unittest.TestCase):
    def test_the_advanced_chart_is_the_reference_bar_for_bar(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Advanced")
        self.assertEqual(secs[HEAD], MARTIN)

    def test_the_key_areas_move_as_the_source_describes(self) -> None:
        cells = rec()["sections"][HEAD]
        self.assertTrue(cells[0].startswith("Gm"))      # D minor area
        self.assertTrue(cells[4].startswith("Bbmaj7"))  # Bb
        self.assertTrue(cells[7].startswith("E7"))      # A minor approach
        self.assertTrue(cells[8].startswith("Am"))      # A minor
        self.assertEqual(cells[9], "Dm7")               # home

    def test_the_iReal_reharmonisation_is_not_mixed_in(self) -> None:
        for level in ("Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            cells = " ".join(secs[HEAD])
            for ireal_only in ("Dm6", "E7b13"):
                self.assertNotIn(ireal_only, cells, f"{level}: {ireal_only}")

    def test_intermediate_reduces_martin_rather_than_borrowing(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Intermediate")
        cells = secs[HEAD]
        # Martin's own chords, with the stacked alterations reduced
        self.assertEqual(cells[1], "A7")
        self.assertEqual(cells[6], "Dmmaj7")
        self.assertEqual(cells[8], "Ammaj7")

    def test_the_contested_opening_is_recorded(self) -> None:
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("Gm13", notes)
        for variant in ("Gm7", "Gm6", "Bbmaj7#11"):
            self.assertIn(variant, notes, variant)


class TheTwoSplitBarsDivideEqually(unittest.TestCase):
    def test_bars_three_and_four_split_two_plus_two(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Advanced")
        ev = section_chord_list_to_events(HEAD, secs[HEAD], time_signature="4/4")
        got = [(e["bar"], e["beat"], e["duration_beats"], e["chord"])
               for e in ev if e["bar"] in (3, 4)]
        self.assertEqual(got, [(3, 1.0, 2.0, "Dm9"), (3, 3.0, 2.0, "Db7#5#9"),
                               (4, 1.0, 2.0, "Cm9"), (4, 3.0, 2.0, "F7b9")])

    def test_no_other_bar_is_split(self) -> None:
        _v, secs = resolve_level_chart(rec(), "Advanced")
        split = [i + 1 for i, c in enumerate(secs[HEAD]) if "|" in str(c)]
        self.assertEqual(split, [3, 4])

    def test_every_bar_fills_the_meter_at_every_level(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            ev = section_chord_list_to_events(HEAD, secs[HEAD], time_signature="4/4")
            self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [], level)

    def test_no_push_is_written(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for tok in secs[HEAD]:
                for sub in cs.parse_subdivisions(tok, beats_per_bar=4):
                    self.assertFalse(sub.push, f"{level}: {tok!r}")


class TheFormLoopsWithoutACadence(unittest.TestCase):
    def test_the_last_bar_is_the_tonic_minor_seventh(self) -> None:
        self.assertEqual(rec()["sections"][HEAD][-1], "Dm7")

    def test_nothing_was_appended_to_lengthen_the_form(self) -> None:
        cells = rec()["sections"][HEAD]
        self.assertEqual(len(cells), 10, "a turnaround or coda was added")

    def test_the_loop_point_runs_straight_back_to_bar_one(self) -> None:
        """Bar 10 into bar 1: Dm7 -> Gm13, no V-i cadence between them."""
        cells = rec()["sections"][HEAD]
        self.assertEqual((cells[-1], cells[0]), ("Dm7", "Gm13"))
        ev = section_chord_list_to_events(HEAD, cells * 2, time_signature="4/4")
        pairs = [(ev[i]["chord"], ev[i + 1]["chord"]) for i in range(len(ev) - 1)]
        self.assertIn(("Dm7", "Gm13"), pairs, "the wrap is not seamless")


if __name__ == "__main__":
    unittest.main()
