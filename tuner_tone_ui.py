"""Streamlit UI for Tuner & Tone Development (Practice page)."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from instrument_transposition import (
    is_transposing_instrument,
    selected_transposing_type,
    written_key_for_instrument,
)
from tuner_tone import (
    InstrumentTunerProfile,
    _profile_for_instrument,
    analyze_tone_practice,
    cents_meter_html,
    detect_pitch_from_audio,
    librosa_available,
    note_label,
    parse_note_token,
    pitch_trace_svg,
)


def render_tuner_tone_section(
    st_module: Any,
    *,
    instrument: str,
    display_key: str,
    key_prefix: str = "practice_tuner",
) -> None:
    """Collapsible Tuner & Tone Development block for the Practice page."""
    transposing_type = ""
    if is_transposing_instrument(instrument):
        transposing_type = selected_transposing_type(
            st_module.session_state,
            instrument,
        )

    profile = _profile_for_instrument(instrument, sax_type=transposing_type)

    with st_module.expander("🎵 Tuner & Tone Development", expanded=False):
        if not librosa_available():
            st_module.warning(
                "Install **librosa** and **soundfile** (see requirements.txt) to enable "
                "microphone tuning and tone analysis."
            )
            return

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
            ["Tune", "Tone practice (sustain)"],
            horizontal=True,
            key=f"{key_prefix}::mode",
        )

        target_note = st_module.session_state.get("tuner_target_note")
        if profile.mode == "strings" and profile.string_targets:
            st_module.markdown("**String targets** (tap to set target)")
            cols = st_module.columns(min(len(profile.string_targets), 6))
            for i, s in enumerate(profile.string_targets):
                with cols[i % len(cols)]:
                    if st_module.button(
                        s,
                        key=f"{key_prefix}::str::{s}",
                        use_container_width=True,
                    ):
                        st_module.session_state["tuner_target_note"] = s
                        target_note = s
            if target_note:
                st_module.caption(f"Target: **{target_note}**")
        elif profile.mode in ("wind", "voice", "chromatic"):
            target_note = st_module.text_input(
                "Target note (optional)",
                value=st_module.session_state.get("tuner_target_note", ""),
                placeholder="e.g. A4, concert D4",
                key=f"{key_prefix}::target_input",
            )
            if target_note:
                st_module.session_state["tuner_target_note"] = target_note.strip()

        target_note = st_module.session_state.get("tuner_target_note") or None
        if target_note == "":
            target_note = None

        st_module.markdown("##### Microphone")
        st_module.caption(
            "Record a short clip (pluck, long tone, or hum). "
            "Works best in a quiet room with the mic close to the instrument."
        )
        audio_clip = st_module.audio_input(
            "Listen & analyze",
            key=f"{key_prefix}::audio_in",
        )

        if audio_clip is None:
            st_module.markdown(
                '<div style="text-align:center;padding:1.5rem;color:#64748b;">'
                "🎤 Waiting for audio — record above to tune or check tone."
                "</div>",
                unsafe_allow_html=True,
            )
            return

        raw = audio_clip.getvalue() if hasattr(audio_clip, "getvalue") else audio_clip.read()
        if not raw:
            return

        if mode.startswith("Tune"):
            _render_tune_result(st_module, raw, target_note=target_note, profile=profile)
        else:
            _render_tone_practice_result(
                st_module,
                raw,
                target_note=target_note,
                profile=profile,
            )


def _render_tune_result(
    st_module: Any,
    audio_bytes: bytes,
    *,
    target_note: str | None,
    profile: InstrumentTunerProfile,
) -> None:
    try:
        reading = detect_pitch_from_audio(audio_bytes, target_note=target_note)
    except Exception as exc:
        st_module.error(f"Could not analyze audio: {exc}")
        return

    if reading is None:
        st_module.warning(
            "No clear pitch detected. Play one note at a time, closer to the mic, "
            "and reduce background noise."
        )
        return

    note_big = html.escape(reading.note_name)
    cents = reading.cents_offset
    st_module.markdown(
        f'<div style="text-align:center;padding:0.5rem 0;">'
        f'<div style="font-size:2.8rem;font-weight:700;line-height:1.1;">{note_big}</div>'
        f'<div style="font-size:1rem;color:#64748b;">{reading.frequency_hz:.1f} Hz</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    if target_note:
        st_module.markdown(
            f"**Target:** {html.escape(target_note)} · "
            f"**Offset:** {cents:+.0f} cents"
        )
    else:
        st_module.markdown(f"**Cents from nearest pitch:** {cents:+.0f}")

    st_module.markdown(cents_meter_html(cents), unsafe_allow_html=True)

    if reading.in_tune:
        st_module.success("In tune — good to move on or check the next string.")
    elif profile.mode == "strings" and target_note:
        st_module.info(
            "If the wrong string lights up, you may be on a different octave — "
            "mute other strings and pluck again."
        )
    else:
        direction = "sharp" if cents > 0 else "flat"
        st_module.info(f"Adjust tuning — you're slightly **{direction}**.")


def _render_tone_practice_result(
    st_module: Any,
    audio_bytes: bytes,
    *,
    target_note: str | None,
    profile: InstrumentTunerProfile,
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
