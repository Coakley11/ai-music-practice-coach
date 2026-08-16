"""Compact Instrument / Level / Focus controls synced with global sidebar session keys."""

from __future__ import annotations

from typing import Any, Callable

DEFAULT_INSTRUMENT_OPTIONS: list[str] = [
    "Piano",
    "Guitar",
    "Bass",
    "Saxophone",
    "Flute",
    "Trumpet",
    "Clarinet",
    "Voice",
    "Other",
]

LEVEL_OPTIONS: list[str] = ["Beginner", "Intermediate", "Advanced"]

FOCUS_OPTIONS_BY_INSTRUMENT: dict[str, list[str]] = {
    "Guitar": [
        "Strumming",
        "Rhythm Guitar",
        "Chord Transitions",
        "Barre Chords",
        "Fingerstyle",
        "Triads",
        "Double Stops",
        "Lead Guitar",
        "Soloing",
        "Dynamics",
        "Ear Training",
    ],
    "Piano": [
        "Voicings",
        "Left-Hand Patterns",
        "Comping",
        "Voice Leading",
        "Inversions",
        "Reharmonization",
        "Dynamics",
        "Ear Training",
    ],
    "Bass": [
        "Groove",
        "Pocket",
        "Root Motion",
        "Walking Bass",
        "Syncopation",
        "Dynamics",
        "Ear Training",
    ],
    "Saxophone": [
        "Tone",
        "Scales",
        "Articulation",
        "Bebop Phrasing",
        "Breath Support",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Flute": [
        "Tone",
        "Scales",
        "Articulation",
        "Breath Support",
        "Guide Tones",
        "Phrasing",
        "Dynamics",
        "Ear Training",
    ],
    "Trumpet": [
        "Tone",
        "Endurance",
        "Articulation",
        "Range",
        "Jazz Phrasing",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Clarinet": [
        "Tone",
        "Scales",
        "Articulation",
        "Breath Support",
        "Guide Tones",
        "Dynamics",
        "Ear Training",
    ],
    "Voice": [
        "Breath Control",
        "Phrasing",
        "Pitch Accuracy",
        "Emotional Delivery",
        "Harmony Singing",
        "Vibrato",
        "Dynamics",
        "Ear Training",
    ],
}

GLOBAL_CONTROL_TRACE_KEY = "_global_control_widget_trace"


def focus_options_for_instrument(instrument: str) -> list[str]:
    """Instrument-aware Practice Focus labels.

    The first option remains the instrument default (Guitar → Strumming,
    Saxophone → Tone, …). Shared coaching focuses (Timing, Melody, Harmony,
    …) are appended so the same coaching concepts exist across instruments
    without changing that default.
    """
    try:
        from practice_focus_policy import append_shared_coaching_focuses
    except ImportError:
        def append_shared_coaching_focuses(options):  # type: ignore[misc]
            return list(options)

    base = FOCUS_OPTIONS_BY_INSTRUMENT.get(instrument)
    if base is None:
        return append_shared_coaching_focuses(
            [
                "Melody",
                "Harmony",
                "Rhythm",
                "Dynamics",
                "Improvisation",
                "Technique",
                "Ear Training",
            ]
        )
    return append_shared_coaching_focuses(list(base))


def _widget_value_for_global(
    session_state: dict,
    widget_key: str,
    global_key: str,
    options: list[str],
) -> str:
    """Pre-fill a prefixed widget from globals without mutating global keys.

    Global keys are owned by the sidebar widgets (``key=instrument`` etc.).
    Writing globals after those widgets render causes Streamlit snapback.
    """
    if not options:
        return str(session_state.get(global_key) or "")
    value = str(session_state.get(global_key) or "").strip()
    if value not in options:
        value = options[0]
    session_state[widget_key] = value
    return value


def record_global_control_widget_trace(
    session_state: dict,
    *,
    control_name: str,
    widget_key: str,
    attempted_value: str,
    source: str,
) -> None:
    """Temporary diagnostics for page-local global control widgets."""
    try:
        from practice_setup_globals import record_global_control_change

        record_global_control_change(session_state, control_name, source)
    except ImportError:
        pass
    trace = {
        "control_name": control_name,
        "widget_key": widget_key,
        "attempted_value": str(attempted_value or "").strip(),
        "source": str(source or "").strip() or "unknown",
    }
    session_state[GLOBAL_CONTROL_TRACE_KEY] = trace
    session_state[f"_global_control_last_{control_name}"] = trace


def snapshot_global_control_values(session_state: dict) -> None:
    """Record post-prepare session/canonical values for ?dev=1 trace."""
    trace = dict(session_state.get(GLOBAL_CONTROL_TRACE_KEY) or {})
    if not trace:
        return
    canonical = {}
    meta = session_state.get("active_song_state")
    if isinstance(meta, dict):
        canonical = {
            "instrument": str(meta.get("instrument") or ""),
            "level": str(meta.get("level") or ""),
            "focus": str(meta.get("focus") or ""),
            "display_key": str(meta.get("display_key") or ""),
        }
    trace["value_after_rerun"] = {
        "instrument": str(session_state.get("instrument") or ""),
        "level": str(session_state.get("level") or ""),
        "focus": str(session_state.get("focus") or ""),
        "display_key": str(session_state.get("display_key") or ""),
    }
    trace["active_song_state"] = canonical
    trace["overwrite_source"] = str(
        session_state.get("global_control_overwrite_source") or ""
    ).strip() or None
    session_state[GLOBAL_CONTROL_TRACE_KEY] = trace


