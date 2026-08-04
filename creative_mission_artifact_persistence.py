"""Mission Creative artifacts (motif, generated example, practice lick) — Phase 1 Item 3."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    write_canonical_creative_workspace,
)
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MISSION_NEW_NONCE_KEY,
    MISSION_PRACTICE_LICK_KEY,
    MISSION_VARIANT_KEY,
)

CREATIVE_MISSION_ARTIFACT_DIAG_KEY = "_creative_mission_artifact_diag"
CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY = "_creative_mission_artifact_hydrated_snapshot"
CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY = "_creative_mission_artifact_last_user_event"
CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY = "_creative_mission_artifact_save_active_tx"

SAVE_REASON_MOTIF = "creative_motif_change"
SAVE_REASON_MISSION_EXAMPLE = "creative_mission_example_change"
SAVE_REASON_PRACTICE_LICK = "creative_mission_practice_lick_change"

MISSION_ARTIFACT_SAVE_REASONS: frozenset[str] = frozenset(
    {
        SAVE_REASON_MOTIF,
        SAVE_REASON_MISSION_EXAMPLE,
        SAVE_REASON_PRACTICE_LICK,
    }
)

VIOLATION_PASSIVE_ARTIFACT_STARTUP_WRITE = "CREATIVE_MISSION_ARTIFACT_PASSIVE_STARTUP_WRITE"

# Item 3 — user-created / generated artifacts (not mission config Item 2).
MISSION_ARTIFACT_CANONICAL_KEYS: tuple[str, ...] = (
    "improv_motif",
    "improv_motif_output_mode",
    "improv_motif_abc",
    "improv_motif_tab",
    MISSION_EXAMPLE_KEY,
    MISSION_VARIANT_KEY,
    MISSION_NEW_NONCE_KEY,
    MISSION_PRACTICE_LICK_KEY,
)


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(CREATIVE_MISSION_ARTIFACT_DIAG_KEY)
    if not isinstance(d, dict):
        d = {}
        session[CREATIVE_MISSION_ARTIFACT_DIAG_KEY] = d
    return d


def _run_seq(session: dict[str, Any]) -> int:
    try:
        return int(session.get("_script_run_seq") or 0)
    except (TypeError, ValueError):
        return 0


def is_mission_artifact_save_reason(reason: str) -> bool:
    return str(reason or "").strip() in MISSION_ARTIFACT_SAVE_REASONS


def record_mission_artifact_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)


def canonical_mission_artifact_value(session: dict[str, Any], key: str) -> Any:
    if key not in MISSION_ARTIFACT_CANONICAL_KEYS:
        return session.get(key)
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict) and key in blob:
        return copy.deepcopy(blob[key])
    return copy.deepcopy(session.get(key)) if key in session else None


def mission_artifact_configured_in_canonical(session: dict[str, Any], key: str) -> bool:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    return isinstance(blob, dict) and key in blob


def _artifact_slice(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in MISSION_ARTIFACT_CANONICAL_KEYS:
        if key in session:
            out[key] = copy.deepcopy(session[key])
    return out


def commit_mission_artifacts_to_canonical(
    session: dict[str, Any],
    *,
    reason: str,
    values: dict[str, Any] | None = None,
    removed_keys: tuple[str, ...] = (),
) -> None:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    base = copy.deepcopy(blob) if isinstance(blob, dict) else default_creative_workspace_state()
    slice_ = copy.deepcopy(values) if values is not None else _artifact_slice(session)
    for k, v in slice_.items():
        base[k] = copy.deepcopy(v)
    for k in removed_keys:
        base.pop(k, None)
    write_canonical_creative_workspace(session, base, reason=reason)


def snapshot_hydrated_mission_artifacts(session: dict[str, Any], *, source: str = "prepare") -> None:
    snap = {k: canonical_mission_artifact_value(session, k) for k in MISSION_ARTIFACT_CANONICAL_KEYS}
    session[CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY] = snap
    d = _diag(session)
    d["hydrated_mission_artifacts"] = copy.deepcopy(snap)
    d["hydration_source"] = source


def project_mission_artifacts_from_canonical(session: dict[str, Any], *, overwrite: bool = False) -> None:
    user_ev = session.get(CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY)
    user_field = str((user_ev or {}).get("field") or "") if isinstance(user_ev, dict) else ""
    session_fp = str(session.get("_mission_example_output_fp") or "")
    for key in MISSION_ARTIFACT_CANONICAL_KEYS:
        if not mission_artifact_configured_in_canonical(session, key):
            continue
        val = canonical_mission_artifact_value(session, key)
        if val is None:
            continue
        if key == "improv_motif" and isinstance(val, dict) and not val.get("notes"):
            continue
        if key == MISSION_EXAMPLE_KEY and overwrite and key in session:
            try:
                from improvisation_missions import mission_example_fingerprint, load_mission_example
                from improvisation_intelligence import ImprovSessionContext

                raw = session.get(MISSION_EXAMPLE_KEY)
                if isinstance(raw, dict) and session_fp:
                    ctx = ImprovSessionContext(
                        song_title=str(session.get("song") or "Song"),
                        artist=str(session.get("artist") or ""),
                        key_center=str(session.get("concert_key") or session.get("display_key") or "C"),
                        display_key=str(session.get("display_key") or "C"),
                        instrument=str(session.get("instrument") or "Guitar"),
                        level=str(session.get("level") or "Intermediate"),
                        focus=str(session.get("focus") or "Improvisation"),
                        sections={},
                    )
                    loaded = load_mission_example(session, ctx)
                    if loaded and mission_example_fingerprint(loaded) == session_fp:
                        continue
            except Exception:
                pass
        if key == MISSION_EXAMPLE_KEY and user_field == MISSION_EXAMPLE_KEY:
            canon = canonical_mission_artifact_value(session, key)
            if canon is not None and session.get(key) == canon:
                continue
        if overwrite or key not in session:
            session[key] = copy.deepcopy(val)
    d = _diag(session)
    d["projection_source"] = "creative_workspace_state"


def should_gather_mission_artifact_from_session(
    session: dict[str, Any],
    key: str,
    session_val: Any,
    *,
    persist_reason: str = "autosave",
) -> bool:
    if key not in MISSION_ARTIFACT_CANONICAL_KEYS:
        return True
    if persist_reason in MISSION_ARTIFACT_SAVE_REASONS:
        return False
    if session.get(CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY):
        return False
    try:
        from creative_mission_config_persistence import mission_passive_sync_suppressed_this_run

        if mission_passive_sync_suppressed_this_run(session, reason=persist_reason):
            return False
    except ImportError:
        pass
    try:
        from creative_tab_tool_persistence import selector_hydration_complete
        from creative_workspace_state_persistence import CREATIVE_WORKSPACE_RESTORED_KEY

        if session.get(CREATIVE_WORKSPACE_RESTORED_KEY) and not session.get("_creative_workspace_restored_applied"):
            return False
        if not selector_hydration_complete(session):
            return False
    except ImportError:
        pass
    if mission_artifact_configured_in_canonical(session, key):
        canon = canonical_mission_artifact_value(session, key)
        if session_val != canon:
            return False
        return True
    if persist_reason in ("autosave", "force_autosave", ""):
        return False
    return True


def note_passive_mission_artifact_persist(session: dict[str, Any], *, reason: str) -> None:
    if reason in MISSION_ARTIFACT_SAVE_REASONS:
        return
    if reason == "page_change":
        return
    try:
        from creative_mission_config_persistence import mission_passive_sync_suppressed_this_run

        if mission_passive_sync_suppressed_this_run(session, reason=reason):
            return
    except ImportError:
        pass
    snap = session.get(CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if session.get(CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY):
        return
    for key in MISSION_ARTIFACT_CANONICAL_KEYS:
        if canonical_mission_artifact_value(session, key) != snap.get(key):
            try:
                from creative_mission_config_persistence import (
                    CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY,
                )

                session[CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY] = True
            except ImportError:
                pass
            record_mission_artifact_violation(session, VIOLATION_PASSIVE_ARTIFACT_STARTUP_WRITE, detail=reason)
            return


def _mark_user_save_this_run(session: dict[str, Any]) -> None:
    session["_creative_mission_user_save_this_run"] = _run_seq(session)


def begin_mission_artifact_save_tx(session: dict[str, Any], *, save_reason: str, field: str) -> str:
    tx_id = f"artifact-save-{_run_seq(session)}-{uuid.uuid4().hex[:8]}"
    session[CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY] = {
        "transaction_id": tx_id,
        "save_reason": save_reason,
        "field": field,
        "run_seq": _run_seq(session),
    }
    return tx_id


def request_mission_artifact_cloud_save(session: dict[str, Any], *, save_reason: str) -> bool:
    d = _diag(session)
    d["cloud_save_requested"] = True
    try:
        import streamlit as st
    except ImportError:
        return False
    try:
        from music_persistent_state import build_music_disk_state, force_save_music_state

        ok = force_save_music_state(st, reason=save_reason)
        d["cloud_save_ok"] = bool(ok)
        if ok:
            _mark_user_save_this_run(session)
        session.pop(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY, None)
        return bool(ok)
    except ImportError:
        try:
            from music_workspace_cloud_save import force_music_workspace_save

            ok = force_music_workspace_save(
                st,
                reason=save_reason,
                build_state=build_music_disk_state,
            )
            d["cloud_save_ok"] = bool(ok)
            if ok:
                _mark_user_save_this_run(session)
            session.pop(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY, None)
            return bool(ok)
        except ImportError:
            return False


def _handle_user_artifact_change(
    session: dict[str, Any],
    *,
    save_reason: str,
    field: str,
    interaction: str,
    removed_keys: tuple[str, ...] = (),
) -> None:
    begin_mission_artifact_save_tx(session, save_reason=save_reason, field=field)
    session[CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY] = {
        "field": field,
        "save_reason": save_reason,
        "run_seq": _run_seq(session),
        "interaction": interaction or None,
    }
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        try:
            from improvisation_mission_persistence import mark_mission_workspace_dirty

            mark_mission_workspace_dirty(session)
        except ImportError:
            pass
    values = _artifact_slice(session)
    commit_mission_artifacts_to_canonical(
        session,
        reason=save_reason,
        values=values,
        removed_keys=removed_keys,
    )
    snapshot_hydrated_mission_artifacts(session, source=f"user_save:{save_reason}")
    try:
        from creative_artifact_global_key_guard import freeze_global_keys_for_creative_artifact_save

        freeze_global_keys_for_creative_artifact_save(
            session,
            save_reason=save_reason,
            caller="_handle_user_artifact_change",
        )
    except ImportError:
        pass
    request_mission_artifact_cloud_save(session, save_reason=save_reason)


def handle_user_motif_artifact_change(session: dict[str, Any], *, interaction: str = "") -> None:
    _handle_user_artifact_change(
        session,
        save_reason=SAVE_REASON_MOTIF,
        field="improv_motif",
        interaction=interaction or "motif_user_edit",
    )


def handle_user_mission_example_artifact_saved(session: dict[str, Any], *, interaction: str = "") -> None:
    _handle_user_artifact_change(
        session,
        save_reason=SAVE_REASON_MISSION_EXAMPLE,
        field=MISSION_EXAMPLE_KEY,
        interaction=interaction or "mission_example_saved",
    )


def handle_user_mission_practice_lick_saved(session: dict[str, Any], *, interaction: str = "") -> None:
    _handle_user_artifact_change(
        session,
        save_reason=SAVE_REASON_PRACTICE_LICK,
        field=MISSION_PRACTICE_LICK_KEY,
        interaction=interaction or "mission_practice_lick_saved",
    )


def commit_mission_practice_lick_for_navigation_handoff(
    session: dict[str, Any],
    *,
    interaction: str = "",
) -> None:
    """Commit practice lick to canonical for the next ``page_change`` save — no artifact cloud write."""
    field = MISSION_PRACTICE_LICK_KEY
    session[CREATIVE_MISSION_ARTIFACT_USER_EVENT_KEY] = {
        "field": field,
        "save_reason": SAVE_REASON_PRACTICE_LICK,
        "run_seq": _run_seq(session),
        "interaction": interaction or "store_practice_lick_for_backing",
        "defer_cloud_until_page_change": True,
    }
    try:
        from creative_workspace_persistence import mark_creative_workspace_dirty

        mark_creative_workspace_dirty(session)
    except ImportError:
        try:
            from improvisation_mission_persistence import mark_mission_workspace_dirty

            mark_mission_workspace_dirty(session)
        except ImportError:
            pass
    values = _artifact_slice(session)
    commit_mission_artifacts_to_canonical(
        session,
        reason=SAVE_REASON_PRACTICE_LICK,
        values=values,
        removed_keys=(),
    )
    snapshot_hydrated_mission_artifacts(session, source="handoff:defer_cloud_until_page_change")
    try:
        from creative_artifact_global_key_guard import freeze_global_keys_for_creative_artifact_save

        freeze_global_keys_for_creative_artifact_save(
            session,
            save_reason=SAVE_REASON_PRACTICE_LICK,
            caller="commit_mission_practice_lick_for_navigation_handoff",
        )
    except ImportError:
        pass


def clear_mission_example_from_canonical(session: dict[str, Any], *, reason: str = "artifact_clear") -> None:
    """Explicit clear — removes example blob from canonical (session keys should already be popped)."""
    commit_mission_artifacts_to_canonical(
        session,
        reason=reason,
        values={},
        removed_keys=(MISSION_EXAMPLE_KEY, MISSION_VARIANT_KEY),
    )


def collect_creative_mission_artifact_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    d = dict(_diag(session))
    d.setdefault("hydrated_mission_artifacts", session.get(CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY))
    d.setdefault(
        "canonical_values",
        {k: canonical_mission_artifact_value(session, k) for k in MISSION_ARTIFACT_CANONICAL_KEYS},
    )
    d.setdefault(
        "session_artifact_values",
        {k: copy.deepcopy(session.get(k)) for k in MISSION_ARTIFACT_CANONICAL_KEYS if k in session},
    )
    d.setdefault("violations", d.get("violations") or [])
    try:
        from creative_mission_config_persistence import CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY

        d.setdefault(
            "startup_write_attempted",
            bool(session.get(CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY)),
        )
    except ImportError:
        d.setdefault("startup_write_attempted", False)
    return d


__all__ = [
    "CREATIVE_MISSION_ARTIFACT_HYDRATED_SNAPSHOT_KEY",
    "CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY",
    "MISSION_ARTIFACT_CANONICAL_KEYS",
    "MISSION_ARTIFACT_SAVE_REASONS",
    "SAVE_REASON_MISSION_EXAMPLE",
    "SAVE_REASON_MOTIF",
    "SAVE_REASON_PRACTICE_LICK",
    "VIOLATION_PASSIVE_ARTIFACT_STARTUP_WRITE",
    "canonical_mission_artifact_value",
    "clear_mission_example_from_canonical",
    "collect_creative_mission_artifact_diagnostics",
    "commit_mission_artifacts_to_canonical",
    "handle_user_mission_example_artifact_saved",
    "commit_mission_practice_lick_for_navigation_handoff",
    "handle_user_mission_practice_lick_saved",
    "handle_user_motif_artifact_change",
    "is_mission_artifact_save_reason",
    "note_passive_mission_artifact_persist",
    "project_mission_artifacts_from_canonical",
    "should_gather_mission_artifact_from_session",
    "snapshot_hydrated_mission_artifacts",
]
