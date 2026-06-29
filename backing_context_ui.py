"""Display-only Backing Track context banner and reset control."""

from __future__ import annotations

from typing import Any

from backing_context import (
    format_backing_context_banner,
    get_backing_context,
    restore_regular_song_backing,
)


def render_backing_context_banner(st: Any, session: dict[str, Any]) -> bool:
    """Show backing source banner. Returns True when a non-regular source is active."""
    ctx = get_backing_context(session)
    label = format_backing_context_banner(ctx)
    if not label:
        return False
    accent = "#2563eb" if ctx and ctx.source == "entry_jam" else "#7c3aed"
    if ctx and ctx.source == "mission":
        accent = "#9333ea"
    elif ctx and ctx.source == "custom_progression":
        accent = "#0891b2"
    elif ctx and ctx.source == "regular_song":
        accent = "#64748b"
    st.markdown(
        f'<div style="border-left:4px solid {accent};border-radius:10px;padding:0.55rem 0.75rem;'
        f'margin:0.35rem 0 0.65rem;background:rgba(248,250,252,.95);">'
        f'<span style="font-size:0.88rem;font-weight:750;color:#0f172a;">{label}</span></div>',
        unsafe_allow_html=True,
    )
    return bool(ctx and ctx.source != "regular_song")


def render_backing_context_reset(st: Any, session: dict[str, Any]) -> None:
    """Reset Creative/custom backing to regular active song."""
    ctx = get_backing_context(session)
    if ctx is None or ctx.source == "regular_song":
        return
    if st.button("Use regular song backing", key="backing_context_reset_btn", use_container_width=False):
        restore_regular_song_backing(session, st_like=st)
        st.rerun()
