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


def cycle_prefetch_neighbor_keys(session: dict[str, Any]) -> list[str]:
    """Keys to prepare ahead of the sounding pass.

    Include +1 (idle now), +2 (idle after next seamless handoff), and +3
    (following refill after that handoff's Python ack) so component→Python
    latency cannot starve consecutive short passes.
    """
    cur = str(temporary_playback_key(session) or "").strip()
    keys: list[str] = []
    for steps in (1, 2, 3, -1):
        k = str(peek_cycle_key_at_delta(session, steps=steps) or "").strip()
        if k and k != cur and k not in keys:
            keys.append(k)
    return keys


def clear_key_cycle_prepared_audio(
    session: dict[str, Any],
    *,
    stop_player: bool = False,
) -> None:
    session.pop(BACKING_KEY_CYCLE_PREPARED_KEY, None)
    session.pop(BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY, None)
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session.pop("_kc_seamless_handoff", None)
    session.pop("_kc_skip_audio_remount", None)
    session.pop("_kc_current_static_url", None)
    # Bump cancel generation so in-flight prefetch / player cmds abandon work.
    session["_kc_prefetch_gen"] = int(session.get("_kc_prefetch_gen") or 0) + 1
    session["_kc_prefetch_cancel"] = True
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    # Only stop the parent dual-buffer on true Off / leave — never on start/On.
    if stop_player:
        session["_kc_force_player_off"] = True
        session["_kc_player_needs_teardown"] = True
        try:
            from backing_key_cycle_handoff import ACKED_IDS_KEY, LAST_PASS_ID_KEY

            session.pop(ACKED_IDS_KEY, None)
            session.pop(LAST_PASS_ID_KEY, None)
        except Exception:
            pass


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


def _kc_static_dir() -> Any:
    from pathlib import Path

    root = Path(__file__).resolve().parent
    path = root / "static" / "kc"
    path.mkdir(parents=True, exist_ok=True)
    # Keep enough neighbors for dual-buffer (+1/+2/+3) across several passes.
    # Aggressive pruning previously deleted the currently-playing WAV (404).
    try:
        files = sorted(path.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[48:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except Exception:
        pass
    return path


def _kc_static_url_on_disk(url: str) -> bool:
    from pathlib import Path

    u = str(url or "").strip()
    if not u.startswith("/app/static/kc/"):
        return False
    name = u.rsplit("/", 1)[-1]
    if not name.endswith(".wav"):
        return False
    return (_kc_static_dir() / name).is_file()


def publish_cycle_wav_static_url(wav_path: str, *, signature: Any = None) -> str:
    """Copy a spilled WAV into ``static/kc`` and return an ``/app/static/…`` URL."""
    import hashlib
    import shutil
    from pathlib import Path

    src = Path(str(wav_path or "").strip())
    if not src.is_file():
        return ""
    digest = hashlib.sha1(
        repr(signature if signature is not None else src.name).encode("utf-8", errors="replace")
    ).hexdigest()[:20]
    dest = _kc_static_dir() / f"{digest}.wav"
    try:
        if not dest.is_file() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
    except OSError:
        return ""
    return f"/app/static/kc/{digest}.wav"


def store_prepared_cycle_audio(
    session: dict[str, Any],
    *,
    sounding_key: str,
    signature: Any,
    wav_path: str = "",
    static_url: str = "",
    chart_html: str = "",
    chords: list[str] | tuple[str, ...] | None = None,
    sections: dict[str, list[str]] | None = None,
) -> None:
    """Remember prepared neighbor keys (+1/+2/+3 and previous) by path/sig only."""
    key = str(sounding_key or "").strip()
    if not key:
        return
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not isinstance(bag, dict):
        bag = {}
    path = str(wav_path or "").strip()
    url = str(static_url or "").strip()
    if path and not url:
        url = publish_cycle_wav_static_url(path, signature=signature)
    html = str(chart_html or "").strip()
    if not html:
        try:
            from backing_key_cycle_handoff import build_cycle_chart_strip_html

            html = build_cycle_chart_strip_html(
                sounding_key=key,
                chords=list(chords or ()),
                sections=sections if isinstance(sections, dict) else None,
            )
        except Exception:
            html = ""
    bag[key] = {
        "signature": signature,
        "path": path,
        "static_url": url,
        "chart_html": html,
    }
    # Bound memory: keep sounding + ahead/behind neighbors used by dual-buffer.
    keep = {
        temporary_playback_key(session),
        key,
        *cycle_prefetch_neighbor_keys(session),
    }
    keep = {str(k or "").strip() for k in keep if str(k or "").strip()}
    for stale in list(bag.keys()):
        if stale not in keep:
            bag.pop(stale, None)
    session[BACKING_KEY_CYCLE_PREPARED_KEY] = bag


def prepared_cycle_chart_html(session: dict[str, Any], sounding_key: str) -> str:
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return ""
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("chart_html") or "").strip()


def prepared_cycle_static_url(session: dict[str, Any], sounding_key: str) -> str:
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return ""
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return ""
    url = str(entry.get("static_url") or "").strip()
    if url and _kc_static_url_on_disk(url):
        return url
    path = str(entry.get("path") or "").strip()
    if path:
        url = publish_cycle_wav_static_url(path, signature=entry.get("signature"))
        if url:
            entry = dict(entry)
            entry["static_url"] = url
            bag[key] = entry
            session[BACKING_KEY_CYCLE_PREPARED_KEY] = bag
        return url
    return ""


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
    url = str(entry.get("static_url") or "").strip()
    if not url:
        url = publish_cycle_wav_static_url(path, signature=sig)
    if url:
        session["_kc_current_static_url"] = url
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
            fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "gap_s": gap,
                        "kind": "ready",
                        "sounding": temporary_playback_key(session),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    return gap


def mark_cycle_next_pass_playing_clock(
    session: dict[str, Any],
    *,
    gap_ms: float | None = None,
) -> float | None:
    """Record end→playing gap (browser-measured preferred)."""
    import time

    raw = session.get(BACKING_KEY_CYCLE_PASS_GAP_KEY)
    if not isinstance(raw, dict):
        raw = {}
    if gap_ms is not None:
        gap = max(0.0, float(gap_ms) / 1000.0)
        ended = raw.get("ended_at") or (time.time() - gap)
    else:
        ended = raw.get("ended_at")
        if not ended:
            return None
        gap = max(0.0, float(time.time()) - float(ended))
    session[BACKING_KEY_CYCLE_PASS_GAP_KEY] = {
        "ended_at": ended,
        "playing_at": time.time(),
        "gap_playing_s": gap,
        "gap_s": gap,
    }
    try:
        import json
        import os
        from pathlib import Path

        data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data.mkdir(parents=True, exist_ok=True)
        with (data / "_key_cycle_pass_gaps.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "gap_s": gap,
                        "kind": "playing",
                        "sounding": temporary_playback_key(session),
                    }
                )
                + "\n"
            )
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
        "cycle_id": "",
        "pass_id": 0,
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
    try:
        from backing_key_cycle_handoff import new_cycle_id

        data["cycle_id"] = new_cycle_id()
    except Exception:
        import time as _time

        data["cycle_id"] = str(int(_time.time()))[-12:]
    data["pass_id"] = 0
    session["_kc_cycle_id"] = data["cycle_id"]
    try:
        from backing_key_cycle_handoff import ACKED_IDS_KEY, LAST_PASS_ID_KEY

        session.pop(ACKED_IDS_KEY, None)
        session[LAST_PASS_ID_KEY] = 0
    except Exception:
        pass
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
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    return data


def resume_key_cycle(session: dict[str, Any]) -> dict[str, Any] | None:
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return data
    data = dict(data)
    data["status"] = STATUS_RUNNING
    _put_owner_cycle_session(session, owner, data)
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
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
    clear_key_cycle_prepared_audio(session, stop_player=True)
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
    clear_key_cycle_prepared_audio(session, stop_player=True)
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
    queue_continue: bool = True,
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
        data["pass_id"] = int(data.get("pass_id") or 0) + 1
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
    if queue_continue:
        session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
    else:
        session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    # Ask the app to prefetch neighbors after this step settles (+1 and +2).
    _pf_neighbors = cycle_prefetch_neighbor_keys(session)
    session[BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY] = (
        peek_cycle_key_at_delta(session, steps=1 if steps >= 0 else -1)
        or (_pf_neighbors[0] if _pf_neighbors else "")
    )
    session["_kc_prefetch_neighbors"] = list(_pf_neighbors)
    session["_kc_prefetch_armed"] = False
    return data


def _advance_owner_cycle(
    session: dict[str, Any],
    *,
    force: bool = False,
    queue_continue: bool = True,
) -> dict[str, Any] | None:
    return _step_owner_cycle(
        session, steps=1, force=force, queue_continue=queue_continue
    )


def _keys_equivalent(a: str, b: str) -> bool:
    """True when two key tokens name the same pitch-class + mode."""
    left = str(a or "").strip()
    right = str(b or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    try:
        lt, lm = split_key_center(left)
        rt, rm = split_key_center(right)
        if (lm or "major") != (rm or "major"):
            return False
        return _pc_of_tonic(lt) == _pc_of_tonic(rt)
    except Exception:
        return False


def _log_cycle_key_write(
    session: dict[str, Any],
    *,
    trigger: str,
    old_key: str,
    new_key: str,
    cycle_id: str = "",
    pass_id: Any = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one Python-side sounding/cycle-position write for forensics."""
    try:
        import json
        import os
        import time
        from pathlib import Path

        data_dir = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "t": time.time(),
            "realm": "python",
            "trigger": str(trigger or ""),
            "old": str(old_key or ""),
            "new": str(new_key or ""),
            "cycleId": str(cycle_id or session.get("_kc_cycle_id") or ""),
            "passId": pass_id,
            "owner": resolve_cycle_owner(session),
        }
        if isinstance(extra, dict):
            row.update(extra)
        with (data_dir / "_kc_key_writes.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def _confirm_owner_cycle_to_playing_key(
    session: dict[str, Any],
    playing: str,
    *,
    from_key: str = "",
    pass_id: Any = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Align temporary key to the browser's confirmed playing key.

    Playing acks must not blindly ``+1`` again: the browser already flipped.
    Returns ``(changed, data)``.
    """
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return False, data
    if str(data.get("status") or "") != STATUS_RUNNING:
        return False, data
    want = str(playing or "").strip()
    if not want:
        return False, data
    before = str(data.get("current_playback_key") or "").strip()
    cycle_id = str(data.get("cycle_id") or session.get("_kc_cycle_id") or "")
    if _keys_equivalent(before, want):
        promote_prepared_cycle_audio(session, want)
        session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
        session["_kc_seamless_handoff"] = True
        session["_kc_skip_audio_remount"] = True
        _pf = cycle_prefetch_neighbor_keys(session)
        session[BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY] = (
            peek_cycle_key_at_delta(session, steps=1) or (_pf[0] if _pf else "")
        )
        session["_kc_prefetch_neighbors"] = list(_pf)
        session["_kc_prefetch_armed"] = False
        session["_kc_last_playing_confirm"] = {
            "key": want,
            "passId": pass_id,
            "cycleId": cycle_id,
            "t": __import__("time").time(),
        }
        _log_cycle_key_write(
            session,
            trigger="playing_ack_confirm_noop",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"fromKey": from_key},
        )
        return False, data

    expected = str(next_cycle_playback_key(session) or "").strip()
    if _keys_equivalent(expected, want) or (
        from_key and _keys_equivalent(from_key, before)
    ):
        after = _advance_owner_cycle(session, force=False, queue_continue=False)
        after_key = str((after or {}).get("current_playback_key") or "")
        changed = bool(after_key and not _keys_equivalent(after_key, before))
        _log_cycle_key_write(
            session,
            trigger="playing_ack_advance_to_expected",
            old_key=before,
            new_key=after_key or want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"fromKey": from_key, "expected": expected},
        )
        if changed:
            session["_kc_last_playing_confirm"] = {
                "key": after_key or want,
                "passId": pass_id,
                "cycleId": cycle_id,
                "t": __import__("time").time(),
            }
        return changed, after

    # Absolute align (spelling / skipped catch-up) — never step past ``want``.
    prefs = (
        data.get("spelling_prefs")
        if isinstance(data.get("spelling_prefs"), dict)
        else spelling_prefs_from_session(session)
    )
    start = str(data.get("start_cycle_key") or data.get("base_practice_key") or "C").strip() or "C"
    interval = int(data.get("interval") or 1)
    if interval not in {1, 2}:
        interval = 1
    direction = str(data.get("direction") or "up")
    unit = -interval if direction == "down" else interval
    new_offset = None
    for i in range(0, cycle_sequence_length(interval=interval) + 1):
        off = i * unit
        cand = cycle_concert_practice_key(start, semitones=off, spelling_prefs=prefs)
        if _keys_equivalent(cand, want):
            new_offset = off
            break
    if new_offset is None:
        _log_cycle_key_write(
            session,
            trigger="playing_ack_align_reject_unknown",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"fromKey": from_key},
        )
        return False, data
    cur_off = int(data.get("offset_semitones") or 0)
    # Reject stale confirms that would move backward while running forward.
    if unit > 0 and new_offset < cur_off:
        _log_cycle_key_write(
            session,
            trigger="playing_ack_align_reject_stale_behind",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"cur_off": cur_off, "new_offset": new_offset},
        )
        return False, data
    if unit < 0 and new_offset > cur_off:
        _log_cycle_key_write(
            session,
            trigger="playing_ack_align_reject_stale_behind",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"cur_off": cur_off, "new_offset": new_offset},
        )
        return False, data
    data = dict(data)
    stepped = new_offset != cur_off
    data["offset_semitones"] = int(new_offset)
    data["current_playback_key"] = cycle_concert_practice_key(
        start, semitones=int(new_offset), spelling_prefs=prefs
    )
    if stepped:
        data["pass_index"] = int(data.get("pass_index") or 0) + 1
        data["passes_completed"] = int(data.get("passes_completed") or 0) + 1
        data["pass_id"] = int(data.get("pass_id") or 0) + 1
    data["pending_pass_advance"] = False
    _put_owner_cycle_session(session, owner, data)
    try:
        from songs.key_state import invalidate_backing_cache

        invalidate_backing_cache(session)
    except Exception:
        session.pop("_last_backing_wav", None)
        session.pop("_last_backing_signature", None)
        session.pop("_last_backing_wav_path", None)
    promote_prepared_cycle_audio(session, str(data["current_playback_key"]))
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session["_kc_seamless_handoff"] = True
    session["_kc_skip_audio_remount"] = True
    _pf = cycle_prefetch_neighbor_keys(session)
    session[BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY] = (
        peek_cycle_key_at_delta(session, steps=1) or (_pf[0] if _pf else "")
    )
    session["_kc_prefetch_neighbors"] = list(_pf)
    session["_kc_prefetch_armed"] = False
    after_key = str(data.get("current_playback_key") or "")
    _log_cycle_key_write(
        session,
        trigger="playing_ack_align_absolute",
        old_key=before,
        new_key=after_key,
        cycle_id=cycle_id,
        pass_id=pass_id,
        extra={"fromKey": from_key, "cur_off": cur_off, "new_offset": new_offset},
    )
    if stepped:
        session["_kc_last_playing_confirm"] = {
            "key": after_key,
            "passId": pass_id,
            "cycleId": cycle_id,
            "t": __import__("time").time(),
        }
    return stepped, data


