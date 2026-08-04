"""Mission upload / recording studio — compact optional capture."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

from mission_evaluation_focus import default_mission_recording_expander_expanded
from mission_exact_chord_backing_ui import render_exact_chord_mission_backing_panel
from mission_live_recording_mix import (
    build_live_recording_previews,
    resolve_backing_wav_for_live_mix,
)
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
MISSIONS_RECORDING_UI_VERSION = "phase2a-live-only-mix-v3"
MISSIONS_RECORDING_KEY_PREFIX = "improv_mission_live"

_LEGACY_MISSION_CAPTURE_WIDGET_SUFFIXES = (
    "_capture_path",
    "_file",
    "_upload_pending_bytes",
)


def _clear_legacy_missions_upload_widgets(session: dict[str, Any]) -> None:
    """Drop stale Streamlit/session keys from pre-live-only Missions UI."""
    session["mission_upload_capture_mode"] = "live"
    for suffix in _LEGACY_MISSION_CAPTURE_WIDGET_SUFFIXES:
        session.pop(f"improv_mission_upload{suffix}", None)
        session.pop(f"{MISSIONS_RECORDING_KEY_PREFIX}{suffix}", None)


def _deploy_commit_short() -> str:
    try:
        from suite_deploy_marker import resolve_git_commit_short

        return str(resolve_git_commit_short() or "unknown")
    except ImportError:
        return "unknown"


def _render_recording_route_dev_marker(
    st: Any,
    *,
    renderer: str,
    key_prefix: str,
    dev_mode: bool,
) -> None:
    if not dev_mode:
        return
    st.markdown(
        f"<p style='font-size:0.75rem;color:#0f766e;margin:0.35rem 0;'>"
        f"<strong>DEV recording route</strong> · renderer <code>{renderer}</code> · "
        f"module <code>mission_upload_recording_ui</code> · "
        f"version <code>{MISSIONS_RECORDING_UI_VERSION}</code> · "
        f"key_prefix <code>{key_prefix}</code> · "
        f"live_only <code>true</code> · "
        f"deploy <code>{_deploy_commit_short()}</code>"
        f"</p>",
        unsafe_allow_html=True,
    )


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
    key_prefix: str = MISSIONS_RECORDING_KEY_PREFIX,
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
) -> None:
    session[MISSIONS_LIVE_ONLY_KEY] = True
    _clear_legacy_missions_upload_widgets(session)
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


def _dry_wav_fingerprint(wav: bytes) -> str:
    if not wav:
        return ""
    return hashlib.sha256(wav).hexdigest()[:16]


def _refresh_live_previews(
    session: dict[str, Any],
    dry_wav: bytes,
    *,
    bpm: int,
    meter: str,
    backing_gain: float,
    mic_gain: float = 1.0,
) -> dict[str, Any]:
    """Build mixed preview using the same backing WAV as Play when available."""
    backing_wav, source = resolve_backing_wav_for_live_mix(session)
    session["_mission_live_backing_source"] = source
    return build_live_recording_previews(
        session,
        dry_wav,
        backing_wav=backing_wav,
        bpm=bpm,
        meter=meter,
        backing_gain=backing_gain,
        mic_gain=mic_gain,
    )


def render_mission_live_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = MISSIONS_RECORDING_KEY_PREFIX,
    on_open_upload_analysis: Callable[[], None] | None = None,
    dev_mode: bool = False,
) -> None:
    session[MISSIONS_LIVE_ONLY_KEY] = True
    session["mission_upload_capture_mode"] = "live"
    _clear_legacy_missions_upload_widgets(session)

    _render_recording_route_dev_marker(
        st,
        renderer="render_mission_live_recording_studio",
        key_prefix=key_prefix,
        dev_mode=dev_mode,
    )

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
    backing_gain = float(session.get("mission_live_mix_backing_gain") or 0.65)
    mic_gain = float(session.get("mission_live_mix_mic_gain") or 1.0)

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
                    session,
                    raw,
                    bpm=bpm,
                    meter=meter,
                    backing_gain=backing_gain,
                    mic_gain=mic_gain,
                )
                dry_bytes = previews["dry"]
                mixed_bytes = previews["mixed"]
                session["_mission_live_dry_fp"] = _dry_wav_fingerprint(bytes(dry_bytes))
        except Exception:
            st.caption("Live mic unavailable in this browser — use Upload Analysis for file uploads.")

    if dry_bytes and not recording:
        dry_fp = _dry_wav_fingerprint(bytes(dry_bytes))
        if (
            dry_fp
            and dry_fp == session.get("_mission_live_dry_fp")
            and session.get("_mission_live_mic_mixed")
        ):
            mixed_bytes = session.get("_mission_live_mic_mixed")
        else:
            previews = _refresh_live_previews(
                session,
                bytes(dry_bytes),
                bpm=bpm,
                meter=meter,
                backing_gain=backing_gain,
                mic_gain=mic_gain,
            )
            dry_bytes = previews["dry"]
            mixed_bytes = previews["mixed"]
            session["_mission_live_dry_fp"] = _dry_wav_fingerprint(bytes(dry_bytes))

    preview_mode = "Performance Only"
    if dry_bytes:
        preview_mode = st.radio(
            "Preview",
            ("Performance + Backing", "Performance Only"),
            key=f"{key_prefix}_preview_mode",
            horizontal=True,
        )
        want_mixed = preview_mode.startswith("Performance +")
        mixed_ok = bool(mixed_bytes) and mixed_bytes != dry_bytes
        if want_mixed and mixed_ok:
            st.audio(mixed_bytes, format="audio/wav")
            session["_mission_preview_source"] = "_mission_live_mic_mixed"
        else:
            if want_mixed and not mixed_ok:
                st.caption(
                    "Mixed preview unavailable — press **Play** on backing before recording, then try again."
                )
            st.audio(dry_bytes, format="audio/wav")
            session["_mission_preview_source"] = "_mission_live_mic_dry"

        if dev_mode:
            backing_only = session.get("_mission_live_backing_looped_preview")
            if isinstance(backing_only, (bytes, bytearray)) and len(backing_only) > 44:
                st.caption("Developer · Backing Only (looped for mix)")
                st.audio(bytes(backing_only), format="audio/wav")

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
            st=st,
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
        diag["renderer"] = "render_mission_live_recording_studio"
        diag["recording_ui_version"] = MISSIONS_RECORDING_UI_VERSION
        diag["key_prefix"] = key_prefix
        diag["live_only"] = True
        diag["deploy_sha"] = _deploy_commit_short()
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
    """Legacy name — Missions and improv paths are live-only; file upload is Upload Analysis only."""
    del show_live_mic
    session[MISSIONS_LIVE_ONLY_KEY] = True
    render_mission_live_recording_studio(
        st,
        session,
        key_prefix=key_prefix if key_prefix.startswith("improv") else MISSIONS_RECORDING_KEY_PREFIX,
        on_open_upload_analysis=on_open_upload_analysis,
        dev_mode=dev_mode,
    )


def render_mission_file_upload_capture(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload_analysis",
) -> None:
    """Existing-file capture for Upload Analysis workflows (not Missions)."""
    st.caption("Upload a take to analyze — live recording stays on the Missions tab.")
    uploaded = st.file_uploader(
        "Select audio file",
        type=["wav", "mp3", "m4a", "ogg", "flac"],
        key=f"{key_prefix}_file",
    )
    if uploaded is not None:
        session["_mission_upload_pending_bytes"] = uploaded.getvalue()
        session["_mission_upload_pending_name"] = uploaded.name
        session["mission_upload_capture_mode"] = "upload"
        st.audio(uploaded.getvalue())
