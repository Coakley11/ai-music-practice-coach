"""Navigate from Backing Studio back to the source that created the current context."""

from __future__ import annotations

from typing import Any, Literal

from backing_context import (
    BACKING_CONTEXT_KEY,
    BackingContext,
    get_backing_context,
)

CreativeReturnPage = Literal["creative", "custom", "picker", "practice"]

BACKING_OPEN_INTENT_KEY = "_backing_open_intent"
BACKING_INTENT_RESTORE_LAST = "restore_last"
BACKING_INTENT_FROM_PRACTICE = "from_practice"
PRACTICE_SOURCE_DISPLAY_KEY = "_practice_source_display_key"
PRACTICE_SOURCE_PICK_KEY = "_practice_source_pick_key"


def set_backing_open_intent(session: dict[str, Any], intent: str) -> None:
    session[BACKING_OPEN_INTENT_KEY] = str(intent or BACKING_INTENT_RESTORE_LAST).strip()


def consume_backing_open_intent(session: dict[str, Any]) -> str:
    return str(session.pop(BACKING_OPEN_INTENT_KEY, BACKING_INTENT_RESTORE_LAST) or BACKING_INTENT_RESTORE_LAST)


def snapshot_practice_source_display_key(session: dict[str, Any]) -> None:
    """Remember the active practice-song concert key before Creative backing overrides it."""
    key = str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"
    session[PRACTICE_SOURCE_DISPLAY_KEY] = key
    session[PRACTICE_SOURCE_PICK_KEY] = str(session.get("active_catalog_pick_key") or "").strip()


def _resolved_practice_display_key(session: dict[str, Any]) -> str:
    saved = str(session.get(PRACTICE_SOURCE_DISPLAY_KEY) or "").strip()
    saved_pick = str(session.get(PRACTICE_SOURCE_PICK_KEY) or "").strip()
    live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    if saved and saved_pick and live_pick and saved_pick != live_pick:
        saved = ""
    if saved:
        return saved
    try:
        from active_song_state import canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            key = str(ctx.get("display_key") or ctx.get("concert_key") or "").strip()
            if key:
                return key
    except ImportError:
        pass
    return str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"


def restore_practice_source_display_key(session: dict[str, Any], *, st_like: Any | None = None) -> str:
    """Practice page owns the active song key — not the last Creative backing key."""
    key = _resolved_practice_display_key(session)
    try:
        from session_widget_safe import safe_assign_display_key

        safe_assign_display_key(session, key, widget_safe=True, st_like=st_like)
    except ImportError:
        session["concert_key"] = key
        session["_pending_display_key"] = key
        if st_like is not None:
            try:
                from songs.key_state import request_display_key

                request_display_key(st_like, key)
            except ImportError:
                pass
        else:
            session["display_key"] = key
    return key