def note_backing_pass_finished(
    session: dict[str, Any],
    *,
    pass_signature: str = "",
    seamless: bool = False,
    gap_ms: float | None = None,
    handoff_ack: dict[str, Any] | None = None,
) -> bool:
    """Advance after a real scope+loop completion. Reruns must not call this casually.

    Returns True when the temporary key advanced.
    When ``seamless`` is True, the browser already started the next pass — do not
    queue CONTINUE_PLAY remount/autoplay.

    Prefer an explicit ``handoff_ack`` with ``kind=playing`` (cycleId / passId /
    playingKey / ackId). A playing ack *confirms* the browser key — it must not
    step again past that key. Prepared audio alone must not advance or autoplay.
    """
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return False
    if str(data.get("status") or "") != STATUS_RUNNING:
        return False

    ack = handoff_ack if isinstance(handoff_ack, dict) else None
    if ack is not None:
        try:
            from backing_key_cycle_handoff import (
                log_handoff_event,
                mark_ack_consumed,
                validate_playing_ack,
            )

            ok, reason = validate_playing_ack(
                session, ack, expect_cycle_id=str(data.get("cycle_id") or "")
            )
            log_handoff_event(
                session,
                {
                    "event": "validate",
                    "ok": ok,
                    "reason": reason,
                    "ack": {
                        k: ack.get(k)
                        for k in (
                            "kind",
                            "ackId",
                            "cycleId",
                            "passId",
                            "playingKey",
                            "fromKey",
                            "gapMs",
                            "chartMs",
                            "epoch",
                            "natural",
                        )
                    },
                },
            )
            if not ok:
                return False
            mark_ack_consumed(session, str(ack.get("ackId") or ""))
            try:
                from backing_key_cycle_handoff import mark_pass_id_seen

                mark_pass_id_seen(session, int(ack.get("passId") or 0))
            except Exception:
                pass
            seamless = True
            # Late ack must never force a regenerate/remount — browser is already playing.
            session["_kc_skip_audio_remount"] = True
            session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
            if gap_ms is None and ack.get("gapMs") is not None:
                try:
                    gap_ms = float(ack.get("gapMs"))
                except Exception:
                    gap_ms = None
            playing = str(ack.get("playingKey") or "").strip()
            pass_id = ack.get("passId")
            from_key = str(ack.get("fromKey") or "").strip()
            if playing:
                pass_signature = (
                    f"playing::{data.get('cycle_id') or ''}::{pass_id}::{playing}"
                )
            try:
                from backing_key_cycle_handoff import log_timing_event

                log_timing_event(
                    {
                        "event": "ack_received_python",
                        "ackId": ack.get("ackId"),
                        "cycleId": ack.get("cycleId"),
                        "passId": ack.get("passId"),
                        "playingKey": playing,
                        "timing": ack.get("timing") or {},
                        "gapMs": gap_ms,
                        "chartMs": ack.get("chartMs"),
                    }
                )
            except Exception:
                pass
            # One completed browser pass → one confirm (no blind +1 past playingKey).
            sig = str(pass_signature or "").strip()
            if sig and sig == str(data.get("last_pass_signature") or ""):
                return False
            data = dict(data)
            if sig:
                data["last_pass_signature"] = sig
            _put_owner_cycle_session(session, owner, data)
            before = str(data.get("current_playback_key") or "")
            changed, after_data = _confirm_owner_cycle_to_playing_key(
                session,
                playing,
                from_key=from_key,
                pass_id=pass_id,
            )
            after = str((after_data or {}).get("current_playback_key") or before)
            if gap_ms is not None:
                mark_cycle_pass_ended_clock(session)
                mark_cycle_next_pass_playing_clock(session, gap_ms=gap_ms)
            elif changed:
                mark_cycle_pass_ended_clock(session)
                mark_cycle_next_pass_playing_clock(session, gap_ms=80)
            session["_kc_seamless_handoff"] = True
            session["_kc_skip_audio_remount"] = True
            session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
            data2 = get_owner_cycle_session(session, owner) or {}
            data2 = dict(data2)
            data2["advanced_for_wav_sig"] = str(
                session.get("_last_backing_signature") or after or playing
            )
            _put_owner_cycle_session(session, owner, data2)
            final = str(
                (get_owner_cycle_session(session, owner) or {}).get("current_playback_key")
                or after
                or before
            )
            # Only force a Streamlit rerun when the temporary key actually moved.
            # Confirm-noop (already aligned) must not burn the next pass waiting on rerun.
            return bool(changed and _keys_equivalent(final, playing))
        except Exception:
            return False
    elif seamless:
        # Legacy seamless token path — still require prepared next, but do not
        # treat "prepared only" as playing without an ack.
        pass
    else:
        # Reject legacy ended/bridge clicks once this cycle has a playing-ack
        # confirm. Identity is cycleId (+ confirmed passId), not a wall-clock
        # timeout — short passes must still advance, delayed duplicates must not.
        try:
            last_c = session.get("_kc_last_playing_confirm")
            if isinstance(last_c, dict):
                conf_cycle = str(last_c.get("cycleId") or "").strip()
                cur_cycle = str(
                    data.get("cycle_id") or session.get("_kc_cycle_id") or ""
                ).strip()
                if conf_cycle and cur_cycle and conf_cycle == cur_cycle:
                    try:
                        from backing_key_cycle_handoff import LAST_PASS_ID_KEY

                        confirmed_pass = int(
                            session.get(LAST_PASS_ID_KEY)
                            or last_c.get("passId")
                            or 0
                        )
                    except Exception:
                        confirmed_pass = int(last_c.get("passId") or 0)
                    if confirmed_pass > 0:
                        _log_cycle_key_write(
                            session,
                            trigger="legacy_advance_reject_playing_ack_owns_cycle",
                            old_key=str(data.get("current_playback_key") or ""),
                            new_key="",
                            cycle_id=cur_cycle,
                            pass_id=confirmed_pass,
                            extra={
                                "confirmed_key": last_c.get("key"),
                                "sig": pass_signature,
                                "transition": (
                                    f"{conf_cycle}::{confirmed_pass}::"
                                    f"{last_c.get('key') or ''}"
                                ),
                            },
                        )
                        return False
        except Exception:
            pass

    sig = str(pass_signature or "").strip()
    # Duplicate ended/bridge clicks while next-pass regen is queued. Distinct
    # non-audio pass signatures (unit / manual sequencing) may clear the flag.
    if session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY) and not seamless:
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
    if (
        wav_sig
        and wav_sig == str(data.get("advanced_for_wav_sig") or "")
        and not seamless
    ):
        return False
    data = dict(data)
    if sig:
        data["last_pass_signature"] = sig
    if wav_sig and not seamless:
        data["advanced_for_wav_sig"] = wav_sig
    _put_owner_cycle_session(session, owner, data)
    before = str(data.get("current_playback_key") or "")
    after_data = _advance_owner_cycle(
        session, force=False, queue_continue=not seamless
    )
    after = str((after_data or {}).get("current_playback_key") or "")
    advanced = bool(after and after != before)
    if advanced:
        _log_cycle_key_write(
            session,
            trigger="legacy_pass_advance",
            old_key=before,
            new_key=after,
            cycle_id=str(data.get("cycle_id") or ""),
            pass_id=(after_data or {}).get("pass_id"),
            extra={"sig": sig, "seamless": seamless},
        )
        mark_cycle_pass_ended_clock(session)
        if gap_ms is not None:
            mark_cycle_next_pass_playing_clock(session, gap_ms=gap_ms)
        if seamless:
            # Prefer browser dual-buffer handoff (no CONTINUE_PLAY remount).
            promoted = bool(str(session.get("_last_backing_wav_path") or "").strip())
            if promoted:
                session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
                session["_kc_seamless_handoff"] = True
                session["_kc_skip_audio_remount"] = True
                if gap_ms is None:
                    mark_cycle_next_pass_playing_clock(session, gap_ms=80)
            else:
                session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
                session.pop("_kc_seamless_handoff", None)
                session.pop("_kc_skip_audio_remount", None)
            data2 = get_owner_cycle_session(session, owner) or {}
            data2 = dict(data2)
            data2["advanced_for_wav_sig"] = str(
                session.get("_last_backing_signature") or wav_sig or after
            )
            _put_owner_cycle_session(session, owner, data2)
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


