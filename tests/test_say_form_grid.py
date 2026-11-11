"""Say: two chords to a bar, not one - the chart was a half-bar grid.

The chart used to spend four bars on the B flat - E flat - Gm - F loop, so every
verse, chorus and turnaround was twice its played length. One pass ran 156 bars
= 7:36 at 82 BPM against a 3:49 single; with the app's default two loops, over
fifteen minutes.

The record puts two chords in a bar. The lyric-and-chord sheet this song is
charted from writes the verse as ``|Bb Eb | Gm F |`` repeated 4x and labels it
an **8-bar verse** - a two-bar loop, four passes, not a four-bar loop. Regridded
to that, one pass is 78 bars = 3:48.3 against the 3:49 single.

Tempo is NOT the problem and is unchanged: the Musicnotes edition prints a
metronome mark of 82 and Hooktheory reads 89, so nothing supports the ~164 a
double-time misreading would need. The key (B flat), the capo-3 G shapes, the
chord identities and the written pushes are all unchanged too - the pushes are
simply re-expressed on the halved grid, where an eighth before the slot is now
an eighth before the middle of the bar instead of before the next downbeat.

Two things this file pins beyond the arithmetic:

  * **No harmony was deleted.** The run-length-collapsed chord sequence is
    identical to the old chart's. A chart cut in half to hit a stopwatch would
    lose half its chords; this one loses none.
  * **Beginner now carries the same bar counts as the other tiers.** It used to
    play a single loop pass per section against Intermediate's four, so
    switching level changed the song's form rather than its difficulty. Beginner
    keeps the real grid and drops only the pushes and the added colours.

Section repeat counts beyond the verse and chorus the sheet labels are still not
source-verified, and nothing here is checked by ear.
"""
from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

TITLE, ARTIST = "Say", "John Mayer"
BPM = 82
BARS = {"Intro": 8, "Verse 1": 8, "Chorus 1": 8, "Turnaround 1": 2, "Verse 2": 8,
        "Chorus 2": 8, "Turnaround 2": 2, "Bridge": 8, "Turnaround 3": 2,
        "Verse 3": 8, "Final Chorus": 16}

# the chart as it was BEFORE this correction
_OLD_MAIN = ["Bb:3.5|Eb:0.5p", "Eb:4", "Gm:3.5|F:0.5p", "F:4"]
_OLD_BRIDGE = (["Cm:4", "Cm:4", "Eb:3.5|F:0.5p", "F:4"] * 3
               + ["Eb:4", "Eb:4", "Eb:3.5|F:0.5p", "F:4"])
_OLD_FINAL = ["Gm:3.5|Bb:0.5p", "Bb:4", "Eb7:4", "Eb7:4"] * 8
_OLD_INTRO = ["Bb", "Bb", "Bbsus4", "Bbsus4", "Bb", "Bb", "Bbsus4/C", "Bbsus4/C"] * 2
_OLD = {
    "Intro": list(_OLD_INTRO), "Verse 1": _OLD_MAIN * 4, "Chorus 1": _OLD_MAIN * 4,
    "Turnaround 1": list(_OLD_MAIN), "Verse 2": _OLD_MAIN * 4, "Chorus 2": _OLD_MAIN * 4,
    "Turnaround 2": list(_OLD_MAIN), "Bridge": list(_OLD_BRIDGE),
    "Turnaround 3": list(_OLD_MAIN), "Verse 3": _OLD_MAIN * 4,
    "Final Chorus": list(_OLD_FINAL),
}


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST)
    )


def chords_of(cells):
    return [s.chord for cell in cells
            for s in cs.parse_subdivisions(str(cell), beats_per_bar=4)]


def collapse(seq):
    out = []
    for c in seq:
        if not out or out[-1] != c:
            out.append(c)
    return out


