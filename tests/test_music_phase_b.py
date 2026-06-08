"""Music Phase B — workspace sync, page ownership, Music Coach stub."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    SESSION_RETURN_PAGE_KEY,
    MUSIC_COACH_INSIGHT_PANEL_KEY,
    _insight_has_displayable_content,
    _insight_loaded_placeholder,
    hydrate_applied_math_insight_for_session,
    insight_page_scope_decision,
    reconcile_stale_page_navigation,
    render_suite_applied_math_insight_for_page,
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

    def test_placeholder_insight_is_not_displayable(self) -> None:
        placeholder = _insight_loaded_placeholder("music")
        insight = {
            "source_app": "music",
            "conclusion": placeholder,
            "question": "",
        }
        self.assertFalse(_insight_has_displayable_content(insight))

    def test_real_insight_is_displayable(self) -> None:
        insight = {
            "source_app": "music",
            "conclusion": "Slow down the chorus.",
            "question": "How should I practice?",
        }
        self.assertTrue(_insight_has_displayable_content(insight))

    def test_insight_render_skips_wrong_page_without_card(self) -> None:
        st = MagicMock()
        st.session_state = {
            SESSION_PENDING_KEY: {
                "source_app": "music",
                "source_page": "backing",
                "conclusion": "Use a metronome.",
                "question": "Backing tips?",
            }
        }
        with patch("applied_math_return_insight.render_applied_math_insight_panel") as mock_panel:
            ok = render_suite_applied_math_insight_for_page(
                st,
                source_app="music",
                source_page="practice",
            )
        self.assertFalse(ok)
        mock_panel.assert_not_called()
        self.assertFalse(st.session_state.get("_ami_insight_card_rendered"))

    def test_insight_panel_uses_stable_container_key(self) -> None:
        self.assertEqual(MUSIC_COACH_INSIGHT_PANEL_KEY, "music_coach_insight_panel")


class TestStudioPageCloudSave(unittest.TestCase):
    def test_navigate_studio_page_triggers_cloud_save(self) -> None:
        from studio_nav_history import init_nav_history, navigate_studio_page

        state = {"studio_page": "practice"}
        init_nav_history(state)
        with patch("music_persistent_state.after_studio_page_change") as mock_after:
            self.assertTrue(navigate_studio_page(state, "backing"))
        mock_after.assert_called_once()

    def test_after_studio_page_change_force_saves(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "backing", "instrument": "Piano"}
        with patch("music_persistent_state.force_save_music_state") as mock_save, patch(
            "music_persistent_state.claim_studio_page_ownership"
        ), patch("suite_user_persistence._release_user_page_ownership_after_save"):
            from music_persistent_state import after_studio_page_change

            after_studio_page_change(st, st.session_state)
        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args.kwargs.get("reason"), "page_change")


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
