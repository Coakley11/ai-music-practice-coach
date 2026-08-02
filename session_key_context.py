"""Canonical fixed-family session key — one resolver for charts, practice, and backing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from music_theory import key_mode

LIVE_KEY_FAMILY_RENDER_TRACE_KEY = "_live_key_family_render_trace"
LAST_KEY_WRITER_FUNCTION_KEY = "last_key_writer_function"
KEY_OVERWRITE_STAGE_KEY = "key_overwrite_stage"

SOURCE_FIXED_KEY_FAMILY = "fixed_key_family"
SOURCE_STANDARD = "standard"


@dataclass(frozen=True)
class EffectiveSessionKeyContext:
    selected_family: str
    selected_family_normalized: str
    mode: str
    resolved_tonal_key: str
    concert_key: str
    practice_key: str
    display_key: str
    source: str
    fixed_key_mode_enabled: bool
    active_object_source: str
    active_object_title: str
    active_object_mode: str
    family_override_should_apply: bool
    family_override_applied: bool
    concert_key_before_override: str
    concert_key_after_override: str
    practice_key_before_override: str
    practice_key_after_override: str
    display_key_before_override: str
    display_key_final: str
    chart_target_key: str
    backing_target_key: str
    last_key_writer_function: str
    key_overwritten_after_family_resolution: bool
    key_overwrite_stage: str
    instrument: str
    transposition_mode: str
    capo_mode_enabled: bool
    shape_key: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _str(v: Any) -> str:
    return str(v or "").strip()


def resolve_active_object_title(session: dict[str, Any]) -> str:
    try:
        from songs.state import SELECTED_SONG_STATE_KEY

        sel = session.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict):
            title = _str(sel.get("title"))
            if title:
                return title
    except ImportError:
        pass
    return _str(session.get("song") or session.get("active_song_title"))


def resolve_active_object_source(session: dict[str, Any]) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            return _str(getattr(ctx, "source", "") or "backing_context")
    except ImportError:
        pass
    try:
        from songs.music_source import cpl_session_is_active

        if cpl_session_is_active(session):
            return "custom_progression"
    except ImportError:
        pass
    if session.get("improv_active_mission"):
        return "mission"
    if session.get("improv_jam_session") or session.get("improv_style_key"):
        return "jam"
    return "catalog_song"


def resolve_active_object_home_key(
    session: dict[str, Any],
    *,
    original_key: str = "",
) -> str:
    """Catalog/custom/jam/mission/backing home key — never stale display_key."""
    source = resolve_active_object_source(session)
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            obj_key = _str(getattr(ctx, "key", "") or "")
            if obj_key:
                return obj_key
    except ImportError:
        ctx = None

    if source == "custom_progression":
        try:
            from custom_progression_lab import (
                CPL_ACTIVE_KEY,
                default_active_progression,
                ensure_original_structure,
            )
            from songs.music_source import custom_original_key

            active = ensure_original_structure(
                session.get(CPL_ACTIVE_KEY) or default_active_progression()
            )
            home = custom_original_key(active)
            if home:
                return home
        except ImportError:
            pass

    if source == "mission":
        mission = session.get("improv_active_mission")
        if isinstance(mission, dict):
            mk = _str(mission.get("key") or mission.get("tonic") or mission.get("home_key"))
            if mk:
                return mk

    if source == "jam":
        for key in ("improv_jam_key", "improv_style_key"):
            jk = _str(session.get(key))
            if jk:
                return jk
        meta = session.get("improv_style_meta")
        if isinstance(meta, dict):
            mk = _str(meta.get("key"))
            if mk:
                return mk

    try:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        pick = _str(session.get(ACTIVE_CATALOG_PICK_KEY))
        sel = session.get(SELECTED_SONG_STATE_KEY)
        if isinstance(sel, dict):
            sel_pick = _str(sel.get("pick_key"))
            if not pick or sel_pick == pick:
                sk = _str(sel.get("key") or sel.get("original_key"))
                if sk:
                    return sk
    except ImportError:
        pass

    home = _str(original_key)
    if home:
        return home
    try:
        from songs.music_source import _catalog_original_key_for_session

        return _catalog_original_key_for_session(session, None) or "C"
    except ImportError:
        return "C"


def resolve_active_object_mode(session: dict[str, Any], *, original_key: str) -> str:
    """Major/minor from active object metadata — not display_key or family label."""
    home = resolve_active_object_home_key(session, original_key=original_key)
    return key_mode(home or "C")


def resolve_effective_session_key_context(
    session: dict[str, Any],
    *,
    original_key: str = "",
    instrument: str = "",
    apply_to_session: bool = False,
    writer: str = "",
) -> EffectiveSessionKeyContext:
    """
    One canonical key context for the active practice session.

    When fixed key family is enabled, concert/practice/display session keys are the
    family-resolved tonal key (C or Am for C|A). Chart written/shape keys are derived
    from that concert key — not from stale display_key or catalog overrides.
    """
    from practice_key_mode import (
        is_fixed_practice_key_mode,
        normalize_stored_family_option_id,
        resolve_family_option_id,
        resolve_session_key_from_family,
    )

    orig = _str(original_key)
    if not orig:
        orig = resolve_active_object_home_key(session, original_key="")
    orig = orig or "C"

    inst = _str(instrument or session.get("instrument") or "Piano") or "Piano"
    fixed = is_fixed_practice_key_mode(session)
    family_raw = _str(session.get("fixed_practice_key_family_id") or session.get("practice_panel_fixed_practice_key"))
    family_norm = normalize_stored_family_option_id(family_raw or resolve_family_option_id(session))
    object_mode = resolve_active_object_mode(session, original_key=orig)
    object_source = resolve_active_object_source(session)
    object_title = resolve_active_object_title(session)

    concert_before = _str(session.get("concert_key") or orig)
    practice_before = _str(session.get("practice_key") or session.get("display_key") or concert_before)
    display_before = _str(session.get("display_key") or practice_before or concert_before)

    should_apply = bool(fixed and family_norm)
    resolved_tonal = ""
    concert_after = concert_before
    practice_after = practice_before
    display_after = display_before
    source = SOURCE_STANDARD

    if should_apply:
        resolved_tonal = resolve_session_key_from_family(family_norm, object_mode)
        concert_after = resolved_tonal
        practice_after = resolved_tonal
        display_after = resolved_tonal
        source = SOURCE_FIXED_KEY_FAMILY

    chart_target = concert_after
    backing_target = concert_after
    try:
        from instrument_transposition import (
            chart_in_instrument_key,
            effective_chart_key,
            is_transposing_instrument,
        )

        if should_apply and is_transposing_instrument(inst) and chart_in_instrument_key(session):
            chart_target, _ = effective_chart_key(concert_after, inst, session)
        backing_target = concert_after
    except ImportError:
        pass

    if should_apply and apply_to_session:
        session["concert_key"] = concert_after
        session["display_key"] = display_after
        session["practice_key"] = practice_after
        if writer:
            session[LAST_KEY_WRITER_FUNCTION_KEY] = writer
            session[KEY_OVERWRITE_STAGE_KEY] = writer
        try:
            from instrument_transposition import CONCERT_KEY_SESSION_KEY

            session[CONCERT_KEY_SESSION_KEY] = concert_after
        except ImportError:
            pass
        try:
            from songs.key_state import resolve_active_musical_key

            musical = resolve_active_musical_key(session, instrument=inst, surface="session_key_context")
            chart_target = _str(musical.chart_key or display_after)
            backing_target = _str(musical.practice_concert_key or concert_after)
        except ImportError:
            pass

    overwritten = bool(
        should_apply
        and (
            _str(concert_before) != concert_after
            or _str(display_before) != display_after
            or _str(practice_before) != practice_after
        )
    )

    last_writer = _str(session.get(LAST_KEY_WRITER_FUNCTION_KEY) or session.get("_display_key_last_write_source"))

    ctx = EffectiveSessionKeyContext(
        selected_family=family_raw or "(none)",
        selected_family_normalized=family_norm or "(none)",
        mode=object_mode,
        resolved_tonal_key=resolved_tonal or "(n/a)",
        concert_key=concert_after,
        practice_key=practice_after,
        display_key=display_after,
        source=source,
        fixed_key_mode_enabled=fixed,
        active_object_source=object_source,
        active_object_title=object_title or "(none)",
        active_object_mode=object_mode,
        family_override_should_apply=should_apply,
        family_override_applied=bool(should_apply and apply_to_session),
        concert_key_before_override=concert_before or "(none)",
        concert_key_after_override=concert_after or "(none)",
        practice_key_before_override=practice_before or "(none)",
        practice_key_after_override=practice_after or "(none)",
        display_key_before_override=display_before or "(none)",
        display_key_final=_str(session.get("display_key") or display_after),
        chart_target_key=chart_target or "(none)",
        backing_target_key=backing_target or "(none)",
        last_key_writer_function=last_writer or "(none)",
        key_overwritten_after_family_resolution=overwritten,
        key_overwrite_stage=_str(session.get(KEY_OVERWRITE_STAGE_KEY)),
        instrument=inst,
        transposition_mode=_str(session.get("transposition_mode") or session.get("written_key_mode")),
        capo_mode_enabled=bool(session.get("guitar_capo_enabled")),
        shape_key=_str(session.get("guitar_capo_shape_key")),
    )
    session[LIVE_KEY_FAMILY_RENDER_TRACE_KEY] = ctx.as_dict()
    return ctx


def sync_effective_session_keys_before_render(
    session: dict[str, Any],
    *,
    original_key: str = "",
    instrument: str = "",
) -> EffectiveSessionKeyContext:
    """Apply fixed-family concert keys to session immediately before UI/chart render."""
    return resolve_effective_session_key_context(
        session,
        original_key=original_key,
        instrument=instrument,
        apply_to_session=True,
        writer="sync_effective_session_keys_before_render",
    )


def collect_live_key_family_render_trace(session: dict[str, Any]) -> dict[str, Any]:
    """Latest pre-render trace (``?dev=1``)."""
    trace = session.get(LIVE_KEY_FAMILY_RENDER_TRACE_KEY)
    if isinstance(trace, dict):
        return dict(trace)
    return {}


__all__ = [
    "EffectiveSessionKeyContext",
    "LIVE_KEY_FAMILY_RENDER_TRACE_KEY",
    "LAST_KEY_WRITER_FUNCTION_KEY",
    "collect_live_key_family_render_trace",
    "resolve_active_object_home_key",
    "resolve_active_object_mode",
    "resolve_active_object_source",
    "resolve_active_object_title",
    "resolve_effective_session_key_context",
    "sync_effective_session_keys_before_render",
]
