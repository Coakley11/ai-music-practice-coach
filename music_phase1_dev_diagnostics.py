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
        ):
            val = mission_diag.get(key) if key != "last_user_event" else session.get("_creative_mission_config_last_user_event")
            if val is not None:
                st.caption(f"`{key}`: {val!r}")


__all__ = ["render_phase1_live_path_diagnostics"]
