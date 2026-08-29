"""Karaoke setlist entry model — Practice Key snapshots, duplicates, play count."""

from __future__ import annotations

import copy
import unittest

import karaoke_mode as km
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    set_practice_concert_key,
)


def _ss(**extra) -> dict:
    ss: dict = {
        "instrument": "Voice",
        PRACTICE_KEY_BY_SOURCE_KEY: {},
        "karaoke_queue": [],
    }
    ss.update(extra)
    return ss


class TestKaraokeEntryModel(unittest.TestCase):
    def test_add_snapshots_practice_key_and_allows_duplicates(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        set_practice_concert_key(ss, "C", pick_key=pick)
        e1 = km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        self.assertIsNotNone(e1)
        self.assertEqual(e1["practice_key"], "C")
        set_practice_concert_key(ss, "D", pick_key=pick)
        e2 = km.add_to_queue(ss, pick, title="All the Things You Are")
        self.assertEqual(e2["practice_key"], "D")
        # Global key change must not rewrite prior entries
        set_practice_concert_key(ss, "G", pick_key=pick)
        q = km.get_queue(ss)
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0]["practice_key"], "C")
        self.assertEqual(q[1]["practice_key"], "D")
        self.assertNotEqual(q[0]["entry_id"], q[1]["entry_id"])

    def test_five_keys_same_song(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        keys = ["C", "D", "E", "F", "G"]
        for k in keys:
            set_practice_concert_key(ss, k, pick_key=pick)
            km.add_to_queue(ss, pick, title="All the Things You Are")
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], keys)
        self.assertEqual(len({e["entry_id"] for e in q}), 5)

    def test_legacy_string_queue_normalizes(self) -> None:
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        ss = _ss(karaoke_queue=[pick, pick])
        q = km.get_queue(ss)
        self.assertEqual(len(q), 2)
        self.assertTrue(all(isinstance(e, dict) and e.get("entry_id") for e in q))
        self.assertEqual(q[0]["pick_key"], pick)

    def test_refresh_preserves_entries_and_keys(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        set_practice_concert_key(ss, "Fm", pick_key=pick)
        km.add_to_queue(ss, pick, title="Blue Bossa")
        set_practice_concert_key(ss, "Gm", pick_key=pick)
        km.add_to_queue(ss, pick, title="Blue Bossa")
        blob = copy.deepcopy(ss[km.KARAOKE_QUEUE_KEY])
        restored = _ss(karaoke_queue=blob)
        q = km.get_queue(restored)
        self.assertEqual([e["practice_key"] for e in q], ["Fm", "Gm"])

    def test_playback_applies_entry_saved_key(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("C", "D", "E"):
            set_practice_concert_key(ss, k, pick_key=pick)
            km.add_to_queue(ss, pick)
        started = km.start_session(ss)
        self.assertEqual(started, pick)
        self.assertEqual(km.current_session_practice_key(ss), "C")
        self.assertEqual(get_practice_concert_key(ss, pick), "C")
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "D")
        self.assertEqual(get_practice_concert_key(ss, pick), "D")
        km.advance_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "E")

    def test_play_count_repeats_before_advance(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fBlue Bossa — Kenny Dorham"
        set_practice_concert_key(ss, "Fm", pick_key=pick)
        entry = km.add_to_queue(ss, pick, play_count=3)
        set_practice_concert_key(ss, "C", pick_key="other\x1fSong — A")
        km.add_to_queue(ss, "other\x1fSong — A", practice_key="C")
        km.start_session(ss)
        self.assertEqual(km.current_session_entry(ss)["entry_id"], entry["entry_id"])
        # First two advances stay on same entry
        self.assertEqual(km.advance_session(ss), pick)
        self.assertEqual(km.current_session_entry(ss)["entry_id"], entry["entry_id"])
        self.assertEqual(km.advance_session(ss), pick)
        # Third advance moves to next entry
        nxt = km.advance_session(ss)
        self.assertEqual(nxt, "other\x1fSong — A")
        self.assertEqual(km.current_session_practice_key(ss), "C")

    def test_custom_pick_key_source_and_identity(self) -> None:
        ss = _ss()
        pick = "custom::my_progress_v1"
        set_practice_concert_key(ss, "Bb", pick_key=pick)
        entry = km.add_to_queue(ss, pick, title="My Custom Song", source="custom_progression")
        self.assertEqual(entry["source"], "custom_progression")
        self.assertEqual(entry["practice_key"], "Bb")
        self.assertEqual(entry["pick_key"], pick)

    def test_stop_and_restart_preserves_queue_keys(self) -> None:
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("C", "G"):
            set_practice_concert_key(ss, k, pick_key=pick)
            km.add_to_queue(ss, pick)
        km.start_session(ss)
        km.stop_session(ss)
        q = km.get_queue(ss)
        self.assertEqual([e["practice_key"] for e in q], ["C", "G"])
        km.start_session(ss)
        self.assertEqual(km.current_session_practice_key(ss), "C")

    def test_entry_display_line_shows_key(self) -> None:
        line = km.entry_display_line(
            {
                "title": "All the Things You Are",
                "practice_key": "D",
                "play_count": 3,
            }
        )
        self.assertEqual(line, "All the Things You Are · Practice Key D · Play 3×")

    def test_duplicate_titles_distinct_practice_keys_in_managed_setlist(self) -> None:
        """ATTYA Ab / G / Ab must stay distinguishable while managing the queue."""
        ss = _ss()
        pick = "Jazz\x1fAll the Things You Are — Jerome Kern"
        for k in ("Ab", "G", "Ab"):
            set_practice_concert_key(ss, k, pick_key=pick)
            km.add_to_queue(ss, pick, title="All the Things You Are", artist="Jerome Kern")
        rows = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in rows], ["Ab", "G", "Ab"])
        self.assertEqual(
            [r["label"] for r in rows],
            [
                "All the Things You Are · Practice Key Ab",
                "All the Things You Are · Practice Key G",
                "All the Things You Are · Practice Key Ab",
            ],
        )
        self.assertEqual(len({r["entry_id"] for r in rows}), 3)

        # Sidebar Practice Key must not rewrite saved entry labels.
        set_practice_concert_key(ss, "C", pick_key=pick)
        rows_after = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in rows_after], ["Ab", "G", "Ab"])
        self.assertEqual([r["label"] for r in rows_after], [r["label"] for r in rows])

        # Reorder moves the exact entry (key + id).
        mid_id = rows[1]["entry_id"]
        km.move_in_queue(ss, mid_id, -1)
        reordered = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in reordered], ["G", "Ab", "Ab"])
        self.assertEqual(reordered[0]["entry_id"], mid_id)

        # Remove only the targeted entry_id (first Ab after reorder = original first Ab).
        remove_id = reordered[1]["entry_id"]
        km.remove_from_queue(ss, remove_id)
        left = km.managed_setlist_display_rows(ss)
        self.assertEqual([r["practice_key"] for r in left], ["G", "Ab"])
        self.assertNotIn(remove_id, {r["entry_id"] for r in left})


class TestMusicSourceBadgeIcons(unittest.TestCase):
    def test_custom_and_composition_icons(self) -> None:
        from app_ui import studio_song_meta_badges_html
        from music_feature_icons import FEATURE_ICONS

        custom_html = studio_song_meta_badges_html(source="Custom Progression")
        self.assertIn(FEATURE_ICONS["custom"], custom_html)
        comp_html = studio_song_meta_badges_html(source="Composition")
        self.assertIn(FEATURE_ICONS["composition"], comp_html)


if __name__ == "__main__":
    unittest.main()
