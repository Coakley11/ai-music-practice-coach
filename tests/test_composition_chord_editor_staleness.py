"""Manual chord editor never carries stale chords or bar lengths (2026-11-19).

1. After a song key change (or Undo key change) the editor's draft still held the old key's chords, warned about
   edits nobody made, and its Accept wrote them into the transposed song.
2. Bars inputs were keyed by row position: after Delete/Insert the old row's value was written onto the chord that
   moved into that slot.
"""

import unittest

import composition_studio_page as page
from composition_chord_manual_editor import draft_key, ensure_draft, push_undo, undo_key
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_key_transpose import apply_song_key_change, apply_undo_key_change


def _doc():
    doc = bootstrap_from_vision(genre="Pop", song_idea="Chord editor.")
    apply_structure_template(doc, "simple")
    g = doc.setdefault("global", {})
    g.update({"original_key_center": "D", "original_key_label": "D major"})
    sec = ordered_sections(doc)[0]
    apply_section_chords(doc, str(sec["id"]), parse_chord_paste("D Bm G A"))
    return doc, str(sec["id"])


def _chords(doc, sid):
    sec = next(s for s in ordered_sections(doc) if str(s["id"]) == sid)
    return [str(c.get("chord")) for c in sec.get("chords") or []]


class TestChordDraftFollowsKey(unittest.TestCase):
    def test_key_change_and_undo_drop_the_old_key_draft(self) -> None:
        doc, sid = _doc()
        ss: dict = {}
        sec = next(s for s in ordered_sections(doc) if str(s["id"]) == sid)
        ensure_draft(ss, sid, sec["chords"])
        push_undo(ss, sid, sec["chords"])
        apply_song_key_change(ss, doc, "E", new_key_label="E major", push_undo=True)
        self.assertEqual(_chords(doc, sid), ["E", "C#m", "A", "B"])
        self.assertNotIn(draft_key(sid), ss)
        self.assertNotIn(undo_key(sid), ss)
        sec = next(s for s in ordered_sections(doc) if str(s["id"]) == sid)
        self.assertEqual([c["chord"] for c in ensure_draft(ss, sid, sec["chords"])], ["E", "C#m", "A", "B"])
        self.assertTrue(apply_undo_key_change(ss, doc))
        self.assertEqual(_chords(doc, sid), ["D", "Bm", "G", "A"])
        self.assertNotIn(draft_key(sid), ss)


