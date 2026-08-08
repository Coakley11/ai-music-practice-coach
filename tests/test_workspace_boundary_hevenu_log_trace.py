"""Trace-backed boundary tests: Hevenu + Log repro (Say + Practice hydrate)."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock, patch
from music_restore_phase import complete_music_restore_phase
from music_startup_save_suppression import (
    STARTUP_FINGERPRINT_MATCHES_KEY,
    STARTUP_SUPPRESSION_ARMED_KEY,
    STARTUP_SUPPRESSION_RELEASED_KEY,
    finalize_startup_canonical_alignment,
    gate_music_workspace_save_at_startup,
    record_hydrated_canonical_fingerprint,
    should_suppress_music_workspace_save,
)
from music_workspace_boundary_trace import (
    evaluate_binary_refresh_question,
    envelope_snapshot,
    live_session_snapshot,
)
from music_workspace_hydration import mark_workspace_blob_hydrated


SAY_KEY = "Traditional::Say Something"
HEVENU_KEY = "Traditional::Hevenu Shalom Aleichem"


def _payload(*, rev: int, pick_key: str, page: str) -> dict:
    title = "Say Something" if "Say" in pick_key else "Hevenu Shalom Aleichem"
    return {
        "core": {
            "pick_key": pick_key,
            "studio_page": page,
            "page": page,
            "instrument": "Piano",
        },
        "session": {"studio_page": page, "active_catalog_pick_key": pick_key},
        "active_song_state": {
            "pick_key": pick_key,
            "music_source": "catalog",
            "selected_song": {"title": title},
        },
        "studio_nav_state": {"studio_page": page, "page": page},
        "practice_workspace_state": {"studio_page": page, "page": page},
        "music_workspace_state": {
            "workspace_revision": rev,
            "studio_page": page,
            "active_song": {"pick_key": pick_key, "music_source": "catalog"},
        },
        "workspace_revision": rev,
    }


def _session_after_hydrate(payload: dict) -> dict:
    ss = copy.deepcopy(payload)
    ss.update(
        {
            "studio_page": payload["core"]["studio_page"],
            "music_workspace_state": copy.deepcopy(payload["music_workspace_state"]),
            "active_song_state": copy.deepcopy(payload["active_song_state"]),
            "studio_nav_state": copy.deepcopy(payload["studio_nav_state"]),
            "core": copy.deepcopy(payload["core"]),
            "_script_run_seq": 1,
            "_music_user_navigated_page_this_run": "",
        }
    )
    record_hydrated_canonical_fingerprint(ss, payload, stage="test:hydrate_say")
    mark_workspace_blob_hydrated(ss)
    return ss


class WorkspaceBoundaryHevenuLogTests(unittest.TestCase):
    def test_song_edit_blocked_while_startup_fingerprint_matches_after_user_edits(self) -> None:
        """Proves A/D: after hydrate finalize, fingerprint stays true while live session diverges."""
        rev = 200
        hydrated = _payload(rev=rev, pick_key=SAY_KEY, page="practice")
        ss = _session_after_hydrate(hydrated)
        st = MagicMock()
        st.session_state = ss
        finalize_startup_canonical_alignment(st, stage="test:post_hydrate")
        complete_music_restore_phase(ss)
        # Simulate prior run that finalized with canonical_match (flag persists in Streamlit session).
        ss[STARTUP_FINGERPRINT_MATCHES_KEY] = True
        ss[STARTUP_SUPPRESSION_RELEASED_KEY] = True
        ss.pop("startup_restore_in_progress", None)

        ss["studio_page"] = "log"
        ss["core"] = dict(ss.get("core") or {})
        ss["core"]["pick_key"] = HEVENU_KEY
        ss["core"]["studio_page"] = "log"
        ass = dict(ss.get("active_song_state") or {})
        ass["pick_key"] = HEVENU_KEY
        ass["selected_song"] = {"title": "Hevenu Shalom Aleichem"}
        ss["active_song_state"] = ass
        ws = dict(ss.get("music_workspace_state") or {})
        ws["studio_page"] = "log"
        ws["active_song"] = {"pick_key": HEVENU_KEY, "music_source": "catalog"}
        ss["music_workspace_state"] = ws

        live = live_session_snapshot(ss)
        self.assertEqual(live["studio_page"], "log")
        self.assertIn("Hevenu", live["pick_key"])

        suppress, why = should_suppress_music_workspace_save(ss, "song_edit")
        self.assertTrue(suppress)
        self.assertEqual(why, "startup_canonical_unchanged")

        skip, gate_why = gate_music_workspace_save_at_startup(ss, "song_edit")
        self.assertTrue(skip)
        self.assertEqual(gate_why, "startup_canonical_unchanged")

    def test_binary_question_when_durable_still_say_practice(self) -> None:
        live = {
            "studio_page": "log",
            "pick_key": HEVENU_KEY,
        }
        durable = envelope_snapshot(_payload(rev=200, pick_key=SAY_KEY, page="practice"))
        verdict = evaluate_binary_refresh_question(
            live_before_refresh=live,
            durable_envelope=durable,
        )
        self.assertIn("A_or_B", verdict["hypothesis"])
        self.assertFalse(verdict["durable_matches_live_before_refresh"])

    def test_page_change_deferred_flush_uses_reconciliation_origin_and_can_block(self) -> None:
        from music_persistent_state import _page_change_save_ready, maybe_flush_deferred_page_change_save
        from music_startup_save_suppression import get_page_change_origin, set_page_change_origin

        rev = 201
        hydrated = _payload(rev=rev, pick_key=SAY_KEY, page="practice")
        ss = _session_after_hydrate(hydrated)
        st = MagicMock()
        st.session_state = ss
        finalize_startup_canonical_alignment(st, stage="test:defer")
        complete_music_restore_phase(ss)

        ss["studio_page"] = "log"
        ss["_suite_deferred_page_change_save"] = "log"
        ss["_suite_page_user_nav"] = True
        nav = dict(ss.get("studio_nav_state") or {})
        nav["studio_page"] = "log"
        ss["studio_nav_state"] = nav
        ws = dict(ss.get("music_workspace_state") or {})
        ws["studio_page"] = "practice"
        ss["music_workspace_state"] = ws

        self.assertFalse(_page_change_save_ready(ss, "log"))

        ws["studio_page"] = "log"
        ss["music_workspace_state"] = ws
        self.assertTrue(_page_change_save_ready(ss, "log"))

        set_page_change_origin(ss, "reconciliation")
        ss[STARTUP_SUPPRESSION_RELEASED_KEY] = True
        ss.pop(STARTUP_SUPPRESSION_ARMED_KEY, None)
        ss.pop("startup_restore_in_progress", None)
        suppress, why = should_suppress_music_workspace_save(ss, "page_change")
        self.assertTrue(suppress)
        self.assertIn(
            why,
            (
                "page_change_origin:reconciliation",
                "startup_suppression_armed_page_change",
            ),
        )

        cloud_calls: list[int] = []

        def _save_cloud(*_a: object, **_k: object) -> object:
            cloud_calls.append(1)
            from suite_cloud_state import CloudSaveResult

            return CloudSaveResult(success=True, cloud_upsert_succeeded=True)

        with patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud):
            maybe_flush_deferred_page_change_save(st)

        self.assertEqual(cloud_calls, [])
        self.assertEqual(get_page_change_origin(ss), "reconciliation")

    def test_startup_fingerprint_flag_blocks_song_edit_even_when_live_differs(self) -> None:
        ss: dict = {"startup_fingerprint_matches": True, "startup_suppression_released": True}
        suppress, why = should_suppress_music_workspace_save(ss, "song_edit")
        self.assertTrue(suppress)
        self.assertEqual(why, "startup_canonical_unchanged")


if __name__ == "__main__":
    unittest.main()
