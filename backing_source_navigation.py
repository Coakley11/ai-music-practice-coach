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
BACKING_INTENT_FROM_SONG_TO_BACKING = "from_song_or_practice_to_backing"
BACKING_INTENT_FROM_CREATIVE = "from_creative"
BACKING_INTENT_SWITCH_CATALOG = "switch_to_catalog_backing"
BACKING_INTENT_SWITCH_CUSTOM = "switch_to_custom_backing"
BACKING_INTENT_CREATIVE_TO_CATALOG = "creative_to_catalog"
KEY_TRANSITION_INTENT_KEY = "_key_transition_intent"
PRACTICE_SOURCE_DISPLAY_KEY = "_practice_source_display_key"
PRACTICE_SOURCE_PICK_KEY = "_practice_source_pick_key"
CREATIVE_RESTORE_FROM_BACKING_KEY = "_creative_restore_from_backing"

# Active-source epoch for top-level Backing restore eligibility.
# Restore last Mission/Jam/SBI Backing only while this matches the current
# catalog/custom active source identity.
BACKING_RESTORE_ANCHOR_KEY = "_backing_restore_anchor_source"
BACKING_RESTORE_EPOCH_KEY = "_backing_restore_epoch"


def resolve_active_source_identity_for_restore(session: dict[str, Any]) -> str:
    """Stable active base-source identity (catalog pick or custom progression).

    Always derive from the live catalog/custom pick — never prefer a stale
    ``ACTIVE_SONG_IDENTITY_KEY`` that can lag behind ``selected_song`` / sidebar
    (E4 split-brain: sidebar Country Roads, identity still Love Story).
    """
    try:
        from songs.music_source import (
            ACTIVE_SONG_IDENTITY_KEY,
            compute_active_song_identity,
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        is_custom = bool(
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        )
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        title = ""
        artist = ""
        original = ""
        sel = session.get("selected_song")
        if isinstance(sel, dict):
            sel_pick = str(sel.get("pick_key") or "").strip()
            if sel_pick and not pick:
                pick = sel_pick
            title = str(sel.get("title") or sel.get("name") or "").strip()
            artist = str(sel.get("artist") or "").strip()
            original = str(sel.get("key") or sel.get("original_key") or "").strip()
        if not pick and not is_custom:
            try:
                from active_song_state import canonical_active_song_context

                ctx = canonical_active_song_context(session)
                if isinstance(ctx, dict):
                    pick = str(ctx.get("pick_key") or "").strip()
            except ImportError:
                pass
        custom_rev = str(
            session.get("custom_progression_revision_id")
            or session.get("cpl_revision_id")
            or ""
        ).strip()
        computed = compute_active_song_identity(
            pick_key=pick,
            title=title,
            artist=artist,
            original_key=original,
            is_custom=is_custom,
            custom_revision=custom_rev,
        )
        existing = str(session.get(ACTIVE_SONG_IDENTITY_KEY) or "").strip()
        if computed and existing != computed:
            session[ACTIVE_SONG_IDENTITY_KEY] = computed
        return computed or existing
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
        sel = session.get("selected_song")
        if isinstance(sel, dict):
            sel_pick = str(sel.get("pick_key") or "").strip()
            if sel_pick:
                pick = sel_pick
        return f"pk::{pick}" if pick else ""


def stamp_backing_restore_anchor(session: dict[str, Any], *, anchor: str = "") -> str:
    """Record which active source owns the current Backing restore eligibility."""
    identity = str(anchor or resolve_active_source_identity_for_restore(session) or "").strip()
    if identity:
        session[BACKING_RESTORE_ANCHOR_KEY] = identity
        try:
            import time

            session[BACKING_RESTORE_EPOCH_KEY] = float(time.time())
        except Exception:
            session[BACKING_RESTORE_EPOCH_KEY] = 1
    return identity


def backing_restore_anchor(session: dict[str, Any]) -> str:
    return str(session.get(BACKING_RESTORE_ANCHOR_KEY) or "").strip()


def backing_restore_eligible(session: dict[str, Any]) -> bool:
    """True when last Backing may be restored for top-level Backing nav."""
    anchor = backing_restore_anchor(session)
    current = resolve_active_source_identity_for_restore(session)
    if not anchor or not current:
        return False
    return anchor == current


def invalidate_backing_restore_for_active_source_change(
    session: dict[str, Any],
    *,
    previous_identity: str = "",
    new_identity: str = "",
    reason: str = "active_source_change",
) -> bool:
    """Invalidate CURRENT Backing restore/play-session pointers for a new active source.

    Does not delete separately persisted library history — only clears the current
    restore eligibility so top-level Backing initializes regular Backing for the
    newly active source.

    Must prove a real identity change before expiring. Empty previous identity with
    no restore anchor is a first-commit / same-catalog hydrate (Case A Current BPM
    must survive ``restore_regular_song_backing`` / ``force_reset`` creative_to_catalog).
    """
    prev = str(previous_identity or "").strip()
    if not prev:
        prev = backing_restore_anchor(session)
    nxt = str(new_identity or "").strip()
    if not nxt:
        nxt = resolve_active_source_identity_for_restore(session)
    # No proven change → do not expire play session or clear restore pointers.
    if not prev or not nxt or prev == nxt:
        return False
    try:
        from backing_play_session import expire_backing_play_session

        expire_backing_play_session(session)
    except ImportError:
        session.pop("_backing_play_session", None)
        session["_backing_play_session_expired"] = True
    try:
        from backing_context import clear_backing_context

        clear_backing_context(session)
    except ImportError:
        session.pop(BACKING_CONTEXT_KEY, None)
    session.pop(BACKING_RESTORE_ANCHOR_KEY, None)
    session.pop(BACKING_RESTORE_EPOCH_KEY, None)
    session.pop(BACKING_OPEN_INTENT_KEY, None)
    session.pop(BACKING_ENTRY_CLASS_KEY, None)
    session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None)
    session.pop("improv_mission_backing_handoff", None)
    session.pop("_backing_explicit_handoff_source", None)
    try:
        from music_workflow_pending_backing_handoff import PENDING_BACKING_WORKFLOW_KEY

        session.pop(PENDING_BACKING_WORKFLOW_KEY, None)
    except ImportError:
        pass
    try:
        from creative_key_sync import invalidate_creative_backing_context

        invalidate_creative_backing_context(session)
    except ImportError:
        pass
    # Explicit Songs Catalog/Custom switch outranks sealed Mission/SBI/Jam.
    session["_backing_released_specialized_context"] = True
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            BACKING_PREF_CUSTOM,
            set_backing_source_preference,
        )
        from songs.music_source import SOURCE_CUSTOM, is_custom_progression

        if is_custom_progression(session) or str(session.get("active_music_source") or "") == SOURCE_CUSTOM:
            set_backing_source_preference(session, BACKING_PREF_CUSTOM)
        else:
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
    except ImportError:
        pass
    session["_backing_restore_invalidated_reason"] = str(reason or "active_source_change")
    session["_backing_restore_invalidated_from"] = prev
    session["_backing_restore_invalidated_to"] = nxt
    return True


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
    """Open Backing Studio for the current Practice catalog/custom source (Case C)."""
    snapshot_practice_source_display_key(session)
    transition = peek_key_transition_intent(session)
    preserve_key = _backing_intent_preserves_practice_key(transition) if transition else True
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


