"""My Uploaded Melodies - a musician's own PDF references, kept beside a song.

Sheet music, licks, technical exercises, handwritten pages, notes about a song. The
musician uploads them, names them, tags them and opens one while practising; the app
stores them and gives them back, and otherwise leaves them alone.

This is the layer the Practice page talks to. It owns no storage of its own: rows go
through ``media_persistence`` into the one media catalog, bytes go through
``media_storage`` into the same private workspace folder and bucket the recordings use,
and the row schema lives in ``media_state`` beside the other kinds. It is a separate
module from ``media_upload_catalog`` only because that one is the Upload-Analysis
recording layer - the storage underneath is deliberately the same.

Three things this module is careful about.

**Whose document it is.** A row is bound to ``source_type`` + ``source_id`` from
``song_coach_context.global_song_identity``, the same identity the activity reporter
uses. Two songs called "Autumn Leaves" - one from the Catalog, one the musician wrote -
are different owners and never see each other's references. Binding **fails closed**: if
the active song cannot be named with certainty, the save is refused rather than filed
against a guess.

**Whether it is really saved.** ``save_song_document`` reports ``ok`` only when the
catalog write was confirmed, and carries the storage status with it, so the Practice page
can say "saved to this device only" when the cloud is off or refused instead of a
success message that is not true.

**That a tag is not a setting.** ``key_tag`` is the musician's note about the document
("written for E flat"). Nothing here reads it back into the session, and selecting a
document cannot change the song's Practice Key.
"""

from __future__ import annotations

import hashlib
from typing import Any

__all__ = [
    "active_song_owner",
    "delete_song_document",
    "document_belongs_to_owner",
    "documents_for_active_song",
    "documents_for_owner",
    "load_song_document_bytes",
    "rename_song_document",
    "retag_song_document",
    "save_song_document",
    "summarize_document",
]


def _session(st: Any | None) -> dict[str, Any]:
    if st is None:
        return {}
    try:
        ss = st.session_state if hasattr(st, "session_state") else st
        return ss if isinstance(ss, dict) else {}
    except Exception:
        return {}


def _workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import resolve_workspace_id

        return resolve_workspace_id(st=st)
    except Exception:
        return "daniel"


def active_song_owner(session: Any, *, st: Any | None = None) -> dict[str, str]:
    """``{source_type, source_id, song_title}`` for the song on screen, or ``{}``.

    Empty means "cannot be named safely", and the caller must treat that as a refusal
    rather than a default. Copied in spirit from ``music_progress_activity._context``:
    an identity that cannot be confirmed is worse than none, because it files a private
    document against the wrong song.
    """
    sess = session if isinstance(session, dict) else _session(st)
    if not sess:
        return {}
    try:
        from song_coach_context import global_song_identity, source_owner
    except Exception:
        return {}
    try:
        owner = str(source_owner(sess) or "").strip()
        identity = str(global_song_identity(sess, owner) or "").strip()
    except Exception:
        return {}
    source, separator, pick = identity.partition("|")
    if not separator or not pick:
        return {}
    from media_state import SONG_DOCUMENT_SOURCE_TYPES

    if source not in SONG_DOCUMENT_SOURCE_TYPES or source != owner:
        return {}
    return {
        "source_type": source,
        "source_id": pick[:500],
        "song_title": _active_song_title(sess, source)[:160],
    }


def _active_song_title(session: dict[str, Any], source: str) -> str:
    """A label for the list. Never an identifier - two songs may share it."""
    try:
        from song_coach_context import _active_composition, _active_custom, live_catalog_record

        record = (
            live_catalog_record(session)
            if source == "catalog"
            else _active_custom(session)
            if source == "custom"
            else _active_composition(session)
        )
        if isinstance(record, dict):
            return str(record.get("title") or record.get("name") or "").strip()
    except Exception:
        pass
    return ""


def document_belongs_to_owner(row: dict[str, Any], owner: dict[str, str]) -> bool:
    """Both halves of the identity must match. A shared title is not a match."""
    if not isinstance(row, dict) or not owner:
        return False
    return (
        str(row.get("source_type") or "") == str(owner.get("source_type") or "")
        and str(row.get("source_id") or "") == str(owner.get("source_id") or "")
        and bool(row.get("source_id"))
    )


