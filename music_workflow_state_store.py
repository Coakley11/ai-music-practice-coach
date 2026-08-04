"""Authoritative workflow state store — durable blobs + single active pointer (Phase 3 Commit 1)."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

WorkflowOwner = Literal[
    "song_based_improvisation",
    "mission_jam",
    "entry_jam",
    "style_jam",
    "jam_session_generator",
    "regular_catalog_backing",
    "regular_custom_backing",
    "pending_upload_analysis",
]

WORKFLOW_STORE_SCHEMA_VERSION = 1
MUSIC_WORKFLOW_STATE_STORE_KEY = "_music_workflow_state_store"
MUSIC_ACTIVE_WORKFLOW_KEY = "_music_active_workflow"
WORKFLOW_STORE_DIAG_KEY = "_music_workflow_store_diag"
WORKFLOW_LEGACY_READS_KEY = "_music_workflow_legacy_reads_run"
WORKFLOW_COMPAT_FALLBACKS_KEY = "_music_workflow_compat_fallbacks_run"

SAVE_REASON_WORKFLOW_STATE = "music_workflow_state_save"

ALL_WORKFLOW_OWNERS: tuple[str, ...] = (
    "song_based_improvisation",
    "mission_jam",
    "entry_jam",
    "style_jam",
    "jam_session_generator",
    "regular_catalog_backing",
    "regular_custom_backing",
    "pending_upload_analysis",
)


@dataclass
class KeyAuthority:
    original_tonic: str = "C"
    original_mode: str = "major"
    practice_tonic: str = "C"
    practice_mode: str = "major"
    written_tonic: str = ""
    written_mode: str = ""
    instrument: str = ""
    transposition: str = ""
    key_owner: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> KeyAuthority:
        if not isinstance(raw, dict):
            return cls()
        return cls(
            original_tonic=str(raw.get("original_tonic") or "C"),
            original_mode=str(raw.get("original_mode") or "major"),
            practice_tonic=str(raw.get("practice_tonic") or "C"),
            practice_mode=str(raw.get("practice_mode") or "major"),
            written_tonic=str(raw.get("written_tonic") or ""),
            written_mode=str(raw.get("written_mode") or ""),
            instrument=str(raw.get("instrument") or ""),
            transposition=str(raw.get("transposition") or ""),
            key_owner=str(raw.get("key_owner") or ""),
        )


@dataclass
class WorkflowStateBlob:
    schema_version: int = WORKFLOW_STORE_SCHEMA_VERSION
    workflow_owner: str = ""
    workflow_session_id: str = ""
    context_revision: int = 0
    source_type: str = ""
    song_id: str = ""
    song_title: str = ""
    generated_session_id: str = ""
    keys: KeyAuthority = field(default_factory=KeyAuthority)
    section_map: dict[str, list[str]] = field(default_factory=dict)
    progression: list[str] = field(default_factory=list)
    selected_section: str = ""
    selected_chord_index: int = 0
    selected_chord_symbol: str = ""
    mission_type: str = ""
    mission_id: str = ""
    artifact_fingerprint: str = ""
    example_fingerprint: str = ""
    backing_handoff_chord: str = ""
    recording_seal_chord: str = ""
    style: str = ""
    mood: str = ""
    groove: str = ""
    tempo_bpm: int = 0
    meter: str = "4/4"
    playback_scope: str = ""
    style_owner: str = ""
    progression_owner: str = ""
    page_route: str = ""
    return_route: str = ""
    pending_analysis_take_id: str = ""
    material_fingerprint: str = ""
    updated_at_seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["keys"] = self.keys.to_dict()
        return d

    @classmethod
    def from_dict(cls, raw: Any) -> WorkflowStateBlob | None:
        if not isinstance(raw, dict):
            return None
        keys = KeyAuthority.from_dict(raw.get("keys"))
        return cls(
            schema_version=int(raw.get("schema_version") or WORKFLOW_STORE_SCHEMA_VERSION),
            workflow_owner=str(raw.get("workflow_owner") or ""),
            workflow_session_id=str(raw.get("workflow_session_id") or ""),
            context_revision=int(raw.get("context_revision") or 0),
            source_type=str(raw.get("source_type") or ""),
            song_id=str(raw.get("song_id") or ""),
            song_title=str(raw.get("song_title") or ""),
            generated_session_id=str(raw.get("generated_session_id") or ""),
            keys=keys,
            section_map=dict(raw.get("section_map") or {}),
            progression=list(raw.get("progression") or []),
            selected_section=str(raw.get("selected_section") or ""),
            selected_chord_index=int(raw.get("selected_chord_index") or 0),
            selected_chord_symbol=str(raw.get("selected_chord_symbol") or ""),
            mission_type=str(raw.get("mission_type") or ""),
            mission_id=str(raw.get("mission_id") or ""),
            artifact_fingerprint=str(raw.get("artifact_fingerprint") or ""),
            example_fingerprint=str(raw.get("example_fingerprint") or ""),
            backing_handoff_chord=str(raw.get("backing_handoff_chord") or ""),
            recording_seal_chord=str(raw.get("recording_seal_chord") or ""),
            style=str(raw.get("style") or ""),
            mood=str(raw.get("mood") or ""),
            groove=str(raw.get("groove") or ""),
            tempo_bpm=int(raw.get("tempo_bpm") or 0),
            meter=str(raw.get("meter") or "4/4"),
            playback_scope=str(raw.get("playback_scope") or ""),
            style_owner=str(raw.get("style_owner") or ""),
            progression_owner=str(raw.get("progression_owner") or ""),
            page_route=str(raw.get("page_route") or ""),
            return_route=str(raw.get("return_route") or ""),
            pending_analysis_take_id=str(raw.get("pending_analysis_take_id") or ""),
            material_fingerprint=str(raw.get("material_fingerprint") or ""),
            updated_at_seq=int(raw.get("updated_at_seq") or 0),
        )


@dataclass
class ActiveWorkflowPointer:
    workflow_owner: str = ""
    workflow_session_id: str = ""
    context_revision: int = 0
    activation_source: str = ""
    activation_seq: int = 0
    activation_ts: float = 0.0
    workspace_id: str = ""
    account_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> ActiveWorkflowPointer | None:
        if not isinstance(raw, dict):
            return None
        return cls(
            workflow_owner=str(raw.get("workflow_owner") or ""),
            workflow_session_id=str(raw.get("workflow_session_id") or ""),
            context_revision=int(raw.get("context_revision") or 0),
            activation_source=str(raw.get("activation_source") or ""),
            activation_seq=int(raw.get("activation_seq") or 0),
            activation_ts=float(raw.get("activation_ts") or 0.0),
            workspace_id=str(raw.get("workspace_id") or ""),
            account_id=str(raw.get("account_id") or ""),
        )


def resolve_workspace_identity(session: dict[str, Any]) -> tuple[str, str]:
    ws = str(
        session.get("_suite_active_workspace_id")
        or session.get("suite_active_workspace")
        or session.get("music_user_id")
        or ""
    ).strip()
    acct = str(session.get("_suite_account_id") or session.get("suite_account_id") or ws).strip()
    return ws or "default", acct or ws or "default"


def blob_storage_key(workflow_owner: str, workflow_session_id: str) -> str:
    owner = str(workflow_owner or "").strip() or "unknown"
    sid = str(workflow_session_id or "").strip() or "_default"
    return f"{owner}|{sid}"


def _material_fingerprint(blob: WorkflowStateBlob) -> str:
    payload = blob.to_dict()
    for k in ("material_fingerprint", "updated_at_seq", "context_revision"):
        payload.pop(k, None)
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _ensure_store(session: dict[str, Any]) -> dict[str, Any]:
    ws, _ = resolve_workspace_identity(session)
    store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
    if not isinstance(store, dict):
        store = {
            "schema_version": WORKFLOW_STORE_SCHEMA_VERSION,
            "workspace_id": ws,
            "context_revision_seq": 0,
            "blobs": {},
            "stats": {"reads": 0, "writes": 0, "writes_skipped": 0, "pointer_switches": 0},
        }
        session[MUSIC_WORKFLOW_STATE_STORE_KEY] = store
        return store
    if str(store.get("workspace_id") or "") != ws:
        store = {
            "schema_version": WORKFLOW_STORE_SCHEMA_VERSION,
            "workspace_id": ws,
            "context_revision_seq": 0,
            "blobs": {},
            "stats": {"reads": 0, "writes": 0, "writes_skipped": 0, "pointer_switches": 0},
        }
        session[MUSIC_WORKFLOW_STATE_STORE_KEY] = store
    store.setdefault("blobs", {})
    store.setdefault("stats", {"reads": 0, "writes": 0, "writes_skipped": 0, "pointer_switches": 0})
    return store


def get_music_workflow_state_store(session: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(_ensure_store(session))


def get_workflow_blob(
    session: dict[str, Any],
    workflow_owner: str,
    workflow_session_id: str,
) -> WorkflowStateBlob | None:
    store = _ensure_store(session)
    key = blob_storage_key(workflow_owner, workflow_session_id)
    raw = (store.get("blobs") or {}).get(key)
    stats = store.get("stats")
    if isinstance(stats, dict):
        stats["reads"] = int(stats.get("reads") or 0) + 1
    return WorkflowStateBlob.from_dict(raw)


def save_workflow_blob(
    session: dict[str, Any],
    blob: WorkflowStateBlob,
    *,
    source: str = "unspecified",
) -> bool:
    """Persist blob; return True if material content changed and write occurred."""
    store = _ensure_store(session)
    ws, _ = resolve_workspace_identity(session)
    if str(store.get("workspace_id") or "") != ws:
        return False
    blob.material_fingerprint = _material_fingerprint(blob)
    key = blob_storage_key(blob.workflow_owner, blob.workflow_session_id)
    blobs = store.setdefault("blobs", {})
    existing = WorkflowStateBlob.from_dict(blobs.get(key))
    if existing and existing.material_fingerprint == blob.material_fingerprint:
        stats = store.setdefault("stats", {})
        if isinstance(stats, dict):
            stats["writes_skipped"] = int(stats.get("writes_skipped") or 0) + 1
        _diag(session)["last_save"] = {"key": key, "skipped": True, "source": source}
        return False
    if existing:
        blob.context_revision = max(int(existing.context_revision) + 1, int(blob.context_revision))
    else:
        blob.context_revision = max(1, int(blob.context_revision))
    seq = int(store.get("context_revision_seq") or 0) + 1
    store["context_revision_seq"] = seq
    blob.updated_at_seq = seq
    blobs[key] = blob.to_dict()
    stats = store.setdefault("stats", {})
    if isinstance(stats, dict):
        stats["writes"] = int(stats.get("writes") or 0) + 1
    _diag(session)["last_save"] = {"key": key, "skipped": False, "source": source, "revision": blob.context_revision}
    return True


def get_active_workflow_pointer(session: dict[str, Any]) -> ActiveWorkflowPointer | None:
    return ActiveWorkflowPointer.from_dict(session.get(MUSIC_ACTIVE_WORKFLOW_KEY))


def set_active_workflow_pointer(
    session: dict[str, Any],
    pointer: ActiveWorkflowPointer,
    *,
    source: str = "unspecified",
) -> bool:
    """Set the single active pointer; return True if owner/session/revision changed."""
    ws, acct = resolve_workspace_identity(session)
    pointer.workspace_id = ws
    pointer.account_id = acct
    prev = get_active_workflow_pointer(session)
    changed = (
        prev is None
        or prev.workflow_owner != pointer.workflow_owner
        or prev.workflow_session_id != pointer.workflow_session_id
        or prev.context_revision != pointer.context_revision
    )
    if not changed and prev is not None:
        return False
    store = _ensure_store(session)
    stats = store.get("stats")
    if isinstance(stats, dict):
        stats["pointer_switches"] = int(stats.get("pointer_switches") or 0) + 1
    seq = int(store.get("context_revision_seq") or 0) + 1
    store["context_revision_seq"] = seq
    pointer.activation_seq = seq
    pointer.activation_ts = time.time()
    pointer.activation_source = str(source or pointer.activation_source or "unspecified")
    session[MUSIC_ACTIVE_WORKFLOW_KEY] = pointer.to_dict()
    _diag(session)["last_pointer"] = pointer.to_dict()
    return True


def workflow_cache_identity(session: dict[str, Any]) -> str:
    """Fingerprint for caches — includes active owner, session, practice mode, mission chord."""
    ptr = get_active_workflow_pointer(session)
    blob = None
    if ptr and ptr.workflow_owner:
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    parts = [
        ptr.workflow_owner if ptr else "",
        ptr.workflow_session_id if ptr else "",
        str(ptr.context_revision if ptr else ""),
    ]
    if blob:
        parts.extend(
            [
                blob.keys.practice_tonic,
                blob.keys.practice_mode,
                blob.selected_chord_symbol,
                blob.generated_session_id,
                blob.material_fingerprint,
            ]
        )
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def record_legacy_field_read(session: dict[str, Any], field: str, *, adapter: str = "") -> None:
    bucket = session.setdefault(WORKFLOW_LEGACY_READS_KEY, [])
    if not isinstance(bucket, list):
        bucket = []
        session[WORKFLOW_LEGACY_READS_KEY] = bucket
    entry = {"field": str(field), "adapter": str(adapter or "")}
    if entry not in bucket[-50:]:
        bucket.append(entry)
    try:
        from music_dev_nav import dev_count

        dev_count(session, "workflow_legacy_read")
    except ImportError:
        pass


def record_compat_fallback(session: dict[str, Any], name: str, detail: str = "") -> None:
    bucket = session.setdefault(WORKFLOW_COMPAT_FALLBACKS_KEY, [])
    if not isinstance(bucket, list):
        bucket = []
        session[WORKFLOW_COMPAT_FALLBACKS_KEY] = bucket
    bucket.append({"name": name, "detail": detail or None})


def _diag(session: dict[str, Any]) -> dict[str, Any]:
    d = session.get(WORKFLOW_STORE_DIAG_KEY)
    if not isinstance(d, dict):
        d = {}
        session[WORKFLOW_STORE_DIAG_KEY] = d
    return d


def validate_active_workflow_pointer(session: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    ptr = get_active_workflow_pointer(session)
    if ptr is None:
        return violations
    ws, acct = resolve_workspace_identity(session)
    if ptr.workspace_id and ptr.workspace_id != ws:
        violations.append("ACTIVE_POINTER_WORKSPACE_MISMATCH")
    if ptr.account_id and acct and ptr.account_id != acct:
        violations.append("ACTIVE_POINTER_ACCOUNT_MISMATCH")
    if ptr.workflow_owner and ptr.workflow_owner not in ALL_WORKFLOW_OWNERS:
        violations.append("ACTIVE_POINTER_UNKNOWN_OWNER")
    if ptr.workflow_owner and not ptr.workflow_session_id:
        violations.append("ACTIVE_POINTER_MISSING_SESSION_ID")
    return violations


def validate_workflow_state_identity(session: dict[str, Any], blob: WorkflowStateBlob | None = None) -> list[str]:
    violations: list[str] = []
    ptr = get_active_workflow_pointer(session)
    if blob is None and ptr:
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return violations
    key = blob_storage_key(blob.workflow_owner, blob.workflow_session_id)
    store = _ensure_store(session)
    if key not in (store.get("blobs") or {}):
        violations.append("BLOB_NOT_IN_STORE")
    if blob.workflow_owner and blob.workflow_owner not in ALL_WORKFLOW_OWNERS:
        violations.append("BLOB_UNKNOWN_OWNER")
    if ptr and ptr.workflow_owner == blob.workflow_owner:
        if ptr.context_revision < blob.context_revision:
            violations.append("POINTER_REVISION_BEHIND_BLOB")
    return violations


def validate_owner_bound_fingerprints(session: dict[str, Any], blob: WorkflowStateBlob | None = None) -> list[str]:
    violations: list[str] = []
    ptr = get_active_workflow_pointer(session)
    if blob is None and ptr:
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
    if blob is None:
        return violations
    if blob.example_fingerprint and not blob.selected_chord_symbol:
        violations.append("EXAMPLE_FP_WITHOUT_CHORD")
    if blob.artifact_fingerprint and blob.workflow_owner == "mission_jam" and not blob.mission_type:
        violations.append("ARTIFACT_FP_WITHOUT_MISSION")
    if blob.example_fingerprint and blob.selected_chord_symbol:
        pass
    return violations


def validate_context_revision(session: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    store = session.get(MUSIC_WORKFLOW_STATE_STORE_KEY)
    if not isinstance(store, dict):
        return violations
    seq = int(store.get("context_revision_seq") or 0)
    for _k, raw in (store.get("blobs") or {}).items():
        b = WorkflowStateBlob.from_dict(raw)
        if b and int(b.updated_at_seq or 0) > seq:
            violations.append("BLOB_SEQ_AHEAD_OF_STORE")
    ptr = get_active_workflow_pointer(session)
    if ptr and int(ptr.activation_seq or 0) > seq:
        violations.append("POINTER_SEQ_AHEAD_OF_STORE")
    return violations


def collect_consistency_violations(session: dict[str, Any]) -> list[str]:
    out: list[str] = []
    out.extend(validate_active_workflow_pointer(session))
    out.extend(validate_workflow_state_identity(session))
    out.extend(validate_owner_bound_fingerprints(session))
    out.extend(validate_context_revision(session))
    return out


__all__ = [
    "ALL_WORKFLOW_OWNERS",
    "ActiveWorkflowPointer",
    "KeyAuthority",
    "MUSIC_ACTIVE_WORKFLOW_KEY",
    "MUSIC_WORKFLOW_STATE_STORE_KEY",
    "SAVE_REASON_WORKFLOW_STATE",
    "WORKFLOW_COMPAT_FALLBACKS_KEY",
    "WORKFLOW_LEGACY_READS_KEY",
    "WORKFLOW_STORE_DIAG_KEY",
    "WORKFLOW_STORE_SCHEMA_VERSION",
    "WorkflowOwner",
    "WorkflowStateBlob",
    "blob_storage_key",
    "collect_consistency_violations",
    "get_active_workflow_pointer",
    "get_music_workflow_state_store",
    "get_workflow_blob",
    "record_compat_fallback",
    "record_legacy_field_read",
    "resolve_workspace_identity",
    "save_workflow_blob",
    "set_active_workflow_pointer",
    "validate_active_workflow_pointer",
    "validate_context_revision",
    "validate_owner_bound_fingerprints",
    "validate_workflow_state_identity",
    "workflow_cache_identity",
]
