"""Established user navigation must not read cloud when no restore is pending.

Latency numbers in this file are simulated with a local sleep inside the
cloud loader mock. They are not hosted Supabase timings.
"""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from music_persistent_state import (
    MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY,
    MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY,
    NAV_CLOUD_READ_ONCE_KEY,
    begin_script_run_navigation_markers,
)
from music_workspace_hydration import WORKSPACE_BLOB_HYDRATED_KEY
from music_workspace_restore_mode import (
    ACCOUNT_RESOLUTION_DIAG_KEY,
    PENDING_USER_EDITS_KEY,
    USER_EDIT_TRACKING_ENABLED_KEY,
)
from suite_user_persistence import (
    NAV_CLOUD_READ_IDENTITY_KEY,
    NAV_CLOUD_READ_TIMINGS_KEY,
    USER_NAV_CLOUD_SKIP_REASON,
    _local_dirty_key,
    sync_workspace_protocol,
)

SIMULATED_CLOUD_LATENCY_S = 0.04


def _established_session(*, run_seq: int = 4, dirty: bool = False) -> dict:
    session = {
        "_script_run_seq": run_seq,
        "studio_page": "practice",
        "_suite_page_user_nav": True,
        WORKSPACE_BLOB_HYDRATED_KEY: True,
        USER_EDIT_TRACKING_ENABLED_KEY: True,
        ACCOUNT_RESOLUTION_DIAG_KEY: {
            "account_hint": "player@example.com",
            "workspace_key": "daniel",
            "authenticated": True,
        },
        NAV_CLOUD_READ_IDENTITY_KEY: {
            "account_hint": "player@example.com",
            "workspace_key": "daniel",
        },
        NAV_CLOUD_READ_ONCE_KEY: {
            "page": "backing",
            "from_run": run_seq - 1,
            "for_run": run_seq,
        },
    }
    if dirty:
        session[_local_dirty_key("music")] = True
    return session


def _identity(session: dict, app_id: str) -> None:
    session[ACCOUNT_RESOLUTION_DIAG_KEY] = {
        "account_hint": "player@example.com",
        "workspace_key": "daniel",
        "authenticated": True,
    }


