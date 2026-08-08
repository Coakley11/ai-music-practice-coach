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
        "creative_tab_change",
        "creative_tool_change",
        "creative_mission_change",
        "creative_mission_target_change",
        "creative_mission_metrics_change",
        "creative_motif_change",
        "creative_mission_example_change",
        "creative_mission_practice_lick_change",
        "creative_context_section_change",
        "creative_context_snapshot_change",
        "practice_tool_select",
        "practice_workspace_edit",
        "practice_key_mode_change",
        "display_key_change",
        "capo_widget",
        "multitrack_upload",
        "multitrack_layer_save",
        "force_autosave",
        "startup_migration",
        "canonical_repair",
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


def _snapshot_save_transaction_debug(st: Any, ss: dict[str, Any], *, event: str = "force_music_workspace_save") -> None:
    try:
        from music_workspace_save_transaction_debug import append_workspace_save_transaction_snapshot

        append_workspace_save_transaction_snapshot(ss, st=st, event=event)
    except ImportError:
        pass


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


def _merge_cloud_save_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    diag = session.get("_suite_last_cloud_save_result")
    if isinstance(diag, dict):
        return dict(diag)
    diag2 = session.get("_music_last_cloud_save_diag")
    return dict(diag2) if isinstance(diag2, dict) else {}


def _record_force_save_early_return(
    st: Any,
    ss: dict[str, Any],
    *,
    stage: str,
    reason: str,
    save_reason: str = "",
    flushed: bool = False,
) -> None:
    try:
        from music_startup_save_suppression import (
            STARTUP_SUPPRESSION_ARMED_KEY,
            STARTUP_SUPPRESSION_RELEASED_KEY,
            collect_startup_save_suppression_diagnostics,
            queued_user_page_change_target,
        )
    except ImportError:
        STARTUP_SUPPRESSION_ARMED_KEY = "startup_suppression_armed"
        STARTUP_SUPPRESSION_RELEASED_KEY = "startup_suppression_released"

        def queued_user_page_change_target(_s: dict[str, Any]) -> str:
            return str(_s.get("_music_user_navigated_page_this_run") or "").strip()

        def collect_startup_save_suppression_diagnostics(_s: dict[str, Any]) -> dict[str, Any]:
            return {}

    queued = ""
    try:
        queued = queued_user_page_change_target(ss)
    except Exception:
        queued = str(ss.get("_music_user_navigated_page_this_run") or "").strip()

    fields: dict[str, Any] = {
        "force_save_exit_stage": stage,
        "force_save_early_return_reason": reason or None,
        "startup_suppression_armed": ss.get(STARTUP_SUPPRESSION_ARMED_KEY),
        "startup_suppression_released": ss.get(STARTUP_SUPPRESSION_RELEASED_KEY),
        "queued_page_change": queued or None,
        "queued_page_change_preserved": ss.get("queued_page_change_preserved"),
        "queued_page_change_flushed": bool(flushed or ss.get("queued_page_change_flushed")),
        "current_page_change_payload_built": bool(ss.get("_music_page_change_payload_built")),
    }
    try:
        fields["startup_suppression_diag"] = collect_startup_save_suppression_diagnostics(ss)
    except Exception:
        pass
    record_save_transaction(ss, **fields)
    try:
        from music_workspace_boundary_trace import record_save_outcome_boundary

        record_save_outcome_boundary(
            ss,
            save_reason=str(save_reason or fields.get("force_save_reason") or ""),
            ok=False,
            block_reason=str(reason or fields.get("force_save_early_return_reason") or ""),
        )
    except ImportError:
        pass
    try:
        from creative_selector_save_durability_trace import is_selector_save_reason, record_force_save_path

        sr = str(save_reason or fields.get("force_save_reason") or "")
        if is_selector_save_reason(sr):
            record_force_save_path(
                ss,
                save_reason=sr,
                force_save_entered=True,
                allowed=fields.get("force_save_allowed"),
                block_reason=str(fields.get("force_save_block_reason") or reason or ""),
                early_return_stage=stage,
                early_return_reason=str(reason or ""),
                startup_suppression_armed=fields.get("startup_suppression_armed"),
                startup_suppression_released=fields.get("startup_suppression_released"),
            )
    except ImportError:
        pass
    try:
        from music_page_save_pipeline_trace import record_pipeline_event

        record_pipeline_event(
            ss,
            function="force_music_workspace_save",
            phase="early_return",
            branch=stage,
            extra={"force_save_early_return": fields, "save_reason": save_reason},
        )
    except ImportError:
        pass
    try:
        from music_page_cloud_durability_trace import record_force_save_early_exit

        record_force_save_early_exit(
            ss,
            save_reason=str(save_reason or ""),
            exit_stage=stage,
            exit_reason=str(reason or ""),
        )
    except ImportError:
        pass
    _snapshot_save_transaction_debug(st, ss, event=f"force_save_early_return:{stage}")


