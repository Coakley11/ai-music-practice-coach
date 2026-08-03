"""Visible Phase 1 live-path diagnostics (?dev=1)."""

from __future__ import annotations

from typing import Any


def render_phase1_live_path_diagnostics(st: Any, session: dict[str, Any]) -> None:
    try:
        from music_global_control_diagnostics import collect_global_control_diagnostics
        from music_studio_page_diagnostics import collect_studio_page_diagnostics
    except ImportError:
        return

    page_diag = collect_studio_page_diagnostics(session)
    global_diag = collect_global_control_diagnostics(session)

    with st.sidebar.expander("Phase 1 live-path (?dev=1)", expanded=False):
        st.markdown("**Studio page**")
        for key in (
            "clicked_page",
            "page_change_origin",
            "canonical_page_after_click",
            "session_page_after_click",
            "save_payload_core_page",
            "save_payload_session_page",
            "save_payload_workspace_page",
            "save_payload_studio_nav_page",
            "save_core_page",
            "save_session_page",
            "save_workspace_page",
            "save_studio_nav_page",
            "confirmed_revision",
            "page_change_cloud_confirmed",
            "hydrated_studio_page",
            "canonical_page_before_widget",
            "widget_default_page",
            "widget_returned_page",
            "final_rendered_page",
            "page_restore_overwrite_source",
            "page_restore_overwrite_function",
        ):
            val = page_diag.get(key)
            if val is not None:
                st.caption(f"`{key}`: {val!r}")

        st.markdown("**Global controls**")
        by_field = global_diag.get("by_field") if isinstance(global_diag.get("by_field"), dict) else {}
        for field in ("instrument", "level", "focus"):
            row = by_field.get(field) if isinstance(by_field, dict) else {}
            if not isinstance(row, dict):
                row = {}
            st.caption(
                f"**{field}** widget=`{session.get(field)!r}` "
                f"canonical=`{row.get('final_canonical_value') or global_diag.get(f'{field}_final_canonical_value')!r}`"
            )
            for suffix in (
                "attempted_widget_value",
                "canonical_before",
                "canonical_after_callback",
                "final_canonical_value",
                "final_widget_value",
                "overwrite_source",
                "overwrite_function",
            ):
                val = row.get(suffix) or global_diag.get(f"{field}_{suffix}")
                if val is not None:
                    st.caption(f"  `{suffix}`: {val!r}")
        for key in (
            "restore_projection_applied_this_run",
            "creative_projection_attempted",
            "creative_projection_blocked_as_non_authoritative",
        ):
            val = global_diag.get(key)
            if val is not None:
                st.caption(f"`{key}`: {val!r}")

        try:
            from creative_tab_tool_persistence import collect_creative_tab_tool_diagnostics

            tab_diag = collect_creative_tab_tool_diagnostics(session)
        except ImportError:
            tab_diag = {}

        st.markdown("**Creative tool/tab persistence**")
        for key in (
            "hydrated_tool_tab_values",
            "canonical_values",
            "widget_values",
            "current_run_user_selection_event",
            "last_selector_transaction",
            "belongs_to_current_run",
            "transaction_confirmed",
            "user_selection_event",
            "save_reason",
            "reserved_revision",
            "confirmed_revision",
            "confirmation_status",
            "confirmation_stage",
            "confirmation_checks",
            "authoritative_refetched_values",
            "projection_source",
            "overwrite_source",
            "startup_write_attempted",
            "migration_reason",
            "violations",
            "selector_hydration_trace",
        ):
            val = tab_diag.get(key)
            if val is not None:
                st.caption(f"`{key}`: {val!r}")

        try:
            from creative_mission_config_persistence import collect_creative_mission_config_diagnostics

            mission_diag = collect_creative_mission_config_diagnostics(session)
        except ImportError:
            mission_diag = {}

        st.markdown("**Creative mission config (Item 2)**")
        for key in (
            "hydrated_mission_config",
            "canonical_values",
            "cloud_save_requested",
            "cloud_save_ok",
            "startup_write_attempted",
            "violations",
            "last_user_event",
            "last_chord_click_trace",
            "last_target_identity_mismatch",
            "persistence_journal",
            "widget_values",
            "metrics_widget_projection",
        ):
            val = mission_diag.get(key) if key != "last_user_event" else session.get("_creative_mission_config_last_user_event")
            if val is not None:
                st.caption(f"`{key}`: {val!r}")

        try:
            from creative_mission_artifact_persistence import collect_creative_mission_artifact_diagnostics

            artifact_diag = collect_creative_mission_artifact_diagnostics(session)
        except ImportError:
            artifact_diag = {}

        st.markdown("**Creative mission artifacts (Item 3)**")
        for key in (
            "hydrated_mission_artifacts",
            "canonical_values",
            "session_artifact_values",
            "cloud_save_requested",
            "cloud_save_ok",
            "startup_write_attempted",
            "violations",
            "last_user_event",
        ):
            val = artifact_diag.get(key) if key != "last_user_event" else session.get(
                "_creative_mission_artifact_last_user_event"
            )
            if val is not None:
                st.caption(f"`{key}`: {val!r}")

        try:
            from creative_artifact_global_key_guard import collect_creative_artifact_global_key_diagnostics

            key_guard_diag = collect_creative_artifact_global_key_diagnostics(session)
        except ImportError:
            key_guard_diag = {}

        if key_guard_diag:
            st.markdown("**Creative artifact global key guard**")
            for key in (
                "prior_global_keys",
                "session_keys_after_freeze",
                "artifact_key_center",
                "save_reason",
                "writes",
                "violations",
            ):
                val = key_guard_diag.get(key)
                if val is not None:
                    st.caption(f"`{key}`: {val!r}")

        try:
            from creative_context_snapshot_persistence import render_item4_creative_context_snapshot_panel

            render_item4_creative_context_snapshot_panel(st, session)
        except ImportError:
            st.markdown("**Creative context snapshots (Item 4)**")
            st.caption("`item4_module`: unavailable (ImportError)")
        except Exception as exc:
            st.markdown("**Creative context snapshots (Item 4)**")
            st.caption(f"`item4_panel_error`: {exc!r}")

        try:
            from phase1_item5_refresh_certification import render_phase1_item5_refresh_certification_panel

            render_phase1_item5_refresh_certification_panel(st, session)
        except ImportError:
            st.markdown("**Phase 1 Item 5 — Refresh / cold reboot certification**")
            st.caption("`item5_module`: unavailable (ImportError)")
        except Exception as exc:
            st.markdown("**Phase 1 Item 5 — Refresh / cold reboot certification**")
            st.caption(f"`item5_panel_error`: {exc!r}")

        try:
            from phase1_item8_stale_write_certification import render_phase1_item8_stale_write_certification_panel

            render_phase1_item8_stale_write_certification_panel(st, session)
        except ImportError:
            st.markdown("**Phase 1 Item 8 — Stale-device revision protection**")
            st.caption("`item8_module`: unavailable (ImportError)")
        except Exception as exc:
            st.markdown("**Phase 1 Item 8 — Stale-device revision protection**")
            st.caption(f"`item8_panel_error`: {exc!r}")

        try:
            from mission_backing_handoff_persistence import collect_mission_backing_handoff_diagnostics

            handoff_diag = collect_mission_backing_handoff_diagnostics(session)
        except ImportError:
            handoff_diag = {}

        if handoff_diag:
            st.markdown("**Mission Backing handoff (Item 3 nav)**")
            for key in (
                "navigation_callback",
                "page_before",
                "page_after",
                "backing_subview_before",
                "backing_subview_after",
                "final_handoff_upsert",
                "authoritative_confirmation",
                "refresh_hydration_trace",
                "post_confirm_overwrite",
                "studio_nav_state_before",
                "studio_nav_state_after",
                "backing_view_state_before",
                "backing_view_state_after",
                "payload_page_fields",
                "practice_lick_present_in_payload",
                "practice_lick_present_after",
                "save_reason",
                "reserved_revision",
                "confirmed_revision",
                "upsert_result",
                "authoritative_refetched_page",
                "authoritative_refetched_backing_subview",
                "overwrite_source",
                "violations",
            ):
                val = handoff_diag.get(key)
                if val is not None:
                    st.caption(f"`{key}`: {val!r}")

        try:
            from display_key_sidebar_persistence_trace import collect_display_key_sidebar_trace

            dk_trace = collect_display_key_sidebar_trace(session)
        except ImportError:
            dk_trace = {}

        if dk_trace:
            st.markdown("**Display key sidebar (corrective save)**")
            for key in (
                "events",
                "stages",
                "save_transaction",
                "last_stage",
                "violations",
                "last_event",
                "widget_before",
                "widget_after",
                "callback_invoked",
                "display_key_change_source",
                "session_display_key",
                "canonical_display_key",
                "skipped_projection",
                "resolver_key",
                "backing_key",
                "save_reason",
                "cloud_save_requested",
                "cloud_save_ok",
                "transaction_id",
                "confirmation_forensic",
                "failure_code",
            ):
                val = dk_trace.get(key)
                if val is not None:
                    st.caption(f"`{key}`: {val!r}")


__all__ = ["render_phase1_live_path_diagnostics"]
