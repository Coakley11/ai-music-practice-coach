"""Canonical Practice page filters — groove, section focus, notation prefs, session length."""



from __future__ import annotations



from datetime import datetime, timezone

from typing import Any



PRACTICE_STATE_KEY = "practice_state"

PRACTICE_DIRTY_KEY = "practice_state_dirty"

PRACTICE_LOCAL_EDIT_TS_KEY = "practice_state_last_local_edit_ts"

PRACTICE_PENDING_SYNC_KEY = "_practice_filters_pending_sync"

PRACTICE_RESTORED_KEY = "_practice_state_cloud_restored"



PRACTICE_MINUTES_MIN = 10

PRACTICE_MINUTES_MAX = 120

PRACTICE_MINUTES_STEP = 5

PRACTICE_MINUTES_DEFAULT = 30



PRACTICE_SCALAR_KEYS = (

    "practice_focus_section",

    "practice_groove_style",

    "practice_minutes",

    "practice_notation_lines",

    "practice_notation_difficulty",

    "last_practice_mode",

)



_DURABLE_FILTER_KEYS = ("practice_groove_style", "practice_minutes")



__all__ = (

    "PRACTICE_DIRTY_KEY",

    "PRACTICE_MINUTES_DEFAULT",

    "PRACTICE_MINUTES_MAX",

    "PRACTICE_MINUTES_MIN",

    "PRACTICE_MINUTES_STEP",

    "PRACTICE_PENDING_SYNC_KEY",

    "PRACTICE_RESTORED_KEY",

    "PRACTICE_SCALAR_KEYS",

    "PRACTICE_STATE_KEY",

    "apply_cloud_practice_state_if_allowed",

    "apply_practice_source_state_from_ami",

    "canonical_practice_filters",

    "clear_practice_local_edit",

    "collect_practice_persistence_trace",

    "commit_practice_state_from_session",

    "coerce_practice_focus_for_widget",

    "coerce_practice_groove_for_widget",
    "resolve_practice_groove_style",

    "flush_practice_edits",

    "gather_practice_filters",

    "is_practice_locally_dirty",

    "mark_practice_local_edit",

    "mark_practice_pending_sync",

    "normalize_practice_focus_section",

    "normalize_practice_groove",

    "normalize_practice_minutes",

    "prepare_practice_minutes_for_widget",

    "prepare_practice_page",

    "render_practice_state_debug",

    "write_canonical_practice_state",

)





def _utc_now_iso() -> str:

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()





def is_practice_locally_dirty(session: dict[str, Any]) -> bool:

    return bool(session.get(PRACTICE_DIRTY_KEY))





def mark_practice_local_edit(session: dict[str, Any]) -> None:

    try:
        from music_workspace_restore_mode import should_record_user_local_dirty

        if not should_record_user_local_dirty(session):
            return
    except ImportError:
        pass
    session[PRACTICE_DIRTY_KEY] = True

    session[PRACTICE_LOCAL_EDIT_TS_KEY] = _utc_now_iso()





def clear_practice_local_edit(session: dict[str, Any]) -> None:

    session.pop(PRACTICE_DIRTY_KEY, None)

    session.pop(PRACTICE_LOCAL_EDIT_TS_KEY, None)

    session.pop(PRACTICE_PENDING_SYNC_KEY, None)





def mark_practice_pending_sync(session: dict[str, Any]) -> None:

    session[PRACTICE_PENDING_SYNC_KEY] = True





