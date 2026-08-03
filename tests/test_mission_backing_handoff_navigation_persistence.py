"""Mission Backing handoff — page_change must persist Backing + mission subview + practice lick."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack
from typing import Any
from unittest.mock import MagicMock, patch

import suite_storage
from backing_context import BACKING_CONTEXT_KEY, open_backing_from_creative
from creative_mission_artifact_persistence import (
    CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY,
    canonical_mission_artifact_value,
)
from creative_workspace_state_persistence import CREATIVE_WORKSPACE_STATE_KEY, default_creative_workspace_state
from improvisation_missions import MISSION_PRACTICE_LICK_KEY, MissionExample, store_mission_practice_lick_for_backing
from mission_backing_handoff_persistence import (
    begin_mission_backing_handoff,
    collect_mission_backing_handoff_diagnostics,
    complete_mission_backing_handoff_after_navigation,
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
    lick_payload = {
        "motif": dict(example.motif),
        "abc": example.abc,
        "bpm": 90,
        "example_variant": "normal",
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
            "ii_selected_chord_index": 3,
            "improv_mission_chord_options": ["Ab"],
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "backing_track_bpm": 90,
            "backing_groove_style": "Pop groove",
            "backing_time_signature": "4/4",
            "_script_run_seq": 100,
            "_suite_last_cloud_fetch_payload": {
                "core": {"studio_page": "creative"},
                "session": {"studio_page": "creative"},
                "studio_nav_state": {"studio_page": "creative", "page": "creative"},
                "music_workspace_state": {"studio_page": "creative", "workspace_revision": 5},
                "workspace_revision": 5,
            },
            STUDIO_NAV_STATE_KEY: {"studio_page": "creative", "page": "creative"},
            "music_workspace_state": {"studio_page": "creative", "workspace_revision": 5},
            _local_dirty_key("music"): True,
            "improv_mission_example": example,
            MISSION_PRACTICE_LICK_KEY: lick_payload,
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

    def _cloud_patches(self, ss: dict[str, Any], *, cloud_writes: list[dict[str, Any]]):
        stack = ExitStack()

        def _save_cloud(_app: str, state: dict, **kwargs: object) -> CloudSaveResult:
            import copy

            cloud_writes.append(copy.deepcopy(state))
            ss["_suite_last_cloud_fetch_payload"] = copy.deepcopy(state)
            ss["_suite_persist_last_save_cloud"] = True
            ss["_music_last_confirmed_cloud_revision"] = (
                (state.get("music_workspace_state") or {}).get("workspace_revision")
                if isinstance(state.get("music_workspace_state"), dict)
                else None
            )
            return CloudSaveResult(success=True, save_cloud_full_session_return_value=True)

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
            patch("music_egress_config.skip_cloud_readback_after_write", return_value=True),
            patch(
                "music_startup_save_suppression.gate_music_workspace_save_at_startup",
                return_value=(False, ""),
            ),
        ):
            stack.enter_context(ctx)
        return stack

    def test_handoff_single_page_change_with_lick_and_mission_subview(self) -> None:
        os.environ[MUSIC_EGRESS_STRICT_KEY] = "1"
        ss = _creative_missions_session()
        example = ss["improv_mission_example"]
        cloud_writes: list[dict[str, Any]] = []

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
        self.assertTrue(canonical_mission_artifact_value(ss, MISSION_PRACTICE_LICK_KEY))

        begin_mission_backing_handoff(
            ss,
            navigation_callback="_open_mission_backing",
            with_practice_lick=True,
        )
        open_backing_from_creative(ss, source="mission", st_like=MagicMock(session_state=ss))

        with self._cloud_patches(ss, cloud_writes=cloud_writes):
            changed = navigate_studio_page(ss, "backing")
            self.assertTrue(changed)
            complete_mission_backing_handoff_after_navigation(
                ss,
                navigation_callback="_improv_open_backing",
                backing_source="mission",
            )

        self.assertGreaterEqual(len(cloud_writes), 1)
        artifact_only = [
            w
            for w in cloud_writes
            if any(
                (v or "").lower() == "creative"
                for v in _all_payload_pages(w).values()
                if v
            )
            and not any(
                (v or "").lower() == "backing"
                for v in _all_payload_pages(w).values()
                if v
            )
        ]
        self.assertEqual(
            artifact_only,
            [],
            msg="creative-only cloud write must not occur on Mission Backing handoff",
        )

        last = cloud_writes[-1]
        pages = _all_payload_pages(last)
        for key, val in pages.items():
            if val:
                self.assertEqual(val.lower(), "backing", msg=f"payload page field {key}={val!r}")

        cws = last.get("creative_workspace_state") or {}
        self.assertTrue(cws.get(MISSION_PRACTICE_LICK_KEY))

        ctx = last.get("session", {}).get(BACKING_CONTEXT_KEY) or last.get(BACKING_CONTEXT_KEY)
        if isinstance(ctx, dict):
            self.assertEqual(ctx.get("source"), "mission")

        handoff = collect_mission_backing_handoff_diagnostics(ss)
        self.assertEqual(handoff.get("page_before"), "creative")
        self.assertEqual(handoff.get("page_after"), "backing")
        self.assertEqual(handoff.get("save_reason"), "page_change")
        self.assertEqual(handoff.get("violations"), [])

        # Hard refresh hydrate
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
        self.assertEqual(ss2.get("studio_page"), "backing")

        # Cold session
        ss3 = _FakeSessionState({"developer_mode": True, "_script_run_seq": 102})
        st3 = MagicMock()
        st3.session_state = ss3
        apply_music_disk_state(
            st3,
            last,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        self.assertEqual(prepare_studio_nav(ss3), "backing")
        lick = canonical_mission_artifact_value(ss3, MISSION_PRACTICE_LICK_KEY)
        self.assertEqual(
            (lick or {}).get("motif", {}).get("notes"),
            ["Ab", "C", "Eb"],
        )


if __name__ == "__main__":
    unittest.main()
