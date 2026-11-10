"""Durable upload recording storage — local workspace files + Supabase Storage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from media_state import migrate_uploaded_recording

DEFAULT_BUCKET = "music-media"
MAX_RECORDING_BYTES = 50 * 1024 * 1024
PLAYBACK_PLAYABLE = "playable"
PLAYBACK_METADATA_ONLY = "metadata_only"
PLAYBACK_MISSING_FILE = "missing_file"
PLAYBACK_UPLOAD_FAILED = "upload_failed"
_MEDIA_EGRESS_KEY = "_media_storage_egress"


def _egress_bucket(st: Any | None) -> dict[str, Any]:
    if st is None:
        return {}
    try:
        ss = st.session_state if hasattr(st, "session_state") else st
        if not isinstance(ss, dict):
            return {}
        raw = ss.get(_MEDIA_EGRESS_KEY)
        if isinstance(raw, dict):
            return raw
        bucket: dict[str, Any] = {
            "cloud_downloads": 0,
            "downloaded_bytes": 0,
            "cache_hits": 0,
        }
        ss[_MEDIA_EGRESS_KEY] = bucket
        return bucket
    except Exception:
        return {}


def record_cache_hit(*, st: Any | None = None, bytes_count: int = 0) -> None:
    bucket = _egress_bucket(st)
    if bucket:
        bucket["cache_hits"] = int(bucket.get("cache_hits") or 0) + 1


def record_cloud_download(*, st: Any | None = None, bytes_count: int = 0) -> None:
    bucket = _egress_bucket(st)
    if bucket:
        bucket["cloud_downloads"] = int(bucket.get("cloud_downloads") or 0) + 1
        bucket["downloaded_bytes"] = int(bucket.get("downloaded_bytes") or 0) + max(0, int(bytes_count))


def get_media_egress_stats(*, st: Any | None = None) -> dict[str, Any]:
    bucket = _egress_bucket(st)
    return {
        "cloud_downloads": int(bucket.get("cloud_downloads") or 0),
        "downloaded_bytes": int(bucket.get("downloaded_bytes") or 0),
        "cache_hits": int(bucket.get("cache_hits") or 0),
    }


def _resolve_workspace_id(*, st: Any | None = None) -> str:
    try:
        from suite_workspace import resolve_workspace_id

        return resolve_workspace_id(st=st)
    except Exception:
        return "daniel"


def _resolve_user_id() -> str:
    try:
        from suite_user import get_account_user_id

        uid = str(get_account_user_id() or "").strip()
        return uid or "local"
    except Exception:
        return "local"


def _media_bucket() -> str:
    try:
        import streamlit as st  # noqa: WPS433

        block = st.secrets.get("suite_activity") if hasattr(st, "secrets") else None
        if block is not None:
            name = str(getattr(block, "media_storage_bucket", None) or block.get("media_storage_bucket") or "").strip()
            if name:
                return name
    except Exception:
        pass
    return os.environ.get("MUSIC_MEDIA_STORAGE_BUCKET", DEFAULT_BUCKET).strip() or DEFAULT_BUCKET


def _recording_extension(filename: str, mime_type: str = "") -> str:
    name = str(filename or "").strip().lower()
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".mp4"):
        if name.endswith(ext):
            return ext
    mime = str(mime_type or "").strip().lower()
    if "mpeg" in mime or mime == "audio/mp3":
        return ".mp3"
    if "mp4" in mime or "m4a" in mime:
        return ".m4a"
    if "ogg" in mime:
        return ".ogg"
    return ".wav"


def recording_media_relpath(recording_id: str, *, filename: str = "", mime_type: str = "") -> str:
    ext = _recording_extension(filename, mime_type)
    rid = str(recording_id or "").strip()
    return f"media/recordings/{rid}{ext}"


def tone_take_media_relpath(tone_take_id: str, *, filename: str = "", mime_type: str = "") -> str:
    ext = _recording_extension(filename, mime_type)
    tid = str(tone_take_id or "").strip()
    return f"media/tone_takes/{tid}{ext}"


def build_tone_take_object_key(
    user_id: str,
    workspace_id: str,
    tone_take_id: str,
    *,
    filename: str = "",
    mime_type: str = "",
) -> str:
    ext = _recording_extension(filename, mime_type)
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    tid = str(tone_take_id or "").strip()
    return f"{uid}/{ws}/tone_takes/{tid}{ext}"


def mix_export_media_relpath(export_id: str, *, filename: str = "", mime_type: str = "") -> str:
    ext = _recording_extension(filename, mime_type)
    eid = str(export_id or "").strip()
    return f"media/multitrack_exports/{eid}{ext}"


def build_mix_export_object_key(
    user_id: str,
    workspace_id: str,
    export_id: str,
    *,
    filename: str = "",
    mime_type: str = "",
) -> str:
    ext = _recording_extension(filename, mime_type)
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    eid = str(export_id or "").strip()
    return f"{uid}/{ws}/multitrack_exports/{eid}{ext}"


def song_document_relpath(document_id: str) -> str:
    """Where a document's bytes live inside the workspace folder.

    Always ``.pdf``: the extension comes from the validated content, never from the name
    the browser sent, so an uploaded "lick.pdf.exe" cannot choose its own path.
    """
    return f"media/song_documents/{str(document_id or '').strip()}.pdf"


def song_document_local_path(workspace_id: str, rel_path: str) -> Path | None:
    """The document's file, or ``None`` if the row points outside the workspace.

    ``recording_local_abs_path`` only strips a leading slash, so a relative path holding
    ``..`` resolves outside the workspace folder entirely. Nothing the app writes ever
    contains one - the name is built from a generated id - but a catalog row is data,
    and data that has been edited, synced from elsewhere or corrupted must not be able
    to name an arbitrary file on disk. Resolved and checked, every read.
    """
    rel = str(rel_path or "").strip()
    if not rel:
        return None
    base = recording_local_abs_path(workspace_id, "media/song_documents")
    path = recording_local_abs_path(workspace_id, rel)
    try:
        resolved = path.resolve()
        root = base.resolve()
    except Exception:
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def build_song_document_object_key(user_id: str, workspace_id: str, document_id: str) -> str:
    """The private object key, scoped by user and workspace exactly like recordings."""
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    did = str(document_id or "").strip()
    return f"{uid}/{ws}/song_documents/{did}.pdf"


def song_document_key_belongs_to(storage_ref: str, user_id: str, workspace_id: str) -> bool:
    """Does this reference live under *this* user's and workspace's prefix?

    Checked before any download. The bucket is private and reached through a service
    client, so a row is the only way to name an object - and a row from another
    workspace, or a hand-edited one, must not be able to point this session at someone
    else's bytes.
    """
    _bucket, object_key = parse_storage_ref(storage_ref)
    if not object_key:
        return False
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    return object_key.startswith(f"{uid}/{ws}/song_documents/")


def recording_local_abs_path(workspace_id: str, rel_path: str) -> Path:
    from suite_workspace import workspace_dir

    ws = str(workspace_id or "daniel").strip() or "daniel"
    rel = str(rel_path or "").strip().lstrip("/\\")
    return workspace_dir(ws) / rel


def build_supabase_object_key(
    user_id: str,
    workspace_id: str,
    recording_id: str,
    *,
    filename: str = "",
    mime_type: str = "",
) -> str:
    ext = _recording_extension(filename, mime_type)
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    rid = str(recording_id or "").strip()
    return f"{uid}/{ws}/recordings/{rid}{ext}"


def build_storage_ref(bucket: str, object_key: str) -> str:
    b = str(bucket or DEFAULT_BUCKET).strip()
    key = str(object_key or "").strip().lstrip("/")
    return f"supabase://{b}/{key}"


def parse_storage_ref(storage_ref: str) -> tuple[str, str]:
    text = str(storage_ref or "").strip()
    if not text.startswith("supabase://"):
        return "", ""
    rest = text[len("supabase://") :]
    if "/" not in rest:
        return rest, ""
    bucket, object_key = rest.split("/", 1)
    return bucket, object_key


def _cloud_storage_enabled() -> bool:
    try:
        from studio_history_cloud import cloud_enabled

        return bool(cloud_enabled())
    except Exception:
        return False


def _service_storage_client() -> Any | None:
    try:
        from suite_storage_config import get_cloud_config

        cfg = get_cloud_config()
        if cfg is None:
            return None
        from supabase import create_client

        return create_client(cfg.url, cfg.key)
    except Exception:
        return None


def _validate_audio_bytes(audio: Any) -> tuple[bytes | None, str]:
    if not audio:
        return None, "missing_audio"
    if isinstance(audio, bytearray):
        data = bytes(audio)
    elif isinstance(audio, bytes):
        data = audio
    else:
        return None, "invalid_audio_type"
    if not data:
        return None, "empty_audio"
    if len(data) > MAX_RECORDING_BYTES:
        return None, "audio_too_large"
    return data, ""


def validate_pdf_bytes(data: Any) -> tuple[bytes | None, str]:
    """Is this really a PDF, and is it a sane size?

    The filename is not evidence - a browser will happily send "exercise.pdf" for
    anything - so the content is checked instead: the ``%PDF-`` signature every PDF
    opens with, and an ``%%EOF`` marker near the end, which a truncated or interrupted
    upload will not have. Both are cheap and neither needs a PDF library.
    """
    from upload_media import DOCUMENT_MAX_SIZE_BYTES

    if data is None or data == b"":
        return None, "missing_document"
    if isinstance(data, bytearray):
        raw = bytes(data)
    elif isinstance(data, bytes):
        raw = data
    else:
        return None, "invalid_document_type"
    if not raw:
        return None, "empty_document"
    if len(raw) > DOCUMENT_MAX_SIZE_BYTES:
        return None, "document_too_large"
    if not raw.startswith(b"%PDF-"):
        return None, "not_a_pdf"
    # The trailer is the last thing a writer emits, so its absence is the signature of a
    # file that never finished arriving. Some writers pad after it, hence the window.
    if b"%%EOF" not in raw[-2048:]:
        return None, "pdf_truncated"
    return raw, ""


def pdf_page_count(data: bytes) -> int | None:
    """A best-effort page count for the list, never a reason to reject a file.

    PyMuPDF when it is installed, because it reads the page tree rather than guessing;
    a ``/Type /Page`` scan otherwise, which is close enough for a caption and wrong for
    a document that stores its pages in an object stream.
    """
    try:
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            count = int(doc.page_count)
            if count > 0:
                return count
    except Exception:
        pass
    try:
        import re

        hits = len(re.findall(rb"/Type\s*/Page[^s]", data or b""))
        return hits or None
    except Exception:
        return None


def save_song_document_local(
    workspace_id: str,
    document_id: str,
    data: bytes,
) -> tuple[str, str]:
    """Write the PDF into the workspace folder. ``(relpath, error)``."""
    rel = song_document_relpath(document_id)
    path = recording_local_abs_path(workspace_id, rel)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        try:
            with path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        if not path.is_file() or path.stat().st_size <= 0:
            return "", "local_write_empty"
        if path.stat().st_size != len(data):
            return "", "local_write_short"
        return rel, ""
    except Exception as exc:
        return "", str(exc)


def upload_song_document_cloud(
    workspace_id: str,
    document_id: str,
    data: bytes,
    *,
    user_id: str | None = None,
) -> tuple[str, str]:
    """Upload to the private media bucket. ``(storage_ref, error)``."""
    if not _cloud_storage_enabled():
        return "", "cloud_disabled"
    client = _service_storage_client()
    if client is None:
        return "", "cloud_client_unavailable"
    bucket = _media_bucket()
    uid = user_id or _resolve_user_id()
    object_key = build_song_document_object_key(uid, workspace_id, document_id)
    try:
        storage = client.storage.from_(bucket)
        storage.upload(
            object_key,
            data,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        return build_storage_ref(bucket, object_key), ""
    except Exception as exc:
        return "", str(exc)


def download_song_document_cloud(
    storage_ref: str,
    *,
    workspace_id: str,
    user_id: str | None = None,
    st: Any | None = None,
) -> tuple[bytes | None, str]:
    """Fetch a document's bytes, but only from this user's own prefix."""
    uid = user_id or _resolve_user_id()
    if not song_document_key_belongs_to(storage_ref, uid, workspace_id):
        return None, "storage_ref_not_owned"
    return download_recording_cloud(storage_ref, st=st)


def delete_song_document_files(
    workspace_id: str,
    *,
    local_path: str = "",
    storage_ref: str = "",
    user_id: str | None = None,
) -> dict[str, str]:
    """Remove both copies. Errors are reported, never raised."""
    out: dict[str, str] = {}
    if local_path:
        out["local"] = delete_recording_local(workspace_id, local_path)
    if storage_ref:
        uid = user_id or _resolve_user_id()
        if not song_document_key_belongs_to(storage_ref, uid, workspace_id):
            out["cloud"] = "storage_ref_not_owned"
        else:
            out["cloud"] = delete_recording_cloud(storage_ref)
    return out


def persist_song_document(
    workspace_id: str,
    document_id: str,
    data: bytes,
    *,
    user_id: str | None = None,
    reuse_storage_ref: str = "",
    reuse_local_path: str = "",
) -> dict[str, Any]:
    """Store one document and say honestly where it ended up.

    ``storage_status`` is the answer to "is this really saved": ``cloud`` only once the
    upload returned, ``local_only`` when the workspace file is written but the cloud is
    off or refused, ``save_failed`` when not even that worked. The caller shows what this
    says rather than assuming success.

    ``reuse_*`` short-circuits the whole thing when an identical file (same SHA-256) is
    already stored for this workspace, so uploading the same exercise sheet to a second
    song does not write a second blob.
    """
    from media_state import (
        DOCUMENT_STORAGE_CLOUD,
        DOCUMENT_STORAGE_FAILED,
        DOCUMENT_STORAGE_LOCAL_ONLY,
    )

    if reuse_storage_ref or reuse_local_path:
        return {
            "local_path": reuse_local_path or None,
            "storage_ref": reuse_storage_ref or None,
            "storage_status": (
                DOCUMENT_STORAGE_CLOUD if reuse_storage_ref else DOCUMENT_STORAGE_LOCAL_ONLY
            ),
            "storage_error": "",
            "reused": True,
        }

    rel, local_err = save_song_document_local(workspace_id, document_id, data)
    ref, cloud_err = upload_song_document_cloud(
        workspace_id, document_id, data, user_id=user_id
    )
    if ref:
        status, error = DOCUMENT_STORAGE_CLOUD, ""
    elif rel:
        status, error = DOCUMENT_STORAGE_LOCAL_ONLY, cloud_err
    else:
        status, error = DOCUMENT_STORAGE_FAILED, local_err or cloud_err or "save_failed"
    return {
        "local_path": rel or None,
        "storage_ref": ref or None,
        "storage_status": status,
        "storage_error": error,
        "reused": False,
    }


def save_recording_local(
    workspace_id: str,
    recording_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "",
) -> tuple[str, str]:
    rel = recording_media_relpath(recording_id, filename=filename, mime_type=mime_type)
    path = recording_local_abs_path(workspace_id, rel)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        try:
            with path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        if not path.is_file() or path.stat().st_size <= 0:
            return "", "local_write_empty"
        return rel, ""
    except Exception as exc:
        return "", str(exc)


def upload_recording_cloud(
    workspace_id: str,
    recording_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    user_id: str | None = None,
) -> tuple[str, str]:
    if not _cloud_storage_enabled():
        return "", "cloud_disabled"
    client = _service_storage_client()
    if client is None:
        return "", "cloud_client_unavailable"
    bucket = _media_bucket()
    uid = user_id or _resolve_user_id()
    object_key = build_supabase_object_key(uid, workspace_id, recording_id, filename=filename, mime_type=mime_type)
    content_type = str(mime_type or "audio/wav").strip() or "audio/wav"
    try:
        storage = client.storage.from_(bucket)
        storage.upload(
            object_key,
            audio,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return build_storage_ref(bucket, object_key), ""
    except Exception as exc:
        return "", str(exc)


def download_recording_cloud(storage_ref: str, *, st: Any | None = None) -> tuple[bytes | None, str]:
    bucket, object_key = parse_storage_ref(storage_ref)
    if not bucket or not object_key:
        return None, "invalid_storage_ref"
    client = _service_storage_client()
    if client is None:
        return None, "cloud_client_unavailable"
    try:
        data = client.storage.from_(bucket).download(object_key)
        if not data:
            return None, "cloud_download_empty"
        raw = bytes(data)
        record_cloud_download(st=st, bytes_count=len(raw))
        return raw, ""
    except Exception as exc:
        return None, str(exc)


def delete_recording_cloud(storage_ref: str) -> str:
    bucket, object_key = parse_storage_ref(storage_ref)
    if not bucket or not object_key:
        return ""
    client = _service_storage_client()
    if client is None:
        return "cloud_client_unavailable"
    try:
        client.storage.from_(bucket).remove([object_key])
        return ""
    except Exception as exc:
        return str(exc)


def delete_recording_local(workspace_id: str, rel_path: str) -> str:
    rel = str(rel_path or "").strip()
    if not rel:
        return ""
    path = recording_local_abs_path(workspace_id, rel)
    try:
        if path.is_file():
            path.unlink()
        return ""
    except Exception as exc:
        return str(exc)


def persist_recording_audio(
    st: Any | None,
    recording_id: str,
    audio: Any,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Save audio locally and to Supabase Storage when cloud is enabled."""
    rid = str(recording_id or "").strip()
    ws = str(workspace_id or _resolve_workspace_id(st=st)).strip() or "daniel"
    data, audio_err = _validate_audio_bytes(audio)
    if not rid:
        return {"ok": False, "error": "missing_recording_id", "playback_status": PLAYBACK_UPLOAD_FAILED}
    if audio_err or data is None:
        return {
            "ok": False,
            "error": audio_err or "missing_audio",
            "playback_status": PLAYBACK_METADATA_ONLY,
        }

    local_path, local_err = save_recording_local(ws, rid, data, filename=filename, mime_type=mime_type)
    storage_ref, cloud_err = upload_recording_cloud(
        ws,
        rid,
        data,
        filename=filename,
        mime_type=mime_type,
    )

    local_ok = bool(local_path) and not local_err
    cloud_ok = bool(storage_ref) and not cloud_err

    if local_ok or cloud_ok:
        status = PLAYBACK_PLAYABLE
        ok = True
        err = cloud_err if not cloud_ok and _cloud_storage_enabled() else ""
    else:
        status = PLAYBACK_UPLOAD_FAILED
        ok = False
        err = local_err or cloud_err or "persist_failed"

    return {
        "ok": ok,
        "local_path": local_path or None,
        "storage_ref": storage_ref or None,
        "local_ok": local_ok,
        "cloud_ok": cloud_ok,
        "local_error": local_err or None,
        "cloud_error": cloud_err or None,
        "storage_error": err or None,
        "playback_status": status,
    }


