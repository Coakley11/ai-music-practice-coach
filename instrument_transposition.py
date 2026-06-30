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
WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY = "_chart_written_key_instrument_anchor"
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

# Instrument-family metadata (display / education)
TRANSPOSING_INSTRUMENT_METADATA: dict[str, dict[str, str | int]] = {
    "Trumpet": {"family": "Bb", "semitones_up": 2},
    "Tenor saxophone": {"family": "Bb", "semitones_up": 2},
    "Soprano saxophone": {"family": "Bb", "semitones_up": 2},
    "Alto saxophone": {"family": "Eb", "semitones_up": 9},
    "Baritone saxophone": {"family": "Eb", "semitones_up": 9},
    "Clarinet": {"family": "Bb", "semitones_up": 2},
    "Saxophone": {"family": "varies", "semitones_up": 0},
}

# Chord-symbol transpose steps (matches music_theory.transpose_chord labels)
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
    "Trumpet": 2,
    "Clarinet": 2,
    "Tenor saxophone": 2,
    "Soprano saxophone": 2,
    "Alto saxophone": 9,
    "Baritone saxophone": 9,
}

USER_TRANSPOSING_INSTRUMENTS: tuple[str, ...] = ("Saxophone", "Trumpet", "Clarinet")


_FLAT_PITCH_CLASSES: tuple[str, ...] = (
    "C",
    "Db",
    "D",
    "Eb",
    "E",
    "F",
    "Gb",
    "G",
    "Ab",
    "A",
    "Bb",
    "B",
)
_SHARP_PITCH_CLASSES: tuple[str, ...] = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)
_NATURAL_PITCH_CLASSES: frozenset[str] = frozenset(
    {"C", "D", "E", "F", "G", "A", "B"}
)


def _reference_spelling_mode(reference_key: str) -> str:
    """flat | sharp | natural — follow concert/display key accidental family."""
    from music_theory import reference_spelling_mode

    return reference_spelling_mode(reference_key)


def _spell_pitch_class(pitch_idx: int, *, mode: str) -> str:
    idx = int(pitch_idx) % 12
    if mode == "flat":
        return _FLAT_PITCH_CLASSES[idx]
    if mode == "sharp":
        return _SHARP_PITCH_CLASSES[idx]
    natural = _FLAT_PITCH_CLASSES[idx]
    if natural in _NATURAL_PITCH_CLASSES:
        return natural
    return _FLAT_PITCH_CLASSES[idx]


def _transpose_key_center(
    key: str,
    steps: int,
    *,
    reference_key: str | None = None,
) -> str:
    root, suffix = split_chord(str(key or "C"))
    nr = normalize_root(root)
    if nr not in CHROMATIC:
        return str(key)
    ref = str(reference_key if reference_key is not None else key)
    mode = _reference_spelling_mode(ref)
    new_idx = (CHROMATIC.index(nr) + steps) % 12
    new_root = _spell_pitch_class(new_idx, mode=mode)
    return new_root + suffix


def transposing_instrument_names() -> tuple[str, ...]:
    return USER_TRANSPOSING_INSTRUMENTS


def is_transposing_instrument(instrument: str) -> bool:
    inst = str(instrument or "").strip()
    return inst in USER_TRANSPOSING_INSTRUMENTS or inst in TRANSPOSING_INSTRUMENT_METADATA


