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


def build_cycle_lead_sheet_html(
    *,
    sounding_key: str,
    sections: dict[str, list[str]] | None = None,
    song_name: str = "",
    song_data: dict[str, Any] | None = None,
    selected_section_names: list[str] | tuple[str, ...] | None = None,
    level: str = "Intermediate",
    groove_style: str = "Pop groove",
    bpm: int = 100,
    time_signature: str = "4/4",
    chords: list[str] | tuple[str, ...] = (),
) -> str:
    """Real backing lead-sheet HTML for the sounding key (not a raw-token grid)."""
    key = str(sounding_key or "").strip() or "C"
    sec_map = sections if isinstance(sections, dict) else {}
    selected = [str(n) for n in (selected_section_names or ()) if str(n).strip()]
    filtered: dict[str, list[str]] = {}
    if sec_map:
        for name, chs in sec_map.items():
            nm = str(name or "").strip()
            if not nm:
                continue
            if selected and nm not in selected:
                continue
            toks = [str(c).strip() for c in (chs or []) if str(c).strip()]
            if toks:
                filtered[nm] = toks
    if not filtered and chords:
        filtered = {"Section": [str(c).strip() for c in chords if str(c).strip()]}
    if not filtered:
        return ""
    data = dict(song_data) if isinstance(song_data, dict) else {}
    data.setdefault("key", key)
    data.setdefault("title", song_name or data.get("title") or "Backing")
    try:
        from songs.backing_chart import render_backing_chord_chart

        return render_backing_chord_chart(
            str(song_name or data.get("title") or "Backing"),
            data,
            filtered,
            display_key=key,
            level=str(level or "Intermediate"),
            groove_style=str(groove_style or "Pop groove"),
            bpm=int(bpm or 100),
            time_signature=str(time_signature or "4/4"),
            selected_section_names=list(filtered.keys()),
            show_user_lyric_preview=False,
        )
    except Exception:
        return ""


def build_cycle_chart_strip_html(
    *,
    sounding_key: str,
    chords: list[str] | tuple[str, ...] = (),
    sections: dict[str, list[str]] | None = None,
    song_name: str = "",
    song_data: dict[str, Any] | None = None,
    selected_section_names: list[str] | tuple[str, ...] | None = None,
    level: str = "Intermediate",
    groove_style: str = "Pop groove",
    bpm: int = 100,
    time_signature: str = "4/4",
) -> str:
    """Compatibility alias — always the real lead sheet (never a raw chord grid)."""
    return build_cycle_lead_sheet_html(
        sounding_key=sounding_key,
        chords=chords,
        sections=sections,
        song_name=song_name,
        song_data=song_data,
        selected_section_names=selected_section_names,
        level=level,
        groove_style=groove_style,
        bpm=bpm,
        time_signature=time_signature,
    )


def render_handoff_component(
    st: Any,
    session: dict[str, Any],
    *,
    expect_cycle_id: str = "",
    armed: bool = True,
) -> dict[str, Any] | None:
    """Mount the handoff receiver; return one new playing ack per Streamlit run."""
    bag = session.get(ACKED_IDS_KEY)
    consumed = list(bag) if isinstance(bag, list) else []
    raw = _kc_handoff_component(
        expect_cycle_id=str(expect_cycle_id or session.get("_kc_cycle_id") or ""),
        armed=bool(armed),
        last_consumed_ack_id=(str(consumed[0]) if consumed else ""),
        consumed_ack_ids=consumed[:16],
        # Remount when the cycle identity changes so a prior setComponentValue
        # cannot keep replaying a stale_cycle ack across Off→On.
        key=f"kc_handoff_receiver_v2_{str(expect_cycle_id or session.get('_kc_cycle_id') or 'off')[:12]}",
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
                    {
                        k: raw.get(k)
                        for k in (
                            "kind",
                            "ackId",
                            "cycleId",
                            "passId",
                            "playingKey",
                            "batchId",
                            "count",
                        )
                    }
                    if isinstance(raw, dict)
                    else str(raw)[:120]
                ),
            },
        )
    except Exception:
        pass
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "")
    if kind == "playing_batch":
        acks_raw = raw.get("acks")
        if not isinstance(acks_raw, list):
            try:
                parsed = json.loads(str(raw.get("acks_json") or "[]"))
                acks_raw = parsed if isinstance(parsed, list) else []
            except Exception:
                acks_raw = []
        pending = session.get("_kc_handoff_pending_acks")
        if not isinstance(pending, list):
            pending = []
        for item in acks_raw:
            if not isinstance(item, dict):
                continue
            if str(item.get("kind") or "") != "playing":
                continue
            ack_id = str(item.get("ackId") or "").strip()
            if not ack_id or ack_already_consumed(session, ack_id):
                continue
            expect = str(expect_cycle_id or session.get("_kc_cycle_id") or "").strip()
            cid = str(item.get("cycleId") or "").strip()
            if expect and cid and cid != expect:
                continue
            if not any(str(p.get("ackId") or "") == ack_id for p in pending):
                pending.append(item)
        session["_kc_handoff_pending_acks"] = pending
        if pending:
            first = pending.pop(0)
            session["_kc_handoff_pending_acks"] = pending
            return first
        return None
    if kind != "playing":
        return None
    ack_id = str(raw.get("ackId") or "").strip()
    if not ack_id:
        return None
    if ack_already_consumed(session, ack_id):
        pending = session.get("_kc_handoff_pending_acks")
        if isinstance(pending, list) and pending:
            nxt = pending.pop(0)
            session["_kc_handoff_pending_acks"] = pending
            return nxt if isinstance(nxt, dict) else None
        return None
    return raw


def drain_pending_handoff_ack(session: dict[str, Any]) -> dict[str, Any] | None:
    """Pop the next queued playing ack from a prior playing_batch."""
    pending = session.get("_kc_handoff_pending_acks")
    if not isinstance(pending, list) or not pending:
        return None
    expect = str(session.get("_kc_cycle_id") or "").strip()
    while pending:
        nxt = pending.pop(0)
        if not isinstance(nxt, dict):
            continue
        cid = str(nxt.get("cycleId") or "").strip()
        if expect and cid and cid != expect:
            continue  # discard stale-cycle leftovers after Off→On
        session["_kc_handoff_pending_acks"] = pending
        return nxt
    session["_kc_handoff_pending_acks"] = pending
    return None


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
    try:
        from backing_key_cycle import key_cycle_settings_pending

        if key_cycle_settings_pending(session):
            return False, "settings_pending"
    except Exception:
        pass
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
    "build_cycle_lead_sheet_html",
    "drain_pending_handoff_ack",
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
