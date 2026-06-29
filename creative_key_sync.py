"""Creative page concert-key sync — Style Jam / Jam Session → global practice key."""

from __future__ import annotations

from typing import Any

IMPROV_STYLE_KEY_TRACKER = "_improv_style_key_tracker"
CREATIVE_CONCERT_KEY_SOURCE = "_creative_concert_key_source"


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
            out[label] = [transpose_chord(str(c), delta) for c in chords if str(c).strip()]
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
    session["improv_style_meta"] = {
        "style": str(session.get("improv_style") or "").strip(),
        "bpm": int(session.get("improv_style_bpm") or 110),
        "groove": str(session.get("improv_groove") or "Medium").strip(),
        "key": str(session.get("improv_style_key") or "").strip(),
    }


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
