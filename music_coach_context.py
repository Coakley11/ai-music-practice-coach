"""Music Coach insight context — practice/app help (not Applied Math wording)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

APP_ID = "music"

# Canonical coach page ids used for insight scoping and AMI return routing.
COACH_PAGE_IDS: frozenset[str] = frozenset({"practice", "backing", "custom", "karaoke"})

COACH_PAGE_DISPLAY: dict[str, str] = {
    "practice": "Practice",
    "backing": "Backing Track Studio",
    "custom": "Creative Progression",
    "karaoke": "Karaoke",
}

STUDIO_PAGE_TO_COACH: dict[str, str] = {
    "practice": "practice",
    "backing": "backing",
    "custom": "custom",
    "picker": "practice",
    "creative": "custom",
}


def _is_karaoke_active(session_state: dict[str, Any]) -> bool:
    try:
        import karaoke_mode as km

        return bool(km.is_voice_mode(session_state) and km.is_karaoke_session_active(session_state))
    except Exception:
        return False


def resolve_coach_source_page(session_state: dict[str, Any]) -> str:
    """Canonical coach page id for insight send/render and workspace ownership."""
    if _is_karaoke_active(session_state):
        return "karaoke"
    studio = str(session_state.get("studio_page") or "practice").strip()
    return STUDIO_PAGE_TO_COACH.get(studio, studio if studio in COACH_PAGE_IDS else "practice")


def coach_page_display_name(coach_page: str) -> str:
    page = str(coach_page or "").strip()
    return COACH_PAGE_DISPLAY.get(page, page.replace("_", " ").title())


def sync_music_coach_workspace_page(session_state: dict[str, Any]) -> str:
    """Mirror coach page into session for suite_user_persistence workspace checks."""
    page = resolve_coach_source_page(session_state)
    session_state["_music_coach_workspace_page"] = page
    return page


def build_source_state(page: str, session_state: dict[str, Any]) -> dict[str, Any]:
    """Build AMI / Music Coach source_state from canonical page modules when available."""
    coach_page = str(page or "").strip() or resolve_coach_source_page(session_state)
    if coach_page not in COACH_PAGE_IDS:
        coach_page = resolve_coach_source_page(session_state)
    try:
        from active_song_state import gather_active_song_context

        song_ctx = gather_active_song_context(session_state)
    except ImportError:
        song_ctx = {}
    song = song_ctx.get("selected_song") if isinstance(song_ctx.get("selected_song"), dict) else {}
    if not song:
        song = session_state.get("selected_song") if isinstance(session_state.get("selected_song"), dict) else {}
    pick_key = str(
        song_ctx.get("pick_key")
        or session_state.get("active_catalog_pick_key")
        or song.get("pick_key")
        or ""
    ).strip()
    widget_params: dict[str, Any] = {
        "studio_page": str(session_state.get("studio_page") or ""),
        "instrument": str(song_ctx.get("instrument") or session_state.get("instrument") or ""),
        "level": str(song_ctx.get("level") or session_state.get("level") or ""),
        "focus": str(song_ctx.get("focus") or session_state.get("focus") or ""),
        "display_key": str(song_ctx.get("display_key") or session_state.get("display_key") or ""),
        "practice_focus_section": str(
            song_ctx.get("practice_focus_section") or session_state.get("practice_focus_section") or ""
        ),
    }
    try:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
        )

        if CHART_IN_INSTRUMENT_KEY_KEY in song_ctx:
            widget_params[CHART_IN_INSTRUMENT_KEY_KEY] = bool(song_ctx[CHART_IN_INSTRUMENT_KEY_KEY])
        anchor = str(song_ctx.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
        if anchor:
            widget_params[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = anchor
        subtype = str(song_ctx.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
        if subtype:
            widget_params[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = subtype
    except ImportError:
        pass
    if coach_page == "backing":
        try:
            from backing_track_state import gather_backing_filters

            widget_params.update(gather_backing_filters(session_state))
        except ImportError:
            widget_params.update(
                {
                    "backing_track_scope": session_state.get("backing_track_scope"),
                    "backing_track_bpm": session_state.get("backing_track_bpm"),
                    "backing_groove_style": session_state.get("backing_groove_style"),
                }
            )
    elif coach_page == "custom":
        widget_params.update(
            {
                "cpl_active_progression": session_state.get("cpl_active_progression"),
                "cpl_edit_section": session_state.get("cpl_edit_section"),
            }
        )
    elif coach_page == "practice":
        try:
            from practice_state import gather_practice_filters

            widget_params.update(gather_practice_filters(session_state))
        except ImportError:
            widget_params.update(
                {
                    "practice_groove_style": session_state.get("practice_groove_style"),
                    "practice_notation_lines": session_state.get("practice_notation_lines"),
                    "practice_notation_difficulty": session_state.get("practice_notation_difficulty"),
                    "last_practice_mode": session_state.get("last_practice_mode"),
                }
            )
    elif coach_page == "karaoke":
        widget_params["karaoke_session_active"] = True
    return {
        "source_app": APP_ID,
        "source_page": coach_page,
        "page_params": {"page": coach_page, "studio_page": session_state.get("studio_page")},
        "entity_params": {
            "pick_key": pick_key,
            "song_title": str(song.get("title") or ""),
            "song_artist": str(song.get("artist") or ""),
        },
        "widget_params": widget_params,
        "filter_params": {},
        "chart_params": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_music_coach_context(page: str, session_state: dict[str, Any]) -> dict[str, Any]:
    """Sidebar context summary for Music Coach send UI."""
    coach_page = str(page or "").strip() or resolve_coach_source_page(session_state)
    ctx = build_source_state(coach_page, session_state)
    return {
        "source_app": "Music",
        "page": coach_page_display_name(coach_page),
        "workflow": "Music practice coach",
        "pick_key": ctx.get("entity_params", {}).get("pick_key"),
        "instrument": session_state.get("instrument"),
        "display_key": session_state.get("display_key"),
    }


def _coach_page_to_studio_page(coach_page: str) -> str:
    page = str(coach_page or "").strip().lower()
    if page == "karaoke":
        return "backing"
    if page in STUDIO_PAGE_TO_COACH:
        for studio, coach in STUDIO_PAGE_TO_COACH.items():
            if coach == page:
                return studio
    return page if page in {"practice", "backing", "custom", "picker", "creative"} else "practice"


def apply_source_state_to_session(
    session_state: dict[str, Any],
    source_state: dict[str, Any],
    *,
    schedule_navigation: bool = True,
) -> None:
    """Apply Music Coach / AMI return payload via canonical state modules."""
    if not isinstance(source_state, dict):
        return
    try:
        from active_song_state import apply_active_song_source_state_from_ami
        from backing_track_state import apply_backing_source_state_from_ami
        from practice_state import apply_practice_source_state_from_ami
        from studio_nav_state import apply_studio_nav_source_state_from_ami

        apply_active_song_source_state_from_ami(session_state, source_state)
        apply_practice_source_state_from_ami(session_state, source_state)
        apply_backing_source_state_from_ami(session_state, source_state)
        studio_target = apply_studio_nav_source_state_from_ami(session_state, source_state)
    except ImportError:
        coach_page = str(
            source_state.get("source_page")
            or source_state.get("page_params", {}).get("page")
            or ""
        ).strip()
        widgets = source_state.get("widget_params")
        if isinstance(widgets, dict):
            for key, val in widgets.items():
                if key in session_state or str(key).startswith(
                    ("practice_", "backing_", "cpl_", "instrument", "level", "focus", "display_key")
                ):
                    session_state[key] = val
        entity = source_state.get("entity_params")
        if isinstance(entity, dict) and entity.get("pick_key"):
            session_state["active_catalog_pick_key"] = entity["pick_key"]
        sync_music_coach_workspace_page(session_state)
        studio_target = _coach_page_to_studio_page(coach_page)
        if schedule_navigation and studio_target:
            session_state["studio_page"] = studio_target
            session_state["_navigate_to_studio_page"] = studio_target
        return
    sync_music_coach_workspace_page(session_state)
    if schedule_navigation and studio_target:
        session_state["_navigate_to_studio_page"] = studio_target
    widgets = source_state.get("widget_params")
    if isinstance(widgets, dict):
        for key, val in widgets.items():
            if str(key).startswith(("practice_", "backing_", "cpl_", "karaoke_")):
                session_state[key] = val


def is_coach_page_eligible(coach_page: str) -> bool:
    return str(coach_page or "").strip() in COACH_PAGE_IDS
