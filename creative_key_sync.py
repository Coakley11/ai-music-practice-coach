"""Creative page concert-key sync — Style Jam / Jam Session → global practice key."""

from __future__ import annotations

import html
from typing import Any

from studio_page_state import CREATIVE_MAJOR_KEY_OPTIONS

IMPROV_STYLE_KEY_TRACKER = "_improv_style_key_tracker"
IMPROV_JAM_KEY_TRACKER = "_improv_jam_key_tracker"
CREATIVE_CONCERT_KEY_SOURCE = "_creative_concert_key_source"

# Re-export for UI pickers.
CREATIVE_MAJOR_KEY_OPTIONS = CREATIVE_MAJOR_KEY_OPTIONS


def _key_steps_to_center(key_center: str) -> int:
    from music_theory import normalize_root, semitone_distance, split_chord

    root, _suffix = split_chord(str(key_center or "C"))
    target = normalize_root(root)
    return semitone_distance("C", target)


def creative_entry_concert_key(session: dict[str, Any]) -> str:
    """Selected concert key from Creative entry widgets, if any."""
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
    session[CREATIVE_CONCERT_KEY_SOURCE] = source
    session["concert_key"] = key
    if st_like is None:
        st_like = type("_St", (), {"session_state": session})()
    try:
        from songs.key_state import request_display_key

        request_display_key(st_like, key)
    except ImportError:
        session["_pending_display_key"] = key
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


def invalidate_creative_backing_context(session: dict[str, Any]) -> None:
    """Drop stale Creative backing handoff after key/BPM/groove changes."""
    try:
        from backing_context import clear_backing_context, get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None and ctx.source in {"entry_jam", "mission"}:
            clear_backing_context(session)
    except ImportError:
        pass
    session.pop("_pending_backing_context_apply", None)


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


def sync_creative_style_jam_meta(session: dict[str, Any]) -> None:
    """Keep improv_style_meta aligned with Style Jam widgets."""
    groove_intensity = str(session.get("improv_groove") or "Medium").strip()
    session["improv_style_meta"] = {
        "style": str(session.get("improv_style") or "").strip(),
        "bpm": int(session.get("improv_style_bpm") or 110),
        "groove": groove_intensity,
        "groove_intensity": groove_intensity,
        "key": str(session.get("improv_style_key") or "").strip(),
        "mood": str(session.get("improv_mood") or "Mellow").strip(),
        "difficulty": str(session.get("improv_difficulty") or "Intermediate").strip(),
        "meter": str(session.get("improv_style_meter") or session.get("backing_time_signature") or "4/4").strip(),
        "entry_mode": str(session.get("improv_entry_mode") or "").strip(),
    }


def on_improv_jam_key_change() -> None:
    import streamlit as st

    prev = str(st.session_state.get(IMPROV_JAM_KEY_TRACKER) or "").strip()
    new = str(st.session_state.get("improv_jam_key") or "").strip()
    if not new:
        return
    gen = st.session_state.get("improv_jam_session")
    if isinstance(gen, dict) and gen.get("sections") and prev and prev != new:
        st.session_state["improv_jam_session"] = {
            **gen,
            "sections": retranspose_generated_sections(
                dict(gen.get("sections") or {}),
                from_key=prev,
                to_key=new,
            ),
        }
    apply_creative_concert_key(st.session_state, new, st_like=st, source="creative_jam_session")
    st.session_state[IMPROV_JAM_KEY_TRACKER] = new
    invalidate_creative_backing_context(st.session_state)


def on_improv_style_key_change() -> None:
    import streamlit as st

    prev = str(st.session_state.get(IMPROV_STYLE_KEY_TRACKER) or "").strip()
    new = str(st.session_state.get("improv_style_key") or "").strip()
    sync_creative_key_change(st.session_state, new, previous_key=prev, st_like=st)


def on_improv_style_jam_setting_change() -> None:
    """BPM / groove / style change — refresh meta and invalidate backing handoff."""
    import streamlit as st

    sync_creative_style_jam_meta(st.session_state)
    invalidate_creative_backing_context(st.session_state)


def ensure_creative_analysis_mode_restored(session_state: dict[str, Any]) -> str:
    """Restore Creative analysis mode before the selectbox renders."""
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
    show_chart = bool(chart_key and chart_key != concert and chart_line and chart_line != concert_line)
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
            f'<p class="ui-creative-progression-preview"><strong>Concert progression:</strong> '
            f"{html.escape(display['concert_line'])}</p>",
            unsafe_allow_html=True,
        )
    if display["chart_line"]:
        label = display["chart_label"] or "Chart"
        key_note = f" ({html.escape(display['chart_key'])})" if display.get("chart_key") else ""
        st.markdown(
            f'<p class="ui-creative-progression-preview"><strong>{html.escape(label)}{key_note}:</strong> '
            f"{html.escape(display['chart_line'])}</p>",
            unsafe_allow_html=True,
        )
