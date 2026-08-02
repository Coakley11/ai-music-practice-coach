"""Music workspace cloud save transaction — diagnostics, gating, readback."""

from __future__ import annotations

from typing import Any

APP_ID = "music"

MUSIC_SAVE_TX_KEY = "_music_workspace_save_transaction"

_USER_FORCE_REASONS: frozenset[str] = frozenset(
    {
        "comparison_edit",
        "trend_edit",
        "career_edit",
        "draft_edit",
        "historical_edit",
        "valuation_edit",
        "projections_edit",
        "leaderboards_edit",
        "fantasy_edit",
        "page_change",
        "insight_persist",
        "insight_hydrate",
        "applied_math_send",
        "music_coach_send",
        "team_change",
        "nba_settings_change",
        "cpl_draft_edit",
        "song_edit",
        "practice_edit",
        "backing_edit",
        "practice_tool_select",
        "practice_workspace_edit",
        "practice_key_mode_change",
        "display_key_change",
        "capo_widget",
        "multitrack_upload",
        "multitrack_layer_save",
        "force_autosave",
    }
)


def _ss(st: Any) -> dict[str, Any]:
    return st.session_state


def _cloud_enabled() -> bool:
    try:
        from suite_storage_config import cloud_storage_enabled

        return bool(cloud_storage_enabled())
    except ImportError:
        return False


def record_save_transaction(session: dict[str, Any], **fields: Any) -> None:
    tx = session.get(MUSIC_SAVE_TX_KEY)
    if not isinstance(tx, dict):
        tx = {}
    tx.update({k: v for k, v in fields.items() if v is not None})
    session[MUSIC_SAVE_TX_KEY] = tx


def collect_save_transaction_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    tx = session.get(MUSIC_SAVE_TX_KEY)
    return dict(tx) if isinstance(tx, dict) else {}


def _workspace_dirty_field_names(session: dict[str, Any]) -> list[str]:
    from suite_user_persistence import _local_dirty_key

    fields: list[str] = []
    if session.get(_local_dirty_key(APP_ID)):
        fields.append("suite_local_dirty")
    for key, label in (
        ("_active_song_local_dirty", "active_song"),
        ("_practice_local_dirty", "practice"),
        ("_studio_nav_local_dirty", "studio_nav"),
        ("_backing_local_dirty", "backing"),
        ("_mission_workspace_local_dirty", "mission"),
        ("_practice_workspace_dirty", "practice_workspace"),
    ):
        if session.get(key):
            fields.append(label)
    pending = session.get("_suite_pending_save_reason")
    if pending:
        fields.append(f"pending:{pending}")
    return fields


def music_workspace_save_allowed(session: dict[str, Any], *, reason: str) -> tuple[bool, str]:
    """Block saves that would overwrite cloud with bootstrap defaults."""
    r = str(reason or "autosave").strip() or "autosave"
    user_action = r in _USER_FORCE_REASONS
    if session.get("_music_default_song_ephemeral"):
        if not user_action and r in ("autosave", "force_autosave", ""):
            return False, "ephemeral_default_song"
        if user_action:
            try:
                from music_persistent_state import _session_has_restored_song_context

                if not _session_has_restored_song_context(session):
                    return False, "ephemeral_default_song_blocks_save"
            except ImportError:
                return False, "ephemeral_default_song_blocks_save"
    try:
        from music_workspace_hydration import can_finalize_music_restore, workspace_empty_confirmed

        finalized = can_finalize_music_restore(session) or workspace_empty_confirmed(session)
        if not finalized and not user_action and r in ("autosave", "force_autosave", ""):
            return False, "hydration_not_finalized"
    except ImportError:
        pass
    return True, ""


