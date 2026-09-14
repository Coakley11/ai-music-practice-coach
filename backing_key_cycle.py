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
    start = str(start_key or session.get(BACKING_KEY_CYCLE_START_KEY) or base).strip() or base
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
    """Manual advance to the next temporary key (does not mutate Practice Key)."""
    return _advance_owner_cycle(session, force=True)


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
    session.pop("_last_backing_wav", None)
    session.pop("_last_backing_signature", None)
    return data


def _advance_owner_cycle(session: dict[str, Any], *, force: bool = False) -> dict[str, Any] | None:
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
    delta = -mag if str(data.get("direction") or "up") == "down" else mag
    prefs = data.get("spelling_prefs") if isinstance(data.get("spelling_prefs"), dict) else spelling_prefs_from_session(session)
    start = str(data.get("start_cycle_key") or data.get("base_practice_key") or "C").strip() or "C"
    new_offset = int(data.get("offset_semitones") or 0) + delta
    new_key = cycle_concert_practice_key(start, semitones=new_offset, spelling_prefs=prefs)
    data["offset_semitones"] = new_offset
    data["current_playback_key"] = new_key
    data["pass_index"] = int(data.get("pass_index") or 0) + 1
    data["passes_completed"] = int(data.get("passes_completed") or 0) + 1
    data["pending_pass_advance"] = False
    if status == STATUS_HELD and force:
        data["status"] = STATUS_RUNNING
    _put_owner_cycle_session(session, owner, data)
    session.pop("_last_backing_wav", None)
    session.pop("_last_backing_signature", None)
    return data


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
    return bool(after and after != before)


BACKING_KEY_CYCLE_PASS_QUERY = "backing_key_cycle_pass"


def maybe_consume_cycle_pass_from_query(st: Any, session: dict[str, Any]) -> bool:
    """Consume an audio-ended pass signal from the URL (one advance max per token)."""
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


def cycle_pass_ended_js_snippet(*, pass_token: str = "") -> str:
    """Inject into the live audio ``ended`` handler to signal Python once per play.

    Uses a stable ``pass_token`` (backing signature) so duplicate ``ended`` events
    cannot advance the cycle twice for the same generated pass.
    """
    token = str(pass_token or "").strip() or "pass"
    # Escape for JS string literal
    safe = token.replace("\\", "\\\\").replace("'", "\\'")
    return (
        "try {"
        f"  const token = '{safe}';"
        "  if (window.__backingKeyCyclePassConsumed === token) { return; }"
        "  window.__backingKeyCyclePassConsumed = token;"
        f"  const u = new URL(window.parent.location.href);"
        f"  u.searchParams.set('{BACKING_KEY_CYCLE_PASS_QUERY}', token);"
        "  window.parent.location.href = u.toString();"
        "} catch (e) {}"
    )


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
    """Always-visible status when a cycle is active (outside the Advanced expander)."""
    if not is_cycle_active(session):
        return
    lines = cycle_status_lines(session)
    # Compact single card so browser walks and musicians both see sounding vs saved.
    joined = " · ".join(lines[:4])
    st.info(joined)