def cycle_persistent_player_bridge_html(*, cmd_json: str) -> str:
    """Height-1 iframe: install parent dual-buffer player + push the latest command.

    The audible ``<audio>`` elements live on ``window.parent`` so Streamlit
    script reruns do not remount/stop them. On natural ``ended``, if the next
    buffer is ready, JS swaps chart+audio immediately, waits for ``play()`` to
    resolve, then writes a ``kc_handoff`` cookie (cycleId/passId/playingKey) and
    clicks the Python bridge. Prepared audio alone never advances Python.
    """
    import base64

    # Base64 avoids quote/script escaping issues inside components.html.
    b64 = base64.b64encode(str(cmd_json or "{}").encode("utf-8")).decode("ascii")
    label = BACKING_KEY_CYCLE_PASS_FINISHED_LABEL.replace("\\", "\\\\").replace("'", "\\'")
    return f"""<!DOCTYPE html><html><body><script>
(function () {{
  const CMD = JSON.parse(atob('{b64}'));
  const WANT = '{label}';
  const parentWin = window.parent;
  const parentDoc = parentWin.document;

  function ensurePlayer() {{
    let root = parentDoc.getElementById('kc-persistent-root');
    const rebuildBuffers = (host) => {{
      if (!host) return;
      if (!parentDoc.getElementById('kc-buf-0') || !parentDoc.getElementById('kc-buf-1')) {{
        host.innerHTML = `
        <div id="kc-chart-live" data-testid="kc-chart-live"></div>
        <div id="kc-persistent-meta" style="font:12px/1.35 system-ui,sans-serif;opacity:.85;margin:0 0 .25rem"></div>
        <audio id="kc-buf-0" controls preload="auto" style="width:100%;display:block"></audio>
        <audio id="kc-buf-1" preload="auto" style="display:none"></audio>
        <div id="kc-persistent-detail" style="font:11px/1.3 system-ui,sans-serif;opacity:.65;margin-top:2px"></div>`;
      }}
    }};
    if (!root) {{
      root = parentDoc.createElement('div');
      root.id = 'kc-persistent-root';
      root.setAttribute('data-testid', 'kc-persistent-root');
      root.style.cssText = 'margin:.35rem 0 .5rem;padding:0;position:relative;z-index:20;';
      rebuildBuffers(root);
      // Attach to body so Streamlit widget rerenders cannot drop the dual-buffer.
      try {{
        parentDoc.body.appendChild(root);
      }} catch (e) {{
        const btnAnchor = parentDoc.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]')
          || parentDoc.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
        const btnRow = btnAnchor && (
          btnAnchor.closest('[data-testid="stHorizontalBlock"]')
          || btnAnchor.parentElement
        );
        if (btnRow && btnRow.parentElement) {{
          btnRow.parentElement.insertBefore(root, btnRow.nextSibling);
        }} else {{
          parentDoc.body.appendChild(root);
        }}
      }}
    }} else {{
      rebuildBuffers(root);
      try {{
        if (root.parentElement !== parentDoc.body) {{
          parentDoc.body.appendChild(root);
        }}
      }} catch (e) {{}}
    }}
    if (!parentDoc.getElementById('kc-chart-live')) {{
      const meta = parentDoc.getElementById('kc-persistent-meta');
      const chart = parentDoc.createElement('div');
      chart.id = 'kc-chart-live';
      chart.setAttribute('data-testid', 'kc-chart-live');
      if (meta && meta.parentElement) meta.parentElement.insertBefore(chart, meta);
      else root.insertBefore(chart, root.firstChild);
    }}
    // Do not reparent under Streamlit widget rows — those nodes are destroyed on
    // script rerun after handoff ack and would wipe the dual-buffer mid-pass.
    if (!parentWin.__kcDual) {{
      parentWin.__kcDual = {{
        active: 0,
        playingUrl: '',
        nextUrl: '',
        nextSounding: '',
        followingUrl: '',
        followingSounding: '',
        aheadUrl: '',
        aheadSounding: '',
        currentChartHtml: '',
        nextChartHtml: '',
        followingChartHtml: '',
        aheadChartHtml: '',
        nextBufferReadyAt: null,
        nextBufferReadyState: 0,
        nextBufferReadyUrl: '',
        passToken: '',
        cycleId: '',
        passId: 0,
        epoch: -1,
        playGen: 0,
        endedAt: 0,
        chartMs: null,
        swapping: false,
        ending: false,
        enabled: false,
      }};
    }}
    const state = parentWin.__kcDual;
    if (state.followingUrl == null) state.followingUrl = '';
    if (state.followingSounding == null) state.followingSounding = '';
    if (state.followingChartHtml == null) state.followingChartHtml = '';
    if (state.aheadUrl == null) state.aheadUrl = '';
    if (state.aheadSounding == null) state.aheadSounding = '';
    if (state.aheadChartHtml == null) state.aheadChartHtml = '';
    if (state.nextBufferReadyAt == null) state.nextBufferReadyAt = null;
    if (state.nextBufferReadyState == null) state.nextBufferReadyState = 0;
    if (state.nextBufferReadyUrl == null) state.nextBufferReadyUrl = '';

    function activeAudio() {{
      const doc = parentWin.document;
      return doc.getElementById(state.active === 0 ? 'kc-buf-0' : 'kc-buf-1');
    }}
    function idleAudio() {{
      const doc = parentWin.document;
      return doc.getElementById(state.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
    }}
    function urlsMatch(el, want) {{
      if (!el || !want) return false;
      const attr = el.getAttribute('data-kc-url') || '';
      if (attr === want) return true;
      const src = el.currentSrc || el.src || '';
      if (!src) return false;
      try {{
        const abs = new URL(want, parentWin.location.origin).href;
        return src === abs || src.indexOf(want) !== -1;
      }} catch (e) {{
        return src.indexOf(want) !== -1;
      }}
    }}
    function cancelPendingPlays() {{
      state.playGen = Number(state.playGen || 0) + 1;
    }}
    // Prefer parent-realm scheduler (installed by boot script). Iframe timers die
    // when Streamlit destroys the components.html frame.
    function kcSched(fn, ms) {{
      try {{
        if (typeof parentWin.__kcSched === 'function') return parentWin.__kcSched(fn, ms);
      }} catch (e) {{}}
      try {{ return parentWin.setTimeout(fn, ms); }} catch (e2) {{ return -1; }}
    }}
    // Parent-realm clock only — iframe performance.now() resets on Streamlit
    // remounts and must never mix into end→playing gaps.
    function kcNow() {{
      try {{ return parentWin.performance.now(); }} catch (e) {{ return performance.now(); }}
    }}
    function markBufferReady(el, role) {{
      if (!el) return;
      const url = el.getAttribute('data-kc-url') || '';
      const apply = () => {{
        const readyAt = kcNow();
        const rs = Number(el.readyState || 0);
        if (role === 'next') {{
          state.nextBufferReadyAt = readyAt;
          state.nextBufferReadyState = rs;
          state.nextBufferReadyUrl = url;
        }}
        try {{
          parentWin.__kcBufferReadyLog = parentWin.__kcBufferReadyLog || [];
          parentWin.__kcBufferReadyLog.push({{
            t: readyAt,
            role: role,
            url: String(url).slice(-48),
            readyState: rs,
            sounding: el.getAttribute('data-kc-sounding') || '',
          }});
        }} catch (e) {{}}
      }};
      if (Number(el.readyState || 0) >= 3) {{
        apply();
        return;
      }}
      const onThru = () => {{ apply(); }};
      try {{
        el.addEventListener('canplaythrough', onThru, {{ once: true }});
        el.addEventListener('canplay', () => {{
          if (Number(el.readyState || 0) >= 3) apply();
        }}, {{ once: true }});
      }} catch (e) {{}}
    }}
    function armIdleFromUrl(el, url, sounding, role) {{
      if (!el || !url) return;
      el.setAttribute('data-kc-url', url);
      if (sounding) el.setAttribute('data-kc-sounding', sounding);
      el.preload = 'auto';
      // load()/src change on a previously-ended buffer can re-fire `ended`.
      // Preload must never count as a pass completion.
      try {{ el.__kcIgnoreEndedUntil = kcNow() + 4000; }} catch (e0) {{}}
      if (el.getAttribute('src') !== url && el.src !== url) {{
        el.src = url;
        try {{ el.load(); }} catch (e) {{}}
      }}
      markBufferReady(el, role || 'next');
      // Preload never changes the current sounding key / highlight.
    }}
    function teardownKeyCycleWatchers() {{
      try {{
        if (typeof parentWin.__kcTeardownKeyCycleWatchers === 'function') {{
          parentWin.__kcTeardownKeyCycleWatchers();
          return;
        }}
      }} catch (e) {{}}
      try {{
        if (parentWin.__kcEndedWatch) {{
          parentWin.clearInterval(parentWin.__kcEndedWatch);
          parentWin.__kcEndedWatch = null;
        }}
        parentWin.__kcEndedWatchInstalled = false;
        parentWin.__kcOnEnded = null;
        ['kc-buf-0', 'kc-buf-1'].forEach((id) => {{
          const a = parentWin.document.getElementById(id);
          if (!a) return;
          if (a.__kcEndedHandler) {{
            try {{ a.removeEventListener('ended', a.__kcEndedHandler); }} catch (e2) {{}}
            a.__kcEndedHandler = null;
          }}
          a.__kcEndedListener = false;
          a.__kcEndedHook = false;
        }});
      }} catch (e) {{}}
    }}
    function ensureKeyCycleWatchers() {{
      // Durable parent-realm interval + scheduler. Survives bridge iframe death.
      // Always (re)attach buffer ended listeners — buffers may not exist on first boot.
      try {{
        if (typeof parentWin.__kcAttachEndedListeners === 'function') {{
          parentWin.__kcAttachEndedListeners();
        }}
      }} catch (e) {{}}
      // If an old watcher lacks parent finish / swap-play, tear it down and reinstall.
      try {{
        const needReinstall = (
          parentWin.__kcEndedWatch
          && (
            typeof parentWin.__kcFinishPendingHandoff !== 'function'
            || parentWin.__kcWatchVersion !== 18
          )
        );
        if (needReinstall) {{
          if (typeof parentWin.__kcTeardownKeyCycleWatchers === 'function') {{
            parentWin.__kcTeardownKeyCycleWatchers();
          }} else if (parentWin.__kcEndedWatch) {{
            parentWin.clearInterval(parentWin.__kcEndedWatch);
            parentWin.__kcEndedWatch = null;
            parentWin.__kcEndedWatchInstalled = false;
          }}
        }}
      }} catch (e) {{}}
      if (parentWin.__kcEndedWatchInstalled && parentWin.__kcEndedWatch
          && typeof parentWin.__kcFinishPendingHandoff === 'function'
          && parentWin.__kcWatchVersion === 18) return;
      try {{
        const boot = parentDoc.createElement('script');
        boot.textContent = `
(function(){{
  if (!window.__kcSched) {{
    window.__kcSched = function(fn, ms) {{ return window.setTimeout(fn, ms); }};
  }}
  // Ensure kc-buf play() rejects are retried from the parent realm.
  try {{
    var proto = window.HTMLMediaElement && window.HTMLMediaElement.prototype;
    if (proto && !proto.__kcPlayRetryPatched) {{
      var rawPlay = proto.play;
      proto.play = function() {{
        var el = this;
        var p = rawPlay.apply(el, arguments);
        if (p && p.then && el && String(el.id || '').indexOf('kc-buf') === 0) {{
          p.catch(function(err) {{
            try {{
              window.__kcPlayDiag = window.__kcPlayDiag || [];
              window.__kcPlayDiag.push({{
                t: performance.now(),
                ev: 'play_reject',
                id: el.id,
                name: err && err.name,
                message: err && err.message,
              }});
            }} catch (e) {{}}
            window.__kcSched(function() {{
              try {{
                el.muted = false;
                el.autoplay = true;
                var p2 = rawPlay.apply(el, []);
                if (p2 && p2.catch) p2.catch(function(){{}});
              }} catch (e2) {{}}
            }}, 120);
          }});
        }}
        return p;
      }};
      proto.__kcPlayRetryPatched = true;
    }}
  }} catch (e) {{}}
  window.__kcAttachEndedListeners = function() {{
    ['kc-buf-0','kc-buf-1'].forEach(function(id) {{
      var a = window.document.getElementById(id);
      if (!a || a.__kcParentEndedListener) return;
      a.__kcEndedHandler = function(ev) {{
        try {{
          var st = window.__kcDual;
          if (!st || !st.enabled) return;
          // Ignore ended on the idle/previous buffer after a flip.
          var activeId = st.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
          var target = (ev && ev.target) || a;
          if (target && target.id && target.id !== activeId) return;
          if (target && Number(target.__kcIgnoreEndedUntil || 0) > performance.now()) return;
          if (typeof window.__kcOnEnded === 'function') window.__kcOnEnded();
        }} catch (e) {{}}
      }};
      a.addEventListener('ended', a.__kcEndedHandler);
      a.__kcParentEndedListener = true;
      a.__kcEndedListener = true;
      a.__kcEndedHook = true;
    }});
  }};
  window.__kcTeardownKeyCycleWatchers = function() {{
    try {{
      if (window.__kcEndedWatch) {{
        window.clearInterval(window.__kcEndedWatch);
        window.__kcEndedWatch = null;
      }}
      window.__kcEndedWatchInstalled = false;
      window.__kcOnEnded = null;
      window.__kcFinishPendingHandoff = null;
      if (window.__kcDual) {{
        window.__kcDual.pendingHandoff = null;
        window.__kcDual.swapping = false;
        window.__kcDual.ending = false;
      }}
      ['kc-buf-0','kc-buf-1'].forEach(function(id) {{
        var a = window.document.getElementById(id);
        if (!a) return;
        if (a.__kcEndedHandler) {{
          try {{ a.removeEventListener('ended', a.__kcEndedHandler); }} catch (e) {{}}
          a.__kcEndedHandler = null;
        }}
        a.__kcEndedListener = false;
        a.__kcEndedHook = false;
        a.__kcParentEndedListener = false;
      }});
    }} catch (e) {{}}
  }};
  window.__kcAttachEndedListeners();
  window.__kcFinishPendingHandoff = function(reason) {{
    try {{
      var st = window.__kcDual;
      if (!st || !st.pendingHandoff) return false;
      var ph = st.pendingHandoff;
      if (st.handoffSettledToken && st.handoffSettledToken === ph.token) {{
        st.swapping = false;
        st.pendingHandoff = null;
        return true;
      }}
      if (window.__kcLastGapMs != null && window.__kcLastHandoffAck
          && window.__kcLastHandoffAck.ackId
          && st.handoffSettledToken === ph.token) {{
        st.swapping = false;
        st.pendingHandoff = null;
        return true;
      }}
      var doc = window.document;
      var act = doc.getElementById(st.active === 0 ? 'kc-buf-0' : 'kc-buf-1');
      var idle = doc.getElementById(st.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
      if (!act) return false;
      var ct = Number(act.currentTime || 0);
      // paused can lag while currentTime advances after play() on recycled buffers.
      var playing = !act.ended && ct >= 0.02 && (!act.paused || ct >= 0.05);
      if (!playing) return false;
      var endedAt = Number(ph.endedAt || st.endedAt || 0);
      var playingAt = performance.now();
      var swapAt = Number(st.swapStartedAt || 0);
      // Prefer swapStartedAt when endedAt is missing/stale (iframe clock skew).
      if (!endedAt || (swapAt > 0 && (playingAt - endedAt) > 8000 && (playingAt - swapAt) <= 8000)) {{
        endedAt = swapAt > 0 ? swapAt : (playingAt - 80);
      }}
      var gapMs = Math.max(0, playingAt - endedAt);
      // Re-base only when still absurd after swap alignment.
      if (gapMs > 8000) {{
        if (swapAt > 0 && (playingAt - swapAt) <= 8000) {{
          endedAt = swapAt;
          gapMs = Math.max(0, playingAt - endedAt);
        }} else {{
          gapMs = Math.min(gapMs, 250);
          endedAt = playingAt - gapMs;
        }}
        try {{
          window.__kcPlayDiag = window.__kcPlayDiag || [];
          window.__kcPlayDiag.push({{
            t: playingAt,
            ev: 'parent_finish_rebased_gap',
            gapMs: gapMs,
            id: act.id,
          }});
        }} catch (eG) {{}}
      }}
      st.handoffSettledToken = ph.token;
      st._kcPlayInFlight = false;
      var playingKey = String(ph.playingKey || act.getAttribute('data-kc-sounding') || window.__kcLastSounding || '');
      var chartHtml = String(ph.chartHtml || '');
      if (!chartHtml && playingKey) {{
        chartHtml = '<div class="kc-chart-full" data-kc-playing-key="' + playingKey
          + '"><div><span style="opacity:.7">Playing chart</span> <strong>'
          + playingKey + '</strong></div></div>';
      }}
      window.__kcLastGapMs = gapMs;
      window.__kcLastSounding = playingKey;
      st.swapping = false;
      st.passId = Number(st.passId || 0) + 1;
      st.playingUrl = ph.nextUrl || st.playingUrl || '';
      try {{
        var el = doc.getElementById('kc-chart-live');
        if (el && chartHtml) {{
          el.innerHTML = chartHtml;
          el.setAttribute('data-kc-playing-key', playingKey);
        }}
      }} catch (e) {{}}
      try {{
        if (typeof window.__kcSyncHighlight === 'function') window.__kcSyncHighlight(playingKey);
      }} catch (eH) {{}}
      var chartAt = performance.now();
      window.__kcLastChartMs = Math.max(0, chartAt - playingAt);
      st.chartMs = window.__kcLastChartMs;
      try {{
        if (ph.followUrl && idle) {{
          idle.setAttribute('data-kc-url', ph.followUrl);
          if (ph.followKey) idle.setAttribute('data-kc-sounding', ph.followKey);
          idle.preload = 'auto';
          if (idle.getAttribute('src') !== ph.followUrl && idle.src !== ph.followUrl) {{
            idle.src = ph.followUrl;
            try {{ idle.load(); }} catch (e2) {{}}
          }}
        }}
      }} catch (e3) {{}}
      var timing = ph.timing || {{}};
      timing.playingAt = playingAt;
      timing.chartAt = chartAt;
      timing.ackSentAt = kcNow();
      timing.endedAt = endedAt;
      var ackId = 'ack_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
      var ack = {{
        kind: 'playing',
        ackId: ackId,
        cycleId: st.cycleId || '',
        passId: st.passId,
        playingKey: playingKey,
        fromKey: ph.fromKey || '',
        gapMs: Math.round(gapMs),
        chartMs: Math.round(Number(st.chartMs) || 0),
        epoch: st.epoch,
        natural: true,
        timing: timing,
        finishReason: reason || 'parent_watch',
      }};
      window.__kcPendingPlayingAck = ack;
      try {{
        window.__kcPendingPlayingAckQueue = window.__kcPendingPlayingAckQueue || [];
        window.__kcPendingPlayingAckQueue.push(ack);
        if (window.__kcPendingPlayingAckQueue.length > 12) {{
          window.__kcPendingPlayingAckQueue.shift();
        }}
      }} catch (eQ) {{}}
      window.__kcLastHandoffAck = ack;
      try {{
        window.__kcAckLog = window.__kcAckLog || [];
        window.__kcAckLog.push({{
          t: performance.now(),
          fromKey: String(ph.fromKey || ''),
          playingKey: playingKey,
          gapMs: Math.round(gapMs),
          ack: ack,
        }});
        if (window.__kcAckLog.length > 24) window.__kcAckLog.shift();
      }} catch (eLog) {{}}
      try {{
        var payload = encodeURIComponent(JSON.stringify(ack));
        document.cookie = 'kc_handoff=' + payload + '; path=/; SameSite=Lax';
      }} catch (eC) {{}}
      try {{
        var root = document.querySelector('[class*="st-key-kc_handoff_ack_json"]');
        var input = root && root.querySelector('input');
        if (input) {{
          var json = JSON.stringify(ack);
          var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          var tracker = input._valueTracker;
          if (tracker) tracker.setValue('');
          setter.call(input, json);
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
      }} catch (eI) {{}}
      window.__kcPlayDiag = window.__kcPlayDiag || [];
      window.__kcPlayDiag.push({{ t: performance.now(), ev: 'parent_finish', reason: reason || '', gapMs: gapMs, id: act.id }});
      st.pendingHandoff = null;
      return true;
    }} catch (e) {{
      try {{ window.__kcWatchErr = 'finish:' + String(e && e.message || e); }} catch (e2) {{}}
      return false;
    }}
  }};
  if (window.__kcEndedWatch) return;
  window.__kcWatchVersion = 18;
  window.__kcEndedWatchInstalled = true;
  window.__kcEndedWatch = window.setInterval(function(){{
    try {{
      window.__kcWatchTicks = Number(window.__kcWatchTicks || 0) + 1;
      var st = window.__kcDual;
      if (!st || !st.enabled) return;
      var doc = window.document;
      var act = doc.getElementById(st.active === 0 ? 'kc-buf-0' : 'kc-buf-1');
      var idle = doc.getElementById(st.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
      // During swap: keep trying play + finish ack in parent realm (iframe timers die).
      if (st.swapping || st.pendingHandoff) {{
        var age = performance.now() - Number(st.swapStartedAt || 0);
        // Do not stack muted play() while iframe kick is in-flight — competing
        // play() promises are the ~1–3s recycled-buffer stall (Ab→A).
        // Only treat play as busy for a short window — a hung play() promise
        // must not block parent recovery for the full 1–3s stall.
        var playBusy = !!st._kcPlayInFlight && age < 280;
        if (act && !act.ended && act.paused && age > 120 && age < 20000
            && !window.__kcLastGapMs && !playBusy) {{
          try {{
            act.muted = true;
            act.loop = false;
            act.autoplay = true;
            st._kcPlayInFlight = true;
            var p = act.play();
            if (p && p.then) {{
              p.then(function() {{
                st._kcPlayInFlight = false;
                try {{ act.muted = false; }} catch (eU) {{}}
                window.__kcFinishPendingHandoff('play_resolved_muted');
              }}).catch(function(err) {{
                st._kcPlayInFlight = false;
                window.__kcPlayDiag = window.__kcPlayDiag || [];
                window.__kcPlayDiag.push({{
                  t: performance.now(),
                  ev: 'watch_play_reject',
                  name: err && err.name,
                  message: err && err.message,
                }});
                try {{
                  act.muted = false;
                  var p2 = act.play();
                  if (p2 && p2.then) {{
                    p2.then(function() {{ window.__kcFinishPendingHandoff('play_resolved'); }})
                      .catch(function(){{}});
                  }}
                }} catch (e3) {{}}
              }});
            }} else {{
              st._kcPlayInFlight = false;
            }}
          }} catch (e) {{ st._kcPlayInFlight = false; }}
        }}
        if (window.__kcFinishPendingHandoff('watch_playing')) return;
        if (age < 8000) return;
        st.swapping = false; st.ending = false; st._onEndedGate = false;
      }}
      if (st.ending) {{
        var stuckEnd = performance.now() - Number(st.endedAt || 0);
        if (stuckEnd < 2000) return;
        st.ending = false; st._onEndedGate = false;
      }}
      var hasNext = !!(st.nextUrl || (st.nextSounding && idle && (idle.getAttribute('data-kc-url') || idle.src)));
      if (act && act.ended && !act.loop && hasNext && typeof window.__kcOnEnded === 'function') {{
        // Recover when a prior gate/ignore left the active buffer stuck at ended.
        if (st._onEndedGate) {{
          var gateAge2 = performance.now() - Number(st.swapStartedAt || st.endedAt || 0);
          if (gateAge2 > 2000) st._onEndedGate = false;
        }}
        try {{ if (act.__kcIgnoreEndedUntil) act.__kcIgnoreEndedUntil = 0; }} catch (eIgn3) {{}}
        window.__kcSched(function(){{
          try {{ window.__kcOnEnded(); }} catch (e) {{}}
        }}, 0);
      }} else if (
        act && !act.ended && !act.loop && hasNext
        && Number(act.duration || 0) > 1
        && Number(act.currentTime || 0) >= Number(act.duration || 0) - 0.08
        && typeof window.__kcOnEnded === 'function'
        && !st.swapping && !st.pendingHandoff
      ) {{
        // Some browsers leave currentTime at duration without firing ended.
        // Ignore a stuck _onEndedGate after 2.5s — iframe may have died before clearing it.
        if (st._onEndedGate) {{
          var gateAge = performance.now() - Number(st.swapStartedAt || 0);
          if (gateAge < 5000) return;
          st._onEndedGate = false;
        }}
        if (!act._kcEndStuckAt) act._kcEndStuckAt = performance.now();
        if (performance.now() - Number(act._kcEndStuckAt || 0) > 500) {{
          act._kcEndStuckAt = 0;
          window.__kcSched(function(){{
            try {{ window.__kcOnEnded(); }} catch (e) {{}}
          }}, 0);
        }}
      }} else {{
        if (act) act._kcEndStuckAt = 0;
        // Warm-start next buffer muted in the last ~0.8s so swap only unmutes
        // (avoids recycled-buffer play() stalls of 1–3s).
        if (
          act && idle && !act.ended && !act.paused
          && Number(act.duration || 0) > 2
          && !st.swapping && !st.pendingHandoff
          && st.nextUrl
        ) {{
          var left = Number(act.duration || 0) - Number(act.currentTime || 0);
      // Start warm late so promote lands near bar 1 (not 1.5s into the pass).
          if (left > 0.08 && left < 0.40 && Number(idle.readyState || 0) >= 3) {{
            try {{
              var warmUrl = String(idle.getAttribute('data-kc-url') || idle.src || '');
              var want = String(st.nextUrl || '');
              if (warmUrl && want && (warmUrl.indexOf(want.slice(-24)) !== -1 || want.indexOf(warmUrl.slice(-24)) !== -1 || warmUrl === want)) {{
                if (idle.paused || Number(idle.currentTime || 0) > 0.35) {{
                  idle.muted = true;
                  idle.loop = false;
                  try {{ if (Number(idle.currentTime || 0) > 0.02) idle.currentTime = 0; }} catch (eW0) {{}}
                  var pw = idle.play();
                  st._kcWarmStarted = true;
                  if (pw && pw.catch) pw.catch(function(){{ st._kcWarmStarted = false; }});
                  window.__kcPlayDiag = window.__kcPlayDiag || [];
                  window.__kcPlayDiag.push({{
                    t: performance.now(),
                    ev: 'warm_start_idle',
                    left: left,
                    id: idle.id,
                  }});
                }}
              }}
            }} catch (eW) {{}}
          }}
        }}
        if (
          act && !act.ended && act.paused && Number(act.currentTime || 0) < 0.05
          && st.swapStartedAt && (performance.now() - Number(st.swapStartedAt)) > 400
          && (performance.now() - Number(st.swapStartedAt)) < 12000
          && !window.__kcLastGapMs
        ) {{
          try {{
            act.muted = false;
            act.loop = false;
            var p2 = act.play();
            if (p2 && p2.then) {{
              p2.then(function() {{ window.__kcFinishPendingHandoff('stall_nudge'); }});
              if (p2.catch) p2.catch(function(){{}});
            }}
          }} catch (e) {{}}
        }}
      }}
    }} catch (e) {{
      try {{ window.__kcWatchErr = String(e && e.message || e); }} catch (e2) {{}}
    }}
  }}, 200);
}})();`;
        parentDoc.documentElement.appendChild(boot);
        boot.remove();
        try {{
          if (typeof parentWin.__kcAttachEndedListeners === 'function') {{
            parentWin.__kcAttachEndedListeners();
          }}
        }} catch (e2) {{}}
      }} catch (e) {{
        parentWin.__kcEndedWatchInstalled = true;
        parentWin.__kcEndedWatch = parentWin.setInterval(() => {{
          try {{
            parentWin.__kcWatchTicks = Number(parentWin.__kcWatchTicks || 0) + 1;
            const st = parentWin.__kcDual;
            if (!st || !st.enabled) return;
            const doc = parentWin.document;
            const act = doc.getElementById(st.active === 0 ? 'kc-buf-0' : 'kc-buf-1');
            const idle = doc.getElementById(st.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
            const hasNext = !!(
              st.nextUrl
              || (st.nextSounding && idle && (idle.getAttribute('data-kc-url') || idle.src))
            );
            if (act && act.ended && !act.loop && hasNext && typeof parentWin.__kcOnEnded === 'function') {{
              kcSched(() => {{ try {{ parentWin.__kcOnEnded(); }} catch (e2) {{}} }}, 0);
            }}
          }} catch (err) {{}}
        }}, 200);
      }}
    }}
    function setHandoffCookie(ack) {{
      try {{
        const payload = encodeURIComponent(JSON.stringify(ack));
        parentDoc.cookie = 'kc_handoff=' + payload + '; path=/; SameSite=Lax';
        parentWin.__kcLastHandoffAck = ack;
      }} catch (e) {{}}
      // Streamlit text_input channel (more reliable than cookies).
      try {{
        const root = parentDoc.querySelector('[class*="st-key-kc_handoff_ack_json"]');
        const input = root && root.querySelector('input');
        if (input) {{
          const json = JSON.stringify(ack);
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          const tracker = input._valueTracker;
          if (tracker) tracker.setValue('');
          setter.call(input, json);
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
      }} catch (e) {{}}
    }}
    function clearHandoffCookie() {{
      try {{
        parentDoc.cookie = 'kc_handoff=; path=/; Max-Age=0; SameSite=Lax';
      }} catch (e) {{}}
    }}
    function clickBridge(token) {{
      try {{
        if (parentWin.__backingKeyCyclePassConsumed === token) return;
        parentWin.__backingKeyCyclePassConsumed = token;
        try {{
          const url = new URL(parentWin.location.href);
          url.searchParams.set('kc_bridge', token);
          parentWin.history.replaceState({{}}, '', url.toString());
        }} catch (e) {{}}
        window.setTimeout(() => {{
          try {{
            if (!state.enabled) return;
            const buttons = parentDoc.querySelectorAll('button');
            for (const b of buttons) {{
              if ((b.textContent || '').trim() !== WANT) continue;
              const form = b.closest('form');
              if (form && typeof form.requestSubmit === 'function') {{
                form.requestSubmit(b);
              }} else {{
                b.click();
              }}
              break;
            }}
          }} catch (e) {{}}
        }}, 20);
      }} catch (e) {{}}
    }}
    function applyChartHtml(html, sounding) {{
      try {{
        const el = parentDoc.getElementById('kc-chart-live');
        if (el && html) {{
          el.innerHTML = html;
          el.setAttribute('data-kc-playing-key', String(sounding || ''));
        }} else if (el && sounding) {{
          el.innerHTML = '<div class="kc-chart-strip"><strong>' + String(sounding) + '</strong></div>';
          el.setAttribute('data-kc-playing-key', String(sounding));
        }}
      }} catch (e) {{}}
    }}
    function syncHighlight(sounding) {{
      try {{
        const s = String(sounding || '').trim();
        if (!s) return;
        const old = String(parentWin.__kcLastSounding || '');
        if (old !== s) {{
          try {{
            parentWin.__kcWriteTrace = parentWin.__kcWriteTrace || [];
            const act = activeAudio();
            parentWin.__kcWriteTrace.push({{
              t: performance.now(),
              trigger: 'syncHighlight',
              old: old,
              new: s,
              cycleId: String(state.cycleId || ''),
              passId: Number(state.passId || 0),
              audioId: act ? act.id : '',
              active: state.active,
              stack: (new Error()).stack.split('\\n').slice(0, 4).join(' | '),
            }});
            if (parentWin.__kcWriteTrace.length > 80) parentWin.__kcWriteTrace =
              parentWin.__kcWriteTrace.slice(-80);
          }} catch (eT) {{}}
        }}
        parentWin.__kcLastSounding = s;
        const chips = parentDoc.querySelectorAll('.ui-key-cycle-chip, .ui-key-cycle-playbar span[data-key]');
        chips.forEach((el) => {{
          const key = (el.getAttribute('data-key') || el.textContent || '').trim();
          const on = key === s;
          el.classList.toggle('ui-key-cycle-chip-on', on);
          if (on) el.setAttribute('data-current', '1');
          else el.removeAttribute('data-current');
        }});
        const meta = parentDoc.getElementById('kc-persistent-meta');
        if (meta) meta.innerHTML = 'Sounding <strong>' + s + '</strong>';
        const bar = parentDoc.querySelector('.ui-key-cycle-playbar');
        if (bar) {{
          const strong = bar.querySelector('strong');
          if (strong) strong.textContent = s;
        }}
      }} catch (e) {{}}
    }}
    parentWin.__kcSyncHighlight = syncHighlight;
    function doSeamlessSwap(idle, nextUrl) {{
      state.swapping = true;
      state.swapStartedAt = kcNow();
      // Do not pause the ended buffer — pause() can disrupt subsequent autoplay.
      const fromKey = String(parentWin.__kcLastSounding || '');
      let sounding = String(state.nextSounding || '');
      let chartHtml = String(state.nextChartHtml || '');
      try {{
        const idleEl = idle || idleAudio();
        if (!sounding && idleEl) {{
          sounding = String(idleEl.getAttribute('data-kc-sounding') || '').trim();
        }}
        if (!sounding && nextUrl && parentWin.__kcUrlToKey) {{
          sounding = String(parentWin.__kcUrlToKey[nextUrl] || '').trim();
        }}
        if (!sounding && nextUrl && parentWin.__kcUrlToKey) {{
          // Absolute vs path mismatch
          for (const [u, k] of Object.entries(parentWin.__kcUrlToKey)) {{
            if (nextUrl.indexOf(u) !== -1 || String(u).indexOf(nextUrl) !== -1) {{
              sounding = String(k || '').trim();
              if (sounding) break;
            }}
          }}
        }}
        if (!chartHtml && sounding) {{
          // Minimal chart if Python bag lagged behind the preloaded buffer.
          chartHtml = '<div class="kc-chart-full" data-kc-playing-key="' + sounding
            + '"><div><span style="opacity:.7">Playing chart</span> <strong>'
            + sounding + '</strong></div></div>';
        }}
      }} catch (e) {{}}
      if (!sounding && chartHtml) {{
        try {{
          const m = chartHtml.match(/data-kc-playing-key=\"([^\"]+)\"/);
          if (m) sounding = m[1];
        }} catch (e) {{}}
      }}
      if (!sounding) {{
        // Audio can still start; resolve key from URL map shortly if Python is late.
        try {{
          parentWin.__kcHandoffErrors = parentWin.__kcHandoffErrors || [];
          parentWin.__kcHandoffErrors.push({{ t: kcNow(), err: 'missing_next_sounding_at_swap', nextUrl: nextUrl }});
        }} catch (e) {{}}
      }}
      const timing = {{
        endedAt: (state.endedAt != null ? state.endedAt : kcNow()),
        nextReadyAt: null,
        bufferReadyAt: null,
        bufferReadyStateAtEnded: null,
        nextWasReadyBeforeEnd: false,
        playRequestedAt: null,
        playingAt: null,
        chartAt: null,
        ackSentAt: null,
      }};
      try {{
        const idleEl = idle || idleAudio();
        const rs = idleEl ? Number(idleEl.readyState || 0) : -1;
        timing.bufferReadyStateAtEnded = rs;
        timing.bufferReadyAt = state.nextBufferReadyAt || null;
        // readyState >= 3 (HAVE_FUTURE_DATA) means decode/readiness is genuine.
        timing.nextWasReadyBeforeEnd = rs >= 3;
        if (rs >= 2 || rs >= 1) {{
          timing.nextReadyAt = state.nextBufferReadyAt || kcNow();
        }}
      }} catch (e) {{}}
      // Capture the key we are swapping TO before any promote mutates nextSounding.
      const playingKeyAtFlip = sounding
        || String(state.nextSounding || '')
        || (idle ? String(idle.getAttribute('data-kc-sounding') || '') : '')
        || '';
      state.active = state.active === 0 ? 1 : 0;
      const now = activeAudio();
      const other = idleAudio();
      now.style.display = 'block';
      if (other) other.style.display = 'none';
      // If parent warm-started this buffer muted, unmute and confirm — skip the
      // cold play() path that stalls 1–3s on recycled elements.
      let warmLive = false;
      try {{
        if (now && state._kcWarmStarted) {{
          now.muted = false;
          now.volume = 1;
          now.loop = false;
          if (now.paused || now.ended || Number(now.currentTime || 0) > 0.28) {{
            try {{
              if (Number(now.currentTime || 0) > 0.05) now.currentTime = 0;
            }} catch (eWs) {{}}
            try {{ now.play(); }} catch (eWp) {{}}
          }}
          warmLive = true;
          state._kcWarmStarted = false;
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: kcNow(),
              ev: 'warm_promote_unmute',
              id: now.id,
              ct: Number(now.currentTime || 0),
              paused: !!now.paused,
            }});
          }} catch (eWm) {{}}
        }} else {{
          state._kcWarmStarted = false;
        }}
      }} catch (eW2) {{ warmLive = false; state._kcWarmStarted = false; }}
      // Seek-to-zero BEFORE play, and wait for seeked — playing while a seek is
      // outstanding is the main cause of ~1.5–3s play() stalls on recycled buffers.
      let seekPending = false;
      try {{
        if (!warmLive && now && Number(now.currentTime || 0) > 0.05) {{
          seekPending = true;
          now.currentTime = 0;
        }}
      }} catch (e) {{ seekPending = false; }}
      // Promote +2/+3 identity immediately at flip so a late/aborted ack cannot
      // leave nextUrl stuck on the key we just started playing. Defer idle.load()
      // until after play succeeds — competing decode stalls the handoff (~3s+).
      const followUrl = String(state.followingUrl || '');
      const followKey = String(state.followingSounding || '');
      const followChart = String(state.followingChartHtml || '');
      const aheadUrl = String(state.aheadUrl || '');
      const aheadKey = String(state.aheadSounding || '');
      const aheadChart = String(state.aheadChartHtml || '');
      try {{
        state.nextUrl = followUrl;
        state.nextSounding = followKey;
        state.nextChartHtml = followChart;
        state.followingUrl = aheadUrl;
        state.followingSounding = aheadKey;
        state.followingChartHtml = aheadChart;
        state.aheadUrl = '';
        state.aheadSounding = '';
        state.aheadChartHtml = '';
        // Clear readiness until deferred arm completes (do not load yet).
        state.nextBufferReadyAt = null;
        state.nextBufferReadyState = 0;
        state.nextBufferReadyUrl = '';
        try {{
          parentWin.__kcUrlToKey = parentWin.__kcUrlToKey || {{}};
          if (followUrl && followKey) parentWin.__kcUrlToKey[followUrl] = followKey;
          if (aheadUrl && aheadKey) parentWin.__kcUrlToKey[aheadUrl] = aheadKey;
        }} catch (e2) {{}}
      }} catch (e) {{}}
      const armFollowingAfterPlay = () => {{
        try {{
          if (followUrl && other) {{
            armIdleFromUrl(other, followUrl, followKey, 'next');
          }} else if (other) {{
            try {{
              other.pause();
              other.removeAttribute('data-kc-url');
              other.removeAttribute('data-kc-sounding');
              other.removeAttribute('src');
              other.load();
            }} catch (e2) {{}}
            state.nextBufferReadyAt = null;
            state.nextBufferReadyState = 0;
            state.nextBufferReadyUrl = '';
          }}
        }} catch (e) {{}}
      }};
      // Own the live URL immediately so stale Python cmds cannot clobber sounding.
      if (nextUrl) state.playingUrl = nextUrl;
      try {{
        if (now && nextUrl) {{
          now.setAttribute('data-kc-url', nextUrl);
          if (playingKeyAtFlip) now.setAttribute('data-kc-sounding', playingKeyAtFlip);
        }}
      }} catch (e) {{}}
      // Publish sounding identity at flip (chart still waits for playing).
      if (playingKeyAtFlip) {{
        try {{
          parentWin.__kcWriteTrace = parentWin.__kcWriteTrace || [];
          parentWin.__kcWriteTrace.push({{
            t: kcNow(),
            trigger: 'doSeamlessSwap_flip',
            old: fromKey,
            new: playingKeyAtFlip,
            cycleId: String(state.cycleId || ''),
            passId: Number(state.passId || 0),
            audioId: now ? now.id : '',
            nextUrl: String(nextUrl || '').slice(-40),
          }});
          parentWin.__kcLastSounding = playingKeyAtFlip;
          syncHighlight(playingKeyAtFlip);
        }} catch (e) {{}}
      }}
      // Suppress stale ended echoes on the buffer we just left (not the new active).
      // Also abort the outgoing buffer's decoder — Chromium stalls the new play()
      // for ~1.5–3s when the just-ended element still holds a decoded WAV.
      try {{
        if (other) {{
          other.__kcIgnoreEndedUntil = kcNow() + 4000;
          try {{ other.pause(); }} catch (eP) {{}}
          try {{
            other.removeAttribute('src');
            other.removeAttribute('data-kc-url');
            other.load();
          }} catch (eL) {{}}
        }}
      }} catch (eIgn2) {{}}
      // Keep previous chart/highlight until audio is actually playing.
      // Do NOT bump playGen here — a concurrent applyCmd cancel would drop the ack.
      const handoffToken = String(Date.now()) + '_' + Math.random().toString(36).slice(2, 7);
      state.handoffToken = handoffToken;
      // Register pending handoff ASAP so parent watch can finish if iframe dies.
      state.pendingHandoff = {{
        token: handoffToken,
        fromKey: fromKey,
        playingKey: playingKeyAtFlip || sounding,
        chartHtml: chartHtml,
        nextUrl: nextUrl,
        endedAt: timing.endedAt,
        timing: timing,
        followUrl: followUrl,
        followKey: followKey,
        followChart: followChart,
      }};
      let settled = false;
      let soundingWait = 0;
      const resolveSounding = () => {{
        let s = playingKeyAtFlip || sounding;
        if (s) return s;
        try {{
          if (now) s = String(now.getAttribute('data-kc-sounding') || '').trim();
          if (!s && nextUrl && parentWin.__kcUrlToKey) {{
            s = String(parentWin.__kcUrlToKey[nextUrl] || '').trim();
            if (!s) {{
              for (const [u, k] of Object.entries(parentWin.__kcUrlToKey)) {{
                if (nextUrl.indexOf(u) !== -1 || String(u).indexOf(nextUrl) !== -1) {{
                  s = String(k || '').trim();
                  if (s) break;
                }}
              }}
            }}
          }}
        }} catch (e) {{}}
        return s;
      }};
      const publishAck = (gapMs) => {{
        if (settled) return;
        if (!state.enabled) return;
        if (state.handoffToken !== handoffToken) return;
        if (state.handoffSettledToken === handoffToken) return;
        const playingKey = resolveSounding();
        if (!playingKey) {{
          soundingWait += 1;
          if (soundingWait < 60) {{
            kcSched(() => {{
              if (!settled && state.handoffToken === handoffToken) publishAck(gapMs);
            }}, 80);
            return;
          }}
          state.swapping = false;
          state.pendingHandoff = null;
          return;
        }}
        settled = true;
        state.handoffSettledToken = handoffToken;
        state.pendingHandoff = null;
        state._kcPlayInFlight = false;
        // Do NOT clear _onEndedGate here — a queued second ended callback would
        // immediately advance again. Gate is released on a timer after swap.
        sounding = playingKey;
        if (!chartHtml) {{
          chartHtml = '<div class="kc-chart-full" data-kc-playing-key="' + playingKey
            + '"><div><span style="opacity:.7">Playing chart</span> <strong>'
            + playingKey + '</strong></div></div>';
        }}
        parentWin.__kcLastGapMs = gapMs;
        state.playingUrl = nextUrl;
        // next/following already promoted at buffer flip; arm idle decode now.
        armFollowingAfterPlay();
        state.swapping = false;
        state.passId = Number(state.passId || 0) + 1;
        // Chart + highlight only after confirmed playing (not at buffer swap).
        applyChartHtml(chartHtml, playingKey);
        syncHighlight(playingKey);
        timing.chartAt = kcNow();
        state.chartMs = Math.max(0, timing.chartAt - (timing.playingAt || timing.endedAt));
        parentWin.__kcLastChartMs = state.chartMs;
        if (chartHtml) state.currentChartHtml = chartHtml;
        // Also update any on-page lead sheet if present.
        try {{
          const sheet = parentDoc.querySelector('.backing-chart-sheet, .lead-sheet, [data-testid="kc-streamlit-chart"]');
          if (sheet && chartHtml) {{
            const host = parentDoc.getElementById('kc-full-chart-host') || sheet;
            if (host.id !== 'kc-full-chart-host') {{
              let wrap = parentDoc.getElementById('kc-full-chart-host');
              if (!wrap) {{
                wrap = parentDoc.createElement('div');
                wrap.id = 'kc-full-chart-host';
                wrap.setAttribute('data-testid', 'kc-full-chart-host');
                sheet.parentElement && sheet.parentElement.insertBefore(wrap, sheet);
              }}
              wrap.innerHTML = chartHtml;
              sheet.style.display = 'none';
            }} else {{
              host.innerHTML = chartHtml;
            }}
          }}
        }} catch (e) {{}}
        const ackId = 'ack_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
        timing.ackSentAt = kcNow();
        const ack = {{
          kind: 'playing',
          ackId: ackId,
          cycleId: String(state.cycleId || ''),
          passId: Number(state.passId || 0),
          playingKey: playingKey,
          fromKey: fromKey,
          gapMs: Math.round(gapMs),
          chartMs: Math.round(Number(state.chartMs) || 0),
          epoch: Number(state.epoch || 0),
          natural: true,
          timing: {{
            endedToReadyMs: timing.nextReadyAt != null ? Math.round(timing.nextReadyAt - timing.endedAt) : null,
            endedToPlayRequestMs: timing.playRequestedAt != null ? Math.round(timing.playRequestedAt - timing.endedAt) : null,
            endedToPlayingMs: timing.playingAt != null ? Math.round(timing.playingAt - timing.endedAt) : Math.round(gapMs),
            playingToChartMs: timing.chartAt != null && timing.playingAt != null ? Math.round(timing.chartAt - timing.playingAt) : null,
            endedToAckMs: Math.round(timing.ackSentAt - timing.endedAt),
            bufferReadyAt: timing.bufferReadyAt,
            bufferReadyStateAtEnded: timing.bufferReadyStateAtEnded,
            nextWasReadyBeforeEnd: !!timing.nextWasReadyBeforeEnd,
            readyToEndedMs: timing.bufferReadyAt != null ? Math.round(timing.endedAt - timing.bufferReadyAt) : null,
            nextReadyAt: timing.nextReadyAt,
            playRequestedAt: timing.playRequestedAt,
            playingAt: timing.playingAt,
            chartAt: timing.chartAt,
            ackSentAt: timing.ackSentAt,
            endedAt: timing.endedAt,
          }},
        }};
        try {{
          parentWin.__kcPendingPlayingAck = ack;
          parentWin.__kcPendingPlayingAckQueue = parentWin.__kcPendingPlayingAckQueue || [];
          parentWin.__kcPendingPlayingAckQueue.push(ack);
          if (parentWin.__kcPendingPlayingAckQueue.length > 12) {{
            parentWin.__kcPendingPlayingAckQueue.shift();
          }}
          parentWin.__kcLastHandoffAck = ack;
          parentWin.__kcTimingLast = timing;
          parentWin.__kcAckLog = parentWin.__kcAckLog || [];
          parentWin.__kcAckLog.push({{
            t: kcNow(),
            fromKey: fromKey,
            playingKey: playingKey,
            gapMs: Math.round(gapMs),
            ack: ack,
          }});
          if (parentWin.__kcAckLog.length > 24) parentWin.__kcAckLog.shift();
        }} catch (e) {{}}
        try {{
          parentWin.sessionStorage.setItem('kc_last_gap_ms', String(Math.round(gapMs)));
          parentWin.sessionStorage.setItem('kc_last_chart_ms', String(Math.round(Number(state.chartMs) || 0)));
          parentWin.sessionStorage.setItem('kc_last_bridge', 'playing::' + ackId);
        }} catch (e) {{}}
        // Component polls __kcPendingPlayingAck — no form/button race.
      }};
      const afterPlayFail = () => {{
        if (state.handoffToken !== handoffToken) return;
        // Retry play — seek-to-zero / autoplay can fail several times.
        if (!state._handoffRetries) state._handoffRetries = 0;
        if (state._handoffRetries < 20) {{
          state._handoffRetries += 1;
          kcSched(() => {{
            if (state.handoffToken !== handoffToken || settled) return;
            try {{
              if (now && Number(now.readyState || 0) < 2) {{
                try {{ now.load(); }} catch (e3) {{}}
                now.addEventListener('canplay', () => {{
                  try {{
                    const p2 = now.play();
                    if (p2 && p2.then) {{
                      p2.then(() => {{
                        if (timing.playingAt == null) timing.playingAt = kcNow();
                        publishAck(Math.max(0, timing.playingAt - timing.endedAt));
                      }}).catch(() => afterPlayFail());
                    }} else {{
                      afterPlayFail();
                    }}
                  }} catch (e4) {{ afterPlayFail(); }}
                }}, {{ once: true }});
                return;
              }}
              now.muted = false;
              now.loop = false;
              const p = now.play();
              if (p && p.then) {{
                p.then(() => {{
                  if (timing.playingAt == null) timing.playingAt = kcNow();
                  publishAck(Math.max(0, timing.playingAt - timing.endedAt));
                }}).catch(() => afterPlayFail());
              }} else if (now && !now.paused) {{
                onPlaying();
              }} else {{
                afterPlayFail();
              }}
            }} catch (e) {{ afterPlayFail(); }}
          }}, 100);
          return;
        }}
        // Last resort: if audio is already moving, still publish the playing ack.
        try {{
          if (now && (!now.paused || Number(now.currentTime) > 0.05) && !now.ended) {{
            if (timing.playingAt == null) timing.playingAt = kcNow();
            publishAck(Math.max(0, timing.playingAt - timing.endedAt));
            return;
          }}
        }} catch (e) {{}}
        // Keep swapping true briefly so liveHandoff still blocks remounts; schedule
        // one final parent-realm play attempt before releasing.
        kcSched(() => {{
          if (settled || state.handoffToken !== handoffToken) return;
          try {{
            if (now) {{
              now.muted = false;
              const p = now.play();
              if (p && p.then) {{
                p.then(() => {{
                  if (timing.playingAt == null) timing.playingAt = kcNow();
                  publishAck(Math.max(0, timing.playingAt - timing.endedAt));
                }}).catch(() => {{
                  try {{ armFollowingAfterPlay(); }} catch (e3) {{}}
                  state.swapping = false;
                }});
                return;
              }}
            }}
          }} catch (e) {{}}
          try {{ armFollowingAfterPlay(); }} catch (e3) {{}}
          state.swapping = false;
          state._handoffRetries = 0;
        }}, 250);
      }};
      state._handoffRetries = 0;
      timing.playRequestedAt = kcNow();
      try {{
        parentWin.__kcLastHandoffAck = null;
        parentWin.__kcLastGapMs = null;
        parentWin.__kcLastChartMs = null;
      }} catch (e) {{}}
      // Refresh pending timing/playRequestedAt (token already registered at flip).
      try {{
        if (state.pendingHandoff && state.pendingHandoff.token === handoffToken) {{
          state.pendingHandoff.timing = timing;
          state.pendingHandoff.chartHtml = chartHtml;
          state.pendingHandoff.playingKey = playingKeyAtFlip || sounding;
        }}
      }} catch (e) {{}}
      const kickPlay = () => {{
        if (state.handoffToken !== handoffToken || settled) return;
        // Avoid stacked play() on recycled buffers — a second call while the
        // first promise is pending stalls resolve by 1–3s even though audio moves.
        if (state._kcPlayInFlight) {{
          try {{
            if (now && !now.paused && Number(now.currentTime || 0) >= 0.02) {{
              onPlaying();
            }}
          }} catch (eBusy) {{}}
          return;
        }}
        let playP = null;
        try {{
          parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
          parentWin.__kcPlayDiag.push({{
            t: kcNow(),
            ev: 'kick_play',
            id: now && now.id,
            rs: now ? Number(now.readyState || 0) : -1,
            ct: now ? Number(now.currentTime || 0) : -1,
            paused: now ? !!now.paused : null,
          }});
        }} catch (e0) {{}}
        try {{
          now.muted = false;
          now.volume = 1;
          now.loop = false;
          now.autoplay = true;
          state._kcPlayInFlight = true;
          playP = now.play();
        }} catch (e) {{ playP = null; state._kcPlayInFlight = false; }}
        if (playP && playP.then) {{
          playP.then(() => {{
            state._kcPlayInFlight = false;
            const resolvedAt = kcNow();
            const ctNow = now ? Number(now.currentTime || 0) : 0;
            try {{
              parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
              parentWin.__kcPlayDiag.push({{
                t: resolvedAt,
                ev: 'play_ok',
                id: now && now.id,
                paused: now ? !!now.paused : null,
                ct: ctNow,
                rs: now ? Number(now.readyState || 0) : -1,
                alreadySettled: !!settled,
                playingAtWas: timing.playingAt,
              }});
            }} catch (e1) {{}}
            // Recycled-buffer play() often resolves 1–3s late while currentTime
            // already reflects audible start — backdate the gap clock.
            if (timing.playingAt == null) {{
              if (ctNow >= 0.05 && timing.playRequestedAt != null) {{
                timing.playingAt = Math.max(
                  Number(timing.endedAt || 0),
                  resolvedAt - ctNow * 1000
                );
                if (timing.playingAt < timing.playRequestedAt) {{
                  timing.playingAt = timing.playRequestedAt;
                }}
              }} else {{
                timing.playingAt = resolvedAt;
              }}
            }}
            if (!settled) {{
              publishAck(Math.max(0, timing.playingAt - timing.endedAt));
            }}
            try {{
              if (now.paused) {{
                const p2 = now.play();
                if (p2 && p2.catch) p2.catch(() => {{}});
              }}
            }} catch (e2) {{}}
          }}).catch(() => {{
            state._kcPlayInFlight = false;
            // Unmuted rejected — retry muted then unmute (autoplay policy).
            try {{
              now.muted = true;
              state._kcPlayInFlight = true;
              const pm = now.play();
              if (pm && pm.then) {{
                pm.then(() => {{
                  state._kcPlayInFlight = false;
                  try {{ now.muted = false; }} catch (e3) {{}}
                  if (timing.playingAt == null) timing.playingAt = kcNow();
                  if (!settled) {{
                    publishAck(Math.max(0, timing.playingAt - timing.endedAt));
                  }}
                }}).catch(() => {{
                  state._kcPlayInFlight = false;
                  afterPlayFail();
                }});
              }} else {{
                state._kcPlayInFlight = false;
                afterPlayFail();
              }}
            }} catch (e4) {{ state._kcPlayInFlight = false; afterPlayFail(); }}
          }});
        }} else if (now && !now.paused) {{
          state._kcPlayInFlight = false;
          onPlaying();
        }} else {{
          state._kcPlayInFlight = false;
          afterPlayFail();
        }}
      }};
      const onPlaying = () => {{
        if (settled || state.handoffToken !== handoffToken) return;
        if (timing.playingAt == null) timing.playingAt = kcNow();
        const gapMs = Math.max(0, timing.playingAt - timing.endedAt);
        publishAck(gapMs);
      }};
      try {{
        now.addEventListener('playing', onPlaying, {{ once: true }});
      }} catch (e) {{}}
      if (warmLive) {{
        try {{
          parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
          parentWin.__kcPlayDiag.push({{
            t: kcNow(),
            ev: 'warm_live_ack',
            id: now && now.id,
            ct: now ? Number(now.currentTime || 0) : -1,
          }});
        }} catch (eWL) {{}}
        onPlaying();
        kcSched(() => {{
          if (state.handoffToken !== handoffToken) return;
          if (settled) return;
          try {{ armFollowingAfterPlay(); }} catch (eArm) {{}}
        }}, 50);
        return;
      }}
      // If play() resolves late, a timeupdate still proves audible start.
      try {{
        const onTime = () => {{
          if (settled || state.handoffToken !== handoffToken) return;
          // Do not require !paused — Chromium can advance currentTime while the
          // play() promise (and paused flag) lag for 1–3s on recycled buffers.
          if (!now || Number(now.currentTime) < 0.02) return;
          try {{ now.removeEventListener('timeupdate', onTime); }} catch (e2) {{}}
          onPlaying();
        }};
        now.addEventListener('timeupdate', onTime);
        kcSched(() => {{
          try {{ now.removeEventListener('timeupdate', onTime); }} catch (e2) {{}}
        }}, 15000);
      }} catch (e) {{}}
      // High-frequency audible poll — primary gap clock. play() promise is not
      // trustworthy for recycled-buffer handoffs (measured ~1.4–2.6s late).
      try {{
        let pollN = 0;
        const audiblePoll = () => {{
          if (settled || state.handoffToken !== handoffToken) return;
          pollN += 1;
          try {{
            const ct = now ? Number(now.currentTime || 0) : 0;
            const moving = !!(now && ct >= 0.02 && (!now.paused || ct >= 0.05));
            if (moving) {{
              try {{
                parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
                parentWin.__kcPlayDiag.push({{
                  t: kcNow(),
                  ev: 'audible_poll_hit',
                  ct: ct,
                  paused: now ? !!now.paused : null,
                  pollN: pollN,
                  id: now && now.id,
                }});
              }} catch (eD) {{}}
              onPlaying();
              return;
            }}
          }} catch (eP) {{}}
          if (pollN < 200) kcSched(audiblePoll, 25);
        }};
        kcSched(audiblePoll, 0);
      }} catch (eAP) {{}}
      // After seek-to-zero, wait for seeked (or canplay) before kickPlay.
      // CRITICAL: call play() on the ended-event stack when no seek is needed
      // so Chromium keeps the user-gesture / media-engagement allowance.
      try {{
        const onReady = () => {{
          if (timing.nextReadyAt == null) timing.nextReadyAt = kcNow();
          kickPlay();
        }};
        const beginPlay = () => {{
          if (settled || state.handoffToken !== handoffToken) return;
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: kcNow(),
              ev: 'begin_play_after_seek',
              seekPending: !!seekPending,
              ct: now ? Number(now.currentTime || 0) : -1,
              rs: now ? Number(now.readyState || 0) : -1,
            }});
          }} catch (eB) {{}}
          if (now && Number(now.readyState || 0) >= 2) {{
            kickPlay();
          }} else if (now) {{
            now.addEventListener('canplay', onReady, {{ once: true }});
            try {{
              now.muted = true;
              const pm = now.play();
              if (pm && pm.then) {{
                pm.then(() => {{
                  try {{ now.muted = false; }} catch (eM) {{}}
                  kickPlay();
                }}).catch(() => {{ try {{ now.muted = false; }} catch (eM2) {{}} }});
              }}
            }} catch (eM0) {{}}
          }}
        }};
        if (seekPending && now) {{
          let seekDone = false;
          const onSeeked = () => {{
            if (seekDone) return;
            seekDone = true;
            beginPlay();
          }};
          now.addEventListener('seeked', onSeeked, {{ once: true }});
          // If already at 0 after sync seek, or seeked never fires.
          kcSched(() => {{
            if (!seekDone) {{
              seekDone = true;
              beginPlay();
            }}
          }}, 80);
          try {{
            if (Number(now.currentTime || 0) <= 0.05 && Number(now.readyState || 0) >= 2) {{
              seekDone = true;
              try {{ now.removeEventListener('seeked', onSeeked); }} catch (eR) {{}}
              beginPlay();
            }}
          }} catch (eS) {{}}
        }} else {{
          beginPlay();
        }}
        // Never arm idle decode while play() is still pending — competing load()
        // on the other buffer stalls the handoff (~3s+). Only arm after settle;
        // publishAck already calls armFollowingAfterPlay.
        kcSched(() => {{
          // Single re-kick only if still paused at ~0 (first kick lost).
          if (settled || state.handoffToken !== handoffToken) return;
          if (state._kcPlayInFlight) return;
          try {{
            if (now && now.paused && Number(now.currentTime || 0) < 0.02) {{
              kickPlay();
            }} else if (now && Number(now.currentTime || 0) >= 0.02) {{
              onPlaying();
            }}
          }} catch (eRk) {{}}
        }}, 500);
        return;
      }} catch (e) {{}}
      kickPlay();
    }}
    function onEnded() {{
      if (!state.enabled) return;
      if (state._onEndedGate) return;
      if (state.swapping || state.pendingHandoff) {{
        try {{
          parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
          parentWin.__kcPlayDiag.push({{
            t: performance.now(),
            ev: 'onEnded_ignore_handoff_in_flight',
            swapping: !!state.swapping,
            pending: !!state.pendingHandoff,
          }});
        }} catch (e) {{}}
        return;
      }}
      // Only advance when the ACTIVE buffer has actually ended (ignore idle/stale ended).
      try {{
        const act = activeAudio();
        if (act && Number(act.__kcIgnoreEndedUntil || 0) > kcNow()) {{
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: kcNow(),
              ev: 'onEnded_ignore_post_load',
              id: act.id,
              until: act.__kcIgnoreEndedUntil,
            }});
          }} catch (eIgn) {{}}
          return;
        }}
        if (act && !act.ended) {{
          const nearEnd = Number(act.duration || 0) > 1
            && Number(act.currentTime || 0) >= Number(act.duration || 0) - 0.08;
          if (!nearEnd) {{
            try {{
              parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
              parentWin.__kcPlayDiag.push({{
                t: performance.now(),
                ev: 'onEnded_ignore_active_not_ended',
                active: state.active,
                ct: Number(act.currentTime || 0),
                id: act.id,
              }});
            }} catch (e0) {{}}
            return;
          }}
        }}
        const sinceSwap = kcNow() - Number(state.swapStartedAt || 0);
        // One completed pass → one transition. Require a real mid-pass dwell
        // (or true near-end) before any new advance after a prior handoff.
        if (state.swapStartedAt && sinceSwap < 8000 && Number(state.passId || 0) > 0) {{
          const act2 = activeAudio();
          const played = act2 ? Number(act2.currentTime || 0) : 0;
          const dur = act2 ? Number(act2.duration || 0) : 0;
          const nearEnd2 = act2 && dur > 1 && played >= dur - 0.08;
          if (!nearEnd2 || played < 5) {{
            try {{
              parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
              parentWin.__kcPlayDiag.push({{
                t: performance.now(),
                ev: 'onEnded_ignore_too_soon',
                sinceSwap: sinceSwap,
                played: played,
                passId: state.passId,
              }});
            }} catch (e1) {{}}
            return;
          }}
        }}
      }} catch (e) {{}}
      state._onEndedGate = true;
      try {{
      if (state.swapping) {{
        const stuckFor = kcNow() - Number(state.swapStartedAt || 0);
        if (stuckFor < 4000) return;
        // Prior handoff never settled — force recover so the cycle can continue.
        try {{
          parentWin.__kcHandoffErrors = parentWin.__kcHandoffErrors || [];
          parentWin.__kcHandoffErrors.push({{
            t: performance.now(),
            err: 'force_clear_stuck_swapping',
            stuckFor: stuckFor,
          }});
        }} catch (e) {{}}
        state.swapping = false;
        state.ending = false;
      }}
      // Clear stuck ending from a prior failed attempt.
      state.ending = true;
      state.endedAt = kcNow();
      const idle = idleAudio();
      let nextUrl = String(state.nextUrl || '').trim();
      if (!nextUrl && idle && state.nextSounding) {{
        // Only fall back to idle URL when nextSounding is still armed.
        nextUrl = idle.getAttribute('data-kc-url') || '';
        if (!nextUrl && idle.src) {{
          try {{
            const u = new URL(idle.src, parentWin.location.origin);
            nextUrl = u.pathname + u.search;
          }} catch (e) {{
            nextUrl = idle.src;
          }}
        }}
      }}
      if (nextUrl) state.nextUrl = nextUrl;
      try {{
        parentWin.__kcOnEndedTrace = parentWin.__kcOnEndedTrace || [];
        parentWin.__kcOnEndedTrace.push({{
          t: state.endedAt,
          nextUrl: nextUrl,
          nextSounding: state.nextSounding || '',
          followingUrl: state.followingUrl || '',
          followingSounding: state.followingSounding || '',
          hasIdle: !!idle,
          idleReady: idle ? idle.readyState : -1,
          idleSrc: idle ? (idle.getAttribute('data-kc-url') || '').slice(-40) : '',
          idleSounding: idle ? (idle.getAttribute('data-kc-sounding') || '') : '',
        }});
      }} catch (e) {{}}
      if (idle && nextUrl) {{
        // Prefer seamless even if urlsMatch is strict — idle.src may be absolute.
        state.ending = false;
        doSeamlessSwap(idle, nextUrl);
        // Keep gate briefly; MUST clear via parent timer (iframe may die).
        try {{
          if (typeof parentWin.__kcSched === 'function') {{
            parentWin.__kcSched(() => {{ state._onEndedGate = false; }}, 5000);
          }} else {{
            parentWin.setTimeout(() => {{ state._onEndedGate = false; }}, 5000);
          }}
        }} catch (eGate) {{
          state._onEndedGate = false;
        }}
        return;
      }}
      const trySwap = (attempt) => {{
        if (!state.enabled) {{ state.ending = false; state._onEndedGate = false; return; }}
        if (state.swapping || state.pendingHandoff) {{ state.ending = false; return; }}
        const idle2 = idleAudio();
        const nxt = state.nextUrl
          || (idle2 && idle2.getAttribute('data-kc-url'))
          || '';
        if (idle2 && nxt) {{
          state.ending = false;
          doSeamlessSwap(idle2, nxt);
          try {{
            if (typeof parentWin.__kcSched === 'function') {{
              parentWin.__kcSched(() => {{ state._onEndedGate = false; }}, 5000);
            }} else {{
              parentWin.setTimeout(() => {{ state._onEndedGate = false; }}, 5000);
            }}
          }} catch (eGate) {{
            state._onEndedGate = false;
          }}
          return;
        }}
        if (attempt < 30) {{
          kcSched(() => trySwap(attempt + 1), 50);
          return;
        }}
        state.ending = false;
        state._onEndedGate = false;
        parentWin.__kcLastGapMs = null;
        clearHandoffCookie();
        // Last resort: signal Python without claiming playing.
        clickBridge('audio_ended::' + (state.passToken || 'pass'));
      }};
      trySwap(0);
      }} catch (eFinal) {{
        state._onEndedGate = false;
      }}
    }}
    parentWin.__kcOnEnded = onEnded;
    ensureKeyCycleWatchers();
    ['kc-buf-0', 'kc-buf-1'].forEach((id) => {{
      const a = parentWin.document.getElementById(id) || parentDoc.getElementById(id);
      if (!a) return;
      // One ended listener per buffer element; refresh only the shared handler ptr.
      if (!a.__kcEndedListener) {{
        a.__kcEndedHandler = (ev) => {{
          try {{
            const activeId = state.active === 1 ? 'kc-buf-1' : 'kc-buf-0';
            const target = (ev && ev.target) || a;
            if (target && target.id && target.id !== activeId) return;
            if (target && Number(target.__kcIgnoreEndedUntil || 0) > kcNow()) return;
            if (typeof parentWin.__kcOnEnded === 'function') parentWin.__kcOnEnded();
          }} catch (e) {{}}
        }};
        a.addEventListener('ended', a.__kcEndedHandler);
        a.__kcEndedListener = true;
      }}
      try {{ a.onended = null; }} catch (e) {{}}
      a.__kcEndedHook = true;
      // Bridge rerun after a missed ended event — recover once if active is ended.
      try {{
        if (
          state.enabled
          && !state.swapping
          && !state.ending
          && a.ended
          && !a.loop
          && (state.active === 0 ? id === 'kc-buf-0' : id === 'kc-buf-1')
        ) {{
          kcSched(() => {{
            try {{ if (typeof parentWin.__kcOnEnded === 'function') parentWin.__kcOnEnded(); }} catch (e) {{}}
          }}, 0);
        }}
      }} catch (e) {{}}
    }});

    parentWin.__kcApplyCmd = function applyCmd(cmd) {{
      if (!cmd) return;
      const detail = parentDoc.getElementById('kc-persistent-detail');
      parentWin.__kcLastCmd = cmd;
      if (!cmd.enabled) {{
        state.enabled = false;
        cancelPendingPlays();
        clearHandoffCookie();
        try {{ parentWin.__kcPendingPlayingAck = null; }} catch (e) {{}}
        try {{
          const a0 = parentWin.document.getElementById('kc-buf-0');
          const a1 = parentWin.document.getElementById('kc-buf-1');
          if (a0) {{ a0.pause(); a0.removeAttribute('src'); a0.removeAttribute('data-kc-url'); a0.load(); }}
          if (a1) {{ a1.pause(); a1.removeAttribute('src'); a1.removeAttribute('data-kc-url'); a1.load(); }}
        }} catch (e) {{}}
        state.playingUrl = '';
        state.nextUrl = '';
        state.nextSounding = '';
        state.nextChartHtml = '';
        state.followingUrl = '';
        state.followingSounding = '';
        state.followingChartHtml = '';
        state.aheadUrl = '';
        state.aheadSounding = '';
        state.aheadChartHtml = '';
        state.nextBufferReadyAt = null;
        state.nextBufferReadyState = 0;
        state.nextBufferReadyUrl = '';
        teardownKeyCycleWatchers();
        if (detail) detail.textContent = 'Key cycling off';
        return;
      }}
      // Re-enable path: ensure durable watchers exist after an Off teardown.
      ensureKeyCycleWatchers();
      parentWin.__kcOnEnded = onEnded;
      if (cmd.epoch != null && state.epoch > -1 && Number(cmd.epoch) < Number(state.epoch)) {{
        return; // stale
      }}
      state.enabled = true;
      state.epoch = Number(cmd.epoch || 0);
      state.passToken = String(cmd.passToken || 'pass');
      if (cmd.cycleId) state.cycleId = String(cmd.cycleId);
      if (cmd.passId != null && Number(cmd.passId) >= Number(state.passId || 0)) {{
        state.passId = Number(cmd.passId);
      }}
      const cur = String(cmd.currentUrl || '');
      const nxt = String(cmd.nextUrl || '');
      const follow = String(cmd.followingUrl || '');
      const ahead = String(cmd.aheadUrl || '');
      const act = activeAudio();
      const idle = idleAudio();
      try {{
        parentWin.__kcUrlToKey = parentWin.__kcUrlToKey || {{}};
        if (cur && cmd.sounding) parentWin.__kcUrlToKey[cur] = String(cmd.sounding);
        if (nxt && cmd.nextSounding) parentWin.__kcUrlToKey[nxt] = String(cmd.nextSounding);
        if (follow && cmd.followingSounding) parentWin.__kcUrlToKey[follow] = String(cmd.followingSounding);
        if (ahead && cmd.aheadSounding) parentWin.__kcUrlToKey[ahead] = String(cmd.aheadSounding);
      }} catch (e) {{}}
      if (nxt) {{
        // Never point next at the URL already sounding after a seamless flip.
        if (!(act && urlsMatch(act, nxt)) && state.playingUrl !== nxt) {{
          state.nextUrl = nxt;
          if (cmd.nextSounding) state.nextSounding = String(cmd.nextSounding || '');
          if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
        }}
      }} else if (cmd.nextSounding) {{
        if (cmd.nextSounding !== String(parentWin.__kcLastSounding || '')) {{
          state.nextSounding = String(cmd.nextSounding || '');
          if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
        }}
      }}
      if (follow) {{
        if (follow !== state.nextUrl && !(act && urlsMatch(act, follow))) {{
          state.followingUrl = follow;
          if (cmd.followingSounding) state.followingSounding = String(cmd.followingSounding || '');
          if (cmd.followingChartHtml) state.followingChartHtml = String(cmd.followingChartHtml || '');
        }}
      }} else if (cmd.followingSounding) {{
        if (cmd.followingSounding !== state.nextSounding) {{
          state.followingSounding = String(cmd.followingSounding || '');
          if (cmd.followingChartHtml) state.followingChartHtml = String(cmd.followingChartHtml || '');
        }}
      }}
      if (ahead) {{
        if (
          ahead !== state.nextUrl
          && ahead !== state.followingUrl
          && !(act && urlsMatch(act, ahead))
        ) {{
          state.aheadUrl = ahead;
          if (cmd.aheadSounding) state.aheadSounding = String(cmd.aheadSounding || '');
          if (cmd.aheadChartHtml) state.aheadChartHtml = String(cmd.aheadChartHtml || '');
        }}
      }} else if (cmd.aheadSounding) {{
        if (
          cmd.aheadSounding !== state.nextSounding
          && cmd.aheadSounding !== state.followingSounding
        ) {{
          state.aheadSounding = String(cmd.aheadSounding || '');
          if (cmd.aheadChartHtml) state.aheadChartHtml = String(cmd.aheadChartHtml || '');
        }}
      }}
      // If Streamlit wiped and recreated empty <audio> nodes, restore from state.
      try {{
        if (state.enabled && act && state.playingUrl && !act.getAttribute('data-kc-url')) {{
          act.setAttribute('data-kc-url', state.playingUrl);
          act.preload = 'auto';
          act.src = state.playingUrl;
          try {{ act.load(); }} catch (e2) {{}}
          if (!cmd.paused) {{
            const p = act.play();
            if (p && p.catch) p.catch(() => {{}});
          }}
        }}
        if (state.enabled && idle && state.nextUrl && !idle.getAttribute('data-kc-url')) {{
          armIdleFromUrl(idle, state.nextUrl, state.nextSounding, 'next');
        }}
      }} catch (e) {{}}
      const alreadyPlaying = !!(cur && (urlsMatch(act, cur) || state.playingUrl === cur));
      // Prefer live element URL over stale playingUrl during an in-flight handoff.
      if (cur && act && urlsMatch(act, cur)) {{
        state.playingUrl = cur;
      }}
      // Live seamless handoff owns the active buffer until Python's currentUrl
      // catches up. Prefetch fragment cmds often still carry the previous key.
      // Manual Next/Prev intentionally moves Python ahead to nextSounding — allow that.
      let liveHandoff = false;
      let browserSounding = '';
      try {{
        const actUrl = act ? (act.getAttribute('data-kc-url') || '') : '';
        browserSounding = act
          ? String(act.getAttribute('data-kc-sounding') || parentWin.__kcLastSounding || '').trim()
          : String(parentWin.__kcLastSounding || '').trim();
        const cmdSounding = String(cmd.sounding || '').trim();
        const armedNext = String(state.nextSounding || '').trim();
        const pythonToArmedNext = !!(cmdSounding && armedNext && cmdSounding === armedNext);
        const pythonMatchesBrowser = !!(
          cmdSounding && browserSounding && cmdSounding === browserSounding
        );
        // In-flight seamless swap must own the active buffer — a stale Python
        // currentUrl must not remount over the key we just flipped to.
        liveHandoff = !!(
          act
          && state.enabled
          && !pythonToArmedNext
          && (
            state.swapping
            || state.pendingHandoff
            || state._onEndedGate
            || (
              state.swapStartedAt
              && (performance.now() - Number(state.swapStartedAt)) < 12000
              && Number(state.passId || 0) > 0
              && !pythonMatchesBrowser
            )
            || (
              browserSounding
              && cmdSounding
              && browserSounding !== cmdSounding
              && cmdSounding !== armedNext
              && cmdSounding !== String(state.followingSounding || '').trim()
              && (urlsMatch(act, state.playingUrl) || !!actUrl)
            )
            || (
              state.playingUrl
              && cur
              && state.playingUrl !== cur
              && !urlsMatch(act, cur)
              && (urlsMatch(act, state.playingUrl) || actUrl === state.playingUrl)
            )
          )
        );
      }} catch (e) {{ liveHandoff = false; }}
      // Do not push chart/highlight from Python when audio is already on this URL
      // or when a seamless handoff owns the live buffer. Browser confirmed key wins.
      if (!alreadyPlaying && !liveHandoff) {{
        if (cmd.currentChartHtml) {{
          state.currentChartHtml = String(cmd.currentChartHtml);
          applyChartHtml(state.currentChartHtml, String(cmd.sounding || ''));
        }}
        try {{
          parentWin.__kcWriteTrace = parentWin.__kcWriteTrace || [];
          parentWin.__kcWriteTrace.push({{
            t: performance.now(),
            trigger: 'applyCmd_sounding',
            old: String(parentWin.__kcLastSounding || ''),
            new: String(cmd.sounding || ''),
            cycleId: String(state.cycleId || ''),
            passId: Number(state.passId || 0),
            audioId: act ? act.id : '',
            liveHandoff: false,
          }});
        }} catch (eW) {{}}
        parentWin.__kcLastSounding = String(cmd.sounding || '');
        syncHighlight(String(cmd.sounding || ''));
      }} else if (cmd.nextChartHtml) {{
        state.nextChartHtml = String(cmd.nextChartHtml);
      }} else if (liveHandoff) {{
        try {{
          parentWin.__kcWriteTrace = parentWin.__kcWriteTrace || [];
          parentWin.__kcWriteTrace.push({{
            t: performance.now(),
            trigger: 'applyCmd_reject_stale_python',
            old: String(parentWin.__kcLastSounding || ''),
            new: String(cmd.sounding || ''),
            browser: browserSounding,
            cycleId: String(state.cycleId || ''),
            passId: Number(state.passId || 0),
            audioId: act ? act.id : '',
          }});
        }} catch (eR) {{}}
      }}
      if (detail) {{
        detail.textContent = !cur
          ? 'Waiting for audio…'
          : ((state.nextUrl || nxt) ? 'Next key preloaded' : 'Preparing next key…');
      }}
      const refreshIdleOnly = () => {{
        if (!nxt || !idle) {{
          if (idle && state.nextSounding) idle.setAttribute('data-kc-sounding', state.nextSounding);
          return;
        }}
        // Never clobber idle with the URL already sounding on active.
        if (urlsMatch(act, nxt) || (state.playingUrl && state.playingUrl === nxt)) return;
        // After seamless promote, idle already holds +2; ignore stale Python +1.
        try {{
          const idleUrl = idle.getAttribute('data-kc-url') || '';
          if (
            state.nextUrl
            && idleUrl
            && idleUrl === state.nextUrl
            && nxt !== state.nextUrl
          ) {{
            return;
          }}
        }} catch (e) {{}}
        if (idle.getAttribute('data-kc-url') !== nxt) {{
          armIdleFromUrl(idle, nxt, state.nextSounding, 'next');
        }} else if (state.nextSounding) {{
          idle.setAttribute('data-kc-sounding', state.nextSounding);
          markBufferReady(idle, 'next');
        }}
      }};
      // Already sounding this URL (seamless handoff) — only refresh next buffer / pause.
      if (alreadyPlaying || liveHandoff) {{
        if (alreadyPlaying) state.playingUrl = cur;
        refreshIdleOnly();
        if (cmd.paused) {{
          cancelPendingPlays();
          try {{ if (act) act.pause(); }} catch (e) {{}}
        }} else if (!liveHandoff && (cmd.resume || (cmd.autoplay && act && act.paused))) {{
          cancelPendingPlays();
          const myGen = state.playGen;
          if (act) {{
            const p = act.play();
            if (p && p.catch) p.catch(() => {{ if (myGen === state.playGen) {{}} }});
          }}
        }}
        return;
      }}
      if (cur && act) {{
        const same = urlsMatch(act, cur) && state.playingUrl === cur;
        if (!same) {{
          cancelPendingPlays();
          try {{
            parentWin.__kcRemountLog = parentWin.__kcRemountLog || [];
            parentWin.__kcRemountLog.push({{
              t: performance.now(),
              from: state.playingUrl || '',
              to: cur,
              reason: 'applyCmd_src',
            }});
          }} catch (e) {{}}
          act.setAttribute('data-kc-url', cur);
          act.preload = 'auto';
          act.src = cur;
          state.playingUrl = cur;
          try {{ act.load(); }} catch (e) {{}}
          if (cmd.autoplay && !cmd.paused) {{
            const myGen = state.playGen;
            const tryPlay = () => {{
              if (!state.enabled || myGen !== state.playGen) return;
              const p = act.play();
              if (p && p.catch) p.catch(() => {{}});
            }};
            if (act.readyState >= 2) tryPlay();
            else {{
              act.addEventListener('canplay', tryPlay, {{ once: true }});
              window.setTimeout(tryPlay, 250);
            }}
          }}
        }} else if (cmd.paused) {{
          cancelPendingPlays();
          try {{ act.pause(); }} catch (e) {{}}
        }} else if (cmd.autoplay || cmd.resume) {{
          cancelPendingPlays();
          const myGen = state.playGen;
          const p = act.play();
          if (p && p.catch) p.catch(() => {{ if (myGen === state.playGen) {{}} }});
        }}
      }}
      if (nxt && idle) {{
        refreshIdleOnly();
      }}
    }};
    return root;
  }}

  try {{
    ensurePlayer();
    if (typeof parentWin.__kcApplyCmd === 'function') {{
      parentWin.__kcApplyCmd(CMD);
    }}
  }} catch (err) {{
    console.warn('kc persistent player bridge failed', err);
  }}
}})();
</script></body></html>"""


