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
    def test_core_fallback_infers_only_catalog_and_keeps_typed_identity(self):
        from active_song_state import _active_song_context_from_blob

        pick = format_pick_key("Pop", "Perfect — Ed Sheeran")
        context = _active_song_context_from_blob({"core": {"pick_key": pick}})
        self.assertEqual(context["music_source"], "catalog_song")
        for core in ({"pick_key": "composition::piece"}, {"song": "Unidentified song"}):
            self.assertNotEqual(_active_song_context_from_blob({"core": core})["music_source"], "catalog_song")
        typed = {"pick_key": "custom::trial", "music_source": "custom_progression"}
        context = _active_song_context_from_blob({"core": {"pick_key": pick}, "active_song_state": typed})
        self.assertEqual(context["pick_key"], "custom::trial")
        self.assertEqual(context["music_source"], "custom_progression")

    def test_legacy_catalog_and_custom_reopen_preserve_each_saved_source(self):
        from copy import deepcopy
        from custom_progression_lab import default_active_progression
        from music_persistent_state import apply_music_disk_state
        from songs.practice_key_state import get_practice_concert_key

        catalog = _mini_catalog()
        pick = format_pick_key("Pop", "Perfect — Ed Sheeran")
        custom_pick = "custom::trial"
        trial = default_active_progression()
        trial.update(id="trial", name="Trial Song", original_key_center="C", user_locked_home_key=True)
        trial["original_sections"]["Verse"] = [{"chord": "Cmaj7", "bars": 2}]
        library = {"Trial Song": trial}
        extra = {
            "active_music_source": "custom_progression", "cpl_active_progression": trial,
            "cpl_saved_progressions": library, "cpl_last_display_key": "Eb",
            "practice_key_by_source": {pick: "Bb", custom_pick: "Eb"},
            "practice_key_user_override_picks": [pick, custom_pick],
        }
        for active, source, key, title in (
            (pick, "catalog_song", "Bb", "Perfect"),
            (custom_pick, "custom_progression", "Eb", "Trial Song"),
            (pick, "catalog_song", "Bb", "Perfect"),
        ):
            with self.subTest(active=active, key=key):
                # A reopened workspace is a new session. Mid-session reapply
                # correctly protects already projected local controls instead.
                st = _FakeSt(deepcopy(extra))
                payload = {"core": {"pick_key": active, "song": title, "display_key": key, "instrument": "Piano"},
                           "session": deepcopy(extra)}
                apply_music_disk_state(st, payload, song_picker_catalog=catalog,
                                       song_library=catalog, authoritative_restore=True)
                self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], active)
                self.assertEqual(st.session_state["active_music_source"], source)
                self.assertEqual(st.session_state["display_key"], key)
                self.assertEqual(st.session_state[SELECTED_SONG_STATE_KEY]["title"], title)
                self.assertEqual(st.session_state["cpl_saved_progressions"], library)
                self.assertEqual(get_practice_concert_key(st.session_state, pick_key=pick), "Bb")
                self.assertEqual(get_practice_concert_key(st.session_state, pick_key=custom_pick), "Eb")

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
