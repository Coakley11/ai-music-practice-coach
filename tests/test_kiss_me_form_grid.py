"""Kiss Me: the bar grid is the recording's, not a half-bar grid.

The chart used to be written at HALF-bar granularity. Every cell was half a
played bar, so each section came out twice as long as it is played: Advanced ran
176 bars = 7:02 at 100 BPM against a 3:30 album version (3:19 radio). With the
app's default two loops that was fourteen minutes of Kiss Me.

Reference arrangement, named and kept consistent: the bar-formatted chord chart
at bellandcomusic.com/kiss-me.html. It is written in capo-3 C shapes and gives

  * the intro as **four bars, one chord each**, inside repeat signs
    (``C | Cmaj7 | C7 | Cmaj7``), where we had eight; and
  * the instrumental as its eight chorus chords across **four bars** - two
    chords to a bar - where we had eight bars.

So the cycle is one chord per bar and the chorus is two chords per bar. Regridded
to that, Advanced is 88 bars = 3:31.2, against the 3:30 album version.

Nothing was deleted to shorten anything, which is what this file mainly pins:
the run-length-collapsed chord sequence is **identical** to the old chart's at
every level. The repeated pairs in the cycle became one bar each; the differing
pairs in the chorus became within-bar changes. That distinction matters - a
chart cut in half would lose half its chords, and this one loses none.

Its chorus and ours still differ on a few chord identities (the reference prints
Em and Am7/G where we hold D/C# and D/A). That is a separate question and is
deliberately NOT touched here; this correction is to the bar grid only.

Tempo (100), meter, key (Eb) and the capo metadata are untouched. The sections
Beginner and Intermediate omit are unchanged - see test_beginner_form_guard.
Not checked by ear.
"""
from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from chart_level_arrangement import resolve_level_chart
from chord_events import section_chord_list_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from songs.meter import meter_timing

TITLE, ARTIST = "Kiss Me", "Sixpence None the Richer"
BPM = 100
BARS = {"Intro": 8, "Verse 1": 8, "Chorus 1": 9, "Interlude": 8, "Verse 2": 8,
        "Chorus 2": 9, "Harmonica / Accordion": 8, "Guitar Section": 4,
        "Chorus 3": 9, "Outro": 17}

# --- the chart as it was BEFORE this correction, in concert Eb ---
_OLD_CYCLE = ["Eb", "Eb", "Ebmaj7", "Ebmaj7", "Eb7", "Eb7", "Ebmaj7", "Ebmaj7"]
_OLD_VERSE = ["Eb", "Eb", "Ebmaj7", "Ebmaj7", "Eb7", "Eb7", "Ebmaj7", "Ebmaj7",
              "Eb", "Eb", "Ebmaj7", "Ebmaj7", "Eb7", "Eb7", "Ab", "Ab"]
_OLD_CHORUS = ["Fm", "Bb", "Eb", "Cm", "Fm", "Bb", "Eb", "Eb7", "Fm", "Bb",
               "Eb", "Eb/D", "Cm7", "Eb/Bb", "Abmaj7", "Abmaj7", "Bbsus4", "Bb"]
_OLD_GUITAR = ["Fm", "Bb", "Eb", "Cm", "Fm", "Bb", "Eb", "Eb7"]
_OLD = {
    "Intro": _OLD_CYCLE * 2, "Verse 1": list(_OLD_VERSE), "Chorus 1": list(_OLD_CHORUS),
    "Interlude": _OLD_CYCLE * 2, "Verse 2": list(_OLD_VERSE), "Chorus 2": list(_OLD_CHORUS),
    "Harmonica / Accordion": _OLD_CYCLE * 2, "Guitar Section": list(_OLD_GUITAR),
    "Chorus 3": list(_OLD_CHORUS), "Outro": _OLD_CYCLE * 4 + ["Eb", "Eb"],
}


def rec():
    return copy.deepcopy(
        next(r for r in curated_song_records() if r["title"] == TITLE and r["artist"] == ARTIST)
    )


def chords_of(cells):
    """Flatten cells to the chord sequence they sound, splits expanded."""
    return [s.chord for cell in cells
            for s in cs.parse_subdivisions(str(cell), beats_per_bar=4)]


def collapse(seq):
    """Drop consecutive repeats: the harmony, independent of how long each lasts."""
    out = []
    for c in seq:
        if not out or out[-1] != c:
            out.append(c)
    return out


def _simplify(level, cells):
    """Map the old concert-Eb cells through the level's chord substitutions."""
    if level == "Advanced":
        m = {"Eb": "Ebadd9", "Ebmaj7": "Ebmaj9", "Eb7": "Eb9", "Eb/D": "Ebmaj7/D",
             "Eb/Bb": "Ebadd9/Bb", "Ab": "Abadd9", "Abmaj7": "Abmaj9", "Fm": "Fm9",
             "Cm": "Cm9", "Cm7": "Cm9", "Bb": "Bbsus2", "Bbsus4": "Bb7sus4"}
    elif level == "Beginner":
        m = {"Ebmaj7": "Eb", "Eb7": "Eb", "Eb/D": "Eb", "Eb/Bb": "Eb",
             "Cm7": "Cm", "Abmaj7": "Ab", "Bbsus4": "Bb"}
    else:
        m = {}
    return [m.get(c, c) for c in cells]


