"""Backing Key Cycle Practice — temporary playback session (not Practice Key).

Authoritative design: ``cursor-prompts/plans/2026-09-02-key-cycle-practice.md``
plus the temporary-cycle-session correction:

- Saved Practice Key never changes.
- Temporary sounding / chart key advances after each completed scope+loop pass.
- Per-owner isolated cycle sessions; no shared ``display_key`` cycling.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from music_theory import (
    NOTE_TO_MIDI,
    key_center_token,
    normalize_root,
    split_key_center,
)

# --- Session / widget keys (stable, never a nonce) ---

BACKING_KEY_CYCLE_SESSIONS_KEY = "_backing_key_cycle_sessions"
BACKING_KEY_CYCLE_STEP_KEY = "backing_key_cycle_step"
BACKING_KEY_CYCLE_DIRECTION_KEY = "backing_key_cycle_direction"
BACKING_KEY_SPELLING_PREFS_KEY = "backing_key_spelling_prefs"
BACKING_KEY_CYCLE_START_KEY = "backing_key_cycle_start_key"
BACKING_KEY_CYCLE_UI_OWNER_KEY = "_backing_key_cycle_ui_owner"
# One-shot: after a completed pass, regenerate + autoplay the next sounding key.
BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY = "_backing_key_cycle_continue_play"
# Bounded prepared-audio bag: {sounding_key: {path, signature, bytes_hint}}
BACKING_KEY_CYCLE_PREPARED_KEY = "_backing_key_cycle_prepared"
BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY = "_backing_key_cycle_prefetch_target"
BACKING_KEY_CYCLE_PASS_GAP_KEY = "_backing_key_cycle_pass_gap"
# Hidden Streamlit bridge (karaoke-style parent button click from the audio iframe).
BACKING_KEY_CYCLE_PASS_FINISHED_LABEL = "Key cycle pass finished"
BACKING_KEY_CYCLE_PASS_FINISHED_KEY = "backing_key_cycle_pass_finished_bridge"

KEY_CYCLE_TOOLTIP = (
    "Automatically repeat the backing track in a new key after each play-through. "
    "Choose half-step or whole-step changes, moving up or down. "
    "Your selected Practice Key stays the same."
)

# Keys persisted across browser refresh (not CONTINUE_PLAY / prepared WAV blobs).
KEY_CYCLE_PERSIST_KEYS: tuple[str, ...] = (
    BACKING_KEY_CYCLE_SESSIONS_KEY,
    "backing_key_cycle_enabled",
    BACKING_KEY_CYCLE_STEP_KEY,
    BACKING_KEY_CYCLE_DIRECTION_KEY,
    BACKING_KEY_SPELLING_PREFS_KEY,
    "backing_key_cycle_enabled_ui",
    "backing_key_cycle_step_ui",
    "backing_key_cycle_direction_ui",
    BACKING_KEY_CYCLE_UI_OWNER_KEY,
)

# Status values
STATUS_OFF = "off"
STATUS_RUNNING = "running"
STATUS_HELD = "held"
STATUS_STOPPED = "stopped"

# Owner ids — isolated cycle bags
OWNER_CATALOG = "catalog"
OWNER_CUSTOM = "custom"
OWNER_COMPOSITION = "composition"
OWNER_SBI_ACTIVE = "sbi_active"
OWNER_SBI_CUSTOM = "sbi_custom"
OWNER_SBI_COMPOSITION = "sbi_composition"
OWNER_STYLE_JAM = "style_jam"
OWNER_JAM_GENERATOR = "jam_generator"
OWNER_MISSION = "mission"

CYCLE_OWNERS: tuple[str, ...] = (
    OWNER_CATALOG,
    OWNER_CUSTOM,
    OWNER_COMPOSITION,
    OWNER_SBI_ACTIVE,
    OWNER_SBI_CUSTOM,
    OWNER_SBI_COMPOSITION,
    OWNER_STYLE_JAM,
    OWNER_JAM_GENERATOR,
    OWNER_MISSION,
)

# Pitch-class → default spelling (musician-friendly; matches major-default prefs).
_DEFAULT_BLACK_SPELLING: dict[int, str] = {
    1: "Db",
    3: "Eb",
    6: "F#",
    8: "Ab",
    10: "Bb",
}

_NATURAL_SPELLING: dict[int, str] = {
    0: "C",
    2: "D",
    4: "E",
    5: "F",
    7: "G",
    9: "A",
    11: "B",
}

ENHARMONIC_SPELLING_PAIRS: tuple[tuple[str, str], ...] = (
    ("C#", "Db"),
    ("D#", "Eb"),
    ("F#", "Gb"),
    ("G#", "Ab"),
    ("A#", "Bb"),
)


def _pc_of_tonic(tonic: str) -> int:
    root = normalize_root(str(tonic or "C").strip() or "C")
    return int(NOTE_TO_MIDI.get(root, 60)) % 12


def default_spelling_prefs() -> dict[str, str]:
    return {
        "C#/Db": "Db",
        "D#/Eb": "Eb",
        "F#/Gb": "F#",
        "G#/Ab": "Ab",
        "A#/Bb": "Bb",
    }


def spelling_prefs_from_session(session: dict[str, Any]) -> dict[str, str]:
    raw = session.get(BACKING_KEY_SPELLING_PREFS_KEY)
    prefs = default_spelling_prefs()
    if isinstance(raw, dict):
        for pair, _default in list(prefs.items()):
            chosen = str(raw.get(pair) or "").strip()
            options = pair.split("/")
            if chosen in options:
                prefs[pair] = chosen
    return prefs


def _spelling_for_pc(pc: int, prefs: dict[str, str]) -> str:
    pc = int(pc) % 12
    if pc in _NATURAL_SPELLING:
        return _NATURAL_SPELLING[pc]
    pair_map = {
        1: "C#/Db",
        3: "D#/Eb",
        6: "F#/Gb",
        8: "G#/Ab",
        10: "A#/Bb",
    }
    pair = pair_map.get(pc, "")
    chosen = str(prefs.get(pair) or "").strip()
    if chosen:
        return chosen
    return _DEFAULT_BLACK_SPELLING.get(pc, _NATURAL_SPELLING.get(pc, "C"))


def cycle_concert_practice_key(
    token: str,
    *,
    semitones: int,
    spelling_prefs: dict[str, str] | None = None,
) -> str:
    """Move a key token by ``semitones``; preserve major/minor mode (pitch math only)."""
    tonic, mode = split_key_center(str(token or "C").strip() or "C")
    prefs = spelling_prefs or default_spelling_prefs()
    pc = (_pc_of_tonic(tonic) + int(semitones)) % 12
    new_tonic = _spelling_for_pc(pc, prefs)
    return key_center_token(new_tonic, mode or "major")


def cycle_sequence_length(*, interval: int) -> int:
    """Distinct keys in one full repeating cycle (12 semitone / 6 whole-tone)."""
    return 6 if int(interval) >= 2 else 12


def cycle_key_sequence(session: dict[str, Any], owner: str = "") -> list[str]:
    """One complete repeating cycle in playback order, starting at cycle start key."""
    data = get_owner_cycle_session(session, owner) or {}
    start = str(
        data.get("start_cycle_key")
        or data.get("base_practice_key")
        or current_backing_owner_practice_key(session)
        or "C"
    ).strip() or "C"
    interval = int(data.get("interval") or 1)
    if interval not in {1, 2}:
        interval = 1
    direction = str(data.get("direction") or "up")
    delta = -interval if direction == "down" else interval
    prefs = (
        data.get("spelling_prefs")
        if isinstance(data.get("spelling_prefs"), dict)
        else spelling_prefs_from_session(session)
    )
    n = cycle_sequence_length(interval=interval)
    return [
        cycle_concert_practice_key(start, semitones=i * delta, spelling_prefs=prefs)
        for i in range(n)
    ]


def cycle_sequence_index(session: dict[str, Any], owner: str = "") -> int:
    """Index of current sounding key within ``cycle_key_sequence`` (wrap-safe)."""
    data = get_owner_cycle_session(session, owner) or {}
    interval = int(data.get("interval") or 1)
    if interval not in {1, 2}:
        interval = 1
    n = cycle_sequence_length(interval=interval)
    steps = int(data.get("offset_semitones") or 0) // interval
    return int(steps) % n


def peek_cycle_key_at_delta(session: dict[str, Any], *, steps: int = 1) -> str:
    """Sounding key ``steps`` intervals ahead (1) or behind (-1) without mutating."""
    data = get_owner_cycle_session(session) or {}
    if not data:
        return current_backing_owner_practice_key(session)
    interval = int(data.get("interval") or 1)
    if interval not in {1, 2}:
        interval = 1
    direction = str(data.get("direction") or "up")
    unit = -interval if direction == "down" else interval
    prefs = (
        data.get("spelling_prefs")
        if isinstance(data.get("spelling_prefs"), dict)
        else spelling_prefs_from_session(session)
    )
    start = str(data.get("start_cycle_key") or data.get("base_practice_key") or "C").strip() or "C"
    offset = int(data.get("offset_semitones") or 0) + int(steps) * unit
    return cycle_concert_practice_key(start, semitones=offset, spelling_prefs=prefs)


def next_cycle_playback_key(session: dict[str, Any]) -> str:
    return peek_cycle_key_at_delta(session, steps=1)


def previous_cycle_playback_key(session: dict[str, Any]) -> str:
    return peek_cycle_key_at_delta(session, steps=-1)


def clear_key_cycle_prepared_audio(session: dict[str, Any]) -> None:
    session.pop(BACKING_KEY_CYCLE_PREPARED_KEY, None)
    session.pop(BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY, None)
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    # Bump cancel generation so in-flight prefetch threads abandon work.
    session["_kc_prefetch_gen"] = int(session.get("_kc_prefetch_gen") or 0) + 1
    session["_kc_prefetch_cancel"] = True


def key_cycle_prefetch_generation(session: dict[str, Any]) -> int:
    return int(session.get("_kc_prefetch_gen") or 0)


def arm_key_cycle_prefetch(session: dict[str, Any]) -> int:
    """Clear cancel flag and return the generation token for a new prefetch job."""
    session["_kc_prefetch_cancel"] = False
    gen = int(session.get("_kc_prefetch_gen") or 0)
    session["_kc_prefetch_gen"] = gen
    return gen


def key_cycle_prefetch_still_valid(session: dict[str, Any], gen: int) -> bool:
    if bool(session.get("_kc_prefetch_cancel")):
        return False
    if not is_cycle_active(session):
        return False
    return int(session.get("_kc_prefetch_gen") or 0) == int(gen)


def store_prepared_cycle_audio(
    session: dict[str, Any],
    *,
    sounding_key: str,
    signature: Any,
    wav_path: str = "",
) -> None:
    """Remember at most two prepared keys (current neighbor + next) by path/sig only."""
    key = str(sounding_key or "").strip()
    if not key:
        return
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not isinstance(bag, dict):
        bag = {}
    bag[key] = {
        "signature": signature,
        "path": str(wav_path or "").strip(),
    }
    # Bound memory: keep current + next + previous at most.
    keep = {
        temporary_playback_key(session),
        next_cycle_playback_key(session),
        previous_cycle_playback_key(session),
        key,
    }
    for stale in list(bag.keys()):
        if stale not in keep:
            bag.pop(stale, None)
    session[BACKING_KEY_CYCLE_PREPARED_KEY] = bag


def promote_prepared_cycle_audio(session: dict[str, Any], sounding_key: str) -> bool:
    """If prepared audio exists for ``sounding_key``, install it as the live WAV."""
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return False
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return False
    path = str(entry.get("path") or "").strip()
    sig = entry.get("signature")
    if not path or sig is None:
        return False
    try:
        from pathlib import Path

        if not Path(path).is_file():
            return False
    except Exception:
        return False
    session["_last_backing_wav_path"] = path
    session["_last_backing_signature"] = sig
    session.pop("_last_backing_wav", None)
    session.pop("_last_backing_wav_b64", None)
    return True


def mark_cycle_pass_ended_clock(session: dict[str, Any]) -> None:
    import time

    session[BACKING_KEY_CYCLE_PASS_GAP_KEY] = {"ended_at": time.time()}


def mark_cycle_next_pass_ready_clock(session: dict[str, Any]) -> float | None:
    """Return gap seconds from prior pass end → next audio ready, if measurable."""
    import time

    raw = session.get(BACKING_KEY_CYCLE_PASS_GAP_KEY)
    if not isinstance(raw, dict):
        return None
    ended = raw.get("ended_at")
    if not ended:
        return None
    gap = max(0.0, float(time.time()) - float(ended))
    session[BACKING_KEY_CYCLE_PASS_GAP_KEY] = {
        "ended_at": ended,
        "ready_at": time.time(),
        "gap_s": gap,
    }
    try:
        import json
        import os
        from pathlib import Path

        data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data.mkdir(parents=True, exist_ok=True)
        with (data / "_key_cycle_pass_gaps.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "gap_s": gap, "sounding": temporary_playback_key(session)}) + "\n")
    except Exception:
        pass
    return gap


def cycle_step_semitones(session: dict[str, Any]) -> int:
    step = str(session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone").strip().lower()
    direction = str(session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up").strip().lower()
    magnitude = 2 if step in {"whole", "wholetone", "whole_tone", "whole tone"} else 1
    return magnitude if direction != "down" else -magnitude


def resolve_cycle_owner(session: dict[str, Any]) -> str:
    """Backing owner bag for the current page (isolated cycle sessions)."""
    page = str(session.get("studio_page") or "").strip().lower()
    src = ""
    try:
        from creative_key_sync import live_backing_source

        src = str(live_backing_source(session) or "").strip()
    except ImportError:
        src = str(session.get("_backing_explicit_handoff_source") or "").strip()
    if page != "backing":
        # Off Backing: keep last UI owner sticky for inspect only; default catalog.
        return str(session.get(BACKING_KEY_CYCLE_UI_OWNER_KEY) or OWNER_CATALOG).strip() or OWNER_CATALOG

    if src == "mission":
        return OWNER_MISSION
    if src == "custom_progression":
        return OWNER_CUSTOM
    if src in {"composition_song", "composition"}:
        return OWNER_COMPOSITION
    if src == "entry_jam":
        entry = str(session.get("improv_entry_mode") or "").strip()
        try:
            from backing_context import get_backing_context

            ctx = get_backing_context(session)
            if ctx is not None:
                entry = str(getattr(ctx, "entry_mode", "") or entry).strip()
        except Exception:
            pass
        if "Style Jam" in entry:
            return OWNER_STYLE_JAM
        return OWNER_JAM_GENERATOR
    if src == "song_improv":
        preview = ""
        try:
            from source_session_state import get_sbi_preview_source

            preview = str(get_sbi_preview_source(session) or "").strip()
        except ImportError:
            preview = str(session.get("sbi_preview_source") or "").strip()
        if preview == "Custom progression":
            return OWNER_SBI_CUSTOM
        if preview == "Composition":
            return OWNER_SBI_COMPOSITION
        return OWNER_SBI_ACTIVE
    # Catalog / regular_song — refuse Shape leak into other owners via pick checks elsewhere.
    try:
        from songs.music_source import composition_song_is_active, picker_composition_mode

        if composition_song_is_active(session) or picker_composition_mode(session):
            return OWNER_COMPOSITION
    except ImportError:
        pass
    return OWNER_CATALOG


def _empty_session(
    *,
    owner: str,
    base_key: str,
    start_key: str,
    interval: int,
    direction: str,
    spelling_prefs: dict[str, str],
) -> dict[str, Any]:
    base = str(base_key or "C").strip() or "C"
    start = str(start_key or base).strip() or base
    return {
        "owner": owner,
        "status": STATUS_OFF,
        "enabled": False,
        "base_practice_key": base,
        "start_cycle_key": start,
        "current_playback_key": start,
        "offset_semitones": 0,
        "interval": 1 if int(interval) not in {1, 2} else int(interval),
        "direction": "down" if str(direction).lower() == "down" else "up",
        "spelling_prefs": dict(spelling_prefs or default_spelling_prefs()),
        "pass_index": 0,
        "passes_completed": 0,
        "pending_pass_advance": False,
        "last_pass_signature": "",
    }


def _sessions_bag(session: dict[str, Any]) -> dict[str, Any]:
    bag = session.get(BACKING_KEY_CYCLE_SESSIONS_KEY)
    if not isinstance(bag, dict):
        bag = {}
        session[BACKING_KEY_CYCLE_SESSIONS_KEY] = bag
    return bag


def get_owner_cycle_session(session: dict[str, Any], owner: str = "") -> dict[str, Any] | None:
    owner = str(owner or resolve_cycle_owner(session) or "").strip()
    if not owner:
        return None
    bag = _sessions_bag(session)
    raw = bag.get(owner)
    return dict(raw) if isinstance(raw, dict) else None


def _put_owner_cycle_session(session: dict[str, Any], owner: str, data: dict[str, Any]) -> None:
    bag = _sessions_bag(session)
    bag[owner] = dict(data)
    session[BACKING_KEY_CYCLE_SESSIONS_KEY] = bag
    session[BACKING_KEY_CYCLE_UI_OWNER_KEY] = owner


def current_backing_owner_practice_key(session: dict[str, Any]) -> str:
    """Canonical saved Practice Key for the current Backing owner (never the cycle key)."""
    try:
        from backing_practice_key_control import canonical_concert_key_for_owner

        owned = str(canonical_concert_key_for_owner(session) or "").strip()
        if owned:
            return owned
    except ImportError:
        pass
    owner = resolve_cycle_owner(session)
    try:
        from creative_key_sync import live_backing_source

        src = live_backing_source(session)
    except ImportError:
        src = ""
    page = str(session.get("studio_page") or "").strip().lower()
    if owner == OWNER_STYLE_JAM or (page == "backing" and src == "entry_jam" and "Style Jam" in str(session.get("improv_entry_mode") or "")):
        tok = str(session.get("improv_style_key") or "").strip()
        if tok:
            return tok
    if owner == OWNER_JAM_GENERATOR:
        try:
            from generated_jam_key_context import GENERATED_JAM_KEY_CONTEXT_KEY

            raw = session.get(GENERATED_JAM_KEY_CONTEXT_KEY)
            if isinstance(raw, dict):
                tok = str(raw.get("practice_key_token") or "").strip()
                if tok:
                    return tok
        except ImportError:
            pass
        return str(session.get("improv_jam_key") or session.get("display_key") or "C").strip() or "C"
    if owner == OWNER_MISSION:
        try:
            from creative_key_sync import canonical_mission_practice_key

            tok = str(canonical_mission_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
    if owner in {OWNER_CUSTOM, OWNER_SBI_CUSTOM}:
        try:
            from source_session_state import resolve_sbi_custom_practice_key

            tok = str(resolve_sbi_custom_practice_key(session) or "").strip()
            if tok:
                return tok
        except ImportError:
            pass
        return str(session.get("display_key") or "C").strip() or "C"
    if owner in {OWNER_COMPOSITION, OWNER_SBI_COMPOSITION}:
        try:
            from composition_session_state import get_active_document
            from composition_songs_bridge import composition_home_key

            doc = get_active_document(session)
            if isinstance(doc, dict):
                tok = str(composition_home_key(doc) or "").strip()
                if tok:
                    return tok
        except ImportError:
            pass
    try:
        from songs.practice_key_state import get_practice_concert_key, resolve_practice_source_pick

        pick = str(resolve_practice_source_pick(session) or "").strip()
        if pick and not pick.startswith("creative::"):
            saved = str(get_practice_concert_key(session, pick) or "").strip()
            if saved:
                return saved
    except ImportError:
        pass
    return str(session.get("display_key") or session.get("concert_key") or "C").strip() or "C"


def is_cycle_active(session: dict[str, Any], owner: str = "") -> bool:
    data = get_owner_cycle_session(session, owner)
    if not data:
        return False
    return bool(data.get("enabled")) and str(data.get("status") or "") in {
        STATUS_RUNNING,
        STATUS_HELD,
    }


def temporary_playback_key(session: dict[str, Any], owner: str = "") -> str:
    """Current temporary sounding key, or empty when cycle is off."""
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return ""
    if str(data.get("status") or "") not in {STATUS_RUNNING, STATUS_HELD}:
        return ""
    return str(data.get("current_playback_key") or "").strip()


def effective_backing_playback_key(session: dict[str, Any], base_key: str = "") -> str:
    """Key used for Backing audio + temporary charts. Never writes Practice Key."""
    base = str(base_key or current_backing_owner_practice_key(session) or "C").strip() or "C"
    temp = temporary_playback_key(session)
    return temp or base


def start_key_cycle(
    session: dict[str, Any],
    *,
    start_key: str = "",
    interval: int | None = None,
    direction: str = "",
    spelling_prefs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Begin a temporary cycle for the current Backing owner."""
    owner = resolve_cycle_owner(session)
    base = current_backing_owner_practice_key(session)
    prefs = spelling_prefs or spelling_prefs_from_session(session)
    step = cycle_step_semitones(session) if interval is None else (
        (2 if int(interval) >= 2 else 1) * (-1 if str(direction).lower() == "down" else 1)
    )
    mag = abs(int(step)) or 1
    direc = "down" if int(step) < 0 else "up"
    if direction:
        direc = "down" if str(direction).lower() == "down" else "up"
    if interval is not None:
        mag = 2 if int(interval) >= 2 else 1
    # New cycles always begin at Saved Practice Key unless a caller passes start_key
    # (tests). There is no musician-facing start-key control.
    start = str(start_key or base).strip() or base
    # Preserve mode from base when start is tonic-only.
    _bt, base_mode = split_key_center(base)
    st_tonic, st_mode = split_key_center(start)
    if not st_mode and base_mode:
        start = key_center_token(st_tonic, base_mode)
    data = _empty_session(
        owner=owner,
        base_key=base,
        start_key=start,
        interval=mag,
        direction=direc,
        spelling_prefs=prefs,
    )
    data["status"] = STATUS_RUNNING
    data["enabled"] = True
    data["current_playback_key"] = start
    data["offset_semitones"] = 0
    _put_owner_cycle_session(session, owner, data)
    session["backing_key_cycle_enabled"] = True
    clear_key_cycle_prepared_audio(session)
    # Invalidate backing so next generate uses temporary key.
    session.pop("_last_backing_wav", None)
    session.pop("_last_backing_signature", None)
    return data