def documents_for_owner(owner: dict[str, str], *, st: Any | None = None) -> list[dict[str, Any]]:
    """This song's visible documents, newest first, from this workspace only."""
    if not owner:
        return []
    from media_persistence import list_song_documents

    ws = _workspace_id(st=st)
    return [
        row
        for row in list_song_documents(st=st)
        if document_belongs_to_owner(row, owner)
        and str(row.get("workspace_id") or ws) == ws
    ]


def documents_for_active_song(session: Any, *, st: Any | None = None) -> list[dict[str, Any]]:
    return documents_for_owner(active_song_owner(session, st=st), st=st)


def _existing_blob_for_hash(digest: str, *, st: Any | None = None) -> dict[str, str]:
    """A document already stored in this workspace with identical content, if any.

    The same exercise sheet saved against three songs is three rows and one blob.
    """
    if not digest:
        return {}
    from media_persistence import list_song_documents
    from media_state import DOCUMENT_STORAGE_CLOUD, DOCUMENT_STORAGE_LOCAL_ONLY

    for row in list_song_documents(st=st):
        if str(row.get("sha256") or "") != digest:
            continue
        if str(row.get("storage_status") or "") not in (
            DOCUMENT_STORAGE_CLOUD,
            DOCUMENT_STORAGE_LOCAL_ONLY,
        ):
            continue
        return {
            "storage_ref": str(row.get("storage_ref") or ""),
            "local_path": str(row.get("local_path") or ""),
        }
    return {}


def save_song_document(
    session: Any,
    data: Any,
    *,
    filename: str = "",
    title: str = "",
    instrument_tag: str = "",
    key_tag: str = "",
    notes: str = "",
    st: Any | None = None,
) -> dict[str, Any]:
    """Validate, store and record one PDF for the active song.

    Returns ``{ok, row, error, storage_status, reused}``. ``ok`` is the honest answer:
    the bytes reached durable storage *and* the catalog write was confirmed.
    """
    from media_state import DOCUMENT_STORAGE_FAILED, new_song_document_id
    from media_storage import pdf_page_count, persist_song_document, validate_pdf_bytes

    owner = active_song_owner(session, st=st)
    if not owner:
        return {
            "ok": False,
            "row": {},
            "error": "unknown_song",
            "storage_status": "",
            "reused": False,
        }

    raw, err = validate_pdf_bytes(data)
    if raw is None:
        return {
            "ok": False,
            "row": {},
            "error": err,
            "storage_status": "",
            "reused": False,
        }

    ws = _workspace_id(st=st)
    document_id = new_song_document_id()
    digest = hashlib.sha256(raw).hexdigest()
    reuse = _existing_blob_for_hash(digest, st=st)
    stored = persist_song_document(
        ws,
        document_id,
        raw,
        reuse_storage_ref=reuse.get("storage_ref", ""),
        reuse_local_path=reuse.get("local_path", ""),
    )
    if stored.get("storage_status") == DOCUMENT_STORAGE_FAILED:
        # Nothing durable exists, so there is nothing to list. Do not write a row that
        # would show the musician a document they cannot open.
        return {
            "ok": False,
            "row": {},
            "error": str(stored.get("storage_error") or "save_failed"),
            "storage_status": DOCUMENT_STORAGE_FAILED,
            "reused": False,
        }

    from media_persistence import add_song_document

    result = add_song_document(
        st,
        {
            "document_id": document_id,
            **owner,
            "title": (title or "").strip() or (filename or "").strip(),
            "filename": filename,
            "instrument_tag": instrument_tag,
            "key_tag": key_tag,
            "notes": notes,
            "mime_type": "application/pdf",
            "byte_size": len(raw),
            "page_count": pdf_page_count(raw),
            "sha256": digest,
            "local_path": stored.get("local_path"),
            "storage_ref": stored.get("storage_ref"),
            "storage_status": stored.get("storage_status"),
            "storage_error": stored.get("storage_error"),
        },
    )
    return {
        "ok": bool(result.get("ok")),
        "row": result.get("row") or {},
        "error": str(result.get("error") or ""),
        "storage_status": str(stored.get("storage_status") or ""),
        "reused": bool(stored.get("reused")),
    }


