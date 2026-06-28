"""Multitrack mixer state persistence tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_multitrack_catalog import apply_catalog_multitrack_to_session, save_multitrack_session_with_notes
from media_persistence import load_media_catalog
from media_state import migrate_multitrack_session
from multitrack_history import apply_multitrack_history, build_multitrack_history_payload
from multitrack_mixer_state import (
    commit_all_multitrack_mixer_widgets,
    merge_mt_track_controls,
    prepare_multitrack_mixer_widgets,
    resolve_slot_control,
)
from multitrack_slots import MULTITRACK_SLOTS
from studio_page_persistence import apply_page_snapshot, capture_page_snapshot


class TestMultitrackMixerPersistence(unittest.TestCase):
    def _two_layer_session(self) -> dict:
        return {
            "mt_tracks": {
                slot: (b"guitar" if slot == "Guitar" else b"piano" if slot == "Piano / Keys" else None)
                for slot in MULTITRACK_SLOTS
            },
            "mt_track_filenames": {"Guitar": "guitar.wav", "Piano / Keys": "piano.wav"},
            "mt_name_Guitar": "Lead",
            "mt_name_Piano / Keys": "Comp",
            "mt_vol_Guitar": 0.55,
            "mt_vol_Piano / Keys": 0.65,
            "mt_delay_Guitar": 0.1,
            "mt_delay_Piano / Keys": -0.2,
            "mt_mute_Guitar": True,
            "mt_mute_Piano / Keys": False,
            "mt_solo_Guitar": False,
            "mt_solo_Piano / Keys": True,
            "mt_track_controls": {
                "Guitar": {"volume": 0.55, "mute": True, "solo": False, "delay": 0.1},
                "Piano / Keys": {"volume": 0.65, "mute": False, "solo": True, "delay": -0.2},
            },
            "active_song_title": "Say",
        }

    def test_prepare_seeds_missing_keys_without_clobbering_user_edits(self) -> None:
        session = self._two_layer_session()
        commit_all_multitrack_mixer_widgets(session)
        session["mt_vol_Guitar"] = 0.2
        session["mt_mute_Guitar"] = False
        prepare_multitrack_mixer_widgets(session)
        self.assertEqual(session["mt_vol_Guitar"], 0.2)
        self.assertFalse(session["mt_mute_Guitar"])
        from multitrack_mixer_state import sync_mixer_widgets_from_canonical

        sync_mixer_widgets_from_canonical(session)
        self.assertEqual(session["mt_vol_Guitar"], 0.55)
        self.assertTrue(session["mt_mute_Guitar"])

    def test_page_snapshot_restores_mute_solo_after_refresh(self) -> None:
        session = self._two_layer_session()
        session["studio_page"] = "multitrack"
        commit_all_multitrack_mixer_widgets(session)
        snap = capture_page_snapshot(session, "multitrack")
        fresh: dict = {"studio_page": "multitrack"}
        apply_page_snapshot(fresh, snap)
        self.assertTrue(fresh["mt_mute_Guitar"])
        self.assertTrue(fresh["mt_solo_Piano / Keys"])
        self.assertTrue(fresh["mt_track_controls"]["Guitar"]["mute"])

    def test_transport_monitor_persist_in_snapshot(self) -> None:
        session = self._two_layer_session()
        session.update({"studio_page": "multitrack", "mt_use_backing_monitor": False})
        snap = capture_page_snapshot(session, "multitrack")
        fresh: dict = {"studio_page": "multitrack"}
        apply_page_snapshot(fresh, snap)
        self.assertFalse(fresh["mt_use_backing_monitor"])

    def test_transport_toggles_persist_in_snapshot(self) -> None:
        session = self._two_layer_session()
        session.update(
            {
                "studio_page": "multitrack",
                "mt_loop_backing": False,
                "mt_metronome_playback": True,
            }
        )
        snap = capture_page_snapshot(session, "multitrack")
        fresh: dict = {"studio_page": "multitrack"}
        apply_page_snapshot(fresh, snap)
        self.assertFalse(fresh["mt_loop_backing"])
        self.assertTrue(fresh["mt_metronome_playback"])

    def test_transport_fields_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._two_layer_session()
            session["mt_loop_backing"] = False
            session["mt_metronome_playback"] = True
            session["mt_use_backing_monitor"] = False
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_multitrack_catalog.persist_track_audio", MagicMock(return_value={"ok": True, "playback_status": "playable"})):
                                ok, mid, err = save_multitrack_session_with_notes(
                                    session,
                                    project_name="Transport test",
                                    song_title="Say",
                                )
                                self.assertTrue(ok, err)
                                catalog = load_media_catalog(st=None)
                                row = migrate_multitrack_session(catalog["multitrack_sessions"][0])
                                phone: dict = {}
                                with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (b"layer", "")):
                                    ok2, _msg = apply_catalog_multitrack_to_session(phone, row, load_audio=False)
                                    self.assertTrue(ok2)
                                    self.assertFalse(phone["mt_loop_backing"])
                                    self.assertTrue(phone["mt_metronome_playback"])
                                    self.assertFalse(phone["mt_use_backing_monitor"])

    def test_page_snapshot_restores_mixer_controls(self) -> None:
        session = self._two_layer_session()
        session["studio_page"] = "multitrack"
        snap = capture_page_snapshot(session, "multitrack")
        fresh: dict = {"studio_page": "multitrack"}
        apply_page_snapshot(fresh, snap)
        self.assertEqual(fresh["mt_track_controls"]["Guitar"]["volume"], 0.55)
        self.assertTrue(fresh["mt_track_controls"]["Piano / Keys"]["solo"])
        self.assertTrue(fresh["mt_mute_Guitar"])

    def test_snapshot_merge_prefers_live_controls(self) -> None:
        live = {"Guitar": {"volume": 0.33, "mute": True, "solo": False, "delay": 0.0}}
        snap = {"Guitar": {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0}}
        merged = merge_mt_track_controls(snap, live)
        self.assertEqual(merged["Guitar"]["volume"], 0.33)
        self.assertTrue(merged["Guitar"]["mute"])

    def test_history_payload_excludes_empty_slots(self) -> None:
        session = self._two_layer_session()
        payload, err = build_multitrack_history_payload(session, project_name="Two layers", song_title="Say")
        self.assertFalse(err)
        assert payload is not None
        self.assertEqual(len(payload["tracks"]), 2)
        slots = {row["slot"] for row in payload["tracks"]}
        self.assertEqual(slots, {"Guitar", "Piano / Keys"})
        self.assertTrue(payload["track_controls"]["Guitar"]["mute"])
        self.assertTrue(payload["track_controls"]["Piano / Keys"]["solo"])

    def test_apply_history_restores_widget_keys(self) -> None:
        session: dict = {}
        payload, _err = build_multitrack_history_payload(self._two_layer_session(), project_name="Two layers")
        assert payload is not None
        apply_multitrack_history(session, payload)
        self.assertEqual(session["mt_vol_Guitar"], 0.55)
        self.assertTrue(session["mt_mute_Guitar"])
        self.assertTrue(session["mt_solo_Piano / Keys"])

    def test_save_and_reload_mixer_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media_catalog.json"

            def _fake_path(*, st=None):
                return path

            session = self._two_layer_session()
            with patch("media_persistence._local_path", _fake_path):
                with patch("media_persistence._resolve_workspace_id", lambda *, st=None: "daniel"):
                    with patch("media_persistence._load_cloud_catalog", lambda *, st=None: ({}, None)):
                        with patch("media_persistence._save_cloud_catalog", lambda catalog, *, st=None: (True, "")):
                            with patch("media_multitrack_catalog.persist_track_audio", MagicMock(return_value={"ok": True, "playback_status": "playable"})):
                                ok, mid, err = save_multitrack_session_with_notes(
                                    session,
                                    project_name="Two layers",
                                    song_title="Say",
                                )
                                self.assertTrue(ok, err)
                                catalog = load_media_catalog(st=None)
                                row = migrate_multitrack_session(catalog["multitrack_sessions"][0])
                                guitar = next(t for t in row["tracks"] if t["slot"] == "Guitar")
                                piano = next(t for t in row["tracks"] if t["slot"] == "Piano / Keys")
                                self.assertTrue(guitar["analysis_summary"]["mute"])
                                self.assertTrue(piano["analysis_summary"]["solo"])
                                self.assertEqual(guitar["analysis_summary"]["volume"], 0.55)

                                phone: dict = {}
                                with patch("media_multitrack_catalog.load_track_audio", lambda track, session=None, st=None: (b"layer", "")):
                                    ok2, _msg = apply_catalog_multitrack_to_session(phone, row, load_audio=False)
                                    self.assertTrue(ok2)
                                    self.assertEqual(phone["mt_vol_Guitar"], 0.55)
                                    self.assertTrue(phone["mt_mute_Guitar"])
                                    self.assertTrue(phone["mt_solo_Piano / Keys"])

    def test_legacy_layer_name_controls_migrate_to_slot(self) -> None:
        session = {
            "mt_tracks": {"Guitar": b"x", **{slot: None for slot in MULTITRACK_SLOTS if slot != "Guitar"}},
            "mt_name_Guitar": "Lead",
            "mt_track_controls": {"Lead": {"volume": 0.42, "mute": True, "solo": False, "delay": 0.0}},
        }
        ctrl = resolve_slot_control(session, "Guitar", layer_name="Lead")
        self.assertEqual(ctrl["volume"], 0.42)
        self.assertTrue(ctrl["mute"])
        self.assertIn("Guitar", session["mt_track_controls"])


if __name__ == "__main__":
    unittest.main()
