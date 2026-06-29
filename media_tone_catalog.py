"""Tone & Tuner History ↔ canonical media catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from media_persistence import (
    add_tone_take,
    delete_tone_take,
    load_media_catalog,
    update_tone_take,
)
from media_state import (
    compact_tone_take_for_ami,
    migrate_tone_take,
    normalize_tone_takes,
)
from media_storage import (
    delete_tone_take_files,
    load_tone_take_audio,
    persist_tone_take_audio,
    playback_status_label,
    tone_take_playback_status,
)
from tuner_tone import NOTE_NAMES, TonePracticeResult, parse_note_token

_PENDING_TONE_AUDIO_KEY = "_pending_tone_take_audio"
_PENDING_TONE_RESULT_KEY = "_pending_tone_practice_result"
_PENDING_TONE_META_KEY = "_pending_tone_take_meta"
_LAST_TONE_SAVE_STATUS_KEY = "_tone_take_last_save_status"
_LAST_TONE_LOAD_STATUS_KEY = "_tone_take_last_load_status"
_LAST_TONE_PLAYBACK_STATUS_KEY = "_tone_take_last_playback_status"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_state(st: Any | None) -> dict[str, Any] | None:
    if st is None:
        return None
    try:
        ss = st.session_state if hasattr(st, "session_state") else st
        return ss if isinstance(ss, dict) else None
    except Exception:
        return None


def midi_to_note_token(midi: int) -> str:
    octave = midi // 12 - 1
    name = NOTE_NAMES[midi % 12]
    return f"{name}{octave}"


def transpose_note_token(token: str, semitones: int) -> str | None:
    midi = parse_note_token(token)
    if midi is None:
        return None
    return midi_to_note_token(midi + semitones)


def _note_pitch_class(token: str) -> str:
    midi = parse_note_token(token)
    if midi is None:
        return str(token or "").strip().split("0")[0].split("1")[0][:3]
    return NOTE_NAMES[midi % 12]


CHROMATIC_NOTE_OPTIONS: tuple[str, ...] = (
    "C",
    "C#/Db",
    "D",
    "D#/Eb",
    "E",
    "F",
    "F#/Gb",
    "G",
    "G#/Ab",
    "A",
    "A#/Bb",
    "B",
)

TONE_HISTORY_NOTE_FILTER_ALL = "All notes"
TONE_HISTORY_NOTE_FILTER_OPTIONS: tuple[str, ...] = (TONE_HISTORY_NOTE_FILTER_ALL,) + CHROMATIC_NOTE_OPTIONS
NOTE_FILTER_MODE_PLAYER = "Player-facing note"
NOTE_FILTER_MODE_CONCERT = "Concert pitch"
NOTE_FILTER_MODE_OPTIONS: tuple[str, ...] = (NOTE_FILTER_MODE_PLAYER, NOTE_FILTER_MODE_CONCERT)

DEFAULT_TONE_PRACTICE_OCTAVE = 4

_PITCH_CLASS_ALIASES: dict[str, int] | None = None


def _pitch_class_alias_map() -> dict[str, int]:
    global _PITCH_CLASS_ALIASES
    if _PITCH_CLASS_ALIASES is not None:
        return _PITCH_CLASS_ALIASES
    aliases: dict[str, int] = {}
    for idx, name in enumerate(NOTE_NAMES):
        aliases[name.lower()] = idx
    for opt in CHROMATIC_NOTE_OPTIONS:
        canonical = pitch_class_from_option(opt)
        idx = NOTE_NAMES.index(canonical)
        aliases[opt.lower()] = idx
        for part in opt.split("/"):
            aliases[part.strip().lower()] = idx
    _PITCH_CLASS_ALIASES = aliases
    return aliases


def pitch_class_index(token: str) -> int | None:
    """Map a note token or dropdown label to a chromatic pitch-class index (0–11)."""
    text = str(token or "").strip()
    if not text:
        return None
    midi = parse_note_token(text)
    if midi is not None:
        return midi % 12
    aliases = _pitch_class_alias_map()
    low = text.lower()
    if low in aliases:
        return aliases[low]
    if "/" in text:
        for part in text.split("/"):
            part_low = part.strip().lower()
            if part_low in aliases:
                return aliases[part_low]
    if not any(ch.isdigit() for ch in text):
        for octave in (4, 3, 5, 2, 6):
            midi = parse_note_token(f"{text}{octave}")
            if midi is not None:
                return midi % 12
    return None


def _canonical_tone_instrument_key(name: str, *, transposing_type: str = "") -> str:
    text = str(name or "").strip().lower().replace("_", " ").replace("-", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    type_low = str(transposing_type or "").strip().lower()

    def _from_transposing_type() -> str | None:
        if "alto" in type_low:
            return "alto saxophone"
        if "tenor" in type_low:
            return "tenor saxophone"
        if "soprano" in type_low:
            return "soprano saxophone"
        if "baritone" in type_low or "bari" in type_low:
            return "baritone saxophone"
        if "trumpet" in type_low:
            return "trumpet"
        if "clarinet" in type_low:
            return "clarinet"
        return None

    if "alto" in text and "sax" in text:
        return "alto saxophone"
    if "tenor" in text and "sax" in text:
        return "tenor saxophone"
    if "soprano" in text and "sax" in text:
        return "soprano saxophone"
    if ("baritone" in text or "bari" in text) and "sax" in text:
        return "baritone saxophone"
    if text == "saxophone" or text == "sax":
        return _from_transposing_type() or "saxophone"
    if "trumpet" in text:
        return "trumpet"
    if "clarinet" in text:
        return "clarinet"
    if "flute" in text:
        return "flute"
    if "piano" in text:
        return "piano"
    if "guitar" in text:
        return "guitar"
    if "voice" in text or "vocal" in text:
        return "voice"
    typed = _from_transposing_type()
    if typed and text in {"saxophone", "sax"}:
        return typed
    return text


def tone_take_display_instrument(row: dict[str, Any]) -> str:
    row = migrate_tone_take(row)
    inst = str(row.get("instrument") or "").strip()
    transposing_type = str(row.get("transposing_type") or "").strip()
    if inst and inst.lower() not in {"saxophone", "sax", "instrument"}:
        return inst
    if transposing_type:
        try:
            from instrument_transposition import instrument_display_name

            display = str(instrument_display_name(transposing_type, inst) or "").strip()
            if display and display != "Instrument":
                return display
        except ImportError:
            pass
    family = str(row.get("instrument_family") or "").strip()
    return inst or family or "Instrument"


def tone_take_instrument_matches(row: dict[str, Any], filter_instrument: str) -> bool:
    choice = str(filter_instrument or "").strip()
    if not choice or choice.lower() in {"all instruments", "all"}:
        return True
    row = migrate_tone_take(row)
    transposing_type = str(row.get("transposing_type") or "").strip()
    row_inst = str(row.get("instrument") or "").strip()
    row_family = str(row.get("instrument_family") or "").strip()

    filter_key = _canonical_tone_instrument_key(choice)
    for candidate in (row_inst, row_family):
        if not candidate:
            continue
        if _canonical_tone_instrument_key(candidate, transposing_type=transposing_type) == filter_key:
            return True
    return row_inst.lower() == choice.lower()


def pitch_class_from_option(option: str) -> str:
    """First spelling from an enharmonic dropdown label (e.g. ``A#/Bb`` → ``A#``)."""
    text = str(option or "").strip()
    if "/" in text:
        return text.split("/", 1)[0].strip()
    return text


def pitch_class_option_to_token(option: str, *, octave: int = DEFAULT_TONE_PRACTICE_OCTAVE) -> str:
    return f"{pitch_class_from_option(option)}{int(octave)}"


def concert_note_to_written_display(
    concert_token: str,
    transposing_type: str,
) -> dict[str, str | None]:
    """Map a detected concert note to written pitch for live tuner display."""
    from instrument_transposition import TRANSPOSING_SEMITONE_STEPS

    concert = str(concert_token or "").strip()
    if not concert or not str(transposing_type or "").strip():
        return {
            "concert_note": concert or None,
            "written_note": None,
            "written_pitch_class": None,
            "concert_pitch_class": _note_pitch_class(concert) if concert else None,
        }

    steps = TRANSPOSING_SEMITONE_STEPS.get(transposing_type)
    if steps is None:
        return {
            "concert_note": concert,
            "written_note": concert,
            "written_pitch_class": _note_pitch_class(concert),
            "concert_pitch_class": _note_pitch_class(concert),
        }

    written_token = transpose_note_token(concert, steps)
    return {
        "concert_note": concert,
        "written_note": written_token,
        "written_pitch_class": _note_pitch_class(written_token or ""),
        "concert_pitch_class": _note_pitch_class(concert),
    }


def live_tuner_display_settings(
    *,
    instrument: str,
    transposing_type: str,
    instrument_display_name: str = "",
) -> dict[str, Any]:
    """Display-layer config for Tune Live (engine stays concert; UI may show written first)."""
    from instrument_transposition import TRANSPOSING_SEMITONE_STEPS, is_transposing_instrument

    if not is_transposing_instrument(instrument) or not str(transposing_type or "").strip():
        return {
            "display_mode": "concert",
            "concert_to_written_semitones": 0,
            "instrument_label": "",
        }

    steps = TRANSPOSING_SEMITONE_STEPS.get(transposing_type, 0)
    label = str(instrument_display_name or instrument or "").strip()
    return {
        "display_mode": "transposing_written",
        "concert_to_written_semitones": int(steps),
        "instrument_label": label,
    }


def resolve_tone_target_from_pitch_class(
    pitch_class_label: str,
    transposing_type: str,
    *,
    is_transposing: bool,
    default_octave: int = DEFAULT_TONE_PRACTICE_OCTAVE,
) -> dict[str, Any]:
    """Map UI pitch-class selection to storage + analysis concert/written tokens."""
    selected_token = pitch_class_option_to_token(pitch_class_label, octave=default_octave)
    selected_pc = pitch_class_from_option(pitch_class_label)

    if not is_transposing or not str(transposing_type or "").strip():
        return {
            "target_note": selected_token,
            "analysis_target_note": selected_token,
            "written_note": None,
            "concert_note": selected_token,
            "display_written": None,
            "display_concert": selected_pc,
        }

    _, written_note, concert_note = resolve_tone_note_context(
        target_note=selected_token,
        detected_note=None,
        transposing_type=transposing_type,
    )
    written_pc = _note_pitch_class(str(written_note or selected_token))
    concert_pc = _note_pitch_class(str(concert_note or ""))
    return {
        "target_note": selected_token,
        "analysis_target_note": concert_note or selected_token,
        "written_note": written_note,
        "concert_note": concert_note,
        "display_written": written_pc,
        "display_concert": concert_pc,
    }


def resolve_tone_note_context(
    *,
    target_note: str | None,
    detected_note: str | None,
    transposing_type: str,
) -> tuple[str | None, str | None, str | None]:
    """Return (target, written_note, concert_note) for catalog storage."""
    from instrument_transposition import TRANSPOSING_SEMITONE_STEPS

    target = str(target_note or "").strip() or None
    detected = str(detected_note or "").strip() or None
    if not transposing_type:
        return target, None, detected or target

    steps = TRANSPOSING_SEMITONE_STEPS.get(transposing_type)
    if steps is None:
        return target, None, detected or target

    concert_target: str | None = None
    written_target: str | None = None
    if target:
        low = target.lower()
        if low.startswith("concert "):
            concert_target = target[8:].strip()
            written_target = transpose_note_token(concert_target, steps)
        else:
            written_target = target
            concert_target = transpose_note_token(target, -steps)

    concert_note = detected or concert_target
    written_note = written_target
    if concert_note and not written_note:
        written_note = transpose_note_token(concert_note, steps)
    if written_note and not concert_note:
        concert_note = transpose_note_token(written_note, -steps)

    return target, written_note, concert_note


def tone_take_quality(row: dict[str, Any]) -> str:
    score = float(row.get("pitch_stability_score") or 0)
    cents = abs(float(row.get("mean_cents") or 0))
    if score >= 78 and cents <= 10:
        return "best"
    if score < 55 or cents > 20:
        return "needs_work"
    return "steady"


def build_tone_take_fields(
    session_state: dict[str, Any],
    result: TonePracticeResult,
    *,
    st: Any | None = None,
    target_note: str | None = None,
    instrument: str = "",
    display_key: str = "",
    transposing_type: str = "",
    notes: str = "",
    selected_pitch_class: str = "",
) -> dict[str, Any]:
    instrument_family = ""
    instrument_label = str(instrument or "").strip()
    try:
        from practice_setup_globals import (
            get_active_instrument,
            get_active_instrument_display_name,
        )

        instrument_family = str(get_active_instrument(session_state) or instrument_label).strip()
        display_name = str(get_active_instrument_display_name(session_state) or "").strip()
        if display_name:
            instrument_label = display_name
        elif not instrument_label:
            instrument_label = instrument_family
    except ImportError:
        instrument_family = instrument_label

    try:
        from music_coach_instrument_voice import instrument_family as _fam

        fam = _fam(instrument_family or instrument_label)
    except ImportError:
        fam = instrument_family or instrument_label

    written_key = ""
    try:
        from instrument_transposition import is_transposing_instrument, written_key_for_instrument

        if is_transposing_instrument(instrument_family or instrument_label):
            written_key = written_key_for_instrument(display_key, instrument_family or instrument_label, session_state)
    except ImportError:
        pass

    _, written_note, concert_note = resolve_tone_note_context(
        target_note=target_note,
        detected_note=result.median_note,
        transposing_type=transposing_type,
    )
    player_target = str(written_note or target_note or "").strip() or None
    if transposing_type and written_note:
        target_note = written_note
    elif player_target:
        target_note = player_target

    tone_consistency = round((result.pitch_stability_score + result.volume_stability_score) / 2.0, 1)
    coach = " · ".join(x.replace("**", "") for x in (result.feedback or [])[:4])
    mean_cents = round(result.mean_cents, 1)
    pitch_score = round(result.pitch_stability_score, 1)
    vol_score = round(result.volume_stability_score, 1)

    analysis_summary = {
        "pitch_stability_score": pitch_score,
        "pitch_stability": pitch_score,
        "volume_stability_score": vol_score,
        "sustain_steadiness": vol_score,
        "mean_cents": mean_cents,
        "average_cents": mean_cents,
        "max_cents_drift": round(result.max_cents_drift, 1),
        "sustain_seconds": round(result.sustain_seconds, 2),
        "tone_consistency_score": tone_consistency,
        "feedback": list(result.feedback or []),
    }

    return {
        "instrument": instrument_label,
        "instrument_family": fam,
        "transposing_type": transposing_type,
        "target_note": target_note,
        "selected_pitch_class": str(selected_pitch_class or "").strip(),
        "detected_note": result.median_note,
        "written_note": written_note,
        "concert_note": concert_note,
        "written_key": written_key,
        "practice_concert_key": str(display_key or "").strip(),
        "duration_seconds": round(result.duration_sec, 2),
        "median_note": result.median_note,
        "mean_cents": mean_cents,
        "average_cents": mean_cents,
        "max_cents_drift": round(result.max_cents_drift, 1),
        "pitch_stability_score": pitch_score,
        "pitch_stability": pitch_score,
        "volume_stability_score": vol_score,
        "sustain_steadiness": vol_score,
        "sustain_seconds": round(result.sustain_seconds, 2),
        "tone_consistency_score": tone_consistency,
        "attack_quality": None,
        "feedback": list(result.feedback or []),
        "coach_summary": coach[:500],
        "coach_report": coach[:500],
        "analysis_summary": analysis_summary,
        "notes": str(notes or "").strip()[:2000],
        "user_notes": str(notes or "").strip()[:2000],
        "mime_type": "audio/wav",
        "playback_status": "metadata_only",
    }


def _note_filter_tokens(note_filter: str) -> list[str]:
    text = str(note_filter or "").strip()
    if not text or text == TONE_HISTORY_NOTE_FILTER_ALL:
        return []
    parts = [text.lower()]
    if "/" in text:
        parts.extend(p.strip().lower() for p in text.split("/") if p.strip())
    return parts


def is_transposing_tone_take(row: dict[str, Any]) -> bool:
    """True when the take stores separate written vs concert pitch context."""
    row = migrate_tone_take(row)
    if str(row.get("transposing_type") or "").strip():
        return True
    written = str(row.get("written_note") or "").strip()
    concert = str(row.get("concert_note") or "").strip()
    if written and concert:
        return _note_pitch_class(written) != _note_pitch_class(concert)
    return False


def _pitch_class_matches_option(field_value: str, note_filter: str) -> bool:
    if not field_value or not note_filter or note_filter == TONE_HISTORY_NOTE_FILTER_ALL:
        return False
    field_idx = pitch_class_index(field_value)
    filter_indices: set[int] = set()
    for token in _note_filter_tokens(note_filter):
        idx = pitch_class_index(token)
        if idx is not None:
            filter_indices.add(idx)
        elif token:
            aliases = _pitch_class_alias_map()
            if token in aliases:
                filter_indices.add(aliases[token])
    if field_idx is not None and filter_indices:
        return field_idx in filter_indices
    val_low = field_value.lower()
    return any(token in val_low for token in _note_filter_tokens(note_filter))


def _selected_pitch_class_matches(row: dict[str, Any], note_filter: str) -> bool:
    selected_pc = str(row.get("selected_pitch_class") or "").strip()
    if not selected_pc:
        return False
    return _pitch_class_matches_option(selected_pc, note_filter)


def note_filter_matches_row(
    row: dict[str, Any],
    note_filter: str,
    *,
    filter_mode: str = NOTE_FILTER_MODE_PLAYER,
    current_instrument_is_transposing: bool = False,
    all_instruments_view: bool = False,
) -> bool:
    if not note_filter or note_filter == TONE_HISTORY_NOTE_FILTER_ALL:
        return True

    row = migrate_tone_take(row)
    transposing_take = is_transposing_tone_take(row)

    if all_instruments_view and filter_mode == NOTE_FILTER_MODE_CONCERT:
        return _pitch_class_matches_option(str(row.get("concert_note") or ""), note_filter)

    if all_instruments_view:
        if transposing_take:
            return (
                _pitch_class_matches_option(str(row.get("written_note") or ""), note_filter)
                or _pitch_class_matches_option(str(row.get("target_note") or ""), note_filter)
                or _selected_pitch_class_matches(row, note_filter)
            )
        return (
            _pitch_class_matches_option(str(row.get("concert_note") or ""), note_filter)
            or _pitch_class_matches_option(str(row.get("target_note") or ""), note_filter)
            or _selected_pitch_class_matches(row, note_filter)
        )

    if current_instrument_is_transposing:
        return (
            _pitch_class_matches_option(str(row.get("written_note") or ""), note_filter)
            or _pitch_class_matches_option(str(row.get("target_note") or ""), note_filter)
            or _selected_pitch_class_matches(row, note_filter)
        )

    return (
        _pitch_class_matches_option(str(row.get("concert_note") or ""), note_filter)
        or _pitch_class_matches_option(str(row.get("target_note") or ""), note_filter)
        or _selected_pitch_class_matches(row, note_filter)
    )


def tone_history_note_filter_label(*, all_instruments_view: bool, instrument_is_transposing: bool) -> str:
    if all_instruments_view:
        return "Filter by note"
    if instrument_is_transposing:
        return "Filter by written note"
    return "Filter by concert note"


def tone_take_row_note_part(row: dict[str, Any]) -> str:
    row = migrate_tone_take(row)
    written = str(row.get("written_note") or "")
    concert = str(row.get("concert_note") or "")
    selected_pc = str(row.get("selected_pitch_class") or "").strip()

    if is_transposing_tone_take(row) and written and concert:
        w_label = selected_pc or _note_pitch_class(written)
        return f"written {w_label} / concert {_note_pitch_class(concert)}"

    target_label = selected_pc or _note_pitch_class(concert or written or str(row.get("target_note") or ""))
    if not target_label or target_label == "—":
        target_label = str(row.get("target_note") or row.get("detected_note") or "—")
    return f"target {target_label}"


def tone_take_history_detail_fields(row: dict[str, Any]) -> list[tuple[str, str]]:
    """Display labels for the Tone History detail panel."""
    row = migrate_tone_take(row)
    inst = tone_take_display_instrument(row)
    fields: list[tuple[str, str]] = [("Instrument", inst)]

    target = str(row.get("target_note") or "—")
    fields.append(("Target note (player-facing)", target))

    written = str(row.get("written_note") or "")
    concert = str(row.get("concert_note") or "")
    if is_transposing_tone_take(row) and (written or concert):
        fields.append(("Written note (player/instrument)", written or "—"))
        fields.append(("Concert note (sounding pitch)", concert or "—"))
    elif concert or written:
        fields.append(("Concert note (sounding pitch)", concert or written or "—"))

    detected = str(row.get("detected_note") or row.get("median_note") or "—")
    fields.append(("Detected concert note (heard)", detected))
    return fields


def format_tone_take_display_time(created_at: str) -> str:
    text = str(created_at or "").strip()
    if not text:
        return "—"
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        ts = datetime.fromisoformat(text)
        hour = ts.strftime("%I").lstrip("0") or "12"
        return f"{ts.strftime('%Y-%m-%d')} {hour}:{ts.strftime('%M %p')}"
    except ValueError:
        return text[:16]


def cache_pending_tone_take(
    session_state: dict[str, Any],
    *,
    result: TonePracticeResult,
    audio_bytes: bytes,
    target_note: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    session_state[_PENDING_TONE_RESULT_KEY] = {
        "duration_sec": result.duration_sec,
        "median_note": result.median_note,
        "target_note": target_note,
        "mean_cents": result.mean_cents,
        "max_cents_drift": result.max_cents_drift,
        "pitch_stability_score": result.pitch_stability_score,
        "volume_stability_score": result.volume_stability_score,
        "sustain_seconds": result.sustain_seconds,
        "feedback": list(result.feedback or []),
    }
    session_state[_PENDING_TONE_AUDIO_KEY] = bytes(audio_bytes)
    if meta:
        session_state[_PENDING_TONE_META_KEY] = dict(meta)


def clear_pending_tone_take(session_state: dict[str, Any]) -> None:
    session_state.pop(_PENDING_TONE_RESULT_KEY, None)
    session_state.pop(_PENDING_TONE_AUDIO_KEY, None)
    session_state.pop(_PENDING_TONE_META_KEY, None)


def pending_tone_take_ready(session_state: dict[str, Any]) -> bool:
    has_result = isinstance(session_state.get(_PENDING_TONE_RESULT_KEY), dict)
    has_audio = bool(session_state.get(_PENDING_TONE_AUDIO_KEY))
    return has_result and has_audio


def pending_tone_take_meta(session_state: dict[str, Any]) -> dict[str, Any]:
    raw = session_state.get(_PENDING_TONE_META_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def save_pending_tone_take(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    instrument: str = "",
    display_key: str = "",
    transposing_type: str = "",
    notes: str = "",
) -> tuple[bool, str, str]:
    raw = session_state.get(_PENDING_TONE_RESULT_KEY)
    audio = session_state.get(_PENDING_TONE_AUDIO_KEY)
    if not isinstance(raw, dict) or not audio:
        return False, "", "no_pending_tone_take"

    meta = pending_tone_take_meta(session_state)
    instrument = str(instrument or meta.get("instrument") or "").strip()
    display_key = str(display_key or meta.get("display_key") or "").strip()
    transposing_type = str(transposing_type or meta.get("transposing_type") or "").strip()
    selected_pitch_class = str(meta.get("pitch_class_label") or meta.get("selected_pitch_class") or "").strip()

    result = TonePracticeResult(
        duration_sec=float(raw.get("duration_sec") or 0),
        median_note=str(raw.get("median_note") or ""),
        target_note=raw.get("target_note"),
        mean_cents=float(raw.get("mean_cents") or 0),
        max_cents_drift=float(raw.get("max_cents_drift") or 0),
        pitch_stability_score=float(raw.get("pitch_stability_score") or 0),
        volume_stability_score=float(raw.get("volume_stability_score") or 0),
        sustain_seconds=float(raw.get("sustain_seconds") or 0),
        feedback=list(raw.get("feedback") or []),
    )
    fields = build_tone_take_fields(
        session_state,
        result,
        st=st,
        target_note=raw.get("target_note"),
        instrument=instrument,
        display_key=display_key,
        transposing_type=transposing_type,
        notes=notes,
        selected_pitch_class=selected_pitch_class,
    )
    row = add_tone_take(st, fields)
    tid = str(row.get("tone_take_id") or "")
    if not tid:
        session_state[_LAST_TONE_SAVE_STATUS_KEY] = {"ok": False, "error": "catalog_save_failed"}
        return False, "", "catalog_save_failed"

    stored = persist_tone_take_audio(st, tid, audio, mime_type="audio/wav")
    if stored.get("local_path") or stored.get("storage_ref"):
        row = update_tone_take(
            st,
            tid,
            {
                "local_path": stored.get("local_path"),
                "storage_ref": stored.get("storage_ref"),
                "playback_status": stored.get("playback_status"),
                "storage_error": stored.get("storage_error") or "",
                "updated_at": _utc_now_iso(),
            },
        )

    session_state[_LAST_TONE_SAVE_STATUS_KEY] = {
        "ok": True,
        "tone_take_id": tid,
        "playback_status": row.get("playback_status"),
        "storage_ref": bool(row.get("storage_ref")),
        "local_path": bool(row.get("local_path")),
    }
    clear_pending_tone_take(session_state)
    return True, tid, ""


def list_tone_takes(
    *,
    st: Any | None = None,
    instrument: str | None = None,
    note_filter: str = "",
    note_filter_mode: str = NOTE_FILTER_MODE_PLAYER,
    current_instrument_is_transposing: bool = False,
    all_instruments_view: bool = False,
    quality_filter: str = "",
) -> list[dict[str, Any]]:
    catalog = load_media_catalog(st=st)
    rows = normalize_tone_takes(catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else [])

    if instrument and instrument != "All instruments":
        rows = [r for r in rows if tone_take_instrument_matches(r, instrument)]

    if note_filter and note_filter != TONE_HISTORY_NOTE_FILTER_ALL:
        rows = [
            r
            for r in rows
            if note_filter_matches_row(
                r,
                note_filter,
                filter_mode=note_filter_mode,
                current_instrument_is_transposing=current_instrument_is_transposing,
                all_instruments_view=all_instruments_view,
            )
        ]

    if quality_filter == "best":
        rows = [r for r in rows if tone_take_quality(r) == "best"]
    elif quality_filter == "needs_work":
        rows = [r for r in rows if tone_take_quality(r) == "needs_work"]

    return rows


def tone_take_row_summary(row: dict[str, Any]) -> str:
    row = migrate_tone_take(row)
    inst = tone_take_display_instrument(row)
    note_part = tone_take_row_note_part(row)

    dur = float(row.get("duration_seconds") or 0)
    cents = row.get("mean_cents")
    cents_part = f"avg {float(cents):+.0f} cents" if cents is not None else "avg — cents"
    score = float(row.get("pitch_stability_score") or 0)
    stab = "stable" if score >= 78 else ("moderate" if score >= 55 else "unstable")
    created = format_tone_take_display_time(str(row.get("created_at") or ""))
    return f"{inst} · {note_part} · {dur:.0f} sec · {cents_part} · {stab} · {created}"


def delete_tone_take_entry(st: Any | None, tone_take_id: str, *, row: dict[str, Any] | None = None) -> bool:
    tid = str(tone_take_id or "").strip()
    if not tid:
        return False
    if row is None:
        catalog = load_media_catalog(st=st)
        for candidate in catalog.get("tone_takes") or []:
            if isinstance(candidate, dict) and str(candidate.get("tone_take_id") or "") == tid:
                row = migrate_tone_take(candidate)
                break
    if row:
        delete_tone_take_files(row, st=st)
    return delete_tone_take(st, tid)


def load_tone_take_for_playback(
    tone_take_id: str,
    *,
    st: Any | None = None,
) -> tuple[bytes | None, str, dict[str, Any]]:
    tid = str(tone_take_id or "").strip()
    catalog = load_media_catalog(st=st)
    row: dict[str, Any] = {}
    for candidate in catalog.get("tone_takes") or []:
        if isinstance(candidate, dict) and str(candidate.get("tone_take_id") or "") == tid:
            row = migrate_tone_take(candidate)
            break
    if not row or row.get("deleted"):
        ss = _session_state(st)
        if ss is not None:
            ss[_LAST_TONE_LOAD_STATUS_KEY] = {"ok": False, "tone_take_id": tid, "error": "not_found"}
        return None, "not_found", {}

    data, err = load_tone_take_audio(row, st=st)
    playback_status = tone_take_playback_status(row, st=st)
    ss = _session_state(st)
    if ss is not None:
        ss[_LAST_TONE_LOAD_STATUS_KEY] = {
            "ok": bool(data),
            "tone_take_id": tid,
            "error": err or None,
            "bytes": len(data) if data else 0,
        }
        ss[_LAST_TONE_PLAYBACK_STATUS_KEY] = {
            "tone_take_id": tid,
            "status": playback_status,
            "ok": bool(data),
            "error": err or None,
        }
    return data, err, row


def tone_improvement_card(rows: list[dict[str, Any]]) -> str:
    if len(rows) < 2:
        return "Save a few more tone takes to see improvement trends."
    ordered = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
    recent = ordered[-3:]
    older = ordered[:-3] or ordered[:1]

    def _avg(key: str) -> float | None:
        vals = [float(r.get(key)) for r in recent if r.get(key) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _avg_old(key: str) -> float | None:
        vals = [float(r.get(key)) for r in older if r.get(key) is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    new_cents = _avg("mean_cents")
    old_cents = _avg_old("mean_cents")
    new_stab = _avg("pitch_stability_score")
    old_stab = _avg_old("pitch_stability_score")
    parts: list[str] = []
    if new_cents is not None and old_cents is not None:
        delta = new_cents - old_cents
        if abs(delta) >= 2:
            direction = "flatter" if delta < 0 else "sharper"
            parts.append(f"Pitch center shifted {direction} (avg {old_cents:+.0f}¢ → {new_cents:+.0f}¢).")
    if new_stab is not None and old_stab is not None and new_stab - old_stab >= 5:
        parts.append(f"Pitch stability improved ({old_stab:.0f}% → {new_stab:.0f}%).")
    if not parts:
        return f"{len(rows)} saved takes — keep practicing long tones for clearer trends."
    return " ".join(parts)


def build_tone_ami_payload(*, st: Any | None = None, window_days: int = 30) -> dict[str, Any]:
    from media_persistence import build_media_ami_payload

    payload = build_media_ami_payload(st, window_days=window_days)
    return dict(payload.get("tone_history") or {})


def tone_catalog_diagnostics(
    session_state: dict[str, Any],
    *,
    st: Any | None = None,
    active_instrument: str = "",
) -> dict[str, Any]:
    catalog = load_media_catalog(st=st)
    raw = catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else []
    visible = normalize_tone_takes(raw)
    tomb = sum(1 for row in raw if isinstance(row, dict) and row.get("deleted"))
    storage_refs = sum(1 for row in visible if str(row.get("storage_ref") or "").strip())
    metadata_only = sum(
        1
        for row in visible
        if not str(row.get("storage_ref") or "").strip() and not str(row.get("local_path") or "").strip()
    )
    inst_filter = str(active_instrument or "").strip()
    filtered = visible
    if inst_filter and inst_filter != "All instruments":
        filtered = [r for r in visible if str(r.get("instrument") or "").strip().lower() == inst_filter.lower()]

    ami = build_tone_ami_payload(st=st, window_days=30)
    ami_json = str(ami)
    blob_fields = any(token in ami_json for token in ("audio_b64", "base64", "blob", "audio_bytes"))

    return {
        "tone_take_count": len(visible),
        "current_instrument_count": len(filtered),
        "all_instruments_count": len(visible),
        "storage_ref_count": storage_refs,
        "metadata_only_count": metadata_only,
        "deleted_tombstone_count": tomb,
        "last_save_status": session_state.get(_LAST_TONE_SAVE_STATUS_KEY),
        "last_load_status": session_state.get(_LAST_TONE_LOAD_STATUS_KEY),
        "last_playback_status": session_state.get(_LAST_TONE_PLAYBACK_STATUS_KEY),
        "ami_payload_tone_count": ami.get("tone_take_count_total", 0),
        "ami_excludes_raw_audio": not blob_fields,
        "ami_blob_fields_absent": not blob_fields,
    }


def playback_label_for_row(row: dict[str, Any], *, st: Any | None = None) -> str:
    status = tone_take_playback_status(row, st=st)
    return playback_status_label(status)