def rename_song_document(document_id: str, title: str, *, st: Any | None = None) -> dict[str, Any]:
    from media_persistence import update_song_document

    name = str(title or "").strip()
    if not name:
        return {"ok": False, "row": {}, "error": "empty_title"}
    return update_song_document(st, document_id, {"title": name})


def retag_song_document(
    document_id: str,
    *,
    instrument_tag: str | None = None,
    key_tag: str | None = None,
    notes: str | None = None,
    st: Any | None = None,
) -> dict[str, Any]:
    from media_persistence import update_song_document

    updates: dict[str, Any] = {}
    if instrument_tag is not None:
        updates["instrument_tag"] = instrument_tag
    if key_tag is not None:
        updates["key_tag"] = key_tag
    if notes is not None:
        updates["notes"] = notes
    if not updates:
        return {"ok": False, "row": {}, "error": "no_changes"}
    return update_song_document(st, document_id, updates)


def delete_song_document(document_id: str, *, st: Any | None = None) -> dict[str, Any]:
    """Tombstone the row, then remove the blob - but only if nothing else uses it."""
    from media_persistence import (
        delete_song_document as _tombstone,
        list_song_documents,
    )
    from media_storage import delete_song_document_files

    did = str(document_id or "").strip()
    rows = list_song_documents(st=st)
    row = next((r for r in rows if str(r.get("document_id") or "") == did), None)
    if row is None:
        return {"ok": False, "error": "document_not_found"}

    result = _tombstone(st, did)
    if not result.get("ok"):
        return {"ok": False, "error": str(result.get("error") or "delete_failed")}

    digest = str(row.get("sha256") or "")
    shared = any(
        str(r.get("sha256") or "") == digest and str(r.get("document_id") or "") != did
        for r in rows
        if digest
    )
    files: dict[str, str] = {}
    if not shared:
        files = delete_song_document_files(
            _workspace_id(st=st),
            local_path=str(row.get("local_path") or ""),
            storage_ref=str(row.get("storage_ref") or ""),
        )
    return {"ok": True, "error": "", "files": files, "blob_kept_for_other_rows": shared}


def load_song_document_bytes(
    document_id: str,
    *,
    session: Any = None,
    st: Any | None = None,
) -> tuple[bytes | None, str]:
    """The PDF's bytes for preview, from the local copy first, then the cloud.

    A row from another workspace is not readable here even if its id is known, and a
    storage reference outside this user's own prefix is refused before any fetch.
    """
    from media_persistence import list_song_documents
    from media_storage import (
        download_song_document_cloud,
        recording_local_abs_path,
    )

    did = str(document_id or "").strip()
    if not did:
        return None, "missing_document_id"
    ws = _workspace_id(st=st)
    row = next(
        (
            r
            for r in list_song_documents(st=st)
            if str(r.get("document_id") or "") == did
            and str(r.get("workspace_id") or ws) == ws
        ),
        None,
    )
    if row is None:
        return None, "document_not_found"

    local = str(row.get("local_path") or "")
    if local:
        try:
            path = recording_local_abs_path(ws, local)
            if path.is_file() and path.stat().st_size > 0:
                return path.read_bytes(), ""
        except Exception:
            pass

    ref = str(row.get("storage_ref") or "")
    if ref:
        data, err = download_song_document_cloud(ref, workspace_id=ws, st=st)
        if data:
            return data, ""
        return None, err or "download_failed"
    return None, "missing_file"


def summarize_document(row: dict[str, Any]) -> str:
    """One line for the picker: the name, then the tags that exist."""
    if not isinstance(row, dict):
        return ""
    bits = [str(row.get("title") or "Untitled reference")]
    tags = [
        str(row.get("instrument_tag") or "").strip(),
        str(row.get("key_tag") or "").strip(),
    ]
    tags = [t for t in tags if t]
    if tags:
        bits.append(" / ".join(tags))
    pages = row.get("page_count")
    if pages:
        bits.append(f"{int(pages)} page{'s' if int(pages) != 1 else ''}")
    return " · ".join(bits)
