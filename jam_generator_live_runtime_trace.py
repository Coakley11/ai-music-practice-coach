"""Read-only ?dev=1 trace for Jam Session Generator coherence failures (§N live acceptance).

Captures one consolidated table: workflow pointer → blob → artifact → UI projections →
coherence resolver → backing handoff. Does not mutate musical state.
"""

from __future__ import annotations

import copy
from typing import Any

JAM_GENERATOR_LIVE_TRACE_KEY = "_jam_generator_live_runtime_trace"
JAM_BACKING_HANDOFF_TRACE_KEY = "_jam_backing_handoff_live_trace"
JAM_SIDEBAR_KEY_TRACE_KEY = "_jam_sidebar_practice_key_trace"

_GENERATED_OWNER = "jam_session_generator"


def _progression_head(section_map: dict[str, list[str]] | None, n: int = 6) -> list[str]:
    if not isinstance(section_map, dict):
        return []
    flat: list[str] = []
    for chords in section_map.values():
        if isinstance(chords, list):
            flat.extend(str(c).strip() for c in chords if str(c).strip())
    return flat[:n]


def _jam_flat_head(jam: dict[str, Any] | None, n: int = 6) -> list[str]:
    if not isinstance(jam, dict):
        return []
    sections = jam.get("sections")
    if not isinstance(sections, dict):
        return []
    return _progression_head(sections, n=n)


def _widget_value(session: dict[str, Any], key: str) -> Any:
    try:
        from session_widget_safe import read_widget_bound_value

        return read_widget_bound_value(session, key)
    except ImportError:
        return session.get(key)


def _blob_for_jam_owner(session: dict[str, Any]) -> tuple[Any | None, Any | None]:
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == _GENERATED_OWNER:
            blob = get_workflow_blob(session, _GENERATED_OWNER, str(ptr.workflow_session_id or ""))
            return ptr, blob
        if ptr:
            return ptr, get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    except ImportError:
        pass
    return None, None