class NavCloudReadSkipTests(unittest.TestCase):
    def _sync(self, session: dict, cloud_fn):
        st = SimpleNamespace(session_state=session)
        with patch(
            "suite_cloud_state.load_cloud_full_session", side_effect=cloud_fn
        ), patch(
            "suite_user_persistence._load_raw", return_value=({}, None, None)
        ), patch(
            "music_workspace_restore_mode.record_account_workspace_identity",
            side_effect=_identity,
        ), patch(
            "suite_cloud_state.should_skip_workspace_restore_for_resume",
            return_value=False,
        ), patch(
            "suite_cloud_state.reconcile_stale_resume_session_flags",
            return_value=False,
        ):
            return sync_workspace_protocol(
                st, "music", apply_state=lambda _st, _blob: None, cloud_first=True
            )

    def test_established_nav_skips_cloud_read(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({"core": {"studio_page": "practice"}}, "2026-11-04T00:00:00Z")

        session = _established_session()
        applied = self._sync(session, cloud)
        self.assertFalse(applied)
        self.assertEqual(calls, [])
        self.assertEqual(session.get("_suite_persist_restore_skip_reason"), USER_NAV_CLOUD_SKIP_REASON)
        self.assertTrue(session.get("_suite_user_nav_sync_skipped"))
        self.assertFalse(session.get("_suite_workspace_sync_skipped_no_apply"))
        self.assertFalse(session.get("_suite_cloud_fetch_attempted"))
        self.assertTrue(session.get("_music_nav_cloud_read_skipped"))
        self.assertTrue(session.get(WORKSPACE_BLOB_HYDRATED_KEY))
        row = session[NAV_CLOUD_READ_TIMINGS_KEY][-1]
        self.assertEqual(row["cloud_calls"], 0)
        self.assertTrue(row["skipped"])
        self.assertFalse(row["simulated"])

    def test_sticky_flag_without_one_shot_still_reads_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        session.pop(NAV_CLOUD_READ_ONCE_KEY, None)
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])
        self.assertFalse(session.get("_music_nav_cloud_read_skipped"))

    def test_cold_start_with_stale_flag_still_reads_cloud(self) -> None:
        calls: list[str] = []
        cloud_blob = {
            "core": {"studio_page": "practice", "pick_key": "Pop::Say — John Mayer"},
            "workspace_revision": 2,
        }

        def cloud(app_id: str):
            calls.append(app_id)
            return (cloud_blob, "2026-11-04T00:00:00Z")

        session = _established_session()
        session[WORKSPACE_BLOB_HYDRATED_KEY] = False
        session[USER_EDIT_TRACKING_ENABLED_KEY] = False
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])
        self.assertFalse(session.get("_music_nav_cloud_read_skipped"))

    def test_pending_local_edits_still_read_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session(dirty=True)
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_pending_edit_queue_still_reads_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        session[PENDING_USER_EDITS_KEY] = [{"field": "display_key"}]
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_workspace_switch_still_reads_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        session[NAV_CLOUD_READ_IDENTITY_KEY] = {
            "account_hint": "player@example.com",
            "workspace_key": "old-studio",
        }
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_account_switch_still_reads_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        session[NAV_CLOUD_READ_IDENTITY_KEY] = {
            "account_hint": "other@example.com",
            "workspace_key": "daniel",
        }
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_simulated_latency_skip_versus_fetch(self) -> None:
        """SIMULATED 40ms cloud loader. Not a hosted Supabase measurement."""

        def slow_cloud(app_id: str):
            time.sleep(SIMULATED_CLOUD_LATENCY_S)
            return ({}, None)

        skip_session = _established_session()
        t0 = time.perf_counter()
        self._sync(skip_session, slow_cloud)
        skip_ms = (time.perf_counter() - t0) * 1000.0

        fetch_session = _established_session()
        fetch_session.pop(NAV_CLOUD_READ_ONCE_KEY, None)
        t1 = time.perf_counter()
        self._sync(fetch_session, slow_cloud)
        fetch_ms = (time.perf_counter() - t1) * 1000.0

        skip_row = skip_session[NAV_CLOUD_READ_TIMINGS_KEY][-1]
        fetch_row = fetch_session[NAV_CLOUD_READ_TIMINGS_KEY][-1]
        self.assertEqual(skip_row["cloud_calls"], 0)
        self.assertLess(skip_row["elapsed_ms"], 15.0)
        self.assertEqual(fetch_row["cloud_calls"], 1)
        self.assertGreaterEqual(fetch_row["elapsed_ms"], SIMULATED_CLOUD_LATENCY_S * 1000.0 - 5.0)
        self.assertGreater(fetch_ms - skip_ms, 20.0)

    def test_begin_run_promotes_only_previous_stamp(self) -> None:
        fresh = {
            "_script_run_seq": 10,
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "backing",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 9,
        }
        begin_script_run_navigation_markers(fresh)
        self.assertIsNone(fresh.get(MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY))
        self.assertEqual(fresh[NAV_CLOUD_READ_ONCE_KEY]["for_run"], 10)
        self.assertEqual(fresh[NAV_CLOUD_READ_ONCE_KEY]["page"], "backing")

        ancient = {
            "_script_run_seq": 10,
            MUSIC_USER_NAVIGATED_PAGE_THIS_RUN_KEY: "backing",
            MUSIC_USER_NAVIGATED_PAGE_RUN_SEQ_KEY: 7,
            NAV_CLOUD_READ_ONCE_KEY: {"page": "practice", "from_run": 6, "for_run": 7},
        }
        begin_script_run_navigation_markers(ancient)
        self.assertNotIn(NAV_CLOUD_READ_ONCE_KEY, ancient)

    def test_one_shot_is_not_reusable(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        self._sync(session, cloud)
        self.assertEqual(calls, [])
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_refresh_drops_previous_token_and_reads_cloud(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session(run_seq=8)
        session["_script_run_seq"] = 9
        begin_script_run_navigation_markers(session)
        self.assertNotIn(NAV_CLOUD_READ_ONCE_KEY, session)
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_missing_identity_stamp_does_not_skip(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({}, None)

        session = _established_session()
        session.pop(NAV_CLOUD_READ_IDENTITY_KEY, None)
        self._sync(session, cloud)
        self.assertEqual(calls, ["music"])

    def test_cloud_error_still_surfaces_before_hydration(self) -> None:
        session = _established_session()
        session[WORKSPACE_BLOB_HYDRATED_KEY] = False
        session[USER_EDIT_TRACKING_ENABLED_KEY] = False

        def cloud(app_id: str):
            raise RuntimeError("simulated cloud outage")

        with self.assertRaises(RuntimeError):
            self._sync(session, cloud)

    def test_skip_does_not_touch_song_ownership(self) -> None:
        calls: list[str] = []

        def cloud(app_id: str):
            calls.append(app_id)
            return ({"core": {"studio_page": "practice"}}, "2026-11-04T00:00:00Z")

        session = _established_session()
        session.update(
            {
                "studio_page": "composer",
                "display_key": "Eb",
                "active_catalog_pick_key": "composition::abc",
                "backing_context": {"source": "composition_song", "practice_key": "Eb"},
                "cpl_active": {"id": "custom-1", "name": "My Progression", "original_key_center": "D"},
                "composer_active_document": {"id": "abc", "title": "New Song"},
            }
        )
        self._sync(session, cloud)
        self.assertEqual(calls, [])
        self.assertEqual(session["studio_page"], "composer")
        self.assertEqual(session["display_key"], "Eb")
        self.assertEqual(session["active_catalog_pick_key"], "composition::abc")
        self.assertEqual(session["backing_context"]["practice_key"], "Eb")
        self.assertEqual(session["cpl_active"]["id"], "custom-1")
        self.assertEqual(session["composer_active_document"]["id"], "abc")

    def test_page_change_save_call_unchanged(self) -> None:
        import inspect

        import music_persistent_state as mps

        source = inspect.getsource(mps.force_save_music_state)
        self.assertIn("def force_save_music_state", source)
        caller = inspect.getsource(mps)
        self.assertIn('force_save_music_state(st, reason="page_change")', caller)


if __name__ == "__main__":
    unittest.main()
