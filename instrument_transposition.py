"""Concert pitch vs written key for transposing instruments (saxophone focus)."""

from __future__ import annotations

from typing import Any

from music_theory import CHROMATIC, normalize_root, split_chord, transpose_chord

SAXOPHONE_TYPES: tuple[str, ...] = (
    "Alto saxophone (Eb)",
    "Tenor saxophone (Bb)",
    "Soprano saxophone (Bb)",
    "Baritone saxophone (Eb)",
)

SELECTED_TRANSPOSING_INSTRUMENT_KEY = "selected_transposing_instrument"
CHART_IN_INSTRUMENT_KEY_KEY = "show_chart_in_instrument_key"
# Legacy alias — kept for migration only
SAX_TYPE_SESSION_KEY = "saxophone_type"


def _migrate_transposing_instrument_state(session_state: dict) -> None:
    if SELECTED_TRANSPOSING_INSTRUMENT_KEY not in session_state:
        legacy = session_state.get(SAX_TYPE_SESSION_KEY)
        if legacy in SAXOPHONE_TYPES:
            session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = legacy
    selected = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    if selected in SAXOPHONE_TYPES:
        session_state[SAX_TYPE_SESSION_KEY] = selected


def _transpose_key_center(key: str, steps: int) -> str:
    root, suffix = split_chord(str(key or "C"))
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return str(key)
    new_root = CHROMATIC[(CHROMATIC.index(nr) + steps) % 12]
    return new_root + suffix


def sax_written_key_steps(sax_type: str) -> int:
    """Semitone shift from concert key to written key on the chart."""
    low = str(sax_type or "").lower()
    if "tenor" in low or "soprano" in low:
        return 2
    if "alto" in low or "baritone" in low or "bari" in low:
        return -3
    return -3


def written_key_for_saxophone(concert_key: str, sax_type: str) -> str:
    return _transpose_key_center(concert_key, sax_written_key_steps(sax_type))


def is_transposing_instrument(instrument: str) -> bool:
    return str(instrument or "").strip() == "Saxophone"


def sax_display_name(sax_type: str) -> str:
    low = str(sax_type or "").lower()
    if "tenor" in low:
        return "Tenor Saxophone"
    if "soprano" in low:
        return "Soprano Saxophone"
    if "baritone" in low or "bari" in low:
        return "Baritone Saxophone"
    if "alto" in low:
        return "Alto Saxophone"
    return str(sax_type or "Saxophone")


def selected_saxophone_type(session_state: dict) -> str:
    _migrate_transposing_instrument_state(session_state)
    pick = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    if pick in SAXOPHONE_TYPES:
        return str(pick)
    return SAXOPHONE_TYPES[0]


def chart_in_instrument_key(session_state: dict) -> bool:
    return bool(session_state.get(CHART_IN_INSTRUMENT_KEY_KEY, False))


def sax_transposition_blurb(
    concert_key: str,
    sax_type: str,
    *,
    chart_in_instrument_key: bool,
) -> str:
    written = written_key_for_saxophone(concert_key, sax_type)
    display = sax_display_name(sax_type)
    low = sax_type.lower()
    if "alto" in low or "baritone" in low or "bari" in low:
        inst = "Eb instrument"
    else:
        inst = "Bb instrument"
    lines = [
        f"You selected **{display}**. This is a **{inst}**.",
        f"**Concert key:** {concert_key}",
        f"**Written key for you:** {written}",
    ]
    if chart_in_instrument_key:
        lines.append(
            "Charts and notation below are transposed into your **written instrument key**."
        )
    else:
        lines.append(
            "Charts stay in **concert key**; use the written key above when you read from a chart."
        )
    return " ".join(lines)


def effective_chart_key(
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> tuple[str, str]:
    """Return (chart_key, mode_label) where mode_label is 'concert' or 'written'."""
    if is_transposing_instrument(instrument) and chart_in_instrument_key(session_state):
        sax_type = selected_saxophone_type(session_state)
        return written_key_for_saxophone(concert_key, sax_type), "written"
    return concert_key, "concert"


def render_sidebar_transposing_controls(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> None:
    """Saxophone type + concert/written key recap (sidebar)."""
    import html

    if not is_transposing_instrument(instrument):
        return
    _migrate_transposing_instrument_state(st.session_state)
    st.session_state.setdefault(SELECTED_TRANSPOSING_INSTRUMENT_KEY, SAXOPHONE_TYPES[0])
    sax_type = st.sidebar.selectbox(
        "Saxophone type",
        SAXOPHONE_TYPES,
        key=SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    )
    _migrate_transposing_instrument_state(st.session_state)
    written = written_key_for_saxophone(concert_key, sax_type)
    st.sidebar.markdown(
        f'<div class="ui-card soft" style="margin:0.5rem 0;padding:0.65rem;">'
        f"<strong>Concert key:</strong> {html.escape(concert_key)}<br>"
        f"<strong>Written key for you:</strong> {html.escape(written)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(
        "Use **Show chart in instrument key** on Practice to transpose charts; "
        "backing track stays in concert pitch."
    )


def render_practice_transposing_helper(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> tuple[str, str]:
    """Practice-page helper card; returns (chart_key, mode_label)."""
    if not is_transposing_instrument(instrument):
        return concert_key, "concert"
    sax_type = selected_saxophone_type(st.session_state)
    show_written = st.checkbox(
        "Show chart in instrument key",
        key=CHART_IN_INSTRUMENT_KEY_KEY,
    )
    st.markdown(
        '<div class="ui-card soft"><div class="ui-card-sub">'
        + sax_transposition_blurb(
            concert_key,
            sax_type,
            chart_in_instrument_key=show_written,
        )
        + "</div></div>",
        unsafe_allow_html=True,
    )
    return effective_chart_key(concert_key, instrument, st.session_state)
