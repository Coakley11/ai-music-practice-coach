"""Startup suppression must release after restore finalize so user page saves persist."""

from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import MagicMock, patch

from music_restore_phase import complete_music_restore_phase
from music_startup_save_suppression import (
    RESTORE_FINALIZED_STAGE_KEY,
    STARTUP_RESTORE_IN_PROGRESS_KEY,
    STARTUP_SUPPRESSION_ARMED_KEY,
    STARTUP_SUPPRESSION_RELEASED_KEY,
    finalize_startup_canonical_alignment,
    gate_music_workspace_save_at_startup,
    record_hydrated_canonical_fingerprint,
    run_late_startup_restore_guard,
    set_page_change_origin,
    should_suppress_music_workspace_save,
)
from music_workspace_hydration import mark_workspace_blob_hydrated

HEVENU = "Traditional::Hevenu Shalom Aleichem"

NAV_TARGETS = (
    "practice",
    "picker",
    "backing",
    "log",
    "compose",
    "creative",
)


def _payload(*, rev: int, page: str) -> dict:
    return {
        "core": {
            "pick_key": HEVENU,
            "studio_page": page,
            "page": page,
            "instrument": "Piano",
        },
        "session": {"studio_page": page, "active_catalog_pick_key": HEVENU},
        "active_song_state": {
            "pick_key": HEVENU,
            "music_source": "catalog",
            "selected_song": {"title": "Hevenu Shalom Aleichem"},
        },
        "studio_nav_state": {"studio_page": page, "page": page},
        "practice_workspace_state": {"studio_page": page, "page": page},
        "music_workspace_state": {
            "workspace_revision": rev,
            "studio_page": page,
            "page": page,
            "active_song": {"pick_key": HEVENU, "music_source": "catalog"},
        },
        "workspace_revision": rev,
    }


def _hydrated_session(payload: dict) -> dict:
    ss = copy.deepcopy(payload)
    ss.update(
        {
            "studio_page": payload["core"]["studio_page"],
            "music_workspace_state": copy.deepcopy(payload["music_workspace_state"]),
            "active_song_state": copy.deepcopy(payload["active_song_state"]),
            "studio_nav_state": copy.deepcopy(payload["studio_nav_state"]),
            "core": copy.deepcopy(payload["core"]),
            "_script_run_seq": 1,
        }
    )
    record_hydrated_canonical_fingerprint(ss, payload, stage="test:hydrate")
    mark_workspace_blob_hydrated(ss)
    return ss


def _simulate_user_page_nav(ss: dict, target: str) -> None:
    ss["studio_page"] = target
    ss["_suite_page_user_nav"] = True
    ss["_music_user_navigated_page_this_run"] = target
    ss["_suite_page_change_write_pending"] = target
    ss["_suite_page_change_stamp_target"] = target
    core = dict(ss.get("core") or {})
    core["studio_page"] = target
    core["page"] = target
    ss["core"] = core
    nav = dict(ss.get("studio_nav_state") or {})
    nav["studio_page"] = target
    nav["page"] = target
    ss["studio_nav_state"] = nav
    mws = dict(ss.get("music_workspace_state") or {})
    mws["studio_page"] = target
    mws["page"] = target
    ss["music_workspace_state"] = mws
    pws = dict(ss.get("practice_workspace_state") or {})
    pws["studio_page"] = target
    pws["page"] = target
    ss["practice_workspace_state"] = pws
    set_page_change_origin(ss, "user_navigation")


