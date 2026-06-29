"""Streamlit UI for Tuner & Tone Development (Practice page)."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from instrument_transposition import (
    is_transposing_instrument,
    selected_transposing_type,
    written_key_for_instrument,
)
from tuner_live import render_live_tuner
from tuner_tone import (
    InstrumentTunerProfile,
    _profile_for_instrument,
    analyze_tone_practice,
    librosa_available,
    parse_note_token,
    pitch_trace_svg,
)
from tone_take_history_ui import render_pending_tone_save, render_tone_take_history_section
from media_tone_catalog import cache_pending_tone_take

def _safe_key_part(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip())
    return (slug[:48] or "song").strip("_")


def tuner_key_prefix_for_song(song_title: str) -> str:
    """Stable Streamlit key prefix (no spaces or punctuation)."""
    return f"practice_tuner_{_safe_key_part(song_title)}"


TUNER_TARGET_KEY = "tuner_target_note"


def _target_storage_key(key_prefix: str) -> str:
    return f"{key_prefix}::tuner_target_note"


def _get_persisted_target(session_state: dict, key_prefix: str) -> str | None:
    """Read target note from session (scoped per song, then global)."""
    raw = session_state.get(_target_storage_key(key_prefix)) or session_state.get(TUNER_TARGET_KEY)
    if not raw:
        return None
    token = str(raw).strip()
    if not token:
        return None
    return token if parse_note_token(token) is not None else None


def _set_persisted_target(session_state: dict, key_prefix: str, note: str | None) -> None:
    if note and parse_note_token(note) is not None:
        session_state[TUNER_TARGET_KEY] = note
        session_state[_target_storage_key(key_prefix)] = note
    else:
        session_state.pop(TUNER_TARGET_KEY, None)
        session_state.pop(_target_storage_key(key_prefix), None)


def _practice_expected_note(session_state: dict) -> str | None:
    """Optional hook: expected pitch from practice session (future-friendly)."""
    raw = session_state.get("tuner_expected_note") or session_state.get("practice_expected_note")
    if not raw:
        return None
    token = str(raw).strip()
    return token if parse_note_token(token) is not None else None


def render_tuner_tone_section(
    st_module: Any,
    *,
    instrument: str,
    display_key: str,
    key_prefix: str = "practice_tuner",
) -> None:
    """Collapsible Tuner & Tone Development block for the Practice page."""
    if "::" in key_prefix:
        parts = key_prefix.split("::", 1)
        key_prefix = tuner_key_prefix_for_song(parts[-1] if len(parts) > 1 else "song")
    elif not key_prefix.startswith("practice_tuner_"):
        key_prefix = tuner_key_prefix_for_song(key_prefix)

    transposing_type = ""
    if is_transposing_instrument(instrument):
        transposing_type = selected_transposing_type(
            st_module.session_state,
            instrument,
        )

    profile = _profile_for_instrument(instrument, sax_type=transposing_type)

    with st_module.expander("🎵 Tuner & Tone Development", expanded=False):
        st_module.caption(profile.hint)
        if profile.tone_focus:
            st_module.markdown(
                "**Tone focus:** " + " · ".join(profile.tone_focus),
            )

        if is_transposing_instrument(instrument):
            written = written_key_for_instrument(
                display_key,
                instrument,
                st_module.session_state,
            )
            st_module.info(
                f"Song practice key (concert): **{display_key}** · "
                f"Your written key: **{written}** — long tones in written key help intonation."
            )

        mode = st_module.radio(
            "Mode",
            ["Tune (live)", "Tone practice (sustain)"],
            horizontal=True,
            key=f"{key_prefix}::mode",
        )

        target_note = _get_persisted_target(st_module.session_state, key_prefix)
        string_targets: list[str] | None = None

        if profile.mode == "strings" and profile.string_targets:
            string_targets = list(profile.string_targets)
            st_module.caption(
                "Tap a string inside the tuner — the active string lights up **red** "
                "and tuning is judged against that note while you play."
            )
        elif profile.mode in ("wind", "voice", "chromatic"):
            st_module.text_input(
                "Target note (optional)",
                value=_get_persisted_target(st_module.session_state, key_prefix) or "",
                placeholder="e.g. A4, concert D4",
                key=f"{key_prefix}::target_input",
            )
            raw = str(st_module.session_state.get(f"{key_prefix}::target_input", "") or "").strip()
            if raw and parse_note_token(raw):
                _set_persisted_target(st_module.session_state, key_prefix, raw)
            elif not raw:
                _set_persisted_target(st_module.session_state, key_prefix, None)
            target_note = _get_persisted_target(st_module.session_state, key_prefix)
            if target_note:
                st_module.caption(f"Target locked: **{target_note}** — needle centered on this pitch.")

        expected_note = _practice_expected_note(st_module.session_state)

        if mode.startswith("Tune"):
            st_module.markdown("##### Live tuner")
            st_module.caption(
                "Press **Start Tuner** — your browser listens continuously. "
                "Play one note at a time; the needle shows flat ← in tune → sharp."
            )
            render_live_tuner(
                st_module,
                key_prefix=key_prefix,
                target_note=target_note,
                expected_note=expected_note,
                string_targets=string_targets,
            )
            if expected_note:
                st_module.caption(
                    f"Practice target: **{html.escape(expected_note)}** — "
                    "match this note while the tuner listens."
                )
            render_tone_take_history_section(
                st_module,
                st_module.session_state,
                key_prefix=key_prefix,
                instrument=instrument,
                display_key=display_key,
                transposing_type=transposing_type,
            )
            return

        _render_tone_practice_mode(
            st_module,
            key_prefix=key_prefix,
            target_note=target_note,
            profile=profile,
            instrument=instrument,
            display_key=display_key,
            transposing_type=transposing_type,
        )
        render_tone_take_history_section(
            st_module,
            st_module.session_state,
            key_prefix=key_prefix,
            instrument=instrument,
            display_key=display_key,
            transposing_type=transposing_type,
        )


def _render_tone_practice_mode(
    st_module: Any,
    *,
    key_prefix: str,
    target_note: str | None,
    profile: InstrumentTunerProfile,
    instrument: str = "",
    display_key: str = "",
    transposing_type: str = "",
) -> None:
    """Sustain / tone analysis — still uses recorded clip + librosa."""
    if not librosa_available():
        st_module.warning(
            "Install **librosa** and **soundfile** (see requirements.txt) to enable "
            "tone sustain analysis."
        )
        return

    st_module.markdown("##### Tone practice (recorded)")
    st_module.caption(
        "Record a **3–5 second** steady long tone. The app analyzes sustain, "
        "pitch drift, and volume after you finish recording."
    )
    audio_clip = st_module.audio_input(
        "Record long tone",
        key=f"{key_prefix}::audio_in",
    )

    if audio_clip is None:
        st_module.markdown(
            '<div style="text-align:center;padding:1.5rem;color:#64748b;">'
            "🎤 Record a sustained note above for tone feedback."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    raw = audio_clip.getvalue() if hasattr(audio_clip, "getvalue") else audio_clip.read()
    if not raw:
        return

    _render_tone_practice_result(
        st_module,
        raw,
        target_note=target_note,
        profile=profile,
        instrument=instrument,
        display_key=display_key,
        transposing_type=transposing_type,
        key_prefix=key_prefix,
    )


def _render_tone_practice_result(
    st_module: Any,
    audio_bytes: bytes,
    *,
    target_note: str | None,
    profile: InstrumentTunerProfile,
    instrument: str = "",
    display_key: str = "",
    transposing_type: str = "",
    key_prefix: str = "practice_tuner",
) -> None:
    hold_goal = 5.0 if profile.mode in ("wind", "voice") else 4.0
    try:
        result = analyze_tone_practice(
            audio_bytes,
            target_note=target_note,
            min_sustain_sec=hold_goal,
        )
    except Exception as exc:
        st_module.error(f"Tone analysis failed: {exc}")
        return

    if result is None:
        st_module.warning(
            "Could not analyze tone — hold a steady note for at least 2–3 seconds."
        )
        return

    c1, c2, c3 = st_module.columns(3)
    with c1:
        st_module.metric("Pitch stability", f"{result.pitch_stability_score:.0f}%")
    with c2:
        st_module.metric("Volume consistency", f"{result.volume_stability_score:.0f}%")
    with c3:
        st_module.metric("Sustain", f"{result.sustain_seconds:.1f}s")

    st_module.markdown(
        f"**Detected center:** {html.escape(result.median_note)} · "
        f"**Mean offset:** {result.mean_cents:+.0f}¢ · "
        f"**Clip:** {result.duration_sec:.1f}s"
    )

    if result.pitch_trace_hz and result.time_trace_sec:
        target_hz = None
        if target_note:
            tm = parse_note_token(target_note)
            if tm is not None:
                target_hz = 440.0 * (2 ** ((tm - 69) / 12))
        svg = pitch_trace_svg(result.time_trace_sec, result.pitch_trace_hz, target_hz=target_hz)
        if svg:
            st_module.markdown("**Pitch trace**")
            st_module.markdown(svg, unsafe_allow_html=True)

    for line in result.feedback:
        st_module.markdown(f"• {line}")

    if result.sustain_seconds < hold_goal:
        st_module.caption(
            f"Tip: hold one steady note for **{hold_goal:.0f}+ seconds** for richer feedback."
        )

    cache_pending_tone_take(
        st_module.session_state,
        result=result,
        audio_bytes=audio_bytes,
        target_note=target_note,
    )
    render_pending_tone_save(
        st_module,
        st_module.session_state,
        key_prefix=key_prefix,
        instrument=instrument,
        display_key=display_key,
        transposing_type=transposing_type,
    )
