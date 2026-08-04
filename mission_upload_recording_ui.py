"""Mission upload / recording studio — exact-chord backing + capture paths."""

from __future__ import annotations

from typing import Any, Callable

from mission_evaluation_focus import (
    EVALUATION_FOCUS_OPTIONS,
    MISSION_EVALUATION_FOCUS_KEY,
    MISSION_MATCH_EXAMPLE_MODE_KEY,
    authoritative_evaluation_focus,
    default_mission_recording_expander_expanded,
    example_match_mode_enabled,
)
from mission_exact_chord_backing_ui import render_exact_chord_mission_backing_panel
from mission_practice_context import (
    MISSION_EXACT_BACKING_ARMED_KEY,
    MISSION_RECORDING_STUDIO_ENGAGED_KEY,
    authoritative_mission_type,
    ensure_mission_practice_context,
    mark_mission_practice_context_dirty,
    mission_capture_allowed,
    recording_context_stale_warning,
    seal_recording_context,
    ui_backing_chord_mismatch,
)

MISSION_RECORDING_EXPANDER_LABEL = "Mission Recording & Upload (optional)"


def should_show_exact_chord_panel(session: dict[str, Any]) -> bool:
    try:
        from mission_analysis_ui import is_analysis_criteria_locked

        if is_analysis_criteria_locked(session) and authoritative_mission_type(session):
            return True
    except ImportError:
        pass
    if not session.get(MISSION_RECORDING_STUDIO_ENGAGED_KEY):
        return False
    mission_type = authoritative_mission_type(session)
    if mission_type:
        return True
    ctx = ensure_mission_practice_context(session)
    return bool(ctx and ctx.chord.symbol)


def render_mission_recording_upload_expander(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "improv_mission_upload",
    on_analyze_take: Callable[[], None] | None = None,
    dev_mode: bool = False,
) -> None:
    """Collapsed-by-default optional recording studio (heavy UI gated until engaged)."""
    with st.expander(
        MISSION_RECORDING_EXPANDER_LABEL,
        expanded=default_mission_recording_expander_expanded(),
    ):
        if not session.get(MISSION_RECORDING_STUDIO_ENGAGED_KEY):
            st.caption(
                "Optional: record or upload a take for AI coaching. "
                "Most practice happens without recording."
            )
            if st.button(
                "Open recording & upload tools",
                key=f"{key_prefix}_engage_studio",
                use_container_width=True,
            ):
                session[MISSION_RECORDING_STUDIO_ENGAGED_KEY] = True
                st.rerun()
            return

        render_mission_upload_recording_studio(
            st,
            session,
            key_prefix=key_prefix,
            on_analyze_take=on_analyze_take,
            dev_mode=dev_mode,
        )


def _render_evaluation_focus_selector(st: Any, session: dict[str, Any], *, key_prefix: str) -> str:
    current = authoritative_evaluation_focus(session)
    try:
        idx = EVALUATION_FOCUS_OPTIONS.index(current)
    except ValueError:
        idx = 0

    def _on_focus_change() -> None:
        mark_mission_practice_context_dirty(session)

    focus = st.selectbox(
        "Evaluation focus",
        EVALUATION_FOCUS_OPTIONS,
        index=idx,
        key=f"{key_prefix}_eval_focus",
        help="What the AI should emphasize when judging your take.",
        on_change=_on_focus_change,
    )
    session[MISSION_EVALUATION_FOCUS_KEY] = str(focus)
    match = st.checkbox(
        "Match the example (score pitch against the optional example)",
        value=example_match_mode_enabled(session),
        key=f"{key_prefix}_match_example",
        help="Off by default — improvise freely; the example is inspiration only.",
    )
    session[MISSION_MATCH_EXAMPLE_MODE_KEY] = bool(match)
    return str(focus)


def _render_context_summary(st: Any, session: dict[str, Any], *, eval_focus: str) -> None:
    ctx = ensure_mission_practice_context(session)
    mission = (ctx.mission_type if ctx else "") or authoritative_mission_type(session) or "—"
    chord = ctx.chord.symbol if ctx else "—"
    st.markdown(f"**Mission:** {mission}")
    st.markdown(f"**Chord:** {chord}")
    st.markdown(f"**Evaluation focus:** {eval_focus}")


def _render_status_line(
    st: Any,
    session: dict[str, Any],
    *,
    capture_path: str,
    dev_mode: bool,
) -> None:
    armed = bool(session.get(MISSION_EXACT_BACKING_ARMED_KEY))
    mismatch, _msg = ui_backing_chord_mismatch(session)
    stale = recording_context_stale_warning(session)

    bits: list[str] = []
    if capture_path == "live":
        if armed and not mismatch:
            bits.append("Backing synced with selected chord")
        elif mismatch:
            bits.append("Chord mismatch — press Play backing for the selected chord")
        else:
            bits.append("Backing optional — press Play if you want to hear the chord while recording")
    else:
        bits.append("Upload uses mission, chord, and evaluation focus only")
        if armed and not mismatch:
            bits.append("Reference backing available (not mixed into your file)")

    if stale:
        bits.append("Take context outdated — mission or chord changed since capture")
    elif dev_mode and session.get("improv_mission_recording_seal"):
        bits.append("(dev) recording context saved")

    if bits:
        st.markdown("**Status:** " + " · ".join(bits))


