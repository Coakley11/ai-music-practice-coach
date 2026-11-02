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
_SEEN_KEY = "_music_ctx_seen_revision"
_CHOSEN_KEY = "_music_ctx_resource_chosen"

# Fields that define "the same context" (everything else is bookkeeping).
CONTENT_FIELDS = ("source_type", "resource_id", "page", "workflow", "mission_id", "instrument", "practice_key")

# ``workflow`` is the meaningful destination inside ``page``. It is read from authoritative
# session state, never inferred from labels:
#   practice | backing | <other page id>   workflow == page
#   creative page: "mission" | "song_aware_coaching" | "creative" (any other Creative tool)
WORKFLOW_MISSION = "mission"
WORKFLOW_COACHING = "song_aware_coaching"
WORKFLOW_CREATIVE = "creative"


@dataclass(frozen=True)
class ActiveContext:
    account_id: str
    workspace_id: str
    revision: int
    source_type: str          # catalog | custom | composition
    resource_id: str          # stable pick key
    page: str                 # studio page
    workflow: str = ""        # destination within the page (see WORKFLOW_*); "" in legacy records == page
    mission_id: str = ""      # stable Mission identity (PRACTICE_MISSIONS key); only when workflow == mission
    instrument: str = ""
    practice_key: str = ""    # canonical Practice Key (concert pitch)
    intentional_at: str = ""  # ISO-8601 UTC of the user's action
    device_id: str = ""
    cause: str = ""           # last applied intent type
    # Per-field time of the intent that last set that field. Lets a later intent
    # tell whether the field it owns was changed more recently by someone else.
    field_at: dict = field(default_factory=dict)
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
            data["workflow"] = str(data.get("workflow") or data.get("page") or "")
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
            except (FileExistsError, PermissionError):
                # Windows reports a lock file that is pending delete as PermissionError.
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


# Intent types -> (fields the intent owns, field whose newer change supersedes it,
# whether it is only meaningful for the resource it was made on).
#   song_selected       a deliberate resource choice; takes its page/key with it
#   workflow_selected   page + workflow (+ Mission identity); meaningless once the resource
#                       changed elsewhere (a stale Mission/Coaching/page change never moves a newer song)
#   instrument_changed  instrument only
#   practice_key_changed  Practice Key only; resource-dependent (a key chosen against song A
#                         is never merged onto song B -- no respelling or mode guessing);
#                         never a Key Cycling sounding key
#   resume              a deliberate Resume (incl. a historical card): all fields
INTENT_SPECS: dict[str, dict[str, Any]] = {
    "song_selected": dict(owns=("source_type", "resource_id", "page", "workflow", "mission_id", "practice_key"),
                          conflicts="resource_id", needs_resource=False),
    "workflow_selected": dict(owns=("page", "workflow", "mission_id"), conflicts="workflow", needs_resource=True),
    "instrument_changed": dict(owns=("instrument",), conflicts="instrument", needs_resource=False),
    "practice_key_changed": dict(owns=("practice_key",), conflicts="practice_key", needs_resource=True),
    "resume": dict(owns=CONTENT_FIELDS, conflicts="resource_id", needs_resource=False),
}
_CAUSE_ALIASES = {"select": "song_selected", "page": "workflow_selected",
                  "instrument": "instrument_changed", "key": "practice_key_changed"}


def mark_intent(session: Any, cause: str = "song_selected") -> None:
    """Record that the USER just made a context-defining choice, as an intent
    delta: its type, the fields it owns, the revision this device had accepted and
    the resource it was made on. Side-effect free apart from one session key; a
    no-op while adopting. Unknown causes are ignored (never inferred)."""
    try:
        if not active_context_enabled():
            return  # feature unset: a complete no-op (no snapshot, no session keys)
        if session.get(_SUPPRESS_KEY):
            return
        kind = _CAUSE_ALIASES.get(str(cause or ""), str(cause or ""))
        spec = INTENT_SPECS.get(kind)
        if spec is None:
            return
        snap = snapshot_from_session(session) or {}
        entry = {"type": kind, "owns": list(spec["owns"]), "at": _now_iso(),
                 "base_revision": accepted_revision(session),
                 "base_resource": snap.get("resource_id", "")}
        pending = session.get(_INTENT_KEY)
        items = list(pending["items"]) if isinstance(pending, dict) else []
        if kind == "resume":
            items = []  # a Resume replaces everything marked earlier in the same run
        items.append(entry)
        if "resource_id" in spec["owns"]:
            session[_CHOSEN_KEY] = True  # the user deliberately picked this session's resource
        session[_INTENT_KEY] = {"cause": kind, "at": entry["at"], "items": items}
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


