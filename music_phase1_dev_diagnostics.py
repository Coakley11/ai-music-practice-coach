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
            "page_saved_in_payload",
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
        for field in ("instrument", "level", "focus"):
            st.caption(f"**{field}** session=`{session.get(field)!r}`")
            for suffix in (
                "attempted_widget_value",
                "canonical_before",
                "canonical_after_callback",
                "final_canonical_value",
                "final_widget_value",
                "overwrite_source",
                "overwrite_function",
            ):
                k = f"{field}_{suffix}" if suffix != "attempted_widget_value" else f"widget_attempted_value"
                if suffix == "attempted_widget_value" and global_diag.get("widget_field") != field:
                    continue
                val = global_diag.get(k) if k in global_diag else global_diag.get(suffix)
                if val is not None and (suffix != "attempted_widget_value" or global_diag.get("widget_field") == field):
                    st.caption(f"  `{suffix}`: {val!r}")
        for key in (
            "restore_projection_applied_this_run",
            "creative_projection_attempted",
            "creative_projection_blocked_as_non_authoritative",
        ):
            val = global_diag.get(key)
            if val is not None:
                st.caption(f"`{key}`: {val!r}")


__all__ = ["render_phase1_live_path_diagnostics"]
