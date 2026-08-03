"""Re-sync authoritative workspace fields from hydrated cloud snapshot (startup only, no save)."""

from __future__ import annotations

import copy
from typing import Any

_GUITAR_CAPO_KEYS: frozenset[str] = frozenset(
    {
        "guitar_capo_enabled",
        "guitar_capo_sounding_key",
        "guitar_capo_shape_key",
        "guitar_capo_last_concert_key",
    }
)


def _resolved_instrument(session: dict[str, Any], payload: dict[str, Any]) -> str:
    for blob in (
        session.get("active_song_state"),
        session,
        payload.get("active_song_state"),
        payload.get("core"),
    ):
        if isinstance(blob, dict):
            inst = str(blob.get("instrument") or "").strip()
            if inst:
                return inst
    return ""


def _merge_envelope_filters(session: dict[str, Any], payload: dict[str, Any]) -> None:
    ws_in = payload.get("music_workspace_state")
    if not isinstance(ws_in, dict):
        return
    ws = session.get("music_workspace_state")
    if not isinstance(ws, dict):
        ws = {}
    ws = copy.deepcopy(ws)
    for key in ("backing_filters", "practice_filters"):
        block = ws_in.get(key)
        if isinstance(block, dict) and block:
            ws[key] = copy.deepcopy(block)
    active_in = ws_in.get("active_song")
    if isinstance(active_in, dict):
        active_out = ws.get("active_song")
        if not isinstance(active_out, dict):
            active_out = {}
        src = str(active_in.get("music_source") or active_in.get("source_type") or "").strip()
        if src:
            active_out["music_source"] = src
            active_out.pop("source_type", None)
        for k, v in active_in.items():
            if k in ("source_type", "label"):
                continue
            if v is not None and v != "":
                active_out[k] = copy.deepcopy(v)
        ws["active_song"] = active_out
    session["music_workspace_state"] = ws


def _strip_inactive_guitar_capo_from_canonical(session: dict[str, Any], payload: dict[str, Any]) -> None:
    if _resolved_instrument(session, payload) == "Guitar":
        try:
            from guitar_capo import CAPO_ENABLED_KEY

            if session.get(CAPO_ENABLED_KEY):
                return
        except ImportError:
            pass
    ass = session.get("active_song_state")
    if isinstance(ass, dict):
        for key in _GUITAR_CAPO_KEYS:
            ass.pop(key, None)
    for key in _GUITAR_CAPO_KEYS:
        session.pop(key, None)


def align_authoritative_canonical_from_hydrated(
    session: dict[str, Any],
    payload: dict[str, Any] | None,
) -> None:
    """
    Copy cloud-authoritative backing/practice/source fields into session before fingerprint compare.

    Does not enqueue cloud writes or mark suite local dirty.
    """
    if not isinstance(payload, dict) or not payload:
        return

    try:
        from display_key_startup_save_queue import has_queued_display_key_change

        if has_queued_display_key_change(session):
            return
    except ImportError:
        pass

    try:
        from backing_track_state import (
            apply_cloud_backing_state_if_allowed,
            clear_backing_local_edit,
        )

        clear_backing_local_edit(session)
        apply_cloud_backing_state_if_allowed(session, payload)
    except ImportError:
        pass

    try:
        from practice_state import (
            apply_cloud_practice_state_if_allowed,
            clear_practice_local_edit,
        )

        clear_practice_local_edit(session)
        apply_cloud_practice_state_if_allowed(session, payload, authoritative=True)
    except ImportError:
        pass

    try:
        from active_song_state import (
            apply_cloud_active_song_state_if_allowed,
            clear_active_song_local_edit,
        )

        clear_active_song_local_edit(session)
        apply_cloud_active_song_state_if_allowed(session, payload)
    except ImportError:
        pass

    _merge_envelope_filters(session, payload)

    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict):
        active = ws.get("active_song")
        if isinstance(active, dict):
            src = str(active.get("music_source") or active.get("source_type") or "").strip()
            if src:
                session["active_music_source"] = src
                ass = session.get("active_song_state")
                if isinstance(ass, dict):
                    ass["music_source"] = src

    for top_key in (
        "backing_track_state",
        "practice_state",
        "active_song_state",
        "studio_nav_state",
        "practice_workspace_state",
    ):
        block = payload.get(top_key)
        if isinstance(block, dict) and block:
            cur = session.get(top_key)
            if not isinstance(cur, dict):
                cur = {}
            merged = copy.deepcopy(cur)
            for field in (
                "backing_track_bpm",
                "backing_groove_style",
                "practice_minutes",
                "practice_groove_style",
                "music_source",
            ):
                if field in block and block[field] not in (None, ""):
                    merged[field] = copy.deepcopy(block[field])
            session[top_key] = merged

    _strip_inactive_guitar_capo_from_canonical(session, payload)


__all__ = ["align_authoritative_canonical_from_hydrated"]
