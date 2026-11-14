"""Streamlit rendering for the Composition Library (Custom Progressions style list)."""
from __future__ import annotations

import html
from typing import Any

SCROLL_ROW_THRESHOLD = 5
PENDING_DELETE_KEY = "composer_library_pending_delete_id"


def _set_pending_delete(session_state: dict, rid: str) -> None:
    """Delete needs a second, explicit confirmation; Cancel just clears the pending id."""
    if rid:
        session_state[PENDING_DELETE_KEY] = rid
    else:
        session_state.pop(PENDING_DELETE_KEY, None)


def render_library_rows(st: Any, session_state: dict, active_song_id: str) -> str:
    """Render every saved composition; returns the id the user asked to open/delete action taken.

    Statuses: "Now Editing" (Studio document) and "Active Song" (global song) are
    independent and can be shown together or on different rows.
    """
    from composition_library import library_rows, status_badges, switch_to_composition
    from composition_session_state import delete_library_document

    rows = library_rows(session_state, active_song_id)
    if not rows:
        st.caption("No saved compositions yet.")
        return ""
    st.caption(f"{len(rows)} composition(s) in your library")
    host = st.container(height=360) if len(rows) > SCROLL_ROW_THRESHOLD else st.container()
    action = ""
    with host:
        for row in rows:
            rid = row["id"]
            # Stacked, not side-by-side: at 375/390 px two side-by-side columns overflowed the
            # scrolling list (600 px of content in 330 px) and pushed the delete button out of reach.
            badges = status_badges(row)
            attrs = ""
            if row["now_editing"]:
                attrs += ' data-composer-active="1"'
            if row["active_song"]:
                attrs += ' data-composer-active-song="1"'
            chips = "".join(f'<span class="composer-active-badge">{html.escape(b)}</span>' for b in badges)
            st.markdown(
                f'<div class="composer-library-item{" is-active" if row["now_editing"] else ""}"{attrs}>'
                f'<h4>{html.escape(row["title"])}{chips}</h4></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Editing now" if row["now_editing"] else "Open for editing",
                key=f"composer_lib_open_{rid}",
                use_container_width=True,
                type="primary" if row["now_editing"] else "secondary",
                disabled=row["now_editing"],
            ):
                ok, msg = switch_to_composition(session_state, rid)
                if not ok:
                    st.error(msg)
                else:
                    action = rid
            if session_state.get(PENDING_DELETE_KEY) == rid:
                st.warning(f"Delete “{row['title']}” permanently? This cannot be undone.")
                if st.button("Yes, delete permanently", key=f"composer_lib_delyes_{rid}", type="primary", use_container_width=True):
                    session_state.pop(PENDING_DELETE_KEY, None)
                    delete_library_document(session_state, rid)
                    action = f"deleted:{rid}"
                st.button(
                    "Cancel",
                    key=f"composer_lib_delcancel_{rid}",
                    use_container_width=True,
                    on_click=_set_pending_delete,
                    args=(session_state, ""),
                )
            else:
                st.button(
                    "🗑 Delete",
                    key=f"composer_lib_del_{rid}",
                    use_container_width=True,
                    on_click=_set_pending_delete,
                    args=(session_state, rid),
                )
    return action


def render_save_recovery(st: Any, session_state: dict) -> None:
    """Retry / conflict-resolution controls while a draft is not confirmed in the cloud."""
    from composition_save_verification import RESULT_KEY, save_feedback

    result = session_state.get(RESULT_KEY) or {}
    code = str(result.get("failure_code") or "")
    if not code or result.get("cloud_verified") or not session_state.get("composition_workspace_state_dirty"):
        return
    if code == "stale_revision_conflict":
        if st.button("Load cloud version and keep my edits", key="composer_load_cloud_keep",
                     use_container_width=True):
            from composition_library import load_cloud_and_keep_edits

            ok, msg = load_cloud_and_keep_edits(session_state)
            (st.success if ok else st.error)(msg)
    if result.get("retryable") and code in ("policy_blocked", "readback_mismatch", "readback_failed",
                                            "cloud_write_failed", "account_unresolved", "not_signed_in"):
        if st.button("Retry cloud save", key="composer_retry_cloud_save", use_container_width=True):
            from composition_library import retry_cloud_save

            level, msg = retry_cloud_save(session_state, st)
            getattr(st, {"success": "success", "warning": "warning"}.get(level, "error"))(msg)
