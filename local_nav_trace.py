"""?dev=1 checkpoints for local studio_page navigation (phone Songs → Backing)."""

from __future__ import annotations

from typing import Any

LOCAL_NAV_CHECKPOINTS_KEY = "_music_local_nav_checkpoints"
_MAX_CHECKPOINTS = 24

__all__ = (
    "LOCAL_NAV_CHECKPOINTS_KEY",
    "record_local_nav_checkpoint",
    "render_local_nav_trace_sidebar",
    "snapshot_local_nav_fields",
)


def snapshot_local_nav_fields(session: dict[str, Any]) -> dict[str, Any]:
    nav_meta = session.get("studio_nav_state")
    ws_meta = session.get("music_workspace_state")
    nav_page = ""
    nav_last_write = ""
    if isinstance(nav_meta, dict):
        nav_page = str(nav_meta.get("studio_page") or "").strip()
        nav_last_write = str(nav_meta.get("last_write_reason") or "").strip()
    ws_page = ""
    if isinstance(ws_meta, dict):
        ws_page = str(ws_meta.get("studio_page") or "").strip()
    return {
        "studio_page": str(session.get("studio_page") or "").strip(),
        "studio_nav_state_page": nav_page,
        "studio_nav_last_write": nav_last_write,
        "normalized_studio_page": str(session.get("studio_page") or "").strip(),
        "active_page_source": session.get("active_page_source"),
        "_suite_page_user_nav": bool(session.get("_suite_page_user_nav")),
        "page_owner_flag": bool(session.get("_suite_page_user_nav")),
        "_suite_user_owned_page": session.get("_suite_user_owned_page"),
        "restore_decision": session.get("_suite_page_overwrite_source")
        or session.get("_suite_restore_decision"),
        "page_overwrite_source": session.get("_suite_page_overwrite_source"),
        "music_workspace_state_studio_page": ws_page,
        "_active_page_tracker": session.get("_studio_active_page_id"),
        "_suite_last_persisted_page": session.get("_suite_last_persisted_page"),
    }


def record_local_nav_checkpoint(
    st: Any,
    stage: str,
    *,
    session: dict[str, Any] | None = None,
    intent: str = "",
) -> None:
    """Append a nav snapshot for ?dev=1 (answers: set backing then overwritten?)."""
    ss = session if session is not None else st.session_state
    row = {"stage": str(stage), "intent": intent or None, **snapshot_local_nav_fields(ss)}
    checkpoints = ss.get(LOCAL_NAV_CHECKPOINTS_KEY)
    if not isinstance(checkpoints, list):
        checkpoints = []
    checkpoints.append(row)
    if len(checkpoints) > _MAX_CHECKPOINTS:
        checkpoints = checkpoints[-_MAX_CHECKPOINTS:]
    ss[LOCAL_NAV_CHECKPOINTS_KEY] = checkpoints
    try:
        from music_persistence_trace import update_trace

        update_trace(
            st,
            studio_page_raw=row.get("studio_page"),
            final_studio_page=row.get("studio_page"),
            normalized_studio_page=row.get("normalized_studio_page"),
            page_owner_flag=row.get("page_owner_flag"),
            music_workspace_state_studio_page=row.get("music_workspace_state_studio_page"),
            restore_decision=row.get("restore_decision"),
            page_overwrite_source=row.get("page_overwrite_source"),
            local_nav_last_stage=stage,
            local_nav_last_studio_page=row.get("studio_page"),
        )
    except ImportError:
        pass


def render_local_nav_trace_sidebar(st: Any) -> None:
    ss = st.session_state
    checkpoints = ss.get(LOCAL_NAV_CHECKPOINTS_KEY)
    if not isinstance(checkpoints, list) or not checkpoints:
        st.text("local nav checkpoints: (none yet — tap Backing from Songs)")
        return
    last = checkpoints[-1]
    st.text(f"local_nav_last_stage: {last.get('stage')}")
    for label in (
        "studio_page raw",
        "final_studio_page",
        "normalized studio_page",
        "active_page_source",
        "_suite_page_user_nav",
        "page_owner flag",
        "restore_decision",
        "page overwrite source",
        "music_workspace_state studio_page",
        "studio_nav_state page",
        "studio_nav last_write",
        "_suite_user_owned_page",
        "_active_page_tracker",
    ):
        key_map = {
            "studio_page raw": "studio_page",
            "final_studio_page": "studio_page",
            "normalized studio_page": "normalized_studio_page",
            "studio_nav_state page": "studio_nav_state_page",
            "studio_nav last_write": "studio_nav_last_write",
        }
        key = key_map.get(label, label.replace(" ", "_"))
        val = last.get(key)
        if val is not None and val != "":
            st.text(f"{label}: {val}")
    st.markdown("**Local nav checkpoints (this session)**")
    for i, row in enumerate(checkpoints[-8:], start=max(1, len(checkpoints) - 7)):
        st.text(
            f"{i}. [{row.get('stage')}] page=`{row.get('studio_page')}` "
            f"nav=`{row.get('studio_nav_state_page')}` "
            f"write=`{row.get('studio_nav_last_write')}` "
            f"owner=`{row.get('_suite_page_user_nav')}`"
        )
