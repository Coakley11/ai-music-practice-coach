"""Item 4 — Harmony Map + Creative session context snapshots (no competing global SSOT)."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from creative_workspace_state_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    default_creative_workspace_state,
    write_canonical_creative_workspace,
)

CREATIVE_CONTEXT_DIAG_KEY = "_creative_context_snapshot_diag"
CREATIVE_CONTEXT_USER_EVENT_KEY = "_creative_context_snapshot_user_event"
CREATIVE_CONTEXT_SAVE_ACTIVE_KEY = "_creative_context_snapshot_save_active_tx"
CREATIVE_CONTEXT_HYDRATED_SNAPSHOT_KEY = "_creative_context_snapshot_hydrated"
CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY = "_creative_context_item4_last_save_diag"

ITEM4_DEV_PANEL_HEADING = "Creative context snapshots (Item 4)"

ITEM4_DEV_PANEL_KEYS: tuple[str, ...] = (
    "last_user_interaction",
    "save_reason",
    "current_section_tuple",
    "harmony_map",
    "creative_session_tool",
    "creative_session_key_snapshot",
    "creative_context_snapshot",
    "artifact_context_snapshot",
    "global_keys_before",
    "global_keys_after",
    "global_keys",
    "authoritative_field_owners",
    "envelope_field_presence",
    "cloud_save_requested",
    "cloud_save_ok",
    "cloud_confirmed",
    "payload_revision",
    "cloud_write_attempted",
    "cloud_write_succeeded",
    "startup_write_attempted",
    "violations",
)

_AUTHORITATIVE_FIELD_OWNERS: dict[str, str] = {
    "instrument": "global_session_active_song",
    "level": "global_session_active_song",
    "focus": "global_session_active_song",
    "display_key": "global_session_active_song",
    "ii_selected_section": "creative_workspace_item2_tuple",
    "ii_selected_chord_index": "creative_workspace_item2_tuple",
    "ii_selected_chord": "creative_workspace_item2_tuple",
    "ii_selected_chord_label": "creative_workspace_item2_tuple",
    "harmony_map_section": "creative_workspace_item4",
    "harmony_map_chord": "creative_workspace_item4",
    "creative_session": "creative_workspace_item4_derived",
    "improv_mission_example": "creative_workspace_item3_artifact_historical",
    "improv_mission_practice_lick": "creative_workspace_item3_artifact_historical",
}

SAVE_REASON_CONTEXT_SECTION = "creative_context_section_change"
SAVE_REASON_CONTEXT_SNAPSHOT = "creative_context_snapshot_change"

CONTEXT_SNAPSHOT_SAVE_REASONS: frozenset[str] = frozenset(
    {
        SAVE_REASON_CONTEXT_SECTION,
        SAVE_REASON_CONTEXT_SNAPSHOT,
    }
)

CREATIVE_CONTEXT_CANONICAL_KEYS: tuple[str, ...] = (
    "harmony_map_section",
    "harmony_map_chord",
    "creative_session",
    "improv_generated_sections",
    "improv_style_meta",
    "improv_jam_session",
    "deep_harmony_lesson_step",
    "improv_deep_harmony_dha_section_idx",
)

VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE = "CREATIVE_CONTEXT_PASSIVE_STARTUP_WRITE"
VIOLATION_SNAPSHOT_MUTATED_GLOBAL_KEY = "CREATIVE_CONTEXT_SNAPSHOT_MUTATED_GLOBAL_KEY"
VIOLATION_PARTIAL_SECTION_TUPLE = "CREATIVE_CONTEXT_PARTIAL_SECTION_TUPLE"
VIOLATION_MUTATED_ARTIFACT_CONTEXT = "CREATIVE_CONTEXT_MUTATED_ARTIFACT_CONTEXT"
VIOLATION_ARTIFACT_OVERWROTE_GLOBAL = "CREATIVE_CONTEXT_ARTIFACT_OVERWROTE_GLOBAL"
VIOLATION_ENVELOPE_FIELD_DROPPED = "CREATIVE_CONTEXT_ENVELOPE_FIELD_DROPPED"
VIOLATION_CLOUD_CONFIRMATION_MISMATCH = "CREATIVE_CONTEXT_CLOUD_CONFIRMATION_MISMATCH"

_ENVELOPE_GUARD_KEYS: tuple[str, ...] = ()
try:
    from creative_tab_tool_persistence import SAVE_REASON_TAB, SAVE_REASON_TOOL  # noqa: F401
except ImportError:
    pass


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    raw = session.get(CREATIVE_CONTEXT_DIAG_KEY)
    if not isinstance(raw, dict):
        raw = {"violations": [], "events": []}
        session[CREATIVE_CONTEXT_DIAG_KEY] = raw
    return raw


def record_context_violation(session: dict[str, Any], code: str, *, detail: str = "") -> None:
    d = _diag(session)
    violations = d.setdefault("violations", [])
    if not isinstance(violations, list):
        violations = []
        d["violations"] = violations
    entry = {"code": code, "detail": detail or None}
    if entry not in violations:
        violations.append(entry)


def is_context_snapshot_save_reason(reason: str) -> bool:
    return str(reason or "").strip() in CONTEXT_SNAPSHOT_SAVE_REASONS


def _context_slice(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in CREATIVE_CONTEXT_CANONICAL_KEYS:
        if key in session:
            out[key] = copy.deepcopy(session[key])
    return out


def canonical_context_value(session: dict[str, Any], key: str) -> Any:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict) and key in blob:
        return copy.deepcopy(blob[key])
    return copy.deepcopy(session.get(key)) if key in session else None


def context_configured_in_canonical(session: dict[str, Any], key: str) -> bool:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    return isinstance(blob, dict) and key in blob


def _persist_item4_last_save_diag(session: dict[str, Any], patch: dict[str, Any]) -> None:
    last = session.get(CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY)
    merged: dict[str, Any] = dict(last) if isinstance(last, dict) else {}
    merged.update({k: v for k, v in patch.items() if v is not None})
    session[CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY] = copy.deepcopy(merged)
    d = _diag(session)
    for k, v in merged.items():
        if v is not None:
            d[k] = copy.deepcopy(v)


def _artifact_context_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY

        for art_key in (MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY):
            blob = canonical_context_value(session, art_key)
            if not isinstance(blob, dict):
                continue
            out[art_key] = {
                "key_center": blob.get("key_center") or blob.get("display_key"),
                "section_label": blob.get("section_label") or blob.get("section"),
                "chord": blob.get("chord"),
                "mission_title": blob.get("mission_title"),
            }
    except ImportError:
        pass
    return out


def _creative_context_snapshot_view(session: dict[str, Any]) -> dict[str, Any]:
    cs = canonical_context_value(session, "creative_session")
    view: dict[str, Any] = {
        "harmony_map_section": canonical_context_value(session, "harmony_map_section"),
        "harmony_map_chord": canonical_context_value(session, "harmony_map_chord"),
    }
    if isinstance(cs, dict):
        view["creative_session"] = {
            "tool_type": cs.get("tool_type"),
            "entry_mode": cs.get("entry_mode"),
            "selected_section": cs.get("selected_section"),
            "display_key_snapshot": cs.get("display_key") or cs.get("concert_key"),
        }
    return view


def _merge_workspace_tx_into_item4_diag(session: dict[str, Any], d: dict[str, Any]) -> None:
    reason = str(
        session.get("_suite_persist_last_save_reason")
        or session.get("_music_build_save_reason")
        or ""
    ).strip()
    tx = session.get("_music_workspace_save_transaction")
    if not isinstance(tx, dict):
        return
    tx_reason = str(tx.get("force_save_reason") or tx.get("raw_save_reason") or reason or "").strip()
    if tx_reason not in CONTEXT_SNAPSHOT_SAVE_REASONS and reason not in CONTEXT_SNAPSHOT_SAVE_REASONS:
        return
    for key in (
        "reserved_write_revision",
        "cloud_write_attempted",
        "cloud_write_succeeded",
        "cloud_upsert_succeeded",
        "cloud_confirmed",
    ):
        val = tx.get(key)
        if val is not None:
            if key == "reserved_write_revision":
                d.setdefault("payload_revision", val)
            elif key == "cloud_upsert_succeeded":
                d.setdefault("cloud_write_succeeded", val)
            else:
                d.setdefault(key, val)
    d.setdefault("save_reason", tx_reason or reason or None)


def _mission_target_tuple(session: dict[str, Any]) -> dict[str, Any]:
    try:
        from creative_mission_config_persistence import (
            MISSION_TARGET_IDENTITY_KEYS,
            canonical_mission_config_value,
        )

        return {k: canonical_mission_config_value(session, k) for k in MISSION_TARGET_IDENTITY_KEYS}
    except ImportError:
        keys = (
            "ii_selected_section",
            "ii_selected_chord_index",
            "ii_selected_chord",
            "ii_selected_chord_label",
        )
        return {k: session.get(k) for k in keys}


def default_item4_dev_diag(session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session or {}
    return {
        "last_user_interaction": None,
        "save_reason": None,
        "current_section_tuple": _mission_target_tuple(session) if session else {},
        "harmony_map": {
            "section": canonical_context_value(session, "harmony_map_section") if session else None,
            "chord": canonical_context_value(session, "harmony_map_chord") if session else None,
        },
        "creative_session_tool": None,
        "creative_session_key_snapshot": None,
        "creative_context_snapshot": _creative_context_snapshot_view(session) if session else {},
        "artifact_context_snapshot": _artifact_context_snapshot(session) if session else {},
        "global_keys_before": None,
        "global_keys_after": None,
        "global_keys": _global_keys_snapshot(session) if session else {},
        "authoritative_field_owners": copy.deepcopy(_AUTHORITATIVE_FIELD_OWNERS),
        "envelope_field_presence": None,
        "cloud_save_requested": None,
        "cloud_save_ok": None,
        "cloud_confirmed": None,
        "payload_revision": None,
        "cloud_write_attempted": None,
        "cloud_write_succeeded": None,
        "startup_write_attempted": False,
        "violations": [],
    }


def _global_keys_snapshot(session: dict[str, Any]) -> dict[str, str]:
    return {
        "display_key": str(session.get("display_key") or "").strip(),
        "instrument": str(session.get("instrument") or "").strip(),
        "level": str(session.get("level") or "").strip(),
        "focus": str(session.get("focus") or "").strip(),
    }


def _envelope_presence_keys() -> tuple[str, ...]:
    keys: list[str] = []
    try:
        from creative_selector_hydration_trace import SELECTOR_CANONICAL_FIELDS

        keys.extend(list(SELECTOR_CANONICAL_FIELDS))
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import MISSION_CONFIG_CANONICAL_KEYS

        keys.extend(list(MISSION_CONFIG_CANONICAL_KEYS))
    except ImportError:
        pass
    try:
        from creative_mission_artifact_persistence import MISSION_ARTIFACT_CANONICAL_KEYS

        keys.extend(list(MISSION_ARTIFACT_CANONICAL_KEYS))
    except ImportError:
        pass
    keys.extend(list(CREATIVE_CONTEXT_CANONICAL_KEYS))
    return tuple(dict.fromkeys(keys))


def verify_full_creative_envelope_preserved(
    session: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    dropped: list[str] = []
    for key in _envelope_presence_keys():
        if key not in before:
            continue
        if before.get(key) is None:
            continue
        if key not in after:
            dropped.append(key)
            continue
        if after.get(key) is None and before.get(key) is not None:
            dropped.append(key)
    if dropped:
        record_context_violation(
            session,
            VIOLATION_ENVELOPE_FIELD_DROPPED,
            detail=",".join(dropped),
        )
    return dropped


def commit_context_snapshot_to_canonical(
    session: dict[str, Any],
    *,
    reason: str,
    values: dict[str, Any] | None = None,
) -> None:
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    before = copy.deepcopy(blob) if isinstance(blob, dict) else {}
    base = copy.deepcopy(before) if before else default_creative_workspace_state()
    slice_ = copy.deepcopy(values) if values is not None else _context_slice(session)
    for k, v in slice_.items():
        base[k] = copy.deepcopy(v)
    verify_full_creative_envelope_preserved(session, before, base)
    write_canonical_creative_workspace(session, base, reason=reason)


def snapshot_hydrated_context(session: dict[str, Any], *, source: str = "prepare") -> None:
    snap = {k: canonical_context_value(session, k) for k in CREATIVE_CONTEXT_CANONICAL_KEYS}
    session[CREATIVE_CONTEXT_HYDRATED_SNAPSHOT_KEY] = snap
    d = _diag(session)
    d["hydrated_context"] = copy.deepcopy(snap)
    d["hydration_source"] = source


def project_context_from_canonical(session: dict[str, Any], *, overwrite: bool = False) -> None:
    for key in CREATIVE_CONTEXT_CANONICAL_KEYS:
        if not context_configured_in_canonical(session, key):
            continue
        val = canonical_context_value(session, key)
        if val is None:
            continue
        if key == "creative_session" and isinstance(val, dict):
            val = copy.deepcopy(val)
            val.pop("instrument", None)
        if overwrite or key not in session:
            session[key] = copy.deepcopy(val)


def should_gather_context_from_session(
    session: dict[str, Any],
    key: str,
    session_val: Any,
    *,
    persist_reason: str = "autosave",
) -> bool:
    if key not in CREATIVE_CONTEXT_CANONICAL_KEYS:
        return True
    if persist_reason in CONTEXT_SNAPSHOT_SAVE_REASONS:
        return True
    if session.get(CREATIVE_CONTEXT_USER_EVENT_KEY):
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
    if context_configured_in_canonical(session, key):
        canon = canonical_context_value(session, key)
        if session_val != canon:
            return False
    if persist_reason in ("autosave", "force_autosave", "", "page_change"):
        return False
    return True


def note_passive_context_persist(session: dict[str, Any], *, reason: str) -> None:
    if reason in CONTEXT_SNAPSHOT_SAVE_REASONS:
        return
    if reason == "page_change":
        return
    snap = session.get(CREATIVE_CONTEXT_HYDRATED_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return
    if session.get(CREATIVE_CONTEXT_USER_EVENT_KEY):
        return
    for key in CREATIVE_CONTEXT_CANONICAL_KEYS:
        if key not in session:
            continue
        if session.get(key) != snap.get(key):
            record_context_violation(
                session,
                VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE,
                detail=f"key={key}|reason={reason}",
            )
            break


def _record_user_event(session: dict[str, Any], *, interaction: str, save_reason: str, fields: dict[str, Any]) -> str:
    tx_id = f"ctx-{session.get('_script_run_seq', 0)}-{uuid.uuid4().hex[:8]}"
    session[CREATIVE_CONTEXT_USER_EVENT_KEY] = {
        "transaction_id": tx_id,
        "interaction": interaction,
        "save_reason": save_reason,
        "fields": copy.deepcopy(fields),
    }
    session[CREATIVE_CONTEXT_SAVE_ACTIVE_KEY] = {
        "transaction_id": tx_id,
        "save_reason": save_reason,
        "global_keys_before": _global_keys_snapshot(session),
    }
    return tx_id


def request_context_cloud_save(session: dict[str, Any], *, save_reason: str) -> bool:
    d = _diag(session)
    d["cloud_save_requested"] = True
    d["save_reason"] = save_reason
    try:
        import streamlit as st
    except ImportError:
        return False
    try:
        from music_persistent_state import force_save_music_state

        ok = bool(force_save_music_state(st, reason=save_reason))
        d["cloud_save_ok"] = ok
        active = session.get(CREATIVE_CONTEXT_SAVE_ACTIVE_KEY)
        if isinstance(active, dict):
            active["global_keys_after"] = _global_keys_snapshot(session)
            before = active.get("global_keys_before") or {}
            after = active.get("global_keys_after") or {}
            for field in ("display_key", "instrument", "level", "focus"):
                if before.get(field) and after.get(field) and before.get(field) != after.get(field):
                    record_context_violation(
                        session,
                        VIOLATION_SNAPSHOT_MUTATED_GLOBAL_KEY,
                        detail=f"{field}:{before.get(field)}->{after.get(field)}",
                    )
        try:
            from music_workspace_cloud_save import collect_save_transaction_diagnostics

            tx = collect_save_transaction_diagnostics(session)
            d["payload_revision"] = tx.get("reserved_write_revision")
            d["cloud_write_attempted"] = tx.get("cloud_write_attempted")
            d["cloud_write_succeeded"] = tx.get("cloud_write_succeeded") or tx.get("cloud_upsert_succeeded")
            d["cloud_confirmed"] = tx.get("cloud_confirmed")
            if save_reason in CONTEXT_SNAPSHOT_SAVE_REASONS and not tx.get("cloud_confirmed"):
                if tx.get("cloud_write_attempted"):
                    record_context_violation(session, VIOLATION_CLOUD_CONFIRMATION_MISMATCH, detail=save_reason)
            global_after = _global_keys_snapshot(session)
            active = session.get(CREATIVE_CONTEXT_SAVE_ACTIVE_KEY)
            global_before = (active or {}).get("global_keys_before") if isinstance(active, dict) else None
            ue = session.get(CREATIVE_CONTEXT_USER_EVENT_KEY)
            last_interaction = d.get("last_user_interaction")
            if not last_interaction and isinstance(ue, dict):
                last_interaction = ue.get("interaction")
            _persist_item4_last_save_diag(
                session,
                {
                    "last_user_interaction": last_interaction,
                    "save_reason": save_reason,
                    "payload_revision": d.get("payload_revision"),
                    "cloud_write_attempted": d.get("cloud_write_attempted"),
                    "cloud_write_succeeded": d.get("cloud_write_succeeded"),
                    "cloud_confirmed": d.get("cloud_confirmed"),
                    "cloud_save_requested": d.get("cloud_save_requested"),
                    "cloud_save_ok": d.get("cloud_save_ok"),
                    "global_keys_before": global_before,
                    "global_keys_after": global_after,
                    "harmony_map": {
                        "section": canonical_context_value(session, "harmony_map_section"),
                        "chord": canonical_context_value(session, "harmony_map_chord"),
                    },
                    "current_section_tuple": _mission_target_tuple(session),
                },
            )
        except ImportError:
            pass
        session.pop(CREATIVE_CONTEXT_USER_EVENT_KEY, None)
        session.pop(CREATIVE_CONTEXT_SAVE_ACTIVE_KEY, None)
        return ok
    except ImportError:
        return False


def handle_user_harmony_map_context_change(
    session: dict[str, Any],
    *,
    section: str,
    chord: str,
) -> None:
    sec = str(section or "").strip()
    ch = str(chord or "").strip()
    if not sec or not ch:
        return
    fields = {"harmony_map_section": sec, "harmony_map_chord": ch}
    _record_user_event(
        session,
        interaction="harmony_map_chord_button",
        save_reason=SAVE_REASON_CONTEXT_SECTION,
        fields=fields,
    )
    session["harmony_map_section"] = sec
    session["harmony_map_chord"] = ch
    commit_context_snapshot_to_canonical(
        session,
        reason=SAVE_REASON_CONTEXT_SECTION,
        values={**_context_slice(session), **fields},
    )
    try:
        from creative_mission_config_persistence import mark_mission_workspace_dirty

        mark_mission_workspace_dirty(session)
    except ImportError:
        try:
            from creative_workspace_persistence import mark_creative_workspace_dirty

            mark_creative_workspace_dirty(session)
        except ImportError:
            pass
    request_context_cloud_save(session, save_reason=SAVE_REASON_CONTEXT_SECTION)
    d = _diag(session)
    d["last_user_interaction"] = "harmony_map_chord_button"
    d["current_section_tuple"] = _mission_target_tuple(session)
    d["harmony_map"] = {"section": sec, "chord": ch}
    _persist_item4_last_save_diag(
        session,
        {
            "last_user_interaction": "harmony_map_chord_button",
            "save_reason": SAVE_REASON_CONTEXT_SECTION,
            "harmony_map": {"section": sec, "chord": ch},
            "current_section_tuple": d["current_section_tuple"],
            "creative_context_snapshot": _creative_context_snapshot_view(session),
            "artifact_context_snapshot": _artifact_context_snapshot(session),
        },
    )


def collect_creative_context_snapshot_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    base = default_item4_dev_diag(session)
    live = copy.deepcopy(_diag(session))
    last = session.get(CREATIVE_CONTEXT_LAST_SAVE_DIAG_KEY)
    if isinstance(last, dict):
        for k, v in last.items():
            if v is not None and base.get(k) is None:
                base[k] = copy.deepcopy(v)
    for k, v in live.items():
        if v is not None:
            base[k] = copy.deepcopy(v)
    base["current_section_tuple"] = _mission_target_tuple(session)
    base["harmony_map"] = {
        "section": canonical_context_value(session, "harmony_map_section"),
        "chord": canonical_context_value(session, "harmony_map_chord"),
    }
    cs = canonical_context_value(session, "creative_session")
    if isinstance(cs, dict):
        base["creative_session_tool"] = cs.get("tool_type")
        base["creative_session_key_snapshot"] = cs.get("display_key") or cs.get("concert_key")
    base["creative_context_snapshot"] = _creative_context_snapshot_view(session)
    base["artifact_context_snapshot"] = _artifact_context_snapshot(session)
    base["global_keys"] = _global_keys_snapshot(session)
    base["authoritative_field_owners"] = copy.deepcopy(_AUTHORITATIVE_FIELD_OWNERS)
    blob = session.get(CREATIVE_WORKSPACE_STATE_KEY)
    if isinstance(blob, dict):
        base["envelope_field_presence"] = {
            k: k in blob and blob.get(k) is not None for k in _envelope_presence_keys()
        }
    try:
        from creative_mission_config_persistence import CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY

        base["startup_write_attempted"] = bool(session.get(CREATIVE_MISSION_PASSIVE_STARTUP_WRITE_REQUESTED_KEY))
    except ImportError:
        base["startup_write_attempted"] = False
    _merge_workspace_tx_into_item4_diag(session, base)
    base["violations"] = list(live.get("violations") or base.get("violations") or [])
    if isinstance(last, dict):
        for k in (
            "last_user_interaction",
            "save_reason",
            "payload_revision",
            "cloud_write_attempted",
            "cloud_write_succeeded",
            "cloud_confirmed",
            "cloud_save_requested",
            "cloud_save_ok",
            "global_keys_before",
            "global_keys_after",
        ):
            v = last.get(k)
            if v is not None:
                base[k] = copy.deepcopy(v)
    for key in ITEM4_DEV_PANEL_KEYS:
        base.setdefault(key, None if key != "violations" else [])
    return base


def render_item4_creative_context_snapshot_panel(st: Any, session: dict[str, Any]) -> None:
    """Always render Item 4 dev panel when ?dev=1 (sidebar Phase 1 expander)."""
    st.markdown(f"**{ITEM4_DEV_PANEL_HEADING}**")
    try:
        diag = collect_creative_context_snapshot_diagnostics(session)
    except Exception as exc:
        diag = default_item4_dev_diag(session)
        diag["collect_error"] = str(exc)
    for key in ITEM4_DEV_PANEL_KEYS:
        st.caption(f"`{key}`: {diag.get(key)!r}")


def audit_mission_target_tuple_complete(session: dict[str, Any], *, interaction: str = "") -> bool:
    try:
        from creative_mission_config_persistence import MISSION_TARGET_IDENTITY_KEYS

        keys = MISSION_TARGET_IDENTITY_KEYS
    except ImportError:
        keys = (
            "ii_selected_section",
            "ii_selected_chord_index",
            "ii_selected_chord",
            "ii_selected_chord_label",
        )
    present = sum(1 for k in keys if str(canonical_context_value(session, k) or session.get(k) or "").strip())
    if present > 0 and present < len(keys):
        record_context_violation(
            session,
            VIOLATION_PARTIAL_SECTION_TUPLE,
            detail=f"present={present}/{len(keys)}|interaction={interaction}",
        )
        return False
    return True


__all__ = [
    "CONTEXT_SNAPSHOT_SAVE_REASONS",
    "CREATIVE_CONTEXT_CANONICAL_KEYS",
    "SAVE_REASON_CONTEXT_SECTION",
    "SAVE_REASON_CONTEXT_SNAPSHOT",
    "VIOLATION_ARTIFACT_OVERWROTE_GLOBAL",
    "VIOLATION_CLOUD_CONFIRMATION_MISMATCH",
    "VIOLATION_ENVELOPE_FIELD_DROPPED",
    "VIOLATION_MUTATED_ARTIFACT_CONTEXT",
    "VIOLATION_PARTIAL_SECTION_TUPLE",
    "VIOLATION_PASSIVE_CONTEXT_STARTUP_WRITE",
    "VIOLATION_SNAPSHOT_MUTATED_GLOBAL_KEY",
    "audit_mission_target_tuple_complete",
    "collect_creative_context_snapshot_diagnostics",
    "commit_context_snapshot_to_canonical",
    "default_item4_dev_diag",
    "handle_user_harmony_map_context_change",
    "is_context_snapshot_save_reason",
    "note_passive_context_persist",
    "project_context_from_canonical",
    "record_context_violation",
    "render_item4_creative_context_snapshot_panel",
    "request_context_cloud_save",
    "should_gather_context_from_session",
    "snapshot_hydrated_context",
    "verify_full_creative_envelope_preserved",
]