def pause_key_cycle(session: dict[str, Any]) -> dict[str, Any] | None:
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return data
    data = dict(data)
    data["status"] = STATUS_HELD
    _put_owner_cycle_session(session, owner, data)
    return data


def resume_key_cycle(session: dict[str, Any]) -> dict[str, Any] | None:
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return data
    data = dict(data)
    data["status"] = STATUS_RUNNING
    _put_owner_cycle_session(session, owner, data)
    return data


def advance_key_cycle_now(session: dict[str, Any]) -> dict[str, Any] | None:
    """Manual Next key — move forward one interval (does not mutate Practice Key)."""
    return _step_owner_cycle(session, steps=1, force=True)


def previous_key_cycle_now(session: dict[str, Any]) -> dict[str, Any] | None:
    """Manual Previous key — move backward one interval (wraps via offset math)."""
    return _step_owner_cycle(session, steps=-1, force=True)


def stop_key_cycle(session: dict[str, Any]) -> dict[str, Any] | None:
    """End cycling; restore playback/charts to unchanged saved Practice Key."""
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    base = current_backing_owner_practice_key(session)
    if not data:
        data = _empty_session(
            owner=owner,
            base_key=base,
            start_key=base,
            interval=1,
            direction="up",
            spelling_prefs=spelling_prefs_from_session(session),
        )
    else:
        data = dict(data)
        data["base_practice_key"] = str(data.get("base_practice_key") or base).strip() or base
    data["status"] = STATUS_STOPPED
    data["enabled"] = False
    data["current_playback_key"] = data["base_practice_key"]
    data["offset_semitones"] = 0
    data["pending_pass_advance"] = False
    _put_owner_cycle_session(session, owner, data)
    clear_key_cycle_prepared_audio(session)
    session["backing_key_cycle_enabled"] = False
    # Defer Off sync until before the Off/On radio remounts (widget-safe).
    session["_key_cycle_force_ui_off"] = True
    try:
        from songs.key_state import invalidate_backing_cache

        invalidate_backing_cache(session)
    except Exception:
        session.pop("_last_backing_wav", None)
        session.pop("_last_backing_signature", None)
        session.pop("_last_backing_wav_path", None)
    return data


