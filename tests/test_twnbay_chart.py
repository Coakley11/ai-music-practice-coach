"""There Will Never Be Another You: the 32-bar ABAC form, and the right A section.

The old chart was 16 bars in two 8-bar halves, and its "A Section" ran

    Ebmaj7 | Cm7 | Fm7 | Bb7 | Gm7 | C7 | Fm7 | Bb7

which is a I-vi-ii-V turnaround. That progression belongs to no part of this
tune. The real A section holds the **tonic for two bars**, then goes to
**Dm7b5 - G7**, the ii7b5-V of the relative minor, in bars 3-4, then Cm7 for two
bars and Bbm7 - Eb7 into the IV. So the opening harmony was wrong, not merely
simplified - and the form is 32-bar ABAC, which a 16-bar chart cannot state.

Reference arrangement, named and kept consistent: the iReal Pro chart catalogued
at jazzchanges.app/there-will-never-be-another-you, which that page derives from
Chet Baker's 1954 opening chorus (Weimar Jazz Database), moved from the record's
F to Eb. It is deliberately not blended with fake-book variants, which that page
notes differ in the last four bars.

B and C both open Abmaj7 - Db7#11 - Ebmaj7. They part company at bar 28, where C
doubles to **two chords a bar** for the final cadence; that is what makes C a C
and not a second B, so those split bars are the substance of the section rather
than decoration.

Source consistency. The reference page renders that one iReal chart **two
ways**, and the two renderings disagree: the chart graphic gives **G7b9** in
bars 4 and 20 and **Db7#11** in bars 10 and 26, while its bar-by-bar text list
gives G7 and Db9#11 in the same places. The **chart graphic is used
throughout**, which keeps the two A sections identical - as that page states
they are.

An earlier draft of this chart had G7b9 in bar 4 and plain G7 in bar 20, from
reading that disagreement as an asymmetry *within* the arrangement. It is not:
both renderings give the same changes for bars 1-8 and 17-24. That mixture is
corrected here, and the tests below pin that the two A sections match.

The Chet Baker transcription the page names supplies its harmonic basis but
**no chord labels of its own**, so it is not a second source for these chords
and nothing is taken from it.

Tempo and groove remain unset and are NOT established here. No melody is
reproduced and nothing is checked by ear.
"""
from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from backing_audio import chord_notes
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

TITLE, ARTIST = "There Will Never Be Another You", "Harry Warren"
SECTIONS = ["A1", "B", "A2", "C"]

# the reference, bar by bar
REF = {
    "A1": ["Ebmaj7", "Ebmaj7", "Dm7b5", "G7b9", "Cm7", "Cm7", "Bbm7", "Eb7"],
    "B": ["Abmaj7", "Db7#11", "Ebmaj7", "Cm7", "F7", "F7", "Fm7", "Bb7"],
    "A2": ["Ebmaj7", "Ebmaj7", "Dm7b5", "G7b9", "Cm7", "Cm7", "Bbm7", "Eb7"],
    "C": ["Abmaj7", "Db7#11", "Ebmaj7", "Am7b5|D7",
          "Ebmaj7|Ab7", "Gm7|C7", "Fm7|Bb7", "Eb6|Bb7"],
}

# the chart as it was before this correction
OLD = {
    "A Section": ["Ebmaj7", "Cm7", "Fm7", "Bb7", "Gm7", "C7", "Fm7", "Bb7"],
    "B Section": ["Ebmaj7", "Abmaj7", "Dm7b5", "G7", "Cm7", "F7", "Fm7", "Bb7"],
}


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records()
             if r["title"] == TITLE and r["artist"] == ARTIST)
    )


def chords_of(cells):
    return [s.chord for cell in cells
            for s in cs.parse_subdivisions(str(cell), beats_per_bar=4)]


class TheFormIsThirtyTwoBarABAC(unittest.TestCase):
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

    def test_the_shorter_levels_are_not_abridged_by_dropping_a_section(self) -> None:
        """full_form_levels guards this: B and C differ only at the cadence, so
        dropping either loses what makes the form ABAC."""
        ext = rec()["extensions"]
        for level in ("Beginner", "Intermediate"):
            self.assertIn(level, ext.get("full_form_levels") or [], level)

    def test_the_old_sixteen_bar_chart_is_gone(self) -> None:
        r = rec()
        self.assertNotIn("A Section", r["sections"])
        self.assertNotIn("B Section", r["sections"])
        self.assertNotEqual(sum(len(v) for v in r["sections"].values()), 16)

    def test_the_key_is_e_flat(self) -> None:
        self.assertEqual(rec()["key"], "Eb")


