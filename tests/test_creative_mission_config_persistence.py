"""Phase 1 Item 2 — mission configuration persistence."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from creative_mission_config_persistence import (
    CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY,
    CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY,
    CREATIVE_MISSION_PERSISTENCE_REQUESTED_KEY,
    CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY,
    IMPROV_MISSION_SECTION_MAP_SESSION_KEY,
    SAVE_REASON_MISSION_PICK,
    SAVE_REASON_MISSION_TARGET,
    SAVE_REASON_MISSION_METRICS,
    VIOLATION_PASSIVE_MISSION_STARTUP_WRITE,
    VIOLATION_POST_INSTANTIATION_WIDGET_WRITE,
    VIOLATION_TARGET_IDENTITY_MISMATCH,
    canonical_mission_config_value,
    commit_mission_config_to_canonical,
    handle_user_mission_metrics_change,
    handle_user_mission_pick_change,
    handle_user_mission_target_selection,
    mark_mission_widgets_instantiated,
    mission_target_identity_valid,
    note_passive_mission_config_persist,
    project_mission_config_from_canonical_before_widgets,
    should_gather_mission_config_from_session,
    snapshot_hydrated_mission_config,
    sync_mission_target_from_canonical,
)
from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    gather_creative_workspace_from_session,
    sync_creative_workspace_state_before_persist,
)


class TestMissionConfigGather(unittest.TestCase):
    def test_autosave_does_not_overwrite_canonical_mission_pick(self) -> None:
        ss: dict = {
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_active_mission": "Use only chord tones",
                "improv_mission_pick": "Use only chord tones",
            },
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {
                "improv_active_mission": "Use only chord tones",
                "improv_mission_pick": "Use only chord tones",
            },
            "improv_mission_pick": "Rhythm-first, note-second",
            "improv_active_mission": "Rhythm-first, note-second",
        }
        self.assertFalse(
            should_gather_mission_config_from_session(
                ss, "improv_mission_pick", "Rhythm-first, note-second", persist_reason="autosave"
            )
        )
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_mission_pick"), "Use only chord tones")

    def test_user_save_reason_skips_stale_session_gather(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Target tone drill",
            },
            "improv_mission_pick": "Stale pick from widgets",
        }
        self.assertFalse(
            should_gather_mission_config_from_session(
                ss, "improv_mission_pick", "Stale pick from widgets", persist_reason=SAVE_REASON_MISSION_PICK
            )
        )


class TestMissionConfigUserSave(unittest.TestCase):
    def test_pick_change_requests_cloud_save(self) -> None:
        chords = ["Cm", "Fm", "Bb", "Ab"]
        section_map = [("Melody A", chords)]
        ss: dict = {
            "_script_run_seq": 3,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "ii–V–I drill",
                "improv_mission_chord_options": chords,
                "ii_selected_chord_index": 0,
                "ii_selected_chord": "Cm",
                "ii_selected_section": "Melody A",
                "ii_selected_chord_label": "Melody A · Cm",
            },
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY: section_map,
            "improv_mission_chord_options": chords,
            "improv_mission_pick": "ii–V–I drill",
        }
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_pick_change(ss)
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_PICK)
        self.assertEqual(canonical_mission_config_value(ss, "improv_mission_pick"), "ii–V–I drill")

    def test_mission_change_preserves_valid_canonical_target_over_stale_session_index(self) -> None:
        chords = ["Cm", "Fm", "Bb", "Ab"]
        section_map = [("Melody A", chords)]
        ss: dict = {
            "_script_run_seq": 20,
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_active_mission": "Use only chord tones",
                "improv_mission_pick": "Use only chord tones",
                "improv_mission_chord_options": chords,
                "ii_selected_chord_index": 3,
                "ii_selected_chord": "Ab",
                "ii_selected_section": "Melody A",
                "ii_selected_chord_label": "Melody A · Ab",
            },
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY: section_map,
            "improv_mission_chord_options": chords,
            "improv_mission_pick": "Create tension on dominant chords",
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Ab",
            "ii_selected_section": "Melody A",
            "ii_selected_chord_label": "Melody A · Ab",
            "improv_intelligence_tab": "Missions",
        }
        self.assertTrue(
            mission_target_identity_valid(
                chords,
                section_map,
                index=3,
                chord="Ab",
                section="Melody A",
                label="Melody A · Ab",
            )
        )
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_pick_change(ss)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_PICK)
        idx = canonical_mission_config_value(ss, "ii_selected_chord_index")
        ch = canonical_mission_config_value(ss, "ii_selected_chord")
        label = canonical_mission_config_value(ss, "ii_selected_chord_label")
        self.assertEqual(idx, 3)
        self.assertEqual(ch, "Ab")
        self.assertEqual(label, "Melody A · Ab")
        self.assertEqual(chords[int(idx)], ch)
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_TARGET_IDENTITY_MISMATCH, codes)
        ss["_music_build_save_reason"] = SAVE_REASON_MISSION_PICK
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("ii_selected_chord_index"), 3)
        self.assertEqual(gathered.get("ii_selected_chord"), "Ab")


class TestMissionConfigPassiveWrite(unittest.TestCase):
    def test_passive_violation_when_canonical_drift(self) -> None:
        ss: dict = {
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {"improv_mission_pick": "Use only chord tones"},
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Rhythm-first, note-second",
            },
        }
        note_passive_mission_config_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)

    def test_sync_autosave_no_passive_when_snapshot_matches(self) -> None:
        ss: dict = {
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Use only chord tones",
            },
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {"improv_mission_pick": "Use only chord tones"},
            "improv_mission_pick": "Use only chord tones",
        }
        snapshot_hydrated_mission_config(ss, source="test")
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        note_passive_mission_config_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)


class TestMissionWidgetLifecycle(unittest.TestCase):
    def test_chord_target_updates_canonical_without_widget_write_after_instantiation(self) -> None:
        ss: dict = {
            "_script_run_seq": 7,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "C",
            "ii_selected_section": "Verse",
            "ii_selected_chord_label": "Verse · C",
        }
        mark_mission_widgets_instantiated(ss)
        before_index = ss["ii_selected_chord_index"]
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_target_selection(
                ss,
                chord="Am",
                section="Chorus",
                chord_index=5,
                chord_label="Chorus · Am",
            )
            save.assert_called_once()
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_TARGET)
        self.assertEqual(ss["ii_selected_chord_index"], before_index)
        self.assertEqual(canonical_mission_config_value(ss, "ii_selected_chord_index"), 5)
        self.assertEqual(canonical_mission_config_value(ss, "ii_selected_chord"), "Am")
        self.assertTrue(ss.get(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY))

    def test_next_rerun_projects_canonical_into_widgets_before_creation(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "ii_selected_chord_index": 5,
                "ii_selected_chord": "Am",
                "ii_selected_section": "Chorus",
                "ii_selected_chord_label": "Chorus · Am",
            },
            "ii_selected_chord_index": 0,
            CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY: True,
        }
        project_mission_config_from_canonical_before_widgets(ss)
        self.assertEqual(ss.get("ii_selected_chord_index"), 5)
        self.assertEqual(ss.get("ii_selected_chord"), "Am")
        self.assertFalse(ss.get(CREATIVE_MISSION_NEEDS_WIDGET_PROJECTION_KEY))

    def test_commit_records_violation_on_post_instantiation_widget_write(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY: True,
            "ii_selected_chord_index": 1,
        }
        commit_mission_config_to_canonical(
            ss,
            reason="test",
            values={"ii_selected_chord_index": 9},
            project_widget_keys=True,
        )
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_POST_INSTANTIATION_WIDGET_WRITE, codes)
        self.assertEqual(ss.get("ii_selected_chord_index"), 1)

    def test_metrics_callback_does_not_rewrite_widget_ids_after_instantiation(self) -> None:
        ss: dict = {
            "_script_run_seq": 8,
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_ai_metric_multiselect": ["Rhythm accuracy"],
            "improv_ai_metric_ids": ["old"],
        }
        mark_mission_widgets_instantiated(ss)
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ):
            handle_user_mission_metrics_change(ss)
        self.assertEqual(ss.get("improv_ai_metric_ids"), ["old"])

    def test_mission_pick_single_persistence_request(self) -> None:
        ss: dict = {
            CREATIVE_WORKSPACE_STATE_KEY: default_creative_workspace_state(),
            "improv_mission_pick": "Target tone drill",
        }
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_pick_change(ss)
            self.assertEqual(save.call_count, 1)

    def test_second_chord_tile_click_survives_gather_and_next_render_highlight(self) -> None:
        """Regression: stale session index must not revert canonical during target save."""
        chords = ["C", "Dm", "Em", "F", "G", "Am"]
        ss: dict = {
            "_script_run_seq": 12,
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "ii_selected_chord_index": 0,
                "ii_selected_chord": "C",
                "ii_selected_section": "Verse",
                "ii_selected_chord_label": "Verse · C",
            },
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "C",
            "ii_selected_section": "Verse",
            "ii_selected_chord_label": "Verse · C",
            "improv_mission_chord_options": list(chords),
        }
        mark_mission_widgets_instantiated(ss)
        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            return_value=True,
        ) as save:
            handle_user_mission_target_selection(
                ss,
                chord="Am",
                section="Chorus",
                chord_index=5,
                chord_label="Chorus · Am",
                button_key="ii_chord_tile_test_chorus_5_Am",
            )
            self.assertEqual(save.call_count, 1)
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_TARGET)
        self.assertEqual(ss.get("ii_selected_chord_index"), 0)
        self.assertEqual(canonical_mission_config_value(ss, "ii_selected_chord_index"), 5)
        ss["_music_build_save_reason"] = SAVE_REASON_MISSION_TARGET
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("ii_selected_chord_index"), 5)
        self.assertEqual(gathered.get("ii_selected_chord"), "Am")
        project_mission_config_from_canonical_before_widgets(ss)
        highlight_idx = sync_mission_target_from_canonical(ss)
        self.assertEqual(highlight_idx, 5)
        self.assertEqual(ss.get("ii_selected_chord_index"), 5)
        trace = (ss.get("_creative_mission_config_diag") or {}).get("last_chord_click_trace") or {}
        self.assertTrue(trace.get("callback_invoked"))
        self.assertEqual(trace.get("args", {}).get("chord_index"), 5)


class TestMissionMetricsPassiveWrite(unittest.TestCase):
    def test_metrics_change_one_transaction_no_passive_violation(self) -> None:
        section_map = [("Melody A", ["Cm", "Fm", "Bb", "Ab"])]
        chords = ["Cm", "Fm", "Bb", "Ab"]
        ss: dict = {
            "_script_run_seq": 41,
            "_creative_selector_hydration_complete": True,
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {
                "improv_ai_metric_ids": ["melodic_diversity_goal"],
                "improv_mission_pick": "Use only 5 notes in one register",
            },
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Use only 5 notes in one register",
                "improv_mission_chord_options": chords,
                "ii_selected_chord_index": 3,
                "ii_selected_chord": "Ab",
                "ii_selected_section": "Melody A",
                "ii_selected_chord_label": "Melody A · Ab",
                "improv_ai_metric_ids": ["melodic_diversity_goal"],
            },
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY: section_map,
            "improv_mission_chord_options": chords,
            "improv_ai_metric_multiselect": ["phrase_structure", "melodic_diversity_goal"],
            "improv_intelligence_tab": "Missions",
        }
        def _fake_cloud_save(session: dict, *, save_reason: str) -> bool:
            d = session.setdefault("_creative_mission_config_diag", {})
            d["cloud_save_requested"] = True
            d["cloud_save_ok"] = True
            session["_creative_mission_user_save_this_run"] = session.get("_script_run_seq")
            return True

        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            side_effect=_fake_cloud_save,
        ) as save:
            handle_user_mission_metrics_change(ss)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(save.call_args.kwargs.get("save_reason"), SAVE_REASON_MISSION_METRICS)
        self.assertEqual(
            canonical_mission_config_value(ss, "improv_ai_metric_ids"),
            ["phrase_structure", "melodic_diversity_goal"],
        )
        snap = ss.get(CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY) or {}
        self.assertEqual(snap.get("improv_ai_metric_ids"), ["phrase_structure", "melodic_diversity_goal"])
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)
        diag = ss.get("_creative_mission_config_diag") or {}
        self.assertFalse(diag.get("startup_write_attempted"))
        self.assertTrue(diag.get("cloud_save_requested"))
        sync_creative_workspace_state_before_persist(ss, reason="autosave")
        codes_after = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes_after)
        ss["_music_build_save_reason"] = SAVE_REASON_MISSION_METRICS
        gathered = gather_creative_workspace_from_session(ss)
        self.assertEqual(gathered.get("improv_ai_metric_ids"), ["phrase_structure", "melodic_diversity_goal"])

    def test_passive_violation_still_detects_real_startup_drift(self) -> None:
        ss: dict = {
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {"improv_mission_pick": "Use only chord tones"},
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_mission_pick": "Rhythm-first, note-second",
            },
        }
        note_passive_mission_config_persist(ss, reason="autosave")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertIn(VIOLATION_PASSIVE_MISSION_STARTUP_WRITE, codes)
        self.assertTrue(ss.get("_creative_mission_passive_startup_write_requested"))


class TestMissionMetricsWidgetProjection(unittest.TestCase):
    def test_canonical_partial_list_projects_to_widget_without_extra_defaults(self) -> None:
        ss: dict = {
            "_creative_selector_hydration_complete": True,
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_ai_metric_ids": ["phrase_structure"],
                "improv_active_mission": "Use only 5 notes in one register",
            },
            "improv_ai_metric_ids": ["phrase_structure", "melodic_diversity_goal"],
            "improv_ai_metric_multiselect": ["Phrase structure", "Melodic diversity"],
        }
        from creative_mission_config_persistence import (
            VIOLATION_METRICS_WIDGET_DIVERGENCE,
            audit_mission_metrics_widget_divergence,
            project_mission_metrics_widgets_from_canonical,
        )

        project_mission_metrics_widgets_from_canonical(ss, overwrite=True, key_prefix="improv")
        self.assertEqual(ss.get("improv_ai_metric_ids"), ["phrase_structure"])
        self.assertEqual(ss.get("improv_ai_metric_multiselect"), ["Phrase structure"])
        audit_mission_metrics_widget_divergence(ss, key_prefix="improv")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_METRICS_WIDGET_DIVERGENCE, codes)

    def test_user_removes_metric_then_refresh_projection_keeps_single_id(self) -> None:
        section_map = [("Melody A", ["Cm", "Fm", "Bb", "Ab"])]
        chords = ["Cm", "Fm", "Bb", "Ab"]
        ss: dict = {
            "_script_run_seq": 55,
            "_creative_selector_hydration_complete": True,
            CREATIVE_MISSION_HYDRATED_SNAPSHOT_KEY: {
                "improv_ai_metric_ids": ["phrase_structure", "melodic_diversity_goal"],
            },
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "improv_ai_metric_ids": ["phrase_structure", "melodic_diversity_goal"],
            },
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY: section_map,
            "improv_mission_chord_options": chords,
            "improv_ai_metric_multiselect": ["phrase_structure", "melodic_diversity_goal"],
        }

        def _fake_cloud_save(session: dict, *, save_reason: str) -> bool:
            session["_creative_mission_user_save_this_run"] = session.get("_script_run_seq")
            return True

        with patch(
            "creative_mission_config_persistence.request_mission_config_cloud_save",
            side_effect=_fake_cloud_save,
        ):
            ss["improv_ai_metric_multiselect"] = ["phrase_structure"]
            handle_user_mission_metrics_change(ss)
        self.assertEqual(canonical_mission_config_value(ss, "improv_ai_metric_ids"), ["phrase_structure"])
        ss["improv_ai_metric_multiselect"] = ["Phrase structure", "Melodic diversity"]
        from creative_mission_config_persistence import (
            VIOLATION_METRICS_WIDGET_DIVERGENCE,
            audit_mission_metrics_widget_divergence,
            project_mission_config_from_canonical,
            project_mission_metrics_widgets_from_canonical,
        )

        project_mission_config_from_canonical(ss, overwrite=True)
        project_mission_metrics_widgets_from_canonical(ss, overwrite=True, key_prefix="improv")
        self.assertEqual(canonical_mission_config_value(ss, "improv_ai_metric_ids"), ["phrase_structure"])
        self.assertEqual(ss.get("improv_ai_metric_ids"), ["phrase_structure"])
        self.assertEqual(ss.get("improv_ai_metric_multiselect"), ["Phrase structure"])
        audit_mission_metrics_widget_divergence(ss, key_prefix="improv")
        codes = [v.get("code") for v in (ss.get("_creative_mission_config_diag") or {}).get("violations") or []]
        self.assertNotIn(VIOLATION_METRICS_WIDGET_DIVERGENCE, codes)


if __name__ == "__main__":
    unittest.main()
