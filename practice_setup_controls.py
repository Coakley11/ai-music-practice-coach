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


def focus_options_for_instrument(instrument: str) -> list[str]:
    return FOCUS_OPTIONS_BY_INSTRUMENT.get(
        instrument,
        [
            "Melody",
            "Harmony",
            "Rhythm",
            "Dynamics",
            "Improvisation",
            "Technique",
            "Ear Training",
        ],
    )


def _sync_widget_from_global(
    session_state: dict,
    widget_key: str,
    global_key: str,
    options: list[str],
) -> str:
    value = str(session_state.get(global_key) or "")
    if value not in options:
        value = options[0]
        session_state[global_key] = value
    session_state[widget_key] = value
    return value


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

  Widget keys are prefixed; values sync to session_state instrument / level / focus
  (same keys as the sidebar).
  """
    instruments = instrument_options or DEFAULT_INSTRUMENT_OPTIONS
    ik = f"{key_prefix}::qc_instrument"
    lk = f"{key_prefix}::qc_level"
    fk = f"{key_prefix}::qc_focus"

    instrument = _sync_widget_from_global(session_state, ik, "instrument", instruments)
    level = _sync_widget_from_global(session_state, lk, "level", LEVEL_OPTIONS)
    focus_opts = focus_options_for_instrument(instrument)
    focus = _sync_widget_from_global(session_state, fk, "focus", focus_opts)

    def _apply_instrument() -> None:
        session_state["instrument"] = session_state[ik]
        try:
            from instrument_transposition import request_transposing_instrument_sync

            request_transposing_instrument_sync(session_state, session_state["instrument"])
        except ImportError:
            pass
        opts = focus_options_for_instrument(session_state["instrument"])
        if session_state.get("focus") not in opts:
            session_state["focus"] = opts[0]
        session_state[fk] = session_state["focus"]
        if on_instrument_change:
            on_instrument_change()

    def _apply_level() -> None:
        session_state["level"] = session_state[lk]

    def _apply_focus() -> None:
        session_state["focus"] = session_state[fk]

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
            focus_options_for_instrument(session_state.get("instrument", instrument)),
            key=fk,
            on_change=_apply_focus,
        )
    st_module.markdown("</div>", unsafe_allow_html=True)
    if show_sync_caption:
        st_module.caption("Synced with the sidebar — changes apply across Practice, Backing Track, and Creative Lab.")

    return (
        str(session_state.get("instrument", instrument)),
        str(session_state.get("level", level)),
        str(session_state.get("focus", focus)),
    )
