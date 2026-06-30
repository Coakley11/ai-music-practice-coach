"""Shared helpers for Custom Progression — never import the main Streamlit app."""

from __future__ import annotations

from typing import Any

from backing_audio import generate_backing_track, infer_groove_style
from coach_overlay import section_overlay_html
from custom_progression_lab import default_active_progression
from songs.key_state import invalidate_backing_cache
from songs.music_source import is_custom_progression

__all__ = [
    "default_active_progression",
    "generate_backing_track",
    "infer_groove_style",
    "invalidate_backing_cache",
    "is_custom_progression",
    "render_cpl_page_header",
    "section_overlay_html",
    "session_display_key",
    "session_focus",
    "session_instrument",
    "session_level",
]


def session_display_key(session_state: dict[str, Any]) -> str:
    return str(session_state.get("display_key") or "C")


def session_instrument(session_state: dict[str, Any]) -> str:
    return str(session_state.get("instrument") or "Piano")


def session_level(session_state: dict[str, Any]) -> str:
    return str(session_state.get("level") or "Intermediate")


def session_focus(session_state: dict[str, Any]) -> str:
    return str(session_state.get("focus") or "General")


def render_cpl_page_header() -> None:
    """Instrument strip below the Custom Progression title (quick nav is canonical/global)."""
    import streamlit as st

    try:
        from instrument_aware import render_instrument_context_strip

        render_instrument_context_strip(
            st,
            str(st.session_state.get("instrument") or "Guitar"),
            "custom",
            st.session_state,
        )
    except Exception:
        pass
