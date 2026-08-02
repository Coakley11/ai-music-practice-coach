"""Cloud save transaction + hydration diagnostics for music workspace."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from music_workspace_cloud_hydration import (
    collect_hydration_diagnostics,
    record_cloud_fetch_result,
    record_selected_payload_source,
)
from music_workspace_cloud_save import (
    collect_save_transaction_diagnostics,
    music_workspace_save_allowed,
    record_save_transaction,
)
from suite_user_persistence import _local_dirty_key


class MusicWorkspaceSaveGateTests(unittest.TestCase):
    def test_ephemeral_blocks_autosave_not_song_edit_with_real_song(self) -> None:
        ss = {
            "_music_default_song_ephemeral": True,
            "selected_song": {"pick_key": "Pop::Say — John Mayer"},
            "active_catalog_pick_key": "Pop::Say — John Mayer",
        }
        allowed, reason = music_workspace_save_allowed(ss, reason="autosave")
        self.assertFalse(allowed)
        self.assertEqual(reason, "ephemeral_default_song")

        allowed2, reason2 = music_workspace_save_allowed(ss, reason="song_edit")
        self.assertFalse(allowed2)
        self.assertEqual(reason2, "ephemeral_default_song_blocks_save")

        from music_persistent_state import clear_music_ephemeral_default_song

        clear_music_ephemeral_default_song(ss)
        ss["_music_workspace_blob_hydrated"] = True
        allowed3, reason3 = music_workspace_save_allowed(ss, reason="song_edit")
        self.assertTrue(allowed3)
        self.assertEqual(reason3, "")

    def test_hydration_blocks_autosave_not_user_page_change(self) -> None:
        ss = {}
        allowed, reason = music_workspace_save_allowed(ss, reason="autosave")
        self.assertFalse(allowed)
        self.assertEqual(reason, "hydration_not_finalized")

        allowed2, _ = music_workspace_save_allowed(ss, reason="page_change")
        self.assertTrue(allowed2)


class MusicCloudHydrationDiagTests(unittest.TestCase):
    def test_selected_payload_source_cloud(self) -> None:
        ss: dict = {}
        record_selected_payload_source(ss, source="cloud")
        self.assertEqual(ss["_music_cloud_payload_source"], "cloud")
        self.assertEqual(collect_hydration_diagnostics(ss)["selected_payload_source"], "cloud")

    def test_cloud_fetch_failed_not_success(self) -> None:
        ss: dict = {}
        record_cloud_fetch_result(
            ss,
            app_id="music",
            cloud_state={},
            cloud_ts=None,
            disk_state={"core": {}},
            disk_ts="2026-01-01T00:00:00Z",
            error="network_timeout",
        )
        diag = collect_hydration_diagnostics(ss)
        self.assertTrue(diag["cloud_fetch_attempted"])
        self.assertFalse(diag["cloud_fetch_succeeded"])
        self.assertTrue(diag["disk_payload_found"])


class ForceMusicWorkspaceSaveTests(unittest.TestCase):
    def _run_force_save(
        self,
        *,
        cloud_write_ok: bool,
        readback_state: dict | None,
        rev_before: int = 1,
    ) -> tuple[bool, dict]:
        from music_workspace_cloud_save import force_music_workspace_save

        ss = {
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
        }
        st = MagicMock()
        st.session_state = ss
        stamped: dict = {}

        def build_state(_st: object) -> dict:
            return {
                "core": {"studio_page": "Creative"},
                "music_workspace_state": {"workspace_revision": rev_before},
                "workspace_revision": rev_before,
            }

        def stamp(_st: object, state: dict, **_kw: object) -> dict:
            stamped.clear()
            stamped.update(state)
            stamped["workspace_revision"] = rev_before + 1
            ws = stamped.get("music_workspace_state")
            if isinstance(ws, dict):
                ws = dict(ws)
                ws["workspace_revision"] = rev_before + 1
                stamped["music_workspace_state"] = ws
            return stamped

        readback = readback_state

        def _load_cloud(*_a: object, **_k: object) -> tuple[dict, str]:
            payload = readback if readback is not None else dict(stamped)
            return payload, "2026-01-01T00:00:00Z"

        with patch("music_workspace_cloud_save._cloud_enabled", return_value=True), patch(
            "suite_user_persistence.save_user_state", return_value=True
        ), patch("music_egress_config.music_cloud_write_allowed", return_value=True), patch(
            "music_persistent_state.stamp_music_payload_for_write", side_effect=stamp
        ), patch("music_egress_config.skip_cloud_readback_after_write", return_value=False), patch(
            "music_persistent_state.save_music_cloud_session", return_value=cloud_write_ok
        ), patch(
            "suite_cloud_state.load_cloud_full_session",
            side_effect=_load_cloud,
        ), patch(
            "suite_cloud_state.session_page_summary", return_value=("Creative", "test")
        ):
            ok = force_music_workspace_save(st, reason="song_edit", build_state=build_state)
        return ok, collect_save_transaction_diagnostics(ss)

    def test_confirmed_cloud_save_clears_dirty(self) -> None:
        ok, tx = self._run_force_save(cloud_write_ok=True, readback_state=None)
        self.assertTrue(ok)
        self.assertTrue(tx.get("cloud_write_succeeded"))
        self.assertTrue(tx.get("cloud_readback_matches"))
        self.assertTrue(tx.get("dirty_cleared_after_confirmed_save"))
        self.assertGreater(tx.get("envelope_revision_after", 0), tx.get("envelope_revision_before", 0))

    def test_dirty_not_cleared_when_cloud_write_fails(self) -> None:
        ok, tx = self._run_force_save(cloud_write_ok=False, readback_state={})
        self.assertFalse(ok)
        self.assertFalse(tx.get("dirty_cleared_after_confirmed_save"))
        self.assertFalse(tx.get("cloud_write_succeeded"))

    def test_readback_mismatch_leaves_dirty(self) -> None:
        ok, tx = self._run_force_save(
            cloud_write_ok=True,
            readback_state={"core": {}, "workspace_revision": 1},
        )
        self.assertFalse(ok)
        self.assertFalse(tx.get("cloud_readback_matches"))
        self.assertFalse(tx.get("dirty_cleared_after_confirmed_save"))

    def test_disk_only_not_reported_as_cloud_success(self) -> None:
        from music_workspace_cloud_save import force_music_workspace_save

        ss = {"_music_workspace_blob_hydrated": True, _local_dirty_key("music"): True}
        st = MagicMock()
        st.session_state = ss

        with patch("music_workspace_cloud_save._cloud_enabled", return_value=True), patch(
            "suite_user_persistence.save_user_state", return_value=True
        ), patch("music_egress_config.music_cloud_write_allowed", return_value=True), patch(
            "music_persistent_state.stamp_music_payload_for_write",
            side_effect=lambda _s, state, **_: {**state, "workspace_revision": 2},
        ), patch("music_persistent_state.save_music_cloud_session", return_value=False):
            ok = force_music_workspace_save(
                st,
                reason="song_edit",
                build_state=lambda _s: {"core": {}, "workspace_revision": 1},
            )
        self.assertFalse(ok)
        self.assertFalse(st.session_state.get("_suite_persist_last_save_cloud"))


    def test_failed_cloud_save_marks_retry_dirty(self) -> None:
        from suite_user_persistence import _local_dirty_key

        ok, tx = self._run_force_save(cloud_write_ok=False, readback_state={})
        self.assertFalse(ok)
        self.assertTrue(tx.get("retry_required"))
        self.assertTrue(tx.get("dirty_after_failed_cloud_save"))
        self.assertFalse(tx.get("dirty_cleared_after_confirmed_save"))


if __name__ == "__main__":
    unittest.main()
