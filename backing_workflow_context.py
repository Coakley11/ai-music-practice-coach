"""Explicit backing workflow ownership — isolated from catalog/mission session keys."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Literal

from backing_context import BackingContext, get_backing_context

BACKING_WORKFLOW_ENVELOPE_KEY = "backing_workflow_envelope"
BACKING_WORKFLOW_SCOPE_OWNER_KEY = "_backing_workflow_scope_owner"

WorkflowType = Literal[
    "song_based_improvisation",
    "entry_jam",
    "jam_session_generator",
    "mission_jam",
    "regular_catalog_backing",
    "regular_custom_backing",
]

SourceType = Literal["catalog", "custom", "generated"]


def _workflow_from_ctx(ctx: BackingContext) -> WorkflowType:
    src = str(ctx.source or "").strip()
    entry = str(ctx.entry_mode or "").strip()
    if src == "song_improv":
        return "song_based_improvisation"
    if src == "mission":
        return "mission_jam"
    if src == "custom_progression":
        return "regular_custom_backing"
    if src == "entry_jam":
        if entry == "Jam Session Generator":
            return "jam_session_generator"
        return "entry_jam"
    return "regular_catalog_backing"


def _source_type_for_workflow(wf: WorkflowType, ctx: BackingContext) -> SourceType:
    if wf in {"entry_jam", "jam_session_generator"}:
        return "generated"
    if wf == "song_based_improvisation":
        return "custom" if str(ctx.active_song_id or "").startswith("custom::") else "catalog"
    if wf == "regular_custom_backing":
        return "custom"
    if wf == "mission_jam":
        return "catalog"
    return "catalog"


def _creative_tab_for_ctx(ctx: BackingContext, session: dict[str, Any]) -> str:
    tab = str(
        session.get("improv_intelligence_tab")
        or session.get("creative_improv_intelligence_tab")
        or ""
    ).strip()
    if tab:
        return tab
    if ctx.source in {"entry_jam", "song_improv", "mission"}:
        return "Improvisation Intelligence"
    return ""


def _creative_origin_mode(ctx: BackingContext) -> str:
    entry = str(ctx.entry_mode or "").strip()
    if ctx.source == "song_improv":
        return "Song-Based Improvisation"
    if entry == "Jam Session Generator":
        return "Jam Session Generator"
    if ctx.source == "entry_jam":
        return entry or "Style Jam Mode"
    if ctx.source == "mission":
        return "Missions"
    return ""


def _return_destination(wf: WorkflowType) -> str:
    if wf == "mission_jam":
        return "creative:missions"
    if wf in {"entry_jam", "jam_session_generator", "song_based_improvisation"}:
        return "creative:improvisation"
    return "creative"


def _context_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_backing_workflow_envelope(
    session: dict[str, Any],
    ctx: BackingContext,
) -> dict[str, Any]:
    wf = _workflow_from_ctx(ctx)
    stype = _source_type_for_workflow(wf, ctx)
    owner_id = ""
    song_id = ""
    generated_id = ""
    if wf == "song_based_improvisation":
        song_id = str(ctx.bound_pick_key or ctx.active_song_id or "").strip()
        owner_id = song_id or "song_improv"
    elif wf in {"entry_jam", "jam_session_generator"}:
        generated_id = str(ctx.jam_id or ctx.source_signature or wf).strip()
        owner_id = generated_id or wf
    elif wf == "mission_jam":
        owner_id = str(ctx.mission_id or "mission").strip()
        song_id = str(ctx.bound_pick_key or ctx.active_song_id or "").strip()
    else:
        owner_id = str(ctx.active_song_id or ctx.bound_pick_key or "regular").strip()
        if stype == "custom":
            song_id = owner_id

    envelope: dict[str, Any] = {
        "workflow_type": wf,
        "context_owner_id": owner_id,
        "source_type": stype,
        "song_id": song_id or None,
        "generated_session_id": generated_id or None,
        "tonic": str(ctx.concert_key or ctx.display_key or ctx.key or "C").strip() or "C",
        "mode": str(ctx.mode_label or "").strip() or None,
        "style_owner": owner_id if wf in {"entry_jam", "jam_session_generator"} else (song_id or owner_id),
        "progression_owner": owner_id,
        "section_map_keys": list(ctx.section_labels or ctx.sections or []),
        "style": str(ctx.style or "").strip(),
        "mood": str(ctx.mood or "").strip(),
        "groove": str(ctx.groove or "").strip(),
        "tempo_bpm": int(ctx.bpm or 0),
        "style_source": "generated" if wf in {"entry_jam", "jam_session_generator"} else "workflow",
        "creative_origin_tab": _creative_tab_for_ctx(ctx, session),
        "creative_origin_mode": _creative_origin_mode(ctx),
        "return_destination": _return_destination(wf),
        "backing_session_type": wf,
        "playback_scope_default": "Mission chord" if wf == "mission_jam" else "Full song",
        "mission_id": str(ctx.mission_id or "").strip() or None,
        "entry_mode": str(ctx.entry_mode or "").strip() or None,
    }
    try:
        from music_theory import key_is_minor, split_chord

        if wf in {"entry_jam", "jam_session_generator"}:
            envelope["current_practice_mode"] = "major" if not key_is_minor(str(ctx.concert_key or "")) else "minor"
        else:
            from musical_context_authority import resolve_authoritative_practice_key

            pk = resolve_authoritative_practice_key(session)
            envelope["original_tonic"] = pk.original_tonic
            envelope["original_mode"] = pk.original_mode
            envelope["current_practice_tonic"] = pk.practice_tonic
            envelope["current_practice_mode"] = pk.practice_mode
    except ImportError:
        pass
    envelope["displayed_style"] = str(ctx.style or ctx.groove or "").strip() or None
    envelope["context_fingerprint"] = _context_fingerprint(
        {k: envelope[k] for k in envelope if k != "context_fingerprint"}
    )
    return envelope


def sync_backing_workflow_envelope(session: dict[str, Any], ctx: BackingContext | None = None) -> dict[str, Any]:
    ctx = ctx or get_backing_context(session)
    if ctx is None:
        session.pop(BACKING_WORKFLOW_ENVELOPE_KEY, None)
        return {}
    env = build_backing_workflow_envelope(session, ctx)
    session[BACKING_WORKFLOW_ENVELOPE_KEY] = copy.deepcopy(env)
    return env


def get_backing_workflow_envelope(session: dict[str, Any]) -> dict[str, Any] | None:
    raw = session.get(BACKING_WORKFLOW_ENVELOPE_KEY)
    return raw if isinstance(raw, dict) and raw.get("workflow_type") else None


def workflow_is_generated(session: dict[str, Any]) -> bool:
    env = get_backing_workflow_envelope(session)
    if env:
        return str(env.get("source_type") or "") == "generated"
    ctx = get_backing_context(session)
    if ctx is None:
        return False
    return _workflow_from_ctx(ctx) in {"entry_jam", "jam_session_generator"}


def backing_scope_for_workflow(
    session: dict[str, Any],
    *,
    workflow_type: WorkflowType,
    context_fingerprint: str,
) -> tuple[str, str | None, list[str]]:
    """Default Full song for creative jams; reuse saved scope only for same workflow owner."""
    if workflow_type == "mission_jam":
        ctx = get_backing_context(session)
        sec = str(getattr(ctx, "section", None) or "").strip() or None
        return "Mission chord", sec, [sec] if sec else []
    owner = str(session.get(BACKING_WORKFLOW_SCOPE_OWNER_KEY) or "").strip()
    if owner and owner == context_fingerprint:
        scope = str(session.get("backing_track_scope") or "Full song").strip()
        section = str(session.get("backing_track_single_section") or "").strip() or None
        multi = session.get("backing_track_multi_sections")
        sections = [str(s) for s in multi if str(s).strip()] if isinstance(multi, list) else []
        if scope.lower() in {"selected sections", "multi section", "multi-section"} and sections:
            return "Selected sections", section, sections
        if scope == "Single section" and section:
            return "Single section", section, [section]
        if scope == "Full song":
            return "Full song", None, []
    session[BACKING_WORKFLOW_SCOPE_OWNER_KEY] = context_fingerprint
    session["backing_track_scope"] = "Full song"
    session.pop("backing_track_single_section", None)
    session.pop("backing_track_multi_sections", None)
    return "Full song", None, []


def display_source_label(session: dict[str, Any]) -> str:
    env = get_backing_workflow_envelope(session)
    if env:
        wf = str(env.get("workflow_type") or "")
        if wf == "jam_session_generator":
            return "Jam Session Generator"
        if wf == "entry_jam":
            return "Entry & Jam"
        if wf == "song_based_improvisation":
            st = str(env.get("source_type") or "")
            return f"Song-Based Improvisation ({st})"
        if wf == "mission_jam":
            return "Mission Jam"
    ctx = get_backing_context(session)
    if ctx is None:
        return ""
    if workflow_is_generated(session):
        return _creative_origin_mode(ctx) or ctx.source_label
    return ctx.source_label


def render_backing_workflow_dev_diagnostics(st_module: Any, session: dict[str, Any]) -> None:
    try:
        from suite_workspace import is_developer_mode_enabled

        if not is_developer_mode_enabled(st=st_module):
            return
    except ImportError:
        if not session.get("dev_mode"):
            return
    env = get_backing_workflow_envelope(session) or {}
    deploy = str(session.get("_studio_ui_release_sha") or "—")
    try:
        from musical_context_authority import (
            PRACTICE_KEY_AUTHORITY_DIAG_KEY,
            run_musical_context_consistency_checks,
            sidebar_key_list_mode,
        )

        run_musical_context_consistency_checks(session)
        pk_diag = session.get(PRACTICE_KEY_AUTHORITY_DIAG_KEY) or {}
    except ImportError:
        pk_diag = {}
    st_module.caption(
        "DEV backing workflow · "
        f"type `{env.get('workflow_type', '—')}` · "
        f"source `{env.get('source_type', '—')}` · "
        f"owner `{env.get('context_owner_id', '—')}` · "
        f"style `{env.get('displayed_style') or env.get('style', '—')}` · "
        f"style_owner `{env.get('style_owner', '—')}` · "
        f"practice `{env.get('current_practice_tonic', '—')}` `{env.get('current_practice_mode', '—')}` · "
        f"sidebar_mode `{sidebar_key_list_mode(session) if pk_diag else '—'}` · "
        f"violations `{pk_diag.get('violations', [])}` · "
        f"fp `{env.get('context_fingerprint', '—')}` · "
        f"sha `{deploy[:7] if deploy != '—' else '—'}`"
    )


__all__ = [
    "BACKING_WORKFLOW_ENVELOPE_KEY",
    "BACKING_WORKFLOW_SCOPE_OWNER_KEY",
    "backing_scope_for_workflow",
    "build_backing_workflow_envelope",
    "display_source_label",
    "get_backing_workflow_envelope",
    "render_backing_workflow_dev_diagnostics",
    "sync_backing_workflow_envelope",
    "workflow_is_generated",
]
