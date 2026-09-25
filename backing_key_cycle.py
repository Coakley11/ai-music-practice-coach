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
# Arrangement / PK / cycle-settings changed — next Play applies; do not autoplay.
BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY = "_backing_key_cycle_settings_pending_play"
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


def cycle_chart_mode(session: dict[str, Any]) -> str:
    """Active reading mode for cycle strip / charts: concert | written | shape."""
    instrument = str(session.get("instrument") or "Piano").strip() or "Piano"
    try:
        from instrument_transposition import chart_in_instrument_key, is_transposing_instrument

        if is_transposing_instrument(instrument) and chart_in_instrument_key(session):
            return "written"
    except ImportError:
        pass
    try:
        from guitar_capo import CAPO_ENABLED_KEY

        if instrument == "Guitar" and session.get(CAPO_ENABLED_KEY):
            return "shape"
    except ImportError:
        pass
    return "concert"


def project_cycle_display_key(
    session: dict[str, Any],
    concert_key: str,
    *,
    owner: str = "",
) -> str:
    """Musician-facing cycle label for one concert token (strip + chart).

    Concert audio identity is unchanged. Written mode uses the existing
    instrument transposition helpers. Shape mode maps the cycle motion into
    shape-key space from the cycle start anchor (G→Ab→A with C-shape → C→C#→D).
    """
    concert = str(concert_key or "").strip() or "C"
    mode = cycle_chart_mode(session)
    if mode == "concert":
        return concert
    if mode == "written":
        try:
            from instrument_transposition import written_key_for_instrument

            instrument = str(session.get("instrument") or "Piano").strip() or "Piano"
            written = str(
                written_key_for_instrument(concert, instrument, session) or ""
            ).strip()
            return written or concert
        except ImportError:
            return concert
    # shape
    try:
        from guitar_capo import CAPO_SHAPE_KEY, shape_chart_key_for_concert, shape_tonic_only
        from music_theory import semitone_distance

        shape = shape_tonic_only(str(session.get(CAPO_SHAPE_KEY) or "").strip())
        if not shape:
            return concert
        data = get_owner_cycle_session(session, owner) or {}
        start = str(
            data.get("start_cycle_key")
            or data.get("base_practice_key")
            or current_backing_owner_practice_key(session)
            or concert
        ).strip() or concert
        base_display = shape_chart_key_for_concert(start, shape)
        steps = semitone_distance(start, concert)
        prefs = (
            data.get("spelling_prefs")
            if isinstance(data.get("spelling_prefs"), dict)
            else spelling_prefs_from_session(session)
        )
        return cycle_concert_practice_key(
            base_display, semitones=steps, spelling_prefs=prefs
        )
    except ImportError:
        return concert


def project_cycle_sequence_labels(
    session: dict[str, Any],
    *,
    owner: str = "",
    sequence: list[str] | None = None,
) -> list[str]:
    """Display labels aligned 1:1 with the concert ``cycle_key_sequence``."""
    seq = list(sequence) if sequence is not None else cycle_key_sequence(session, owner)
    return [project_cycle_display_key(session, k, owner=owner) for k in seq]


def reproject_key_cycle_display(session: dict[str, Any]) -> bool:
    """Rebuild strip/chart projection after instrument / Written / Shape change.

    Keeps cycle position, concert audio URLs, and saved Practice Key. Only
    refreshes prepared ``chart_html`` and a display signature for the playbar.
    """
    if not is_cycle_active(session):
        return False
    mode = cycle_chart_mode(session)
    seq = cycle_key_sequence(session)
    labels = project_cycle_sequence_labels(session, sequence=seq)
    sig = f"{mode}|{','.join(labels)}|{session.get('instrument')}|{session.get('guitar_capo_shape_key')}"
    prev = str(session.get("_kc_display_proj_sig") or "")
    session["_kc_display_proj_sig"] = sig
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if isinstance(bag, dict):
        for key, entry in list(bag.items()):
            if not isinstance(entry, dict):
                continue
            # Force chart rebuild on next ensure/store path.
            entry["chart_html"] = ""
            entry["display_proj_sig"] = sig
            # Rebuild immediately when we still have arrangement metadata.
            try:
                store_prepared_cycle_audio(
                    session,
                    sounding_key=str(key),
                    signature=entry.get("signature"),
                    wav_path=str(entry.get("path") or ""),
                    static_url=str(entry.get("static_url") or ""),
                )
            except Exception:
                bag[key] = entry
    # Soft bump so the bridge remounts chips/charts without treating this as
    # a new arrangement Play.
    session["_kc_display_cmd_nonce"] = int(session.get("_kc_display_cmd_nonce") or 0) + 1
    if sig != prev:
        session["_kc_display_reproject"] = True
        # Remount the cmd bridge so JS receives fresh chart HTML without a
        # new arrangement replace. Player treats displayReproject as skip_remount.
        session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    return sig != prev


def cycle_sequence_index(session: dict[str, Any], owner: str = "") -> int:
    """Index of current sounding key within ``cycle_key_sequence`` (wrap-safe)."""
    seq = cycle_key_sequence(session, owner)
    if not seq:
        return 0
    data = get_owner_cycle_session(session, owner) or {}
    cur = str(
        data.get("current_playback_key")
        or temporary_playback_key(session)
        or ""
    ).strip()
    for i, key_tok in enumerate(seq):
        if _keys_equivalent(key_tok, cur):
            return i
    # Fall back: map offset onto sequence order (direction-aware).
    interval = int(data.get("interval") or 1)
    if interval not in {1, 2}:
        interval = 1
    n = len(seq)
    direction = str(data.get("direction") or "up")
    raw = int(data.get("offset_semitones") or 0) // interval
    if direction == "down":
        return int((-raw) % n)
    return int(raw % n)


def peek_cycle_key_at_delta(session: dict[str, Any], *, steps: int = 1) -> str:
    """Sounding key ``steps`` along the configured sequence without mutating."""
    data = get_owner_cycle_session(session) or {}
    if not data:
        return current_backing_owner_practice_key(session)
    seq = cycle_key_sequence(session)
    if not seq:
        return current_backing_owner_practice_key(session)
    cur = str(data.get("current_playback_key") or temporary_playback_key(session) or "").strip()
    idx = 0
    for i, key_tok in enumerate(seq):
        if _keys_equivalent(key_tok, cur):
            idx = i
            break
    else:
        idx = cycle_sequence_index(session)
    return seq[(idx + int(steps)) % len(seq)]


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
    # Adjacent keys first (+1 and -1) so Next and Previous can hit cache.
    for steps in (1, -1, 2, 3):
        k = str(peek_cycle_key_at_delta(session, steps=steps) or "").strip()
        if k and k != cur and k not in keys:
            keys.append(k)
    return keys


def clear_key_cycle_prepared_audio(
    session: dict[str, Any],
    *,
    stop_player: bool = False,
    clear_current_url: bool = True,
) -> None:
    session.pop(BACKING_KEY_CYCLE_PREPARED_KEY, None)
    session.pop(BACKING_KEY_CYCLE_PREFETCH_TARGET_KEY, None)
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session.pop("_kc_seamless_handoff", None)
    session.pop("_kc_skip_audio_remount", None)
    if clear_current_url:
        session.pop("_kc_current_static_url", None)
    session.pop("_kc_arrangement_url", None)
    session.pop("_kc_arrangement_reload", None)
    session.pop("_kc_force_arrangement_replace", None)
    session.pop("_kc_force_play_published_url", None)
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


