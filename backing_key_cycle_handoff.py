"""Key-cycle dual-buffer handoff acknowledgements (browser → Python).

Cookie channel: JS sets ``kc_handoff`` before clicking the pass-finished button.
Streamlit 1.33+ exposes it via ``st.context.cookies`` on the click rerun.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any
from urllib.parse import unquote


HANDOFF_COOKIE = "kc_handoff"
ACKED_IDS_KEY = "_kc_handoff_acked_ids"
MAX_ACKED = 32


def new_cycle_id() -> str:
    return uuid.uuid4().hex[:12]


def new_ack_id() -> str:
    return uuid.uuid4().hex[:16]


def build_cycle_chart_strip_html(
    *,
    sounding_key: str,
    chords: list[str] | tuple[str, ...] = (),
) -> str:
    """Compact chart strip swapped in JS at the same moment as audio handoff."""
    key = str(sounding_key or "").strip() or "—"
    safe_key = (
        key.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    toks = [str(c).strip() for c in (chords or ()) if str(c).strip()][:16]
    safe_chords = " · ".join(
        t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for t in toks
    )
    body = safe_chords or "(preparing chart…)"
    return (
        f'<div class="kc-chart-strip" data-kc-playing-key="{safe_key}" '
        f'style="font:13px/1.4 system-ui,sans-serif;margin:.2rem 0 .35rem">'
        f'<span style="opacity:.75">Chart</span> '
        f'<strong data-kc-chart-key="{safe_key}">{safe_key}</strong>'
        f'<span style="opacity:.8"> — {body}</span></div>'
    )


def read_handoff_ack_from_st(st: Any) -> dict[str, Any] | None:
    """Read and parse the handoff cookie from the current Streamlit request."""
    raw = ""
    try:
        cookies = getattr(getattr(st, "context", None), "cookies", None)
        if cookies is not None:
            raw = str(cookies.get(HANDOFF_COOKIE) or "").strip()
    except Exception:
        raw = ""
    if not raw:
        return None
    try:
        text = unquote(raw)
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def ack_already_consumed(session: dict[str, Any], ack_id: str) -> bool:
    aid = str(ack_id or "").strip()
    if not aid:
        return False
    bag = session.get(ACKED_IDS_KEY)
    if not isinstance(bag, list):
        return False
    return aid in bag


def mark_ack_consumed(session: dict[str, Any], ack_id: str) -> None:
    aid = str(ack_id or "").strip()
    if not aid:
        return
    bag = session.get(ACKED_IDS_KEY)
    if not isinstance(bag, list):
        bag = []
    bag = [aid, *[x for x in bag if x != aid]][:MAX_ACKED]
    session[ACKED_IDS_KEY] = bag


def validate_playing_ack(
    session: dict[str, Any],
    ack: dict[str, Any] | None,
    *,
    expect_cycle_id: str = "",
) -> tuple[bool, str]:
    """Return (ok, reason). Only ``kind=playing`` advances the cycle."""
    if not isinstance(ack, dict):
        return False, "missing_ack"
    if str(ack.get("kind") or "") != "playing":
        return False, "not_playing"
    ack_id = str(ack.get("ackId") or "").strip()
    if not ack_id:
        return False, "no_ack_id"
    if ack_already_consumed(session, ack_id):
        return False, "duplicate_ack"
    cycle_id = str(ack.get("cycleId") or "").strip()
    expect = str(expect_cycle_id or session.get("_kc_cycle_id") or "").strip()
    if expect and cycle_id and cycle_id != expect:
        return False, "stale_cycle"
    epoch = ack.get("epoch")
    try:
        if epoch is not None and int(epoch) < int(session.get("_kc_player_cmd_epoch") or 0) - 1:
            # Allow current or previous epoch (click can race a remount bump).
            return False, "stale_epoch"
    except Exception:
        pass
    playing = str(ack.get("playingKey") or "").strip()
    if not playing:
        return False, "no_playing_key"
    return True, "ok"


def log_handoff_event(session: dict[str, Any], event: dict[str, Any]) -> None:
    try:
        import os
        from pathlib import Path

        data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data.mkdir(parents=True, exist_ok=True)
        row = {"t": time.time(), **event}
        with (data / "_kc_handoff_acks.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


__all__ = [
    "ACKED_IDS_KEY",
    "HANDOFF_COOKIE",
    "ack_already_consumed",
    "build_cycle_chart_strip_html",
    "log_handoff_event",
    "mark_ack_consumed",
    "new_ack_id",
    "new_cycle_id",
    "read_handoff_ack_from_st",
    "validate_playing_ack",
]