class TestBarsWidgetKey(unittest.TestCase):
    def test_key_follows_the_row_not_just_its_position(self) -> None:
        k = page._chord_bars_widget_key
        bm2 = {"chord": "Bm", "bars": 2}
        g1 = {"chord": "G", "bars": 1}
        # Before delete: Bm(2) at index 1 of 4. After deleting D: Bm(2) at index 0 of 3, G(1) at index 1 of 3.
        before = {k("s", 1, 4, bm2), k("s", 2, 4, g1)}
        after = {k("s", 0, 3, bm2), k("s", 1, 3, g1)}
        self.assertFalse(before & after)
        self.assertNotEqual(k("s", 1, 4, {"chord": "Bm", "bars": 1}), k("s", 1, 4, bm2))
        self.assertEqual(k("s", 1, 4, dict(bm2)), k("s", 1, 4, bm2))  # stable while nothing changes

    def test_repeated_identical_chords_each_get_their_own_widget(self) -> None:
        """Eight identical rows ("C C C C C C C C", 1 bar each) must not share one Bars input."""
        k = page._chord_bars_widget_key
        rows = [{"chord": "C", "bars": 1} for _ in range(8)]
        keys = [k("s", i, len(rows), r) for i, r in enumerate(rows)]
        self.assertEqual(len(set(keys)), 8)

    def test_adjacent_duplicates_keep_their_own_bar_counts(self) -> None:
        """C(1) C(2) C(1): same symbol three times, so only index + length may tell the inputs apart."""
        k = page._chord_bars_widget_key
        rows = [{"chord": "C", "bars": 1}, {"chord": "C", "bars": 2}, {"chord": "C", "bars": 1}]
        keys = [k("s", i, len(rows), r) for i, r in enumerate(rows)]
        self.assertEqual(len(set(keys)), 3)
        # Deleting the first row shifts C(2) and C(1) up; neither may inherit a key from before the delete.
        after = [k("s", i, 2, r) for i, r in enumerate(rows[1:])]
        self.assertFalse(set(keys) & set(after))

    def test_two_sections_never_share_a_widget(self) -> None:
        k = page._chord_bars_widget_key
        row = {"chord": "C", "bars": 1}
        self.assertNotEqual(k("verse", 0, 1, row), k("chorus", 0, 1, row))

    def test_a_reused_key_can_only_carry_the_same_bar_count(self) -> None:
        """The safety invariant: if a key repeats, the stored Bars value is already the right one.

        Streamlit keeps a widget's value under its key, so a key may only be reused by a row that wants the same
        value. The bar count is part of the key, so rows differing in bars can never collide.
        """
        k = page._chord_bars_widget_key
        seen: dict[str, int] = {}
        for sid in ("verse", "chorus"):
            for n_rows in range(1, 9):
                for i in range(n_rows):
                    for chord in ("C", "Am", "G/B", "C"):
                        for bars in range(1, 9):
                            key = k(sid, i, n_rows, {"chord": chord, "bars": bars})
                            self.assertEqual(seen.setdefault(key, bars), bars)

    def test_insert_and_delete_keep_bars_with_their_chords(self) -> None:
        """End to end on the draft itself: the bar counts move with their chords, not with screen positions."""
        from composition_chord_manual_editor import insert_draft_chord, remove_draft_chord, update_draft_chord

        draft = [{"chord": "D", "bars": 1}, {"chord": "Bm", "bars": 2}, {"chord": "G", "bars": 1}]
        after_del = remove_draft_chord(draft, 0)
        self.assertEqual([(r["chord"], r["bars"]) for r in after_del], [("Bm", 2), ("G", 1)])
        after_ins = insert_draft_chord(after_del, 1, "A")
        self.assertEqual([(r["chord"], r["bars"]) for r in after_ins][:2], [("Bm", 2), ("A", 1)])
        self.assertEqual(after_ins[-1]["chord"], "G")
        self.assertEqual(after_ins[-1]["bars"], 1)

    def test_a_bar_count_edit_touches_only_its_own_row(self) -> None:
        from composition_chord_manual_editor import update_draft_chord

        k = page._chord_bars_widget_key
        draft = [{"chord": "D", "bars": 1}, {"chord": "Bm", "bars": 1}, {"chord": "G", "bars": 1}]
        before = [k("s", i, 3, r) for i, r in enumerate(draft)]
        edited = update_draft_chord(draft, 1, bars=3)
        self.assertEqual([(r["chord"], r["bars"]) for r in edited], [("D", 1), ("Bm", 3), ("G", 1)])
        after = [k("s", i, 3, r) for i, r in enumerate(edited)]
        self.assertEqual(before[0], after[0])  # untouched rows keep their input
        self.assertEqual(before[2], after[2])
        self.assertNotEqual(before[1], after[1])  # the edited row gets a fresh input, seeded with 3

    def test_timeline_rows_carry_the_bars_the_key_needs(self) -> None:
        """The widget is keyed from timeline rows, including a '%' repeat row (which shows the previous chord)."""
        from composition_chord_manual_editor import chord_timeline

        rows = chord_timeline(
            [{"chord": "D", "bars": 1}, {"repeat": True, "bars": 2}, {"chord": "G", "bars": 1}], meter="4/4"
        )
        self.assertEqual([(r["chord"], r["bars"]) for r in rows], [("D", 1), ("D", 2), ("G", 1)])
        keys = [page._chord_bars_widget_key("s", int(r["index"]), len(rows), r) for r in rows]
        self.assertEqual(len(set(keys)), 3)


if __name__ == "__main__":
    unittest.main()