def render_backing_key_cycle_persistent_player(
    st: Any,
    session: dict[str, Any],
    *,
    current_url: str,
    next_url: str = "",
    autoplay: bool = True,
    force_disable: bool = False,
) -> bool:
    """Drive the parent dual-buffer player. Returns True when command was sent."""
    import json

    if force_disable or not is_cycle_active(session):
        # Push a disable command so leftover parent audio stops.
        try:
            import streamlit.components.v1 as components

            components.html(
                cycle_persistent_player_bridge_html(
                    cmd_json=json.dumps(
                        {
                            "enabled": False,
                            "epoch": int(session.get("_kc_player_cmd_epoch") or 0),
                        }
                    )
                ),
                height=1,
                scrolling=False,
            )
        except Exception:
            pass
        return False
    data = get_owner_cycle_session(session) or {}
    if str(data.get("status") or "") == STATUS_STOPPED:
        return False
    cur = str(current_url or session.get("_kc_current_static_url") or "").strip()
    if cur and not _kc_static_url_on_disk(cur):
        cur = ""
        session.pop("_kc_current_static_url", None)
    if not cur:
        path = str(session.get("_last_backing_wav_path") or "").strip()
        if path:
            cur = publish_cycle_wav_static_url(
                path, signature=session.get("_last_backing_signature")
            )
            if cur:
                session["_kc_current_static_url"] = cur
    # Do not send an empty enable command — that blanks the parent player.
    if not cur:
        return False
    nxt = str(next_url or "").strip()
    if not nxt:
        nxt = prepared_cycle_static_url(session, next_cycle_playback_key(session))
    following_sounding = str(peek_cycle_key_at_delta(session, steps=2) or "").strip()
    following_url = ""
    if following_sounding and following_sounding != str(
        next_cycle_playback_key(session) or ""
    ).strip():
        following_url = prepared_cycle_static_url(session, following_sounding)
    ahead_sounding = str(peek_cycle_key_at_delta(session, steps=3) or "").strip()
    ahead_url = ""
    if (
        ahead_sounding
        and ahead_sounding != following_sounding
        and ahead_sounding != str(next_cycle_playback_key(session) or "").strip()
    ):
        ahead_url = prepared_cycle_static_url(session, ahead_sounding)
    wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
    token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
    held = str(data.get("status") or "") == STATUS_HELD
    skip_remount = bool(session.pop("_kc_skip_audio_remount", False))
    sounding = str(data.get("current_playback_key") or temporary_playback_key(session) or "")
    next_sounding = ""
    if nxt:
        next_sounding = str(next_cycle_playback_key(session) or "").strip()
    current_chart = prepared_cycle_chart_html(session, sounding)
    next_chart = prepared_cycle_chart_html(session, next_sounding) if next_sounding else ""
    following_chart = (
        prepared_cycle_chart_html(session, following_sounding)
        if following_sounding and following_url
        else ""
    )
    ahead_chart = (
        prepared_cycle_chart_html(session, ahead_sounding)
        if ahead_sounding and ahead_url
        else ""
    )
    if not current_chart:
        try:
            from backing_key_cycle_handoff import build_cycle_chart_strip_html

            current_chart = build_cycle_chart_strip_html(sounding_key=sounding, chords=[])
        except Exception:
            current_chart = ""
    cmd = {
        "enabled": True,
        "epoch": int(session.get("_kc_player_cmd_epoch") or 0),
        "cycleId": str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
        "passId": int(data.get("pass_id") or 0),
        "currentUrl": cur,
        "nextUrl": nxt,
        "followingUrl": following_url,
        "aheadUrl": ahead_url,
        "sounding": sounding,
        "nextSounding": next_sounding,
        "followingSounding": following_sounding if following_url else "",
        "aheadSounding": ahead_sounding if ahead_url else "",
        "currentChartHtml": current_chart,
        "nextChartHtml": next_chart,
        "followingChartHtml": following_chart,
        "aheadChartHtml": ahead_chart,
        "passToken": token,
        "autoplay": bool(autoplay) and not held and not skip_remount and bool(cur),
        "paused": held,
        "resume": (not held) and skip_remount,
    }
    try:
        import streamlit.components.v1 as components

        components.html(
            cycle_persistent_player_bridge_html(cmd_json=json.dumps(cmd)),
            height=1,
            scrolling=False,
        )
        return True
    except Exception:
        return False


