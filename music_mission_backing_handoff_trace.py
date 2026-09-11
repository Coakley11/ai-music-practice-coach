"""Click → queue → rerun → consume trace for Mission / Practice-in-Jam backing."""

from __future__ import annotations

import sys
from typing import Any

TRACE_KEY = "_music_mission_backing_handoff_trace"


def _stderr(msg: str) -> None:
    """Best-effort stderr; never crash the Streamlit run (Windows OSError 22)."""
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        try:
            print(msg, flush=True)
        except Exception:
            pass


def _append(session: dict[str, Any], phase: str, payload: dict[str, Any]) -> None:
    bucket = session.get(TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **payload})
    session[TRACE_KEY] = bucket[-24:]


def log_mission_backing_click(
    session: dict[str, Any],
    *,
    with_practice_lick: bool,
    mission_id: str,
    mission_session_id: str,
    section: str,
    chord: str,
    workflow_owner: str,
    widgets_locked: bool,
    mission_widgets_instantiated: bool,
) -> None:
    _append(
        session,
        "click",
        {
            "with_practice_lick": with_practice_lick,
            "mission_id": mission_id,
            "mission_session_id": mission_session_id,
            "section": section,
            "chord": chord,
            "workflow_owner": workflow_owner,
            "widgets_locked": widgets_locked,
            "mission_widgets_instantiated": mission_widgets_instantiated,
        },
    )
    _stderr(
        f"[mission_backing_handoff] click with_practice_lick={with_practice_lick} "
        f"mission={mission_id!r} chord={chord!r} widgets_locked={widgets_locked} "
        f"mission_widgets={mission_widgets_instantiated}"
    )


def log_pending_queued(session: dict[str, Any], req: dict[str, Any]) -> None:
    _append(session, "queued", dict(req))
    _stderr(
        f"[mission_backing_handoff] queued seq={req.get('request_seq')} "
        f"lick={req.get('with_practice_lick')} mode={req.get('handoff_mode')} "
        f"token={req.get('consume_token')}"
    )


def log_rerun_request(session: dict[str, Any], *, allowed: bool, reason: str, fingerprint: str = "") -> None:
    _append(session, "rerun", {"allowed": allowed, "reason": reason, "fingerprint": fingerprint})
    _stderr(
        f"[mission_backing_handoff] rerun allowed={allowed} reason={reason} fp={fingerprint[:48]}"
    )


def log_consume(session: dict[str, Any], *, phase: str, detail: dict[str, Any]) -> None:
    _append(session, phase, detail)
    _stderr(f"[mission_backing_handoff] consume_{phase} {detail}")


__all__ = [
    "TRACE_KEY",
    "log_consume",
    "log_mission_backing_click",
    "log_pending_queued",
    "log_rerun_request",
]
