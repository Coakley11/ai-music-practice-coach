"""Say (John Mayer): original key is B-flat (G-shape chart with capo 3), not G.

Evidence: Hooktheory TheoryTab (Bb major, 89 BPM) and the Musicnotes edition ("original key is
Bb major"); guitar charts show G-C-Em-D with a capo on fret 3, which sounds Bb-Eb-Gm-F. The chart
used to carry the G shapes AS the original key.  These tests pin that the chord content did not
change, only its concert spelling, and that saved data is neither double-transposed nor reset.

The BAR GRID was corrected separately, in W21 (156 cells -> 78): the chart had been written at
half-bar granularity. ``_old_sections()`` is deliberately left on the old grid, because the
saved-copy tests need a chart a user could really have stored; ``_g_shapes()`` is the current
chart in G shapes and is what the round-trip test compares against.
"""

from __future__ import annotations

import copy
import re
import unittest

from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from music_theory import transpose_sections_dict
from song_catalog.catalog import curated_song_records
from songs import chart_provenance as cp

PICK = "Say\x1fJohn Mayer"
# The chart as it was before the correction (G shapes labelled as the original key).
OLD_MAIN = ["G:3.5|C:0.5p", "C:4", "Em:3.5|D:0.5p", "D:4"]
OLD_BRIDGE = ["Am:4", "Am:4", "C:3.5|D:0.5p", "D:4"] * 3 + ["C:4", "C:4", "C:3.5|D:0.5p", "D:4"]
OLD_FINAL = ["Em:3.5|G:0.5p", "G:4", "C7:4", "C7:4"] * 8
OLD_INTRO = (["G", "G", "Gsus4", "Gsus4", "G", "G", "Gsus4/A", "Gsus4/A"]) * 2


def _old_sections() -> dict:
    """The chart as a user could have saved it before either correction.

    Kept on the pre-W21 half-bar grid on purpose: the saved-copy tests below
    need a chart that really existed, so they can prove an old stored copy
    refreshes without being double-transposed or silently reset.
    """
    return {
        "Intro": list(OLD_INTRO), "Verse 1": OLD_MAIN * 4, "Chorus 1": OLD_MAIN * 4,
        "Turnaround 1": list(OLD_MAIN), "Verse 2": OLD_MAIN * 4, "Chorus 2": OLD_MAIN * 4,
        "Turnaround 2": list(OLD_MAIN), "Bridge": list(OLD_BRIDGE), "Turnaround 3": list(OLD_MAIN),
        "Verse 3": OLD_MAIN * 4, "Final Chorus": list(OLD_FINAL),
    }


# The CURRENT chart in its G shapes, i.e. after W21 corrected the bar grid to
# the record's two-chords-per-bar reading. The round-trip test uses this; the
# bar counts here are half the OLD ones because each played bar used to be
# written as two cells.
G_MAIN = ["G:2|C:2p", "Em:2|D:2p"]
G_BRIDGE = ["Am", "C:2|D:2p"] * 3 + ["C", "C:2|D:2p"]
G_FINAL = ["Em:2|G:2p", "C7"] * 8
G_INTRO = ["G", "Gsus4", "G", "Gsus4/A"] * 2


def _g_shapes() -> dict:
    return {
        "Intro": list(G_INTRO), "Verse 1": G_MAIN * 4, "Chorus 1": G_MAIN * 4,
        "Turnaround 1": list(G_MAIN), "Verse 2": G_MAIN * 4, "Chorus 2": G_MAIN * 4,
        "Turnaround 2": list(G_MAIN), "Bridge": list(G_BRIDGE), "Turnaround 3": list(G_MAIN),
        "Verse 3": G_MAIN * 4, "Final Chorus": list(G_FINAL),
    }


def _norm(token: str) -> str:
    return re.sub(r":4(?![.\d])", "", token)


def _record() -> dict:
    return copy.deepcopy(next(r for r in curated_song_records() if r["title"] == "Say"))