def _bump_cycle_identity(session: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """New cycle_id / pass_id so late handoffs and stale gens cannot restore old state."""
    data = dict(data)
    try:
        from backing_key_cycle_handoff import new_cycle_id

        data["cycle_id"] = new_cycle_id()
    except Exception:
        import time as _time

        data["cycle_id"] = str(int(_time.time() * 1000))[-12:]
    data["pass_id"] = 0
    data["pending_pass_advance"] = False
    data["last_pass_signature"] = ""
    data["passes_completed"] = 0
    session["_kc_cycle_id"] = data["cycle_id"]
    try:
        from backing_key_cycle_handoff import ACKED_IDS_KEY, LAST_PASS_ID_KEY

        session.pop(ACKED_IDS_KEY, None)
        session[LAST_PASS_ID_KEY] = 0
    except Exception:
        pass
    session.pop("_kc_handoff_pending_acks", None)
    # Invalidate in-flight player cmds / prefetch so the next bridge push
    # carries the new cycleId + sequence (avoids stale playbar fragments).
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    session["_kc_prefetch_gen"] = int(session.get("_kc_prefetch_gen") or 0) + 1
    session["_kc_prefetch_cancel"] = True
    return data


def _mark_settings_pending_no_autoplay(session: dict[str, Any]) -> None:
    session[BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY] = True
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session.pop("_kc_seamless_handoff", None)
    session.pop("_kc_skip_audio_remount", None)
    # Sticky dual-buffer URL can keep playing the prior arrangement after BPM /
    # feel / scope edits. Stash that arrangement's follow timeline + chart so
    # highlighting does not jump to the pending widget BPM before Play.
    try:
        _tl = session.get("_last_backing_timeline")
        if not (isinstance(_tl, list) and _tl):
            _tl = session.get("_kc_audible_follow_timeline")
        if isinstance(_tl, list) and _tl:
            session["_kc_audible_follow_timeline"] = list(_tl)
        _sig = session.get("_last_backing_signature")
        if _sig is None:
            _sig = session.get("_kc_audible_signature")
        if _sig is not None:
            session["_kc_audible_signature"] = _sig
        _chart = (
            session.get("_kc_last_open_chart_html")
            or session.get("_kc_audible_chart_html")
        )
        if _chart:
            session["_kc_audible_chart_html"] = str(_chart)
        _secs = session.get("_kc_chart_selected_sections")
        if not isinstance(_secs, list):
            _secs = session.get("_kc_audible_section_names")
        if isinstance(_secs, list):
            session["_kc_audible_section_names"] = list(_secs)
        # Capture audible BPM from the arrangement signature (not the widget).
        try:
            _asig = session.get("_kc_audible_signature") or session.get(
                "_last_backing_signature"
            )
            if isinstance(_asig, tuple) and len(_asig) > 4:
                session["_kc_audible_bpm"] = int(_asig[4])
        except (TypeError, ValueError):
            pass
    except Exception:
        pass
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        invalidate_backing_cache(session)
        session[BACKING_NEEDS_REGEN] = True
    except Exception:
        session.pop("_last_backing_wav", None)
        session.pop("_last_backing_signature", None)
        session.pop("_last_backing_wav_path", None)
        session["backing_needs_regen"] = True


def stash_audible_arrangement_after_generate(
    session: dict[str, Any],
    *,
    timeline: list | None,
    signature: Any,
    chart_html: str = "",
    section_names: list | None = None,
    bpm: int | None = None,
    groove: str = "",
) -> None:
    """Record the arrangement that was just installed into the audible buffer."""
    if isinstance(timeline, list) and timeline:
        session["_kc_audible_follow_timeline"] = list(timeline)
        session["_last_backing_timeline"] = list(timeline)
    if signature is not None:
        session["_kc_audible_signature"] = signature
    if chart_html:
        session["_kc_audible_chart_html"] = str(chart_html)
        session["_kc_last_open_chart_html"] = str(chart_html)
    if section_names is not None:
        session["_kc_audible_section_names"] = [str(s) for s in section_names]
    if bpm is not None:
        try:
            session["_kc_audible_bpm"] = int(bpm)
        except (TypeError, ValueError):
            pass
    if groove:
        session["_kc_audible_groove"] = str(groove)
    meter = str(session.get("backing_time_signature") or session.get("time_signature") or "").strip()
    if meter:
        session["_kc_audible_meter"] = meter
    # Arrangement replace finished for this generate — release key lock.
    session.pop("_kc_arr_key_lock", None)


def audible_follow_timeline(session: dict[str, Any]) -> list | None:
    """Timeline matching the sticky/playing arrangement (not pending widget BPM)."""
    tl = session.get("_kc_audible_follow_timeline")
    if isinstance(tl, list) and tl:
        return list(tl)
    tl2 = session.get("_last_backing_timeline")
    if isinstance(tl2, list) and tl2:
        return list(tl2)
    return None


def normalize_key_cycle_after_browser_restore(session: dict[str, Any]) -> bool:
    """On a fresh Streamlit process/session with a restored cycle: hold at pass start.

    Preserves current key, offset, interval, direction, and On. Does not autoplay.
    Next Resume seeks to the beginning of that key's pass. Saved Practice Key
    is untouched.
    """
    if session.get("_kc_session_live"):
        return False
    session["_kc_session_live"] = True
    if not is_cycle_active(session):
        return False
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return False
    data = dict(data)
    data["status"] = STATUS_HELD
    _put_owner_cycle_session(session, owner, data)
    session["_backing_autoplay"] = False
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session.pop("_kc_seamless_handoff", None)
    session.pop("_kc_skip_audio_remount", None)
    session["_backing_transport_user_stopped"] = True
    session["_kc_hard_stop"] = True
    session["_kc_pause_audio"] = True
    # Resume after refresh starts this key's pass from the first chord.
    session["_kc_refresh_resume_from_start"] = True
    session.pop("_kc_resume_play", None)
    session.pop("_kc_restart_play", None)
    try:
        session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    except Exception:
        pass
    return True


def reanchor_key_cycle_from_practice_key(
    session: dict[str, Any],
    *,
    new_key: str = "",
) -> dict[str, Any] | None:
    """Rebuild the cycle from the saved Practice Key while keeping On + settings.

    Resets position to the new first key. Does not autoplay — next Play starts there.
    Automatic cycling never writes Practice Key; only this user PK change reanchors.
    """
    if not is_cycle_active(session):
        return None
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return None
    base = str(new_key or current_backing_owner_practice_key(session) or "").strip()
    if not base:
        return None
    old = dict(data)
    old_base = str(old.get("base_practice_key") or "").strip()
    old_start = str(old.get("start_cycle_key") or "").strip()
    old_cur = str(old.get("current_playback_key") or "").strip()
    already = (
        _keys_equivalent(old_base, base)
        and _keys_equivalent(old_start, base)
        and _keys_equivalent(old_cur, base)
        and int(old.get("offset_semitones") or 0) == 0
    )
    if already:
        return old

    mag = int(old.get("interval") or 1)
    if mag not in {1, 2}:
        mag = 1
    direc = "down" if str(old.get("direction") or "up").lower() == "down" else "up"
    prefs = (
        dict(old["spelling_prefs"])
        if isinstance(old.get("spelling_prefs"), dict)
        else spelling_prefs_from_session(session)
    )
    _bt, base_mode = split_key_center(base)
    st_tonic, st_mode = split_key_center(base)
    start = base
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
    data = _bump_cycle_identity(session, data)
    _put_owner_cycle_session(session, owner, data)
    session["backing_key_cycle_enabled"] = True
    # Keep the live static URL so the bridge can push the new cycleId/sequence
    # while settings are pending Play (avoids orphaned playbar chips).
    clear_key_cycle_prepared_audio(session, clear_current_url=False)
    _mark_settings_pending_no_autoplay(session)
    session.pop("_kc_last_playing_confirm", None)
    session["_kc_cycle_settings_applied"] = (
        int(data.get("interval") or 1),
        str(data.get("direction") or "up"),
        str(data.get("cycle_id") or ""),
    )
    session["backing_key_cycle_step_ui"] = (
        "whole" if int(data.get("interval") or 1) == 2 else "semitone"
    )
    session["backing_key_cycle_direction_ui"] = str(data.get("direction") or "up")
    try:
        import json
        import os
        import time
        from pathlib import Path

        data_dir = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / "_kc_reanchor.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "old": old_cur,
                        "new": start,
                        "base": base,
                        "cycle_id": data.get("cycle_id"),
                        "seq0": (cycle_key_sequence(session) or [""])[0],
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    _log_cycle_key_write(
        session,
        trigger="reanchor_practice_key",
        old_key=old_cur,
        new_key=start,
        cycle_id=str(data.get("cycle_id") or ""),
        pass_id=0,
        extra={"old_base": old_base, "new_base": base},
    )
    return data


def reset_key_cycle_position_for_settings(
    session: dict[str, Any],
    *,
    interval: int | None = None,
    direction: str | None = None,
    spelling_prefs: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Interval / direction / spelling changed: reset to first key = saved Practice Key.

    Keeps cycling enabled. Does not autoplay.
    """
    if not is_cycle_active(session):
        return None
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if not data or not data.get("enabled"):
        return None
    data = dict(data)
    base = str(
        current_backing_owner_practice_key(session)
        or data.get("base_practice_key")
        or "C"
    ).strip() or "C"
    old_cur = str(data.get("current_playback_key") or "").strip()
    if interval is not None:
        data["interval"] = 2 if int(interval) >= 2 else 1
    if direction is not None:
        data["direction"] = "down" if str(direction).lower() == "down" else "up"
    if spelling_prefs is not None:
        data["spelling_prefs"] = dict(spelling_prefs)
    data["base_practice_key"] = base
    data["start_cycle_key"] = base
    data["current_playback_key"] = base
    data["offset_semitones"] = 0
    data["status"] = STATUS_RUNNING
    data["enabled"] = True
    data = _bump_cycle_identity(session, data)
    _put_owner_cycle_session(session, owner, data)
    clear_key_cycle_prepared_audio(session, clear_current_url=False)
    _mark_settings_pending_no_autoplay(session)
    session.pop("_kc_last_playing_confirm", None)
    session["_kc_cycle_settings_applied"] = (
        int(data.get("interval") or 1),
        str(data.get("direction") or "up"),
        str(data.get("cycle_id") or ""),
    )
    session["backing_key_cycle_step_ui"] = (
        "whole" if int(data.get("interval") or 1) == 2 else "semitone"
    )
    session["backing_key_cycle_direction_ui"] = str(data.get("direction") or "up")
    _log_cycle_key_write(
        session,
        trigger="reset_for_cycle_settings",
        old_key=old_cur,
        new_key=base,
        cycle_id=str(data.get("cycle_id") or ""),
        pass_id=0,
        extra={
            "interval": data.get("interval"),
            "direction": data.get("direction"),
        },
    )
    return data


def adopt_explicit_arrangement_url(session: dict[str, Any], url: str) -> str:
    """Install a Play-generated static URL and require the sounding buffer to load it.

    Generate writes ``_kc_current_static_url`` before the playbar compares URLs.
    That comparison then sees no change, ``arrangementReload`` stays false, and
    the handoff guard rejects the new file. A sticky arrangement URL keeps the
    replacement distinct from an automatic key handoff until the buffer matches.
    """
    url = str(url or "").strip()
    if not url:
        return ""
    session["_kc_current_static_url"] = url
    session["_kc_arrangement_url"] = url
    session["_kc_arrangement_reload"] = True
    # Durable until forcePlay publishes — survives an early oneshot pop.
    session["_kc_force_arrangement_replace"] = True
    session.pop("_kc_skip_audio_remount", None)
    # Always bump epoch on explicit Play adopt — even when the static URL hash
    # matches a prior visit. Same-URL + same epoch left the bridge iframe
    # un-remounted and __kcCmdPollSeen skipped the duplicate payload while the
    # active buffer still held the previous BPM/feel WAV.
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    return url


def arrangement_fingerprint_from_signature(sig: Any) -> tuple:
    """Stable arrangement identity for cycle settings (not sounding-key advances).

    Excludes:
    - index 1 sounding key (cycle advances must not look like settings changes)
    - musical-profile mood/intensity tuple (can flip Medium↔Ballad across reruns
      without a user Tempo/Feel/scope edit — that was perpetually invalidating
      WAV and hanging Play waits)
    - trailing event/chord counts and short-pass markers
    """
    if not isinstance(sig, tuple) or len(sig) < 3:
        return ()
    parts: list[Any] = [sig[0]]
    for i in (2, 3, 4, 5, 6, 7, 8, 9):
        if len(sig) > i:
            parts.append(sig[i])
    return tuple(parts)


def sync_key_cycle_after_practice_key_commit(
    session: dict[str, Any],
    *,
    new_key: str = "",
) -> dict[str, Any] | None:
    """Hook for Practice Key widget commits while cycling is On."""
    return reanchor_key_cycle_from_practice_key(session, new_key=new_key)


def consume_key_cycle_settings_pending(session: dict[str, Any]) -> bool:
    """Clear the pending-settings flag (caller must prove arrangement is applied)."""
    if session.pop(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY, None):
        return True
    return False


def key_cycle_settings_pending(session: dict[str, Any]) -> bool:
    return bool(session.get(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY))


def _normalize_feel_for_pending(feel: str) -> str:
    raw = str(feel or "").strip()
    if not raw:
        return ""
    try:
        from songs.playback_defaults import normalize_groove_label

        return str(normalize_groove_label(raw) or raw).strip().lower()
    except Exception:
        return raw.lower()


def applied_arrangement_ready(session: dict[str, Any]) -> bool:
    """True when an arrangement is actually installed (disk/URL/WAV), not just clicked."""
    if str(session.get("_kc_current_static_url") or "").strip():
        return True
    path = str(session.get("_last_backing_wav_path") or "").strip()
    if path:
        try:
            from pathlib import Path

            if Path(path).is_file() and Path(path).stat().st_size > 64:
                return True
        except Exception:
            pass
    wav = session.get("_last_backing_wav")
    if isinstance(wav, (bytes, bytearray)) and len(wav) > 64:
        return True
    return False


def _selected_arrangement_triplet(
    session: dict[str, Any],
    *,
    bpm: int | None = None,
    groove: str = "",
    meter: str = "",
) -> tuple[int, str, str]:
    """Committed arrangement selection for Pending match.

    Prefer canonical Tempo/Feel over the live selectbox. After a Feel commit the
    widget often remounts on the prior groove while canonical already holds the
    new one; treating the lagging widget as "selection" cleared Pending and made
    Play regenerate the old Feel (Pop→Blues audible stuck on Blues).
    """
    canon: dict[str, Any] = {}
    normalize_backing_bpm = None
    normalize_backing_groove = None
    try:
        from backing_track_state import (
            canonical_backing_filters,
            normalize_backing_bpm as _nbpm,
            normalize_backing_groove as _ngroove,
        )

        normalize_backing_bpm = _nbpm
        normalize_backing_groove = _ngroove
        raw = canonical_backing_filters(session)
        if isinstance(raw, dict):
            canon = raw
    except Exception:
        canon = {}
    try:
        selected_bpm = int(bpm if bpm is not None else 0)
    except (TypeError, ValueError):
        selected_bpm = 0
    if selected_bpm <= 0 and canon:
        try:
            if normalize_backing_bpm is not None:
                selected_bpm = int(
                    normalize_backing_bpm(canon.get("backing_track_bpm")) or 0
                )
            else:
                selected_bpm = int(canon.get("backing_track_bpm") or 0)
        except (TypeError, ValueError):
            selected_bpm = 0
    if selected_bpm <= 0:
        try:
            selected_bpm = int(session.get("backing_track_bpm") or session.get("bpm") or 0)
        except (TypeError, ValueError):
            selected_bpm = 0
    selected_groove = str(groove or "").strip()
    canon_groove = ""
    if canon:
        try:
            if normalize_backing_groove is not None:
                canon_groove = str(
                    normalize_backing_groove(canon.get("backing_groove_style")) or ""
                ).strip()
            else:
                canon_groove = str(canon.get("backing_groove_style") or "").strip()
        except Exception:
            canon_groove = str(canon.get("backing_groove_style") or "").strip()
    if not selected_groove:
        selected_groove = canon_groove or str(
            session.get("backing_groove_style") or ""
        ).strip()
    elif canon_groove and _normalize_feel_for_pending(
        selected_groove
    ) != _normalize_feel_for_pending(canon_groove):
        # Explicit/widget Feel disagrees with committed canonical — trust canon.
        selected_groove = canon_groove
    selected_meter = str(
        meter
        or (canon.get("backing_time_signature") if canon else "")
        or session.get("backing_time_signature")
        or session.get("time_signature")
        or ""
    ).strip()
    return selected_bpm, selected_groove, selected_meter


def _applied_arrangement_triplet(session: dict[str, Any]) -> tuple[int, str, str]:
    try:
        applied_bpm = int(session.get("_kc_audible_bpm") or 0)
    except (TypeError, ValueError):
        applied_bpm = 0
    applied_groove = str(session.get("_kc_audible_groove") or "").strip()
    applied_meter = str(session.get("_kc_audible_meter") or "").strip()
    sig = session.get("_kc_audible_signature") or session.get("_last_backing_signature")
    if isinstance(sig, (tuple, list)) and len(sig) > 4:
        if applied_bpm <= 0:
            try:
                applied_bpm = int(sig[4] or 0)
            except (TypeError, ValueError):
                applied_bpm = 0
        if not applied_groove:
            applied_groove = str(sig[3] or "").strip()
        if not applied_meter and len(sig) > 5:
            applied_meter = str(sig[5] or "").strip()
    return applied_bpm, applied_groove, applied_meter


def _selected_arrangement_scope(session: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    """Committed loops + selected section names for arrangement match."""
    loops = 0
    sections: tuple[str, ...] = ()
    try:
        from backing_track_state import (
            canonical_backing_filters,
            normalize_backing_loops,
            normalize_backing_scope,
        )

        canon = canonical_backing_filters(session) or {}
        if isinstance(canon, dict):
            try:
                loops = int(normalize_backing_loops(canon.get("backing_track_loops")) or 0)
            except (TypeError, ValueError):
                loops = 0
            scope = normalize_backing_scope(canon.get("backing_track_scope"))
            if scope == "Selected sections":
                multi = canon.get("backing_track_multi_sections") or []
                if isinstance(multi, (list, tuple)):
                    sections = tuple(str(x).strip() for x in multi if str(x).strip())
                single = str(canon.get("backing_track_single_section") or "").strip()
                if not sections and single:
                    sections = (single,)
    except Exception:
        pass
    if loops <= 0:
        try:
            loops = int(session.get("backing_track_loops") or 0)
        except (TypeError, ValueError):
            loops = 0
    if not sections:
        multi = session.get("backing_track_multi_sections") or []
        if isinstance(multi, (list, tuple)):
            sections = tuple(str(x).strip() for x in multi if str(x).strip())
    return loops, sections


def _applied_arrangement_scope(session: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    """Loops + sections from the audible / last-applied backing signature."""
    loops = 0
    sections: tuple[str, ...] = ()
    sig = session.get("_kc_audible_signature") or session.get("_last_backing_signature")
    if isinstance(sig, (tuple, list)):
        if len(sig) > 6:
            try:
                loops = int(sig[6] or 0)
            except (TypeError, ValueError):
                loops = 0
        if len(sig) > 7:
            raw = sig[7]
            if isinstance(raw, (list, tuple)):
                sections = tuple(str(x).strip() for x in raw if str(x).strip())
            elif str(raw or "").strip():
                sections = (str(raw).strip(),)
    return loops, sections


def arrangement_content_matches_selection(
    session: dict[str, Any],
    *,
    bpm: int | None = None,
    groove: str = "",
    meter: str = "",
) -> bool:
    """True when audible Tempo/Feel/meter/loops/scope match the selection.

    Ignores URL readiness. Scope (sections) and loops are included so a
    Verse→Verse+Chorus (or loops) edit is not mistaken for remount noise.
    """
    selected_bpm, selected_groove, selected_meter = _selected_arrangement_triplet(
        session, bpm=bpm, groove=groove, meter=meter
    )
    applied_bpm, applied_groove, applied_meter = _applied_arrangement_triplet(session)
    if selected_bpm <= 0 or applied_bpm <= 0 or int(selected_bpm) != int(applied_bpm):
        return False
    if selected_groove and applied_groove:
        if _normalize_feel_for_pending(selected_groove) != _normalize_feel_for_pending(
            applied_groove
        ):
            return False
    if selected_meter and applied_meter and selected_meter != applied_meter:
        return False
    selected_loops, selected_sections = _selected_arrangement_scope(session)
    applied_loops, applied_sections = _applied_arrangement_scope(session)
    _ = selected_loops, applied_loops  # loops compared via fingerprint / user_edit path
    # Scope: only enforce when the selection side has an explicit section list
    # (Full-song / empty fixtures must not block Pending-clear). Real scope edits
    # set `_kc_user_arrangement_edit` and bypass remount early-returns.
    if selected_sections and selected_sections != applied_sections:
        return False
    # Require audible meta (or last signature) so a bare Play click cannot "match".
    if not (
        session.get("_kc_audible_bpm")
        or session.get("_kc_audible_signature")
        or session.get("_last_backing_signature")
    ):
        return False
    return True


def applied_arrangement_matches_selection(
    session: dict[str, Any],
    *,
    bpm: int | None = None,
    groove: str = "",
    meter: str = "",
) -> bool:
    """True when the audible/last-applied arrangement matches selected widgets."""
    if not arrangement_content_matches_selection(
        session, bpm=bpm, groove=groove, meter=meter
    ):
        return False
    # Prefer disk/URL readiness. If content matches after a just-completed
    # generate, audible meta alone is enough — static URL can lag one remount
    # behind spill, and that lag was re-forcing Pending on the caption.
    if applied_arrangement_ready(session):
        return True
    return bool(
        session.get("_kc_audible_bpm") and session.get("_kc_audible_signature")
    )


def clear_settings_pending_if_arrangement_applied(
    session: dict[str, Any],
    *,
    bpm: int | None = None,
    groove: str = "",
    meter: str = "",
    signature: Any = None,
) -> bool:
    """Clear Pending only when the installed arrangement matches the selection.

    A bare Play click, a failed load, or a newer Tempo/Feel/scope edit must keep
    Pending. When cleared, also seal ``_kc_applied_arrangement_fp`` so remount
    flushes cannot re-arm Pending for the same arrangement.
    """
    if not key_cycle_settings_pending(session):
        # Still seal applied fp when caller proves a match after generate.
        if signature is not None and applied_arrangement_matches_selection(
            session, bpm=bpm, groove=groove, meter=meter
        ):
            session["_kc_applied_arrangement_fp"] = arrangement_fingerprint_from_signature(
                signature
            )
        return False
    if not applied_arrangement_matches_selection(
        session, bpm=bpm, groove=groove, meter=meter
    ):
        return False
    consume_key_cycle_settings_pending(session)
    if signature is not None:
        session["_kc_applied_arrangement_fp"] = arrangement_fingerprint_from_signature(
            signature
        )
    else:
        sig = session.get("_kc_audible_signature") or session.get("_last_backing_signature")
        if sig is not None:
            session["_kc_applied_arrangement_fp"] = arrangement_fingerprint_from_signature(
                sig
            )
    session["_kc_settings_applied_this_play"] = True
    return True


def note_key_cycle_arrangement_settings_changed(session: dict[str, Any]) -> None:
    """BPM / loops / feel / scope changed: apply to the CURRENT cycle key.

    Preserves cycle key and sequence position. Rebuilds the arrangement for the
    current key (restart pass from first chord). Continues automatically when
    playback was running; stays stopped until Resume when it was paused.
    Rapid edits bump a generation token so older generates cannot overwrite.
    """
    # Post-Play remount: arrangement fingerprint / widget flush can re-enter here
    # for the arrangement that was just generated. Do not re-arm Pending or wipe
    # the prepared Blues+140 chart on that same apply.
    if session.pop("_kc_settings_applied_this_play", None):
        return
    # Explicit filter on_change (BPM/Feel/scope/loops): never treat as remount
    # noise. Scope-only edits used to early-return when Tempo/Feel still matched.
    user_edit = bool(session.pop("_kc_user_arrangement_edit", False))
    if not user_edit:
        # Widgets still match the sealed applied arrangement — ignore remount noise.
        try:
            sealed = session.get("_kc_applied_arrangement_fp")
            if sealed and arrangement_content_matches_selection(session):
                return
        except Exception:
            pass
        # Sealed arrangement still matches the last installed signature.
        try:
            sealed = session.get("_kc_applied_arrangement_fp")
            last = session.get("_last_backing_signature") or session.get(
                "_kc_audible_signature"
            )
            if (
                sealed is not None
                and last is not None
                and arrangement_fingerprint_from_signature(last) == sealed
            ):
                return
        except Exception:
            pass

    # Already preparing the newest generation — further same-run flushes must not
    # thrash invalidate.
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        pending_gen = int(session.get("_kc_arr_apply_gen") or 0)
        if (
            pending_gen
            and bool(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY))
            and bool(session.get(BACKING_NEEDS_REGEN))
        ):
            # Still bump gen so a slower prior generate is discarded on finish.
            session["_kc_arr_apply_gen"] = pending_gen + 1
            return
    except Exception:
        pass
    sticky = bool(str(session.get("_kc_current_static_url") or "").strip())
    if is_cycle_active(session) or sticky:
        # Keep prior audible caption/timeline until the new arrangement lands
        # (preparing state). Match the pending-path stash so BPM/Feel/scope
        # widgets do not jump the status panel before audio replaces.
        try:
            _tl = session.get("_last_backing_timeline")
            if not (isinstance(_tl, list) and _tl):
                _tl = session.get("_kc_audible_follow_timeline")
            if isinstance(_tl, list) and _tl:
                session["_kc_audible_follow_timeline"] = list(_tl)
            _sig = session.get("_last_backing_signature")
            if _sig is None:
                _sig = session.get("_kc_audible_signature")
            if _sig is not None:
                session["_kc_audible_signature"] = _sig
            try:
                _asig = session.get("_kc_audible_signature")
                if isinstance(_asig, tuple) and len(_asig) > 4:
                    session["_kc_audible_bpm"] = int(_asig[4])
                if isinstance(_asig, tuple) and len(_asig) > 3:
                    g = str(_asig[3] or "").strip()
                    if g:
                        session["_kc_audible_groove"] = g
            except (TypeError, ValueError):
                pass
        except Exception:
            pass
        clear_key_cycle_prepared_audio(session, clear_current_url=False)
        # Auto-apply: do not wait for Play (PK/direction/interval still use
        # settings_pending via reanchor / reset_key_cycle_position_for_settings).
        session.pop(BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY, None)
        try:
            from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

            invalidate_backing_cache(session)
            session[BACKING_NEEDS_REGEN] = True
        except Exception:
            session.pop("_last_backing_wav", None)
            session.pop("_last_backing_signature", None)
            session.pop("_last_backing_wav_path", None)
            session["backing_needs_regen"] = True
        session.pop("_kc_applied_arrangement_fp", None)
        gen = int(session.get("_kc_arr_apply_gen") or 0) + 1
        session["_kc_arr_apply_gen"] = gen
        data = get_owner_cycle_session(session) or {}
        was_playing = (
            str(data.get("status") or "") == STATUS_RUNNING
            and not bool(session.get("_backing_transport_user_stopped"))
            and not bool(session.get("_kc_pause_audio"))
            and not bool(session.get("_kc_hard_stop"))
        )
        session["_kc_arr_was_playing"] = was_playing
        session["_kc_arr_hold_after"] = not was_playing
        # Lock the current cycle key until the new arrangement is installed so a
        # natural pass-end during prepare cannot walk Bm→Am mid-replace.
        session["_kc_arr_key_lock"] = str(data.get("current_playback_key") or "")
        # Rebuild current key from first chord; keep lead sheet open.
        session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
        session["_kc_restart_play"] = True
        session.pop("_kc_hard_stop", None)
        session.pop("_kc_pause_audio", None)
        if was_playing:
            data2 = dict(data) if data else {}
            if data2.get("enabled"):
                data2["status"] = STATUS_RUNNING
                _put_owner_cycle_session(session, resolve_cycle_owner(session), data2)
            session.pop("_backing_transport_user_stopped", None)
            session["_backing_autoplay"] = True
            session["_kc_resume_play"] = True
            session.pop("_kc_pause_audio", None)
            session.pop("_kc_hard_stop", None)
        else:
            # Temporarily RUNNING so continue-play/generate runs; hold after install.
            data2 = dict(data) if data else {}
            if data2.get("enabled"):
                data2["status"] = STATUS_RUNNING
                _put_owner_cycle_session(session, resolve_cycle_owner(session), data2)
            session.pop("_backing_transport_user_stopped", None)
            session.pop("_kc_hard_stop", None)
            session.pop("_kc_pause_audio", None)
            session["_backing_autoplay"] = False
            session["_kc_arr_hold_after"] = True
            session["_kc_restart_play"] = True
        session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
        try:
            session["_backing_play_feedback"] = (
                "Preparing arrangement…"
                if was_playing
                else "Preparing arrangement… (will stay stopped until Resume)"
            )
        except Exception:
            pass
        try:
            _log_cycle_key_write(
                session,
                trigger="arrangement_settings_auto_apply",
                old_key=str(data.get("current_playback_key") or ""),
                new_key=str(data.get("current_playback_key") or ""),
                cycle_id=str(data.get("cycle_id") or ""),
                pass_id=data.get("pass_id"),
                extra={
                    "preserved_offset": data.get("offset_semitones"),
                    "was_playing": was_playing,
                    "gen": gen,
                },
            )
        except Exception:
            pass
        return
    # Cycling Off: invalidate so Play regenerates; no dual-buffer sticky hold.
    try:
        from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

        invalidate_backing_cache(session)
        session[BACKING_NEEDS_REGEN] = True
    except Exception:
        session.pop("_last_backing_wav", None)
        session.pop("_last_backing_signature", None)
        session["backing_needs_regen"] = True
    session.pop("_kc_applied_arrangement_fp", None)


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
        # Same length is not same content: Pop↔Blues at one BPM often share
        # wav_bytes length, and skipping the copy left currentSrc on stale Pop.
        need_copy = True
        if dest.is_file() and dest.stat().st_size == src.stat().st_size:
            def _md5(path: Path) -> bytes:
                h = hashlib.md5()
                with path.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                return h.digest()

            need_copy = _md5(dest) != _md5(src)
        if need_copy:
            shutil.copy2(src, dest)
    except OSError:
        return ""
    return f"/app/static/kc/{digest}.wav"


def _prepared_chart_bpm_groove(
    session: dict[str, Any],
    *,
    signature: Any = None,
    bpm: int | None = None,
    groove_style: str = "",
) -> tuple[int, str]:
    """Resolve Tempo/Feel for prepared lead sheets.

    Explicit args win, then the arrangement signature, then session chart /
    audible / live widgets. Never treat the old ``bpm=100`` /
    ``groove_style="Pop groove"`` call defaults as intentional — those values
    blocked session fallbacks and resealed Live Follow-Along captions to
    100/Pop after Play while audio was Blues+140.
    """
    resolved_bpm = 0
    try:
        if bpm is not None and int(bpm) > 0:
            resolved_bpm = int(bpm)
    except (TypeError, ValueError):
        resolved_bpm = 0
    if resolved_bpm <= 0 and isinstance(signature, (tuple, list)) and len(signature) > 4:
        try:
            resolved_bpm = int(signature[4] or 0)
        except (TypeError, ValueError):
            resolved_bpm = 0
    if resolved_bpm <= 0:
        for key in (
            "_kc_chart_bpm",
            "_kc_audible_bpm",
            "backing_track_bpm",
            "bpm",
        ):
            try:
                cand = int(session.get(key) or 0)
            except (TypeError, ValueError):
                cand = 0
            if cand > 0:
                resolved_bpm = cand
                break
    if resolved_bpm <= 0:
        resolved_bpm = 100

    resolved_groove = str(groove_style or "").strip()
    if not resolved_groove and isinstance(signature, (tuple, list)) and len(signature) > 3:
        resolved_groove = str(signature[3] or "").strip()
    if not resolved_groove:
        for key in (
            "_kc_chart_groove",
            "_kc_audible_groove",
            "backing_groove_style",
        ):
            cand = str(session.get(key) or "").strip()
            if cand and cand.lower() not in {"auto", "none"}:
                resolved_groove = cand
                break
    if not resolved_groove:
        resolved_groove = "Pop groove"
    return resolved_bpm, resolved_groove


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
    song_name: str = "",
    song_data: dict[str, Any] | None = None,
    selected_section_names: list[str] | tuple[str, ...] | None = None,
    level: str = "Intermediate",
    groove_style: str = "",
    bpm: int | None = None,
    time_signature: str = "4/4",
    timeline: list | None = None,
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
    chart_bpm, chart_groove = _prepared_chart_bpm_groove(
        session,
        signature=signature,
        bpm=bpm,
        groove_style=groove_style,
    )
    # Keep session chart meta aligned so later ensure/rebuild paths stay coherent.
    session["_kc_chart_bpm"] = int(chart_bpm)
    session["_kc_chart_groove"] = str(chart_groove)
    html = str(chart_html or "").strip()
    if not html:
        try:
            from backing_key_cycle_handoff import build_cycle_lead_sheet_html

            html = build_cycle_lead_sheet_html(
                sounding_key=key,
                chords=list(chords or ()),
                sections=sections if isinstance(sections, dict) else None,
                song_name=song_name or str(session.get("_kc_chart_song_name") or ""),
                song_data=song_data
                if isinstance(song_data, dict)
                else session.get("_kc_chart_song_data"),
                selected_section_names=selected_section_names
                or session.get("_kc_chart_selected_sections"),
                level=level or str(session.get("_kc_chart_level") or "Intermediate"),
                groove_style=chart_groove,
                bpm=int(chart_bpm),
                time_signature=time_signature
                or str(session.get("_kc_chart_meter") or "4/4"),
                session=session,
                chart_display_key=project_cycle_display_key(session, key),
            )
        except Exception:
            html = ""
    if not html:
        prev = bag.get(key) if isinstance(bag, dict) else None
        if isinstance(prev, dict):
            html = str(prev.get("chart_html") or "").strip()
    # Persist arrangement identity so loops/bpm changes cannot keep a stale URL.
    loops_in_sig = None
    try:
        if isinstance(signature, tuple) and len(signature) >= 7:
            loops_in_sig = int(signature[6])
    except Exception:
        loops_in_sig = None
    # Timeline must match THIS sounding key. Never copy the audible key's
    # `_last_backing_timeline` onto a neighbor — that left Bm chords under Am.
    follow_tl: list = []
    if isinstance(timeline, list) and timeline:
        follow_tl = list(timeline)
    else:
        last_sig = session.get("_last_backing_signature") or session.get(
            "_kc_audible_signature"
        )
        last_key = ""
        try:
            if isinstance(last_sig, (tuple, list)) and len(last_sig) > 1:
                last_key = str(last_sig[1] or "").strip()
        except Exception:
            last_key = ""
        if last_key and _keys_equivalent(last_key, key):
            raw = session.get("_last_backing_timeline")
            if isinstance(raw, list) and raw:
                follow_tl = list(raw)
        if not follow_tl:
            prev_e = bag.get(key) if isinstance(bag, dict) else None
            if isinstance(prev_e, dict):
                prev_tl = prev_e.get("timeline")
                if isinstance(prev_tl, list) and prev_tl:
                    follow_tl = list(prev_tl)
    bag[key] = {
        "signature": signature,
        "path": path,
        "static_url": url,
        "chart_html": html,
        "loops": loops_in_sig,
        # Transposed follow timeline for this sounding key — required so
        # Current/Next Chord update on seamless handoff (not the prior key).
        "timeline": follow_tl,
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
    _prune_cycle_static_files(session)


def _prune_cycle_static_files(session: dict[str, Any]) -> None:
    """Drop published WAVs that are not this arrangement's prepared set.

    The in-memory bag is already bounded. Leftover ``static/kc`` files are not,
    and once that folder exceeds Streamlit's static cap every neighbor fetch
    stalls in HAVE_NOTHING.
    """
    keep: set[str] = set()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if isinstance(bag, dict):
        for entry in bag.values():
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("static_url") or "")
            name = url.rsplit("/", 1)[-1]
            if name.endswith(".wav"):
                keep.add(name)
    for raw in (
        session.get("_kc_current_static_url"),
        session.get("_kc_playing_static_url"),
    ):
        name = str(raw or "").rsplit("/", 1)[-1]
        if name.endswith(".wav"):
            keep.add(name)
    try:
        import hashlib

        sig = session.get("_last_backing_signature")
        if sig is not None:
            digest = hashlib.sha1(
                repr(sig).encode("utf-8", errors="replace")
            ).hexdigest()[:20]
            keep.add(f"{digest}.wav")
    except Exception:
        pass
    if not keep:
        return
    try:
        folder = _kc_static_dir()
    except Exception:
        return
    for path in folder.glob("*.wav"):
        if path.name in keep:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def prepared_cycle_chart_html(session: dict[str, Any], sounding_key: str) -> str:
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return ""
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("chart_html") or "").strip()


def prepared_cycle_follow_timeline(
    session: dict[str, Any], sounding_key: str
) -> list:
    """Return the transposed follow timeline stored with prepared audio for a key."""
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return []
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return []
    tl = entry.get("timeline")
    return list(tl) if isinstance(tl, list) else []


def ensure_prepared_cycle_chart(session: dict[str, Any], sounding_key: str) -> str:
    """Build the neighbor lead sheet if audio was stored without one.

    Publication of a WAV is not enough: the chart has to be ready before the
    audible handoff, or the open sheet lags the buffer.
    """
    key = str(sounding_key or "").strip()
    html = prepared_cycle_chart_html(session, key)
    if html or not key:
        return html
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    entry = bag.get(key) if isinstance(bag, dict) else None
    if not isinstance(entry, dict):
        return ""
    store_prepared_cycle_audio(
        session,
        sounding_key=key,
        signature=entry.get("signature"),
        wav_path=str(entry.get("path") or ""),
        static_url=str(entry.get("static_url") or ""),
    )
    return prepared_cycle_chart_html(session, key)


def prepared_cycle_audio_matches_loops(
    session: dict[str, Any], sounding_key: str, loops: int
) -> bool:
    """True when the prepared bag entry for ``sounding_key`` matches ``loops``."""
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return False
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return False
    want = int(loops or 0)
    try:
        have = entry.get("loops")
        if have is not None and int(have) == want:
            return True
    except Exception:
        pass
    sig = entry.get("signature")
    try:
        if isinstance(sig, tuple) and len(sig) >= 7 and int(sig[6]) == want:
            return True
    except Exception:
        pass
    return False


def prepared_cycle_static_url(
    session: dict[str, Any],
    sounding_key: str,
    *,
    require_loops: int | None = None,
) -> str:
    key = str(sounding_key or "").strip()
    bag = session.get(BACKING_KEY_CYCLE_PREPARED_KEY)
    if not key or not isinstance(bag, dict):
        return ""
    entry = bag.get(key)
    if not isinstance(entry, dict):
        return ""
    if require_loops is not None and not prepared_cycle_audio_matches_loops(
        session, key, int(require_loops)
    ):
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
        arranged = str(session.get("_kc_arrangement_url") or "").strip()
        force_arr = bool(session.get("_kc_force_arrangement_replace"))
        # Explicit Play (BPM/feel/scope) owns currentUrl until forcePlay publishes.
        # Neighbor promote must not steal current or drop the replace markers —
        # that left generate_saved at the new BPM while the buffer kept the old
        # WAV (or cleared src) because needsReplace never saw forceArr+cur.
        if force_arr and arranged and url != arranged:
            return True
        session["_kc_current_static_url"] = url
        # Key handoff is not another explicit Play. Drop the arrangement marker
        # and bump epoch so a late command cannot reload the previous file.
        if arranged and arranged != url and not force_arr:
            session.pop("_kc_arrangement_url", None)
            session.pop("_kc_arrangement_reload", None)
            session.pop("_kc_force_arrangement_replace", None)
            session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
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
    prev = bag.get(owner) if isinstance(bag.get(owner), dict) else {}
    bag[owner] = dict(data)
    session[BACKING_KEY_CYCLE_SESSIONS_KEY] = bag
    session[BACKING_KEY_CYCLE_UI_OWNER_KEY] = owner
    # Durable position so a normal browser refresh (new Streamlit session) restores
    # the confirmed sounding key/offset — not only an in-memory session.
    try:
        _prev_key = str((prev or {}).get("current_playback_key") or "")
        _new_key = str(data.get("current_playback_key") or "")
        _prev_off = int((prev or {}).get("offset_semitones") or 0)
        _new_off = int(data.get("offset_semitones") or 0)
        _prev_en = bool((prev or {}).get("enabled"))
        _new_en = bool(data.get("enabled"))
        if (
            _prev_key != _new_key
            or _prev_off != _new_off
            or _prev_en != _new_en
            or str((prev or {}).get("status") or "") != str(data.get("status") or "")
        ):
            persist_key_cycle_position(session)
    except Exception:
        pass


_CYCLE_DISK_SESSION_KEYS: tuple[str, ...] = (
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


def persist_key_cycle_position(session: dict[str, Any]) -> bool:
    """Merge cycle On/position/settings into local workspace JSON (Practice Key untouched).

    Used so a hard browser refresh / new Streamlit session restores the confirmed
    temporary sounding key and offset. Does not rewrite practice_key_by_source.
    """
    try:
        import copy
        import json
        import time
        from pathlib import Path

        # Resolve path dynamically so MUSIC_APP_DATA_DIR set at process start wins
        # even if suite_workspace.DATA_DIR was imported early in tests.
        try:
            from suite_workspace import _resolve_data_dir, resolve_workspace_id

            path = (
                _resolve_data_dir()
                / "workspaces"
                / resolve_workspace_id()
                / "music_user_state.json"
            )
        except Exception:
            from suite_user_persistence import state_file_path

            path = state_file_path("music")
    except Exception:
        return False
    try:
        raw: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    raw = loaded
            except (OSError, json.JSONDecodeError):
                raw = {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        if not isinstance(state, dict):
            state = {}
        sess = state.get("session") if isinstance(state.get("session"), dict) else {}
        if not isinstance(sess, dict):
            sess = {}
        for key in _CYCLE_DISK_SESSION_KEYS:
            if key in session:
                if key == BACKING_KEY_CYCLE_SESSIONS_KEY:
                    # Reject stale behind-writes for the same cycle_id (e.g. a
                    # deferred full save that still holds the pre-handoff key).
                    incoming = session[key]
                    disk_bag = sess.get(key) if isinstance(sess.get(key), dict) else {}
                    merged_bag = copy.deepcopy(disk_bag) if isinstance(disk_bag, dict) else {}
                    if isinstance(incoming, dict):
                        for owner, neu in incoming.items():
                            if not isinstance(neu, dict):
                                continue
                            old = merged_bag.get(owner) if isinstance(merged_bag.get(owner), dict) else {}
                            if (
                                old
                                and str(old.get("cycle_id") or "")
                                and str(old.get("cycle_id") or "") == str(neu.get("cycle_id") or "")
                                and bool(old.get("enabled"))
                                and bool(neu.get("enabled"))
                            ):
                                try:
                                    old_pass = int(old.get("pass_id") or 0)
                                    new_pass = int(neu.get("pass_id") or 0)
                                    old_off = abs(int(old.get("offset_semitones") or 0))
                                    new_off = abs(int(neu.get("offset_semitones") or 0))
                                except (TypeError, ValueError):
                                    old_pass = new_pass = old_off = new_off = 0
                                if old_pass > new_pass or (
                                    old_pass == new_pass and old_off > new_off
                                ):
                                    # Keep the more advanced disk position.
                                    continue
                            merged_bag[owner] = copy.deepcopy(neu)
                    sess[key] = merged_bag
                else:
                    sess[key] = copy.deepcopy(session[key])
        # Never stamp Practice Key from the temporary cycle key.
        state["session"] = sess
        # Preserve non-session envelope fields (active_song_state, etc.).
        if isinstance(raw.get("state"), dict):
            for k, v in raw["state"].items():
                if k == "session":
                    continue
                if k not in state:
                    state[k] = v
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": int(raw.get("version") or 1),
            "app": str(raw.get("app") or "music"),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "state": state,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        session["_kc_position_persisted_at"] = time.time()
        session["_kc_position_persisted_key"] = str(
            (get_owner_cycle_session(session) or {}).get("current_playback_key") or ""
        )
        return True
    except Exception:
        return False


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
    # Drop queued handoff acks from a prior cycle (soft Off → On).
    session.pop("_kc_handoff_pending_acks", None)
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
    session.pop("_kc_resume_play", None)
    session.pop("_kc_restart_play", None)
    session["_kc_pause_audio"] = True
    # Pause must not leave BACKING_AUTOPLAY armed — remounts would forcePlay.
    session["_backing_autoplay"] = False
    session["_backing_transport_user_stopped"] = True
    # Drop explicit-Play sticky so a later natural handoff is not deferred.
    session.pop("_kc_arrangement_url", None)
    session.pop("_kc_arrangement_reload", None)
    session.pop("_kc_force_arrangement_replace", None)
    session.pop("_kc_force_play_published_url", None)
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
    session.pop("_backing_transport_user_stopped", None)
    session.pop("_kc_hard_stop", None)
    session.pop("_kc_pause_audio", None)
    session["_kc_resume_play"] = True
    # Keep remounts arming autoplay until the next Pause — a oneshot resume
    # flag was often consumed before the bridge applied it after refresh.
    session["_backing_autoplay"] = True
    # After browser refresh we intentionally restart the current key's pass.
    refresh_start = bool(session.pop("_kc_refresh_resume_from_start", False))
    if refresh_start:
        session["_kc_restart_play"] = True
    cur = str(data.get("current_playback_key") or "").strip()
    if cur:
        try:
            promote_prepared_cycle_audio(session, cur)
        except Exception:
            pass
    has_audio = bool(
        str(session.get("_kc_current_static_url") or "").strip()
        or str(session.get("_last_backing_wav_path") or "").strip()
    )
    if not has_audio:
        # Fresh Streamlit session: prepared bag + sticky URLs are gone. Reuse the
        # continue-play pipeline (module WAV cache hit or regenerate) so Resume
        # mounts an audible buffer for the restored cycle key — not label-only.
        session[BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY] = True
    return data


def arm_key_cycle_for_explicit_play(session: dict[str, Any]) -> dict[str, Any] | None:
    """Play Backing Track with cycling On: fresh cycle at the FIRST key.

    Always restarts from the first chord of the first sequence key using all
    current settings (including pending PK / direction / interval / spelling).
    Distinct from Resume (continue mid-pass at the retained key/position).
    """
    owner = resolve_cycle_owner(session)
    data = get_owner_cycle_session(session, owner)
    if data and data.get("enabled"):
        data = dict(data)
        start = str(
            data.get("start_cycle_key")
            or data.get("base_practice_key")
            or current_backing_owner_practice_key(session)
            or ""
        ).strip()
        seq = cycle_key_sequence(session, owner)
        if seq:
            start = str(seq[0] or start).strip() or start
        if start:
            data["current_playback_key"] = start
            data["offset_semitones"] = 0
            if not str(data.get("start_cycle_key") or "").strip():
                data["start_cycle_key"] = start
        data["status"] = STATUS_RUNNING
        data["pass_id"] = int(data.get("pass_id") or 0) + 1
        _put_owner_cycle_session(session, owner, data)
        try:
            promote_prepared_cycle_audio(
                session, str(data.get("current_playback_key") or "")
            )
        except Exception:
            pass
        session.pop("_kc_at_final_key", None)
        session.pop("_kc_cycle_finished_final", None)
    else:
        data = None
    session["_kc_player_cmd_epoch"] = int(session.get("_kc_player_cmd_epoch") or 0) + 1
    session.pop("_backing_transport_user_stopped", None)
    session.pop("_kc_hard_stop", None)
    session.pop("_kc_pause_audio", None)
    session.pop("_kc_resume_play", None)
    session.pop("_kc_refresh_resume_from_start", None)
    session["_kc_restart_play"] = True
    session["_backing_autoplay"] = True
    return get_owner_cycle_session(session, owner) if data is not None else data


def hard_stop_key_cycle_audio(session: dict[str, Any]) -> dict[str, Any] | None:
    """Silence dual-buffer + cancel handoffs; keep position and sounding key.

    Stopped playback shows Resume and continues from the same place — it does
    not seek to t=0. Turn off cycling remains the separate disable action.
    """
    data = pause_key_cycle(session)
    session["_kc_hard_stop"] = True
    session["_kc_pause_audio"] = True
    session.pop("_kc_resume_play", None)
    session.pop("_kc_restart_play", None)
    session.pop(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    session.pop("_kc_seamless_handoff", None)
    session.pop("_kc_skip_audio_remount", None)
    return data


def restart_key_cycle_audio(session: dict[str, Any]) -> dict[str, Any] | None:
    """Resume after Stop/Pause from the preserved position (same sounding key)."""
    data = resume_key_cycle(session)
    # Do not seek to t=0 — Stop preserves position; Resume continues there.
    session.pop("_kc_restart_play", None)
    session.pop("_kc_hard_stop", None)
    session.pop("_kc_pause_audio", None)
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
    sounding_before = ""
    if data:
        sounding_before = str(
            data.get("current_playback_key")
            or temporary_playback_key(session)
            or ""
        ).strip()
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
    # Kill transport so late prefetch / CONTINUE_PLAY cannot restart audio.
    session["_backing_autoplay"] = False
    session.pop("_backing_play_request", None)
    session["_backing_transport_user_stopped"] = True
    session.pop("_kc_prefetch_neighbors", None)
    session.pop("_kc_prefetch_push_sig", None)
    session.pop("_kc_prefetch_armed", None)
    session["_kc_hard_stop"] = True
    session["_kc_pause_audio"] = True
    # Only drop the WAV when the audible key actually differed from saved PK.
    # Spurious Off (radio remount after Play) while still on the first cycle key
    # must not wipe a just-generated arrangement — that hung proofs in
    # has_wav=false limbo while waiting for audio.
    try:
        base_key = str(data.get("base_practice_key") or base or "").strip()
        if sounding_before and base_key and not _keys_equivalent(
            sounding_before, base_key
        ):
            from songs.key_state import BACKING_NEEDS_REGEN, invalidate_backing_cache

            invalidate_backing_cache(session)
            session[BACKING_NEEDS_REGEN] = True
    except Exception:
        pass
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
    allow_wrap: bool | None = None,
) -> dict[str, Any] | None:
    """Move temporary sounding key by ``steps`` along the configured sequence.

    ``steps=+1`` is Next (forward in displayed order); ``steps=-1`` is Previous.
    Direction (up/down) is already baked into ``cycle_key_sequence`` — do not
    treat Next as "raise pitch".

    Natural pass completion uses ``allow_wrap=False`` so the final key stops
    and waits. Manual Next/Previous wraps (``force=True`` ⇒ wrap by default).
    """
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
    prefs = data.get("spelling_prefs") if isinstance(data.get("spelling_prefs"), dict) else spelling_prefs_from_session(session)
    start = str(data.get("start_cycle_key") or data.get("base_practice_key") or "C").strip() or "C"
    seq = cycle_key_sequence(session, owner)
    n = len(seq) or cycle_sequence_length(interval=mag)
    cur = str(data.get("current_playback_key") or "").strip()
    idx = 0
    for i, key_tok in enumerate(seq):
        if _keys_equivalent(key_tok, cur):
            idx = i
            break
    else:
        raw = int(data.get("offset_semitones") or 0) // mag
        idx = int((-raw) % n) if str(data.get("direction") or "up") == "down" else int(raw % n)
    wrap = bool(force) if allow_wrap is None else bool(allow_wrap)
    # Natural advance during arrangement replace must not leave the locked key.
    if not force:
        lock = str(session.get("_kc_arr_key_lock") or "").strip()
        if lock:
            _log_cycle_key_write(
                session,
                trigger="step_reject_arrangement_key_lock",
                old_key=str(data.get("current_playback_key") or ""),
                new_key=lock,
                cycle_id=str(data.get("cycle_id") or ""),
                pass_id=data.get("pass_id"),
                extra={"steps": steps},
            )
            return get_owner_cycle_session(session, owner)
    raw_next = idx + int(steps)
    if not wrap:
        if raw_next >= n:
            session["_kc_at_final_key"] = True
            session["_kc_cycle_finished_final"] = True
            pause_key_cycle(session)
            # Ensure the bridge publishes a hard stop — JS must not keep a
            # wrap-neighbor nextUrl armed after the final key ends.
            session["_kc_hard_stop"] = True
            session["_kc_pause_audio"] = True
            _log_cycle_key_write(
                session,
                trigger="final_key_stop",
                old_key=cur,
                new_key=cur,
                cycle_id=str(data.get("cycle_id") or ""),
                pass_id=data.get("pass_id"),
                extra={"idx": idx, "n": n},
            )
            return get_owner_cycle_session(session, owner)
        if raw_next < 0:
            return data
        new_idx = raw_next
    else:
        new_idx = raw_next % n
        session.pop("_kc_at_final_key", None)
        session.pop("_kc_cycle_finished_final", None)
    new_key = seq[new_idx] if seq else cycle_concert_practice_key(
        start, semitones=new_idx * unit, spelling_prefs=prefs
    )
    new_offset = int(new_idx) * int(unit)
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

    # Reuse prepared audio when present — do not wipe the live WAV first
    # (that forced a full regenerate even on a cache hit).
    hit = promote_prepared_cycle_audio(session, new_key)
    session["_kc_switch_cache_hit"] = bool(hit)
    if hit:
        session["_kc_skip_audio_remount"] = True
        # Audio for this key is already prepared. Show it as sounding now so
        # the playbar does not keep the previous key highlighted during prep.
        session["_kc_last_playing_confirm"] = {
            "key": str(new_key),
            "passId": data.get("pass_id"),
            "cycleId": str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
            "t": __import__("time").time(),
        }
    else:
        try:
            from songs.key_state import invalidate_backing_cache

            invalidate_backing_cache(session)
        except Exception:
            session.pop("_last_backing_wav", None)
            session.pop("_last_backing_signature", None)
            session.pop("_last_backing_wav_path", None)
    # Manual Next/Previous must always restart at the first chord of the new key.
    if force:
        session["_kc_restart_play"] = True
        session.pop("_kc_restart_play_pubs", None)
        session.pop("_kc_hard_stop", None)
        session.pop("_kc_pause_audio", None)
        session.pop("_backing_transport_user_stopped", None)
        session.pop("_kc_at_final_key", None)
        session.pop("_kc_cycle_finished_final", None)
        session["_backing_autoplay"] = True
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
    allow_wrap: bool | None = None,
) -> dict[str, Any] | None:
    return _step_owner_cycle(
        session,
        steps=1,
        force=force,
        queue_continue=queue_continue,
        allow_wrap=allow_wrap,
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
    # Practice Key / cycle-settings / arrangement changes own the next Play.
    # Late browser playing acks from the prior pass must not walk the new cycle.
    if key_cycle_settings_pending(session):
        _log_cycle_key_write(
            session,
            trigger="playing_ack_reject_settings_pending",
            old_key=str(data.get("current_playback_key") or ""),
            new_key=str(playing or ""),
            cycle_id=str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
            pass_id=pass_id,
            extra={"fromKey": from_key},
        )
        return False, data
    lock = str(session.get("_kc_arr_key_lock") or "").strip()
    if lock:
        _log_cycle_key_write(
            session,
            trigger="playing_ack_reject_arrangement_key_lock",
            old_key=str(data.get("current_playback_key") or ""),
            new_key=str(playing or ""),
            cycle_id=str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
            pass_id=pass_id,
            extra={"fromKey": from_key, "lock": lock},
        )
        return False, data
    want = str(playing or "").strip()
    if not want:
        return False, data
    before = str(data.get("current_playback_key") or "").strip()
    cycle_id = str(data.get("cycle_id") or session.get("_kc_cycle_id") or "")
    # Ack identity must match the live cycle after reanchor / settings reset.
    ack_cycle = ""
    try:
        # Optional: callers may stash the ack cycle on session for this apply.
        ack_cycle = str(session.get("_kc_applying_ack_cycle") or "").strip()
    except Exception:
        ack_cycle = ""
    if ack_cycle and cycle_id and ack_cycle != cycle_id:
        _log_cycle_key_write(
            session,
            trigger="playing_ack_reject_cycle_mismatch",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"fromKey": from_key, "ackCycle": ack_cycle},
        )
        return False, data
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
    # Only step when the browser confirms the *expected* next key.
    # Do not advance merely because from_key matches before — that lets late
    # acks from a prior cycle walk a freshly reanchored session.
    if _keys_equivalent(expected, want):
        after = _advance_owner_cycle(
            session, force=False, queue_continue=False, allow_wrap=False
        )
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

    # Absolute align must not skip sequence entries (Fm ack saying Am).
    # Only confirm-noop when already on ``want``; otherwise refuse.
    if not _keys_equivalent(before, want):
        _log_cycle_key_write(
            session,
            trigger="playing_ack_align_reject_skip",
            old_key=before,
            new_key=want,
            cycle_id=cycle_id,
            pass_id=pass_id,
            extra={"fromKey": from_key, "expected": expected},
        )
        return False, data

    # Absolute align (spelling) — already on want; stamp confirm only.
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
    # Arrangement auto-apply rebuilds the CURRENT key — ignore pass-end /
    # playing-ack advances until the new WAV is stashed (clears the lock).
    lock = str(session.get("_kc_arr_key_lock") or "").strip()
    if lock:
        _log_cycle_key_write(
            session,
            trigger="pass_finished_reject_arrangement_key_lock",
            old_key=str(data.get("current_playback_key") or ""),
            new_key=lock,
            cycle_id=str(data.get("cycle_id") or ""),
            pass_id=data.get("pass_id"),
            extra={"sig": pass_signature, "seamless": seamless},
        )
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
                # Stale-cycle leftovers from a prior Off→On must not block forever —
                # consume so the component can deliver a fresh ack.
                # settings_pending: also consume — otherwise pass-bridge kept
                # re-delivering the same natural ack and st.rerun()-starved Play.
                if reason in {"stale_cycle", "settings_pending"}:
                    try:
                        mark_ack_consumed(session, str(ack.get("ackId") or ""))
                    except Exception:
                        pass
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
            # Durably stamp the confirmed playing key immediately — do not wait
            # for a later full-session save that may still hold the prior key.
            if changed or (playing and not _keys_equivalent(before, playing)):
                try:
                    persist_key_cycle_position(session)
                except Exception:
                    pass
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
        # Exception: explicit late_prep_recover when the dual-buffer never armed
        # next (loops=2 nextReady=0) — must not stall indefinitely.
        _late_prep = str(pass_signature or "").startswith("late_prep_recover::")
        try:
            last_c = session.get("_kc_last_playing_confirm")
            if (not _late_prep) and isinstance(last_c, dict):
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
        session, force=False, queue_continue=not seamless, allow_wrap=False
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
    // Remove legacy substitute chord-grid host if a prior build left it in the DOM.
    try {{
      const junkLive = parentDoc.getElementById('kc-chart-live');
      if (junkLive) junkLive.remove();
      const junkHost = parentDoc.getElementById('kc-full-chart-host');
      if (junkHost) junkHost.remove();
    }} catch (eJunk) {{}}
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
        userPaused: false,
      }};
    }}
    const state = parentWin.__kcDual;
    if (state.userPaused == null) {{
      try {{
        state.userPaused = parentWin.sessionStorage.getItem('kc_user_paused') === '1';
      }} catch (eUP) {{ state.userPaused = false; }}
    }}
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
    function prepAudio(role) {{
      const id = 'kc-prep-' + role;
      let el = parentDoc.getElementById(id);
      if (el) return el;
      el = parentDoc.createElement('audio');
      el.id = id;
      el.preload = 'auto';
      el.setAttribute('data-kc-prep', role);
      el.style.cssText = 'display:none';
      const root = parentDoc.getElementById('kc-persistent-root') || parentDoc.body;
      try {{ root.appendChild(el); }} catch (eA) {{
        try {{ parentDoc.body.appendChild(el); }} catch (eB) {{}}
      }}
      return el;
    }}
    function ensureDecoded(url, sounding, role) {{
      url = String(url || '');
      sounding = String(sounding || '');
      if (!url || !sounding) return;
      const ids = ['kc-buf-0', 'kc-buf-1', 'kc-prep-next', 'kc-prep-prev', 'kc-prep-follow'];
      for (let i = 0; i < ids.length; i++) {{
        const a = parentDoc.getElementById(ids[i]);
        if (a && urlsMatch(a, url)) {{
          if (!a.getAttribute('data-kc-sounding')) a.setAttribute('data-kc-sounding', sounding);
          const rs = Number(a.readyState || 0);
          const ns = Number(a.networkState || 0);
          // A matching element that never fetched (or failed) must be retried.
          // Leaving it at HAVE_NOTHING made the +3 key look like a cold miss.
          if (rs < 2 && (a.error || ns === 0 || ns === 3)) {{
            try {{ a.load(); }} catch (eL) {{}}
          }}
          return;
        }}
      }}
      const slot = prepAudio(role);
      const live = activeAudio();
      if (!slot || (live && slot === live)) return;
      armIdleFromUrl(slot, url, sounding, role);
    }}
    function parkAudio(sounding) {{
      const safe = String(sounding || '').replace(/[^A-Za-z0-9]/g, '') || 'x';
      const id = 'kc-park-' + safe;
      let el = parentDoc.getElementById(id);
      if (el) return el;
      el = parentDoc.createElement('audio');
      el.id = id;
      el.preload = 'auto';
      el.setAttribute('data-kc-park', sounding);
      el.style.cssText = 'display:none';
      const root = parentDoc.getElementById('kc-persistent-root') || parentDoc.body;
      try {{ root.appendChild(el); }} catch (eA) {{
        try {{ parentDoc.body.appendChild(el); }} catch (eB) {{}}
      }}
      return el;
    }}
    function parkKey(url, sounding) {{
      url = String(url || '');
      sounding = String(sounding || '');
      if (!url || !sounding) return;
      const live = activeAudio();
      const all = [...parentDoc.querySelectorAll('audio')];
      for (let i = 0; i < all.length; i++) {{
        const a = all[i];
        if (!a || a === live) continue;
        if (!urlsMatch(a, url)) continue;
        if (Number(a.currentTime || 0) < 1.25) return;
      }}
      const slot = parkAudio(sounding);
      if (!slot || slot === live) return;
      if (!urlsMatch(slot, url)) armIdleFromUrl(slot, url, sounding, 'park');
    }}
    function ensureNeighborDecode() {{
      try {{
        ensureDecoded(state.nextUrl, state.nextSounding, 'next');
        ensureDecoded(state.prevUrl, state.prevSounding, 'prev');
        ensureDecoded(state.followingUrl, state.followingSounding, 'follow');
        ensureDecoded(state.aheadUrl, state.aheadSounding, 'ahead');
        parkKey(state.nextUrl, state.nextSounding);
        parkKey(state.prevUrl, state.prevSounding);
        parkKey(state.followingUrl, state.followingSounding);
        parkKey(state.aheadUrl, state.aheadSounding);
        parkKey(state.playingUrl, parentWin.__kcLastSounding);
      }} catch (eN) {{}}
    }}
    function noteCmdNeighbors(cmd) {{
      try {{
        if (!cmd) return;
        parentWin.__kcUrlToKey = parentWin.__kcUrlToKey || {{}};
        parentWin.__kcChartByKey = parentWin.__kcChartByKey || {{}};
        if (cmd.nextUrl && cmd.nextSounding && String(cmd.nextSounding) !== String(cmd.sounding || '')) {{
          parentWin.__kcUrlToKey[String(cmd.nextUrl)] = String(cmd.nextSounding);
          state.nextUrl = String(cmd.nextUrl);
          state.nextSounding = String(cmd.nextSounding);
          if (cmd.nextChartHtml) {{
            parentWin.__kcChartByKey[String(cmd.nextSounding)] = String(cmd.nextChartHtml);
          }}
        }}
        if (cmd.prevUrl && cmd.prevSounding) {{
          parentWin.__kcUrlToKey[String(cmd.prevUrl)] = String(cmd.prevSounding);
          state.prevUrl = String(cmd.prevUrl);
          state.prevSounding = String(cmd.prevSounding);
          if (cmd.prevChartHtml) {{
            parentWin.__kcChartByKey[String(cmd.prevSounding)] = String(cmd.prevChartHtml);
          }}
        }}
        if (cmd.followingUrl && cmd.followingSounding) {{
          parentWin.__kcUrlToKey[String(cmd.followingUrl)] = String(cmd.followingSounding);
          state.followingUrl = String(cmd.followingUrl);
          state.followingSounding = String(cmd.followingSounding);
          if (cmd.followingChartHtml) {{
            parentWin.__kcChartByKey[String(cmd.followingSounding)] = String(cmd.followingChartHtml);
          }}
        }}
        if (cmd.aheadUrl && cmd.aheadSounding) {{
          parentWin.__kcUrlToKey[String(cmd.aheadUrl)] = String(cmd.aheadSounding);
          state.aheadUrl = String(cmd.aheadUrl);
          state.aheadSounding = String(cmd.aheadSounding);
          if (cmd.aheadChartHtml) {{
            parentWin.__kcChartByKey[String(cmd.aheadSounding)] = String(cmd.aheadChartHtml);
          }}
        }}
        ensureNeighborDecode();
      }} catch (eNote) {{}}
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
            || parentWin.__kcWatchVersion !== 30
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
          && parentWin.__kcWatchVersion === 30) return;
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
      var userPaused = !!st.userPaused;
      try {{ userPaused = userPaused || window.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eUP) {{}}
      if (userPaused) {{
        try {{
          var docP = window.document;
          var a0 = docP.getElementById('kc-buf-0');
          var a1 = docP.getElementById('kc-buf-1');
          if (a0) a0.pause();
          if (a1) a1.pause();
        }} catch (ePs) {{}}
        return false;
      }}
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
      // Resolve key + push ack BEFORE marking settled. Marking settled first
      // then throwing left the third natural handoff with no __kcAckLog entry.
      var playingKey = String(ph.playingKey || act.getAttribute('data-kc-sounding') || window.__kcLastSounding || '').trim();
      if (!playingKey) {{
        try {{
          window.__kcPlayDiag = window.__kcPlayDiag || [];
          window.__kcPlayDiag.push({{
            t: playingAt,
            ev: 'parent_finish_no_key',
            id: act.id,
            reason: reason || '',
          }});
        }} catch (eNk) {{}}
        return false;
      }}
      var chartHtml = String(ph.chartHtml || '');
      // Never invent a raw substitute grid — highlight chips only if lead sheet HTML lagged.
      var chartAt = performance.now();
      var timing = ph.timing || {{}};
      timing.playingAt = playingAt;
      timing.chartAt = chartAt;
      timing.ackSentAt = (typeof kcNow === 'function' ? kcNow() : playingAt);
      timing.endedAt = endedAt;
      st.passId = Number(st.passId || 0) + 1;
      st.chartMs = Math.max(0, chartAt - playingAt);
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
      window.__kcPendingPlayingAck = ack;
      try {{
        window.__kcPendingPlayingAckQueue = window.__kcPendingPlayingAckQueue || [];
        window.__kcPendingPlayingAckQueue.push(ack);
        if (window.__kcPendingPlayingAckQueue.length > 12) {{
          window.__kcPendingPlayingAckQueue.shift();
        }}
      }} catch (eQ) {{}}
      window.__kcLastHandoffAck = ack;
      window.__kcLastGapMs = gapMs;
      window.__kcLastSounding = playingKey;
      window.__kcLastChartMs = st.chartMs;
      st._kcPlayInFlight = false;
      st.handoffSettledToken = ph.token;
      st.swapping = false;
      st.playingUrl = ph.nextUrl || st.playingUrl || '';
      st.pendingHandoff = null;
      try {{
        // Apply prepared lead-sheet HTML onto the real chart; never revive kc-chart-live.
        var junkLive = doc.getElementById('kc-chart-live');
        if (junkLive) junkLive.remove();
        var junkHost = doc.getElementById('kc-full-chart-host');
        if (junkHost) junkHost.remove();
        if (chartHtml) {{
          var wrap = doc.createElement('div');
          wrap.innerHTML = chartHtml;
          var neu = wrap.querySelector('.backing-chart-sheet, .lead-sheet') || wrap.firstElementChild;
          var sheet = doc.querySelector('.backing-chart-sheet, .lead-sheet, [data-testid="kc-streamlit-chart"]');
          if (neu && sheet && sheet.parentElement) {{
            neu.setAttribute('data-kc-playing-key', playingKey);
            sheet.replaceWith(neu);
          }}
        }}
      }} catch (e) {{}}
      try {{
        if (typeof window.__kcSyncHighlight === 'function') window.__kcSyncHighlight(playingKey);
      }} catch (eH) {{}}
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
      window.__kcPlayDiag.push({{ t: performance.now(), ev: 'parent_finish', reason: reason || '', gapMs: gapMs, id: act.id, playingKey: playingKey }});
      return true;
    }} catch (e) {{
      try {{ window.__kcWatchErr = 'finish:' + String(e && e.message || e); }} catch (e2) {{}}
      return false;
    }}
  }};
  if (window.__kcEndedWatch) return;
  window.__kcWatchVersion = 30;
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
        var userPaused = !!st.userPaused;
        try {{ userPaused = userPaused || window.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eUP) {{}}
        if (act && !act.ended && act.paused && age > 120 && age < 20000
            && !window.__kcLastGapMs && !playBusy && !userPaused) {{
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
        // Keep pendingHandoff until an exact playing ack settles — clearing
        // swapping alone at 8s left the third cold handoff without publishAck.
        if (age < 20000) return;
        try {{
          window.__kcPlayDiag = window.__kcPlayDiag || [];
          window.__kcPlayDiag.push({{
            t: performance.now(),
            ev: 'handoff_watch_timeout',
            age: age,
            pending: !!(st.pendingHandoff && st.pendingHandoff.playingKey),
            ct: act ? Number(act.currentTime || 0) : -1,
            paused: act ? !!act.paused : null,
          }});
        }} catch (eTo) {{}}
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
        st._kcLatePrepAt = 0;
        window.__kcSched(function(){{
          try {{ window.__kcOnEnded(); }} catch (e) {{}}
        }}, 0);
      }} else if (
        act && !act.ended && !act.paused && !act.loop && hasNext
        && Number(act.duration || 0) > 8
        && Number(act.currentTime || 0) >= Number(act.duration) - 0.45
        && !st.swapping && !st.pendingHandoff && !st.userPaused
        && !st._kcNearEndFired
        && typeof window.__kcOnEnded === 'function'
      ) {{
        // Full-length WAVs: after a seek-to-tail some Chromium builds never
        // flip ended even though playback has reached the last samples.
        st._kcNearEndFired = true;
        st._kcNearEndUrl = act.getAttribute('data-kc-url') || act.src || '';
        try {{ if (act.__kcIgnoreEndedUntil) act.__kcIgnoreEndedUntil = 0; }} catch (eIgnN) {{}}
        window.__kcSched(function(){{
          try {{ window.__kcOnEnded(); }} catch (eN) {{}}
        }}, 0);
      }} else if (
        act && st._kcNearEndFired
        && Number(act.currentTime || 0) < 5
        && Number(act.duration || 0) > 8
      ) {{
        // New pass is playing from the start — allow a future near-end fire.
        st._kcNearEndFired = false;
        st._kcNearEndUrl = '';
      }} else if (
        act && act.ended && !act.loop && !hasNext
        && !st.swapping && !st.pendingHandoff && !st.userPaused
        && typeof window.__kcOnEnded === 'function'
      ) {{
        // Natural end with no next buffer yet — wait for fragment publication.
        var userPausedLP = !!st.userPaused;
        try {{ userPausedLP = userPausedLP || window.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eUPL) {{}}
        if (userPausedLP) {{
          st._kcLatePrepAt = 0;
        }} else {{
          if (!st._kcLatePrepAt) st._kcLatePrepAt = performance.now();
          var lateAge = performance.now() - Number(st._kcLatePrepAt || 0);
          // Re-arm from last cmd if Python published while we were ended.
          try {{
            var lastCmd = window.__kcLastCmd || {{}};
            if (lastCmd && lastCmd.nextUrl && !st.nextUrl) {{
              st.nextUrl = String(lastCmd.nextUrl || '');
              if (lastCmd.nextSounding) st.nextSounding = String(lastCmd.nextSounding || '');
              if (idle && st.nextUrl) {{
                idle.setAttribute('data-kc-url', st.nextUrl);
                if (st.nextSounding) idle.setAttribute('data-kc-sounding', st.nextSounding);
                idle.preload = 'auto';
                if (idle.getAttribute('src') !== st.nextUrl && idle.src !== st.nextUrl) {{
                  idle.src = st.nextUrl;
                  try {{ idle.load(); }} catch (eLdLP) {{}}
                }}
              }}
            }}
          }} catch (eRe) {{}}
          if (st.nextUrl) {{
            st._kcLatePrepAt = 0;
            window.__kcSched(function(){{
              try {{ window.__kcOnEnded(); }} catch (e) {{}}
            }}, 0);
          }} else if (lateAge > 90000) {{
            st._kcLatePrepAt = 0;
            try {{
              window.__kcPlayDiag = window.__kcPlayDiag || [];
              window.__kcPlayDiag.push({{
                t: performance.now(),
                ev: 'late_prep_watch_timeout',
                age: lateAge,
              }});
            }} catch (eLPT) {{}}
            window.__kcSched(function(){{
              try {{ window.__kcOnEnded(); }} catch (e) {{}}
            }}, 0);
          }}
        }}
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
        if (act && !act.ended) st._kcLatePrepAt = 0;
        // Warm-start next buffer muted in the last ~0.8s so swap only unmutes
        // (avoids recycled-buffer play() stalls of 1–3s).
        if (
          act && idle && !act.ended && !act.paused
          && Number(act.duration || 0) > 2
          && !st.swapping && !st.pendingHandoff
          && st.nextUrl
        ) {{
          var left = Number(act.duration || 0) - Number(act.currentTime || 0);
          // Keep idle pointed at promoted next — mid-pass Python cmds can leave
          // data-kc-url empty after the outgoing buffer abort+load.
          try {{
            if (left > 0.05 && left < 3.0) {{
              var idleUrl0 = String(idle.getAttribute('data-kc-url') || idle.src || '');
              var want0 = String(st.nextUrl || '');
              var matched0 = !!(idleUrl0 && want0 && (
                idleUrl0.indexOf(want0.slice(-24)) !== -1
                || want0.indexOf(idleUrl0.slice(-24)) !== -1
                || idleUrl0 === want0
              ));
              if (!matched0 && want0) {{
                idle.setAttribute('data-kc-url', want0);
                if (st.nextSounding) idle.setAttribute('data-kc-sounding', st.nextSounding);
                idle.preload = 'auto';
                if (idle.getAttribute('src') !== want0 && idle.src !== want0) {{
                  idle.src = want0;
                  try {{ idle.load(); }} catch (eLd) {{}}
                }}
                st._kcWarmStarted = false;
              }}
            }}
          }} catch (eArmN) {{}}
          // Diagnose why warm does not arm (log near end only).
          if (left > 0.05 && left < 2.5) {{
            try {{
              var warmUrl = String(idle.getAttribute('data-kc-url') || idle.src || '');
              var want = String(st.nextUrl || '');
              var rs = Number(idle.readyState || 0);
              var urlOk = !!(warmUrl && want && (
                warmUrl.indexOf(want.slice(-24)) !== -1
                || want.indexOf(warmUrl.slice(-24)) !== -1
                || warmUrl === want
              ));
              var reason = '';
              if (st._kcWarmStarted) reason = 'already_warm';
              else if (!(left < 1.5)) reason = 'left_too_early';
              else if (rs < 2) reason = 'idle_rs_' + rs;
              else if (!urlOk) reason = 'url_mismatch';
              else if (!(idle.paused || Number(idle.currentTime || 0) > 0.35 || Number(idle.currentTime || 0) < 0.02))
                reason = 'idle_ct_mid_' + Number(idle.currentTime || 0).toFixed(2);
              else reason = 'eligible';
              var nowT = performance.now();
              if (!st._kcWarmSkipAt || (nowT - st._kcWarmSkipAt) > 180) {{
                st._kcWarmSkipAt = nowT;
                window.__kcPlayDiag = window.__kcPlayDiag || [];
                window.__kcPlayDiag.push({{
                  t: nowT,
                  ev: 'warm_arm_probe',
                  left: left,
                  rs: rs,
                  urlOk: urlOk,
                  reason: reason,
                  idleId: idle.id,
                  ct: Number(idle.currentTime || 0),
                  paused: !!idle.paused,
                  nextTail: want ? want.slice(-24) : '',
                }});
              }}
            }} catch (eProbe) {{}}
          }}
          // Start warm late so promote lands near bar 1 (not deep into the pass).
          // Window must exceed the 200ms watch tick or warm never arms.
          // Seek-0 on promote preserves count-in even if muted pre-roll advances.
          if (left > 0.05 && left < 1.5 && Number(idle.readyState || 0) >= 2 && !st._kcWarmStarted) {{
            try {{
              var warmUrl2 = String(idle.getAttribute('data-kc-url') || idle.src || '');
              var want2 = String(st.nextUrl || '');
              if (warmUrl2 && want2 && (warmUrl2.indexOf(want2.slice(-24)) !== -1 || want2.indexOf(warmUrl2.slice(-24)) !== -1 || warmUrl2 === want2)) {{
                // Arm when idle is stopped, at start, or stuck mid-buffer from a
                // prior warm — always seek 0 so count-in is preserved on promote.
                if (idle.paused || Number(idle.currentTime || 0) < 0.05 || Number(idle.currentTime || 0) > 0.25) {{
                  idle.muted = true;
                  idle.loop = false;
                  try {{ idle.currentTime = 0; }} catch (eW0) {{}}
                  var pw = idle.play();
                  st._kcWarmStarted = true;
                  if (pw && pw.catch) pw.catch(function(){{ st._kcWarmStarted = false; }});
                  window.__kcPlayDiag = window.__kcPlayDiag || [];
                  window.__kcPlayDiag.push({{
                    t: performance.now(),
                    ev: 'warm_start_idle',
                    left: left,
                    id: idle.id,
                    rs: Number(idle.readyState || 0),
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
          && !st.userPaused
          && (function(){{ try {{ return window.sessionStorage.getItem('kc_user_paused') !== '1'; }} catch (e) {{ return true; }} }})()
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
    function ensureChartStage() {{
      let stage = parentDoc.getElementById('kc-chart-staged');
      if (!stage) {{
        stage = parentDoc.createElement('div');
        stage.id = 'kc-chart-staged';
        stage.setAttribute('data-testid', 'kc-chart-staged');
        stage.style.cssText = 'position:absolute;left:-99999px;top:0;width:1px;height:1px;overflow:hidden;visibility:hidden;pointer-events:none;';
        const live = parentDoc.getElementById('kc-chart-live');
        if (live && live.parentElement) live.parentElement.appendChild(stage);
        else parentDoc.body.appendChild(stage);
      }}
      return stage;
    }}
    function stageNextChart(html, sounding) {{
      try {{
        // Preload lead-sheet HTML for the next sounding key; applied onto the
        // existing .backing-chart-sheet at audible start (never a substitute grid).
        const stage = ensureChartStage();
        if (!stage) return false;
        const key = String(sounding || '');
        const body = String(html || '').trim();
        if (!body) return false;
        stage.innerHTML = body;
        stage.setAttribute('data-kc-playing-key', key);
        stage.setAttribute('data-kc-ready', '1');
        return true;
      }} catch (e) {{ return false; }}
    }}
    // Parent-owned lead sheet for cycle mode (survives Streamlit remounts; no
    // duplicate pre-iframe chart). Chord follow is driven by dual-buffer audio.
    function ensureLeadSheetFollowCss() {{
      if (parentDoc.getElementById('kc-lead-sheet-follow-css')) return;
      const style = parentDoc.createElement('style');
      style.id = 'kc-lead-sheet-follow-css';
      style.textContent = `
        #kc-lead-sheet-host .chord-cell.current-chord,
        #kc-lead-sheet-host .live-chart-cell.current-chord {{
          background: #86efac !important;
          border-color: #15803d !important;
          box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.28), 0 0 22px rgba(22, 163, 74, 0.28) !important;
          transform: translateY(-1px);
        }}
        #kc-lead-sheet-host .section-card.current {{
          outline: 3px solid rgba(34, 197, 94, 0.34) !important;
          box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.10) !important;
        }}
      `;
      try {{ parentDoc.head.appendChild(style); }} catch (e) {{ parentDoc.body.appendChild(style); }}
    }}
    function ensureLeadSheetHost() {{
      ensureLeadSheetFollowCss();
      let host = parentDoc.getElementById('kc-lead-sheet-host');
      if (!host) {{
        host = parentDoc.createElement('div');
        host.id = 'kc-lead-sheet-host';
        host.setAttribute('data-testid', 'kc-streamlit-chart');
        host.setAttribute('data-kc-parent-sheet', '1');
        parentDoc.body.appendChild(host);
        if (parentWin.__kcLastChartHtml) {{
          try {{ host.innerHTML = String(parentWin.__kcLastChartHtml); }} catch (eR) {{}}
        }}
      }}
      // Re-home into the Streamlit open-card when present so layout stays correct
      // after each rerun without forcing the user to reopen the sheet.
      try {{
        const anchor = parentDoc.getElementById('backing-lead-sheet-anchor')
          || parentDoc.querySelector('.ui-backing-leadsheet-card[data-state="open"]');
        if (anchor) {{
          let slot = parentDoc.getElementById('kc-lead-sheet-slot');
          if (!slot || !anchor.contains(slot)) {{
            slot = parentDoc.createElement('div');
            slot.id = 'kc-lead-sheet-slot';
            anchor.appendChild(slot);
          }}
          if (host.parentElement !== slot) slot.appendChild(host);
        }}
      }} catch (eP) {{}}
      return host;
    }}
    function teardownLeadSheetHost() {{
      try {{
        const host = parentDoc.getElementById('kc-lead-sheet-host');
        if (host) host.remove();
        const slot = parentDoc.getElementById('kc-lead-sheet-slot');
        if (slot) slot.remove();
      }} catch (e) {{}}
    }}
    function stripDuplicateLeadSheets(keepRoot) {{
      try {{
        const keep = keepRoot || parentDoc.getElementById('kc-lead-sheet-host');
        const sheets = Array.from(
          parentDoc.querySelectorAll('.backing-chart-sheet, .lead-sheet')
        );
        sheets.forEach((el) => {{
          if (keep && (el === keep || keep.contains(el))) return;
          if (keep) {{
            try {{ el.remove(); }} catch (eR) {{}}
          }}
        }});
      }} catch (e) {{}}
    }}
    function findLeadSheetTargets() {{
      const out = [];
      try {{
        const host = parentDoc.getElementById('kc-lead-sheet-host');
        if (host) {{
          const sheet = host.querySelector('.backing-chart-sheet, .lead-sheet');
          if (sheet) out.push({{ doc: parentDoc, sheet: sheet, root: host }});
          else out.push({{ doc: parentDoc, sheet: null, root: host }});
        }}
      }} catch (e) {{}}
      try {{
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const doc = frame.contentDocument;
            if (!doc) return;
            const root = doc.getElementById('live-chart-root')
              || doc.querySelector('.live-follow-shell');
            if (!root) return;
            const sheet = root.querySelector('.backing-chart-sheet, .lead-sheet');
            out.push({{ doc: doc, sheet: sheet, root: root, win: frame.contentWindow }});
          }} catch (eF) {{}}
        }});
      }} catch (e2) {{}}
      return out;
    }}
    let _kcFollowLastIdx = null;
    let _kcFollowRaf = null;
    function kcFollowTimeline() {{
      try {{
        const tl = parentWin.__kcFollowTimeline;
        return Array.isArray(tl) ? tl : [];
      }} catch (e) {{ return []; }}
    }}
    function kcFollowEventAt(timeSeconds) {{
      const timeline = kcFollowTimeline();
      if (!timeline.length) return null;
      if (timeSeconds >= Number(timeline[timeline.length - 1].end_time || 0)) {{
        return timeline[timeline.length - 1];
      }}
      let lo = 0;
      let hi = timeline.length - 1;
      while (lo <= hi) {{
        const mid = (lo + hi) >> 1;
        const event = timeline[mid];
        const start = Number(event.start_time || 0);
        const end = Number(event.end_time || 0);
        if (timeSeconds < start) hi = mid - 1;
        else if (timeSeconds >= end) lo = mid + 1;
        else return event;
      }}
      return timeline[Math.max(0, Math.min(lo, timeline.length - 1))] || timeline[0];
    }}
    function kcClearChordHighlight(scopeDoc) {{
      const doc = scopeDoc || parentDoc;
      try {{
        doc.querySelectorAll('.live-chart-cell.current-chord, .chord-cell.current-chord')
          .forEach((el) => el.classList.remove('current-chord'));
        doc.querySelectorAll('.section-card.current').forEach((el) => el.classList.remove('current'));
        doc.querySelectorAll('.sub-chord.active-sub').forEach((el) => el.classList.remove('active-sub'));
      }} catch (e) {{}}
    }}
    function kcUpdateChordHighlight(force) {{
      try {{
        const act = activeAudio();
        const t = act ? Number(act.currentTime || 0) : Number(parentWin.__kcFollowForceTime || 0);
        const event = kcFollowEventAt(t);
        if (!event) return;
        const idx = event.event_index;
        if (!force && idx === _kcFollowLastIdx) return;
        _kcFollowLastIdx = idx;
        const host = parentDoc.getElementById('kc-lead-sheet-host');
        const scope = host || parentDoc;
        kcClearChordHighlight(scope);
        const cells = Array.from(scope.querySelectorAll('.live-chart-cell, .chord-cell'));
        const currentCell = cells.find((cell) =>
          String(cell.dataset.section || '') === String(event.section || '')
          && Number(cell.dataset.bar) === Number(event.bar_in_section)
        );
        if (currentCell) {{
          currentCell.classList.add('current-chord');
          if (typeof event.subdivision_index === 'number') {{
            const subEl = currentCell.querySelector(
              '.sub-chord[data-sub="' + event.subdivision_index + '"]'
            );
            if (subEl) subEl.classList.add('active-sub');
          }}
          const card = currentCell.closest('.section-card');
          if (card) card.classList.add('current');
          const banner = scope.querySelector('.now-playing');
          if (banner) {{
            const label = (typeof event.subdivision_index === 'number')
              ? (event.chord + '  (' + (event.subdivision_index + 1) + '/' + event.subdivision_count + ')')
              : (event.chord || '-');
            banner.textContent = 'Now Playing: ' + (event.section || 'Section')
              + ' | Bar ' + event.bar_in_section + ' | ' + label;
          }}
          try {{
            if (force || (act && !act.paused)) {{
              // Scroll only inside the chart host — never the Streamlit page.
              // Parent scrollIntoView was burying Pause above the viewport so
              // ordinary clicks never reached the hooked button.
              kcScrollChartCell(currentCell, scope);
            }}
          }} catch (eS) {{}}
        }}
      }} catch (e) {{}}
    }}
    function kcScrollChartCell(cell, scope) {{
      try {{
        if (!cell) return;
        const doc = (cell.ownerDocument || parentDoc);
        const win = doc.defaultView || parentWin;
        const chartRoot = cell.closest('#kc-lead-sheet-host')
          || cell.closest('#kc-lead-sheet-slot')
          || cell.closest('.live-follow-shell')
          || cell.closest('#live-chart-root')
          || cell.closest('.backing-chart-sheet')
          || ((scope && scope.nodeType === 1
            && (scope.id === 'kc-lead-sheet-host' || scope.id === 'kc-lead-sheet-slot'
              || (scope.classList && scope.classList.contains('live-follow-shell'))))
              ? scope : null);
        // No chart root → do not scroll (parent scrollIntoView buried Pause).
        if (!chartRoot) return;
        let target = null;
        let p = cell.parentElement;
        while (p && p !== doc.body && p !== doc.documentElement) {{
          if (!chartRoot.contains(p) && p !== chartRoot) break;
          let oy = '';
          try {{ oy = String((win.getComputedStyle(p).overflowY || '')).toLowerCase(); }} catch (eOy) {{}}
          if ((oy === 'auto' || oy === 'scroll' || oy === 'overlay')
              && p.scrollHeight > p.clientHeight + 8) {{
            target = p;
            break;
          }}
          if (p === chartRoot) break;
          p = p.parentElement;
        }}
        if (!target) return;
        // Refuse Streamlit page scrollers — those hide the Pause row.
        try {{
          const tid = String(target.getAttribute && target.getAttribute('data-testid') || '');
          const cls = String(target.className || '');
          if (tid === 'stMain' || tid === 'stAppViewContainer'
              || /\\bstMain\\b|\\bmain\\b|appview-container/i.test(cls)
              || target === parentDoc.body
              || target === parentDoc.documentElement) {{
            return;
          }}
        }} catch (eRej) {{ return; }}
        const cRect = cell.getBoundingClientRect();
        const tRect = target.getBoundingClientRect();
        if (!tRect.height) return;
        const midDelta = (cRect.top + cRect.height / 2) - (tRect.top + tRect.height / 2);
        if (Math.abs(midDelta) > 12) {{
          target.scrollTop = Number(target.scrollTop || 0) + midDelta;
        }}
      }} catch (eScr) {{}}
    }}
    function kcPinTransportRow() {{
      try {{
        const pauseRoot = parentDoc.querySelector(
          '[class*="st-key-backing_key_cycle_pause_btn"]'
        );
        if (!pauseRoot) return;
        let row = pauseRoot.parentElement;
        for (let i = 0; i < 8 && row; i++) {{
          const kids = row.children ? row.children.length : 0;
          // Streamlit horizontal columns wrapper typically has 4 children.
          if (kids >= 4 && kids <= 6) break;
          row = row.parentElement;
        }}
        if (!row) row = pauseRoot;
        if (row.getAttribute('data-kc-transport-pin') === '1') return;
        row.setAttribute('data-kc-transport-pin', '1');
        row.style.position = 'sticky';
        row.style.top = '3.25rem';
        row.style.zIndex = '10050';
        try {{
          const bg = parentWin.getComputedStyle(parentDoc.body).backgroundColor;
          if (bg) row.style.background = bg;
        }} catch (eBg) {{}}
      }} catch (ePin) {{}}
    }}
    try {{ parentWin.__kcPinTransportRow = kcPinTransportRow; }} catch (ePinW) {{}}
    function kcFollowLoop() {{
      kcUpdateChordHighlight(false);
      const act = activeAudio();
      if (act && !act.paused && !act.ended) {{
        _kcFollowRaf = parentWin.requestAnimationFrame(kcFollowLoop);
      }} else {{
        _kcFollowRaf = null;
      }}
    }}
    function restartChordFollow(optTime) {{
      try {{
        if (_kcFollowRaf) {{
          try {{ parentWin.cancelAnimationFrame(_kcFollowRaf); }} catch (eC) {{}}
          _kcFollowRaf = null;
        }}
        _kcFollowLastIdx = null;
        if (optTime != null && isFinite(Number(optTime))) {{
          parentWin.__kcFollowForceTime = Number(optTime);
        }} else {{
          try {{ delete parentWin.__kcFollowForceTime; }} catch (eD) {{ parentWin.__kcFollowForceTime = 0; }}
        }}
        kcUpdateChordHighlight(true);
        const act = activeAudio();
        if (act && !act.paused && !act.ended) {{
          _kcFollowRaf = parentWin.requestAnimationFrame(kcFollowLoop);
        }}
      }} catch (e) {{}}
    }}
    function setFollowTimeline(timeline) {{
      try {{
        const tl = Array.isArray(timeline) ? timeline : [];
        // Refuse empty arrays — they wipe a good audible timeline and leave
        // Current/Next Chord on the iframe's embedded prior-key const.
        if (!tl.length) return;
        parentWin.__kcFollowTimeline = tl;
        // Keep every live-follow iframe's karaoke timeline in lockstep with the
        // audible buffer. A Streamlit remount otherwise keeps the prior key's
        // embedded const timeline in live-chord / live-next.
        try {{
          parentDoc.querySelectorAll('iframe').forEach((frame) => {{
            try {{
              const win = frame.contentWindow;
              const doc = frame.contentDocument;
              if (!win || !doc || !doc.getElementById('live-chord')) return;
              win.__karaokeTimeline = tl;
              win.__kcFollowTimeline = tl;
              if (typeof win.__kcSyncHighlightAt === 'function') {{
                try {{
                  const act = activeAudio();
                  const t = act ? Number(act.currentTime || 0) : 0;
                  win.__kcSyncHighlightAt(t);
                }} catch (eH) {{}}
              }}
            }} catch (eF) {{}}
          }});
        }} catch (eI) {{}}
      }} catch (e) {{}}
    }}
    function followTimelineForAudible(cmd, audibleKey) {{
      // Resolve the transposed event timeline that belongs to the audible key.
      // Never return a Python followTimeline stamped for a different sounding.
      const want = String(audibleKey || '').trim();
      const cmdKey = String((cmd && cmd.sounding) || '').trim();
      if (want && cmdKey && want !== cmdKey) {{
        try {{
          const cached = parentWin.__kcTimelineByKey && parentWin.__kcTimelineByKey[want];
          if (Array.isArray(cached) && cached.length) return cached;
        }} catch (eC) {{}}
        return null;
      }}
      if (cmd && Array.isArray(cmd.followTimeline) && cmd.followTimeline.length) {{
        return cmd.followTimeline;
      }}
      const key = want || cmdKey;
      if (key) {{
        try {{
          const cached = parentWin.__kcTimelineByKey && parentWin.__kcTimelineByKey[key];
          if (Array.isArray(cached) && cached.length) return cached;
        }} catch (eC2) {{}}
      }}
      return null;
    }}
    function adoptCmdFollowTimeline(cmd, audibleKey) {{
      const tl = followTimelineForAudible(cmd, audibleKey);
      if (!tl) return false;
      setFollowTimeline(tl);
      try {{
        parentWin.__kcTimelineByKey = parentWin.__kcTimelineByKey || {{}};
        const k = String(audibleKey || (cmd && cmd.sounding) || '').trim();
        if (k) parentWin.__kcTimelineByKey[k] = tl;
      }} catch (eK) {{}}
      return true;
    }}
    function applyLeadSheetHtml(html, sounding) {{
      try {{
        const key = String(sounding || '');
        const body = String(html || '').trim();
        // Tear down the mistaken a58b53c parent host — it showed only the raw
        // Backing-chart dump and hid the real live-follow lead sheet.
        try {{ teardownLeadSheetHost(); }} catch (eTD) {{}}
        try {{
          const junk = parentDoc.getElementById('kc-full-chart-host');
          if (junk) junk.remove();
          const live = parentDoc.getElementById('kc-chart-live');
          if (live) live.remove();
        }} catch (eJ) {{}}
        if (!body) {{
          syncHighlight(key);
          try {{ restartChordFollow(0); }} catch (eR0) {{}}
          return;
        }}
        let applied = false;
        // Prefer the live-follow iframe (#live-chart-root) — same renderer as Off.
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const win = frame.contentWindow;
            const doc = frame.contentDocument;
            if (!doc) return;
            if (win && typeof win.__kcApplyLeadSheetHtml === 'function') {{
              if (win.__kcApplyLeadSheetHtml(body, key)) {{
                applied = true;
                try {{ win.__kcRestartChordFollow(0); }} catch (eRS) {{}}
                return;
              }}
            }}
            const root = doc.getElementById('live-chart-root');
            if (!root) return;
            const wrap = doc.createElement('div');
            wrap.innerHTML = body;
            const neu = wrap.querySelector('.backing-chart-sheet, .lead-sheet') || wrap.firstElementChild;
            if (!neu) return;
            neu.setAttribute('data-kc-playing-key', key);
            const old = root.querySelector('.backing-chart-sheet, .lead-sheet');
            if (old) old.replaceWith(neu);
            else {{ root.innerHTML = ''; root.appendChild(neu); }}
            applied = true;
            try {{
              if (win && typeof win.__kcRestartChordFollow === 'function') win.__kcRestartChordFollow(0);
            }} catch (eRS2) {{}}
          }} catch (eF) {{}}
        }});
        // Never append a second chart into #backing-lead-sheet-anchor.
        if (!applied) {{
          parentWin.__kcPendingLeadSheetHtml = body;
          parentWin.__kcPendingLeadSheetKey = key;
        }} else {{
          try {{
            delete parentWin.__kcPendingLeadSheetHtml;
            delete parentWin.__kcPendingLeadSheetKey;
          }} catch (eP) {{}}
        }}
        syncHighlight(key);
        parentWin.__kcSheetKey = key;
        parentWin.__kcAudibleHold = key;
        if (parentWin.__kcClickT0) {{
          parentWin.__kcChartMs = kcNow() - Number(parentWin.__kcClickT0);
        }}
        try {{
          const act = activeAudio();
          restartChordFollow(act ? Number(act.currentTime || 0) : 0);
        }} catch (eRF) {{}}
      }} catch (e) {{
        try {{ syncHighlight(sounding); }} catch (e2) {{}}
      }}
    }}
    function applyChartHtml(html, sounding) {{
      // Prefer staged lead-sheet HTML, then fall back to the provided body.
      try {{
        const stage = parentDoc.getElementById('kc-chart-staged');
        const key = String(sounding || '');
        if (stage && stage.getAttribute('data-kc-ready') === '1'
            && (!key || stage.getAttribute('data-kc-playing-key') === key
                || !stage.getAttribute('data-kc-playing-key'))) {{
          const staged = stage.innerHTML;
          stage.removeAttribute('data-kc-ready');
          stage.innerHTML = '';
          applyLeadSheetHtml(staged || html, key);
          return;
        }}
        applyLeadSheetHtml(html, key);
      }} catch (e) {{
        try {{ syncHighlight(sounding); }} catch (e2) {{}}
      }}
    }}
    function activePlaybar() {{
      const bars = [...parentDoc.querySelectorAll('.ui-key-cycle-playbar')];
      if (!bars.length) return null;
      const cid = String(state.cycleId || '');
      if (cid) {{
        const match = bars.filter((b) => String(b.getAttribute('data-cycle-id') || '') === cid);
        if (match.length) return match[match.length - 1];
      }}
      // Prefer a bar that is not marked stale.
      const live = bars.filter((b) => b.getAttribute('data-kc-stale') !== '1');
      if (live.length) return live[live.length - 1];
      return bars[bars.length - 1];
    }}
    function pruneStalePlaybars() {{
      try {{
        const bars = [...parentDoc.querySelectorAll('.ui-key-cycle-playbar')];
        if (!bars.length) return null;
        const keep = activePlaybar() || bars[bars.length - 1];
        // Hide — do not remove — Streamlit-owned nodes (removal can break widgets).
        bars.forEach((b) => {{
          if (b !== keep) {{
            b.style.display = 'none';
            b.setAttribute('data-kc-stale', '1');
          }} else {{
            b.style.display = '';
            b.removeAttribute('data-kc-stale');
          }}
        }});
        return keep;
      }} catch (e) {{
        return activePlaybar();
      }}
    }}
    function syncPlaybarSequence(keys, sounding, displayKeys) {{
      try {{
        const seq = (Array.isArray(keys) ? keys : []).map((k) => String(k || '').trim()).filter(Boolean);
        const labels = (Array.isArray(displayKeys) ? displayKeys : [])
          .map((k) => String(k || '').trim());
        try {{
          state.sequence = seq;
          state.displaySequence = (labels.length === seq.length) ? labels : seq;
          // Track final-key so onEnded cannot wrap to the first neighbor.
          try {{
            const cur = String(sounding || state.sounding || parentWin.__kcLastSounding || '').trim();
            if (seq.length && cur && cur === String(seq[seq.length - 1] || '').trim()) {{
              state.atFinalKey = true;
            }} else if (seq.length && cur && cur !== String(seq[seq.length - 1] || '').trim()) {{
              state.atFinalKey = false;
            }}
          }} catch (eFin) {{}}
        }} catch (eSt) {{}}
        const bar = pruneStalePlaybars();
        if (!bar) return;
        if (state.cycleId) bar.setAttribute('data-cycle-id', String(state.cycleId));
        if (seq.length) {{
          const joined = seq.join(',');
          const displayJoined = (labels.length === seq.length ? labels : seq).join(',');
          const priorDisplay = String(bar.getAttribute('data-display-seq') || '');
          // Only rewrite chips when Python has not already rendered this sequence.
          // Mutating Streamlit HTML is a last resort for orphaned prior fragments.
          if (
            String(bar.getAttribute('data-seq') || '') !== joined
            || priorDisplay !== displayJoined
          ) {{
            bar.setAttribute('data-seq', joined);
            bar.setAttribute('data-display-seq', displayJoined);
            let host = bar.querySelector('.ui-key-cycle-seq');
            if (!host) {{
              host = parentDoc.createElement('div');
              host.className = 'ui-key-cycle-seq';
              host.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:.05rem;line-height:1.6';
              bar.appendChild(host);
            }}
            const s = String(sounding || state.sounding || '').trim();
            const shown = (labels.length === seq.length) ? labels : seq;
            host.innerHTML = seq.map((key, i) => {{
              const label = shown[i] || key;
              const on = s && key === s;
              const cls = on ? 'ui-key-cycle-chip ui-key-cycle-chip-on' : 'ui-key-cycle-chip';
              const cur = on ? ' data-current=\"1\"' : '';
              return '<span class=\"' + cls + '\" data-key=\"' + key
                + '\" data-display=\"' + label + '\"' + cur + '>' + label + '</span>';
            }}).join('');
          }}
        }}
        syncHighlight(sounding || state.sounding || '');
      }} catch (eSeq) {{}}
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
        const bar = pruneStalePlaybars();
        const chips = bar
          ? bar.querySelectorAll('.ui-key-cycle-chip, span[data-key]')
          : [];
        chips.forEach((el) => {{
          const key = (el.getAttribute('data-key') || el.textContent || '').trim();
          const on = key === s;
          el.classList.toggle('ui-key-cycle-chip-on', on);
          el.classList.remove('ui-key-cycle-chip-pending', 'ui-key-cycle-chip-audible');
          if (on) el.setAttribute('data-current', '1');
          else el.removeAttribute('data-current');
        }});
        const meta = parentDoc.getElementById('kc-persistent-meta');
        if (meta) meta.innerHTML = 'Sounding <strong>' + s + '</strong>';
        if (bar) {{
          const strong = bar.querySelector('strong');
          if (strong) strong.textContent = s;
        }}
      }} catch (e) {{}}
    }}
    parentWin.__kcSyncHighlight = syncHighlight;
    parentWin.__kcSyncPlaybarSequence = syncPlaybarSequence;
    parentWin.__kcPruneStalePlaybars = pruneStalePlaybars;
    parentWin.__kcRestartChordFollow = restartChordFollow;
    parentWin.__kcSetFollowTimeline = setFollowTimeline;
    parentWin.__kcEnsureLeadSheetHost = ensureLeadSheetHost;
    parentWin.__kcTeardownLeadSheetHost = teardownLeadSheetHost;
    parentWin.__kcActiveAudio = activeAudio;
    function abortTransportPlayback(opts) {{
      opts = opts || {{}};
      cancelPendingPlays();
      state.userPaused = true;
      try {{ parentWin.sessionStorage.setItem('kc_user_paused', '1'); }} catch (eSS) {{}}
      state.pendingHandoff = null;
      state.swapping = false;
      state.ending = false;
      state._onEndedGate = false;
      state.swapStartedAt = 0;
      state._kcLatePrepAt = 0;
      try {{
        parentWin.__kcPendingPlayingAck = null;
        parentWin.__kcPendingPlayingAckQueue = [];
        parentWin.__backingKeyCyclePassConsumed = null;
      }} catch (eAck) {{}}
      try {{ clearHandoffCookie(); }} catch (eC) {{}}
      try {{
        const a0 = parentDoc.getElementById('kc-buf-0');
        const a1 = parentDoc.getElementById('kc-buf-1');
        if (a0) {{
          a0.pause();
          if (opts.seekZero) {{ try {{ a0.currentTime = 0; }} catch (eZ0) {{}} }}
        }}
        if (a1) {{
          a1.pause();
          if (opts.seekZero) {{ try {{ a1.currentTime = 0; }} catch (eZ1) {{}} }}
        }}
      }} catch (eP) {{}}
    }}
    parentWin.__kcHardStop = function () {{
      const t0 = Number(parentWin.__kcClickT0 || kcNow());
      abortTransportPlayback({{ seekZero: false }});
      parentWin.__kcLastStopMs = kcNow() - t0;
      try {{
        const act = activeAudio();
        parentWin.__kcLastStopT = act ? Number(act.currentTime || 0) : null;
      }} catch (eT) {{ parentWin.__kcLastStopT = null; }}
      try {{
        if (typeof parentWin.__kcSyncVisibleTransport === 'function') parentWin.__kcSyncVisibleTransport();
      }} catch (eV) {{}}
    }};
    // Seek dual-buffer clock while staying stopped — used when an explicit
    // hold is required. "Back to loop start" prefers __kcSeekAndPlay below.
    parentWin.__kcSeekKeepPaused = function (seconds) {{
      const t = Math.max(0, Number(seconds || 0));
      abortTransportPlayback({{ seekZero: false }});
      // Keep muted while stopped so a remount cannot briefly sound.
      try {{
        const a0 = parentDoc.getElementById('kc-buf-0');
        const a1 = parentDoc.getElementById('kc-buf-1');
        [a0, a1].forEach((el) => {{
          if (!el) return;
          try {{ el.pause(); }} catch (eP) {{}}
          try {{ el.muted = true; }} catch (eM) {{}}
          try {{ el.currentTime = t; }} catch (eT) {{}}
        }});
      }} catch (eBuf) {{}}
      try {{ parentWin.__kcFollowForceTime = t; }} catch (eF) {{}}
      try {{ parentWin.__kcLastSeekT = t; }} catch (eLS) {{}}
      // Do not force Resume to t=0 after an explicit loop-start seek.
      try {{ parentWin.__kcForceResumeFromStart = false; }} catch (eFr) {{}}
      try {{ restartChordFollow(t); }} catch (eR) {{}}
      try {{
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const doc = frame.contentDocument;
            if (!doc || !doc.querySelector('.live-follow-shell')) return;
            const live = doc.getElementById('live-audio');
            if (live) {{
              try {{ live.pause(); }} catch (eL) {{}}
            }}
            const win = frame.contentWindow;
            if (win && typeof win.__kcSyncHighlightAt === 'function') {{
              win.__kcSyncHighlightAt(t);
            }}
          }} catch (eI) {{}}
        }});
      }} catch (eIF) {{}}
      try {{
        if (typeof parentWin.__kcSyncVisibleTransport === 'function') parentWin.__kcSyncVisibleTransport();
      }} catch (eV) {{}}
      try {{
        const act = activeAudio();
        parentWin.__kcLastSeekT = act ? Number(act.currentTime || 0) : t;
      }} catch (eT2) {{ parentWin.__kcLastSeekT = t; }}
      return parentWin.__kcLastSeekT;
    }};
    // Seek to t within the CURRENT key's current arrangement, then play.
    // Used by Live Follow "Back to loop start" — never advances the cycle key.
    parentWin.__kcSeekAndPlay = function (seconds) {{
      const t = Math.max(0, Number(seconds || 0));
      try {{
        state.userPaused = false;
        parentWin.sessionStorage.setItem('kc_user_paused', '0');
      }} catch (eClr) {{}}
      try {{ parentWin.__kcForceResumeFromStart = false; }} catch (eFr) {{}}
      try {{ parentWin.__kcFollowForceTime = t; }} catch (eF) {{}}
      const act = activeAudio();
      if (act) {{
        try {{ act.pause(); }} catch (eP) {{}}
        try {{ act.currentTime = t; }} catch (eT) {{}}
        try {{ act.muted = false; act.volume = 1; }} catch (eUm) {{}}
        try {{ restartChordFollow(t); }} catch (eR) {{}}
        const myGen = state.playGen;
        const kick = () => {{
          if (!state.enabled || myGen !== state.playGen) return;
          try {{ act.muted = false; act.volume = 1; }} catch (eU2) {{}}
          const p = act.play();
          if (p && p.then) p.catch(() => {{}});
        }};
        if (act.readyState >= 2) kick();
        else {{
          act.addEventListener('canplay', kick, {{ once: true }});
          window.setTimeout(kick, 200);
        }}
      }}
      try {{
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const win = frame.contentWindow;
            if (win && typeof win.__kcSyncHighlightAt === 'function') {{
              win.__kcSyncHighlightAt(t);
            }}
          }} catch (eI) {{}}
        }});
      }} catch (eIF) {{}}
      // Leave Held in Streamlit so remounts do not re-pause.
      try {{
        parentWin.__kcProgrammaticResumeClick = true;
        const b = parentDoc.querySelector(
          '[class*="st-key-backing_key_cycle_pause_btn"] button'
        );
        if (b) {{
          const lab = String((b.innerText || b.textContent || '')).replace(/\\s+/g, ' ').trim();
          if (/^Resume$/i.test(lab)) b.click();
        }}
      }} catch (eB) {{}}
      window.setTimeout(() => {{
        try {{ parentWin.__kcProgrammaticResumeClick = false; }} catch (eC) {{}}
        try {{ syncVisibleTransport(); }} catch (eV) {{}}
      }}, 500);
      try {{ syncVisibleTransport(); }} catch (eV0) {{}}
      return t;
    }};
    parentWin.__kcRequestCycleResume = function () {{
      // Audible kick immediately, then click the cycle Resume so Streamlit
      // leaves Held (otherwise the next remount re-publishes paused).
      parentWin.__kcProgrammaticResumeClick = true;
      try {{
        state.userPaused = false;
        parentWin.sessionStorage.setItem('kc_user_paused', '0');
      }} catch (eClr) {{}}
      try {{
        if (typeof parentWin.__kcResumeAudio === 'function') parentWin.__kcResumeAudio();
      }} catch (eR) {{}}
      try {{
        const b = parentDoc.querySelector(
          '[class*="st-key-backing_key_cycle_pause_btn"] button'
        );
        // Always click — label can lag "Pause" while Streamlit is still Held
        // after Back-to-loop-start seek; skipping the click left audio paused.
        if (b) {{
          b.click();
        }}
      }} catch (eB) {{}}
      window.setTimeout(() => {{
        try {{ parentWin.__kcProgrammaticResumeClick = false; }} catch (eC) {{}}
        try {{ syncVisibleTransport(); }} catch (eV) {{}}
      }}, 800);
    }};
    parentWin.__kcPauseAudio = function () {{
      abortTransportPlayback({{ seekZero: false }});
      try {{
        const a0 = parentDoc.getElementById('kc-buf-0');
        const a1 = parentDoc.getElementById('kc-buf-1');
        [a0, a1].forEach((el) => {{
          if (!el) return;
          try {{ el.pause(); }} catch (eP) {{}}
          // Keep muted so a remount cannot briefly double-hear before hold applies.
          try {{ el.muted = true; }} catch (eM) {{}}
        }});
      }} catch (eAll) {{}}
      try {{ silenceLeadSheetIframes(false); }} catch (eLS) {{}}
      try {{ syncVisibleTransport(); }} catch (eV) {{}}
    }};
    parentWin.__kcResumeAudio = function () {{
      const t0 = parentWin.__kcClickT0 || kcNow();
      cancelPendingPlays();
      state.userPaused = false;
      try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS) {{}}
      const act = activeAudio();
      if (!act) return;
      // Fresh-session Resume often has empty buffers; load last known URL.
      try {{
        const want = String(
          state.playingUrl
          || (parentWin.__kcLastCmd && parentWin.__kcLastCmd.currentUrl)
          || ''
        ).trim();
        const have = String(act.currentSrc || act.src || '').trim();
        if (want && (!have || (state.playingUrl && want !== state.playingUrl))) {{
          act.setAttribute('data-kc-url', want);
          act.preload = 'auto';
          act.src = want;
          state.playingUrl = want;
          act.load();
        }}
      }} catch (eSrc) {{}}
      // Restore Back-to-loop-start / Stop position. Only force t=0 when
      // explicitly requested (refresh-resume / restart), not after a seek.
      try {{
        const seekT = Number(parentWin.__kcLastSeekT);
        if (parentWin.__kcForceResumeFromStart) {{
          act.currentTime = 0;
          parentWin.__kcForceResumeFromStart = false;
          parentWin.__kcFollowForceTime = 0;
        }} else if (isFinite(seekT) && seekT >= 0) {{
          act.currentTime = seekT;
          parentWin.__kcFollowForceTime = seekT;
        }}
      }} catch (eSeek) {{}}
      try {{ act.muted = false; act.volume = 1; }} catch (eU) {{}}
      const myGen = state.playGen;
      const kick = () => {{
        if (myGen !== state.playGen) return;
        try {{ act.muted = false; act.volume = 1; }} catch (eU2) {{}}
        const p = act.play();
        if (!act.paused) {{
          parentWin.__kcLastResumeMs = kcNow() - t0;
          parentWin.__kcLastResumeT = Number(act.currentTime || 0);
          try {{ delete parentWin.__kcFollowForceTime; }} catch (eD) {{ parentWin.__kcFollowForceTime = null; }}
        }}
        const note = () => {{
          if (parentWin.__kcLastResumeMs == null) {{
            parentWin.__kcLastResumeMs = kcNow() - t0;
            parentWin.__kcLastResumeT = Number(act.currentTime || 0);
          }}
          try {{
            restartChordFollow(Number(act.currentTime || 0));
          }} catch (eRF2) {{}}
        }};
        if (p && p.then) {{
          p.then(() => {{
            try {{ act.muted = false; act.volume = 1; }} catch (eU3) {{}}
            note();
          }}).catch(() => {{
            try {{ act.muted = true; }} catch (eM) {{}}
            const pm = act.play();
            if (pm && pm.then) {{
              pm.then(() => {{
                try {{ act.muted = false; act.volume = 1; }} catch (eU4) {{}}
                note();
              }}).catch(note);
            }} else note();
          }});
        }} else note();
      }};
      if (act.readyState >= 2) kick();
      else {{
        act.addEventListener('canplay', kick, {{ once: true }});
        window.setTimeout(kick, 300);
        window.setTimeout(kick, 1200);
      }}
      try {{
        restartChordFollow(Number(act.currentTime || 0));
      }} catch (eRF) {{}}
      try {{ syncVisibleTransport(); }} catch (eV) {{}}
      window.setTimeout(() => {{
        try {{ syncVisibleTransport(); }} catch (eV2) {{}}
      }}, 400);
      try {{ syncVisibleTransport(); }} catch (eV) {{}}
    }};
    function noteAudioResp(kind, extra) {{
      const t0 = Number(parentWin.__kcClickT0 || kcNow());
      const row = Object.assign({{
        kind: kind,
        audioMs: kcNow() - t0,
        t: kcNow(),
      }}, extra || {{}});
      parentWin.__kcRespLog = parentWin.__kcRespLog || [];
      parentWin.__kcRespLog.push(row);
      if (parentWin.__kcRespLog.length > 30) {{
        parentWin.__kcRespLog = parentWin.__kcRespLog.slice(-30);
      }}
      return row;
    }}
    parentWin.__kcSwitchPrepared = function (delta) {{
      const now = kcNow();
      // Stacked bridge listeners must not turn one Next into several steps.
      if (now - Number(parentWin.__kcSwitchAt || 0) < 350) return false;
      parentWin.__kcSwitchAt = now;
      const t0 = parentWin.__kcClickT0 || now;
      const chips = [...parentDoc.querySelectorAll('.ui-key-cycle-chip[data-key]')];
      const keys = [];
      chips.forEach((el) => {{
        const k = (el.getAttribute('data-key') || '').trim();
        if (k && keys.indexOf(k) < 0) keys.push(k);
      }});
      if (!keys.length) {{
        parentWin.__kcLastSwitch = {{ ok: false, reason: 'no_chips', audioMs: null, hitKind: 'cold', target: '' }};
        return false;
      }}
      const bufs = ['kc-buf-0', 'kc-buf-1']
        .map((id) => parentDoc.getElementById(id))
        .filter(Boolean);
      const playing = bufs.find((a) => a && !a.paused && Number(a.currentTime || 0) > 0.05);
      const act0 = playing || activeAudio();
      const audible = String(
        (act0 && act0.getAttribute('data-kc-sounding'))
        || parentWin.__kcAudibleHold
        || parentWin.__kcLastSounding
        || ''
      ).trim();
      let idx = audible ? keys.indexOf(audible) : -1;
      if (idx < 0) {{
        const on = chips.find((el) => el.classList.contains('ui-key-cycle-chip-on') || el.getAttribute('data-current') === '1');
        const onKey = on ? String(on.getAttribute('data-key') || '').trim() : '';
        idx = onKey ? keys.indexOf(onKey) : -1;
      }}
      if (idx < 0) idx = 0;
      const target = keys[(idx + delta + keys.length) % keys.length];
      parentWin.__kcLastSwitch = {{ ok: false, target: target, hitKind: 'pending', audioMs: null, paused: true }};
      const matchSounding = (el) => el && String(el.getAttribute('data-kc-sounding') || '').trim() === target
        && (el.getAttribute('src') || el.currentSrc || el.src || el.getAttribute('data-kc-url'));
      const pool = ['kc-buf-0', 'kc-buf-1', 'kc-prep-next', 'kc-prep-prev', 'kc-prep-follow', 'kc-prep-ahead']
        .map((id) => parentDoc.getElementById(id))
        .concat([...parentDoc.querySelectorAll('audio[id^="kc-park-"]')])
        .filter(Boolean);
      let el = null;
      let hitKind = 'cold';
      const soundingOf = (a) => matchSounding(a);
      pool.forEach((a) => {{
        if (!el && soundingOf(a) && Number(a.readyState || 0) >= 2 && Number(a.currentTime || 0) < 1.25) {{
          el = a;
          hitKind = 'buffer';
        }}
      }});
      if (!el) {{
        pool.forEach((a) => {{
          if (!el && soundingOf(a) && Number(a.readyState || 0) >= 2) {{
            el = a;
            hitKind = 'buffer';
          }}
        }});
      }}
      if (!el) {{
        // Sounding attr may have been cleared by a remount; match by URL map.
        const map = parentWin.__kcUrlToKey || {{}};
        let wantUrl = '';
        Object.keys(map).forEach((u) => {{
          if (!wantUrl && String(map[u] || '').trim() === target) wantUrl = u;
        }});
        if (!wantUrl && String(state.nextSounding || '') === target) wantUrl = String(state.nextUrl || '');
        if (!wantUrl && String(state.followingSounding || '') === target) wantUrl = String(state.followingUrl || '');
        if (!wantUrl && String(state.prevSounding || '') === target) wantUrl = String(state.prevUrl || '');
        if (!wantUrl && String(state.aheadSounding || '') === target) wantUrl = String(state.aheadUrl || '');
        if (wantUrl) {{
          pool.forEach((a) => {{
            if (!el && urlsMatch(a, wantUrl) && Number(a.readyState || 0) >= 2) {{
              el = a;
              hitKind = 'buffer';
              try {{ a.setAttribute('data-kc-sounding', target); }} catch (eM) {{}}
            }}
          }});
        }}
      }}
      if (!el) {{
        pool.forEach((a) => {{
          if (!el && matchSounding(a)) {{
            el = a;
            hitKind = 'url';
          }}
        }});
      }}
      let url = '';
      if (!el) {{
        const map = parentWin.__kcUrlToKey || {{}};
        Object.keys(map).forEach((u) => {{
          if (!url && String(map[u] || '').trim() === target) url = u;
        }});
        if (!url && String(state.nextSounding || '') === target) url = String(state.nextUrl || '');
        if (!url && String(state.followingSounding || '') === target) url = String(state.followingUrl || '');
        if (!url && String(state.prevSounding || '') === target) url = String(state.prevUrl || '');
        if (!url && String(state.aheadSounding || '') === target) url = String(state.aheadUrl || '');
        if (url) {{
          hitKind = 'url';
          const idle = idleAudio();
          if (idle) {{
            armIdleFromUrl(idle, url, target, 'switch');
            el = idle;
          }}
        }}
      }}
      if (!el) {{
        parentWin.__kcLastSwitch = {{
          ok: false, reason: 'cold', target: target,
          audioMs: kcNow() - t0, hitKind: 'cold',
        }};
        noteAudioResp('key', parentWin.__kcLastSwitch);
        return false;
      }}
      if (el.id && (el.id.indexOf('kc-prep-') === 0 || el.id.indexOf('kc-park-') === 0)) {{
        const idle = idleAudio();
        if (idle && idle !== el) {{
          const idleId = idle.id;
          const prepId = el.id;
          idle.removeAttribute('id');
          el.id = idleId;
          idle.id = prepId;
        }}
      }}
      parentDoc.querySelectorAll('audio[id^="kc-"]').forEach((other) => {{
        if (other && other !== el) {{
          try {{ other.pause(); }} catch (eO) {{}}
          if (other.id === 'kc-buf-0' || other.id === 'kc-buf-1') other.style.display = 'none';
        }}
      }});
      if (el.id === 'kc-buf-0' || el.id === 'kc-buf-1') {{
        el.style.display = 'block';
        el.controls = true;
        state.active = el.id === 'kc-buf-1' ? 1 : 0;
      }}
      state.playingUrl = el.getAttribute('data-kc-url') || el.src || '';
      state.userPaused = false;
      try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS) {{}}
      el.muted = false;
      try {{ el.volume = 1; }} catch (eV) {{}}
      // Next/Previous always start the new key at the first chord of the
      // selected loop/section — never inherit a mid-pass or warm-buffer time.
      try {{ el.currentTime = 0; }} catch (eZ) {{}}
      try {{ parentWin.__kcFollowForceTime = 0; }} catch (eF0) {{}}
      const finish = () => {{
        const audioMs = kcNow() - t0;
        parentWin.__kcLastSwitch = {{
          ok: !el.paused,
          target: target,
          hitKind: hitKind,
          audioMs: audioMs,
          paused: !!el.paused,
          t: Number(el.currentTime || 0),
          src: String(el.getAttribute('data-kc-url') || el.src || '').slice(-48),
          readyState: Number(el.readyState || 0),
        }};
        noteAudioResp('key', parentWin.__kcLastSwitch);
        try {{
          parentWin.__kcAudibleHold = target;
          parentWin.__kcLastSounding = target;
          syncHighlight(target);
          const charts = parentWin.__kcChartByKey || {{}};
          let chart = charts[target] || '';
          if (!chart && String(state.nextSounding || '') === target) chart = state.nextChartHtml || '';
          if (!chart && String(state.prevSounding || '') === target) chart = state.prevChartHtml || '';
          if (!chart && String(state.followingSounding || '') === target) chart = state.followingChartHtml || '';
          if (!chart && String(state.aheadSounding || '') === target) chart = state.aheadChartHtml || '';
          if (chart) applyLeadSheetHtml(chart, target);
          try {{ restartChordFollow(0); }} catch (eRF0) {{}}
          try {{
            parentDoc.querySelectorAll('iframe').forEach((frame) => {{
              try {{
                const win = frame.contentWindow;
                if (win && typeof win.__kcRestartChordFollow === 'function') {{
                  win.__kcRestartChordFollow(0);
                }}
              }} catch (eI) {{}}
            }});
          }} catch (eIF) {{}}
          // Retarget neighbors from the key we just made audible so natural
          // handoff does not keep the previous next (often the same key).
          const ti = keys.indexOf(target);
          if (ti >= 0) {{
            const urlFor = (k) => {{
              const map = parentWin.__kcUrlToKey || {{}};
              let found = '';
              Object.keys(map).forEach((u) => {{
                if (!found && String(map[u] || '').trim() === k) found = u;
              }});
              return found;
            }};
            const nKey = keys[(ti + 1) % keys.length];
            const pKey = keys[(ti - 1 + keys.length) % keys.length];
            const fKey = keys[(ti + 2) % keys.length];
            const aKey = keys[(ti + 3) % keys.length];
            state.nextSounding = nKey;
            state.nextUrl = urlFor(nKey) || state.nextUrl;
            state.prevSounding = pKey;
            state.prevUrl = urlFor(pKey) || state.prevUrl;
            state.followingSounding = fKey;
            state.followingUrl = urlFor(fKey) || state.followingUrl;
            state.aheadSounding = aKey;
            state.aheadUrl = urlFor(aKey) || state.aheadUrl;
            if (charts[nKey]) state.nextChartHtml = charts[nKey];
            if (charts[fKey]) state.followingChartHtml = charts[fKey];
            if (charts[aKey]) state.aheadChartHtml = charts[aKey];
            try {{ ensureNeighborDecode(); }} catch (eDec) {{}}
          }}
        }} catch (eH) {{
          try {{ syncHighlight(target); }} catch (eH2) {{}}
        }}
      }};
      const p = el.play();
      if (!el.paused && Number(el.readyState || 0) >= 2) {{
        finish();
      }} else if (Number(el.readyState || 0) >= 2) {{
        if (p && p.then) p.then(finish).catch(finish);
        else finish();
      }} else {{
        el.addEventListener('playing', finish, {{ once: true }});
        if (p && p.catch) p.catch(() => {{}});
      }}
      return true;
    }};
    function silenceLeadSheetIframes(seekZero) {{
      try {{
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const doc = frame.contentDocument;
            if (!doc) return;
            const live = doc.getElementById('live-audio');
            if (live) {{
              live.pause();
              if (seekZero) {{ try {{ live.currentTime = 0; }} catch (eZ) {{}} }}
            }}
            doc.querySelectorAll('audio').forEach((a) => {{
              try {{
                a.pause();
                if (seekZero) {{ try {{ a.currentTime = 0; }} catch (eZ2) {{}} }}
              }} catch (eA) {{}}
            }});
          }} catch (eF) {{}}
        }});
      }} catch (eAll) {{}}
    }}
    const _abortTransportPlaybackInner = abortTransportPlayback;
    abortTransportPlayback = function (opts) {{
      _abortTransportPlaybackInner(opts);
      silenceLeadSheetIframes(!!(opts && opts.seekZero));
    }};
    // Capture-phase: Pause / Resume / Stop silence dual-buffer immediately.
    function syncVisibleTransport() {{
      let paused = false;
      try {{ paused = !!(parentWin.__kcDual && parentWin.__kcDual.userPaused); }} catch (eU) {{}}
      try {{ paused = paused || parentWin.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eS) {{}}
      // User Pause/Stop intent wins. Otherwise any unmuted playing buffer means
      // audible playback — do not trust only activeAudio() (wrong buffer mid-swap).
      let anyPlaying = false;
      try {{
        const a0 = parentDoc.getElementById('kc-buf-0');
        const a1 = parentDoc.getElementById('kc-buf-1');
        anyPlaying = [a0, a1].some((a) => a && !a.paused && !a.muted
          && Number(a.volume || 0) > 0.01 && Number(a.currentTime || 0) > 0.05);
      }} catch (eA) {{ anyPlaying = false; }}
      // Audible playback clears a stale Pause latch (loop-start / resume kick).
      if (anyPlaying) {{
        try {{
          state.userPaused = false;
          parentWin.sessionStorage.setItem('kc_user_paused', '0');
        }} catch (eClr) {{}}
        paused = false;
      }} else if (!paused) {{
        paused = true;
      }}
      try {{ parentWin.__kcTransportPaused = !!paused; }} catch (eTP) {{}}
      const want = paused ? 'Resume' : 'Pause';
      const btn = parentDoc.querySelector('[class*="st-key-backing_key_cycle_pause_btn"] button');
      if (btn) {{
        const labelEl = btn.querySelector('p') || btn;
        const cur = String(labelEl.textContent || '').replace(/\\s+/g, ' ').trim();
        if (cur !== want) labelEl.textContent = want;
      }}
      // Live Follow-Along: Stop while playing, Resume when held (not Pause).
      try {{
        parentDoc.querySelectorAll('button').forEach((b) => {{
          const t = String(b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim();
          if (
            /^(⏸\\s*)?Pause playback$/i.test(t)
            || /^(▶\\s*)?Resume playback$/i.test(t)
            || /^■\\s*Stop playback$/i.test(t)
          ) {{
            const next = paused ? '▶ Resume playback' : '■ Stop playback';
            if (t !== next) {{
              const labelEl = b.querySelector('p') || b;
              labelEl.textContent = next;
            }}
          }}
        }});
      }} catch (eLive) {{}}
      // Keep Live Follow-Along Resume/Pause aligned with the playbar.
      try {{
        if (typeof parentWin.__kcSyncLeadSheetTransport === 'function') {{
          parentWin.__kcSyncLeadSheetTransport();
        }}
        parentDoc.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            const w = frame.contentWindow;
            if (w && typeof w.__kcSyncLeadSheetTransport === 'function') w.__kcSyncLeadSheetTransport();
            // Also call the iframe-local sync when exposed as syncStopResumeLabel alias.
            if (w && typeof w.parent !== 'undefined') {{
              try {{
                if (typeof w.__kcLeadSheetSyncTransport === 'function') w.__kcLeadSheetSyncTransport();
              }} catch (e2) {{}}
            }}
          }} catch (eI) {{}}
        }});
      }} catch (eLS) {{}}
    }}
    function enforceAudibleSurfaces() {{
      if (parentWin.__kcSyncing) return;
      parentWin.__kcSyncing = true;
      try {{
        syncVisibleTransport();
        // Only one dual-buffer element may be audible. Overlap after natural
        // handoff makes the next key sound faster/louder.
        try {{
          const a0 = parentDoc.getElementById('kc-buf-0');
          const a1 = parentDoc.getElementById('kc-buf-1');
          if (state.userPaused) {{
            // Pause coordination: keep every surface silent while held.
            try {{ abortTransportPlayback({{ seekZero: false }}); }} catch (eAP) {{}}
          }} else {{
            const act = activeAudio();
            [a0, a1].forEach((el) => {{
              if (!el || el === act) {{
                if (el && el === act) {{
                  try {{ el.muted = false; if (Number(el.volume || 0) < 0.05) el.volume = 1; }} catch (eU) {{}}
                }}
                return;
              }}
              // Idle may be muted warm-preload (ok) or accidentally unmuted.
              if (!el.paused && Number(el.currentTime || 0) > 0.02) {{
                try {{ el.pause(); }} catch (eP) {{}}
              }}
              if (!el.muted || Number(el.volume || 0) > 0.01) {{
                try {{ el.muted = true; el.volume = 0; }} catch (eM) {{}}
              }}
            }});
          }}
          // Lead-sheet iframe must not double the audible mix while cycling owns audio.
          // Muted preload elements are left alone; only unmuted playing audio is stopped.
          try {{
            parentDoc.querySelectorAll('iframe').forEach((frame) => {{
              try {{
                const doc = frame.contentDocument;
                if (!doc) return;
                doc.querySelectorAll('audio').forEach((a) => {{
                  try {{
                    if (!a.paused && !a.muted && Number(a.volume || 0) > 0.01
                        && Number(a.currentTime || 0) > 0.02) {{
                      a.pause();
                    }}
                  }} catch (eA) {{}}
                }});
              }} catch (eF) {{}}
            }});
          }} catch (eLS) {{}}
        }} catch (eOne) {{}}
        let hold = String(parentWin.__kcAudibleHold || '').trim();
        try {{
          const bufs = ['kc-buf-0', 'kc-buf-1']
            .map((id) => parentDoc.getElementById(id))
            .filter(Boolean);
          const playing = bufs.find((a) => a && !a.paused && Number(a.currentTime || 0) > 0.05);
          const act = playing || activeAudio();
          const live = act
            ? String(act.getAttribute('data-kc-sounding') || '').trim()
            : '';
          if (live) {{
            hold = live;
            parentWin.__kcAudibleHold = live;
            if (String(parentWin.__kcLastSounding || '') !== live) {{
              parentWin.__kcLastSounding = live;
            }}
          }}
        }} catch (eLive) {{}}
        if (!hold) return;
        const chip = parentDoc.querySelector('.ui-key-cycle-chip-on');
        const chipKey = chip ? String(chip.getAttribute('data-key') || '').trim() : '';
        const strong = parentDoc.querySelector('.ui-key-cycle-playbar strong');
        const strongKey = strong ? String(strong.textContent || '').trim() : '';
        if (chipKey !== hold || strongKey !== hold) {{
          try {{ syncHighlight(hold); }} catch (eH) {{}}
        }}
        if (String(parentWin.__kcSheetKey || '') === hold) return;
        const chart = (parentWin.__kcChartByKey || {{}})[hold];
        if (chart) {{
          try {{ applyLeadSheetHtml(chart, hold); }} catch (eC) {{}}
        }}
      }} catch (eE) {{}}
      finally {{ parentWin.__kcSyncing = false; }}
    }}
    parentWin.__kcSyncVisibleTransport = syncVisibleTransport;
    try {{
      parentWin.__kcOnTransportClick = function (ev) {{
        const path = (typeof ev.composedPath === 'function') ? ev.composedPath() : [];
        const raw = ev && ev.target;
        let t = raw && raw.nodeType === 1 ? raw : (raw && raw.parentElement);
        // Prefer composedPath so clicks inside Streamlit button chrome still match.
        for (let i = 0; i < path.length; i++) {{
          const el = path[i];
          if (el && el.nodeType === 1 && el.classList && (
            [...el.classList].some((c) => c.indexOf('st-key-backing_key_cycle_pause_btn') >= 0)
            || [...el.classList].some((c) => c.indexOf('st-key-stop_backing_btn') >= 0)
          )) {{
            t = el;
            break;
          }}
        }}
        if (!t || !t.closest) {{
          // Fallback: label match when Streamlit strips/relocates key classes.
          const btnHit = (path || []).find((el) => el && el.tagName === 'BUTTON')
            || (raw && raw.closest && raw.closest('button'));
          if (btnHit) {{
            const lab = (btnHit.innerText || btnHit.textContent || '').replace(/\\s+/g, ' ').trim();
            if (/^(⏸\\s*)?Pause$|^(▶\\s*)?Resume$/i.test(lab)
              || /Pause playback|Resume playback/i.test(lab)) {{
              // Do NOT stopPropagation — Streamlit must leave Held on Resume.
              if (typeof parentWin.__kcPauseBtnHandler === 'function') {{
                parentWin.__kcPauseBtnHandler(ev);
              }}
            }}
          }}
          return;
        }}
        const pauseRoot = t.closest('[class*="st-key-backing_key_cycle_pause_btn"]')
          || (t.classList && [...t.classList].some((c) => c.indexOf('st-key-backing_key_cycle_pause_btn') >= 0) ? t : null);
        if (pauseRoot) {{
          // pointerdown/mousedown/click all route here; __kcPauseBtnHandler
          // debounce collapses one gesture to a single Pause/Resume.
          // Do NOT stopPropagation — Streamlit must also leave Held/Running
          // or the next remount re-publishes paused (broke Resume after seek).
          if (typeof parentWin.__kcPauseBtnHandler === 'function') {{
            parentWin.__kcPauseBtnHandler(ev);
          }}
          return;
        }}
        const btn = t.closest('button') || (t.tagName === 'BUTTON' ? t : null);
        if (!btn) return;
        const label = (btn.innerText || btn.textContent || '').replace(/\\s+/g, ' ').trim();
        // Cycle Pause/Resume may render without a stable key class after remount.
        if (/^(⏸\\s*)?Pause$|^(▶\\s*)?Resume$/i.test(label)) {{
          if (typeof parentWin.__kcPauseBtnHandler === 'function') {{
            parentWin.__kcPauseBtnHandler(ev);
          }}
          return;
        }}
        const stopRoot = t.closest('[class*="st-key-stop_backing_btn"]');
        if (stopRoot || label === '■ Stop' || label.indexOf('■ Stop') === 0) {{
          parentWin.__kcClickT0 = kcNow();
          if (typeof parentWin.__kcHardStop === 'function') parentWin.__kcHardStop();
          return;
        }}
      }};
      parentWin.__kcPauseBtnHandler = function () {{
        const now = kcNow();
        // Document capture and the button capture both see one gesture.
        // A second call resumes immediately and made Pause look delayed.
        if (now - Number(parentWin.__kcPauseToggleAt || 0) < 500) return;
        parentWin.__kcPauseToggleAt = now;
        parentWin.__kcClickT0 = now;
        // Count before pause/resume so a throw cannot hide that the binding fired.
        parentWin.__kcPauseApplies = Number(parentWin.__kcPauseApplies || 0) + 1;
        try {{
          const st = parentWin.__kcDual || {{}};
          let stored = false;
          try {{ stored = parentWin.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eS) {{}}
          // Prefer the visible control label: after a fresh-session restore the
          // button says Resume but dual-state/sessionStorage may still look
          // "not paused", which previously called PauseAudio on Resume.
          let label = '';
          try {{
            const b = parentDoc.querySelector(
              '[class*="st-key-backing_key_cycle_pause_btn"] button'
            );
            label = String((b && (b.innerText || b.textContent)) || '')
              .replace(/\\s+/g, ' ').trim();
          }} catch (eL) {{}}
          const labelResume = /Resume/i.test(label);
          const labelPause = /Pause/i.test(label) && !labelResume;
          // Programmatic live-Resume must never flip to Pause mid-gesture.
          const prog = !!parentWin.__kcProgrammaticResumeClick;
          const wantResume = prog || labelResume || (!labelPause && !!(st.userPaused || stored));
          if (wantResume) {{
            if (typeof parentWin.__kcResumeAudio === 'function') parentWin.__kcResumeAudio();
          }} else {{
            if (typeof parentWin.__kcPauseAudio === 'function') parentWin.__kcPauseAudio();
            else if (typeof abortTransportPlayback === 'function') abortTransportPlayback({{ seekZero: false }});
            parentWin.__kcLastPauseMs = kcNow() - parentWin.__kcClickT0;
            const act = (typeof activeAudio === 'function') ? activeAudio() : null;
            parentWin.__kcLastPauseT = act ? Number(act.currentTime || 0) : null;
          }}
          try {{ syncVisibleTransport(); }} catch (eV) {{}}
        }} catch (eP) {{
          try {{ parentWin.__kcPauseErr = String((eP && eP.message) || eP); }} catch (eE) {{}}
        }}
      }};
      parentWin.__kcStopBtnHandler = function () {{
        parentWin.__kcClickT0 = kcNow();
        try {{
          if (typeof parentWin.__kcHardStop === 'function') parentWin.__kcHardStop();
          parentWin.__kcLastStopMs = kcNow() - parentWin.__kcClickT0;
        }} catch (eS) {{}}
      }};
      parentWin.__kcStepBtnHandler = function (ev) {{
        parentWin.__kcClickT0 = kcNow();
        const btn = ev && ev.currentTarget;
        const delta = btn && btn.__kcStepDelta ? Number(btn.__kcStepDelta) : 0;
        if (!delta) return;
        try {{
          if (typeof parentWin.__kcSwitchPrepared === 'function') {{
            parentWin.__kcSwitchPrepared(delta);
          }}
        }} catch (eStep) {{}}
      }};
      if (!parentWin.__kcStepBtnHandlerStable) {{
        parentWin.__kcStepBtnHandlerStable = function (ev) {{
          try {{
            if (typeof parentWin.__kcStepBtnHandler === 'function') {{
              parentWin.__kcStepBtnHandler(ev);
            }}
          }} catch (eH) {{}}
        }};
      }}
      if (!parentWin.__kcPauseBtnHandlerStable) {{
        parentWin.__kcPauseBtnHandlerStable = function (ev) {{
          try {{
            if (typeof parentWin.__kcPauseBtnHandler === 'function') {{
              parentWin.__kcPauseBtnHandler(ev);
            }}
          }} catch (eH) {{}}
        }};
      }}
      parentWin.__kcArmTransportHooks = function () {{
        try {{
          parentWin.__kcHookTick = Number(parentWin.__kcHookTick || 0) + 1;
          // Install capture in the parent main world. Cross-realm Function
          // listeners saw dispatchEvent but missed trusted Playwright/user mouse
          // clicks; page-main-world listeners see both.
          try {{
            if (!parentWin.__kcCaptureBound) {{
              parentWin.eval(
                'if(!window.__kcCaptureBound){{'
                + 'window.__kcTransportCaptureFn=function(ev){{'
                + 'try{{window.__kcTransportHeard=Number(window.__kcTransportHeard||0)+1;}}catch(eH){{}}'
                + 'try{{if(typeof window.__kcOnTransportClick==="function")'
                + 'window.__kcOnTransportClick(ev);}}catch(eC){{}}'
                + '}};'
                + 'var fn=window.__kcTransportCaptureFn;'
                + 'document.addEventListener("pointerdown",fn,true);'
                + 'document.addEventListener("mousedown",fn,true);'
                + 'document.addEventListener("click",fn,true);'
                + 'window.__kcCaptureBound=true;'
                + 'window.__kcOnTransportPointer=fn;'
                + '}}'
              );
            }}
            parentWin.__kcTransportBindInstalled = true;
            parentWin.__kcTransportBindVer = 10;
            parentWin.__kcTransportRebindTick = Number(parentWin.__kcTransportRebindTick || 0) + 1;
          }} catch (eRebind) {{
            try {{
              // Last resort: parent Function realm (synthetic-only in some Chromium builds).
              const doc = parentWin.document;
              if (!parentWin.__kcTransportCaptureFn) {{
                parentWin.__kcTransportCaptureFn = parentWin.Function(
                  'return function(ev){{'
                  + 'try{{window.__kcTransportHeard=Number(window.__kcTransportHeard||0)+1;}}catch(eH){{}}'
                  + 'try{{if(typeof window.__kcOnTransportClick==="function")'
                  + 'window.__kcOnTransportClick(ev);}}catch(eC){{}}'
                  + '}};'
                )();
              }}
              if (!parentWin.__kcCaptureBound) {{
                const fn = parentWin.__kcTransportCaptureFn;
                doc.addEventListener('pointerdown', fn, true);
                doc.addEventListener('mousedown', fn, true);
                doc.addEventListener('click', fn, true);
                parentWin.__kcCaptureBound = true;
                parentWin.__kcOnTransportPointer = fn;
              }}
            }} catch (eFb) {{}}
          }}
          const pauseBtn = parentDoc.querySelector(
            '[class*="st-key-backing_key_cycle_pause_btn"] button'
          );
          if (pauseBtn) {{
            try {{
              pauseBtn.removeEventListener('click', parentWin.__kcPauseBtnHandlerStable, true);
              pauseBtn.removeEventListener('click', parentWin.__kcPauseBtnHandler, true);
              pauseBtn.removeEventListener('pointerdown', parentWin.__kcPauseBtnHandlerStable, true);
              pauseBtn.removeEventListener('mousedown', parentWin.__kcPauseBtnHandlerStable, true);
              pauseBtn.removeEventListener('keydown', parentWin.__kcPauseKeyHandlerStable, true);
            }} catch (eR) {{}}
            // pointerdown + mousedown + keydown — click alone was ignored while
            // pointerdown was missing under Playwright mouse sequences.
            pauseBtn.addEventListener('pointerdown', parentWin.__kcPauseBtnHandlerStable, true);
            pauseBtn.addEventListener('mousedown', parentWin.__kcPauseBtnHandlerStable, true);
            if (!parentWin.__kcPauseKeyHandlerStable) {{
              parentWin.__kcPauseKeyHandlerStable = function (ev) {{
                const key = String((ev && ev.key) || '');
                if (key !== 'Enter' && key !== ' ') return;
                try {{ ev.preventDefault(); }} catch (eP) {{}}
                try {{
                  if (typeof parentWin.__kcPauseBtnHandler === 'function') {{
                    parentWin.__kcPauseBtnHandler(ev);
                  }}
                }} catch (eH) {{}}
              }};
            }}
            pauseBtn.addEventListener('keydown', parentWin.__kcPauseKeyHandlerStable, true);
            pauseBtn.__kcTransportHooked = true;
          }}
          parentDoc.querySelectorAll('button').forEach(function (btn) {{
            const label = (btn.innerText || btn.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!(label === '■ Stop' || label.indexOf('■ Stop') === 0) && !(btn.closest && btn.closest('[class*="st-key-stop_backing_btn"]'))) return;
            try {{
              btn.removeEventListener('click', parentWin.__kcStopBtnHandler, true);
            }} catch (eR2) {{}}
            btn.addEventListener('click', parentWin.__kcStopBtnHandler, true);
            btn.__kcStopHooked = true;
          }});
          [['backing_key_cycle_advance_btn', 1], ['backing_key_cycle_prev_btn', -1]].forEach(function (pair) {{
            const btn = parentDoc.querySelector('[class*="st-key-' + pair[0] + '"] button');
            if (!btn) return;
            btn.__kcStepDelta = pair[1];
            try {{
              btn.removeEventListener('click', parentWin.__kcStepBtnHandlerStable, true);
              btn.removeEventListener('click', parentWin.__kcStepBtnHandler, true);
            }} catch (eR3) {{}}
            btn.addEventListener('click', parentWin.__kcStepBtnHandlerStable, true);
          }});
        }} catch (eHook) {{}}
      }};
      try {{ parentWin.__kcArmTransportHooks(); }} catch (eArm0) {{}}
      // Parent-realm capture is owned by __kcArmTransportHooks / __kcCaptureBound.
      // Do not install a second iframe-realm document listener here — that path
      // missed ordinary Pause clicks even when events reached the document.
      const KC_TRANSPORT_BIND_VER = 10;
      if (Number(parentWin.__kcTransportBindVer || 0) !== KC_TRANSPORT_BIND_VER
          || !parentWin.__kcCaptureBound) {{
        try {{
          const prev = parentWin.__kcOnTransportPointer;
          if (typeof prev === 'function' && prev !== parentWin.__kcTransportCaptureFn) {{
            parentDoc.removeEventListener('pointerdown', prev, true);
            parentDoc.removeEventListener('mousedown', prev, true);
            parentDoc.removeEventListener('click', prev, true);
          }}
        }} catch (eRm) {{}}
        parentWin.__kcTransportBindVer = KC_TRANSPORT_BIND_VER;
        try {{ parentWin.__kcArmTransportHooks(); }} catch (eArm1) {{}}
        try {{
          const oldZ = parentDoc.getElementById('kc-transport-zfix');
          if (oldZ) oldZ.remove();
        }} catch (eZ0) {{}}
      }}
      if (!parentWin.__kcTransportUiBoot) {{
        parentWin.__kcTransportUiBoot = true;
        // Sticky + high z-index keeps Pause hittable while the chart follows.
        try {{
          if (!parentDoc.getElementById('kc-transport-zfix')) {{
            const style = parentDoc.createElement('style');
            style.id = 'kc-transport-zfix';
            style.textContent = [
              '[class*="st-key-backing_key_cycle_pause_btn"],',
              '[class*="st-key-backing_key_cycle_prev_btn"],',
              '[class*="st-key-backing_key_cycle_advance_btn"],',
              '[class*="st-key-backing_key_cycle_stop_btn"]{{',
              'position:sticky!important;top:3.25rem!important;',
              'z-index:1002!important;background:var(--background-color,#0e1117);}}',
              '[class*="st-key-backing_key_cycle_pause_btn"] button,',
              '[class*="st-key-backing_key_cycle_prev_btn"] button,',
              '[class*="st-key-backing_key_cycle_advance_btn"] button,',
              '[class*="st-key-backing_key_cycle_stop_btn"] button{{',
              'position:relative!important;z-index:1003!important;}}',
            ].join('');
            (parentDoc.head || parentDoc.documentElement).appendChild(style);
          }}
        }} catch (eZ) {{}}
        parentWin.setInterval(function () {{
          try {{
            if (typeof parentWin.__kcArmTransportHooks === 'function') {{
              parentWin.__kcArmTransportHooks();
            }}
            if (typeof parentWin.__kcPinTransportRow === 'function') {{
              parentWin.__kcPinTransportRow();
            }}
            enforceAudibleSurfaces();
          }} catch (eArm) {{}}
        }}, 200);
      }}
    }} catch (eBind) {{}}

    // Keep chord follow ticking even if the bridge iframe remounts.
    try {{
      if (!parentWin.__kcFollowWatchInstalled) {{
        parentWin.__kcFollowWatchInstalled = true;
        parentWin.setInterval(() => {{
          try {{
            if (!parentDoc.getElementById('kc-lead-sheet-host')) return;
            kcUpdateChordHighlight(false);
          }} catch (eW) {{}}
        }}, 120);
      }}
    }} catch (eInst) {{}}
    function doSeamlessSwap(idle, nextUrl) {{
      // Arrangement Play replace owns the active buffer until a real pass ends.
      try {{
        const guardUntil = Number(state.arrangementGuardUntil || 0);
        if (guardUntil > kcNow()) {{
          const actG = activeAudio();
          const playedG = actG ? Number(actG.currentTime || 0) : 0;
          const durG = actG ? Number(actG.duration || 0) : 0;
          const realPass = durG > 2 && playedG > 5 && playedG >= durG - 0.15;
          if (!realPass) {{
            try {{
              parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
              parentWin.__kcPlayDiag.push({{
                t: kcNow(),
                ev: 'swap_blocked_arrangement_guard',
                until: guardUntil,
                played: playedG,
              }});
            }} catch (eSGB) {{}}
            return;
          }}
          state.arrangementGuardUntil = 0;
        }}
      }} catch (eSG) {{}}
      state.swapping = true;
      state.swapStartedAt = kcNow();
      // Keep _kcNearEndFired set until the new buffer is clearly past the
      // tail region — otherwise the watch re-fires and skips keys.
      // Do not pause the ended buffer — pause() can disrupt subsequent autoplay.
      const fromKey = String(parentWin.__kcLastSounding || '');
      let sounding = String(state.nextSounding || '');
      let chartHtml = String(state.nextChartHtml || '');
      let nextTl = Array.isArray(state.nextFollowTimeline) ? state.nextFollowTimeline : [];
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
          // Prefer a previously prepared lead-sheet for this sounding key.
          try {{
            chartHtml = String(state.nextChartHtml || state.currentChartHtml || '');
          }} catch (eCh) {{ chartHtml = ''; }}
        }}
        if ((!nextTl || !nextTl.length) && sounding && parentWin.__kcTimelineByKey) {{
          const cached = parentWin.__kcTimelineByKey[String(sounding)];
          if (Array.isArray(cached) && cached.length) nextTl = cached;
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
      // Build the full next chart off-screen BEFORE buffer flip / play so the
      // audible-start commit is a promote, not a cold innerHTML parse.
      try {{
        stageNextChart(chartHtml, playingKeyAtFlip || sounding || '');
      }} catch (eSt) {{}}
      state.active = state.active === 0 ? 1 : 0;
      const now = activeAudio();
      const other = idleAudio();
      now.style.display = 'block';
      if (other) other.style.display = 'none';
      // Silence the outgoing buffer BEFORE unmuting the incoming one — otherwise
      // both kc-buf elements are unmuted+playing for a detectable window.
      try {{
        if (other) {{
          try {{ other.pause(); }} catch (eOP) {{}}
          other.muted = true;
          try {{ other.volume = 0; }} catch (eOV) {{}}
        }}
      }} catch (eSil) {{}}
      // If parent warm-started this buffer muted, reset to 0 then unmute so
      // opening notes / count-in are never skipped by muted pre-roll.
      let warmLive = false;
      try {{
        if (now && state._kcWarmStarted) {{
          const ctBefore = Number(now.currentTime || 0);
          try {{ now.pause(); }} catch (ePs) {{}}
          try {{ now.currentTime = 0; }} catch (eZ) {{}}
          now.muted = false;
          now.volume = 1;
          now.loop = false;
          try {{ now.play(); }} catch (eWp) {{}}
          warmLive = true;
          state._kcWarmStarted = false;
          const unmuteAt = kcNow();
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: unmuteAt,
              ev: 'warm_promote_unmute',
              id: now.id,
              ctBefore: ctBefore,
              ct: Number(now.currentTime || 0),
              paused: !!now.paused,
              muted: !!now.muted,
            }});
            parentWin.__kcLastWarmUnmute = {{
              t: unmuteAt,
              ct: Number(now.currentTime || 0),
              ctBefore: ctBefore,
              id: now.id,
            }};
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
            // Keep the idle element intact when +2 is not ready yet — late prep
            // / fragment push will arm it. Clearing src here left nextReady=0
            // and blocked the next natural advance after loops>1 passes.
            try {{
              other.pause();
              other.removeAttribute('data-kc-sounding');
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
          // Cold swap: idle may never have been armed (nextReady stayed 0). Load now.
          if (!urlsMatch(now, nextUrl)) {{
            now.preload = 'auto';
            now.src = nextUrl;
            try {{ now.load(); }} catch (eLdN) {{}}
          }}
        }}
      }} catch (e) {{}}
      // Publish flip identity only — chart+highlight commit with audible start
      // (commitVisualSync) so a late play() cannot leave ~800ms of new audio
      // under the previous key's chart.
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
        }} catch (e) {{}}
      }}
      // Suppress stale ended echoes on the buffer we just left (not the new active).
      // Also abort the outgoing buffer's decoder — Chromium stalls the new play()
      // for ~1.5–3s when the just-ended element still holds a decoded WAV.
      // Never strip src from a buffer that still holds the live playingUrl
      // (arrangement replace can leave the new WAV on the outgoing slot if
      // active/idle flipped under a stale handoff).
      try {{
        if (other) {{
          other.__kcIgnoreEndedUntil = kcNow() + 4000;
          try {{ other.pause(); }} catch (eP) {{}}
          const otherUrl = String(other.getAttribute('data-kc-url') || other.src || '');
          const protectPlaying = !!(
            state.playingUrl
            && otherUrl
            && (otherUrl === state.playingUrl || urlsMatch(other, state.playingUrl))
          );
          if (!protectPlaying) {{
            try {{
              other.removeAttribute('src');
              other.removeAttribute('data-kc-url');
              other.load();
            }} catch (eL) {{}}
          }}
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
      let visualsCommitted = false;
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
      // Apply prepared next chart + highlight at the same clock tick as audible
      // start — never leave new audio under the previous key's chart.
      const commitVisualSync = (playingKey) => {{
        if (visualsCommitted) return;
        const key = String(playingKey || resolveSounding() || '');
        if (!key) return;
        let html = String(chartHtml || '').trim();
        try {{
          const mapped = parentWin.__kcChartByKey && parentWin.__kcChartByKey[key];
          if (mapped && String(mapped).trim()) html = String(mapped).trim();
        }} catch (eMap2) {{}}
        // Swap Current/Next Chord to the new key's transposed timeline now —
        // not on a later Python remount (that left Bm chords under Cm audio).
        try {{
          let tl = nextTl;
          if ((!tl || !tl.length) && parentWin.__kcTimelineByKey) {{
            const cached = parentWin.__kcTimelineByKey[key];
            if (Array.isArray(cached) && cached.length) tl = cached;
          }}
          if (Array.isArray(tl) && tl.length) {{
            setFollowTimeline(tl);
            state.currentFollowTimeline = tl;
            try {{
              parentWin.__kcTimelineByKey = parentWin.__kcTimelineByKey || {{}};
              parentWin.__kcTimelineByKey[key] = tl;
            }} catch (eTk) {{}}
          }} else {{
            // Never leave the previous key's Current/Next Chord timeline running
            // under the new sounding key when neighbor prep omitted a timeline.
            setFollowTimeline([]);
            state.currentFollowTimeline = [];
          }}
          // +1 buffer's timeline must track the following key, not the one we
          // just adopted (reusing nextTl left Am labels under the Gm pass).
          try {{
            state.nextFollowTimeline = [];
            const fk = String(followKey || state.nextSounding || '').trim();
            if (fk && parentWin.__kcTimelineByKey) {{
              const ftl = parentWin.__kcTimelineByKey[fk];
              if (Array.isArray(ftl) && ftl.length) state.nextFollowTimeline = ftl;
            }}
          }} catch (eNxt) {{}}
        }} catch (eTl) {{}}
        applyChartHtml(html, key);
        syncHighlight(key);
        try {{
          // New key audible now: restart highlighter at audio head (count-in aware).
          const act = activeAudio();
          const t0 = act ? Number(act.currentTime || 0) : 0;
          restartChordFollow(t0);
          parentDoc.querySelectorAll('iframe').forEach((frame) => {{
            try {{
              const win = frame.contentWindow;
              if (win && typeof win.__kcRestartChordFollow === 'function') {{
                win.__kcRestartChordFollow(t0);
              }}
            }} catch (eIR) {{}}
          }});
        }} catch (eRF) {{}}
        timing.chartAt = kcNow();
        state.chartMs = Math.max(0, timing.chartAt - (timing.playingAt || timing.endedAt));
        parentWin.__kcLastChartMs = state.chartMs;
        if (html) {{
          chartHtml = html;
          state.currentChartHtml = html;
        }}
        visualsCommitted = true;
        try {{
          parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
          parentWin.__kcPlayDiag.push({{
            t: timing.chartAt,
            ev: 'visual_sync',
            key: key,
            playingAt: timing.playingAt,
            endedAt: timing.endedAt,
            leadSheet: !!parentDoc.querySelector('.backing-chart-sheet, .lead-sheet'),
            hasRawGrid: !!parentDoc.querySelector('.kc-chart-full, #kc-full-chart-host, #kc-chart-live'),
          }});
        }} catch (eV) {{}}
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
        if (timing.playingAt == null) timing.playingAt = kcNow();
        commitVisualSync(playingKey);
        settled = true;
        state.handoffSettledToken = handoffToken;
        state.pendingHandoff = null;
        state._kcPlayInFlight = false;
        // Do NOT clear _onEndedGate here — a queued second ended callback would
        // immediately advance again. Gate is released on a timer after swap.
        sounding = playingKey;
        parentWin.__kcLastGapMs = gapMs;
        state.playingUrl = nextUrl;
        // next/following already promoted at buffer flip; arm idle decode now.
        armFollowingAfterPlay();
        state.swapping = false;
        state.passId = Number(state.passId || 0) + 1;
        if (timing.chartAt == null) timing.chartAt = kcNow();
        state.chartMs = Math.max(0, timing.chartAt - (timing.playingAt || timing.endedAt));
        parentWin.__kcLastChartMs = state.chartMs;
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
            warmUnmute: parentWin.__kcLastWarmUnmute || null,
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
            // Measured evidence only — no currentTime backdate as the gap clock.
            // If play() stalled and Chromium jumped well past the opening, rewind
            // so count-in / bar-1 are not skipped. Settle the playing ack FIRST
            // with the known flip key — waiting on a second play() after pause
            // was dropping the third natural ack when the bridge iframe died.
            if (ctNow > 1.0 && !settled && timing.playingAt == null) {{
              try {{
                parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
                parentWin.__kcPlayDiag.push({{
                  t: resolvedAt,
                  ev: 'play_ok_rewind_open',
                  id: now && now.id,
                  ctBefore: ctNow,
                }});
              }} catch (eRw) {{}}
              timing.playingAt = resolvedAt;
              const keyNow = resolveSounding() || playingKeyAtFlip || sounding;
              if (keyNow && !settled) {{
                commitVisualSync(keyNow);
                publishAck(Math.max(0, timing.playingAt - timing.endedAt));
              }}
              const afterRewind = () => {{
                if (state.handoffToken !== handoffToken) return;
                try {{
                  now.muted = false;
                  const p3 = now.play();
                  if (p3 && p3.catch) p3.catch(() => {{}});
                }} catch (eP3) {{}}
              }};
              try {{ now.pause(); }} catch (ePs) {{}}
              try {{ now.currentTime = 0; }} catch (eZ) {{}}
              try {{
                now.addEventListener('seeked', afterRewind, {{ once: true }});
              }} catch (eSk) {{}}
              kcSched(afterRewind, 60);
              return;
            }}
            if (timing.playingAt == null) {{
              timing.playingAt = resolvedAt;
            }}
            if (!settled) {{
              const keyNow = resolveSounding();
              if (keyNow) {{
                commitVisualSync(keyNow);
                publishAck(Math.max(0, timing.playingAt - timing.endedAt));
              }} else {{
                onPlaying();
              }}
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
        const key = resolveSounding();
        if (!key) {{
          // Never stamp playingAt / chart clocks without a key — that created
          // ~1.4s fake playingToChartMs when the key arrived later.
          soundingWait += 1;
          if (soundingWait < 60) {{
            kcSched(() => {{
              if (!settled && state.handoffToken === handoffToken) onPlaying();
            }}, 16);
          }}
          return;
        }}
        if (timing.playingAt == null) timing.playingAt = kcNow();
        commitVisualSync(key);
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
            muted: now ? !!now.muted : null,
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
    function isAtFinalCycleKey() {{
      try {{
        if (state.atFinalKey) return true;
        const seq = Array.isArray(state.sequence) ? state.sequence : [];
        if (!seq.length) return false;
        let cur = '';
        try {{
          const act = activeAudio();
          cur = String((act && act.getAttribute('data-kc-sounding')) || '').trim();
        }} catch (eA) {{}}
        if (!cur) cur = String(parentWin.__kcLastSounding || '').trim();
        if (!cur) return false;
        return cur === String(seq[seq.length - 1] || '').trim();
      }} catch (eF) {{ return !!state.atFinalKey; }}
    }}
    function expectedNextInSequence(curKey) {{
      try {{
        const seq = Array.isArray(state.sequence) ? state.sequence : [];
        const cur = String(curKey || '').trim();
        if (!seq.length || !cur) return '';
        const i = seq.indexOf(cur);
        if (i < 0) return '';
        if (i >= seq.length - 1) return '';
        return String(seq[i + 1] || '').trim();
      }} catch (eN) {{ return ''; }}
    }}
    function stopAtFinalKey(reason) {{
      // Final key finished — stay stopped. Manual Next wraps to the first key.
      try {{
        state.atFinalKey = true;
        state.ending = false;
        state.swapping = false;
        state.pendingHandoff = null;
        state.nextUrl = '';
        state.nextSounding = '';
        state.followingUrl = '';
        state.followingSounding = '';
        state.aheadUrl = '';
        state.aheadSounding = '';
        state.nextFollowTimeline = [];
        const idle = idleAudio();
        if (idle) {{
          try {{ idle.pause(); }} catch (eP) {{}}
          try {{
            idle.removeAttribute('src');
            idle.removeAttribute('data-kc-url');
            idle.removeAttribute('data-kc-sounding');
            idle.load();
          }} catch (eL) {{}}
        }}
        abortTransportPlayback({{ seekZero: false }});
        parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
        parentWin.__kcPlayDiag.push({{
          t: kcNow(),
          ev: 'final_key_stop',
          reason: String(reason || ''),
          key: String(parentWin.__kcLastSounding || ''),
        }});
        // Tell Python the pass finished so pause_key_cycle / final flags stick.
        try {{
          const fromKey = String(parentWin.__kcLastSounding || '');
          const ack = {{
            kind: 'final_key_stop',
            ackId: 'fks_' + Date.now().toString(36),
            cycleId: String(state.cycleId || ''),
            passId: Number(state.passId || 0),
            playingKey: fromKey,
            fromKey: fromKey,
            gapMs: 0,
            natural: true,
            passToken: state.passToken || '',
          }};
          parentWin.__kcPendingPlayingAck = ack;
          parentWin.__kcPendingPlayingAckQueue = parentWin.__kcPendingPlayingAckQueue || [];
          parentWin.__kcPendingPlayingAckQueue.push(ack);
          try {{
            const payload = encodeURIComponent(JSON.stringify(ack));
            parentDoc.cookie = 'kc_handoff=' + payload + '; path=/; SameSite=Lax';
          }} catch (eC) {{}}
        }} catch (eAck) {{}}
      }} catch (eStop) {{}}
      state._onEndedGate = false;
    }}
    function onEnded() {{
      if (!state.enabled) return;
      if (state.userPaused) return;
      try {{
        if (parentWin.sessionStorage.getItem('kc_user_paused') === '1') return;
      }} catch (eUP) {{}}
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
      // Final key: never seamless-swap to the wrap neighbor (first key).
      if (isAtFinalCycleKey()) {{
        state._onEndedGate = true;
        stopAtFinalKey('onEnded');
        return;
      }}
      // Natural advance must move exactly one sequence step. A stale nextUrl
      // (e.g. Am still armed while labels say Fm) caused Fm→Am skips.
      try {{
        const actCur = activeAudio();
        const curKey = String(
          (actCur && actCur.getAttribute('data-kc-sounding'))
          || parentWin.__kcLastSounding
          || ''
        ).trim();
        const expectNext = expectedNextInSequence(curKey);
        const armedNext = String(state.nextSounding || '').trim();
        if (curKey && !expectNext) {{
          state._onEndedGate = true;
          stopAtFinalKey('onEnded_no_expect_next');
          return;
        }}
        if (curKey && expectNext && armedNext && armedNext !== expectNext) {{
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: kcNow(),
              ev: 'onEnded_refuse_stale_next',
              curKey: curKey,
              expectNext: expectNext,
              armedNext: armedNext,
              nextUrl: String(state.nextUrl || '').slice(-40),
            }});
          }} catch (eStale) {{}}
          // Drop the wrong neighbor; wait for Python/prefetch to arm expectNext.
          state.nextUrl = '';
          state.nextSounding = '';
          // Fall through to trySwap which will wait for late prep.
        }}
        // Empty / unloaded buffers must not count as a completed pass.
        if (actCur && !(Number(actCur.duration || 0) > 2) && !actCur.ended) {{
          try {{
            parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
            parentWin.__kcPlayDiag.push({{
              t: kcNow(),
              ev: 'onEnded_ignore_no_duration',
              dur: Number(actCur.duration || 0),
              key: curKey,
            }});
          }} catch (eDur) {{}}
          state._onEndedGate = false;
          return;
        }}
      }} catch (eExp) {{}}
      // Explicit arrangement replace: ignore stale ended/prefetch swaps until
      // the new WAV has actually played a real pass (or the guard expires).
      try {{
        const guardUntil = Number(state.arrangementGuardUntil || 0);
        if (guardUntil > kcNow()) {{
          const actG = activeAudio();
          const playedG = actG ? Number(actG.currentTime || 0) : 0;
          const durG = actG ? Number(actG.duration || 0) : 0;
          const realPass = durG > 2 && playedG > 5 && playedG >= durG - 0.15;
          if (!realPass) {{
            try {{
              parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
              parentWin.__kcPlayDiag.push({{
                t: kcNow(),
                ev: 'onEnded_ignore_arrangement_guard',
                until: guardUntil,
                played: playedG,
                dur: durG,
              }});
            }} catch (eAGD) {{}}
            return;
          }}
          state.arrangementGuardUntil = 0;
        }}
      }} catch (eAG) {{}}
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
        if (attempt < 1800) {{
          // Up to ~90s for late neighbor prep (loops=2 Verse WAVs can finish
          // generating after the current pass ends). Abort on Off / Pause.
          if (!state.enabled || state.userPaused) {{
            state.ending = false;
            state._onEndedGate = false;
            return;
          }}
          try {{
            if (parentWin.sessionStorage.getItem('kc_user_paused') === '1') {{
              state.ending = false;
              state._onEndedGate = false;
              return;
            }}
          }} catch (eUP2) {{}}
          kcSched(() => trySwap(attempt + 1), 50);
          return;
        }}
        state.ending = false;
        state._onEndedGate = false;
        parentWin.__kcLastGapMs = null;
        clearHandoffCookie();
        try {{
          parentWin.__kcPlayDiag = parentWin.__kcPlayDiag || [];
          parentWin.__kcPlayDiag.push({{
            t: performance.now(),
            ev: 'late_prep_timeout',
            passToken: state.passToken || '',
            nextUrl: state.nextUrl || '',
          }});
        }} catch (eTo) {{}}
        // Explicit late-prep recovery via handoff channel (bridge button may be gone).
        try {{
          const fromKey = String(parentWin.__kcLastSounding || '');
          const ack = {{
            kind: 'late_prep_recover',
            ackId: 'lpr_' + Date.now().toString(36),
            cycleId: String(state.cycleId || ''),
            passId: Number(state.passId || 0),
            playingKey: fromKey,
            fromKey: fromKey,
            gapMs: 0,
            natural: true,
            passToken: state.passToken || '',
          }};
          parentWin.__kcPendingPlayingAck = ack;
          parentWin.__kcPendingPlayingAckQueue = parentWin.__kcPendingPlayingAckQueue || [];
          parentWin.__kcPendingPlayingAckQueue.push(ack);
          try {{
            const payload = encodeURIComponent(JSON.stringify(ack));
            parentDoc.cookie = 'kc_handoff=' + payload + '; path=/; SameSite=Lax';
          }} catch (eC) {{}}
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
          }} catch (eI) {{}}
        }} catch (eAck) {{
          clickBridge('late_prep_recover::' + (state.passToken || 'pass'));
        }}
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
        try {{ parentWin.__kcPendingPlayingAckQueue = []; }} catch (eQ) {{}}
        try {{ parentWin.__kcAckLog = []; }} catch (eA) {{}}
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
        state.swapping = false;
        state.ending = false;
        state.pendingHandoff = null;
        state._onEndedGate = false;
        state.swapStartedAt = 0;
        state._kcLatePrepAt = 0;
        state._kcWarmStarted = false;
        state.userPaused = false;
        state.cycleId = '';
        state.passId = 0;
        state.epoch = -1;
        state.handoffSettledToken = null;
        try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS0) {{}}
        teardownKeyCycleWatchers();
        if (detail) detail.textContent = 'Key cycling off';
        return;
      }}
      // Re-enable path: ensure durable watchers exist after an Off teardown.
      ensureKeyCycleWatchers();
      parentWin.__kcOnEnded = onEnded;
      // Accept any enable after Off (epoch was reset to -1). Reject only when
      // both sides are active and the command is strictly behind.
      if (
        cmd.epoch != null
        && Number(state.epoch) > -1
        && Number(cmd.epoch) < Number(state.epoch)
      ) {{
        try {{
          const bag = parentWin.__kcApplyTrace || (parentWin.__kcApplyTrace = []);
          bag.push({{
            t: Date.now(), reason: 'epoch_reject',
            epoch: cmd.epoch, stateEpoch: state.epoch,
            reload: !!cmd.arrangementReload,
            cur: String(cmd.currentUrl || '').slice(-28),
            sound: String(cmd.sounding || ''),
          }});
          if (bag.length > 40) bag.shift();
        }} catch (eEp) {{}}
        return; // stale
      }}
      state.enabled = true;
      state.epoch = Number(cmd.epoch || 0);
      state.passToken = String(cmd.passToken || 'pass');
      if (cmd.cycleId) {{
        const neuCycle = String(cmd.cycleId);
        if (state.cycleId && state.cycleId !== neuCycle) {{
          // New Python cycle after Off/On — drop prior-cycle handoff identity so
          // acks are not rejected as stale_cycle while audio keeps advancing.
          state.passId = 0;
          state.pendingHandoff = null;
          state.swapping = false;
          state.ending = false;
          state._onEndedGate = false;
          state.handoffSettledToken = null;
          state._kcLatePrepAt = 0;
          try {{
            parentWin.__kcPendingPlayingAck = null;
            parentWin.__kcPendingPlayingAckQueue = [];
            parentWin.__kcAckLog = [];
            parentWin.__backingKeyCyclePassConsumed = null;
          }} catch (eNC) {{}}
          clearHandoffCookie();
        }}
        state.cycleId = neuCycle;
      }}
      if (cmd.passId != null && Number(cmd.passId) >= Number(state.passId || 0)) {{
        state.passId = Number(cmd.passId);
      }}
      // Keep a single authoritative playbar; Streamlit can leave prior HTML fragments.
      try {{
        if (Array.isArray(cmd.sequence) && cmd.sequence.length) {{
          syncPlaybarSequence(
            cmd.sequence,
            cmd.sounding || '',
            Array.isArray(cmd.displaySequence) ? cmd.displaySequence : null
          );
          try {{
            const bar = pruneStalePlaybars();
            if (bar && cmd.chartMode) bar.setAttribute('data-chart-mode', String(cmd.chartMode));
            if (bar && Array.isArray(cmd.displaySequence)) {{
              bar.setAttribute('data-display-seq', cmd.displaySequence.join(','));
            }}
          }} catch (eMode) {{}}
        }} else {{
          pruneStalePlaybars();
        }}
      }} catch (eBar) {{}}
      // Stop / Pause own the audible buffer. Explicit arrangement Play is
      // handled after needsReplace is known (below) so a sticky arrangement
      // URL cannot clear a later Stop. Resume/restart always win over paused.
      if ((cmd.hardStop || cmd.paused) && !cmd.resume && !cmd.restart && !cmd.forcePlay) {{
        try {{ noteCmdNeighbors(cmd); }} catch (eNote1) {{}}
        abortTransportPlayback({{ seekZero: false }});
        if (detail) detail.textContent = cmd.hardStop ? 'Stopped' : 'Paused';
        return;
      }}
      if (cmd.restart || cmd.resume) {{
        cancelPendingPlays();
        state.userPaused = false;
        try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS) {{}}
        state.pendingHandoff = null;
        state.swapping = false;
        state.ending = false;
        state._onEndedGate = false;
        state.atFinalKey = false;
        const actR0 = activeAudio();
        const curR = String(cmd.currentUrl || '').trim();
        const sameUrl = !!(actR0 && curR && urlsMatch(actR0, curR));
        // Resume of the SAME pass: keep audible buffer if already playing that URL.
        // Restart (Manual Next / Play cycle restart) MUST load cmd.currentUrl at t=0
        // even when the prior key is still playing — otherwise labels say Fm while
        // Am audio keeps running (Fm→Am "skip" on the next natural end).
        if (cmd.resume && !cmd.restart && actR0 && !actR0.paused && sameUrl) {{
          try {{ actR0.muted = false; actR0.volume = 1; }} catch (eKeep) {{}}
          if (detail) detail.textContent = 'Resumed';
          try {{ noteCmdNeighbors(cmd); }} catch (eNoteKeep) {{}}
          return;
        }}
        const actR = actR0 || activeAudio();
        if (actR) {{
          if (cmd.sounding) {{
            try {{ actR.setAttribute('data-kc-sounding', String(cmd.sounding)); }} catch (eSk) {{}}
            try {{ parentWin.__kcLastSounding = String(cmd.sounding); }} catch (eLs) {{}}
            try {{ syncHighlight(String(cmd.sounding)); }} catch (eSh) {{}}
          }}
          if (curR && (!String(actR.currentSrc || actR.src || '').trim() || !urlsMatch(actR, curR))) {{
            try {{
              actR.setAttribute('data-kc-url', curR);
              actR.preload = 'auto';
              actR.src = curR;
              state.playingUrl = curR;
              actR.load();
            }} catch (eSrcR) {{}}
          }} else if (curR) {{
            state.playingUrl = curR;
          }}
          if (cmd.restart || Number(actR.currentTime || 0) < 0.35 || !sameUrl) {{
            try {{ actR.currentTime = 0; }} catch (eSeek) {{}}
          }}
          const myGen = state.playGen;
          try {{ actR.muted = false; actR.volume = 1; }} catch (eUmR) {{}}
          const kick = () => {{
            if (!state.enabled || myGen !== state.playGen) return;
            try {{ actR.muted = false; actR.volume = 1; }} catch (eUm2) {{}}
            const p = actR.play();
            if (p && p.then) {{
              p.then(() => {{
                try {{ actR.muted = false; actR.volume = 1; }} catch (eU) {{}}
                try {{ parentWin.__kcLastResumeMs = Date.now(); }} catch (eMs) {{}}
              }}).catch(() => {{
                if (myGen !== state.playGen) return;
                try {{ actR.muted = true; }} catch (eM) {{}}
                const pm = actR.play();
                if (pm && pm.then) {{
                  pm.then(() => {{
                    try {{ actR.muted = false; actR.volume = 1; }} catch (eU2) {{}}
                    try {{ parentWin.__kcLastResumeMs = Date.now(); }} catch (eMs2) {{}}
                  }}).catch(() => {{}});
                }}
              }});
            }}
          }};
          if (actR.readyState >= 2) kick();
          else {{
            actR.addEventListener('canplay', kick, {{ once: true }});
            window.setTimeout(kick, 300);
            window.setTimeout(kick, 1200);
          }}
          try {{
            restartChordFollow(cmd.restart || !sameUrl ? 0 : Number(actR.currentTime || 0));
          }} catch (eRF) {{}}
          try {{
            const bag = parentWin.__kcApplyTrace || (parentWin.__kcApplyTrace = []);
            bag.push({{
              t: Date.now(), reason: cmd.restart ? 'restart_load' : 'resume_kick',
              restart: !!cmd.restart, resume: !!cmd.resume,
              src: String(curR || '').slice(-28),
              sounding: String(cmd.sounding || ''),
              sameUrl: !!sameUrl,
              ready: Number(actR.readyState || 0),
              paused: !!actR.paused,
            }});
            if (bag.length > 40) bag.shift();
          }} catch (eTrR) {{}}
        }}
        if (detail) detail.textContent = cmd.restart ? 'Restarting…' : 'Resumed';
        try {{ noteCmdNeighbors(cmd); }} catch (eNoteR) {{}}
        return;
      }}
      // Mid-handoff: never remount/restart the active buffer — only refresh
      // prefetch fields and honor an explicit pause. Never regress the
      // already-promoted next/following/ahead queue (Python often still
      // carries the key we just flipped to as nextUrl, which was wiping Bb
      // and blocking warm-arm for the third natural transition).
      if ((state.swapping || state.pendingHandoff) && !cmd.paused && !cmd.hardStop && !cmd.restart) {{
        try {{
          const liveKey = String(
            parentWin.__kcLastSounding
            || (state.pendingHandoff && state.pendingHandoff.playingKey)
            || ''
          ).trim();
          const cmdNextKey = String(cmd.nextSounding || '').trim();
          const cmdFollowKey = String(cmd.followingSounding || '').trim();
          const cmdAheadKey = String(cmd.aheadSounding || '').trim();
          const curNextKey = String(state.nextSounding || '').trim();
          const curFollowKey = String(state.followingSounding || '').trim();
          // Accept next only when it advances past the live key and does not
          // clobber a newer browser-promoted next.
          if (cmd.nextUrl && cmdNextKey && cmdNextKey !== liveKey) {{
            if (!curNextKey || curNextKey === liveKey || curNextKey === cmdNextKey) {{
              state.nextUrl = String(cmd.nextUrl || '');
              state.nextSounding = cmdNextKey;
              if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
            }}
          }}
          if (cmd.followingUrl && cmdFollowKey
              && cmdFollowKey !== liveKey && cmdFollowKey !== cmdNextKey) {{
            if (!curFollowKey || curFollowKey === curNextKey || curFollowKey === cmdFollowKey) {{
              state.followingUrl = String(cmd.followingUrl || '');
              state.followingSounding = cmdFollowKey;
              if (cmd.followingChartHtml) state.followingChartHtml = String(cmd.followingChartHtml);
            }}
          }}
          if (cmd.aheadUrl && cmdAheadKey
              && cmdAheadKey !== liveKey
              && cmdAheadKey !== cmdNextKey
              && cmdAheadKey !== cmdFollowKey) {{
            state.aheadUrl = String(cmd.aheadUrl || '');
            state.aheadSounding = cmdAheadKey;
            if (cmd.aheadChartHtml) state.aheadChartHtml = String(cmd.aheadChartHtml);
          }}
          // Keep idle decode armed for the promoted next so warm can still fire.
          try {{
            const idleEl = idleAudio();
            if (idleEl && state.nextUrl
                && !urlsMatch(idleEl, state.nextUrl)
                && !(activeAudio() && urlsMatch(activeAudio(), state.nextUrl))) {{
              armIdleFromUrl(idleEl, state.nextUrl, state.nextSounding, 'next');
              state._kcWarmStarted = false;
            }}
          }} catch (eArmMid) {{}}
        }} catch (eH) {{}}
        return;
      }}
      const cur = String(cmd.currentUrl || '');
      const noteApply = (reason, extra) => {{
        try {{
          const row = {{
            t: Date.now(),
            reason: reason,
            epoch: cmd.epoch,
            reload: !!cmd.arrangementReload,
            cur: cur.slice(-28),
            actUrl: act ? String(act.getAttribute('data-kc-url') || '').slice(-28) : '',
            actSrc: act ? String(act.currentSrc || '').slice(-28) : '',
            dur: (act && isFinite(act.duration)) ? Math.round(act.duration * 10) / 10 : 0,
            sound: String(cmd.sounding || ''),
          }};
          if (extra) Object.assign(row, extra);
          const bag = parentWin.__kcApplyTrace || (parentWin.__kcApplyTrace = []);
          bag.push(row);
          if (bag.length > 40) bag.shift();
        }} catch (eN) {{}}
      }};
      const nxt = String(cmd.nextUrl || '');
      const follow = String(cmd.followingUrl || '');
      const ahead = String(cmd.aheadUrl || '');
      const act = activeAudio();
      const idle = idleAudio();
      // Capture armed next BEFORE cmd overwrites it — Manual Next sets
      // sounding=priorArmedNext while nextSounding advances to +2.
      const priorArmedNext = String(state.nextSounding || '').trim();
      try {{
        parentWin.__kcUrlToKey = parentWin.__kcUrlToKey || {{}};
        if (cur && cmd.sounding) parentWin.__kcUrlToKey[cur] = String(cmd.sounding);
        if (nxt && cmd.nextSounding) parentWin.__kcUrlToKey[nxt] = String(cmd.nextSounding);
        if (follow && cmd.followingSounding) parentWin.__kcUrlToKey[follow] = String(cmd.followingSounding);
        if (ahead && cmd.aheadSounding) parentWin.__kcUrlToKey[ahead] = String(cmd.aheadSounding);
        const prev = String(cmd.prevUrl || '');
        if (prev && cmd.prevSounding) {{
          parentWin.__kcUrlToKey[prev] = String(cmd.prevSounding);
          state.prevUrl = prev;
          state.prevSounding = String(cmd.prevSounding || '');
          if (cmd.prevChartHtml) {{
            parentWin.__kcChartByKey = parentWin.__kcChartByKey || {{}};
            parentWin.__kcChartByKey[String(cmd.prevSounding)] = String(cmd.prevChartHtml);
          }}
        }}
      }} catch (e) {{}}
      if (nxt) {{
        // Never point next at the URL already sounding after a seamless flip.
        if (!(act && urlsMatch(act, nxt)) && state.playingUrl !== nxt) {{
          state.nextUrl = nxt;
          if (cmd.nextSounding) state.nextSounding = String(cmd.nextSounding || '');
          if (cmd.nextChartHtml) state.nextChartHtml = String(cmd.nextChartHtml);
          if (Array.isArray(cmd.nextFollowTimeline) && cmd.nextFollowTimeline.length) {{
            state.nextFollowTimeline = cmd.nextFollowTimeline;
            try {{
              parentWin.__kcTimelineByKey = parentWin.__kcTimelineByKey || {{}};
              parentWin.__kcTimelineByKey[String(cmd.nextSounding || '')] = cmd.nextFollowTimeline;
            }} catch (eNT) {{}}
          }}
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
      try {{ ensureNeighborDecode(); }} catch (ePrep) {{}}
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
      // alreadyPlaying requires the live element to hold cur — not merely
      // state.playingUrl (sticky arrangement could set playingUrl early while
      // act still has the prior BPM/feel WAV, which rejected set_src).
      let alreadyPlaying = !!(cur && act && urlsMatch(act, cur));
      // Prefer live element URL over stale playingUrl during an in-flight handoff.
      if (cur && act && urlsMatch(act, cur)) {{
        state.playingUrl = cur;
      }}
      // Live seamless handoff owns the active buffer until Python's currentUrl
      // catches up. Prefetch fragment cmds often still carry the previous key.
      // Manual Next/Prev intentionally moves Python ahead to nextSounding — allow that.
      // Same-key arrangement replace (new BPM/feel/scope file) is NOT a handoff.
      let liveHandoff = false;
      let browserSounding = '';
      try {{
        const actUrl = act ? (act.getAttribute('data-kc-url') || '') : '';
        browserSounding = act
          ? String(act.getAttribute('data-kc-sounding') || parentWin.__kcLastSounding || '').trim()
          : String(parentWin.__kcLastSounding || '').trim();
        const cmdSounding = String(cmd.sounding || '').trim();
        const armedNext = String(state.nextSounding || '').trim();
        // Manual Next: cmd.sounding was the prior armed next (before this cmd
        // advanced nextSounding to +2). Also accept sequence-expected next.
        const expectFromBrowser = expectedNextInSequence(browserSounding);
        const intentionalAdvance = !!(
          cmd.restart
          || cmd.forcePlay
          || (cmdSounding && priorArmedNext && cmdSounding === priorArmedNext)
          || (cmdSounding && expectFromBrowser && cmdSounding === expectFromBrowser)
        );
        const pythonToArmedNext = !!(
          intentionalAdvance
          || (cmdSounding && armedNext && cmdSounding === armedNext)
        );
        const pythonMatchesBrowser = !!(
          cmdSounding && browserSounding && cmdSounding === browserSounding
        );
        const sameKeyNewFile = !!(
          pythonMatchesBrowser
          && cur
          && act
          && !urlsMatch(act, cur)
        );
        // In-flight seamless swap must own the active buffer — a stale Python
        // currentUrl must not remount over the key we just flipped to.
        // Do NOT treat Manual Next (Python ahead by one) as stale.
        liveHandoff = !!(
          act
          && state.enabled
          && !pythonToArmedNext
          && !sameKeyNewFile
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
              && cmdSounding !== priorArmedNext
              && cmdSounding !== String(state.followingSounding || '').trim()
              && (urlsMatch(act, state.playingUrl) || !!actUrl)
            )
            || (
              state.playingUrl
              && cur
              && state.playingUrl !== cur
              && !urlsMatch(act, cur)
              && (urlsMatch(act, state.playingUrl) || actUrl === state.playingUrl)
              && !pythonMatchesBrowser
            )
          )
        );
        if (intentionalAdvance) liveHandoff = false;
      }} catch (e) {{ liveHandoff = false; }}
      // Final-key latch: only when the audible buffer is the sequence last.
      // Lagging Python atFinalKey must not clear nextUrl under an earlier key.
      try {{
        const seq = Array.isArray(cmd.sequence) ? cmd.sequence : (state.sequence || []);
        const last = seq.length ? String(seq[seq.length - 1] || '').trim() : '';
        const cmdKey = String(cmd.sounding || '').trim();
        if (cmd.restart || cmd.forcePlay || (cmd.resume && !cmd.paused)) {{
          if (!(last && cmdKey && cmdKey === last)) state.atFinalKey = false;
        }}
        if (last && browserSounding && browserSounding === last) {{
          state.atFinalKey = true;
          const first = seq.length ? String(seq[0] || '').trim() : '';
          const ns = String(state.nextSounding || cmd.nextSounding || '').trim();
          if (!ns || (first && ns === first)) {{
            state.nextUrl = '';
            state.nextSounding = '';
            state.followingUrl = '';
            state.aheadUrl = '';
          }}
        }} else if (browserSounding && last && browserSounding !== last) {{
          state.atFinalKey = false;
        }} else if (cmd.atFinalKey && cmdKey && browserSounding && cmdKey === browserSounding) {{
          state.atFinalKey = true;
        }}
      }} catch (eFinCmd) {{}}
      noteApply('decide', {{
        live: !!liveHandoff,
        already: !!alreadyPlaying,
        browser: String(browserSounding || ''),
      }});
      // Explicit Play (BPM / feel / scope / loops) publishes a new file at the
      // current cycle key. That is not an automatic handoff, even when a later
      // command no longer carries the one-shot reload flag.
      const arrangeUrl = String(cmd.arrangementUrl || '');
      const forceArr = !!(cmd.forceArrangementReplace || cmd.arrangementReload);
      const elementMismatch = !!(act && cur && !urlsMatch(act, cur));
      const sameKey = !!(
        String(cmd.sounding || '').trim()
        && String(cmd.sounding || '').trim() === String(browserSounding || '').trim()
      );
      const needsReplace = !!(
        elementMismatch
        && (
          forceArr
          || sameKeyNewFile
          || cmd.restart
          || (arrangeUrl && (arrangeUrl === cur || !urlsMatch(act, arrangeUrl)))
          || (cmd.forcePlay && cmd.autoplay)
          || (cmd.autoplay && sameKey)
        )
      );
      if (needsReplace) {{
        noteApply('replace');
        liveHandoff = false;
        // Sticky arrangement may have set state.playingUrl to the new URL before
        // the active element has loaded it — do not treat that as alreadyPlaying
        // for chart/highlight (would skip applyLeadSheetHtml below).
        alreadyPlaying = !!(cur && act && urlsMatch(act, cur));
        state.swapping = false;
        state.pendingHandoff = null;
        state.ending = false;
        state._onEndedGate = false;
        state.forceFromStart = true;
        // Block stale onended/seamless swaps from clearing the buffer we are
        // about to load (BPM/feel/scope Play replace). Cleared after a real
        // mid-pass dwell or natural near-end of the new arrangement.
        try {{ state.arrangementGuardUntil = kcNow() + 28000; }} catch (eAG) {{
          state.arrangementGuardUntil = Date.now() + 28000;
        }}
        // New arrangement clears Stop hold so set_src can run — unless this
        // command is itself a Pause/Stop remount (cmd.paused). Clearing pause
        // here previously undid an in-flight Pause click.
        if (!(cmd.paused || cmd.hardStop)) {{
          state.userPaused = false;
          try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eAR) {{}}
        }}
        state.nextUrl = '';
        state.followingUrl = '';
        state.aheadUrl = '';
        state.prevUrl = '';
        try {{
          const idleR = idleAudio();
          if (idleR) {{
            idleR.pause();
            idleR.removeAttribute('src');
            idleR.removeAttribute('data-kc-url');
            idleR.load();
          }}
        }} catch (eIdle) {{}}
        // Preserve the one real live-follow sheet: refresh chart + restart
        // highlight at t=0 for the new arrangement audio (not a substitute host).
        try {{
          if (cmd.leadSheetOpen) {{
            adoptCmdFollowTimeline(cmd, String(cmd.sounding || ''));
            if (cmd.currentChartHtml) {{
              state.currentChartHtml = String(cmd.currentChartHtml);
              applyChartHtml(state.currentChartHtml, String(cmd.sounding || ''));
              applyLeadSheetHtml(String(cmd.currentChartHtml), String(cmd.sounding || ''));
            }}
            restartChordFollow(0);
          }}
        }} catch (eRepLS) {{}}
        // User Pause/Stop while a replacement is pending: still install the new
        // arrangement (src + timeline) then hold paused at the start — do not
        // return before set_src (that left empty/stale buffers).
        if ((cmd.paused || cmd.hardStop) && !cmd.resume && !cmd.restart && !cmd.forcePlay) {{
          try {{ noteCmdNeighbors(cmd); }} catch (eNoteP) {{}}
          if (cur && act && !urlsMatch(act, cur)) {{
            noteApply('set_src_paused_replace');
            cancelPendingPlays();
            act.setAttribute('data-kc-url', cur);
            act.preload = 'auto';
            act.src = cur;
            state.playingUrl = cur;
            try {{ act.load(); }} catch (eLoadP) {{}}
            try {{ act.currentTime = 0; }} catch (eSeekP) {{}}
            state.forceFromStart = false;
          }}
          abortTransportPlayback({{ seekZero: false }});
          if (detail) detail.textContent = cmd.hardStop ? 'Stopped' : 'Paused';
          return;
        }}
      }} else {{
        // Stop hold: only after we know this is not a buffer replace.
        let storedHold = false;
        try {{ storedHold = parentWin.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eHold) {{}}
        if ((state.userPaused || storedHold || cmd.paused) && !cmd.resume && !cmd.restart && !cmd.forcePlay) {{
          try {{
            const bag = parentWin.__kcApplyTrace || (parentWin.__kcApplyTrace = []);
            bag.push({{
              t: Date.now(), reason: 'pause_hold',
              reload: !!cmd.arrangementReload, force: !!cmd.forcePlay,
              auto: !!cmd.autoplay, epoch: cmd.epoch,
            }});
            if (bag.length > 40) bag.shift();
          }} catch (eHoldTr) {{}}
          try {{ noteCmdNeighbors(cmd); }} catch (eNote2) {{}}
          abortTransportPlayback({{ seekZero: false }});
          if (detail) detail.textContent = 'Paused';
          return;
        }}
      }}
      if (
        cmd.forcePlay
        && cmd.autoplay
        && !cmd.paused
        && Number(cmd.epoch || 0) !== Number(state.honoredForceEpoch)
      ) {{
        state.honoredForceEpoch = Number(cmd.epoch || 0);
        state.userPaused = false;
        try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eFP) {{}}
      }}
      try {{
        parentWin.__kcChartByKey = parentWin.__kcChartByKey || {{}};
        try {{
          if (cmd.sounding && cmd.currentChartHtml)
            parentWin.__kcChartByKey[String(cmd.sounding)] = String(cmd.currentChartHtml);
          if (cmd.nextSounding && cmd.nextChartHtml)
            parentWin.__kcChartByKey[String(cmd.nextSounding)] = String(cmd.nextChartHtml);
          if (cmd.followingSounding && cmd.followingChartHtml)
            parentWin.__kcChartByKey[String(cmd.followingSounding)] = String(cmd.followingChartHtml);
          if (cmd.aheadSounding && cmd.aheadChartHtml)
            parentWin.__kcChartByKey[String(cmd.aheadSounding)] = String(cmd.aheadChartHtml);
          if (cmd.prevSounding && cmd.prevChartHtml)
            parentWin.__kcChartByKey[String(cmd.prevSounding)] = String(cmd.prevChartHtml);
        }} catch (eMap) {{}}
        // Always remove the wrong parent host; real sheet is live-follow iframe.
        teardownLeadSheetHost();
        if (cmd.leadSheetOpen) {{
          // Seamless handoff owns the audible timeline until ack; a lagging
          // Python followTimeline (prior key) must not restore old labels.
          if (!liveHandoff) {{
            adoptCmdFollowTimeline(
              cmd,
              String(browserSounding || cmd.sounding || '')
            );
          }}
          // If a pending chart arrived before the iframe mounted, apply now.
          try {{
            const pending = parentWin.__kcPendingLeadSheetHtml;
            const pkey = parentWin.__kcPendingLeadSheetKey || cmd.sounding;
            if (pending) applyLeadSheetHtml(String(pending), String(pkey || ''));
          }} catch (ePend) {{}}
          try {{
            const act = activeAudio();
            restartChordFollow(act ? Number(act.currentTime || 0) : 0);
            parentDoc.querySelectorAll('iframe').forEach((frame) => {{
              try {{
                const win = frame.contentWindow;
                if (win && typeof win.__kcRestartChordFollow === 'function') {{
                  win.__kcRestartChordFollow(act ? Number(act.currentTime || 0) : 0);
                }}
              }} catch (eI) {{}}
            }});
          }} catch (eRF) {{}}
        }}
      }} catch (eLS0) {{}}
      // Do not push chart/highlight from Python when audio is already on this URL
      // or when a seamless handoff owns the live buffer. Browser confirmed key wins.
      // Exception: display-mode reproject (written/shape) refreshes strip + sheet
      // in place without touching audio identity.
      if (cmd.displayReproject) {{
        try {{
          syncPlaybarSequence(
            Array.isArray(cmd.sequence) ? cmd.sequence : [],
            cmd.sounding || state.sounding || '',
            Array.isArray(cmd.displaySequence) ? cmd.displaySequence : null
          );
        }} catch (eDispSeq) {{}}
        if (cmd.currentChartHtml) {{
          state.currentChartHtml = String(cmd.currentChartHtml);
          applyChartHtml(state.currentChartHtml, String(cmd.sounding || ''));
          try {{
            if (cmd.leadSheetOpen) {{
              applyLeadSheetHtml(String(cmd.currentChartHtml), String(cmd.sounding || ''));
            }}
          }} catch (eDispLS) {{}}
        }}
        try {{
          const actPos = activeAudio();
          if (cmd.leadSheetOpen && actPos) {{
            restartChordFollow(Number(actPos.currentTime || 0));
          }}
        }} catch (eDispCF) {{}}
      }}
      if (!alreadyPlaying && !liveHandoff) {{
        if (cmd.currentChartHtml) {{
          state.currentChartHtml = String(cmd.currentChartHtml);
          applyChartHtml(state.currentChartHtml, String(cmd.sounding || ''));
        }}
        try {{
          teardownLeadSheetHost();
          if (cmd.leadSheetOpen) {{
            adoptCmdFollowTimeline(cmd, String(cmd.sounding || browserSounding || ''));
            if (cmd.currentChartHtml) {{
              applyLeadSheetHtml(String(cmd.currentChartHtml), String(cmd.sounding || ''));
            }}
            restartChordFollow(0);
          }}
        }} catch (eLS) {{}}
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
        if (act && cmd.sounding) act.setAttribute('data-kc-sounding', String(cmd.sounding));
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
      // The audible element must carry the key that is actually playing.
      // Switch/proof logic reads data-kc-sounding; an empty attribute made
      // every Next look like a miss and retargeted prefetch before decode.
      if (act && !liveHandoff && cmd.sounding && (alreadyPlaying || urlsMatch(act, cur))) {{
        act.setAttribute('data-kc-sounding', String(cmd.sounding));
        if (!parentWin.__kcLastSounding) parentWin.__kcLastSounding = String(cmd.sounding);
      }} else if (act && !String(act.getAttribute('data-kc-sounding') || '').trim()) {{
        const stamped = String(parentWin.__kcLastSounding || '').trim();
        if (stamped) act.setAttribute('data-kc-sounding', stamped);
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
        // Always (re)arm when URL differs OR idle has no src yet (nextReady=0).
        const idleSrc = idle.getAttribute('src') || idle.src || '';
        if (idle.getAttribute('data-kc-url') !== nxt || !idleSrc) {{
          armIdleFromUrl(idle, nxt, state.nextSounding, 'next');
        }} else if (state.nextSounding) {{
          idle.setAttribute('data-kc-sounding', state.nextSounding);
          markBufferReady(idle, 'next');
        }}
      }};
      // Already sounding this URL (seamless handoff) — only refresh next buffer / pause.
      if ((alreadyPlaying || liveHandoff) && !needsReplace) {{
        noteApply('reject_handoff', {{live: !!liveHandoff, already: !!alreadyPlaying}});
        if (alreadyPlaying) state.playingUrl = cur;
        refreshIdleOnly();
        if (cmd.paused) {{
          cancelPendingPlays();
          state.userPaused = true;
          try {{ parentWin.sessionStorage.setItem('kc_user_paused', '1'); }} catch (eSS) {{}}
          try {{ if (act) act.pause(); }} catch (e) {{}}
          try {{
            const a0 = parentDoc.getElementById('kc-buf-0');
            const a1 = parentDoc.getElementById('kc-buf-1');
            if (a0) a0.pause();
            if (a1) a1.pause();
          }} catch (eP) {{}}
        }} else if (cmd.resume || (!liveHandoff && cmd.autoplay && act && act.paused)) {{
          let storedPaused = false;
          try {{ storedPaused = parentWin.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eSP) {{}}
          if (!cmd.resume && (state.userPaused || storedPaused)) {{
            cancelPendingPlays();
            try {{ if (act) act.pause(); }} catch (eHP) {{}}
            return;
          }}
          cancelPendingPlays();
          state.userPaused = false;
          try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS2) {{}}
          const myGen = state.playGen;
          if (act) {{
            // Pause mutes buffers; Resume / forcePlay must unmute or WAV is silent.
            // After long generate, unmuted play may reject — mute→play→unmute.
            try {{ act.muted = false; act.volume = 1; }} catch (eUmRH) {{}}
            const p = act.play();
            if (p && p.then) {{
              p.then(() => {{
                try {{ act.muted = false; act.volume = 1; }} catch (eU) {{}}
              }}).catch(() => {{
                if (myGen !== state.playGen) return;
                try {{ act.muted = true; }} catch (eM) {{}}
                const pm = act.play();
                if (pm && pm.then) {{
                  pm.then(() => {{
                    try {{ act.muted = false; act.volume = 1; }} catch (eU2) {{}}
                  }}).catch(() => {{}});
                }}
              }});
            }}
          }}
        }}
        return;
      }}
      if (cur && act) {{
        const same = urlsMatch(act, cur) && state.playingUrl === cur;
        if (!same) {{
          noteApply('set_src');
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
          if ((cmd.autoplay || cmd.forcePlay || forceArr || needsReplace) && !cmd.paused) {{
            const myGen = state.playGen;
            const tryPlay = () => {{
              if (!state.enabled || myGen !== state.playGen) return;
              if (state.forceFromStart) {{
                try {{ act.currentTime = 0; }} catch (e0) {{}}
                state.forceFromStart = false;
              }}
              // Play click's user-gesture is lost after a long generate. Unmuted
              // play() often rejects; mute→play→unmute matches handoff kick.
              const kickAudible = () => {{
                try {{ act.muted = false; act.volume = 1; }} catch (eUm) {{}}
                const p = act.play();
                if (p && p.then) {{
                  p.then(() => {{
                    try {{ act.muted = false; act.volume = 1; }} catch (eU2) {{}}
                  }}).catch(() => {{
                    try {{ act.muted = true; }} catch (eM) {{}}
                    const pm = act.play();
                    if (pm && pm.then) {{
                      pm.then(() => {{
                        try {{ act.muted = false; act.volume = 1; }} catch (eU3) {{}}
                      }}).catch(() => {{}});
                    }}
                  }});
                }}
              }};
              kickAudible();
            }};
            if (act.readyState >= 2) tryPlay();
            else {{
              act.addEventListener('canplay', tryPlay, {{ once: true }});
              window.setTimeout(tryPlay, 250);
            }}
          }} else if (state.forceFromStart) {{
            try {{ act.currentTime = 0; }} catch (e0b) {{}}
            state.forceFromStart = false;
          }}
        }} else if (cmd.paused) {{
          cancelPendingPlays();
          state.userPaused = true;
          try {{ parentWin.sessionStorage.setItem('kc_user_paused', '1'); }} catch (eSS3) {{}}
          try {{ act.pause(); }} catch (e) {{}}
          try {{
            const a0 = parentDoc.getElementById('kc-buf-0');
            const a1 = parentDoc.getElementById('kc-buf-1');
            if (a0) a0.pause();
            if (a1) a1.pause();
          }} catch (eP2) {{}}
        }} else if (cmd.autoplay || cmd.resume || forceArr) {{
          let storedPaused2 = false;
          try {{ storedPaused2 = parentWin.sessionStorage.getItem('kc_user_paused') === '1'; }} catch (eSP2) {{}}
          if (!cmd.resume && !forceArr && (state.userPaused || storedPaused2)) {{
            cancelPendingPlays();
            try {{ act.pause(); }} catch (eHP2) {{}}
          }} else {{
            cancelPendingPlays();
            state.userPaused = false;
            try {{ parentWin.sessionStorage.setItem('kc_user_paused', '0'); }} catch (eSS4) {{}}
            const myGen = state.playGen;
            try {{ act.muted = false; act.volume = 1; }} catch (eUm2) {{}}
            const p = act.play();
            if (p && p.then) {{
              p.then(() => {{
                try {{ act.muted = false; act.volume = 1; }} catch (eU4) {{}}
              }}).catch(() => {{
                try {{ act.muted = true; }} catch (eM2) {{}}
                const pm = act.play();
                if (pm && pm.then) {{
                  pm.then(() => {{
                    try {{ act.muted = false; act.volume = 1; }} catch (eU5) {{}}
                  }}).catch(() => {{ if (myGen === state.playGen) {{}} }});
                }}
              }});
            }}
          }}
        }}
      }}
      if (nxt && idle) {{
        refreshIdleOnly();
      }}
    }};
    return root;
  }}

  if (!parentWin.__kcCmdPoll) {{
    parentWin.__kcCmdPoll = parentWin.setInterval(() => {{
      try {{
        const byId = parentWin.document.getElementById('kc-cmd-slot');
        const slots = parentWin.document.querySelectorAll('[data-kc-cmd-slot]');
        const slot = byId || (slots.length ? slots[slots.length - 1] : null);
        const raw = slot ? String(slot.textContent || '').trim() : '';
        if (!raw) return;
        let forceRetry = false;
        try {{
          const peek = JSON.parse(parentWin.atob(raw));
          forceRetry = !!(
            peek
            && (
              peek.forcePlay
              || peek.forceArrangementReplace
              || peek.arrangementReload
              || peek.resume
              || peek.restart
            )
          );
        }} catch (ePeek) {{}}
        // Explicit arrangement Play must re-apply even when Streamlit rewrote an
        // identical slot payload (same URL hash) — poll-seen dedupe previously
        // skipped the only forcePlay cmd while the buffer kept the prior WAV.
        if (raw === parentWin.__kcCmdPollSeen && !forceRetry) return;
        if (forceRetry && raw === parentWin.__kcCmdPollSeen) {{
          const now = Date.now();
          if (!parentWin.__kcCmdForceArmedUntil) {{
            parentWin.__kcCmdForceArmedUntil = now + 90000;
          }}
          if (now > Number(parentWin.__kcCmdForceArmedUntil || 0)) return;
          if (now - Number(parentWin.__kcCmdForceRetryAt || 0) < 1200) return;
          parentWin.__kcCmdForceRetryAt = now;
        }} else if (forceRetry) {{
          parentWin.__kcCmdForceArmedUntil = Date.now() + 90000;
        }}
        parentWin.__kcCmdPollSeen = raw;
        const cmd = JSON.parse(parentWin.atob(raw));
        if (typeof parentWin.__kcApplyCmd === 'function') parentWin.__kcApplyCmd(cmd);
      }} catch (ePoll) {{}}
    }}, 300);
  }}

  try {{
    ensurePlayer();
    if (typeof parentWin.__kcApplyCmd === 'function') {{
      parentWin.__kcApplyCmd(CMD);
    }}
  }} catch (err) {{
    try {{ parentWin.__kcBridgeErr = String(err && (err.stack || err)); }} catch (eBr) {{}}
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
    mirror_to_dom: bool = True,
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
    # Explicit Play / arrangement replace must still publish even if a prior Off
    # or hard-stop left status=stopped while the owner cycle is enabled again.
    _force_play = bool(
        session.get("_kc_restart_play")
        or session.get("_kc_force_arrangement_replace")
        or session.get("_kc_arrangement_reload")
    )
    if str(data.get("status") or "") == STATUS_STOPPED and not _force_play:
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
        try:
            _loops_req = None
            _sig = session.get("_last_backing_signature")
            if isinstance(_sig, tuple) and len(_sig) >= 7:
                _loops_req = int(_sig[6])
        except Exception:
            _loops_req = None
        nxt = prepared_cycle_static_url(
            session,
            next_cycle_playback_key(session),
            require_loops=_loops_req,
        )
    following_sounding = str(peek_cycle_key_at_delta(session, steps=2) or "").strip()
    following_url = ""
    try:
        _loops_req2 = None
        _sig2 = session.get("_last_backing_signature")
        if isinstance(_sig2, tuple) and len(_sig2) >= 7:
            _loops_req2 = int(_sig2[6])
    except Exception:
        _loops_req2 = None
    if following_sounding and following_sounding != str(
        next_cycle_playback_key(session) or ""
    ).strip():
        following_url = prepared_cycle_static_url(
            session, following_sounding, require_loops=_loops_req2
        )
    ahead_sounding = str(peek_cycle_key_at_delta(session, steps=3) or "").strip()
    ahead_url = ""
    if (
        ahead_sounding
        and ahead_sounding != following_sounding
        and ahead_sounding != str(next_cycle_playback_key(session) or "").strip()
    ):
        ahead_url = prepared_cycle_static_url(
            session, ahead_sounding, require_loops=_loops_req2
        )
    wav_sig = str(session.get("_last_backing_signature") or "").strip() or "pass"
    token = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in wav_sig)[:180]
    held = str(data.get("status") or "") == STATUS_HELD
    # Prefetch fragment pushes (mirror_to_dom=False) must not consume one-shot
    # transport flags — otherwise main mount after Next/Prev loses restart@0.
    if mirror_to_dom:
        skip_remount = bool(session.pop("_kc_skip_audio_remount", False))
        hard_stop = bool(session.pop("_kc_hard_stop", False))
        # Resume stays sticky until Pause (refresh Resume was often consumed
        # before the bridge applied). Restart is oneshot — intentional advance
        # (priorArmedNext / expected next) must not be rejected as liveHandoff.
        resume_play = bool(session.get("_kc_resume_play", False))
        restart_play = bool(session.pop("_kc_restart_play", False))
        session.pop("_kc_restart_play_pubs", None)
        pause_flag = bool(session.pop("_kc_pause_audio", False))
    else:
        skip_remount = bool(session.get("_kc_skip_audio_remount", False))
        hard_stop = bool(session.get("_kc_hard_stop", False))
        resume_play = False
        restart_play = False
        pause_flag = bool(session.get("_kc_pause_audio", False))
    user_stopped = bool(session.get("_backing_transport_user_stopped"))
    want_pause = (
        (held or user_stopped or hard_stop or pause_flag)
        and not resume_play
        and not restart_play
    )
    sounding = str(data.get("current_playback_key") or temporary_playback_key(session) or "")
    next_sounding = ""
    if nxt:
        next_sounding = str(next_cycle_playback_key(session) or "").strip()
    prev_sounding = str(previous_cycle_playback_key(session) or "").strip()
    prev_url = ""
    if prev_sounding and prev_sounding != sounding:
        prev_url = prepared_cycle_static_url(
            session, prev_sounding, require_loops=_loops_req2
        )
    prev_chart = prepared_cycle_chart_html(session, prev_sounding) if prev_url else ""
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
        current_chart = ""
    _oneshot_reload = bool(session.pop("_kc_arrangement_reload", False))
    _force_replace = bool(session.get("_kc_force_arrangement_replace"))
    _arrange_url = str(session.get("_kc_arrangement_url") or "").strip()
    _arrangement_reload = bool(
        _oneshot_reload
        or _force_replace
        or (_arrange_url and _arrange_url == str(cur or "").strip())
    )
    if _oneshot_reload or _force_replace:
        # Drop prefetched neighbors from the previous arrangement.
        nxt = ""
        following_url = ""
        ahead_url = ""
        prev_url = ""
    _display_reproject = bool(session.pop("_kc_display_reproject", False))
    try:
        _cmd_sequence = list(cycle_key_sequence(session) or [])
    except Exception:
        _cmd_sequence = []
    # Final key: once stopped (held / sealed), never publish a wrap-neighbor
    # nextUrl. While still RUNNING on the last key, keep prefetch empty too so
    # onEnded cannot seamless-swap to the first key — JS also gates on sequence.
    _at_final = bool(
        session.get("_kc_at_final_key") or session.get("_kc_cycle_finished_final")
    )
    try:
        if _cmd_sequence and sounding and str(sounding) == str(_cmd_sequence[-1]):
            _at_final = True
    except Exception:
        pass
    if _at_final:
        nxt = ""
        following_url = ""
        ahead_url = ""
        next_sounding = ""
        following_sounding = ""
        ahead_sounding = ""
        next_chart = ""
        following_chart = ""
        ahead_chart = ""
    try:
        # Avoid recursive epoch bumps: only rebuild charts when sig changed.
        if not _display_reproject:
            reproject_key_cycle_display(session)
            _display_reproject = bool(session.pop("_kc_display_reproject", False))
            if _display_reproject:
                skip_remount = True
                # Charts were rebuilt — refresh prepared HTML for this cmd.
                current_chart = prepared_cycle_chart_html(session, sounding)
                next_chart = (
                    prepared_cycle_chart_html(session, next_sounding)
                    if next_sounding
                    else ""
                )
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
                prev_chart = (
                    prepared_cycle_chart_html(session, prev_sounding) if prev_url else ""
                )
    except Exception:
        pass
    next_follow_tl = (
        prepared_cycle_follow_timeline(session, next_sounding) if next_sounding else []
    )
    current_follow_tl = (
        prepared_cycle_follow_timeline(session, sounding) if sounding else []
    )
    if not current_follow_tl:
        try:
            _aud = session.get("_last_backing_timeline") or session.get(
                "_kc_audible_follow_timeline"
            )
            if isinstance(_aud, list):
                current_follow_tl = list(_aud)
        except Exception:
            current_follow_tl = []
    try:
        _cmd_display_sequence = project_cycle_sequence_labels(
            session, sequence=_cmd_sequence
        )
    except Exception:
        _cmd_display_sequence = list(_cmd_sequence)
    import time as _kc_time

    cmd = {
        "enabled": True,
        "epoch": int(session.get("_kc_player_cmd_epoch") or 0),
        "cycleId": str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
        "passId": int(data.get("pass_id") or 0),
        "sequence": _cmd_sequence,
        "displaySequence": _cmd_display_sequence,
        "chartMode": cycle_chart_mode(session),
        "readingKey": project_cycle_display_key(session, sounding or ""),
        "displayReproject": _display_reproject,
        "currentUrl": cur,
        "nextUrl": nxt,
        "followingUrl": following_url,
        "aheadUrl": ahead_url,
        "prevUrl": prev_url,
        "sounding": sounding,
        "nextSounding": next_sounding,
        "prevSounding": prev_sounding if prev_url else "",
        "prevChartHtml": prev_chart,
        "followingSounding": following_sounding if following_url else "",
        "aheadSounding": ahead_sounding if ahead_url else "",
        "currentChartHtml": current_chart,
        "nextChartHtml": next_chart,
        "followingChartHtml": following_chart,
        "aheadChartHtml": ahead_chart,
        "followTimeline": (
            list(current_follow_tl)
            if current_follow_tl
            else (
                list(
                    session.get("_kc_follow_timeline")
                    or session.get("_last_backing_timeline")
                    or session.get("_kc_audible_follow_timeline")
                    or []
                )
                if session.get("backing_lead_sheet_open")
                else []
            )
        ),
        "nextFollowTimeline": list(next_follow_tl) if next_follow_tl else [],
        "atFinalKey": bool(_at_final),
        "passToken": token,
        "autoplay": (
            (bool(autoplay) or bool(session.get("_backing_autoplay")))
            and not want_pause
            and not skip_remount
            and bool(cur)
            and not hard_stop
        ),
        "paused": want_pause,
        "resume": bool(resume_play) or ((not held) and skip_remount and not user_stopped),
        "hardStop": bool(hard_stop),
        "restart": bool(restart_play),
        "arrangementReload": _arrangement_reload,
        "arrangementUrl": _arrange_url,
        "forceArrangementReplace": bool(_force_replace or _oneshot_reload),
        "forcePlay": bool(
            _arrange_url
            and _arrange_url == str(cur or "").strip()
            and (bool(autoplay) or bool(session.get("_backing_autoplay")))
            and not want_pause
            and not hard_stop
        ),
        # Unique per publish so Streamlit remounts the bridge iframe and the
        # DOM slot poll cannot treat a same-URL forcePlay as already-seen.
        # Resume/restart stay sticky in the slot (forceRetry) — do not mint a
        # new nonce every remount or the bridge thrash resets buffers.
        "publishNonce": (
            f"{int(session.get('_kc_player_cmd_epoch') or 0)}:"
            f"{int(_kc_time.time() * 1000) % 100000000}"
            if (_force_replace or _oneshot_reload or _arrange_url)
            else ""
        ),
        "leadSheetOpen": bool(session.get("backing_lead_sheet_open")),
    }
    try:
        import os
        import time
        from pathlib import Path

        _data = Path(os.environ.get("MUSIC_APP_DATA_DIR") or "_runtime_key_cycle_8510")
        _data.mkdir(parents=True, exist_ok=True)
        with (_data / "_kc_player_cmds.jsonl").open("a", encoding="utf-8") as _fh:
            _fh.write(
                json.dumps(
                    {
                        "t": time.time(),
                        "event": "cmd",
                        "reload": bool(_arrangement_reload),
                        "forcePlay": bool(cmd.get("forcePlay")),
                        "arrange": str(_arrange_url or "")[-32:],
                        "epoch": cmd.get("epoch"),
                        "sound": cmd.get("sounding"),
                        "autoplay": cmd.get("autoplay"),
                        "paused": cmd.get("paused"),
                        "resume": cmd.get("resume"),
                        "restart": cmd.get("restart"),
                        "currentUrl": str(cur or "")[-48:],
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    try:
        import streamlit.components.v1 as components

        _cmd_h = 1 + (int(session.get("_kc_player_cmd_epoch") or 0) % 4)
        # Include nonce so same-epoch forcePlay republishes still remount.
        try:
            _nonce = str(cmd.get("publishNonce") or "")
            if _nonce:
                _tail = _nonce.split(":")[-1]
                _cmd_h = 1 + (int(_tail or "0") % 7)
        except Exception:
            pass
        components.html(
            cycle_persistent_player_bridge_html(cmd_json=json.dumps(cmd)),
            height=_cmd_h,
            scrolling=False,
        )
        if mirror_to_dom:
            import base64

            _slot = {
                k: v
                for k, v in cmd.items()
                if k
                not in {
                    "currentChartHtml",
                    "nextChartHtml",
                    "followingChartHtml",
                    "aheadChartHtml",
                    "prevChartHtml",
                    "followTimeline",
                }
            }
            _chart = str(cmd.get("currentChartHtml") or "")
            if _chart and len(_chart) <= 80000:
                _slot["currentChartHtml"] = _chart
            _b64 = base64.b64encode(
                json.dumps(_slot).encode("utf-8")
            ).decode("ascii")
            st.markdown(
                f'<div id="kc-cmd-slot" data-kc-cmd-slot="1" style="display:none">{_b64}</div>',
                unsafe_allow_html=True,
            )
        # After an explicit Play command with a real URL is published, drop the
        # sticky marker so later Stop / prefetch / natural handoffs are not
        # treated as another Play. Delivery retries use publishNonce + epoch
        # remount + cmd-slot forceRetry (not an eternal sticky that deferred
        # pass-bridge acks and blocked key advances).
        if bool(cmd.get("forcePlay")) and str(cmd.get("currentUrl") or "").strip():
            session.pop("_kc_arrangement_url", None)
            session.pop("_kc_arrangement_reload", None)
            session.pop("_kc_force_arrangement_replace", None)
            session.pop("_kc_force_play_published_url", None)
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
    # Explicit Feel/BPM/scope Play owns this visit. Pass-bridge runs *before* the
    # Play button in the same script; st.rerun() on a stale natural/playing ack
    # aborted the run so Blues commit never reached generate_saved.
    _explicit_play_owns = bool(
        key_cycle_settings_pending(session)
        or session.get("_kc_force_arrangement_replace")
        or session.get("_kc_arrangement_reload")
        or session.get("_kc_arrangement_url")
    )
    data = get_owner_cycle_session(session)
    if not data or str(data.get("status") or "") != STATUS_RUNNING:
        return
    try:
        from backing_key_cycle_handoff import (
            drain_pending_handoff_ack,
            mark_ack_consumed,
            render_handoff_component,
        )
    except Exception:
        return

    handoff_ack = render_handoff_component(
        st,
        session,
        expect_cycle_id=str(data.get("cycle_id") or session.get("_kc_cycle_id") or ""),
        armed=True,
    )
    # Prefer draining a queued batch ack when the component returns nothing new.
    if not isinstance(handoff_ack, dict):
        handoff_ack = drain_pending_handoff_ack(session)
    if not isinstance(handoff_ack, dict):
        return

    if _explicit_play_owns:
        # Drop the ack without advancing or rerunning — natural handoff must not
        # overwrite / consume the pending explicit arrangement Play.
        try:
            mark_ack_consumed(session, str(handoff_ack.get("ackId") or ""))
        except Exception:
            pass
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
                            "advanced": False,
                            "deferred": True,
                            "reason": "explicit_play_owns",
                            "ack_kind": str(handoff_ack.get("kind") or ""),
                            "playing_key": str(handoff_ack.get("playingKey") or ""),
                            "pending": bool(key_cycle_settings_pending(session)),
                            "channel": "declare_component",
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
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
    ack_kind = str(handoff_ack.get("kind") or "").strip()
    if ack_kind == "final_key_stop":
        try:
            from backing_key_cycle_handoff import mark_ack_consumed

            mark_ack_consumed(session, str(handoff_ack.get("ackId") or ""))
        except Exception:
            pass
        # Browser already stopped on the final key — seal Python final flags.
        pass_sig = (
            f"final_key_stop::{handoff_ack.get('ackId') or 'ack'}"
            f"::{playing_key or 'key'}"
        )
        advanced = note_backing_pass_finished(
            session,
            pass_signature=pass_sig,
            seamless=False,
            gap_ms=gap_ms,
            handoff_ack=None,
        )
    elif ack_kind == "late_prep_recover":
        # Dual-buffer never armed next in time — force one advance + CONTINUE_PLAY.
        # Do not use the playing-ack confirm path (that would no-op on the same key).
        try:
            from backing_key_cycle_handoff import mark_ack_consumed

            mark_ack_consumed(session, str(handoff_ack.get("ackId") or ""))
        except Exception:
            pass
        pass_sig = (
            f"late_prep_recover::{handoff_ack.get('ackId') or 'ack'}"
            f"::{handoff_ack.get('passToken') or playing_key or 'key'}"
        )
        advanced = note_backing_pass_finished(
            session,
            pass_signature=pass_sig,
            seamless=False,
            gap_ms=gap_ms,
            handoff_ack=None,
        )
    else:
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
    # Always rerun after a handled ack so pending batch items drain next run
    # (only reached when explicit Feel/BPM Play is not owning the visit).
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
    force_off = bool(session.pop("_key_cycle_force_ui_off", False))
    reseed_on = bool(session.pop("_kc_reseed_cycle_ui_on", False))
    user_toggled = bool(session.pop("_kc_cycle_user_toggled", False))
    if force_off:
        session[mode_key] = "Off"
    elif reseed_on and active:
        # Play/generate remount can snap a destroyed Off/On radio back to Off
        # while the owner cycle session is still enabled. Reseed once.
        session[mode_key] = "On"
    elif active and str(session.get(mode_key) or "") != "On" and not user_toggled:
        # Advanced/Play remounts often recreate the radio at option 0 (Off) without
        # an on_change. That used to call stop_key_cycle, drop the dual-buffer, and
        # leave generate_saved Blues/BPM WAVs with an unchanged audible currentSrc.
        session[mode_key] = "On"
    elif mode_key not in session:
        session[mode_key] = "On" if active else "Off"

    def _mark_cycle_user_toggle() -> None:
        session["_kc_cycle_user_toggled"] = True

    choice = st.radio(
        "Key cycling",
        options=["Off", "On"],
        horizontal=True,
        key=mode_key,
        help=KEY_CYCLE_TOOLTIP,
        on_change=_mark_cycle_user_toggle,
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
        # Only honor Off when the user clicked the radio (or an explicit force-off).
        # Spurious remount Off must not tear down a live cycle / dual-buffer.
        if user_toggled or force_off:
            stop_key_cycle(session)
            active = False
            # Push disable in this same run (rerun is not used here).
            try:
                render_backing_key_cycle_persistent_player(
                    st,
                    session,
                    current_url="",
                    next_url="",
                    autoplay=False,
                    force_disable=True,
                )
                session["_kc_persistent_player_mounted"] = False
                session.pop("_kc_player_needs_teardown", None)
                session.pop("_kc_force_player_off", None)
            except Exception:
                pass
        else:
            session[mode_key] = "On"
            session[enable_flag] = True
            on = True
        # No rerun — hide config below in this same run; playbar mounts later.
    if not on and not is_cycle_active(session):
        return

    # Compact settings only while enabled.
    step_key = "backing_key_cycle_step_ui"
    dir_key = "backing_key_cycle_direction_ui"
    data = get_owner_cycle_session(session, owner)
    # Seed radios from the live cycle session so a remount after PK reanchor
    # does not look like the user flipped Interval/Direction.
    if data and data.get("enabled"):
        session.setdefault(
            step_key,
            "whole" if int(data.get("interval") or 1) == 2 else "semitone",
        )
        session.setdefault(dir_key, str(data.get("direction") or "up"))
    else:
        session.setdefault(step_key, session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone")
        session.setdefault(dir_key, session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up")

    # Practice Key drift while On → rebuild sequence from the new saved key.
    live_pk = str(current_backing_owner_practice_key(session) or "").strip()
    data = get_owner_cycle_session(session, owner)
    if (
        active
        and data
        and data.get("enabled")
        and live_pk
        and not _keys_equivalent(str(data.get("base_practice_key") or ""), live_pk)
    ):
        reanchor_key_cycle_from_practice_key(session, new_key=live_pk)
        data = get_owner_cycle_session(session, owner)
        active = is_cycle_active(session)
        # Keep radios aligned with the reanchored session (no spurious reset).
        if data:
            session[step_key] = (
                "whole" if int(data.get("interval") or 1) == 2 else "semitone"
            )
            session[dir_key] = str(data.get("direction") or "up")
            session["_kc_cycle_settings_applied"] = (
                int(data.get("interval") or 1),
                str(data.get("direction") or "up"),
                str(data.get("cycle_id") or ""),
            )

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

    # Interval / direction change → keep On, reset position to saved Practice Key.
    # Skip when cycle_id just bumped (PK reanchor / settings apply) so widget
    # remount defaults cannot wipe the new sequence.
    data = get_owner_cycle_session(session, owner)
    if data and data.get("enabled"):
        mag = 2 if str(session.get(BACKING_KEY_CYCLE_STEP_KEY) or "semitone") == "whole" else 1
        direc = str(session.get(BACKING_KEY_CYCLE_DIRECTION_KEY) or "up")
        applied = session.get("_kc_cycle_settings_applied")
        cur_id = str(data.get("cycle_id") or "")
        if (
            isinstance(applied, tuple)
            and len(applied) >= 3
            and str(applied[2] or "")
            and str(applied[2]) != cur_id
        ):
            # Identity bump already carried interval/direction — adopt, don't reset.
            session["_kc_cycle_settings_applied"] = (
                int(data.get("interval") or mag),
                str(data.get("direction") or direc),
                cur_id,
            )
        elif (
            isinstance(applied, tuple)
            and len(applied) >= 2
            and (int(applied[0]) != mag or str(applied[1]) != direc)
        ):
            reset_key_cycle_position_for_settings(
                session,
                interval=mag,
                direction=direc,
            )
            data = get_owner_cycle_session(session, owner)
            session["_kc_cycle_settings_applied"] = (
                int((data or {}).get("interval") or mag),
                str((data or {}).get("direction") or direc),
                str((data or {}).get("cycle_id") or ""),
            )
        elif not isinstance(applied, tuple):
            # First paint while On: record without resetting.
            session["_kc_cycle_settings_applied"] = (
                int(data.get("interval") or mag),
                str(data.get("direction") or direc),
                cur_id,
            )
            # If radios disagree with session on first paint after a cold start,
            # prefer session (already seeded above).
        elif int(data.get("interval") or 1) != mag or str(data.get("direction") or "") != direc:
            # Applied matches UI but session drifted (should be rare).
            reset_key_cycle_position_for_settings(
                session,
                interval=mag,
                direction=direc,
            )
            data = get_owner_cycle_session(session, owner)
            session["_kc_cycle_settings_applied"] = (
                int((data or {}).get("interval") or mag),
                str((data or {}).get("direction") or direc),
                str((data or {}).get("cycle_id") or ""),
            )

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
            if old_prefs != prefs:
                reset_key_cycle_position_for_settings(
                    session,
                    spelling_prefs=prefs,
                )
            else:
                data["spelling_prefs"] = prefs
                _put_owner_cycle_session(session, owner, data)


def render_backing_key_cycle_playback_bar(st: Any, session: dict[str, Any]) -> None:
    """Compact Pause / Previous / Next / Turn off + key sequence near the player."""
    if not is_cycle_active(session):
        return
    session["backing_key_cycle_enabled"] = True
    data = get_owner_cycle_session(session) or {}
    pending_sounding = str(
        data.get("current_playback_key") or temporary_playback_key(session) or ""
    ).strip()
    # While next audio prepares, keep showing the last confirmed audible key.
    audible = ""
    try:
        conf = session.get("_kc_last_playing_confirm")
        if isinstance(conf, dict):
            audible = str(conf.get("key") or "").strip()
    except Exception:
        audible = ""
    settings_pending = key_cycle_settings_pending(session)
    preparing_key = bool(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY)) and bool(
        audible
    ) and not _keys_equivalent(audible, pending_sounding)
    # Arrangement auto-apply (BPM/Feel/scope): same key, still regenerating.
    preparing_arr = False
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        preparing_arr = bool(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY)) and bool(
            session.get(BACKING_NEEDS_REGEN)
        )
    except Exception:
        preparing_arr = bool(session.get(BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY)) and bool(
            session.get("backing_needs_regen")
        )
    preparing = preparing_key or preparing_arr
    # Settings / PK change pending Play: distinguish still-playing audio from selection.
    pending_vs_audible = bool(
        settings_pending
        and audible
        and pending_sounding
        and not _keys_equivalent(audible, pending_sounding)
    )
    sounding = audible if (preparing_key or pending_vs_audible) else pending_sounding
    saved = str(data.get("base_practice_key") or current_backing_owner_practice_key(session)).strip()
    held = str(data.get("status") or "") == STATUS_HELD
    user_stopped = bool(session.get("_backing_transport_user_stopped"))
    # Stopped and paused both offer Resume; button must match held audio state.
    pause_label = "Resume" if (held or user_stopped) else "Pause"
    sequence = cycle_key_sequence(session)
    display_labels = project_cycle_sequence_labels(session, sequence=sequence)
    chart_mode = cycle_chart_mode(session)
    reading_now = project_cycle_display_key(
        session, sounding or pending_sounding or saved or "C"
    )
    # Highlight the selected/pending key for next Play; mark audible separately when it differs.
    idx = 0
    for i, key_tok in enumerate(sequence):
        if _keys_equivalent(key_tok, pending_sounding if (preparing_key or pending_vs_audible) else sounding):
            idx = i
            break
    else:
        idx = cycle_sequence_index(session)

    chips = []
    for i, key_tok in enumerate(sequence):
        concert_attr = html_escape(key_tok)
        display_label = (
            display_labels[i] if i < len(display_labels) else key_tok
        )
        visible = html_escape(display_label)
        is_pending = _keys_equivalent(key_tok, pending_sounding)
        is_audible = bool(audible) and _keys_equivalent(key_tok, audible)
        # data-key stays concert so JS handoff highlight matches audio identity.
        if is_pending and (preparing_key or pending_vs_audible) and not is_audible:
            chips.append(
                f'<span class="ui-key-cycle-chip ui-key-cycle-chip-pending" data-pending="1"'
                f' data-key="{concert_attr}" data-display="{visible}"'
                f' title="Next Play sounding {concert_attr}">{visible}</span>'
            )
        elif i == idx or (is_pending and not pending_vs_audible and not preparing_key):
            chips.append(
                f'<span class="ui-key-cycle-chip ui-key-cycle-chip-on" data-current="1"'
                f' data-key="{concert_attr}" data-display="{visible}">{visible}</span>'
            )
        elif is_audible and pending_vs_audible:
            chips.append(
                f'<span class="ui-key-cycle-chip ui-key-cycle-chip-audible" data-audible="1"'
                f' data-key="{concert_attr}" data-display="{visible}"'
                f' title="Still sounding {concert_attr}">{visible}</span>'
            )
        else:
            chips.append(
                f'<span class="ui-key-cycle-chip" data-key="{concert_attr}"'
                f' data-display="{visible}">{visible}</span>'
            )

    cycle_id = str(data.get("cycle_id") or session.get("_kc_cycle_id") or "").strip()
    seq_joined = ",".join(sequence)
    display_joined = ",".join(display_labels)
    reading_line = ""
    if chart_mode != "concert" and reading_now and not _keys_equivalent(reading_now, sounding):
        mode_label = "Written" if chart_mode == "written" else "Shape"
        reading_line = (
            f'<div><span>{mode_label} <strong>{html_escape(reading_now)}</strong>'
            f'<span style="opacity:.65"> · reading mode</span></span></div>'
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
        ".ui-key-cycle-chip-pending{background:#0e7490!important;color:#fff!important;"
        "font-weight:700!important;opacity:1!important;outline:1px dashed rgba(255,255,255,.55)}"
        ".ui-key-cycle-chip-audible{background:#64748b!important;color:#fff!important;"
        "opacity:1!important}"
        "</style>"
        f'<div class="ui-key-cycle-playbar" data-cycle-id="{html_escape(cycle_id)}" '
        f'data-seq="{html_escape(seq_joined)}" '
        f'data-display-seq="{html_escape(display_joined)}" '
        f'data-chart-mode="{html_escape(chart_mode)}">'
        f'<div><span>Sounding <strong>{html_escape(sounding) or "—"}</strong>'
        f'<span style="opacity:.65"> · saved {html_escape(saved) or "—"}</span>'
        f'{"<span style=\"opacity:.75;margin-left:.4rem\">· preparing arrangement…</span>" if preparing_arr and not preparing_key else ""}'
        f'{"<span style=\"opacity:.75;margin-left:.4rem\">· preparing next…</span>" if preparing_key else ""}'
        f'{"<span style=\"opacity:.75;margin-left:.4rem\">· next Play: " + html_escape(pending_sounding) + "</span>" if pending_vs_audible else ""}'
        f'{"<span style=\"opacity:.75;margin-left:.4rem\">· cycle settings pending Play</span>" if settings_pending and not pending_vs_audible else ""}'
        f'</span></div>'
        f'{reading_line}'
        f'<div class="ui-key-cycle-seq" style="display:flex;flex-wrap:wrap;align-items:center;'
        f'gap:.05rem;line-height:1.6" title="One full cycle in reading order (audio stays concert)">'
        f'{"".join(chips)}</div></div>'
    )
    try:
        st.html(bar_html)
    except Exception:
        st.markdown(bar_html, unsafe_allow_html=True)
    # Chart follow must not bury Pause; sticky keeps the row hittable over the sheet.
    st.markdown(
        """
<style>
[class*="st-key-backing_key_cycle_pause_btn"],
[class*="st-key-backing_key_cycle_prev_btn"],
[class*="st-key-backing_key_cycle_advance_btn"],
[class*="st-key-backing_key_cycle_stop_btn"] {
  position: sticky !important;
  top: 3.25rem !important;
  z-index: 1002 !important;
  background: var(--background-color, #0e1117);
}
[class*="st-key-backing_key_cycle_pause_btn"] button,
[class*="st-key-backing_key_cycle_prev_btn"] button,
[class*="st-key-backing_key_cycle_advance_btn"] button,
[class*="st-key-backing_key_cycle_stop_btn"] button {
  position: relative !important;
  z-index: 1003 !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )
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
            # Must disable the dual-buffer *before* rerun — teardown after this
            # playbar return is skipped when st.rerun() aborts the script.
            try:
                render_backing_key_cycle_persistent_player(
                    st,
                    session,
                    current_url="",
                    next_url="",
                    autoplay=False,
                    force_disable=True,
                )
                session["_kc_persistent_player_mounted"] = False
                session.pop("_kc_player_needs_teardown", None)
                session.pop("_kc_force_player_off", None)
            except Exception:
                pass
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
    "BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY",
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
    "arrangement_fingerprint_from_signature",
    "assert_practice_key_unchanged",
    "clear_key_cycle_prepared_audio",
    "consume_cycle_continue_play",
    "consume_key_cycle_settings_pending",
    "clear_settings_pending_if_arrangement_applied",
    "applied_arrangement_matches_selection",
    "arrangement_content_matches_selection",
    "applied_arrangement_ready",
    "audible_follow_timeline",
    "normalize_key_cycle_after_browser_restore",
    "stash_audible_arrangement_after_generate",
    "current_backing_owner_practice_key",
    "cycle_chart_mode",
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
    "key_cycle_settings_pending",
    "mark_cycle_next_pass_playing_clock",
    "mark_cycle_next_pass_ready_clock",
    "mark_cycle_pass_ended_clock",
    "maybe_consume_cycle_pass_from_query",
    "next_cycle_playback_key",
    "note_backing_pass_finished",
    "note_key_cycle_arrangement_settings_changed",
    "hard_stop_key_cycle_audio",
    "pause_key_cycle",
    "peek_cycle_key_at_delta",
    "persist_key_cycle_position",
    "prepared_cycle_audio_matches_loops",
    "prepared_cycle_static_url",
    "previous_cycle_playback_key",
    "previous_key_cycle_now",
    "project_cycle_display_key",
    "project_cycle_sequence_labels",
    "promote_prepared_cycle_audio",
    "publish_cycle_wav_static_url",
    "reanchor_key_cycle_from_practice_key",
    "render_backing_key_cycle_compact_audio",
    "render_backing_key_cycle_controls",
    "render_backing_key_cycle_pass_bridge",
    "render_backing_key_cycle_persistent_player",
    "render_backing_key_cycle_playback_bar",
    "render_backing_key_cycle_st_audio_bridge",
    "render_backing_key_cycle_status_banner",
    "reproject_key_cycle_display",
    "reset_key_cycle_position_for_settings",
    "resolve_cycle_owner",
    "restart_key_cycle_audio",
    "resume_key_cycle",
    "arm_key_cycle_for_explicit_play",
    "spelling_prefs_from_session",
    "start_key_cycle",
    "stop_key_cycle",
    "store_prepared_cycle_audio",
    "sync_key_cycle_after_practice_key_commit",
    "temporary_playback_key",
    "cycle_prefetch_neighbor_keys",
]
