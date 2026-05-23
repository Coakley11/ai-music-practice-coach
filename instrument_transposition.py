"""Concert vs written key — single source of truth for all studio pages."""

from __future__ import annotations

from typing import Any

from music_theory import CHROMATIC, normalize_root, split_chord

SAXOPHONE_TYPES: tuple[str, ...] = (
    "Alto saxophone (Eb)",
    "Tenor saxophone (Bb)",
    "Soprano saxophone (Bb)",
    "Baritone saxophone (Eb)",
)

BB_INSTRUMENT_TYPES: tuple[str, ...] = (
    "Bb Trumpet",
    "Bb Clarinet",
)

SELECTED_TRANSPOSING_INSTRUMENT_KEY = "selected_transposing_instrument"
PENDING_SELECTED_TRANSPOSING_INSTRUMENT = "_pending_selected_transposing_instrument"
CHART_IN_INSTRUMENT_KEY_KEY = "show_chart_in_instrument_key"
CONCERT_KEY_SESSION_KEY = "concert_practice_key"
SAX_TYPE_SESSION_KEY = "saxophone_type"

# Semitone shift: concert key center → written key center
TRANSPOSING_SEMITONE_STEPS: dict[str, int] = {
    "Alto saxophone (Eb)": -3,
    "Tenor saxophone (Bb)": 2,
    "Soprano saxophone (Bb)": 2,
    "Baritone saxophone (Eb)": -3,
    "Alto Sax (Eb)": -3,
    "Tenor Sax (Bb)": 2,
    "Soprano Sax (Bb)": 2,
    "Bari Sax (Eb)": -3,
    "Bb Trumpet": 2,
    "Bb Clarinet": 2,
}


def _transpose_key_center(key: str, steps: int) -> str:
    root, suffix = split_chord(str(key or "C"))
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return str(key)
    new_root = CHROMATIC[(CHROMATIC.index(nr) + steps) % 12]
    return new_root + suffix


def transposing_instrument_names() -> tuple[str, ...]:
    return ("Saxophone", "Trumpet", "Clarinet")


def is_transposing_instrument(instrument: str) -> bool:
    return str(instrument or "").strip() in transposing_instrument_names()


def options_for_instrument(instrument: str) -> list[str]:
    inst = str(instrument or "").strip()
    if inst == "Saxophone":
        return list(SAXOPHONE_TYPES)
    if inst == "Trumpet":
        return ["Bb Trumpet"]
    if inst == "Clarinet":
        return ["Bb Clarinet"]
    return []


def default_transposing_type(instrument: str) -> str:
    opts = options_for_instrument(instrument)
    return opts[0] if opts else ""


def _migrate_transposing_instrument_state(session_state: dict) -> None:
    """One-time legacy migration — only when the widget key is not yet set."""
    if SELECTED_TRANSPOSING_INSTRUMENT_KEY in session_state:
        selected = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
        if selected in SAXOPHONE_TYPES:
            session_state[SAX_TYPE_SESSION_KEY] = selected
        return
    legacy = session_state.get(SAX_TYPE_SESSION_KEY)
    if legacy in SAXOPHONE_TYPES:
        session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = legacy


def apply_pending_transposing_instrument(session_state: dict, instrument: str) -> None:
    """Apply pending type or fix invalid value — call only BEFORE the type selectbox."""
    if not is_transposing_instrument(instrument):
        return
    _migrate_transposing_instrument_state(session_state)
    opts = options_for_instrument(instrument)
    pending = session_state.pop(PENDING_SELECTED_TRANSPOSING_INSTRUMENT, None)
    if pending in opts:
        session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = pending
        return
    current = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    if current not in opts:
        session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = default_transposing_type(instrument)


def request_transposing_instrument_sync(session_state: dict, instrument: str) -> None:
    """Queue type reset when instrument changes (safe after widgets exist)."""
    if not is_transposing_instrument(instrument):
        return
    opts = options_for_instrument(instrument)
    current = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    if current not in opts:
        session_state[PENDING_SELECTED_TRANSPOSING_INSTRUMENT] = default_transposing_type(instrument)


def ensure_transposing_defaults(session_state: dict, instrument: str) -> None:
    """Backward-compatible alias — queues sync, never mutates widget keys mid-run."""
    request_transposing_instrument_sync(session_state, instrument)


def selected_transposing_type(session_state: dict, instrument: str) -> str:
    """Read selected type without writing widget session keys."""
    if not is_transposing_instrument(instrument):
        return ""
    opts = options_for_instrument(instrument)
    pick = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY, "")
    if pick in opts:
        return str(pick)
    return default_transposing_type(instrument)


def chart_in_instrument_key(session_state: dict) -> bool:
    return bool(session_state.get(CHART_IN_INSTRUMENT_KEY_KEY, False))


def written_key_for_type(concert_key: str, transposing_type: str) -> str:
    steps = TRANSPOSING_SEMITONE_STEPS.get(transposing_type, 0)
    return _transpose_key_center(concert_key, steps)


