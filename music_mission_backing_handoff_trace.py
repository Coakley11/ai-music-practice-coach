"""Click → queue → rerun → consume trace for Mission / Practice-in-Jam backing."""

from __future__ import annotations

import sys
from typing import Any

TRACE_KEY = "_music_mission_backing_handoff_trace"


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
    print(
        f"[mission_backing_handoff] click with_practice_lick={with_practice_lick} "
        f"mission={mission_id!r} chord={chord!r} widgets_locked={widgets_locked} "
        f"mission_widgets={mission_widgets_instantiated}",
        file=sys.stderr,
        flush=True,
    )


def log_pending_queued(session: dict[str, Any], req: dict[str, Any]) -> None:
    _append(session, "queued", dict(req))
    print(
        f"[mission_backing_handoff] queued seq={req.get('request_seq')} "
        f"lick={req.get('with_practice_lick')} mode={req.get('handoff_mode')} "
        f"token={req.get('consume_token')}",
        file=sys.stderr,
        flush=True,
    )


def log_rerun_request(session: dict[str, Any], *, allowed: bool, reason: str, fingerprint: str = "") -> None:
    _append(session, "rerun", {"allowed": allowed, "reason": reason, "fingerprint": fingerprint})
    print(
        f"[mission_backing_handoff] rerun allowed={allowed} reason={reason} fp={fingerprint[:48]}",
        file=sys.stderr,
        flush=True,
    )


def log_consume(session: dict[str, Any], *, phase: str, detail: dict[str, Any]) -> None:
    _append(session, phase, detail)
    print(f"[mission_backing_handoff] consume_{phase} {detail}", file=sys.stderr, flush=True)


__all__ = [
    "TRACE_KEY",
    "log_consume",
    "log_mission_backing_click",
    "log_pending_queued",
    "log_rerun_request",
]
