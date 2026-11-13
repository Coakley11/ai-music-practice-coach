"""Composition Library model: list, switch, merge and retry (pure session logic, no UI).

Mirrors Custom Progressions: every saved composition of the account is listed;
"Now Editing" (Studio document) and "Active Song" (global Practice/Backing song)
are independent statuses and may sit on different rows.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any

from composition_document import deep_copy_document
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_LIBRARY_KEY,
    get_active_document,
    load_library_document,
    save_document_to_library,
    set_active_document,
)

DELETED_KEY = "composer_deleted_document_ids"


def _title(doc: dict[str, Any]) -> str:
    return str(doc.get("title") or "Untitled").strip() or "Untitled"


def _retitled(doc: dict[str, Any], suffix: str) -> dict[str, Any]:
    """Copy with a fresh stable id and a title suffix (conflict-preservation copy)."""
    out = deep_copy_document(doc)
    out["id"] = str(uuid.uuid4())
    out["title"] = f"{_title(doc)} ({suffix})"
    return out


def _doc_id(sid: str, doc: dict[str, Any]) -> str:
    return str(doc.get("id") or sid or "").strip()


def _content(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Document content without the touch timestamp (compare edits, not clocks)."""
    d = copy.deepcopy(doc or {})
    d.pop("updated_at", None)
    return d


def library_rows(session: dict[str, Any], active_song_id: str = "") -> list[dict[str, Any]]:
    """ALL non-deleted compositions, newest first, with independent status flags.

    The Studio document is always included, even if it was never upserted into the
    library (a draft must not be invisible in the list).
    """
    deleted = {str(x) for x in (session.get(DELETED_KEY) or [])}
    lib = session.get(COMPOSER_LIBRARY_KEY)
    docs: dict[str, dict[str, Any]] = {}
    if isinstance(lib, dict):
        for sid, doc in lib.items():
            if isinstance(doc, dict):
                did = _doc_id(str(sid), doc)
                if did and did not in deleted and str(sid) not in deleted:
                    docs[did] = doc
    editing = get_active_document(session)
    editing_id = str((editing or {}).get("id") or "").strip()
    in_library = editing_id in docs
    if editing and editing_id and editing_id not in deleted and not in_library:
        docs[editing_id] = editing
    rows = []
    for did, doc in docs.items():
        rows.append({
            "id": did,
            "title": _title(doc),
            "updated_at": str(doc.get("updated_at") or doc.get("created_at") or ""),
            "now_editing": did == editing_id,
            "active_song": bool(active_song_id) and did == str(active_song_id),
            "in_library": did != editing_id or in_library,
        })
    rows.sort(key=lambda r: (r["updated_at"], r["title"].lower()), reverse=True)
    return rows


def status_badges(row: dict[str, Any]) -> list[str]:
    badges = []
    if row.get("now_editing"):
        badges.append("Now Editing")
    if row.get("active_song"):
        badges.append("Active Song")
    if not row.get("in_library", True):
        badges.append("Unsaved draft")
    return badges


def preserve_active_document(session: dict[str, Any]) -> bool:
    """Upsert the Studio document into the library when absent or edited (never loses edits)."""
    doc = get_active_document(session)
    if not doc or not str(doc.get("id") or "").strip():
        return False
    if str(doc["id"]) in {str(x) for x in (session.get(DELETED_KEY) or [])}:
        return False
    lib = session.get(COMPOSER_LIBRARY_KEY)
    stored = lib.get(str(doc["id"])) if isinstance(lib, dict) else None
    if isinstance(stored, dict) and _content(stored) == _content(doc):
        return True
    return bool(save_document_to_library(session, doc, force_disk=False, reason="preserve_before_switch"))


def switch_to_composition(session: dict[str, Any], doc_id: str) -> tuple[bool, str]:
    """Open another saved composition for editing after preserving current edits."""
    target = str(doc_id or "").strip()
    lib = session.get(COMPOSER_LIBRARY_KEY)
    if target in {str(x) for x in (session.get(DELETED_KEY) or [])} or not isinstance(lib, dict) or not isinstance(lib.get(target), dict):
        return False, "That composition is not in your library."
    current = get_active_document(session)
    if current and str(current.get("id") or "") == target:
        return True, ""
    if current and not preserve_active_document(session):
        return False, "Your current composition could not be preserved, so it was not closed."
    load_library_document(session, target)
    return True, ""


