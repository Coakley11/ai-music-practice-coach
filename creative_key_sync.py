"""Creative page concert-key sync — Style Jam / Jam Session → global practice key."""

from __future__ import annotations

import html
from typing import Any

from studio_page_state import CREATIVE_MAJOR_KEY_OPTIONS

IMPROV_STYLE_KEY_TRACKER = "_improv_style_key_tracker"
IMPROV_JAM_KEY_TRACKER = "_improv_jam_key_tracker"
CREATIVE_CONCERT_KEY_SOURCE = "_creative_concert_key_source"
PENDING_CAPO_SHAPE_KEY = "_pending_capo_shape_key"
PENDING_IMPROV_STYLE_KEY = "_pending_improv_style_key"
PENDING_IMPROV_JAM_KEY = "_pending_improv_jam_key"

CREATIVE_MAJOR_JAM_MODES: tuple[str, ...] = ("Style Jam Mode", "Jam Session Generator")

_SIDEBAR_USER_DISPLAY_KEY_SOURCES: frozenset[str] = frozenset(
    {
        "sidebar_on_change",
        "sidebar",
        "display_key_widget",
        "display_key_change",
        "user",
        "user_navigation",
    }
)

# Re-export for UI pickers.
CREATIVE_MAJOR_KEY_OPTIONS = CREATIVE_MAJOR_KEY_OPTIONS


def _key_steps_to_center(key_center: str) -> int:
    from music_theory import normalize_root, semitone_distance, split_chord

    root, _suffix = split_chord(str(key_center or "C"))
    target = normalize_root(root)
    return semitone_distance("C", target)


def creative_entry_concert_key(session: dict[str, Any]) -> str:
    """Selected concert key from Creative entry widgets, if any."""
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return resolve_practice_concert_key_for_song(session, "C", fallback="C")
    except ImportError:
        pass
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        return str(session.get("improv_style_key") or "").strip()
    if entry == "Jam Session Generator":
        return str(session.get("improv_jam_key") or "").strip()
    return ""


def retranspose_generated_sections(
    sections: dict[str, list[str]],
    *,
    from_key: str,
    to_key: str,
) -> dict[str, list[str]]:
    """Transpose Style Jam section dict when the user changes key."""
    if not sections or not from_key or not to_key or from_key == to_key:
        return sections
    from music_theory import transpose_chord

    delta = _key_steps_to_center(to_key) - _key_steps_to_center(from_key)
    if delta == 0:
        return sections
    out: dict[str, list[str]] = {}
    for label, chords in sections.items():
        if isinstance(chords, list):
            out[label] = [transpose_chord(str(c), delta, reference_key=to_key) for c in chords if str(c).strip()]
        else:
            out[label] = chords
    return out


