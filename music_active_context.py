"""Account-level *active Music context*: the latest intentional workspace choice.

Three systems stay separate:

* durable Music state    -- the workspace blob / saved resources (unchanged);
* active context (this) -- one small record: what the user most recently CHOSE;
* historical Continue     -- past contexts, still reopenable, never "current".

Only explicit user intent publishes a newer revision. Hydration, reruns,
rendering, autosave and passive logging never do. Adoption on another device
re-uses ``apply_music_resume_payload`` so every P0/P1 ownership check applies,
and adopting never publishes.

Transient UI (playback position, autoplay, Key Cycling sounding key, scroll,
expanders, unsaved text, widget state) is deliberately not part of the record.

The store is an interface. ``LocalFileActiveContextStore`` is the local/mock
implementation with real compare-and-set semantics; a cloud store is future
work and is NOT claimed here. The feature is dark unless ``MUSIC_ACTIVE_CONTEXT``
is ``local``.
"""
from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Protocol

SCHEMA_VERSION = 1
ENV_MODE = "MUSIC_ACTIVE_CONTEXT"          # "local" enables the local/mock store
ENV_DIR = "MUSIC_ACTIVE_CONTEXT_DIR"       # shared dir for the local store

_INTENT_KEY = "_music_ctx_intent"
_SUPPRESS_KEY = "_music_ctx_suppress"
_ACCEPTED_KEY = "_music_ctx_accepted_revision"
_ADOPT_CHECKED_KEY = "_music_ctx_adopt_checked"
_REJECTED_KEY = "_music_ctx_rejected_revision"

# Fields that define "the same context" (everything else is bookkeeping).
CONTENT_FIELDS = ("source_type", "resource_id", "page", "instrument", "practice_key")


@dataclass(frozen=True)
class ActiveContext:
    account_id: str
    workspace_id: str
    revision: int
    source_type: str          # catalog | custom | composition
    resource_id: str          # stable pick key
    page: str                 # studio page / workflow
    instrument: str = ""
    practice_key: str = ""    # canonical Practice Key (concert pitch)
    intentional_at: str = ""  # ISO-8601 UTC of the user's action
    device_id: str = ""
    cause: str = ""           # select | resume | instrument | key | page
    schema_version: int = SCHEMA_VERSION

    def content(self) -> tuple:
        return tuple(getattr(self, f) for f in CONTENT_FIELDS)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Any) -> "ActiveContext | None":
        if not isinstance(raw, dict):
            return None
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in raw.items() if k in known}
        try:
            data["revision"] = int(data.get("revision"))
            return cls(**data)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class CasResult:
    ok: bool
    current: ActiveContext | None = None


class ActiveContextStore(Protocol):
    def read(self, account_id: str, workspace_id: str) -> ActiveContext | None: ...

    def compare_and_set(self, expected_revision: int, record: ActiveContext) -> CasResult:
        """Write ``record`` only if the stored revision equals ``expected_revision``
        (0 means "no record yet"). Never merges; a mismatch returns the current record."""


# --------------------------------------------------------------------------- store

def _safe(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(token or "").strip()) or "_"