class TheGridMatchesTheRecording(unittest.TestCase):
    def test_section_bar_counts(self):
        self.assertEqual({n: len(c) for n, c in rec()["sections"].items()}, BARS)

    def test_one_pass_is_three_forty_eight_not_seven_thirty_six(self):
        _v, adv = resolve_level_chart(rec(), "Advanced")
        bars = sum(len(v) for v in adv.values())
        self.assertEqual(bars, 78)
        secs = bars * meter_timing(BPM, "4/4").bar_sec
        self.assertAlmostEqual(secs, 228.29, places=1)      # 3:48.3
        self.assertLess(abs(secs - 229.0), 5.0)             # the 3:49 single
        # the defect, for the record
        self.assertAlmostEqual(156 * meter_timing(BPM, "4/4").bar_sec, 456.59, places=1)

    def test_the_main_loop_is_two_bars_of_two_chords(self):
        secs = rec()["sections"]
        self.assertEqual(secs["Verse 1"][:2], ["Bb:2|Eb:2p", "Gm:2|F:2p"])
        # the source: an 8-bar verse written as |Bb Eb | Gm F | 4x
        self.assertEqual(len(secs["Verse 1"]), 8)
        self.assertEqual(secs["Verse 1"], ["Bb:2|Eb:2p", "Gm:2|F:2p"] * 4)
        self.assertEqual(collapse(chords_of(secs["Verse 1"]))[:4], ["Bb", "Eb", "Gm", "F"])

    def test_the_verse_and_chorus_are_both_eight_bars(self):
        secs = rec()["sections"]
        for name in ("Verse 1", "Verse 2", "Verse 3", "Chorus 1", "Chorus 2"):
            self.assertEqual(len(secs[name]), 8, name)

    def test_the_intro_is_one_chord_per_bar_twice_through(self):
        intro = rec()["sections"]["Intro"]
        self.assertEqual(intro, ["Bb", "Bbsus4", "Bb", "Bbsus4/C"] * 2)
        for cell in intro:
            self.assertNotIn("|", str(cell))

    def test_the_bridge_is_eight_bars_and_keeps_its_shape(self):
        bridge = rec()["sections"]["Bridge"]
        self.assertEqual(bridge, ["Cm", "Eb:2|F:2p"] * 3 + ["Eb", "Eb:2|F:2p"])

    def test_the_final_chorus_is_sixteen_bars(self):
        fc = rec()["sections"]["Final Chorus"]
        self.assertEqual(fc, ["Gm:2|Bb:2p", "Eb7"] * 8)


class ThePushesSurvivedTheRegrid(unittest.TestCase):
    def test_the_pushed_chords_are_the_ones_the_arrangement_documents(self):
        _v, adv = resolve_level_chart(rec(), "Advanced")
        pushed = {s.chord for cells in adv.values() for cell in cells
                  for s in cs.parse_subdivisions(str(cell), beats_per_bar=4) if s.push}
        self.assertEqual(pushed, {"Eb", "F", "Bb"})

    def test_a_pushed_cell_places_its_chord_at_the_half_bar(self):
        ev = section_chord_list_to_events("Verse 1", ["Bb:2|Eb:2p"], time_signature="4/4")
        self.assertEqual(
            [(e["beat"], e["duration_beats"], e["chord"], bool(e.get("push"))) for e in ev],
            [(1.0, 2.0, "Bb", False), (3.0, 2.0, "Eb", True)],
        )

    def test_every_loop_bar_that_changes_chord_is_pushed(self):
        """The second chord of each loop bar is anticipated, as it was before."""
        _v, adv = resolve_level_chart(rec(), "Advanced")
        for name in ("Verse 1", "Chorus 1", "Turnaround 1", "Verse 3"):
            for cell in adv[name]:
                subs = cs.parse_subdivisions(str(cell), beats_per_bar=4)
                self.assertEqual(len(subs), 2, cell)
                self.assertFalse(subs[0].push, cell)
                self.assertTrue(subs[1].push, cell)

    def test_the_old_chart_was_pushed_too_so_this_is_not_a_new_feature(self):
        old = {s.chord for cells in _OLD.values() for cell in cells
               for s in cs.parse_subdivisions(str(cell), beats_per_bar=4) if s.push}
        self.assertEqual(old, {"Eb", "F", "Bb"})


class NoHarmonyWasDeleted(unittest.TestCase):
    def test_the_chord_sequence_is_unchanged_in_every_section(self):
        secs = rec()["sections"]
        for name, old_cells in _OLD.items():
            self.assertEqual(
                collapse(chords_of(secs[name])),
                collapse(chords_of(old_cells)),
                f"{name}: the harmony changed, not just the timing",
            )

    def test_no_section_was_dropped_or_added(self):
        r = rec()
        self.assertEqual(list(r.get("section_order") or r["sections"]), list(_OLD))

    def test_the_distinct_chords_are_the_same_set(self):
        now = set(chords_of([c for v in rec()["sections"].values() for c in v]))
        was = set(chords_of([c for v in _OLD.values() for c in v]))
        self.assertEqual(now, was)