class TestSayOriginalKey(unittest.TestCase):
    def test_original_key_is_bb_with_the_capo_note_and_unchanged_tempo(self) -> None:
        r = _record()
        self.assertEqual(r["key"], "Bb")
        ext = r.get("extensions") or {}
        self.assertEqual(ext.get("default_bpm"), 82)  # provisional; sources say 82-89, not changed arbitrarily
        self.assertIn("Capo 3", str(ext.get("capo_note")))
        self.assertEqual(r["section_order"], list(_old_sections()))

    def test_chart_in_the_g_practice_key_is_identical_to_the_g_shape_chart(self) -> None:
        """Transposing the Bb chart to G reproduces the G-shape chart exactly.

        Renamed from test_chart_in_the_old_g_practice_key_is_identical_to_the_old_chart
        and retargeted from _old_sections() to _g_shapes(): the key correction
        this file is about lost nothing, and W21's separate grid correction
        changed the bar layout, so the round-trip target is the current chart in
        G shapes rather than the pre-W21 one.
        """
        r = _record()
        back = transpose_sections_dict(r["sections"], "Bb", "G")
        for name, cells in _g_shapes().items():
            self.assertEqual([_norm(c) for c in back[name]], [_norm(c) for c in cells], name)

    def test_all_levels_have_valid_chords_and_events(self) -> None:
        for level in ("Beginner", "Intermediate", "Advanced"):
            view, secs = resolve_level_chart(_record(), level)
            order = list(view.get("section_order") or secs)
            self.assertEqual(validate_chord_events(sections_dict_to_events({n: secs[n] for n in order})), [], level)
            flat = " ".join(c for n in order for c in secs[n])
            self.assertNotRegex(flat, r"(?<![A-Za-z])(G|Em|Am|D)(?![A-Za-z#b0-9])", level)  # no leftover G-shape chords

    def test_bar_counts_match_the_corrected_grid(self) -> None:
        """Renamed from test_bar_counts_are_unchanged.

        The KEY correction left the bar counts alone, which is what this
        originally pinned. W21 then halved them on purpose, so the pin now
        states the corrected grid: 78 cells, one pass = 3:48 at 82 BPM against
        a 3:49 single.
        """
        r = _record()
        self.assertEqual(
            {n: len(c) for n, c in r["sections"].items()},
            {n: len(c) for n, c in _g_shapes().items()},
        )
        self.assertEqual(sum(len(c) for c in r["sections"].values()), 78)

    def test_saved_catalog_copy_of_the_old_chart_refreshes_with_its_key_not_double_transposed(self) -> None:
        new = _record()
        snap = {"title": "Say", "artist": "John Mayer", "pick_key": PICK, "key": "G", "sections": _old_sections()}
        frozen = copy.deepcopy(snap)
        self.assertEqual(cp.classify_snapshot(snap, new, pick_key=PICK)[0], cp.REFRESH)
        out = cp.reconcile_snapshot(snap, new, pick_key=PICK)
        self.assertEqual(snap, frozen)  # stored copy untouched
        self.assertEqual(out["key"], "Bb")
        self.assertEqual(out["sections"], new["sections"])  # chords and key agree (Bb chords, Bb key)

    def test_user_edited_or_user_origin_copies_keep_their_g_chart_and_key(self) -> None:
        new = _record()
        edited = {"title": "Say", "artist": "John Mayer", "pick_key": PICK, "key": "G",
                  "sections": {**_old_sections(), "Intro": ["G"] * 3}}
        out = cp.reconcile_snapshot(edited, new, pick_key=PICK)
        self.assertEqual(out["key"], "G")
        self.assertEqual(out["sections"]["Intro"], ["G"] * 3)
        origin = dict(edited, sections=_old_sections(), chart_origin="user")
        self.assertEqual(cp.reconcile_snapshot(origin, new, pick_key=PICK)["key"], "G")

    def test_a_saved_g_practice_key_is_not_part_of_the_chart_refresh(self) -> None:
        """Practice Key lives outside the chart snapshot; healing a session must not touch it."""
        new = _record()
        session = {
            "selected_song": {"title": "Say", "artist": "John Mayer", "pick_key": PICK, "key": "G", "sections": _old_sections()},
            "display_key": "G", "concert_key": "G", "practice_key_by_source": {"catalog": "G"},
        }
        cp.heal_session_chart_copies(session, new, PICK, where="test")
        self.assertEqual(session["selected_song"]["key"], "Bb")
        self.assertEqual((session["display_key"], session["concert_key"]), ("G", "G"))
        self.assertEqual(session["practice_key_by_source"], {"catalog": "G"})

    def test_transposing_instruments_get_correct_written_keys_for_bb_and_for_a_g_practice_key(self) -> None:
        from instrument_transposition import written_key_for_type

        expected = {  # (concert key, instrument type) -> written key
            ("Bb", "Bb Trumpet"): "C", ("Bb", "Alto Sax (Eb)"): "G", ("Bb", "Tenor Sax (Bb)"): "C",
            ("G", "Bb Trumpet"): "A", ("G", "Alto Sax (Eb)"): "E", ("G", "Tenor Sax (Bb)"): "A",
        }
        for (concert, t), written in expected.items():
            self.assertEqual(written_key_for_type(concert, t), written, (concert, t))


if __name__ == "__main__":
    unittest.main()