def end_key_cycle_on_page_leave(session: dict[str, Any]) -> None:
    """True leave from Backing: stop cycle and reset config defaults (not refresh)."""
    try:
        if is_cycle_active(session):
            stop_key_cycle(session)
    except Exception:
        pass
    clear_key_cycle_prepared_audio(session)
    session[BACKING_KEY_CYCLE_SESSIONS_KEY] = {}
    session["backing_key_cycle_enabled"] = False
    session[BACKING_KEY_CYCLE_STEP_KEY] = "semitone"
    session[BACKING_KEY_CYCLE_DIRECTION_KEY] = "up"
    session[BACKING_KEY_SPELLING_PREFS_KEY] = default_spelling_prefs()
    session["backing_key_cycle_enabled_ui"] = "Off"
    session["backing_key_cycle_step_ui"] = "semitone"
    session["backing_key_cycle_direction_ui"] = "up"
    session["_key_cycle_force_ui_off"] = True
    # Drop spelling widget keys so defaults remount cleanly.
    for sharp, flat in ENHARMONIC_SPELLING_PAIRS:
        session.pop(f"backing_key_spell__{sharp}/{flat}", None)


def _step_owner_cycle(
    session: dict[str, Any],
    *,
    steps: int = 1,
    force: bool = False,
) -> dict[str, Any] | None:
    """Move temporary sounding key by ``steps`` intervals (+forward / −back)."""
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return data
    status = str(data.get("status") or "")
    if status == STATUS_HELD and not force:
        return data
    if status not in {STATUS_RUNNING, STATUS_HELD}:
        return data
    data = dict(data)
    mag = int(data.get("interval") or 1)
    if mag not in {1, 2}:
        mag = 1
    unit = -mag if str(data.get("direction") or "up") == "down" else mag
    delta = int(steps) * unit
    prefs = data.get("spelling_prefs") if isinstance(data.get("spelling_prefs"), dict) else spelling_prefs_from_session(session)
    start = str(data.get("start_cycle_key") or data.get("base_practice_key") or "C").strip() or "C"
    new_offset = int(data.get("offset_semitones") or 0) + delta
    new_key = cycle_concert_practice_key(start, semitones=new_offset, spelling_prefs=prefs)
    data["offset_semitones"] = new_offset
    data["current_playback_key"] = new_key
    data["pass_index"] = int(data.get("pass_index") or 0) + (1 if steps > 0 else 0)
    if steps > 0:
        data["passes_completed"] = int(data.get("passes_completed") or 0) + 1
    data["pending_pass_advance"] = False
    if status == STATUS_HELD and force:
        data["status"] = STATUS_RUNNING
    _put_owner_cycle_session(session, owner, data)

    # Clear live session WAV; prefer promoting a prepared neighbor if present.
    try:
        from songs.key_state import invalidate_backing_cache

        invalidate_backing_cache(session)
    except Exception:
        session.pop("_last_backing_wav", None)
        session.pop("_last_backing_signature", None)
        session.pop("_last_backing_wav_path", None)
    promote_prepared_cycle_audio(session, new_key)
    session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
    # Ask the app to prefetch the new neighbor after this step settles.
    session[BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY] = peek_cycle_key_at_delta(
        session, steps=1 if steps >= 0 else -1
    )
    session["_kc_prefetch_armed"] = False
    return data