def semitone_steps_for_label(label: str) -> int:
    """Semitone steps for chord-symbol transposition (type label or instrument name)."""
    key = str(label or "").strip()
    if key in TRANSPOSING_INSTRUMENTS:
        return int(TRANSPOSING_INSTRUMENTS[key])
    meta = TRANSPOSING_INSTRUMENT_METADATA.get(key)
    if meta:
        return int(meta.get("semitones_up", 0))
    return int(TRANSPOSING_SEMITONE_STEPS.get(key, 0))


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
    try:
        from active_song_state import rehydrate_transposing_sidebar_from_canonical

        rehydrate_transposing_sidebar_from_canonical(session_state)
    except ImportError:
        pass
    _migrate_transposing_instrument_state(session_state)
    opts = options_for_instrument(instrument)
    pending = session_state.pop(PENDING_SELECTED_TRANSPOSING_INSTRUMENT, None)
    if pending in opts:
        session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = pending
        return
    current = session_state.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY)
    if current not in opts:
        try:
            from active_song_state import ACTIVE_SONG_STATE_KEY

            meta = session_state.get(ACTIVE_SONG_STATE_KEY)
            if isinstance(meta, dict):
                restored = str(meta.get(SELECTED_TRANSPOSING_INSTRUMENT_KEY) or "").strip()
                if restored in opts:
                    session_state[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = restored
                    return
        except ImportError:
            pass
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


def sync_written_key_instrument_anchor(session_state: dict, instrument: str) -> None:
    """Reset chart helper modes when the global instrument changes."""
    instrument = str(instrument or "").strip()
    anchor = str(session_state.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY) or "").strip()
    if not anchor:
        session_state[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = instrument
        return
    if anchor == instrument:
        return
    session_state[CHART_IN_INSTRUMENT_KEY_KEY] = False
    try:
        from guitar_capo import CAPO_ENABLED_KEY, sync_capo_from_practice_display_key

        session_state[CAPO_ENABLED_KEY] = False
        practice = str(
            session_state.get("display_key") or session_state.get("concert_key") or "C"
        ).strip() or "C"
        sync_capo_from_practice_display_key(session_state, practice)
    except ImportError:
        pass
    try:
        from backing_musical_state import clear_stale_chart_session_keys

        clear_stale_chart_session_keys(session_state)
    except ImportError:
        session_state.pop("_creative_chart_display_key", None)
    session_state[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = instrument


def preserve_written_key_on_display_key_change(session_state: dict) -> None:
    """Display / practice key changes must never clear written-key mode (explicit no-op)."""
    _ = session_state


def chart_transpose_cache_signature(
    session_state: dict,
    instrument: str,
) -> tuple[bool, str]:
    """Extra tuple fields for chart caches when concert or written mode changes."""
    if not is_transposing_instrument(instrument):
        return False, ""
    return (
        chart_in_instrument_key(session_state),
        selected_transposing_type(session_state, instrument),
    )


def written_key_for_type(concert_key: str, transposing_type: str) -> str:
    steps = TRANSPOSING_SEMITONE_STEPS.get(transposing_type, 0)
    if not steps:
        return str(concert_key or "C")
    natural = _transpose_key_center(concert_key, steps, reference_key=concert_key)
    sharp = _transpose_key_center(concert_key, steps, reference_key="E")
    if natural == sharp:
        return natural
    root_nat, _ = split_chord(natural)
    root_shp, _ = split_chord(sharp)
    from music_theory import key_is_minor, normalize_root, reference_spelling_mode

    nr_nat = normalize_root(root_nat)
    nr_shp = normalize_root(root_shp)
    if nr_nat in {"Gb", "Cb"} and nr_shp in {"F#", "B"}:
        return sharp
    if key_is_minor(concert_key) and reference_spelling_mode(concert_key) in {"sharp", "natural"}:
        if nr_shp in {"F#", "C#", "G#", "D#"}:
            return sharp
    return natural


def transpose_key_for_instrument(
    concert_key: str,
    instrument: str,
    session_state: dict | None = None,
) -> str:
    """Return written key for the user's instrument (concert → written)."""
    session_state = session_state if session_state is not None else {}
    if not is_transposing_instrument(instrument):
        return str(concert_key or "C")
    return written_key_for_instrument(concert_key, instrument, session_state)


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


def get_instrument_transposition_simple(instrument: str) -> dict[str, str | int]:
    """Metadata for a transposing instrument name (no session state)."""
    inst = str(instrument or "").strip()
    meta = TRANSPOSING_INSTRUMENT_METADATA.get(inst)
    if meta:
        return {
            "family": str(meta.get("family", "Concert")),
            "semitones_up": int(meta.get("semitones_up", 0)),
        }
    if inst in USER_TRANSPOSING_INSTRUMENTS:
        default_type = default_transposing_type(inst)
        return {
            "family": "Eb" if is_eb_instrument(default_type) else "Bb",
            "semitones_up": semitone_steps_for_label(default_type),
            "default_type": default_type,
        }
    return {"family": "Concert", "semitones_up": 0}


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


def charts_shown_in_key(
    concert_key: str,
    written_key: str,
    *,
    show_in_instrument_key: bool,
) -> str:
    """Key label for charts — written when instrument-key mode is on, else concert."""
    return written_key if show_in_instrument_key else concert_key


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


def effective_practice_key(
    session_state: dict,
    concert_key: str,
    instrument: str,
    *,
    capo_shape_key: str | None = None,
) -> str:
    """Authoritative key for player-facing Practice coaching and scale text.

    Matches the chart key the musician reads (written or concert), with an
    optional guitar capo shape-key override when capo is enabled.
    """
    chart_key, _ = effective_chart_key(concert_key, instrument, session_state)
    if capo_shape_key and str(instrument or "").strip() == "Guitar":
        return str(capo_shape_key).strip() or chart_key
    return chart_key


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
    capo_shape: str | None = None
    try:
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY

        if str(instrument or "").strip() == "Guitar" and session_state.get(CAPO_ENABLED_KEY):
            capo_shape = str(session_state.get(CAPO_SHAPE_KEY) or "").strip() or None
    except ImportError:
        capo_shape = None
    if capo_shape:
        chart_key = capo_shape
        mode = "written"
    global_display = concert_key
    practice_key = effective_practice_key(
        session_state,
        concert_key,
        instrument,
        capo_shape_key=capo_shape,
    )
    return {
        "concert_key": concert_key,
        "written_key": written,
        "chart_key": chart_key,
        "effective_practice_key": practice_key,
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


def render_sidebar_transposing_widgets(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
    on_written_key_change: Any | None = None,
    on_transposing_type_change: Any | None = None,
    **_: Any,
) -> None:
    """App-wide transposing controls (sidebar) — persist across all studio pages."""
    if not is_transposing_instrument(instrument):
        return
    try:
        from active_song_state import rehydrate_transposing_sidebar_from_canonical

        rehydrate_transposing_sidebar_from_canonical(st.session_state)
    except ImportError:
        pass
    apply_pending_transposing_instrument(st.session_state, instrument)
    if instrument == "Saxophone":
        sax_kwargs: dict[str, Any] = {
            "help": "Applies to charts, backing chord view, and notation on every page.",
        }
        if on_transposing_type_change is not None:
            sax_kwargs["on_change"] = on_transposing_type_change
        st.sidebar.selectbox(
            "Saxophone type",
            list(SAXOPHONE_TYPES),
            format_func=lambda t: instrument_display_name(str(t), "Saxophone"),
            key=SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            **sax_kwargs,
        )
    checkbox_kwargs: dict[str, Any] = {
        "help": (
            "When on, charts stay in your instrument's written key while you change "
            "Practice / Concert Key. Turn off to read charts in concert pitch."
        ),
    }
    if on_written_key_change is not None:
        checkbox_kwargs["on_change"] = on_written_key_change
    st.sidebar.checkbox(
        "Show chart in written key for instrument",
        key=CHART_IN_INSTRUMENT_KEY_KEY,
        **checkbox_kwargs,
    )


def render_sidebar_transposing_recap(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> None:
    """Read-only transposing summary in sidebar."""
    import html

    if not is_transposing_instrument(instrument):
        return
    written = written_key_for_instrument(concert_key, instrument, st.session_state)
    t_type = selected_transposing_type(st.session_state, instrument)
    show_written = chart_in_instrument_key(st.session_state)
    charts_in = charts_shown_in_key(
        concert_key,
        written,
        show_in_instrument_key=show_written,
    )
    st.sidebar.markdown(
        f'<div class="ui-card soft ui-transposing-recap" style="margin:0.5rem 0;padding:0.65rem;">'
        f"<strong>Concert key:</strong> {html.escape(concert_key)}<br>"
        f"<strong>Written key:</strong> {html.escape(written)}<br>"
        f"<strong>Charts shown in:</strong> {html.escape(charts_in)}<br>"
        f"<small class=\"ui-transposing-recap-meta\">{html.escape(instrument_display_name(t_type, instrument))}</small>"
        f"{' · written charts on' if show_written else ' · concert charts'}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_sidebar_transposing_controls(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
    on_written_key_change: Any | None = None,
    on_transposing_type_change: Any | None = None,
    **_: Any,
) -> None:
    """Sidebar type selector, written-key toggle, and recap (all pages)."""
    render_sidebar_transposing_widgets(
        st,
        concert_key=concert_key,
        instrument=instrument,
        on_written_key_change=on_written_key_change,
        on_transposing_type_change=on_transposing_type_change,
    )
    render_sidebar_transposing_recap(st, concert_key=concert_key, instrument=instrument)


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


def render_transposing_key_summary_card(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> None:
    """White summary card — concert, instrument, written, and charts-shown keys."""
    import html

    if not is_transposing_instrument(instrument):
        return
    t_type = selected_transposing_type(session_state, instrument)
    written = written_key_for_type(concert_key, t_type)
    inst_name = instrument_display_name(t_type, instrument)
    show_written = chart_in_instrument_key(session_state)
    charts_in = charts_shown_in_key(
        concert_key,
        written,
        show_in_instrument_key=show_written,
    )
    mode_label = "ON" if show_written else "OFF"
    st.markdown(
        f'<div class="ui-card soft" style="margin:0.65rem 0;">'
        f'<p class="ui-card-title">Chart key / transposition</p>'
        f'<p class="ui-card-sub" style="margin:0;line-height:1.55;">'
        f"<strong>Concert key:</strong> {html.escape(concert_key)}<br>"
        f"<strong>Instrument:</strong> {html.escape(inst_name)}<br>"
        f"<strong>Written key:</strong> {html.escape(written)}<br>"
        f"<strong>Show charts in instrument key:</strong> {mode_label}<br>"
        f"<strong>Charts shown in:</strong> {html.escape(charts_in)}"
        f"</p></div>",
        unsafe_allow_html=True,
    )


def render_practice_transposing_controls(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> None:
    """Practice-page transposing recap (controls live in the sidebar for all pages)."""
    if not is_transposing_instrument(instrument):
        return

    with st.expander(
        "🎷 Transposing instrument / instrument key helper",
        expanded=True,
    ):
        if instrument == "Trumpet":
            st.markdown("**Trumpet** — **Bb instrument** (reads in written key above concert pitch).")
        elif instrument == "Clarinet":
            st.markdown("**Clarinet** — **Bb instrument** (reads in written key above concert pitch).")
        else:
            st.markdown(
                "**Saxophone type** and **Show chart in written key for instrument** "
                "are in the **sidebar** and stay on while you change Practice Key."
            )
        show_written = chart_in_instrument_key(st.session_state)
        written = written_key_for_instrument(concert_key, instrument, st.session_state)
        chart_k, mode = effective_chart_key(concert_key, instrument, st.session_state)
        st.caption(
            f"Charts now use **{chart_k}** ({mode}). "
            f"Concert **{concert_key}** · written **{written}**."
            + (
                " Written-key mode stays on when you change Practice / Concert Key."
                if show_written
                else " Enable written-key mode in the sidebar to transpose all charts."
            )
        )

    render_transposing_key_summary_card(
        st,
        concert_key=concert_key,
        instrument=instrument,
        session_state=st.session_state,
    )


def render_practice_transposing_panel(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> dict[str, str]:
    """Practice-page transposing controls (single widget source for type + checkbox)."""
    if is_transposing_instrument(instrument):
        apply_pending_transposing_instrument(st.session_state, instrument)
        render_practice_transposing_controls(
            st,
            concert_key=concert_key,
            instrument=instrument,
        )
    return resolve_practice_keys(st.session_state, concert_key, instrument)


def render_practice_transposing_helper(
    st: Any,
    *,
    concert_key: str,
    instrument: str,
) -> tuple[str, str]:
    """Backward-compatible wrapper."""
    ctx = render_practice_transposing_panel(st, concert_key=concert_key, instrument=instrument)
    return ctx["chart_key"], ctx["chart_key_mode"]


def get_written_key_for_instrument(
    concert_key: str,
    instrument: str,
    session_state: dict,
) -> str:
    return written_key_for_instrument(concert_key, instrument, session_state)


def get_instrument_transposition(
    instrument: str,
    session_state: dict | None = None,
    *,
    concert_key: str = "C",
) -> dict[str, str | int | bool]:
    """Metadata for the active transposing instrument (type, steps, written key)."""
    session_state = session_state if session_state is not None else {}
    if not is_transposing_instrument(instrument):
        base = get_instrument_transposition_simple(instrument)
        return {
            "instrument": instrument,
            "transposing_type": "",
            "concert_key": concert_key,
            "written_key": concert_key,
            "chart_key": concert_key,
            "chart_key_mode": "concert",
            "semitone_steps": int(base.get("semitones_up", 0)),
            "show_charts_in_instrument_key": False,
            "is_eb": False,
            "family": str(base.get("family", "Concert")),
        }
    t_type = selected_transposing_type(session_state, instrument)
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
    *,
    concert_key: str | None = None,
) -> str:
    """Transpose a chord symbol into written key for the selected transposing type."""
    from music_theory import transpose_chord

    if not is_transposing_instrument(instrument):
        return chord
    t_type = selected_transposing_type(session_state, instrument)
    steps = semitone_steps_for_label(t_type)
    ref = str(
        concert_key
        or session_state.get(CONCERT_KEY_SESSION_KEY)
        or session_state.get("display_key")
        or "C"
    )
    return transpose_chord(chord, steps, reference_key=ref)


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
    "WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY",
    "CONCERT_KEY_SESSION_KEY",
    "PENDING_SELECTED_TRANSPOSING_INSTRUMENT",
    "SAXOPHONE_TYPES",
    "SAX_TYPE_SESSION_KEY",
    "SELECTED_TRANSPOSING_INSTRUMENT_KEY",
    "TRANSPOSING_INSTRUMENTS",
    "TRANSPOSING_INSTRUMENT_METADATA",
    "TRANSPOSING_SEMITONE_STEPS",
    "USER_TRANSPOSING_INSTRUMENTS",
    "apply_instrument_key_display",
    "apply_pending_transposing_instrument",
    "chart_in_instrument_key",
    "chart_transpose_cache_signature",
    "charts_shown_in_key",
    "default_transposing_type",
    "effective_chart_key",
    "ensure_transposing_defaults",
    "get_instrument_transposition",
    "get_instrument_transposition_simple",
    "get_written_key_for_instrument",
    "instrument_display_name",
    "is_eb_instrument",
    "is_transposing_instrument",
    "options_for_instrument",
    "render_practice_transposing_controls",
    "render_practice_transposing_helper",
    "render_practice_transposing_panel",
    "render_transposing_key_summary_card",
    "render_sidebar_transposing_controls",
    "render_sidebar_transposing_recap",
    "render_sidebar_transposing_widgets",
    "preserve_written_key_on_display_key_change",
    "sync_written_key_instrument_anchor",
    "render_transposing_info_card",
    "request_transposing_instrument_sync",
    "resolve_practice_keys",
    "sax_display_name",
    "sax_transposition_blurb",
    "sax_written_key_steps",
    "selected_saxophone_type",
    "selected_transposing_type",
    "semitone_steps_for_label",
    "transposing_instrument_names",
    "transpose_chord_for_instrument",
    "transpose_key_for_instrument",
    "transpose_song_for_instrument",
    "transposition_blurb",
    "written_key_for_instrument",
    "written_key_for_saxophone",
    "written_key_for_type",
]