def hydrate_practice_source_for_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Re-apply active practice song context when entering Practice (Case A)."""
    try:
        from backing_context import active_creative_backing_context

        if active_creative_backing_context(session) is not None:
            return
    except ImportError:
        pass
    try:
        from active_song_state import canonical_active_song_context

        canon = canonical_active_song_context(session)
        if isinstance(canon, dict):
            pick = str(session.get("active_catalog_pick_key") or canon.get("pick_key") or "").strip()
            original = str(canon.get("original_key") or canon.get("key") or "").strip()
            key = original
            if pick:
                try:
                    from songs.key_state import canonical_display_key_for_pick

                    scoped = canonical_display_key_for_pick(session, pick)
                    if scoped:
                        key = scoped
                except ImportError:
                    pass
            if key:
                session[PRACTICE_SOURCE_DISPLAY_KEY] = key
                session[PRACTICE_SOURCE_PICK_KEY] = pick
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, key, widget_safe=True, st_like=st_like)
                except ImportError:
                    session["display_key"] = key
                    session["concert_key"] = key
                    session["_pending_display_key"] = key
                return
    except ImportError:
        pass
    restore_practice_source_display_key(session, st_like=st_like)


def open_backing_for_practice_source(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext | None:
    """Open Backing Studio for the current Practice catalog/custom source (Case C)."""
    snapshot_practice_source_display_key(session)
    try:
        from backing_context import (
            apply_backing_context_to_session,
            build_custom_progression_context,
            restore_regular_song_backing,
            set_backing_context,
        )
        from songs.music_source import cpl_session_is_active, is_custom_progression

        if cpl_session_is_active(session) or is_custom_progression(session):
            ctx = build_custom_progression_context(session)
            set_backing_context(session, ctx)
            apply_backing_context_to_session(session, ctx, st_like=st_like)
            return ctx
        return restore_regular_song_backing(session, st_like=st_like)
    except ImportError:
        return None


def hydrate_backing_source_for_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply backing navigation intent and preserve last Backing Studio source (Cases B + refresh)."""
    intent = consume_backing_open_intent(session)
    if intent == BACKING_INTENT_FROM_PRACTICE:
        open_backing_for_practice_source(session, st_like=st_like)
        return
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            active_creative_backing_context,
            ensure_backing_context_from_creative_session,
            get_backing_context,
        )
        from creative_session_state import hydrate_creative_session_for_page

        hydrate_creative_session_for_page(session)
        ctx = get_backing_context(session)
        if ctx is None:
            ensure_backing_context_from_creative_session(session)
        ctx = active_creative_backing_context(session) or get_backing_context(session)
        if ctx is not None and ctx.source != "regular_song":
            concert = str(ctx.concert_key or ctx.display_key or ctx.key or "").strip()
            if concert:
                try:
                    from session_widget_safe import safe_assign_display_key

                    safe_assign_display_key(session, concert, widget_safe=True, st_like=st_like)
                except ImportError:
                    session["concert_key"] = concert
                    session["_pending_display_key"] = concert
            session[PENDING_BACKING_CONTEXT_APPLY] = True
    except ImportError:
        pass


def _practice_source_type(session: dict[str, Any]) -> str:
    try:
        from songs.music_source import cpl_session_is_active, is_custom_progression

        if cpl_session_is_active(session) or is_custom_progression(session):
            return "custom"
    except ImportError:
        pass
    return "catalog"


def _practice_source_name(session: dict[str, Any]) -> str:
    try:
        from songs.music_source import cpl_session_is_active

        if cpl_session_is_active(session):
            active = session.get("cpl_active_progression") or {}
            if isinstance(active, dict):
                return str(active.get("name") or "Custom progression").strip()
    except ImportError:
        pass
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        title = str(sel.get("title") or "").strip()
        if title:
            return title
    return str(session.get("active_song_title") or session.get("selected_song") or "Song").strip() or "Song"


def _backing_source_type(session: dict[str, Any]) -> str:
    ctx = get_backing_context(session)
    if ctx is None:
        return "none"
    return str(ctx.source or "none")


def _backing_source_name(session: dict[str, Any]) -> str:
    ctx = get_backing_context(session)
    if ctx is None:
        return ""
    if ctx.source == "regular_song":
        return str(ctx.song_title or _practice_source_name(session)).strip()
    if ctx.source == "entry_jam":
        entry = str(ctx.entry_mode or "").strip()
        if entry == "Style Jam Mode":
            return "Entry Style Jam"
        if entry == "Jam Session Generator":
            return "Jam Session Generator"
        return str(ctx.style or ctx.song_title or "Creative backing").strip()
    return str(ctx.song_title or ctx.style or ctx.source_label or "Backing").strip()


