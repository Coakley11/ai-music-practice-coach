"""Strict egress intentional save policy + coalesced workspace writes."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import suite_storage
from music_egress_config import (
    MUSIC_EGRESS_STRICT_KEY,
    is_intentional_user_save_reason,
    music_cloud_write_allowed,
)
from music_egress_strict_save import plan_strict_egress_cloud_write
from suite_user_persistence import _local_dirty_key


class StrictEgressPolicyTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def test_intentional_reasons_allowed_passive_blocked(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        self.assertTrue(music_cloud_write_allowed(save_reason="song_edit"))
        self.assertTrue(music_cloud_write_allowed(save_reason="instrument_change"))
        self.assertFalse(music_cloud_write_allowed(save_reason="autosave"))
        self.assertFalse(music_cloud_write_allowed(save_reason="widget_render"))

    def test_capo_widget_normalizes_to_intentional(self) -> None:
        self.assertTrue(is_intentional_user_save_reason("capo_widget"))


class HevenuStrictSaveRegressionTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _hevenu_state(self, rev: int) -> dict:
        return {
            "core": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "studio_page": "Creative",
            },
            "active_song_state": {
                "instrument": "Saxophone",
                "level": "Advanced",
                "focus": "Tone",
                "display_key": "C minor",
                "melody_variant": "Melody A",
            },
            "workspace_revision": rev,
        }

    def test_coalesced_edits_one_cloud_write_with_authoritative_confirmation(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        ss = {
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
        }
        st = MagicMock()
        st.session_state = ss
        rev = 3

        def build_state(_st: object) -> dict:
            return self._hevenu_state(rev)

        def stamp(_s: object, state: dict, **_kw: object) -> dict:
            out = dict(state)
            out["workspace_revision"] = rev + 1
            return out

        plan1 = plan_strict_egress_cloud_write(ss, save_reason="song_edit", payload_fp="aaa")
        self.assertTrue(plan1.defer_cloud_write)
        self.assertTrue(plan1.strict_egress_user_write_allowed)

        with patch("music_workspace_cloud_save._cloud_enabled", return_value=True), patch(
            "suite_user_persistence.save_user_state", return_value=True
        ), patch("music_persistent_state.stamp_music_payload_for_write", side_effect=stamp), patch(
            "suite_storage_config.cloud_storage_enabled", return_value=True
        ), patch("suite_storage_config.get_cloud_config", return_value=object()), patch(
            "suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")
        ), patch("suite_cloud_state._cloud_storage_app_id", return_value="music"), patch.object(
            suite_storage, "save_current_state"
        ), patch("suite_cloud_state._streamlit_session", return_value=ss), patch(
            "suite_cloud_state.session_page_summary", return_value=("Creative", "Hevenu")
        ):
            ok_defer = force_music_workspace_save(st, reason="song_edit", build_state=build_state)
            ok_final = force_music_workspace_save(
                st,
                reason="song_edit",
                build_state=build_state,
                bypass_strict_defer=True,
            )

        self.assertFalse(ok_defer)
        self.assertTrue(ok_final)
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertTrue(tx.get("strict_egress_user_write_allowed"))
        self.assertTrue(tx.get("cloud_write_succeeded"))
        self.assertTrue(tx.get("cloud_readback_matches"))
        self.assertTrue(tx.get("cloud_readback_authoritative"))
        self.assertTrue(tx.get("dirty_cleared_after_confirmed_save"))
        self.assertEqual(tx.get("cloud_write_count_for_transaction"), 1)
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))

    def test_unchanged_rerun_skips_cloud_write(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_egress_strict_save import workspace_payload_fingerprint

        ss: dict = {}
        state = self._hevenu_state(2)
        fp = workspace_payload_fingerprint(state)
        ss["_music_last_confirmed_cloud_fp"] = fp
        plan = plan_strict_egress_cloud_write(ss, save_reason="song_edit", payload_fp=fp, bypass_defer=True)
        self.assertTrue(plan.duplicate_write_skipped)
        self.assertFalse(plan.allow_cloud_write)

    def test_passive_autosave_zero_cloud_writes(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import music_autosave_if_changed

        ss = {"_music_workspace_blob_hydrated": True}
        st = MagicMock()
        st.session_state = ss
        with patch("music_workspace_cloud_save.force_music_workspace_save") as force_save:
            result = music_autosave_if_changed(st, build_state=lambda _s: self._hevenu_state(1))
        force_save.assert_not_called()
        self.assertTrue(result["skipped"])


if __name__ == "__main__":
    unittest.main()