class LocalFileActiveContextStore:
    """Local/mock store. Atomic CAS via an exclusive lock file + atomic replace."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)

    def _path(self, account_id: str, workspace_id: str) -> Path:
        return self.root / f"{_safe(account_id)}__{_safe(workspace_id)}.json"

    def read(self, account_id: str, workspace_id: str) -> ActiveContext | None:
        path = self._path(account_id, workspace_id)
        for attempt in range(20):
            try:
                return ActiveContext.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except FileNotFoundError:
                return None
            except PermissionError:
                # Windows: a concurrent atomic replace briefly locks the file.
                time.sleep(0.005 * (attempt + 1))
            except (OSError, ValueError):
                return None
        raise OSError(f"active-context record unreadable: {path}")

    @contextmanager
    def _locked(self, path: Path) -> Iterator[None]:
        lock = path.with_suffix(".lock")
        deadline = time.monotonic() + 5.0
        fd = None
        while fd is None:
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:  # break a lock left by a crashed writer
                    if time.time() - lock.stat().st_mtime > 10:
                        lock.unlink()
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("active-context lock timeout")
                time.sleep(0.01)
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock.unlink()
            except OSError:
                pass

    def compare_and_set(self, expected_revision: int, record: ActiveContext) -> CasResult:
        path = self._path(record.account_id, record.workspace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked(path):
            current = self.read(record.account_id, record.workspace_id)
            current_rev = current.revision if current else 0
            if current_rev != int(expected_revision) or record.revision != current_rev + 1:
                return CasResult(False, current)
            tmp = path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(record.to_dict(), sort_keys=True), encoding="utf-8")
            for attempt in range(20):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:  # a reader briefly holds the file (Windows)
                    if attempt == 19:
                        raise
                    time.sleep(0.005 * (attempt + 1))
            return CasResult(True, record)


def active_context_enabled() -> bool:
    return str(os.environ.get(ENV_MODE) or "").strip().lower() == "local"


def get_store() -> ActiveContextStore | None:
    """The configured store, or None (feature dark). Cloud store: not implemented."""
    if not active_context_enabled():
        return None
    root = os.environ.get(ENV_DIR) or os.path.join(
        os.environ.get("MUSIC_APP_DATA_DIR") or "data", "active_context")
    return LocalFileActiveContextStore(root)


# ------------------------------------------------------------------------ intent

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def mark_intent(session: Any, cause: str = "select") -> None:
    """Record that the USER just made a context-defining choice. Cheap and
    side-effect free apart from one session key; a no-op while adopting."""
    try:
        if session.get(_SUPPRESS_KEY):
            return
        session[_INTENT_KEY] = {"cause": str(cause or "select"), "at": _now_iso()}
    except Exception:
        pass


@contextmanager
def suppress_intent(session: Any) -> Iterator[None]:
    """While active, mark_intent is ignored (used when adopting / hydrating)."""
    previous = session.get(_SUPPRESS_KEY)
    session[_SUPPRESS_KEY] = True
    try:
        yield
    finally:
        if previous:
            session[_SUPPRESS_KEY] = previous
        else:
            session.pop(_SUPPRESS_KEY, None)


def clear_intent(session: Any) -> None:
    session.pop(_INTENT_KEY, None)


def accepted_revision(session: Any) -> int:
    try:
        return int(session.get(_ACCEPTED_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def _source_type(pick_key: str) -> str:
    if pick_key.startswith(("composition::", "composition\x1f")):
        return "composition"
    if pick_key.startswith(("custom::", "custom\x1f")):
        return "custom"
    return "catalog"


def snapshot_from_session(session: Any) -> dict[str, str] | None:
    """The CURRENT resolved context fields, or None when no song is active.
    Reuses the Resume payload builder so there is one definition of the fields."""
    from music_resume_payload import build_music_resume_payload

    payload = build_music_resume_payload(session)
    pick = str(payload.get("pick_key") or "").strip()
    if not pick:
        return None
    return {
        "source_type": _source_type(pick),
        "resource_id": pick,
        "page": str(payload.get("studio_page") or "").strip() or "practice",
        "instrument": str(payload.get("instrument") or "").strip(),
        "practice_key": str(payload.get("display_key") or "").strip(),
    }


def publish_status(session: Any) -> str:
    return str(session.get("_music_ctx_last_status") or "")


def _status(session: Any, value: str) -> str:
    try:
        session["_music_ctx_last_status"] = value
    except Exception:
        pass
    return value


def flush_intent(
    session: Any,
    store: ActiveContextStore | None,
    *,
    account_id: str,
    workspace_id: str,
    device_id: str,
) -> str:
    """Publish ONE newer revision iff an explicit intent is pending and the
    resolved context differs from the stored one. Returns a status string.

    Conflict rule (last intentional activity wins): on a CAS conflict our write is
    retried once on top of the newer record only when our intent is later than the
    stored record's intentional_at; otherwise the newer intent stands and we drop.
    Any store failure leaves durable Music state untouched and keeps the intent so
    a later run retries."""
    intent = session.get(_INTENT_KEY)
    if not isinstance(intent, dict) or store is None:
        return _status(session, "no_intent")
    snap = snapshot_from_session(session)
    if snap is None:
        clear_intent(session)
        return _status(session, "no_context")
    try:
        current = store.read(account_id, workspace_id)
        for attempt in range(2):
            if current is not None and tuple(snap[f] for f in CONTENT_FIELDS) == current.content():
                session[_ACCEPTED_KEY] = max(accepted_revision(session), current.revision)
                clear_intent(session)
                return _status(session, "unchanged")
            if current is not None and str(intent.get("at") or "") <= current.intentional_at:
                # A later intentional action elsewhere already won (last intent wins).
                session[_ACCEPTED_KEY] = max(accepted_revision(session), current.revision)
                clear_intent(session)
                return _status(session, "superseded")
            expected = current.revision if current else 0
            record = ActiveContext(
                account_id=account_id, workspace_id=workspace_id, revision=expected + 1,
                intentional_at=str(intent.get("at") or _now_iso()), device_id=device_id,
                cause=str(intent.get("cause") or ""), **snap,
            )
            result = store.compare_and_set(expected, record)
            if result.ok:
                session[_ACCEPTED_KEY] = record.revision
                clear_intent(session)
                return _status(session, "published")
            current = result.current  # lost the CAS race: re-evaluate against the winner
        return _status(session, "conflict")  # keep intent; retry on a later run
    except Exception:
        return _status(session, "store_error")  # intent kept; durable state untouched


def pending_adoption(
    session: Any,
    store: ActiveContextStore | None,
    *,
    account_id: str,
    workspace_id: str,
    explicit_resume_present: bool,
) -> ActiveContext | None:
    """The record to adopt on a COLD session start, or None. Never writes.

    Skipped when an explicit Resume URL is present (it wins and publishes), when
    an intent is pending, when the session already accepted this revision, or when
    the record is already what the hydrated session shows."""
    if store is None or explicit_resume_present or session.get(_ADOPT_CHECKED_KEY):
        return None
    session[_ADOPT_CHECKED_KEY] = True
    if isinstance(session.get(_INTENT_KEY), dict):
        return None
    try:
        record = store.read(account_id, workspace_id)
    except Exception:
        return None
    if record is None or record.revision <= accepted_revision(session):
        return None
    snap = snapshot_from_session(session)
    if snap is not None and tuple(snap[f] for f in CONTENT_FIELDS) == record.content():
        session[_ACCEPTED_KEY] = record.revision
        return None
    return record


def payload_for_adoption(record: ActiveContext) -> dict[str, Any]:
    """A Resume-shaped payload so adoption goes through the normal owner checks."""
    kind = {"backing": "backing", "creative": "creative", "multitrack": "multitrack",
            "analysis": "upload"}.get(record.page, "practice")
    payload: dict[str, Any] = {
        "version": 1, "resume_kind": kind, "studio_page": record.page,
        "pick_key": record.resource_id, "source_type": record.source_type,
        "source_id": record.resource_id, "instrument": record.instrument,
        "display_key": record.practice_key,
    }
    if record.practice_key:
        payload["key_kind"] = "concert"
    return payload


def adopt(session: Any, record: ActiveContext, apply_payload) -> bool:
    """Apply ``record`` through ``apply_payload(payload) -> bool``. Never publishes.
    A rejected revision (missing resource, ownership mismatch) is remembered so it
    is not retried every rerun."""
    with suppress_intent(session):
        try:
            ok = bool(apply_payload(payload_for_adoption(record)))
        except Exception:
            ok = False
    clear_intent(session)  # nothing applied here may count as user intent
    if ok:
        session[_ACCEPTED_KEY] = record.revision
    else:
        session[_REJECTED_KEY] = record.revision
    return ok
