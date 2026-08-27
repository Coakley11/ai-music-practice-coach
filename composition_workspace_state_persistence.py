"""Canonical Composition Studio workspace blob — draft song + editing location.

Mirrors practice_workspace_persistence / creative_workspace_state_persistence:
durable envelope field ``composition_workspace_state`` survives Streamlit reboot.
Preview WAV / signatures are intentionally excluded.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from composition_document import (
    COMPOSITION_PHASES,
    deep_copy_document,
    ensure_workflow,
    get_workflow_phase,
    ordered_sections,
    set_workflow_phase,
    touch_composition,
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_ARRANGEMENT_PREVIEW_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_NEEDS_SEED_KEY,
    COMPOSER_PREVIEW_SIG_KEY,
    COMPOSER_PREVIEW_WAV_KEY,
    COMPOSER_SNAPSHOT_STAMP_KEY,
)

COMPOSITION_WORKSPACE_STATE_KEY = "composition_workspace_state"
COMPOSITION_WORKSPACE_DIRTY_KEY = "composition_workspace_state_dirty"
COMPOSITION_WORKSPACE_RESTORED_KEY = "_composition_workspace_state_restored"
COMPOSITION_WORKSPACE_MIGRATED_KEY = "_composition_workspace_legacy_migrated"
COMPOSITION_WORKSPACE_LAST_SAVE_REASON_KEY = "_composition_workspace_last_save_reason"
COMPOSITION_WORKSPACE_LAST_SKIP_KEY = "_composition_workspace_last_apply_skipped"

SCHEMA_VERSION = 1

VALID_FOCUS_LANES: frozenset[str] = frozenset(
    {"chords", "melody", "lyrics", "review", "structure", "vision"}
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_composition_workspace_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "active_document": None,
        "library": {},
        "needs_seed": True,
        "active_section_id": "",
        "focus_lane": "chords",
        "workflow_phase": "vision",
        "arrangement_preview_style": "",
        "updated_at": _utc_now_iso(),
    }


def upgrade_composition_workspace_blob(blob: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(default_composition_workspace_state())
    raw = blob if isinstance(blob, dict) else {}
    out["schema_version"] = max(int(raw.get("schema_version") or 0), SCHEMA_VERSION)
    doc = raw.get("active_document")
    if isinstance(doc, dict):
        prepared = touch_composition(deep_copy_document(doc))
        ensure_workflow(prepared)
        out["active_document"] = prepared
        out["needs_seed"] = False
    else:
        out["active_document"] = None
        out["needs_seed"] = bool(raw.get("needs_seed", True))
    lib = raw.get("library")
    if isinstance(lib, dict):
        cleaned: dict[str, Any] = {}
        for sid, item in lib.items():
            if isinstance(item, dict) and str(sid or "").strip():
                cleaned[str(sid)] = touch_composition(deep_copy_document(item))
        out["library"] = cleaned
    lane = str(raw.get("focus_lane") or "chords").strip().lower()
    out["focus_lane"] = lane if lane in VALID_FOCUS_LANES else "chords"
    phase = str(raw.get("workflow_phase") or "").strip().lower()
    if phase in COMPOSITION_PHASES:
        out["workflow_phase"] = phase
    elif out["focus_lane"] in COMPOSITION_PHASES:
        out["workflow_phase"] = out["focus_lane"]
    else:
        out["workflow_phase"] = "vision"
    out["active_section_id"] = str(raw.get("active_section_id") or "").strip()
    out["arrangement_preview_style"] = str(raw.get("arrangement_preview_style") or "").strip()
    out["updated_at"] = str(raw.get("updated_at") or "").strip() or _utc_now_iso()
    return out


def normalize_focus_lane(raw: str, *, skip_lyrics: bool = False) -> str:
    lane = str(raw or "").strip().lower()
    if lane not in VALID_FOCUS_LANES:
        return "chords"
    if skip_lyrics and lane == "lyrics":
        return "chords"
    return lane


def resolve_valid_section_id(doc: dict[str, Any] | None, preferred: str) -> str:
    """Pick preferred section if present; else first ordered section; else empty."""
    if not isinstance(doc, dict):
        return ""
    order = [str(s.get("id") or "") for s in ordered_sections(doc) if str(s.get("id") or "")]
    if not order:
        return ""
    pref = str(preferred or "").strip()
    if pref and pref in order:
        return pref
    return order[0]


def gather_composition_workspace_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Live session → durable composition_workspace_state (no preview audio)."""
    base = session.get(COMPOSITION_WORKSPACE_STATE_KEY)
    if not isinstance(base, dict):
        base = default_composition_workspace_state()
    else:
        base = upgrade_composition_workspace_blob(base)

    doc = session.get(COMPOSER_ACTIVE_KEY)
    if isinstance(doc, dict):
        prepared = touch_composition(deep_copy_document(doc))
        ensure_workflow(prepared)
        base["active_document"] = prepared
        base["needs_seed"] = False
        base["workflow_phase"] = get_workflow_phase(prepared)
    else:
        if not isinstance(base.get("active_document"), dict):
            base["active_document"] = None
            base["needs_seed"] = bool(session.get(COMPOSER_NEEDS_SEED_KEY, True))

    lib = session.get(COMPOSER_LIBRARY_KEY)
    if isinstance(lib, dict):
        cleaned: dict[str, Any] = {}
        for sid, item in lib.items():
            if isinstance(item, dict) and str(sid or "").strip():
                cleaned[str(sid)] = touch_composition(deep_copy_document(item))
        base["library"] = cleaned

    skip_lyrics = False
    active = base.get("active_document")
    if isinstance(active, dict):
        wf = active.get("workflow") or {}
        skip_lyrics = bool(wf.get("skip_lyrics")) if isinstance(wf, dict) else False

    lane = normalize_focus_lane(
        str(session.get(COMPOSER_FOCUS_LANE_KEY) or base.get("focus_lane") or "chords"),
        skip_lyrics=skip_lyrics,
    )
    base["focus_lane"] = lane
    # Workflow phase stays owned by the document; do not overwrite vision/structure
    # just because a section lane default is "chords".
    if isinstance(active, dict):
        base["workflow_phase"] = get_workflow_phase(active)
        base["active_document"] = active

    base["active_section_id"] = resolve_valid_section_id(
        base.get("active_document") if isinstance(base.get("active_document"), dict) else None,
        str(session.get(COMPOSER_ACTIVE_SECTION_KEY) or base.get("active_section_id") or ""),
    )
    preview_style = str(
        session.get(COMPOSER_ARRANGEMENT_PREVIEW_KEY) or base.get("arrangement_preview_style") or ""
    ).strip()
    base["arrangement_preview_style"] = preview_style
    base["updated_at"] = _utc_now_iso()
    base["schema_version"] = SCHEMA_VERSION
    return base


