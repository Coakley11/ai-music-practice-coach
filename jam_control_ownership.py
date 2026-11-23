"""Which jam owns which Creative controls, and when those controls hold the musician's choice.

Style Jam and the Jam Session Generator each have their own controls and their own saved record (a workflow
blob). Only one set of controls is on screen at a time. Streamlit forgets a control that is not drawn, and
when it is drawn again without a value assigned in that run it starts at its first option (Beginner, Light,
Bossa Nova, Bright...). The browser then reports that first option back as if the musician had chosen it.
Three rules follow:

1. A control's callback writes only its own jam's record (never "the mode on screen now").
2. A callback whose controls were not on screen in the previous run is not a musician's change.
3. Before a jam's controls are drawn again, their values are assigned from that jam's own record.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator

STYLE_JAM = "style_jam"
GENERATOR = "jam_session_generator"
JAM_OWNERS: tuple[str, ...] = (STYLE_JAM, GENERATOR)

ENTRY_MODE_FOR_OWNER: dict[str, str] = {STYLE_JAM: "Style Jam Mode", GENERATOR: "Jam Session Generator"}
OWNER_FOR_ENTRY_MODE: dict[str, str] = {v: k for k, v in ENTRY_MODE_FOR_OWNER.items()}

# Set while the owner's controls are drawn; cleared at the start of every script run (music_restore_phase).
MOUNTED_THIS_RUN_KEY: dict[str, str] = {
    STYLE_JAM: "_improv_style_key_mounted_this_run",
    GENERATOR: "_improv_jam_key_mounted_this_run",
}
# Whether the owner's controls were drawn in the previous script run (set when that flag is cleared).
MOUNTED_LAST_RUN_KEY: dict[str, str] = {
    STYLE_JAM: "_improv_style_controls_mounted_last_run",
    GENERATOR: "_improv_jam_controls_mounted_last_run",
}

JAM_ENSEMBLES: tuple[str, ...] = (
    "Jazz trio",
    "Jazz quartet",
    "Neo-soul band",
    "Rock trio",
    "Latin quartet",
    "Lo-fi duo",
)

# Each jam's own control keys, by setting.
CONTROL_KEYS: dict[str, dict[str, str]] = {
    STYLE_JAM: {
        "style": "improv_style",
        "mood": "improv_mood",
        "intensity": "improv_groove",
        "level": "improv_difficulty",
        "bpm": "improv_style_bpm",
    },
    GENERATOR: {
        "style": "improv_jam_style",
        "mood": "improv_jam_mood",
        "intensity": "improv_jam_intensity",
        "level": "improv_jam_difficulty",
        "bpm": "improv_jam_bpm",
        "ensemble": "improv_ensemble",
    },
}

_CALLBACK_OWNER: contextvars.ContextVar[str] = contextvars.ContextVar("jam_callback_owner", default="")


def _get(session: Any, key: str) -> Any:
    try:
        return session.get(key)
    except Exception:
        return None


def owner_for_entry_mode(entry_mode: Any) -> str:
    return OWNER_FOR_ENTRY_MODE.get(str(entry_mode or "").strip(), "")


def current_jam_owner(session: Any) -> str:
    """The jam whose controls the Entry & Jam mode selector shows ('' for any other mode)."""
    return owner_for_entry_mode(_get(session, "improv_entry_mode"))


# --------------------------------------------------------------------------- when controls are live
def note_script_run_started(session: Any) -> None:
    """Start of a script run: last run's 'drawn' flags become 'drawn last run'."""
    for owner in JAM_OWNERS:
        drawn = bool(session.pop(MOUNTED_THIS_RUN_KEY[owner], None))
        session[MOUNTED_LAST_RUN_KEY[owner]] = drawn


def note_controls_mounted(session: Any, owner: str) -> None:
    """The owner's controls are being drawn. The other jam's controls are not (one mode at a time)."""
    session[MOUNTED_THIS_RUN_KEY[owner]] = True
    for other in JAM_OWNERS:
        if other != owner:
            session.pop(MOUNTED_THIS_RUN_KEY[other], None)
            session.pop(MOUNTED_LAST_RUN_KEY[other], None)


def controls_drawn_last_run(session: Any, owner: str) -> bool:
    """Inside a callback (callbacks run before the script): were the owner's controls on screen?"""
    return bool(_get(session, MOUNTED_THIS_RUN_KEY.get(owner, "")))


@contextlib.contextmanager
def jam_callback_scope(owner: str) -> Iterator[None]:
    """Mark a jam control's callback, so readers know only last run's drawing counts as live."""
    token = _CALLBACK_OWNER.set(owner)
    try:
        yield
    finally:
        _CALLBACK_OWNER.reset(token)


def in_jam_callback() -> str:
    return _CALLBACK_OWNER.get()


def creative_jam_controls_live(session: Any, owner: str) -> bool:
    """True when the owner's Creative controls hold the musician's current choice.

    In a jam control's callback: only if they were drawn in the run the musician interacted with.
    In the script: if they are drawn in this run or were drawn in the previous one. Anywhere else (another
    mode on screen, the Backing page, a reload) the widgets hold transient defaults that nobody chose.
    """
    if owner not in MOUNTED_THIS_RUN_KEY:
        return False
    if in_jam_callback():
        return controls_drawn_last_run(session, owner)
    return bool(_get(session, MOUNTED_THIS_RUN_KEY[owner])) or bool(_get(session, MOUNTED_LAST_RUN_KEY[owner]))


