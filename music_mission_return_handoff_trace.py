"""Trace Mission return-from-backing click → queue → rerun → consume."""

from __future__ import annotations

import sys
from typing import Any

TRACE_KEY = "_music_mission_return_handoff_trace"


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


def log_mission_return_click(session: dict[str, Any], *, detail: dict[str, Any]) -> None:
    _append(session, "click", detail)
    _stderr(f"[mission_return_handoff] click {detail}")


def log_mission_return_queued(session: dict[str, Any], req: dict[str, Any]) -> None:
    _append(session, "queued", dict(req))
    _stderr(
        f"[mission_return_handoff] queued token={req.get('consume_token')} "
        f"mission={req.get('mission_id')!r}"
    )


def log_mission_return_rerun(session: dict[str, Any], *, allowed: bool, fingerprint: str = "") -> None:
    _append(session, "rerun", {"allowed": allowed, "fingerprint": fingerprint})
    _stderr(f"[mission_return_handoff] rerun allowed={allowed} fp={fingerprint[:48]}")


def log_mission_return_consume(session: dict[str, Any], *, phase: str, detail: dict[str, Any]) -> None:
    _append(session, phase, detail)
    _stderr(f"[mission_return_handoff] consume_{phase} {detail}")


__all__ = [
    "TRACE_KEY",
    "log_mission_return_click",
    "log_mission_return_consume",
    "log_mission_return_queued",
    "log_mission_return_rerun",
]
