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
            BACKING_PREF_CATALOG,
            BACKING_PREF_CUSTOM,
            apply_backing_context_to_session,
            build_custom_progression_context,
            restore_regular_song_backing,
            set_backing_context,
            set_backing_source_preference,
        )
        from songs.music_source import (
            cpl_session_is_active,
            ensure_custom_active_song_identity,
            is_custom_progression,
        )

        if cpl_session_is_active(session) or is_custom_progression(session):
            ensure_custom_active_song_identity(session)
            set_backing_source_preference(session, BACKING_PREF_CUSTOM)
            ctx = build_custom_progression_context(session)
            set_backing_context(session, ctx)
            apply_backing_context_to_session(session, ctx, st_like=st_like)
            return ctx
        set_backing_source_preference(session, BACKING_PREF_CATALOG)
        return restore_regular_song_backing(session, st_like=st_like)
    except ImportError:
        return None


def _ctx_is_stale_creative_for_practice(session: dict[str, Any], ctx: BackingContext | None) -> bool:
    try:
        from backing_context import ctx_is_stale_creative_for_practice

        return ctx_is_stale_creative_for_practice(session, ctx)
    except ImportError:
        return False


def _open_live_practice_backing(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    try:
        from backing_context import open_live_practice_backing

        open_live_practice_backing(session, st_like=st_like)
    except ImportError:
        open_backing_for_practice_source(session, st_like=st_like)


def hydrate_backing_source_for_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply backing navigation intent and preserve last Backing Studio source (Cases B + refresh)."""
    intent = consume_backing_open_intent(session)
    if intent == BACKING_INTENT_FROM_PRACTICE:
        open_backing_for_practice_source(session, st_like=st_like)
        return
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        if (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            ctx = get_backing_context(session)
            if ctx is None or str(getattr(ctx, "source", "") or "") in {
                "entry_jam",
                "song_improv",
                "mission",
            }:
                open_backing_for_practice_source(session, st_like=st_like)
                return
    except ImportError:
        pass
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            active_creative_backing_context,
            ensure_backing_context_from_creative_session,
            is_backing_context_valid,
            reset_backing_on_active_song_change,
        )
        from creative_session_state import creative_session_is_active, hydrate_creative_session_for_page
        from songs.music_source import cpl_session_is_active, is_custom_progression

        hydrate_creative_session_for_page(session)
        ctx = get_backing_context(session)
        if _ctx_is_stale_creative_for_practice(session, ctx):
            _open_live_practice_backing(session, st_like=st_like)
            return
        if ctx is not None and ctx.source != "regular_song":
            if not is_backing_context_valid(session, ctx):
                reset_backing_on_active_song_change(session)
                ctx = get_backing_context(session)
        if ctx is None:
            if cpl_session_is_active(session) or is_custom_progression(session):
                _open_live_practice_backing(session, st_like=st_like)
                return
            if not creative_session_is_active(session):
                _open_live_practice_backing(session, st_like=st_like)
                return
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


def _backing_open_intent_label(session: dict[str, Any]) -> str:
    return str(session.get(BACKING_OPEN_INTENT_KEY) or "none").strip() or "none"


def _last_catalog_song_label(session: dict[str, Any]) -> str:
    try:
        from songs.music_source import previous_catalog_snapshot

        snap = previous_catalog_snapshot(session)
        if not snap:
            return ""
        sel = snap.get("selected_song") or {}
        title = str(sel.get("title") or "").strip()
        return title
    except ImportError:
        return ""


def _custom_progression_label(session: dict[str, Any]) -> str:
    active = session.get("cpl_active_progression")
    if isinstance(active, dict):
        return str(active.get("name") or "").strip()
    return ""


def _chart_visibility_label(session: dict[str, Any]) -> str:
    val = session.get("chart_in_instrument_key")
    if val is None:
        return "unknown"
    return "ON" if bool(val) else "OFF"


def _sections_source_label(session: dict[str, Any], ctx: BackingContext | None) -> str:
    if ctx is None:
        return "none"
    if ctx.source == "custom_progression":
        return "cpl_active_progression"
    if ctx.source == "regular_song":
        return "catalog_song_data"
    if ctx.source == "song_improv":
        if session.get("improv_song_concert_sections"):
            return "improv_song_concert_sections"
        return "backing_context.progression"
    if ctx.source == "entry_jam":
        if session.get("improv_generated_sections"):
            return "improv_generated_sections"
        return "backing_context.progression"
    return f"backing_context.{ctx.source}"


def source_ownership_diagnostics_enabled(*, st: Any | None = None) -> bool:
    """True when ?dev=1 (or dev session flag) — any workspace, not Daniel-only."""
    try:
        from suite_workspace import is_developer_mode_enabled

        return is_developer_mode_enabled(st=st)
    except ImportError:
        return False


def _diag_value(value: Any, *, default: str = "n/a") -> str:
    """Format diagnostics table values; never raise."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _diag_attr(obj: Any, *names: str, default: str = "n/a") -> str:
    """Read first present attribute from an object for diagnostics display."""
    if obj is None:
        return default
    for name in names:
        try:
            val = getattr(obj, name, None)
        except Exception:
            continue
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def render_source_ownership_dev_table(st: Any, session: dict[str, Any]) -> None:
    """Dev-only ownership matrix (?dev=1) — Song, Creative, and Backing pages."""
    if not source_ownership_diagnostics_enabled(st=st):
        return
    try:
        _render_source_ownership_dev_table_body(st, session)
    except Exception as exc:
        st.caption("**Debug:** Source ownership diagnostics active")
        with st.expander("Source ownership diagnostics", expanded=True):
            st.warning(f"Diagnostics failed safely: {exc!r}")


def _render_source_ownership_dev_table_body(st: Any, session: dict[str, Any]) -> None:
    ctx = get_backing_context(session)
    tool = "n/a"
    creative_title = "n/a"
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            tool = _diag_attr(sess, "tool_type", default="none")
            creative_title = str(
                getattr(sess, "song_title", None)
                or getattr(sess, "title", None)
                or getattr(sess, "style", None)
                or ""
            ).strip() or "n/a"
    except Exception:
        pass

    try:
        from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG, SOURCE_CUSTOM
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        music_source = str(session.get(ACTIVE_MUSIC_SOURCE_KEY) or "").strip()
        if music_source == SOURCE_CUSTOM:
            source_type = "custom"
        elif music_source == SOURCE_CATALOG:
            source_type = "catalog"
        else:
            source_type = music_source or "unknown"
        active_pick = str(session.get(ACTIVE_CATALOG_PICK_KEY) or "").strip()
    except ImportError:
        source_type = _practice_source_type(session)
        active_pick = ""

    try:
        from songs.key_state import PENDING_DISPLAY_KEY
    except ImportError:
        PENDING_DISPLAY_KEY = "_pending_display_key"  # type: ignore[misc,assignment]

    pref = "n/a"
    ctx_valid = False
    bound_pick = "n/a"
    current_pick = active_pick
    banner = "n/a"
    try:
        from backing_context import (
            format_backing_context_banner,
            get_backing_source_preference,
            is_backing_context_valid,
        )
        from backing_context import _current_pick_key as backing_current_pick_key

        pref = _diag_value(get_backing_source_preference(session))
        ctx_valid = bool(is_backing_context_valid(session, ctx)) if ctx else False
        bound_pick = _diag_attr(ctx, "bound_pick_key") if ctx else "n/a"
        current_pick = _diag_value(backing_current_pick_key(session))
        banner = _diag_value(format_backing_context_banner(ctx) if ctx else None)
    except Exception:
        pass

    backing_title = "n/a"
    try:
        backing_title = _diag_value(_backing_source_name(session) if ctx else None)
    except Exception:
        pass

    rows = {
        "page": _diag_value(session.get("studio_page")),
        "active_music_source": _diag_value(source_type),
        "active_song_title": _diag_value(
            session.get("song") or session.get("active_song_title")
        ),
        "active_pick_key": _diag_value(active_pick),
        "custom_progression": _diag_value(_custom_progression_label(session)),
        "last_catalog_song": _diag_value(_last_catalog_song_label(session)),
        "backing_open_intent": _diag_value(_backing_open_intent_label(session), default="none"),
        "backing_pref": pref,
        "backing_context.source": _diag_attr(ctx, "source") if ctx else "n/a",
        "backing_context.title": backing_title,
        "backing_context.valid": str(ctx_valid),
        "backing_context.bound_pick": bound_pick,
        "current_pick_key": current_pick,
        "creative_session.tool": tool,
        "creative_session.title": creative_title,
        "original_key": _diag_value(session.get("original_key")),
        "display_key": _diag_value(session.get("display_key")),
        "pending_display_key": _diag_value(session.get(PENDING_DISPLAY_KEY)),
        "concert_key": _diag_value(session.get("concert_key")),
        "chart_visibility": _chart_visibility_label(session),
        "instrument": _diag_value(session.get("instrument")),
        "sections_source": _sections_source_label(session, ctx),
        "top_backing_banner": banner,
    }

    st.caption("**Debug:** Source ownership diagnostics active")
    with st.expander("Source ownership diagnostics", expanded=True):
        try:
            from suite_deploy_probe import deploy_info

            deploy = deploy_info()
            commit = str(deploy.get("commit") or "unknown").strip()[:12]
        except Exception:
            commit = "unknown"
        try:
            from suite_workspace import is_developer_workspace, resolve_workspace_id

            workspace = str(resolve_workspace_id(st=st) or "").strip()
            daniel_only_tools = is_developer_workspace(st=st)
        except Exception:
            workspace = ""
            daniel_only_tools = False
        st.caption(
            f"URL gate: `?dev=1` · workspace `{workspace or 'unknown'}` · "
            f"commit `{commit}` · Daniel-only sidebar tools: "
            f"{'yes' if daniel_only_tools else 'no (this panel works on any workspace)'}"
        )
        st.table([{"field": k, "value": v} for k, v in rows.items()])


def render_source_context_debug(st: Any, session: dict[str, Any]) -> None:
    """Dev-only source context visibility (?dev=1) — caption, expander, and quick summary."""
    if not source_ownership_diagnostics_enabled(st=st):
        return
    render_source_ownership_dev_table(st, session)


def _tool_type_for_backing_context(ctx: BackingContext) -> str:
    """Map backing_context source to canonical CreativeSession tool_type."""
    if ctx.source == "mission":
        return "mission"
    if ctx.source == "song_improv":
        return "song_based_improvisation"
    if ctx.source == "entry_jam":
        entry = str(ctx.entry_mode or "").strip()
        if entry == "Jam Session Generator":
            return "jam_session_generator"
        return "entry_style_jam"
    return "entry_style_jam"


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
    if ctx.source in {"custom_progression", "regular_song"}:
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
        return

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
        custom_improv = bool(
            ctx.custom_revision_id
            or str(ctx.active_song_id or "").startswith("custom::")
        )
        if custom_improv:
            session["improv_song_source"] = "Custom progression"
            try:
                from studio_page_state import CREATIVE_BACKING_SONG_SOURCE_KEY

                session[CREATIVE_BACKING_SONG_SOURCE_KEY] = "Custom progression"
            except ImportError:
                pass
            try:
                from songs.music_source import set_custom_source

                set_custom_source(session)
            except ImportError:
                pass
        else:
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

    try:
        from backing_context import BACKING_PREF_CREATIVE, set_backing_source_preference

        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
    except ImportError:
        pass

    try:
        from creative_session_state import (
            apply_creative_session_to_session,
            get_creative_session,
            set_creative_session,
            sync_creative_session_from_session,
        )

        sess = get_creative_session(session)
        if sess is None:
            sync_creative_session_from_session(session)
            sess = get_creative_session(session)
        if sess is not None:
            tool_type = _tool_type_for_backing_context(ctx)
            sess.tool_type = tool_type  # type: ignore[assignment]
            if ctx.source == "entry_jam" and ctx.entry_mode:
                sess.entry_mode = str(ctx.entry_mode).strip()
            elif ctx.source == "song_improv":
                sess.entry_mode = "Song-Based Improvisation"
            elif ctx.source == "mission":
                sess.entry_mode = str(ctx.entry_mode or "Song-Based Improvisation").strip()
            if ctx.style:
                sess.style = str(ctx.style).strip()
            if ctx.bpm:
                sess.bpm = int(ctx.bpm)
            if ctx.mood:
                sess.mood = str(ctx.mood).strip()
            if ctx.groove_intensity:
                sess.groove_intensity = str(ctx.groove_intensity).strip()
            if ctx.difficulty:
                sess.difficulty = str(ctx.difficulty).strip()
            if ctx.meter:
                sess.meter = str(ctx.meter).strip()
            if ctx.progression:
                label = str(ctx.progression_label or ctx.style or "Jam").strip() or "Jam"
                sess.sections = {label: list(ctx.progression)}
            if concert:
                sess.concert_key = concert
                if sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
                    try:
                        from creative_key_sync import to_major_key_preserve_spelling

                        sess.display_key = to_major_key_preserve_spelling(concert)
                    except ImportError:
                        sess.display_key = concert
                else:
                    sess.display_key = concert
            set_creative_session(session, sess)
            apply_creative_session_to_session(session, sess, widget_safe=widget_safe)
    except ImportError:
        pass


def prepare_return_to_backing_source(session: dict[str, Any]) -> CreativeReturnPage:
    """Restore Creative/custom/picker widgets from the active backing_context snapshot."""
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
    try:
        from songs.key_state import PENDING_DISPLAY_KEY
    except ImportError:
        PENDING_DISPLAY_KEY = "_pending_display_key"  # type: ignore[misc,assignment]
    live_key = str(
        session.get("display_key")
        or session.get(PENDING_DISPLAY_KEY)
        or session.get("concert_key")
        or ""
    ).strip()
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
    "render_source_ownership_dev_table",
    "source_ownership_diagnostics_enabled",
    "restore_practice_source_display_key",
    "restore_session_widgets_from_backing_context",
    "return_to_source_button_label",
    "set_backing_open_intent",
    "snapshot_practice_source_display_key",
    "target_page_for_backing_context",
]
