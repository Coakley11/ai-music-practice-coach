"""Ephemeral Backing play-session overrides — not durable song/generated/Mission state.

Lifecycle:
- Same Backing session / Streamlit rerun: overrides remain.
- Browser refresh while still on that Backing session: overrides remain (persisted in the
  workspace session bag, not in song or generated blobs).
- Leave Backing for another page: overrides expire; source identity may restore later.
- Return to Backing: restore last Backing SOURCE, seed a new play session from source defaults.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

BACKING_PLAY_SESSION_KEY = "_backing_play_session"
BACKING_PLAY_SESSION_EXPIRED_KEY = "_backing_play_session_expired"

_OVERRIDE_FIELDS = (
    "bpm",
    "groove",
    "meter",
    "meter_override",
    "scope",
    "single_section",
    "multi_sections",
    "loops",
)


def _ctx_launch_id(session: dict[str, Any]) -> str:
    try:
        from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
        if isinstance(raw, dict):
            return str(raw.get(BACKING_SESSION_LAUNCH_ID_BLOB_KEY) or "").strip()
    except ImportError:
        pass
    return ""


def _mint_launch_id(session: dict[str, Any]) -> str:
    launch_id = uuid.uuid4().hex
    try:
        from backing_context import BACKING_CONTEXT_KEY, BACKING_SESSION_LAUNCH_ID_BLOB_KEY

        raw = session.get(BACKING_CONTEXT_KEY)
        if isinstance(raw, dict):
            raw = dict(raw)
            raw[BACKING_SESSION_LAUNCH_ID_BLOB_KEY] = launch_id
            session[BACKING_CONTEXT_KEY] = raw
    except ImportError:
        pass
    return launch_id


def _source_defaults_from_session(session: dict[str, Any]) -> dict[str, Any]:
    bpm = 100
    groove = ""
    meter = "4/4"
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        if ctx is not None:
            if int(getattr(ctx, "bpm", 0) or 0) > 0:
                bpm = int(ctx.bpm)
            groove = str(getattr(ctx, "style", "") or getattr(ctx, "groove", "") or "").strip()
            meter = str(getattr(ctx, "meter", "") or meter).strip() or meter
    except ImportError:
        pass
    if not groove:
        groove = str(session.get("backing_groove_style") or "").strip()
    try:
        from songs.playback_defaults import normalize_groove_label

        if groove:
            groove = normalize_groove_label(groove)
    except ImportError:
        pass
    return {
        "bpm": int(bpm or 100),
        "groove": groove,
        "meter": meter or "4/4",
        "meter_override": False,
        "scope": "Full song",
        "single_section": "",
        "multi_sections": [],
        "loops": 2,
    }


def get_backing_play_session(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(BACKING_PLAY_SESSION_KEY)
    return raw if isinstance(raw, dict) else None


def effective_backing_play_overrides(session: dict[str, Any]) -> dict[str, Any]:
    """Resolved playback knobs: source defaults overlaid with current play-session overrides."""
    ps = get_backing_play_session(session)
    defaults = dict((ps or {}).get("defaults") or _source_defaults_from_session(session))
    overrides = dict((ps or {}).get("overrides") or {}) if ps and not ps.get("expired") else {}
    out = dict(defaults)
    for key in _OVERRIDE_FIELDS:
        if key in overrides and overrides[key] not in (None, ""):
            out[key] = copy.deepcopy(overrides[key])
    return out


def capture_backing_play_session_overrides(session: dict[str, Any]) -> dict[str, Any]:
    """Read live Backing widgets into the current play-session override bag."""
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        ps = _new_play_session(session, mint_launch=False)
    overrides = dict(ps.get("overrides") or {})
    try:
        bpm = int(session.get("backing_track_bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    if bpm > 0:
        overrides["bpm"] = bpm
    groove = str(session.get("backing_groove_style") or "").strip()
    if groove:
        overrides["groove"] = groove
    meter = str(session.get("backing_time_signature") or "").strip()
    if meter:
        overrides["meter"] = meter
    if "backing_time_signature_override" in session:
        overrides["meter_override"] = bool(session.get("backing_time_signature_override"))
    scope = str(session.get("backing_track_scope") or "").strip()
    if scope:
        overrides["scope"] = scope
    single = str(session.get("backing_track_single_section") or "").strip()
    if single:
        overrides["single_section"] = single
    multi = session.get("backing_track_multi_sections")
    if isinstance(multi, list):
        overrides["multi_sections"] = [str(s) for s in multi if str(s).strip()]
    try:
        loops = int(session.get("backing_track_loops") or 0)
    except (TypeError, ValueError):
        loops = 0
    if loops > 0:
        overrides["loops"] = loops
    ps["overrides"] = overrides
    ps["expired"] = False
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = False
    return ps


def apply_backing_play_session_to_widgets(session: dict[str, Any]) -> None:
    """Project current play-session defaults+overrides onto Backing widget keys."""
    resolved = effective_backing_play_overrides(session)
    if resolved.get("bpm"):
        session["backing_track_bpm"] = int(resolved["bpm"])
        session["bpm"] = int(resolved["bpm"])
    if resolved.get("groove"):
        session["backing_groove_style"] = str(resolved["groove"])
    if resolved.get("meter"):
        session["backing_time_signature"] = str(resolved["meter"])
    session["backing_time_signature_override"] = bool(resolved.get("meter_override"))
    if resolved.get("scope"):
        session["backing_track_scope"] = str(resolved["scope"])
    if resolved.get("single_section"):
        session["backing_track_single_section"] = str(resolved["single_section"])
    multi = resolved.get("multi_sections")
    if isinstance(multi, list):
        session["backing_track_multi_sections"] = list(multi)
    if resolved.get("loops"):
        session["backing_track_loops"] = int(resolved["loops"])


def _apply_defaults_to_widgets(session: dict[str, Any], defaults: dict[str, Any]) -> None:
    session["backing_track_bpm"] = int(defaults.get("bpm") or 100)
    session["bpm"] = int(defaults.get("bpm") or 100)
    if defaults.get("groove"):
        session["backing_groove_style"] = str(defaults["groove"])
    session["backing_time_signature"] = str(defaults.get("meter") or "4/4")
    session["backing_time_signature_override"] = bool(defaults.get("meter_override"))
    session["backing_track_scope"] = str(defaults.get("scope") or "Full song")
    session["backing_track_single_section"] = str(defaults.get("single_section") or "")
    session["backing_track_multi_sections"] = list(defaults.get("multi_sections") or [])
    session["backing_track_loops"] = int(defaults.get("loops") or 2)
    session.pop("_pending_backing_track_bpm", None)


def _new_play_session(session: dict[str, Any], *, mint_launch: bool) -> dict[str, Any]:
    launch_id = _mint_launch_id(session) if mint_launch else (_ctx_launch_id(session) or uuid.uuid4().hex)
    defaults = _source_defaults_from_session(session)
    ps = {
        "launch_id": launch_id,
        "expired": False,
        "defaults": defaults,
        "overrides": {},
    }
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = False
    return ps


def expire_backing_play_session(session: dict[str, Any]) -> None:
    """Leave-Backing: drop temporary Advanced/BPM/scope knobs; keep last source identity."""
    ps = get_backing_play_session(session) or {}
    defaults = dict(ps.get("defaults") or _source_defaults_from_session(session))
    _apply_defaults_to_widgets(session, defaults)
    ps = {
        "launch_id": str(ps.get("launch_id") or _ctx_launch_id(session) or ""),
        "expired": True,
        "defaults": defaults,
        "overrides": {},
    }
    session[BACKING_PLAY_SESSION_KEY] = ps
    session[BACKING_PLAY_SESSION_EXPIRED_KEY] = True
    try:
        from backing_track_state import (
            BACKING_DIRTY_KEY,
            BACKING_USER_EDIT_INTENT_KEY,
            BACKING_WIDGETS_SEEDED_KEY,
            gather_backing_filters,
            write_canonical_backing_state,
        )

        session.pop(BACKING_DIRTY_KEY, None)
        session.pop(BACKING_USER_EDIT_INTENT_KEY, None)
        session.pop(BACKING_WIDGETS_SEEDED_KEY, None)
        write_canonical_backing_state(
            session,
            gather_backing_filters(session),
            reason="play_session_expire",
            local_edit=False,
        )
    except ImportError:
        session.pop("backing_track_state_dirty", None)
        session.pop("_backing_user_edit_intent", None)


def expire_backing_play_session_on_page_exit(
    session: dict[str, Any],
    *,
    previous_page: str,
    new_page: str,
) -> bool:
    prev = str(previous_page or "").strip().lower()
    nxt = str(new_page or "").strip().lower()
    if prev == "backing" and nxt != "backing":
        expire_backing_play_session(session)
        return True
    return False


def sync_backing_play_session_on_backing_page(session: dict[str, Any]) -> dict[str, Any]:
    """Enter/refresh Backing: keep this play session, or seed a new one after page exit."""
    ps = get_backing_play_session(session)
    launch_id = _ctx_launch_id(session)
    expired = bool(session.get(BACKING_PLAY_SESSION_EXPIRED_KEY)) or bool((ps or {}).get("expired"))
    ps_launch = str((ps or {}).get("launch_id") or "")
    same_launch = bool(ps and not expired and (not launch_id or not ps_launch or ps_launch == launch_id))
    if same_launch:
        apply_backing_play_session_to_widgets(session)
        return ps
    ps = _new_play_session(session, mint_launch=not bool(launch_id))
    if launch_id:
        ps["launch_id"] = launch_id
        session[BACKING_PLAY_SESSION_KEY] = ps
    _apply_defaults_to_widgets(session, dict(ps.get("defaults") or {}))
    return ps


def backing_play_session_has_override(session: dict[str, Any], field: str) -> bool:
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        return False
    overrides = ps.get("overrides")
    if not isinstance(overrides, dict):
        return False
    val = overrides.get(field)
    if val in (None, "", []):
        return False
    return True


def play_session_blocks_canonical_seed(session: dict[str, Any]) -> bool:
    """True when ephemeral play-session knobs must win over canonical backing_track_state."""
    ps = get_backing_play_session(session)
    if ps is None or ps.get("expired"):
        return False
    overrides = ps.get("overrides")
    if not isinstance(overrides, dict) or not overrides:
        return False
    for key in _OVERRIDE_FIELDS:
        val = overrides.get(key)
        if val not in (None, "", []):
            return True
    return False


__all__ = [
    "BACKING_PLAY_SESSION_EXPIRED_KEY",
    "BACKING_PLAY_SESSION_KEY",
    "apply_backing_play_session_to_widgets",
    "backing_play_session_has_override",
    "capture_backing_play_session_overrides",
    "effective_backing_play_overrides",
    "expire_backing_play_session",
    "expire_backing_play_session_on_page_exit",
    "get_backing_play_session",
    "play_session_blocks_canonical_seed",
    "sync_backing_play_session_on_backing_page",
]
