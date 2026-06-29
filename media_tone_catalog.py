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
) -> dict[str, Any]:
    instrument_family = ""
    instrument_label = str(instrument or "").strip()
    try:
        from practice_setup_globals import (
            get_active_instrument,
            get_active_instrument_display_name,
        )

        instrument_family = str(get_active_instrument(session_state) or instrument_label).strip()
        if not instrument_label:
            instrument_label = str(get_active_instrument_display_name(session_state) or instrument_family).strip()
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


def cache_pending_tone_take(
    session_state: dict[str, Any],
    *,
    result: TonePracticeResult,
    audio_bytes: bytes,
    target_note: str | None = None,
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


def clear_pending_tone_take(session_state: dict[str, Any]) -> None:
    session_state.pop(_PENDING_TONE_RESULT_KEY, None)
    session_state.pop(_PENDING_TONE_AUDIO_KEY, None)


def pending_tone_take_ready(session_state: dict[str, Any]) -> bool:
    return isinstance(session_state.get(_PENDING_TONE_RESULT_KEY), dict)


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
    quality_filter: str = "",
) -> list[dict[str, Any]]:
    catalog = load_media_catalog(st=st)
    rows = normalize_tone_takes(catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else [])

    if instrument and instrument != "All instruments":
        inst = str(instrument).strip().lower()
        rows = [r for r in rows if str(r.get("instrument") or "").strip().lower() == inst]

    if note_filter:
        nf = note_filter.strip().lower()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            for key in ("written_note", "concert_note", "target_note", "detected_note"):
                val = str(row.get(key) or "")
                if nf in val.lower() or _note_pitch_class(val).lower() == nf:
                    filtered.append(row)
                    break
        rows = filtered

    if quality_filter == "best":
        rows = [r for r in rows if tone_take_quality(r) == "best"]
    elif quality_filter == "needs_work":
        rows = [r for r in rows if tone_take_quality(r) == "needs_work"]

    return rows


def tone_take_row_summary(row: dict[str, Any]) -> str:
    row = migrate_tone_take(row)
    inst = str(row.get("instrument") or "Instrument")
    written = str(row.get("written_note") or "")
    concert = str(row.get("concert_note") or "")
    if written and concert:
        note_part = f"written {_note_pitch_class(written)} / concert {_note_pitch_class(concert)}"
    elif written or concert:
        note_part = written or concert
    else:
        note_part = str(row.get("target_note") or row.get("detected_note") or "—")

    dur = float(row.get("duration_seconds") or 0)
    cents = row.get("mean_cents")
    cents_part = f"avg {float(cents):+.0f} cents" if cents is not None else "avg — cents"
    score = float(row.get("pitch_stability_score") or 0)
    stab = "stable" if score >= 78 else ("moderate" if score >= 55 else "unstable")
    created = str(row.get("created_at") or "")[:10]
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