class EveryLevelSharesTheGrid(unittest.TestCase):
    def test_all_three_levels_have_identical_bar_counts(self):
        counts = {}
        for level in ("Beginner", "Intermediate", "Advanced"):
            r = rec()
            counts[level] = {n: len(c) for n, c in (r["chart_versions"] or {})[level].items()}
        self.assertEqual(counts["Beginner"], counts["Intermediate"])
        self.assertEqual(counts["Intermediate"], counts["Advanced"])
        self.assertEqual(counts["Beginner"], BARS)

    def test_beginner_keeps_the_grid_but_drops_the_pushes(self):
        beg = (rec()["chart_versions"] or {})["Beginner"]
        self.assertEqual(beg["Verse 1"], ["Bb|Eb", "Gm|F"] * 4)
        for cells in beg.values():
            for cell in cells:
                for s in cs.parse_subdivisions(str(cell), beats_per_bar=4):
                    self.assertFalse(s.push, f"Beginner should carry no push: {cell!r}")

    def test_beginner_uses_the_same_chord_sequence_as_the_others(self):
        r = rec()
        beg = (r["chart_versions"] or {})["Beginner"]
        for name, cells in beg.items():
            self.assertEqual(collapse(chords_of(cells)),
                             collapse(chords_of(r["sections"][name])), name)

    def test_every_bar_fills_the_meter_at_every_level(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                ev = section_chord_list_to_events(name, cells, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

    def test_every_cell_voices_and_keeps_its_root(self):
        from backing_audio import chord_notes
        pcs = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7,
               "Ab": 8, "A": 9, "Bb": 10, "B": 11}
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


class TheMetadataIsUntouched(unittest.TestCase):
    def test_key_tempo_meter_and_capo(self):
        r = rec()
        ext = r["extensions"]
        self.assertEqual(r["key"], "Bb")
        self.assertEqual(ext["default_bpm"], 82)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertIn("Capo 3", ext["capo_note"])

    def test_the_notes_record_the_correction_and_keep_the_tempo_evidence(self):
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("BAR GRID CORRECTED", notes)
        self.assertIn("8-bar verse", notes)
        self.assertIn("82", notes)
        self.assertNotIn("chart is longer than the recording", notes)


class SavedChartsAreProtected(unittest.TestCase):
    """A stored copy of the PRE-W21 chart (right key, old grid) is the realistic
    case: anyone who opened the song between the key fix and this one has one.
    It must refresh, and a copy the user actually edited must not."""

    def _snap(self):
        from songs import chart_provenance as cp
        new = rec()
        pick = f"{TITLE}{ARTIST}"
        snap = {"title": TITLE, "artist": ARTIST, "pick_key": pick,
                "key": new["key"], "sections": copy.deepcopy(_OLD)}
        return cp, new, pick, snap

    def test_an_unedited_saved_copy_refreshes_to_the_corrected_chart(self):
        cp, new, pick, snap = self._snap()
        frozen = copy.deepcopy(snap)
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=pick)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=pick)
        self.assertEqual(out["sections"], new["sections"])
        self.assertEqual(out["key"], new["key"])
        self.assertEqual(snap, frozen, "the stored copy must not be mutated")

    def test_a_user_edited_copy_is_kept(self):
        cp, new, pick, snap = self._snap()
        first = next(iter(_OLD))
        edited = copy.deepcopy(_OLD)
        edited[first] = [edited[first][0]] * 3
        esnap = {**snap, "sections": edited}
        self.assertEqual(cp.classify_snapshot(esnap, new, pick_key=pick)[0], cp.KEEP)
        out = cp.reconcile_snapshot(esnap, new, pick_key=pick)
        self.assertEqual(out["sections"][first], edited[first])

    def test_a_user_origin_copy_is_kept(self):
        cp, new, pick, snap = self._snap()
        first = next(iter(_OLD))
        out = cp.reconcile_snapshot({**snap, "chart_origin": "user"}, new, pick_key=pick)
        self.assertEqual(out["sections"][first], _OLD[first])

    def test_healing_a_session_leaves_the_practice_key_alone(self):
        cp, new, pick, snap = self._snap()
        session = {"selected_song": copy.deepcopy(snap),
                   "display_key": "C", "concert_key": "C"}
        cp.heal_session_chart_copies(session, new, pick, where="test")
        self.assertEqual((session["display_key"], session["concert_key"]), ("C", "C"))

    def test_the_old_grid_is_a_known_prior_revision(self):
        """Without the revision-table entry the refresh above cannot happen."""
        from songs.chart_revision_table import PRIOR_REVISIONS
        from songs.chart_provenance import chart_fingerprint
        fp = chart_fingerprint(_OLD)  # takes the sections map directly
        known = {e[0] if isinstance(e, (list, tuple)) else e
                 for v in PRIOR_REVISIONS.values() for e in v}
        self.assertIn(fp, known, "the pre-W21 grid is not in the revision table")


if __name__ == "__main__":
    unittest.main()