def _advance_owner_cycle(session: dict[str, Any], *, force: bool = False) -> dict[str, Any] | None:
    return _step_owner_cycle(session, steps=1, force=force)


def note_backing_pass_finished(session: dict[str, Any], *, pass_signature: str = "") -> bool:
    """Advance after a real scope+loop completion. Reruns must not call this casually.

    Returns True when the temporary key advanced.
    """
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return False
    if str(data.get("status") or "") != STATUS_RUNNING:
        return False
    sig = str(pass_signature or "").strip()
    # Duplicate ended/bridge clicks while next-pass regen is queued. Distinct
    # non-audio pass signatures (unit / manual sequencing) may clear the flag.
    if session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY):
        last = str(data.get("last_pass_signature") or "")
        if not sig or sig == last:
            return False
        if sig.startswith("audio_ended::") and last.startswith("audio_ended::"):
            return False
        session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    if sig and sig == str(data.get("last_pass_signature") or ""):
        return False
    # One advance per generated backing signature (duplicate audio ended → no-op).
    wav_sig = str(session.get("_last_backing_signature") or "").strip()
    if wav_sig and wav_sig == str(data.get("advanced_for_wav_sig") or ""):
        return False
    data = dict(data)
    if sig:
        data["last_pass_signature"] = sig
    if wav_sig:
        data["advanced_for_wav_sig"] = wav_sig
    _put_owner_cycle_session(session, owner, data)
    before = str(data.get("current_playback_key") or "")
    after_data = _advance_owner_cycle(session, force=False)
    after = str((after_data or {}).get("current_playback_key") or "")
    advanced = bool(after and after != before)
    if advanced:
        mark_cycle_pass_ended_clock(session)
        # Next pass should autoplay (prepared hit or regen via CONTINUE_PLAY).
        session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
    return advanced