def force_music_workspace_save(
    st: Any,
    *,
    reason: str,
    build_state: Any,
) -> bool:
    """
    Build full stamped envelope, write disk, require cloud when enabled.

    Clears workspace dirty flags only after confirmed cloud write (+ readback when enabled).
    """
    from suite_user_persistence import (
        _applied_cloud_ts_key,
        _autosave_block_key,
        _local_dirty_key,
        _restored_fp_key,
        save_user_state,
    )

    ss = _ss(st)
    r = str(reason or "force_autosave").strip() or "force_autosave"
    dirty_fields = _workspace_dirty_field_names(ss)
    record_save_transaction(
        ss,
        force_save_requested=True,
        force_save_reason=r,
        workspace_dirty_before_save=bool(ss.get(_local_dirty_key(APP_ID))) or bool(dirty_fields),
        workspace_dirty_fields=dirty_fields or None,
    )

    allowed, block = music_workspace_save_allowed(ss, reason=r)
    record_save_transaction(ss, force_save_allowed=allowed, force_save_block_reason=block or None)
    if not allowed:
        ss["_music_force_save_ok"] = False
        ss["_music_force_save_blocked_reason"] = block
        return False

    bypass_block = r in _USER_FORCE_REASONS
    block_key = _autosave_block_key(APP_ID)
    if ss.get(block_key) and not bypass_block:
        br = str(ss.get("_suite_autosave_block_reason") or "post-restore cooldown")
        record_save_transaction(ss, force_save_allowed=False, force_save_block_reason=br)
        ss["_suite_autosave_blocked_after_restore"] = True
        return False

    if r:
        ss["_suite_pending_save_reason"] = r

    try:
        state = build_state(st)
        try:
            from workspace_revision import workspace_revision_from_blob

            rev_before = workspace_revision_from_blob(state)
        except ImportError:
            rev_before = 0
        from music_persistent_state import stamp_music_payload_for_write

        state = stamp_music_payload_for_write(
            st,
            state,
            explicit_reason=r,
            write_path="force_music_workspace_save",
        )
    except Exception as exc:
        record_save_transaction(ss, envelope_built=False, cloud_write_error=str(exc))
        ss["_music_commit_error"] = str(exc)
        return False

    record_save_transaction(ss, envelope_built=True, envelope_revision_before=rev_before)
    try:
        from workspace_revision import workspace_revision_from_blob

        rev_after_write = workspace_revision_from_blob(state)
        record_save_transaction(ss, envelope_revision_after=rev_after_write)
    except ImportError:
        rev_after_write = rev_before

    import hashlib
    import json

    blob = json.dumps(state, sort_keys=True, default=str)
    fp = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]

    saved_disk = bool(save_user_state(APP_ID, state))
    record_save_transaction(ss, disk_write_attempted=True, disk_write_succeeded=saved_disk)

    cloud_required = _cloud_enabled()
    saved_cloud = False
    cloud_error = ""
    if cloud_required:
        try:
            from music_egress_config import music_cloud_write_allowed

            if not music_cloud_write_allowed(save_reason=r, st=st):
                cloud_error = "music_egress_strict"
                record_save_transaction(ss, force_save_block_reason=cloud_error)
            else:
                from suite_cloud_state import session_page_summary
                from music_persistent_state import save_music_cloud_session

                page, summary = session_page_summary(APP_ID, state)
                record_save_transaction(ss, cloud_write_attempted=True)
                saved_cloud = bool(
                    save_music_cloud_session(
                        st,
                        state,
                        write_path="force_music_workspace_save",
                        page=page,
                        summary=summary,
                    )
                )
                if not saved_cloud:
                    cloud_error = str(ss.get("_music_last_cloud_write_error") or "cloud_write_failed")
        except Exception as exc:
            cloud_error = str(exc)
            record_save_transaction(ss, cloud_write_attempted=True, cloud_write_error=cloud_error)
    else:
        cloud_error = "cloud_storage_disabled"
        record_save_transaction(ss, cloud_write_attempted=False, force_save_block_reason=cloud_error)

    rev_after = rev_after_write
    readback_ok = False
    revision_advanced = rev_after > rev_before or (rev_before == 0 and rev_after >= 1)
    if saved_cloud:
        try:
            from workspace_revision import stamp_applied_workspace_revision

            stamp_applied_workspace_revision(ss, state)
            record_save_transaction(ss, envelope_revision_after=rev_after)
            try:
                from music_egress_config import skip_cloud_readback_after_write

                do_readback = not skip_cloud_readback_after_write(APP_ID, st=st)
            except ImportError:
                do_readback = True
            if do_readback:
                from suite_cloud_state import load_cloud_full_session

                record_save_transaction(ss, cloud_readback_attempted=True)
                readback, cloud_ts = load_cloud_full_session(APP_ID, force=True)
                readback_rev = workspace_revision_from_blob(readback if isinstance(readback, dict) else {})
                readback_fp = hashlib.sha256(
                    json.dumps(readback if isinstance(readback, dict) else {}, sort_keys=True, default=str).encode(
                        "utf-8"
                    )
                ).hexdigest()[:20]
                fp_matches = readback_fp == fp
                rev_matches = readback_rev == rev_after and rev_after > 0
                readback_ok = bool(readback) and rev_matches and revision_advanced and fp_matches
                record_save_transaction(
                    ss,
                    cloud_readback_revision=readback_rev,
                    cloud_readback_matches=readback_ok,
                    cloud_readback_fp_matches=fp_matches,
                )
                if not readback_ok:
                    cloud_error = cloud_error or "readback_not_confirmed"
                if cloud_ts:
                    ss[_applied_cloud_ts_key(APP_ID)] = cloud_ts
            else:
                readback_ok = False
                cloud_error = cloud_error or "cloud_readback_skipped"
                record_save_transaction(ss, cloud_readback_attempted=False, cloud_readback_matches=False)
        except Exception as exc:
            cloud_error = cloud_error or str(exc)
            readback_ok = False

    record_save_transaction(
        ss,
        cloud_write_succeeded=saved_cloud,
        cloud_write_error=cloud_error or None,
        cloud_readback_matches=readback_ok if saved_cloud else None,
        dirty_cleared_after_confirmed_save=False,
    )

    ss["_suite_persist_last_save_disk"] = saved_disk
    ss["_suite_persist_last_save_cloud"] = False
    ss["_suite_persist_last_save_reason"] = r
    if cloud_error and not saved_cloud:
        ss["_suite_persist_last_cloud_error"] = cloud_error

    cloud_confirmed = (
        saved_cloud
        and readback_ok
        and revision_advanced
        and (not cloud_required or readback_ok)
    )
    if cloud_required:
        if not cloud_confirmed:
            ss[_local_dirty_key(APP_ID)] = True
            ss["_music_workspace_save_pending_retry"] = True
            ss["_music_force_save_ok"] = False
            ss["_music_force_save_blocked_reason"] = cloud_error or "cloud_save_unconfirmed"
            return False
        ss["_suite_persist_last_save_cloud"] = True
        ss[f"_suite_autosave_fp::{APP_ID}"] = fp
        ss[_restored_fp_key(APP_ID)] = fp
        ss[_local_dirty_key(APP_ID)] = False
        record_save_transaction(ss, dirty_cleared_after_confirmed_save=True)
        ss.pop("_music_workspace_save_pending_retry", None)
        ss["_music_force_save_ok"] = True
        ss.pop("_music_force_save_blocked_reason", None)
        from suite_user_persistence import _utc_now_iso

        ss["_suite_persist_last_save_at"] = _utc_now_iso()
        return True

    if saved_disk or saved_cloud:
        ss[f"_suite_autosave_fp::{APP_ID}"] = fp
        ss[_restored_fp_key(APP_ID)] = fp
        ss[_local_dirty_key(APP_ID)] = False
        record_save_transaction(ss, dirty_cleared_after_confirmed_save=True)
        ss.pop("_music_workspace_save_pending_retry", None)
        ss["_music_force_save_ok"] = True
        ss.pop("_music_force_save_blocked_reason", None)
        from suite_user_persistence import _utc_now_iso

        ss["_suite_persist_last_save_at"] = _utc_now_iso()
        return True

    ss["_music_force_save_ok"] = False
    return False


