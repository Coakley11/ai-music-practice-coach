"""Trace Mission return-from-backing click → queue → rerun → consume."""

from __future__ import annotations

import sys
from typing import Any

TRACE_KEY = "_music_mission_return_handoff_trace"


def _append(session: dict[str, Any], phase: str, payload: dict[str, Any]) -> None:
    bucket = session.get(TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **payload})
    session[TRACE_KEY] = bucket[-24:]


def log_mission_return_click(session: dict[str, Any], *, detail: dict[str, Any]) -> None:
    _append(session, "click", detail)
    print(f"[mission_return_handoff] click {detail}", file=sys.stderr, flush=True)


def log_mission_return_queued(session: dict[str, Any], req: dict[str, Any]) -> None:
    _append(session, "queued", dict(req))
    print(
        f"[mission_return_handoff] queued token={req.get('consume_token')} "
        f"mission={req.get('mission_id')!r}",
        file=sys.stderr,
        flush=True,
    )


def log_mission_return_rerun(session: dict[str, Any], *, allowed: bool, fingerprint: str = "") -> None:
    _append(session, "rerun", {"allowed": allowed, "fingerprint": fingerprint})
    print(
        f"[mission_return_handoff] rerun allowed={allowed} fp={fingerprint[:48]}",
        file=sys.stderr,
        flush=True,
    )


def log_mission_return_consume(session: dict[str, Any], *, phase: str, detail: dict[str, Any]) -> None:
    _append(session, phase, detail)
    print(f"[mission_return_handoff] consume_{phase} {detail}", file=sys.stderr, flush=True)


__all__ = [
    "TRACE_KEY",
    "log_mission_return_click",
    "log_mission_return_consume",
    "log_mission_return_queued",
    "log_mission_return_rerun",
]
