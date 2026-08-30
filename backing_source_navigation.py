"""Navigate from Backing Studio back to the source that created the current context."""

from __future__ import annotations

from typing import Any, Literal

from backing_context import (
    BACKING_CONTEXT_KEY,
    BackingContext,
    get_backing_context,
)
from music_feature_icons import FEATURE_ICONS, feature_label

CreativeReturnPage = Literal["creative", "custom", "picker", "practice"]

BACKING_OPEN_INTENT_KEY = "_backing_open_intent"
BACKING_INTENT_RESTORE_LAST = "restore_last"
BACKING_INTENT_FROM_PRACTICE = "from_practice"
BACKING_INTENT_FROM_SONG_TO_BACKING = "from_song_or_practice_to_backing"
BACKING_INTENT_FROM_CREATIVE = "from_creative"
BACKING_INTENT_SWITCH_CATALOG = "switch_to_catalog_backing"
BACKING_INTENT_SWITCH_CUSTOM = "switch_to_custom_backing"
BACKING_INTENT_CREATIVE_TO_CATALOG = "creative_to_catalog"
KEY_TRANSITION_INTENT_KEY = "_key_transition_intent"
PRACTICE_SOURCE_DISPLAY_KEY = "_practice_source_display_key"
PRACTICE_SOURCE_PICK_KEY = "_practice_source_pick_key"
CREATIVE_RESTORE_FROM_BACKING_KEY = "_creative_restore_from_backing"

# Page-snapshot keys that must not clobber an explicit Return-to-Creative handoff.
# ``handle_studio_page_transition`` runs before early Creative hydrate; skipping these
# prevents stale SBI widget values from winning over entry_jam backing context.
CREATIVE_BACKING_RETURN_WIDGET_KEYS: frozenset[str] = frozenset(
    {
        "improv_entry_mode",
        "improv_intelligence_tab",
        "creative_improv_intelligence_tab",
        "creative_session",
        "_improv_tab_user_touched",
        "improv_active_mission",
        "improv_mission_pick",
        "ii_selected_chord",
        "II_SELECTED_CHORD",
        "ii_selected_section",
        "II_SELECTED_SECTION",
    }
)


def set_backing_open_intent(session: dict[str, Any], intent: str) -> None:
    session[BACKING_OPEN_INTENT_KEY] = str(intent or BACKING_INTENT_RESTORE_LAST).strip()


def consume_backing_open_intent(session: dict[str, Any]) -> str:
    return str(session.pop(BACKING_OPEN_INTENT_KEY, BACKING_INTENT_RESTORE_LAST) or BACKING_INTENT_RESTORE_LAST)


def set_key_transition_intent(session: dict[str, Any], intent: str) -> None:
    session[KEY_TRANSITION_INTENT_KEY] = str(intent or "").strip()


def peek_key_transition_intent(session: dict[str, Any]) -> str:
    return str(session.get(KEY_TRANSITION_INTENT_KEY) or "").strip()


def consume_key_transition_intent(session: dict[str, Any]) -> str:
    return str(session.pop(KEY_TRANSITION_INTENT_KEY, "") or "").strip()


def _backing_intent_preserves_practice_key(intent: str) -> bool:
    return intent in {
        BACKING_INTENT_FROM_PRACTICE,
        BACKING_INTENT_FROM_SONG_TO_BACKING,
    }


def _key_transition_resets_to_original(intent: str) -> bool:
    return intent in {
        BACKING_INTENT_SWITCH_CATALOG,
        BACKING_INTENT_SWITCH_CUSTOM,
        BACKING_INTENT_CREATIVE_TO_CATALOG,
    }


def _backing_sections_for_practice_handoff(session: dict[str, Any]) -> dict[str, list[str]]:
    """Best-effort section map for Practice → Backing scope handoff."""
    try:
        from backing_context import get_backing_context, sections_dict_from_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            sections = sections_dict_from_backing_context(session, ctx)
            if sections:
                return sections
    except ImportError:
        pass
    for key in ("active_song_data", "selected_song"):
        raw = session.get(key)
        if isinstance(raw, dict):
            sections = raw.get("sections")
            if isinstance(sections, dict) and sections:
                return sections
    return {}


def _practice_focus_section_names(
    session: dict[str, Any],
    sections: dict[str, list[str]],
) -> list[str]:
    """Resolve Practice section focus to concrete chart section keys."""
    multi_raw = session.get("practice_focus_sections")
    if isinstance(multi_raw, list) and multi_raw:
        resolved: list[str] = []
        try:
            from practice_studio import practice_active_section_name, practice_is_full_song
        except ImportError:
            return []
        for item in multi_raw:
            if practice_is_full_song(item):
                continue
            name = practice_active_section_name(item, sections) if sections else str(item).strip()
            if name and name not in resolved:
                resolved.append(name)
        if resolved:
            return resolved
    focus = str(session.get("practice_focus_section") or "").strip()
    try:
        from practice_studio import practice_active_section_name, practice_is_full_song
    except ImportError:
        return [focus] if focus else []
    if practice_is_full_song(focus):
        return []
    name = practice_active_section_name(focus, sections) if sections else focus
    return [name] if name else []