def written_key_for_instrument(
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> str:
    if not is_transposing_instrument(instrument):
        return concert_key
    t_type = selected_transposing_type(session_state, instrument)
    return written_key_for_type(concert_key, t_type)


def instrument_display_name(transposing_type: str, instrument: str = "") -> str:
    low = str(transposing_type or "").lower()
    if "tenor" in low:
        return "Tenor Saxophone"
    if "soprano" in low:
        return "Soprano Saxophone"
    if "baritone" in low or "bari" in low:
        return "Baritone Saxophone"
    if "alto" in low:
        return "Alto Saxophone"
    if "trumpet" in low:
        return "Trumpet"
    if "clarinet" in low:
        return "Clarinet"
    return str(instrument or transposing_type or "Instrument")


def is_eb_instrument(transposing_type: str) -> bool:
    low = str(transposing_type or "").lower()
    return "alto" in low or "baritone" in low or "bari" in low or "(eb)" in low


def transposition_blurb(
    concert_key: str,
    instrument: str,
    session_state: dict,
    *,
    chart_in_instrument_key: bool,
) -> str:
    t_type = selected_transposing_type(session_state, instrument)
    written = written_key_for_type(concert_key, t_type)
    display = instrument_display_name(t_type, instrument)
    inst_label = "Eb instrument" if is_eb_instrument(t_type) else "Bb instrument"
    lines = [
        f"**{display}** ({inst_label}).",
        f"**Concert key:** {concert_key}",
        f"**Written key for you:** {written}",
    ]
    if chart_in_instrument_key:
        lines.append(
            "Charts, exercises, notation, and backing chord view use your **written key** app-wide."
        )
    else:
        lines.append(
            "Charts stay in **concert key**; use the written key above when reading or fingering."
        )
    return " ".join(lines)


def effective_chart_key(
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> tuple[str, str]:
    """Return (chart_key, mode_label) where mode_label is 'concert' or 'written'."""
    if is_transposing_instrument(instrument) and chart_in_instrument_key(session_state):
        t_type = selected_transposing_type(session_state, instrument)
        return written_key_for_type(concert_key, t_type), "written"
    return concert_key, "concert"


def resolve_practice_keys(
    session_state: dict,
    concert_key: str,
    instrument: str,
) -> dict[str, str]:
    """Single source of truth for concert, written, chart, and UI display keys."""
    concert_key = str(concert_key or "C")
    session_state[CONCERT_KEY_SESSION_KEY] = concert_key
    written = written_key_for_instrument(concert_key, instrument, session_state)
    chart_key, mode = effective_chart_key(concert_key, instrument, session_state)
    global_display = chart_key if mode == "written" else concert_key
    return {
        "concert_key": concert_key,
        "written_key": written,
        "chart_key": chart_key,
        "global_display_key": global_display,
        "chart_key_mode": mode,
        "transposing_type": selected_transposing_type(session_state, instrument)
        if is_transposing_instrument(instrument)
        else "",
    }


# Backward-compatible aliases
def sax_written_key_steps(sax_type: str) -> int:
    return TRANSPOSING_SEMITONE_STEPS.get(sax_type, -3)


def written_key_for_saxophone(concert_key: str, sax_type: str) -> str:
    return written_key_for_type(concert_key, sax_type)


def selected_saxophone_type(session_state: dict) -> str:
    return selected_transposing_type(session_state, "Saxophone")


def sax_display_name(sax_type: str) -> str:
    return instrument_display_name(sax_type, "Saxophone")


def sax_transposition_blurb(
    concert_key: str,
    sax_type: str,
    *,
    chart_in_instrument_key: bool,
) -> str:
    written = written_key_for_type(concert_key, sax_type)
    display = instrument_display_name(sax_type, "Saxophone")
    inst_label = "Eb instrument" if is_eb_instrument(sax_type) else "Bb instrument"
    lines = [
        f"You selected **{display}**. This is a **{inst_label}**.",
        f"**Concert key:** {concert_key}",
        f"**Written key for you:** {written}",
    ]
    if chart_in_instrument_key:
        lines.append("Charts and notation use your **written instrument key**.")
    else:
        lines.append("Charts stay in **concert key**; finger in your written key.")
    return " ".join(lines)


def render_sidebar_transposing_controls(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> None:
    """Global transposing controls (sidebar) — all pages."""
    import html

    if not is_transposing_instrument(instrument):
        return

    ensure_transposing_defaults(st.session_state, instrument)
    opts = options_for_instrument(instrument)
    st.sidebar.selectbox(
        "Transposing instrument type",
        opts,
        key=SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    )
    written = written_key_for_instrument(concert_key, instrument, st.session_state)
    st.sidebar.checkbox(
        "Show charts in instrument key",
        key=CHART_IN_INSTRUMENT_KEY_KEY,
        help="When on, chord charts, coach, notation, and backing chord view use your written key everywhere.",
    )
    t_type = selected_transposing_type(st.session_state, instrument)
    st.sidebar.markdown(
        f'<div class="ui-card soft" style="margin:0.5rem 0;padding:0.65rem;">'
        f"<strong>Concert key:</strong> {html.escape(concert_key)}<br>"
        f"<strong>Written key:</strong> {html.escape(written)}<br>"
        f"<small>{html.escape(t_type)}</small>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_transposing_info_card(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> tuple[str, str]:
    """Compact transposing recap (any page); returns (chart_key, mode)."""
    if not is_transposing_instrument(instrument):
        return concert_key, "concert"
    show_written = chart_in_instrument_key(st.session_state)
    st.markdown(
        '<div class="ui-card soft"><div class="ui-card-sub">'
        + transposition_blurb(
            concert_key,
            instrument,
            st.session_state,
            chart_in_instrument_key=show_written,
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )
    return effective_chart_key(concert_key, instrument, st.session_state)


def render_practice_transposing_helper(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> tuple[str, str]:
    """Practice page — uses global sidebar settings (no duplicate checkbox)."""
    return render_transposing_info_card(st, concert_key=concert_key, instrument=instrument)


# --- Public aliases (documented API / legacy names) ---

# For transpose_chord()-style shifts (matches streamlit TRANSPOSING_INSTRUMENTS labels)
TRANSPOSING_INSTRUMENTS: dict[str, int] = {
    "Alto saxophone (Eb)": 9,
    "Tenor saxophone (Bb)": 2,
    "Soprano saxophone (Bb)": 2,
    "Baritone saxophone (Eb)": 9,
    "Alto Sax (Eb)": 9,
    "Tenor Sax (Bb)": 2,
    "Soprano Sax (Bb)": 2,
    "Bari Sax (Eb)": 9,
    "Bb Trumpet": 2,
    "Bb Clarinet": 2,
}


def get_written_key_for_instrument(
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> str:
    return written_key_for_instrument(concert_key, instrument, session_state)


def get_instrument_transposition(
    instrument: str,
    session_state: dict,
    *,
    concert_key: str = "C",
) -> dict[str, str | int | bool]:
    """Metadata for the active transposing instrument (type, steps, written key)."""
    t_type = selected_transposing_type(session_state, instrument) if is_transposing_instrument(instrument) else ""
    steps = TRANSPOSING_SEMITONE_STEPS.get(t_type, 0)
    written = written_key_for_instrument(concert_key, instrument, session_state)
    chart_key, mode = effective_chart_key(concert_key, instrument, session_state)
    return {
        "instrument": instrument,
        "transposing_type": t_type,
        "concert_key": concert_key,
        "written_key": written,
        "chart_key": chart_key,
        "chart_key_mode": mode,
        "semitone_steps": steps,
        "show_charts_in_instrument_key": chart_in_instrument_key(session_state),
        "is_eb": is_eb_instrument(t_type) if t_type else False,
    }


def transpose_chord_for_instrument(
    chord: str,
    instrument: str,
    session_state: dict,
) -> str:
    """Transpose a chord symbol into written key for the selected transposing type."""
    from music_theory import transpose_chord

    if not is_transposing_instrument(instrument):
        return chord
    t_type = selected_transposing_type(session_state, instrument)
    steps = TRANSPOSING_INSTRUMENTS.get(t_type, 0)
    return transpose_chord(chord, steps)


def transpose_song_for_instrument(
    session_state: dict,
    concert_key: str,
    instrument: str,
) -> dict[str, str]:
    """Resolve keys for transposing a song chart (alias for resolve_practice_keys)."""
    return resolve_practice_keys(session_state, concert_key, instrument)


def apply_instrument_key_display(
    session_state: dict,
    concert_key: str,
    instrument: str,
) -> dict[str, str]:
    """Apply global instrument-key display rules; returns key context dict."""
    return resolve_practice_keys(session_state, concert_key, instrument)


__all__ = [
    "BB_INSTRUMENT_TYPES",
    "CHART_IN_INSTRUMENT_KEY_KEY",
    "CONCERT_KEY_SESSION_KEY",
    "SAXOPHONE_TYPES",
    "SAX_TYPE_SESSION_KEY",
    "SELECTED_TRANSPOSING_INSTRUMENT_KEY",
    "TRANSPOSING_INSTRUMENTS",
    "TRANSPOSING_SEMITONE_STEPS",
    "apply_instrument_key_display",
    "chart_in_instrument_key",
    "default_transposing_type",
    "effective_chart_key",
    "apply_pending_transposing_instrument",
    "ensure_transposing_defaults",
    "request_transposing_instrument_sync",
    "PENDING_SELECTED_TRANSPOSING_INSTRUMENT",
    "get_instrument_transposition",
    "get_written_key_for_instrument",
    "instrument_display_name",
    "is_eb_instrument",
    "is_transposing_instrument",
    "options_for_instrument",
    "render_practice_transposing_helper",
    "render_sidebar_transposing_controls",
    "render_transposing_info_card",
    "resolve_practice_keys",
    "sax_display_name",
    "sax_transposition_blurb",
    "sax_written_key_steps",
    "selected_saxophone_type",
    "selected_transposing_type",
    "transposing_instrument_names",
    "transpose_chord_for_instrument",
    "transpose_song_for_instrument",
    "transposition_blurb",
    "written_key_for_instrument",
    "written_key_for_saxophone",
    "written_key_for_type",
]
