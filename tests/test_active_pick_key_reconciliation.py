"""Startup active-song reconciliation — cloud workspace must not clobber to catalog default."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    PICK_KEY_RECOVERY_NOTICE_KEY,
    apply_active_pick_key_reconciliation,
    get_song_context,
    reconcile_active_pick_key,
)


def _mini_catalog() -> dict:
    return {
        "Pop": {
            "Say — Artist": {"title": "Say", "artist": "Artist", "key": "C", "sections": {}},
            "Perfect — Ed Sheeran": {
                "title": "Perfect",
                "artist": "Ed Sheeran",
                "key": "G",
                "sections": {"Verse": ["G", "Em7"]},
            },
        }
    }


class _FakeSt:
    def __init__(self, session_state: dict) -> None:
        self.session_state = session_state


class ActivePickKeyReconciliationTests(unittest.TestCase):
    def test_reconcile_prefers_cloud_over_empty_session(self):
        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {},
            "_suite_last_cloud_fetch_payload": {"core": {"pick_key": perfect_pk}},
        }
        self.assertEqual(
            reconcile_active_pick_key(ss, song_picker_catalog=catalog),
            perfect_pk,
        )

    def test_startup_restores_perfect_not_say(self):
        catalog = _mini_catalog()
        say_pk = format_pick_key("Pop", "Say — Artist")
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {},
            "studio_page": "creative",
            "instrument": "Alto Saxophone",
            "_suite_last_cloud_fetch_payload": {
                "core": {"pick_key": perfect_pk},
                "music_workspace_state": {
                    "studio_page": "creative",
                    "instrument": "Alto Saxophone",
                },
            },
            "_music_workspace_blob_hydrated": True,
        }
        st = _FakeSt(ss)

        from music_persistent_state import finalize_music_startup_restore

        finalize_music_startup_restore(
            st,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        genre, title, _data = get_song_context(
            st,
            song_library=catalog,
            song_picker_catalog=catalog,
        )
        self.assertEqual(title, "Perfect")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), perfect_pk)
        self.assertNotEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), say_pk)
        self.assertEqual(st.session_state.get("studio_page"), "creative")
        self.assertEqual(st.session_state.get("instrument"), "Alto Saxophone")

    def test_cloud_perfect_does_not_persist_say_default(self):
        catalog = _mini_catalog()
        say_pk = format_pick_key("Pop", "Say — Artist")
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {},
            "_suite_last_cloud_fetch_payload": {"core": {"pick_key": perfect_pk}},
            "_music_workspace_blob_hydrated": True,
        }
        st = _FakeSt(ss)
        persisted: list[str] = []

        def _fake_persist(_st: _FakeSt) -> None:
            persisted.append(str(_st.session_state.get(ACTIVE_CATALOG_PICK_KEY)))

        with patch("songs.state.persist_music_local_state", side_effect=_fake_persist):
            from music_restore_phase import complete_music_restore_phase

            apply_active_pick_key_reconciliation(
                st,
                song_picker_catalog=catalog,
                song_library=catalog,
            )
            complete_music_restore_phase(st.session_state)
            get_song_context(
                st,
                song_library=catalog,
                song_picker_catalog=catalog,
            )

        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), perfect_pk)
        if persisted:
            self.assertNotIn(say_pk, persisted)
        self.assertNotIn(
            "No saved song selection; restored default catalog song.",
            str(st.session_state.get(PICK_KEY_RECOVERY_NOTICE_KEY) or ""),
        )

    def test_empty_workspace_may_still_apply_catalog_default_after_finalize(self):
        catalog = _mini_catalog()
        say_pk = format_pick_key("Pop", "Say — Artist")
        st = _FakeSt(
            {
                ACTIVE_CATALOG_PICK_KEY: "",
                "selected_song": {},
            }
        )
        from music_restore_phase import complete_music_restore_phase

        complete_music_restore_phase(st.session_state)
        genre, title, _data = get_song_context(
            st,
            song_library=catalog,
            song_picker_catalog=catalog,
        )
        self.assertEqual(title, "Say")
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), say_pk)


if __name__ == "__main__":
    unittest.main()