def _creative_handoff_entry_mode(session: dict[str, Any]) -> str:
    """Authoritative Creative entry mode for Open Backing / return handoff."""
    try:
        from studio_page_state import IMPROV_ENTRY_MODES
    except ImportError:
        IMPROV_ENTRY_MODES = ("Song-Based Improvisation", "Style Jam Mode", "Jam Session Generator")  # type: ignore[misc,assignment]
    live = str(
        session.get("improv_entry_mode") or session.get("creative_improv_entry_mode") or ""
    ).strip()
    # Live Entry & Jam submode is the user selection. Leftover Style Jam blob must
    # not own a Jam Generator launch (or the reverse). Leftover SBI radio is ignored
    # here so generated Style Jam still owns Backing.
    if live in ("Style Jam Mode", "Jam Session Generator"):
        return live
    try:
        from session_widget_safe import PENDING_IMPROV_ENTRY_MODE_KEY

        pending = str(session.get(PENDING_IMPROV_ENTRY_MODE_KEY) or "").strip()
        if pending in ("Style Jam Mode", "Jam Session Generator"):
            return pending
    except ImportError:
        pending = str(session.get("_pending_improv_entry_mode") or "").strip()
        if pending in ("Style Jam Mode", "Jam Session Generator"):
            return pending
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
    if live in IMPROV_ENTRY_MODES:
        return live
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

        handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
        entry = _creative_handoff_entry_mode(session)
        if handoff == "mission":
            return activate_mission_ownership(session, st_like=st_like)
        if handoff == "song_improv":
            return activate_sbi_ownership(session, st_like=st_like)
        if handoff == "entry_jam":
            return activate_entry_jam_ownership(session, st_like=st_like)
        if handoff == "custom_progression":
            return activate_custom_ownership(session, st_like=st_like)

        # Live Creative entry wins over a sealed Mission/Jam ctx. Opening SBI
        # Backing after a prior Mission visit must not resurrect Mission.
        if entry == "Song-Based Improvisation":
            session.pop("improv_mission_backing_handoff", None)
            try:
                from studio_page_state import resolve_improv_song_source

                source = resolve_improv_song_source(session)
            except ImportError:
                source = "Active song"
            if source == "Custom progression":
                # SBI Custom Backing uses song_improv + LAST_CUSTOM preview — do not
                # promote Custom to Global Active Source (H5).
                return activate_sbi_ownership(session, st_like=st_like)
            return activate_sbi_ownership(session, st_like=st_like)
        if entry in ("Style Jam Mode", "Jam Session Generator"):
            session.pop("improv_mission_backing_handoff", None)
            return activate_entry_jam_ownership(session, st_like=st_like)

        if session.get("improv_mission_backing_handoff"):
            session.pop("improv_mission_backing_handoff", None)
            return activate_mission_ownership(session, st_like=st_like)

        # Specialized Mission handoff may already have cleared the one-shot flag;
        # prefer existing mission context / pending / active mission_jam owner.
        try:
            ctx = get_backing_context(session)
            if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
                return activate_mission_ownership(session, st_like=st_like)
        except Exception:
            pass
        try:
            from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

            pending = peek_pending_backing_workflow_handoff(session) or {}
            if str(pending.get("backing_source") or "").strip() == "mission":
                return activate_mission_ownership(session, st_like=st_like)
        except ImportError:
            pass
        try:
            from music_workflow_state_store import get_active_workflow_pointer

            ptr = get_active_workflow_pointer(session)
            if ptr and str(ptr.workflow_owner or "") == "mission_jam":
                return activate_mission_ownership(session, st_like=st_like)
        except ImportError:
            pass
        try:
            from creative_session_state import get_creative_session

            sess = get_creative_session(session)
            if sess is not None and str(getattr(sess, "tool_type", "") or "") == "mission":
                return activate_mission_ownership(session, st_like=st_like)
        except ImportError:
            pass

        # Jam / Style Jam handoff mirrors Mission: prefer sealed ctx + workflow owner
        # over stale Song-Based Improvisation widget residue.
        try:
            ctx = get_backing_context(session)
            if ctx is not None and str(getattr(ctx, "source", "") or "") == "entry_jam":
                return activate_entry_jam_ownership(session, st_like=st_like)
        except Exception:
            pass
        try:
            from music_workflow_pending_backing_handoff import peek_pending_backing_workflow_handoff

            pending = peek_pending_backing_workflow_handoff(session) or {}
            pending_src = str(pending.get("backing_source") or "").strip()
            if pending_src in {"entry_jam", "jam", "style_jam", "jam_session_generator"}:
                return activate_entry_jam_ownership(session, st_like=st_like)
        except ImportError:
            pass
        try:
            from music_workflow_state_store import get_active_workflow_pointer

            ptr = get_active_workflow_pointer(session)
            if ptr and str(ptr.workflow_owner or "") in {"jam_session_generator", "style_jam"}:
                return activate_entry_jam_ownership(session, st_like=st_like)
        except ImportError:
            pass
        try:
            from creative_session_state import get_creative_session

            sess = get_creative_session(session)
            if sess is not None and str(getattr(sess, "tool_type", "") or "") in {
                "jam_session_generator",
                "entry_style_jam",
            }:
                return activate_entry_jam_ownership(session, st_like=st_like)
        except ImportError:
            pass

        return activate_entry_jam_ownership(session, st_like=st_like)
    except ImportError:
        pass
    try:
        from backing_context import open_backing_from_creative

        return open_backing_from_creative(session, source="entry_jam", st_like=st_like)
    except ImportError:
        return None


