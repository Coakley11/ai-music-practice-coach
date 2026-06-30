"""Navigate from Backing Studio back to the source that created the current context."""

from __future__ import annotations

from typing import Any, Literal

from backing_context import (
    BACKING_CONTEXT_KEY,
    BackingContext,
    get_backing_context,
)

CreativeReturnPage = Literal["creative", "custom", "picker", "practice"]


def target_page_for_backing_context(ctx: BackingContext | None) -> CreativeReturnPage:
    """Resolve studio page id for Edit-in-Creative / return-to-source."""
    if ctx is None:
        return "practice"
    if ctx.source == "custom_progression":
        return "custom"
    if ctx.source == "regular_song":
        return "picker"
    return "creative"


def restore_session_widgets_from_backing_context(
    session: dict[str, Any],
    ctx: BackingContext,
) -> None:
    """Push backing_context snapshot fields into Creative/custom session widgets."""
    try:
        from creative_session_state import apply_creative_session_to_session, get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            apply_creative_session_to_session(session, sess)
            return
    except ImportError:
        pass

    concert = str(
        ctx.concert_key or ctx.display_key or ctx.key or session.get("display_key") or ""
    ).strip()
    if concert:
        session["concert_key"] = concert
        session["display_key"] = concert
        session["_pending_display_key"] = concert

    if ctx.source in {"custom_progression", "regular_song"}:
        return

    session["creative_lab_analysis_mode"] = "Improvisation Intelligence"
    session["creative_lab_last_mode"] = "Improvisation Intelligence"

    if ctx.source == "mission":
        session["improv_intelligence_tab"] = "Missions"
        if ctx.mission_id:
            session["improv_active_mission"] = ctx.mission_id
            session["improv_mission_pick"] = ctx.mission_id
        entry = str(ctx.entry_mode or "Song-Based Improvisation").strip()
        session["improv_entry_mode"] = entry or "Song-Based Improvisation"
        meta = dict(session.get("improv_style_meta") or {})
        meta.update(
            {
                "style": str(ctx.style or meta.get("style") or ""),
                "bpm": int(ctx.bpm or meta.get("bpm") or 100),
                "key": concert or str(meta.get("key") or ""),
                "entry_mode": entry,
            }
        )
        session["improv_style_meta"] = meta
    elif ctx.source == "song_improv":
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_song_source"] = "Active song"
    elif ctx.source == "entry_jam":
        session["improv_intelligence_tab"] = "Entry & Jam"
        entry = str(ctx.entry_mode or "Style Jam Mode").strip()
        session["improv_entry_mode"] = entry
        if entry == "Jam Session Generator":
            if concert:
                session["improv_jam_key"] = concert
                session["_pending_improv_jam_key"] = concert
            if ctx.style:
                session["improv_jam_style"] = ctx.style
            if ctx.bpm:
                session["improv_jam_bpm"] = int(ctx.bpm)
            if ctx.mood:
                session["improv_jam_mood"] = ctx.mood
            jam = session.get("improv_jam_session")
            if isinstance(jam, dict) and ctx.progression:
                sections = jam.get("sections")
                if not isinstance(sections, dict) or not sections:
                    label = str(ctx.progression_label or ctx.style or "Jam").strip() or "Jam"
                    jam = {**jam, "sections": {label: list(ctx.progression)}}
                    session["improv_jam_session"] = jam
        else:
            if ctx.style:
                session["improv_style"] = ctx.style
            if concert:
                session["improv_style_key"] = concert
                session["_pending_improv_style_key"] = concert
            if ctx.bpm:
                session["improv_style_bpm"] = int(ctx.bpm)
            if ctx.mood:
                session["improv_mood"] = ctx.mood
            if ctx.groove_intensity:
                session["improv_groove"] = ctx.groove_intensity
            if ctx.difficulty:
                session["improv_difficulty"] = ctx.difficulty
            if ctx.meter:
                session["improv_style_meter"] = ctx.meter
            if ctx.progression:
                label = str(ctx.progression_label or ctx.style or "Style Jam").strip() or "Style Jam"
                session["improv_generated_sections"] = {label: list(ctx.progression)}
        meta = dict(session.get("improv_style_meta") or {})
        meta.update(
            {
                "style": str(ctx.style or meta.get("style") or ""),
                "bpm": int(ctx.bpm or meta.get("bpm") or 100),
                "groove": str(ctx.groove_intensity or meta.get("groove") or "Medium"),
                "groove_intensity": str(ctx.groove_intensity or meta.get("groove_intensity") or "Medium"),
                "key": concert or str(meta.get("key") or ""),
                "mood": str(ctx.mood or meta.get("mood") or "Mellow"),
                "difficulty": str(ctx.difficulty or meta.get("difficulty") or "Intermediate"),
                "meter": str(ctx.meter or meta.get("meter") or "4/4"),
                "entry_mode": entry,
            }
        )
        session["improv_style_meta"] = meta


def prepare_return_to_backing_source(session: dict[str, Any]) -> CreativeReturnPage:
    """Restore Creative/custom/picker widgets from the active backing_context snapshot."""
    ctx = get_backing_context(session)
    page = target_page_for_backing_context(ctx)
    if ctx is None:
        return page
    restore_session_widgets_from_backing_context(session, ctx)
    return page


def return_to_source_button_label(ctx: BackingContext | None) -> str:
    """User-facing label for the return-to-source button."""
    if ctx is None:
        return "Return to source"
    if ctx.source == "custom_progression":
        return "✏️ Return to Custom Page"
    if ctx.source == "regular_song":
        return "🎵 Return to Catalog Song"
    return "🎨 Return to Creative Page"


def edit_in_creative_button_label(ctx: BackingContext | None) -> str:
    """Backward-compatible alias."""
    return return_to_source_button_label(ctx)


__all__ = [
    "BACKING_CONTEXT_KEY",
    "CreativeReturnPage",
    "edit_in_creative_button_label",
    "prepare_return_to_backing_source",
    "restore_session_widgets_from_backing_context",
    "return_to_source_button_label",
    "target_page_for_backing_context",
]
