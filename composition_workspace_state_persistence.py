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
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
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

SCHEMA_VERSION = 2
COMPOSITION_DELETED_IDS_KEY = "composer_deleted_document_ids"
COMPOSITION_LIBRARY_INITIALIZED_KEY = "composer_library_initialized"
COMPOSITION_RECOVERY_KEY = "_composition_legacy_recovery"

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
        "updated_at": _utc_now_iso(),
        "deleted_document_ids": [],
        "library_initialized": False,
    }


def upgrade_composition_workspace_blob(blob: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(default_composition_workspace_state())
    raw = blob if isinstance(blob, dict) else {}
    deleted = {str(x) for x in (raw.get("deleted_document_ids") or []) if isinstance(x, str) and x}
    out["deleted_document_ids"] = sorted(deleted)
    out["library_initialized"] = bool(raw.get("library_initialized"))
    out["schema_version"] = max(int(raw.get("schema_version") or 0), SCHEMA_VERSION)
    doc = raw.get("active_document")
    if isinstance(doc, dict) and str(doc.get("id") or "") not in deleted:
        prepared = deep_copy_document(doc)
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
            if (isinstance(item, dict) and str(sid or "").strip() and str(sid) not in deleted
                    and str(item.get("id") or "") not in deleted):
                cleaned[str(sid)] = deep_copy_document(item)
        out["library"] = cleaned
        if cleaned:
            out["library_initialized"] = True
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
        prepared = deep_copy_document(doc)
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
                cleaned[str(sid)] = deep_copy_document(item)
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
    base["updated_at"] = _utc_now_iso()
    base["schema_version"] = SCHEMA_VERSION
    base["deleted_document_ids"] = sorted(set(base.get("deleted_document_ids", [])) |
        set(session.get(COMPOSITION_DELETED_IDS_KEY) or []))
    base["library_initialized"] = bool(base.get("library_initialized") or
        session.get(COMPOSITION_LIBRARY_INITIALIZED_KEY) or base.get("library"))
    return upgrade_composition_workspace_blob(base)


def write_canonical_composition_workspace(
    session: dict[str, Any],
    blob: dict[str, Any],
    *,
    reason: str = "autosave",
) -> dict[str, Any]:
    canonical = upgrade_composition_workspace_blob(blob)
    session[COMPOSITION_WORKSPACE_STATE_KEY] = copy.deepcopy(canonical)
    session[COMPOSITION_WORKSPACE_LAST_SAVE_REASON_KEY] = reason
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
    meta = copy.deepcopy(meta)
    meta["deleted_document_ids"] = sorted(set(meta.get("deleted_document_ids") or []) |
        set(session.get(COMPOSITION_DELETED_IDS_KEY) or []))
    canonical = upgrade_composition_workspace_blob(meta)
    session[COMPOSITION_WORKSPACE_STATE_KEY] = canonical

    doc = canonical.get("active_document")
    if isinstance(doc, dict):
        prepared = deep_copy_document(doc)
        ensure_workflow(prepared)
        phase = str(canonical.get("workflow_phase") or "").strip().lower()
        if phase in COMPOSITION_PHASES:
            set_workflow_phase(prepared, phase)
        session[COMPOSER_ACTIVE_KEY] = prepared
        session[COMPOSER_NEEDS_SEED_KEY] = False
        # Prefer a live, valid section selection over a stale blob value.
        # Section clicks update session first; without this preference, prepare_render
        # would re-assert the previous section (often Bridge) on every rerun.
        # On cold restore live is empty — must use canonical, not "first section" fallback.
        live_section = str(session.get(COMPOSER_ACTIVE_SECTION_KEY) or "").strip()
        canon_section = str(canonical.get("active_section_id") or "").strip()
        order_ids = {
            str(s.get("id") or "")
            for s in ordered_sections(prepared)
            if str(s.get("id") or "")
        }
        if live_section and live_section in order_ids:
            section_id = live_section
        elif canon_section and canon_section in order_ids:
            section_id = canon_section
        else:
            section_id = resolve_valid_section_id(prepared, "")
        if section_id:
            session[COMPOSER_ACTIVE_SECTION_KEY] = section_id
        skip_lyrics = bool((prepared.get("workflow") or {}).get("skip_lyrics"))
        lane = normalize_focus_lane(str(canonical.get("focus_lane") or "chords"), skip_lyrics=skip_lyrics)
        session[COMPOSER_FOCUS_LANE_KEY] = lane
    elif overwrite:
        session.pop(COMPOSER_ACTIVE_KEY, None)
        session[COMPOSER_NEEDS_SEED_KEY] = bool(canonical.get("needs_seed", True))

    lib = canonical.get("library")
    session[COMPOSITION_DELETED_IDS_KEY] = list(canonical["deleted_document_ids"])
    session[COMPOSITION_LIBRARY_INITIALIZED_KEY] = bool(canonical["library_initialized"])
    if isinstance(lib, dict):
        session[COMPOSER_LIBRARY_KEY] = copy.deepcopy(lib)
    elif overwrite:
        session.setdefault(COMPOSER_LIBRARY_KEY, {})

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
    session.pop(COMPOSITION_WORKSPACE_DIRTY_KEY, None)
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
        # Pending local edits win, but earlier compositions from storage must not stay
        # hidden behind a fresh local document: add missing ids only (never overwrite).
        remote = _composition_workspace_from_payload(payload)
        if remote:
            from composition_library import merge_missing_library_documents

            if merge_missing_library_documents(session, remote):
                session["_composition_library_merged_while_dirty"] = True
        return False
    blob = _composition_workspace_from_payload(payload)
    if blob:
        # An old empty schema-v1 block cannot distinguish a deletion from a
        # bootstrap default. Preserve the legacy candidate and ask, never revive
        # a possibly deleted project silently or hide it behind a blank editor.
        probe: dict[str, Any] = {}
        legacy = migrate_legacy_composition_workspace_once(probe, payload)
        nested = payload.get("music_workspace_state")
        nested = nested.get(COMPOSITION_WORKSPACE_STATE_KEY) if isinstance(nested, dict) else None
        if not (legacy and (legacy.get("active_document") or legacy.get("library"))) and isinstance(nested, dict):
            legacy = copy.deepcopy(nested)
        has_docs = bool(blob.get("active_document") or blob.get("library"))
        initialized = bool(blob.get("library_initialized"))
        deleted = set(blob.get("deleted_document_ids") or []) | set(session.get(COMPOSITION_DELETED_IDS_KEY) or [])
        if legacy:
            legacy = copy.deepcopy(legacy)
            legacy["deleted_document_ids"] = sorted(deleted | set(legacy.get("deleted_document_ids") or []))
            legacy = upgrade_composition_workspace_blob(legacy)
        legacy_has_docs = bool(legacy and (legacy.get("active_document") or legacy.get("library")))
        if not has_docs and legacy_has_docs and not initialized:
            if "library_initialized" not in blob:
                session[COMPOSITION_RECOVERY_KEY] = copy.deepcopy(legacy)
                session[COMPOSITION_WORKSPACE_LAST_SKIP_KEY] = "ambiguous_empty_legacy_preserved"
                return False
            blob = legacy
        blob = copy.deepcopy(blob)
        blob["deleted_document_ids"] = sorted(deleted)
    if not blob:
        migrated = migrate_legacy_composition_workspace_once(session, payload)
        if migrated:
            migrated["deleted_document_ids"] = sorted(set(migrated.get("deleted_document_ids") or []) |
                set(session.get(COMPOSITION_DELETED_IDS_KEY) or []))
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
    session.pop(COMPOSITION_RECOVERY_KEY, None)
    return True


def resolve_legacy_recovery(session: dict[str, Any], *, recover: bool) -> None:
    """Explicit choice for an ambiguous v1 empty block; never overwrite live IDs."""
    candidate = session.pop(COMPOSITION_RECOVERY_KEY, None)
    if not isinstance(candidate, dict):
        return
    deleted = set(session.get(COMPOSITION_DELETED_IDS_KEY) or [])
    library = session.setdefault(COMPOSER_LIBRARY_KEY, {})
    candidate_library = dict(candidate.get("library") or {})
    active = candidate.get("active_document")
    if isinstance(active, dict) and active.get("id"):
        candidate_library.setdefault(str(active["id"]), active)
    if recover:
        live_ids = {str(doc.get("id") or sid) for sid, doc in library.items() if isinstance(doc, dict)}
        for sid, doc in candidate_library.items():
            if (sid not in deleted and isinstance(doc, dict) and str(doc.get("id") or "") not in deleted
                    and str(doc.get("id") or sid) not in live_ids):
                library.setdefault(sid, copy.deepcopy(doc))
        if not session.get(COMPOSER_ACTIVE_KEY) and isinstance(active, dict):
            chosen = library.get(str(active.get("id") or ""))
            if isinstance(chosen, dict):
                session[COMPOSER_ACTIVE_KEY] = copy.deepcopy(chosen)
                session[COMPOSER_NEEDS_SEED_KEY] = False
    else:
        # Declining a legacy recovery is explicit deletion provenance. Do not
        # mark any currently live project as deleted.
        live_ids = {str(doc.get("id") or sid) for sid, doc in library.items() if isinstance(doc, dict)}
        for sid, doc in candidate_library.items():
            identity = str(doc.get("id") or sid) if isinstance(doc, dict) else sid
            if identity not in live_ids:
                deleted.update((sid, identity))
    session[COMPOSITION_DELETED_IDS_KEY] = sorted(deleted)
    session[COMPOSITION_LIBRARY_INITIALIZED_KEY] = True
    mark_composition_workspace_dirty(session, reason="legacy_recovery_choice")
    sync_composition_workspace_before_persist(session, reason="legacy_recovery_choice")


def prepare_composition_workspace_for_render(session: dict[str, Any]) -> None:
    """Project restored canonical state before Composition widgets instantiate."""
    meta = session.get(COMPOSITION_WORKSPACE_STATE_KEY)
    if isinstance(meta, dict) and (
        composition_workspace_restored(session) or isinstance(meta.get("active_document"), dict)
        or meta.get("library_initialized") or meta.get("deleted_document_ids")
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
) -> dict[str, Any] | None:
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
        from composition_save_verification import RESULT_KEY, content_fingerprint
        session[RESULT_KEY] = {"status": "memory_only", "disk_verified": False,
                              "cloud_verified": False, "fingerprint": content_fingerprint(
                                  session[COMPOSITION_WORKSPACE_STATE_KEY])}
        return
    target = st
    if target is None:

        class _Proxy:
            session_state = session

        target = _Proxy()
    from composition_save_verification import RESULT_KEY, verify_checkpoint
    expected = copy.deepcopy(session[COMPOSITION_WORKSPACE_STATE_KEY])
    # Reset per-attempt flags; previous page saves must not acknowledge this one.
    session.pop(RESULT_KEY, None)
    session.pop("_composition_workspace_force_save_error", None)
    session["_suite_persist_last_save_disk"] = False
    session["_suite_persist_last_save_cloud"] = False
    session["_music_force_save_ok"] = False
    force_ok = False
    try:
        from music_persistent_state import force_save_music_state

        force_ok = bool(force_save_music_state(target, reason=reason))
    except Exception:
        session["_composition_workspace_force_save_error"] = True
    result = verify_checkpoint(session, expected, force_ok=force_ok)
    if result["cloud_verified"] or (result["disk_verified"] and not result["cloud_required"]):
        session.pop(COMPOSITION_WORKSPACE_DIRTY_KEY, None)
    else:
        session[COMPOSITION_WORKSPACE_DIRTY_KEY] = True
    return result
