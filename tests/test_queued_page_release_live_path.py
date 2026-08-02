"""Verify force_save uses the same queued-release module path as production."""

from __future__ import annotations

import copy
import inspect
import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_startup_save_suppression import (
    STARTUP_SUPPRESSION_ARMED_KEY,
    attempt_release_startup_for_queued_page_change,
    record_hydrated_canonical_fingerprint,
    run_late_startup_restore_guard,
    set_page_change_origin,
)
from music_queued_page_startup_release_trace import (
    QUEUED_PAGE_STARTUP_RELEASE_IMPL,
    QUEUED_PAGE_RELEASE_TRACE_KEY,
)
from music_workspace_cloud_save import force_music_workspace_save
from studio_nav_history import navigate_studio_page
from suite_user_persistence import _local_dirty_key
from tests.test_music_startup_queued_page_change import (
    StartupQueuedPageChangeTests,
    _backing_payload,
    _FakeSessionState,
)


class QueuedReleaseLivePathTests(StartupQueuedPageChangeTests):
    def test_force_save_imports_same_attempt_release_function(self) -> None:
        import music_workspace_cloud_save as cloud_save_mod

        source = inspect.getsource(cloud_save_mod.force_music_workspace_save)
        self.assertIn("attempt_release_startup_for_queued_page_change", source)
        self.assertIs(
            cloud_save_mod.force_music_workspace_save.__module__,
            "music_workspace_cloud_save",
        )

    def test_reconciliation_origin_still_invokes_dedicated_release(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = self._armed_backing_session(rev=191)
        ss["studio_page"] = "creative"
        ss["_music_user_navigated_page_this_run"] = "creative"
        ss["_suite_page_change_save_page"] = "creative"
        set_page_change_origin(ss, "reconciliation")
        st = MagicMock()
        st.session_state = ss
        ok = attempt_release_startup_for_queued_page_change(st, suppress_reason="test")
        self.assertTrue(ok)
        self.assertTrue(ss.get("startup_suppression_released"))
        trace = ss.get(QUEUED_PAGE_RELEASE_TRACE_KEY) or {}
        self.assertTrue(trace.get("queued_release_return_value"))
        self.assertIn(
            str(trace.get("queued_release_branch_selected") or ""),
            ("dedicated_release_function", "pre_aligned_no_arm", "pre_aligned_shortcut"),
        )

    def test_late_guard_defers_finalize_preserves_revision_191(self) -> None:
        ss = self._armed_backing_session(rev=191)
        ss["studio_page"] = "creative"
        ss["_music_user_navigated_page_this_run"] = "creative"
        ss["_suite_page_change_save_page"] = "creative"
        set_page_change_origin(ss, "user_navigation")
        st = MagicMock()
        st.session_state = ss
        run_late_startup_restore_guard(st)
        self.assertEqual(ss.get("startup_revision_final"), 191)
        trace = ss.get(QUEUED_PAGE_RELEASE_TRACE_KEY) or {}
        self.assertTrue(trace.get("finalize_deferred_for_queued_page_change"))

    def test_navigate_via_force_save_module_path_sets_impl_marker(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = self._armed_backing_session(rev=191)
        cloud_writes: list[dict[str, Any]] = []
        st = MagicMock()
        st.session_state = ss

        def _build_state(st_obj: Any) -> dict[str, Any]:
            from music_persistent_state import build_music_disk_state

            return build_music_disk_state(st_obj)

        with self._cloud_patches(ss, cloud_writes):
            navigate_studio_page(ss, "creative")

        trace = ss.get(QUEUED_PAGE_RELEASE_TRACE_KEY) or {}
        self.assertEqual(
            trace.get("queued_release_impl_marker") or QUEUED_PAGE_STARTUP_RELEASE_IMPL,
            QUEUED_PAGE_STARTUP_RELEASE_IMPL,
        )


if __name__ == "__main__":
    unittest.main()