def is_creative_catalog_pick_frozen(session: dict[str, Any]) -> bool:
    """True when Creative jam/style edits must not mutate the active catalog song."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "backing":
        try:
            from backing_workflow_context import workflow_is_generated

            if workflow_is_generated(session):
                return True
        except ImportError:
            pass
    if page != "creative":
        return False
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry in CREATIVE_MAJOR_JAM_MODES:
        return True
    try:
        from creative_session_state import get_creative_session

        sess = get_creative_session(session)
        if sess is not None and sess.tool_type in {"entry_style_jam", "jam_session_generator"}:
            return True
    except ImportError:
        pass
    return False


def guard_creative_catalog_pick_before_edit(session: dict[str, Any], *, writer: str) -> str:
    """Record active catalog pick before a Creative widget edit; pin dropdown aliases."""
    pick = ""
    try:
        from songs.music_source import pin_catalog_pick_aliases, write_creative_catalog_guard_diag

        pick = pin_catalog_pick_aliases(session)
        before = str(session.get("song") or session.get("active_song_title") or pick or "").strip()
        snap = session.get("_catalog_before_creative_state")
        snap_pick = str(snap.get("pick_key") or "").strip() if isinstance(snap, dict) else ""
        write_creative_catalog_guard_diag(
            session,
            catalog_song_before_jam_edit=before or pick,
            catalog_snapshot_before_creative=snap_pick or pick,
        )
    except ImportError:
        pick = str(session.get("active_catalog_pick_key") or "").strip()
    return pick


def verify_creative_catalog_pick_after_edit(
    session: dict[str, Any],
    *,
    before_pick: str,
    writer: str,
) -> None:
    """Restore catalog pick if a Creative edit incorrectly mutated it."""
    try:
        from songs.music_source import (
            restore_frozen_catalog_pick_if_mutated,
            write_creative_catalog_guard_diag,
        )

        restore_frozen_catalog_pick_if_mutated(session, before_pick, writer=writer)
        after = str(session.get("song") or session.get("active_song_title") or "").strip()
        snap = session.get("_catalog_before_creative_state")
        snap_pick = str(snap.get("pick_key") or "").strip() if isinstance(snap, dict) else ""
        write_creative_catalog_guard_diag(
            session,
            catalog_song_after_jam_edit=after or str(session.get("active_catalog_pick_key") or "").strip(),
            catalog_snapshot_after_creative=snap_pick,
        )
    except ImportError:
        pass


def apply_creative_concert_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    st_like: Any | None = None,
    source: str = "creative_style_jam",
) -> None:
    """Push Creative-selected key into canonical practice concert / display key state."""
    key = str(concert_key or "").strip()
    if not key:
        return
    try:
        from creative_key_sync import is_creative_major_jam_active

        if not is_creative_major_jam_active(session):
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                key = resolve_practice_concert_key_for_song(session, key, fallback=key)
    except ImportError:
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

            if is_fixed_practice_key_mode(session):
                key = resolve_practice_concert_key_for_song(session, key, fallback=key)
        except ImportError:
            pass
    session[CREATIVE_CONCERT_KEY_SOURCE] = source
    session["concert_key"] = to_major_key_preserve_spelling(key)
    key = session["concert_key"]
    if st_like is None:
        st_like = type("_St", (), {"session_state": session})()
    try:
        from songs.key_state import request_display_key

        request_display_key(st_like, key)
    except ImportError:
        session["_pending_display_key"] = key
    if not is_creative_catalog_pick_frozen(session):
        try:
            from active_song_state import mark_active_song_local_edit

            mark_active_song_local_edit(session)
        except ImportError:
            pass
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        invalidate_backing_cache(st_like)
        session[BACKING_NEEDS_REGEN] = True
    except ImportError:
        pass
    if is_creative_major_jam_active(session):
        sanitize_creative_major_chart_keys(session, st_like=st_like)


def flush_pending_creative_major_keys(session: dict[str, Any]) -> None:
    """Apply queued Creative chart-key values before their widgets render."""
    try:
        from guitar_capo import CAPO_SHAPE_KEY
    except ImportError:
        CAPO_SHAPE_KEY = "guitar_capo_shape_key"

    pending_shape = session.pop(PENDING_CAPO_SHAPE_KEY, None)
    if pending_shape is not None:
        session[CAPO_SHAPE_KEY] = str(pending_shape).strip()

    pending_style = session.pop(PENDING_IMPROV_STYLE_KEY, None)
    if pending_style is not None:
        session["improv_style_key"] = str(pending_style).strip()

    pending_jam = session.pop(PENDING_IMPROV_JAM_KEY, None)
    if pending_jam is not None:
        session["improv_jam_key"] = str(pending_jam).strip()


def invalidate_creative_backing_context(session: dict[str, Any]) -> None:
    """Refresh Creative backing handoff after key/BPM/groove changes."""
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            get_backing_context,
            refresh_backing_context_from_session,
            set_backing_context,
        )

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source in {
            "entry_jam",
            "mission",
            "custom_progression",
            "song_improv",
        }:
            refreshed = refresh_backing_context_from_session(session)
            if refreshed is not None:
                set_backing_context(session, refreshed)
                session[PENDING_BACKING_CONTEXT_APPLY] = True
                session.pop("_backing_creative_chart_sections", None)
                try:
                    from creative_session_state import sync_creative_session_from_session

                    sync_creative_session_from_session(session)
                except ImportError:
                    pass
                return
    except ImportError:
        pass
    session.pop("_pending_backing_context_apply", None)
    session.pop("_backing_creative_chart_sections", None)


def sync_creative_key_change(
    session: dict[str, Any],
    new_key: str,
    *,
    previous_key: str = "",
    st_like: Any | None = None,
) -> None:
    """Retranspose generated chords and sync global concert key on key picker change."""
    prev = str(previous_key or session.get(IMPROV_STYLE_KEY_TRACKER) or "").strip()
    new = str(new_key or "").strip()
    if not new:
        return
    gen = session.get("improv_generated_sections")
    if isinstance(gen, dict) and gen and prev and prev != new:
        session["improv_generated_sections"] = retranspose_generated_sections(
            gen,
            from_key=prev,
            to_key=new,
        )
    apply_creative_concert_key(session, new, st_like=st_like)
    session[IMPROV_STYLE_KEY_TRACKER] = new
    meta = dict(session.get("improv_style_meta") or {})
    meta["key"] = new
    session["improv_style_meta"] = meta
    invalidate_creative_backing_context(session)


def sync_style_jam_legacy_after_authoritative_key(
    session: dict[str, Any],
    new_key: str,
    *,
    st_like: Any | None = None,
) -> None:
    """After update_active_practice_key — sync trackers only; do not re-transpose sections."""
    new = str(new_key or "").strip()
    if not new:
        return
    apply_creative_concert_key(session, new, st_like=st_like, source="style_jam_authoritative_key")
    session[IMPROV_STYLE_KEY_TRACKER] = new
    meta = dict(session.get("improv_style_meta") or {})
    meta["key"] = new
    session["improv_style_meta"] = meta
    invalidate_creative_backing_context(session)
    _apply_pending_backing_context_on_page(session, st_like=st_like)


def sync_creative_style_jam_meta(session: dict[str, Any]) -> None:
    """Keep improv_style_meta aligned with Style Jam widgets."""
    from songs.playback_defaults import normalize_groove_label

    groove_intensity = str(session.get("improv_groove") or "Medium").strip()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Jam Session Generator":
        style_name = str(session.get("improv_jam_style") or "").strip()
        mood_name = str(session.get("improv_jam_mood") or "Mellow").strip()
        key_name = str(session.get("improv_jam_key") or "").strip()
        bpm_val = int(session.get("improv_jam_bpm") or 110)
    else:
        style_name = str(session.get("improv_style") or session.get("improv_jam_style") or "").strip()
        mood_name = str(session.get("improv_mood") or session.get("improv_jam_mood") or "Mellow").strip()
        key_name = str(session.get("improv_style_key") or session.get("improv_jam_key") or "").strip()
        bpm_val = int(session.get("improv_style_bpm") or session.get("improv_jam_bpm") or 110)
    backing_style = normalize_groove_label(style_name or "Pop groove")
    session["improv_style_meta"] = {
        "style": style_name,
        "backing_style": backing_style,
        "bpm": bpm_val,
        "groove": groove_intensity,
        "groove_intensity": groove_intensity,
        "key": key_name,
        "mood": mood_name,
        "difficulty": str(session.get("improv_difficulty") or "Intermediate").strip(),
        "meter": str(session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4").strip(),
        "entry_mode": entry,
    }
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass


def on_improv_jam_key_change() -> None:
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_jam_key_change"
    )
    try:
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(
            st.session_state,
            widget_key="improv_jam_key",
        )
    except ImportError:
        pass
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_jam_key_change"
    )


def user_sidebar_display_key_authoritative(session: dict[str, Any]) -> bool:
    """True when the user explicitly set display_key — Creative projection must not overwrite."""
    try:
        from active_song_state import _display_key_override_valid_for_identity

        if _display_key_override_valid_for_identity(session):
            return True
    except ImportError:
        pass
    src = str(session.get("display_key_change_source") or "").strip()
    if src in _SIDEBAR_USER_DISPLAY_KEY_SOURCES:
        return True
    if src and "sidebar" in src.lower():
        return True
    return False


def _sidebar_key_options_including(session: dict[str, Any], key: str) -> list[str]:
    from music_theory import key_mode, practice_keys_for_mode

    live = str(key or session.get("display_key") or "").strip() or "C"
    options = list(practice_keys_for_mode(key_mode(live)))
    if live not in options:
        options = [live] + options
    return options


def is_creative_major_jam_active(session: dict[str, Any]) -> bool:
    """True when Style Jam or Jam Session Generator owns major-key context."""
    try:
        from musical_context_authority import song_catalog_context_owns_practice_key

        if song_catalog_context_owns_practice_key(session):
            return False
    except ImportError:
        pass
    tab = str(
        session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or ""
    ).strip()
    if tab in {"Missions", "Song-Based Improvisation", "Phrase / Motif"}:
        return False
    page = str(session.get("studio_page") or "").strip().lower()
    entry = str(session.get("improv_entry_mode") or "").strip()
    if page == "creative" and entry in CREATIVE_MAJOR_JAM_MODES:
        return True
    if page not in {"creative", "backing"}:
        return False
    try:
        from backing_context import active_creative_backing_context, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "regular_song":
            return False
        creative = active_creative_backing_context(session)
        if creative is not None and creative.source == "entry_jam":
            mode = str(creative.entry_mode or creative.mode_label or "").strip()
            if mode in CREATIVE_MAJOR_JAM_MODES:
                return True
            short = mode.replace(" Mode", "").replace(" Generator", "")
            if short in {"Style Jam", "Jam Session"}:
                return True
    except ImportError:
        pass
    if entry not in CREATIVE_MAJOR_JAM_MODES:
        return False
    return True


def to_major_key_preserve_spelling(key: str) -> str:
    """Strip minor quality while keeping the user's flat/sharp spelling family."""
    from music_theory import CHROMATIC, key_is_minor, normalize_root, reference_spelling_mode, spell_pitch_class, split_chord

    text = str(key or "C").strip() or "C"
    if text.lower().endswith(" minor"):
        text = text[: -len(" minor")].strip() or "C"
    if not key_is_minor(text):
        return text
    root, _suffix = split_chord(text)
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return text
    mode = reference_spelling_mode(text)
    return spell_pitch_class(CHROMATIC.index(nr), mode=mode)