def render_mission_upload_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload",
    on_analyze_take: Callable[[], None] | None = None,
    dev_mode: bool = False,
    show_live_mic: bool = True,
) -> None:
    """Full optional studio: backing, evaluation focus, live vs upload paths."""
    st.caption(
        "Improvise freely while focusing on your selected mission. "
        "The optional example is inspiration — you are not required to copy those notes."
    )

    eval_focus = _render_evaluation_focus_selector(st, session, key_prefix=key_prefix)
    _render_context_summary(st, session, eval_focus=eval_focus)

    path_labels = ("Record Live", "Upload Existing Take")
    path = st.radio(
        "Choose how to provide your take:",
        path_labels,
        key=f"{key_prefix}_capture_path",
        horizontal=True,
    )
    capture_path = "live" if path == path_labels[0] else "upload"
    session["mission_upload_capture_mode"] = capture_path

    st.markdown("##### Backing for this mission")
    if capture_path == "live":
        st.caption("Optionally play harmonic backing while you record. Improvise any notes you choose.")
        render_exact_chord_mission_backing_panel(
            st,
            session,
            key_prefix=f"{key_prefix}_backing",
            compact=False,
            play_label=None,
        )
    else:
        st.caption(
            "The uploaded recording will be analyzed using this mission, chord, and evaluation focus. "
            "The backing track is not added to the uploaded audio."
        )
        with st.expander("Hear chord for reference (optional)", expanded=False):
            render_exact_chord_mission_backing_panel(
                st,
                session,
                key_prefix=f"{key_prefix}_backing_ref",
                compact=True,
                play_label=None,
            )

    _render_status_line(st, session, capture_path=capture_path, dev_mode=dev_mode)

    pending_bytes = session.get("_mission_live_mic_pending")

    if capture_path == "live":
        st.markdown("##### A · Record Live")
        cap_ok, cap_msg = mission_capture_allowed(
            session,
            require_mission_workflow=True,
            capture_path="live",
        )
        if not cap_ok and cap_msg:
            st.warning(cap_msg.replace("**", ""))

        col_rec, col_stop = st.columns(2)
        with col_rec:
            recording = st.toggle(
                "Record Live",
                key=f"{key_prefix}_live_recording",
                help="Start recording, perform, then turn off to finish.",
            )
        with col_stop:
            st.caption("Turn **Record Live** off when finished.")

        if show_live_mic and recording and cap_ok:
            try:
                mic = st.audio_input("Perform while recording", key=f"{key_prefix}_live_mic")
                if mic is not None:
                    session["_mission_live_mic_pending"] = mic.getvalue()
                    pending_bytes = mic.getvalue()
            except Exception:
                st.caption("Live mic unavailable in this view — use Upload Analysis.")

        if pending_bytes:
            st.markdown("**Preview captured take**")
            st.audio(pending_bytes, format="audio/wav")
    else:
        st.markdown("##### B · Upload Existing Take")
        st.caption(
            "Select audio you already recorded. Confirm mission, chord, and evaluation focus, then analyze."
        )
        uploaded = st.file_uploader(
            "Audio file",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            key=f"{key_prefix}_file",
        )
        if uploaded is not None:
            session["_mission_upload_pending_bytes"] = uploaded.getvalue()
            session["_mission_upload_pending_name"] = uploaded.name
            st.audio(uploaded.getvalue())

    analyze_ok, analyze_msg = mission_capture_allowed(
        session,
        require_mission_workflow=True,
        capture_path="analysis",
    )
    has_take = bool(pending_bytes or session.get("_mission_upload_pending_bytes"))
    if st.button(
        "Analyze This Take",
        key=f"{key_prefix}_analyze",
        type="primary",
        use_container_width=True,
        disabled=not has_take or not analyze_ok,
    ):
        seal_recording_context(
            session,
            association="missions_analyze" if capture_path == "live" else "missions_upload_analyze",
        )
        session["analysis_sync_creative_mission"] = True
        try:
            from mission_analysis_ui import ANALYSIS_CRITERIA_LOCKED

            session[ANALYSIS_CRITERIA_LOCKED] = True
        except ImportError:
            session["analysis_criteria_locked"] = True
        if on_analyze_take:
            on_analyze_take()

    if not has_take:
        st.caption("Capture or upload audio above, then run **Analyze This Take**.")
    elif not analyze_ok and analyze_msg:
        st.warning(analyze_msg.replace("**", ""))
