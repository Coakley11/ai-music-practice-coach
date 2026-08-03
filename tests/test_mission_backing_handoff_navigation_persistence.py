"""Mission Backing handoff — page_change durability, full CWS, network confirm, refresh trace."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from backing_context import open_backing_from_creative
from creative_mission_artifact_persistence import (
    CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY,
    canonical_mission_artifact_value,
)
from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY, default_creative_workspace_state
from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY, MissionExample, store_mission_practice_lick_for_backing
from mission_backing_handoff_persistence import (
    VIOLATION_POST_CONFIRM_OVERWRITE,
    arm_mission_backing_handoff_page_change,
    begin_mission_backing_handoff,
    collect_mission_backing_handoff_diagnostics,
    complete_mission_backing_handoff_after_navigation,
    guard_mission_backing_handoff_post_confirm_overwrite,
    summarize_handoff_payload_forensics,
)
from music_egress_config import MUSIC_EGRESS_STRICT_KEY
from music_page_save_pipeline_trace import payload_pages_from_state
from music_persistent_state import apply_music_disk_state
from studio_nav_history import navigate_studio_page
from studio_nav_state import STUDIO_NAV_STATE_KEY, prepare_studio_nav
from suite_cloud_state import CloudSaveResult
from suite_user_persistence import _local_dirty_key


class _FakeSessionState(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _example_blob() -> dict[str, Any]:
    return {
        "mission": "chord_tones",
        "variant": "normal",
        "chord": "Ab",
        "section": "Verse",
        "motif": {"notes": ["Ab", "C", "Eb"], "display": "Ab C Eb", "rhythm": "q q q", "chord": "Ab"},
        "abc": "X:1",
        "tab": "",
        "why": "test",
        "practice_steps": [],
    }


def _creative_missions_session() -> _FakeSessionState:
    example = MissionExample(
        mission="chord_tones",
        variant="normal",
        chord="Ab",
        section="Verse",
        song_title="Say",
        display_key="Ab",
        instrument="Guitar",
        level="Intermediate",
        focus="Melody",
        motif={"notes": ["Ab", "C", "Eb"], "display": "Ab C Eb", "rhythm": "q q q", "chord": "Ab"},
        abc="X:1",
        tab="",
        piano_html="",
        why="test",
        practice_steps=[],
        insight=None,
        show_tab=False,
        show_piano=False,
    )
    cws = {
        **default_creative_workspace_state(),
        "improv_intelligence_tab": "Missions",
        "improv_active_mission": "chord_tones",
        MISSION_EXAMPLE_KEY: _example_blob(),
        "improv_ai_metric_ids": ["phrase_structure"],
    }
    return _FakeSessionState(
        {
            "developer_mode": True,
            "_phase1_write_journal_force": True,
            "startup_suppression_released": True,
            "_music_workspace_blob_hydrated": True,
            "_music_studio_page_restore_projection_complete": True,
            "studio_page": "creative",
            "improv_intelligence_tab": "Missions",
            "improv_active_mission": "chord_tones",
            "improv_ai_metric_ids": ["phrase_structure"],
            "ii_selected_chord_index": 3,
            "improv_mission_chord_options": ["Ab"],
            CREATIVE_WORKSPACE_STATE_KEY: cws,
            "backing_track_bpm": 90,
            "backing_groove_style": "Pop groove",
            "backing_time_signature": "4/4",
            "_script_run_seq": 100,
            STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            "music_workspace_state": {"studio_page": "creative", "workspace_revision": 5},
            _local_dirty_key("music"): True,
            "improv_mission_example": _example_blob(),
        }
    )


def _all_payload_pages(payload: dict[str, Any]) -> dict[str, str]:
    pages = payload_pages_from_state(payload)
    env = payload.get("music_workspace_state")
    if isinstance(env, dict):
        pages["envelope"] = str(env.get("studio_page") or env.get("page") or "").strip()
    return pages


class TestMissionBackingHandoffNavigationPersistence(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(MUSIC_EGRESS_STRICT_KEY, None)

    def _cloud_patches(self, ss: dict[str, Any], *, cloud_writes: list[dict[str, Any]], readback: list[dict[str, Any]]):
        stack = ExitStack()

        def _save_cloud(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            import copy

            cloud_writes.append(copy.deepcopy(state))
            readback.clear()
            readback.append(copy.deepcopy(state))
            ss["_suite_last_cloud_fetch_payload"] = copy.deepcopy(state)
            ss["_suite_persist_last_save_cloud"] = True
            ss["_music_last_confirmed_cloud_revision"] = (
                (state.get("music_workspace_state") or {}).get("workspace_revision")
                if isinstance(state.get("music_workspace_state"), dict)
                else None
            )
            return CloudSaveResult(success=True, save_cloud_full_session_return_value=True)

        def _load_cloud(_app: str, force: bool = False):
            import copy

            if readback:
                return copy.deepcopy(readback[-1]), "2026-08-02T12:00:00+00:00"
            return None, None

        for ctx in (
            patch("music_workspace_cloud_save._cloud_enabled", return_value=True),
            patch("suite_user_persistence.save_user_state", return_value=True),
            patch("suite_storage_config.cloud_storage_enabled", return_value=True),
            patch("suite_storage_config.get_cloud_config", return_value=object()),
            patch("suite_cloud_state._import_storage", return_value=(suite_storage, "suite_storage")),
            patch("suite_cloud_state._cloud_storage_app_id", return_value="music"),
            patch.object(suite_storage, "save_current_state"),
            patch("suite_cloud_state._streamlit_session", return_value=ss),
            patch("suite_cloud_state.save_cloud_full_session", side_effect=_save_cloud),
            patch("suite_cloud_state.load_cloud_full_session", side_effect=_load_cloud),
            patch("music_egress_config.skip_cloud_readback_after_write", return_value=True),
            patch(
                "music_startup_save_suppression.gate_music_workspace_save_at_startup",
                return_value=(False, ""),
            ),
        ):
            stack.enter_context(ctx)
        return stack

    def test_handoff_preserves_full_cws_and_network_confirm(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = _creative_missions_session()
        example = MissionExample(
            mission="chord_tones",
            variant="normal",
            chord="Ab",
            section="Verse",
            song_title="Say",
            display_key="Ab",
            instrument="Guitar",
            level="Intermediate",
            focus="Melody",
            motif={"notes": ["Ab", "C", "Eb"], "display": "Ab C Eb", "rhythm": "q q q", "chord": "Ab"},
            abc="X:1",
            tab="",
            piano_html="",
            why="test",
            practice_steps=[],
            insight=None,
            show_tab=False,
            show_piano=False,
        )
        cloud_writes: list[dict[str, Any]] = []
        readback_store: list[dict[str, Any]] = []

        store_mission_practice_lick_for_backing(
            ss,
            example=example,
            mission_title="chord_tones",
            instrument="Guitar",
            bpm=90,
            groove="Pop groove",
            meter="4/4",
            song_title="Say",
            section_label="Verse",
            persist_artifact=False,
        )
        self.assertIsNone(ss.get(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY))

        begin_mission_backing_handoff(
            ss,
            navigation_callback="_open_mission_backing",
            with_practice_lick=True,
        )
        open_backing_from_creative(ss, source="mission", st_like=MagicMock(session_state=ss))
        arm_mission_backing_handoff_page_change(ss)

        cws = ss.get(CREATIVE_WORKSPACE_STATE_KEY) or {}
        self.assertIn(MISSION_EXAMPLE_KEY, cws)
        self.assertIn(MISSION_PRACTICE_LICK_KEY, cws)
        self.assertEqual(cws.get("improv_intelligence_tab"), "Missions")

        with self._cloud_patches(ss, cloud_writes=cloud_writes, readback=readback_store):
            changed = navigate_studio_page(ss, "backing")
            self.assertTrue(changed)
            complete_mission_backing_handoff_after_navigation(
                ss,
                navigation_callback="_improv_open_backing",
                backing_source="mission",
            )

        self.assertGreaterEqual(len(cloud_writes), 1)
        last = cloud_writes[-1]
        forensics = summarize_handoff_payload_forensics(last)
        self.assertTrue((forensics.get("improv_mission_example") or {}).get("present"))
        self.assertTrue((forensics.get("improv_mission_practice_lick") or {}).get("present"))

        pages = _all_payload_pages(last)
        for key, val in pages.items():
            if val:
                self.assertEqual(val.lower(), "backing", msg=f"payload page field {key}={val!r}")

        handoff = collect_mission_backing_handoff_diagnostics(ss)
        self.assertEqual(handoff.get("save_reason"), "page_change")
        confirm = handoff.get("authoritative_confirmation") or {}
        self.assertEqual(confirm.get("fetch_source"), "network")
        self.assertTrue(confirm.get("confirmed"))
        self.assertEqual(handoff.get("violations"), [])

        ss2 = _FakeSessionState({"developer_mode": True, "_script_run_seq": 101})
        st2 = MagicMock()
        st2.session_state = ss2
        apply_music_disk_state(
            st2,
            last,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        rendered = prepare_studio_nav(ss2)
        self.assertEqual(rendered, "backing")
        self.assertTrue(ss2.get("improv_mission_example"))
        self.assertTrue(canonical_mission_artifact_value(ss2, MISSION_EXAMPLE_KEY))

    def test_post_confirm_overwrite_guard_blocks_passive_autosave(self) -> None:
        from mission_backing_handoff_persistence import MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY
        from mission_backing_handoff_persistence import MISSION_BACKING_HANDOFF_CONFIRMED_SNAPSHOT_KEY

        ss: dict[str, Any] = {
            MISSION_BACKING_HANDOFF_CONFIRMED_REVISION_KEY: 10,
            MISSION_BACKING_HANDOFF_CONFIRMED_SNAPSHOT_KEY: {
                "had_example": True,
                "had_lick": True,
                "page_fields": {"workspace": "backing"},
            },
        }
        bad_state = {
            "core": {"studio_page": "creative", "page": "creative"},
            "session": {"studio_page": "creative"},
            "studio_nav_state": {"studio_page": "creative", "page": "creative"},
            "music_workspace_state": {"studio_page": "creative", "workspace_revision": 11},
            "creative_workspace_state": {**default_creative_workspace_state()},
        }
        blocked, _detail = guard_mission_backing_handoff_post_confirm_overwrite(
            ss, save_reason="autosave", state=bad_state
        )
        self.assertTrue(blocked)


if __name__ == "__main__":
    unittest.main()
