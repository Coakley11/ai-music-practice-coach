"""Custom Lab refresh: persisted page beats Global Active / Songs bootstrap."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state
from songs.chart_bundle_startup import studio_page_exempt_from_chart_bundle
from songs.music_source import LAST_CUSTOM_STATE_KEY, SOURCE_CATALOG
from studio_nav_state import (
    _studio_page_from_blob,
    prepare_studio_nav,
    resolve_studio_page_for_restore,
)

SHAPE_PK = "Pop\u001fShape of You — Ed Sheeran"


def _trial_active() -> dict:
    return {
        "id": "trial-rev-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Verse": [{"chord": "D", "bars": 1}, {"chord": "A", "bars": 1}],
        },
        "bpm": 96,
    }


def _last_custom() -> dict:
    active = _trial_active()
    return {"name": "Trial Song", "active": active, "original_key": "D", "practice_key": "D"}


def _shape_selected() -> dict:
    return {
        "pick_key": SHAPE_PK,
        "title": "Shape of You",
        "artist": "Ed Sheeran",
        "genre": "Pop",
        "key": "Bm",
        "label": "Shape of You — Ed Sheeran",
    }


def _blob(
    *,
    session_page: str,
    nav_page: str,
    workspace_page: str,
    core_page: str,
    last_custom: dict | None = None,
) -> dict:
    session = {
        "studio_page": session_page,
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": SHAPE_PK,
        "selected_song": _shape_selected(),
        "display_key": "D",
        "cpl_active_progression": _trial_active(),
    }
    if last_custom is not None:
        session[LAST_CUSTOM_STATE_KEY] = last_custom
    return {
        "studio_nav_state": {"studio_page": nav_page, "page": nav_page},
        "music_workspace_state": {
            "studio_page": workspace_page,
            "page": workspace_page,
            "pick_key": SHAPE_PK,
        },
        "core": {
            "studio_page": core_page,
            "pick_key": SHAPE_PK,
            "song": "Shape of You",
            "display_key": "D",
        },
        "session": session,
        "active_song_state": {
            "pick_key": SHAPE_PK,
            "music_source": SOURCE_CATALOG,
            "selected_song": _shape_selected(),
            "display_key": "D",
        },
    }


def _hydrate(blob: dict) -> dict:
    st = MagicMock()
    st.session_state = {}
    apply_music_disk_state(st, blob, song_picker_catalog={}, song_library={})
    prepare_studio_nav(st.session_state)
    return st.session_state


class TestCustomPageRefreshRestore(unittest.TestCase):
    def test_persisted_custom_beats_generic_picker_workspace(self) -> None:
        blob = _blob(
            session_page="custom",
            nav_page="custom",
            workspace_page="picker",
            core_page="picker",
            last_custom=_last_custom(),
        )
        self.assertEqual(_studio_page_from_blob(blob), "custom")
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "custom")
        self.assertEqual(source, "persisted_session_custom")
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "custom")
        self.assertNotEqual(ss.get("studio_page"), "picker")
        last = ss.get(LAST_CUSTOM_STATE_KEY) if isinstance(ss.get(LAST_CUSTOM_STATE_KEY), dict) else {}
        active = last.get("active") if isinstance(last.get("active"), dict) else {}
        self.assertEqual(str(active.get("name") or last.get("name") or ""), "Trial Song")
        self.assertEqual(ss.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(ss.get("active_catalog_pick_key"), SHAPE_PK)

    def test_explicit_songs_page_wins_even_with_last_custom(self) -> None:
        blob = _blob(
            session_page="picker",
            nav_page="picker",
            workspace_page="picker",
            core_page="picker",
            last_custom=_last_custom(),
        )
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "picker")
        self.assertNotEqual(source, "persisted_session_custom")
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "picker")
        last = ss.get(LAST_CUSTOM_STATE_KEY) if isinstance(ss.get(LAST_CUSTOM_STATE_KEY), dict) else {}
        active = last.get("active") if isinstance(last.get("active"), dict) else {}
        self.assertEqual(str(active.get("name") or last.get("name") or ""), "Trial Song")

    def test_no_last_custom_does_not_invent_custom_over_songs(self) -> None:
        blob = _blob(
            session_page="picker",
            nav_page="picker",
            workspace_page="picker",
            core_page="picker",
            last_custom=None,
        )
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "picker")
        self.assertNotEqual(source, "persisted_session_custom")
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "picker")

    def test_prepare_live_custom_beats_stale_canonical_practice(self) -> None:
        session = {
            "studio_page": "custom",
            "studio_nav_state": {"studio_page": "practice", "last_write_reason": "empty_workspace_default"},
            LAST_CUSTOM_STATE_KEY: _last_custom(),
        }
        page = prepare_studio_nav(session)
        self.assertEqual(page, "custom")
        self.assertEqual(session["studio_page"], "custom")
        self.assertEqual(session["studio_nav_state"]["studio_page"], "custom")

    def test_mission_backing_restore_still_outranks_generic_picker(self) -> None:
        blob = {
            "studio_nav_state": {"studio_page": "backing", "page": "backing"},
            "music_workspace_state": {"studio_page": "picker", "page": "picker"},
            "core": {"studio_page": "picker"},
            "session": {
                "studio_page": "backing",
                "backing_context": {"source": "mission", "key": "G"},
                "_backing_explicit_handoff_source": "mission",
            },
        }
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "backing")
        self.assertEqual(source, "persisted_session_backing")

    def test_custom_lab_is_exempt_from_catalog_chart_bundle_gate(self) -> None:
        self.assertTrue(studio_page_exempt_from_chart_bundle("custom"))
        self.assertFalse(studio_page_exempt_from_chart_bundle("practice"))
        self.assertFalse(studio_page_exempt_from_chart_bundle("backing"))


if __name__ == "__main__":
    unittest.main()
