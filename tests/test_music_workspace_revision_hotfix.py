"""Regression tests: canonical revision advancement for strict egress saves."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import suite_storage
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_egress_strict_save import (
    last_confirmed_cloud_fingerprint,
    plan_strict_egress_cloud_write,
    workspace_payload_fingerprint,
)
from music_strict_egress_transaction import note_passive_autosave_cloud_skip
from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint
from suite_cloud_state import CloudSaveResult
from suite_user_persistence import _local_dirty_key


class CanonicalRevisionHotfixTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _hevenu(self, rev: int, *, page: str = "Creative") -> dict:
        return {
            "core": {
                "pick_key": "Traditional::Hevenu Shalom Aleichem",
                "studio_page": page,
            },
            "active_song_state": {
                "instrument": "Saxophone",
                "level": "Advanced",
                "focus": "Tone",
                "display_key": "C minor",
            },
            "music_workspace_state": {
                "workspace_revision": rev,
                "studio_page": page,
                "updated_at": "2026-01-01T00:00:00Z",
            },
            "workspace_revision": rev,
        }

    def _save_patches(self, ss: dict, *, cloud_ok: bool, cloud_rev: int):
        stack = ExitStack()

        def _save_cloud(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            ss["_suite_last_cloud_save_result"] = CloudSaveResult(
                success=cloud_ok,
                save_cloud_full_session_return_value=cloud_ok,
                cloud_upsert_attempted=True,
                cloud_upsert_succeeded=cloud_ok,
                supabase_response_status=200 if cloud_ok else 500,
                cloud_payload_revision=cloud_rev,
            ).to_diag()
            return CloudSaveResult(
                success=cloud_ok,
                save_cloud_full_session_return_value=cloud_ok,
                cloud_upsert_attempted=True,
                cloud_upsert_succeeded=cloud_ok,
                supabase_response_status=200 if cloud_ok else 500,
                cloud_payload_revision=cloud_rev,
            )

        for ctx in (
            patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
            patch("suite_user_persistence.save_user_state", return_value=True),
            patch("music_persistent_state.stamp_music_payload_for_write", side_effect=lambda _s, st, **_: st),
            patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            patch("suite_storage_config.get_cloud_config", return_value=object()),
            patch("suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")),
            patch("suite_cloud_state._cloud_storage_app_id", return_value="music"),
            patch.object(suite_storage, "save_current_state"),
            patch("suite_cloud_state._streamlit_session", return_value=ss),
            patch("suite_cloud_state.session_page_summary", return_value=("Creative", "Hevenu")),
            patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud),
            patch("music_egress_config.skip_cloud_readback_after_write", return_value=True),
            patch(
                "music_egress_strict_save.strict_post_save_confirmation_uses_authoritative_upsert",
                return_value=True,
            ),
        ):
            stack.enter_context(ctx)
        return stack

    def test_a_changed_payload_dirty_false_page_change_advances_revision(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        rev = 107
        practice = self._hevenu(rev, page="Practice")
        confirmed_fp = workspace_canonical_content_fingerprint(practice)
        ss = {
            "_music_workspace_blob_hydrated": True,
            "_music_last_confirmed_cloud_fp": confirmed_fp,
            "_music_last_confirmed_cloud_revision": rev,
            "_suite_workspace_revision": rev - 1,
            "_suite_applied_workspace_revision": rev,
            "_suite_cloud_workspace_revision": rev,
        }
        st = MagicMock()
        st.session_state = ss
        creative = self._hevenu(rev, page="Creative")

        plan = plan_strict_egress_cloud_write(ss, save_reason="page_change", payload_fp=workspace_payload_fingerprint(creative))
        self.assertTrue(plan.payload_changed_since_last_confirmed_save)

        with self._save_patches(ss, cloud_ok=True, cloud_rev=108):
            ok = force_music_workspace_save(
                st,
                reason="page_change",
                build_state=lambda _s: creative,
            )

        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertTrue(ok, tx)
        self.assertEqual(tx.get("envelope_revision_before"), rev)
        self.assertEqual(tx.get("envelope_revision_after"), 108)
        self.assertTrue(tx.get("revision_advanced"))
        self.assertTrue(tx.get("cloud_confirmed"))
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))
        diag = ss.get("_suite_last_cloud_save_result") or {}
        self.assertEqual(diag.get("cloud_payload_revision"), 108)

    def test_b_same_payload_later_is_duplicate_skip_preserves_cloud(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        rev = 108
        state = self._hevenu(rev, page="Creative")
        fp = workspace_canonical_content_fingerprint(state)
        ss = {
            "_music_workspace_blob_hydrated": True,
            "_music_last_confirmed_cloud_fp": fp,
            "_music_last_confirmed_cloud_revision": rev,
            "_suite_persist_last_save_cloud": True,
        }
        st = MagicMock()
        st.session_state = ss

        with self._save_patches(ss, cloud_ok=True, cloud_rev=rev):
            ok = force_music_workspace_save(st, reason="song_edit", build_state=lambda _s: state)

        self.assertTrue(ok)
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertTrue(tx.get("duplicate_write_skipped") or tx.get("strict_egress_plan_action") == "duplicate_skip")
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))
        self.assertFalse(tx.get("cloud_write_attempted"))

    def test_c_new_content_advances_to_next_revision(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        rev = 108
        base = self._hevenu(rev, page="Creative")
        fp = workspace_canonical_content_fingerprint(base)
        ss = {
            "_music_workspace_blob_hydrated": True,
            "_music_last_confirmed_cloud_fp": fp,
            "_music_last_confirmed_cloud_revision": rev,
            "_suite_persist_last_save_cloud": True,
        }
        st = MagicMock()
        st.session_state = ss
        changed = self._hevenu(rev, page="Creative")
        changed["active_song_state"] = {**changed["active_song_state"], "focus": "Articulation"}

        with self._save_patches(ss, cloud_ok=True, cloud_rev=109):
            ok = force_music_workspace_save(st, reason="song_edit", build_state=lambda _s: changed)

        self.assertTrue(ok)
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertEqual(tx.get("envelope_revision_after"), 109)

    def test_d_failed_write_retries_same_revision(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        from music_workspace_cloud_save import force_music_workspace_save

        rev = 107
        state = self._hevenu(rev, page="Practice")
        confirmed_fp = workspace_canonical_content_fingerprint(state)
        creative = self._hevenu(rev, page="Creative")
        ss = {
            "_music_workspace_blob_hydrated": True,
            _local_dirty_key("music"): True,
            "_music_last_confirmed_cloud_fp": confirmed_fp,
            "_music_last_confirmed_cloud_revision": rev,
        }
        st = MagicMock()
        st.session_state = ss

        with self._save_patches(ss, cloud_ok=False, cloud_rev=108):
            ok1 = force_music_workspace_save(st, reason="page_change", build_state=lambda _s: creative)
        self.assertFalse(ok1)
        reserved = ss.get("_music_reserved_write_revision")
        self.assertEqual(reserved, 108)

        with self._save_patches(ss, cloud_ok=True, cloud_rev=108):
            ok2 = force_music_workspace_save(st, reason="page_change", build_state=lambda _s: creative)

        self.assertTrue(ok2)
        self.assertEqual(ss.get("_music_reserved_write_revision"), None)
        tx = ss.get("_music_workspace_save_transaction", {})
        self.assertEqual(tx.get("envelope_revision_after"), 108)

    def test_e_passive_skip_does_not_clear_confirmed_cloud(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = {
            "_suite_persist_last_save_cloud": True,
            "_music_last_confirmed_cloud_fp": "abc",
        }
        note_passive_autosave_cloud_skip(ss, reason="music_egress_strict")
        self.assertEqual(ss.get("_music_passive_autosave_cloud_skip_reason"), "music_egress_strict")
        self.assertTrue(ss.get("_suite_persist_last_save_cloud"))


if __name__ == "__main__":
    unittest.main()