def merge_missing_library_documents(session: dict[str, Any], remote: dict[str, Any]) -> list[str]:
    """Add remote compositions the local session lacks. Never overwrites or deletes local content.

    Used when cloud hydration is skipped because local edits are pending, so earlier
    compositions from the account are not hidden behind a fresh local document.
    """
    deleted = {str(x) for x in (session.get(DELETED_KEY) or [])} | {
        str(x) for x in ((remote or {}).get("deleted_document_ids") or [])}
    lib = session.setdefault(COMPOSER_LIBRARY_KEY, {})
    if not isinstance(lib, dict):
        lib = session[COMPOSER_LIBRARY_KEY] = {}
    known = {_doc_id(str(s), d) for s, d in lib.items() if isinstance(d, dict)}
    added: list[str] = []
    rlib = (remote or {}).get("library")
    candidates = dict(rlib) if isinstance(rlib, dict) else {}
    ractive = (remote or {}).get("active_document")
    if isinstance(ractive, dict) and ractive.get("id"):
        candidates.setdefault(str(ractive["id"]), ractive)
    for sid, doc in candidates.items():
        if not isinstance(doc, dict):
            continue
        did = _doc_id(str(sid), doc)
        if did and did not in deleted and did not in known:
            lib[did if did == str(sid) else str(sid)] = deep_copy_document(doc)
            known.add(did)
            added.append(did)
    return added


def merge_remote_workspace_keep_local(session: dict[str, Any], remote: dict[str, Any]) -> dict[str, Any]:
    """Reconcile after a stale-revision conflict without discarding either side.

    * remote-only ids are added;
    * same id, different content: the remote copy is kept under its id and the local
      edit is preserved as a new "(my edits)" composition with a fresh id.
    """
    added = merge_missing_library_documents(session, remote)
    conflicts: list[str] = []
    moved: dict[str, str] = {}
    lib = session[COMPOSER_LIBRARY_KEY]
    rlib = dict((remote or {}).get("library") or {})
    for sid, rdoc in rlib.items():
        local = lib.get(sid)
        if not (isinstance(local, dict) and isinstance(rdoc, dict)):
            continue
        if _content(local) == _content(rdoc):
            continue
        from composition_save_verification import CLOUD_BASE_KEY, doc_hash

        if (session.get(CLOUD_BASE_KEY) or {}).get(str(sid)) == doc_hash(rdoc):
            continue  # cloud copy is exactly what this session last synced: only local changed
        if str(local.get("updated_at") or "") <= str(rdoc.get("updated_at") or ""):
            # Remote is newer: it keeps the id; the local edit is preserved as a copy.
            copy_doc = _retitled(local, "my edits")
            new_id = copy_doc["id"]
            lib[new_id] = copy_doc
            lib[sid] = deep_copy_document(rdoc)
            conflicts.append(new_id)
            moved[str(sid)] = new_id
            continue
        # Local is newer: keep local; preserve the remote version separately.
        copy_doc = _retitled(rdoc, "cloud version")
        new_id = copy_doc["id"]
        lib[new_id] = copy_doc
        conflicts.append(new_id)
    return {"added": added, "conflict_copies": conflicts, "moved": moved}


def load_cloud_and_keep_edits(session: dict[str, Any]) -> tuple[bool, str]:
    """'Load cloud version and keep my edits': merge, adopt the cloud revision, stay dirty."""
    try:
        from suite_cloud_state import load_cloud_full_session
        state, _ts = load_cloud_full_session("music", force=True)
    except Exception:
        return False, "The cloud copy could not be loaded. Your edits are unchanged; try again."
    remote = state.get("composition_workspace_state") if isinstance(state, dict) else None
    if not isinstance(remote, dict):
        return False, "No cloud Composition data was found. Your edits are unchanged."
    result = merge_remote_workspace_keep_local(session, remote)
    session[DELETED_KEY] = sorted({str(x) for x in (session.get(DELETED_KEY) or [])} |
                                  {str(x) for x in (remote.get("deleted_document_ids") or [])})
    try:
        from workspace_revision import stamp_applied_workspace_revision
        stamp_applied_workspace_revision(session, state)
    except Exception:
        pass
    session.pop("_music_stale_write_blocked", None)
    session.pop("stale_write_blocked", None)
    editing = get_active_document(session)
    moved_to = result["moved"].get(str((editing or {}).get("id") or ""))
    if moved_to:  # the cloud version kept the id; keep editing the preserved local copy
        set_active_document(session, session[COMPOSER_LIBRARY_KEY][moved_to], checkpoint=False)
    preserve_active_document(session)
    from composition_workspace_state_persistence import mark_composition_workspace_dirty, sync_composition_workspace_before_persist
    mark_composition_workspace_dirty(session, reason="composer_edit")
    sync_composition_workspace_before_persist(session, reason="composer_edit")
    n = len(result["added"]) + len(result["conflict_copies"])
    return True, f"Cloud version loaded; {n} composition(s) merged. Your edits were kept. Press Save to store them."


def retry_cloud_save(session: dict[str, Any], st: Any | None = None) -> tuple[str, str]:
    """Re-run the verified save for the current draft; returns (level, message)."""
    from composition_save_verification import save_feedback
    from composition_workspace_state_persistence import checkpoint_composition_workspace

    result = checkpoint_composition_workspace(session, reason="composer_edit", force_disk=True, st=st)
    return save_feedback(result or {})