BACKING_KEY_CYCLE_PASS_QUERY = "backing_key_cycle_pass"


def maybe_consume_cycle_pass_from_query(st: Any, session: dict[str, Any]) -> bool:
    """Legacy URL-token path (kept as fallback). Prefer the parent-button bridge."""
    if not is_cycle_active(session):
        return False
    try:
        raw = st.query_params.get(BACKING_KEY_CYCLE_PASS_QUERY)
    except Exception:
        raw = None
    if raw is None:
        return False
    token = raw[0] if isinstance(raw, (list, tuple)) else raw
    token = str(token or "").strip()
    try:
        if BACKING_KEY_CYCLE_PASS_QUERY in st.query_params:
            del st.query_params[BACKING_KEY_CYCLE_PASS_QUERY]
    except Exception:
        pass
    if not token:
        return False
    return note_backing_pass_finished(session, pass_signature=f"audio_ended::{token}")


def consume_cycle_continue_play(session: dict[str, Any]) -> bool:
    """Consume one-shot autoplay-after-advance flag. False when cycle is not running."""
    if not bool(session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, False)):
        return False
    if not is_cycle_active(session):
        return False
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return False
    return True


def cycle_pass_ended_js_snippet(*, pass_token: str = "") -> str:
    """Inject into the live audio ``ended`` handler to signal Python once per play.

    Uses the same parent-document button-click bridge as karaoke auto-advance
    (reliable inside ``components.html`` iframes). ``pass_token`` dedupes duplicate
    ``ended`` events in the iframe before the click.
    """
    token = str(pass_token or "").strip() or "pass"
    safe = token.replace("\\", "\\\\").replace("'", "\\'")
    label = BACKING_KEY_CYCLE_PASS_FINISHED_LABEL.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "try {"
        f"  const token = '{safe}';"
        "  if (window.__backingKeyCyclePassConsumed === token) { return; }"
        "  window.__backingKeyCyclePassConsumed = token;"
        "  try { window.parent.__backingKeyCyclePassConsumed = token; } catch (e) {}"
        "  if (typeof detailEl !== 'undefined' && detailEl) {"
        "    detailEl.textContent = 'Pass complete — advancing Key Cycle…';"
        "  }"
        "  window.setTimeout(() => {"
        "    try {"
        "      const parentDoc = window.parent.document;"
        "      const buttons = parentDoc.querySelectorAll('button');"
        f"      const want = '{label}';"
        "      for (const b of buttons) {"
        "        if ((b.textContent || '').trim() === want) { b.click(); break; }"
        "      }"
        "    } catch (err) { console.warn('key-cycle pass bridge failed', err); }"
        "  }, 40);"
        "} catch (e) {}"
    )


