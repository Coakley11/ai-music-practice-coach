"""A reopened Multitrack project brings back its saved audio.

Measured defect (scripts/_accept_mt_save_project_durability.py): after Save project, a new session -
same server, or after the server was replaced - restored the ACTIVE project id from the workspace but
not its layers (the workspace save caps a layer at 2 MiB, so a song-length layer is never in it).
The page then said "Loaded project ... 1 playable", hid the Load button because the project counted
as loaded, and asked the musician to record a layer - while the exact bytes sat in their private
storage. Only a deliberate Load called ``load_track_audio``.

This does what Load does, for the layers that are missing: once per session per project, for each
track the saved project records as playable whose slot has no audio, fetch it through the same
``load_track_audio`` (local copy first, then the cloud) and mark it a saved layer. A layer the
musician deliberately removed in this project is never brought back by it; the saved project still
holds it, and Load restores it on request.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

#: Layers deliberately removed from the active project: ``{project_id: [slot, ...]}``. Persisted, so a
#: new session respects the removal too; cleared for a project when it is saved again.
REMOVED_KEY = "_mt_removed_project_slots"
ATTEMPT_KEY = "_mt_project_audio_restore_attempted"
REPORT_KEY = "_mt_project_audio_restore_report"
#: The saved audio already fetched this session, per project and slot: a later rerun that finds the
#: slot emptied again (page-snapshot reconciliation does that, as it does to a stage-1 draft) refills
#: it from here instead of downloading again. Session only - never part of a workspace save.
CACHE_KEY = "_mt_project_audio_cache"


def _why(session_state: Any, reason: str, **extra: Any) -> None:
    """Env-gated trace of what the restore decided (sizes and reasons only, never audio)."""
    try:
        from multitrack_draft_trace import enabled, note

        if enabled():
            note(session_state, "project_audio_restore", reason=reason, **extra)
    except Exception:
        pass


def _has_audio(value: Any) -> bool:
    return isinstance(value, (bytes, bytearray)) and len(value) > 0


def note_slot_removed(session_state: Any, slot: str) -> None:
    try:
        from media_multitrack_catalog import active_catalog_multitrack_id

        mid = active_catalog_multitrack_id(session_state)
    except Exception:
        mid = ""
    if not mid:
        return
    removed = session_state.get(REMOVED_KEY)
    removed = dict(removed) if isinstance(removed, dict) else {}
    slots = list(removed.get(mid) or [])
    if slot not in slots:
        slots.append(slot)
    removed[mid] = slots
    session_state[REMOVED_KEY] = removed


def note_project_saved(session_state: Any, project_id: str) -> None:
    removed = session_state.get(REMOVED_KEY)
    if isinstance(removed, dict) and project_id in removed:
        removed = dict(removed)
        removed.pop(project_id, None)
        session_state[REMOVED_KEY] = removed


def request_retry(session_state: Any) -> None:
    session_state.pop(ATTEMPT_KEY, None)
    session_state.pop(REPORT_KEY, None)


def _refill_from_cache(session_state: Any, mid: str, slots: list, tracks_map: dict, removed: set) -> list:
    cache = session_state.get(CACHE_KEY)
    if not isinstance(cache, dict):
        return []
    filled = []
    for slot in slots:
        data = cache.get(f"{mid}::{slot}")
        if data and not _has_audio(tracks_map.get(slot)) and slot not in removed:
            tracks_map[slot] = data
            try:
                from multitrack_takes import mark_take_saved

                mark_take_saved(session_state, slot)
            except ImportError:
                pass
            filled.append(slot)
    return filled


def _active_row(session_state: Any, st: Any) -> dict | None:
    from media_multitrack_catalog import active_catalog_multitrack_id
    from media_persistence import load_media_catalog
    from media_state import migrate_multitrack_session

    mid = active_catalog_multitrack_id(session_state)
    if not mid:
        return None
    catalog = load_media_catalog(st=st)
    for row in catalog.get("multitrack_sessions") or []:
        if isinstance(row, dict) and str(row.get("multitrack_id") or "") == mid:
            return migrate_multitrack_session(row)
    return None


def restore_active_project_audio(session_state: Any, slots: Iterable[str], *, st: Any = None) -> dict:
    """Fill empty slots of the active saved project from its stored audio. Returns the report."""
    from media_multitrack_catalog import active_catalog_multitrack_id

    mid = active_catalog_multitrack_id(session_state)
    if not mid:
        _why(session_state, "no_active_project")
        return {}
    try:
        from multitrack_take_removal import layers_deliberately_empty

        if layers_deliberately_empty(session_state):
            _why(session_state, "layers_deliberately_empty", project=mid)
            return {}
    except ImportError:
        pass
    tracks_map = session_state.get("mt_tracks")
    if not isinstance(tracks_map, dict):
        tracks_map = {s: None for s in slots}
        session_state["mt_tracks"] = tracks_map
    slots = list(slots)
    if all(_has_audio(tracks_map.get(s)) for s in slots):
        return {}
    removed_now = set(((session_state.get(REMOVED_KEY) or {}).get(mid) or [])) if isinstance(session_state.get(REMOVED_KEY), dict) else set()
    refilled = _refill_from_cache(session_state, mid, slots, tracks_map, removed_now)
    if refilled:
        _why(session_state, "refilled_from_session_cache", project=mid, slots=refilled)
    attempted = session_state.get(ATTEMPT_KEY)
    if isinstance(attempted, dict) and attempted.get(mid):
        return session_state.get(REPORT_KEY) or {}
    _why(session_state, "attempting", project=mid,
         removed=sorted(((session_state.get(REMOVED_KEY) or {}).get(mid) or [])) if isinstance(session_state.get(REMOVED_KEY), dict) else [])
    session_state[ATTEMPT_KEY] = {mid: True}
    report: dict[str, Any] = {"project_id": mid, "slots": {}}
    try:
        row = _active_row(session_state, st)
    except Exception as exc:
        report["error"] = f"catalog:{type(exc).__name__}"
        session_state[REPORT_KEY] = report
        return report
    if not row:
        report["error"] = "project_not_in_library"
        session_state[REPORT_KEY] = report
        return report
    removed = set(((session_state.get(REMOVED_KEY) or {}).get(mid) or [])) if isinstance(session_state.get(REMOVED_KEY), dict) else set()

    from media_multitrack_catalog import PLAYBACK_PLAYABLE, is_real_multitrack_track, track_playback_status
    from media_storage import load_track_audio

    ws = str(row.get("workspace_id") or "daniel")
    for track in row.get("tracks") or []:
        if not isinstance(track, dict) or track.get("deleted") or not is_real_multitrack_track(track):
            continue
        slot = str(track.get("slot") or "")
        if slot not in slots or _has_audio(tracks_map.get(slot)) or slot in removed:
            continue
        status = track_playback_status(track, session_workspace=ws, st=st)
        if status != PLAYBACK_PLAYABLE:
            report["slots"][slot] = {"ok": False, "error": f"status:{status or 'none'}"}
            continue
        try:
            audio, err = load_track_audio(track, session=row, st=st)
        except Exception as exc:
            audio, err = None, f"{type(exc).__name__}"
        if not audio:
            report["slots"][slot] = {"ok": False, "error": str(err or "no_audio")}
            continue
        duration = None
        try:
            from multitrack_audio_validation import REJECTED, check_audio_bytes

            verdict = check_audio_bytes(bytes(audio), str(track.get("filename") or ""))
            if verdict.status == REJECTED:
                report["slots"][slot] = {"ok": False, "error": f"invalid_audio:{verdict.reason}"}
                continue
            duration = verdict.duration_sec
        except ImportError:
            pass
        tracks_map[slot] = bytes(audio)
        cache = session_state.get(CACHE_KEY)
        cache = cache if isinstance(cache, dict) else {}
        cache[f"{mid}::{slot}"] = bytes(audio)
        session_state[CACHE_KEY] = cache
        try:
            from multitrack_takes import mark_take_saved

            mark_take_saved(session_state, slot)
        except ImportError:
            pass
        names = session_state.get("mt_track_filenames")
        if isinstance(names, dict) and track.get("filename"):
            names.setdefault(slot, str(track.get("filename")))
        report["slots"][slot] = {"ok": True, "bytes": len(audio), "seconds": duration,
                                 "fp": hashlib.sha256(bytes(audio)).hexdigest()[:8]}
    if not session_state.get("multitrack_backing_music_wav") and (row.get("backing_storage_ref") or row.get("backing_local_path")):
        try:
            from media_storage import load_backing_audio

            audio, err = load_backing_audio(row, st=st)
            if audio:
                session_state["multitrack_backing_music_wav"] = audio
                session_state["_mt_loaded_backing_project_id"] = mid
                report["backing"] = {"ok": True, "bytes": len(audio)}
            else:
                report["backing"] = {"ok": False, "error": str(err or "no_audio")}
        except Exception as exc:
            report["backing"] = {"ok": False, "error": type(exc).__name__}
    session_state[REPORT_KEY] = report
    _why(session_state, "done", project=mid, report={k: {kk: vv for kk, vv in v.items() if kk != "fp"} for k, v in (report.get("slots") or {}).items()})
    return report


def failed_slots(report: dict | None) -> list[str]:
    if not isinstance(report, dict):
        return []
    return [s for s, r in (report.get("slots") or {}).items() if isinstance(r, dict) and not r.get("ok")]


SAVE_STATUS_KEY = "_mt_project_save_status"


def record_project_save_status(session_state: Any, fields: dict) -> dict:
    """Where each layer of the project just saved actually is: the account, or this server only."""
    try:
        from studio_history_cloud import cloud_enabled

        cloud_on = bool(cloud_enabled())
    except Exception:
        cloud_on = False
    layers: dict[str, str] = {}
    for track in (fields or {}).get("tracks") or []:
        if not isinstance(track, dict) or track.get("deleted"):
            continue
        summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
        if not (track.get("local_path") or track.get("storage_ref") or summary.get("has_audio")):
            continue
        slot = str(track.get("slot") or "")
        if track.get("cloud_verified"):
            layers[slot] = "account"
        elif track.get("local_path"):
            layers[slot] = "server_only"
        else:
            layers[slot] = "not_saved"
    backing = ""
    if (fields or {}).get("backing_storage_ref") or (fields or {}).get("backing_local_path"):
        backing = "account" if fields.get("backing_cloud_verified") else "server_only"
    status = {"cloud_enabled": cloud_on, "layers": layers, "backing": backing}
    session_state[SAVE_STATUS_KEY] = status
    return status


def project_save_message(status: dict | None, success_label: str) -> tuple[str, str]:
    """(level, text). Success only when every layer is confirmed in the account."""
    if not isinstance(status, dict):
        # MT-1: no recorded status (an exception before it was written, an older code path) is not
        # evidence that anything reached the account - it used to read as a plain success.
        return "warning", (f"{success_label}, but where the recordings were stored could not be confirmed. "
                           "Press Save Changes to try again; until then a restart of the app can lose them.")
    layers = status.get("layers") or {}
    if not status.get("cloud_enabled"):
        return "info", (f"{success_label}. Cloud storage is not set up for this app, so the recordings are "
                        "kept on this server only and a restart of the app can lose them.")
    behind = sorted(s for s, w in layers.items() if w != "account")
    if status.get("backing") == "server_only":
        behind.append("the backing track")
    if not behind:
        n = len(layers)
        return "success", f"{success_label} - {n} layer{'s' if n != 1 else ''} saved to your account."
    return "error", (f"{success_label}, but {', '.join(behind)} did NOT reach your account storage: kept on this "
                     "server only, which a restart of the app can lose. Press Save Changes to try again.")