def _artifact_snapshot(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(f"_generated_artifact_last_{_GENERATED_OWNER}")
    return dict(raw) if isinstance(raw, dict) else None


def record_jam_pre_generate_trace(session: dict[str, Any], *, token: str) -> None:
    """Capture jam key surfaces immediately before resolve_generated_concert_key_for_owner (question A)."""
    live_concert = ""
    try:
        from creative_session_state import _live_jam_session_fields

        _style, live_concert, _bpm, _mood = _live_jam_session_fields(session)
    except ImportError:
        pass
    pending_jam = None
    try:
        from session_widget_safe import PENDING_IMPROV_JAM_KEY

        pending_jam = session.get(PENDING_IMPROV_JAM_KEY)
    except ImportError:
        pending_jam = session.get("_pending_improv_jam_key")
    row = {
        "phase": "pre_generate_consume",
        "request_token": token,
        "improv_jam_key_widget": _widget_value(session, "improv_jam_key"),
        "improv_jam_key_session": str(session.get("improv_jam_key") or ""),
        "pending_improv_jam_key": pending_jam,
        "_live_jam_session_fields_concert": live_concert,
        "display_key": str(session.get("display_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
    }
    bucket = session.get(JAM_GENERATOR_LIVE_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append(row)
    session[JAM_GENERATOR_LIVE_TRACE_KEY] = bucket[-24:]


def record_jam_post_generate_trace(
    session: dict[str, Any],
    *,
    key_c: str,
    owner: str,
    token: str,
) -> None:
    """Called immediately after jam_session_generator consume — seals generate-time inputs."""
    jam = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else {}
    ptr, blob = _blob_for_jam_owner(session)
    row = {
        "phase": "post_generate_consume",
        "owner": owner,
        "request_token": token,
        "resolve_generated_concert_key_for_owner": str(key_c or ""),
        "key_c_passed_to_generate_jam_session": str(key_c or ""),
        "improv_jam_key_session": str(session.get("improv_jam_key") or ""),
        "improv_jam_key_widget": _widget_value(session, "improv_jam_key"),
        "jam_object_key": str(jam.get("key") or ""),
        "jam_prompt_head": str(jam.get("prompt") or "")[:160],
        "jam_progression_head": _jam_flat_head(jam),
        "blob_practice_tonic": str(getattr(getattr(blob, "keys", None), "practice_tonic", "") or "") if blob else "",
        "blob_original_tonic": str(getattr(getattr(blob, "keys", None), "original_tonic", "") or "") if blob else "",
        "blob_section_head": _progression_head(getattr(blob, "section_map", None) if blob else None),
        "active_pointer_owner": str(getattr(ptr, "workflow_owner", "") or "") if ptr else "",
        "active_pointer_sid": str(getattr(ptr, "workflow_session_id", "") or "")[:36] if ptr else "",
        "display_key": str(session.get("display_key") or ""),
        "concert_key": str(session.get("concert_key") or ""),
        "artifact_progression_head": _progression_head(
            (_artifact_snapshot(session) or {}).get("section_map")
            if isinstance((_artifact_snapshot(session) or {}).get("section_map"), dict)
            else None
        ),
    }
    bucket = session.get(JAM_GENERATOR_LIVE_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append(row)
    session[JAM_GENERATOR_LIVE_TRACE_KEY] = bucket[-24:]
    refresh_jam_generator_live_trace_table(session)


def append_jam_backing_handoff_trace(session: dict[str, Any], phase: str, **fields: Any) -> None:
    bucket = session.get(JAM_BACKING_HANDOFF_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **fields})
    session[JAM_BACKING_HANDOFF_TRACE_KEY] = bucket[-32:]
    refresh_jam_generator_live_trace_table(session)


def append_jam_sidebar_key_trace(session: dict[str, Any], phase: str, **fields: Any) -> None:
    bucket = session.get(JAM_SIDEBAR_KEY_TRACE_KEY)
    if not isinstance(bucket, list):
        bucket = []
    bucket.append({"phase": phase, **fields})
    session[JAM_SIDEBAR_KEY_TRACE_KEY] = bucket[-24:]
    refresh_jam_generator_live_trace_table(session)


def _coherence_block_summary(session: dict[str, Any]) -> dict[str, Any]:
    block = session.get("_musical_context_coherence_handoff_block")
    if not isinstance(block, dict):
        block = {}
    diag = session.get("_musical_context_coherence_diag")
    if not isinstance(diag, dict):
        diag = {}
    violations = list(diag.get("violations") or [])
    untransposed = any(
        "UNTRANSPOSED_GENERATED_ARTIFACT" in str(v) for v in violations
    ) or any("UNTRANSPOSED_GENERATED_ARTIFACT" in str(v) for v in (block.get("violations") or []))
    return {
        "coherence_blocked": bool(block.get("blocked")),
        "untransposed_generated_artifact_fired": untransposed,
        "violations": violations,
        "block_payload": block if block else None,
        "coherent_context_summary": diag.get("coherent_context_summary"),
    }


def refresh_jam_generator_live_trace_table(session: dict[str, Any]) -> dict[str, Any]:
    """Rebuild consolidated trace table from current session (read-only)."""
    try:
        from musical_context_coherence import run_musical_context_coherence_checks, resolve_coherent_musical_context
        from dataclasses import asdict

        run_musical_context_coherence_checks(session)
        coherent = resolve_coherent_musical_context(session)
        coherent_dict = asdict(coherent) if coherent is not None else None
        if coherent_dict and isinstance(coherent_dict.get("section_map"), dict):
            coherent_dict["progression_head"] = _progression_head(coherent_dict["section_map"])
    except ImportError:
        coherent_dict = None

    ptr, blob = _blob_for_jam_owner(session)
    jam_owner_ptr = None
    jam_blob = None
    try:
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        ap = get_active_workflow_pointer(session)
        if ap:
            jam_owner_ptr = ap.to_dict() if hasattr(ap, "to_dict") else {"workflow_owner": ap.workflow_owner}
            if ap.workflow_owner == _GENERATED_OWNER:
                jam_blob = get_workflow_blob(session, _GENERATED_OWNER, str(ap.workflow_session_id or ""))
    except ImportError:
        ap = ptr

    jam = session.get("improv_jam_session") if isinstance(session.get("improv_jam_session"), dict) else {}
    artifact = _artifact_snapshot(session)
    staging = None
    try:
        from creative_session_state import JAM_CAPTURE_STAGING_KEY

        staging = session.get(JAM_CAPTURE_STAGING_KEY)
    except ImportError:
        staging = session.get("_jam_capture_staging")

    blob_keys: dict[str, Any] = {}
    blob_section_map: dict[str, list[str]] = {}
    blob_meta: dict[str, Any] = {}
    target_blob = jam_blob if jam_blob is not None else blob
    if target_blob is not None:
        k = getattr(target_blob, "keys", None)
        blob_keys = {
            "practice_tonic": str(getattr(k, "practice_tonic", "") or ""),
            "practice_mode": str(getattr(k, "practice_mode", "") or ""),
            "original_tonic": str(getattr(k, "original_tonic", "") or ""),
            "original_mode": str(getattr(k, "original_mode", "") or ""),
            "key_owner": str(getattr(k, "key_owner", "") or ""),
        }
        sm = getattr(target_blob, "section_map", None)
        if isinstance(sm, dict):
            blob_section_map = copy.deepcopy(sm)
        blob_meta = {
            "workflow_session_id": str(getattr(target_blob, "workflow_session_id", "") or ""),
            "context_revision": getattr(target_blob, "context_revision", None),
            "artifact_fingerprint": str(getattr(target_blob, "artifact_fingerprint", "") or "")[:24],
            "style": str(getattr(target_blob, "style", "") or ""),
            "mood": str(getattr(target_blob, "mood", "") or ""),
            "selected_section": str(getattr(target_blob, "selected_section", "") or ""),
            "selected_chord_symbol": str(getattr(target_blob, "selected_chord_symbol", "") or ""),
        }

    try:
        from music_theory import key_center_token

        canonical_token = key_center_token(blob_keys.get("practice_tonic") or "C", blob_keys.get("practice_mode") or "major")
    except ImportError:
        canonical_token = blob_keys.get("practice_tonic") or ""

    try:
        from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY, generated_jam_owns_practice_key

        jam_key_ownership_active = bool(generated_jam_owns_practice_key(session))
        gen_ctx = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
    except ImportError:
        jam_key_ownership_active = bool(session.get("_generated_jam_key_owner_active"))
        gen_ctx = session.get("_generated_jam_key_context")

    table = {
        "active_workflow": {
            "pointer": jam_owner_ptr or (ptr.to_dict() if ptr and hasattr(ptr, "to_dict") else None),
            "owner": str(getattr(ptr, "workflow_owner", "") or "") if ptr else "",
            "improv_intelligence_tab": str(session.get("improv_intelligence_tab") or ""),
            "improv_entry_mode": str(session.get("improv_entry_mode") or ""),
            "jam_generator_ownership_active": jam_key_ownership_active,
        },
        "jam_workflow_blob": {
            **blob_keys,
            "canonical_key_token": canonical_token,
            "section_map": blob_section_map,
            "progression_head": _progression_head(blob_section_map),
            **blob_meta,
        },
        "generated_artifact": {
            "improv_jam_session_key": str(jam.get("key") or ""),
            "improv_jam_session_prompt": str(jam.get("prompt") or ""),
            "improv_jam_session_sections": copy.deepcopy(jam.get("sections")) if isinstance(jam.get("sections"), dict) else {},
            "improv_jam_session_progression_head": _jam_flat_head(jam),
            "_generated_artifact_last_jam_session_generator": artifact,
            "artifact_practice_tonic": (artifact or {}).get("practice_tonic"),
            "artifact_original_tonic": (artifact or {}).get("original_tonic"),
            "artifact_revision": (artifact or {}).get("artifact_revision"),
            "artifact_fingerprint": str((artifact or {}).get("control_fingerprint") or "")[:24],
            "jam_capture_staging_concert_key": (
                str(staging.get("concert_key") or "") if isinstance(staging, dict) else ""
            ),
        },
        "ui_projections": {
            "improv_jam_key": str(session.get("improv_jam_key") or ""),
            "improv_jam_key_widget": _widget_value(session, "improv_jam_key"),
            "display_key": str(session.get("display_key") or ""),
            "concert_key": str(session.get("concert_key") or ""),
            "pending_display_key": session.get("_pending_display_key"),
            "_generated_jam_key_context": gen_ctx if isinstance(gen_ctx, dict) else None,
            "pending_generated_progression_diag": session.get("_music_pending_generated_progression_diag"),
        },
        "coherence_resolver": {
            "resolve_coherent_musical_context": coherent_dict,
            **_coherence_block_summary(session),
        },
        "backing_handoff": {
            "events": list(session.get(JAM_BACKING_HANDOFF_TRACE_KEY) or [])[-12:],
            "backing_entry_class": session.get("_backing_entry_class"),
            "backing_generic_catalog_entry_flag": session.get("_backing_generic_catalog_entry"),
            "backing_open_intent": session.get("_backing_open_intent"),
            "backing_context_source": _backing_context_source(session),
        },
        "sidebar_key_trace": list(session.get(JAM_SIDEBAR_KEY_TRACE_KEY) or [])[-8:],
        "generate_events": list(session.get(JAM_GENERATOR_LIVE_TRACE_KEY) or [])[-6:],
    }
    table["first_divergence_hypothesis"] = infer_first_divergence(session, table=table)
    session["_jam_generator_live_trace_table"] = table
    return table


def _backing_context_source(session: dict[str, Any]) -> str:
    try:
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        return str(getattr(ctx, "source", "") or "") if ctx is not None else ""
    except ImportError:
        return ""


def infer_first_divergence(session: dict[str, Any], *, table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Heuristic label for where requested key first splits from progression (for live report)."""
    tab = table if isinstance(table, dict) else session.get("_jam_generator_live_trace_table")
    if not isinstance(tab, dict):
        return {"first_fork_stage": "trace_not_built_yet", "first_fork_detail": ""}
    gen_events = tab.get("generate_events") or []
    post = gen_events[-1] if gen_events else {}
    ui = tab.get("ui_projections") or {}
    art = tab.get("generated_artifact") or {}
    blob = tab.get("jam_workflow_blob") or {}
    coh = tab.get("coherence_resolver") or {}

    requested = str(
        post.get("resolve_generated_concert_key_for_owner")
        or post.get("resolve_generated_concert_key")
        or ui.get("improv_jam_key")
        or ""
    ).strip()
    practice_label = str(ui.get("display_key") or ui.get("concert_key") or "").strip()
    jam_key = str(art.get("improv_jam_session_key") or post.get("jam_object_key") or "").strip()
    blob_pt = str(blob.get("practice_tonic") or "").strip()
    head = art.get("improv_jam_session_progression_head") or blob.get("progression_head") or []

    steps: list[str] = []
    fork = ""
    fork_detail = ""

    if post:
        kc = str(post.get("resolve_generated_concert_key") or "")
        jk = str(post.get("jam_object_key") or "")
        if kc and jk and kc != jk:
            fork = "generate_input_vs_jam_object"
            fork_detail = f"resolve_generated_concert_key={kc} but jam.key={jk}"
        elif kc and post.get("jam_progression_head") and kc != practice_label:
            steps.append(f"generate used key_c={kc}")

    if blob_pt and practice_label and blob_pt != practice_label:
        if not fork:
            fork = "ui_projection_after_blob"
            fork_detail = f"blob practice_tonic={blob_pt} vs display/concert={practice_label}"
    elif jam_key and practice_label and jam_key != practice_label:
        if not fork:
            fork = "ui_projection_vs_jam_session"
            fork_detail = f"improv_jam_session.key={jam_key} vs display={practice_label}"

    if blob_pt and head and requested and blob_pt == requested:
        try:
            from musical_context_coherence import infer_major_tonic_from_progression

            center = infer_major_tonic_from_progression(list(head))
            if center and center != blob_pt:
                if not fork:
                    fork = "writer_blob_coherent_at_wrong_key" if blob_pt != requested else "writer_incoherent_blob"
                    fork_detail = f"declared={blob_pt} progression_center≈{center} head={head[:3]}"
        except ImportError:
            pass

    if blob_pt and practice_label and blob_pt == practice_label and head:
        try:
            from musical_context_coherence import infer_major_tonic_from_progression

            center = infer_major_tonic_from_progression(list(head))
            if center and center != practice_label and not fork:
                fork = "coherent_blob_wrong_center_or_stale_template"
                fork_detail = f"blob+labels agree on {practice_label} but progression_center≈{center}"
        except ImportError:
            pass

    untransposed = coh.get("untransposed_generated_artifact_fired")
    return {
        "requested_key_guess": requested or practice_label,
        "practice_ui_key": practice_label,
        "jam_session_key": jam_key,
        "blob_practice_tonic": blob_pt,
        "progression_head": head,
        "first_fork_stage": fork or "none_detected_in_session",
        "first_fork_detail": fork_detail,
        "untransposed_flag_in_diag": untransposed,
        "notes": steps,
    }


def render_jam_generator_live_trace_panel(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled
    except ImportError:
        is_developer_mode_enabled = lambda **_: bool(session.get("dev_mode"))  # type: ignore

    if not (session.get("dev_mode") or is_developer_mode_enabled(st=st_module)):
        return
    page = str(session.get("studio_page") or "")
    entry = str(session.get("improv_entry_mode") or "")
    if page not in {"creative", "backing"} and "Jam" not in entry:
        return

    table = refresh_jam_generator_live_trace_table(session)
    div = table.get("first_divergence_hypothesis") or {}
    st_module.caption(
        "Jam Generator live trace · "
        f"fork `{div.get('first_fork_stage', '—')}` · "
        f"UNTRANSPOSED `{div.get('untransposed_flag_in_diag')}` · "
        f"blob `{ (table.get('jam_workflow_blob') or {}).get('practice_tonic', '—')}` · "
        f"UI `{ (table.get('ui_projections') or {}).get('display_key', '—')}`"
    )
    with st_module.expander("Jam Generator live runtime trace (copy for acceptance)", expanded=False):
        st_module.json(table)


__all__ = [
    "JAM_BACKING_HANDOFF_TRACE_KEY",
    "JAM_GENERATOR_LIVE_TRACE_KEY",
    "JAM_SIDEBAR_KEY_TRACE_KEY",
    "append_jam_backing_handoff_trace",
    "append_jam_sidebar_key_trace",
    "infer_first_divergence",
    "record_jam_pre_generate_trace",
    "record_jam_post_generate_trace",
    "refresh_jam_generator_live_trace_table",
    "render_jam_generator_live_trace_panel",
]