BACKING_GENERIC_CATALOG_ENTRY_KEY = "_backing_generic_catalog_entry"
BACKING_ENTRY_CLASS_KEY = "_backing_entry_class"
BACKING_ENTRY_GENERIC_CATALOG = "generic_catalog_navigation"
BACKING_ENTRY_SPECIALIZED_HANDOFF = "specialized_handoff"
SPECIALIZED_BACKING_SOURCES = frozenset(
    {
        "entry_jam",
        "song_improv",
        "mission",
        "custom_progression",
    }
)
LAST_SURVIVING_BACKING_SOURCES = frozenset(SPECIALIZED_BACKING_SOURCES | {"regular_song"})


def explicit_specialized_backing_handoff_pending(session: dict[str, Any]) -> bool:
    """Creative/Mission/Jam/SBI → Backing handoff in flight (not ordinary top-level Backing)."""
    if str(session.get(BACKING_ENTRY_CLASS_KEY) or "").strip() == BACKING_ENTRY_SPECIALIZED_HANDOFF:
        return True
    try:
        from music_workflow_pending_backing_handoff import PENDING_BACKING_WORKFLOW_KEY

        pending = session.get(PENDING_BACKING_WORKFLOW_KEY)
        if isinstance(pending, dict) and str(pending.get("backing_source") or "").strip():
            return True
    except ImportError:
        pass
    if session.get("improv_mission_backing_handoff"):
        return True
    return False


def _selected_catalog_pick_key(session: dict[str, Any]) -> str:
    sel = session.get("selected_song")
    if not isinstance(sel, dict):
        return ""
    return str(sel.get("pick_key") or "").strip()


def _visible_song_title(session: dict[str, Any]) -> str:
    sel = session.get("selected_song")
    if isinstance(sel, dict):
        title = str(sel.get("title") or sel.get("name") or "").strip()
        if title:
            return title
    title = str(session.get("song") or session.get("active_song_title") or "").strip()
    if title:
        return title
    try:
        from active_song_state import canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            return str(ctx.get("title") or ctx.get("song") or "").strip()
    except ImportError:
        pass
    return ""


def _pick_label_for_title_compare(pick: str) -> str:
    raw = str(pick or "").strip()
    if "::" in raw:
        raw = raw.split("::", 1)[-1]
    if "|" in raw:
        raw = raw.split("|", 1)[0]
    return raw.strip().lower()


def _fold_title_for_pick_compare(value: str) -> str:
    raw = str(value or "").lower()
    out = []
    prev_space = False
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        elif not prev_space:
            out.append(" ")
            prev_space = True
    return "".join(out).strip()


def _title_conflicts_with_pick(title: str, pick: str) -> bool:
    label = _fold_title_for_pick_compare(_pick_label_for_title_compare(pick))
    text = _fold_title_for_pick_compare(title)
    if not label or not text or label in {"pick", "active"}:
        return False
    if label in text or text in label:
        return False
    label_tokens = {tok for tok in label.split() if tok}
    text_tokens = {tok for tok in text.split() if tok}
    if label_tokens and label_tokens <= text_tokens:
        return False
    if len(label_tokens & text_tokens) >= 2:
        return False
    return True


def _recover_pick_from_visible_title(session: dict[str, Any]) -> str:
    title = _visible_song_title(session)
    if not title:
        return ""
    sel = session.get("selected_song")
    blob = dict(sel) if isinstance(sel, dict) else {}
    blob.setdefault("title", title)
    try:
        from songs.music_source import _catalog_picker_from_session
        from songs.state import _recover_pick_key_by_title

        catalog = _catalog_picker_from_session(session)
        if isinstance(catalog, dict) and catalog:
            recovered = _recover_pick_key_by_title(blob, catalog)
            if recovered:
                return str(recovered).strip()
    except ImportError:
        pass
    try:
        from active_song_state import ACTIVE_SONG_STATE_KEY, canonical_active_song_context

        ctx = canonical_active_song_context(session)
        if isinstance(ctx, dict):
            pk = str(ctx.get("pick_key") or "").strip()
            if pk and not _title_conflicts_with_pick(title, pk):
                return pk
        meta = session.get(ACTIVE_SONG_STATE_KEY)
        if isinstance(meta, dict):
            pk = str(meta.get("pick_key") or "").strip()
            if pk and not _title_conflicts_with_pick(title, pk):
                return pk
    except ImportError:
        meta = session.get("active_song_state")
        if isinstance(meta, dict):
            pk = str(meta.get("pick_key") or "").strip()
            if pk and not _title_conflicts_with_pick(title, pk):
                return pk
    return ""


def _authoritative_catalog_pick_for_nav(session: dict[str, Any]) -> str:
    """Catalog pick for the song the sidebar is showing (not a lagged pick key)."""
    title = _visible_song_title(session)
    recovered = _recover_pick_from_visible_title(session)
    if recovered and not _title_conflicts_with_pick(title, recovered):
        return recovered
    sel_pick = _selected_catalog_pick_key(session)
    if sel_pick and not _title_conflicts_with_pick(title, sel_pick):
        return sel_pick
    return ""


def _catalog_picks_conflict(session: dict[str, Any], left: str, right: str) -> bool:
    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        return False
    if a in {"pick", "active"} or b in {"pick", "active"}:
        return False
    try:
        from songs.music_source import _pick_keys_match

        return not _pick_keys_match(a, b, session_state=session)
    except ImportError:
        return a != b


