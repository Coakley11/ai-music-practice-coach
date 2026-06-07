"""Music sidebar layout marker — verify suite order in production (?dev=1)."""

from __future__ import annotations

import subprocess
from typing import Any

MUSIC_SIDEBAR_LAYOUT_MARKER = "sidebar-order-v2"

# Primary sidebar blocks in render order (streamlit_music_practice_app.py ~8876–9070).
MUSIC_SIDEBAR_SECTION_ORDER: tuple[str, ...] = (
    "command_center",
    "saved_session",
    "active_song",
    "practice_setup",
    "pages",
    "session",
)


def _git_head_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return ""


def render_sidebar_layout_dev_marker(st: Any) -> None:
    """Developer-only (?dev=1 / developer_mode): confirm deployed sidebar order."""
    try:
        from music_persistence_trace import music_developer_mode
    except Exception:
        return
    if not music_developer_mode(st):
        return
    commit = _git_head_short()
    with st.sidebar.expander("Music sidebar layout marker", expanded=False):
        st.markdown(f"**Music sidebar layout marker:** `{MUSIC_SIDEBAR_LAYOUT_MARKER}`")
        st.markdown("**rendered sections:**")
        for section in MUSIC_SIDEBAR_SECTION_ORDER:
            st.markdown(f"- {section}")
        if commit:
            st.caption(f"git commit: `{commit}`")
