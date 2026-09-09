"""Mission Backing must not stamp catalog Shape Practice Key."""

from __future__ import annotations

import unittest

from song_catalog.catalog import format_pick_key
from songs.practice_key_state import (
    PRACTICE_KEY_BY_SOURCE_KEY,
    creative_jam_owns_practice_settings,
    get_practice_concert_key,
    set_practice_concert_key,
    should_write_song_source_settings,
)


SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")


def _mission_backing_session() -> dict:
    return {
        "studio_page": "backing",
        "active_catalog_pick_key": SHAPE,
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": SHAPE,
        },
        "display_key": "Fm",
        "concert_key": "Fm",
        "improv_mission_concert_key": "Fm",
        PRACTICE_KEY_BY_SOURCE_KEY: {SHAPE: "Dm"},
        "backing_context": {
            "source": "mission",
            "source_label": "Mission",
            "song_title": "Shape of You",
            "active_song_id": SHAPE,
            "bound_pick_key": SHAPE,
            "key": "Fm",
            "display_key": "Fm",
            "concert_key": "Fm",
        },
        "_backing_explicit_handoff_source": "mission",
    }


class MissionBackingCatalogPkIsolationTests(unittest.TestCase):
    def test_mission_owns_settings_and_skips_catalog_map(self) -> None:
        session = _mission_backing_session()
        self.assertTrue(creative_jam_owns_practice_settings(session))
        self.assertFalse(should_write_song_source_settings(session, SHAPE))

    def test_mission_fm_does_not_overwrite_shape_dm_sticky(self) -> None:
        session = _mission_backing_session()
        set_practice_concert_key(session, "Fm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")

    def test_creative_missions_cm_does_not_overwrite_shape_dm_sticky(self) -> None:
        session = _mission_backing_session()
        session["studio_page"] = "creative"
        session["improv_intelligence_tab"] = "Missions"
        session["display_key"] = "Cm"
        session["concert_key"] = "Cm"
        session["improv_mission_concert_key"] = "Cm"
        session["backing_context"]["key"] = "Cm"
        session["backing_context"]["display_key"] = "Cm"
        session["backing_context"]["concert_key"] = "Cm"
        set_practice_concert_key(session, "Cm", pick_key=SHAPE)
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Dm")


if __name__ == "__main__":
    unittest.main()
