"""Suppress false-positive workspace saves during cloud hydration and restore."""

from __future__ import annotations

from typing import Any

STARTUP_RESTORE_IN_PROGRESS_KEY = "startup_restore_in_progress"
STARTUP_SUPPRESSION_ARMED_KEY = "startup_suppression_armed"
STARTUP_SUPPRESSION_ARMED_STAGE_KEY = "startup_suppression_armed_stage"
STARTUP_SUPPRESSION_RELEASED_KEY = "startup_suppression_released"
HYDRATED_FP_RECORDED_STAGE_KEY = "hydrated_fingerprint_recorded_stage"
RESTORE_FINALIZED_STAGE_KEY = "restore_finalized_stage"
FIRST_SONG_EDIT_REQUESTED_STAGE_KEY = "first_song_edit_requested_stage"
STARTUP_PENDING_EDIT_REASONS_KEY = "startup_pending_edit_reasons"
STARTUP_PENDING_EDITS_DISCARDED_KEY = "startup_pending_edits_discarded"
STARTUP_WRITE_SUPPRESSED_KEY = "startup_write_suppressed"
STARTUP_WRITE_ALLOWED_REASON_KEY = "startup_write_allowed_reason"
STARTUP_SAVE_SUPPRESSED_KEY = "startup_save_suppressed"
STARTUP_SAVE_SUPPRESSION_REASON_KEY = "startup_save_suppression_reason"
HYDRATED_CANONICAL_FP_KEY = "hydrated_canonical_fingerprint"
POST_RESTORE_CANONICAL_FP_KEY = "post_restore_canonical_fingerprint"
STARTUP_FINGERPRINT_MATCHES_KEY = "startup_fingerprint_matches"
DIFFERING_CANONICAL_PATHS_KEY = "differing_canonical_paths"
STARTUP_REVISION_LOADED_KEY = "startup_revision_loaded"
STARTUP_REVISION_FINAL_KEY = "startup_revision_final"
HYDRATED_PAYLOAD_SNAPSHOT_KEY = "_music_hydrated_payload_canonical_snapshot"
PAGE_CHANGE_ORIGIN_KEY = "music_page_change_origin"

QUEUED_PAGE_STARTUP_RELEASE_IMPL = "QUEUED_PAGE_STARTUP_RELEASE_IMPL: 38664fc-v2"

_PAGE_CHANGE_ORIGINS: frozenset[str] = frozenset(
    {
        "user_navigation",
        "cloud_restore",
        "startup_default",
        "reconciliation",
        "unknown",
    }
)

_RESTORE_BLOCKED_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "song_edit",
        "display_key_change",
        "capo_widget",
        "autosave",
        "force_autosave",
    }
)

_EXPLICIT_STARTUP_SAVE_REASONS: frozenset[str] = frozenset(
    {
        "startup_migration",
        "canonical_repair",
        "creative_schema_migration",
        # Catalog ↔ Custom ↔ Composition ownership changes must always land on
        # disk even while startup song_edit suppression is still armed.
        "music_source_switch",
    }
)


def _canonical_fp(state: dict[str, Any] | None) -> str:
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    return workspace_canonical_content_fingerprint(state if isinstance(state, dict) else {})


def _is_page_bearing_canonical_path(path: str) -> bool:
    p = str(path or "").strip()
    if not p:
        return False
    if p.endswith(".studio_page") or p.endswith(".page"):
        return True
    return p in {"core.studio_page", "core.page"}


def _differing_only_queued_page_navigation(
    differing: list[str],
    *,
    hydrated_page: str,
    queued_page: str,
) -> bool:
    if not differing:
        return True
    hp = _normalize_page_id(hydrated_page)
    qp = _normalize_page_id(queued_page)
    if not qp or not hp or hp == qp:
        return False
    return all(_is_page_bearing_canonical_path(str(p)) for p in differing)


def _defer_finalize_for_pending_queued_display_key_change(session: dict[str, Any]) -> bool:
    try:
        from display_key_startup_save_queue import has_queued_display_key_change, is_genuine_queued_display_key_change

        if has_queued_display_key_change(session) and is_genuine_queued_display_key_change(session):
            return True
    except ImportError:
        pass
    return False


