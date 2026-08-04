"""Mission upload / recording studio — exact-chord backing + capture paths."""

from __future__ import annotations

from typing import Any, Callable

from mission_exact_chord_backing_ui import render_exact_chord_mission_backing_panel
from mission_practice_context import (
    MISSION_EXACT_BACKING_ARMED_KEY,
    mission_capture_allowed,
    recording_context_stale_warning,
    ui_backing_chord_mismatch,
)


def render_mission_upload_recording_studio(
    st: Any,
    session: dict[str, Any],
    *,
    key_prefix: str = "mission_upload",
    on_open_full_upload: Callable[[], None] | None = None,
    show_live_mic: bool = True,
) -> None:
    """Primary mission capture UX: hear exact chord, then record live or upload a file elsewhere."""
    st.markdown("##### Mission upload & recording")
    st.caption(
        "Play the exact mission chord below, then capture a take. "
        "Uploaded files are analyzed against your mission and chord context only — "
        "backing is not mixed into file uploads unless you recorded that way yourself."
    )

    render_exact_chord_mission_backing_panel(
        st,
        session,
        key_prefix=f"{key_prefix}_backing",
        compact=False,
    )

    armed = bool(session.get(MISSION_EXACT_BACKING_ARMED_KEY))
    mismatch, mismatch_msg = ui_backing_chord_mismatch(session)
    stale = recording_context_stale_warning(session)
    cap_ok, cap_msg = mission_capture_allowed(session, require_mission_workflow=True)

    status_bits: list[str] = []
    if armed and not mismatch:
        status_bits.append("Synced — backing matches selected chord")
    elif mismatch:
        status_bits.append("Not synced — chord mismatch")
    else:
        status_bits.append("Not armed — press Play backing first")
    if stale:
        status_bits.append("Stale — mission context changed since seal")
    st.markdown("**Status:** " + " · ".join(f"_{s}_" for s in status_bits))

    mode = st.radio(
        "Capture mode",
        (
            "Live recording (play backing, then record in browser)",
            "Upload an existing take (analysis uses mission context only)",
        ),
        key=f"{key_prefix}_capture_mode",
        horizontal=False,
    )
    session["mission_upload_capture_mode"] = (
        "live" if mode.startswith("Live") else "upload"
    )

    if mode.startswith("Live"):
        st.caption(
            "Use **Play backing** above, then record while listening (headphones recommended). "
            "Your mic capture is separate from the backing player — the coach scores your take, not a premixed file."
        )
        if not cap_ok and cap_msg:
            st.warning(cap_msg.replace("**", ""))
        elif show_live_mic:
            try:
                mic = st.audio_input("Record live for this mission", key=f"{key_prefix}_live_mic")
                if mic is not None and cap_ok:
                    session["_mission_live_mic_pending"] = mic.getvalue()
                    st.success("Live take captured in this session — open Upload Analysis to run the coach.")
            except Exception:
                st.caption("Live mic unavailable here — use Upload Analysis after saving a take elsewhere.")
    else:
        st.caption(
            "Choose a file on **Upload Analysis**. Scoring uses your sealed mission type and exact chord; "
            "the uploaded audio is analyzed as-is (no backing track added)."
        )
        if on_open_full_upload and st.button(
            "Open Upload Analysis for this mission",
            key=f"{key_prefix}_open_upload",
            type="primary",
            use_container_width=True,
        ):
            on_open_full_upload()