class StartupSuppressionReleaseLifecycleTests(unittest.TestCase):
    def test_hevenu_creative_hydrate_user_log_not_blocked_after_late_finalize(self) -> None:
        rev = 894
        hydrated = _payload(rev=rev, page="creative")
        ss = _hydrated_session(hydrated)
        _simulate_user_page_nav(ss, "log")
        st = MagicMock()
        st.session_state = ss

        built = copy.deepcopy(hydrated)
        built["core"]["studio_page"] = "log"
        built["core"]["page"] = "log"
        built["music_workspace_state"]["studio_page"] = "log"
        built["music_workspace_state"]["page"] = "log"

        with patch(
            "music_persistent_state.build_music_disk_state",
            return_value=built,
        ):
            complete_music_restore_phase(ss)
            finalize_startup_canonical_alignment(st, stage="test:early")
            run_late_startup_restore_guard(st)

        self.assertIn(
            ss.get(RESTORE_FINALIZED_STAGE_KEY),
            (
                "late_end_of_run",
                "late_end_of_run:queued_page_deferred",
                "test:early",
            ),
        )
        self.assertTrue(ss.get(STARTUP_SUPPRESSION_RELEASED_KEY))
        self.assertFalse(ss.get(STARTUP_RESTORE_IN_PROGRESS_KEY))
        suppress, why = should_suppress_music_workspace_save(ss, "page_change")
        self.assertFalse(suppress, msg=why)
        skip, gate_why = gate_music_workspace_save_at_startup(ss, "page_change")
        self.assertFalse(skip, msg=gate_why)

    def test_user_page_nav_targets_release_after_finalize(self) -> None:
        rev = 400
        for target in NAV_TARGETS:
            with self.subTest(target=target):
                hydrated = _payload(rev=rev, page="creative")
                ss = _hydrated_session(hydrated)
                if target == "creative":
                    continue
                _simulate_user_page_nav(ss, target)
                st = MagicMock()
                st.session_state = ss
                built = copy.deepcopy(hydrated)
                built["core"]["studio_page"] = target
                built["core"]["page"] = target
                built["music_workspace_state"]["studio_page"] = target
                built["music_workspace_state"]["page"] = target
                with patch(
                    "music_persistent_state.build_music_disk_state",
                    return_value=built,
                ):
                    run_late_startup_restore_guard(st)
                self.assertTrue(
                    ss.get(STARTUP_SUPPRESSION_RELEASED_KEY),
                    f"target={target}",
                )
                suppress, why = should_suppress_music_workspace_save(ss, "page_change")
                self.assertFalse(suppress, msg=f"{target}: {why}")

    def test_pure_hydrate_no_user_nav_still_suppresses_autosave(self) -> None:
        from music_egress_config import MUSIC_EGRESS_STRICT_KEY

        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        rev = 113
        hydrated = _payload(rev=rev, page="creative")
        ss = _hydrated_session(hydrated)
        st = MagicMock()
        st.session_state = ss
        with patch(
            "music_persistent_state.build_music_disk_state",
            return_value=hydrated,
        ):
            finalize_startup_canonical_alignment(st, stage="test:early")
            complete_music_restore_phase(ss)
            run_late_startup_restore_guard(st)

        self.assertTrue(ss.get(STARTUP_SUPPRESSION_RELEASED_KEY))
        self.assertTrue(ss.get("startup_fingerprint_matches"))
        cloud_calls: list[int] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        with patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud):
            from music_workspace_cloud_save import force_music_workspace_save

            force_music_workspace_save(st, reason="autosave", build_state=lambda _s: hydrated)

        self.assertEqual(cloud_calls, [])

    def test_deferred_user_page_flush_uses_user_navigation_origin(self) -> None:
        from music_persistent_state import maybe_flush_deferred_page_change_save
        from music_startup_save_suppression import get_page_change_origin

        rev = 500
        hydrated = _payload(rev=rev, page="creative")
        ss = _hydrated_session(hydrated)
        _simulate_user_page_nav(ss, "log")
        ss["_suite_deferred_page_change_save"] = "log"
        ss[STARTUP_SUPPRESSION_RELEASED_KEY] = True
        ss[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
        ss.pop(STARTUP_SUPPRESSION_ARMED_KEY, None)
        st = MagicMock()
        st.session_state = ss

        cloud_calls: list[int] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        with patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud), patch(
            "music_persistent_state.force_save_music_state",
            return_value=True,
        ):
            maybe_flush_deferred_page_change_save(st)

        self.assertEqual(get_page_change_origin(ss), "user_navigation")


if __name__ == "__main__":
    unittest.main()