# --------------------------------------------------------------------------- each jam's own record
def owner_record(session: Any, owner: str) -> Any:
    """The owner's own workflow blob: the active one when the owner is active, else its latest saved one."""
    try:
        from music_workflow_state_store import (
            MUSIC_WORKFLOW_STATE_STORE_KEY,
            WorkflowStateBlob,
            get_active_workflow_pointer,
            get_workflow_blob,
        )
    except ImportError:
        return None
    try:
        ptr = get_active_workflow_pointer(session)
        if ptr and str(ptr.workflow_owner or "") == owner and str(ptr.workflow_session_id or "").strip():
            blob = get_workflow_blob(session, owner, str(ptr.workflow_session_id))
            if blob is not None:
                return blob
        store = _get(session, MUSIC_WORKFLOW_STATE_STORE_KEY)
        blobs = (store or {}).get("blobs") if isinstance(store, dict) else None
        best = None
        for raw in dict(blobs or {}).values():
            if not isinstance(raw, dict) or str(raw.get("workflow_owner") or "") != owner:
                continue
            if best is None or int(raw.get("updated_at_seq") or 0) > int(best.get("updated_at_seq") or 0):
                best = raw
        return WorkflowStateBlob.from_dict(best) if best is not None else None
    except Exception:
        return None


def _option(value: Any, options: tuple[str, ...] | list[str]) -> str:
    """The option ``value`` names (case-insensitive), or '' when it names none."""
    v = str(value or "").strip().lower()
    if not v:
        return ""
    return next((o for o in options if o.lower() == v), "")


def _control_options() -> dict[str, tuple[str, ...]]:
    from improvisation_intelligence import DIFFICULTY_LEVELS, GROOVE_INTENSITY, MOOD_OPTIONS, STYLE_JAM_STYLES

    return {
        "style": tuple(STYLE_JAM_STYLES),
        "mood": tuple(MOOD_OPTIONS),
        "intensity": tuple(GROOVE_INTENSITY),
        "level": tuple(DIFFICULTY_LEVELS),
        "ensemble": JAM_ENSEMBLES,
    }


def record_control_values(blob: Any, owner: str) -> dict[str, Any]:
    """The control values a jam's record holds (only the settings it actually recorded)."""
    if blob is None:
        return {}
    out: dict[str, Any] = {
        "style": str(getattr(blob, "style", "") or ""),
        "mood": str(getattr(blob, "mood", "") or ""),
        "level": str(getattr(blob, "play_level", "") or ""),
        "intensity": str(getattr(blob, "play_intensity", "") or "")
        or (str(getattr(blob, "groove", "") or "") if owner == STYLE_JAM else ""),
    }
    if owner == GENERATOR:
        out["ensemble"] = str(getattr(blob, "ensemble", "") or "")
    try:
        bpm = int(getattr(blob, "tempo_bpm", 0) or 0)
    except (TypeError, ValueError):
        bpm = 0
    if bpm > 0:
        out["bpm"] = bpm
    return {k: v for k, v in out.items() if v not in ("", None)}


def seed_jam_controls_before_mount(session: Any, owner: str) -> dict[str, Any]:
    """Assign the owner's controls from its own record before they are drawn again.

    Only when they were not on screen in the previous run (then the widgets hold the musician's live
    choice and are left alone). Every control is assigned explicitly -- from the record when it holds
    the setting, else the control's current value when that is a real option -- so a redrawn control
    never falls back to its first option. Returns what was assigned.
    """
    if owner not in CONTROL_KEYS or _get(session, MOUNTED_LAST_RUN_KEY[owner]):
        return {}
    rec = record_control_values(owner_record(session, owner), owner)
    opts = _control_options()
    assigned: dict[str, Any] = {}
    for setting, key in CONTROL_KEYS[owner].items():
        if setting == "bpm":
            val = rec.get("bpm") or _get(session, key)
            try:
                val = int(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                val = None
            if val:
                session[key] = val
                assigned[key] = val
            continue
        val = _option(rec.get(setting), opts[setting]) or _option(_get(session, key), opts[setting])
        if val:
            session[key] = val
            assigned[key] = val
    return assigned


def owner_control_values(session: Any, owner: str) -> dict[str, Any]:
    """The owner's own control values as they stand, as real options ('' when a value names none)."""
    opts = _control_options()
    out: dict[str, Any] = {}
    for setting, key in CONTROL_KEYS.get(owner, {}).items():
        if setting == "bpm":
            try:
                out["bpm"] = int(_get(session, key) or 0)
            except (TypeError, ValueError):
                out["bpm"] = 0
            continue
        out[setting] = _option(_get(session, key), opts[setting])
    return out


__all__ = [
    "CONTROL_KEYS",
    "ENTRY_MODE_FOR_OWNER",
    "GENERATOR",
    "JAM_ENSEMBLES",
    "JAM_OWNERS",
    "MOUNTED_LAST_RUN_KEY",
    "MOUNTED_THIS_RUN_KEY",
    "STYLE_JAM",
    "controls_drawn_last_run",
    "creative_jam_controls_live",
    "current_jam_owner",
    "in_jam_callback",
    "jam_callback_scope",
    "note_controls_mounted",
    "note_script_run_started",
    "owner_control_values",
    "owner_for_entry_mode",
    "owner_record",
    "record_control_values",
    "seed_jam_controls_before_mount",
]