def save_tone_take_local(
    workspace_id: str,
    tone_take_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "",
) -> tuple[str, str]:
    rel = tone_take_media_relpath(tone_take_id, filename=filename, mime_type=mime_type)
    path = recording_local_abs_path(workspace_id, rel)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        try:
            with path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        if not path.is_file() or path.stat().st_size <= 0:
            return "", "local_write_empty"
        return rel, ""
    except Exception as exc:
        return "", str(exc)


def upload_tone_take_cloud(
    workspace_id: str,
    tone_take_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    user_id: str | None = None,
) -> tuple[str, str]:
    if not _cloud_storage_enabled():
        return "", "cloud_disabled"
    client = _service_storage_client()
    if client is None:
        return "", "cloud_client_unavailable"
    bucket = _media_bucket()
    uid = user_id or _resolve_user_id()
    object_key = build_tone_take_object_key(uid, workspace_id, tone_take_id, filename=filename, mime_type=mime_type)
    content_type = str(mime_type or "audio/wav").strip() or "audio/wav"
    try:
        storage = client.storage.from_(bucket)
        storage.upload(
            object_key,
            audio,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return build_storage_ref(bucket, object_key), ""
    except Exception as exc:
        return "", str(exc)


def persist_tone_take_audio(
    st: Any | None,
    tone_take_id: str,
    audio: Any,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Save tone take audio locally and to Supabase Storage when cloud is enabled."""
    tid = str(tone_take_id or "").strip()
    ws = str(workspace_id or _resolve_workspace_id(st=st)).strip() or "daniel"
    data, audio_err = _validate_audio_bytes(audio)
    if not tid:
        return {"ok": False, "error": "missing_tone_take_id", "playback_status": PLAYBACK_UPLOAD_FAILED}
    if audio_err or data is None:
        return {
            "ok": False,
            "error": audio_err or "missing_audio",
            "playback_status": PLAYBACK_METADATA_ONLY,
        }

    local_path, local_err = save_tone_take_local(ws, tid, data, filename=filename, mime_type=mime_type)
    storage_ref, cloud_err = upload_tone_take_cloud(
        ws,
        tid,
        data,
        filename=filename,
        mime_type=mime_type,
    )

    local_ok = bool(local_path) and not local_err
    cloud_ok = bool(storage_ref) and not cloud_err

    if local_ok or cloud_ok:
        status = PLAYBACK_PLAYABLE
        ok = True
        err = cloud_err if not cloud_ok and _cloud_storage_enabled() else ""
    else:
        status = PLAYBACK_UPLOAD_FAILED
        ok = False
        err = local_err or cloud_err or "persist_failed"

    return {
        "ok": ok,
        "local_path": local_path or None,
        "storage_ref": storage_ref or None,
        "local_ok": local_ok,
        "cloud_ok": cloud_ok,
        "local_error": local_err or None,
        "cloud_error": cloud_err or None,
        "storage_error": err or None,
        "playback_status": status,
    }


def _tone_take_workspace(tone_take: dict[str, Any]) -> str:
    from media_state import migrate_tone_take

    row = migrate_tone_take(tone_take)
    return str(row.get("workspace_id") or "daniel").strip() or "daniel"


def load_tone_take_audio(tone_take: dict[str, Any], *, st: Any | None = None) -> tuple[bytes | None, str]:
    """Resolve playable bytes for a tone take (lazy load — local first, then cloud)."""
    from media_state import migrate_tone_take

    row = migrate_tone_take(tone_take)
    current_ws = _resolve_workspace_id(st=st)
    take_ws = _tone_take_workspace(row)
    if take_ws != current_ws:
        return None, "workspace_mismatch"

    local_path = str(row.get("local_path") or "").strip()
    if local_path:
        path = recording_local_abs_path(take_ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            try:
                data = path.read_bytes()
                record_cache_hit(st=st, bytes_count=len(data))
                return data, ""
            except Exception:
                pass

    storage_ref = str(row.get("storage_ref") or "").strip()
    if storage_ref:
        data, err = download_recording_cloud(storage_ref, st=st)
        if data:
            if local_path and not recording_local_abs_path(take_ws, local_path).is_file():
                save_tone_take_local(
                    take_ws,
                    str(row.get("tone_take_id") or ""),
                    data,
                    filename="",
                    mime_type=str(row.get("mime_type") or ""),
                )
            return data, ""
        if not local_path:
            return None, err or "missing_file"

    if local_path or storage_ref:
        return None, "missing_file"
    return None, "metadata_only"


def delete_tone_take_files(tone_take: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    from media_state import migrate_tone_take

    row = migrate_tone_take(tone_take)
    ws = _tone_take_workspace(row)
    local_path = str(row.get("local_path") or "").strip()
    storage_ref = str(row.get("storage_ref") or "").strip()
    return {
        "local_error": delete_recording_local(ws, local_path) if local_path else "",
        "cloud_error": delete_recording_cloud(storage_ref) if storage_ref else "",
    }


def save_mix_export_local(
    workspace_id: str,
    export_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "",
) -> tuple[str, str]:
    rel = mix_export_media_relpath(export_id, filename=filename, mime_type=mime_type)
    path = recording_local_abs_path(workspace_id, rel)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        try:
            with path.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            pass
        if not path.is_file() or path.stat().st_size <= 0:
            return "", "local_write_empty"
        return rel, ""
    except Exception as exc:
        return "", str(exc)


def upload_mix_export_cloud(
    workspace_id: str,
    export_id: str,
    audio: bytes,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    user_id: str | None = None,
) -> tuple[str, str]:
    if not _cloud_storage_enabled():
        return "", "cloud_disabled"
    client = _service_storage_client()
    if client is None:
        return "", "cloud_client_unavailable"
    bucket = _media_bucket()
    uid = user_id or _resolve_user_id()
    object_key = build_mix_export_object_key(uid, workspace_id, export_id, filename=filename, mime_type=mime_type)
    content_type = str(mime_type or "audio/wav").strip() or "audio/wav"
    try:
        storage = client.storage.from_(bucket)
        storage.upload(
            object_key,
            audio,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return build_storage_ref(bucket, object_key), ""
    except Exception as exc:
        return "", str(exc)


def persist_mix_export_audio(
    st: Any | None,
    export_id: str,
    audio: Any,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    workspace_id: str | None = None,
) -> dict[str, Any]:
    eid = str(export_id or "").strip()
    ws = str(workspace_id or _resolve_workspace_id(st=st)).strip() or "daniel"
    data, audio_err = _validate_audio_bytes(audio)
    if not eid:
        return {"ok": False, "error": "missing_export_id", "playback_status": PLAYBACK_UPLOAD_FAILED}
    if audio_err or data is None:
        return {
            "ok": False,
            "error": audio_err or "missing_audio",
            "playback_status": PLAYBACK_METADATA_ONLY,
        }

    local_path, local_err = save_mix_export_local(ws, eid, data, filename=filename, mime_type=mime_type)
    storage_ref, cloud_err = upload_mix_export_cloud(
        ws,
        eid,
        data,
        filename=filename,
        mime_type=mime_type,
    )

    local_ok = bool(local_path) and not local_err
    cloud_ok = bool(storage_ref) and not cloud_err
    if local_ok or cloud_ok:
        status = PLAYBACK_PLAYABLE
        ok = True
        err = cloud_err if not cloud_ok and _cloud_storage_enabled() else ""
    else:
        status = PLAYBACK_UPLOAD_FAILED
        ok = False
        err = local_err or cloud_err or "persist_failed"

    return {
        "ok": ok,
        "local_path": local_path or None,
        "storage_ref": storage_ref or None,
        "local_ok": local_ok,
        "cloud_ok": cloud_ok,
        "local_error": local_err or None,
        "cloud_error": cloud_err or None,
        "storage_error": err or None,
        "playback_status": status,
    }


def _mix_export_workspace(export_row: dict[str, Any]) -> str:
    from media_state import migrate_multitrack_export

    row = migrate_multitrack_export(export_row)
    return str(row.get("workspace_id") or "daniel").strip() or "daniel"


def load_mix_export_audio(export_row: dict[str, Any], *, st: Any | None = None) -> tuple[bytes | None, str]:
    from media_state import migrate_multitrack_export

    row = migrate_multitrack_export(export_row)
    current_ws = _resolve_workspace_id(st=st)
    export_ws = _mix_export_workspace(row)
    if export_ws != current_ws:
        return None, "workspace_mismatch"

    local_path = str(row.get("local_path") or "").strip()
    if local_path:
        path = recording_local_abs_path(export_ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            try:
                data = path.read_bytes()
                record_cache_hit(st=st, bytes_count=len(data))
                return data, ""
            except Exception:
                pass

    storage_ref = str(row.get("storage_ref") or "").strip()
    if storage_ref:
        data, err = download_recording_cloud(storage_ref, st=st)
        if data:
            if local_path and not recording_local_abs_path(export_ws, local_path).is_file():
                save_mix_export_local(
                    export_ws,
                    str(row.get("export_id") or ""),
                    data,
                    filename=f"{row.get('export_name') or 'export'}.wav",
                    mime_type="audio/wav",
                )
            return data, ""
        if not local_path:
            return None, err or "missing_file"

    if local_path or storage_ref:
        return None, "missing_file"
    return None, "metadata_only"


def mix_export_playback_status(export_row: dict[str, Any], *, st: Any | None = None) -> str:
    from media_state import migrate_multitrack_export

    row = migrate_multitrack_export(export_row)
    if row.get("deleted"):
        return PLAYBACK_METADATA_ONLY
    local_path = str(row.get("local_path") or "").strip()
    storage_ref = str(row.get("storage_ref") or "").strip()
    if not local_path and not storage_ref:
        cached = str(row.get("playback_status") or "").strip()
        if cached == PLAYBACK_UPLOAD_FAILED:
            return PLAYBACK_UPLOAD_FAILED
        return PLAYBACK_METADATA_ONLY

    ws = _mix_export_workspace(row)
    if local_path:
        path = recording_local_abs_path(ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            return PLAYBACK_PLAYABLE
    if storage_ref and _cloud_storage_enabled():
        return PLAYBACK_PLAYABLE
    if storage_ref or local_path:
        return PLAYBACK_METADATA_ONLY
    return PLAYBACK_METADATA_ONLY


def delete_mix_export_files(export_row: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    from media_state import migrate_multitrack_export

    row = migrate_multitrack_export(export_row)
    ws = _mix_export_workspace(row)
    local_path = str(row.get("local_path") or "").strip()
    storage_ref = str(row.get("storage_ref") or "").strip()
    return {
        "local_error": delete_recording_local(ws, local_path) if local_path else "",
        "cloud_error": delete_recording_cloud(storage_ref) if storage_ref else "",
    }


def tone_take_playback_status(tone_take: dict[str, Any], *, st: Any | None = None) -> str:
    from media_state import migrate_tone_take

    row = migrate_tone_take(tone_take)
    if row.get("deleted"):
        return PLAYBACK_METADATA_ONLY
    local_path = str(row.get("local_path") or "").strip()
    storage_ref = str(row.get("storage_ref") or "").strip()
    if not local_path and not storage_ref:
        cached = str(row.get("playback_status") or "").strip()
        if cached == PLAYBACK_UPLOAD_FAILED:
            return PLAYBACK_UPLOAD_FAILED
        return PLAYBACK_METADATA_ONLY

    ws = _tone_take_workspace(row)
    if local_path:
        path = recording_local_abs_path(ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            return PLAYBACK_PLAYABLE
    if storage_ref and _cloud_storage_enabled():
        return PLAYBACK_PLAYABLE
    if storage_ref or local_path:
        return PLAYBACK_METADATA_ONLY
    return PLAYBACK_METADATA_ONLY


def _recording_workspace(recording: dict[str, Any]) -> str:
    row = migrate_uploaded_recording(recording)
    return str(row.get("workspace_id") or "daniel").strip() or "daniel"


def load_recording_audio(recording: dict[str, Any], *, st: Any | None = None) -> tuple[bytes | None, str]:
    """Resolve playable bytes from local_path and/or storage_ref (workspace-scoped)."""
    row = migrate_uploaded_recording(recording)
    current_ws = _resolve_workspace_id(st=st)
    rec_ws = _recording_workspace(row)
    if rec_ws != current_ws:
        return None, "workspace_mismatch"

    local_path = str(row.get("local_path") or "").strip()
    if local_path:
        path = recording_local_abs_path(rec_ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            try:
                data = path.read_bytes()
                record_cache_hit(st=st, bytes_count=len(data))
                return data, ""
            except Exception:
                pass

    storage_ref = str(row.get("storage_ref") or "").strip()
    if storage_ref:
        data, err = download_recording_cloud(storage_ref, st=st)
        if data:
            if local_path and not recording_local_abs_path(rec_ws, local_path).is_file():
                save_recording_local(
                    rec_ws,
                    str(row.get("recording_id") or ""),
                    data,
                    filename=str(row.get("filename") or ""),
                    mime_type=str(row.get("mime_type") or ""),
                )
            return data, ""
        if not local_path:
            return None, err or "missing_file"

    if local_path or storage_ref:
        return None, "missing_file"
    return None, "metadata_only"


def recording_playback_status(recording: dict[str, Any], *, st: Any | None = None) -> str:
    row = migrate_uploaded_recording(recording)
    if row.get("deleted"):
        return PLAYBACK_METADATA_ONLY
    local_path = str(row.get("local_path") or "").strip()
    storage_ref = str(row.get("storage_ref") or "").strip()
    if not local_path and not storage_ref:
        cached = str(row.get("playback_status") or "").strip()
        if cached == PLAYBACK_UPLOAD_FAILED:
            return PLAYBACK_UPLOAD_FAILED
        return PLAYBACK_METADATA_ONLY

    current_ws = _resolve_workspace_id(st=st)
    if _recording_workspace(row) != current_ws:
        return PLAYBACK_MISSING_FILE

    if local_path:
        path = recording_local_abs_path(_recording_workspace(row), local_path)
        if path.is_file() and path.stat().st_size > 0:
            return PLAYBACK_PLAYABLE

    if storage_ref:
        return PLAYBACK_PLAYABLE if _cloud_storage_enabled() else PLAYBACK_MISSING_FILE

    return PLAYBACK_MISSING_FILE


def track_media_relpath(
    multitrack_id: str,
    track_id: str,
    *,
    filename: str = "",
    mime_type: str = "",
) -> str:
    ext = _recording_extension(filename, mime_type)
    mid = str(multitrack_id or "").strip()
    tid = str(track_id or "").strip()
    return f"media/multitrack/{mid}/{tid}{ext}"


def backing_media_relpath(multitrack_id: str) -> str:
    mid = str(multitrack_id or "").strip()
    return f"media/multitrack/{mid}/backing.wav"


def build_backing_supabase_object_key(
    user_id: str,
    workspace_id: str,
    multitrack_id: str,
) -> str:
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    mid = str(multitrack_id or "").strip()
    return f"{uid}/{ws}/multitrack/{mid}/backing.wav"


def build_track_supabase_object_key(
    user_id: str,
    workspace_id: str,
    multitrack_id: str,
    track_id: str,
    *,
    filename: str = "",
    mime_type: str = "",
) -> str:
    ext = _recording_extension(filename, mime_type)
    uid = str(user_id or "local").strip() or "local"
    ws = str(workspace_id or "daniel").strip() or "daniel"
    mid = str(multitrack_id or "").strip()
    tid = str(track_id or "").strip()
    return f"{uid}/{ws}/multitrack/{mid}/{tid}{ext}"


def persist_track_audio(
    st: Any | None,
    multitrack_id: str,
    track_id: str,
    audio: Any,
    *,
    filename: str = "",
    mime_type: str = "audio/wav",
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Save multitrack layer audio locally + cloud (same bucket as uploads)."""
    mid = str(multitrack_id or "").strip()
    tid = str(track_id or "").strip()
    ws = str(workspace_id or _resolve_workspace_id(st=st)).strip() or "daniel"
    data, audio_err = _validate_audio_bytes(audio)
    if not mid or not tid:
        return {"ok": False, "error": "missing_ids", "playback_status": PLAYBACK_UPLOAD_FAILED}
    if audio_err or data is None:
        return {
            "ok": False,
            "error": audio_err or "missing_audio",
            "playback_status": PLAYBACK_METADATA_ONLY,
        }

    rel = track_media_relpath(mid, tid, filename=filename, mime_type=mime_type)
    path = recording_local_abs_path(ws, rel)
    local_err = ""
    local_ok = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        local_ok = path.is_file() and path.stat().st_size > 0
    except Exception as exc:
        local_err = str(exc)

    storage_ref = ""
    cloud_err = ""
    if _cloud_storage_enabled():
        client = _service_storage_client()
        if client is None:
            cloud_err = "cloud_client_unavailable"
        else:
            bucket = _media_bucket()
            object_key = build_track_supabase_object_key(
                _resolve_user_id(),
                ws,
                mid,
                tid,
                filename=filename,
                mime_type=mime_type,
            )
            try:
                client.storage.from_(bucket).upload(
                    object_key,
                    data,
                    file_options={"content-type": mime_type or "audio/wav", "upsert": "true"},
                )
                storage_ref = build_storage_ref(bucket, object_key)
            except Exception as exc:
                cloud_err = str(exc)

    if local_ok or storage_ref:
        return {
            "ok": True,
            "local_path": rel if local_ok else None,
            "storage_ref": storage_ref or None,
            "local_ok": local_ok,
            "cloud_ok": bool(storage_ref),
            "local_error": local_err or None,
            "cloud_error": cloud_err or None,
            "playback_status": PLAYBACK_PLAYABLE,
        }
    return {
        "ok": False,
        "error": local_err or cloud_err or "persist_failed",
        "playback_status": PLAYBACK_UPLOAD_FAILED,
        "storage_error": local_err or cloud_err,
    }


def persist_backing_audio(
    st: Any | None,
    multitrack_id: str,
    audio: Any,
    *,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Save prepared monitor backing locally + cloud (same bucket as track layers)."""
    mid = str(multitrack_id or "").strip()
    ws = str(workspace_id or _resolve_workspace_id(st=st)).strip() or "daniel"
    data, audio_err = _validate_audio_bytes(audio)
    if not mid:
        return {"ok": False, "error": "missing_multitrack_id", "playback_status": PLAYBACK_UPLOAD_FAILED}
    if audio_err or data is None:
        return {
            "ok": False,
            "error": audio_err or "missing_audio",
            "playback_status": PLAYBACK_METADATA_ONLY,
        }

    rel = backing_media_relpath(mid)
    path = recording_local_abs_path(ws, rel)
    local_err = ""
    local_ok = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        local_ok = path.is_file() and path.stat().st_size > 0
    except Exception as exc:
        local_err = str(exc)

    storage_ref = ""
    cloud_err = ""
    if _cloud_storage_enabled():
        client = _service_storage_client()
        if client is None:
            cloud_err = "cloud_client_unavailable"
        else:
            bucket = _media_bucket()
            object_key = build_backing_supabase_object_key(_resolve_user_id(), ws, mid)
            try:
                client.storage.from_(bucket).upload(
                    object_key,
                    data,
                    file_options={"content-type": "audio/wav", "upsert": "true"},
                )
                storage_ref = build_storage_ref(bucket, object_key)
            except Exception as exc:
                cloud_err = str(exc)

    if local_ok or storage_ref:
        return {
            "ok": True,
            "local_path": rel if local_ok else None,
            "storage_ref": storage_ref or None,
            "local_ok": local_ok,
            "cloud_ok": bool(storage_ref),
            "local_error": local_err or None,
            "cloud_error": cloud_err or None,
            "playback_status": PLAYBACK_PLAYABLE,
        }
    return {
        "ok": False,
        "error": local_err or cloud_err or "persist_failed",
        "playback_status": PLAYBACK_UPLOAD_FAILED,
        "storage_error": local_err or cloud_err,
    }


def backing_playback_status(
    session: dict[str, Any],
    *,
    session_workspace: str = "",
    st: Any | None = None,
) -> str:
    ws = str(session_workspace or session.get("workspace_id") or _resolve_workspace_id(st=st)).strip() or "daniel"
    local_path = str(session.get("backing_local_path") or "").strip()
    storage_ref = str(session.get("backing_storage_ref") or "").strip()
    if local_path and _track_local_exists(ws, local_path):
        return PLAYBACK_PLAYABLE
    if storage_ref:
        return PLAYBACK_PLAYABLE
    if local_path or storage_ref or session.get("backing_prepared_at"):
        return PLAYBACK_METADATA_ONLY
    return ""


def load_backing_audio(
    session: dict[str, Any],
    *,
    st: Any | None = None,
) -> tuple[bytes | None, str]:
    ws = str(session.get("workspace_id") or _resolve_workspace_id(st=st)).strip() or "daniel"
    local_path = str(session.get("backing_local_path") or "").strip()
    storage_ref = str(session.get("backing_storage_ref") or "").strip()

    if local_path:
        path = recording_local_abs_path(ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            record_cache_hit(st=st, bytes_count=path.stat().st_size)
            return path.read_bytes(), ""

    if storage_ref:
        data, err = download_recording_cloud(storage_ref, st=st)
        if data:
            if local_path:
                try:
                    path = recording_local_abs_path(ws, local_path)
                    if not path.is_file():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                except Exception:
                    pass
            elif session.get("multitrack_id"):
                rel = backing_media_relpath(str(session.get("multitrack_id")))
                try:
                    path = recording_local_abs_path(ws, rel)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                except Exception:
                    pass
            return data, ""
        return None, err or "missing_file"

    if local_path or storage_ref:
        return None, "missing_file"
    return None, "metadata_only"


def _track_local_exists(workspace_id: str, local_path: str) -> bool:
    rel = str(local_path or "").strip()
    if not rel:
        return False
    path = recording_local_abs_path(workspace_id, rel)
    return path.is_file() and path.stat().st_size > 0


def track_playback_status(
    track: dict[str, Any],
    *,
    session_workspace: str = "",
    st: Any | None = None,
) -> str:
    """Status check without cloud download (egress-safe)."""
    if track.get("deleted"):
        return PLAYBACK_METADATA_ONLY
    local_path = str(track.get("local_path") or "").strip()
    storage_ref = str(track.get("storage_ref") or "").strip()
    if not local_path and not storage_ref:
        cached = str(track.get("playback_status") or "").strip()
        if cached == PLAYBACK_UPLOAD_FAILED:
            return PLAYBACK_UPLOAD_FAILED
        summary = track.get("analysis_summary") if isinstance(track.get("analysis_summary"), dict) else {}
        if summary.get("has_audio"):
            return PLAYBACK_METADATA_ONLY
        return ""

    ws = str(session_workspace or _resolve_workspace_id(st=st)).strip() or "daniel"
    current_ws = _resolve_workspace_id(st=st)
    if ws != current_ws:
        return PLAYBACK_MISSING_FILE

    if _track_local_exists(ws, local_path):
        return PLAYBACK_PLAYABLE
    if storage_ref:
        return PLAYBACK_PLAYABLE if _cloud_storage_enabled() else PLAYBACK_MISSING_FILE
    return PLAYBACK_MISSING_FILE


def load_track_audio(
    track: dict[str, Any],
    *,
    session: dict[str, Any] | None = None,
    st: Any | None = None,
) -> tuple[bytes | None, str]:
    """Lazy resolve track bytes — local first, then cloud download + cache."""
    sess = session if isinstance(session, dict) else {}
    ws = str(sess.get("workspace_id") or _resolve_workspace_id(st=st)).strip() or "daniel"
    current_ws = _resolve_workspace_id(st=st)
    if ws != current_ws:
        return None, "workspace_mismatch"

    local_path = str(track.get("local_path") or "").strip()
    if local_path:
        path = recording_local_abs_path(ws, local_path)
        if path.is_file() and path.stat().st_size > 0:
            try:
                data = path.read_bytes()
                record_cache_hit(st=st, bytes_count=len(data))
                return data, ""
            except Exception:
                pass

    storage_ref = str(track.get("storage_ref") or "").strip()
    if storage_ref:
        data, err = download_recording_cloud(storage_ref, st=st)
        if data:
            if local_path:
                try:
                    path = recording_local_abs_path(ws, local_path)
                    if not path.is_file():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                except Exception:
                    pass
            elif sess.get("multitrack_id") and track.get("track_id"):
                rel = track_media_relpath(
                    str(sess.get("multitrack_id")),
                    str(track.get("track_id")),
                    filename=str(track.get("name") or ""),
                )
                try:
                    path = recording_local_abs_path(ws, rel)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                except Exception:
                    pass
            return data, ""
        return None, err or "missing_file"

    if local_path or storage_ref:
        return None, "missing_file"
    return None, "metadata_only"


def delete_track_files(
    track: dict[str, Any],
    *,
    session_workspace: str = "",
    st: Any | None = None,
) -> dict[str, str]:
    ws = str(session_workspace or _resolve_workspace_id(st=st)).strip() or "daniel"
    local_err = delete_recording_local(ws, str(track.get("local_path") or ""))
    cloud_err = delete_recording_cloud(str(track.get("storage_ref") or ""))
    return {"local_error": local_err, "cloud_error": cloud_err}


def delete_multitrack_session_files(session: dict[str, Any], *, st: Any | None = None) -> None:
    from media_state import migrate_multitrack_session

    row = migrate_multitrack_session(session)
    ws = str(row.get("workspace_id") or "daniel").strip()
    for track in row.get("tracks") or []:
        if isinstance(track, dict):
            delete_track_files(track, session_workspace=ws, st=st)
    mix_ref = str(row.get("mix_storage_ref") or "").strip()
    if mix_ref:
        delete_recording_cloud(mix_ref)
    mix_local = str(row.get("mix_local_path") or "").strip()
    if mix_local:
        delete_recording_local(ws, mix_local)
    backing_ref = str(row.get("backing_storage_ref") or "").strip()
    if backing_ref:
        delete_recording_cloud(backing_ref)
    backing_local = str(row.get("backing_local_path") or "").strip()
    if backing_local:
        delete_recording_local(ws, backing_local)


def delete_recording_files(recording: dict[str, Any], *, st: Any | None = None) -> dict[str, str]:
    row = migrate_uploaded_recording(recording)
    ws = _recording_workspace(row)
    local_err = delete_recording_local(ws, str(row.get("local_path") or ""))
    cloud_err = delete_recording_cloud(str(row.get("storage_ref") or ""))
    return {"local_error": local_err, "cloud_error": cloud_err}


def playback_status_label(status: str) -> str:
    mapping = {
        PLAYBACK_PLAYABLE: "Playable",
        PLAYBACK_METADATA_ONLY: "Metadata only",
        PLAYBACK_MISSING_FILE: "Missing file",
        PLAYBACK_UPLOAD_FAILED: "Upload failed",
    }
    return mapping.get(str(status or "").strip(), str(status or "Unknown"))