def _commit_quick_control_globals(
    session_state: dict,
    *,
    instrument_widget_key: str | None = None,
    level_widget_key: str | None = None,
    focus_widget_key: str | None = None,
    source: str,
    st_module: Any | None = None,
) -> None:
    """Push prefixed widget values to canonical globals + active song blob."""
    from practice_setup_globals import commit_widget_state_to_globals

    commit_widget_state_to_globals(
        session_state,
        instrument_widget_key=instrument_widget_key,
        level_widget_key=level_widget_key,
        focus_widget_key=focus_widget_key,
    )
    try:
        from practice_setup_globals import record_global_control_change

        for field, wkey in (
            ("instrument", instrument_widget_key),
            ("level", level_widget_key),
            ("focus", focus_widget_key),
        ):
            if wkey and session_state.get(wkey) is not None:
                record_global_control_change(session_state, field, source)
    except ImportError:
        pass
    try:
        from active_song_state import mark_active_song_local_edit

        mark_active_song_local_edit(session_state)
    except ImportError:
        pass
    if st_module is not None:
        try:
            from music_persistent_state import flush_active_song_edits_and_save

            flush_active_song_edits_and_save(st_module, reason="song_edit")
            return
        except Exception:
            pass
    try:
        from active_song_state import flush_active_song_edits

        flush_active_song_edits(session_state, reason="song_edit")
    except ImportError:
        pass


def render_setup_quick_controls(
    st_module: Any,
    *,
    session_state: dict,
    key_prefix: str,
    instrument_options: list[str] | None = None,
    on_instrument_change: Callable[[], None] | None = None,
    label: str = "Quick setup",
    show_sync_caption: bool = True,
) -> tuple[str, str, str]:
    """
    Compact Instrument / Level / Focus row.

    Widget keys are prefixed; values commit to global ``instrument`` / ``level`` /
    ``focus`` via on_change (same keys as the sidebar).
    """
    instruments = instrument_options or DEFAULT_INSTRUMENT_OPTIONS
    ik = f"{key_prefix}::qc_instrument"
    lk = f"{key_prefix}::qc_level"
    fk = f"{key_prefix}::qc_focus"

    instrument = _widget_value_for_global(session_state, ik, "instrument", instruments)
    level = _widget_value_for_global(session_state, lk, "level", LEVEL_OPTIONS)
    focus_opts = focus_options_for_instrument(
        str(session_state.get("instrument") or instrument)
    )
    focus = _widget_value_for_global(session_state, fk, "focus", focus_opts)

    source_prefix = key_prefix

    def _apply_instrument() -> None:
        attempted = str(session_state.get(ik) or "")
        record_global_control_widget_trace(
            session_state,
            control_name="instrument",
            widget_key=ik,
            attempted_value=attempted,
            source=f"{source_prefix}:instrument_on_change",
        )
        _commit_quick_control_globals(
            session_state,
            instrument_widget_key=ik,
            level_widget_key=lk,
            focus_widget_key=fk,
            source=f"{source_prefix}:instrument_on_change",
            st_module=st_module,
        )
        new_inst = str(session_state.get("instrument") or "")
        try:
            from instrument_transposition import request_transposing_instrument_sync

            request_transposing_instrument_sync(session_state, new_inst)
        except ImportError:
            pass
        session_state[fk] = str(session_state.get("focus") or "")
        if on_instrument_change:
            on_instrument_change()

    def _apply_level() -> None:
        attempted = str(session_state.get(lk) or "")
        record_global_control_widget_trace(
            session_state,
            control_name="level",
            widget_key=lk,
            attempted_value=attempted,
            source=f"{source_prefix}:level_on_change",
        )
        _commit_quick_control_globals(
            session_state,
            level_widget_key=lk,
            source=f"{source_prefix}:level_on_change",
            st_module=st_module,
        )

    def _apply_focus() -> None:
        attempted = str(session_state.get(fk) or "")
        record_global_control_widget_trace(
            session_state,
            control_name="focus",
            widget_key=fk,
            attempted_value=attempted,
            source=f"{source_prefix}:focus_on_change",
        )
        _commit_quick_control_globals(
            session_state,
            focus_widget_key=fk,
            source=f"{source_prefix}:focus_on_change",
            st_module=st_module,
        )

    st_module.markdown(
        '<div class="setup-quick-row">',
        unsafe_allow_html=True,
    )
    if label:
        st_module.caption(label)
    c1, c2, c3 = st_module.columns(3)
    with c1:
        st_module.selectbox(
            "Instrument",
            instruments,
            key=ik,
            on_change=_apply_instrument,
            label_visibility="visible",
        )
    with c2:
        st_module.selectbox(
            "Level",
            LEVEL_OPTIONS,
            key=lk,
            on_change=_apply_level,
        )
    with c3:
        st_module.selectbox(
            "Focus",
            focus_options_for_instrument(str(session_state.get("instrument") or instrument)),
            key=fk,
            on_change=_apply_focus,
        )
    st_module.markdown("</div>", unsafe_allow_html=True)
    if show_sync_caption:
        st_module.caption(
            "Synced with the sidebar — changes apply across Practice, Backing Track, and Creative Lab."
        )

    return (
        str(session_state.get("instrument", instrument)),
        str(session_state.get("level", level)),
        str(session_state.get("focus", focus)),
    )