class TheGridMatchesTheRecording(unittest.TestCase):
    def test_section_bar_counts(self):
        self.assertEqual({n: len(c) for n, c in rec()["sections"].items()}, BARS)

    def test_one_pass_is_three_and_a_half_minutes_not_seven(self):
        _v, adv = resolve_level_chart(rec(), "Advanced")
        bars = sum(len(v) for v in adv.values())
        self.assertEqual(bars, 88)
        secs = bars * meter_timing(BPM, "4/4").bar_sec
        self.assertAlmostEqual(secs, 211.2, places=3)       # 3:31.2
        self.assertLess(abs(secs - 210.0), 5.0)             # the 3:30 album version
        # the defect, for the record: the old 176 bars ran 7:02
        self.assertAlmostEqual(176 * meter_timing(BPM, "4/4").bar_sec, 422.4, places=3)

    def test_the_cycle_is_one_chord_per_bar(self):
        secs = rec()["sections"]
        self.assertEqual(secs["Intro"][:4], ["Eb", "Ebmaj7", "Eb7", "Ebmaj7"])
        for name in ("Intro", "Interlude", "Harmonica / Accordion"):
            for cell in secs[name]:
                self.assertNotIn("|", str(cell), f"{name}: {cell!r} should be one chord")

    def test_the_chorus_and_instrumental_are_two_chords_per_bar(self):
        secs = rec()["sections"]
        self.assertEqual(secs["Chorus 1"][:3], ["Fm|Bb", "Eb|Cm", "Fm|Bb"])
        # the reference prints the instrumental's eight chords across four bars
        self.assertEqual(secs["Guitar Section"], ["Fm|Bb", "Eb|Cm", "Fm|Bb", "Eb|Eb7"])
        self.assertEqual(len(chords_of(secs["Guitar Section"])), 8)
        # Abmaj7 is the one whole-bar chord in the chorus
        self.assertEqual(secs["Chorus 1"][7], "Abmaj7")

    def test_the_outro_keeps_four_cycles_and_a_final_bar(self):
        outro = rec()["sections"]["Outro"]
        self.assertEqual(len(outro), 17)
        self.assertEqual(outro[:4], ["Eb", "Ebmaj7", "Eb7", "Ebmaj7"])
        self.assertEqual(outro[-1], "Eb")


class NoHarmonyWasDeleted(unittest.TestCase):
    """The point of the correction: durations changed, chords did not."""

    def test_the_chord_sequence_is_unchanged_at_every_level(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                self.assertEqual(
                    collapse(chords_of(cells)),
                    collapse(_simplify(level, _OLD[name])),
                    f"{level} {name}: the harmony changed, not just the timing",
                )

    def test_no_section_was_dropped_or_added(self):
        r = rec()
        self.assertEqual(list(r.get("section_order") or r["sections"]), list(_OLD))

    def test_the_chorus_still_contains_every_chord_it_did(self):
        got = chords_of(rec()["sections"]["Chorus 1"])
        self.assertEqual(collapse(got), collapse(_OLD_CHORUS))


class EverythingStillPlays(unittest.TestCase):
    def test_every_bar_fills_the_meter_at_every_level(self):
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for name, cells in secs.items():
                ev = section_chord_list_to_events(name, cells, time_signature="4/4")
                self.assertEqual(validate_chord_events(ev, time_signature="4/4"), [],
                                 f"{level} {name}")

    def test_a_split_bar_divides_it_evenly_and_carries_no_push(self):
        ev = section_chord_list_to_events("Chorus 1", ["Fm|Bb"], time_signature="4/4")
        self.assertEqual([(e["beat"], e["duration_beats"], e["chord"]) for e in ev],
                         [(1.0, 2.0, "Fm"), (3.0, 2.0, "Bb")])
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(rec(), level)
            for cells in secs.values():
                for cell in cells:
                    for s in cs.parse_subdivisions(str(cell), beats_per_bar=4):
                        self.assertFalse(s.push, f"{level}: unexpected push in {cell!r}")

    def test_the_level_maps_reach_inside_a_split_bar(self):
        """A split cell must not be passed to the chord map as one string."""
        _v, adv = resolve_level_chart(rec(), "Advanced")
        self.assertEqual(adv["Chorus 1"][0], "Fm9|Bbsus2")
        _v, beg = resolve_level_chart(rec(), "Beginner")
        self.assertEqual(beg["Chorus 1"][0], "Fm|Bb")

    def test_every_cell_voices_and_keeps_its_root(self):
        from backing_audio import chord_notes
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


class TheMetadataIsUntouched(unittest.TestCase):
    def test_key_tempo_meter_and_capo(self):
        r = rec()
        ext = r["extensions"]
        self.assertEqual(r["key"], "Eb")
        self.assertEqual(ext["concert_key"], "Eb")
        self.assertEqual(ext["guitar_friendly_key"], "D")
        self.assertEqual(ext["default_bpm"], 100)
        self.assertEqual(ext["time_signature"], "4/4")
        self.assertIn("Capo 1", ext["capo_note"])

    def test_the_notes_record_the_correction_and_its_source(self):
        notes = rec()["extensions"]["arrangement_notes"]
        self.assertIn("FORM CORRECTED", notes)
        self.assertNotIn("FORM NOT VERIFIED", notes)
        self.assertIn("bellandcomusic.com", notes)


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