def _apply_queued_display_key_startup_release(
    session: dict[str, Any],
    *,
    stage: str = "display_key_release",
) -> None:
    """Release startup suppression for queued explicit sidebar display_key without discarding Cm."""
    hydrated_fp = str(session.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    post_fp = str(session.get(POST_RESTORE_CANONICAL_FP_KEY) or "").strip() or hydrated_fp
    try:
        from display_key_startup_save_queue import record_startup_release_diag

        record_startup_release_diag(
            session,
            release_stage=str(stage or "display_key_release"),
            restore_finalized=bool(session.get(RESTORE_FINALIZED_STAGE_KEY)),
            fingerprint_semantic_match=bool(session.get(STARTUP_FINGERPRINT_MATCHES_KEY)),
            ignored_volatile_paths=list(session.get(DIFFERING_CANONICAL_PATHS_KEY) or [])
            if isinstance(session.get(DIFFERING_CANONICAL_PATHS_KEY), list)
            else None,
        )
    except ImportError:
        pass
    session[STARTUP_SUPPRESSION_RELEASED_KEY] = True
    session[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
    session[STARTUP_WRITE_ALLOWED_REASON_KEY] = "queued_display_key_change_after_alignment"
    session.pop(STARTUP_SAVE_SUPPRESSED_KEY, None)
    session.pop(STARTUP_SAVE_SUPPRESSION_REASON_KEY, None)
    try:
        from workspace_revision import (
            APPLIED_REVISION_KEY,
            CLOUD_REVISION_KEY,
            LAST_CONFIRMED_REVISION_KEY,
            LOCAL_REVISION_KEY,
        )

        rev_loaded = int(session.get(STARTUP_REVISION_LOADED_KEY) or 0)
        if rev_loaded:
            session[LAST_CONFIRMED_REVISION_KEY] = rev_loaded
            session[CLOUD_REVISION_KEY] = rev_loaded
            session[APPLIED_REVISION_KEY] = rev_loaded
            session[LOCAL_REVISION_KEY] = rev_loaded
    except ImportError:
        pass
    try:
        from music_egress_strict_save import note_confirmed_cloud_fingerprint

        note_confirmed_cloud_fingerprint(session, post_fp or hydrated_fp)
    except ImportError:
        if post_fp or hydrated_fp:
            session["_music_last_confirmed_cloud_fp"] = post_fp or hydrated_fp


def _metadata_only_canonical_diff(differing: list[str]) -> bool:
    """True when path diffs are only noncanonical ownership/timestamp metadata."""
    if not differing:
        return True
    allowed = (
        "display_key_owner_identity",
        "improv_mission_workspace_updated_at",
        "creative_session.updated_at",
        ".updated_at",
    )
    for path in differing:
        p = str(path)
        if not any(p.endswith(suffix) or suffix in p for suffix in allowed):
            return False
    return True


def _volatile_only_canonical_diff(differing: list[str]) -> bool:
    return _metadata_only_canonical_diff(differing)


def _differing_only_queued_display_key_change(session: dict[str, Any], differing: list[str]) -> bool:
    try:
        from display_key_startup_save_queue import has_queued_display_key_change

        if not has_queued_display_key_change(session):
            return False
    except ImportError:
        return False
    if not differing:
        return True
    allowed = (
        "display_key",
        "core.display_key",
        "active_song_state.display_key",
        "music_workspace_state.active_song.display_key",
    )
    for path in differing:
        p = str(path)
        if not any(p.endswith(suffix) or p == suffix for suffix in allowed):
            if _volatile_only_canonical_diff([p]):
                continue
            return False
    return True


def set_page_change_origin(session: dict[str, Any], origin: str) -> None:
    text = str(origin or "unknown").strip()
    if text not in _PAGE_CHANGE_ORIGINS:
        text = "unknown"
    session[PAGE_CHANGE_ORIGIN_KEY] = text


def get_page_change_origin(session: dict[str, Any]) -> str:
    return str(session.get(PAGE_CHANGE_ORIGIN_KEY) or "unknown").strip()


_QUEUED_PAGE_CHANGE_KEYS: tuple[str, ...] = (
    "_music_user_navigated_page_this_run",
    "_suite_page_change_write_pending",
    "_suite_page_change_stamp_target",
    "_suite_page_change_save_page",
    "_suite_deferred_page_change_save",
    "requested_page",
    "music_page_change_origin",
)


def _normalize_page_id(page: Any) -> str:
    text = str(page or "").strip()
    if not text:
        return ""
    try:
        from studio_nav_history import STUDIO_PAGE_IDS

        return text if text in STUDIO_PAGE_IDS else ""
    except ImportError:
        return text


def queued_user_page_change_target(session: dict[str, Any]) -> str:
    """Page id the user navigated to while startup suppression may still be armed."""
    for key in _QUEUED_PAGE_CHANGE_KEYS:
        page = _normalize_page_id(session.get(key))
        if page:
            return page
    live = _normalize_page_id(session.get("studio_page"))
    if live and _genuine_queued_user_navigation(session):
        return live
    return ""


def has_queued_user_page_change(session: dict[str, Any]) -> bool:
    if not queued_user_page_change_target(session):
        return False
    return _genuine_queued_user_navigation(session)


def _genuine_queued_user_navigation(session: dict[str, Any]) -> bool:
    if get_page_change_origin(session) == "user_navigation":
        return True
    if str(session.get("_music_user_navigated_page_this_run") or "").strip():
        return True
    if session.get("_suite_page_user_nav"):
        return True
    return False


def _defer_finalize_for_pending_queued_page_change(session: dict[str, Any]) -> bool:
    """Queued user nav must release via force_save — not late finalize with Creative stamped."""
    if not queued_user_page_change_target(session):
        return False
    return _genuine_queued_user_navigation(session)


def snapshot_queued_page_change(session: dict[str, Any]) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    for key in (
        *_QUEUED_PAGE_CHANGE_KEYS,
        "studio_page",
        "_suite_page_user_nav",
        "active_page_source",
    ):
        if key in session:
            snap[key] = session[key]
    nav = session.get("studio_nav_state")
    if isinstance(nav, dict):
        snap["studio_nav_state"] = dict(nav)
    mws = session.get("music_workspace_state")
    if isinstance(mws, dict):
        snap["music_workspace_state"] = dict(mws)
    pws = session.get("practice_workspace_state")
    if isinstance(pws, dict):
        snap["practice_workspace_state"] = dict(pws)
    return snap


def restore_queued_page_change(session: dict[str, Any], snap: dict[str, Any]) -> None:
    if not snap:
        return
    for key, val in snap.items():
        session[key] = val


def _stamp_page_into_canonical_tree(canonical: dict[str, Any], page: str) -> None:
    if not page:
        return
    core = canonical.get("core")
    if isinstance(core, dict):
        core["studio_page"] = page
        core["page"] = page
    nav = canonical.get("studio_nav_state")
    if isinstance(nav, dict):
        nav["studio_page"] = page
        nav["page"] = page
    mws = canonical.get("music_workspace_state")
    if isinstance(mws, dict):
        mws["studio_page"] = page
        mws["page"] = page
    pws = canonical.get("practice_workspace_state")
    if isinstance(pws, dict):
        pws["studio_page"] = page
        pws["page"] = page


def _hydrated_page_id(session: dict[str, Any]) -> str:
    snap = session.get(HYDRATED_PAYLOAD_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        snap = session.get("_suite_last_cloud_fetch_payload")
    if not isinstance(snap, dict):
        return ""
    core = snap.get("core") if isinstance(snap.get("core"), dict) else snap
    if not isinstance(core, dict):
        return ""
    return _normalize_page_id(core.get("studio_page") or core.get("page"))


def _pre_navigation_startup_alignment_satisfied(session: dict[str, Any]) -> bool:
    hydrated_fp = str(session.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    post_fp = str(session.get(POST_RESTORE_CANONICAL_FP_KEY) or "").strip()
    if hydrated_fp and post_fp and hydrated_fp == post_fp:
        return True
    if session.get(STARTUP_FINGERPRINT_MATCHES_KEY) and hydrated_fp and post_fp and hydrated_fp == post_fp:
        return True
    return False


def _canonical_fp_for_startup_release(
    session: dict[str, Any],
    state: dict[str, Any] | None,
    *,
    normalize_page: str = "",
) -> str:
    """Alignment fingerprint with page-bearing paths normalized (queued nav masked for compare)."""
    import hashlib
    import json

    from music_workspace_canonical_fingerprint import canonical_workspace_state_for_fingerprint

    canonical = canonical_workspace_state_for_fingerprint(state if isinstance(state, dict) else {})
    page = _normalize_page_id(normalize_page) or _hydrated_page_id(session)
    if page:
        _stamp_page_into_canonical_tree(canonical, page)
    blob = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def clear_startup_deferred_page_change_saves(session: dict[str, Any]) -> None:
    if has_queued_user_page_change(session):
        session["queued_page_change_preserved"] = True
        return
    session.pop("queued_page_change_preserved", None)
    session.pop("_suite_deferred_page_change_save", None)
    session.pop("_suite_page_change_save_page", None)
    session.pop("_suite_page_change_stamp_target", None)
    session.pop("_suite_page_change_write_pending", None)
    session.pop("_music_build_page_change_target", None)


def arm_startup_suppression(session: dict[str, Any], stage: str) -> None:
    session[STARTUP_SUPPRESSION_ARMED_KEY] = True
    session[STARTUP_SUPPRESSION_ARMED_STAGE_KEY] = str(stage or "unknown")
    session.pop(STARTUP_SUPPRESSION_RELEASED_KEY, None)
    session[STARTUP_RESTORE_IN_PROGRESS_KEY] = True


def record_hydrated_canonical_fingerprint(
    session: dict[str, Any],
    payload: dict[str, Any] | None,
    *,
    stage: str = "hydrate",
) -> str:
    """Capture cloud/disk payload fingerprint at hydration (read-only)."""
    arm_startup_suppression(session, stage)
    fp = _canonical_fp(payload if isinstance(payload, dict) else {})
    session[HYDRATED_CANONICAL_FP_KEY] = fp or "(none)"
    session[HYDRATED_FP_RECORDED_STAGE_KEY] = str(stage or "hydrate")
    if isinstance(payload, dict) and payload:
        try:
            import copy

            session[HYDRATED_PAYLOAD_SNAPSHOT_KEY] = copy.deepcopy(payload)
        except Exception:
            session[HYDRATED_PAYLOAD_SNAPSHOT_KEY] = payload
    try:
        from workspace_revision import workspace_revision_from_blob

        loaded_rev = workspace_revision_from_blob(payload if isinstance(payload, dict) else {})
        try:
            from music_metrics_logical_revision import revision_for_authoritative_hydrate

            loaded_rev = revision_for_authoritative_hydrate(session, payload if isinstance(payload, dict) else {})
        except ImportError:
            pass
        session[STARTUP_REVISION_LOADED_KEY] = loaded_rev
        if loaded_rev > 0:
            try:
                from music_device_applied_revision import (
                    set_device_applied_revision_from_authoritative_hydrate,
                )

                set_device_applied_revision_from_authoritative_hydrate(
                    session,
                    loaded_rev,
                    stage=str(stage or "hydrate"),
                    source="authoritative_network_hydrate",
                    payload=payload if isinstance(payload, dict) else None,
                )
            except ImportError:
                pass
    except ImportError:
        session[STARTUP_REVISION_LOADED_KEY] = 0
    return fp


def _queue_startup_pending_edit(session: dict[str, Any], reason: str) -> None:
    reasons = session.get(STARTUP_PENDING_EDIT_REASONS_KEY)
    if not isinstance(reasons, list):
        reasons = []
    text = str(reason or "").strip()
    if text and text not in reasons:
        reasons.append(text)
    session[STARTUP_PENDING_EDIT_REASONS_KEY] = reasons


def note_startup_pending_edit(session: dict[str, Any], reason: str) -> bool:
    if not session.get(STARTUP_SUPPRESSION_ARMED_KEY) or session.get(STARTUP_SUPPRESSION_RELEASED_KEY):
        return False
    _queue_startup_pending_edit(session, reason)
    return True


def note_first_song_edit_request(session: dict[str, Any], stage: str) -> None:
    if session.get(FIRST_SONG_EDIT_REQUESTED_STAGE_KEY):
        return
    session[FIRST_SONG_EDIT_REQUESTED_STAGE_KEY] = str(stage or "unknown")


def _discard_startup_pending_edits(session: dict[str, Any]) -> None:
    try:
        from display_key_startup_save_queue import has_queued_display_key_change

        if has_queued_display_key_change(session):
            return
    except ImportError:
        pass
    pending = session.get(STARTUP_PENDING_EDIT_REASONS_KEY)
    if isinstance(pending, list) and pending:
        session[STARTUP_PENDING_EDITS_DISCARDED_KEY] = list(pending)
    session.pop(STARTUP_PENDING_EDIT_REASONS_KEY, None)
    try:
        from active_song_state import (
            ACTIVE_SONG_DIRTY_KEY,
            ACTIVE_SONG_LOCAL_EDIT_TS_KEY,
            ACTIVE_SONG_PENDING_SYNC_KEY,
            clear_active_song_local_edit,
        )

        clear_active_song_local_edit(session)
        session.pop(ACTIVE_SONG_PENDING_SYNC_KEY, None)
        session.pop(ACTIVE_SONG_DIRTY_KEY, None)
        session.pop(ACTIVE_SONG_LOCAL_EDIT_TS_KEY, None)
    except ImportError:
        pass
    try:
        from suite_user_persistence import _local_dirty_key

        session[_local_dirty_key("music")] = False
    except ImportError:
        pass


def _apply_queued_page_startup_release(
    session: dict[str, Any],
    *,
    rev_loaded: int,
    stage: str,
) -> None:
    """Release suppression for queued user page_change without discarding the navigation edit."""
    hydrated_fp = str(session.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    post_fp = str(session.get(POST_RESTORE_CANONICAL_FP_KEY) or "").strip() or hydrated_fp
    try:
        from music_egress_strict_save import note_confirmed_cloud_fingerprint

        note_confirmed_cloud_fingerprint(session, post_fp or hydrated_fp)
    except ImportError:
        session["_music_last_confirmed_cloud_fp"] = post_fp or hydrated_fp
    try:
        from workspace_revision import (
            APPLIED_REVISION_KEY,
            CLOUD_REVISION_KEY,
            LAST_CONFIRMED_REVISION_KEY,
            LOCAL_REVISION_KEY,
        )

        session[LAST_CONFIRMED_REVISION_KEY] = rev_loaded
        session[CLOUD_REVISION_KEY] = rev_loaded
        session[APPLIED_REVISION_KEY] = rev_loaded
        session[LOCAL_REVISION_KEY] = rev_loaded
    except ImportError:
        pass
    session.pop("_music_pending_canonical_content_fp", None)
    session[STARTUP_SUPPRESSION_RELEASED_KEY] = True
    session[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
    session[STARTUP_FINGERPRINT_MATCHES_KEY] = True
    session[STARTUP_REVISION_FINAL_KEY] = int(rev_loaded or 0)
    session[STARTUP_WRITE_ALLOWED_REASON_KEY] = "queued_page_change_after_alignment"
    session[RESTORE_FINALIZED_STAGE_KEY] = stage
    session[DIFFERING_CANONICAL_PATHS_KEY] = None
    session.pop(STARTUP_WRITE_SUPPRESSED_KEY, None)
    session.pop(STARTUP_SAVE_SUPPRESSED_KEY, None)
    session.pop(STARTUP_SAVE_SUPPRESSION_REASON_KEY, None)
    session["queued_page_change_preserved"] = True
    try:
        from suite_user_persistence import _local_dirty_key

        session[_local_dirty_key("music")] = True
    except ImportError:
        pass


def _record_startup_revision_invariant_violation(session: dict[str, Any]) -> None:
    loaded = int(session.get(STARTUP_REVISION_LOADED_KEY) or 0)
    final = int(session.get(STARTUP_REVISION_FINAL_KEY) or 0)
    if final == loaded:
        return
    if session.get("_music_page_change_payload_built"):
        return
    session["_startup_release_revision_invariant_violation"] = True
    try:
        from music_page_cloud_durability_trace import record_startup_release_revision_violation

        record_startup_release_revision_violation(session)
    except ImportError:
        pass


def _release_startup_for_queued_page_change(
    st: Any,
    *,
    queued: str,
    suppress_reason: str = "",
) -> bool:
    """Confirm pre-hydration alignment (page-normalized) and release suppression."""
    ss = st.session_state
    rev_loaded = int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0)
    hydrated_page = _hydrated_page_id(ss)
    hydrated_fp = str(ss.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    post_fp = str(ss.get(POST_RESTORE_CANONICAL_FP_KEY) or "").strip()
    pre_aligned = _pre_navigation_startup_alignment_satisfied(ss)

    try:
        from music_queued_page_startup_release_trace import record_release_function_body

        record_release_function_body(
            ss,
            phase="entry",
            detail={
                "queued_release_function_called": True,
                "queued_release_pre_aligned_detected": pre_aligned,
                "queued_release_pre_aligned_hydrated_fp": hydrated_fp,
                "queued_release_pre_aligned_post_fp": post_fp,
                "queued_release_queued_target": queued,
            },
        )
    except ImportError:
        pass

    if pre_aligned:
        try:
            from music_queued_page_startup_release_trace import record_release_function_body

            record_release_function_body(
                ss,
                phase="pre_aligned_shortcut",
                detail={
                    "queued_release_branch_selected": "pre_aligned_shortcut",
                    "queued_release_apply_queued_release_called": True,
                },
            )
        except ImportError:
            pass
        _apply_queued_page_startup_release(ss, rev_loaded=rev_loaded, stage="page_change_release_pre_aligned")
        try:
            from music_queued_page_startup_release_trace import record_release_function_body

            record_release_function_body(
                ss,
                phase="pre_aligned_done",
                detail={"queued_release_result": True},
            )
        except ImportError:
            pass
        return True

    snapshot = ss.get(HYDRATED_PAYLOAD_SNAPSHOT_KEY)
    hydrated_side = snapshot if isinstance(snapshot, dict) else ss.get("_suite_last_cloud_fetch_payload")
    hydrated_side = hydrated_side if isinstance(hydrated_side, dict) else {}

    post_state: dict[str, Any] | None = None
    try:
        from music_persistent_state import build_music_disk_state

        post_state = build_music_disk_state(st)
    except Exception:
        post_state = {}

    normalize_page = hydrated_page or "backing"
    release_hydrated_fp = _canonical_fp_for_startup_release(
        ss, hydrated_side, normalize_page=normalize_page
    )
    release_post_fp = _canonical_fp_for_startup_release(
        ss, post_state if isinstance(post_state, dict) else {}, normalize_page=normalize_page
    )
    try:
        from music_workspace_canonical_fingerprint import diff_canonical_paths

        differing = diff_canonical_paths(hydrated_side, post_state if isinstance(post_state, dict) else {})
    except ImportError:
        differing = []

    page_only = _differing_only_queued_page_navigation(
        differing, hydrated_page=normalize_page, queued_page=queued
    )
    matches = bool(release_hydrated_fp and release_post_fp and release_hydrated_fp == release_post_fp)
    if not matches and page_only:
        matches = True
    if not matches and _metadata_only_canonical_diff(differing):
        matches = True

    try:
        from music_queued_page_startup_release_trace import record_release_function_body

        record_release_function_body(
            ss,
            phase="normalized_compare",
            detail={
                "queued_release_branch_selected": "normalized_fingerprint_compare",
                "queued_release_normalized_hydrated_fp": release_hydrated_fp,
                "queued_release_normalized_post_fp": release_post_fp,
                "queued_release_differing_paths_after_mask": differing,
                "queued_release_page_only_diff": page_only,
                "queued_release_matches": matches,
            },
        )
    except ImportError:
        pass

    ss[STARTUP_REVISION_FINAL_KEY] = rev_loaded
    if not matches:
        ss[STARTUP_FINGERPRINT_MATCHES_KEY] = False
        ss[DIFFERING_CANONICAL_PATHS_KEY] = differing or None
        ss["queued_page_change_release_blocked_reason"] = suppress_reason or "startup_page_mismatch"
        try:
            from music_page_cloud_durability_trace import record_startup_release_blocked

            record_startup_release_blocked(
                ss,
                differing_paths=differing,
                suppress_reason=suppress_reason,
            )
        except ImportError:
            pass
        _record_startup_revision_invariant_violation(ss)
        return False

    _apply_queued_page_startup_release(ss, rev_loaded=rev_loaded, stage="page_change_release")
    try:
        from music_queued_page_startup_release_trace import record_release_function_body

        record_release_function_body(
            ss,
            phase="normalized_release_done",
            detail={
                "queued_release_apply_queued_release_called": True,
                "queued_release_result": True,
            },
        )
    except ImportError:
        pass
    return True


def _apply_confirmed_startup_alignment(
    session: dict[str, Any],
    *,
    hydrated_fp: str,
    post_fp: str,
    rev_loaded: int,
) -> None:
    try:
        from music_egress_strict_save import note_confirmed_cloud_fingerprint

        note_confirmed_cloud_fingerprint(session, post_fp or hydrated_fp)
    except ImportError:
        session["_music_last_confirmed_cloud_fp"] = post_fp or hydrated_fp
    try:
        from workspace_revision import (
            APPLIED_REVISION_KEY,
            CLOUD_REVISION_KEY,
            LAST_CONFIRMED_REVISION_KEY,
            LOCAL_REVISION_KEY,
        )

        session[LAST_CONFIRMED_REVISION_KEY] = rev_loaded
        session[CLOUD_REVISION_KEY] = rev_loaded
        session[APPLIED_REVISION_KEY] = rev_loaded
        session[LOCAL_REVISION_KEY] = rev_loaded
    except ImportError:
        pass
    session.pop("_music_pending_canonical_content_fp", None)
    session.pop("_music_reserved_write_revision", None)
    session.pop("_music_pending_save_revision", None)
    _discard_startup_pending_edits(session)
    clear_startup_deferred_page_change_saves(session)


def _record_alignment_diagnostics(
    session: dict[str, Any],
    *,
    hydrated_fp: str,
    post_fp: str,
    matches: bool,
    revision_final: int,
    differing_paths: list[str],
    stage: str,
) -> None:
    session[HYDRATED_CANONICAL_FP_KEY] = hydrated_fp or session.get(HYDRATED_CANONICAL_FP_KEY) or "(none)"
    session[POST_RESTORE_CANONICAL_FP_KEY] = post_fp or "(none)"
    session[STARTUP_FINGERPRINT_MATCHES_KEY] = bool(matches)
    session[STARTUP_REVISION_FINAL_KEY] = int(revision_final or 0)
    session[RESTORE_FINALIZED_STAGE_KEY] = stage
    session[DIFFERING_CANONICAL_PATHS_KEY] = differing_paths or None


def finalize_startup_canonical_alignment(st: Any, *, stage: str = "early_finalize") -> bool:
    """Compare hydrated vs built state; release suppression when canonical content matches."""
    ss = st.session_state
    if _defer_finalize_for_pending_queued_page_change(ss) or _defer_finalize_for_pending_queued_display_key_change(ss):
        try:
            from music_queued_page_startup_release_trace import record_finalize_fallback_blocked

            record_finalize_fallback_blocked(ss, stage=stage)
        except ImportError:
            pass
        rev_loaded = int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0)
        ss[STARTUP_REVISION_FINAL_KEY] = rev_loaded
        if _pre_navigation_startup_alignment_satisfied(ss):
            ss[STARTUP_FINGERPRINT_MATCHES_KEY] = True
        try:
            from display_key_startup_save_queue import (
                flush_queued_display_key_change_once,
                has_queued_display_key_change,
            )

            if has_queued_display_key_change(ss):
                _apply_queued_display_key_startup_release(ss, stage=f"{stage}:queued_display_key")
                flush_queued_display_key_change_once(st)
        except ImportError:
            pass
        return bool(ss.get(STARTUP_FINGERPRINT_MATCHES_KEY))

    _maybe_record_finalize_after_dedicated_release(ss, stage=stage)
    snapshot = ss.get(HYDRATED_PAYLOAD_SNAPSHOT_KEY)
    payload = snapshot if isinstance(snapshot, dict) else ss.get("_suite_last_cloud_fetch_payload")
    hydrated_side = payload if isinstance(payload, dict) else {}
    hydrated_fp = str(ss.get(HYDRATED_CANONICAL_FP_KEY) or "").strip()
    if not hydrated_fp or hydrated_fp == "(none)":
        hydrated_fp = _canonical_fp(hydrated_side)
        ss[HYDRATED_CANONICAL_FP_KEY] = hydrated_fp or "(none)"

    try:
        from music_startup_canonical_align import align_authoritative_canonical_from_hydrated
        from display_key_startup_save_queue import has_queued_display_key_change

        if not has_queued_display_key_change(ss):
            align_authoritative_canonical_from_hydrated(ss, hydrated_side or payload)
    except ImportError:
        try:
            from music_startup_canonical_align import align_authoritative_canonical_from_hydrated

            align_authoritative_canonical_from_hydrated(ss, hydrated_side or payload)
        except ImportError:
            pass

    post_state: dict[str, Any] | None = None
    try:
        from music_persistent_state import build_music_disk_state

        post_state = build_music_disk_state(st)
    except Exception:
        post_state = None

    post_fp = _canonical_fp(post_state)
    hydrated_fp = _canonical_fp(hydrated_side)
    queued_page = queued_user_page_change_target(ss)
    hydrated_page = _hydrated_page_id(ss)
    release_hydrated_fp = _canonical_fp_for_startup_release(
        ss, hydrated_side, normalize_page=hydrated_page
    )
    release_post_fp = _canonical_fp_for_startup_release(
        ss, post_state if isinstance(post_state, dict) else {}, normalize_page=hydrated_page
    )
    try:
        from music_workspace_canonical_fingerprint import diff_canonical_paths

        differing = diff_canonical_paths(hydrated_side, post_state if isinstance(post_state, dict) else {})
    except ImportError:
        differing = []

    matches = bool(hydrated_fp and post_fp and hydrated_fp == post_fp)
    if not matches and queued_page and get_page_change_origin(ss) == "user_navigation":
        matches = bool(
            release_hydrated_fp
            and release_post_fp
            and release_hydrated_fp == release_post_fp
        )
        if matches:
            post_fp = release_post_fp
            hydrated_fp = release_hydrated_fp

    if not matches and queued_page and get_page_change_origin(ss) == "user_navigation":
        if _differing_only_queued_page_navigation(
            differing, hydrated_page=hydrated_page or "backing", queued_page=queued_page
        ):
            matches = True
            post_fp = release_post_fp or post_fp
            hydrated_fp = release_hydrated_fp or hydrated_fp
        elif _metadata_only_canonical_diff(differing):
            matches = True
            post_fp = release_post_fp or post_fp
            hydrated_fp = release_hydrated_fp or hydrated_fp

    if not matches and _metadata_only_canonical_diff(differing):
        matches = True

    if not matches and _volatile_only_canonical_diff(differing):
        matches = True
        try:
            from display_key_startup_save_queue import record_startup_release_diag

            record_startup_release_diag(
                ss,
                release_stage=str(stage),
                restore_finalized=bool(ss.get(RESTORE_FINALIZED_STAGE_KEY)),
                fingerprint_semantic_match=True,
                ignored_volatile_paths=list(differing),
            )
        except ImportError:
            pass

    if not matches and _differing_only_queued_display_key_change(ss, differing):
        matches = True

    rev_loaded = int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0)
    rev_final = rev_loaded
    try:
        from workspace_revision import workspace_revision_from_blob

        if isinstance(payload, dict):
            rev_loaded = workspace_revision_from_blob(payload)
        if matches:
            rev_final = rev_loaded
        elif queued_page and get_page_change_origin(ss) == "user_navigation":
            rev_final = rev_loaded
        else:
            rev_final = workspace_revision_from_blob(post_state if isinstance(post_state, dict) else payload)
        ss[STARTUP_REVISION_LOADED_KEY] = rev_loaded
    except ImportError:
        pass

    _record_alignment_diagnostics(
        ss,
        hydrated_fp=hydrated_fp,
        post_fp=post_fp,
        matches=matches,
        revision_final=rev_final,
        differing_paths=differing,
        stage=stage,
    )
    if not matches and queued_page and get_page_change_origin(ss) == "user_navigation":
        _record_startup_revision_invariant_violation(ss)

    if matches:
        try:
            from display_key_startup_save_queue import has_queued_display_key_change

            queued_dk = has_queued_display_key_change(ss)
        except ImportError:
            queued_dk = False
        if queued_page and get_page_change_origin(ss) == "user_navigation":
            _apply_queued_page_startup_release(ss, rev_loaded=rev_loaded, stage=stage)
        elif queued_dk:
            _apply_queued_display_key_startup_release(ss, stage=stage)
        else:
            _apply_confirmed_startup_alignment(
                ss,
                hydrated_fp=hydrated_fp,
                post_fp=post_fp,
                rev_loaded=rev_loaded,
            )
        ss[STARTUP_SUPPRESSION_RELEASED_KEY] = True
        ss[STARTUP_WRITE_ALLOWED_REASON_KEY] = "canonical_match_after_restore"
        ss[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
    else:
        ss[STARTUP_WRITE_ALLOWED_REASON_KEY] = None

    try:
        from display_key_startup_save_queue import (
            flush_queued_display_key_change_once,
            has_queued_display_key_change,
        )

        if has_queued_display_key_change(ss):
            if not ss.get(STARTUP_SUPPRESSION_RELEASED_KEY):
                _apply_queued_display_key_startup_release(ss, stage=f"{stage}:queued_flush")
            flush_queued_display_key_change_once(st)
    except ImportError:
        pass

    return matches


def attempt_release_startup_for_queued_page_change(st: Any, *, suppress_reason: str = "") -> bool:
    """
    Try startup canonical alignment + suppression release while preserving queued user page_change.
    Returns True when page_change save may proceed.
    """
    ss = st.session_state
    queued = queued_user_page_change_target(ss)
    if not queued or not _genuine_queued_user_navigation(ss):
        ss["queued_page_change_preserved"] = False
        ss["queued_page_change_flushed"] = False
        try:
            from music_queued_page_startup_release_trace import record_attempt_release_result

            record_attempt_release_result(
                ss,
                return_value=False,
                branch_selected="abort_not_genuine_user_nav",
                next_function="none",
            )
        except ImportError:
            pass
        _maybe_record_hotfix_not_executed(ss, queued=queued)
        return False

    if get_page_change_origin(ss) != "user_navigation" and _genuine_queued_user_navigation(ss):
        set_page_change_origin(ss, "user_navigation")

    try:
        from music_queued_page_startup_release_trace import (
            record_attempt_release_dispatch,
        )

        record_attempt_release_dispatch(
            ss,
            attempt_fn=attempt_release_startup_for_queued_page_change,
            release_fn=_release_startup_for_queued_page_change,
        )
    except ImportError:
        pass

    snap = snapshot_queued_page_change(ss)
    ss["queued_page_change_preserved"] = True

    armed = bool(ss.get(STARTUP_SUPPRESSION_ARMED_KEY)) and not ss.get(STARTUP_SUPPRESSION_RELEASED_KEY)
    released = bool(ss.get(STARTUP_SUPPRESSION_RELEASED_KEY))
    branch = "already_released"
    if armed or ss.get(STARTUP_RESTORE_IN_PROGRESS_KEY):
        released = _release_startup_for_queued_page_change(
            st, queued=queued, suppress_reason=suppress_reason
        )
        branch = "dedicated_release_function"
    elif _pre_navigation_startup_alignment_satisfied(ss):
        _apply_queued_page_startup_release(
            ss,
            rev_loaded=int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0),
            stage="page_change_release_pre_aligned_no_arm",
        )
        released = True
        branch = "pre_aligned_no_arm"

    restore_queued_page_change(ss, snap)
    try:
        from music_persistent_state import synchronize_page_bearing_state_for_save

        synchronize_page_bearing_state_for_save(ss, queued)
    except ImportError:
        pass

    if not released or not ss.get(STARTUP_SUPPRESSION_RELEASED_KEY):
        ss["queued_page_change_flushed"] = False
        try:
            from music_queued_page_startup_release_trace import record_attempt_release_result

            record_attempt_release_result(
                ss,
                return_value=False,
                branch_selected=branch,
                next_function="force_save_early_return",
            )
        except ImportError:
            pass
        _maybe_record_hotfix_not_executed(ss, queued=queued)
        return False

    suppress, _why = should_suppress_music_workspace_save(ss, "page_change")
    if suppress:
        ss["queued_page_change_flushed"] = False
        try:
            from music_queued_page_startup_release_trace import record_attempt_release_result

            record_attempt_release_result(
                ss,
                return_value=False,
                branch_selected=f"{branch}:post_release_still_suppressed",
                next_function="force_save_early_return",
            )
        except ImportError:
            pass
        return False

    ss["queued_page_change_flushed"] = True
    ss[STARTUP_RESTORE_IN_PROGRESS_KEY] = False
    try:
        from music_queued_page_startup_release_trace import record_attempt_release_result

        record_attempt_release_result(
            ss,
            return_value=True,
            branch_selected=branch,
            next_function="force_music_workspace_save_payload_build",
        )
    except ImportError:
        pass
    return True


def _maybe_record_hotfix_not_executed(session: dict[str, Any], *, queued: str) -> None:
    if not queued:
        return
    if not _pre_navigation_startup_alignment_satisfied(session):
        return
    if session.get(STARTUP_SUPPRESSION_RELEASED_KEY):
        return
    try:
        from music_page_cloud_durability_trace import record_queued_page_release_hotfix_violation

        record_queued_page_release_hotfix_violation(
            session,
            code="QUEUED_PAGE_RELEASE_HOTFIX_NOT_EXECUTED",
            detail={
                "queued": queued,
                "startup_fingerprint_matches": session.get(STARTUP_FINGERPRINT_MATCHES_KEY),
            },
        )
    except ImportError:
        pass


def run_late_startup_restore_guard(st: Any) -> bool:
    ss = st.session_state
    if _defer_finalize_for_pending_queued_page_change(ss) or _defer_finalize_for_pending_queued_display_key_change(ss):
        try:
            from music_queued_page_startup_release_trace import record_finalize_fallback_blocked

            record_finalize_fallback_blocked(ss, stage="late_end_of_run")
        except ImportError:
            pass
        rev_loaded = int(ss.get(STARTUP_REVISION_LOADED_KEY) or 0)
        ss[STARTUP_REVISION_FINAL_KEY] = rev_loaded
        try:
            from display_key_startup_save_queue import (
                flush_queued_display_key_change_once,
                has_queued_display_key_change,
            )

            if has_queued_display_key_change(ss):
                _apply_queued_display_key_startup_release(ss, stage="late_end_of_run:queued_display_key")
                flush_queued_display_key_change_once(st)
        except ImportError:
            pass
        return bool(ss.get(STARTUP_FINGERPRINT_MATCHES_KEY))
    if not ss.get(STARTUP_SUPPRESSION_ARMED_KEY):
        return bool(ss.get(STARTUP_FINGERPRINT_MATCHES_KEY))
    _maybe_record_finalize_after_dedicated_release(ss, stage="late_end_of_run")
    return finalize_startup_canonical_alignment(st, stage="late_end_of_run")


def _maybe_record_finalize_after_dedicated_release(session: dict[str, Any], *, stage: str) -> None:
    trace = session.get("_music_queued_page_release_trace")
    if not isinstance(trace, dict):
        return
    if not trace.get("queued_release_return_value"):
        return
    try:
        from music_page_cloud_durability_trace import record_queued_page_release_hotfix_violation

        record_queued_page_release_hotfix_violation(
            session,
            code="QUEUED_PAGE_RELEASE_FELL_BACK_TO_OLD_FINALIZE",
            detail={"stage": stage, "trace": trace},
        )
    except ImportError:
        pass


def record_startup_save_suppressed(session: dict[str, Any], reason: str) -> None:
    session[STARTUP_WRITE_SUPPRESSED_KEY] = True
    session[STARTUP_SAVE_SUPPRESSED_KEY] = True
    session[STARTUP_SAVE_SUPPRESSION_REASON_KEY] = reason


def should_suppress_music_workspace_save(session: dict[str, Any], save_reason: str) -> tuple[bool, str]:
    reason = str(save_reason or "").strip() or "autosave"
    if reason in _EXPLICIT_STARTUP_SAVE_REASONS:
        session[STARTUP_WRITE_ALLOWED_REASON_KEY] = reason
        return False, ""

    if reason == "page_change":
        armed = bool(session.get(STARTUP_SUPPRESSION_ARMED_KEY)) and not session.get(
            STARTUP_SUPPRESSION_RELEASED_KEY
        )
        if armed:
            return True, "startup_suppression_armed_page_change"
        if session.get(STARTUP_RESTORE_IN_PROGRESS_KEY):
            return True, "startup_restore_in_progress_page_change"
        origin = get_page_change_origin(session)
        if origin != "user_navigation":
            return True, f"page_change_origin:{origin}"
        if not session.get(STARTUP_SUPPRESSION_RELEASED_KEY):
            return True, "startup_suppression_not_released"

    if reason in ("song_edit", *tuple(_RESTORE_BLOCKED_SAVE_REASONS)):
        note_first_song_edit_request(session, f"save_requested:{reason}")

    armed = bool(session.get(STARTUP_SUPPRESSION_ARMED_KEY)) and not session.get(STARTUP_SUPPRESSION_RELEASED_KEY)
    if armed and reason in _RESTORE_BLOCKED_SAVE_REASONS.union({"song_edit"}):
        return True, "startup_suppression_armed"

    if session.get(STARTUP_RESTORE_IN_PROGRESS_KEY) and reason in _RESTORE_BLOCKED_SAVE_REASONS.union({"song_edit"}):
        return True, "startup_restore_in_progress"

    if session.get(STARTUP_FINGERPRINT_MATCHES_KEY) and reason in _RESTORE_BLOCKED_SAVE_REASONS.union({"song_edit"}):
        if reason == "display_key_change":
            try:
                from practice_setup_globals import DISPLAY_KEY_CHANGE_SOURCE_KEY

                if str(session.get(DISPLAY_KEY_CHANGE_SOURCE_KEY) or "").strip() == "sidebar_on_change":
                    return False, ""
            except ImportError:
                pass
        return True, "startup_canonical_unchanged"

    return False, ""


def gate_music_workspace_save_at_startup(session: dict[str, Any], save_reason: str) -> tuple[bool, str]:
    suppress, why = should_suppress_music_workspace_save(session, save_reason)
    if suppress:
        note_startup_pending_edit(session, f"blocked:{save_reason}:{why}")
        record_startup_save_suppressed(session, why)
    return suppress, why


def collect_startup_save_suppression_diagnostics(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "startup_restore_in_progress": session.get(STARTUP_RESTORE_IN_PROGRESS_KEY),
        "startup_suppression_armed": session.get(STARTUP_SUPPRESSION_ARMED_KEY),
        "startup_suppression_armed_stage": session.get(STARTUP_SUPPRESSION_ARMED_STAGE_KEY),
        "startup_suppression_released": session.get(STARTUP_SUPPRESSION_RELEASED_KEY),
        "hydrated_fingerprint_recorded_stage": session.get(HYDRATED_FP_RECORDED_STAGE_KEY),
        "hydrated_canonical_fingerprint": session.get(HYDRATED_CANONICAL_FP_KEY),
        "post_restore_canonical_fingerprint": session.get(POST_RESTORE_CANONICAL_FP_KEY),
        "startup_fingerprint_matches": session.get(STARTUP_FINGERPRINT_MATCHES_KEY),
        "differing_canonical_paths": session.get(DIFFERING_CANONICAL_PATHS_KEY),
        "first_song_edit_requested_stage": session.get(FIRST_SONG_EDIT_REQUESTED_STAGE_KEY),
        "startup_pending_edit_reasons": session.get(STARTUP_PENDING_EDIT_REASONS_KEY),
        "startup_pending_edits_discarded": session.get(STARTUP_PENDING_EDITS_DISCARDED_KEY),
        "restore_finalized_stage": session.get(RESTORE_FINALIZED_STAGE_KEY),
        "startup_write_suppressed": session.get(STARTUP_WRITE_SUPPRESSED_KEY),
        "startup_write_allowed_reason": session.get(STARTUP_WRITE_ALLOWED_REASON_KEY),
        "startup_save_suppressed": session.get(STARTUP_SAVE_SUPPRESSED_KEY),
        "startup_save_suppression_reason": session.get(STARTUP_SAVE_SUPPRESSION_REASON_KEY),
        "startup_revision_loaded": session.get(STARTUP_REVISION_LOADED_KEY),
        "startup_revision_final": session.get(STARTUP_REVISION_FINAL_KEY),
        "music_page_change_origin": session.get(PAGE_CHANGE_ORIGIN_KEY),
        "queued_page_change_target": queued_user_page_change_target(session) or None,
        "queued_page_change_preserved": session.get("queued_page_change_preserved"),
        "queued_page_change_flushed": session.get("queued_page_change_flushed"),
    }


__all__ = [
    "STARTUP_RESTORE_IN_PROGRESS_KEY",
    "STARTUP_SUPPRESSION_ARMED_KEY",
    "arm_startup_suppression",
    "attempt_release_startup_for_queued_page_change",
    "finalize_startup_canonical_alignment",
    "run_late_startup_restore_guard",
    "gate_music_workspace_save_at_startup",
    "collect_startup_save_suppression_diagnostics",
    "note_startup_pending_edit",
    "record_hydrated_canonical_fingerprint",
    "record_startup_save_suppressed",
    "should_suppress_music_workspace_save",
    "set_page_change_origin",
    "get_page_change_origin",
    "has_queued_user_page_change",
    "queued_user_page_change_target",
    "clear_startup_deferred_page_change_saves",
    "PAGE_CHANGE_ORIGIN_KEY",
]