def music_autosave_if_changed(st: Any, *, build_state: Any) -> dict[str, Any]:
    """Debounced autosave using the same cloud transaction as force saves."""
    import hashlib
    import json

    from suite_user_persistence import _local_dirty_key, _restored_fp_key

    result: dict[str, Any] = {
        "skipped": True,
        "disk_ok": False,
        "cloud_attempted": False,
        "cloud_ok": False,
        "cloud_error": None,
    }
    ss = _ss(st)
    allowed, block = music_workspace_save_allowed(ss, reason="autosave")
    if not allowed:
        result["skip_reason"] = block
        record_save_transaction(ss, force_save_block_reason=block)
        return result

    state = build_state(st)
    blob = json.dumps(state, sort_keys=True, default=str)
    fp = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]
    key = f"_suite_autosave_fp::{APP_ID}"
    if ss.get(key) == fp:
        return result

    result["skipped"] = False
    ok = force_music_workspace_save(st, reason="autosave", build_state=build_state)
    tx = collect_save_transaction_diagnostics(ss)
    result["disk_ok"] = bool(tx.get("disk_write_succeeded"))
    result["cloud_attempted"] = bool(tx.get("cloud_write_attempted"))
    result["cloud_ok"] = bool(tx.get("cloud_write_succeeded")) and bool(
        tx.get("dirty_cleared_after_confirmed_save")
    )
    result["cloud_error"] = tx.get("cloud_write_error") or tx.get("force_save_block_reason")
    result["last_save_source"] = "cloud" if result["cloud_ok"] else ("disk" if result["disk_ok"] else "")
    if not ok:
        result["skip_reason"] = tx.get("force_save_block_reason") or "cloud_save_unconfirmed"
    return result


__all__ = [
    "MUSIC_SAVE_TX_KEY",
    "collect_save_transaction_diagnostics",
    "force_music_workspace_save",
    "music_autosave_if_changed",
    "music_workspace_save_allowed",
    "record_save_transaction",
]
