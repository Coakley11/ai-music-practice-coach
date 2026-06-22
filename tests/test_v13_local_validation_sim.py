"""Programmatic one-device validation sim for music-state-write-gate-v13.

Covers checklist items 3–5, 11–12, 14–15 where state logic can be exercised
without a live Streamlit browser session.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from song_catalog import format_pick_key
from music_persistence_trace import MUSIC_PERSIST_DEPLOY_VERSION
from music_restore_phase import complete_music_restore_phase, music_restore_phase_complete
from music_state_writes import WriteOrigin, guarded_session_set, may_write_contested
from songs.music_source import (
    SONG_PICKER_SOURCE_CATALOG,
    USER_CATALOG_SOURCE_CHOICE_KEY,
    custom_progression_is_active,
    reconcile_music_picker_source_widget,
    set_catalog_source,
    set_custom_source,
)
from songs.state import ACTIVE_CATALOG_PICK_KEY, apply_pick_key, sync_matching_song_dropdown_before_widget


def _catalog() -> dict:
    return {
        "pop": {
            "Stay — The Kid LAROI & Justin Bieber": {
                "title": "Stay",
                "artist": "The Kid LAROI & Justin Bieber",
                "key": "C",
            },
            "Man in the Mirror — Michael Jackson": {
                "title": "Man in the Mirror",
                "artist": "Michael Jackson",
                "key": "G",
            },
        }
    }


STAY = format_pick_key("pop", "Stay — The Kid LAROI & Justin Bieber")
MIRROR = format_pick_key("pop", "Man in the Mirror — Michael Jackson")


class TestV13DeployMarker(unittest.TestCase):
    def test_deploy_marker_v13(self) -> None:
        self.assertEqual(MUSIC_PERSIST_DEPLOY_VERSION, "music-persistence-restore-v16")


class TestV13RestorePhase(unittest.TestCase):
    def test_restore_phase_done_after_startup_complete(self) -> None:
        ss: dict = {"_suite_persist_restore_applied": True, ACTIVE_CATALOG_PICK_KEY: MIRROR}
        complete_music_restore_phase(ss)
        self.assertTrue(music_restore_phase_complete(ss))


class TestV13SongChangeAndSnapBack(unittest.TestCase):
    @patch("songs.state.persist_music_local_state")
    @patch("songs.music_source.on_active_song_identity_changed")
    def test_user_song_change_from_stay_to_mirror(self, _identity, _persist) -> None:
        catalog = _catalog()
        st = MagicMock()
        st.session_state = {
            ACTIVE_CATALOG_PICK_KEY: STAY,
            "selected_song": {
                "pick_key": STAY,
                "title": "Stay",
                "artist": "The Kid LAROI & Justin Bieber",
                "genre": "pop",
                "key": "C",
            },
            "_LAST_PICK_KEY": STAY,
        }
        complete_music_restore_phase(st.session_state)
        apply_pick_key(st, MIRROR, catalog, origin="user", persist=False)
        self.assertEqual(st.session_state[ACTIVE_CATALOG_PICK_KEY], MIRROR)

    def test_default_stay_blocked_after_user_mirror(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: MIRROR}
        complete_music_restore_phase(ss)
        ok = guarded_session_set(
            ss,
            ACTIVE_CATALOG_PICK_KEY,
            STAY,
            origin=WriteOrigin.DEFAULT_STAMP,
            writer="test_default",
        )
        self.assertFalse(ok)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], MIRROR)

    def test_dropdown_does_not_snap_to_stay_when_filtered(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: MIRROR, "matching_song_dropdown": STAY}
        st = MagicMock()
        st.session_state = ss
        options = [STAY]
        active = sync_matching_song_dropdown_before_widget(
            st, options, STAY, song_picker_catalog=_catalog()
        )
        self.assertEqual(active, MIRROR)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], MIRROR)


class TestV13CatalogCustomToggle(unittest.TestCase):
    def test_catalog_custom_catalog_after_phase(self) -> None:
        ss = {
            ACTIVE_CATALOG_PICK_KEY: MIRROR,
            "song_picker_active_source": SONG_PICKER_SOURCE_CATALOG,
            "active_music_source": "catalog_song",
        }
        complete_music_restore_phase(ss)
        set_custom_source(ss)
        self.assertTrue(custom_progression_is_active(ss))
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        reconcile_music_picker_source_widget(ss)
        self.assertEqual(ss["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)
        set_catalog_source(ss)
        ss[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        reconcile_music_picker_source_widget(ss)
        self.assertEqual(ss["song_picker_active_source"], SONG_PICKER_SOURCE_CATALOG)


class TestV13GlobalControlsPreserved(unittest.TestCase):
    def test_canonical_blocked_overwrites_instrument_after_user_state(self) -> None:
        ss = {"instrument": "Guitar", "level": "Intermediate", "focus": "Scales"}
        complete_music_restore_phase(ss)
        self.assertFalse(may_write_contested(ss, WriteOrigin.CANONICAL, "instrument"))
        ok = guarded_session_set(
            ss, "instrument", "Piano", origin=WriteOrigin.CANONICAL, writer="prepare_active"
        )
        self.assertFalse(ok)
        self.assertEqual(ss["instrument"], "Guitar")


class TestSplitStateReconcile(unittest.TestCase):
    def test_reconcile_unifies_selected_and_active(self) -> None:
        from song_catalog import format_pick_key
        from songs.state import reconcile_active_song_identity

        mirror = format_pick_key("pop", "Man in the Mirror — Michael Jackson")
        stay = format_pick_key("pop", "Stay — The Kid LAROI & Justin Bieber")
        catalog = {
            "pop": {
                "Man in the Mirror — Michael Jackson": {
                    "title": "Man in the Mirror",
                    "artist": "Michael Jackson",
                    "key": "G",
                },
                "Stay — The Kid LAROI & Justin Bieber": {
                    "title": "Stay",
                    "artist": "The Kid LAROI & Justin Bieber",
                    "key": "C",
                },
            }
        }
        ss = {
            ACTIVE_CATALOG_PICK_KEY: stay,
            "selected_song": {
                "pick_key": mirror,
                "title": "Man in the Mirror",
                "artist": "Michael Jackson",
                "genre": "pop",
                "key": "G",
            },
            "matching_song_dropdown": mirror,
        }
        master = reconcile_active_song_identity(ss, catalog)
        self.assertEqual(master, mirror)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], mirror)
        self.assertEqual(ss["selected_song"]["pick_key"], mirror)
        self.assertEqual(ss["active_song_title"], "Man in the Mirror")


class TestV13BackingTransport(unittest.TestCase):
    def test_stop_returns_stopped_and_editable_bpm(self) -> None:
        from backing_track_state import (
            commit_backing_transport_from_session,
            prepare_backing_transport_for_session,
        )

        ss = {
            "_backing_autoplay": True,
            "backing_transport_status": "playing",
            "backing_track_bpm": 120,
            "backing_track_state": {
                "backing_track_bpm": 120,
                "backing_autoplay": True,
                "backing_transport_status": "playing",
            },
        }
        ss["_backing_autoplay"] = False
        ss["backing_transport_status"] = "stopped"
        commit_backing_transport_from_session(ss, reason="stop")
        self.assertFalse(ss["_backing_autoplay"])
        self.assertEqual(ss["backing_transport_status"], "stopped")
        meta = ss["backing_track_state"]
        self.assertFalse(meta.get("backing_autoplay"))
        self.assertEqual(meta.get("backing_transport_status"), "stopped")

        ss2 = {"backing_track_state": dict(meta), "backing_track_bpm": 120}
        prepare_backing_transport_for_session(ss2)
        self.assertFalse(ss2["_backing_autoplay"])
        self.assertEqual(ss2["backing_transport_status"], "stopped")

        ss3 = {
            "backing_track_state": {
                "backing_autoplay": True,
                "backing_transport_status": "playing",
            }
        }
        prepare_backing_transport_for_session(ss3)
        self.assertFalse(ss3["_backing_autoplay"])
        self.assertEqual(ss3["backing_transport_status"], "stopped")

        ss4 = {
            "_last_backing_wav": b"RIFF",
            "backing_transport_status": "ready",
            "_backing_transport_user_stopped": True,
        }
        prepare_backing_transport_for_session(ss4)
        self.assertEqual(ss4["backing_transport_status"], "stopped")

        ss5 = {
            "_last_backing_wav": b"RIFF",
            "backing_transport_status": "ready",
        }
        prepare_backing_transport_for_session(ss5)
        self.assertEqual(ss5["backing_transport_status"], "ready")

        ss6 = {"_backing_play_request": True, "_backing_autoplay": False}
        prepare_backing_transport_for_session(ss6)
        self.assertTrue(ss6["_backing_autoplay"])
        self.assertEqual(ss6["backing_transport_status"], "playing")


class TestV13RebootRestoreSim(unittest.TestCase):
    def test_reboot_restores_mirror_not_stay(self) -> None:
        """Simulate: cloud restore applied → phase complete → default blocked."""
        ss = {
            "_suite_persist_restore_applied": True,
            ACTIVE_CATALOG_PICK_KEY: MIRROR,
            "selected_song": {
                "pick_key": MIRROR,
                "title": "Man in the Mirror",
                "artist": "Michael Jackson",
                "genre": "pop",
                "key": "G",
            },
            "instrument": "Guitar",
            "backing_track_bpm": 108,
        }
        complete_music_restore_phase(ss)
        blocked = guarded_session_set(
            ss, ACTIVE_CATALOG_PICK_KEY, STAY, origin=WriteOrigin.DEFAULT_STAMP, writer="ensure_master"
        )
        self.assertFalse(blocked)
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], MIRROR)
        self.assertEqual(ss["instrument"], "Guitar")

    def test_debug_trace_records_blocked_canonical_write(self) -> None:
        ss = {ACTIVE_CATALOG_PICK_KEY: MIRROR}
        complete_music_restore_phase(ss)
        guarded_session_set(
            ss, ACTIVE_CATALOG_PICK_KEY, STAY, origin=WriteOrigin.CANONICAL, writer="write_canonical"
        )
        trace = ss.get("_music_state_write_trace")
        self.assertIsInstance(trace, list)
        blocked = [e for e in trace if e.get("blocked")]
        self.assertTrue(blocked)
        self.assertEqual(blocked[-1].get("key"), ACTIVE_CATALOG_PICK_KEY)


if __name__ == "__main__":
    unittest.main()