def creative_major_shape_key_options(session: dict[str, Any], selected: str = "") -> list[str]:
    """Major-only shape/written key options for Creative jam contexts."""
    pick = to_major_key_preserve_spelling(str(selected or "").strip())
    options = list(CREATIVE_MAJOR_KEY_OPTIONS)
    if pick and pick not in options:
        return [pick] + options
    if pick:
        return [pick] + [k for k in options if k != pick]
    return options


def sanitize_creative_major_chart_keys(
    session: dict[str, Any],
    *,
    st_like: Any | None = None,
) -> None:
    """Convert inherited minor shape/written keys to major spellings for Creative jams.

    Never writes widget-owned session keys (``display_key``, capo shape, improv key
    pickers) after render — uses pending keys flushed before widgets instead.
    """
    if not is_creative_major_jam_active(session):
        return
    try:
        from guitar_capo import CAPO_SHAPE_KEY
    except ImportError:
        CAPO_SHAPE_KEY = "guitar_capo_shape_key"
    try:
        from songs.key_state import PENDING_DISPLAY_KEY, request_display_key
    except ImportError:
        PENDING_DISPLAY_KEY = "_pending_display_key"
        request_display_key = None  # type: ignore

    shape = str(session.get(CAPO_SHAPE_KEY) or "").strip()
    if shape:
        session[PENDING_CAPO_SHAPE_KEY] = to_major_key_preserve_spelling(shape)

    concert = str(creative_entry_concert_key(session) or session.get("concert_key") or "").strip()
    if concert:
        concert = to_major_key_preserve_spelling(concert)
        session["concert_key"] = concert
        if request_display_key is not None and st_like is not None:
            request_display_key(st_like, concert)
        else:
            session[PENDING_DISPLAY_KEY] = concert
        entry = str(session.get("improv_entry_mode") or "").strip()
        if entry == "Style Jam Mode":
            session[PENDING_IMPROV_STYLE_KEY] = concert
        elif entry == "Jam Session Generator":
            session[PENDING_IMPROV_JAM_KEY] = concert