def normalize_practice_focus_section(value: Any) -> str:
    """Normalize section-focus selector values (Full Song casing, trim)."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        from practice_studio import PRACTICE_FOCUS_FULL, practice_is_full_song

        if practice_is_full_song(raw):
            return PRACTICE_FOCUS_FULL
    except ImportError:
        if raw.lower() in ("full song", "full form"):
            return "Full Song"
    return raw


def _section_focus_matches_choices(section: str, choices: list[str]) -> bool:
    if not section or not choices:
        return False
    norm = normalize_practice_focus_section(section)
    if norm in choices:
        return True
    return section in choices


def normalize_practice_groove(groove: Any) -> str:

    """Map any groove label to a ``GROOVE_STYLE_CHOICES`` value."""

    raw = str(groove or "").strip()

    if not raw:

        return ""

    try:

        from songs.playback_defaults import normalize_groove_label



        return normalize_groove_label(raw)

    except ImportError:

        return raw





def normalize_practice_minutes(val: Any, *, default: int | None = None) -> int | None:

    """Clamp practice length to the slider range and 5-minute steps."""

    if val is None or val == "":

        return default

    try:

        n = int(val)

    except (TypeError, ValueError):

        return default

    n = max(PRACTICE_MINUTES_MIN, min(PRACTICE_MINUTES_MAX, n))

    step = PRACTICE_MINUTES_STEP

    n = int(round(n / step) * step)

    n = max(PRACTICE_MINUTES_MIN, min(PRACTICE_MINUTES_MAX, n))

    return n





def _normalize_int(val: Any, default: int = 2) -> int:

    try:

        n = int(val)

        return n if n > 0 else default

    except (TypeError, ValueError):

        return default





def _normalize_filters(raw: dict[str, Any] | None) -> dict[str, Any]:

    src = raw if isinstance(raw, dict) else {}

    groove = normalize_practice_groove(src.get("practice_groove_style"))

    minutes = normalize_practice_minutes(src.get("practice_minutes"))

    return {

        "practice_focus_section": normalize_practice_focus_section(
            src.get("practice_focus_section")
        ),

        "practice_groove_style": groove,

        "practice_minutes": minutes,

        "practice_notation_lines": _normalize_int(src.get("practice_notation_lines"), 2),

        "practice_notation_difficulty": str(src.get("practice_notation_difficulty") or "medium").strip()

        or "medium",

        "last_practice_mode": str(src.get("last_practice_mode") or "").strip(),

    }





def _filters_have_content(filters: dict[str, Any]) -> bool:

    if str(filters.get("practice_focus_section") or "").strip():

        return True

    if str(filters.get("practice_groove_style") or "").strip():

        return True

    if filters.get("practice_minutes") is not None:

        return True

    if filters.get("practice_notation_lines", 0) > 0:

        return True

    if str(filters.get("practice_notation_difficulty") or "").strip() not in ("", "medium"):

        return True

    if str(filters.get("last_practice_mode") or "").strip():

        return True

    return False





def gather_practice_filters(session: dict[str, Any]) -> dict[str, Any]:

    """Read Practice page filters from live session keys."""

    minutes = session.get("practice_minutes")

    if minutes is None and "practice_minutes" not in session:

        minutes_val = None

    else:

        minutes_val = normalize_practice_minutes(minutes)

    return _normalize_filters(

        {

            "practice_focus_section": session.get("practice_focus_section"),

            "practice_groove_style": session.get("practice_groove_style"),

            "practice_minutes": minutes_val,

            "practice_notation_lines": session.get("practice_notation_lines"),

            "practice_notation_difficulty": session.get("practice_notation_difficulty"),

            "last_practice_mode": session.get("last_practice_mode"),

        }

    )





def canonical_practice_filters(session: dict[str, Any]) -> dict[str, Any] | None:

    meta = session.get(PRACTICE_STATE_KEY)

    if not isinstance(meta, dict):

        return None

    filters = _normalize_filters(meta)

    if not _filters_have_content(filters):

        return None

    return filters





def _preserve_durable_filters_for_autosave(

    session: dict[str, Any],

    filters: dict[str, Any],

    *,

    reason: str,

) -> dict[str, Any]:

    """Keep cloud-restored groove/minutes when autosave would re-seed song/slider defaults."""

    if reason != "autosave":

        return filters

    if is_practice_locally_dirty(session) or session.get(PRACTICE_PENDING_SYNC_KEY):

        return filters

    existing = canonical_practice_filters(session) or {}

    merged = dict(filters)

    for key in _DURABLE_FILTER_KEYS:

        existing_val = existing.get(key)

        if existing_val in (None, ""):

            continue

        gathered_val = merged.get(key)

        if gathered_val != existing_val:

            merged[key] = existing_val

    return merged





def _apply_filters_to_session_keys(session: dict[str, Any], filters: dict[str, Any]) -> None:

    section = normalize_practice_focus_section(filters.get("practice_focus_section"))

    if section:

        session["practice_focus_section"] = section

    groove = normalize_practice_groove(filters.get("practice_groove_style"))

    if groove:

        session["practice_groove_style"] = groove

    minutes = filters.get("practice_minutes")

    if minutes is not None:

        session["practice_minutes"] = int(minutes)

    session["practice_notation_lines"] = _normalize_int(filters.get("practice_notation_lines"), 2)

    difficulty = str(filters.get("practice_notation_difficulty") or "").strip()

    if difficulty:

        session["practice_notation_difficulty"] = difficulty

    mode = str(filters.get("last_practice_mode") or "").strip()

    if mode:

        session["last_practice_mode"] = mode





_PRACTICE_GROOVE_RESOLVED_FOR_SONG_KEY = "_practice_groove_resolved_for_song"
_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY = "_practice_groove_last_resolved_value"


def resolve_practice_groove_style(session: dict[str, Any], *, default_groove: str = "") -> str:
    """Effective groove for Practice — canonical/restored filters, Backing override, then song default.

    Every Practice-page surface (Session summary, Song Coach, Section Deep
    Focus, Section Focus, Scales & Approaches, Practice Coach, Notation/TAB,
    generated exercise copy) calls this one function, so it is the single
    choke point where "active song -> authoritative groove" must hold. The
    caches below (canonical_practice_filters' persisted blob,
    backing_groove_style, practice_groove_style) are written by several
    independent code paths across the app and have repeatedly been found to
    survive a song switch when a Backing/Practice "local edit" flag, a
    Streamlit widget's own persisted value, or a disk/cloud-restored blob
    doesn't get invalidated on that exact switch -- which is how a Pop
    song's groove can keep describing a freshly-picked Jazz standard. The
    one signal that reliably DOES update on every genuine song switch is
    ``_active_song_identity`` (songs/music_source.py), so when it differs
    from the identity groove was last resolved for, this function trusts
    only the caller-supplied ``default_groove`` (the new song's own
    authoritative default) and ignores every cache below for that call,
    instead of risking any of them being the stale one.
    """
    current_identity = str(session.get("_active_song_identity") or "").strip()
    resolved_for = str(session.get(_PRACTICE_GROOVE_RESOLVED_FOR_SONG_KEY) or "").strip()
    song_changed = bool(current_identity) and current_identity != resolved_for
    if current_identity:
        session[_PRACTICE_GROOVE_RESOLVED_FOR_SONG_KEY] = current_identity

    if song_changed:
        resolved = normalize_practice_groove(default_groove) or "Auto"
        session["practice_groove_style"] = resolved
        # Also correct backing_groove_style itself (not just the return
        # value) -- otherwise the very next call, with song_changed now
        # False, falls through to the backing_groove_style check below
        # (checked ahead of practice_groove_style) and un-sticks right back
        # to the stale value on the next rerun. Safe to write here: this
        # function is only ever called while rendering the Practice page,
        # never after Backing's own groove selectbox (same session key)
        # has already been instantiated in this run.
        session["backing_groove_style"] = resolved
        session[_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY] = resolved
        # Correct the persisted canonical blob too, not just the session
        # keys above. prepare_practice_page() re-saves
        # canonical_practice_filters() verbatim on every render
        # ("canonical_preserve" / "restored_preserve" reasons), and this
        # function's own canonical-first check right below trusts that
        # blob over a plain session key. Without this write, the very
        # next call for the SAME song (song_changed now False) reads the
        # still-stale pre-switch blob straight back out and un-sticks the
        # correction made above on this call.
        existing_canonical = canonical_practice_filters(session) or {}
        write_canonical_practice_state(
            session,
            {**existing_canonical, "practice_groove_style": resolved},
            reason="song_switch_groove_correct",
        )
        return resolved

    # NOTE: deliberately NOT gated on ``is_practice_locally_dirty`` below.
    # That flag is a blanket "some Practice-page widget changed" signal
    # (Instrument, Level, Focus, minutes, ...) -- it is not groove-specific,
    # and Practice no longer even renders its own groove selectbox (see
    # ``coerce_practice_groove_for_widget``'s docstring above). Skipping the
    # canonical-trust check below whenever an *unrelated* Practice field
    # (e.g. Instrument) had just been edited used to fall straight through
    # to the unconditional ``backing_raw`` read further down, which could
    # resurrect whatever is currently sitting in ``backing_groove_style``
    # even when nobody ever touched Backing's groove control -- reproduced
    # live as the Guitar Notation/TAB groove flipping back to a stale value
    # after an ordinary Instrument-dropdown rerun.
    canonical = canonical_practice_filters(session) or {}
    canon_groove = normalize_practice_groove(canonical.get("practice_groove_style"))
    if canon_groove:
        last_resolved = str(session.get(_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY) or "").strip()
        backing_live = normalize_practice_groove(session.get("backing_groove_style"))
        # A live Backing-groove-selectbox edit since the last time this
        # resolver ran (it now differs from both what we last returned
        # AND from canonical) is a genuine, more-recent user choice --
        # Backing's own groove widget has no hook into practice_state's
        # canonical blob, so trusting canonical unconditionally here
        # would permanently shadow any override made after a song
        # switch already corrected canonical once (see test
        # test_manual_backing_override_after_a_switch_still_flows_through).
        #
        # Whether backing_live merely *differs* from canonical is not
        # enough to tell a genuine edit apart from a stale value some
        # other programmatic write (a defaults sync, a cloud restore, a
        # cross-song leftover) left sitting in the same session key --
        # both look identical by value alone. ``is_backing_user_dirty``
        # is the one authoritative signal the codebase already uses for
        # exactly this distinction (it is only set by a real Backing
        # widget's own on_change handler via ``mark_backing_user_edit``,
        # never by a programmatic default/restore write), and
        # ``apply_backing_defaults_for_song`` already trusts it the same
        # way when deciding whether to preserve a live Backing play
        # session across a song change.
        try:
            from backing_track_state import is_backing_user_dirty

            genuine_backing_edit = is_backing_user_dirty(session)
        except ImportError:
            genuine_backing_edit = False
        if (
            genuine_backing_edit
            and backing_live
            and backing_live != last_resolved
            and backing_live != canon_groove
        ):
            session["practice_groove_style"] = backing_live
            session[_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY] = backing_live
            # Persist the override into canonical too, not just the plain
            # session keys -- otherwise canon_groove above stays stale on
            # the *next* call. That next call would then see
            # backing_live == last_resolved (both the override value) and
            # fall through to "trust canonical", reverting to the pre-
            # override value; the call after THAT would see backing_live
            # != last_resolved again (last_resolved having just been reset
            # to canon_groove) and override again -- an infinite revert/
            # reapply oscillation across ordinary reruns instead of the
            # override simply holding.
            write_canonical_practice_state(
                session,
                {**canonical, "practice_groove_style": backing_live},
                reason="backing_manual_groove_override",
            )
            return backing_live
        session["practice_groove_style"] = canon_groove
        session[_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY] = canon_groove
        return canon_groove

    backing_raw = str(session.get("backing_groove_style") or "").strip()
    if backing_raw:
        backing_groove = normalize_practice_groove(backing_raw)
        if backing_groove:
            session[_PRACTICE_GROOVE_LAST_RESOLVED_VALUE_KEY] = backing_groove
            session["practice_groove_style"] = backing_groove
            return backing_groove

    current = session.get("practice_groove_style")
    if current is not None and str(current).strip():
        normalized = normalize_practice_groove(current)
        session["practice_groove_style"] = normalized
        return normalized

    fallback = normalize_practice_groove(default_groove) or "Auto"
    session.setdefault("practice_groove_style", fallback)
    return str(session["practice_groove_style"])


def coerce_practice_groove_for_widget(session: dict[str, Any], *, default_groove: str = "") -> str:
    """Backward-compatible alias — Practice page no longer renders a groove selectbox."""

    return resolve_practice_groove_style(session, default_groove=default_groove)





def prepare_practice_minutes_for_widget(session: dict[str, Any]) -> int:

    """Bind practice length slider to canonical blob before widget render."""

    if not is_practice_locally_dirty(session):

        canonical = canonical_practice_filters(session) or {}

        canon_minutes = normalize_practice_minutes(canonical.get("practice_minutes"))

        if canon_minutes is not None:

            session["practice_minutes"] = canon_minutes

            return canon_minutes



    minutes = normalize_practice_minutes(

        session.get("practice_minutes"),

        default=PRACTICE_MINUTES_DEFAULT,

    )

    if minutes is not None:

        session["practice_minutes"] = minutes

    return int(minutes or PRACTICE_MINUTES_DEFAULT)





def write_canonical_practice_state(

    session: dict[str, Any],

    filters: dict[str, Any],

    *,

    reason: str = "",

    local_edit: bool = False,

) -> dict[str, Any]:

    """Single write path for Practice page filters."""

    normalized = _normalize_filters(filters)

    session[PRACTICE_STATE_KEY] = {

        **normalized,

        "last_write_reason": reason or None,

    }

    _apply_filters_to_session_keys(session, normalized)

    if local_edit:

        mark_practice_local_edit(session)

    session.pop(PRACTICE_PENDING_SYNC_KEY, None)

    return normalized





def coerce_practice_focus_for_widget(
    session: dict[str, Any],
    section_choices: list[str] | None = None,
) -> str:
    """Bind section-focus radio to canonical/blob before widget render."""
    from session_widget_safe import safe_session_assign

    def _set_focus(value: str) -> None:
        if value:
            safe_session_assign(session, "practice_focus_section", value)

    choices = [str(c) for c in (section_choices or []) if c]
    live = normalize_practice_focus_section(session.get("practice_focus_section"))
    if choices and live and not _section_focus_matches_choices(live, choices):
        live = ""

    if is_practice_locally_dirty(session) or session.get(PRACTICE_PENDING_SYNC_KEY):
        if live:
            _set_focus(live)
        elif choices:
            _set_focus(choices[0])
        return str(session.get("practice_focus_section") or "")

    canonical = canonical_practice_filters(session) or {}
    canon_section = normalize_practice_focus_section(canonical.get("practice_focus_section"))

    if canonical and live and canon_section and canon_section != live:
        merged = dict(canonical)
        merged.update(gather_practice_filters(session))
        merged["practice_focus_section"] = live
        try:
            from music_workspace_restore_mode import should_record_user_local_dirty

            local_edit = should_record_user_local_dirty(session)
        except ImportError:
            local_edit = True
        write_canonical_practice_state(
            session,
            merged,
            reason="session_section_wins",
            local_edit=local_edit,
        )
        return live

    if canon_section and (not choices or _section_focus_matches_choices(canon_section, choices)):
        _set_focus(canon_section)
        return canon_section

    if live:
        _set_focus(live)
        return live

    fallback = choices[0] if choices else ""
    if fallback:
        _set_focus(fallback)
    return fallback


def prepare_practice_page(session: dict[str, Any]) -> dict[str, Any]:

    """Reconcile Practice widgets with canonical blob before page widgets render."""

    if is_practice_locally_dirty(session) or session.get(PRACTICE_PENDING_SYNC_KEY):

        gathered = gather_practice_filters(session)

        return write_canonical_practice_state(

            session,

            gathered,

            reason="local_edit_preserve",

            local_edit=True,

        )

    if session.get(PRACTICE_RESTORED_KEY):
        canonical = canonical_practice_filters(session)
        if canonical is not None:
            return write_canonical_practice_state(session, canonical, reason="restored_preserve")

    canonical = canonical_practice_filters(session)

    live = normalize_practice_focus_section(session.get("practice_focus_section"))

    canon_section = normalize_practice_focus_section(
        (canonical or {}).get("practice_focus_section")
    )

    if canonical and live and canon_section and canon_section != live:

        merged = dict(canonical)

        merged.update(gather_practice_filters(session))

        merged["practice_focus_section"] = live

        return write_canonical_practice_state(

            session,

            merged,

            reason="session_section_wins",

            local_edit=True,

        )

    if canonical is not None:

        return write_canonical_practice_state(session, canonical, reason="canonical_preserve")



    gathered = gather_practice_filters(session)

    if _filters_have_content(gathered):

        return write_canonical_practice_state(session, gathered, reason="reconcile_on_load")

    return gathered





def commit_practice_state_from_session(session: dict[str, Any], *, reason: str = "autosave") -> dict[str, Any]:

    filters = gather_practice_filters(session)

    filters = _preserve_durable_filters_for_autosave(session, filters, reason=reason)

    return write_canonical_practice_state(session, filters, reason=reason, local_edit=False)





def flush_practice_edits(session: dict[str, Any], *, reason: str = "practice_edit") -> dict[str, Any]:

    filters = gather_practice_filters(session)

    return write_canonical_practice_state(session, filters, reason=reason, local_edit=True)





def _practice_filters_from_blob(state: dict[str, Any]) -> dict[str, Any] | None:

    if not isinstance(state, dict):

        return None

    meta = state.get(PRACTICE_STATE_KEY)

    if isinstance(meta, dict):

        filters = _normalize_filters(meta)

        if _filters_have_content(filters):

            return filters

    ws = state.get("music_workspace_state")

    if isinstance(ws, dict) and isinstance(ws.get("practice_filters"), dict):

        filters = _normalize_filters(ws["practice_filters"])

        if _filters_have_content(filters):

            return filters

    session_extra = state.get("session") if isinstance(state.get("session"), dict) else {}

    if isinstance(session_extra, dict):

        filters = _normalize_filters(

            {key: session_extra.get(key) for key in PRACTICE_SCALAR_KEYS if key in session_extra}

        )

        if _filters_have_content(filters):

            return filters

    return None





def apply_cloud_practice_state_if_allowed(
    session: dict[str, Any],
    state: dict[str, Any],
    *,
    authoritative: bool = False,
) -> bool:

    """Apply cloud/disk Practice filters when this device has no local Practice edits."""

    if is_practice_locally_dirty(session) and not authoritative:

        session["_practice_restore_skipped_reason"] = "local_dirty"

        return False

    filters = _practice_filters_from_blob(state)

    if not filters:

        session.pop(PRACTICE_RESTORED_KEY, None)

        return False

    write_canonical_practice_state(session, filters, reason="cloud_restore")

    session[PRACTICE_RESTORED_KEY] = True

    session["_practice_restore_skipped_reason"] = None

    clear_practice_local_edit(session)

    return True





def apply_practice_source_state_from_ami(

    session: dict[str, Any],

    source_state: dict[str, Any],

) -> None:

    """Restore Practice filters from Music Coach / AMI return payload."""

    if not isinstance(source_state, dict):

        return

    filters = gather_practice_filters(session)

    widgets = source_state.get("widget_params")

    if isinstance(widgets, dict):

        for key in PRACTICE_SCALAR_KEYS:

            if key in widgets and widgets[key] not in (None, ""):

                if key == "practice_notation_lines":

                    filters[key] = _normalize_int(widgets[key], filters.get("practice_notation_lines", 2))

                elif key == "practice_minutes":

                    filters[key] = normalize_practice_minutes(widgets[key])

                else:

                    filters[key] = str(widgets[key]).strip()

    write_canonical_practice_state(session, filters, reason="ami_return")

    clear_practice_local_edit(session)





def collect_practice_persistence_trace(

    session: dict[str, Any],

    *,

    payload: dict[str, Any] | None = None,

) -> dict[str, Any]:

    """Fields for ?dev=1 practice restore / overwrite diagnostics."""

    canonical = canonical_practice_filters(session) or {}

    envelope: dict[str, Any] = {}

    cloud_meta: dict[str, Any] = {}

    if isinstance(payload, dict):

        ws = payload.get("music_workspace_state")

        if isinstance(ws, dict) and isinstance(ws.get("practice_filters"), dict):

            envelope = _normalize_filters(ws["practice_filters"])

        cloud_meta = payload.get("practice_state") if isinstance(payload.get("practice_state"), dict) else {}

    return {

        "practice_canonical_groove": canonical.get("practice_groove_style", ""),

        "practice_canonical_minutes": canonical.get("practice_minutes", ""),

        "practice_filters_groove": envelope.get("practice_groove_style", ""),

        "practice_filters_minutes": envelope.get("practice_minutes", ""),

        "cloud_payload_practice_groove": cloud_meta.get("practice_groove_style", ""),

        "cloud_payload_practice_minutes": cloud_meta.get("practice_minutes", ""),

        "restored_practice_groove": session.get("practice_groove_style", ""),

        "restored_practice_minutes": session.get("practice_minutes", ""),

        "practice_dirty": is_practice_locally_dirty(session),

        "practice_restore_applied": bool(session.get(PRACTICE_RESTORED_KEY)),

        "practice_restore_skipped": session.get("_practice_restore_skipped_reason"),

        "practice_last_write": canonical.get("last_write_reason") or session.get(PRACTICE_STATE_KEY, {}).get(

            "last_write_reason"

        ),

        "practice_overwrite_source": session.get("_suite_page_overwrite_source"),

    }





def render_practice_state_debug(st: Any, session: dict[str, Any]) -> None:

    """?dev=1 sidebar panel for Practice canonical state."""

    trace = collect_practice_persistence_trace(session)

    st.sidebar.caption(

        f"**practice_state:** dirty=`{trace['practice_dirty']}` "

        f"section=`{(canonical_practice_filters(session) or {}).get('practice_focus_section', '')}` "

        f"groove=`{trace['practice_canonical_groove']}` "

        f"minutes=`{trace['practice_canonical_minutes']}`"

    )

    st.sidebar.caption(

        f"**practice widget:** groove=`{trace['restored_practice_groove']}` "

        f"minutes=`{trace['restored_practice_minutes']}` "

        f"restore=`{trace['practice_restore_applied']}`"

    )

    if trace.get("practice_last_write"):

        st.sidebar.caption(f"**practice last_write:** `{trace['practice_last_write']}`")

    if trace.get("practice_restore_skipped"):

        st.sidebar.caption(f"**practice restore skipped:** `{trace['practice_restore_skipped']}`")