def _align_live_catalog_pick_to_selected_song(session: dict[str, Any]) -> None:
    """Sidebar/selected song wins when catalog pick hydrator lagged (E4 split-brain)."""
    visible = _authoritative_catalog_pick_for_nav(session)
    if visible:
        live = str(session.get("active_catalog_pick_key") or "").strip()
        if not live or _catalog_picks_conflict(session, visible, live) or _title_conflicts_with_pick(
            _visible_song_title(session), live
        ):
            session["active_catalog_pick_key"] = visible
        return
    sel_pick = _selected_catalog_pick_key(session)
    if not sel_pick or sel_pick.lower().startswith("custom"):
        return
    live = str(session.get("active_catalog_pick_key") or "").strip()
    if not live or not _catalog_picks_conflict(session, sel_pick, live):
        return
    session["active_catalog_pick_key"] = sel_pick


def _backing_ctx_bound_conflicts_with_live_source(session: dict[str, Any], ctx: Any) -> bool:
    """True when sealed ctx is bound to a different catalog/custom pick than live."""
    bound = str(getattr(ctx, "bound_pick_key", "") or "").strip()
    if not bound:
        return False
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        is_custom = bool(
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        )
    except ImportError:
        is_custom = False
    if is_custom:
        return not bound.lower().startswith("custom")
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    if not pick:
        return False
    try:
        from songs.music_source import _pick_keys_match

        return not _pick_keys_match(bound, pick, session_state=session)
    except ImportError:
        return bound != pick


def last_valid_backing_session_survives_ordinary_nav(session: dict[str, Any]) -> bool:
    """True when Upload/Multitrack/Practice/etc. must restore the last Backing session.

    Ordinary top-level navigation must not destroy Mission / Style Jam / Jam Generator /
    Regular Song backing unless that session was intentionally invalidated.

    Restore is CONDITIONAL on the active base source (catalog/custom identity):
    same active source → restore; different active source → ineligible.
    """
    try:
        from backing_context import get_backing_context, is_backing_context_valid
    except ImportError:
        return False
    ctx = get_backing_context(session)
    if ctx is None:
        return False
    src = str(getattr(ctx, "source", "") or "").strip()
    if src not in LAST_SURVIVING_BACKING_SOURCES:
        return False
    if not is_backing_context_valid(session, ctx):
        return False
    # Split-brain: sidebar selected_song already moved (Country Roads) while
    # active_catalog_pick_key / ctx still Love Story — do not restore.
    sel_pick = _authoritative_catalog_pick_for_nav(session) or _selected_catalog_pick_key(session)
    live_pick = str(session.get("active_catalog_pick_key") or "").strip()
    bound = str(getattr(ctx, "bound_pick_key", "") or "").strip()
    visible_title = _visible_song_title(session)
    if (
        _catalog_picks_conflict(session, sel_pick, live_pick)
        or _catalog_picks_conflict(session, sel_pick, bound)
        or _title_conflicts_with_pick(visible_title, bound)
        or _title_conflicts_with_pick(visible_title, live_pick)
    ):
        return False
    # Regular catalog sessions can lose bound_pick_key after song hops; still refuse
    # when sealed song_title disagrees with the sidebar active song (Capo/PK drift).
    # Specialized Mission/Jam titles are not catalog titles — skip this gate for them.
    if src == "regular_song":
        ctx_title = str(getattr(ctx, "song_title", "") or "").strip()
        if _title_conflicts_with_pick(visible_title, ctx_title):
            return False
    # Active-source epoch gate: Clocks Mission must not restore after Love Story pick.
    if not backing_restore_eligible(session):
        # Legacy bags without an anchor: stamp from *live* active source only when
        # ctx is not bound to a conflicting catalog/custom pick (stale Say jam
        # must not become eligible just because we stamped the live custom id).
        anchor = backing_restore_anchor(session)
        if not anchor:
            if _backing_ctx_bound_conflicts_with_live_source(session, ctx):
                return False
            try:
                current = resolve_active_source_identity_for_restore(session)
                if current:
                    stamp_backing_restore_anchor(session, anchor=current)
                else:
                    stamp_backing_restore_anchor(session)
            except Exception:
                stamp_backing_restore_anchor(session)
            if not backing_restore_eligible(session):
                return False
        else:
            return False
    try:
        from songs.music_source import (
            cpl_session_is_active,
            custom_progression_is_active,
            is_custom_progression,
        )

        # Custom-in-session must not destroy a sealed Jam/Mission/SBI session
        # (Jam generated on a custom practice source still restores). Regular
        # catalog Backing is ineligible while custom owns practice.
        if src == "regular_song" and (
            cpl_session_is_active(session)
            or is_custom_progression(session)
            or custom_progression_is_active(session)
        ):
            return False
    except ImportError:
        pass
    # Explicit Songs Custom/Catalog ownership outranks a sealed Mission/SBI overlay
    # that was never opened from this active source (H9 Custom + stale Mission).
    try:
        from music_source_ownership import _raw_practice_owner

        raw = _raw_practice_owner(session)
        if raw == "custom" and src in {"mission", "song_improv", "entry_jam"}:
            return False
        if session.get("_backing_released_specialized_context") and src in {
            "mission",
            "song_improv",
            "entry_jam",
        }:
            return False
    except ImportError:
        pass
    return True