def cycle_st_audio_ended_bridge_html(*, pass_token: str = "") -> str:
    """Tiny components.html doc: attach ``ended`` on parent ``st.audio`` → bridge click.

    Compact Backing (lead sheet closed) mounts Streamlit ``st.audio`` with no
    ``ended`` handler. The live-follow iframe bridge never runs on that path.
    This helper watches parent-document audio elements and clicks the same
    hidden ``Key cycle pass finished`` button used by the follow-along player.
    """
    token = str(pass_token or "").strip() or "pass"
    safe = token.replace("\\", "\\\\").replace("'", "\\'")
    label = BACKING_KEY_CYCLE_PASS_FINISHED_LABEL.replace("\\", "\\\\").replace("'", "\\'")
    return f"""<!DOCTYPE html><html><body><script>
(function () {{
  const token = '{safe}';
  const want = '{label}';
  function alreadyConsumed() {{
    try {{
      if (window.__backingKeyCyclePassConsumed === token) return true;
      if (window.parent && window.parent.__backingKeyCyclePassConsumed === token) return true;
    }} catch (e) {{}}
    return false;
  }}
  function markConsumed() {{
    window.__backingKeyCyclePassConsumed = token;
    try {{ window.parent.__backingKeyCyclePassConsumed = token; }} catch (e) {{}}
  }}
  function clickBridge() {{
    if (alreadyConsumed()) return;
    markConsumed();
    window.setTimeout(() => {{
      try {{
        const parentDoc = window.parent.document;
        const buttons = parentDoc.querySelectorAll('button');
        for (const b of buttons) {{
          if ((b.textContent || '').trim() === want) {{ b.click(); break; }}
        }}
      }} catch (err) {{
        console.warn('key-cycle st.audio bridge failed', err);
      }}
    }}, 40);
  }}
  function attach(audio) {{
    if (!audio || audio.__kcEndedHooked === token) return;
    audio.__kcEndedHooked = token;
    audio.addEventListener('ended', clickBridge);
    try {{
      if (audio.ended && Number(audio.duration) > 0.2) clickBridge();
    }} catch (e) {{}}
  }}
  function scan() {{
    try {{
      const parentDoc = window.parent.document;
      const seen = new Set();
      function walk(node) {{
        if (!node || seen.has(node)) return;
        seen.add(node);
        if (node.querySelectorAll) {{
          node.querySelectorAll('audio').forEach(attach);
        }}
        const children = node.children || [];
        for (const child of children) {{
          if (child.shadowRoot) walk(child.shadowRoot);
          walk(child);
        }}
      }}
      walk(parentDoc);
      parentDoc.querySelectorAll('iframe').forEach((frame) => {{
        try {{
          const doc = frame.contentDocument;
          if (doc) {{
            doc.querySelectorAll('audio').forEach(attach);
            if (doc.body) walk(doc.body);
          }}
        }} catch (e) {{}}
      }});
    }} catch (e) {{}}
  }}
  scan();
  window.setInterval(scan, 400);
}})();
</script></body></html>"""


def cycle_compact_audio_player_html(
    *,
    audio_b64: str,
    pass_token: str = "",
    autoplay: bool = True,
) -> str:
    """Owned HTML5 audio + ended→bridge click for compact Backing (no lead sheet).

    ``st.audio`` never delivers ``ended`` to Python. When Key Cycle is RUNNING we
    mount this same-iframe player instead so the natural ended event and the
    parent-button bridge share one document context (karaoke-style).
    """
    token = str(pass_token or "").strip() or "pass"
    safe = token.replace("\\", "\\\\").replace("'", "\\'")
    label = BACKING_KEY_CYCLE_PASS_FINISHED_LABEL.replace("\\", "\\\\").replace("'", "\\'")
    autoplay_attr = "autoplay" if autoplay else ""
    # Keep payload in a JS string assignment via template; b64 is WAV-safe charset.
    b64 = str(audio_b64 or "").strip()
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  audio {{ width: 100%; display: block; }}
  #kc-detail {{ font: 12px/1.35 system-ui, sans-serif; opacity: 0.75; margin-top: 4px; }}
</style></head>
<body>
  <audio id="kc-cycle-audio" controls preload="auto" {autoplay_attr}
    src="data:audio/wav;base64,{b64}"></audio>
  <div id="kc-detail"></div>
  <script>
  (function () {{
    const token = '{safe}';
    const want = '{label}';
    const audio = document.getElementById('kc-cycle-audio');
    const detailEl = document.getElementById('kc-detail');
    function clickBridge() {{
      try {{
        if (window.__backingKeyCyclePassConsumed === token) return;
        window.__backingKeyCyclePassConsumed = token;
        try {{ window.parent.__backingKeyCyclePassConsumed = token; }} catch (e) {{}}
        if (detailEl) detailEl.textContent = 'Pass complete — advancing Key Cycle…';
        window.setTimeout(() => {{
          try {{
            const parentDoc = window.parent.document;
            const buttons = parentDoc.querySelectorAll('button');
            for (const b of buttons) {{
              if ((b.textContent || '').trim() === want) {{ b.click(); break; }}
            }}
          }} catch (err) {{
            console.warn('key-cycle compact audio bridge failed', err);
          }}
        }}, 40);
      }} catch (e) {{}}
    }}
    if (audio) {{
      audio.addEventListener('ended', clickBridge);
    }}
  }})();
  </script>
</body></html>"""


def render_backing_key_cycle_st_audio_bridge(st: Any, session: dict[str, Any]) -> None:
    """Mount the compact-path audio-ended → Python bridge while cycling is RUNNING."""
    if not is_cycle_active(session):
        return
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return
    wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
    token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
    try:
        import streamlit.components.v1 as components

        components.html(
            cycle_st_audio_ended_bridge_html(pass_token=token),
            height=1,
            scrolling=False,
        )
    except Exception:
        pass


def render_backing_key_cycle_compact_audio(
    st: Any,
    session: dict[str, Any],
    *,
    audio_b64: str,
    autoplay: bool = True,
) -> bool:
    """Mount compact cycle audio player. Returns True when mounted."""
    if not is_cycle_active(session):
        return False
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return False
    b64 = str(audio_b64 or "").strip()
    if not b64:
        return False
    wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
    token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
    try:
        import streamlit.components.v1 as components

        components.html(
            cycle_compact_audio_player_html(
                audio_b64=b64,
                pass_token=token,
                autoplay=bool(autoplay),
            ),
            height=88,
            scrolling=False,
        )
        return True
    except Exception:
        return False


def render_backing_key_cycle_pass_bridge(st: Any, session: dict[str, Any]) -> None:
    """Hidden Streamlit button clicked from the audio iframe when a pass ends."""
    if not is_cycle_active(session):
        return
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return
    # Visually hide; iframe JS still finds the button by exact label text.
    st.markdown(
        f"""
