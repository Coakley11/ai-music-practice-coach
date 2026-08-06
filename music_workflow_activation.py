"""Production workflow activation — sole authority for active musical workflow (Commit 2)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from music_workflow_compatibility import (
    build_workflow_blob_from_legacy,
    legacy_session_id_for_owner,
    peek_legacy_inferred_owner,
)
from music_workflow_legacy_projection import (
    project_active_blob_to_legacy_session,
)
from music_workflow_mutation import (
    commit_staged_workflow,
    resolve_workflow_routes,
    snapshot_session_for_rollback,
    validate_staged_blob,
)
from music_workflow_state_store import (
    ActiveWorkflowPointer,
    KeyAuthority,
    WorkflowStateBlob,
    collect_consistency_violations,
    get_active_workflow_pointer,
    get_workflow_blob,
    record_compat_fallback,
    resolve_workspace_identity,
    save_workflow_blob,
    set_active_workflow_pointer,
    workflow_cache_identity,
)

WORKFLOW_BOOTSTRAP_DONE_KEY = "_music_workflow_bootstrap_done"
WORKFLOW_ACTIVATION_DIAG_KEY = "_music_workflow_activation_diag"
WORKFLOW_ACTIVATION_LAST_KEY = "_music_workflow_activation_last"
WORKFLOW_ACTIVATION_ERROR_KEY = "_music_workflow_activation_error"
WORKFLOW_PENDING_CANONICAL_REASON_KEY = "_music_workflow_pending_canonical_reason"

PersistPolicy = Literal["none", "explicit", "durable_handoff"]
SAVE_REASON_ACTIVATE = "music_workflow_activate"


@dataclass
class ActivateWorkflowRequest:
    target_owner: str
    target_session_id: str = ""
    activation_source: str = "unspecified"
    incoming_blob: WorkflowStateBlob | None = None
    mutate_incoming: dict[str, Any] | None = None
    page_route: str = ""
    return_route: str = ""
    navigation_intent: str = ""
    active_creative_view: str = ""
    apply_studio_page: bool = False
    persist_policy: PersistPolicy = "none"
    expected_workspace_id: str = ""
    expected_account_id: str = ""
    expected_context_revision: int | None = None


@dataclass
class ActivateWorkflowResult:
    ok: bool
    skipped: bool = False
    error_code: str = ""
    error_message: str = ""
    trace: dict[str, Any] = field(default_factory=dict)


def _hydrate_blob_from_legacy_musical_snapshot(
    session: dict[str, Any],
    owner: str,
    session_id: str,
) -> bool:
    """Compatibility: seed store blob from workflow_musical_authority snapshots."""
    try:
        from workflow_musical_authority import WORKFLOW_MUSICAL_STATES_KEY

        store = session.get(WORKFLOW_MUSICAL_STATES_KEY)
        if not isinstance(store, dict):
            return False
        snap = store.get(owner)
        if not isinstance(snap, dict):
            return False
        blob = WorkflowStateBlob(workflow_owner=owner, workflow_session_id=session_id)
        if owner in {"song_based_improvisation", "mission_jam"}:
            dk = str(snap.get("display_key") or snap.get("concert_key") or "").strip()
            if dk:
                from music_workflow_compatibility import _tonic_mode_from_token

                pt, pm = _tonic_mode_from_token(dk)
                blob.keys = KeyAuthority(
                    practice_tonic=pt,
                    practice_mode=pm,
                    original_tonic=pt,
                    original_mode=pm,
                )
            sec = snap.get("sections")
            if isinstance(sec, dict):
                blob.section_map = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}
            if owner == "mission_jam":
                blob.selected_chord_symbol = str(snap.get("ii_selected_chord") or "")
                blob.selected_section = str(snap.get("ii_selected_section") or "")
                blob.selected_chord_index = int(snap.get("ii_selected_chord_index") or 0)
                blob.mission_type = str(snap.get("improv_active_mission") or "")
        elif owner == "style_jam":
            tk = str(snap.get("tonic_key") or "C").strip()
            from music_workflow_compatibility import _tonic_mode_from_token

            pt, pm = _tonic_mode_from_token(tk)
            blob.keys = KeyAuthority(practice_tonic=pt, practice_mode=pm, original_tonic=pt, original_mode=pm)
            blob.style = str(snap.get("style") or "")
            blob.mood = str(snap.get("mood") or "")
            blob.groove = str(snap.get("groove") or "")
            blob.tempo_bpm = int(snap.get("bpm") or 0)
            sec = snap.get("sections")
            if isinstance(sec, dict):
                blob.section_map = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}
        elif owner == "jam_session_generator":
            tk = str(snap.get("tonic_key") or "C").strip()
            from music_workflow_compatibility import _tonic_mode_from_token

            pt, pm = _tonic_mode_from_token(tk)
            blob.keys = KeyAuthority(practice_tonic=pt, practice_mode=pm, original_tonic=pt, original_mode=pm)
            blob.style = str(snap.get("style") or "")
            jam = snap.get("jam_session")
            if isinstance(jam, dict) and jam.get("id"):
                blob.generated_session_id = str(jam.get("id"))
            sec = snap.get("sections")
            if isinstance(sec, dict):
                blob.section_map = {str(k): list(v) for k, v in sec.items() if isinstance(v, list)}
        save_workflow_blob(session, blob, source="legacy_musical_snapshot_hydrate")
        record_compat_fallback(session, "legacy_musical_snapshot_hydrate", owner)
        return True
    except ImportError:
        return False


def capture_outgoing_blob(session: dict[str, Any]) -> tuple[str, str, WorkflowStateBlob | None]:
    ptr = get_active_workflow_pointer(session)
    if ptr and ptr.workflow_owner:
        owner = ptr.workflow_owner
        sid = ptr.workflow_session_id
    else:
        try:
            from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

            owner = str(session.get(ACTIVE_WORKFLOW_OWNER_KEY) or "").strip()
        except ImportError:
            owner = ""
        if not owner:
            entry = str(session.get("improv_entry_mode") or "").strip()
            try:
                from workflow_musical_authority import workflow_type_from_entry

                owner = workflow_type_from_entry(entry) or ""
            except ImportError:
                owner = ""
        if not owner:
            return "", "", None
        sid = legacy_session_id_for_owner(session, owner)
        record_compat_fallback(session, "capture_outgoing_legacy_owner", owner)
    stored = get_workflow_blob(session, owner, sid)
    try:
        from music_workflow_legacy_capture import capture_outgoing_workflow_blob

        outgoing = capture_outgoing_workflow_blob(
            session,
            owner=owner,
            session_id=sid,
            allow_legacy_bootstrap=stored is None,
        )
        if outgoing is not None:
            return owner, sid, outgoing
    except ImportError:
        pass
    if stored is not None:
        return owner, sid, stored
    fresh = build_workflow_blob_from_legacy(session, owner)
    fresh.workflow_owner = owner
    fresh.workflow_session_id = sid
    return owner, sid, fresh


def _merge_blob_mutations(blob: WorkflowStateBlob, mutate: dict[str, Any] | None) -> None:
    if not mutate:
        return
    for k, v in mutate.items():
        if k == "keys" and isinstance(v, dict):
            for kk, vv in v.items():
                if hasattr(blob.keys, kk):
                    setattr(blob.keys, kk, vv)
        elif hasattr(blob, k):
            setattr(blob, k, v)


def invalidate_workflow_caches(
    session: dict[str, Any],
    *,
    prev_ptr: ActiveWorkflowPointer | None,
    new_ptr: ActiveWorkflowPointer,
) -> list[str]:
    """Invalidate caches whose identity is incompatible with the new workflow."""
    invalidated: list[str] = []
    prev_id = str(session.get("_music_workflow_cache_identity") or "")
    new_id = workflow_cache_identity(session)
    if prev_id and prev_id != new_id:
        invalidated.append("workflow_cache_identity")
    if prev_ptr and (
        prev_ptr.workflow_owner != new_ptr.workflow_owner
        or prev_ptr.workflow_session_id != new_ptr.workflow_session_id
    ):
        for key in (
            "_canonical_artifact_projection_cache",
            "_backing_context_cache",
            "_creative_page_context_cache",
            "_route_snapshot_cache",
        ):
            if session.pop(key, None) is not None:
                invalidated.append(key)
        try:
            from songs.key_state import invalidate_backing_cache

            invalidate_backing_cache(session)
            invalidated.append("backing_audio_fingerprint")
        except ImportError:
            pass
        session.pop("_mission_example_output_fp", None)
        invalidated.append("mission_example_cache_hint")
    session["_music_workflow_cache_identity"] = new_id
    return invalidated


def _fail(session: dict[str, Any], code: str, message: str, trace: dict[str, Any]) -> ActivateWorkflowResult:
    trace["validation_result"] = "fail"
    trace["error_code"] = code
    session[WORKFLOW_ACTIVATION_DIAG_KEY] = trace
    session[WORKFLOW_ACTIVATION_ERROR_KEY] = {"code": code, "message": message}
    return ActivateWorkflowResult(ok=False, error_code=code, error_message=message, trace=trace)


def activate_workflow(session: dict[str, Any], request: ActivateWorkflowRequest) -> ActivateWorkflowResult:
    """Atomic workflow switch — complete before callers expose partial state."""
    t0 = time.perf_counter()
    ws, acct = resolve_workspace_identity(session)
    trace: dict[str, Any] = {
        "activation_requested": True,
        "activation_source": request.activation_source,
        "target_owner": request.target_owner,
        "target_session_id": request.target_session_id,
        "workspace_id": ws,
        "account_id": acct,
        "persistence_requested": request.persist_policy != "none",
        "persistence_performed": False,
        "persistence_skipped": True,
    }
    ptr_before = get_active_workflow_pointer(session)
    rev_before = int(ptr_before.context_revision if ptr_before else 0)
    trace["pointer_before"] = ptr_before.to_dict() if ptr_before else None
    trace["context_revision_before"] = rev_before

    if request.expected_workspace_id and request.expected_workspace_id != ws:
        return _fail(session, "WORKSPACE_MISMATCH", "Workspace identity mismatch.", trace)
    if request.expected_account_id and request.expected_account_id != acct:
        return _fail(session, "ACCOUNT_MISMATCH", "Account identity mismatch.", trace)
    if request.expected_context_revision is not None and ptr_before:
        if int(ptr_before.context_revision) != int(request.expected_context_revision):
            return _fail(session, "STALE_REVISION", "Workflow context revision is stale.", trace)

    target_owner = str(request.target_owner or "").strip()
    if not target_owner:
        return _fail(session, "MISSING_OWNER", "Target workflow owner is required.", trace)

    target_sid = str(request.target_session_id or "").strip() or legacy_session_id_for_owner(session, target_owner)
    trace["incoming_owner"] = target_owner
    trace["incoming_session"] = target_sid

    try:
        from music_workflow_canonical_identity import validate_pre_activation_identity

        identity = validate_pre_activation_identity(
            session,
            target_owner=target_owner,
            target_session_id=target_sid,
            ptr_before=ptr_before,
            activation_source=str(request.activation_source or ""),
        )
        trace["canonical_identity"] = identity.diagnostics
        if not identity.ok:
            trace["canonical_identity_violations"] = identity.violations
            return _fail(
                session,
                identity.error_code,
                "Canonical workflow identity conflict — activation aborted with no partial state change.",
                trace,
            )
    except ImportError:
        pass

    if (
        ptr_before
        and ptr_before.workflow_owner == target_owner
        and ptr_before.workflow_session_id == target_sid
        and not request.incoming_blob
        and not request.mutate_incoming
        and not request.page_route
        and not request.return_route
        and not request.navigation_intent
    ):
        trace["validation_result"] = "ok_unchanged"
        trace["skipped"] = True
        trace["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        session[WORKFLOW_ACTIVATION_LAST_KEY] = trace
        session.pop(WORKFLOW_ACTIVATION_ERROR_KEY, None)
        return ActivateWorkflowResult(ok=True, skipped=True, trace=trace)

    out_owner, out_sid, outgoing = capture_outgoing_blob(session)
    trace["outgoing_owner"] = out_owner
    trace["outgoing_session"] = out_sid
    if outgoing and out_owner and out_sid:
        if out_owner != target_owner or out_sid != target_sid:
            saved = save_workflow_blob(session, outgoing, source=f"activate_out:{request.activation_source}")
            trace["outgoing_blob_captured"] = saved
        elif ptr_before and ptr_before.workflow_owner == out_owner and ptr_before.workflow_session_id == out_sid:
            saved = save_workflow_blob(session, outgoing, source=f"activate_out:{request.activation_source}")
            trace["outgoing_blob_captured"] = saved
        else:
            trace["outgoing_blob_skipped"] = True

    target_blob = request.incoming_blob
    if target_blob is None:
        target_blob = get_workflow_blob(session, target_owner, target_sid)
        if target_blob is None and target_owner == "mission_jam":
            try:
                from music_workflow_mission_bootstrap import ensure_mission_blob_from_song

                target_blob = ensure_mission_blob_from_song(session, target_sid)
                if target_blob is not None:
                    trace["mission_bootstrap_source"] = session.get("_music_workflow_mission_bootstrap_diag", {})
            except ImportError:
                pass
        if target_blob is None:
            _hydrate_blob_from_legacy_musical_snapshot(session, target_owner, target_sid)
            target_blob = get_workflow_blob(session, target_owner, target_sid)
        if target_blob is None and target_owner != "mission_jam":
            target_blob = build_workflow_blob_from_legacy(session, target_owner)
            target_blob.workflow_owner = target_owner
            target_blob.workflow_session_id = target_sid
            trace["incoming_blob_built_compat"] = True
        elif target_blob is None and target_owner == "mission_jam":
            trace["mission_bootstrap_failed"] = True
            session["WORKFLOW_MISSION_BOOTSTRAP_USER_NOTICE"] = (
                "This Mission could not be restored from your current song practice state. "
                "Confirm the active song and practice key, then open Missions again."
            )
            return _fail(
                session,
                "MISSION_BOOTSTRAP_FAILED",
                str(session["WORKFLOW_MISSION_BOOTSTRAP_USER_NOTICE"]),
                trace,
            )
        else:
            if not trace.get("mission_bootstrap_source"):
                trace["incoming_blob_restored"] = True
    else:
        trace["incoming_blob_explicit"] = True

    _merge_blob_mutations(target_blob, request.mutate_incoming)
    if request.page_route == "backing":
        target_blob.last_backing_route = "backing"
        target_blob.page_route = "backing"
    elif request.page_route:
        target_blob.resumable_route = request.page_route
    if request.return_route:
        target_blob.return_to_source_route = request.return_route
        target_blob.return_route = request.return_route
    if request.active_creative_view:
        target_blob.active_creative_view = request.active_creative_view
    elif request.navigation_intent == "creative_missions":
        target_blob.active_creative_view = "Missions"

    mode = str(target_blob.keys.practice_mode or "").strip().lower()
    if not mode:
        return _fail(session, "MISSING_MODE", "Target workflow lacks explicit practice mode.", trace)

    nav = resolve_workflow_routes(
        blob=target_blob,
        requested_page=request.page_route if request.apply_studio_page else "",
        requested_return=request.return_route,
        navigation_intent=request.navigation_intent
        or ("creative_missions" if target_owner == "mission_jam" and request.activation_source.endswith("missions_tab_render") else "")
        or ("backing_open" if request.page_route == "backing" else "")
        or ("return_from_backing" if request.return_route else ""),
    )
    trace["route_resolution"] = nav
    if nav.get("violations"):
        trace["route_violations"] = nav.get("violations")

    legacy_snap = snapshot_session_for_rollback(session, target_owner)
    staged_ptr = ActiveWorkflowPointer(
        workflow_owner=target_owner,
        workflow_session_id=target_sid,
        context_revision=int(target_blob.context_revision or 1),
        activation_source=request.activation_source,
        workspace_id=ws,
        account_id=acct,
    )
    pre_v = validate_staged_blob(session, target_blob, staged_ptr)
    trace["validation_before_commit"] = pre_v
    if pre_v:
        from music_workflow_mutation import _restore_legacy_snapshot

        _restore_legacy_snapshot(session, legacy_snap, widget_safe=True)
        return _fail(session, "STAGED_VALIDATION", "Workflow activation failed validation.", trace)

    commit = commit_staged_workflow(
        session,
        target_blob,
        mutation_type="workflow_activation",
        source=request.activation_source,
        ptr=staged_ptr,
        navigation=nav,
        persist_policy=request.persist_policy,
        legacy_snapshot=legacy_snap,
    )
    if not commit.ok:
        return _fail(session, commit.error_code or "COMMIT_FAILED", commit.error_message or "Activation failed.", trace)

    ptr_after = get_active_workflow_pointer(session)
    trace["pointer_after"] = ptr_after.to_dict() if ptr_after else None
    trace["context_revision_after"] = int(ptr_after.context_revision if ptr_after else 0)
    trace["legacy_fields_projected"] = commit.trace.get("validation_after_projection")
    trace["validation_after_projection"] = commit.trace.get("validation_after_projection")

    if target_owner == "mission_jam":
        try:
            from workflow_musical_authority import sync_song_improv_sections_to_practice_key

            sync_song_improv_sections_to_practice_key(session)
        except ImportError:
            pass

    caches = invalidate_workflow_caches(session, prev_ptr=ptr_before, new_ptr=staged_ptr)
    trace["caches_invalidated"] = caches

    if request.persist_policy in {"explicit", "durable_handoff"}:
        try:
            from music_workflow_persist_lifecycle import request_workflow_canonical_persist

            rid = request_workflow_canonical_persist(
                session,
                SAVE_REASON_ACTIVATE,
                expected_revision=int(ptr_after.context_revision if ptr_after else 0),
            )
            trace["persist_request_id"] = rid
        except ImportError:
            session[WORKFLOW_PENDING_CANONICAL_REASON_KEY] = SAVE_REASON_ACTIVATE
        trace["persistence_skipped"] = False
        trace["persistence_requested"] = True

    trace["validation_result"] = "ok"
    trace["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    trace["deploy_sha"] = str(session.get("_studio_ui_release_sha") or "")[:7]
    session[WORKFLOW_ACTIVATION_DIAG_KEY] = trace
    session[WORKFLOW_ACTIVATION_LAST_KEY] = trace
    session.pop(WORKFLOW_ACTIVATION_ERROR_KEY, None)
    return ActivateWorkflowResult(ok=True, trace=trace)


def bootstrap_active_workflow_if_needed(session: dict[str, Any]) -> dict[str, Any]:
    """One-time compatibility bootstrap when no valid active pointer exists."""
    if session.get(WORKFLOW_BOOTSTRAP_DONE_KEY):
        return {"bootstrapped": False, "reason": "already_done"}
    ptr = get_active_workflow_pointer(session)
    if ptr and ptr.workflow_owner and ptr.workflow_session_id:
        session[WORKFLOW_BOOTSTRAP_DONE_KEY] = True
        return {"bootstrapped": False, "reason": "pointer_exists"}

    store = session.get("_music_workflow_state_store")
    if isinstance(store, dict) and (store.get("blobs") or {}):
        for raw in (store.get("blobs") or {}).values():
            b = WorkflowStateBlob.from_dict(raw)
            if b and b.workflow_owner:
                sid = b.workflow_session_id or legacy_session_id_for_owner(session, b.workflow_owner)
                activate_workflow(
                    session,
                    ActivateWorkflowRequest(
                        target_owner=b.workflow_owner,
                        target_session_id=sid,
                        activation_source="compatibility_bootstrap_store",
                    ),
                )
                session[WORKFLOW_BOOTSTRAP_DONE_KEY] = True
                return {
                    "bootstrapped": True,
                    "activation_source": "compatibility_bootstrap_store",
                    "owner": b.workflow_owner,
                    "session_id": sid,
                }

    inferred = peek_legacy_inferred_owner(session)
    if not inferred:
        entry = str(session.get("improv_entry_mode") or "").strip()
        tab = str(session.get("improv_intelligence_tab") or "").strip()
        if tab == "Missions":
            inferred = "mission_jam"
        elif entry == "Jam Session Generator":
            inferred = "jam_session_generator"
        elif entry == "Style Jam Mode":
            inferred = "style_jam"
        elif entry == "Song-Based Improvisation":
            inferred = "song_based_improvisation"
    if not inferred:
        session[WORKFLOW_BOOTSTRAP_DONE_KEY] = True
        return {"bootstrapped": False, "reason": "no_infer_signal"}

    sid = legacy_session_id_for_owner(session, inferred)
    result = activate_workflow(
        session,
        ActivateWorkflowRequest(
            target_owner=inferred,
            target_session_id=sid,
            activation_source="compatibility_bootstrap",
        ),
    )
    session[WORKFLOW_BOOTSTRAP_DONE_KEY] = True
    out = {
        "bootstrapped": result.ok,
        "activation_source": "compatibility_bootstrap",
        "owner": inferred,
        "session_id": sid,
        "fields_used": {
            "improv_entry_mode": session.get("improv_entry_mode"),
            "improv_intelligence_tab": session.get("improv_intelligence_tab"),
            "studio_page": session.get("studio_page"),
        },
    }
    session["_music_workflow_bootstrap_trace"] = out
    return out


def activate_workflow_for_entry_mode(session: dict[str, Any]) -> ActivateWorkflowResult | None:
    """Legacy API — queues typed activation; apply via pre-widget consume."""
    try:
        from music_workflow_pending_activation import queue_workflow_activation_for_entry_mode
    except ImportError:
        entry = str(session.get("improv_entry_mode") or "").strip()
        mapping = {
            "Song-Based Improvisation": "song_based_improvisation",
            "Style Jam Mode": "style_jam",
            "Jam Session Generator": "jam_session_generator",
        }
        owner = mapping.get(entry)
        if not owner:
            return None
        return activate_workflow_simple(
            session, owner, activation_source="entry_mode_change", navigation_intent="creative_entry"
        )
    out = queue_workflow_activation_for_entry_mode(session)
    if not out.get("queued"):
        return None
    return ActivateWorkflowResult(ok=True, skipped=True, trace={"queued_entry_mode_activation": out})


def activate_workflow_simple(
    session: dict[str, Any],
    target_owner: str,
    *,
    activation_source: str,
    persist_policy: PersistPolicy = "none",
    page_route: str = "",
    return_route: str = "",
    navigation_intent: str = "",
    active_creative_view: str = "",
) -> ActivateWorkflowResult:
    return activate_workflow(
        session,
        ActivateWorkflowRequest(
            target_owner=target_owner,
            activation_source=activation_source,
            persist_policy=persist_policy,
            page_route=page_route,
            return_route=return_route,
            navigation_intent=navigation_intent,
            active_creative_view=active_creative_view,
        ),
    )


def activation_user_notice(session: dict[str, Any]) -> str:
    err = session.get(WORKFLOW_ACTIVATION_ERROR_KEY)
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])
    bootstrap = str(session.get("WORKFLOW_MISSION_BOOTSTRAP_USER_NOTICE") or "").strip()
    if bootstrap:
        return bootstrap
    custom = str(session.get("_mission_bootstrap_key_notice") or "").strip()
    if custom:
        return custom
    return ""


__all__ = [
    "SAVE_REASON_ACTIVATE",
    "WORKFLOW_ACTIVATION_DIAG_KEY",
    "WORKFLOW_ACTIVATION_ERROR_KEY",
    "WORKFLOW_ACTIVATION_LAST_KEY",
    "WORKFLOW_BOOTSTRAP_DONE_KEY",
    "WORKFLOW_PENDING_CANONICAL_REASON_KEY",
    "ActivateWorkflowRequest",
    "ActivateWorkflowResult",
    "activate_workflow",
    "activate_workflow_for_entry_mode",
    "activate_workflow_simple",
    "activation_user_notice",
    "bootstrap_active_workflow_if_needed",
    "capture_outgoing_blob",
    "invalidate_workflow_caches",
]
