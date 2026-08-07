"""Authoritative workflow mutations — stage, validate, commit, rollback (Commit 3)."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from music_workflow_legacy_projection import (
    PROJECTED_LEGACY_KEYS,
    RequiresPreWidgetActivation,
    project_active_blob_to_legacy_session,
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
    validate_owner_bound_fingerprints,
    workflow_cache_identity,
)

WORKFLOW_MUTATION_DIAG_KEY = "_music_workflow_mutation_diag"
WORKFLOW_MUTATION_LAST_KEY = "_music_workflow_mutation_last"
ACTIVE_CREATIVE_VIEW_KEY = "_music_active_creative_view"
WORKFLOW_DIRECT_WRITE_LOG_KEY = "_music_workflow_direct_write_log"

VIOLATION_STALE_BACKING_ROUTE_OVERRIDE = "STALE_BACKING_ROUTE_OVERRIDE"
VIOLATION_WORKFLOW_ROUTE_OWNER_MISMATCH = "WORKFLOW_ROUTE_OWNER_MISMATCH"
VIOLATION_RETURN_ROUTE_DESTINATION_MISMATCH = "RETURN_ROUTE_DESTINATION_MISMATCH"
VIOLATION_KEY_HANDLER_OWNER_MISMATCH = "KEY_HANDLER_OWNER_MISMATCH"
VIOLATION_KEY_LABEL_PROGRESSION_MISMATCH = "KEY_LABEL_PROGRESSION_MISMATCH"
VIOLATION_STYLE_JAM_DOUBLE_TRANSPOSE = "STYLE_JAM_DOUBLE_TRANSPOSE_ATTEMPT"
VIOLATION_GENERATOR_KEY_PROGRESSION_MISMATCH = "GENERATOR_KEY_PROGRESSION_MISMATCH"
VIOLATION_GENERATOR_SECTION_OWNER_MISMATCH = "GENERATOR_SECTION_OWNER_MISMATCH"
VIOLATION_GENERATOR_PRETRANSPOSE_SECTIONS_RETAINED = "GENERATOR_PRETRANSPOSE_SECTIONS_RETAINED"
VIOLATION_WRITTEN_CONCERT_KEY_MISMATCH = "WRITTEN_CONCERT_KEY_MISMATCH"

PersistPolicy = Literal["none", "explicit", "durable_handoff"]

_OWNER_FOR_KEY_SOURCE: dict[str, str] = {
    "creative_jam_session": "jam_session_generator",
    "on_improv_jam_key_change": "jam_session_generator",
    "on_improv_style_key_change": "style_jam",
    "creative_style_jam": "style_jam",
    "sidebar_song_improv": "song_based_improvisation",
    "sidebar_mission": "mission_jam",
    "sidebar_missions": "mission_jam",
    "sync_sidebar_creative_concert_key": "",
}


@dataclass
class MutationResult:
    ok: bool
    error_code: str = ""
    error_message: str = ""
    rollback_performed: bool = False
    trace: dict[str, Any] = field(default_factory=dict)


def log_direct_owner_write_attempt(session: dict[str, Any], key: str, *, caller: str) -> None:
    bucket = session.setdefault(WORKFLOW_DIRECT_WRITE_LOG_KEY, [])
    if not isinstance(bucket, list):
        bucket = []
        session[WORKFLOW_DIRECT_WRITE_LOG_KEY] = bucket
    bucket.append({"key": key, "caller": caller, "ts": time.time()})
    record_compat_fallback(session, "direct_owner_write_blocked", caller)


def set_legacy_owner_compat_hint(session: dict[str, Any], owner: str) -> None:
    """Single allowed path for legacy _active_workflow_owner hint (projection pipeline)."""
    try:
        from workflow_musical_authority import ACTIVE_WORKFLOW_OWNER_KEY

        session[ACTIVE_WORKFLOW_OWNER_KEY] = str(owner or "").strip()
    except ImportError:
        pass


def _clone_blob(blob: WorkflowStateBlob) -> WorkflowStateBlob:
    return WorkflowStateBlob.from_dict(copy.deepcopy(blob.to_dict())) or blob


def _progression_fingerprint(section_map: dict[str, list[str]]) -> str:
    raw = json.dumps(section_map, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _snapshot_legacy_keys(session: dict[str, Any], owner: str) -> dict[str, Any]:
    keys = set()
    for group in PROJECTED_LEGACY_KEYS.values():
        keys.update(group)
    keys.update(
        {
            "studio_page",
            ACTIVE_CREATIVE_VIEW_KEY,
            "_music_workflow_return_route",
        }
    )
    return {k: copy.deepcopy(session.get(k)) for k in keys if k in session}


def snapshot_session_for_rollback(session: dict[str, Any], owner: str) -> dict[str, Any]:
    return _snapshot_legacy_keys(session, owner)


def _widget_bound_session_keys() -> frozenset[str]:
    try:
        from session_widget_safe import WIDGET_BOUND_KEYS

        return frozenset(WIDGET_BOUND_KEYS)
    except ImportError:
        return frozenset({"display_key"})


def _session_widgets_locked(session: dict[str, Any]) -> bool:
    try:
        from creative_mission_config_persistence import CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY

        if session.get(CREATIVE_MISSION_WIDGETS_INSTANTIATED_KEY):
            return True
    except ImportError:
        pass
    try:
        from session_widget_safe import widgets_likely_instantiated

        if widgets_likely_instantiated(session):
            return True
    except ImportError:
        pass
    return bool(session.get("_streamlit_widgets_locked_this_run"))


def _restore_legacy_snapshot(
    session: dict[str, Any],
    snap: dict[str, Any],
    *,
    widget_safe: bool = False,
) -> list[str]:
    """Restore legacy snapshot pre-widget only; never assign session keys when locked."""
    skipped: list[str] = list(snap.keys())
    locked = widget_safe and _session_widgets_locked(session)
    if locked:
        session["_music_workflow_rollback_skipped_keys"] = skipped
        session.setdefault(
            "_music_workflow_deferred_legacy_projection",
            {"reason": "rollback_canonical_only", "keys": skipped[:24]},
        )
        try:
            from music_workflow_projection_log import log_projection_defer

            log_projection_defer(
                session,
                result="ROLLBACK_CANONICAL_ONLY",
                rollback_mode="canonical_only",
                legacy_restore_attempted=False,
                deferred_projection=True,
                widgets_locked=True,
            )
        except ImportError:
            pass
        return skipped
    skipped = []
    for k, v in snap.items():
        if v is None:
            session.pop(k, None)
        else:
            session[k] = copy.deepcopy(v)
    return skipped


def resolve_workflow_routes(
    *,
    blob: WorkflowStateBlob,
    requested_page: str = "",
    requested_return: str = "",
    navigation_intent: str = "",
) -> dict[str, Any]:
    """Choose navigation fields — explicit request beats stale stored backing route."""
    stored_backing = str(blob.last_backing_route or blob.page_route or "").strip()
    stored_return = str(blob.return_to_source_route or blob.return_route or "").strip()
    chosen_page = ""
    precedence = "none"
    violations: list[str] = []

    intent = str(navigation_intent or "").strip().lower()
    req_page = str(requested_page or "").strip()
    req_return = str(requested_return or "").strip()

    if intent in {"creative_missions", "creative_entry", "creative_tab"}:
        chosen_page = "creative"
        precedence = "explicit_creative_intent"
        if stored_backing == "backing" and not req_page:
            violations.append(VIOLATION_STALE_BACKING_ROUTE_OVERRIDE)
    elif intent == "backing_open":
        chosen_page = "backing"
        precedence = "explicit_backing_open"
    elif intent == "return_from_backing":
        chosen_page = req_return or "creative"
        precedence = "return_route_request"
        if req_return and stored_return and req_return != stored_return:
            violations.append(VIOLATION_RETURN_ROUTE_DESTINATION_MISMATCH)
    elif req_page:
        chosen_page = req_page
        precedence = "requested_page_route"
    elif req_return:
        chosen_page = req_return
        precedence = "requested_return_route"
    else:
        precedence = "no_studio_page_apply"
        if stored_backing == "backing":
            violations.append(VIOLATION_STALE_BACKING_ROUTE_OVERRIDE)

    return {
        "stored_backing_route": stored_backing,
        "stored_return_route": stored_return,
        "requested_page": req_page,
        "requested_return": req_return,
        "chosen_studio_page": chosen_page,
        "precedence": precedence,
        "violations": violations,
        "navigation_intent": intent,
    }


def validate_staged_blob(
    session: dict[str, Any],
    blob: WorkflowStateBlob,
    ptr: ActiveWorkflowPointer,
    *,
    allow_owner_change: bool = False,
) -> list[str]:
    violations: list[str] = []
    if not allow_owner_change:
        if ptr.workflow_owner != blob.workflow_owner or ptr.workflow_session_id != blob.workflow_session_id:
            violations.append("POINTER_BLOB_IDENTITY_MISMATCH")
    mode = str(blob.keys.practice_mode or "").strip().lower()
    if not mode:
        violations.append("MISSING_MODE")
    if not str(blob.keys.practice_tonic or "").strip():
        violations.append("MISSING_TONIC")
    violations.extend(validate_owner_bound_fingerprints(session, blob))
    if blob.workflow_owner == "mission_jam" and blob.example_fingerprint and blob.selected_chord_symbol:
        if blob.backing_handoff_chord and blob.backing_handoff_chord != blob.selected_chord_symbol:
            violations.append("MISSION_BACKING_HANDOFF_CHORD_MISMATCH")
    live = str(session.get("display_key") or session.get("concert_key") or "").strip()
    if live and blob.workflow_owner in {"song_based_improvisation", "mission_jam"}:
        try:
            from music_workflow_compatibility import _tonic_mode_from_token

            pt, pm = _tonic_mode_from_token(live)
            if pm != blob.keys.practice_mode and pt != blob.keys.practice_tonic:
                pass
        except ImportError:
            pass
    return violations


def commit_staged_workflow(
    session: dict[str, Any],
    staged: WorkflowStateBlob,
    *,
    mutation_type: str,
    source: str,
    ptr: ActiveWorkflowPointer | None = None,
    navigation: dict[str, Any] | None = None,
    persist_policy: PersistPolicy = "none",
    legacy_snapshot: dict[str, Any] | None = None,
) -> MutationResult:
    """Validate staged blob, commit to store, project legacy — rollback on failure."""
    t0 = time.perf_counter()
    ws, acct = resolve_workspace_identity(session)
    ptr = ptr or get_active_workflow_pointer(session)
    trace: dict[str, Any] = {
        "mutation_type": mutation_type,
        "source": source,
        "owner": staged.workflow_owner,
        "session_id": staged.workflow_session_id,
        "staged_fingerprint": staged.material_fingerprint,
    }
    if ptr is None:
        return _fail_mutation(session, trace, legacy_snapshot, "NO_ACTIVE_POINTER", "No active workflow pointer.")

    staged.context_revision = max(int(staged.context_revision or 0), int(ptr.context_revision or 0))
    pre_violations = validate_staged_blob(session, staged, ptr)
    trace["validation_before_commit"] = pre_violations
    if pre_violations:
        return _fail_mutation(session, trace, legacy_snapshot, "STAGED_VALIDATION", "Workflow mutation failed validation.", pre_violations)

    ptr_before_commit = get_active_workflow_pointer(session)
    blob_before_commit = None
    if ptr_before_commit is not None:
        blob_before_commit = get_workflow_blob(
            session,
            ptr_before_commit.workflow_owner,
            ptr_before_commit.workflow_session_id,
        )

    save_workflow_blob(session, staged, source=f"{mutation_type}:{source}")
    new_ptr = ActiveWorkflowPointer(
        workflow_owner=staged.workflow_owner,
        workflow_session_id=staged.workflow_session_id,
        context_revision=int(staged.context_revision or ptr.context_revision),
        activation_source=source,
        workspace_id=ws,
        account_id=acct,
    )
    set_active_workflow_pointer(session, new_ptr, source=source)

    if staged.active_creative_view:
        session[ACTIVE_CREATIVE_VIEW_KEY] = staged.active_creative_view

    nav = navigation or {}
    chosen = str(nav.get("chosen_studio_page") or "").strip()
    trace["route_diag"] = nav
    if chosen:
        session["studio_page"] = chosen
    elif nav.get("precedence") == "no_studio_page_apply":
        pass

    session["_music_workflow_projection_mutation_source"] = str(source or mutation_type or "")
    try:
        project_active_blob_to_legacy_session(
            session,
            staged,
        )
    except RequiresPreWidgetActivation as exc:
        owner = str(staged.workflow_owner or exc.owner or "").strip()
        try:
            from music_workflow_projection_diagnostics import record_requires_pre_widget_activation

            record_requires_pre_widget_activation(
                session,
                exc,
                workflow_owner=owner,
                workflow_session_id=str(staged.workflow_session_id or ""),
                mutation_source=str(source or ""),
            )
        except ImportError:
            pass
        trace["requires_pre_widget_activation"] = {"owner": exc.owner, "field": exc.field}
        canonical_keep = mutation_type == "practice_key_change" and owner in {
            "style_jam",
            "jam_session_generator",
        }
        if not canonical_keep and str(source or "") in {
            "on_improv_style_key_change",
            "on_improv_jam_key_change",
        }:
            canonical_keep = True
        if not canonical_keep and mutation_type == "mission_example_artifact":
            canonical_keep = True
        if canonical_keep:
            trace["validation_result"] = "defer"
            trace["error_code"] = "PROJECTION_DEFERRED"
            trace["rollback_performed"] = False
            trace["legacy_snapshot_restored"] = False
            trace["canonical_blob_retained"] = True
            set_legacy_owner_compat_hint(session, staged.workflow_owner)
            session[WORKFLOW_MUTATION_DIAG_KEY] = trace
            session[WORKFLOW_MUTATION_LAST_KEY] = trace
            session["_music_workflow_deferred_legacy_projection"] = {
                "owner": owner,
                "source": source,
                "mutation_type": mutation_type,
            }
            try:
                from music_workflow_projection_log import log_projection_defer

                log_projection_defer(
                    session,
                    result="PROJECTION_DEFERRED",
                    rollback_mode="canonical_only",
                    legacy_restore_attempted=False,
                    deferred_projection=True,
                    widgets_locked=_session_widgets_locked(session),
                    extra={"owner": owner},
                )
            except ImportError:
                pass
            return MutationResult(
                ok=True,
                error_code="PROJECTION_DEFERRED",
                error_message=str(exc),
                rollback_performed=False,
                trace=trace,
            )
        if ptr_before_commit is not None:
            set_active_workflow_pointer(session, ptr_before_commit, source=f"rollback:{source}")
        if blob_before_commit is not None:
            save_workflow_blob(session, blob_before_commit, source=f"rollback:{source}")
        if mutation_type == "workflow_activation" or str(source or "") in {
            "entry_mode_change",
            "creative_tab_change",
            "creative_pre_widget",
            "test_late",
        }:
            try:
                from music_workflow_pending_activation import queue_pending_workflow_activation
                from music_workflow_compatibility import legacy_session_id_for_owner

                queue_pending_workflow_activation(
                    session,
                    target_owner=owner,
                    target_session_id=str(staged.workflow_session_id or "").strip()
                    or legacy_session_id_for_owner(session, owner),
                    activation_source=str(source or mutation_type or "projection_guard"),
                    navigation_intent=str(source or mutation_type or ""),
                    active_creative_view=str(
                        staged.active_creative_view or session.get(ACTIVE_CREATIVE_VIEW_KEY) or ""
                    ),
                )
            except ImportError:
                pass
        trace["validation_result"] = "defer"
        trace["error_code"] = "REQUIRES_PRE_WIDGET_ACTIVATION"
        trace["rollback_performed"] = True
        trace["legacy_snapshot_restored"] = False
        session[WORKFLOW_MUTATION_DIAG_KEY] = trace
        session[WORKFLOW_MUTATION_LAST_KEY] = trace
        session["_music_workflow_deferred_legacy_projection"] = {
            "owner": owner,
            "source": source,
        }
        try:
            from music_workflow_projection_log import log_projection_defer

            log_projection_defer(
                session,
                result="REQUIRES_PRE_WIDGET_ACTIVATION",
                rollback_mode="full",
                legacy_restore_attempted=False,
                deferred_projection=True,
                widgets_locked=_session_widgets_locked(session),
                extra={"owner": owner},
            )
        except ImportError:
            pass
        return MutationResult(
            ok=False,
            error_code="REQUIRES_PRE_WIDGET_ACTIVATION",
            error_message=str(exc),
            rollback_performed=True,
            trace=trace,
        )
    finally:
        session.pop("_music_workflow_projection_mutation_source", None)
    set_legacy_owner_compat_hint(session, staged.workflow_owner)

    try:
        from active_musical_workflow_envelope import project_envelope_from_active_store

        project_envelope_from_active_store(session)
    except ImportError:
        pass

    post_violations = collect_consistency_violations(session)
    trace["validation_after_projection"] = post_violations
    if post_violations:
        return _fail_mutation(session, trace, legacy_snapshot, "POST_PROJECTION_VALIDATION", "Projected workflow state is inconsistent.", post_violations)

    session["_music_workflow_cache_identity"] = workflow_cache_identity(session)
    if persist_policy in {"explicit", "durable_handoff"}:
        canon_reason = "material_workflow_key_change" if mutation_type == "practice_key_change" else (
            "creative_mission_example_change" if mutation_type == "mission_example_artifact" else "music_workflow_state_save"
        )
        try:
            from music_workflow_persist_lifecycle import supersede_workflow_persist_request

            supersede_workflow_persist_request(
                session,
                reason=canon_reason,
                expected_revision=int(staged.context_revision or 0),
                expected_fingerprint=str(staged.material_fingerprint or ""),
                owner=str(staged.workflow_owner or ""),
                session_id=str(staged.workflow_session_id or ""),
                expected_workspace_revision=int(session.get("_suite_applied_workspace_revision") or 0),
            )
        except ImportError:
            session["_music_workflow_pending_canonical_reason"] = canon_reason

    trace["validation_result"] = "ok"
    trace["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    trace["deploy_sha"] = str(session.get("_studio_ui_release_sha") or "")[:7]
    session[WORKFLOW_MUTATION_DIAG_KEY] = trace
    session[WORKFLOW_MUTATION_LAST_KEY] = trace
    return MutationResult(ok=True, trace=trace)


def _fail_mutation(
    session: dict[str, Any],
    trace: dict[str, Any],
    legacy_snapshot: dict[str, Any] | None,
    code: str,
    message: str,
    violations: list[str] | None = None,
) -> MutationResult:
    rollback = False
    locked = _session_widgets_locked(session)
    if legacy_snapshot is not None and code != "REQUIRES_PRE_WIDGET_ACTIVATION":
        if locked:
            trace["rollback_mode"] = "canonical_only"
            trace["legacy_restore_attempted"] = False
            trace["rollback_skipped_widget_keys"] = list(legacy_snapshot.keys())
            session.setdefault(
                "_music_workflow_deferred_legacy_projection",
                {"reason": "fail_mutation_canonical_only", "code": code},
            )
            try:
                from music_workflow_projection_log import log_projection_defer

                log_projection_defer(
                    session,
                    result=str(code or "MUTATION_FAIL"),
                    rollback_mode="canonical_only",
                    legacy_restore_attempted=False,
                    deferred_projection=True,
                    widgets_locked=True,
                )
            except ImportError:
                pass
        else:
            _restore_legacy_snapshot(session, legacy_snapshot, widget_safe=False)
            rollback = True
    trace["validation_result"] = "fail"
    trace["error_code"] = code
    if violations:
        trace["violations"] = violations
    trace["rollback_performed"] = rollback
    session[WORKFLOW_MUTATION_DIAG_KEY] = trace
    session[WORKFLOW_MUTATION_LAST_KEY] = trace
    try:
        from music_workflow_activation import WORKFLOW_ACTIVATION_ERROR_KEY

        session[WORKFLOW_ACTIVATION_ERROR_KEY] = {"code": code, "message": message}
    except ImportError:
        pass
    return MutationResult(ok=False, error_code=code, error_message=message, rollback_performed=rollback, trace=trace)


def mutate_active_workflow(
    session: dict[str, Any],
    mutator: Callable[[WorkflowStateBlob], None],
    *,
    mutation_type: str,
    source: str,
    expected_owner: str = "",
    persist_policy: PersistPolicy = "none",
) -> MutationResult:
    ptr = get_active_workflow_pointer(session)
    if ptr is None or not ptr.workflow_owner:
        return MutationResult(ok=False, error_code="NO_POINTER", error_message="No active workflow.")
    if expected_owner and ptr.workflow_owner != expected_owner:
        return MutationResult(ok=False, error_code="OWNER_MISMATCH", error_message="Active owner mismatch.")
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return MutationResult(ok=False, error_code="NO_BLOB", error_message="Active blob missing.")
    legacy_snap = _snapshot_legacy_keys(session, ptr.workflow_owner)
    staged = _clone_blob(blob)
    mutator(staged)
    return commit_staged_workflow(
        session,
        staged,
        mutation_type=mutation_type,
        source=source,
        ptr=ptr,
        persist_policy=persist_policy,
        legacy_snapshot=legacy_snap,
    )


def _invalidate_mission_chord_dependent_session(session: dict[str, Any], *, new_chord: str) -> None:
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY, MISSIONS_GENERATE_CONTEXT_KEY
    except ImportError:
        MISSION_EXAMPLE_KEY = "improv_mission_example"  # type: ignore[misc]
        MISSIONS_GENERATE_CONTEXT_KEY = "_missions_tab_generate_context"  # type: ignore[misc]
    try:
        from improvisation_missions import MISSION_EXAMPLE_KEY

        ex = session.get(MISSION_EXAMPLE_KEY)
        if isinstance(ex, dict) and str(ex.get("chord") or "").strip() not in {"", str(new_chord or "").strip()}:
            session.pop(MISSION_EXAMPLE_KEY, None)
            session.pop("_mission_example_output_fp", None)
            session.pop("_mission_example_material_fp", None)
    except ImportError:
        session.pop("improv_mission_example", None)
    session.pop(MISSIONS_GENERATE_CONTEXT_KEY, None)
    session.pop("improv_mission_recording_seal", None)
    session.pop("_mission_exact_backing_armed", None)
    session.pop("improv_mission_backing_handoff", None)
    try:
        from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

        invalidate_exact_chord_backing_cache(session)
    except ImportError:
        pass
    try:
        from mission_practice_context import refresh_mission_practice_context

        refresh_mission_practice_context(session)
    except ImportError:
        pass


def mutate_mission_chord_selection(
    session: dict[str, Any],
    *,
    chord: str,
    section: str,
    chord_index: int,
    chord_label: str,
    button_key: str = "",
) -> MutationResult:
    """B1 — mission chord updates active mission_jam blob atomically."""
    try:
        from music_workflow_song_practice import mirror_mission_keys_from_song_blob

        mirror_mission_keys_from_song_blob(session)
    except ImportError:
        pass
    ptr = get_active_workflow_pointer(session)
    if ptr is None or ptr.workflow_owner != "mission_jam":
        try:
            from music_workflow_activation import ActivateWorkflowRequest, activate_workflow

            sid = str(session.get("active_catalog_pick_key") or "song").strip()
            try:
                from music_workflow_mission_session import mission_blob_session_id

                sid = mission_blob_session_id(session)
            except ImportError:
                sid = f"mission|catalog|{sid}"
            activate_workflow(
                session,
                ActivateWorkflowRequest(
                    target_owner="mission_jam",
                    target_session_id=sid,
                    activation_source="mission_chord_pre_activate",
                    navigation_intent="creative_missions",
                ),
            )
        except ImportError:
            return MutationResult(ok=False, error_code="NOT_MISSION", error_message="Mission workflow not active.")
        ptr = get_active_workflow_pointer(session)

    prev_chord = ""
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id) if ptr else None
    if blob:
        prev_chord = str(blob.selected_chord_symbol or "").strip()

    try:
        from creative_mission_config_persistence import handle_user_mission_target_selection

        handle_user_mission_target_selection(
            session,
            chord=chord,
            section=section,
            chord_index=int(chord_index),
            chord_label=chord_label,
            button_key=button_key,
        )
    except ImportError:
        session["ii_selected_chord"] = chord
        session["ii_selected_section"] = section
        session["ii_selected_chord_index"] = int(chord_index)
        session["ii_selected_chord_label"] = chord_label

    new_sym = str(chord or "").strip()
    new_sec = str(section or "").strip()
    prev_sec = ""
    if blob:
        prev_sec = str(blob.selected_section or "").strip()
    chord_changed = bool(new_sym) and (prev_chord != new_sym or prev_sec != new_sec)
    source_page = str(session.get("improv_intelligence_tab") or session.get("creative_improv_intelligence_tab") or "Missions")
    try:
        from song_creative_focus_change import commit_song_creative_focus_selection

        commit_song_creative_focus_selection(
            session,
            section=str(section or "").strip(),
            concert_chord=new_sym,
            chord_index=int(chord_index),
            source_page=str(source_page or "Missions"),
        )
    except ImportError:
        pass

    def _mut(b: WorkflowStateBlob) -> None:
        b.selected_chord_symbol = str(chord or "").strip()
        b.selected_section = str(section or "").strip()
        b.selected_chord_index = int(chord_index)
        b.backing_handoff_chord = str(chord or "").strip()
        b.recording_seal_chord = ""
        b.active_creative_view = "Missions"
        if prev_chord and prev_chord != str(chord or "").strip():
            b.example_fingerprint = ""
            b.artifact_fingerprint = ""
        try:
            from mission_practice_context import authoritative_mission_type

            mt = authoritative_mission_type(session)
            b.mission_type = mt
            b.mission_id = mt
        except ImportError:
            b.mission_type = str(session.get("improv_active_mission") or "").strip()
            b.mission_id = b.mission_type

    result = mutate_active_workflow(
        session,
        _mut,
        mutation_type="mission_chord_selection",
        source="apply_atomic_mission_chord",
        expected_owner="mission_jam",
    )
    if chord_changed:
        _invalidate_mission_chord_dependent_session(session, new_chord=new_sym)
    return result


def _reconcile_key_dependent_state(
    session: dict[str, Any],
    blob: WorkflowStateBlob,
    owner: str,
    old_key: str,
    new_key: str,
) -> None:
    if old_key == new_key:
        return
    if owner in {"style_jam", "jam_session_generator"}:
        blob.example_fingerprint = ""
        blob.artifact_fingerprint = ""
        blob.backing_handoff_chord = ""
        return
    if owner not in {"mission_jam", "song_based_improvisation"}:
        return
    blob.example_fingerprint = ""
    blob.artifact_fingerprint = ""
    blob.backing_handoff_chord = ""
    blob.recording_seal_chord = ""
    session.pop("improv_mission_recording_seal", None)
    session.pop("_mission_exact_backing_armed", None)
    session.pop("improv_mission_backing_handoff", None)
    try:
        from music_workflow_key_projection_invalidation import invalidate_key_dependent_session_projections

        invalidate_key_dependent_session_projections(session, owner=owner)
    except ImportError:
        pass
    try:
        from mission_exact_chord_backing import invalidate_exact_chord_backing_cache

        invalidate_exact_chord_backing_cache(session)
    except ImportError:
        pass


def _parse_key_token(key: str) -> tuple[str, str]:
    try:
        from music_workflow_compatibility import _tonic_mode_from_token

        return _tonic_mode_from_token(str(key or "C"))
    except ImportError:
        return "C", "major"


def update_active_practice_key(
    session: dict[str, Any],
    key_token: str,
    *,
    source: str,
    transpose_progression: bool = True,
    persist_policy: PersistPolicy = "none",
) -> MutationResult:
    """B3 — update practice key on the active owner blob only."""
    ptr = get_active_workflow_pointer(session)
    if ptr is None:
        return MutationResult(ok=False, error_code="NO_POINTER", error_message="No active workflow.")
    expected = _OWNER_FOR_KEY_SOURCE.get(source, "")
    if expected and ptr.workflow_owner != expected:
        if source in {"on_improv_style_key_change", "on_improv_jam_key_change"}:
            try:
                from generated_jam_key_change import align_generated_workflow_pointer_for_key_edit

                align_generated_workflow_pointer_for_key_edit(session, expected)
                ptr = get_active_workflow_pointer(session)
            except ImportError:
                pass
        if source == "sidebar_song_improv" and ptr and ptr.workflow_owner in {"mission_jam", "song_based_improvisation"}:
            pass
        elif expected and ptr and ptr.workflow_owner != expected:
            return MutationResult(
                ok=False,
                error_code="KEY_HANDLER_OWNER_MISMATCH",
                error_message="Key handler owner does not match active workflow.",
            )
    if ptr is None:
        return MutationResult(ok=False, error_code="NO_POINTER", error_message="No active workflow.")
    owner = ptr.workflow_owner
    if owner not in {"song_based_improvisation", "mission_jam", "style_jam", "jam_session_generator"}:
        return MutationResult(ok=False, error_code="UNSUPPORTED_OWNER", error_message="Key change unsupported for owner.")

    new_tonic, new_mode = _parse_key_token(key_token)
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return MutationResult(ok=False, error_code="NO_BLOB", error_message="Active blob missing.")

    prev_token = f"{blob.keys.practice_tonic}{blob.keys.practice_mode}"
    new_token = f"{new_tonic}{new_mode}"
    key_material_change = new_token != prev_token
    effective_persist: PersistPolicy = persist_policy
    if key_material_change and effective_persist == "none":
        effective_persist = "explicit"
    prev_sections_fp = _progression_fingerprint(blob.section_map)
    auth_old_key = f"{blob.keys.practice_tonic}m" if blob.keys.practice_mode == "minor" else blob.keys.practice_tonic

    def _mut(b: WorkflowStateBlob) -> None:
        orig_t = b.keys.original_tonic or b.keys.practice_tonic
        orig_m = b.keys.original_mode or b.keys.practice_mode
        b.keys = KeyAuthority(
            original_tonic=orig_t,
            original_mode=orig_m,
            practice_tonic=new_tonic,
            practice_mode=new_mode,
            written_tonic=b.keys.written_tonic,
            written_mode=b.keys.written_mode,
            instrument=b.keys.instrument or str(session.get("instrument") or ""),
            key_owner=owner,
        )
        if owner == "jam_session_generator":
            old_key = auth_old_key
            sections_src: dict[str, list[str]] = copy.deepcopy(b.section_map) if b.section_map else {}
            jam = session.get("improv_jam_session")
            jam_id = ""
            if isinstance(jam, dict):
                jam_id = str(jam.get("id") or b.generated_session_id or "").strip()
                if isinstance(jam.get("sections"), dict) and jam.get("sections"):
                    sections_src = copy.deepcopy(jam.get("sections"))
            if sections_src and transpose_progression and old_key and old_key != key_token:
                try:
                    from music_theory import transpose_sections_dict

                    transposed = transpose_sections_dict(sections_src, old_key, key_token)
                    b.section_map = transposed
                    if isinstance(jam, dict):
                        session["improv_jam_session"] = {
                            **copy.deepcopy(jam),
                            "sections": copy.deepcopy(transposed),
                            "id": jam_id or jam.get("id"),
                        }
                except ImportError:
                    b.section_map = sections_src
                    record_compat_fallback(session, VIOLATION_GENERATOR_PRETRANSPOSE_SECTIONS_RETAINED, key_token)
            elif sections_src:
                b.section_map = sections_src
            if jam_id:
                b.generated_session_id = jam_id
        elif owner == "style_jam" and transpose_progression and b.section_map:
            old_key = auth_old_key
            try:
                from music_theory import transpose_sections_dict

                b.section_map = transpose_sections_dict(b.section_map, old_key, key_token)
            except ImportError:
                pass
        elif transpose_progression and b.section_map:
            old_key = auth_old_key
            try:
                from music_theory import transpose_sections_dict

                b.section_map = transpose_sections_dict(b.section_map, old_key, key_token)
            except ImportError:
                pass
        if owner == "mission_jam" and b.section_map:
            flat = [c for chs in b.section_map.values() for c in chs]
            idx = int(b.selected_chord_index or 0)
            if flat and 0 <= idx < len(flat):
                b.selected_chord_symbol = str(flat[idx])
        if key_material_change:
            _reconcile_key_dependent_state(session, b, owner, auth_old_key, key_token)

    trace_extra = {
        "key_handler_source": source,
        "requested_key": key_token,
        "authoritative_old_key": auth_old_key,
        "progression_fp_before": prev_sections_fp,
        "transpose_applications": 1 if transpose_progression else 0,
    }
    result = mutate_active_workflow(
        session,
        _mut,
        mutation_type="practice_key_change",
        source=source,
        expected_owner=owner,
        persist_policy=effective_persist,
    )
    if result.ok:
        result.trace.update(trace_extra)
        result.trace["progression_fp_after"] = _progression_fingerprint(
            (get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id) or blob).section_map
        )
        result.trace["projected_legacy_key"] = str(session.get("display_key") or session.get("concert_key") or "")
        session[WORKFLOW_MUTATION_LAST_KEY] = result.trace
        try:
            from music_workflow_song_practice import mirror_song_practice_key_to_mission_blob, song_based_blob_session_id

            if owner in {"song_based_improvisation", "mission_jam"}:
                active_blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
                if active_blob:
                    song_sid = song_based_blob_session_id(session)
                    if owner == "mission_jam":
                        song_blob = get_workflow_blob(session, "song_based_improvisation", song_sid)
                        if song_blob is None:
                            song_blob = WorkflowStateBlob(
                                workflow_owner="song_based_improvisation",
                                workflow_session_id=song_sid,
                                keys=active_blob.keys,
                                section_map=copy.deepcopy(active_blob.section_map),
                            )
                            save_workflow_blob(session, song_blob, source="key_mirror_song")
                        else:
                            song_blob.keys = copy.deepcopy(active_blob.keys)
                            song_blob.section_map = copy.deepcopy(active_blob.section_map)
                            save_workflow_blob(session, song_blob, source="key_mirror_song")
                        mirror_song_practice_key_to_mission_blob(session, song_blob)
                    else:
                        mirror_song_practice_key_to_mission_blob(session, active_blob)
        except ImportError:
            pass
    return result


def mutate_mission_handoff_aligned(
    session: dict[str, Any],
    *,
    mission: str,
    cur_chord: str,
    section_label: str,
    chord_idx: int,
    example: Any | None = None,
) -> MutationResult:
    if example is not None and str(getattr(example, "chord", "") or "") != str(cur_chord):
        return MutationResult(ok=False, error_code="HANDOFF_MISMATCH", error_message="Example chord mismatch.")
    result = mutate_mission_chord_selection(
        session,
        chord=str(cur_chord),
        section=str(section_label),
        chord_index=int(chord_idx),
        chord_label=f"{section_label} · {cur_chord}",
    )
    if result.ok:
        session["_mission_last_handoff_chord"] = str(cur_chord)
        try:
            from mission_practice_context import ensure_mission_practice_context

            ensure_mission_practice_context(session, force=True)
        except ImportError:
            pass
    return result


def update_mission_example_on_blob(
    session: dict[str, Any],
    *,
    chord: str,
    example_fingerprint: str,
    artifact_fingerprint: str = "",
    mission_type: str = "",
    section: str = "",
) -> MutationResult:
    try:
        from music_workflow_song_practice import mirror_mission_keys_from_song_blob

        mirror_mission_keys_from_song_blob(session)
    except ImportError:
        pass

    def _mut(b: WorkflowStateBlob) -> None:
        b.selected_chord_symbol = str(chord or "").strip()
        b.example_fingerprint = str(example_fingerprint or "")[:24]
        if artifact_fingerprint:
            b.artifact_fingerprint = str(artifact_fingerprint)[:24]
        if mission_type:
            b.mission_type = str(mission_type).strip()
        if section:
            b.selected_section = str(section).strip()
        try:
            idx_raw = session.get("II_SELECTED_CHORD_INDEX", session.get("ii_selected_chord_index"))
            if idx_raw is not None and str(idx_raw).strip() != "":
                b.selected_chord_index = int(idx_raw)
        except (TypeError, ValueError):
            pass
        if b.selected_chord_symbol and b.example_fingerprint:
            b.backing_handoff_chord = b.selected_chord_symbol

    return mutate_active_workflow(
        session,
        _mut,
        mutation_type="mission_example_artifact",
        source="mission_example_save",
        expected_owner="mission_jam",
        persist_policy="explicit",
    )


def mission_example_matches_active_blob(session: dict[str, Any], *, chord: str, example_fp: str) -> bool:
    ptr = get_active_workflow_pointer(session)
    if not ptr or ptr.workflow_owner != "mission_jam":
        return True
    blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return False
    if blob.selected_chord_symbol and str(chord or "").strip() != blob.selected_chord_symbol:
        return False
    if blob.example_fingerprint and example_fp and blob.example_fingerprint != str(example_fp)[:24]:
        return False
    return True


def should_project_mission_config_from_canonical(session: dict[str, Any]) -> bool:
    """Active blob wins over stale canonical mission config."""
    try:
        from creative_mission_config_persistence import canonical_mission_config_value

        canon_chord = str(canonical_mission_config_value(session, "ii_selected_chord") or "").strip()
    except ImportError:
        canon_chord = ""
    try:
        from song_creative_focus import read_song_creative_focus

        focus = read_song_creative_focus(session)
        if focus and canon_chord:
            fc = str(focus.get("selected_concert_chord") or "").strip()
            if fc and fc != canon_chord:
                record_compat_fallback(session, "canonical_mission_config_stale_focus", canon_chord)
                return False
    except ImportError:
        pass
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if not ptr:
            return True
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        if blob is None:
            return True
        if ptr.workflow_owner == "song_based_improvisation":
            if canon_chord and blob.selected_chord_symbol and canon_chord != blob.selected_chord_symbol:
                record_compat_fallback(session, "canonical_mission_config_stale_song_blob", canon_chord)
                return False
            try:
                from musical_context_authority import resolve_authoritative_practice_key
                from music_theory import key_center_token

                pk = resolve_authoritative_practice_key(session)
                live_key = key_center_token(pk.practice_tonic, pk.practice_mode)
                blob_key = key_center_token(blob.keys.practice_tonic, blob.keys.practice_mode)
                if live_key and blob_key and live_key != blob_key:
                    record_compat_fallback(session, "canonical_mission_config_stale_practice_key", live_key)
                    return False
            except ImportError:
                pass
            return True
        if ptr.workflow_owner != "mission_jam":
            return True
        if canon_chord and blob.selected_chord_symbol and canon_chord != blob.selected_chord_symbol:
            record_compat_fallback(session, "canonical_mission_config_stale", canon_chord)
            return False
    except ImportError:
        return True
    return True


__all__ = [
    "ACTIVE_CREATIVE_VIEW_KEY",
    "MutationResult",
    "VIOLATION_KEY_HANDLER_OWNER_MISMATCH",
    "VIOLATION_STALE_BACKING_ROUTE_OVERRIDE",
    "WORKFLOW_MUTATION_DIAG_KEY",
    "WORKFLOW_MUTATION_LAST_KEY",
    "commit_staged_workflow",
    "log_direct_owner_write_attempt",
    "mutate_active_workflow",
    "mutate_mission_handoff_aligned",
    "mutate_mission_chord_selection",
    "mission_example_matches_active_blob",
    "should_project_mission_config_from_canonical",
    "update_mission_example_on_blob",
    "resolve_workflow_routes",
    "set_legacy_owner_compat_hint",
    "snapshot_session_for_rollback",
    "update_active_practice_key",
    "validate_staged_blob",
]
