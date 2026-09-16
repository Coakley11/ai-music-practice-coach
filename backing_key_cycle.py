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
            from backing_key_cycle_handoff import ACKED_IDS_KEY

            session.pop(ACKED_IDS_KEY, None)
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
    # Keep enough neighbors for dual-buffer + a few recent passes. Never prune
    # aggressively while a long catalog WAV may still be referenced by the player.
    try:
        files = sorted(path.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[12:]:
            try:
                stale.unlink()
            except OSError:
                pass
    except Exception:
        pass
    return path


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
) -> None:
    """Remember at most two prepared keys (current neighbor + next) by path/sig only."""
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
                sounding_key=key, chords=list(chords or ())
            )
        except Exception:
            html = ""
    bag[key] = {
        "signature": signature,
        "path": path,
        "static_url": url,
        "chart_html": html,
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
    if url:
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
    # Ask the app to prefetch the new neighbor after this step settles.
    session[BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY] = peek_cycle_key_at_delta(
        session, steps=1 if steps >= 0 else -1
    )
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
    playingKey / ackId). Prepared audio alone must not advance or autoplay.
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
            seamless = True
            if gap_ms is None and ack.get("gapMs") is not None:
                try:
                    gap_ms = float(ack.get("gapMs"))
                except Exception:
                    gap_ms = None
            # Align signature to playing key + pass id for dedupe.
            playing = str(ack.get("playingKey") or "").strip()
            pass_id = ack.get("passId")
            if playing:
                promote_prepared_cycle_audio(session, playing)
                pass_signature = (
                    f"playing::{data.get('cycle_id') or ''}::{pass_id}::{playing}"
                )
        except Exception:
            return False
    elif seamless:
        # Legacy seamless token path — still require prepared next, but do not
        # treat "prepared only" as playing without an ack.
        pass
    else:
        # Non-ack ended clicks may remount via CONTINUE_PLAY when next buffer
        # was not ready in the browser.
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
    if (!root) {{
      root = parentDoc.createElement('div');
      root.id = 'kc-persistent-root';
      root.setAttribute('data-testid', 'kc-persistent-root');
      root.style.cssText = 'margin:.35rem 0 .5rem;padding:0;';
      root.innerHTML = `
        <div id="kc-chart-live" data-testid="kc-chart-live"></div>
        <div id="kc-persistent-meta" style="font:12px/1.35 system-ui,sans-serif;opacity:.85;margin:0 0 .25rem"></div>
        <audio id="kc-buf-0" controls preload="auto" style="width:100%;display:block"></audio>
        <audio id="kc-buf-1" preload="auto" style="display:none"></audio>
        <div id="kc-persistent-detail" style="font:11px/1.3 system-ui,sans-serif;opacity:.65;margin-top:2px"></div>`;
      const btnAnchor = parentDoc.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]')
        || parentDoc.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
      const btnRow = btnAnchor && (
        btnAnchor.closest('[data-testid="stHorizontalBlock"]')
        || btnAnchor.parentElement
      );
      const bar = parentDoc.querySelector('.ui-key-cycle-playbar');
      if (btnRow && btnRow.parentElement) {{
        // Place audio under Pause/Prev/Next/Off so native controls never cover them.
        btnRow.parentElement.insertBefore(root, btnRow.nextSibling);
      }} else if (bar && bar.parentElement) {{
        bar.parentElement.insertBefore(root, bar.nextSibling);
      }} else {{
        const anchor = parentDoc.querySelector('h4,h3,[data-testid="stMarkdown"]');
        if (anchor && anchor.parentElement) {{
          anchor.parentElement.insertBefore(root, anchor.nextSibling);
        }} else {{
          parentDoc.body.appendChild(root);
        }}
      }}
    }} else if (!parentDoc.getElementById('kc-chart-live')) {{
      const meta = parentDoc.getElementById('kc-persistent-meta');
      const chart = parentDoc.createElement('div');
      chart.id = 'kc-chart-live';
      chart.setAttribute('data-testid', 'kc-chart-live');
      if (meta && meta.parentElement) meta.parentElement.insertBefore(chart, meta);
      else root.insertBefore(chart, root.firstChild);
    }}
    // Keep player below transport buttons even after earlier mounts.
    try {{
      const btnAnchor = parentDoc.querySelector('[class*="st-key-backing_key_cycle_stop_btn"]')
        || parentDoc.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]');
      const btnRow = btnAnchor && (
        btnAnchor.closest('[data-testid="stHorizontalBlock"]')
        || btnAnchor.parentElement
      );
      if (btnRow && btnRow.parentElement && root.previousElementSibling !== btnRow) {{
        btnRow.parentElement.insertBefore(root, btnRow.nextSibling);
      }}
    }} catch (e) {{}}
    if (!parentWin.__kcDual) {{
      parentWin.__kcDual = {{
        active: 0,
        playingUrl: '',
        nextUrl: '',
        nextSounding: '',
        currentChartHtml: '',
        nextChartHtml: '',
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

    function activeAudio() {{
      return parentDoc.getElementById(state.active === 0 ? 'kc-buf-0' : 'kc-buf-1');
    }}
    function idleAudio() {{
      return parentDoc.getElementById(state.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
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
    function doSeamlessSwap(idle, nextUrl) {{
      state.swapping = true;
      try {{ activeAudio().pause(); }} catch (e) {{}}
      const fromKey = String(parentWin.__kcLastSounding || '');
      const sounding = String(state.nextSounding || '');
      const chartHtml = String(state.nextChartHtml || '');
      state.active = state.active === 0 ? 1 : 0;
      const now = activeAudio();
      const other = idleAudio();
      now.style.display = 'block';
      if (other) other.style.display = 'none';
      try {{ now.currentTime = 0; }} catch (e) {{}}
      // Chart swaps with the audio buffer — never wait for Streamlit.
      applyChartHtml(chartHtml, sounding);
      syncHighlight(sounding);
      state.chartMs = Math.max(0, performance.now() - state.endedAt);
      parentWin.__kcLastChartMs = state.chartMs;
      if (chartHtml) state.currentChartHtml = chartHtml;
      cancelPendingPlays();
      const myGen = state.playGen;
      let settled = false;
      const afterPlayOk = () => {{
        if (settled) return;
        if (!state.enabled || myGen !== state.playGen) return;
        settled = true;
        const gapMs = Math.max(0, performance.now() - state.endedAt);
        parentWin.__kcLastGapMs = gapMs;
        state.playingUrl = nextUrl;
        state.nextUrl = '';
        const playingKey = sounding;
        state.nextSounding = '';
        state.nextChartHtml = '';
        state.swapping = false;
        state.passId = Number(state.passId || 0) + 1;
        const ackId = 'ack_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
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
        }};
        setHandoffCookie(ack);
        const tok = 'playing::' + ackId + '::' + Math.round(gapMs);
        try {{ parentWin.__kcLastBridgeTok = tok; }} catch (e) {{}}
        try {{
          parentWin.sessionStorage.setItem('kc_last_gap_ms', String(Math.round(gapMs)));
          parentWin.sessionStorage.setItem('kc_last_chart_ms', String(Math.round(Number(state.chartMs) || 0)));
          parentWin.sessionStorage.setItem('kc_last_bridge', tok);
        }} catch (e) {{}}
        // Give Streamlit's text_input a beat to accept the ack JSON before the click.
        window.setTimeout(() => clickBridge(tok), 120);
      }};
      const afterPlayFail = () => {{
        if (myGen !== state.playGen) return;
        state.swapping = false;
        // Do not ack — prepared/swap without audible play must not advance Python.
      }};
      let playP = null;
      try {{ playP = now.play(); }} catch (e) {{ playP = null; }}
      if (playP && playP.then) {{
        playP.then(afterPlayOk).catch(afterPlayFail);
      }} else if (now && !now.paused) {{
        afterPlayOk();
      }} else {{
        afterPlayFail();
      }}
    }}
    function onEnded() {{
      if (state.swapping || state.ending) return;
      if (!state.enabled) return;
      state.ending = true;
      state.endedAt = performance.now();
      const idle = idleAudio();
      let nextUrl = state.nextUrl
        || (idle && idle.getAttribute('data-kc-url'))
        || '';
      if (!nextUrl && idle && idle.src) {{
        try {{
          const u = new URL(idle.src, parentWin.location.origin);
          nextUrl = u.pathname + u.search;
        }} catch (e) {{
          nextUrl = idle.src;
        }}
      }}
      if (nextUrl) state.nextUrl = nextUrl;
      if (idle && nextUrl && (urlsMatch(idle, nextUrl) || idle.src)) {{
        state.ending = false;
        doSeamlessSwap(idle, nextUrl);
        return;
      }}
      const trySwap = (attempt) => {{
        if (!state.enabled) {{ state.ending = false; return; }}
        const idle2 = idleAudio();
        const nxt = state.nextUrl
          || (idle2 && idle2.getAttribute('data-kc-url'))
          || '';
        if (idle2 && nxt && (urlsMatch(idle2, nxt) || idle2.src)) {{
          state.ending = false;
          doSeamlessSwap(idle2, nxt);
          return;
        }}
        if (attempt < 20 && state.nextUrl) {{
          window.setTimeout(() => trySwap(attempt + 1), 40);
          return;
        }}
        state.ending = false;
        parentWin.__kcLastGapMs = null;
        // Not playing yet — no cookie ack; Python may remount via CONTINUE_PLAY.
        clearHandoffCookie();
        clickBridge('audio_ended::' + (state.passToken || 'pass'));
      }};
      trySwap(0);
    }}
    parentWin.__kcOnEnded = onEnded;
    ['kc-buf-0', 'kc-buf-1'].forEach((id) => {{
      const a = parentDoc.getElementById(id);
      if (!a) return;
      a.onended = onEnded;
      a.__kcEndedHook = true;
    }});

    parentWin.__kcApplyCmd = function applyCmd(cmd) {{
      if (!cmd) return;
      const detail = parentDoc.getElementById('kc-persistent-detail');
      parentWin.__kcLastCmd = cmd;
      if (!cmd.enabled) {{
        state.enabled = false;
        cancelPendingPlays();
        clearHandoffCookie();
        try {{
          const a0 = parentDoc.getElementById('kc-buf-0');
          const a1 = parentDoc.getElementById('kc-buf-1');
          if (a0) {{ a0.pause(); a0.removeAttribute('src'); a0.removeAttribute('data-kc-url'); a0.load(); }}
          if (a1) {{ a1.pause(); a1.removeAttribute('src'); a1.removeAttribute('data-kc-url'); a1.load(); }}
        }} catch (e) {{}}
        state.playingUrl = '';
        state.nextUrl = '';
        state.nextSounding = '';
        state.nextChartHtml = '';
        if (detail) detail.textContent = 'Key cycling off';
        return;
      }}
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
      if (nxt) {{
        state.nextUrl = nxt;
        state.nextSounding = String(cmd.nextSounding || '');
        if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
      }} else if (cmd.nextSounding) {{
        state.nextSounding = String(cmd.nextSounding || '');
        if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
      }}
      if (cmd.currentChartHtml) {{
        state.currentChartHtml = String(cmd.currentChartHtml);
        applyChartHtml(state.currentChartHtml, String(cmd.sounding || ''));
      }}
      parentWin.__kcLastSounding = String(cmd.sounding || '');
      syncHighlight(String(cmd.sounding || ''));
      const act = activeAudio();
      const idle = idleAudio();
      if (detail) {{
        detail.textContent = !cur
          ? 'Waiting for audio…'
          : ((state.nextUrl || nxt) ? 'Next key preloaded' : 'Preparing next key…');
      }}
      // Already sounding this URL (seamless handoff) — only refresh next buffer / pause.
      if (cur && (state.playingUrl === cur || urlsMatch(act, cur))) {{
        state.playingUrl = cur;
        if (nxt && idle && idle.getAttribute('data-kc-url') !== nxt) {{
          idle.setAttribute('data-kc-url', nxt);
          idle.preload = 'auto';
          idle.src = nxt;
          try {{ idle.load(); }} catch (e) {{}}
        }}
        if (cmd.paused) {{
          cancelPendingPlays();
          try {{ if (act) act.pause(); }} catch (e) {{}}
        }} else if (cmd.resume || (cmd.autoplay && act && act.paused)) {{
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
        if (idle.getAttribute('data-kc-url') !== nxt) {{
          idle.setAttribute('data-kc-url', nxt);
          idle.preload = 'auto';
          idle.src = nxt;
          try {{ idle.load(); }} catch (e) {{}}
        }}
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
        "sounding": sounding,
        "nextSounding": next_sounding,
        "currentChartHtml": current_chart,
        "nextChartHtml": next_chart,
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
    """Hidden Streamlit button clicked from the audio iframe when a pass ends."""
    if not is_cycle_active(session):
        return
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return
    # Visually hide; iframe JS still finds the submit button by exact label text.
    st.markdown(
        f"""
<style>
div[class*="st-key-kc_handoff_form"],
div[class*="st-key-kc_handoff_ack_json"],
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
    # Form batches ack JSON + submit so Streamlit does not drop the click after
    # a lone text_input change rerun.
    with st.form("kc_handoff_form", clear_on_submit=False, border=False):
        st.text_input(
            "kc_handoff_ack",
            key="kc_handoff_ack_json",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            BACKING_KEY_CYCLE_PASS_FINISHED_LABEL,
            type="secondary",
        )
    if submitted:
        handoff_ack = None
        try:
            raw_ack = str(session.get("kc_handoff_ack_json") or "").strip()
            if raw_ack:
                import json as _json_ack

                parsed = _json_ack.loads(raw_ack)
                if isinstance(parsed, dict):
                    handoff_ack = parsed
        except Exception:
            handoff_ack = None
        if handoff_ack is None:
            try:
                from backing_key_cycle_handoff import read_handoff_ack_from_st

                handoff_ack = read_handoff_ack_from_st(st)
            except Exception:
                handoff_ack = None
        try:
            session["kc_handoff_ack_json"] = ""
        except Exception:
            pass
        raw_tok = ""
        try:
            raw = st.query_params.get("kc_bridge")
            if isinstance(raw, (list, tuple)):
                raw = raw[0] if raw else ""
            raw_tok = str(raw or "").strip()
            if "kc_bridge" in st.query_params:
                del st.query_params["kc_bridge"]
        except Exception:
            raw_tok = ""
        wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
        token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
        seamless = False
        gap_ms = None
        chart_ms = None
        if isinstance(handoff_ack, dict) and str(handoff_ack.get("kind") or "") == "playing":
            # Explicit playing ack is the only path that skips CONTINUE_PLAY remount.
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
                f"playing::{handoff_ack.get('ackId') or token}"
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
        elif raw_tok.startswith("playing::"):
            # Cookie missed — do not invent a playing ack from prepared audio.
            pass_sig = f"audio_ended::{token}"
            advanced = note_backing_pass_finished(
                session,
                pass_signature=pass_sig,
                seamless=False,
                gap_ms=None,
            )
        elif raw_tok.startswith("seamless::"):
            # Legacy token without cookie — remount path only (prepared ≠ playing).
            parts = raw_tok.split("::")
            if len(parts) >= 3:
                try:
                    gap_ms = float(parts[-1])
                except Exception:
                    gap_ms = None
            pass_sig = f"audio_ended::{token}"
            advanced = note_backing_pass_finished(
                session,
                pass_signature=pass_sig,
                seamless=False,
                gap_ms=None,
            )
        elif raw_tok.startswith("audio_ended::"):
            pass_sig = raw_tok
            advanced = note_backing_pass_finished(
                session,
                pass_signature=pass_sig,
                seamless=False,
                gap_ms=None,
            )
        else:
            pass_sig = f"audio_ended::{token}"
            advanced = note_backing_pass_finished(
                session,
                pass_signature=pass_sig,
                seamless=False,
                gap_ms=None,
            )
        if advanced and session.get("_kc_seamless_handoff"):
            seamless = True
            if gap_ms is None and session.get(BACKING_KEY_CYCLE_PASS_GAP_KEY):
                try:
                    gap_ms = float(
                        (session.get(BACKING_KEY_CYCLE_PASS_GAP_KEY) or {}).get(
                            "gap_playing_s", 0
                        )
                        or 0
                    ) * 1000.0
                except Exception:
                    gap_ms = None
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
                            "token": pass_sig,
                            "seamless": seamless,
                            "gap_ms": gap_ms,
                            "chart_ms": chart_ms,
                            "ack_kind": (
                                str((handoff_ack or {}).get("kind") or "")
                                if isinstance(handoff_ack, dict)
                                else ""
                            ),
                            "playing_key": (
                                str((handoff_ack or {}).get("playingKey") or "")
                                if isinstance(handoff_ack, dict)
                                else ""
                            ),
                            "natural": bool(
                                isinstance(handoff_ack, dict)
                                and handoff_ack.get("natural")
                            ),
                            "sounding": temporary_playback_key(session),
                        }
                    )
                    + "\n"
                )
            if chart_ms is not None:
                with (data / "_key_cycle_pass_gaps.jsonl").open("a", encoding="utf-8") as fh:
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
]