class TheASectionIsNoLongerATurnaround(unittest.TestCase):
    def test_the_tonic_is_held_for_two_bars(self) -> None:
        a = rec()["sections"]["A1"]
        self.assertEqual(a[0], "Ebmaj7")
        self.assertEqual(a[1], "Ebmaj7", "bar 2 should still be the tonic")

    def test_bars_three_and_four_are_the_two_five_of_the_relative_minor(self) -> None:
        a = rec()["sections"]["A1"]
        self.assertEqual(a[2], "Dm7b5")
        self.assertTrue(a[3].startswith("G7"), f"bar 4 is {a[3]!r}")

    def test_the_old_one_six_two_five_opening_is_gone(self) -> None:
        for name in ("A1", "A2"):
            a = rec()["sections"][name]
            self.assertNotEqual(a[:4], OLD["A Section"][:4], name)
            self.assertNotEqual(a[1], "Cm7", f"{name} bar 2 is the old vi")

    def test_the_a_section_closes_into_the_four_chord(self) -> None:
        for name in ("A1", "A2"):
            a = rec()["sections"][name]
            self.assertEqual(a[6], "Bbm7", name)
            self.assertEqual(a[7], "Eb7", name)


class TheChartMatchesTheReference(unittest.TestCase):
    def test_advanced_is_the_reference_bar_for_bar(self) -> None:
        _v, adv = resolve_level_chart(rec(), "Advanced")
        self.assertEqual({k: list(v) for k, v in adv.items()}, REF)

    def test_b_and_c_share_an_opening(self) -> None:
        s = rec()["sections"]
        self.assertEqual(s["B"][:3], s["C"][:3])
        self.assertEqual(s["B"][:3], ["Abmaj7", "Db7#11", "Ebmaj7"])

    def test_the_c_section_doubles_its_harmonic_rhythm_at_bar_twenty_eight(self) -> None:
        c = rec()["sections"]["C"]
        for i in range(3):
            self.assertNotIn("|", str(c[i]), f"C bar {i + 1}")
        for i in range(3, 8):
            self.assertIn("|", str(c[i]), f"C bar {i + 1} should carry two chords")

    def test_one_presentation_of_one_reference_is_used_throughout(self) -> None:
        """The chart graphic's labels, not a mixture with its text list.

        Replaces test_the_sources_two_inconsistencies_are_followed_not_smoothed,
        which asserted G7b9 in bar 4 and plain G7 in bar 20. That was a
        misreading: the disagreement is between two renderings of the same iReal
        chart, not between its two A sections.
        """
        s = rec()["sections"]
        # the chart graphic: G7b9 in both A sections, Db7#11 in both B and C
        self.assertEqual(s["A1"][3], "G7b9")
        self.assertEqual(s["A2"][3], "G7b9")
        self.assertEqual(s["B"][1], "Db7#11")
        self.assertEqual(s["C"][1], "Db7#11")
        # and nothing from the text list's rendering leaked in
        flat = " ".join(c for v in s.values() for c in v)
        self.assertNotIn("Db9#11", flat)

    def test_the_two_a_sections_are_identical(self) -> None:
        """The reference states they are the same, so no bar may differ."""
        s = rec()["sections"]
        self.assertEqual(list(s["A1"]), list(s["A2"]))

    def test_the_two_a_sections_are_identical_at_every_level(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            self.assertEqual(list(secs["A1"]), list(secs["A2"]), level)


class TheLevelsSimplifyQualitiesNotForm(unittest.TestCase):
    def test_all_three_levels_have_the_same_bar_counts(self) -> None:
        counts = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            counts[level] = {n: len(c) for n, c in secs.items()}
        self.assertEqual(counts["Beginner"], counts["Advanced"])
        self.assertEqual(counts["Intermediate"], counts["Advanced"])

    def test_every_level_keeps_every_chord_change(self) -> None:
        """Same number of sounding chords per bar at every level."""
        per_level = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            per_level[level] = [len(cs.parse_subdivisions(str(c), beats_per_bar=4))
                                for n in SECTIONS for c in secs[n]]
        self.assertEqual(per_level["Beginner"], per_level["Advanced"])
        self.assertEqual(per_level["Intermediate"], per_level["Advanced"])

    def test_beginner_drops_the_alterations_and_the_sevenths(self) -> None:
        beg = (rec()["chart_versions"] or {})["Beginner"]
        self.assertEqual(beg["A1"], ["Eb", "Eb", "Dm", "G7",
                                     "Cm", "Cm", "Bbm", "Eb7"])
        flat = " ".join(c for v in beg.values() for c in v)
        for gone in ("maj7", "b9", "#11", "m7b5"):
            self.assertNotIn(gone, flat, f"Beginner still carries {gone}")

    def test_intermediate_keeps_the_sevenths_but_not_the_alterations(self) -> None:
        mid = (rec()["chart_versions"] or {})["Intermediate"]
        self.assertEqual(mid["A1"][3], "G7")
        self.assertEqual(mid["B"][1], "Db7")
        self.assertEqual(mid["A1"][2], "Dm7b5", "the half-diminished is structural")
        flat = " ".join(c for v in mid.values() for c in v)
        for gone in ("b9", "#11"):
            self.assertNotIn(gone, flat)


class EverythingPlays(unittest.TestCase):
    def test_every_bar_fills_the_meter_at_every_level(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                ev = section_chord_list_to_events(name, cells, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

    def test_a_split_bar_divides_evenly_and_carries_no_push(self) -> None:
        ev = section_chord_list_to_events("C", ["Am7b5|D7"], time_signature="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"], e["chord"]) for e in ev],
                         [(1.0, 2.0, "Am7b5"), (3.0, 2.0, "D7")])
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for cells in secs.values():
                for cell in cells:
                    for s in cs.parse_subdivisions(str(cell), beats_per_bar=4):
                        self.assertFalse(s.push, f"{level}: unexpected push in {cell!r}")

    def test_every_cell_voices_and_keeps_its_root(self) -> None:
        pcs = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6,
               "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                for cell in cells:
                    for s in cs.parse_subdivisions(str(cell), beats_per_bar=4):
                        notes = chord_notes(s.chord)
                        self.assertTrue(notes, f"{level} {name}: {s.chord!r}")
                        root = s.chord.split("/")[0]
                        root = root[:2] if len(root) > 1 and root[1] in "#b" else root[:1]
                        if root in pcs:
                            self.assertIn(pcs[root] % 12, {n % 12 for n in notes},
                                          f"{level} {name}: {s.chord!r} lost its root")

    def test_the_last_bar_leads_back_to_the_first(self) -> None:
        """Eb6|Bb7 - the tonic then its dominant, which is how a chorus turns."""
        s = rec()["sections"]
        self.assertEqual(s["C"][-1], "Eb6|Bb7")
        self.assertEqual(chords_of([s["C"][-1]])[-1], "Bb7")
        self.assertEqual(s["A1"][0], "Ebmaj7")


