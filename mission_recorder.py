"""Mission recorder: one browser controller records the microphone and plays the generated backing.

Replaces the separate backing Play / Stop + ``st.audio_input`` pair for Mission recording. Both
ran from different user actions, so the take had no knowable relation to the backing (the mix
assumed they started together; in practice the offset was the gap between pressing Play and
Record, plus browser start-up latency).

The component (``mission_recorder_component/index.html``) runs both on one ``AudioContext``:
the microphone is captured sample-accurately and the backing is scheduled on that same clock,
so the backing's position inside the take is known from frame counters. The take comes back
with its WAV and that timing; the Performance + Backing preview, live alignment and the sealed
take use the stored offset rather than rebuilding it from BPM.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

from mission_music_capture import MUSIC_CAPTURE_CONSTRAINTS

_COMPONENT = components.declare_component(
    "mission_recorder", path=str(Path(__file__).resolve().parent / "mission_recorder_component")
)
LAST_TAKE_ID_KEY = "_mission_recorder_last_take_id"
LIVE_TAKE_KEY = "_mission_live_take"


def backing_media_url(wav: bytes, coordinates: str) -> str:
    """A same-origin URL the recorder can fetch the generated backing from."""
    try:
        from streamlit.runtime import Runtime

        return str(Runtime.instance().media_file_mgr.add(bytes(wav), "audio/wav", coordinates))
    except Exception:
        return "data:audio/wav;base64," + base64.b64encode(bytes(wav)).decode("ascii")


def render_mission_recorder(
    st: Any,
    session: dict[str, Any],
    *,
    key: str,
    backing: dict[str, Any] | None,
    backing_wav: bytes | None,
    disabled_reason: str = "",
    ready_text: str = "",
) -> dict[str, Any] | None:
    """Draw the recorder; return a new take ``{take_id, wav, timing}`` once per take.

    The component also acknowledges the generated backing (``value["ack"]``: the exact fingerprint
    and load request it decoded and armed, or why it could not); that is stored on the session
    (``record_backing_ack``) and is the only source of "Backing ready".
    """
    from mission_generated_backing import ACK_KEY, load_nonce, record_backing_ack

    args: dict[str, Any] = {
        "constraints": dict(MUSIC_CAPTURE_CONSTRAINTS),
        "require_backing": True,
        "disabled": bool(disabled_reason),
        "disabled_reason": str(disabled_reason or ""),
        "ready_text": str(ready_text or ""),
        "backing_fp": "",
        "backing_url": "",
        "backing_duration_sec": 0.0,
        "load_nonce": load_nonce(session),
        "acked_instance": "",
    }
    if backing and backing_wav:
        args["backing_fp"] = str(backing.get("fp") or "")
        args["backing_duration_sec"] = float(backing.get("duration_sec") or 0.0)
        # Re-registered on every run: Streamlit drops media a run did not re-add.
        args["backing_url"] = backing_media_url(backing_wav, f"{key}.backing.{args['backing_fp']}")
        held = session.get(ACK_KEY)
        if isinstance(held, dict) and held.get("fp") == args["backing_fp"] and held.get("state") in ("ready", "failed"):
            args["acked_instance"] = str(held.get("instance") or "")
    value = _COMPONENT(key=key, default=None, **args)
    if isinstance(value, dict) and value.get("ack"):
        record_backing_ack(session, value["ack"])
    if not isinstance(value, dict) or not value.get("take_id") or not value.get("wav_b64"):
        return None
    if value["take_id"] == session.get(LAST_TAKE_ID_KEY):
        return None
    session[LAST_TAKE_ID_KEY] = value["take_id"]
    try:
        wav = base64.b64decode(value["wav_b64"])
    except Exception:
        return None
    return {"take_id": str(value["take_id"]), "wav": wav, "timing": dict(value.get("timing") or {})}


__all__ = ["LIVE_TAKE_KEY", "backing_media_url", "render_mission_recorder"]
