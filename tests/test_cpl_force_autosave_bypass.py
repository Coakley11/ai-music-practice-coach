"""CPL saves must bypass post-restore autosave cooldown via cpl_draft_edit reason."""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from suite_user_persistence import _autosave_block_key, force_autosave

_STAMPED: dict = {}


def _stamp(_st: object, state: dict, **_kw: object) -> dict:
    _STAMPED.clear()
    _STAMPED.update({**state, "workspace_revision": int(state.get("workspace_revision") or 0) + 1})
    return dict(_STAMPED)


def _load_cloud(*_a: object, **_kw: object) -> tuple[dict, str]:
    return dict(_STAMPED), "2026-01-01T00:00:00Z"


def _enter_music_force_save_patches(stack: ExitStack) -> None:
    _STAMPED.clear()
    stack.enter_context(patch("suite_user_persistence.save_user_state", return_value=True))
    stack.enter_context(patch("music_workspace_cloud_save._cloud_enabled", return_value=True))
    stack.enter_context(patch("music_egress_config.music_cloud_write_allowed", return_value=True))
    stack.enter_context(patch("music_persistent_state.stamp_music_payload_for_write", side_effect=_stamp))
    stack.enter_context(patch("music_egress_config.skip_cloud_readback_after_write", return_value=False))
    stack.enter_context(patch("music_persistent_state.save_music_cloud_session", return_value=True))
    stack.enter_context(patch("suite_cloud_state.load_cloud_full_session", side_effect=_load_cloud))
    stack.enter_context(patch("suite_cloud_state.session_page_summary", return_value=("custom", "CPL")))
    stack.enter_context(patch("music_persistent_state._record_music_persist_trace"))


class TestCplForceAutosaveBypass(unittest.TestCase):
    def test_cpl_draft_edit_bypasses_post_restore_autosave_block(self) -> None:
        st = SimpleNamespace(
            session_state={
                "_music_build_save_reason": "cpl_draft_edit",
                "_music_workspace_blob_hydrated": True,
            }
        )
        st.session_state[_autosave_block_key("music")] = True

        def _build_state(_st: object) -> dict:
            return {"core": {}, "session": {}, "workspace_revision": 1}

        with ExitStack() as stack:
            _enter_music_force_save_patches(stack)
            ok = force_autosave(
                st,
                "music",
                build_state=_build_state,
                reason="cpl_draft_edit",
            )

        self.assertTrue(ok)
        self.assertTrue(st.session_state.get("_suite_persist_last_save_cloud"))

    def test_song_edit_still_bypasses_post_restore_autosave_block(self) -> None:
        st = SimpleNamespace(
            session_state={
                "_music_build_save_reason": "song_edit",
                "_music_workspace_blob_hydrated": True,
                "active_catalog_pick_key": "Pop::Other — Artist",
            }
        )
        st.session_state[_autosave_block_key("music")] = True

        def _build_state(_st: object) -> dict:
            return {"core": {}, "session": {}, "workspace_revision": 1}

        with ExitStack() as stack:
            _enter_music_force_save_patches(stack)
            ok = force_autosave(
                st,
                "music",
                build_state=_build_state,
                reason="song_edit",
            )

        self.assertTrue(ok)
        self.assertTrue(st.session_state.get("_suite_persist_last_save_cloud"))


if __name__ == "__main__":
    unittest.main()