def creative_sidebar_key_options(session: dict[str, Any]) -> list[str]:
    """Major key options for Creative jam — preserves user enharmonic spelling."""
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            return [to_major_key_preserve_spelling(resolve_practice_concert_key_for_song(session, "C"))]
    except ImportError:
        pass
    selected = to_major_key_preserve_spelling(
        str(creative_entry_concert_key(session) or session.get("concert_key") or "").strip()
    )
    options = list(CREATIVE_MAJOR_KEY_OPTIONS)
    if selected and selected not in options:
        return [selected] + options
    if selected:
        return [selected] + [k for k in options if k != selected]
    return options


def _sidebar_preserve_user_display_key_options(
    st: Any,
    session: dict[str, Any],
    *,
    trace_phase: str,
    **trace_fields: Any,
) -> list[str] | None:
    """When the user explicitly set display_key, skip Creative/backing projection."""
    if not user_sidebar_display_key_authoritative(session):
        return None
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if not live:
        return None
    session["concert_key"] = live
    options = _sidebar_key_options_including(session, live)
    try:
        from display_key_sidebar_persistence_trace import (
            record_display_key_sidebar_event,
            record_display_key_sidebar_stage,
        )

        record_display_key_sidebar_stage(
            session,
            "next_rerun_projection",
            caller=trace_phase,
            skipped_projection=True,
            **trace_fields,
        )
        record_display_key_sidebar_event(
            session,
            trace_phase,
            skipped_projection=True,
            stage="next_rerun_projection",
            **trace_fields,
        )
    except ImportError:
        pass
    return options