def queue_backing_scope_from_practice_focus(
    session: dict[str, Any],
    *,
    section_key: str | None = None,
    section_keys: list[str] | None = None,
    loops: int | None = None,
    force: bool = False,
) -> None:
    """Queue backing playback scope from Practice section focus (widget-safe)."""
    try:
        from custom_progression_lab import (
            PENDING_BACKING_LOOPS,
            PENDING_BACKING_MULTI_SECTIONS,
            PENDING_BACKING_SCOPE,
            PENDING_BACKING_SINGLE_SECTION,
        )
    except ImportError:
        return
    if session.get(PENDING_BACKING_SCOPE) and not force:
        return

    def _queue_selected(names: list[str]) -> None:
        ordered = [str(n).strip() for n in names if str(n).strip()]
        if not ordered:
            return
        session[PENDING_BACKING_SCOPE] = "Selected sections"
        session[PENDING_BACKING_MULTI_SECTIONS] = ordered
        if len(ordered) == 1:
            session[PENDING_BACKING_SINGLE_SECTION] = ordered[0]
        else:
            session.pop(PENDING_BACKING_SINGLE_SECTION, None)
        if loops is not None:
            session[PENDING_BACKING_LOOPS] = int(loops)

    if section_keys:
        _queue_selected(list(section_keys))
        return
    if section_key:
        _queue_selected([str(section_key).strip()])
        return
    sections = _backing_sections_for_practice_handoff(session)
    resolved = _practice_focus_section_names(session, sections)
    if resolved:
        _queue_selected(resolved)
        return
    focus = str(session.get("practice_focus_section") or "").strip()
    try:
        from practice_studio import practice_is_full_song
    except ImportError:
        return
    if practice_is_full_song(focus):
        session[PENDING_BACKING_SCOPE] = "Full song"
        session.pop(PENDING_BACKING_SINGLE_SECTION, None)
        session.pop(PENDING_BACKING_MULTI_SECTIONS, None)


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
        from music_source_ownership import maybe_reset_practice_key_on_source_activation

        maybe_reset_practice_key_on_source_activation(session, st_like=st_like, surface="practice")
    except ImportError:
        pass
    try:
        from music_source_ownership import reconcile_source_ownership

        reconcile_source_ownership(session, st_like=st_like, reason="practice_hydrate")
    except ImportError:
        pass
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
                    from songs.practice_key_state import get_practice_concert_key

                    scoped = (
                        get_practice_concert_key(session, pick)
                        or canonical_display_key_for_pick(session, pick)
                    )
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


def hydrate_picker_source_for_page(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    song_picker_catalog: dict | None = None,
) -> None:
    """Rebuild stale catalog backing_context when Song Selection shows identity drift."""
    injected_catalog = False
    if isinstance(song_picker_catalog, dict) and song_picker_catalog:
        if not isinstance(session.get("_reconcile_song_picker_catalog"), dict):
            session["_reconcile_song_picker_catalog"] = song_picker_catalog
            injected_catalog = True
    try:
        from music_source_ownership import maybe_reset_practice_key_on_source_activation

        maybe_reset_practice_key_on_source_activation(session, st_like=st_like, surface="picker")
    except ImportError:
        pass
    try:
        from music_source_ownership import reconcile_source_ownership

        reconcile_source_ownership(session, st_like=st_like, reason="picker_hydrate")
    except ImportError:
        pass
    finally:
        if injected_catalog:
            session.pop("_reconcile_song_picker_catalog", None)


def open_backing_for_practice_source(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext | None:
    """Open Backing Studio for the current Practice catalog/custom/composition source (Case C)."""
    snapshot_practice_source_display_key(session)
    transition = peek_key_transition_intent(session)
    preserve_key = _backing_intent_preserves_practice_key(transition) if transition else True
    # Composition must win before catalog/custom fallbacks — otherwise Songs→Backing
    # after Custom→Composition steals ownership back to Custom/Catalog.
    try:
        from songs.music_source import (
            composition_song_is_active,
            picker_composition_mode,
        )

        force_composition = bool(session.pop("_force_composition_backing_open", None))
        pick_now = str(session.get("active_catalog_pick_key") or "").strip()
        meta = session.get("active_song_state")
        meta_pick = (
            str((meta or {}).get("pick_key") or "").strip()
            if isinstance(meta, dict)
            else ""
        )
        pick_looks_composition = pick_now.startswith("composition::") or meta_pick.startswith(
            "composition::"
        )
        if (
            force_composition
            or pick_looks_composition
            or composition_song_is_active(session)
            or picker_composition_mode(session)
        ):
            from backing_context import (
                apply_backing_context_to_session,
                build_composition_song_context,
                set_backing_context,
            )
            from composition_songs_bridge import set_composition_source

            set_composition_source(session)
            if not composition_song_is_active(session):
                try:
                    from songs.music_source import ensure_composition_owns_active_song
                    from types import SimpleNamespace

                    st_proxy = st_like if st_like is not None else SimpleNamespace(session_state=session)
                    if not hasattr(st_proxy, "session_state"):
                        st_proxy = SimpleNamespace(session_state=session)
                    ensure_composition_owns_active_song(st_proxy, invalidate_backing=None)
                except Exception:
                    pass
            ctx = build_composition_song_context(session)
            set_backing_context(session, ctx)
            apply_backing_context_to_session(session, ctx, st_like=st_like)
            return ctx
    except ImportError:
        pass
    try:
        from music_source_ownership import (
            activate_catalog_ownership,
            activate_custom_ownership,
            intended_practice_owner,
        )

        owner = intended_practice_owner(session)
        if owner == "custom":
            try:
                from songs.music_source import ensure_custom_active_song_identity

                ensure_custom_active_song_identity(session)
            except ImportError:
                pass
            return activate_custom_ownership(
                session,
                st_like=st_like,
                preserve_practice_key=preserve_key,
            )
        if owner == "catalog":
            return activate_catalog_ownership(
                session,
                st_like=st_like,
                preserve_practice_key=preserve_key,
            )
    except ImportError:
        pass
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
            composition_song_is_active,
            cpl_session_is_active,
            ensure_custom_active_song_identity,
            is_custom_progression,
            picker_composition_mode,
        )

        if composition_song_is_active(session) or picker_composition_mode(session):
            from backing_context import build_composition_song_context
            from composition_songs_bridge import set_composition_source

            set_composition_source(session)
            ctx = build_composition_song_context(session)
            set_backing_context(session, ctx)
            apply_backing_context_to_session(session, ctx, st_like=st_like)
            return ctx
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