def render_backing_key_cycle_controls(st: Any, session: dict[str, Any]) -> None:
    """Key Cycle Practice controls under Advanced playback settings."""
    owner = resolve_cycle_owner(session)
    session[BACKING_KEY_CYCLE_UI_OWNER_KEY] = owner
    base = current_backing_owner_practice_key(session)
    data = get_owner_cycle_session(session, owner)

    st.markdown("##### Key Cycle Practice")
    st.caption(
        "Temporary playback/chart transposition. Saved Practice Key never changes."
    )
    for line in cycle_status_lines(session):
        st.markdown(f"- {line}")

    try:
        from music_theory import display_key_options

        key_opts = list(display_key_options() or [])
    except Exception:
        key_opts = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    # Include minor forms for the start picker when base is minor.
    _tonic, mode = split_key_center(base)
    if mode == "minor":
        minor_opts = []
        for k in key_opts:
            t, m = split_key_center(k)
            if m == "minor":
                minor_opts.append(k)
            else:
                minor_opts.append(key_center_token(t, "minor"))
        # de-dupe
        seen: set[str] = set()
        key_opts = []
        for k in minor_opts:
            if k not in seen:
                seen.add(k)
                key_opts.append(k)

    step_key = f"backing_key_cycle_step__{owner}"
    dir_key = f"backing_key_cycle_direction__{owner}"
    start_key = f"backing_key_cycle_start__{owner}"
    session.setdefault(BACKING_KEY_CYCLE_STEP_KEY, session.get(step_key) or "semitone")
    session.setdefault(BACKING_KEY_CYCLE_DIRECTION_KEY, session.get(dir_key) or "up")

    c1, c2 = st.columns(2)
    with c1:
        st.selectbox(
            "Interval",
            options=["semitone", "whole"],
            format_func=lambda v: "Semitone" if v == "semitone" else "Whole tone",
            key=step_key,
        )
        session[BACKING_KEY_CYCLE_STEP_KEY] = str(session.get(step_key) or "semitone")
    with c2:
        st.selectbox(
            "Direction",
            options=["up", "down"],
            format_func=lambda v: str(v).title(),
            key=dir_key,
        )
        session[BACKING_KEY_CYCLE_DIRECTION_KEY] = str(session.get(dir_key) or "up")

    default_start = str((data or {}).get("start_cycle_key") or base).strip() or base
    if start_key not in session:
        session[start_key] = default_start if default_start in key_opts else (
            key_opts[0] if key_opts else default_start
        )
    st.selectbox(
        "Starting cycle key",
        options=key_opts or [default_start],
        key=start_key,
        help="Temporary start only — does not change Saved Practice Key.",
    )
    session[BACKING_KEY_CYCLE_START_KEY] = str(session.get(start_key) or base)

    st.markdown("**Chart spelling preferences**")
    prefs = spelling_prefs_from_session(session)
    pref_cols = st.columns(5)
    for i, (sharp, flat) in enumerate(ENHARMONIC_SPELLING_PAIRS):
        pair = f"{sharp}/{flat}"
        with pref_cols[i % 5]:
            choice = st.radio(
                pair,
                options=[sharp, flat],
                index=0 if prefs.get(pair, flat) == sharp else 1,
                key=f"backing_key_spell__{owner}__{pair}",
                horizontal=True,
                label_visibility="visible",
            )
            prefs[pair] = str(choice)
    session[BACKING_KEY_SPELLING_PREFS_KEY] = prefs

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if st.button("Start cycle", key=f"backing_key_cycle_start_btn__{owner}", use_container_width=True):
            start_key_cycle(
                session,
                start_key=str(session.get(start_key) or base),
                spelling_prefs=prefs,
            )
            st.rerun()
    with b2:
        held = bool(data and str(data.get("status")) == STATUS_HELD)
        label = "Resume" if held else "Pause / Hold"
        if st.button(label, key=f"backing_key_cycle_pause_btn__{owner}", use_container_width=True):
            if held:
                resume_key_cycle(session)
            else:
                pause_key_cycle(session)
            st.rerun()
    with b3:
        if st.button("Advance", key=f"backing_key_cycle_advance_btn__{owner}", use_container_width=True):
            if data and data.get("enabled"):
                advance_key_cycle_now(session)
            st.rerun()
    with b4:
        if st.button(
            "Complete pass",
            key=f"backing_key_cycle_complete_pass_btn__{owner}",
            use_container_width=True,
            help="Marks the current scope+loop pass finished (same advance path as audio end).",
        ):
            note_backing_pass_finished(
                session,
                pass_signature=f"ui_complete_pass::{owner}::{int(data.get('passes_completed') or 0) if data else 0}",
            )
            st.rerun()
    with b5:
        if st.button("Stop / Reset", key=f"backing_key_cycle_stop_btn__{owner}", use_container_width=True):
            stop_key_cycle(session)
            st.rerun()


__all__ = [
    "BACKING_KEY_CYCLE_DIRECTION_KEY",
    "BACKING_KEY_CYCLE_SESSIONS_KEY",
    "BACKING_KEY_CYCLE_START_KEY",
    "BACKING_KEY_CYCLE_STEP_KEY",
    "BACKING_KEY_SPELLING_PREFS_KEY",
    "CYCLE_OWNERS",
    "ENHARMONIC_SPELLING_PAIRS",
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
    "assert_practice_key_unchanged",
    "current_backing_owner_practice_key",
    "cycle_concert_practice_key",
    "cycle_pass_ended_js_snippet",
    "cycle_status_lines",
    "cycle_step_semitones",
    "default_spelling_prefs",
    "effective_backing_playback_key",
    "get_owner_cycle_session",
    "is_cycle_active",
    "maybe_consume_cycle_pass_from_query",
    "note_backing_pass_finished",
    "pause_key_cycle",
    "render_backing_key_cycle_controls",
    "render_backing_key_cycle_status_banner",
    "resolve_cycle_owner",
    "resume_key_cycle",
    "spelling_prefs_from_session",
    "start_key_cycle",
    "stop_key_cycle",
    "temporary_playback_key",
]