def prepare_backing_context_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Apply non-major Creative backing concert key before the sidebar widget."""
    from music_theory import key_mode, practice_keys_for_mode
    from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget

    flush_pending_creative_major_keys(session)
    preserved = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_backing_context_sidebar:preserve_user_key",
    )
    if preserved is not None:
        session.pop(PENDING_DISPLAY_KEY, None)
        return preserved
    try:
        from backing_context import active_creative_backing_context, get_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from creative_session_state import (
            creative_session_is_active,
            get_creative_session,
        )

        creative = active_creative_backing_context(session)
        ctx = get_backing_context(session)
        creative_sess = get_creative_session(session) if creative is None else None
    except ImportError:
        creative = None
        ctx = None
        creative_sess = None
        resolve_current_backing_musical_state = None  # type: ignore[assignment]
    pending = session.pop(PENDING_DISPLAY_KEY, None)
    resolver_key = ""
    ctx_source = str(getattr(ctx, "source", "") or "").strip() if ctx is not None else ""
    sbi_custom_preview = False
    try:
        from songs.practice_key_state import sbi_uses_custom_progression_preview

        sbi_custom_preview = sbi_uses_custom_progression_preview(session)
    except ImportError:
        pass
    if ctx_source == "custom_progression" or sbi_custom_preview:
        ctx_source = "custom_progression"
    if ctx_source == "regular_song":
        try:
            from backing_musical_state import resolve_current_backing_musical_state

            resolver_key = str(
                resolve_current_backing_musical_state(session).practice_concert_key or ""
            ).strip()
        except ImportError:
            resolver_key = str(
                getattr(ctx, "concert_key", None)
                or getattr(ctx, "display_key", None)
                or getattr(ctx, "key", None)
                or ""
            ).strip()
    elif ctx_source == "custom_progression":
        home_key = ""
        if ctx is not None:
            home_key = str(getattr(ctx, "key", "") or "").strip()
        try:
            from custom_progression_lab import CPL_ACTIVE_KEY, cpl_draft_written_key, ensure_original_structure

            active = ensure_original_structure(session.get(CPL_ACTIVE_KEY) or {})
            home_key = cpl_draft_written_key(active) or home_key
        except ImportError:
            pass
        try:
            from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song
            from songs.practice_key_state import resolve_practice_source_pick

            if is_fixed_practice_key_mode(session):
                pick = resolve_practice_source_pick(session)
                selected = resolve_practice_concert_key_for_song(
                    session,
                    home_key or "C",
                    pick_key=pick,
                    fallback=home_key or "C",
                )
            else:
                raise ImportError
        except ImportError:
            try:
                from backing_context import _live_backing_concert_keys

                _, _, resolver_key = _live_backing_concert_keys(session)
            except ImportError:
                resolver_key = str(
                    getattr(ctx, "concert_key", None)
                    or getattr(ctx, "display_key", None)
                    or getattr(ctx, "key", None)
                    or ""
                ).strip()
            try:
                from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

                saved = get_practice_concert_key(session, resolve_practice_source_pick(session))
            except ImportError:
                saved = ""
            live = str(session.get("display_key") or session.get("concert_key") or "").strip()
            selected = str(pending or saved or live or resolver_key or home_key or "C").strip() or "C"
    elif creative and resolve_current_backing_musical_state is not None:
        resolver_key = str(
            resolve_current_backing_musical_state(session).practice_concert_key or ""
        ).strip()
    elif (
        creative_sess is not None
        and creative_session_is_active(session)
        and str(session.get("active_music_source") or "").strip() != "catalog"
        and not (ctx is not None and str(getattr(ctx, "source", "") or "").strip() == "custom_progression")
    ):
        resolver_key = str(creative_sess.concert_key or creative_sess.display_key or "").strip()
    if ctx_source != "custom_progression":
        selected = str(
            pending
            or resolver_key
            or (creative_sess.concert_key if creative_sess and creative_session_is_active(session) else "")
            or session.get("concert_key")
            or session.get("display_key")
            or (creative.concert_key if creative else "")
            or "C"
        ).strip() or "C"
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session) and ctx_source != "custom_progression":
            selected = resolve_practice_concert_key_for_song(session, selected, fallback=selected)
    except ImportError:
        pass
    options = practice_keys_for_mode(key_mode(selected))
    if selected not in options:
        options = [selected] + options
    if ctx_source == "custom_progression":
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        session["concert_key"] = selected
        if pending is not None or not live or live != selected:
            _apply_display_key_before_widget(st, selected, source="backing_context_concert")
            session["concert_key"] = selected
        return options
    if user_sidebar_display_key_authoritative(session):
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if live:
            options = _sidebar_key_options_including(session, live)
            session["concert_key"] = live
            try:
                from display_key_sidebar_persistence_trace import record_display_key_sidebar_event

                record_display_key_sidebar_event(
                    session,
                    "prepare_backing_context_sidebar:preserve_user_key",
                    skipped_projection=True,
                    resolver_key=resolver_key or None,
                    selected_would_have_been=selected,
                )
            except ImportError:
                pass
            return options
    _apply_display_key_before_widget(st, selected, source="backing_context_concert")
    session["concert_key"] = selected
    return options


def prepare_creative_sidebar_display_key(st: Any, session: dict[str, Any]) -> list[str]:
    """Apply Creative concert key before the sidebar Practice / Concert Key widget."""
    from songs.key_state import PENDING_DISPLAY_KEY, _apply_display_key_before_widget

    flush_pending_creative_major_keys(session)
    preserved = _sidebar_preserve_user_display_key_options(
        st,
        session,
        trace_phase="prepare_creative_sidebar:preserve_user_key",
    )
    if preserved is not None:
        session.pop(PENDING_DISPLAY_KEY, None)
        return preserved
    options = creative_sidebar_key_options(session)
    backing_key = ""
    try:
        from backing_context import active_creative_backing_context
        from backing_musical_state import resolve_current_backing_musical_state

        creative_ctx = active_creative_backing_context(session)
        if creative_ctx is not None:
            backing_key = str(
                resolve_current_backing_musical_state(session).practice_concert_key
                or creative_ctx.concert_key
                or creative_ctx.display_key
                or ""
            ).strip()
    except ImportError:
        pass
    pending = session.pop(PENDING_DISPLAY_KEY, None)
    selected = str(
        pending
        or backing_key
        or creative_entry_concert_key(session)
        or session.get("concert_key")
        or session.get("display_key")
        or ""
    ).strip()
    try:
        from practice_key_mode import is_fixed_practice_key_mode, resolve_practice_concert_key_for_song

        if is_fixed_practice_key_mode(session):
            selected = resolve_practice_concert_key_for_song(session, "C", fallback=selected or "C")
    except ImportError:
        pass
    selected = to_major_key_preserve_spelling(selected)
    if user_sidebar_display_key_authoritative(session):
        live = str(session.get("display_key") or session.get("concert_key") or "").strip()
        if live:
            options = _sidebar_key_options_including(session, live)
            session["concert_key"] = live
            try:
                from display_key_sidebar_persistence_trace import record_display_key_sidebar_event

                record_display_key_sidebar_event(
                    session,
                    "prepare_creative_sidebar:preserve_user_key",
                    skipped_projection=True,
                    backing_key=backing_key or None,
                )
            except ImportError:
                pass
            return options
    if selected:
        if selected not in options:
            options = [selected] + [k for k in options if k != selected]
        _apply_display_key_before_widget(st, selected, source="creative_concert_key")
    elif session.get("display_key") not in options:
        _apply_display_key_before_widget(st, options[0], source="creative_default")
    session["concert_key"] = str(session.get("display_key") or options[0])
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry == "Style Jam Mode":
        session[PENDING_IMPROV_STYLE_KEY] = session["concert_key"]
    elif entry == "Jam Session Generator":
        session[PENDING_IMPROV_JAM_KEY] = session["concert_key"]
    sanitize_creative_major_chart_keys(session, st_like=st)
    post_sanitize = session.pop(PENDING_DISPLAY_KEY, None)
    if post_sanitize is not None:
        _apply_display_key_before_widget(st, str(post_sanitize), source="creative_sanitize")
    flush_pending_creative_major_keys(session)
    return options


def should_use_live_practice_key_sidebar(session: dict[str, Any]) -> bool:
    """Use session practice concert key instead of catalog original-key defaults."""
    try:
        from songs.music_source import cpl_session_is_active, custom_progression_is_active, is_custom_progression

        if is_custom_progression(session) or custom_progression_is_active(session) or cpl_session_is_active(session):
            return True
    except ImportError:
        pass
    try:
        from backing_musical_state import should_skip_regular_song_defaults

        if should_skip_regular_song_defaults(session):
            return True
    except ImportError:
        pass
    try:
        from backing_context import catalog_or_custom_backing_is_authoritative, get_backing_context

        if catalog_or_custom_backing_is_authoritative(session):
            ctx = get_backing_context(session)
            if ctx is not None and ctx.source == "regular_song":
                return False
    except ImportError:
        pass
    page = str(session.get("studio_page") or "").strip().lower()
    if page == "creative":
        return True
    if page == "backing":
        return True
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry in {"Style Jam Mode", "Jam Session Generator", "Song-Based Improvisation"}:
        return True
    return False


def _resolve_creative_entry_mode(session: dict[str, Any]) -> str:
    """Infer improv entry mode from widgets or active backing_context."""
    entry = str(session.get("improv_entry_mode") or "").strip()
    if entry:
        return entry
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is None:
            return ""
        if ctx.source == "song_improv":
            return "Song-Based Improvisation"
        if ctx.source == "entry_jam":
            return str(ctx.entry_mode or "Style Jam Mode").strip()
    except ImportError:
        pass
    return ""


def _creative_sidebar_key_sync_active(session: dict[str, Any]) -> bool:
    """True when sidebar key changes should retranspose Creative / backing handoff."""
    if is_creative_major_jam_active(session):
        return True
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source in {
            "entry_jam",
            "mission",
            "song_improv",
            "custom_progression",
        }:
            page = str(session.get("studio_page") or "").strip().lower()
            return page in {"creative", "backing"}
    except ImportError:
        pass
    return False


def _apply_pending_backing_context_on_page(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Apply refreshed backing_context to widgets during the same rerun (Backing page)."""
    page = str(session.get("studio_page") or "").strip().lower()
    if page != "backing":
        return
    try:
        from backing_context import (
            PENDING_BACKING_CONTEXT_APPLY,
            apply_backing_context_to_session,
            get_backing_context,
        )
    except ImportError:
        return
    if not session.get(PENDING_BACKING_CONTEXT_APPLY):
        return
    ctx = get_backing_context(session)
    if ctx is None:
        return
    apply_backing_context_to_session(session, ctx, st_like=st_like, widget_safe=True)
    session.pop(PENDING_BACKING_CONTEXT_APPLY, None)


