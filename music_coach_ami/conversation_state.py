"""AMI's short-term conversational memory: recent turns and the working exercise with its version history.

One record per browser session, kept under ``_ami_conv_state`` (so a workspace switch, a sign-out and an account change all
drop it, see ``session_scope``). It holds plain dicts only:

* ``turns``    - the last few questions and AMI answers (short text only, never the notation or the full answer).
* ``versions`` - up to ``MAX_VERSIONS`` snapshots of the working exercise. Each carries the exercise dict, its tempo, the
                 notation and the Open-in-Missions action that matched, so undo restores all of it exactly.
* ``cursor``   - which version is current. Undo moves it back, redo forward, a new revision drops the redo tail.

The version list is the single source of truth for "the working exercise". ``_ami_last_generated_exercise`` (the slot the
existing follow-up engines read) is kept equal to the current version, so both systems always agree.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import MutableMapping
from typing import Any

from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.session_scope import ensure_owner, owner_token, stamp

STATE_KEY = "_ami_conv_state"
MAX_TURNS = 8
MAX_VERSIONS = 10
DEFAULT_BPM = 96
_TEXT_CAP = 240

_Q_TEMPO = re.compile(r"^Q:\s*\d+/\d+\s*=\s*(\d{2,3})\b", re.M)


def _mutable(session_ref: Any) -> MutableMapping | None:
    from music_coach_ami.session_access import as_mutable_session

    session = as_mutable_session(session_ref)
    return session if isinstance(session, MutableMapping) else None


def _blank() -> dict[str, Any]:
    return {"turns": [], "versions": [], "cursor": -1}


def _state(session: MutableMapping, *, create: bool = False) -> dict[str, Any] | None:
    ensure_owner(session)
    raw = session.get(STATE_KEY)
    if isinstance(raw, dict) and raw.get("owner") == owner_token(session):
        return raw
    if not create:
        return None
    fresh = {**_blank(), "owner": owner_token(session)}
    session[STATE_KEY] = fresh
    return fresh


def _short(text: object) -> str:
    one = re.sub(r"\s+", " ", str(text or "")).strip()
    return one if len(one) <= _TEXT_CAP else one[: _TEXT_CAP - 1].rstrip() + "…"


def tempo_of_abc(abc: str) -> int:
    m = _Q_TEMPO.search(str(abc or ""))
    return int(m.group(1)) if m else 0


def version_id(exercise: dict[str, Any], tempo_bpm: int) -> str:
    blob = json.dumps({"x": {k: v for k, v in exercise.items() if k != "_owner"}, "t": tempo_bpm}, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------- reading


def current_version(session_ref: Any) -> dict[str, Any] | None:
    """The working exercise's current version, only if it is still the exercise the follow-up engines hold."""
    session = _mutable(session_ref)
    if session is None:
        return None
    st = _state(session)
    if not st or not st["versions"] or not (0 <= st["cursor"] < len(st["versions"])):
        return None
    ver = st["versions"][st["cursor"]]
    held = session.get(AMI_LAST_EXERCISE_KEY)
    if not isinstance(held, dict) or held.get("id") != ver["exercise"].get("id"):
        return None   # a newer unstructured answer (or a reset) replaced it: there is no working exercise to revise
    return ver


def working_tempo(session_ref: Any) -> int:
    ver = current_version(session_ref)
    return int(ver["tempo_bpm"]) if ver and ver.get("tempo_bpm") else 0


def history(session_ref: Any) -> dict[str, Any]:
    session = _mutable(session_ref)
    st = _state(session) if session is not None else None
    if not st:
        return {"turns": [], "versions": 0, "cursor": -1, "can_undo": False, "can_redo": False}
    n, c = len(st["versions"]), st["cursor"]
    return {"turns": list(st["turns"]), "versions": n, "cursor": c, "can_undo": c > 0, "can_redo": 0 <= c < n - 1}


# ---------------------------------------------------------------- writing


def record_turn(session_ref: Any, question: str, answer: str, *, exercise_id: str = "") -> None:
    session = _mutable(session_ref)
    if session is None:
        return
    st = _state(session, create=True)
    st["turns"].append({"q": _short(question), "a": _short(answer), "ex": exercise_id})
    del st["turns"][:-MAX_TURNS]


def push_version(
    session_ref: Any, exercise: dict[str, Any], *, tempo_bpm: int, abc: str = "", sections: list[str] | None = None,
    label: str = "", action: dict[str, Any] | None = None, context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Add a version after the cursor (dropping any redo tail) and make it current. No-op if it equals the current one."""
    session = _mutable(session_ref)
    if session is None or not isinstance(exercise, dict) or not exercise.get("id"):
        return None
    st = _state(session, create=True)
    clean = {k: v for k, v in copy.deepcopy(exercise).items() if k != "_owner"}
    tempo = int(tempo_bpm or DEFAULT_BPM)
    clean["tempo_bpm"] = tempo
    vid = version_id(clean, tempo)
    if 0 <= st["cursor"] < len(st["versions"]) and st["versions"][st["cursor"]]["vid"] == vid:
        return st["versions"][st["cursor"]]
    ver = {"vid": vid, "exercise": clean, "tempo_bpm": tempo, "abc": abc, "sections": list(sections or ([abc] if abc else [])), "label": _short(label),
           "action": copy.deepcopy(action) if action else None, "context": dict(context or {})}
    st["versions"] = st["versions"][: st["cursor"] + 1] + [ver]
    drop = max(0, len(st["versions"]) - MAX_VERSIONS)
    if drop:
        del st["versions"][:drop]
    st["cursor"] = len(st["versions"]) - 1
    _sync_last_exercise(session, ver)
    return ver


def _sync_last_exercise(session: MutableMapping, ver: dict[str, Any]) -> None:
    session[AMI_LAST_EXERCISE_KEY] = stamp(copy.deepcopy(ver["exercise"]), session)


def step(session_ref: Any, delta: int) -> dict[str, Any] | None:
    """Move the cursor (undo = -1, redo = +1) and re-point the follow-up engines at that version. None if out of range."""
    session = _mutable(session_ref)
    if session is None:
        return None
    if current_version(session) is None:
        return None
    st = _state(session)
    target = st["cursor"] + delta
    if not (0 <= target < len(st["versions"])):
        return None
    st["cursor"] = target
    ver = st["versions"][target]
    _sync_last_exercise(session, ver)
    return ver