def _mark_workspace_pending_cloud_retry(
    session: dict[str, Any],
    *,
    reason: str,
    fields: list[str],
    revision: int,
) -> None:
    from suite_user_persistence import _local_dirty_key

    session[_local_dirty_key(APP_ID)] = True
    session["_music_workspace_save_pending_retry"] = True
    session["_music_pending_save_revision"] = revision
    session["_music_pending_save_fields"] = fields
    session["_music_retry_required"] = True
    try:
        from active_song_state import mark_active_song_local_edit, mark_active_song_pending_sync
        from practice_state import mark_practice_local_edit, mark_practice_pending_sync
        from studio_nav_state import mark_studio_nav_local_edit

        mark_active_song_pending_sync(session)
        mark_practice_pending_sync(session)
        if reason in ("song_edit", "page_change", "practice_edit", "display_key_change"):
            mark_active_song_local_edit(session)
        if reason in ("practice_edit", "practice_tool_select", "practice_workspace_edit"):
            mark_practice_local_edit(session)
        if reason == "page_change":
            mark_studio_nav_local_edit(session)
    except ImportError:
        pass


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
    bypass_strict_defer: bool = False,
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
    try:
        from music_workspace_boundary_trace import record_live_boundary

        record_live_boundary(ss, "force_save_entry", save_reason=r)
    except ImportError:
        pass
    try:
        from display_key_sidebar_persistence_trace import active_sidebar_display_key_transaction_id

        sid = active_sidebar_display_key_transaction_id(ss)
        if sid:
            record_save_transaction(ss, transaction_id=sid)
    except ImportError:
        pass
    try:
        from creative_selector_save_durability_trace import is_selector_save_reason, record_force_save_path

        if is_selector_save_reason(r):
            record_force_save_path(ss, save_reason=r, force_save_entered=True)
    except ImportError:
        pass
    try:
        from music_page_cloud_durability_trace import record_force_save_durability_entry

        record_force_save_durability_entry(ss, reason=r, stage="entry")
    except ImportError:
        pass
    try:
        from music_page_save_pipeline_trace import force_save_impl_marker, record_pipeline_event

        record_pipeline_event(
            ss,
            function="force_music_workspace_save",
            phase="entry",
            extra={"force_save_impl_marker": force_save_impl_marker, "reason": r},
        )
    except ImportError:
        pass
    try:
        from music_startup_save_suppression import (
            attempt_release_startup_for_queued_page_change,
            gate_music_workspace_save_at_startup,
        )

        skip_save, _suppress_reason = gate_music_workspace_save_at_startup(ss, r)
        if r == "page_change":
            try:
                from music_queued_page_startup_release_trace import record_force_save_page_change_entry

                record_force_save_page_change_entry(ss)
            except ImportError:
                pass
        if skip_save:
            flushed = False
            if r == "page_change":
                flushed = attempt_release_startup_for_queued_page_change(
                    st,
                    suppress_reason=str(_suppress_reason or ""),
                )
            elif r == "display_key_change":
                try:
                    from display_key_startup_save_queue import (
                        attempt_release_startup_for_queued_display_key_change,
                        attempt_release_stale_startup_suppression_for_display_key,
                        maybe_queue_display_key_save_blocked_by_startup,
                    )
                    from display_key_sidebar_persistence_trace import (
                        active_sidebar_display_key_transaction_id,
                    )

                    flushed = attempt_release_stale_startup_suppression_for_display_key(st)
                    if not flushed:
                        flushed = attempt_release_startup_for_queued_display_key_change(
                            st,
                            suppress_reason=str(_suppress_reason or ""),
                        )
                    if not flushed:
                        maybe_queue_display_key_save_blocked_by_startup(
                            ss,
                            block_reason=str(_suppress_reason or ""),
                            transaction_id=active_sidebar_display_key_transaction_id(ss),
                        )
                    skip_save, _suppress_reason = gate_music_workspace_save_at_startup(ss, r)
                    flushed = not skip_save
                except ImportError:
                    pass
            if not flushed:
                _record_force_save_early_return(
                    st,
                    ss,
                    stage="before_payload_build",
                    reason=str(_suppress_reason or "startup_suppressed"),
                    save_reason=r,
                )
                ss["_music_force_save_ok"] = False
                ss["_music_force_save_blocked_reason"] = str(_suppress_reason or "startup_suppressed")
                return False
            skip_save, _suppress_reason = gate_music_workspace_save_at_startup(ss, r)
            if skip_save:
                _record_force_save_early_return(
                    st,
                    ss,
                    stage="before_payload_build",
                    reason=str(_suppress_reason or "startup_suppressed_after_release"),
                    save_reason=r,
                    flushed=True,
                )
                ss["_music_force_save_ok"] = False
                ss["_music_force_save_blocked_reason"] = str(_suppress_reason or "startup_suppressed")
                return False
    except ImportError:
        pass
    dirty_fields = _workspace_dirty_field_names(ss)
    dirty_before = bool(ss.get(_local_dirty_key(APP_ID))) or bool(dirty_fields)
    try:
        from music_egress_strict_save import reset_transaction_egress_counters

        reset_transaction_egress_counters(ss)
    except ImportError:
        pass
    record_save_transaction(
        ss,
        force_save_requested=True,
        force_save_reason=r,
        workspace_dirty_before_save=dirty_before,
        workspace_dirty_fields=dirty_fields or None,
        dirty_before_transaction=dirty_before,
    )

    allowed, block = music_workspace_save_allowed(ss, reason=r)
    record_save_transaction(ss, force_save_allowed=allowed, force_save_block_reason=block or None)
    try:
        from creative_selector_save_durability_trace import is_selector_save_reason, record_force_save_path

        if is_selector_save_reason(r):
            record_force_save_path(
                ss,
                save_reason=r,
                force_save_entered=True,
                allowed=allowed,
                block_reason=str(block or ""),
                transaction_sequence=ss.get("_music_page_change_transaction_seq"),
            )
    except ImportError:
        pass
    try:
        from music_page_cloud_durability_trace import (
            authoritative_page_change_cloud_confirmed,
            record_subsequent_save_attempt,
        )

        if authoritative_page_change_cloud_confirmed(ss):
            record_subsequent_save_attempt(
                ss,
                reason=r,
                allowed=allowed,
                blocked_reason=str(block or ""),
                state=None,
                transaction_sequence=ss.get("_music_page_change_transaction_seq"),
            )
    except ImportError:
        pass
    if not allowed:
        ss["_music_force_save_ok"] = False
        ss["_music_force_save_blocked_reason"] = block
        _record_force_save_early_return(
            st,
            ss,
            stage="before_payload_build",
            reason=str(block or "force_save_not_allowed"),
            save_reason=r,
        )
        _snapshot_save_transaction_debug(st, ss, event="force_save_blocked")
        return False

    bypass_block = r in _USER_FORCE_REASONS
    block_key = _autosave_block_key(APP_ID)
    if ss.get(block_key) and not bypass_block:
        br = str(ss.get("_suite_autosave_block_reason") or "post-restore cooldown")
        record_save_transaction(ss, force_save_allowed=False, force_save_block_reason=br)
        ss["_suite_autosave_blocked_after_restore"] = True
        _record_force_save_early_return(
            st,
            ss,
            stage="before_payload_build",
            reason=str(br or "autosave_cooldown"),
            save_reason=r,
        )
        _snapshot_save_transaction_debug(st, ss, event="autosave_cooldown_blocked")
        return False

    if r:
        ss["_suite_pending_save_reason"] = r

    try:
        from creative_artifact_global_key_guard import freeze_global_keys_for_creative_artifact_save

        freeze_global_keys_for_creative_artifact_save(
            ss,
            save_reason=r,
            caller="force_music_workspace_save",
        )
    except ImportError:
        pass

    try:
        from music_page_cloud_durability_trace import begin_page_change_cloud_transaction

        begin_page_change_cloud_transaction(ss, save_reason=r)
    except ImportError:
        pass

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
        try:
            from display_key_sidebar_cloud_confirmation import record_display_key_payload_before_upsert

            record_display_key_payload_before_upsert(ss, state)
        except ImportError:
            pass
        try:
            core = state.get("core") if isinstance(state.get("core"), dict) else {}
            ass = state.get("active_song_state") if isinstance(state.get("active_song_state"), dict) else {}
            payload_dk = str((ass or {}).get("display_key") or (core or {}).get("display_key") or "").strip()
            if payload_dk:
                record_save_transaction(ss, payload_core_display_key=payload_dk)
        except Exception:
            pass
        try:
            from creative_selector_save_durability_trace import ensure_selector_field_in_upsert_payload

            ensure_selector_field_in_upsert_payload(ss, state)
        except ImportError:
            pass
        try:
            from music_page_save_pipeline_trace import (
                force_save_impl_marker,
                payload_pages_from_state,
                record_pipeline_event,
            )

            record_pipeline_event(
                ss,
                function="force_music_workspace_save",
                phase="post_stamp",
                extra={
                    "force_save_impl_marker": force_save_impl_marker,
                    "reason": r,
                    "payload_pages": payload_pages_from_state(state),
                },
                payload=state,
            )
        except ImportError:
            pass
        try:
            from mission_backing_handoff_persistence import (
                VIOLATION_POST_CONFIRM_OVERWRITE,
                guard_mission_backing_handoff_post_confirm_overwrite,
                record_handoff_final_upsert_if_active,
            )

            blocked, _detail = guard_mission_backing_handoff_post_confirm_overwrite(
                ss, save_reason=r, state=state
            )
            if blocked:
                ss["_music_force_save_ok"] = False
                ss["_music_force_save_blocked_reason"] = VIOLATION_POST_CONFIRM_OVERWRITE
                record_save_transaction(
                    ss,
                    force_save_allowed=False,
                    force_save_block_reason=VIOLATION_POST_CONFIRM_OVERWRITE,
                )
                _snapshot_save_transaction_debug(st, ss, event="handoff_post_confirm_overwrite_blocked")
                return False
            record_handoff_final_upsert_if_active(ss, state=state, save_reason=r)
        except ImportError:
            pass
    except Exception as exc:
        record_save_transaction(ss, envelope_built=False, cloud_write_error=str(exc))
        ss["_music_commit_error"] = str(exc)
        _snapshot_save_transaction_debug(st, ss, event="envelope_build_failed")
        return False

    record_save_transaction(ss, envelope_built=True, envelope_revision_before=rev_before)
    try:
        from music_workspace_boundary_trace import record_serialize_boundary

        record_serialize_boundary(ss, state, save_reason=r)
    except ImportError:
        pass

    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    canonical_fp = workspace_canonical_content_fingerprint(state)

    import hashlib
    import json

    egress_plan = None
    egress_tx = None
    try:
        from music_strict_egress_transaction import evaluate_strict_egress_transaction

        egress_tx = evaluate_strict_egress_transaction(
            ss,
            raw_save_reason=r,
            payload_fp=canonical_fp,
            bypass_defer=bypass_strict_defer,
            st=st,
        )
        record_save_transaction(ss, **egress_tx.diag())
        try:
            from music_egress_strict_save import collect_strict_pending_diagnostics

            record_save_transaction(ss, **collect_strict_pending_diagnostics(ss))
        except ImportError:
            pass
    except ImportError:
        try:
            from music_egress_strict_save import plan_strict_egress_cloud_write

            egress_plan = plan_strict_egress_cloud_write(
                ss,
                save_reason=r,
                payload_fp=canonical_fp,
                bypass_defer=bypass_strict_defer,
            )
            record_save_transaction(ss, **egress_plan.diag())
        except ImportError:
            pass

    payload_changed = False
    if egress_tx is not None:
        payload_changed = bool(egress_tx.extra.get("payload_changed_since_last_confirmed_save"))
    elif egress_plan is not None:
        payload_changed = bool(egress_plan.payload_changed_since_last_confirmed_save)

    plan_action = ""
    if egress_tx is not None:
        plan_action = str(egress_tx.strict_egress_plan_action or "")
    elif egress_plan is not None:
        plan_action = "duplicate_skip" if egress_plan.duplicate_write_skipped else (
            "defer" if egress_plan.defer_cloud_write else (
                "immediate" if egress_plan.allow_cloud_write else "deny"
            )
        )

    duplicate_skipped = plan_action == "duplicate_skip" or bool(
        egress_plan is not None and getattr(egress_plan, "duplicate_write_skipped", False)
    )
    deferred_cloud = plan_action == "defer" or bool(
        egress_plan is not None and getattr(egress_plan, "defer_cloud_write", False)
    )
    strict_approved = bool(egress_tx is not None and egress_tx.strict_egress_approved) or bool(
        egress_plan is not None and egress_plan.allow_cloud_write and not egress_plan.defer_cloud_write
    )
    try:
        from creative_selector_save_durability_trace import (
            CREATIVE_SELECTOR_SAVE_ACTIVE_KEY,
            is_selector_save_reason,
        )

        if is_selector_save_reason(r) and ss.get(CREATIVE_SELECTOR_SAVE_ACTIVE_KEY):
            duplicate_skipped = False
            deferred_cloud = False
            payload_changed = True
            strict_approved = True
    except ImportError:
        pass
    try:
        from creative_mission_config_persistence import (
            CREATIVE_MISSION_SAVE_ACTIVE_KEY,
            is_mission_config_save_reason,
        )

        if is_mission_config_save_reason(r) and ss.get(CREATIVE_MISSION_SAVE_ACTIVE_KEY):
            duplicate_skipped = False
            deferred_cloud = False
            payload_changed = True
            strict_approved = True
    except ImportError:
        pass
    try:
        from creative_mission_artifact_persistence import (
            CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY,
            is_mission_artifact_save_reason,
        )

        if is_mission_artifact_save_reason(r) and ss.get(CREATIVE_MISSION_ARTIFACT_SAVE_ACTIVE_KEY):
            duplicate_skipped = False
            deferred_cloud = False
            payload_changed = True
            strict_approved = True
    except ImportError:
        pass

    try:
        from creative_context_snapshot_persistence import (
            CREATIVE_CONTEXT_SAVE_ACTIVE_KEY,
            is_context_snapshot_save_reason,
        )

        if is_context_snapshot_save_reason(r) and ss.get(CREATIVE_CONTEXT_SAVE_ACTIVE_KEY):
            duplicate_skipped = False
            deferred_cloud = False
            payload_changed = True
            strict_approved = True
    except ImportError:
        pass

    try:
        from display_key_sidebar_persistence_trace import (
            active_sidebar_display_key_transaction_id,
            is_explicit_sidebar_display_key_save,
            should_force_display_key_cloud_write,
        )

        if is_explicit_sidebar_display_key_save(r, ss) and should_force_display_key_cloud_write(
            ss, save_reason=r, payload_fp=canonical_fp
        ):
            duplicate_skipped = False
            deferred_cloud = False
            payload_changed = True
            strict_approved = True
            sid = active_sidebar_display_key_transaction_id(ss)
            record_save_transaction(
                ss,
                transaction_id=sid or None,
                explicit_sidebar_display_key_save=True,
                payload_changed_since_last_confirmed_save=True,
                duplicate_write_skipped=False,
            )
    except ImportError:
        pass

    if duplicate_skipped:
        from music_egress_strict_save import last_confirmed_cloud_fingerprint

        if last_confirmed_cloud_fingerprint(ss) == canonical_fp and ss.get("_suite_persist_last_save_cloud"):
            saved_disk = bool(save_user_state(APP_ID, state))
            record_save_transaction(
                ss,
                disk_write_attempted=True,
                disk_write_succeeded=saved_disk,
                cloud_write_attempted=False,
                cloud_write_succeeded=True,
                cloud_readback_matches=True,
                cloud_confirmed=True,
                revision_advanced=True,
                duplicate_write_skipped=True,
                canonical_content_fingerprint=canonical_fp,
                suite_persist_last_save_cloud=True,
                dirty_cleared_after_confirmed_save=True,
            )
            ss["_music_force_save_ok"] = True
            ss.pop("_music_force_save_blocked_reason", None)
            _snapshot_save_transaction_debug(st, ss, event="duplicate_skip_preserve_confirmed")
            return True

    if payload_changed and strict_approved and not duplicate_skipped and not deferred_cloud:
        from workspace_revision import (
            reserve_workspace_revision_for_canonical_fp,
            stamp_workspace_revision_into_state,
        )

        next_rev = reserve_workspace_revision_for_canonical_fp(ss, state, canonical_fp)
        state = stamp_workspace_revision_into_state(state, next_rev)
        record_save_transaction(
            ss,
            envelope_revision_after=next_rev,
            canonical_content_fingerprint=canonical_fp,
            reserved_write_revision=next_rev,
        )
        try:
            from creative_selector_save_durability_trace import is_selector_save_reason, record_force_save_path

            if is_selector_save_reason(r):
                record_force_save_path(
                    ss,
                    save_reason=r,
                    force_save_entered=True,
                    transaction_sequence=ss.get("_music_page_change_transaction_seq"),
                    canonical_revision_before=int(rev_before) if rev_before is not None else None,
                    reserved_revision=int(next_rev),
                )
        except ImportError:
            pass
        try:
            from music_page_cloud_durability_trace import record_revision_stages

            record_revision_stages(
                ss,
                canonical_revision_before=int(rev_before) if rev_before is not None else None,
                reserved_revision=int(next_rev),
                revision_in_upsert_payload=None,
            )
        except ImportError:
            pass

    try:
        from workspace_revision import workspace_revision_from_blob

        rev_after_write = workspace_revision_from_blob(state)
        record_save_transaction(ss, envelope_revision_after=rev_after_write)
        try:
            from music_page_cloud_durability_trace import record_revision_stages

            tx_rev = ss.get("_music_workspace_save_transaction") or {}
            record_revision_stages(
                ss,
                canonical_revision_before=int(rev_before) if rev_before is not None else None,
                reserved_revision=tx_rev.get("reserved_write_revision"),
                revision_in_upsert_payload=int(rev_after_write) if rev_after_write is not None else None,
            )
        except ImportError:
            pass
    except ImportError:
        rev_after_write = rev_before

    blob = json.dumps(state, sort_keys=True, default=str)
    fp = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]

    saved_disk = bool(save_user_state(APP_ID, state))
    record_save_transaction(ss, disk_write_attempted=True, disk_write_succeeded=saved_disk)

    cloud_required = _cloud_enabled()
    saved_cloud = False
    cloud_error = ""
    cloud_write_count = 0
    cloud_read_count = 0
    if cloud_required:
        try:
            if duplicate_skipped:
                cloud_error = ""
                record_save_transaction(ss, cloud_write_attempted=False, force_save_block_reason=None)
            elif deferred_cloud:
                ss[_local_dirty_key(APP_ID)] = True
                record_save_transaction(
                    ss,
                    cloud_write_attempted=False,
                    force_save_block_reason="strict_save_deferred",
                )
            elif egress_tx is not None and egress_tx.strict_egress_approved:
                from suite_cloud_state import session_page_summary
                from music_persistent_state import save_music_cloud_session

                page, summary = session_page_summary(APP_ID, state)
                record_save_transaction(ss, cloud_write_attempted=True)
                approval = egress_tx.approval_dict()
                ss.pop("_suite_autosave_cloud_blocked_reason", None)
                saved_cloud = bool(
                    save_music_cloud_session(
                        st,
                        state,
                        write_path="force_music_workspace_save",
                        page=page,
                        summary=summary,
                        strict_egress_approval=approval,
                    )
                )
                record_save_transaction(
                    ss,
                    save_music_cloud_session_return_value=saved_cloud,
                    save_music_cloud_session_return_type=type(saved_cloud).__name__,
                    cloud_upsert_succeeded=saved_cloud if saved_cloud else None,
                )
                if saved_cloud:
                    cloud_error = ""
                    try:
                        from music_egress_strict_save import bump_cloud_write_count

                        cloud_write_count = bump_cloud_write_count(ss)
                    except ImportError:
                        cloud_write_count = 1
                if not saved_cloud:
                    cloud_error = str(ss.get("_music_last_cloud_write_error") or "cloud_write_failed")
                record_save_transaction(ss, **_merge_cloud_save_diagnostics(ss))
            elif egress_plan is not None and egress_plan.allow_cloud_write and not egress_plan.defer_cloud_write:
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
                record_save_transaction(
                    ss,
                    save_music_cloud_session_return_value=saved_cloud,
                    save_music_cloud_session_return_type=type(saved_cloud).__name__,
                    cloud_upsert_succeeded=saved_cloud if saved_cloud else None,
                )
                if saved_cloud:
                    cloud_error = ""
                    try:
                        from music_egress_strict_save import bump_cloud_write_count

                        cloud_write_count = bump_cloud_write_count(ss)
                    except ImportError:
                        cloud_write_count = 1
                if not saved_cloud:
                    cloud_error = str(ss.get("_music_last_cloud_write_error") or "cloud_write_failed")
                record_save_transaction(ss, **_merge_cloud_save_diagnostics(ss))
            else:
                block = "music_egress_strict"
                if egress_tx is not None and egress_tx.final_cloud_write_block_reason:
                    block = egress_tx.final_cloud_write_block_reason
                cloud_error = block
                record_save_transaction(
                    ss,
                    force_save_block_reason=cloud_error,
                    strict_egress_denied_by_function=getattr(egress_tx, "strict_egress_denied_by_function", None),
                    strict_egress_denied_by_file_line=getattr(egress_tx, "strict_egress_denied_by_file_line", None),
                    final_cloud_write_block_reason=cloud_error,
                )
        except Exception as exc:
            cloud_error = str(exc)
            record_save_transaction(ss, cloud_write_attempted=True, cloud_write_error=cloud_error)
    else:
        cloud_error = "cloud_storage_disabled"
        record_save_transaction(ss, cloud_write_attempted=False, force_save_block_reason=cloud_error)

    rev_after = rev_after_write
    readback_ok = False
    authoritative_upsert = False
    try:
        from workspace_revision import LAST_CONFIRMED_REVISION_KEY

        last_confirmed_rev = int(ss.get(LAST_CONFIRMED_REVISION_KEY) or 0)
    except (TypeError, ValueError):
        last_confirmed_rev = 0
    revision_advanced = (
        rev_after > rev_before
        or (rev_before == 0 and rev_after >= 1)
        or (payload_changed and rev_after > last_confirmed_rev)
    )
    if duplicate_skipped:
        from music_egress_strict_save import last_confirmed_cloud_fingerprint

        if last_confirmed_cloud_fingerprint(ss) == canonical_fp:
            revision_advanced = True

    if duplicate_skipped and saved_disk:
        readback_ok = True
        authoritative_upsert = True

    if saved_cloud:
        try:
            from workspace_revision import stamp_applied_workspace_revision

            stamp_applied_workspace_revision(ss, state)
            record_save_transaction(ss, envelope_revision_after=rev_after)
            cloud_diag = _merge_cloud_save_diagnostics(ss)
            upsert_ok = bool(cloud_diag.get("cloud_upsert_succeeded"))
            try:
                from music_egress_config import skip_cloud_readback_after_write
                from music_egress_strict_save import (
                    allow_single_strict_confirmation_read,
                    bump_cloud_read_count,
                    strict_post_save_confirmation_uses_authoritative_upsert,
                )

                skip_routine_readback = skip_cloud_readback_after_write(APP_ID, st=st)
                use_authoritative = strict_post_save_confirmation_uses_authoritative_upsert(save_reason=r)
            except ImportError:
                skip_routine_readback = False
                use_authoritative = False
                allow_single_strict_confirmation_read = lambda _s: True  # type: ignore[assignment,misc]
                bump_cloud_read_count = lambda _s: 1  # type: ignore[assignment,misc]

            if use_authoritative and upsert_ok:
                cloud_diag = _merge_cloud_save_diagnostics(ss)
                try:
                    written_rev = int(cloud_diag.get("cloud_payload_revision") or rev_after)
                except (TypeError, ValueError):
                    written_rev = rev_after
                readback_ok = revision_advanced and written_rev == rev_after and bool(state)
                authoritative_upsert = True
                record_save_transaction(
                    ss,
                    cloud_readback_attempted=False,
                    cloud_readback_matches=readback_ok,
                    cloud_readback_authoritative=True,
                )
            elif not skip_routine_readback:
                from suite_cloud_state import load_cloud_full_session

                record_save_transaction(ss, cloud_readback_attempted=True)
                readback, cloud_ts = load_cloud_full_session(APP_ID, force=True)
                cloud_read_count = bump_cloud_read_count(ss)
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
            elif allow_single_strict_confirmation_read(ss):
                from suite_cloud_state import load_cloud_full_session

                record_save_transaction(ss, cloud_readback_attempted=True)
                readback, cloud_ts = load_cloud_full_session(APP_ID, force=True)
                cloud_read_count = bump_cloud_read_count(ss)
                readback_rev = workspace_revision_from_blob(readback if isinstance(readback, dict) else {})
                readback_fp = hashlib.sha256(
                    json.dumps(readback if isinstance(readback, dict) else {}, sort_keys=True, default=str).encode(
                        "utf-8"
                    )
                ).hexdigest()[:20]
                fp_matches = readback_fp == fp
                rev_matches = readback_rev == rev_after and rev_after > 0
                readback_ok = bool(readback) and rev_matches and revision_advanced and fp_matches
                authoritative_upsert = readback_ok
                record_save_transaction(
                    ss,
                    cloud_readback_revision=readback_rev,
                    cloud_readback_matches=readback_ok,
                    cloud_readback_fp_matches=fp_matches,
                    cloud_readback_authoritative=readback_ok,
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

    if str(r) == "page_change":
        try:
            from music_page_cloud_durability_trace import finalize_page_change_cloud_durability_trace

            finalize_page_change_cloud_durability_trace(ss, save_reason=r)
        except ImportError:
            pass

    record_save_transaction(
        ss,
        cloud_write_succeeded=saved_cloud or duplicate_skipped,
        cloud_write_error=cloud_error or None,
        cloud_readback_matches=readback_ok if (saved_cloud or duplicate_skipped) else None,
        cloud_readback_authoritative=authoritative_upsert or None,
        dirty_cleared_after_confirmed_save=False,
        cloud_write_count_for_transaction=int(ss.get("_music_strict_tx_cloud_write_count") or cloud_write_count),
        cloud_read_count_for_transaction=int(ss.get("_music_strict_tx_cloud_read_count") or cloud_read_count),
    )

    prior_save_cloud = bool(ss.get("_suite_persist_last_save_cloud"))
    ss["_suite_persist_last_save_disk"] = saved_disk
    ss["_suite_persist_last_save_reason"] = r
    if cloud_error and not saved_cloud:
        ss["_suite_persist_last_cloud_error"] = cloud_error

    cloud_confirmed = (
        (saved_cloud or duplicate_skipped)
        and readback_ok
        and revision_advanced
        and (not cloud_required or readback_ok or duplicate_skipped)
    )
    if str(r) == "page_change":
        try:
            from mission_backing_handoff_persistence import on_page_change_cloud_save_finished

            on_page_change_cloud_save_finished(
                ss,
                state=state,
                save_reason=r,
                cloud_confirmed=bool(cloud_confirmed),
            )
        except ImportError:
            pass
    record_save_transaction(
        ss,
        cloud_confirmed=cloud_confirmed,
        revision_advanced=revision_advanced,
        suite_persist_last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")),
    )
    if deferred_cloud:
        ss[_local_dirty_key(APP_ID)] = True
        ss["_music_force_save_ok"] = False
        ss["_music_force_save_blocked_reason"] = "strict_save_deferred"
        record_save_transaction(
            ss,
            dirty_after_failed_cloud_save=False,
            retry_required=False,
            dirty_cleared_after_confirmed_save=False,
        )
        record_save_transaction(ss, suite_persist_last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")))
        _snapshot_save_transaction_debug(st, ss, event="strict_save_deferred")
        return False

    if cloud_required:
        if not cloud_confirmed:
            try:
                from display_key_sidebar_cloud_confirmation import (
                    attempt_explicit_display_key_authoritative_confirmation,
                )
                from display_key_sidebar_persistence_trace import is_explicit_sidebar_display_key_save

                if is_explicit_sidebar_display_key_save(r, ss):
                    ok_auth, _forensic = attempt_explicit_display_key_authoritative_confirmation(
                        ss,
                        st=st,
                        save_reason=r,
                        expected_display_key=str(ss.get("display_key") or ""),
                        payload_state=state if isinstance(state, dict) else None,
                    )
                    if ok_auth:
                        cloud_confirmed = True
                        readback_ok = True
                        saved_cloud = True
                        ss["_suite_persist_last_save_cloud"] = True
                        ss["_music_force_save_ok"] = True
                        ss.pop("_music_force_save_blocked_reason", None)
                        ss.pop("_music_last_cloud_write_error", None)
                        ss[f"_suite_autosave_fp::{APP_ID}"] = fp
                        ss[_restored_fp_key(APP_ID)] = fp
                        try:
                            from music_egress_strict_save import note_confirmed_cloud_fingerprint

                            note_confirmed_cloud_fingerprint(ss, canonical_fp)
                        except ImportError:
                            pass
                        try:
                            from workspace_revision import note_confirmed_workspace_revision

                            note_confirmed_workspace_revision(ss, state)
                        except ImportError:
                            pass
                        ss[_local_dirty_key(APP_ID)] = False
                        record_save_transaction(
                            ss,
                            cloud_confirmed=True,
                            cloud_readback_matches=True,
                            cloud_readback_authoritative=True,
                            dirty_cleared_after_confirmed_save=True,
                            suite_persist_last_save_cloud=True,
                        )
                        ss.pop("_music_workspace_save_pending_retry", None)
                        from suite_user_persistence import _utc_now_iso, clear_workspace_autosave_block

                        clear_workspace_autosave_block(st, APP_ID)
                        ss["_suite_persist_last_save_at"] = _utc_now_iso()
                        _snapshot_save_transaction_debug(st, ss, event="display_key_authoritative_confirmed")
                        return True
            except ImportError:
                pass
            if duplicate_skipped and prior_save_cloud:
                from music_egress_strict_save import last_confirmed_cloud_fingerprint

                if last_confirmed_cloud_fingerprint(ss) == canonical_fp:
                    ss["_suite_persist_last_save_cloud"] = True
                    ss["_music_force_save_ok"] = True
                    ss.pop("_music_force_save_blocked_reason", None)
                    record_save_transaction(
                        ss,
                        cloud_confirmed=True,
                        suite_persist_last_save_cloud=True,
                        dirty_cleared_after_confirmed_save=True,
                        retry_required=False,
                    )
                    _snapshot_save_transaction_debug(st, ss, event="duplicate_skip_preserve_confirmed")
                    return True
            ss["_suite_persist_last_save_cloud"] = False
            ss[_local_dirty_key(APP_ID)] = True
            ss["_music_workspace_save_pending_retry"] = True
            ss["_music_force_save_ok"] = False
            ss["_music_force_save_blocked_reason"] = cloud_error or "cloud_save_unconfirmed"
            if ss.get("_music_stale_write_blocked") or ss.get("stale_write_blocked"):
                try:
                    from music_workspace_conditional_cloud_write import STALE_WRITE_USER_MESSAGE

                    ss["_music_force_save_blocked_reason"] = "stale_revision_conflict"
                    record_save_transaction(
                        ss,
                        stale_write_blocked=True,
                        conflict_detected=True,
                        cloud_write_succeeded=False,
                        cloud_confirmed=False,
                        dirty_cleared_after_confirmed_save=False,
                        revision_reserved=False,
                    )
                    try:
                        st.warning(STALE_WRITE_USER_MESSAGE)
                    except Exception:
                        pass
                except ImportError:
                    pass
            _mark_workspace_pending_cloud_retry(
                ss,
                reason=r,
                fields=dirty_fields or _workspace_dirty_field_names(ss),
                revision=int(rev_after_write or 0),
            )
            record_save_transaction(
                ss,
                dirty_after_failed_cloud_save=True,
                retry_required=True,
                pending_save_revision=rev_after_write,
                pending_save_fields=dirty_fields or None,
                dirty_cleared_after_confirmed_save=False,
            )
            record_save_transaction(ss, **_merge_cloud_save_diagnostics(ss))
            record_save_transaction(ss, suite_persist_last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")))
            _snapshot_save_transaction_debug(st, ss, event="cloud_save_unconfirmed")
            return False
        ss["_suite_persist_last_save_cloud"] = True
        ss.pop("_suite_autosave_cloud_blocked_reason", None)
        ss.pop("_music_passive_autosave_cloud_skip_reason", None)
        ss[f"_suite_autosave_fp::{APP_ID}"] = fp
        ss[_restored_fp_key(APP_ID)] = fp
        try:
            from music_egress_strict_save import note_confirmed_cloud_fingerprint

            note_confirmed_cloud_fingerprint(ss, canonical_fp)
        except ImportError:
            pass
        try:
            from workspace_revision import note_confirmed_workspace_revision

            note_confirmed_workspace_revision(ss, state)
        except ImportError:
            pass
        ss[_local_dirty_key(APP_ID)] = False
        record_save_transaction(ss, dirty_cleared_after_confirmed_save=True)
        ss.pop("_music_workspace_save_pending_retry", None)
        ss["_music_force_save_ok"] = True
        ss.pop("_music_force_save_blocked_reason", None)
        from suite_user_persistence import _utc_now_iso, clear_workspace_autosave_block

        ss.pop("_suite_workspace_sync_skipped_no_apply", None)
        ss.pop("_suite_autosave_block_reason", None)
        clear_workspace_autosave_block(st, APP_ID)
        ss["_suite_persist_last_save_at"] = _utc_now_iso()
        try:
            from music_egress_strict_save import clear_strict_pending_save

            clear_strict_pending_save(ss, flush_result="confirmed_inline")
        except ImportError:
            pass
        record_save_transaction(ss, suite_persist_last_save_cloud=True, cloud_confirmed=True)
        _snapshot_save_transaction_debug(st, ss, event="cloud_confirmed")
        try:
            from music_workspace_boundary_trace import record_save_outcome_boundary

            record_save_outcome_boundary(ss, save_reason=r, ok=True, cloud_ok=True)
        except ImportError:
            pass
        return True

    if saved_disk or saved_cloud:
        ss[f"_suite_autosave_fp::{APP_ID}"] = fp
        ss[_restored_fp_key(APP_ID)] = fp
        ss[_local_dirty_key(APP_ID)] = False
        record_save_transaction(ss, dirty_cleared_after_confirmed_save=True)
        ss.pop("_music_workspace_save_pending_retry", None)
        ss["_music_force_save_ok"] = True
        ss.pop("_music_force_save_blocked_reason", None)
        from suite_user_persistence import _utc_now_iso, clear_workspace_autosave_block

        ss.pop("_suite_autosave_block_reason", None)
        clear_workspace_autosave_block(st, APP_ID)
        ss["_suite_persist_last_save_at"] = _utc_now_iso()
        record_save_transaction(ss, suite_persist_last_save_cloud=bool(ss.get("_suite_persist_last_save_cloud")))
        _snapshot_save_transaction_debug(st, ss, event="disk_or_cloud_ok_no_strict")
        try:
            from music_workspace_boundary_trace import record_save_outcome_boundary

            record_save_outcome_boundary(
                ss,
                save_reason=r,
                ok=True,
                cloud_ok=bool(ss.get("_suite_persist_last_save_cloud")),
            )
        except ImportError:
            pass
        return True

    ss["_music_force_save_ok"] = False
    _snapshot_save_transaction_debug(st, ss, event="save_failed")
    try:
        from music_workspace_boundary_trace import record_save_outcome_boundary

        record_save_outcome_boundary(
            ss,
            save_reason=r,
            ok=False,
            block_reason=str(ss.get("_music_force_save_blocked_reason") or "save_failed"),
            cloud_ok=bool(ss.get("_suite_persist_last_save_cloud")),
        )
    except ImportError:
        pass
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

    try:
        from music_egress_config import music_cloud_write_allowed, music_egress_strict_enabled
        from music_strict_egress_transaction import note_passive_autosave_cloud_skip

        if music_egress_strict_enabled() and not music_cloud_write_allowed(save_reason="autosave", st=st):
            result["skip_reason"] = "music_egress_strict"
            note_passive_autosave_cloud_skip(ss, reason="music_egress_strict")
            return result
    except ImportError:
        pass

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