def sync_sidebar_creative_concert_key(session: dict[str, Any], *, st_like: Any | None = None) -> None:
    """Retranspose Creative progressions when sidebar Practice Concert Key changes."""
    new = str(session.get("display_key") or "").strip()
    if not new:
        return
    try:
        from music_workflow_mutation import update_active_practice_key
        from music_workflow_state_store import get_active_workflow_pointer

        ptr = get_active_workflow_pointer(session)
        if ptr and ptr.workflow_owner == "style_jam":
            result = update_active_practice_key(
                session, new, source="on_improv_style_key_change", transpose_progression=True
            )
            if not result.ok:
                return
            sync_style_jam_legacy_after_authoritative_key(session, new, st_like=st_like)
            return
        if ptr and ptr.workflow_owner == "jam_session_generator":
            result = update_active_practice_key(
                session, new, source="on_improv_jam_key_change", transpose_progression=True
            )
            if not result.ok:
                return
            apply_creative_concert_key(session, new, st_like=st_like, source="creative_jam_session")
            session[IMPROV_JAM_KEY_TRACKER] = new
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            return
        if ptr and ptr.workflow_owner in {"song_based_improvisation", "mission_jam"}:
            result = update_active_practice_key(
                session, new, source="sidebar_song_improv", transpose_progression=True
            )
            if not result.ok:
                return
            session["concert_key"] = new
            try:
                from backing_context import sync_improv_widgets_from_live_concert_key

                sync_improv_widgets_from_live_concert_key(session)
            except ImportError:
                pass
            try:
                from backing_musical_state import clear_stale_chart_session_keys
                from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

                clear_stale_chart_session_keys(session)
                if st_like is not None:
                    invalidate_backing_cache(st_like)
                session[BACKING_NEEDS_REGEN] = True
            except ImportError:
                pass
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            try:
                from creative_session_state import sync_creative_session_from_session

                sync_creative_session_from_session(session)
            except ImportError:
                pass
            return
    except ImportError:
        pass
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source == "custom_progression":
            session["concert_key"] = new
            try:
                from songs.practice_key_state import resolve_practice_source_pick, set_practice_concert_key

                set_practice_concert_key(
                    session,
                    new,
                    pick_key=resolve_practice_source_pick(session),
                )
            except ImportError:
                pass
            try:
                from custom_progression_lab import on_global_display_key_change

                on_global_display_key_change(session, new)
            except ImportError:
                pass
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            return
    except ImportError:
        pass
    entry = _resolve_creative_entry_mode(session)
    if entry and not str(session.get("improv_entry_mode") or "").strip():
        session["improv_entry_mode"] = entry
    try:
        from studio_page_state import resolve_improv_song_source

        if entry == "Song-Based Improvisation" and resolve_improv_song_source(session) == "Custom progression":
            session["concert_key"] = new
            try:
                from songs.practice_key_state import resolve_practice_source_pick, set_practice_concert_key

                set_practice_concert_key(
                    session,
                    new,
                    pick_key=resolve_practice_source_pick(session),
                )
            except ImportError:
                pass
            try:
                from custom_progression_lab import on_global_display_key_change

                on_global_display_key_change(session, new)
            except ImportError:
                pass
            invalidate_creative_backing_context(session)
            _apply_pending_backing_context_on_page(session, st_like=st_like)
            return
    except ImportError:
        pass
    if entry == "Song-Based Improvisation":
        try:
            from music_workflow_mutation import update_active_practice_key

            update_active_practice_key(
                session,
                new,
                source="sidebar_song_improv",
                transpose_progression=True,
            )
        except ImportError:
            pass
        session["concert_key"] = new
        try:
            from backing_context import sync_improv_widgets_from_live_concert_key

            sync_improv_widgets_from_live_concert_key(session)
        except ImportError:
            pass
        try:
            from backing_musical_state import clear_stale_chart_session_keys
            from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

            clear_stale_chart_session_keys(session)
            if st_like is not None:
                invalidate_backing_cache(st_like)
            session[BACKING_NEEDS_REGEN] = True
        except ImportError:
            pass
        invalidate_creative_backing_context(session)
        _apply_pending_backing_context_on_page(session, st_like=st_like)
        try:
            from creative_session_state import sync_creative_session_from_session

            sync_creative_session_from_session(session)
        except ImportError:
            pass
        return
    if not _creative_sidebar_key_sync_active(session):
        return
    if entry == "Style Jam Mode":
        prev = str(session.get(IMPROV_STYLE_KEY_TRACKER) or session.get("improv_style_key") or "").strip()
        session["improv_style_key"] = new
        sync_creative_key_change(session, new, previous_key=prev, st_like=st_like)
    elif entry == "Jam Session Generator":
        prev = str(session.get(IMPROV_JAM_KEY_TRACKER) or session.get("improv_jam_key") or "").strip()
        session["improv_jam_key"] = new
        gen = session.get("improv_jam_session")
        if isinstance(gen, dict) and gen.get("sections") and prev and prev != new:
            session["improv_jam_session"] = {
                **gen,
                "sections": retranspose_generated_sections(
                    dict(gen.get("sections") or {}),
                    from_key=prev,
                    to_key=new,
                ),
            }
        apply_creative_concert_key(session, new, st_like=st_like, source="creative_jam_session")
        session[IMPROV_JAM_KEY_TRACKER] = new
        meta = dict(session.get("improv_style_meta") or {})
        meta["key"] = new
        session["improv_style_meta"] = meta
        invalidate_creative_backing_context(session)
    _apply_pending_backing_context_on_page(session, st_like=st_like)
    try:
        from creative_session_state import sync_creative_session_from_session

        sync_creative_session_from_session(session)
    except ImportError:
        pass