def relabel_pending_as_resume(session: Any) -> None:
    """A completed Resume transaction: whatever was marked during it is one resume."""
    pending = session.get(_INTENT_KEY)
    if isinstance(pending, dict):
        at = pending.get("at") or _now_iso()
        session[_INTENT_KEY] = {"cause": "resume", "at": at, "items": [
            {"type": "resume", "owns": list(CONTENT_FIELDS), "at": at,
             "base_revision": accepted_revision(session), "base_resource": ""}]}


def accepted_revision(session: Any) -> int:
    try:
        return int(session.get(_ACCEPTED_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def seen_revision(session: Any) -> int:
    try:
        return int(session.get(_SEEN_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def _source_type(pick_key: str) -> str:
    if pick_key.startswith(("composition::", "composition\x1f")):
        return "composition"
    if pick_key.startswith(("custom::", "custom\x1f")):
        return "custom"
    return "catalog"


def _workflow_from_session(session: Any, page: str) -> tuple[str, str]:
    """(workflow, mission_id) from authoritative Creative-tab state; never from labels."""
    if page != "creative":
        return page, ""
    mode = str(session.get("creative_lab_analysis_mode") or "").strip()
    tab = str(session.get("creative_improv_intelligence_tab")
              or session.get("improv_intelligence_tab") or "").strip()
    # The Creative page forces the Analysis mode to Improvisation Intelligence whenever the
    # tab is Missions, so Missions wins; any other tab only counts under that mode.
    if mode and mode != "Improvisation Intelligence" and tab != "Missions":
        return WORKFLOW_CREATIVE, ""
    if tab == "Song-Aware Coaching":
        return WORKFLOW_COACHING, ""
    if tab == "Missions":
        mission = ""
        try:
            from mission_practice_context import authoritative_mission_type

            mission = str(authoritative_mission_type(session) or "").strip()
        except Exception:
            pass
        mission = mission or str(session.get("improv_active_mission")
                                 or session.get("improv_mission_pick") or "").strip()
        return WORKFLOW_MISSION, mission
    return WORKFLOW_CREATIVE, ""


def snapshot_from_session(session: Any) -> dict[str, str] | None:
    """The CURRENT resolved context fields, or None when no song is active.
    Reuses the Resume payload builder so there is one definition of the fields.
    ``display_key`` is the Practice Key (concert); a Key Cycling sounding key is
    never read here."""
    from music_resume_payload import build_music_resume_payload

    payload = build_music_resume_payload(session)
    pick = str(payload.get("pick_key") or "").strip()
    if not pick:
        return None
    page = str(payload.get("studio_page") or "").strip() or "practice"
    workflow, mission_id = _workflow_from_session(session, page)
    return {
        "source_type": _source_type(pick),
        "resource_id": pick,
        "page": page,
        "workflow": workflow,
        "mission_id": mission_id,
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


def merge_intents(
    latest: ActiveContext | None, snap: dict[str, str], items: list[dict[str, Any]],
    resource_chosen: bool = False,
) -> tuple[dict[str, str], dict[str, str], str, str]:
    """Pure merge of intent deltas onto the LATEST record.

    Returns (content, field_at, last_cause, outcome) where outcome is "apply" (some
    delta survived), "superseded" (every delta lost to a later change of a field it
    owns) or "discarded" (every delta no longer fits the newer resource). Only the
    fields an applied intent owns are taken from ``snap``; every other field keeps
    the latest record's value, so a stale device can never resurrect an old
    song/page/instrument/key. With no record yet the snapshot seeds the content."""
    if latest is None:
        content = dict(snap)
        field_at: dict[str, str] = {}
    else:
        content = {f: getattr(latest, f) for f in CONTENT_FIELDS}
        field_at = dict(latest.field_at or {})
    applied, lost_race, lost_fit, last_cause = 0, 0, 0, ""
    for item in items:
        spec = INTENT_SPECS.get(item.get("type"))
        if spec is None:
            continue
        at = str(item.get("at") or "")
        if latest is None and not resource_chosen and "resource_id" not in spec["owns"]:
            # No shared record and the resource was never deliberately chosen (it is
            # the safe default / hydrated state): a page, instrument or key change
            # alone must not create revision 1 around a default song.
            lost_fit += 1
            continue
        if latest is not None:
            if field_at.get(spec["conflicts"], "") > at:
                lost_race += 1  # a later intentional change already owns that field
                continue
            if spec["needs_resource"] and snap["resource_id"] != content["resource_id"]:
                lost_fit += 1  # e.g. Practice->Backing for a song that is no longer current
                continue
        for f in spec["owns"]:
            content[f] = snap[f]
            field_at[f] = at
        applied += 1
        last_cause = item["type"]
    if applied:
        return content, field_at, last_cause, "apply"
    return content, field_at, last_cause, "discarded" if lost_fit and not lost_race else "superseded"


def flush_intent(
    session: Any,
    store: ActiveContextStore | None,
    *,
    account_id: str,
    workspace_id: str,
    device_id: str,
) -> str:
    """Publish ONE newer revision iff an explicit intent is pending and merging it
    onto the latest record changes the content. Returns a status string.

    Algorithm: read latest -> merge only the fields the pending intents own
    (merge_intents) -> compare-and-set. On a CAS loss, reread and re-evaluate against
    the winner. Intents that no longer fit are dropped (``superseded`` /
    ``discarded``), never widened into a full-snapshot write. A store failure keeps
    the intent for a later retry and leaves durable Music state untouched."""
    intent = session.get(_INTENT_KEY)
    if not isinstance(intent, dict) or store is None:
        return _status(session, "no_intent")
    items = [i for i in intent.get("items") or [] if isinstance(i, dict)]
    snap = snapshot_from_session(session)
    if snap is None or not items:
        clear_intent(session)
        return _status(session, "no_context")
    try:
        current = store.read(account_id, workspace_id)
        for _attempt in range(4):
            content, field_at, cause, outcome = merge_intents(current, snap, items, bool(session.get(_CHOSEN_KEY)))
            if outcome != "apply":
                if current is not None:
                    session[_SEEN_KEY] = max(seen_revision(session), current.revision)
                clear_intent(session)
                return _status(session, outcome)
            if current is not None and tuple(content[f] for f in CONTENT_FIELDS) == current.content():
                _note_synced(session, snap, current)
                clear_intent(session)
                return _status(session, "unchanged")
            expected = current.revision if current else 0
            record = ActiveContext(
                account_id=account_id, workspace_id=workspace_id, revision=expected + 1,
                intentional_at=max(str(i.get("at") or "") for i in items), device_id=device_id,
                cause=cause, field_at=field_at, **content,
            )
            result = store.compare_and_set(expected, record)
            if result.ok:
                _note_synced(session, snap, record)
                clear_intent(session)
                return _status(session, "published")
            current = result.current  # lost the CAS race: re-evaluate against the winner
        return _status(session, "conflict")  # keep intent; retry on a later run
    except Exception:
        return _status(session, "store_error")  # intent kept; durable state untouched


def _note_synced(session: Any, snap: dict[str, str], record: ActiveContext) -> None:
    """Remember the revision this device has SEEN; it counts as in sync (accepted)
    only when the device's own resolved context equals the record. After a merged
    publish that differs from what this tab shows, the tab stays "behind" so
    newer_context_available() keeps reporting the shared context."""
    session[_SEEN_KEY] = max(seen_revision(session), record.revision)
    if tuple(snap[f] for f in CONTENT_FIELDS) == record.content():
        session[_ACCEPTED_KEY] = max(accepted_revision(session), record.revision)


def newer_context_available(
    session: Any, store: ActiveContextStore | None, *, account_id: str, workspace_id: str,
) -> ActiveContext | None:
    """Non-mutating: the shared record when it is newer than what this tab last
    accepted AND differs from what this tab currently shows, else None. Reads the
    store only; writes nothing and never touches session state or the UI. A future
    "Workspace changed on another device -- Sync" affordance can call this; nothing
    redirects an active tab."""
    if store is None:
        return None
    try:
        record = store.read(account_id, workspace_id)
        if record is None or record.revision <= accepted_revision(session):
            return None
        snap = snapshot_from_session(session)
        if snap is not None and tuple(snap[f] for f in CONTENT_FIELDS) == record.content():
            return None
        return record
    except Exception:
        return None


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
    if record.page == "creative" and record.workflow in (WORKFLOW_MISSION, WORKFLOW_COACHING):
        # The Resume owner restores Missions / Song-Aware Coaching through its activity branch.
        # The id is only that branch's flag; adoption never writes an activity record.
        payload["resume_kind"] = "creative"
        payload["progress_activity_id"] = "active-context"
        if record.workflow == WORKFLOW_MISSION:
            payload["activity_destination"] = "missions"
            if record.mission_id:
                payload["mission"] = record.mission_id
        else:
            payload["activity_destination"] = "coaching"
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