def write_canonical_composition_workspace(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    canonical = upgrade_composition_workspace_blob(blob)
    session[COMPOSITION_WORKSPACE_STATE_KEY] = copy.deepcopy(canonical)
    session[COMPOSITION_WORKSPACE_LAST_SAVE_REASON_KEY] = reason
    session.pop(COMPOSITION_WORKSPACE_DIRTY_KEY, None)
    return canonical


def mark_composition_workspace_dirty(session: dict[str, Any], *, reason: str = "composer_edit") -> None:
    session[COMPOSITION_WORKSPACE_DIRTY_KEY] = True
    session[COMPOSITION_WORKSPACE_LAST_SAVE_REASON_KEY] = reason


def is_composition_workspace_locally_dirty(session: dict[str, Any]) -> bool:
    return bool(session.get(COMPOSITION_WORKSPACE_DIRTY_KEY))


def composition_workspace_restored(session: dict[str, Any]) -> bool:
    return bool(session.get(COMPOSITION_WORKSPACE_RESTORED_KEY))


def sync_composition_workspace_before_persist(session: dict[str, Any], *, reason: str = "autosave") -> None:
    gathered = gather_composition_workspace_from_session(session)
    write_canonical_composition_workspace(session, gathered, reason=reason)


def composition_workspace_for_envelope(session: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(gather_composition_workspace_from_session(session))


def project_composition_workspace_to_session(session: dict[str, Any], *, overwrite: bool = True) -> None:
    """Project durable blob → live Composition session keys (never preview audio)."""
    meta = session.get(COMPOSITION_WORKSPACE_STATE_KEY)
    if not isinstance(meta, dict):
        return
    canonical = upgrade_composition_workspace_blob(meta)
    session[COMPOSITION_WORKSPACE_STATE_KEY] = canonical

    doc = canonical.get("active_document")
    if isinstance(doc, dict):
        prepared = touch_composition(deep_copy_document(doc))
        ensure_workflow(prepared)
        phase = str(canonical.get("workflow_phase") or "").strip().lower()
        if phase in COMPOSITION_PHASES:
            set_workflow_phase(prepared, phase)
        session[COMPOSER_ACTIVE_KEY] = prepared
        session[COMPOSER_NEEDS_SEED_KEY] = False
        section_id = resolve_valid_section_id(prepared, str(canonical.get("active_section_id") or ""))
        if section_id:
            session[COMPOSER_ACTIVE_SECTION_KEY] = section_id
        skip_lyrics = bool((prepared.get("workflow") or {}).get("skip_lyrics"))
        lane = normalize_focus_lane(str(canonical.get("focus_lane") or "chords"), skip_lyrics=skip_lyrics)
        session[COMPOSER_FOCUS_LANE_KEY] = lane
    elif overwrite:
        session.pop(COMPOSER_ACTIVE_KEY, None)
        session[COMPOSER_NEEDS_SEED_KEY] = bool(canonical.get("needs_seed", True))

    lib = canonical.get("library")
    if isinstance(lib, dict):
        session[COMPOSER_LIBRARY_KEY] = copy.deepcopy(lib)
    elif overwrite:
        session.setdefault(COMPOSER_LIBRARY_KEY, {})

    session[COMPOSER_ARRANGEMENT_PREVIEW_KEY] = str(canonical.get("arrangement_preview_style") or "").strip()
    session.pop(COMPOSER_PREVIEW_WAV_KEY, None)
    session.pop(COMPOSER_PREVIEW_SIG_KEY, None)
    session.pop(COMPOSER_SNAPSHOT_STAMP_KEY, None)


def apply_composition_workspace_to_session(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    source: str = "disk_restore",
) -> None:
    write_canonical_composition_workspace(session, blob, reason=source)
    project_composition_workspace_to_session(session, overwrite=True)
    session[COMPOSITION_WORKSPACE_RESTORED_KEY] = True
    session.pop(COMPOSITION_WORKSPACE_LAST_SKIP_KEY, None)


def _composition_workspace_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    top = payload.get(COMPOSITION_WORKSPACE_STATE_KEY)
    if isinstance(top, dict) and (top.get("active_document") is not None or top.get("library")):
        return copy.deepcopy(top)
    if isinstance(top, dict) and top.get("schema_version"):
        return copy.deepcopy(top)
    ws = payload.get("music_workspace_state")
    if isinstance(ws, dict) and isinstance(ws.get(COMPOSITION_WORKSPACE_STATE_KEY), dict):
        return copy.deepcopy(ws[COMPOSITION_WORKSPACE_STATE_KEY])
    return None


def migrate_legacy_composition_workspace_once(
    session: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Build workspace blob from page snapshot / flat session keys when envelope missing."""
    if session.get(COMPOSITION_WORKSPACE_MIGRATED_KEY):
        return None
    session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
    snaps = session_extra.get("_studio_page_snapshots")
    if not isinstance(snaps, dict):
        snaps = session.get("_studio_page_snapshots")
    composer_snap = snaps.get("composer") if isinstance(snaps, dict) else None
    flat = session_extra if isinstance(session_extra, dict) else {}
    source: dict[str, Any] = {}
    if isinstance(composer_snap, dict):
        source.update(composer_snap)
    for key in (
        COMPOSER_ACTIVE_KEY,
        COMPOSER_LIBRARY_KEY,
        COMPOSER_NEEDS_SEED_KEY,
        COMPOSER_ACTIVE_SECTION_KEY,
        COMPOSER_FOCUS_LANE_KEY,
    ):
        if key in flat and key not in source:
            source[key] = flat[key]
        if key in session and key not in source:
            source[key] = session[key]
    if not source:
        return None
    blob = default_composition_workspace_state()
    doc = source.get(COMPOSER_ACTIVE_KEY)
    if isinstance(doc, dict):
        blob["active_document"] = deep_copy_document(doc)
        blob["needs_seed"] = False
        blob["workflow_phase"] = get_workflow_phase(doc)
    lib = source.get(COMPOSER_LIBRARY_KEY)
    if isinstance(lib, dict):
        blob["library"] = copy.deepcopy(lib)
    blob["active_section_id"] = str(source.get(COMPOSER_ACTIVE_SECTION_KEY) or "")
    blob["focus_lane"] = str(source.get(COMPOSER_FOCUS_LANE_KEY) or "chords")
    if COMPOSER_NEEDS_SEED_KEY in source:
        blob["needs_seed"] = bool(source.get(COMPOSER_NEEDS_SEED_KEY))
    session[COMPOSITION_WORKSPACE_MIGRATED_KEY] = True
    session["_composition_workspace_migrated_from"] = "page_snapshot"
    return upgrade_composition_workspace_blob(blob)


def apply_composition_workspace_from_payload(
    session: dict[str, Any],
    payload: dict[str, Any],
    *,
    authoritative: bool = False,
) -> bool:
    if is_composition_workspace_locally_dirty(session) and not authoritative:
        session[COMPOSITION_WORKSPACE_LAST_SKIP_KEY] = "local_dirty"
        return False
    blob = _composition_workspace_from_payload(payload)
    if not blob:
        migrated = migrate_legacy_composition_workspace_once(session, payload)
        if migrated:
            apply_composition_workspace_to_session(session, migrated, source="legacy_migration")
            return True
        session[COMPOSITION_WORKSPACE_LAST_SKIP_KEY] = "missing_in_envelope"
        return False
    apply_composition_workspace_to_session(
        session,
        blob,
        source="cloud_restore" if authoritative else "disk_restore",
    )
    session[COMPOSITION_WORKSPACE_MIGRATED_KEY] = True
    return True


def prepare_composition_workspace_for_render(session: dict[str, Any]) -> None:
    """Project restored canonical state before Composition widgets instantiate."""
    meta = session.get(COMPOSITION_WORKSPACE_STATE_KEY)
    if isinstance(meta, dict) and (
        composition_workspace_restored(session) or isinstance(meta.get("active_document"), dict)
    ):
        project_composition_workspace_to_session(session, overwrite=True)
        return
    if composition_workspace_restored(session):
        return
    if isinstance(session.get(COMPOSER_ACTIVE_KEY), dict):
        sync_composition_workspace_before_persist(session, reason="prepare_render_seed")


def checkpoint_composition_workspace(
    session: dict[str, Any],
    *,
    reason: str = "composer_edit",
    force_disk: bool = False,
    st: Any | None = None,
) -> None:
    """Mark dirty + sync canonical blob. Optionally force durable save."""
    mark_composition_workspace_dirty(session, reason=reason)
    sync_composition_workspace_before_persist(session, reason=reason)
    try:
        from studio_page_persistence import save_page_snapshot

        if str(session.get("studio_page") or "").strip().lower() == "composer":
            save_page_snapshot(session, "composer")
    except ImportError:
        pass
    if not force_disk:
        return
    target = st
    if target is None:

        class _Proxy:
            session_state = session

        target = _Proxy()
    try:
        from music_persistent_state import force_save_music_state

        force_save_music_state(target, reason=reason)
    except Exception:
        session["_composition_workspace_force_save_error"] = True