def restore_last_valid_backing_on_ordinary_nav(session: dict[str, Any], *, st_like: Any | None = None) -> bool:
    """Re-apply the last valid Backing owner after visiting an ordinary page."""
    if not last_valid_backing_session_survives_ordinary_nav(session):
        return False
    try:
        from backing_context import (
            BACKING_PREF_CREATIVE,
            get_backing_context,
            set_backing_source_preference,
            sync_live_keys_from_backing_context,
        )
    except ImportError:
        return False
    ctx = get_backing_context(session)
    src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    if src == "regular_song":
        try:
            from backing_context import restore_regular_song_backing
            from songs.practice_key_state import (
                get_practice_concert_key,
                resolve_practice_source_pick,
                set_practice_concert_key,
            )

            pick = str(
                resolve_practice_source_pick(session)
                or session.get("active_catalog_pick_key")
                or getattr(ctx, "bound_pick_key", "")
                or ""
            ).strip()
            sticky_before = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
            live_before = str(session.get("display_key") or session.get("concert_key") or "").strip()
            sealed = str(getattr(ctx, "concert_key", "") or getattr(ctx, "display_key", "") or "").strip()
            # Prefer live sidebar when it already diverged from the sealed Backing ctx
            # (user changed Practice Key after the last Backing visit).
            if live_before and sealed and live_before != sealed:
                keep_pk = live_before
            else:
                keep_pk = sticky_before or live_before
            restore_regular_song_backing(session, st_like=st_like)
            if keep_pk and pick:
                set_practice_concert_key(session, keep_pk, pick_key=pick)
                session["display_key"] = keep_pk
                session["concert_key"] = keep_pk
                session["_pending_display_key"] = keep_pk
                try:
                    from backing_context import get_backing_context, set_backing_context

                    restored = get_backing_context(session)
                    if restored is not None and str(getattr(restored, "source", "") or "") == "regular_song":
                        restored.concert_key = keep_pk
                        restored.display_key = keep_pk
                        set_backing_context(session, restored)
                except Exception:
                    pass
                # Persist sticky Practice Key so browser refresh cannot revive Original Key.
                try:
                    if st_like is not None:
                        from songs.state import persist_music_local_state

                        persist_music_local_state(st_like)
                except Exception:
                    pass
                try:
                    if st_like is not None:
                        from music_persistent_state import force_save_music_state

                        force_save_music_state(st_like, reason="backing_restore_keep_practice_key")
                except Exception:
                    pass
        except Exception:
            pass
        return True
    if src in SPECIALIZED_BACKING_SOURCES:
        # Re-seal preference + live keys only. Do NOT call activate_*_ownership /
        # open_backing_from_creative here — that rebuilds from improv state and
        # wipes already-valid sealed Mission/Jam envelopes (E1/E3 restore).
        set_backing_source_preference(session, BACKING_PREF_CREATIVE)
        try:
            sync_live_keys_from_backing_context(session, st_like=st_like)
        except Exception:
            pass
        if src == "mission":
            try:
                from mission_return_destination import (
                    rehydrate_mission_return_destination_from_backing_context,
                )

                rehydrate_mission_return_destination_from_backing_context(session)
            except ImportError:
                pass
    return True


def mark_specialized_backing_handoff_entry(session: dict[str, Any]) -> None:
    """Seal explicit specialized Backing entry (consumed once on hydrate)."""
    session[BACKING_ENTRY_CLASS_KEY] = BACKING_ENTRY_SPECIALIZED_HANDOFF
    session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None)
    # New explicit Creative → Backing handoff outranks a prior release latch.
    session.pop("_backing_released_specialized_context", None)
    stamp_backing_restore_anchor(session)
    set_backing_open_intent(session, BACKING_INTENT_FROM_CREATIVE)


def mark_generic_catalog_backing_entry(session: dict[str, Any]) -> None:
    """User opened Backing from a top-level page — not an in-flight Creative handoff."""
    try:
        from jam_generator_live_runtime_trace import append_jam_backing_handoff_trace

        append_jam_backing_handoff_trace(session, "mark_generic_catalog_backing_entry")
    except ImportError:
        pass
    session[BACKING_ENTRY_CLASS_KEY] = BACKING_ENTRY_GENERIC_CATALOG
    session[BACKING_GENERIC_CATALOG_ENTRY_KEY] = True
    set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)


