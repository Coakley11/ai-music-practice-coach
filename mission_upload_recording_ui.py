"""Mission upload / recording studio — compact optional capture."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

from mission_evaluation_focus import default_mission_recording_expander_expanded
from mission_exact_chord_backing import generate_exact_chord_backing_wav
from mission_exact_chord_backing_ui import render_exact_chord_mission_backing_panel
from mission_live_recording_mix import build_live_recording_previews
from mission_practice_context import (
    MISSION_RECORDING_STUDIO_ENGAGED_KEY,
    authoritative_mission_type,
    ensure_mission_practice_context,
    mission_capture_allowed,
    recording_context_stale_warning,
    seal_recording_context,
    ui_backing_chord_mismatch,
)
from mission_upload_handoff import handoff_mission_take_to_upload_analysis

MISSION_RECORDING_EXPANDER_LABEL = "Mission Live Recording (optional)"
MISSIONS_LIVE_ONLY_KEY = "_missions_live_recording_only"


def should_show_exact_chord_panel(session: dict[str, Any]) -> bool:
    try:
        from mission_upload_handoff import MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY
    except ImportError:
        MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY = "_mission_upload_analysis_handoff"
    if session.get(MISSION_UPLOAD_ANALYSIS_HANDOFF_KEY):
        return False
    try:
        from mission_analysis_ui import is_analysis_criteria_locked

        if is_analysis_criteria_locked(session) and authoritative_mission_type(session):
            return False
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
            st.caption(
                "Optional — record a live take with exact-chord backing, then analyze on Upload Analysis."
            )
            if st.button(
                "Open live recording tools",
                key=f"{key_prefix}_engage_studio",
                use_container_width=True,
            ):
                session[MISSION_RECORDING_STUDIO_ENGAGED_KEY] = True
                session[MISSIONS_LIVE_ONLY_KEY] = True
                st.rerun()
            return
        render_mission_live_recording_studio(
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


def _refresh_live_previews(
    session: dict[str, Any],
    dry_wav: bytes,
    *,
    bpm: int,
    meter: str,
    backing_gain: float,
) -> dict[str, Any]:
    """Regenerate backing from sealed mission context and build mixed preview."""
    backing_wav, _ = generate_exact_chord_backing_wav(session)
    if not backing_wav:
        backing_wav = session.get("mission_exact_backing_wav")
    return build_live_recording_previews(
        session,
        dry_wav,
        backing_wav=backing_wav,
        bpm=bpm,
        meter=meter,
        backing_gain=backing_gain,
    )


def render_mission_live_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload",
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
) -> None:
    session[MISSIONS_LIVE_ONLY_KEY] = True
    session["mission_upload_capture_mode"] = "live"

    mission, chord = _compact_summary(session)
    st.markdown(f"**Mission:** {mission} · **Chord:** {chord}")
    st.caption(
        "Play backing while you record. To analyze an existing file, use **Upload Analysis** in the sidebar."
    )

    render_exact_chord_mission_backing_panel(
        st,
        session,
        key_prefix=f"{key_prefix}_backing",
        compact=True,
    )
    mismatch, _ = ui_backing_chord_mismatch(session)
    if mismatch:
        st.warning("Selected chord does not match current backing — press Play to sync.")

    stale = recording_context_stale_warning(session)
    if stale:
        st.warning(stale.replace("**", ""))

    ctx = ensure_mission_practice_context(session)
    bpm = int(ctx.tempo_bpm if ctx else session.get("backing_track_bpm") or 100)
    meter = str(ctx.meter if ctx else "4/4")
    backing_gain = float(session.get("mission_exact_backing_volume") or (ctx.volume if ctx else 0.85))

    cap_ok, cap_msg = mission_capture_allowed(
        session, require_mission_workflow=True, capture_path="live"
    )
    if not cap_ok and cap_msg:
        st.warning(cap_msg.replace("**", ""))

    recording = st.toggle("Record Live", key=f"{key_prefix}_live_recording")
    if recording:
        if not session.get("_mission_live_recording_active"):
            session["_mission_live_recording_active"] = True
            session["_mission_live_record_start_mono"] = time.monotonic()
            seal_recording_context(session, association="live_record_start")
    else:
        session.pop("_mission_live_recording_active", None)

    dry_bytes = session.get("_mission_live_mic_dry") or session.get("_mission_live_mic_pending")
    mixed_bytes = session.get("_mission_live_mic_mixed")

    if recording and cap_ok:
        try:
            mic = st.audio_input("Perform", key=f"{key_prefix}_live_mic")
            if mic is not None:
                raw = mic.getvalue()
                session["_mission_live_mic_pending"] = raw
                previews = _refresh_live_previews(
                    session, raw, bpm=bpm, meter=meter, backing_gain=backing_gain
                )
                dry_bytes = previews["dry"]
                mixed_bytes = previews["mixed"]
        except Exception:
            st.caption("Live mic unavailable in this browser — use Upload Analysis for file uploads.")

    if dry_bytes and not recording:
        previews = _refresh_live_previews(
            session, bytes(dry_bytes), bpm=bpm, meter=meter, backing_gain=backing_gain
        )
        dry_bytes = previews["dry"]
        mixed_bytes = previews["mixed"]

    preview_mode = "Performance Only"
    if dry_bytes:
        preview_mode = st.radio(
            "Preview",
            ("Performance + Backing", "Performance Only"),
            key=f"{key_prefix}_preview_mode",
            horizontal=True,
        )
        use_mixed = preview_mode.startswith("Performance +") and mixed_bytes
        if use_mixed and mixed_bytes != dry_bytes:
            st.audio(mixed_bytes, format="audio/wav")
            session["_mission_preview_source"] = "mixed"
        else:
            st.audio(dry_bytes, format="audio/wav")
            session["_mission_preview_source"] = "dry"

    has_take = bool(dry_bytes)
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
        audio = bytes(dry_bytes or session.get("_mission_live_mic_pending") or b"")
        handoff_mission_take_to_upload_analysis(
            session,
            audio_bytes=audio,
            filename="mission_live_take.wav",
            source="live",
        )
        if on_open_upload_analysis:
            on_open_upload_analysis()

    if not has_take:
        st.caption("Record a take, preview it, then open Upload Analysis to run the coach.")
    elif not analyze_ok and analyze_msg:
        st.warning(analyze_msg.replace("**", ""))

    if dev_mode:
        diag = dict(session.get("_mission_live_mix_diag") or {})
        diag["preview_source"] = session.get("_mission_preview_source")
        diag["dry_fp"] = hashlib.md5(bytes(dry_bytes or b"")).hexdigest()[:12] if dry_bytes else ""
        diag["mixed_fp"] = (
            hashlib.md5(bytes(mixed_bytes or b"")).hexdigest()[:12] if mixed_bytes else ""
        )
        with st.expander("Developer · live recording mix", expanded=False):
            st.json(diag)


def render_mission_upload_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload",
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
    show_live_mic: bool = True,
) -> None:
    """Legacy entry — Missions uses live-only; upload path is Upload Analysis only."""
    if session.get(MISSIONS_LIVE_ONLY_KEY) or key_prefix.startswith("improv_mission"):
        render_mission_live_recording_studio(
            st,
            session,
            key_prefix=key_prefix,
            on_open_upload_analysis=on_open_upload_analysis,
            dev_mode=dev_mode,
        )
        return

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
    if capture_path == "live":
        render_mission_live_recording_studio(
            st,
            session,
            key_prefix=key_prefix,
            on_open_upload_analysis=on_open_upload_analysis,
            dev_mode=dev_mode,
        )
        return
    st.caption("Upload a file on this page, or use Upload Analysis in the sidebar.")
    uploaded = st.file_uploader(
        "Select audio file",
        type=["wav", "mp3", "m4a", "ogg", "flac"],
        key=f"{key_prefix}_file",
    )
    if uploaded is not None:
        session["_mission_upload_pending_bytes"] = uploaded.getvalue()
        session["_mission_upload_pending_name"] = uploaded.name
        st.audio(uploaded.getvalue())
