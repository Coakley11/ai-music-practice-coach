"""Music Phase B — workspace sync, page ownership, Music Coach stub."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    SESSION_RETURN_CONTEXT_KEY,
    SESSION_RETURN_PAGE_KEY,
    MUSIC_COACH_INSIGHT_PANEL_KEY,
    _insight_has_displayable_content,
    _insight_loaded_placeholder,
    apply_ami_insight_from_query,
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
    def test_claim_studio_page_sets_owned_studio_page(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        st.query_params = {}
        claim_studio_page_ownership(st, "backing")
        self.assertEqual(st.session_state["studio_page"], "backing")
        self.assertEqual(st.session_state.get(SESSION_USER_OWNED_PAGE_KEY), "backing")
        self.assertEqual(st.session_state.get("_music_coach_workspace_page"), "backing")

    def test_picker_ownership_uses_studio_page_not_coach_page(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        st.query_params = {}
        claim_studio_page_ownership(st, "picker")
        self.assertEqual(st.session_state.get(SESSION_USER_OWNED_PAGE_KEY), "picker")
        self.assertEqual(st.session_state.get("_music_coach_workspace_page"), "practice")

    def test_workspace_blob_prefers_studio_page_over_coach_page(self) -> None:
        from suite_user_persistence import _workspace_page_from_blob

        blob = {
            "core": {"studio_page": "picker"},
            "session": {},
            "music_workspace_state": {"page": "practice", "studio_page": "picker"},
        }
        self.assertEqual(_workspace_page_from_blob("music", blob), "picker")

    def test_apply_preserves_local_insight_after_ami_consume(self) -> None:
        from applied_math_return_insight import local_ami_insight_should_preserve

        st = MagicMock()
        insight = {
            "insight_id": "mc-persist",
            "source_app": "music",
            "source_page": "backing",
            "conclusion": "Slow down the chorus.",
            "question": "How do I practice?",
            "_ami_recovery_card": True,
        }
        st.session_state = {
            SESSION_PENDING_KEY: insight,
            "studio_page": "practice",
        }
        self.assertTrue(local_ami_insight_should_preserve(st))
        payload = {
            "core": {"studio_page": "practice"},
            "session": {SESSION_PENDING_KEY: {}},
            "music_workspace_state": {"studio_page": "practice"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True):
            apply_music_disk_state(
                st,
                payload,
                song_picker_catalog={},
                song_library={},
            )
        self.assertEqual(st.session_state[SESSION_PENDING_KEY]["insight_id"], "mc-persist")

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

    def test_recovery_render_consumes_ami_return(self) -> None:
        st = MagicMock()
        placeholder = _insight_loaded_placeholder("music")
        st.session_state = {
            SESSION_PENDING_KEY: {
                "insight_id": "mc1",
                "source_app": "music",
                "source_page": "backing",
                "conclusion": placeholder,
            },
            SESSION_RETURN_PAGE_KEY: "backing",
            "_ami_insight_return_preserve": True,
            "ami_return_forced_page": "backing",
            "ami_return_force_active_page": True,
            "_skip_page_restore_for": "backing",
            "studio_page": "backing",
        }
        st.query_params = {"suite_ami_insight": "mc1", "suite_page": "backing"}

        with patch(
            "applied_math_return_insight._refresh_placeholder_insight_from_cloud",
            return_value=False,
        ), patch(
            "applied_math_return_insight.render_insight_recovery_panel",
            return_value=True,
        ) as mock_recovery, patch(
            "applied_math_return_insight.render_applied_math_insight_panel",
        ) as mock_panel:
            ok = render_suite_applied_math_insight_for_page(
                st,
                source_app="music",
                source_page="backing",
            )

        self.assertTrue(ok)
        mock_recovery.assert_called_once()
        mock_panel.assert_not_called()
        self.assertTrue(st.session_state.get("_ami_insight_card_rendered"))
        self.assertTrue(st.session_state.get("ami_resume_consumed"))
        self.assertNotIn("_ami_insight_return_preserve", st.session_state)
        self.assertNotIn("_skip_page_restore_for", st.session_state)
        self.assertFalse(st.session_state.get("ami_return_force_active_page"))
        self.assertFalse(st.session_state.get("manual_nav_blocked_by_ami_return"))

    def test_merge_recovery_context_marks_displayable_with_question(self) -> None:
        from applied_math_return_insight import _merge_insight_with_recovery_context

        st = MagicMock()
        st.session_state = {SESSION_RETURN_CONTEXT_KEY: {"question": "How should I practice?"}}
        placeholder = _insight_loaded_placeholder("music")
        merged = _merge_insight_with_recovery_context(
            st,
            {
                "insight_id": "mc9",
                "source_app": "music",
                "source_page": "backing",
                "conclusion": placeholder,
            },
            "music",
        )
        self.assertEqual(merged.get("question"), "How should I practice?")
        self.assertTrue(merged.get("_ami_recovery_card"))
        self.assertTrue(_insight_has_displayable_content(merged))

    def test_load_applied_math_insight_prefers_direct_key_lookup(self) -> None:
        from applied_math_return_insight import load_applied_math_insight

        row = {
            "item_key": "deep-id",
            "title": "Coach answer",
            "payload": {
                "insight_id": "deep-id",
                "source_app": "music",
                "conclusion": "Slow down.",
                "question": "Backing tips?",
            },
        }
        with patch(
            "applied_math_return_insight._fetch_insight_saved_row",
            return_value=row,
        ) as mock_fetch:
            loaded = load_applied_math_insight("deep-id", source_app="music")
        mock_fetch.assert_called_once_with("deep-id", source_app="music")
        self.assertEqual(loaded.get("conclusion"), "Slow down.")

    def test_backing_insight_renders_on_backing_studio_page(self) -> None:
        st = MagicMock()
        st.session_state = {
            SESSION_PENDING_KEY: {
                "source_app": "music",
                "source_page": "backing",
                "source_state": {"source_page": "backing", "widget_params": {"studio_page": "backing"}},
                "conclusion": "Slow down the chorus.",
                "question": "How do I practice backing?",
            },
            SESSION_RETURN_PAGE_KEY: "backing",
        }
        with patch("applied_math_return_insight.render_applied_math_insight_panel", return_value=True):
            ok = render_suite_applied_math_insight_for_page(
                st,
                source_app="music",
                source_page="backing",
            )
        self.assertTrue(ok)
        self.assertTrue(st.session_state.get("_ami_insight_card_rendered"))

    def test_apply_insight_schedules_studio_navigation_for_music(self) -> None:
        st = MagicMock()
        st.session_state = {}
        st.query_params = {"suite_ami_insight": "mc2", "suite_page": "backing"}
        insight = {
            "insight_id": "mc2",
            "source_app": "music",
            "source_page": "backing",
            "conclusion": "Use a metronome.",
            "question": "Backing tips?",
        }
        with patch("applied_math_return_insight.load_applied_math_insight", return_value=insight), patch(
            "applied_math_return_insight.apply_return_source_state",
        ):
            ok = apply_ami_insight_from_query(st, "music", force=True)

        self.assertTrue(ok)
        self.assertEqual(st.session_state.get("_navigate_to_studio_page"), "backing")
        self.assertNotIn("_navigate_to_page", st.session_state)

    def test_simple_nav_still_renders_insight(self) -> None:
        from app_ui import USE_SIMPLE_MUSIC_NAV_KEY, render_page_quick_nav, reset_quick_nav_render_diagnostics

        st = MagicMock()
        st.session_state = {USE_SIMPLE_MUSIC_NAV_KEY: True, "studio_page": "backing"}
        reset_quick_nav_render_diagnostics(st.session_state)
        with patch("app_ui._render_simple_nav_row"), patch(
            "app_ui._render_music_coach_insight_below_quick_nav",
        ) as mock_insight:
            render_page_quick_nav(st, current_page="backing", rerun_fn=lambda: None)
        mock_insight.assert_called_once()


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

    def test_build_disk_state_stamps_live_studio_page_over_stale_core(self) -> None:
        st = MagicMock()
        st.session_state = {
            "studio_page": "picker",
            "instrument": "Piano",
            "active_catalog_pick_key": "pop:test",
        }
        with patch("music_persistent_state.build_music_local_state") as mock_core:
            mock_core.return_value = {
                "studio_page": "practice",
                "page": "practice",
                "pick_key": "pop:test",
                "instrument": "Piano",
            }
            state = build_music_disk_state(st)
        self.assertEqual(state["core"]["studio_page"], "picker")
        self.assertEqual(state["session"]["studio_page"], "picker")
        self.assertEqual(state["music_workspace_state"]["studio_page"], "picker")
        self.assertEqual(state["music_workspace_state"]["page"], "practice")

    def test_page_change_save_stamps_backing_over_restored_picker(self) -> None:
        st = MagicMock()
        st.session_state = {
            "studio_page": "backing",
            "_suite_pending_save_reason": "page_change",
            "_suite_page_change_save_page": "backing",
            "studio_nav_state": {"studio_page": "backing", "last_write_reason": "local_nav_preserve"},
            "music_workspace_state": {},
            "instrument": "Piano",
            "active_catalog_pick_key": "pop:test",
            "selected_song": {"title": "Test", "pick_key": "pop:test"},
        }
        with patch("music_persistent_state.build_music_local_state") as mock_core:
            mock_core.return_value = {
                "studio_page": "picker",
                "page": "picker",
                "pick_key": "pop:test",
                "instrument": "Piano",
                "song": "",
                "artist": "",
                "focus": "",
                "display_key": "",
                "practice_focus_section": "",
                "level": "",
                "mode": "",
            }
            state = build_music_disk_state(st)
        self.assertEqual(state["core"]["studio_page"], "backing")
        self.assertEqual(state["session"]["studio_page"], "backing")
        self.assertEqual(state["music_workspace_state"]["studio_page"], "backing")
        self.assertEqual(state["music_workspace_state"]["page"], "backing")
        self.assertEqual(state["studio_nav_state"]["studio_page"], "backing")
        self.assertEqual(state["studio_nav_state"]["page"], "backing")
        stamp = st.session_state.get("_music_save_payload_stamp_trace") or {}
        self.assertEqual(stamp.get("save_payload_source"), "_suite_page_change_save_page")
        self.assertEqual(stamp.get("save_payload_workspace_page"), "backing")

    def test_page_change_hint_wins_over_stale_session_studio_page(self) -> None:
        st = MagicMock()
        st.session_state = {
            "studio_page": "picker",
            "_suite_pending_save_reason": "page_change",
            "_suite_page_change_save_page": "backing",
            "studio_nav_state": {"studio_page": "backing", "last_write_reason": "local_nav_preserve"},
            "music_workspace_state": {"studio_page": "picker", "page": "picker"},
            "instrument": "Piano",
            "active_catalog_pick_key": "pop:test",
            "selected_song": {"title": "Test", "pick_key": "pop:test"},
        }
        with patch("music_persistent_state.build_music_local_state") as mock_core:
            mock_core.return_value = {
                "studio_page": "picker",
                "page": "picker",
                "pick_key": "pop:test",
                "instrument": "Piano",
                "song": "",
                "artist": "",
                "focus": "",
                "display_key": "",
                "practice_focus_section": "",
                "level": "",
                "mode": "",
            }
            state = build_music_disk_state(st)
        self.assertEqual(state["core"]["studio_page"], "backing")
        self.assertEqual(state["session"]["studio_page"], "backing")
        self.assertEqual(state["music_workspace_state"]["studio_page"], "backing")
        self.assertEqual(state["studio_nav_state"]["studio_page"], "backing")
        self.assertEqual(state["studio_nav_state"]["page"], "backing")
        stamp = st.session_state.get("_music_save_payload_stamp_trace") or {}
        self.assertEqual(stamp.get("save_payload_source"), "_suite_page_change_save_page")
        self.assertEqual(stamp.get("save_payload_core_page"), "backing")
        self.assertEqual(stamp.get("save_payload_session_page"), "backing")
        self.assertEqual(stamp.get("save_payload_workspace_page"), "backing")
        self.assertEqual(stamp.get("save_payload_studio_nav_page"), "backing")

    def test_resolve_page_change_prefers_hint_over_stale_studio_page(self) -> None:
        from music_persistent_state import _resolve_live_studio_page_for_save

        page, source = _resolve_live_studio_page_for_save(
            {"studio_page": "picker", "_suite_page_change_save_page": "backing"},
            save_reason="page_change",
        )
        self.assertEqual(page, "backing")
        self.assertEqual(source, "_suite_page_change_save_page")

    def test_page_change_live_studio_page_wins_over_stale_hint_and_workspace(self) -> None:
        """Phone Backing trace: live studio_page=backing, stale hint/workspace picker."""
        st = MagicMock()
        st.session_state = {
            "studio_page": "backing",
            "_suite_page_user_nav": True,
            "_suite_pending_save_reason": "page_change",
            "_suite_page_change_save_page": "picker",
            "studio_nav_state": {
                "studio_page": "backing",
                "page": "backing",
                "last_write_reason": "local_nav_preserve",
            },
            "music_workspace_state": {"studio_page": "picker", "page": "picker"},
            "instrument": "Piano",
            "active_catalog_pick_key": "pop:test",
            "selected_song": {"title": "Test", "pick_key": "pop:test"},
        }
        with patch("music_persistent_state.build_music_local_state") as mock_core:
            mock_core.return_value = {
                "studio_page": "picker",
                "page": "picker",
                "pick_key": "pop:test",
                "instrument": "Piano",
                "song": "",
                "artist": "",
                "focus": "",
                "display_key": "",
                "practice_focus_section": "",
                "level": "",
                "mode": "",
            }
            state = build_music_disk_state(st)
        self.assertEqual(state["core"]["studio_page"], "backing")
        self.assertEqual(state["session"]["studio_page"], "backing")
        self.assertEqual(state["music_workspace_state"]["studio_page"], "backing")
        self.assertEqual(state["studio_nav_state"]["studio_page"], "backing")
        stamp = st.session_state.get("_music_save_payload_stamp_trace") or {}
        self.assertEqual(stamp.get("save_payload_source"), "session_state.studio_page")
        self.assertEqual(stamp.get("save_payload_workspace_page"), "backing")

    def test_resolve_page_change_prefers_live_studio_page_when_nav_matches(self) -> None:
        from music_persistent_state import _resolve_live_studio_page_for_save

        page, source = _resolve_live_studio_page_for_save(
            {
                "studio_page": "backing",
                "_suite_page_user_nav": True,
                "_suite_page_change_save_page": "picker",
                "studio_nav_state": {"studio_page": "backing", "page": "backing"},
            },
            save_reason="page_change",
        )
        self.assertEqual(page, "backing")
        self.assertEqual(source, "session_state.studio_page")

    def test_after_studio_page_change_uses_explicit_target_page(self) -> None:
        st = MagicMock()
        st.session_state = {"studio_page": "picker"}
        with patch("music_persistent_state.claim_studio_page_ownership") as mock_claim, patch(
            "music_persistent_state.force_save_music_state",
            return_value=True,
        ) as mock_save, patch("suite_user_persistence._release_user_page_ownership_after_save"):
            from music_persistent_state import after_studio_page_change

            after_studio_page_change(st, st.session_state, target_page="backing")
        mock_claim.assert_called_once_with(st, "backing")
        self.assertEqual(st.session_state.get("_suite_page_change_save_page"), None)
        self.assertEqual(mock_save.call_args.kwargs.get("reason"), "page_change")

    def test_session_page_summary_prefers_workspace_studio_page(self) -> None:
        from suite_cloud_state import session_page_summary

        blob = {
            "core": {"studio_page": "practice", "page": "practice"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }
        page, _summary = session_page_summary("music", blob)
        self.assertEqual(page, "backing")


class TestPersistenceTracePanel(unittest.TestCase):
    def test_deploy_probe_uses_persist_deploy_version(self) -> None:
        from music_persistence_trace import MUSIC_PERSIST_DEPLOY_VERSION
        from suite_deploy_probe import deploy_info

        info = deploy_info()
        self.assertEqual(info["build_marker"], MUSIC_PERSIST_DEPLOY_VERSION)
        self.assertIn("page-change-save-stamp-v3", info["build_marker"])

    def test_snapshot_workspace_restore_always_sets_trace_fields(self) -> None:
        from music_persistence_trace import get_trace, snapshot_workspace_restore_trace

        st = MagicMock()
        st.session_state = {
            "studio_page": "practice",
            "_suite_persist_restore_skip_reason": "workspace already synced",
            "_suite_restore_decision": "skipped",
        }
        st.query_params = {}
        with patch("suite_cloud_state.load_cloud_full_session", return_value=({}, None)):
            snapshot_workspace_restore_trace(st)
        trace = get_trace(st)
        self.assertIn("cloud_fetch_studio_page", trace)
        self.assertEqual(trace.get("restore_skip_reason"), "workspace already synced")
        self.assertEqual(trace.get("final_studio_page"), "practice")
        self.assertEqual(trace.get("restore_decision"), "skipped")

    def test_snapshot_probes_cloud_studio_page(self) -> None:
        from music_persistence_trace import get_trace, snapshot_workspace_restore_trace

        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        cloud = {
            "core": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing"},
        }
        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud, "2026-06-08T18:00:00+00:00"),
        ):
            snapshot_workspace_restore_trace(st)
        trace = get_trace(st)
        self.assertEqual(trace.get("cloud_fetch_studio_page"), "backing")
        self.assertEqual(trace.get("cloud_updated_at"), "2026-06-08T18:00:00+00:00")


class TestStaleResumeLaunchFlags(unittest.TestCase):
    def test_stale_launch_flag_does_not_block_workspace_sync(self) -> None:
        from suite_cloud_state import has_resume_query_params

        st = MagicMock()
        st.session_state = {
            "_suite_resume_launch_music": True,
            "studio_page": "practice",
        }
        st.query_params = {}
        self.assertFalse(has_resume_query_params(st, "music"))
        self.assertNotIn("_suite_resume_launch_music", st.session_state)

    def test_prepare_music_workspace_applies_cloud_when_no_resume_url(self) -> None:
        from music_persistent_state import apply_music_disk_state, prepare_music_workspace

        st = MagicMock()
        st.session_state = {
            "_suite_resume_launch_music": True,
            "studio_page": "practice",
        }
        st.query_params = {}
        cloud_state = {
            "core": {"studio_page": "backing", "pick_key": "pop:test"},
            "session": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-08T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=({"core": {"studio_page": "practice"}}, None, "2026-06-08T12:00:00+00:00"),
        ), patch(
            "music_persistent_state.apply_music_disk_state",
            wraps=lambda st_obj, state, **kw: apply_music_disk_state(
                st_obj,
                state,
                song_picker_catalog={},
                song_library=None,
            ),
        ) as mock_apply, patch(
            "suite_user_persistence.save_user_state",
            return_value=True,
        ):
            ok = prepare_music_workspace(
                st,
                song_picker_catalog={},
                song_library=None,
            )

        self.assertTrue(ok)
        mock_apply.assert_called_once()
        self.assertEqual(st.session_state.get("studio_page"), "backing")
        self.assertNotIn("_suite_resume_launch_music", st.session_state)
        self.assertNotIn("_suite_persist_restore_skip_reason", st.session_state)

    def test_prepare_music_workspace_records_stale_flag_trace(self) -> None:
        from music_persistent_state import prepare_music_workspace
        from music_persistence_trace import get_trace

        st = MagicMock()
        st.session_state = {
            "_suite_resume_launch_music": True,
            "_ami_insight_return_preserve": True,
            "studio_page": "practice",
        }
        st.query_params = {}
        cloud_state = {
            "core": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-08T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=({"core": {"studio_page": "practice"}}, None, "2026-06-08T12:00:00+00:00"),
        ), patch(
            "music_persistent_state.apply_music_disk_state",
        ), patch(
            "suite_user_persistence.save_user_state",
            return_value=True,
        ):
            prepare_music_workspace(
                st,
                song_picker_catalog={},
                song_library=None,
            )

        trace = get_trace(st)
        self.assertEqual(trace.get("live_resume_url_params"), [])
        self.assertIn("_suite_resume_launch_music", trace.get("stale_resume_flags_cleared") or [])
        self.assertFalse(trace.get("should_skip_workspace_restore_for_resume"))
        self.assertFalse(trace.get("ami_return_navigation_active"))

    def test_prepare_music_workspace_applies_cloud_with_suite_pick_key_only(self) -> None:
        from music_persistent_state import apply_music_disk_state, prepare_music_workspace
        from music_persistence_trace import get_trace
        from suite_cloud_state import should_skip_workspace_restore_for_resume

        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        st.query_params = {"suite_pick_key": "Pop|Perfect"}
        cloud_state = {
            "core": {"studio_page": "backing", "pick_key": "Pop|Perfect"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }

        self.assertFalse(should_skip_workspace_restore_for_resume(st, "music", reconcile_first=False))

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-08T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=({"core": {"studio_page": "practice"}}, None, "2026-06-08T12:00:00+00:00"),
        ), patch(
            "music_persistent_state.apply_music_disk_state",
            wraps=lambda st_obj, state, **kw: apply_music_disk_state(
                st_obj,
                state,
                song_picker_catalog={},
                song_library=None,
            ),
        ) as mock_apply, patch(
            "suite_user_persistence.save_user_state",
            return_value=True,
        ):
            ok = prepare_music_workspace(
                st,
                song_picker_catalog={},
                song_library=None,
            )

        self.assertTrue(ok)
        mock_apply.assert_called_once()
        self.assertEqual(st.session_state.get("studio_page"), "backing")
        trace = get_trace(st)
        self.assertEqual(trace.get("live_resume_url_params"), ["suite_pick_key"])
        self.assertTrue(trace.get("has_resume_query_params_result"))
        self.assertFalse(trace.get("should_skip_workspace_restore_for_resume"))
        self.assertNotIn("_suite_persist_restore_skip_reason", st.session_state)


class TestPageSyncRecovery(unittest.TestCase):
    """Regression: phone session saves page_change; Dell restore applies studio_page."""

    def test_phone_backing_page_change_reaches_dell_restore(self) -> None:
        from music_persistent_state import (
            after_studio_page_change,
            apply_music_disk_state,
            claim_studio_page_ownership,
        )

        phone = MagicMock()
        phone.session_state = {"studio_page": "practice"}
        phone.query_params = {}
        claim_studio_page_ownership(phone, "backing")

        with patch("music_persistent_state.force_save_music_state", return_value=True) as mock_save, patch(
            "suite_user_persistence._release_user_page_ownership_after_save"
        ):
            after_studio_page_change(phone, session_state=phone.session_state)

        mock_save.assert_called_once()
        self.assertEqual(mock_save.call_args.kwargs.get("reason"), "page_change")
        self.assertEqual(phone.session_state["studio_page"], "backing")

        dell = MagicMock()
        dell.session_state = {"studio_page": "practice"}
        dell.query_params = {}
        cloud_payload = {
            "core": {"studio_page": "backing", "pick_key": "Pop|Test"},
            "session": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True), patch(
            "applied_math_return_insight.ami_return_navigation_active",
            return_value=False,
        ):
            apply_music_disk_state(
                dell,
                cloud_payload,
                song_picker_catalog={},
                song_library=None,
            )
        self.assertEqual(dell.session_state.get("studio_page"), "backing")

    def test_phone_picker_page_change_reaches_dell_restore(self) -> None:
        from music_persistent_state import (
            after_studio_page_change,
            apply_music_disk_state,
            claim_studio_page_ownership,
        )

        phone = MagicMock()
        phone.session_state = {"studio_page": "backing"}
        phone.query_params = {}
        claim_studio_page_ownership(phone, "picker")

        with patch("music_persistent_state.force_save_music_state", return_value=True), patch(
            "suite_user_persistence._release_user_page_ownership_after_save"
        ):
            after_studio_page_change(phone, session_state=phone.session_state)

        self.assertEqual(phone.session_state["studio_page"], "picker")

        dell = MagicMock()
        dell.session_state = {"studio_page": "backing"}
        cloud_payload = {
            "core": {"studio_page": "picker"},
            "music_workspace_state": {"studio_page": "picker", "page": "practice"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True), patch(
            "applied_math_return_insight.ami_return_navigation_active",
            return_value=False,
        ):
            apply_music_disk_state(
                dell,
                cloud_payload,
                song_picker_catalog={},
                song_library=None,
            )
        self.assertEqual(dell.session_state.get("studio_page"), "picker")

    def test_suite_pick_key_does_not_block_page_restore(self) -> None:
        from music_persistent_state import apply_music_disk_state, prepare_music_workspace
        from suite_cloud_state import should_skip_workspace_restore_for_resume

        st = MagicMock()
        st.session_state = {"studio_page": "practice"}
        st.query_params = {"suite_pick_key": "Pop|Perfect"}
        cloud_state = {
            "core": {"studio_page": "custom", "pick_key": "Pop|Perfect"},
            "music_workspace_state": {"studio_page": "custom", "page": "custom"},
        }
        self.assertFalse(should_skip_workspace_restore_for_resume(st, "music", reconcile_first=False))

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-09T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=({"core": {"studio_page": "practice"}}, None, "2026-06-09T12:00:00+00:00"),
        ), patch(
            "music_persistent_state.apply_music_disk_state",
            wraps=lambda st_obj, state, **kw: apply_music_disk_state(
                st_obj,
                state,
                song_picker_catalog={},
                song_library=None,
            ),
        ), patch("suite_user_persistence.save_user_state", return_value=True):
            ok = prepare_music_workspace(
                st,
                song_picker_catalog={},
                song_library=None,
            )

        self.assertTrue(ok)
        self.assertEqual(st.session_state.get("studio_page"), "custom")

    def test_stale_resume_flags_cleared_before_cloud_restore(self) -> None:
        from music_persistent_state import prepare_music_workspace

        st = MagicMock()
        st.session_state = {
            "_suite_resume_launch_music": True,
            "studio_page": "practice",
        }
        st.query_params = {}
        cloud_state = {
            "core": {"studio_page": "backing"},
            "music_workspace_state": {"studio_page": "backing", "page": "backing"},
        }

        with patch(
            "suite_cloud_state.load_cloud_full_session",
            return_value=(cloud_state, "2026-06-09T16:00:00+00:00"),
        ), patch(
            "suite_user_persistence._load_raw",
            return_value=({"core": {"studio_page": "practice"}}, None, "2026-06-09T12:00:00+00:00"),
        ), patch("music_persistent_state.apply_music_disk_state"), patch(
            "suite_user_persistence.save_user_state",
            return_value=True,
        ):
            prepare_music_workspace(
                st,
                song_picker_catalog={},
                song_library=None,
            )

        self.assertNotIn("_suite_resume_launch_music", st.session_state)


class TestPhaseCCanonicalWiring(unittest.TestCase):
    def test_prepare_canonical_reconciles_studio_and_song(self) -> None:
        from music_persistent_state import prepare_canonical_music_page_state

        session = {
            "studio_nav_state": {"studio_page": "backing"},
            "active_song_state": {
                "pick_key": "Pop|Test",
                "display_key": "C Major",
                "instrument": "Guitar",
                "selected_song": {"pick_key": "Pop|Test", "title": "Test"},
            },
        }
        prepare_canonical_music_page_state(session)
        self.assertEqual(session.get("studio_page"), "backing")
        self.assertEqual(session.get("active_catalog_pick_key"), "Pop|Test")
        self.assertEqual(session.get("display_key"), "C Major")


if __name__ == "__main__":
    unittest.main()
