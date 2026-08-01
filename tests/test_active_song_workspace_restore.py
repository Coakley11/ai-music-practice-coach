"""Active-song identity apply from hydrated workspace envelopes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from song_catalog.catalog import format_pick_key
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY, reconcile_active_pick_key


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


class ActiveSongWorkspaceRestoreTests(unittest.TestCase):
    def test_hydrated_envelope_applies_pick_key_via_apply_disk_state(self):
        from music_persistent_state import apply_music_disk_state

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        st = _FakeSt({})
        payload = {
            "core": {"pick_key": perfect_pk, "song": "Perfect", "artist": "Ed Sheeran"},
            "session": {},
            "music_workspace_state": {
                "active_song": {
                    "pick_key": perfect_pk,
                    "title": "Perfect",
                    "genre": "Pop",
                    "original_key": "G",
                    "source_type": "catalog",
                }
            },
        }
        apply_music_disk_state(
            st,
            payload,
            song_picker_catalog=catalog,
            song_library=catalog,
            authoritative_restore=True,
        )
        st.session_state["_music_workspace_blob_hydrated"] = True
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), perfect_pk)

    def test_diagnostic_state_reconciles_after_finalize(self):
        from music_persistent_state import finalize_music_startup_restore

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        ss = {
            ACTIVE_CATALOG_PICK_KEY: "",
            "selected_song": {},
            "studio_page": "creative",
            "_suite_last_cloud_fetch_payload": {
                "core": {"pick_key": perfect_pk},
                "music_workspace_state": {"active_song": {"pick_key": perfect_pk, "title": "Perfect"}},
            },
            "_music_workspace_blob_hydrated": True,
        }
        st = _FakeSt(ss)
        finalize_music_startup_restore(
            st,
            song_picker_catalog=catalog,
            song_library=catalog,
        )
        self.assertEqual(reconcile_active_pick_key(ss, song_picker_catalog=catalog), perfect_pk)
        self.assertEqual(ss.get("studio_page"), "creative")

    def test_legacy_title_genre_migration_unique(self):
        from active_song_workspace_restore import migrate_legacy_active_song_pick_key

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        payload = {
            "music_workspace_state": {
                "active_song": {
                    "title": "Perfect",
                    "genre": "Pop",
                    "artist": "Ed Sheeran",
                    "source_type": "catalog",
                }
            }
        }
        pk, result = migrate_legacy_active_song_pick_key({}, payload, song_picker_catalog=catalog)
        self.assertEqual(pk, perfect_pk)
        self.assertEqual(result, "migrated_title_genre_unique")

    def test_ambiguous_title_no_arbitrary_pick(self):
        from active_song_workspace_restore import migrate_legacy_active_song_pick_key

        catalog = {
            "Pop": {
                "A — X": {"title": "Same", "artist": "A", "key": "C", "sections": {}},
                "B — Y": {"title": "Same", "artist": "B", "key": "D", "sections": {}},
            }
        }
        payload = {"music_workspace_state": {"active_song": {"title": "Same", "source_type": "catalog"}}}
        pk, result = migrate_legacy_active_song_pick_key({}, payload, song_picker_catalog=catalog)
        self.assertEqual(pk, "")
        self.assertIn("ambiguous", result)

    def test_truly_empty_workspace_does_not_expect_catalog_song(self):
        from active_song_workspace_restore import workspace_envelope_expects_catalog_song

        self.assertFalse(workspace_envelope_expects_catalog_song({}))
        self.assertFalse(workspace_envelope_expects_catalog_song({"core": {}, "session": {}}))

    def test_defer_custom_does_not_block_catalog_core_pick(self):
        from music_persistent_state import apply_music_disk_state

        catalog = _mini_catalog()
        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        st = _FakeSt(
            {
                "active_music_source": "custom_progression",
                "cpl_active_progression": {"id": "x", "name": "Draft"},
            }
        )
        payload = {
            "core": {"pick_key": perfect_pk, "song": "Perfect"},
            "session": {
                "active_music_source": "custom_progression",
                "cpl_active_progression": {"id": "x", "name": "Draft"},
            },
        }
        apply_music_disk_state(
            st,
            payload,
            song_picker_catalog=catalog,
            song_library=catalog,
            authoritative_restore=True,
        )
        self.assertEqual(st.session_state.get(ACTIVE_CATALOG_PICK_KEY), perfect_pk)

    def test_inspect_envelope_identity_fields(self):
        from active_song_workspace_restore import inspect_workspace_envelope_identity

        perfect_pk = format_pick_key("Pop", "Perfect — Ed Sheeran")
        diag = inspect_workspace_envelope_identity(
            {
                "core": {"pick_key": perfect_pk},
                "music_workspace_state": {
                    "active_song": {"title": "Perfect", "genre": "Pop", "pick_key": perfect_pk}
                },
            }
        )
        self.assertTrue(diag["workspace_has_core_pick_key"])
        self.assertTrue(diag["workspace_has_active_song_pick_key"])
        self.assertEqual(diag["workspace_active_song_title"], "Perfect")
        self.assertEqual(diag["workspace_active_song_genre"], "Pop")


if __name__ == "__main__":
    unittest.main()
