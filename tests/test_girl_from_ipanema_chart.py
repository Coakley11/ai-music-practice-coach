"""The Girl from Ipanema: the complete 40-bar form, and a 16-bar bridge.

The chart was 24 bars - a 4-bar intro, ONE 8-bar A, an 8-bar "B Section" and a
4-bar "Final A / Outro" - and all three levels were equally short, so there was
no complete Advanced form anywhere. The shortening was also undocumented:
``arrangement_notes`` was empty and ``chart_confidence`` unset, so nothing said
it was deliberate.

**What was missing.** The bridge is sixteen bars. The old one had bars 17-21
right (Gbmaj7 x2, B7 x2, F#m7) and then collapsed: it put B7 where the second
F#m7 belongs and jumped straight to Gm7-C7, a ii-V back to F. Absent entirely
were

* the **D7 pair** (bars 23-24) that turns F#m7 toward G minor,
* the **second Gm7** (bar 26),
* the **Eb7 pair** (bars 27-28), and
* the closing **Am7 - D7#5 - Gm7 - C7#5** (bars 29-32) that walks home.

So the bridge never made its journey. The reference marks the key centres
**F -> Db (bar 17) -> E (bar 21) -> F (bar 25)**; the old chart reached Db and
E but short-circuited the return. Two A sections were missing as well: the form
is A-A-Bridge-A, and the 4-bar "Final A / Outro" was a compressed stand-in for
the 8-bar A3.

**Reference**, named and used throughout: the bar-by-bar text list at
jazzchanges.app/the-girl-from-ipanema. That page carries three presentations
which disagree on spellings - its text list gives G7, Gb7, D7#5 and C7#5; its
iReal Pro chart graphic gives G7#11, Gb7#11, F#maj7 (the same pitches as
Gbmaj7) and D7b9b5 / C7b9b5; and a Learn Jazz Standards analysis it summarises
gives G7#11 / Gb7#11 and allows 7#5. **The text list is used for placement and
quality and nothing is taken from the other two** - the same single-presentation
rule applied to There Will Never Be Another You.

Nothing was duplicated to reach forty bars: every added bar is the reference's
own content. The A section was already correct - its roots and functions match
the reference bar for bar - and is untouched. A2 differs from A1 only in bar 16,
where the reference holds Fmaj7 instead of turning on Gb7.

Section names are kept, and "A2" added, because other suites address this song's
sections by name (tests/test_ami_warmup_songs.py asks for its "B Section").
"Final A / Outro" is now the complete 8-bar A3; the 4-bar ii-V-I tag it used to
end on is gone, because the reference's bar 40 is Gb7, the turnaround that makes
the chorus loop.

Advanced keeps this song's existing house style for extensions - 13ths on
dominants, 9ths on minors and majors, which its A section already used - so
placement is the reference's and voicing is the chart's own. The reference's two
named altered dominants (D7#5, C7#5) are kept as it spells them.

Tempo, meter and groove were never set for this song and are NOT filled in here.
Not checked by ear.
"""
from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from backing_audio import chord_notes
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records

TITLE, ARTIST = "The Girl from Ipanema", "Antonio Carlos Jobim"
ORDER = ["Intro", "A Section", "A2", "B Section", "Final A / Outro"]
FORM_SECTIONS = ["A Section", "A2", "B Section", "Final A / Outro"]

# the reference's bridge, bars 17-32
REF_BRIDGE = ["Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "F#m7", "D7", "D7",
              "Gm7", "Gm7", "Eb7", "Eb7", "Am7", "D7#5", "Gm7", "C7#5"]

# the chart as it was before this correction (Intermediate tier)
OLD_BRIDGE = ["Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "B7", "Gm7", "C7"]


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records()
             if r["title"] == TITLE and r["artist"] == ARTIST)
    )


def roots(cells):
    """Chord roots in order, so a comparison ignores voicing extensions."""
    out = []
    for cell in cells:
        for s in cs.parse_subdivisions(str(cell), beats_per_bar=4):
            c = s.chord.split("/")[0]
            out.append(c[:2] if len(c) > 1 and c[1] in "#b" else c[:1])
    return out


