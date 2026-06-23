"""v19 — reboot restore guard and capo persistence helpers."""

from __future__ import annotations

import unittest

from guitar_capo import (
    CAPO_ENABLED_KEY,
    CAPO_SHAPE_KEY,
    CAPO_SOUNDING_KEY,
    apply_capo_context_fields,
    capo_fields_from_session,
)
from song_catalog.catalog import format_pick_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, get_song_context


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


class V19RestoreGuardTests(unittest.TestCase):
    def test_get_song_context_uses_cloud_pick_key_before_catalog_default(self):
        catalog = {
            "Pop": {
                "Say — Artist": {"title": "Say", "artist": "Artist", "key": "C", "sections": {}},
                "Stay — Artist": {"title": "Stay", "artist": "Artist", "key": "G", "sections": {}},
            }
        }
        cloud_pk = format_pick_key("Pop", "Stay — Artist")
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {},
                "_suite_last_cloud_fetch_payload": {
                    "core": {"pick_key": cloud_pk},
                },
                "_music_restore_phase_complete": True,
            }
        )
        genre, title, _data = get_song_context(
            st,
            song_library=catalog,
            song_picker_catalog=catalog,
        )
        self.assertEqual(genre, "Pop")
        self.assertEqual(title, "Stay")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), cloud_pk)

    def test_get_song_context_uses_canonical_pick_key_before_catalog_default(self):
        catalog = {
            "Pop": {
                "Say — Artist": {"title": "Say", "artist": "Artist", "key": "C", "sections": {}},
                "Stay — Artist": {"title": "Stay", "artist": "Artist", "key": "G", "sections": {}},
            }
        }
        saved_pk = format_pick_key("Pop", "Stay — Artist")
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {},
                "active_song_state": {"pick_key": saved_pk},
                "_music_restore_phase_complete": True,
            }
        )
        genre, title, _data = get_song_context(
            st,
            song_library=catalog,
            song_picker_catalog=catalog,
        )
        self.assertEqual(title, "Stay")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), saved_pk)

    def test_capo_fields_round_trip(self):
        ss = {
            CAPO_ENABLED_KEY: True,
            CAPO_SOUNDING_KEY: "D",
            CAPO_SHAPE_KEY: "E",
        }
        fields = capo_fields_from_session(ss)
        target: dict = {}
        apply_capo_context_fields(target, fields)
        self.assertTrue(target[CAPO_ENABLED_KEY])
        self.assertEqual(target[CAPO_SOUNDING_KEY], "D")
        self.assertEqual(target[CAPO_SHAPE_KEY], "E")


if __name__ == "__main__":
    unittest.main()
