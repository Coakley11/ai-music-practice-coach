"""R7 — Songs active-song identity + Creative selected-chord persistence.

Both defects were found by human review on the Songs/Creative surfaces and
reproduced on origin/dev (not caused by the C4 musical work).

1. Selecting a Catalog song, navigating away and back reverted the active song.
   The Songs selectbox mounts without an ``index``, so a remount re-initializes
   it to the first option. ``consume_uncommitted_catalog_dropdown`` treats a
   widget value that differs from the live pick as a genuine un-fired click, and
   its stale-widget guard requires ``committed == live`` — but the genuine
   on_change path never recorded that marker, so the remount echo was applied
   as a real pick and the previous song came back.

2. An explicit Creative chord click did not survive a refresh. The disk writer
   serializes live session extras and the sealed mission chord snapshot, but
   both were written only *after* the save was requested, so the save captured
   the previous chord and restore then resolved the selection back onto it.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class TestCatalogPickCommittedMarker(unittest.TestCase):
    """The committed marker is what lets a remount echo be told apart from a
    genuine click, so the genuine activation path must record it."""

    def test_apply_catalog_pick_records_committed_marker(self) -> None:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        body = src.split("def _apply_catalog_pick(", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("EXPLICIT_CATALOG_PICK_COMMITTED_KEY", body)
        self.assertIn("PENDING_MATCHING_SONG_DROPDOWN", body)

    def test_committed_marker_is_importable_in_app(self) -> None:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        block = src.split("from songs.state import (", 1)[1].split(")", 1)[0]
        self.assertIn("EXPLICIT_CATALOG_PICK_COMMITTED_KEY", block)

    @staticmethod
    def _catalog() -> dict:
        def _song(title: str, artist: str, key: str) -> dict:
            return {
                "title": title,
                "artist": artist,
                "key": key,
                "sections": {"A": [key]},
                "chart_versions": {"Intermediate": {"A": [key]}},
            }

        return {
            "Pop": {
                "First Song — A": _song("First Song", "A", "G"),
                "Second Song — B": _song("Second Song", "B", "C"),
                "Third Song — C": _song("Third Song", "C", "D"),
            }
        }

    def test_stale_remount_widget_does_not_replace_committed_pick(self) -> None:
        """Widget lagged to the first option while a different pick is live and
        committed: that is a remount echo, not a new selection."""
        from song_catalog import first_valid_pick_key, format_pick_key
        from songs.state import (
            ACTIVE_CATALOG_PICK_KEY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY,
            consume_uncommitted_catalog_dropdown,
        )

        cat = self._catalog()
        fallback = first_valid_pick_key(cat)
        live = format_pick_key("Pop", "Second Song — B")
        self.assertNotEqual(fallback, live)

        session = {
            ACTIVE_CATALOG_PICK_KEY: live,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: live,
            "matching_song_dropdown": fallback,
        }
        st = SimpleNamespace(session_state=session)
        out = consume_uncommitted_catalog_dropdown(
            st, [fallback, live], cat, song_library=None
        )
        self.assertEqual(out, live)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], live)

    def test_genuine_new_pick_is_still_applied(self) -> None:
        """A widget value that is neither the live nor the committed pick is a
        real click whose on_change did not fire — it must still win."""
        from song_catalog import first_valid_pick_key, format_pick_key
        from songs.state import (
            ACTIVE_CATALOG_PICK_KEY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY,
            consume_uncommitted_catalog_dropdown,
        )

        cat = self._catalog()
        fallback = first_valid_pick_key(cat)
        live = format_pick_key("Pop", "Second Song — B")
        clicked = format_pick_key("Pop", "Third Song — C")
        session = {
            ACTIVE_CATALOG_PICK_KEY: live,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: live,
            "matching_song_dropdown": clicked,
        }
        st = SimpleNamespace(session_state=session)
        out = consume_uncommitted_catalog_dropdown(
            st, [fallback, live, clicked], cat, song_library=None
        )
        self.assertEqual(out, clicked)


class TestCreativeChordClickIsDurable(unittest.TestCase):
    """The chord click must be sealed into live session state and into the
    mission chord snapshot BEFORE the save is requested."""

    def _order(self) -> tuple[int, int, int]:
        src = (ROOT / "creative_mission_config_persistence.py").read_text(encoding="utf-8")
        body = src.split("def handle_user_mission_target_selection(", 1)[1].split(
            "\ndef ", 1
        )[0]
        seal_keys = body.index('session["ii_selected_chord"] = sym')
        seal_snap = body.index("seal_mission_chord_snapshot(")
        save = body.index("_handle_user_mission_config_change(")
        return seal_keys, seal_snap, save

    def test_session_keys_sealed_before_save(self) -> None:
        seal_keys, _seal_snap, save = self._order()
        self.assertLess(
            seal_keys, save, "chord session keys must be sealed before the save is requested"
        )

    def test_chord_snapshot_sealed_before_save(self) -> None:
        _seal_keys, seal_snap, save = self._order()
        self.assertLess(
            seal_snap, save, "chord snapshot must be sealed before the save is requested"
        )

    def test_click_updates_snapshot_and_session_together(self) -> None:
        from creative_chord_selection_authority import (
            MISSION_CHORD_SNAPSHOT_KEY,
            read_mission_chord_snapshot,
        )
        from creative_mission_config_persistence import handle_user_mission_target_selection

        section_map = [("A", ["Cmaj7", "E7", "A7", "Dm7"])]
        session: dict = {
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_mission_pick": "Improvise using only chord tones",
            "improv_active_mission": "Improvise using only chord tones",
            "_improv_mission_section_map": section_map,
            "improv_mission_chord_options": ["Cmaj7", "E7", "A7", "Dm7"],
            "ii_selected_chord": "Cmaj7",
            "ii_selected_section": "A",
            "ii_selected_chord_index": 0,
            MISSION_CHORD_SNAPSHOT_KEY: {
                "mission_id": "Improvise using only chord tones",
                "session_id": "",
                "source_identity": "",
                "section": "A",
                "chord_index": 0,
                "concert_chord": "Cmaj7",
                "concert_practice_key": "C",
            },
            "concert_key": "C",
            "display_key": "C",
        }
        handle_user_mission_target_selection(
            session, chord="A7", section="A", chord_index=2, chord_label="A · A7"
        )
        self.assertEqual(session["ii_selected_chord"], "A7")
        self.assertEqual(session["ii_selected_chord_index"], 2)
        snap = read_mission_chord_snapshot(session)
        self.assertIsInstance(snap, dict)
        self.assertEqual(str((snap or {}).get("concert_chord")), "A7")
        self.assertEqual(int((snap or {}).get("chord_index")), 2)

    def test_restored_selection_is_not_remapped_to_first_chord(self) -> None:
        """With session and snapshot agreeing on the clicked chord, the
        authoritative resolver must keep it (this is the refresh path)."""
        from creative_chord_selection_authority import (
            MISSION_CHORD_SNAPSHOT_KEY,
            resolve_authoritative_chord_selection,
        )

        section_map = [("A", ["Cmaj7", "E7", "A7", "Dm7"])]
        session: dict = {
            "ii_selected_chord": "A7",
            "ii_selected_section": "A",
            "ii_selected_chord_index": 2,
            MISSION_CHORD_SNAPSHOT_KEY: {
                "mission_id": "",
                "session_id": "",
                "source_identity": "",
                "section": "A",
                "chord_index": 2,
                "concert_chord": "A7",
                "concert_practice_key": "C",
            },
        }
        sym, sec, idx = resolve_authoritative_chord_selection(session, section_map)
        self.assertEqual(sym, "A7")
        self.assertEqual(sec, "A")
        self.assertEqual(int(idx), 2)

    def test_stale_snapshot_index_zero_would_remap(self) -> None:
        """Guard the mechanism itself: a snapshot left at the previous chord is
        what pulled the restored selection back to the first chord."""
        from creative_chord_selection_authority import (
            MISSION_CHORD_SNAPSHOT_KEY,
            resolve_authoritative_chord_selection,
        )

        section_map = [("A", ["Cmaj7", "E7", "A7", "Dm7"])]
        session: dict = {
            "ii_selected_chord": "A7",
            "ii_selected_section": "A",
            "ii_selected_chord_index": 0,
            MISSION_CHORD_SNAPSHOT_KEY: {
                "mission_id": "",
                "session_id": "",
                "source_identity": "",
                "section": "A",
                "chord_index": 0,
                "concert_chord": "Cmaj7",
                "concert_practice_key": "C",
            },
        }
        sym, _sec, _idx = resolve_authoritative_chord_selection(session, section_map)
        self.assertEqual(sym, "Cmaj7")


if __name__ == "__main__":
    unittest.main()