def on_sidebar_practice_concert_key_change() -> None:
    """Sidebar widget callback — global key change + Creative retransposition."""
    import streamlit as st

    from songs.key_state import mark_display_key_changed

    mark_display_key_changed(st)
    sync_sidebar_creative_concert_key(st.session_state, st_like=st)


def on_improv_style_key_change() -> None:
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_style_key_change"
    )
    try:
        from generated_jam_key_change import capture_generated_key_edit_intent

        capture_generated_key_edit_intent(
            st.session_state,
            widget_key="improv_style_key",
        )
    except ImportError:
        pass
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_style_key_change"
    )


def on_improv_style_jam_setting_change() -> None:
    """BPM / groove / style / mood / difficulty change — refresh meta and invalidate backing handoff."""
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_style_jam_setting_change"
    )
    sync_creative_style_jam_meta(st.session_state)
    invalidate_creative_backing_context(st.session_state)
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_style_jam_setting_change"
    )


def on_improv_jam_setting_change() -> None:
    """Jam Session BPM / mood change — refresh meta and invalidate backing handoff."""
    import streamlit as st

    before_pick = guard_creative_catalog_pick_before_edit(
        st.session_state, writer="on_improv_jam_setting_change"
    )
    sync_creative_style_jam_meta(st.session_state)
    invalidate_creative_backing_context(st.session_state)
    verify_creative_catalog_pick_after_edit(
        st.session_state, before_pick=before_pick, writer="on_improv_jam_setting_change"
    )