def release_specialized_backing_for_generic_navigation(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Drop stale mission/jam backing ownership when entering Backing generically."""
    try:
        from jam_generator_live_runtime_trace import append_jam_backing_handoff_trace

        append_jam_backing_handoff_trace(session, "release_specialized_backing_for_generic_navigation")
    except ImportError:
        pass
    session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None)
    try:
        from backing_context import (
            BACKING_PREF_CATALOG,
            clear_backing_context,
            get_backing_context,
            set_backing_source_preference,
        )

        ctx = get_backing_context(session)
        src = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
        if src in {"entry_jam", "song_improv", "mission", "custom_progression"}:
            set_backing_source_preference(session, BACKING_PREF_CATALOG)
            # Stale specialized ctx must not survive a restore miss (song change → Catalog).
            clear_backing_context(session)
    except ImportError:
        pass
    session["_backing_released_specialized_context"] = True
    try:
        from backing_track_state import reset_backing_playback_scope_to_full_song

        reset_backing_playback_scope_to_full_song(session, source="generic_catalog_backing_entry")
    except ImportError:
        pass
    # Seal live Practice Key onto the active catalog pick before ownership reconcile
    # so opening ordinary Backing cannot treat a missing sticky slot as Original Key.
    try:
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_source_pick,
            set_practice_concert_key,
        )

        pick = str(
            resolve_practice_source_pick(session)
            or session.get("active_catalog_pick_key")
            or ""
        ).strip()
        live_dk = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if pick and live_dk and not pick.startswith("custom::"):
            sticky = str(get_practice_concert_key(session, pick) or "").strip()
            if not sticky:
                set_practice_concert_key(session, live_dk, pick_key=pick)
    except ImportError:
        pass
    try:
        from music_source_ownership import reconcile_source_ownership

        reconcile_source_ownership(session, st_like=st_like, reason="generic_backing_entry")
    except ImportError:
        pass


def release_mission_creative_page_ownership(
    session: dict[str, Any],
    *,
    reason: str = "leave_missions",
    force_entry_jam_tab: bool = False,
) -> None:
    """Explicit Entry & Jam / SBI selection outranks sealed Mission Creative ownership (H5).

    Does not change Global Active Source. Clears Mission handoff / sealed Mission
    backing so the next Open in Backing Studio can own song_improv.
    """
    _ = reason
    session.pop("improv_mission_backing_handoff", None)
    session.pop("_backing_explicit_handoff_source", None)
    try:
        from music_workflow_pending_backing_handoff import PENDING_BACKING_WORKFLOW_KEY

        session.pop(PENDING_BACKING_WORKFLOW_KEY, None)
    except ImportError:
        pass
    try:
        from backing_context import clear_backing_context, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and str(getattr(ctx, "source", "") or "") == "mission":
            clear_backing_context(session)
    except ImportError:
        pass
    session["_backing_released_specialized_context"] = True
    try:
        from creative_session_state import get_creative_session, set_creative_session

        sess = get_creative_session(session)
        if sess is not None and str(getattr(sess, "tool_type", "") or "") == "mission":
            entry = str(session.get("improv_entry_mode") or "Song-Based Improvisation").strip()
            sess.tool_type = (
                "song_based_improvisation"
                if entry == "Song-Based Improvisation"
                else "entry_style_jam"
                if entry == "Style Jam Mode"
                else "jam_session_generator"
                if entry == "Jam Session Generator"
                else "song_based_improvisation"
            )
            sess.entry_mode = entry or "Song-Based Improvisation"
            set_creative_session(session, sess)
    except ImportError:
        pass
    if force_entry_jam_tab or reason in {"entry_mode_song_based", "test"}:
        try:
            from studio_page_state import CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY

            session["improv_intelligence_tab"] = "Entry & Jam"
            session[CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY] = "Entry & Jam"
        except ImportError:
            session["improv_intelligence_tab"] = "Entry & Jam"
            session["creative_improv_intelligence_tab"] = "Entry & Jam"


def initialize_active_source_backing_after_restore_miss(
    session: dict[str, Any], *, st_like: Any | None = None
) -> None:
    """After same-source restore fails, initialize regular Backing for the live active source.

    Song-change path (E2/E4/E5): Love Story Mission → Country Roads → top-level Backing must
    open Catalog Country Roads with that song's Practice Key (D), not preserve Love Story C
    and not keep a stale specialized session.

    Same Global Active Source (ordinary Songs/Practice → Backing with no prior session):
    opening Backing is NOT a new song activation — keep the current sticky Practice Key.
    """
    session["_backing_released_specialized_context"] = True
    _align_live_catalog_pick_to_selected_song(session)
    pick = str(session.get("active_catalog_pick_key") or _selected_catalog_pick_key(session) or "").strip()
    prev_pick = ""
    try:
        from songs.music_source import _LAST_ACTIVE_PICK_KEY

        prev_pick = str(session.get(_LAST_ACTIVE_PICK_KEY) or "").strip()
    except ImportError:
        prev_pick = ""
    # Same pick (or no prior pick recorded) → preserve Practice Key for this activation.
    same_active_source = bool(pick) and (not prev_pick or prev_pick == pick)
    if not same_active_source:
        try:
            from music_workflow_song_practice import reconcile_practice_key_after_active_source_change

            sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
            reconcile_practice_key_after_active_source_change(
                session,
                pick_key=pick,
                original_key=str((sel or {}).get("key") or ""),
                previous_pick_key=prev_pick,
                source="initialize_active_source_backing",
            )
        except ImportError:
            pass
        # Reset to the newly active source original/practice owner — do not preserve prior song key.
        set_key_transition_intent(session, BACKING_INTENT_SWITCH_CATALOG)
    else:
        # Ordinary Backing open for the current Global Active Source.
        try:
            from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

            live_dk = str(session.get("display_key") or session.get("concert_key") or "").strip()
            sticky = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
            if not sticky and live_dk and pick:
                set_practice_concert_key(session, live_dk, pick_key=pick)
            elif sticky:
                session["display_key"] = sticky
                session["concert_key"] = sticky
                session["_pending_display_key"] = sticky
        except ImportError:
            pass
        set_key_transition_intent(session, BACKING_INTENT_FROM_SONG_TO_BACKING)
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
            set_key_transition_intent(session, BACKING_INTENT_SWITCH_CUSTOM)
    except ImportError:
        pass
    try:
        open_backing_for_practice_source(session, st_like=st_like)
    finally:
        consume_key_transition_intent(session)
    stamp_backing_restore_anchor(session)


def trace_backing_hydrate_phase(session: dict[str, Any], phase: str, **extra: Any) -> None:
    """Sequence-numbered trace for early-hydrate vs song-pick commit ordering (E4)."""
    seq = int(session.get("_backing_hydrate_trace_seq") or 0) + 1
    session["_backing_hydrate_trace_seq"] = seq
    ctx = get_backing_context(session)
    ctx_source = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    ctx_title = str(getattr(ctx, "song_title", "") or "").strip() if ctx is not None else ""
    ctx_bound = str(getattr(ctx, "bound_pick_key", "") or "").strip() if ctx is not None else ""
    row: dict[str, Any] = {
        "seq": seq,
        "phase": phase,
        "route": str(session.get("studio_page") or ""),
        "visible_title": _visible_song_title(session),
        "selected_pick": _selected_catalog_pick_key(session),
        "active_pick": str(session.get("active_catalog_pick_key") or ""),
        "identity": resolve_active_source_identity_for_restore(session),
        "ctx_source": ctx_source,
        "ctx_title": ctx_title,
        "ctx_bound": ctx_bound,
        "anchor": backing_restore_anchor(session),
        "restore_eligible": backing_restore_eligible(session),
        "intent": str(session.get(BACKING_OPEN_INTENT_KEY) or ""),
        "display_key": str(session.get("display_key") or session.get("concert_key") or ""),
    }
    if extra:
        row.update(extra)
    trace = session.get("_backing_hydrate_trace")
    if not isinstance(trace, list):
        trace = []
    trace.append(row)
    if len(trace) > 48:
        trace = trace[-48:]
    session["_backing_hydrate_trace"] = trace


def commit_active_catalog_source_before_backing_hydrate(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
    song_picker_catalog: dict | None = None,
    song_library: dict | None = None,
    invalidate_backing: Any | None = None,
) -> bool:
    """Commit pending/new catalog source before early Backing hydrate.

    Sidebar Active Song can already show Country Roads while ``catalog_before_creative``
    and stale BackingContext still reference Love Story. This applies pending picks,
    aligns the live catalog pick with the visible song, and invalidates stale restore
    state before ``hydrate_backing_source_for_page`` runs.
    """
    trace_backing_hydrate_phase(session, "01_pre_commit_entry")
    if song_picker_catalog and st_like is not None:
        try:
            from songs.state import apply_pending_catalog_pick_before_widgets

            apply_pending_catalog_pick_before_widgets(
                st_like,
                song_picker_catalog,
                song_library=song_library,
                invalidate_backing=invalidate_backing or (lambda _st: None),
            )
        except ImportError:
            pass

    authoritative = _authoritative_catalog_pick_for_nav(session) or _selected_catalog_pick_key(session)
    live = str(session.get("active_catalog_pick_key") or "").strip()
    if authoritative and (
        not live or _catalog_picks_conflict(session, authoritative, live)
    ):
        session["active_catalog_pick_key"] = authoritative
        if isinstance(song_picker_catalog, dict) and song_picker_catalog:
            try:
                from songs.state import sync_catalog_pick_identity

                sync_catalog_pick_identity(session, authoritative, song_picker_catalog)
            except ImportError:
                pass

    ctx = get_backing_context(session)
    auth_pick = str(session.get("active_catalog_pick_key") or authoritative or "").strip()
    if ctx is not None and auth_pick:
        bound = str(getattr(ctx, "bound_pick_key", "") or getattr(ctx, "active_song_id", "") or "").strip()
        title = _visible_song_title(session)
        stale_ctx = bool(
            bound
            and (
                _catalog_picks_conflict(session, auth_pick, bound)
                or _title_conflicts_with_pick(title, bound)
            )
        )
        if stale_ctx:
            prev_id = backing_restore_anchor(session) or (f"pk::{bound}" if bound else "")
            new_id = resolve_active_source_identity_for_restore(session)
            prev_pick = bound
            invalidate_backing_restore_for_active_source_change(
                session,
                previous_identity=str(prev_id or ""),
                new_identity=str(new_id or ""),
                reason="pre_hydrate_source_commit",
            )
            try:
                from music_workflow_song_practice import reconcile_practice_key_after_active_source_change

                sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
                reconcile_practice_key_after_active_source_change(
                    session,
                    pick_key=auth_pick,
                    original_key=str((sel or {}).get("key") or ""),
                    previous_pick_key=prev_pick,
                    source="pre_hydrate_source_commit",
                )
            except ImportError:
                pass
            if st_like is not None and invalidate_backing is not None:
                try:
                    from songs.music_source import note_active_source_change

                    note_active_source_change(st_like, invalidate_backing=invalidate_backing)
                except ImportError:
                    pass

    trace_backing_hydrate_phase(session, "02_post_commit")
    return True


def hydrate_backing_source_for_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply backing navigation intent and preserve last Backing Studio source (Cases B + refresh)."""
    # Explicit "Use catalog song backing" — next hydrates must seal Catalog ownership.
    # Backing runs hydrate twice per paint; keep the force for 2 consumes so the
    # second pass cannot restore_last a stale custom_progression ctx (H9).
    _force_n = int(session.get("_force_catalog_backing_after_use_catalog") or 0)
    if _force_n > 0:
        try:
            from pathlib import Path

            Path("scripts/evidence-creative-backing/h9-force-hydrate.txt").write_text(
                f"force_n={_force_n}\n"
                f"song={session.get('song')!r}\n"
                f"pick={session.get('active_catalog_pick_key')!r}\n"
                f"source={session.get('active_music_source')!r}\n"
                f"user_catalog={session.get('_user_chose_catalog_music_source')!r}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        session["_force_catalog_backing_after_use_catalog"] = _force_n - 1
        if session["_force_catalog_backing_after_use_catalog"] <= 0:
            session.pop("_force_catalog_backing_after_use_catalog", None)
        try:
            from backing_context import BACKING_PREF_CATALOG, restore_regular_song_backing, set_backing_source_preference

            set_backing_source_preference(session, BACKING_PREF_CATALOG)
            restore_regular_song_backing(session, st_like=st_like)
            set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
            session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None)
            session.pop(BACKING_ENTRY_CLASS_KEY, None)
            return
        except ImportError:
            pass
    trace_backing_hydrate_phase(session, "03_hydrate_entry")
    try:
        import json
        from pathlib import Path

        _dbg = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing" / "h2-hydrate-trace.jsonl"
        _dbg.parent.mkdir(parents=True, exist_ok=True)
        with _dbg.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "phase": "entry",
                        "display_key": str(session.get("display_key") or ""),
                        "concert_key": str(session.get("concert_key") or ""),
                        "pick": str(session.get("active_catalog_pick_key") or ""),
                        "sticky": dict(session.get("practice_key_by_source") or {}),
                        "intent": str(session.get("_backing_open_intent") or ""),
                        "generic": bool(session.get("_backing_generic_catalog_entry")),
                        "page": str(session.get("studio_page") or ""),
                    },
                    default=str,
                )
                + "\n"
            )
    except Exception:
        pass
    # Heal: live sidebar Practice Key ahead of sticky store for this catalog pick.
    try:
        from songs.music_source import cpl_session_is_active, is_custom_progression
        from songs.practice_key_state import (
            get_practice_concert_key,
            resolve_practice_source_pick,
            set_practice_concert_key,
        )

        if not (is_custom_progression(session) or cpl_session_is_active(session)):
            pick = str(
                resolve_practice_source_pick(session) or session.get("active_catalog_pick_key") or ""
            ).strip()
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            sticky = str(get_practice_concert_key(session, pick) or "").strip() if pick else ""
            if pick and live and live != sticky and not pick.startswith("custom::"):
                set_practice_concert_key(session, live, pick_key=pick)
    except ImportError:
        pass
    generic_entry = bool(session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None))
    entry_class = str(session.pop(BACKING_ENTRY_CLASS_KEY, "") or "").strip()
    intent = consume_backing_open_intent(session)
    try:
        from jam_generator_live_runtime_trace import append_jam_backing_handoff_trace

        append_jam_backing_handoff_trace(
            session,
            "hydrate_backing_source_for_page",
            generic_entry=generic_entry,
            entry_class=entry_class,
            intent=intent,
        )
    except ImportError:
        pass
    if generic_entry or entry_class == BACKING_ENTRY_GENERIC_CATALOG:
        # Ordinary top-level Backing — clear any stale Creative handoff stamp.
        session.pop("_backing_explicit_handoff_source", None)
        selected_pick_snapshot = (
            _authoritative_catalog_pick_for_nav(session) or _selected_catalog_pick_key(session)
        )
        _align_live_catalog_pick_to_selected_song(session)
        if restore_last_valid_backing_on_ordinary_nav(session, st_like=st_like):
            return
        release_specialized_backing_for_generic_navigation(session, st_like=st_like)
        # Reconcile during release can restore a lagged catalog pick. Re-apply the
        # sidebar-selected song before initializing regular Backing (E4).
        if selected_pick_snapshot:
            live = str(session.get("active_catalog_pick_key") or "").strip()
            if _catalog_picks_conflict(session, selected_pick_snapshot, live) or not live:
                session["active_catalog_pick_key"] = selected_pick_snapshot
        initialize_active_source_backing_after_restore_miss(session, st_like=st_like)
        try:
            import json
            from pathlib import Path

            from backing_context import get_backing_context

            _ctx = get_backing_context(session)
            _dbg = Path(__file__).resolve().parent / "scripts" / "evidence-creative-backing" / "h2-hydrate-trace.jsonl"
            with _dbg.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "phase": "after_generic_init",
                            "display_key": str(session.get("display_key") or ""),
                            "sticky": dict(session.get("practice_key_by_source") or {}),
                            "ctx_key": str(getattr(_ctx, "concert_key", "") or "") if _ctx else "",
                            "ctx_source": str(getattr(_ctx, "source", "") or "") if _ctx else "",
                        },
                        default=str,
                    )
                    + "\n"
                )
        except Exception:
            pass
        return
    elif intent == BACKING_INTENT_FROM_CREATIVE or entry_class == BACKING_ENTRY_SPECIALIZED_HANDOFF:
        open_backing_for_creative_source(session, st_like=st_like)
        try:
            from backing_context import sync_live_keys_from_backing_context

            sync_live_keys_from_backing_context(session, st_like=st_like)
        except ImportError:
            pass
        # Handoff is one-shot. open_backing_from_creative re-marks specialized /
        # from_creative; leave restore_last so the next Backing visit reseals
        # the same session instead of rebuilding.
        set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
        session.pop(BACKING_ENTRY_CLASS_KEY, None)
        session.pop(BACKING_GENERIC_CATALOG_ENTRY_KEY, None)
        return
    if intent == BACKING_INTENT_RESTORE_LAST:
        selected_pick_snapshot = (
            _authoritative_catalog_pick_for_nav(session) or _selected_catalog_pick_key(session)
        )
        _align_live_catalog_pick_to_selected_song(session)
        if restore_last_valid_backing_on_ordinary_nav(session, st_like=st_like):
            return
        # Explicit Creative handoff must not fall through to regular song Backing.
        try:
            from backing_context import get_backing_context, is_backing_context_valid

            ctx = get_backing_context(session)
            handoff = str(session.get("_backing_explicit_handoff_source") or "").strip()
            specialized = {"mission", "song_improv", "entry_jam", "custom_progression"}
            if (
                ctx is not None
                and str(getattr(ctx, "source", "") or "") in specialized
                and is_backing_context_valid(session, ctx)
                and not _ctx_is_stale_creative_for_practice(session, ctx)
            ):
                return
            if handoff in specialized:
                open_backing_for_creative_source(session, st_like=st_like)
                set_backing_open_intent(session, BACKING_INTENT_RESTORE_LAST)
                return
        except ImportError:
            pass
        # Restore intent but session ineligible (song change): initialize for live active source.
        release_specialized_backing_for_generic_navigation(session, st_like=st_like)
        if selected_pick_snapshot:
            live = str(session.get("active_catalog_pick_key") or "").strip()
            if _catalog_picks_conflict(session, selected_pick_snapshot, live) or not live:
                session["active_catalog_pick_key"] = selected_pick_snapshot
        initialize_active_source_backing_after_restore_miss(session, st_like=st_like)
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
    if session.get("_backing_released_specialized_context"):
        session.pop("_backing_released_specialized_context", None)
        return
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
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob
        from music_workflow_legacy_projection import restore_workflow_blob_to_session

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") in {"jam_session_generator", "style_jam"}:
            blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
            if blob is not None and blob.section_map:
                restore_workflow_blob_to_session(session, blob)
                try:
                    from generated_workflow_projection import project_generated_owner_from_active_blob

                    project_generated_owner_from_active_blob(
                        session, writer="return_from_backing_generated"
                    )
                except ImportError:
                    pass
                try:
                    from workflow_key_identity import apply_practice_key_identity_to_session, resolve_active_workflow_key_identity

                    ident = resolve_active_workflow_key_identity(session)
                    if ident is not None:
                        apply_practice_key_identity_to_session(
                            session,
                            ident,
                            source="return_from_backing_generated_blob",
                            widget_safe=widget_safe,
                        )
                except ImportError:
                    pass
    except ImportError:
        pass
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
    if concert and ctx.source not in {"entry_jam"}:
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
            # SBI Custom is preview/handoff only — never promote LAST_CUSTOM to
            # Global Active Source (H5: Songs must still show catalog Shape).
            session["improv_song_source"] = "Custom progression"
            try:
                from studio_page_state import CREATIVE_BACKING_SONG_SOURCE_KEY

                session[CREATIVE_BACKING_SONG_SOURCE_KEY] = "Custom progression"
            except ImportError:
                pass
            try:
                from source_session_state import set_sbi_preview_source

                set_sbi_preview_source(session, "Custom progression")
            except ImportError:
                pass
        else:
            session["improv_song_source"] = "Active song"
            try:
                from source_session_state import set_sbi_preview_source

                set_sbi_preview_source(session, "Active song")
            except ImportError:
                pass
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
                "groove": str(ctx.groove or meta.get("groove") or "Medium"),
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
    try:
        from mission_return_destination import apply_sealed_mission_return_destination

        if apply_sealed_mission_return_destination(session):
            session["improv_intelligence_tab"] = "Missions"
            session["creative_improv_intelligence_tab"] = "Missions"
            if ctx is not None and str(ctx.source or "") == "mission":
                restore_session_widgets_from_backing_context(session, ctx)
            return page
    except ImportError:
        pass
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
        return "✏️ Return to Custom Page"
    if ctx.source == "regular_song":
        return "🎵 Return to Catalog Song"
    return "🎨 Return to Creative Page"


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
    "explicit_specialized_backing_handoff_pending",
    "hydrate_backing_source_for_page",
    "hydrate_picker_source_for_page",
    "hydrate_practice_source_for_page",
    "last_valid_backing_session_survives_ordinary_nav",
    "restore_last_valid_backing_on_ordinary_nav",
    "merge_live_practice_into_creative_session",
    "open_backing_for_practice_source",
    "queue_backing_scope_from_practice_focus",
    "prepare_return_to_backing_source",
    "prepare_return_to_mission_detail",
    "project_return_destination_to_canonical_creative_selectors",
    "rehydrate_creative_from_backing_context",
    "release_mission_creative_page_ownership",
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