def render_source_context_debug(st: Any, session: dict[str, Any]) -> None:
    """Dev-only source context visibility (?dev=1)."""
    try:
        from suite_deploy_probe import deploy_info
    except ImportError:
        deploy_info = lambda: {"commit": "unknown"}  # type: ignore[misc, assignment]
    try:
        from suite_workspace import can_show_developer_tools

        if not can_show_developer_tools(st=st):
            return
    except ImportError:
        return
    deploy = deploy_info()
    commit = str(deploy.get("commit") or "unknown").strip()[:12]
    tool = ""
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            tool = str(sess.tool_type or "")
    except ImportError:
        pass
    ctx = get_backing_context(session)
    page = str(session.get("studio_page") or "").strip()
    st.caption(
        f"Context · commit `{commit}` · page `{page}` · "
        f"practice={_practice_source_type(session)}/{_practice_source_name(session)} · "
        f"backing={_backing_source_type(session)}/{_backing_source_name(session)} · "
        f"creative_tool={tool or 'none'} · "
        f"concert_key={session.get('display_key') or session.get('concert_key')} · "
        f"instrument={session.get('instrument')} · "
        f"backing_context={'yes' if ctx else 'no'}"
    )


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
    *,
    widget_safe: bool = True,
) -> None:
    """Push backing_context snapshot fields into Creative/custom session widgets."""
    try:
        from creative_session_state import apply_creative_session_to_session, get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            apply_creative_session_to_session(session, sess, widget_safe=widget_safe)
            return
    except ImportError:
        pass

    concert = str(
        ctx.concert_key or ctx.display_key or ctx.key or session.get("display_key") or ""
    ).strip()
    if concert:
        try:
            from session_widget_safe import safe_assign_display_key

            safe_assign_display_key(session, concert, widget_safe=widget_safe)
        except ImportError:
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
    try:
        from creative_session_state import sync_creative_session_before_persist

        sync_creative_session_before_persist(session)
    except ImportError:
        pass
    ctx = get_backing_context(session)
    page = target_page_for_backing_context(ctx)
    if ctx is None:
        return page
    restore_session_widgets_from_backing_context(session, ctx)
    merge_live_practice_into_creative_session(session)
    return page


def merge_live_practice_into_creative_session(session: dict[str, Any]) -> None:
    """Return-to-Creative: keep saved workflow settings but adopt live key + instrument."""
    try:
        from creative_session_state import (
            apply_creative_session_to_session,
            get_creative_session,
            set_creative_session,
        )
        from music_theory import key_is_minor
    except ImportError:
        return
    sess = get_creative_session(session)
    if sess is None:
        return
    live_key = str(session.get("display_key") or session.get("concert_key") or "").strip()
    live_inst = str(session.get("instrument") or "").strip()
    if live_key:
        if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
            try:
                from creative_key_sync import to_major_key_preserve_spelling

                saved_major = to_major_key_preserve_spelling(str(sess.concert_key or "C"))
                if key_is_minor(live_key):
                    live_key = saved_major
                else:
                    live_key = to_major_key_preserve_spelling(live_key)
            except ImportError:
                pass
        sess.concert_key = live_key
        if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
            try:
                from creative_key_sync import to_major_key_preserve_spelling

                sess.display_key = to_major_key_preserve_spelling(live_key)
            except ImportError:
                sess.display_key = live_key
        else:
            sess.display_key = live_key
    if live_inst:
        sess.instrument = live_inst
    set_creative_session(session, sess)
    apply_creative_session_to_session(session, sess, widget_safe=True)


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
    "BACKING_INTENT_FROM_PRACTICE",
    "BACKING_INTENT_RESTORE_LAST",
    "BACKING_OPEN_INTENT_KEY",
    "CreativeReturnPage",
    "PRACTICE_SOURCE_DISPLAY_KEY",
    "consume_backing_open_intent",
    "edit_in_creative_button_label",
    "hydrate_backing_source_for_page",
    "hydrate_practice_source_for_page",
    "merge_live_practice_into_creative_session",
    "open_backing_for_practice_source",
    "prepare_return_to_backing_source",
    "render_source_context_debug",
    "restore_practice_source_display_key",
    "restore_session_widgets_from_backing_context",
    "return_to_source_button_label",
    "set_backing_open_intent",
    "snapshot_practice_source_display_key",
    "target_page_for_backing_context",
]