def ensure_creative_analysis_mode_restored(session_state: dict[str, Any]) -> str:
    """Restore Creative analysis mode before the selectbox renders."""
    try:
        from creative_tab_tool_persistence import (
            canonical_creative_selector_value,
            project_startup_default_selector,
            selector_hydration_complete,
        )

        canon = canonical_creative_selector_value(session_state, "creative_lab_analysis_mode")
        if canon:
            if str(session_state.get("creative_lab_analysis_mode") or "").strip() != canon:
                session_state["creative_lab_analysis_mode"] = canon
            session_state["creative_lab_last_mode"] = canon
            return canon
        if not selector_hydration_complete(session_state):
            return str(session_state.get("creative_lab_analysis_mode") or "").strip()
    except ImportError:
        pass
    last = str(session_state.get("creative_lab_last_mode") or "").strip()
    current = str(session_state.get("creative_lab_analysis_mode") or "").strip()
    if last and last != current:
        session_state["creative_lab_analysis_mode"] = last
        return last
    if current:
        session_state["creative_lab_last_mode"] = current
        return current
    if last:
        session_state["creative_lab_analysis_mode"] = last
        return last
    try:
        from creative_tab_tool_persistence import project_startup_default_selector, selector_hydration_complete

        if selector_hydration_complete(session_state):
            projected = project_startup_default_selector(
                session_state, "creative_lab_analysis_mode", "Deep Harmonic Analyzer"
            )
            if projected:
                return projected
    except ImportError:
        pass
    default = "Deep Harmonic Analyzer"
    session_state["creative_lab_analysis_mode"] = default
    session_state["creative_lab_last_mode"] = default
    return default


def persist_creative_analysis_mode(session_state: dict[str, Any]) -> str:
    """Persist Analysis Mode to a non-widget key before leaving Creative.

    Reads the widget-owned ``creative_lab_analysis_mode`` but never writes it back
    after the selectbox may have rendered in the same run.
    """
    mode = str(session_state.get("creative_lab_analysis_mode") or "").strip()
    if not mode:
        mode = str(session_state.get("creative_lab_last_mode") or "").strip()
    if mode:
        session_state["creative_lab_last_mode"] = mode
        session_state["_creative_mode_user_touched"] = True
    return mode


def on_creative_analysis_mode_change() -> None:
    import streamlit as st

    try:
        from creative_tab_tool_persistence import handle_user_creative_selector_change

        handle_user_creative_selector_change(st.session_state, "creative_lab_analysis_mode")
        return
    except ImportError:
        pass
    mode = str(st.session_state.get("creative_lab_analysis_mode") or "").strip()
    if mode:
        st.session_state["creative_lab_last_mode"] = mode
    st.session_state["_creative_mode_user_touched"] = True


def _chart_display_label(session: dict[str, Any]) -> str:
    instrument = str(session.get("instrument") or "")
    if instrument == "Guitar" and session.get("guitar_capo_enabled"):
        return "Guitar shape chart"
    try:
        from instrument_transposition import chart_in_instrument_key, is_transposing_instrument

        if is_transposing_instrument(instrument) and chart_in_instrument_key(session):
            return "Written chart"
    except ImportError:
        pass
    return "Chart"


def creative_progression_display(
    session: dict[str, Any],
    sections: dict[str, list[str]],
    *,
    concert_key: str = "",
) -> dict[str, str]:
    """Build concert + written/shape progression lines for Creative display."""
    from improvisation_intelligence import flatten_sections

    concert = str(
        concert_key or creative_entry_concert_key(session) or session.get("concert_key") or "C"
    ).strip()
    concert_line = " · ".join(flatten_sections(sections)[:32])
    try:
        from backing_context import _resolve_chart_display_key, sections_dict_for_chart_display

        chart_key = _resolve_chart_display_key(session, concert)
        chart_sections = sections_dict_for_chart_display(session, sections, concert_key=concert)
    except ImportError:
        chart_key = concert
        chart_sections = sections
    chart_line = " · ".join(flatten_sections(chart_sections)[:32])
    show_chart = bool(chart_line and (chart_key != concert or chart_line != concert_line))
    return {
        "concert_key": concert,
        "chart_key": chart_key if show_chart else "",
        "concert_line": concert_line,
        "chart_line": chart_line if show_chart else "",
        "chart_label": _chart_display_label(session) if show_chart else "",
    }


def render_creative_progression_block(st: Any, session: dict[str, Any], sections: dict[str, list[str]]) -> None:
    """Render concert progression and optional written/shape chart line."""
    display = creative_progression_display(session, sections)
    st.markdown(
        f'<p class="ui-creative-progression-preview">Practice concert key: '
        f"<strong>{html.escape(display['concert_key'])}</strong></p>",
        unsafe_allow_html=True,
    )
    if display["concert_line"]:
        st.markdown(
            f'<p class="ui-creative-progression-preview"><strong>Concert Practice Key Progression:</strong> '
            f"{html.escape(display['concert_line'])}</p>",
            unsafe_allow_html=True,
        )
    if display["chart_line"]:
        label = display["chart_label"] or "Written Key"
        key_note = f" ({html.escape(display['chart_key'])})" if display.get("chart_key") else ""
        st.markdown(
            f'<p class="ui-creative-progression-preview"><strong>Written Key Progression{key_note}:</strong> '
            f"{html.escape(display['chart_line'])}</p>",
            unsafe_allow_html=True,
        )
