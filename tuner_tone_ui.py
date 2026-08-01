"""Streamlit UI for Tuner & Tone Development (Practice page)."""

from __future__ import annotations

import html
import re
from typing import Any

from instrument_transposition import (
    is_transposing_instrument,
    selected_transposing_type,
)
from media_tone_catalog import (
    CHROMATIC_NOTE_OPTIONS,
    cache_pending_tone_take,
    live_tuner_display_settings,
    pending_tone_take_ready,
    resolve_tone_target_from_pitch_class,
)
from tone_take_history_ui import (
    render_pending_tone_save,
    render_tone_take_history_section,
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
from tuner_tone_modes import (
    MODE_TONE_SUSTAIN,
    MODE_TUNE_LIVE,
    is_tune_live_mode,
    shows_tone_sustain_note_dropdown,
)


def _safe_key_part(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip())
    return (slug[:48] or "song").strip("_")


def tuner_key_prefix_for_song(song_title: str) -> str:
    """Stable Streamlit key prefix (no spaces or punctuation)."""
    return f"practice_tuner_{_safe_key_part(song_title)}"


TUNER_TARGET_KEY = "tuner_target_note"


def _target_storage_key(key_prefix: str) -> str:
    return f"{key_prefix}::tuner_target_note"


def _pitch_class_storage_key(key_prefix: str) -> str:
    return f"{key_prefix}::tone_target_pitch_class"


def _get_persisted_pitch_class(session_state: dict, key_prefix: str) -> str:
    raw = session_state.get(_pitch_class_storage_key(key_prefix))
    if raw in CHROMATIC_NOTE_OPTIONS:
        return str(raw)
    return CHROMATIC_NOTE_OPTIONS[9]  # default A


def _practice_expected_note(session_state: dict) -> str | None:
    """Optional hook: expected pitch from practice session (future-friendly)."""
    raw = session_state.get("tuner_expected_note") or session_state.get("practice_expected_note")
    if not raw:
        return None
    token = str(raw).strip()
    return token if parse_note_token(token) is not None else None


def _render_tone_target_selector(
    st_module: Any,
    session_state: dict,
    *,
    key_prefix: str,
    instrument: str,
    transposing_type: str,
) -> dict[str, Any] | None:
    """Required chromatic target for Tone Sustain Practice."""
    transposing = is_transposing_instrument(instrument)
    default_pc = _get_persisted_pitch_class(session_state, key_prefix)
    try:
        default_index = CHROMATIC_NOTE_OPTIONS.index(default_pc)
    except ValueError:
        default_index = 9

    selected = st_module.selectbox(
        "Target note",
        CHROMATIC_NOTE_OPTIONS,
        index=default_index,
        key=f"{key_prefix}::tone_target_select",
    )
    session_state[_pitch_class_storage_key(key_prefix)] = selected

    ctx = resolve_tone_target_from_pitch_class(
        selected,
        transposing_type,
        is_transposing=transposing,
    )
    session_state[_target_storage_key(key_prefix)] = ctx.get("target_note")
    session_state[TUNER_TARGET_KEY] = ctx.get("target_note")

    if transposing and ctx.get("display_written") and ctx.get("display_concert"):
        st_module.markdown(
            f"**Written {html.escape(selected)} / "
            f"Concert {html.escape(str(ctx['display_concert']))}**"
        )
    else:
        st_module.markdown(
            f"**Target note:** {html.escape(str(ctx.get('display_concert') or selected))}"
        )
    return ctx


def render_tuner_tone_section(
    st_module: Any,
    *,
    instrument: str,
    display_key: str,
    key_prefix: str = "practice_tuner",
    metronome_bpm: int | None = None,
    metronome_signature: str = "4/4",
    metronome_section_bars: int = 0,
    metronome_section_label: str = "",
    metronome_loop_section: bool = False,
    include_metronome: bool = True,
) -> None:
    """Collapsible Tuner, Tone & Metronome block for the Practice page."""
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

    expander_title = "🎵 Tuner, Tone & Metronome"
    with st_module.expander(expander_title, expanded=False):
        if include_metronome and metronome_bpm is not None:
            from practice_metronome import render_metronome_widget

            render_metronome_widget(
                st_module,
                default_bpm=int(metronome_bpm),
                default_signature=str(metronome_signature or "4/4"),
                section_bars=int(metronome_section_bars or 0),
                section_label=str(metronome_section_label or ""),
                loop_section=bool(metronome_loop_section),
                compact=True,
            )
            st_module.markdown("---")

        st_module.caption(profile.hint)
        if profile.tone_focus:
            st_module.markdown(
                "**Tone focus:** " + " · ".join(profile.tone_focus),
            )

        mode = st_module.radio(
            "Mode",
            [MODE_TUNE_LIVE, MODE_TONE_SUSTAIN],
            horizontal=True,
            key=f"{key_prefix}::mode",
        )

        expected_note = _practice_expected_note(st_module.session_state)

        if is_tune_live_mode(mode):
            string_targets: list[str] | None = None
            if profile.mode == "strings" and profile.string_targets:
                string_targets = list(profile.string_targets)
                st_module.caption(
                    "Tap a string inside the tuner — the active string lights up **red** "
                    "and tuning is judged against that note while you play."
                )

            st_module.markdown("##### Live tuner")
            st_module.caption(
                "Press **Start Tuner** — your browser listens continuously. "
                "Play any note; the needle shows flat ← in tune → sharp."
            )
            instrument_label = instrument
            try:
                from practice_setup_globals import get_active_instrument_display_name

                instrument_label = str(
                    get_active_instrument_display_name(st_module.session_state) or instrument
                ).strip()
            except ImportError:
                pass
            live_display = live_tuner_display_settings(
                instrument=instrument,
                transposing_type=transposing_type,
                instrument_display_name=instrument_label,
            )
            if live_display.get("display_mode") == "transposing_written":
                st_module.caption(
                    f"Showing **{html.escape(instrument_label)}** written note — "
                    "concert pitch shown as secondary info."
                )
            else:
                st_module.caption("Showing concert pitch.")
            render_live_tuner(
                st_module,
                key_prefix=key_prefix,
                target_note=None,
                expected_note=expected_note,
                string_targets=string_targets,
                display_mode=str(live_display.get("display_mode") or "concert"),
                concert_to_written_semitones=int(live_display.get("concert_to_written_semitones") or 0),
                instrument_label=str(live_display.get("instrument_label") or ""),
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

        tone_target_ctx: dict[str, Any] | None = None
        if shows_tone_sustain_note_dropdown(mode, profile.mode):
            tone_target_ctx = _render_tone_target_selector(
                st_module,
                st_module.session_state,
                key_prefix=key_prefix,
                instrument=instrument,
                transposing_type=transposing_type,
            )

        _render_tone_practice_mode(
            st_module,
            key_prefix=key_prefix,
            tone_target_ctx=tone_target_ctx,
            profile=profile,
            instrument=instrument,
            display_key=display_key,
            transposing_type=transposing_type,
        )
        if pending_tone_take_ready(st_module.session_state):
            render_pending_tone_save(
                st_module,
                st_module.session_state,
                key_prefix=key_prefix,
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
    tone_target_ctx: dict[str, Any] | None,
    profile: InstrumentTunerProfile,
    instrument: str = "",
    display_key: str = "",
    transposing_type: str = "",
) -> None:
    """Sustain / tone analysis — recorded clip + librosa."""
    if not librosa_available():
        st_module.warning(
            "Install **librosa** and **soundfile** (see requirements.txt) to enable "
            "tone sustain analysis."
        )
        return

    st_module.markdown("##### Tone Sustain Practice")
    st_module.caption(
        "Select a **target note**, then record a **3–5 second** steady long tone. "
        "The app analyzes pitch drift, sustain steadiness, and tone consistency."
    )

    if tone_target_ctx is None:
        st_module.warning("Select a target note above before recording.")
        return

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

    ui_target_note = str(tone_target_ctx.get("target_note") or "")
    analysis_target = str(tone_target_ctx.get("analysis_target_note") or ui_target_note)

    _render_tone_practice_result(
        st_module,
        raw,
        ui_target_note=ui_target_note,
        analysis_target_note=analysis_target,
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
    ui_target_note: str,
    analysis_target_note: str,
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
            target_note=analysis_target_note or None,
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
        trace_target = analysis_target_note or ui_target_note
        if trace_target:
            tm = parse_note_token(trace_target)
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
        target_note=ui_target_note or None,
        meta={
            "instrument": instrument,
            "display_key": display_key,
            "transposing_type": transposing_type,
            "pitch_class_label": st_module.session_state.get(
                _pitch_class_storage_key(key_prefix),
                "",
            ),
        },
    )
