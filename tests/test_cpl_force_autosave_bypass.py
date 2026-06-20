"""CPL saves must bypass post-restore autosave cooldown via song_edit reason."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from suite_user_persistence import _autosave_block_key, force_autosave


class TestCplForceAutosaveBypass(unittest.TestCase):
    def test_song_edit_bypasses_post_restore_autosave_block(self) -> None:
        st = SimpleNamespace(session_state={"_music_build_save_reason": "song_edit"})
        st.session_state[_autosave_block_key("music")] = True

        def _build_state(_st):
            return {"core": {}, "session": {}}

        with patch("suite_user_persistence.save_user_state", return_value=True), patch(
            "suite_cloud_state.save_cloud_full_session",
            return_value=True,
        ), patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=({}, None),
        ), patch(
            "suite_cloud_state.session_page_summary",
            return_value=("custom", "CPL"),
        ):
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