def _creative_handoff_entry_mode(session: dict[str, Any]) -> str:
    """Authoritative Creative entry mode for Open Backing / return handoff."""
    try:
        from studio_page_state import IMPROV_ENTRY_MODES
    except ImportError:
        IMPROV_ENTRY_MODES = ("Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator")  # type: ignore[misc,assignment]
    tab = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "").strip()
    if tab == "Entry & Jam":
        try:
            from creative_session_state import get_creative_session

            sess = get_creative_session(session)
            if sess is not None:
                if sess.tool_type == "jam_session_generator":
                    return "Jam Session Generator"
                if sess.tool_type == "entry_style_jam":
                    return "Style Jam Mode"
        except ImportError:
            pass
        try:
            from music_workflow_state_store import get_active_workflow_pointer

            ptr = get_active_workflow_pointer(session)
            if ptr is not None:
                owner = str(ptr.workflow_owner or "")
                if owner == "jam_session_generator":
                    return "Jam Session Generator"
                if owner == "style_jam":
                    return "Style Jam Mode"
        except ImportError:
            pass
    try:
        live = str(
            session.get("improv_entry_mode") or session.get("creative_improv_entry_mode") or ""
        ).strip()
        if live in IMPROV_ENTRY_MODES:
            return live
    except ImportError:
        pass
    try:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY

        pending = str(session.get(PENDING_IMPROV_ENTRY_MODE_KEY) or "").strip()
        if pending in IMPROV_ENTRY_MODES:
            return pending
    except ImportError:
        pass
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None:
            if sess.tool_type == "jam_session_generator":
                return "Jam Session Generator"
            if sess.tool_type == "entry_style_jam":
                return "Style Jam Mode"
            if sess.tool_type == "song_based_improvisation":
                return "Song-Based Improvisation"
            if sess.tool_type == "mission":
                return "Song-Based Improvisation"
            entry = str(sess.entry_mode or "").strip()
            if entry in IMPROV_ENTRY_MODES:
                return entry
    except ImportError:
        pass
    return str(session.get("improv_entry_mode") or "").strip()


def open_backing_for_creative_source(session: dict[str, Any], *, st_like: Any | None = None) -> BackingContext | None:
    """Re-apply Creative backing when explicitly opening Backing Studio from Creative Lab."""
    try:
        from music_source_ownership import (
            activate_custom_ownership,
            activate_entry_jam_ownership,
            activate_mission_ownership,
            activate_sbi_ownership,
        )

        if str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "").strip() == "Missions":
            return activate_mission_ownership(session, st_like=st_like)
        if session.get("improv_mission_backing_handoff"):
            session.pop("improv_mission_backing_handoff", None)
            return activate_mission_ownership(session, st_like=st_like)
        entry = _creative_handoff_entry_mode(session)
        if entry in ("Style Jam Mode", "Jam Session Generator"):
            return activate_entry_jam_ownership(session, st_like=st_like)
        if entry == "Song-Based Improvisation":
            try:
                from studio_page_state import resolve_improv_song_source

                source = resolve_improv_song_source(session)
            except ImportError:
                source = "Active song"
            if source == "Custom progression":
                return activate_custom_ownership(session, st_like=st_like)
            return activate_sbi_ownership(session, st_like=st_like)
        return activate_entry_jam_ownership(session, st_like=st_like)
    except ImportError:
        pass
    try:
        from backing_context import open_backing_from_creative

        return open_backing_from_creative(session, source="entry_jam", st_like=st_like)
    except ImportError:
        return None


