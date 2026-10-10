"""Developer-only Backing source-ownership snapshots.

Backing resolves its identity from several independent places: the Songs-page
source, the backing context, the Practice Key control owner, the key-cycle
owner, the play session and the async generation request. When those disagree
the UI shows a mix of two songs' identities, which is impossible to diagnose
from the rendered page alone.

``snapshot_backing_identity`` records all of them together so a transition
sequence can be replayed and the *first* point of divergence located.

Off unless ``BACKING_OWNER_TRACE`` is set; never rendered on the user-facing
page. The latest snapshot is also kept in session for the developer expander.
"""

from __future__ import annotations

import os
from typing import Any

LATEST_SNAPSHOT_KEY = "_backing_owner_identity_snapshot"
TRACE_ENV = "BACKING_OWNER_TRACE"


def trace_enabled() -> bool:
    return str(os.environ.get(TRACE_ENV) or "").strip() in {"1", "true", "True"}


def _s(val: Any) -> str:
    return str(val or "").strip()


def _ctx(session: dict[str, Any]) -> Any | None:
    try:
        from backing_context import get_backing_context

        return get_backing_context(session)
    except Exception:
        return None


def _pk_control_owner(session: dict[str, Any]) -> str:
    try:
        from backing_practice_key_control import resolve_backing_pk_control_owner

        return _s(resolve_backing_pk_control_owner(session))
    except Exception:
        return ""


def _canonical_pk(session: dict[str, Any], owner: str) -> str:
    try:
        from backing_practice_key_control import canonical_concert_key_for_owner

        return _s(canonical_concert_key_for_owner(session, owner))
    except Exception:
        return ""


def _widget_pk(session: dict[str, Any], owner: str) -> tuple[str, str]:
    try:
        from backing_practice_key_control import WIDGET_BY_OWNER

        key = WIDGET_BY_OWNER.get(owner, "")
    except Exception:
        key = ""
    return key, _s(session.get(key)) if key else ""


def _all_pk_widgets(session: dict[str, Any]) -> dict[str, str]:
    try:
        from backing_practice_key_control import WIDGET_BY_OWNER

        names = tuple(WIDGET_BY_OWNER.values())
    except Exception:
        return {}
    return {n: _s(session.get(n)) for n in names if _s(session.get(n))}


def _live_source(session: dict[str, Any]) -> str:
    try:
        from creative_key_sync import live_backing_source

        return _s(live_backing_source(session))
    except Exception:
        return ""


def _play_owner(session: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from backing_play_session import (
            BACKING_PLAY_SESSION_KEY,
            get_backing_play_session,
            resolve_backing_source_identity,
        )

        out["identity"] = _s(resolve_backing_source_identity(session))
        ps = get_backing_play_session(session)
        if isinstance(ps, dict):
            out["session_identity"] = _s(ps.get("source_identity") or ps.get("identity"))
            out["session_launch"] = _s(ps.get("launch_id"))
        out["raw_present"] = "1" if session.get(BACKING_PLAY_SESSION_KEY) else "0"
    except Exception:
        pass
    return out


def _persisted_pk(session: dict[str, Any], pick: str) -> str:
    if not pick:
        return ""
    try:
        from songs.practice_key_state import get_practice_concert_key

        return _s(get_practice_concert_key(session, pick, default=""))
    except Exception:
        return ""


def collect_backing_identity(session: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """One flat snapshot of every Backing identity authority."""
    ctx = _ctx(session)
    owner = _pk_control_owner(session)
    widget_key, widget_pk = _widget_pk(session, owner)
    pick = _s(session.get("active_catalog_pick_key"))

    cycle_owner = ""
    kc_base = ""
    try:
        from backing_key_cycle import (
            current_backing_owner_practice_key,
            get_owner_cycle_session,
            resolve_cycle_owner,
        )

        cycle_owner = _s(resolve_cycle_owner(session))
        kc_base = _s(current_backing_owner_practice_key(session))
        bag = get_owner_cycle_session(session, cycle_owner) if cycle_owner else None
        if isinstance(bag, dict):
            extra.setdefault("kc_bag_base", _s(bag.get("base_practice_key")))
            extra.setdefault("kc_bag_enabled", bool(bag.get("enabled")))
    except Exception:
        pass

    snap: dict[str, Any] = {
        # 1-3: source kind / id / title
        "src_kind_live": _live_source(session),
        "src_kind_ctx": _s(getattr(ctx, "source", "")) if ctx is not None else "",
        "src_id_active_pick": pick,
        "src_id_ctx_signature": _s(getattr(ctx, "source_signature", "")) if ctx is not None else "",
        "src_title_ctx": _s(getattr(ctx, "source_label", "")) if ctx is not None else "",
        "src_title_active": _s(session.get("active_song_title") or session.get("selected_song_title")),
        # 4-5: canonical vs widget Practice Key
        "pk_control_owner": owner,
        "pk_canonical": _canonical_pk(session, owner),
        "pk_widget_key": widget_key,
        "pk_widget": widget_pk,
        "pk_widgets_all": _all_pk_widgets(session),
        "pk_global_display_key": _s(session.get("display_key")),
        "pk_global_concert_key": _s(session.get("concert_key")),
        "pk_persisted_for_active_pick": _persisted_pk(session, pick),
        # 6: key-cycle view of the same thing
        "cycle_owner": cycle_owner,
        "cycle_base_pk": kc_base,
        # 7: playback session owner
        "play": _play_owner(session),
        # 8: pending async generation owner
        "async_building_signature": _s(session.get("_backing_wav_building_signature")),
        "last_backing_signature": _s(session.get("_last_backing_signature")),
        "presentation_session_id": _s(session.get("_backing_presentation_session_id")),
        "bpm_sync_id": _s(session.get("_backing_page_bpm_sync_id")),
        # misc ownership pointers
        "studio_page": _s(session.get("studio_page")),
        "active_music_source": _s(session.get("active_music_source")),
        "kc_ui_error": _s(session.get("_backing_key_cycle_ui_error")),
    }
    snap.update(extra)
    return snap


def snapshot_backing_identity(
    session: dict[str, Any], event: str, **extra: Any
) -> dict[str, Any] | None:
    """Record one labelled snapshot. Returns it, or None when tracing is off."""
    try:
        snap = collect_backing_identity(session, **extra)
    except Exception:
        return None
    snap["event"] = str(event)
    try:
        session[LATEST_SNAPSHOT_KEY] = snap
    except Exception:
        pass
    if not trace_enabled():
        return snap
    try:
        import json
        import time
        from pathlib import Path

        snap["t"] = time.time()
        data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_backing_owner")
        data.mkdir(parents=True, exist_ok=True)
        with (data / "_backing_owner_trace.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(snap, default=str) + "\n")
    except Exception:
        pass
    return snap


def render_backing_identity_diagnostics(st: Any, session: dict[str, Any]) -> None:
    """Developer-only view of the latest ownership snapshot."""
    snap = session.get(LATEST_SNAPSHOT_KEY)
    if not isinstance(snap, dict) or not snap:
        snap = collect_backing_identity(session)
    st.markdown("**Backing source ownership**")
    st.json(snap)


__all__ = (
    "LATEST_SNAPSHOT_KEY",
    "TRACE_ENV",
    "collect_backing_identity",
    "render_backing_identity_diagnostics",
    "snapshot_backing_identity",
    "trace_enabled",
)
