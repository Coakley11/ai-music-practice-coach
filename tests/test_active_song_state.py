"""Tests for canonical active song state (Phase C acceptance A–E)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from active_song_state import (
    ACTIVE_SONG_DIRTY_KEY,
    apply_active_song_source_state_from_ami,
    apply_cloud_active_song_state_if_allowed,
    clear_active_song_local_edit,
    commit_active_song_state_from_session,
    flush_active_song_edits,
    is_active_song_locally_dirty,
    mark_active_song_local_edit,
    prepare_active_song_context,
    write_canonical_active_song_state,
)
from instrument_transposition import (
    CHART_IN_INSTRUMENT_KEY_KEY,
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
    resolve_practice_keys,
)
from music_coach_context import apply_source_state_to_session, build_source_state
from music_persistent_state import apply_music_disk_state, build_music_disk_state
from song_catalog import format_pick_key
from songs.key_state import PENDING_DISPLAY_KEY
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

_PICK_KEY = format_pick_key("Pop", "Turn the Lights Back On — Billy Joel")
_SAMPLE = {
    "pick_key": _PICK_KEY,
    "display_key": "D Major",
    "instrument": "Guitar",
    "level": "Intermediate",
    "focus": "Chords",
    "practice_focus_section": "Chorus",
    "selected_song": {
        "pick_key": _PICK_KEY,
        "title": "Turn the Lights Back On",
        "artist": "Billy Joel",
    },
}


class TestActiveSongState(unittest.TestCase):
    def test_a_local_persist_prepare_preserves_edits(self) -> None:
        session: dict = {}
        write_canonical_active_song_state(session, _SAMPLE, reason="setup")
        session["display_key"] = "F Major"
        session[PENDING_DISPLAY_KEY] = "F Major"
        mark_active_song_local_edit(session)
        flush_active_song_edits(session, reason="song_edit")
        prepare_active_song_context(session)
        self.assertEqual(session["display_key"], "F Major")
        self.assertEqual(session["active_song_state"]["display_key"], "F Major")
        self.assertTrue(is_active_song_locally_dirty(session))

    def test_a_prepare_seeds_from_canonical(self) -> None:
        session = {"active_song_state": {**_SAMPLE, "last_write_reason": "cloud"}}
        prepare_active_song_context(session)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], _PICK_KEY)
        self.assertEqual(session["instrument"], "Guitar")
        self.assertEqual(session[PENDING_DISPLAY_KEY], "D Major")

    def test_b_cross_device_cloud_restore(self) -> None:
        session: dict = {"studio_page": "practice"}
        cloud = {
            "active_song_state": dict(_SAMPLE),
            "music_workspace_state": {"active_song": dict(_SAMPLE)},
        }
        self.assertTrue(apply_cloud_active_song_state_if_allowed(session, cloud))
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], _PICK_KEY)
        self.assertEqual(session["display_key"], "D Major")
        self.assertFalse(is_active_song_locally_dirty(session))

    def test_b_disk_blob_round_trip(self) -> None:
        st = MagicMock()
        st.session_state = {**_SAMPLE, ACTIVE_CATALOG_PICK_KEY: _PICK_KEY, SELECTED_SONG_STATE_KEY: _SAMPLE["selected_song"]}
        write_canonical_active_song_state(st.session_state, _SAMPLE, reason="setup")
        blob = build_music_disk_state(st)
        self.assertIn("active_song_state", blob)
        meta = blob.get("music_workspace_state") or {}
        self.assertEqual(meta.get("active_song", {}).get("display_key"), "D Major")

        st2 = MagicMock()
        st2.session_state = {}
        catalog = {
            "Pop": {
                "Turn the Lights Back On — Billy Joel": {
                    "title": "Turn the Lights Back On",
                    "artist": "Billy Joel",
                    "key": "C",
                }
            }
        }
        library = {"Pop": {"Turn the Lights Back On": catalog["Pop"]["Turn the Lights Back On — Billy Joel"]}}
        apply_music_disk_state(st2, blob, song_picker_catalog=catalog, song_library=library)
        ss = st2.session_state
        self.assertEqual(ss.get(ACTIVE_CATALOG_PICK_KEY), _PICK_KEY)
        self.assertEqual(ss.get("active_song_state", {}).get("display_key"), "D Major")

    def test_c_stale_cloud_blocked_when_locally_dirty(self) -> None:
        session = {**_SAMPLE, ACTIVE_CATALOG_PICK_KEY: _PICK_KEY, "display_key": "F Major"}
        mark_active_song_local_edit(session)
        cloud = {"active_song_state": dict(_SAMPLE)}
        self.assertFalse(apply_cloud_active_song_state_if_allowed(session, cloud))
        self.assertEqual(session["display_key"], "F Major")

    def test_d_navigation_does_not_clear_active_song(self) -> None:
        session = dict(_SAMPLE)
        write_canonical_active_song_state(session, _SAMPLE, reason="setup")
        session["studio_page"] = "backing"
        prepare_active_song_context(session)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], _PICK_KEY)

    def test_e_ami_return_restores_active_song(self) -> None:
        session: dict = {}
        source = {
            "source_page": "backing",
            "entity_params": {
                "pick_key": _PICK_KEY,
                "song_title": "Turn the Lights Back On",
                "song_artist": "Billy Joel",
            },
            "widget_params": {
                "display_key": "D Major",
                "instrument": "Guitar",
                "studio_page": "backing",
            },
        }
        apply_active_song_source_state_from_ami(session, source)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], _PICK_KEY)
        self.assertEqual(session["display_key"], "D Major")
        self.assertFalse(session.get(ACTIVE_SONG_DIRTY_KEY))

    def test_e_build_and_apply_source_state_round_trip(self) -> None:
        session = {**_SAMPLE, ACTIVE_CATALOG_PICK_KEY: _PICK_KEY}
        write_canonical_active_song_state(session, _SAMPLE, reason="setup")
        built = build_source_state("backing", session)
        self.assertEqual(built["entity_params"]["pick_key"], _PICK_KEY)
        self.assertEqual(built["widget_params"]["display_key"], "D Major")

        target: dict = {"display_key": "C Major"}
        apply_source_state_to_session(target, built, schedule_navigation=False)
        self.assertEqual(target["display_key"], "D Major")
        self.assertEqual(target["active_song_state"]["pick_key"], _PICK_KEY)

    def test_commit_autosave_does_not_mutate_display_key_widget(self) -> None:
        """Save build must not assign display_key after the widget exists (Streamlit conflict)."""
        session = {**dict(_SAMPLE), ACTIVE_CATALOG_PICK_KEY: _PICK_KEY}
        write_canonical_active_song_state(session, _SAMPLE, reason="setup")
        session["display_key"] = "Widget Key"
        commit_active_song_state_from_session(session, reason="autosave")
        self.assertEqual(session["display_key"], "Widget Key")
        self.assertEqual(session["active_song_state"]["display_key"], "D Major")

    def test_written_key_checkbox_prepare_and_cloud_restore(self) -> None:
        session = {
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Clarinet",
                CHART_IN_INSTRUMENT_KEY_KEY: True,
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Clarinet",
            }
        }
        prepare_active_song_context(session)
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY], "Clarinet")

        cloud = {
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Clarinet",
                CHART_IN_INSTRUMENT_KEY_KEY: True,
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Clarinet",
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Clarinet",
                    CHART_IN_INSTRUMENT_KEY_KEY: True,
                }
            },
        }
        phone: dict = {"instrument": "Piano"}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(phone, cloud))
        self.assertTrue(phone[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(phone["_written_key_mode_restored"], True)
        self.assertEqual(phone["_written_key_restore_source"], "cloud_restore")

    def test_commit_merges_live_written_key_from_widget(self) -> None:
        """Autosave commit must not drop checkbox when legacy canonical omits written key."""
        session = {
            **_SAMPLE,
            ACTIVE_CATALOG_PICK_KEY: _PICK_KEY,
            "instrument": "Saxophone",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
        }
        write_canonical_active_song_state(session, _SAMPLE, reason="legacy")
        self.assertNotIn(CHART_IN_INSTRUMENT_KEY_KEY, session["active_song_state"])
        commit_active_song_state_from_session(session, reason="autosave")
        self.assertTrue(session["active_song_state"][CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])

    def test_cloud_restore_workspace_written_key_overrides_stale_canonical_false(self) -> None:
        cloud = {
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Saxophone",
                CHART_IN_INSTRUMENT_KEY_KEY: False,
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Saxophone",
                    CHART_IN_INSTRUMENT_KEY_KEY: True,
                    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
                }
            },
        }
        phone: dict = {}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(phone, cloud))
        self.assertTrue(phone[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertTrue(phone["active_song_state"][CHART_IN_INSTRUMENT_KEY_KEY])

    def test_cloud_restore_backfills_written_key_from_workspace(self) -> None:
        cloud = {
            "active_song_state": {**_SAMPLE, "instrument": "Saxophone"},
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Saxophone",
                    CHART_IN_INSTRUMENT_KEY_KEY: True,
                    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
                }
            },
        }
        phone: dict = {}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(phone, cloud))
        self.assertTrue(phone[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertTrue(phone["active_song_state"][CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(phone["_written_key_mode_cloud"], True)

    def test_transposing_subtype_commit_and_cloud_restore(self) -> None:
        session = {
            **_SAMPLE,
            ACTIVE_CATALOG_PICK_KEY: _PICK_KEY,
            "instrument": "Saxophone",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
        }
        write_canonical_active_song_state(
            session,
            {**_SAMPLE, "instrument": "Saxophone"},
            reason="legacy",
        )
        commit_active_song_state_from_session(session, reason="autosave")
        self.assertEqual(
            session["active_song_state"][SELECTED_TRANSPOSING_INSTRUMENT_KEY],
            "Alto saxophone (Eb)",
        )
        self.assertTrue(session["active_song_state"][CHART_IN_INSTRUMENT_KEY_KEY])

        cloud = {
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Saxophone",
                "show_chart_in_instrument_key": None,
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Saxophone",
                    CHART_IN_INSTRUMENT_KEY_KEY: True,
                    SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
                }
            },
        }
        phone: dict = {}
        self.assertTrue(apply_cloud_active_song_state_if_allowed(phone, cloud))
        self.assertEqual(phone[SELECTED_TRANSPOSING_INSTRUMENT_KEY], "Alto saxophone (Eb)")
        self.assertTrue(phone[CHART_IN_INSTRUMENT_KEY_KEY])
        ctx = resolve_practice_keys(phone, "F", "Saxophone")
        self.assertEqual(ctx["chart_key_mode"], "written")
        self.assertEqual(ctx["chart_key"], "D")

    def test_authoritative_restore_clears_dirty_and_restores_written_key(self) -> None:
        """Stale active_song_state_dirty must not block cloud written-key receive."""
        blob = {
            "core": {
                "pick_key": _PICK_KEY,
                "display_key": "Db",
                "instrument": "Saxophone",
                "song": "Turn the Lights Back On",
                "artist": "Billy Joel",
            },
            "session": {
                CHART_IN_INSTRUMENT_KEY_KEY: True,
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
                ACTIVE_SONG_DIRTY_KEY: True,
            },
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Saxophone",
                "display_key": "Db",
                CHART_IN_INSTRUMENT_KEY_KEY: False,
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Saxophone",
                    "display_key": "Db",
                    "show_chart_in_instrument_key": True,
                    SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
                }
            },
        }
        st = MagicMock()
        st.session_state = {ACTIVE_SONG_DIRTY_KEY: True}
        catalog = {
            "Pop": {
                "Turn the Lights Back On — Billy Joel": {
                    "title": "Turn the Lights Back On",
                    "artist": "Billy Joel",
                    "key": "C",
                }
            }
        }
        library = {"Pop": {"Turn the Lights Back On": catalog["Pop"]["Turn the Lights Back On — Billy Joel"]}}
        apply_music_disk_state(
            st,
            blob,
            song_picker_catalog=catalog,
            song_library=library,
            authoritative_restore=True,
        )
        ss = st.session_state
        self.assertFalse(is_active_song_locally_dirty(ss))
        self.assertTrue(ss.get(CHART_IN_INSTRUMENT_KEY_KEY))
        self.assertEqual(ss.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY), "Tenor saxophone (Bb)")
        prepare_active_song_context(ss)
        self.assertTrue(ss.get(CHART_IN_INSTRUMENT_KEY_KEY))
        self.assertTrue(ss.get("active_song_state", {}).get(CHART_IN_INSTRUMENT_KEY_KEY))

    def test_disk_restore_applies_deferred_written_key_from_session_extra(self) -> None:
        """Cloud session extra carries written-key True even when canonical meta is stale False."""
        blob = {
            "core": {
                "pick_key": _PICK_KEY,
                "display_key": "Db",
                "instrument": "Saxophone",
                "song": "Turn the Lights Back On",
                "artist": "Billy Joel",
            },
            "session": {
                CHART_IN_INSTRUMENT_KEY_KEY: True,
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            },
            "active_song_state": {
                **_SAMPLE,
                "instrument": "Saxophone",
                "display_key": "Db",
                CHART_IN_INSTRUMENT_KEY_KEY: False,
                SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": _PICK_KEY,
                    "instrument": "Saxophone",
                    "display_key": "Db",
                    "show_chart_in_instrument_key": False,
                    SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
                }
            },
        }
        st = MagicMock()
        st.session_state = {}
        catalog = {
            "Pop": {
                "Turn the Lights Back On — Billy Joel": {
                    "title": "Turn the Lights Back On",
                    "artist": "Billy Joel",
                    "key": "C",
                }
            }
        }
        library = {"Pop": {"Turn the Lights Back On": catalog["Pop"]["Turn the Lights Back On — Billy Joel"]}}
        apply_music_disk_state(
            st,
            blob,
            song_picker_catalog=catalog,
            song_library=library,
            authoritative_restore=True,
        )
        ss = st.session_state
        self.assertTrue(ss.get(CHART_IN_INSTRUMENT_KEY_KEY))
        self.assertTrue(ss.get("active_song_state", {}).get(CHART_IN_INSTRUMENT_KEY_KEY))
        self.assertEqual(ss.get("_written_key_restore_source"), "receive_finalize")

    def test_written_key_checkbox_disk_round_trip(self) -> None:
        st = MagicMock()
        st.session_state = {
            **_SAMPLE,
            ACTIVE_CATALOG_PICK_KEY: _PICK_KEY,
            SELECTED_SONG_STATE_KEY: _SAMPLE["selected_song"],
            "instrument": "Clarinet",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Clarinet",
        }
        flush_active_song_edits(st.session_state, reason="song_edit")
        blob = build_music_disk_state(st)
        self.assertTrue(blob["active_song_state"][CHART_IN_INSTRUMENT_KEY_KEY])
        ws = blob.get("music_workspace_state") or {}
        self.assertTrue(ws.get("active_song", {}).get(CHART_IN_INSTRUMENT_KEY_KEY))

        st2 = MagicMock()
        st2.session_state = {}
        catalog = {
            "Pop": {
                "Turn the Lights Back On — Billy Joel": {
                    "title": "Turn the Lights Back On",
                    "artist": "Billy Joel",
                    "key": "C",
                }
            }
        }
        library = {"Pop": {"Turn the Lights Back On": catalog["Pop"]["Turn the Lights Back On — Billy Joel"]}}
        apply_music_disk_state(st2, blob, song_picker_catalog=catalog, song_library=library)
        ss = st2.session_state
        self.assertTrue(ss.get(CHART_IN_INSTRUMENT_KEY_KEY))
        self.assertTrue(ss.get("active_song_state", {}).get(CHART_IN_INSTRUMENT_KEY_KEY))

    def test_song_edit_bypasses_post_restore_block(self) -> None:
        from suite_user_persistence import _cloud_autosave_blocked_reason

        st = MagicMock()
        st.session_state = {}
        state = {"active_song_state": dict(_SAMPLE)}
        self.assertIsNone(_cloud_autosave_blocked_reason(st, "music", state, save_reason="song_edit"))


if __name__ == "__main__":
    unittest.main()