class TheFormIsFortyBars(unittest.TestCase):
    def test_the_sections_and_their_order(self) -> None:
        r = rec()
        self.assertEqual(list(r.get("section_order") or r["sections"]), ORDER)

    def test_the_form_is_eight_eight_sixteen_eight(self) -> None:
        s = rec()["sections"]
        self.assertEqual([len(s[n]) for n in FORM_SECTIONS], [8, 8, 16, 8])
        self.assertEqual(sum(len(s[n]) for n in FORM_SECTIONS), 40)

    def test_the_intro_is_a_lead_in_outside_the_form(self) -> None:
        """Four bars of ii-V vamp; the reference's 40 bars contain no intro."""
        s = rec()["sections"]
        self.assertEqual(len(s["Intro"]), 4)
        self.assertEqual(roots(s["Intro"]), ["G", "C", "G", "C"])
        self.assertIn("not part of the 40", rec()["extensions"]["arrangement_notes"])

    def test_every_level_carries_the_whole_form(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            self.assertEqual(list(secs), ORDER, level)
            self.assertEqual(sum(len(secs[n]) for n in FORM_SECTIONS), 40, level)
            self.assertEqual(sum(len(v) for v in secs.values()), 44, level)

    def test_the_shorter_levels_are_not_abridged(self) -> None:
        ext = rec()["extensions"]
        for level in ("Beginner", "Intermediate"):
            self.assertIn(level, ext.get("full_form_levels") or [], level)

    def test_the_old_twenty_four_bar_chart_is_gone(self) -> None:
        self.assertNotEqual(sum(len(v) for v in rec()["sections"].values()), 24)


class TheBridgeIsSixteenBarsAndMakesItsJourney(unittest.TestCase):
    def test_the_bridge_is_the_reference_bar_for_bar(self) -> None:
        """Checked at Advanced, which carries the reference's own qualities.

        Intermediate reduces the two altered dominants to plain D7 and C7, the
        same simplification the other corrected jazz charts use, so it is not
        the tier to compare against the source.
        """
        _v, adv = resolve_level_chart(rec(), "Advanced")
        got = list(adv["B Section"])
        self.assertEqual(roots(got), roots(REF_BRIDGE))
        # the reference's named alterations survive verbatim at Advanced
        self.assertEqual(got[13], REF_BRIDGE[13])
        self.assertEqual(got[15], REF_BRIDGE[15])

    def test_intermediate_keeps_the_placement_and_drops_the_alterations(self) -> None:
        _v, mid = resolve_level_chart(rec(), "Intermediate")
        self.assertEqual(list(mid["B Section"]),
                         ["Gbmaj7", "Gbmaj7", "B7", "B7", "F#m7", "F#m7", "D7", "D7",
                          "Gm7", "Gm7", "Eb7", "Eb7", "Am7", "D7", "Gm7", "C7"])

    def test_the_bridge_doubled_in_length(self) -> None:
        self.assertEqual(len(rec()["sections"]["B Section"]), 16)
        self.assertEqual(len(OLD_BRIDGE), 8)

    def test_the_material_that_was_missing_is_present(self) -> None:
        got = roots(rec()["sections"]["B Section"])
        # the D7 pair, the second Gm7, the Eb7 pair, and the walk home
        self.assertEqual(got[6:8], ["D", "D"], "the D7 pair is missing")
        self.assertEqual(got[8:10], ["G", "G"], "the Gm7 pair is missing")
        self.assertEqual(got[10:12], ["Eb", "Eb"], "the Eb7 pair is missing")
        self.assertEqual(got[12:], ["A", "D", "G", "C"], "the walk home is missing")

    def test_the_second_f_sharp_minor_bar_replaced_a_stray_b_seven(self) -> None:
        """The old bar 22 was B7; the reference holds F#m7 for two bars."""
        s = rec()["sections"]["B Section"]
        self.assertEqual(roots(s)[4:6], ["F#", "F#"])
        self.assertEqual(roots(OLD_BRIDGE)[4:6], ["F#", "B"])

    def test_the_bridge_no_longer_short_circuits_to_a_two_five_in_f(self) -> None:
        """The old bridge jumped to Gm7-C7 at bars 23-24; those are D7 D7 now."""
        self.assertEqual(roots(rec()["sections"]["B Section"])[6:8], ["D", "D"])
        self.assertEqual(roots(OLD_BRIDGE)[6:8], ["G", "C"])

    def test_it_passes_through_the_documented_key_centres(self) -> None:
        """F -> Db (bar 17) -> E (bar 21) -> F (bar 25)."""
        got = roots(rec()["sections"]["B Section"])
        self.assertEqual(got[0], "Gb", "bar 17 opens the Db area on its IV")
        self.assertEqual(got[4], "F#", "bar 21 is the ii of E")
        self.assertEqual(got[2], "B", "B7 is the V of E")
        self.assertEqual(got[8], "G", "bar 25 returns toward F on its ii")
        self.assertEqual(got[-1], "C", "and ends on the V of F")

    def test_nothing_was_duplicated_to_pad_the_length(self) -> None:
        """A padded bridge would be the old eight bars twice."""
        s = [str(c) for c in rec()["sections"]["B Section"]]
        self.assertNotEqual(s[:8], s[8:])


class TheASectionWasAlreadyRightAndIsUntouched(unittest.TestCase):
    def test_the_a_section_roots_match_the_reference(self) -> None:
        _v, mid = resolve_level_chart(rec(), "Intermediate")
        self.assertEqual(list(mid["A Section"]),
                         ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"])

    def test_a2_differs_from_a1_only_in_its_last_bar(self) -> None:
        s = rec()["sections"]
        self.assertEqual(s["A Section"][:7], s["A2"][:7])
        self.assertNotEqual(s["A Section"][7], s["A2"][7])
        self.assertEqual(roots([s["A2"][7]]), ["F"], "A2 holds the tonic")
        self.assertEqual(roots([s["A Section"][7]]), ["Gb"], "A1 turns on Gb7")

    def test_the_final_a_is_the_complete_eight_bar_a3(self) -> None:
        s = rec()["sections"]
        self.assertEqual(len(s["Final A / Outro"]), 8)
        self.assertEqual(list(s["Final A / Outro"]), list(s["A Section"]))

    def test_the_last_form_bar_is_the_turnaround_that_loops(self) -> None:
        self.assertEqual(roots([rec()["sections"]["Final A / Outro"][-1]]), ["Gb"])


class OnePresentationOfOneReference(unittest.TestCase):
    def test_nothing_from_the_ireal_graphic_or_the_analysis_leaked_in(self) -> None:
        flat = " ".join(str(c) for v in rec()["sections"].values() for c in v)
        for other in ("G7#11", "Gb7#11", "F#maj7", "D7b9b5", "C7b9b5", "Cb7"):
            self.assertNotIn(other, flat, f"{other} comes from another presentation")

    def test_the_text_lists_altered_dominants_are_kept_at_advanced(self) -> None:
        _v, adv = resolve_level_chart(rec(), "Advanced")
        self.assertEqual(adv["B Section"][13], "D7#5")
        self.assertEqual(adv["B Section"][15], "C7#5")

    def test_the_notes_name_the_reference_and_the_disagreement(self) -> None:
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("jazzchanges.app", notes)
        self.assertIn("FORM CORRECTED", notes)
        self.assertIn("40-bar", notes)
        self.assertIn("nothing is taken from the other two", notes)


class TheLevelsDifferOnlyInChordQuality(unittest.TestCase):
    def test_all_three_levels_share_the_bar_counts(self) -> None:
        counts = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            counts[level] = {n: len(c) for n, c in secs.items()}
        self.assertEqual(counts["Beginner"], counts["Advanced"])
        self.assertEqual(counts["Intermediate"], counts["Advanced"])

    def test_all_three_levels_share_the_chord_roots(self) -> None:
        per = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            per[level] = [r for n in ORDER for r in roots(secs[n])]
        self.assertEqual(per["Beginner"], per["Advanced"])
        self.assertEqual(per["Intermediate"], per["Advanced"])

    def test_beginner_drops_the_sevenths_and_alterations(self) -> None:
        beg = (rec()["chart_versions"] or {})["Beginner"]
        self.assertEqual(beg["A Section"],
                         ["F", "F", "G7", "G7", "Gm", "Gb7", "F", "Gb7"])
        flat = " ".join(c for v in beg.values() for c in v)
        for gone in ("maj7", "maj9", "#5", "13"):
            self.assertNotIn(gone, flat, f"Beginner still carries {gone}")


class EverythingPlays(unittest.TestCase):
    def test_every_bar_fills_the_meter_at_every_level(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                ev = section_chord_list_to_events(name, cells, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

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

    def test_no_push_or_split_bar_was_introduced(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                for cell in cells:
                    subs = cs.parse_subdivisions(str(cell), beats_per_bar=4)
                    self.assertEqual(len(subs), 1, f"{level} {name}: {cell!r}")
                    self.assertFalse(subs[0].push, f"{level} {name}: {cell!r}")


class OtherSuitesStillFindTheirSections(unittest.TestCase):
    def test_the_b_section_is_still_called_b_section(self) -> None:
        """tests/test_ami_warmup_songs.py addresses this song's B Section."""
        self.assertIn("B Section", rec()["sections"])

    def test_the_original_section_names_all_survive(self) -> None:
        s = rec()["sections"]
        for name in ("Intro", "A Section", "B Section", "Final A / Outro"):
            self.assertIn(name, s, f"{name} was renamed")


class SavedChartsAreProtected(unittest.TestCase):
    def _old(self):
        return {
            "Intro": ["Gm7", "C7", "Gm7", "C7"],
            "A Section": ["Fmaj7", "Fmaj7", "G7", "G7", "Gm7", "Gb7", "Fmaj7", "Gb7"],
            "B Section": list(OLD_BRIDGE),
            "Final A / Outro": ["Gm7", "C7", "Fmaj7", "Fmaj7"],
        }

    def test_the_old_grid_is_a_known_prior_revision(self) -> None:
        from songs.chart_provenance import chart_fingerprint
        from songs.chart_revision_table import PRIOR_REVISIONS
        fp = chart_fingerprint(self._old())
        known = {e[0] if isinstance(e, (list, tuple)) else e
                 for v in PRIOR_REVISIONS.values() for e in v}
        self.assertIn(fp, known, "a saved copy of the old chart could not refresh")

    def test_an_unedited_saved_copy_refreshes(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": pick,
                "key": new["key"], "sections": self._old()}
        frozen = copy.deepcopy(snap)
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=pick)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=pick)
        self.assertEqual(out["sections"], new["sections"])
        self.assertEqual(out["key"], "F")
        self.assertEqual(snap, frozen, "the stored copy must not be mutated")

    def test_a_user_edited_copy_is_kept(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        edited = self._old()
        edited["A Section"] = ["Fmaj7"] * 8
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": pick,
                "key": new["key"], "sections": edited}
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=pick)[0], cp.KEEP)
        out = cp.reconcile_snapshot(snap, new, pick_key=pick)
        self.assertEqual(out["sections"]["A Section"], ["Fmaj7"] * 8)

    def test_healing_a_session_leaves_the_practice_key_alone(self) -> None:
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}\x1f{ARTIST}"
        session = {"selected_song": {"title": TITLE, "artist": ARTIST,
                                     "pick_key": pick, "key": new["key"],
                                     "sections": self._old()},
                   "display_key": "Db", "concert_key": "Db"}
        cp.heal_session_chart_copies(session, new, pick, where="test")
        self.assertEqual((session["display_key"], session["concert_key"]),
                         ("Db", "Db"))


class WhatIsStillNotEstablished(unittest.TestCase):
    def test_tempo_meter_and_groove_are_left_unset(self) -> None:
        ext = rec()["extensions"]
        for field in ("default_bpm", "time_signature", "default_groove"):
            self.assertIsNone(ext.get(field), f"{field} was filled in")
        self.assertIn("Tempo, meter and groove remain unset", ext["arrangement_notes"])


if __name__ == "__main__":
    unittest.main()
