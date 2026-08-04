"""Mission upload / recording studio — compact optional capture."""

from __future__ import annotations

import time
from typing import Any, Callable

from mission_evaluation_focus import default_mission_recording_expander_expanded
from mission_exact_chord_backing import generate_exact_chord_backing_wav
from mission_exact_chord_backing_ui import render_exact_chord_mission_backing_panel
from mission_live_recording_mix import build_live_recording_previews
from mission_practice_context import (
    MISSION_EXACT_BACKING_ARMED_KEY,
    MISSION_RECORDING_STUDIO_ENGAGED_KEY,
    authoritative_mission_type,
    ensure_mission_practice_context,
    mission_capture_allowed,
    recording_context_stale_warning,
    seal_recording_context,
    ui_backing_chord_mismatch,
)
from mission_upload_handoff import handoff_mission_take_to_upload_analysis

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
    return bool(authoritative_mission_type(session))


def render_mission_recording_upload_expander(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "improv_mission_upload",
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
) -> None:
    with st.expander(
        MISSION_RECORDING_EXPANDER_LABEL,
        expanded=default_mission_recording_expander_expanded(),
    ):
        if not session.get(MISSION_RECORDING_STUDIO_ENGAGED_KEY):
            st.caption("Optional — record or upload a take, then analyze on Upload Analysis.")
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
            on_open_upload_analysis=on_open_upload_analysis,
            dev_mode=dev_mode,
        )


def _compact_summary(session: dict[str, Any]) -> tuple[str, str]:
    ctx = ensure_mission_practice_context(session)
    mission = (ctx.mission_type if ctx else "") or authoritative_mission_type(session) or "—"
    chord = ctx.chord.symbol if ctx else "—"
    return mission, chord


def render_mission_upload_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload",
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
    show_live_mic: bool = True,
) -> None:
    mission, chord = _compact_summary(session)
    st.markdown(f"**Mission:** {mission} · **Chord:** {chord}")

    path = st.radio(
        "Choose one",
        ("Record Live", "Upload Existing Take"),
        key=f"{key_prefix}_capture_path",
        horizontal=True,
    )
    capture_path = "live" if path == "Record Live" else "upload"
    session["mission_upload_capture_mode"] = capture_path

    ctx = ensure_mission_practice_context(session)
    bpm = int(ctx.tempo_bpm if ctx else session.get("backing_track_bpm") or 100)
    meter = str(ctx.meter if ctx else "4/4")
    backing_gain = float(session.get("mission_exact_backing_volume") or (ctx.volume if ctx else 0.85))

    if capture_path == "live":
        st.caption("Optional: play backing while you record. Preview can include backing + your performance.")
        render_exact_chord_mission_backing_panel(
            st,
            session,
            key_prefix=f"{key_prefix}_backing",
            compact=True,
        )
        armed = bool(session.get(MISSION_EXACT_BACKING_ARMED_KEY))
        mismatch, _ = ui_backing_chord_mismatch(session)
        if mismatch:
            st.warning("Selected chord does not match current backing — press Play to sync.")
        elif armed:
            st.caption("Backing synced with selected chord.")
    else:
        st.caption(
            "The uploaded recording will be analyzed using this mission and chord. "
            "The backing track is not added to the uploaded audio."
        )

    stale = recording_context_stale_warning(session)
    if stale:
        st.warning(stale.replace("**", ""))

    dry_bytes = session.get("_mission_live_mic_dry") or session.get("_mission_live_mic_pending")
    mixed_bytes = session.get("_mission_live_mic_mixed")

    if capture_path == "live":
        cap_ok, cap_msg = mission_capture_allowed(
            session, require_mission_workflow=True, capture_path="live"
        )
        if not cap_ok and cap_msg:
            st.warning(cap_msg.replace("**", ""))
        recording = st.toggle("Record Live", key=f"{key_prefix}_live_recording")
        if recording:
            session["_mission_live_record_start_mono"] = time.monotonic()
            seal_recording_context(session, association="live_record_start")
        if show_live_mic and recording and cap_ok:
            try:
                mic = st.audio_input("Perform", key=f"{key_prefix}_live_mic")
                if mic is not None:
                    raw = mic.getvalue()
                    session["_mission_live_mic_pending"] = raw
                    backing_wav = session.get("mission_exact_backing_wav")
                    if not backing_wav:
                        backing_wav, _ = generate_exact_chord_backing_wav(session)
                    previews = build_live_recording_previews(
                        session,
                        raw,
                        backing_wav=backing_wav if armed else None,
                        bpm=bpm,
                        meter=meter,
                        backing_gain=backing_gain,
                    )
                    dry_bytes = previews["dry"]
                    mixed_bytes = previews["mixed"]
            except Exception:
                st.caption("Live mic unavailable — use Upload Analysis to capture elsewhere.")

        if dry_bytes:
            preview_mode = st.radio(
                "Preview",
                ("Performance + Backing", "Performance Only"),
                key=f"{key_prefix}_preview_mode",
                horizontal=True,
            )
            if preview_mode.startswith("Performance +") and mixed_bytes:
                st.audio(mixed_bytes, format="audio/wav")
            else:
                st.audio(dry_bytes, format="audio/wav")
    else:
        uploaded = st.file_uploader(
            "Select audio file",
            type=["wav", "mp3", "m4a", "ogg", "flac"],
            key=f"{key_prefix}_file",
        )
        if uploaded is not None:
            session["_mission_upload_pending_bytes"] = uploaded.getvalue()
            session["_mission_upload_pending_name"] = uploaded.name
            st.audio(uploaded.getvalue())

    has_take = bool(
        dry_bytes
        or session.get("_mission_upload_pending_bytes")
    )
    analyze_ok, analyze_msg = mission_capture_allowed(
        session, require_mission_workflow=True, capture_path="analysis"
    )

    if st.button(
        "Analyze This Take",
        key=f"{key_prefix}_analyze",
        type="primary",
        use_container_width=True,
        disabled=not has_take or not analyze_ok,
    ):
        if capture_path == "live":
            audio = bytes(dry_bytes or session.get("_mission_live_mic_pending") or b"")
            name = "mission_live_take.wav"
        else:
            audio = bytes(session.get("_mission_upload_pending_bytes") or b"")
            name = str(session.get("_mission_upload_pending_name") or "mission_upload.wav")
        handoff_mission_take_to_upload_analysis(
            session,
            audio_bytes=audio,
            filename=name,
            source=capture_path,
        )
        if on_open_upload_analysis:
            on_open_upload_analysis()

    if not has_take:
        st.caption("Capture or select a take, then open Upload Analysis to choose AI criteria and run the coach.")
    elif not analyze_ok and analyze_msg:
        st.warning(analyze_msg.replace("**", ""))

    if dev_mode:
        with st.expander("Developer · mission capture", expanded=False):
            st.json(
                {
                    "capture_path": capture_path,
                    "has_dry": bool(dry_bytes),
                    "has_mixed": bool(mixed_bytes),
                    "handoff_source": session.get("_mission_upload_handoff_source"),
                }
            )
