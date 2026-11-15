"""Karaoke Part 5: Just the Two of Us - the ii and the V share the fourth bar.

The chart gave Ebm7 and Ab7 a bar each. Measured from the chart itself, that makes the
turnaround five bars long, so the eight-bar section held 1.60 of them and stopped three bars
into its second pass - a loop that cannot close. The song's turnaround is four bars:

    Dbmaj7 | C7 | Fm7 | Ebm7 Ab7

In Db that is Imaj7 - VII7 - iii7 - ii7 V7, the ii and the V arriving together in bar four.

Read back out of the rendered keys layer by chroma, with no reference to the chart, before and
after the correction:

    before   bar 4: beats 1-2 Ebm7   beats 3-4 Ebm7      bar 5: Ab7 for a whole bar
    after    bar 4: beats 1-2 Ebm7   beats 3-4 Ab7       bar 5: Dbmaj7, the turnaround closed

These tests pin the timing, not the spelling, so a later chord-colour change at any level is
free while the four-bar turnaround is not.
"""

from __future__ import annotations

import unittest

from chord_subdivisions import parse_subdivisions, primary_chord
from song_catalog.catalog import load_song_catalog

TITLE = "Just the Two of Us"
#: Every section built on the turnaround. The Bridge is not: its chords are one to a bar.
TURNAROUND_SECTIONS = ("Intro / Groove", "Verse", "Chorus", "Solo")


def entry() -> dict:
    def find(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(key, str) and key == TITLE and isinstance(value, dict):
                    return value
                got = find(value)
                if got:
                    return got
        elif isinstance(obj, (list, tuple)):
            for value in obj:
                got = find(value)
                if got:
                    return got
        return None

    found = find(load_song_catalog())
    assert found, f"{TITLE} is not in the catalog"
    return found


def bars(section: list) -> list[list]:
    """Each bar's sub-chords as (chord, beats)."""
    return [
        [(s.chord, float(s.weight)) for s in parse_subdivisions(token, beats_per_bar=4.0)]
        for token in section
    ]


class TheTurnaroundIsFourBars(unittest.TestCase):
    def setUp(self) -> None:
        self.song = entry()
        versions = self.song.get("chart_versions") or {}
        # The three practice levels live under chart_versions; ``sections`` is the level the
        # current reader resolved to. Named explicitly, and asserted below, because an earlier
        # version of this file guessed key names that do not exist and silently tested one
        # level while reporting on three.
        self.levels = {name: versions[name] for name in ("Beginner", "Intermediate", "Advanced")
                       if isinstance(versions.get(name), dict) and versions[name]}
        self.assertEqual(sorted(self.levels), ["Advanced", "Beginner", "Intermediate"],
                         f"expected all three practice levels, found {sorted(versions)}")
        self.levels["resolved"] = self.song.get("sections") or {}

    def test_every_level_has_the_sections(self) -> None:
        for name, sections in self.levels.items():
            for sec in TURNAROUND_SECTIONS:
                with self.subTest(level=name, section=sec):
                    self.assertIn(sec, sections)

    def test_the_fourth_bar_holds_two_chords_of_two_beats(self) -> None:
        for name, sections in self.levels.items():
            for sec in TURNAROUND_SECTIONS:
                with self.subTest(level=name, section=sec):
                    bar4 = bars(sections[sec])[3]
                    self.assertEqual(len(bar4), 2, f"bar 4 of {sec} should hold the ii and the V")
                    self.assertEqual([w for _, w in bar4], [2.0, 2.0])

    def test_the_fourth_bar_is_the_ii_then_the_v(self) -> None:
        """Spelling is free; the roots are not - Eb minor then Ab, in that order."""
        for name, sections in self.levels.items():
            for sec in TURNAROUND_SECTIONS:
                with self.subTest(level=name, section=sec):
                    bar4 = bars(sections[sec])[3]
                    self.assertTrue(bar4[0][0].startswith("Ebm"), bar4)
                    self.assertTrue(bar4[1][0].startswith("Ab"), bar4)

    def test_each_section_holds_whole_turnarounds(self) -> None:
        for name, sections in self.levels.items():
            for sec in TURNAROUND_SECTIONS:
                with self.subTest(level=name, section=sec):
                    heads = [primary_chord(t) for t in sections[sec]]
                    period = heads.index(heads[0], 1)
                    self.assertEqual(period, 4, f"{sec} turnaround is {period} bars")
                    self.assertEqual(len(heads) % period, 0,
                                     f"{sec} stops mid-turnaround: {len(heads)} bars")

    def test_the_section_length_did_not_change(self) -> None:
        """The correction is about where the chords fall, not how long the section runs."""
        for name, sections in self.levels.items():
            for sec in TURNAROUND_SECTIONS:
                with self.subTest(level=name, section=sec):
                    self.assertEqual(len(sections[sec]), 8)
            with self.subTest(level=name, section="Outro"):
                self.assertEqual(len(sections["Outro"]), 7)
            with self.subTest(level=name, section="Bridge"):
                self.assertEqual(len(sections["Bridge"]), 8)

    def test_the_outro_closes_its_turnaround_then_sits_on_the_tonic(self) -> None:
        for name, sections in self.levels.items():
            with self.subTest(level=name):
                rows = bars(sections["Outro"])
                self.assertEqual(len(rows[3]), 2, "the Outro turnaround shares its fourth bar")
                tails = {primary_chord(t) for t in sections["Outro"][4:]}
                self.assertEqual(len(tails), 1, f"the fade should hold one chord: {tails}")
                self.assertTrue(next(iter(tails)).startswith("Db"), tails)

    def test_the_bridge_is_left_as_it_was(self) -> None:
        """One chord to a bar there, and nothing measured says otherwise."""
        for name, sections in self.levels.items():
            with self.subTest(level=name):
                self.assertTrue(all(len(b) == 1 for b in bars(sections["Bridge"])))

    def test_no_section_lost_a_beat(self) -> None:
        for name, sections in self.levels.items():
            for sec, chart in sections.items():
                with self.subTest(level=name, section=sec):
                    total = sum(w for bar in bars(chart) for _, w in bar)
                    self.assertEqual(total, 4.0 * len(chart))


class TheKeyAndFormAreUntouched(unittest.TestCase):
    def test_the_song_is_still_in_db(self) -> None:
        self.assertEqual(str(entry().get("key") or ""), "Db")

    def test_the_section_order_is_untouched(self) -> None:
        self.assertEqual(
            list((entry().get("sections") or {}).keys()),
            ["Intro / Groove", "Verse", "Chorus", "Bridge", "Solo", "Outro"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
