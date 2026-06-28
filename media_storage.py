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


def download_recording_cloud(storage_ref: str) -> tuple[bytes | None, str]:
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
        return bytes(data), ""
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
                return path.read_bytes(), ""
            except Exception:
                pass

    storage_ref = str(row.get("storage_ref") or "").strip()
    if storage_ref:
        data, err = download_recording_cloud(storage_ref)
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
        data, err = load_recording_audio(row, st=st)
        if data:
            return PLAYBACK_PLAYABLE
        return PLAYBACK_MISSING_FILE if err in ("missing_file", "cloud_download_empty", "invalid_storage_ref") else PLAYBACK_METADATA_ONLY

    return PLAYBACK_MISSING_FILE


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