<style>
div[class*="st-key-{BACKING_KEY_CYCLE_PASS_FINISHED_KEY}"] {{
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: 0 !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
  opacity: 0 !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )
    if st.button(
        BACKING_KEY_CYCLE_PASS_FINISHED_LABEL,
        key=BACKING_KEY_CYCLE_PASS_FINISHED_KEY,
        type="secondary",
    ):
        wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
        token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
        advanced = note_backing_pass_finished(session, pass_signature=f"audio_ended::{token}")
        try:
            import json
            import os
            import time
            from pathlib import Path

            data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
            data.mkdir(parents=True, exist_ok=True)
            with (data / "_key_cycle_bridge_clicks.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "advanced": bool(advanced),
                            "token": token,
                            "sounding": temporary_playback_key(session),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        st.rerun()


def cycle_status_lines(session: dict[str, Any]) -> list[str]:
    """Human-readable status for Advanced Settings."""
    owner = resolve_cycle_owner(session)
    base = current_backing_owner_practice_key(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return [
            "Key Cycle Practice: OFF",
            f"Saved Practice Key: {base}",
        ]
    status = str(data.get("status") or STATUS_OFF).upper()
    temp = str(data.get("current_playback_key") or base)
    saved = str(data.get("base_practice_key") or base)
    passes = int(data.get("passes_completed") or 0)
    interval = "Whole tone" if int(data.get("interval") or 1) == 2 else "Semitone"
    direction = str(data.get("direction") or "up").title()
    return [
        f"Key Cycle Practice: {status}",
        f"Owner: {owner}",
        f"Saved Practice Key: {saved}",
        f"Current Playback Key: {temp}",
        f"Interval: {interval} · Direction: {direction}",
        f"Passes completed: {passes}",
    ]


def assert_practice_key_unchanged(session: dict[str, Any], expected: str) -> bool:
    """Test helper: saved Practice Key still equals ``expected``."""
    return current_backing_owner_practice_key(session) == str(expected or "").strip()


# --- Legacy names kept for imports; no longer mutate Practice Key ---


def apply_backing_key_cycle(session: dict[str, Any], *, semitones: int | None = None) -> str:
    """Advance temporary cycle key only (compat wrapper).

    Historically this wrote Practice Key — that behavior is removed. Prefer
    ``start_key_cycle`` / ``advance_key_cycle_now`` / ``note_backing_pass_finished``.
    """
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        # Start a one-shot running session from current base if tests call apply directly.
        if semitones is not None:
            session[BACKING_KEY_CYCLE_STEP_KEY] = "whole" if abs(int(semitones)) >= 2 else "semitone"
            session[BACKING_KEY_CYCLE_DIRECTION_KEY] = "down" if int(semitones) < 0 else "up"
        start_key_cycle(session)
        if semitones is not None and int(semitones) != 0:
            # First apply historically moved immediately; keep that for unit math tests.
            _advance_owner_cycle(session, force=True)
        return temporary_playback_key(session) or current_backing_owner_practice_key(session)
    _advance_owner_cycle(session, force=True)
    return temporary_playback_key(session) or current_backing_owner_practice_key(session)


def render_backing_key_cycle_status_banner(st: Any, session: dict[str, Any]) -> None:
    """No-op: cycling status lives in Advanced / the compact playback bar only."""
    return None


def render_backing_key_cycle_controls(st: Any, session: dict[str, Any]) -> None:
    """Compact Key cycling config — must be called *inside* Advanced expander."""
    owner = resolve_cycle_owner(session)
    session[BACKING_KEY_CYCLE_UI_OWNER_KEY] = owner
    base = current_backing_owner_practice_key(session)
    active = is_cycle_active(session)

    # Segmented Off/On (stable key). Default OFF. Closing Advanced must not clear this.
    mode_key = "backing_key_cycle_enabled_ui"
    enable_flag = "backing_key_cycle_enabled"
    if session.pop("_key_cycle_force_ui_off", False):
        session[mode_key] = "Off"
    elif mode_key not in session:
        session[mode_key] = "On" if active else "Off"

    choice = st.radio(
        "Key cycling",
        options=["Off", "On"],
        horizontal=True,
        key=mode_key,
        help=KEY_CYCLE_TOOLTIP,
    )
    on = str(choice or "Off") == "On"
    session[enable_flag] = on

    if on and not active:
        # Always begin at current Practice Key (no start-key picker).
        # Do not st.rerun() here — a mid-expander rerun resets Off/On to Off.
        start_key_cycle(
            session,
            start_key=base,
            spelling_prefs=spelling_prefs_from_session(session),
        )
        active = True
    if (not on) and active:
        stop_key_cycle(session)
        active = False
        # No rerun — hide config below in this same run; playbar mounts later.
    if not on and not is_cycle_active(session):
        return

    # Compact settings only while enabled.
    step_key = "backing_key_cycle_step_ui"
    dir_key = "backing_key_cycle_direction_ui"
    session.setdefault(step_key, session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone")
    session.setdefault(dir_key, session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up")

    c1, c2 = st.columns(2)
    with c1:
        st.radio(
            "Interval",
            options=["semitone", "whole"],
            format_func=lambda v: "Semitone" if v == "semitone" else "Whole tone",
            key=step_key,
            horizontal=True,
        )
        session[BACKING_KEY_CYCLE_STEP_KEY] = str(session.get(step_key) or "semitone")
    with c2:
        st.radio(
            "Direction",
            options=["up", "down"],
            format_func=lambda v: str(v).title(),
            key=dir_key,
            horizontal=True,
        )
        session[BACKING_KEY_CYCLE_DIRECTION_KEY] = str(session.get(dir_key) or "up")

    # Keep live session bag in sync for the *next* advance (never mutates Practice Key).
    data = get_owner_cycle_session(session, owner)
    if data and data.get("enabled"):
        mag = 2 if str(session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone") == "whole" else 1
        direc = str(session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up")
        if int(data.get("interval") or 1) != mag or str(data.get("direction") or "") != direc:
            data = dict(data)
            data["interval"] = mag
            data["direction"] = direc
            _put_owner_cycle_session(session, owner, data)
            clear_key_cycle_prepared_audio(session)

    prefs = spelling_prefs_from_session(session)
    with st.expander("Chart spelling", expanded=False):
        pref_cols = st.columns(5)
        for i, (sharp, flat) in enumerate(ENHARMONIC_SPELLING_PAIRS):
            pair = f"{sharp}/{flat}"
            with pref_cols[i % 5]:
                choice_spell = st.radio(
                    pair,
                    options=[sharp, flat],
                    index=0 if prefs.get(pair, flat) == sharp else 1,
                    key=f"backing_key_spell__{pair}",
                    horizontal=True,
                    label_visibility="visible",
                )
                prefs[pair] = str(choice_spell)
        session[BACKING_KEY_SPELLING_PREFS_KEY] = prefs
        if data and data.get("enabled"):
            data = dict(get_owner_cycle_session(session, owner) or data)
            old_prefs = data.get("spelling_prefs") if isinstance(data.get("spelling_prefs"), dict) else {}
            data["spelling_prefs"] = prefs
            _put_owner_cycle_session(session, owner, data)
            if old_prefs != prefs:
                clear_key_cycle_prepared_audio(session)


def render_backing_key_cycle_playback_bar(st: Any, session: dict[str, Any]) -> None:
    """Compact Pause / Previous / Next / Turn off + key sequence near the player."""
    if not is_cycle_active(session):
        return
    session["backing_key_cycle_enabled"] = True
    data = get_owner_cycle_session(session) or {}
    sounding = str(data.get("current_playback_key") or temporary_playback_key(session) or "").strip()
    saved = str(data.get("base_practice_key") or current_backing_owner_practice_key(session)).strip()
    held = str(data.get("status") or "") == STATUS_HELD
    pause_label = "Resume" if held else "Pause"
    sequence = cycle_key_sequence(session)
    idx = cycle_sequence_index(session)

    chips = []
    for i, key_tok in enumerate(sequence):
        label = html_escape(key_tok)
        if i == idx:
            chips.append(
                f'<span class="ui-key-cycle-chip ui-key-cycle-chip-on" data-current="1"'
                f' data-key="{label}">{label}</span>'
            )
        else:
            chips.append(
                f'<span class="ui-key-cycle-chip" data-key="{label}">{label}</span>'
            )

    # st.html preserves classes/styles that st.markdown sanitizes away.
    bar_html = (
        "<style>"
        ".ui-key-cycle-playbar{display:flex;flex-direction:column;gap:.35rem;"
        "margin:.35rem 0;font-size:.85rem;opacity:.95}"
        ".ui-key-cycle-chip{display:inline-block;padding:.12rem .4rem;margin:.1rem;"
        "border-radius:999px;background:rgba(127,127,127,.18);font-size:.8rem;opacity:.85}"
        ".ui-key-cycle-chip-on{background:#1f6feb!important;color:#fff!important;"
        "font-weight:700!important;opacity:1!important}"
        "</style>"
        f'<div class="ui-key-cycle-playbar">'
        f'<div><span>Sounding <strong>{html_escape(sounding) or "—"}</strong>'
        f'<span style="opacity:.65"> · saved {html_escape(saved) or "—"}</span></span></div>'
        f'<div class="ui-key-cycle-seq" style="display:flex;flex-wrap:wrap;align-items:center;'
        f'gap:.05rem;line-height:1.6" title="One full cycle in playback order">'
        f'{"".join(chips)}</div></div>'
    )
    try:
        st.html(bar_html)
    except Exception:
        st.markdown(bar_html, unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button(pause_label, key="backing_key_cycle_pause_btn", use_container_width=True):
            if held:
                resume_key_cycle(session)
            else:
                pause_key_cycle(session)
            st.rerun()
    with b2:
        if st.button("Previous key", key="backing_key_cycle_prev_btn", use_container_width=True):
            previous_key_cycle_now(session)
            st.rerun()
    with b3:
        if st.button("Next key", key="backing_key_cycle_advance_btn", use_container_width=True):
            advance_key_cycle_now(session)
            st.rerun()
    with b4:
        if st.button(
            "Turn off cycling",
            key="backing_key_cycle_stop_btn",
            use_container_width=True,
        ):
            stop_key_cycle(session)
            st.rerun()


def html_escape(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY",
    "BACKING_KEY_CYCLE_DIRECTION_KEY",
    "BACKING_KEY_CYCLE_PASS_FINISHED_KEY",
    "BACKING_KEY_CYCLE_PASS_FINISHED_LABEL",
    "BACKING_KEY_CYCLE_PREPARED_KEY",
    "BACKING_KEY_CYCLE_SESSIONS_KEY",
    "BACKING_KEY_CYCLE_START_KEY",
    "BACKING_KEY_CYCLE_STEP_KEY",
    "BACKING_KEY_SPELLING_PREFS_KEY",
    "CYCLE_OWNERS",
    "ENHARMONIC_SPELLING_PAIRS",
    "KEY_CYCLE_PERSIST_KEYS",
    "KEY_CYCLE_TOOLTIP",
    "OWNER_CATALOG",
    "OWNER_COMPOSITION",
    "OWNER_CUSTOM",
    "OWNER_JAM_GENERATOR",
    "OWNER_MISSION",
    "OWNER_SBI_ACTIVE",
    "OWNER_SBI_COMPOSITION",
    "OWNER_SBI_CUSTOM",
    "OWNER_STYLE_JAM",
    "STATUS_HELD",
    "STATUS_OFF",
    "STATUS_RUNNING",
    "STATUS_STOPPED",
    "advance_key_cycle_now",
    "apply_backing_key_cycle",
    "arm_key_cycle_prefetch",
    "assert_practice_key_unchanged",
    "clear_key_cycle_prepared_audio",
    "consume_cycle_continue_play",
    "current_backing_owner_practice_key",
    "cycle_compact_audio_player_html",
    "cycle_concert_practice_key",
    "cycle_key_sequence",
    "cycle_pass_ended_js_snippet",
    "cycle_sequence_index",
    "cycle_sequence_length",
    "cycle_st_audio_ended_bridge_html",
    "cycle_status_lines",
    "cycle_step_semitones",
    "default_spelling_prefs",
    "effective_backing_playback_key",
    "end_key_cycle_on_page_leave",
    "get_owner_cycle_session",
    "is_cycle_active",
    "key_cycle_prefetch_generation",
    "key_cycle_prefetch_still_valid",
    "mark_cycle_next_pass_ready_clock",
    "mark_cycle_pass_ended_clock",
    "maybe_consume_cycle_pass_from_query",
    "next_cycle_playback_key",
    "note_backing_pass_finished",
    "pause_key_cycle",
    "peek_cycle_key_at_delta",
    "previous_cycle_playback_key",
    "previous_key_cycle_now",
    "promote_prepared_cycle_audio",
    "render_backing_key_cycle_compact_audio",
    "render_backing_key_cycle_controls",
    "render_backing_key_cycle_pass_bridge",
    "render_backing_key_cycle_playback_bar",
    "render_backing_key_cycle_st_audio_bridge",
    "render_backing_key_cycle_status_banner",
    "resolve_cycle_owner",
    "resume_key_cycle",
    "spelling_prefs_from_session",
    "start_key_cycle",
    "stop_key_cycle",
    "store_prepared_cycle_audio",
    "temporary_playback_key",
]