def cycle_compact_audio_player_html(
    *,
    audio_b64: str,
    pass_token: str = "",
    autoplay: bool = True,
) -> str:
    """Legacy compact b64 player (kept for small-WAV fallback)."""
    token = str(pass_token or "").strip() or "pass"
    safe = token.replace("\\", "\\\\").replace("'", "\\'")
    label = BACKING_KEY_CYCLE_PASS_FINISHED_LABEL.replace("\\", "\\\\").replace("'", "\\'")
    autoplay_attr = "autoplay" if autoplay else ""
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
    """Receive playing handoffs via declare_component (no hidden form race)."""
    if not is_cycle_active(session):
        try:
            from backing_key_cycle_handoff import render_handoff_component

            # Disarm receiver after Off / leave so stale pending acks are ignored.
            render_handoff_component(st, session, armed=False, expect_cycle_id="")
        except Exception:
            pass
        return
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return
    handoff_ack = None
    try:
        from backing_key_cycle_handoff import render_handoff_component

        handoff_ack = render_handoff_component(
            st,
            session,
            expect_cycle_id=str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
            armed=True,
        )
    except Exception:
        handoff_ack = None
    if not isinstance(handoff_ack, dict):
        return
    gap_ms = None
    chart_ms = None
    if handoff_ack.get("gapMs") is not None:
        try:
            gap_ms = float(handoff_ack.get("gapMs"))
        except Exception:
            gap_ms = None
    if handoff_ack.get("chartMs") is not None:
        try:
            chart_ms = float(handoff_ack.get("chartMs"))
        except Exception:
            chart_ms = None
    playing_key = str(handoff_ack.get("playingKey") or "").strip()
    pass_sig = (
        f"playing::{handoff_ack.get('ackId') or 'ack'}"
        f"::{playing_key or 'key'}"
    )
    advanced = note_backing_pass_finished(
        session,
        pass_signature=pass_sig,
        seamless=True,
        gap_ms=gap_ms,
        handoff_ack=handoff_ack,
    )
    seamless = bool(session.get("_kc_seamless_handoff"))
    try:
        import json
        import os
        import time
        from pathlib import Path as _Path

        data_dir = _Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / "_key_cycle_bridge_clicks.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "advanced": bool(advanced),
                        "token": pass_sig,
                        "seamless": seamless,
                        "gap_ms": gap_ms,
                        "chart_ms": chart_ms,
                        "ack_kind": str(handoff_ack.get("kind") or ""),
                        "playing_key": playing_key,
                        "natural": bool(handoff_ack.get("natural")),
                        "channel": "declare_component",
                        "timing": handoff_ack.get("timing") or {},
                        "sounding": temporary_playback_key(session),
                    }
                )
                + "\n"
            )
        if chart_ms is not None:
            with (data_dir / "_key_cycle_pass_gaps.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "t": time.time(),
                            "gap_s": float(chart_ms) / 1000.0,
                            "kind": "chart",
                            "sounding": temporary_playback_key(session),
                        }
                    )
                    + "\n"
                )
    except Exception:
        pass
    if advanced:
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
    "mark_cycle_next_pass_playing_clock",
    "mark_cycle_next_pass_ready_clock",
    "mark_cycle_pass_ended_clock",
    "maybe_consume_cycle_pass_from_query",
    "next_cycle_playback_key",
    "note_backing_pass_finished",
    "pause_key_cycle",
    "peek_cycle_key_at_delta",
    "prepared_cycle_static_url",
    "previous_cycle_playback_key",
    "previous_key_cycle_now",
    "promote_prepared_cycle_audio",
    "publish_cycle_wav_static_url",
    "render_backing_key_cycle_compact_audio",
    "render_backing_key_cycle_controls",
    "render_backing_key_cycle_pass_bridge",
    "render_backing_key_cycle_persistent_player",
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
    "cycle_prefetch_neighbor_keys",
]