class SavedChartsAreProtected(unittest.TestCase):
    def test_the_old_sixteen_bar_grid_is_a_known_prior_revision(self) -> None:
        from songs.chart_provenance import chart_fingerprint
        from songs.chart_revision_table import PRIOR_REVISIONS
        fp = chart_fingerprint(OLD)
        known = {e[0] if isinstance(e, (list, tuple)) else e
                 for v in PRIOR_REVISIONS.values() for e in v}
        self.assertIn(fp, known, "a saved copy of the old chart could not refresh")

    def test_an_unedited_saved_copy_refreshes(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": pick,
                "key": new["key"], "sections": copy.deepcopy(OLD)}
        frozen = copy.deepcopy(snap)
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=pick)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=pick)
        self.assertEqual(out["sections"], new["sections"])
        self.assertEqual(snap, frozen, "the stored copy must not be mutated")

    def test_a_user_edited_copy_is_kept(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        edited = copy.deepcopy(OLD)
        edited["A Section"] = ["Ebmaj7"] * 8
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": pick,
                "key": new["key"], "sections": edited}
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=pick)[0], cp.KEEP)
        out = cp.reconcile_snapshot(snap, new, pick_key=pick)
        self.assertEqual(out["sections"]["A Section"], ["Ebmaj7"] * 8)

    def test_healing_a_session_leaves_the_practice_key_alone(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        session = {"selected_song": {"title": TITLE, "artist": ARTIST,
                                     "pick_key": pick, "key": new["key"],
                                     "sections": copy.deepcopy(OLD)},
                   "display_key": "C", "concert_key": "C"}
        cp.heal_session_chart_copies(session, new, pick, where="test")
        self.assertEqual((session["display_key"], session["concert_key"]), ("C", "C"))


class WhatIsStillNotEstablished(unittest.TestCase):
    def test_tempo_and_groove_are_left_unset_and_said_to_be(self) -> None:
        """They were never set, and this correction did not invent them."""
        ext = rec()["extensions"]
        self.assertIsNone(ext.get("default_bpm"))
        self.assertIsNone(ext.get("default_groove"))
        self.assertIn("Tempo and groove are still unset",
                      ext["arrangement_notes"])

    def test_the_notes_name_the_reference_and_the_correction(self) -> None:
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("jazzchanges.app", notes)
        self.assertIn("HARMONY CORRECTED", notes)
        self.assertIn("32-bar ABAC", notes)

    def test_the_notes_state_which_presentation_was_used(self) -> None:
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("SOURCE CONSISTENCY", notes)
        self.assertIn("chart graphic is used throughout", notes)
        self.assertIn("no chord labels of its own", notes)


if __name__ == "__main__":
    unittest.main()
