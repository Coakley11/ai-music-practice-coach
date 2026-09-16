"""Key-cycle dual-buffer handoff acknowledgements (browser → Python).

Primary channel: a Streamlit ``declare_component`` that polls
``window.parent.__kcPendingPlayingAck`` and calls ``setComponentValue``.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import streamlit.components.v1 as components

HANDOFF_COOKIE = "kc_handoff"
ACKED_IDS_KEY = "_kc_handoff_acked_ids"
LAST_PASS_ID_KEY = "_kc_handoff_last_pass_id"
MAX_ACKED = 32

_COMPONENT_DIR = Path(__file__).resolve().parent / "kc_handoff_component"
_kc_handoff_component = components.declare_component(
    "kc_handoff",
    path=str(_COMPONENT_DIR),
)


def new_cycle_id() -> str:
    return uuid.uuid4().hex[:12]


def new_ack_id() -> str:
    return uuid.uuid4().hex[:16]


def build_cycle_chart_strip_html(
    *,
    sounding_key: str,
    chords: list[str] | tuple[str, ...] = (),
    sections: dict[str, list[str]] | None = None,
) -> str:
    """Visible chart for the sounding key (section grid when sections provided)."""
    key = str(sounding_key or "").strip() or "—"
    safe_key = (
        key.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    sec_map = sections if isinstance(sections, dict) else {}
    blocks: list[str] = []
    if sec_map:
        for name, chs in sec_map.items():
            safe_name = (
                str(name or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            toks = [str(c).strip() for c in (chs or []) if str(c).strip()][:24]
            if not toks:
                continue
            cells = "".join(
                f'<span class="kc-chord-cell" style="display:inline-block;min-width:2.6rem;'
                f'padding:.15rem .35rem;margin:.12rem;border:1px solid rgba(0,0,0,.12);'
                f'border-radius:6px;background:#fff;font-weight:650">{t.replace("&", "&amp;").replace("<", "&lt;")}</span>'
                for t in toks
            )
            blocks.append(
                f'<div class="kc-chart-section" style="margin:.35rem 0">'
                f'<div style="font-size:12px;opacity:.75;margin-bottom:.15rem">{safe_name}</div>'
                f'<div>{cells}</div></div>'
            )
    if not blocks:
        toks = [str(c).strip() for c in (chords or ()) if str(c).strip()][:24]
        safe_chords = " · ".join(
            t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for t in toks
        )
        body = safe_chords or "(preparing chart…)"
        blocks.append(f'<div style="opacity:.85">{body}</div>')
    return (
        f'<div class="kc-chart-full" data-kc-playing-key="{safe_key}" '
        f'style="font:13px/1.35 system-ui,sans-serif;margin:.25rem 0 .45rem;'
        f'padding:.45rem .55rem;border:1px solid rgba(15,23,42,.12);border-radius:10px;'
        f'background:linear-gradient(180deg,#fff,#f8fafc)">'
        f'<div style="margin-bottom:.25rem"><span style="opacity:.7">Playing chart</span> '
        f'<strong data-kc-chart-key="{safe_key}">{safe_key}</strong></div>'
        f'{"".join(blocks)}</div>'
    )


def render_handoff_component(
    st: Any,
    session: dict[str, Any],
    *,
    expect_cycle_id: str = "",
    armed: bool = True,
) -> dict[str, Any] | None:
    """Mount the handoff receiver; return a new playing ack exactly once."""
    raw = _kc_handoff_component(
        expect_cycle_id=str(expect_cycle_id or session.get("_kc_cycle_id") or ""),
        armed=bool(armed),
        key="kc_handoff_receiver",
        default=None,
    )
    try:
        log_handoff_event(
            session,
            {
                "event": "component_raw",
                "armed": bool(armed),
                "expect_cycle_id": str(expect_cycle_id or session.get("_kc_cycle_id") or ""),
                "raw_type": type(raw).__name__,
                "raw_kind": (raw.get("kind") if isinstance(raw, dict) else None),
                "raw_ack": (raw.get("ackId") if isinstance(raw, dict) else None),
                "raw_preview": (
                    {k: raw.get(k) for k in ("kind", "ackId", "cycleId", "passId", "playingKey")}
                    if isinstance(raw, dict)
                    else str(raw)[:120]
                ),
            },
        )
    except Exception:
        pass
    if not isinstance(raw, dict):
        return None
    if str(raw.get("kind") or "") != "playing":
        return None
    ack_id = str(raw.get("ackId") or "").strip()
    if not ack_id:
        return None
    if ack_already_consumed(session, ack_id):
        return None
    return raw


def read_handoff_ack_from_st(st: Any) -> dict[str, Any] | None:
    """Legacy cookie fallback (kept for diagnostics only)."""
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
    if not bool(session.get("backing_key_cycle_enabled")) and not session.get(
        "_kc_cycle_id"
    ):
        # Soft check — owner session is authoritative below.
        pass
    ack_id = str(ack.get("ackId") or "").strip()
    if not ack_id:
        return False, "no_ack_id"
    if ack_already_consumed(session, ack_id):
        return False, "duplicate_ack"
    cycle_id = str(ack.get("cycleId") or "").strip()
    expect = str(expect_cycle_id or session.get("_kc_cycle_id") or "").strip()
    if expect and cycle_id and cycle_id != expect:
        return False, "stale_cycle"
    if not cycle_id:
        return False, "no_cycle_id"
    # Reject after Off / teardown epoch bump (more than one behind).
    epoch = ack.get("epoch")
    try:
        cur_epoch = int(session.get("_kc_player_cmd_epoch") or 0)
        if epoch is not None and int(epoch) < cur_epoch - 1:
            return False, "stale_epoch"
    except Exception:
        pass
    playing = str(ack.get("playingKey") or "").strip()
    if not playing:
        return False, "no_playing_key"
    # Monotonic pass id within a cycle — ignore late/replayed lower ids.
    try:
        pass_id = int(ack.get("passId"))
    except Exception:
        return False, "bad_pass_id"
    last_pass = int(session.get(LAST_PASS_ID_KEY) or 0)
    if pass_id <= last_pass:
        return False, "stale_pass_id"
    return True, "ok"


def mark_pass_id_seen(session: dict[str, Any], pass_id: int) -> None:
    try:
        session[LAST_PASS_ID_KEY] = max(int(session.get(LAST_PASS_ID_KEY) or 0), int(pass_id))
    except Exception:
        session[LAST_PASS_ID_KEY] = int(pass_id or 0)


def log_timing_event(event: dict[str, Any]) -> None:
    try:
        import os

        data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data.mkdir(parents=True, exist_ok=True)
        row = {"t": time.time(), **event}
        with (data / "_kc_handoff_timing.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def log_handoff_event(session: dict[str, Any], event: dict[str, Any]) -> None:
    try:
        import os

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
    "LAST_PASS_ID_KEY",
    "ack_already_consumed",
    "build_cycle_chart_strip_html",
    "log_handoff_event",
    "log_timing_event",
    "mark_ack_consumed",
    "mark_pass_id_seen",
    "new_ack_id",
    "new_cycle_id",
    "read_handoff_ack_from_st",
    "render_handoff_component",
    "validate_playing_ack",
]