def hydrate_backing_source_for_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply backing navigation intent and preserve last Backing Studio source (Cases B + refresh)."""
    intent = consume_backing_open_intent(session)
    if intent == BACKING_INTENT_FROM_CREATIVE:
        open_backing_for_creative_source(session, st_like=st_like)
        try:
            from backing_context import sync_live_keys_from_backing_context

            sync_live_keys_from_backing_context(session, st_like=st_like)
        except ImportError:
            pass
        return
    if intent == BACKING_INTENT_FROM_PRACTICE or intent == BACKING_INTENT_FROM_SONG_TO_BACKING:
        try:
            from custom_progression_lab import (
                PENDING_BACKING_LOOPS,
                PENDING_BACKING_MULTI_SECTIONS,
                PENDING_BACKING_SCOPE,
                PENDING_BACKING_SINGLE_SECTION,
            )
        except ImportError:
            PENDING_BACKING_LOOPS = "_pending_backing_loops"  # type: ignore[misc,assignment]
            PENDING_BACKING_MULTI_SECTIONS = "_pending_backing_multi_sections"  # type: ignore[misc,assignment]
            PENDING_BACKING_SCOPE = "_pending_backing_scope"  # type: ignore[misc,assignment]
            PENDING_BACKING_SINGLE_SECTION = "_pending_backing_single_section"  # type: ignore[misc,assignment]
        _saved_scope = session.get(PENDING_BACKING_SCOPE)
        _saved_section = session.get(PENDING_BACKING_SINGLE_SECTION)
        _saved_multi = session.get(PENDING_BACKING_MULTI_SECTIONS)
        _saved_loops = session.get(PENDING_BACKING_LOOPS)
        set_key_transition_intent(session, BACKING_INTENT_FROM_SONG_TO_BACKING)
        open_backing_for_practice_source(session, st_like=st_like)
        if _saved_scope:
            session[PENDING_BACKING_SCOPE] = _saved_scope
            if _saved_multi:
                session[PENDING_BACKING_MULTI_SECTIONS] = list(_saved_multi)
            if _saved_section:
                session[PENDING_BACKING_SINGLE_SECTION] = _saved_section
            if _saved_loops is not None:
                session[PENDING_BACKING_LOOPS] = int(_saved_loops)
        else:
            queue_backing_scope_from_practice_focus(session, force=True)
        consume_key_transition_intent(session)
        return
    try:
        from music_source_ownership import intentional_creative_backing_active

        if intentional_creative_backing_active(session):
            ctx = get_backing_context(session)
            if ctx is not None and str(getattr(ctx, "source", "") or "") in {
                "entry_jam",
                "song_improv",
                "mission",
            }:
                try:
                    from backing_context import sync_live_keys_from_backing_context

                    sync_live_keys_from_backing_context(session, st_like=st_like)
                except ImportError:
                    pass
                return
    except ImportError:
        pass
    try:
        from music_source_ownership import intentional_creative_backing_active, reconcile_source_ownership

        if not intentional_creative_backing_active(session):
            reconcile_source_ownership(session, st_like=st_like, reason="backing_hydrate")
    except ImportError:
        pass
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
            try:
                from music_source_ownership import intentional_creative_backing_active

                if intentional_creative_backing_active(session):
                    ctx = get_backing_context(session)
                    if ctx is not None and str(getattr(ctx, "source", "") or "") in {
                        "entry_jam",
                        "song_improv",
                        "mission",
                    }:
                        return
            except ImportError:
                pass
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
            try:
                from backing_context import sync_live_keys_from_backing_context

                sync_live_keys_from_backing_context(session, st_like=st_like)
            except ImportError:
                pass
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

    owners_aligned = "n/a"
    intended_owner = "n/a"
    backing_owner = "n/a"
    identity_aligned = "n/a"
    canonical_pick = "n/a"
    try:
        from music_source_ownership import (
            active_catalog_pick_key,
            catalog_identity_aligns,
            current_backing_owner,
            intended_practice_owner,
            practice_backing_owners_align,
        )

        intended_owner = _diag_value(intended_practice_owner(session), default="none")
        backing_owner = _diag_value(current_backing_owner(session), default="none")
        owners_aligned = str(practice_backing_owners_align(session))
        identity_aligned = str(catalog_identity_aligns(session))
        canonical_pick = _diag_value(active_catalog_pick_key(session))
    except Exception:
        pass

    rows = {
        "page": _diag_value(session.get("studio_page")),
        "active_music_source": _diag_value(source_type),
        "intended_practice_owner": intended_owner,
        "current_backing_owner": backing_owner,
        "canonical_active_pick_key": canonical_pick,
        "catalog_identity_aligned": identity_aligned,
        "practice_backing_aligned": owners_aligned,
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
        "catalog_rebuild_needed": _diag_value(session.get("catalog_rebuild_needed")),
        "catalog_rebuild_ran": _diag_value(session.get("catalog_rebuild_ran")),
        "catalog_rebuild_pick_key": _diag_value(session.get("catalog_rebuild_pick_key")),
        "catalog_rebuild_result_bound_pick": _diag_value(
            session.get("catalog_rebuild_result_bound_pick")
        ),
        "catalog_rebuild_result_key": _diag_value(session.get("catalog_rebuild_result_key")),
        "catalog_rebuild_result_bpm": _diag_value(session.get("catalog_rebuild_result_bpm")),
        "catalog_rebuild_catalog_present": _diag_value(session.get("catalog_rebuild_catalog_present")),
        "catalog_rebuild_row_bpm": _diag_value(session.get("catalog_rebuild_row_bpm")),
        "catalog_rebuild_row_default_bpm": _diag_value(session.get("catalog_rebuild_row_default_bpm")),
        "catalog_rebuild_selected_bpm_after_merge": _diag_value(
            session.get("catalog_rebuild_selected_bpm_after_merge")
        ),
        "catalog_rebuild_canonical_bpm": _diag_value(session.get("catalog_rebuild_canonical_bpm")),
        "catalog_rebuild_ctx_bpm": _diag_value(session.get("catalog_rebuild_ctx_bpm")),
        "last_reconcile_reason": _diag_value(session.get("last_reconcile_reason")),
    }
    restore_diag = dict(session.get("_catalog_restore_diag") or {})
    restore_diag.update(dict(session.get("_catalog_backing_restore_diag") or {}))
    guard_diag = dict(session.get("_creative_catalog_guard_diag") or {})
    for key in (
        "catalog_before_creative_pick",
        "catalog_restore_pick_chosen",
        "catalog_restore_pick_source",
        "catalog_restore_original_key",
        "catalog_restore_target_key",
        "catalog_restore_bpm",
        "creative_key_before_restore",
        "display_key_after_restore",
        "concert_key_after_restore",
        "backing_context_title_after_restore",
        "catalog_song_before_jam_edit",
        "catalog_song_after_jam_edit",
        "catalog_snapshot_before_creative",
        "catalog_snapshot_after_creative",
        "last_catalog_song_writer",
        "catalog_restore_pin_pick",
        "catalog_restore_pin_writer",
    ):
        val = restore_diag.get(key)
        if val in (None, "") and key in guard_diag:
            val = guard_diag.get(key)
        if val not in (None, ""):
            rows[key] = _diag_value(val)
    try:
        from songs.bpm_state import BPM_WIDGET_KEY, LAST_BPM_SONG
        from songs.playback_defaults import LAST_BACKING_DEFAULTS_SONG_ID

        rows["backing_track_bpm"] = _diag_value(session.get("backing_track_bpm"))
        rows["last_bpm_song"] = _diag_value(session.get(LAST_BPM_SONG))
        rows["last_backing_defaults_song_id"] = _diag_value(session.get(LAST_BACKING_DEFAULTS_SONG_ID))
        rows["bpm_widget_key"] = _diag_value(session.get(BPM_WIDGET_KEY))
    except ImportError:
        pass

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


def resolve_entry_jam_entry_mode(
    session: dict[str, Any],
    *,
    ctx: BackingContext | None = None,
) -> str:
    """Authoritative entry mode for entry_jam — never inherit stale SBI widget state."""
    handoff = str(session.get("_backing_handoff_entry_mode") or "").strip()
    if handoff in ("Style Jam Mode", "Jam Session Generator"):
        return handoff
    try:
        from generated_workflow_artifact import BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY

        raw = session.get(BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY)
        if isinstance(raw, dict):
            snap_entry = str(raw.get("entry_mode") or "").strip()
            if snap_entry in ("Style Jam Mode", "Jam Session Generator"):
                return snap_entry
    except ImportError:
        pass
    widget = str(session.get("improv_entry_mode") or "").strip()
    if widget == "Style Jam Mode":
        return "Style Jam Mode"
    if widget == "Jam Session Generator":
        return "Jam Session Generator"
    if ctx is not None:
        ctx_entry = str(ctx.entry_mode or "").strip()
        if ctx_entry in ("Style Jam Mode", "Jam Session Generator"):
            return ctx_entry
    if widget == "Jam Session Generator":
        return widget
    try:
        from backing_source_navigation import _creative_handoff_entry_mode

        resolved = _creative_handoff_entry_mode(session)
        if resolved in ("Style Jam Mode", "Jam Session Generator"):
            return resolved
    except ImportError:
        pass
    try:
        from creative_session_state import get_creative_session
        from studio_page_state import IMPROV_ENTRY_MODES

        sess = get_creative_session(session)
        if sess is not None:
            if sess.tool_type == "jam_session_generator":
                return "Jam Session Generator"
            if sess.tool_type == "entry_style_jam":
                return "Style Jam Mode"
            entry = str(sess.entry_mode or "").strip()
            if entry in IMPROV_ENTRY_MODES and entry != "Song-Based Improvisation":
                return entry
    except ImportError:
        pass
    if session.get("improv_generated_sections"):
        return "Style Jam Mode"
    if widget == "Style Jam Mode":
        return widget
    return "Style Jam Mode"


def _backing_creative_concert_key(session: dict[str, Any]) -> str:
    """Concert key from active Creative backing_context — authoritative on return."""
    try:
        from backing_context import active_creative_backing_context

        ctx = active_creative_backing_context(session)
        if ctx is not None:
            return str(ctx.concert_key or ctx.display_key or ctx.key or "").strip()
    except ImportError:
        pass
    return ""


def _clear_creative_page_hydrate_flags(session: dict[str, Any]) -> None:
    for key in list(session.keys()):
        if str(key).startswith("_creative_session_hydrated_"):
            session.pop(key, None)


def creative_return_identity_from_backing_context(
    session: dict[str, Any],
    ctx: BackingContext,
) -> dict[str, str]:
    """Authoritative Creative tab + entry submode from backing_context (not stale session widgets)."""
    source = str(ctx.source or "").strip()
    if source == "song_improv":
        return {
            "backing_source": source,
            "intelligence_tab": "Entry & Jam",
            "entry_mode": "Song-Based Improvisation",
            "workflow_owner": "song_based_improvisation",
        }
    if source == "entry_jam":
        entry = str(ctx.entry_mode or "").strip()
        if entry not in ("Style Jam Mode", "Jam Session Generator"):
            entry = resolve_entry_jam_entry_mode(session, ctx=ctx)
        owner = "jam_session_generator" if entry == "Jam Session Generator" else "style_jam"
        return {
            "backing_source": source,
            "intelligence_tab": "Entry & Jam",
            "entry_mode": entry,
            "workflow_owner": owner,
        }
    if source == "mission":
        entry = str(ctx.entry_mode or "Song-Based Improvisation").strip() or "Song-Based Improvisation"
        return {
            "backing_source": source,
            "intelligence_tab": "Missions",
            "entry_mode": entry,
            "workflow_owner": "mission_jam",
        }
    tab = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "Entry & Jam").strip()
    entry = str(session.get("improv_entry_mode") or "").strip() or "Style Jam Mode"
    return {
        "backing_source": source or "entry_jam",
        "intelligence_tab": tab or "Entry & Jam",
        "entry_mode": entry,
        "workflow_owner": "style_jam",
    }


def seal_creative_return_context_from_backing(
    session: dict[str, Any],
    ctx: BackingContext,
) -> dict[str, str]:
    """Return-click payload — mirrors launch-sealed route (no re-inference)."""
    try:
        from backing_creative_return_route import get_creative_return_route

        route = get_creative_return_route(session)
    except ImportError:
        route = None
    if isinstance(route, dict):
        sealed = {
            "source": str(route.get("backing_source") or getattr(ctx, "source", "") or ""),
            "entry_mode": str(route.get("entry_mode") or ""),
            "creative_tab": str(route.get("intelligence_tab") or ""),
            "workflow_owner": str(route.get("workflow_owner") or ""),
            "display_key": str(getattr(ctx, "display_key", "") or getattr(ctx, "concert_key", "") or ""),
            "concert_key": str(getattr(ctx, "concert_key", "") or ""),
            "song_pick": str(session.get("active_catalog_pick_key") or route.get("song_pick_key") or ""),
        }
        return sealed
    ident = creative_return_identity_from_backing_context(session, ctx)
    return {
        "source": ident["backing_source"],
        "entry_mode": ident["entry_mode"],
        "creative_tab": ident["intelligence_tab"],
        "workflow_owner": ident["workflow_owner"],
        "display_key": str(getattr(ctx, "display_key", "") or getattr(ctx, "concert_key", "") or ""),
        "concert_key": str(getattr(ctx, "concert_key", "") or ""),
        "song_pick": str(session.get("active_catalog_pick_key") or ""),
    }


def apply_creative_return_identity_to_session(
    session: dict[str, Any],
    ctx: BackingContext,
    *,
    widget_safe: bool = False,
) -> dict[str, str]:
    """Prime improv tab + entry mode from backing_context before workflow activation."""
    ident = creative_return_identity_from_backing_context(session, ctx)
    tab = ident["intelligence_tab"]
    entry = ident["entry_mode"]
    try:
        from session_widget_safe import safe_session_assign
        from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

        safe_session_assign(session, "improv_intelligence_tab", tab, widget_safe=widget_safe)
        safe_session_assign(session, "improv_entry_mode", entry, widget_safe=widget_safe)
        session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
    except ImportError:
        session["improv_intelligence_tab"] = tab
        session["creative_improv_intelligence_tab"] = tab
        session["improv_entry_mode"] = entry
    session.pop("_improv_tab_user_touched", None)
    return ident


def _activate_workflow_for_creative_return(session: dict[str, Any], ctx: BackingContext, ident: dict[str, str]) -> None:
    owner = str(ident.get("workflow_owner") or "").strip()
    try:
        from generated_jam_key_context import deactivate_generated_jam_key_ownership
        from music_workflow_activation import activate_workflow_simple

        if owner == "song_based_improvisation":
            activate_workflow_simple(
                session,
                "song_based_improvisation",
                activation_source="return_from_backing",
                return_route="creative",
            )
            try:
                from song_improv_scope_authority import (
                    apply_song_improv_entry_defaults,
                    restore_song_improv_creative_navigation,
                )

                restore_song_improv_creative_navigation(session)
                apply_song_improv_entry_defaults(session, source="return_from_backing")
            except ImportError:
                pass
            deactivate_generated_jam_key_ownership(session)
            return
        if owner == "style_jam":
            activate_workflow_simple(
                session,
                "style_jam",
                activation_source="return_from_backing",
                return_route="creative",
            )
            return
        if owner == "jam_session_generator":
            activate_workflow_simple(
                session,
                "jam_session_generator",
                activation_source="return_from_backing",
                return_route="creative",
            )
            return
        if owner == "mission_jam":
            activate_workflow_simple(
                session,
                "mission_jam",
                activation_source="return_from_backing",
                return_route="creative",
                navigation_intent="return_from_backing",
            )
            return
        if str(ctx.source or "") == "entry_jam":
            activate_workflow_simple(
                session,
                owner or "style_jam",
                activation_source="return_from_backing",
                return_route="creative",
            )
    except ImportError:
        try:
            from generated_jam_key_context import deactivate_generated_jam_key_ownership
            from workflow_musical_authority import switch_workflow_owner

            if owner in {"style_jam", "jam_session_generator", "song_based_improvisation", "mission_jam"}:
                switch_workflow_owner(session, owner)
                if owner == "song_based_improvisation":
                    deactivate_generated_jam_key_ownership(session)
        except ImportError:
            pass


def rehydrate_creative_from_backing_context(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    widget_safe: bool = True,
) -> bool:
    """Restore Creative widgets + session blob from active entry_jam/song_improv/mission ctx."""
    try:
        from backing_context import active_creative_backing_context
    except ImportError:
        return False
    ctx = active_creative_backing_context(session)
    if ctx is None:
        return False
    restore_session_widgets_from_backing_context(session, ctx, widget_safe=widget_safe)
    try:
        from backing_context import sync_live_keys_from_backing_context

        sync_live_keys_from_backing_context(session, st_like=st_like, widget_safe=widget_safe)
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    if page:
        session[f"_creative_session_hydrated_{page}"] = True
    return True


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
    def _fixed_concert(candidate: str) -> str:
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                original = str(ctx.key or candidate or "C").strip() or "C"
                return resolve_practice_concert_key_for_song(session, original, fallback=candidate or original)
        except ImportError:
            pass
        return str(candidate or "").strip()

    if ctx.source in {"custom_progression", "regular_song"}:
        concert = str(
            ctx.concert_key or ctx.display_key or ctx.key or session.get("display_key") or ""
        ).strip()
        concert = _fixed_concert(concert)
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
    concert = _fixed_concert(concert)
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
        session["creative_improv_intelligence_tab"] = "Missions"
        if ctx.mission_id:
            session["improv_active_mission"] = ctx.mission_id
            session["improv_mission_pick"] = ctx.mission_id
        if ctx.progression:
            chord = str(ctx.progression[0] or "").strip()
            if chord:
                session["ii_selected_chord"] = chord
                session["II_SELECTED_CHORD"] = chord
        if ctx.section:
            sec = str(ctx.section).split("·")[0].strip()
            if sec:
                session["ii_selected_section"] = sec
                session["II_SELECTED_SECTION"] = sec
        try:
            from mission_practice_context import refresh_mission_practice_context

            refresh_mission_practice_context(session)
        except ImportError:
            pass
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
        session["creative_improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        try:
            from song_improv_scope_authority import apply_song_improv_entry_defaults

            apply_song_improv_entry_defaults(session, source="restore_from_song_improv_ctx")
        except ImportError:
            pass
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
        entry = resolve_entry_jam_entry_mode(session, ctx=ctx)
        tab = "Entry & Jam"
        try:
            from session_widget_safe import safe_session_assign
            from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

            safe_session_assign(session, "improv_intelligence_tab", tab, widget_safe=widget_safe)
            safe_session_assign(session, "improv_entry_mode", entry, widget_safe=widget_safe)
            session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = tab
        except ImportError:
            session["improv_intelligence_tab"] = tab
            session["improv_entry_mode"] = entry
        if entry == "Jam Session Generator":
            if concert:
                try:
                    from session_widget_safe import safe_session_assign

                    safe_session_assign(session, "improv_jam_key", concert, widget_safe=widget_safe)
                except ImportError:
                    session["improv_jam_key"] = concert
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
                try:
                    from session_widget_safe import safe_session_assign

                    safe_session_assign(session, "improv_style", ctx.style, widget_safe=widget_safe)
                except ImportError:
                    session["improv_style"] = ctx.style
            if concert:
                try:
                    from session_widget_safe import safe_session_assign

                    safe_session_assign(session, "improv_style_key", concert, widget_safe=widget_safe)
                except ImportError:
                    session["improv_style_key"] = concert
            if ctx.bpm:
                try:
                    from session_widget_safe import safe_session_assign

                    safe_session_assign(session, "improv_style_bpm", int(ctx.bpm), widget_safe=widget_safe)
                except ImportError:
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
            if ctx.source == "entry_jam":
                sess.entry_mode = resolve_entry_jam_entry_mode(session, ctx=ctx)
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
    """Restore Creative from launch-sealed return route + backing_context snapshot."""
    ctx = get_backing_context(session)
    page = target_page_for_backing_context(ctx)
    if ctx is None:
        return page
    route = None
    route_source = "none"
    try:
        from backing_creative_return_route import apply_creative_return_route, get_creative_return_route
        from creative_return_trace import snapshot_return_surface, trace_return_after_apply, trace_return_route_read

        route = get_creative_return_route(session)
        route_source = "blob_sealed" if isinstance(route, dict) else "legacy_inference_fallback"
        trace_return_route_read(session, route=route, route_source=route_source)
        before_apply = snapshot_return_surface(session)
        if isinstance(route, dict):
            apply_creative_return_route(session, route, ctx=ctx)
            requested = dict(route)
        else:
            ident = apply_creative_return_identity_to_session(session, ctx)
            _activate_workflow_for_creative_return(session, ctx, ident)
            restore_session_widgets_from_backing_context(session, ctx)
            requested = {"legacy": True, "ident": str(ident)}
            project_return_destination_to_canonical_creative_selectors(session)
        after_apply = snapshot_return_surface(session)
        trace_return_after_apply(
            session,
            requested={
                "studio_page": "creative",
                "intelligence_tab": requested.get("intelligence_tab"),
                "entry_mode": requested.get("entry_mode"),
                "workflow_owner": requested.get("workflow_owner"),
                "backing_source": requested.get("backing_source"),
                "mission_id": requested.get("mission_id"),
            },
            written={
                "studio_page": str(session.get("studio_page") or ""),
                "improv_intelligence_tab": after_apply.get("improv_intelligence_tab"),
                "creative_improv_intelligence_tab": after_apply.get("creative_improv_intelligence_tab"),
                "improv_entry_mode": after_apply.get("improv_entry_mode"),
                "improv_active_mission": after_apply.get("improv_active_mission"),
                "before_apply_snapshot": before_apply,
            },
        )
    except ImportError:
        ident = apply_creative_return_identity_to_session(session, ctx)
        _activate_workflow_for_creative_return(session, ctx, ident)
        restore_session_widgets_from_backing_context(session, ctx)
        project_return_destination_to_canonical_creative_selectors(session)
    _clear_creative_page_hydrate_flags(session)
    session[CREATIVE_RESTORE_FROM_BACKING_KEY] = True
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass
    merge_live_practice_into_creative_session(session, prefer_backing_context_key=True)
    return page


def project_return_destination_to_canonical_creative_selectors(
    session: dict[str, Any],
    *,
    intelligence_tab: str = "",
    entry_mode: str = "",
) -> None:
    """Make sealed Return destination authoritative in canonical Creative selector blob (first widget sync)."""
    tab = str(intelligence_tab or session.get("improv_intelligence_tab") or "").strip()
    entry = str(entry_mode or session.get("improv_entry_mode") or "").strip()
    if not tab and not entry:
        return
    try:
        from creative_tab_tool_persistence import commit_creative_selector_to_canonical
    except ImportError:
        return
    if tab:
        commit_creative_selector_to_canonical(
            session,
            "improv_intelligence_tab",
            tab,
            reason="return_from_backing",
            projection_source="sealed_return_route",
        )
    if entry:
        commit_creative_selector_to_canonical(
            session,
            "improv_entry_mode",
            entry,
            reason="return_from_backing",
            projection_source="sealed_return_route",
        )


def prepare_return_to_mission_detail(session: dict[str, Any]) -> CreativeReturnPage:
    """Return to Creative with exact mission section/chord/example context restored."""
    ctx = get_backing_context(session)
    page = prepare_return_to_backing_source(session)
    if ctx is not None and str(ctx.source or "") == "mission":
        session["improv_intelligence_tab"] = "Missions"
        session["creative_improv_intelligence_tab"] = "Missions"
        restore_session_widgets_from_backing_context(session, ctx)
        try:
            from active_musical_workflow_envelope import reconcile_mission_workflow_envelope

            reconcile_mission_workflow_envelope(session)
        except ImportError:
            pass
    return page


def merge_live_practice_into_creative_session(
    session: dict[str, Any],
    *,
    prefer_backing_context_key: bool = False,
) -> None:
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
    ctx_key = _backing_creative_concert_key(session) if prefer_backing_context_key else ""
    if ctx_key:
        live_key = ctx_key
    else:
        live_key = str(
            session.get("concert_key")
            or session.get(PENDING_DISPLAY_KEY)
            or session.get("display_key")
            or ""
        ).strip()
    live_inst = str(session.get("instrument") or "").strip()
    if live_key:
        try:
            from backing_context import get_backing_context
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                ctx = get_backing_context(session)
                original = str(getattr(ctx, "key", "") or live_key or "C").strip() or "C"
                live_key = resolve_practice_concert_key_for_song(session, original, fallback=live_key)
        except ImportError:
            pass
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


def return_to_catalog_song_backing_label(*, custom: bool = False) -> str:
    if custom:
        return "🎧 Return to Custom Song Backing"
    return "🎧 Return to Catalog Song Backing"


def return_to_source_button_label(ctx: BackingContext | None) -> str:
    """User-facing label for the return-to-source button."""
    if ctx is None:
        return "Return to source"
    if ctx.source == "custom_progression":
        return feature_label("custom", "Return to Custom Page")
    if ctx.source == "regular_song":
        return "🎵 Return to Catalog Song"
    return feature_label("creative", "Return to Creative Page")


def edit_in_creative_button_label(ctx: BackingContext | None) -> str:
    """Backward-compatible alias."""
    return return_to_source_button_label(ctx)


__all__ = [
    "BACKING_CONTEXT_KEY",
    "BACKING_INTENT_CREATIVE_TO_CATALOG",
    "BACKING_INTENT_FROM_PRACTICE",
    "BACKING_INTENT_FROM_SONG_TO_BACKING",
    "BACKING_INTENT_RESTORE_LAST",
    "BACKING_INTENT_SWITCH_CATALOG",
    "BACKING_INTENT_SWITCH_CUSTOM",
    "BACKING_OPEN_INTENT_KEY",
    "KEY_TRANSITION_INTENT_KEY",
    "CreativeReturnPage",
    "PRACTICE_SOURCE_DISPLAY_KEY",
    "CREATIVE_RESTORE_FROM_BACKING_KEY",
    "apply_creative_return_identity_to_session",
    "consume_backing_open_intent",
    "consume_key_transition_intent",
    "creative_return_identity_from_backing_context",
    "edit_in_creative_button_label",
    "hydrate_backing_source_for_page",
    "hydrate_picker_source_for_page",
    "hydrate_practice_source_for_page",
    "merge_live_practice_into_creative_session",
    "open_backing_for_practice_source",
    "queue_backing_scope_from_practice_focus",
    "prepare_return_to_backing_source",
    "prepare_return_to_mission_detail",
    "rehydrate_creative_from_backing_context",
    "resolve_entry_jam_entry_mode",
    "render_source_context_debug",
    "render_source_ownership_dev_table",
    "source_ownership_diagnostics_enabled",
    "restore_practice_source_display_key",
    "restore_session_widgets_from_backing_context",
    "return_to_catalog_song_backing_label",
    "return_to_source_button_label",
    "seal_creative_return_context_from_backing",
    "set_backing_open_intent",
    "set_key_transition_intent",
    "peek_key_transition_intent",
    "snapshot_practice_source_display_key",
    "target_page_for_backing_context",
]
