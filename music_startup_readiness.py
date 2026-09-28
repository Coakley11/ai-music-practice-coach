"""Stable browser boundary for the canonical music startup state.

Streamlit streams the shell while the workspace and first song are still being
resolved.  Browser automation must not treat the shell (or the Membership
sidebar) as proof that the music state is ready for navigation.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class MusicStartupReadiness:
    ready: bool
    reason: str
    song_title: str = ""
    pick_key: str = ""
    source: str = ""
    practice_key: str = ""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def collect_music_startup_readiness(
    session_state: Mapping[str, Any],
    *,
    song_title: str,
    song_data: Mapping[str, Any] | None,
) -> MusicStartupReadiness:
    """Return ready only after hydration and canonical first-song resolution."""
    try:
        from music_workspace_hydration import can_finalize_music_restore

        if not can_finalize_music_restore(dict(session_state)):
            return MusicStartupReadiness(False, "workspace_not_finalized")
    except ImportError:
        return MusicStartupReadiness(False, "hydration_contract_unavailable")

    if not session_state.get("_music_post_nav_startup_done"):
        return MusicStartupReadiness(False, "post_nav_startup_incomplete")
    if not isinstance(song_data, Mapping) or not song_data:
        return MusicStartupReadiness(False, "song_data_unresolved")

    selected = session_state.get("selected_song")
    selected = selected if isinstance(selected, Mapping) else {}
    pick_key = _clean(
        selected.get("pick_key")
        or session_state.get("active_catalog_pick_key")
        or song_data.get("pick_key")
    )
    resolved_title = _clean(song_title or selected.get("title") or song_data.get("title"))
    if not pick_key:
        return MusicStartupReadiness(False, "pick_key_unresolved", song_title=resolved_title)
    if not resolved_title:
        return MusicStartupReadiness(False, "song_title_unresolved", pick_key=pick_key)

    source = _clean(
        session_state.get("active_music_source")
        or selected.get("source")
        or song_data.get("source")
        or "catalog"
    )
    practice_key = _clean(
        session_state.get("display_key")
        or selected.get("display_key")
        or song_data.get("key")
    )
    return MusicStartupReadiness(
        True,
        "ready",
        song_title=resolved_title,
        pick_key=pick_key,
        source=source,
        practice_key=practice_key,
    )


def render_music_startup_ready_marker(
    st: Any,
    *,
    song_title: str,
    song_data: Mapping[str, Any] | None,
    studio_page: str,
) -> bool:
    """Render a hidden marker only when navigation-safe music state exists."""
    state = collect_music_startup_readiness(
        st.session_state,
        song_title=song_title,
        song_data=song_data,
    )
    st.session_state["_music_startup_readiness_reason"] = state.reason
    if not state.ready:
        return False

    from monetization_entitlements import resolve_entitlement

    entitlement = resolve_entitlement(st.session_state)
    attrs = {
        "data-music-startup-ready": "true",
        "data-song-title": state.song_title,
        "data-pick-key": state.pick_key,
        "data-music-source": state.source,
        "data-practice-key": state.practice_key,
        "data-studio-page": _clean(studio_page),
        "data-entitlement-plan": entitlement.plan.value,
        "data-entitlement-status": entitlement.status.value,
        "data-entitlement-source": entitlement.source,
    }
    encoded = " ".join(
        f'{name}="{html.escape(value, quote=True)}"' for name, value in attrs.items()
    )
    st.markdown(
        f'<div id="music-startup-ready-marker" {encoded} '
        'style="display:none!important" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    return True


__all__ = (
    "MusicStartupReadiness",
    "collect_music_startup_readiness",
    "render_music_startup_ready_marker",
)
