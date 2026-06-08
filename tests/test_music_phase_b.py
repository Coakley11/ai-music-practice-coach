"""Music Phase B — workspace sync, page ownership, Music Coach stub."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    SESSION_RETURN_PAGE_KEY,
    hydrate_applied_math_insight_for_session,
    insight_page_scope_decision,
    reconcile_stale_page_navigation,
)
from music_coach_context import (
    build_source_state,
    resolve_coach_source_page,
    sync_music_coach_workspace_page,
)
from music_persistent_state import (
    apply_music_disk_state,
    build_music_disk_state,
    claim_studio_page_ownership,
)
from suite_user_persistence import (
    SESSION_USER_OWNED_PAGE_KEY,
    _user_page_blocks_cloud_overwrite,
    sync_cloud_workspace_before_sidebar,
)


class TestMusicCoachContext(unittest.TestCase):
    def test_resolve_practice_page(self) -> None:
        ss = {"studio_page": "practice", "instrument": "Piano"}
        self.assertEqual(resolve_coach_source_page(ss), "practice")

    def test_resolve_karaoke_virtual_page(self) -> None:
        ss = {"studio_page": "backing", "instrument": "Voice", "karaoke_session_active": True}
        with patch("karaoke_mode.is_voice_mode", return_value=True), patch(
            "karaoke_mode.is_karaoke_session_active",
            return_value=True,
        ):
            self.assertEqual(resolve_coach_source_page(ss), "karaoke")

    def test_build_source_state_stub(self) -> None:
        ss = {
            "studio_page": "custom",
            "instrument": "Piano",
            "selected_song": {"title": "Test Song", "pick_key": "pop:test"},
        }
        blob = build_source_state("custom", ss)
        self.assertEqual(blob["source_app"], "music")
        self.assertEqual(blob["source_page"], "custom")
        self.assertEqual(blob["entity_params"]["song_title"], "Test Song")


class TestMusicPageOwnership(unittest.TestCase):
    def test_claim_studio_page_sets_owned_coach_page(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        st.query_params = {}
        claim_studio_page_ownership(st, "backing")
        self.assertEqual(st.session_state["studio_page"], "backing")
        self.assertEqual(st.session_state.get(SESSION_USER_OWNED_PAGE_KEY), "backing")
        self.assertEqual(st.session_state.get("_music_coach_workspace_page"), "backing")

    def test_user_owned_page_blocks_cloud_overwrite(self) -> None:
        st = MagicMock()
        st.session_state = {
            SESSION_USER_OWNED_PAGE_KEY: "practice",
            "studio_page": "practice",
            "_music_coach_workspace_page": "practice",
        }
        self.assertTrue(_user_page_blocks_cloud_overwrite(st, "backing"))
        self.assertFalse(_user_page_blocks_cloud_overwrite(st, "practice"))

    def test_sync_skips_when_user_owns_different_page(self) -> None:
        st = MagicMock()
        st.session_state = {
            SESSION_USER_OWNED_PAGE_KEY: "practice",
            "studio_page": "practice",
            "_music_coach_workspace_page": "practice",
        }
        cloud_state = {
            "core": {"studio_page": "backing", "pick_key": "pop:test"},
            "session": {},
            "music_workspace_state": {"page": "backing", "studio_page": "backing"},
        }
        applied: list[dict] = []

        with patch("suite_cloud_state.has_resume_query_params", return_value=False), patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-08T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=(
                {"core": {"studio_page": "practice"}, "session": {}},
                None,
                "2026-06-08T12:00:00+00:00",
            ),
        ):
            ok = sync_cloud_workspace_before_sidebar(
                st,
                "music",
                apply_state=lambda _s, state: applied.append(state),
            )

        self.assertFalse(ok)
        self.assertEqual(applied, [])

    def test_apply_preserves_user_studio_page(self) -> None:
        st = MagicMock()
        st.session_state = {
            "studio_page": "practice",
            "_suite_page_user_nav": True,
            "_music_coach_workspace_page": "practice",
        }
        payload = {
            "core": {"studio_page": "backing", "pick_key": "pop:test"},
            "session": {},
            "music_workspace_state": {"page": "backing", "studio_page": "backing"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True):
            apply_music_disk_state(
                st,
                payload,
                song_picker_catalog={},
                song_library={},
            )
        self.assertEqual(st.session_state["studio_page"], "practice")


class TestMusicCoachInsightScope(unittest.TestCase):
    def test_insight_renders_only_on_matching_page(self) -> None:
        insight = {
            "source_page": "practice",
            "source_state": {"source_page": "practice"},
            "conclusion": "Try the chorus next.",
        }
        ok = insight_page_scope_decision("music", "practice", insight)
        self.assertTrue(ok["should_render_insight_on_page"])
        wrong = insight_page_scope_decision("music", "backing", insight)
        self.assertFalse(wrong["should_render_insight_on_page"])

    def test_cloud_hydrate_does_not_force_navigation(self) -> None:
        st = MagicMock()
        st.session_state = {}
        st.query_params = {}
        cloud_insight = {
            "insight_id": "mc1",
            "source_app": "music",
            "source_page": "practice",
            "conclusion": "Practice the verse slowly.",
            "source_state": {"source_page": "practice"},
        }
        with patch(
            "applied_math_return_insight.load_latest_applied_math_insight_for_app",
            return_value=cloud_insight,
        ), patch("applied_math_return_insight.sync_dismissed_insights_from_cloud"), patch(
            "applied_math_return_insight.apply_return_source_state",
        ) as mock_apply:
            ok = hydrate_applied_math_insight_for_session(st, "music")
        self.assertTrue(ok)
        self.assertNotIn("_navigate_to_page", st.session_state)
        mock_apply.assert_not_called()

    def test_reconcile_clears_stale_navigate(self) -> None:
        st = MagicMock()
        st.session_state = {"_navigate_to_page": "backing", "_suite_cloud_target_page": "backing"}
        st.query_params = {}
        reconcile_stale_page_navigation(st, "music")
        self.assertNotIn("_navigate_to_page", st.session_state)


class TestMusicWorkspaceEnvelope(unittest.TestCase):
    def test_build_disk_state_includes_envelope(self) -> None:
        st = MagicMock()
        st.session_state = {
            "studio_page": "practice",
            "instrument": "Piano",
            "active_catalog_pick_key": "pop:test",
            "selected_song": {"title": "Test", "pick_key": "pop:test"},
            "level": "Intermediate",
            "focus": "Chords",
            "display_key": "C",
        }
        with patch("music_persistent_state.build_music_local_state") as mock_core:
            mock_core.return_value = {
                "studio_page": "practice",
                "pick_key": "pop:test",
                "instrument": "Piano",
            }
            state = build_music_disk_state(st)
        self.assertIn("music_workspace_state", state)
        meta = state["music_workspace_state"]
        self.assertEqual(meta.get("schema_version"), 1)
        self.assertEqual(meta.get("studio_page"), "practice")


if __name__ == "__main__":
    unittest.main()
