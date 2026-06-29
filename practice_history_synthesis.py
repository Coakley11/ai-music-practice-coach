"""Analyze My Practice — full practice-history synthesis payload and progress report."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

_FORBIDDEN_AMI_KEYS = frozenset(
    {
        "audio_b64",
        "audio_bytes",
        "raw_audio",
        "blob",
        "wav_data",
        "last_analysis_audio",
    }
)
_FORBIDDEN_AMI_SUBSTRINGS = ("base64", "blob", "audio_data")
_FAR_CENTS_THRESHOLD = 100.0
_ENHARMONIC_NOTE_LABELS = {
    "C#": "C#/Db",
    "Db": "C#/Db",
    "D#": "D#/Eb",
    "Eb": "D#/Eb",
    "F#": "F#/Gb",
    "Gb": "F#/Gb",
    "G#": "G#/Ab",
    "Ab": "G#/Ab",
    "A#": "A#/Bb",
    "Bb": "A#/Bb",
}
_RECORDING_TYPE_LABELS = {
    "single_recording": "Single recording",
    "multitrack_mix": "Multitrack mix",
    "multitrack_export": "Multitrack export",
    "backing_track_plus_performance": "Backing track + performance",
    "microphone_recording": "Microphone recording",
    "manual_upload": "Manual upload",
}
_GUITAR_FOCUS_TERMS = frozenset({"strumming", "chords", "fret", "fretting", "picking", "capo"})
_WIND_INSTRUMENT_HINTS = frozenset(
    {
        "flute",
        "tenor saxophone",
        "alto saxophone",
        "soprano saxophone",
        "baritone saxophone",
        "clarinet",
        "trumpet",
        "trombone",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _coerce_float(raw: Any) -> float | None:
    try:
        if raw is None or raw == "":
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _format_recording_type_label(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    if not key:
        return "Recording"
    return _RECORDING_TYPE_LABELS.get(key, key.replace("_", " ").strip().title())


def _clip_summary_at_sentence(text: str, *, max_len: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned.rstrip(" ,;")
    chunk = cleaned[:max_len]
    for sep in (". ", "! ", "? "):
        idx = chunk.rfind(sep)
        if idx >= 40:
            return chunk[: idx + 1].strip()
    trimmed = chunk.rsplit(" ", 1)[0].strip()
    return trimmed.rstrip(" ,;") + "."


def _format_written_note(raw: Any) -> str:
    """Display note without octave — e.g. F#4 → F#/Gb."""
    text = str(raw or "").strip().replace("♯", "#").replace("♭", "b")
    if not text:
        return ""
    match = re.match(r"^([A-Ga-g])([#b]?)(\d*)$", text)
    if match:
        pitch = f"{match.group(1).upper()}{match.group(2)}"
        return _ENHARMONIC_NOTE_LABELS.get(pitch, pitch)
    return text


def _format_date_range_label(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%b %d, %Y")
    if start.year == end.year:
        return f"{start.strftime('%b %d')}–{end.strftime('%b %d, %Y')}"
    return f"{start.strftime('%b %d, %Y')}–{end.strftime('%b %d, %Y')}"


def _format_tone_cents_phrase(cents: Any, *, role: str = "recent avg") -> str:
    value = _coerce_float(cents)
    if value is None:
        return ""
    if abs(value) > _FAR_CENTS_THRESHOLD:
        return (
            "The detected pitch was far from target, so this take may have captured the wrong note or octave."
        )
    return f"{role} **{value:.1f}** cents"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if int(count) == 1 else (plural or f"{singular}s")
    return f"{int(count)} {word}"


def _join_natural(items: list[str]) -> str:
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _format_tone_trend_line(trend: dict[str, Any], *, payload: dict[str, Any] | None = None) -> str:
    top_inst = format_instrument_display_name(
        _top_instrument_from_payload(payload or {}),
        payload=payload,
    )
    instrument = format_instrument_display_name(trend.get("instrument"), payload=payload)
    if instrument.lower() == "saxophone" and top_inst.lower() != "saxophone":
        instrument = top_inst
    note = _format_written_note(trend.get("note") or trend.get("written_note") or trend.get("target_note"))
    if _tone_trend_unreliable(trend):
        return (
            f"**{instrument} {note}**: Recent tone takes need a cleaner re-recording "
            f"before pitch progress can be judged. The detected pitch was far from target, "
            f"so this take may have captured the wrong note or octave."
        )
    recent = _format_tone_cents_phrase(trend.get("recent_mean_cents"), role="recent avg")
    older = _format_tone_cents_phrase(trend.get("older_mean_cents"), role="earlier avg")
    parts = [f"**{instrument} {note}**:"]
    if recent:
        parts.append(recent)
    if older:
        parts.append(f"({older})")
    delta = _coerce_float(trend.get("mean_cents_delta"))
    if delta is not None and abs(delta) <= _FAR_CENTS_THRESHOLD and abs(delta) >= 1.0:
        parts.append(f"Δ **{delta:+.1f}** cents")
    return " ".join(parts) + "."


def _tone_trend_unreliable(trend: dict[str, Any]) -> bool:
    recent = _format_tone_cents_phrase(trend.get("recent_mean_cents"), role="recent avg")
    older = _format_tone_cents_phrase(trend.get("older_mean_cents"), role="earlier avg")
    if "wrong note or octave" in recent or "wrong note or octave" in older:
        return True
    for key in ("recent_mean_cents", "older_mean_cents"):
        val = _coerce_float(trend.get(key))
        if val is not None and abs(val) > _FAR_CENTS_THRESHOLD:
            return True
    return False


def _executive_practice_instrument_line(top_song: str, pl: dict[str, Any], *, payload: dict[str, Any]) -> str:
    by_inst = pl.get("practice_time_by_instrument") if isinstance(pl.get("practice_time_by_instrument"), dict) else {}
    if not top_song or not by_inst:
        return ""
    items = sorted(((str(k), int(v or 0)) for k, v in by_inst.items() if str(k).strip()), key=lambda row: -row[1])
    if not items:
        return ""
    total = sum(mins for _, mins in items) or 1
    names = [format_instrument_display_name(key, payload=payload) for key, _ in items]
    if len(items) == 1:
        return f"Most work was on **{top_song}** with **{names[0]}**."
    top_mins = items[0][1]
    if top_mins / total >= 0.6:
        return f"Most work was on **{top_song}** with **{names[0]}**."
    if len(items) == 2 and items[0][1] == items[1][1]:
        return f"Recent work includes **{top_song}** on **{names[0]}** and **{names[1]}**."
    return f"Most work was on **{top_song}** across multiple instruments."


def _format_suggested_next_focus_line(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    token = _normalize_focus_token(text)
    if token and len(text.split()) == 1 and token in {
        "tone",
        "timing",
        "pitch",
        "groove",
        "technique",
        "intonation",
        "articulation",
        "dynamics",
    }:
        return f"Prioritize **{token}** in your next session and save one take as evidence."
    return text


def _format_evidence_used_line(payload: dict[str, Any]) -> str:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    mt = payload.get("multitrack_export_summary") if isinstance(payload.get("multitrack_export_summary"), dict) else {}
    analyzed_exports = _count_analyzed_multitrack_exports(payload)
    export_total = int(mt.get("export_count_total") or 0)
    pl_count = int(pl.get("entry_count_total") or 0)
    ua_count = int(ua.get("analysis_count_total") or 0)
    th_count = int(th.get("tone_take_count_total") or 0)
    evidence = (
        f"Evidence used: {pl_count} practice logs, {ua_count} saved upload analyses, "
        f"and {th_count} tone takes."
    )
    if export_total:
        saved_exports = _plural(export_total, "saved export", "saved exports")
        analyzed_exports_phrase = _plural(
            analyzed_exports,
            "linked analyzed export",
            "linked analyzed exports",
        )
        evidence += f" Multitrack: {saved_exports}, {analyzed_exports_phrase}."
    start, end = _date_range_from_payload(payload)
    if start and end:
        try:
            start_d = date.fromisoformat(start[:10])
            end_d = date.fromisoformat(end[:10])
            evidence += f" Date range: {_format_date_range_label(start_d, end_d)}."
        except ValueError:
            evidence += f" Date range: {start}–{end}."
    return evidence


def _instrument_is_wind(name: str) -> bool:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return False
    if any(term in lowered for term in _WIND_INSTRUMENT_HINTS):
        return True
    return "sax" in lowered or "flute" in lowered or "clarinet" in lowered


def format_instrument_display_name(raw: Any, *, payload: dict[str, Any] | None = None) -> str:
    """Prefer specific instrument names (Tenor Saxophone, Alto Saxophone, Flute)."""
    text = str(raw or "").strip()
    if text:
        lowered = text.lower()
        if lowered not in {"saxophone", "instrument", ""} and (
            "guitar" in lowered
            or "flute" in lowered
            or "tenor" in lowered
            or "alto" in lowered
            or "trumpet" in lowered
            or "piano" in lowered
            or "clarinet" in lowered
            or "trombone" in lowered
        ):
            return text
    candidates: list[str] = []
    if text:
        candidates.append(text)
    if isinstance(payload, dict):
        pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
        ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
        th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
        for key in ("practice_time_by_instrument", "count_by_instrument"):
            block = pl.get(key) if key.startswith("practice") else ua.get(key)
            if isinstance(block, dict):
                candidates.extend(str(k) for k in block.keys() if str(k).strip())
        for rows in (th.get("recent_tone_takes_by_instrument") or {}).values():
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                inst = str(rows[0].get("instrument") or "").strip()
                if inst:
                    candidates.append(inst)
    specific = [
        c
        for c in candidates
        if any(h in c.lower() for h in ("tenor sax", "alto sax", "soprano sax", "baritone sax", "flute"))
    ]
    if specific:
        return specific[0]
    if text and text.lower() != "saxophone":
        return text
    for c in candidates:
        cl = c.lower()
        if c and cl != "saxophone":
            return c
    for c in candidates:
        if c and "tenor sax" in c.lower():
            return c
    for c in candidates:
        if c and "alto sax" in c.lower():
            return c
    return text or "your instrument"


def _normalize_focus_token(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    text = text.replace("_", " ")
    text = text.strip("* ")
    if not text:
        return ""
    for sep in (".", ",", ";"):
        text = text.split(sep)[0].strip()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    return text


def _dedupe_focus_terms(terms: list[str], *, is_wind: bool) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in terms:
        token = _normalize_focus_token(raw)
        if not token:
            continue
        if is_wind and token in _GUITAR_FOCUS_TERMS:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        label = token.replace("/", " / ")
        if label in {"pitch", "intonation", "pitch intonation"}:
            label = "pitch/intonation"
        out.append(label)
    return out


def _format_recommended_focus(terms: list[str], *, is_wind: bool) -> str:
    cleaned = _dedupe_focus_terms(terms, is_wind=is_wind)
    if not cleaned:
        return "Prioritize tone stability, timing, and saving evidence after each session."
    if len(cleaned) == 1:
        return f"Prioritize **{cleaned[0]}** this week."
    if len(cleaned) == 2:
        return f"Prioritize **{cleaned[0]}** and **{cleaned[1]}** this week."
    body = ", ".join(f"**{t}**" for t in cleaned[:-1]) + f", and **{cleaned[-1]}**"
    return f"Prioritize {body} this week."


def _count_analyzed_multitrack_exports(payload: dict[str, Any]) -> int:
    mt = payload.get("multitrack_export_summary") if isinstance(payload.get("multitrack_export_summary"), dict) else {}
    count = int(mt.get("analyzed_export_count") or 0)
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    export_ids: set[str] = set()
    for row in ua.get("recent_analyses") or []:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("export_id") or "").strip()
        if not eid:
            continue
        source = str(row.get("source") or "").strip().lower()
        if source == "multitrack_export" or row.get("coach_summary"):
            export_ids.add(eid)
    return max(count, len(export_ids))


def _avg_rating(entry: dict[str, Any]) -> float | None:
    ratings = entry.get("ratings") if isinstance(entry.get("ratings"), dict) else {}
    vals = [_coerce_float(v) for v in ratings.values()]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _normalize_upload_source(row: dict[str, Any]) -> str:
    explicit = str(row.get("source") or "").strip().lower()
    if explicit == "multitrack_export":
        return "multitrack_export"
    if str(row.get("export_id") or "").strip():
        return "multitrack_export"
    filename = str(row.get("filename") or "").strip().lower()
    if filename.startswith("recording.") or "mic" in filename:
        return "microphone_recording"
    return "manual_upload"


def _normalize_recording_type(row: dict[str, Any]) -> str:
    raw = str(
        row.get("legacy_recording_type")
        or row.get("recording_type")
        or ""
    ).strip().lower()
    source = str(row.get("source") or "").strip().lower()
    has_export = bool(str(row.get("export_id") or "").strip())
    if source == "multitrack_export" or has_export:
        if "mix" in raw or "multitrack mix" in raw:
            return "multitrack_mix"
        return "multitrack_export"
    if "multitrack mix" in raw:
        return "multitrack_mix"
    if "backing" in raw:
        return "backing_track_plus_performance"
    return "single_recording"


def _upload_analysis_display_label(row: dict[str, Any]) -> str:
    """User-facing upload line label — distinguish multitrack-linked analyses."""
    song = row.get("song_title") or row.get("song") or "your take"
    source = str(row.get("source") or "").strip().lower()
    export_name = str(row.get("export_name") or "").strip()
    rtype = _format_recording_type_label(row.get("recording_type") or "recording")
    if source == "multitrack_export" or row.get("export_id"):
        if export_name:
            return f"**{export_name}** (Multitrack export → Upload Analysis)"
        return f"**{song}** (Multitrack export → Upload Analysis)"
    return f"**{song}** ({rtype})"


def _category_observations(summary: dict[str, Any]) -> dict[str, list[str]]:
    categories = summary.get("categories") if isinstance(summary.get("categories"), dict) else {}
    out: dict[str, list[str]] = {}
    for key in ("timing", "pitch", "tone", "groove", "technique", "musicality", "articulation", "dynamics"):
        block = categories.get(key) if isinstance(categories.get(key), dict) else {}
        bits: list[str] = []
        for item in block.get("findings") or []:
            text = str(item).strip()
            if text:
                bits.append(text[:240])
        for item in block.get("tips") or []:
            text = str(item).strip()
            if text and text not in bits:
                bits.append(text[:240])
        if bits:
            out[key] = bits[:4]
    return out


def _score_strengths_weaknesses(summary: dict[str, Any]) -> tuple[list[str], list[str]]:
    scores = summary.get("scores") if isinstance(summary.get("scores"), dict) else {}
    if not scores:
        for key in ("timing", "pitch", "tone", "groove", "technique", "musicality", "confidence"):
            val = summary.get(key)
            if val is not None:
                scores[key] = val
    ranked = sorted(
        ((k, _coerce_float(v) or 0) for k, v in scores.items()),
        key=lambda x: x[1],
    )
    if not ranked:
        return [], []
    strengths = [f"{k} ({int(v)})" for k, v in ranked[-2:] if v >= 60]
    weaknesses = [f"{k} ({int(v)})" for k, v in ranked[:2] if v < 75]
    return strengths, weaknesses


def compact_upload_analysis_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    """Compact saved upload analysis for AMI — summaries only, no audio."""
    from media_state import compact_recording_for_ami, is_recording_tombstone, migrate_uploaded_recording

    pre = dict(entry or {})
    row = migrate_uploaded_recording(entry)
    for key in ("source", "export_id", "export_name", "song_title"):
        if pre.get(key) and not row.get(key):
            row[key] = pre[key]
    if is_recording_tombstone(row):
        return {}
    base = compact_recording_for_ami(row)
    if not base:
        return {}
    summary = row.get("analysis_summary") if isinstance(row.get("analysis_summary"), dict) else {}
    obs = _category_observations(summary)
    strengths, weaknesses = _score_strengths_weaknesses(summary)
    scores = summary.get("scores") if isinstance(summary.get("scores"), dict) else {}
    tags: list[str] = []
    for key in ("timing", "pitch", "tone", "groove", "technique"):
        val = _coerce_float(scores.get(key) if scores else summary.get(key))
        if val is not None and val < 70:
            tags.append(key)
    compact: dict[str, Any] = {
        **base,
        "analysis_id": row.get("recording_id"),
        "created_at": row.get("created_at") or row.get("updated_at"),
        "source": _normalize_upload_source(row),
        "recording_type": _normalize_recording_type(row),
        "song_title": row.get("song") or base.get("song"),
        "export_id": row.get("export_id"),
        "coach_summary": summary.get("coach_summary") or base.get("coach_summary"),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "timing_observations": obs.get("timing", []),
        "pitch_observations": obs.get("pitch", []),
        "tone_observations": obs.get("tone", []),
        "rhythm_observations": obs.get("groove", []) or obs.get("timing", []),
        "articulation_observations": obs.get("articulation", []),
        "dynamics_observations": obs.get("dynamics", []) or obs.get("musicality", []),
        "improvement_suggestions": (summary.get("practice_plan") or [])[:4]
        if isinstance(summary.get("practice_plan"), list)
        else [],
        "scores": scores or {
            k: summary.get(k)
            for k in ("timing", "pitch", "tone", "groove", "technique", "musicality", "confidence")
            if summary.get(k) is not None
        },
        "tags": tags,
        "weakest_category": summary.get("weakest_category") or base.get("weakest_category"),
        "strongest_category": summary.get("strongest_category") or base.get("strongest_category"),
    }
    if row.get("instrument"):
        compact["instrument"] = row.get("instrument")
    return {k: v for k, v in compact.items() if v not in (None, "", [], {})}


def compact_practice_log_for_ami(entry: dict[str, Any]) -> dict[str, Any]:
    """Compact practice log entry for AMI evidence list."""
    from practice_log_state import migrate_practice_log_entry

    row = migrate_practice_log_entry(entry)
    if row.get("deleted"):
        return {}
    rating = _avg_rating(row)
    out: dict[str, Any] = {
        "log_entry_id": row.get("session_id"),
        "date": row.get("date"),
        "updated_at": row.get("updated_at"),
        "instrument": row.get("instrument"),
        "song_title": row.get("active_song") or row.get("song"),
        "focus_area": row.get("focus_area") or row.get("focus"),
        "duration_minutes": row.get("duration_minutes"),
        "notes": row.get("notes"),
        "practice_rating": round(rating, 2) if rating is not None else None,
        "what_went_well": row.get("what_went_well"),
        "what_was_hard": row.get("what_was_hard"),
        "next_step": row.get("next_step"),
        "linked_upload_analysis_ids": row.get("linked_upload_analysis_ids") or [],
        "linked_tone_take_ids": row.get("linked_tone_take_ids") or [],
        "linked_export_ids": row.get("linked_export_ids") or [],
    }
    if row.get("linked_upload_analysis_id"):
        ids = list(out.get("linked_upload_analysis_ids") or [])
        lid = str(row.get("linked_upload_analysis_id"))
        if lid and lid not in ids:
            ids.append(lid)
        out["linked_upload_analysis_ids"] = ids
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def _focus_area_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in entries:
        focus = str(entry.get("focus_area") or entry.get("focus") or "").strip().lower()
        if focus:
            counts[focus] += 1
    return dict(counts.most_common(8))


def _practice_time_by_key(entries: list[dict[str, Any]], key: str) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for entry in entries:
        label = str(entry.get(key) or "").strip()
        if not label:
            continue
        try:
            mins = int(entry.get("duration_minutes") or 0)
        except (TypeError, ValueError):
            mins = 0
        totals[label] += max(0, mins)
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True)[:8])


def build_practice_log_ami_summary(entries: list[dict[str, Any]], *, window_days: int) -> dict[str, Any]:
    from practice_log_state import compute_practice_log_summary, filter_practice_log_entries

    visible = filter_practice_log_entries(entries, {"window_days": window_days}) if window_days > 0 else entries
    summary = compute_practice_log_summary(entries, window_days=window_days)
    recent = [compact_practice_log_for_ami(e) for e in visible[:30]]
    recent = [r for r in recent if r]
    return {
        "entry_count_total": summary.get("session_count", len(recent)),
        "recent_entries": recent,
        "focus_area_counts": _focus_area_counts(visible),
        "practice_time_by_instrument": _practice_time_by_key(visible, "instrument"),
        "practice_time_by_song": _practice_time_by_key(visible, "active_song"),
        "window_days": window_days,
    }


def _recurring_items(analyses: list[dict[str, Any]], field: str) -> list[str]:
    counts: Counter[str] = Counter()
    for row in analyses:
        for item in row.get(field) or []:
            text = str(item).strip().lower()
            if text:
                counts[text] += 1
    return [text for text, n in counts.most_common(5) if n >= 1]


def _score_trend_rows(analyses: list[dict[str, Any]], score_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(analyses, key=lambda r: str(r.get("created_at") or "")):
        scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
        val = _coerce_float(scores.get(score_key) or row.get(score_key))
        if val is None:
            continue
        rows.append(
            {
                "date": row.get("created_at"),
                "song": row.get("song_title") or row.get("song"),
                "score": round(val, 1),
            }
        )
    return rows[-8:]


def build_upload_analysis_ami_summary(
    uploads: list[dict[str, Any]],
    *,
    window_days: int,
) -> dict[str, Any]:
    compact = [compact_upload_analysis_for_ami(u) for u in uploads]
    compact = [c for c in compact if c]
    by_source: Counter[str] = Counter()
    by_instrument: Counter[str] = Counter()
    by_song: Counter[str] = Counter()
    for row in compact:
        by_source[str(row.get("source") or "manual_upload")] += 1
        inst = str(row.get("instrument") or "").strip()
        if inst:
            by_instrument[inst] += 1
        song = str(row.get("song_title") or row.get("song") or "").strip()
        if song:
            by_song[song] += 1
    return {
        "analysis_count_total": len(compact),
        "count_by_source": dict(by_source),
        "count_by_instrument": dict(by_instrument),
        "count_by_song": dict(by_song),
        "recent_analyses": compact[:16],
        "recurring_strengths": _recurring_items(compact, "strengths"),
        "recurring_weaknesses": _recurring_items(compact, "weaknesses"),
        "timing_trends": _score_trend_rows(compact, "timing"),
        "pitch_trends": _score_trend_rows(compact, "pitch"),
        "tone_trends": _score_trend_rows(compact, "tone"),
        "rhythm_trends": _score_trend_rows(compact, "groove"),
        "window_days": window_days,
    }


def build_multitrack_export_context_summary(
    exports: list[dict[str, Any]],
    upload_analyses: list[dict[str, Any]],
    *,
    window_days: int,
) -> dict[str, Any]:
    """Export metadata only — distinguish analyzed vs waiting; no playing-quality inference."""
    from media_state import compact_multitrack_export_for_ami, is_multitrack_export_tombstone, migrate_multitrack_export

    analyzed_export_ids: set[str] = set()
    for row in upload_analyses:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("export_id") or "").strip()
        source = str(row.get("source") or "").strip().lower()
        if eid and source == "multitrack_export":
            analyzed_export_ids.add(eid)
        elif eid and row.get("coach_summary"):
            analyzed_export_ids.add(eid)

    compact_exports: list[dict[str, Any]] = []
    with_analysis: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    for entry in exports:
        row = migrate_multitrack_export(entry)
        if is_multitrack_export_tombstone(row):
            continue
        base = compact_multitrack_export_for_ami(row)
        if not base:
            continue
        eid = str(base.get("export_id") or "").strip()
        has_analysis = eid in analyzed_export_ids or bool(base.get("coach_summary"))
        enriched = {
            **base,
            "sent_to_upload_analysis": bool(row.get("linked_recording_id") or eid in analyzed_export_ids),
            "has_saved_analysis_result": has_analysis,
            "usable_as_playing_evidence": has_analysis,
        }
        compact_exports.append(enriched)
        if has_analysis:
            with_analysis.append(enriched)
        else:
            waiting.append(enriched)

    compact_exports.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    with_analysis_ids = {str(r.get("export_id") or "").strip() for r in with_analysis if r.get("export_id")}
    upload_only_analyzed = analyzed_export_ids - with_analysis_ids
    analyzed_total = len(with_analysis) + len(upload_only_analyzed)
    return {
        "export_count_total": len(compact_exports),
        "recent_exports": compact_exports[:12],
        "exports_with_saved_analysis": with_analysis[:12],
        "exports_waiting_for_analysis": waiting[:12],
        "analyzed_export_count": analyzed_total,
        "unanalyzed_export_count": max(0, len(compact_exports) - analyzed_total),
        "window_days": window_days,
    }


def scan_ami_payload_for_forbidden_data(payload: Any, *, _depth: int = 0) -> list[str]:
    """Return paths to forbidden audio/blob fields if any."""
    if _depth > 12:
        return []
    violations: list[str] = []
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return ["<binary-root>"]
    if isinstance(payload, dict):
        for key, val in payload.items():
            key_l = str(key).lower()
            if key_l in _FORBIDDEN_AMI_KEYS:
                violations.append(str(key))
            elif isinstance(val, str) and len(val) > 200 and "base64" in val.lower():
                violations.append(str(key))
            violations.extend(scan_ami_payload_for_forbidden_data(val, _depth=_depth + 1))
    elif isinstance(payload, list):
        for val in payload[:50]:
            violations.extend(scan_ami_payload_for_forbidden_data(val, _depth=_depth + 1))
            if violations:
                break
    return violations


def ami_payload_safety_checks(payload: dict[str, Any]) -> dict[str, Any]:
    violations = scan_ami_payload_for_forbidden_data(payload)
    try:
        size_estimate = len(json.dumps(payload, default=str))
    except Exception:
        size_estimate = 0
    return {
        "raw_audio_excluded": True,
        "base64_excluded": True,
        "blob_fields_excluded": True,
        "deleted_items_excluded": True,
        "forbidden_field_violations": violations,
        "payload_size_estimate_bytes": size_estimate,
        "payload_size_reasonable": size_estimate < 500_000,
    }


def ami_payload_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    mt = payload.get("multitrack_export_summary") if isinstance(payload.get("multitrack_export_summary"), dict) else {}
    safety = payload.get("safety_checks") if isinstance(payload.get("safety_checks"), dict) else {}
    return {
        "practice_log_entry_count": pl.get("entry_count_total", 0),
        "saved_upload_analysis_count": ua.get("analysis_count_total", 0),
        "tone_take_count": th.get("tone_take_count_total", 0),
        "multitrack_export_count": mt.get("export_count_total", 0),
        "analyzed_export_count": mt.get("analyzed_export_count", 0),
        "unanalyzed_export_count": mt.get("unanalyzed_export_count", 0),
        "raw_audio_excluded": safety.get("raw_audio_excluded", True),
        "base64_excluded": safety.get("base64_excluded", True),
        "blob_fields_excluded": safety.get("blob_fields_excluded", True),
        "deleted_items_excluded": safety.get("deleted_items_excluded", True),
        "payload_size_estimate_bytes": safety.get("payload_size_estimate_bytes", 0),
        "forbidden_field_violations": safety.get("forbidden_field_violations", []),
    }


def _date_range_from_payload(payload: dict[str, Any]) -> tuple[str, str]:
    dates: list[date] = []
    for block_key in ("practice_log_summary", "upload_analysis_summary", "tone_history_summary"):
        block = payload.get(block_key) if isinstance(payload.get(block_key), dict) else {}
        for row in block.get("recent_entries") or block.get("recent_analyses") or []:
            if isinstance(row, dict):
                d = _parse_date(row.get("date") or row.get("created_at"))
                if d:
                    dates.append(d)
    tone = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    for rows in (tone.get("recent_tone_takes_by_instrument") or {}).values():
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    d = _parse_date(row.get("created_at"))
                    if d:
                        dates.append(d)
    if not dates:
        return "", ""
    start, end = min(dates), max(dates)
    return start.isoformat(), end.isoformat()


def build_practice_progress_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Rule-based progress report from synthesized AMI payload (10 sections)."""
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    mt = payload.get("multitrack_export_summary") if isinstance(payload.get("multitrack_export_summary"), dict) else {}
    safety = payload.get("safety_checks") if isinstance(payload.get("safety_checks"), dict) else {}

    recent_logs = pl.get("recent_entries") or []
    recent_analyses = ua.get("recent_analyses") or []
    tone_trends = th.get("improvement_trends_by_instrument_and_note") or th.get("improvement_trends") or []

    top_instrument = ""
    if pl.get("practice_time_by_instrument"):
        top_instrument = next(iter(pl["practice_time_by_instrument"]), "")
    top_song = ""
    if pl.get("practice_time_by_song"):
        items = sorted(
            ((str(k), int(v or 0)) for k, v in pl["practice_time_by_song"].items()),
            key=lambda row: -row[1],
        )
        top_song = items[0][0] if items else ""

    exec_bits: list[str] = []
    coach_summary = _build_coach_executive_summary(payload)

    activity_lines: list[str] = []
    if pl.get("entry_count_total"):
        mins = sum(int(r.get("duration_minutes") or 0) for r in recent_logs if isinstance(r, dict))
        activity_lines.append(
            f"You logged **{_plural(int(pl['entry_count_total']), 'session')}** totaling about **{mins}** minutes."
        )
    if pl.get("focus_area_counts"):
        focus_labels = []
        for key, count in list(pl["focus_area_counts"].items())[:4]:
            label = _normalize_focus_token(key) or str(key).strip()
            if label:
                focus_labels.append(f"**{label}** ({count})")
        if focus_labels:
            activity_lines.append(f"Top focus areas: {', '.join(focus_labels)}.")
    if not activity_lines:
        activity_lines.append("No practice log entries in the current window.")

    upload_lines: list[str] = []
    for row in recent_analyses[:3]:
        if not isinstance(row, dict):
            continue
        song = row.get("song_title") or row.get("song") or "your take"
        rtype = _format_recording_type_label(_normalize_recording_type(row))
        strengths = [str(s).strip() for s in (row.get("strengths") or []) if str(s).strip()]
        weaknesses = [str(w).strip() for w in (row.get("weaknesses") or []) if str(w).strip()]
        strongest = strengths[0] if strengths else "steady playing"
        weakest = weaknesses[0] if weaknesses else "consistency"
        upload_lines.append(
            f"**{song}** ({rtype}): Strongest area — {strongest}. Needs work — {weakest}."
        )
        upload_lines.append(
            f"  Next action: record one short pass of **{song}** and compare in Upload Analysis."
        )
    if not upload_lines:
        upload_lines.append(
            "No saved upload analyses yet — record a take and use **Save to History** for song-level evidence."
        )

    tone_lines: list[str] = []
    for trend in tone_trends[:3]:
        if not isinstance(trend, dict):
            continue
        tone_lines.append(_format_tone_trend_line(trend, payload=payload))
    best = th.get("best_pitch_stability") or []
    if best and not tone_lines:
        row = best[0] if isinstance(best[0], dict) else {}
        tone_lines.append(
            f"Best pitch stability: **{format_instrument_display_name(row.get('instrument'), payload=payload)} "
            f"{row.get('written_note') or row.get('target_note')}**."
        )
    if not tone_lines:
        tone_lines.append("No tone/tuner takes in the current window.")

    cross_lines: list[str] = []
    focus_tone = any("tone" in str(k).lower() for k in (pl.get("focus_area_counts") or {}))
    if focus_tone and th.get("tone_take_count_total"):
        cross_lines.append(
            f"Your logs emphasize **tone** and you saved **{_plural(int(th['tone_take_count_total']), 'tone take')}** — "
            "isolated long-tone work is showing up in your evidence."
        )
    if ua.get("analysis_count_total") and th.get("tone_take_count_total"):
        cross_lines.append(
            "Compare upload-analysis tone scores with tone-take pitch stability to see if long-tone work transfers."
        )
    if not cross_lines:
        cross_lines.append("Link practice-log focus areas to saved analyses and tone takes as you build history.")

    improvements: list[str] = []
    for trend in tone_trends:
        delta = _coerce_float(trend.get("mean_cents_delta") if isinstance(trend, dict) else None)
        if delta is not None and abs(delta) >= 3 and delta < 0 and abs(delta) <= _FAR_CENTS_THRESHOLD:
            improvements.append(
                f"Pitch drift reduced on **{format_instrument_display_name(trend.get('instrument'), payload=payload)} "
                f"{_format_written_note(trend.get('note') or trend.get('written_note'))}** ({delta:+.1f} cents)."
            )
    for row in recent_analyses:
        if not isinstance(row, dict):
            continue
        strengths = row.get("strengths") or []
        for s in strengths[:1]:
            improvements.append(f"Upload analysis strength: **{s}** on **{row.get('song_title') or 'take'}**.")
    timing = ua.get("timing_trends") or []
    if len(timing) >= 2:
        first, last = timing[0], timing[-1]
        if _coerce_float(last.get("score")) and _coerce_float(first.get("score")):
            if last["score"] > first["score"]:
                improvements.append("Timing scores trend upward across recent saved analyses.")
    if pl.get("entry_count_total"):
        improvements.append("You are saving practice evidence, which makes progress easier to track.")
    if not improvements:
        improvements.append("Keep logging sessions and saving analyses to surface measurable improvements.")

    needs_work: list[str] = []
    for w in ua.get("recurring_weaknesses") or []:
        needs_work.append(f"Recurring in uploads: **{w}**.")
    waiting = mt.get("exports_waiting_for_analysis") or []
    linked_export_ids: set[str] = set()
    for row in ua.get("recent_analyses") or []:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("export_id") or "").strip()
        if eid and (str(row.get("source") or "").strip().lower() == "multitrack_export" or row.get("coach_summary")):
            linked_export_ids.add(eid)
    if linked_export_ids:
        waiting = [
            row
            for row in waiting
            if isinstance(row, dict) and str(row.get("export_id") or "").strip() not in linked_export_ids
        ]
    if waiting:
        names = [str(r.get("export_name") or r.get("song") or "export") for r in waiting[:3] if isinstance(r, dict)]
        export_phrase = _plural(len(waiting), "export", "exports")
        verb = "needs" if len(waiting) == 1 else "need"
        needs_work.append(
            f"**{len(waiting)}** saved multitrack {export_phrase} still {verb} a linked Upload Analysis "
            f"({', '.join(names)})."
        )
    for trend in tone_trends:
        if not isinstance(trend, dict):
            continue
        stab = _coerce_float(trend.get("pitch_stability_delta"))
        if stab is not None and stab < -5:
            needs_work.append(
                f"Pitch stability slipped on **{format_instrument_display_name(trend.get('instrument'), payload=payload)} "
                f"{_format_written_note(trend.get('note') or trend.get('written_note'))}**."
            )
    hard = pl.get("recent_entries") or []
    for row in hard[:3]:
        if isinstance(row, dict) and row.get("what_was_hard"):
            needs_work.append(f"Practice log challenge: **{row['what_was_hard']}**.")
    if not needs_work:
        needs_work.append("No recurring weaknesses detected yet — save more analyses for sharper coaching.")

    next_plan = _build_thirty_minute_plan(payload)

    evidence = _format_evidence_used_line(payload)

    return {
        "title": "Analyze My Practice — Progress Report",
        "executive_summary": coach_summary,
        "practice_activity": activity_lines,
        "upload_analysis_findings": upload_lines,
        "tone_tuner_findings": tone_lines,
        "cross_evidence_connections": cross_lines,
        "improvements": improvements[:8],
        "needs_work": needs_work[:8],
        "recommended_next_practice_plan": next_plan[:6],
        "evidence_used": evidence,
        "data_safety_confirmation": {
            "raw_audio_excluded": safety.get("raw_audio_excluded", True),
            "base64_excluded": safety.get("base64_excluded", True),
            "deleted_items_excluded": safety.get("deleted_items_excluded", True),
            "payload_size_reasonable": safety.get("payload_size_reasonable", True),
        },
    }


def format_progress_report_markdown(report: dict[str, Any]) -> str:
    """Render progress report sections as markdown for UI / instant solver."""
    _BARE = frozenset({"tone", "timing", "pitch", "groove", "technique", "intonation"})

    def _clean(item: Any) -> str:
        text = str(item or "").strip()
        return "" if not text or text.lower() in _BARE else text

    sections = [
        ("Executive Summary", report.get("executive_summary")),
        ("Practice Activity", report.get("practice_activity")),
        ("Upload Analysis Findings", report.get("upload_analysis_findings")),
        ("Tone & Tuner Findings", report.get("tone_tuner_findings")),
        ("Cross-Evidence Connections", report.get("cross_evidence_connections")),
        ("Improvements", report.get("improvements")),
        ("Needs Work", report.get("needs_work")),
        ("Recommended Next Practice Plan", report.get("recommended_next_practice_plan")),
        ("Evidence Used", report.get("evidence_used")),
    ]
    lines = [f"# {report.get('title', 'Analyze My Practice — Progress Report')}", ""]
    for heading, body in sections:
        if isinstance(body, list):
            items = [line for line in (_clean(item) for item in body) if line]
            if not items:
                continue
            lines.append(f"## {heading}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
        else:
            cleaned = _clean(body)
            if not cleaned:
                continue
            lines.append(f"## {heading}")
            if heading == "Executive Summary":
                lines.append(cleaned)
            else:
                lines.append(f"- {cleaned}")
            lines.append("")
    safety = report.get("data_safety_confirmation") if isinstance(report.get("data_safety_confirmation"), dict) else {}
    if safety:
        lines.append("## Data Safety Confirmation")
        lines.append(
            f"- Raw audio excluded: **{safety.get('raw_audio_excluded', True)}** · "
            f"Base64 excluded: **{safety.get('base64_excluded', True)}** · "
            f"Deleted items excluded: **{safety.get('deleted_items_excluded', True)}**"
        )
    return "\n".join(lines).strip()


LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY = "latest_practice_analysis_summary"
LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY = "latest_practice_analysis_created_at"
LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY = "latest_practice_analysis_evidence_counts"
LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY = "latest_practice_analysis_full_report"
LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY = "latest_practice_analysis_handoff_status"

PRACTICE_ANALYSIS_PERSIST_KEYS: tuple[str, ...] = (
    LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY,
    LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY,
    LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY,
    LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY,
    LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY,
)


def _top_song_from_payload(payload: dict[str, Any]) -> str:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    by_song = pl.get("practice_time_by_song") if isinstance(pl.get("practice_time_by_song"), dict) else {}
    if by_song:
        items = sorted(((str(k), int(v or 0)) for k, v in by_song.items() if str(k).strip()), key=lambda row: -row[1])
        if items:
            return items[0][0]
    songs = pl.get("most_practiced_songs")
    if isinstance(songs, list) and songs:
        return str(songs[0] or "").strip()
    return ""


def _top_instrument_from_payload(payload: dict[str, Any]) -> str:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    by_inst = pl.get("practice_time_by_instrument") if isinstance(pl.get("practice_time_by_instrument"), dict) else {}
    if by_inst:
        items = sorted(((str(k), int(v or 0)) for k, v in by_inst.items() if str(k).strip()), key=lambda row: -row[1])
        if items:
            return format_instrument_display_name(items[0][0], payload=payload)
    return ""


def _build_coach_executive_summary(payload: dict[str, Any]) -> str:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    tone_trends = th.get("improvement_trends_by_instrument_and_note") or th.get("improvement_trends") or []
    top_song = _top_song_from_payload(payload)
    sentences: list[str] = []

    entry_count = int(pl.get("entry_count_total") or 0)
    if entry_count:
        mins = sum(int(r.get("duration_minutes") or 0) for r in (pl.get("recent_entries") or []) if isinstance(r, dict))
        session_word = "session" if entry_count == 1 else "sessions"
        minute_part = f" totaling {mins} minutes" if mins else ""
        sentences.append(f"You logged {entry_count} practice {session_word}{minute_part}.")

    if top_song:
        inst_line = _executive_practice_instrument_line(top_song, pl, payload=payload)
        if inst_line:
            sentences.append(inst_line.replace("**", "").replace("Most work was on ", "Recent work includes ").replace(" across multiple instruments.", " across multiple instruments."))

    strengths: list[str] = []
    weaknesses: list[str] = []
    for row in ua.get("recent_analyses") or []:
        if not isinstance(row, dict):
            continue
        for s in row.get("strengths") or []:
            token = _normalize_focus_token(s)
            if token and token not in strengths:
                strengths.append(token)
        for w in row.get("weaknesses") or []:
            token = _normalize_focus_token(w)
            if token and token not in weaknesses:
                weaknesses.append(token)
    if strengths or weaknesses:
        strength_text = _join_natural(strengths[:2]) if strengths else "steady playing"
        weakness_text = _join_natural(weaknesses[:2]) if weaknesses else "consistency"
        sentences.append(
            f"Upload Analysis shows {strength_text} as strengths, while {weakness_text} are the main areas to improve."
        )
    elif ua.get("analysis_count_total"):
        sentences.append("Saved upload analyses provide playing-quality evidence for your recent work.")

    if tone_trends and isinstance(tone_trends[0], dict) and _tone_trend_unreliable(tone_trends[0]):
        inst = format_instrument_display_name(tone_trends[0].get("instrument"), payload=payload)
        note = _format_written_note(tone_trends[0].get("note"))
        sentences.append(
            f"Recent {inst} {note} tone takes need a cleaner re-recording before pitch progress can be judged."
        )

    next_bits: list[str] = []
    if tone_trends and isinstance(tone_trends[0], dict):
        note = _format_written_note(tone_trends[0].get("note"))
        if note:
            next_bits.append(f"cleaner {note} long tones")
    if top_song:
        next_bits.append(f"one short {top_song} recording")
    next_bits.append("a saved Upload Analysis comparison")
    if next_bits:
        focus = ", ".join(next_bits[:-1]) + f", and {next_bits[-1]}" if len(next_bits) > 1 else next_bits[0]
        sentences.append(f"Your next session should focus on {focus}.")

    if not sentences:
        return (
            "Log practice sessions and save upload analyses or tone takes to build a richer progress report."
        )
    return " ".join(sentences[:3])


def _build_thirty_minute_plan(payload: dict[str, Any]) -> list[str]:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    tone_trends = th.get("improvement_trends_by_instrument_and_note") or th.get("improvement_trends") or []
    top_song = _top_song_from_payload(payload)
    top_inst = _top_instrument_from_payload(payload) or format_instrument_display_name(
        next(iter(pl.get("practice_time_by_instrument") or {}), ""),
        payload=payload,
    )
    note = ""
    if tone_trends and isinstance(tone_trends[0], dict):
        note = _format_written_note(tone_trends[0].get("note"))
    note_phrase = f"{top_inst} {note}".strip() if note else top_inst
    plan: list[str] = [
        f"5 min — Long tones: {note_phrase} with metronome. Focus on steady air and stable center pitch.",
        "8 min — Pitch/intonation drill: Play slow scale tones. Hold each note for 4 beats and listen for center pitch.",
    ]
    if top_song:
        plan.append(
            f"10 min — {top_song} section pass: Record one short section of {top_song}, not the whole song. "
            "Focus on pitch and tone consistency."
        )
    else:
        plan.append(
            "10 min — Repertoire pass: Record one short section and focus on pitch and tone consistency."
        )
    plan.extend(
        [
            "5 min — Listen back: Run Upload Analysis and compare pitch/tone against your previous report.",
            "2 min — Log notes: Save one short reflection on what improved and what still felt unstable.",
        ]
    )
    return plan


def _evidence_counts_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}
    mt = payload.get("multitrack_export_summary") if isinstance(payload.get("multitrack_export_summary"), dict) else {}
    return {
        "practice_logs": int(pl.get("entry_count_total") or 0),
        "upload_analyses": int(ua.get("analysis_count_total") or 0),
        "tone_takes": int(th.get("tone_take_count_total") or 0),
        "multitrack_exports": int(mt.get("export_count_total") or 0),
        "analyzed_exports": _count_analyzed_multitrack_exports(payload),
        "top_song": _top_song_from_payload(payload),
        "top_instrument": _top_instrument_from_payload(payload),
    }


def _empty_log_page_analysis_summary(*, window_days: int = 14) -> dict[str, str]:
    return {
        "practice_summary": (
            f"No saved practice evidence in the last **{window_days}** days yet. "
            "Log a session, save an Upload Analysis, or record tone takes to build your first summary."
        ),
        "improvement_notes": (
            "Once you have logs plus upload analyses or tone takes, improvement patterns will appear here."
        ),
        "upload_recording_review": (
            "No saved upload analyses yet. Record a take on **Upload Analysis** and use **Save to History**."
        ),
        "tone_tuner_notes": (
            "No tone/tuner takes saved yet. Use **Practice → Tone & Tuner** and save a take after analysis."
        ),
        "recommended_next_session": (
            "Log today's practice, save one tone take, and send one recording to Upload Analysis this week."
        ),
        "recommended_focus_this_week": "Start with tone stability, timing, and saving evidence after each session.",
        "evidence_used": "Evidence used: **0** practice logs, **0** upload analyses, **0** tone takes, **0** analyzed exports.",
    }


def build_log_page_analysis_summary(payload: dict[str, Any]) -> dict[str, str]:
    """Concise action-oriented summary for the Practice Log page."""
    counts = _evidence_counts_from_payload(payload)
    total = counts["practice_logs"] + counts["upload_analyses"] + counts["tone_takes"]
    window_days = int(
        (payload.get("practice_log_summary") or {}).get("window_days")
        or payload.get("window_days")
        or 14
    )
    if total == 0 and counts["multitrack_exports"] == 0:
        return _empty_log_page_analysis_summary(window_days=window_days)

    report = payload.get("progress_report") if isinstance(payload.get("progress_report"), dict) else {}
    if not report:
        report = build_practice_progress_report(payload)

    pl = payload.get("practice_log_summary") if isinstance(payload.get("practice_log_summary"), dict) else {}
    ua = payload.get("upload_analysis_summary") if isinstance(payload.get("upload_analysis_summary"), dict) else {}
    th = payload.get("tone_history_summary") if isinstance(payload.get("tone_history_summary"), dict) else {}

    top_instrument = ""
    top_focus = ""
    if pl.get("practice_time_by_instrument"):
        top_instrument = next(iter(pl["practice_time_by_instrument"]), "")
    if pl.get("focus_area_counts"):
        top_focus = next(iter(pl["focus_area_counts"]), "")

    focus_phrase = _normalize_focus_token(top_focus) or "general practice"
    instrument_phrase = format_instrument_display_name(top_instrument, payload=payload)

    practice_summary = (
        f"You worked mostly on **{instrument_phrase}**"
        + (f" with focus on **{focus_phrase}**" if top_focus else "")
        + ". Recent saved evidence includes "
        f"**{counts['practice_logs']}** practice log(s), **{counts['upload_analyses']}** upload analysis(es), "
        f"**{counts['tone_takes']}** tone take(s)"
        + (
            f", and **{counts['analyzed_exports']}** analyzed multitrack export(s)."
            if counts["analyzed_exports"]
            else "."
        )
    )

    improvements = report.get("improvements") or []
    improvement_notes = " ".join(str(x) for x in improvements[:2]) if improvements else (
        "Keep logging sessions and saving analyses to surface measurable improvements."
    )

    upload_lines = report.get("upload_analysis_findings") or []
    upload_recording_review = str(upload_lines[0]) if upload_lines else (
        "No saved upload analyses yet — record a take and save to history for song-level feedback."
    )

    tone_lines = report.get("tone_tuner_findings") or []
    tone_tuner_notes = str(tone_lines[0]) if tone_lines else (
        "No tone/tuner takes in the current window."
    )

    next_plan = report.get("recommended_next_practice_plan") or []
    recommended_next_session = " ".join(str(x) for x in next_plan[:2]) if next_plan else (
        str(pl.get("suggested_next_focus") or "Log a session and save one piece of evidence today.")
    )

    focus_bits: list[str] = []
    if pl.get("focus_area_counts"):
        focus_bits.extend(list(pl["focus_area_counts"].keys())[:3])
    needs = report.get("needs_work") or []
    for item in needs[:2]:
        text = str(item).replace("Recurring in uploads: ", "").strip("* ")
        if text:
            focus_bits.append(text[:80])
    is_wind = _instrument_is_wind(instrument_phrase)
    recommended_focus = _format_recommended_focus(focus_bits, is_wind=is_wind)

    evidence_used = str(report.get("evidence_used") or (
        f"Evidence used: **{counts['practice_logs']}** practice logs, "
        f"**{counts['upload_analyses']}** upload analyses, **{counts['tone_takes']}** tone takes, "
        f"**{counts['analyzed_exports']}** analyzed multitrack export(s)."
    ))

    return {
        "practice_summary": practice_summary,
        "improvement_notes": improvement_notes,
        "upload_recording_review": upload_recording_review,
        "tone_tuner_notes": tone_tuner_notes,
        "recommended_next_session": recommended_next_session,
        "recommended_focus_this_week": recommended_focus,
        "evidence_used": evidence_used,
    }


def store_latest_practice_analysis(
    session_state: dict[str, Any],
    payload: dict[str, Any],
    *,
    handoff_result: dict[str, Any] | None = None,
    handoff_success: bool | None = None,
) -> dict[str, str]:
    """Cache the latest Log-page Practice Analysis summary and related state."""
    summary = build_log_page_analysis_summary(payload)
    session_state[LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY] = summary
    session_state[LATEST_PRACTICE_ANALYSIS_CREATED_AT_KEY] = _utc_now_iso()
    session_state[LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY] = _evidence_counts_from_payload(payload)
    report = payload.get("progress_report") if isinstance(payload.get("progress_report"), dict) else {}
    session_state[LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY] = report
    if handoff_result is not None:
        success = (
            handoff_success
            if handoff_success is not None
            else bool(handoff_result.get("handoff_success"))
        )
        session_state[LATEST_PRACTICE_ANALYSIS_HANDOFF_STATUS_KEY] = {
            "duplicate": bool(handoff_result.get("duplicate")),
            "success": success,
            "question_id": handoff_result.get("question_id"),
            "analysis_run_id": handoff_result.get("analysis_run_id"),
            "insight_id": handoff_result.get("insight_id"),
            "action_url": handoff_result.get("action_url"),
            "continue_title": handoff_result.get("continue_title"),
            "resume_key": handoff_result.get("resume_key"),
            "sent_at": _utc_now_iso() if success else "",
            "error": str(handoff_result.get("handoff_error") or ""),
        }
    return summary


def hydrate_latest_practice_analysis_from_storage(session_state: dict[str, Any], *, st: Any = None) -> bool:
    """Restore Practice Analysis keys from disk when session state is empty after refresh."""
    import copy

    has_any = any(session_state.get(key) for key in PRACTICE_ANALYSIS_PERSIST_KEYS)
    if not has_any:
        try:
            from music_persistent_state import APP_ID
            from suite_user_persistence import load_user_state

            payload, _err = load_user_state(APP_ID)
            session_extra = payload.get("session") if isinstance(payload.get("session"), dict) else {}
            for key in PRACTICE_ANALYSIS_PERSIST_KEYS:
                if key in session_extra:
                    session_state[key] = copy.deepcopy(session_extra[key])
        except Exception:
            pass
    return hydrate_latest_practice_analysis(session_state)


def hydrate_latest_practice_analysis(session_state: dict[str, Any]) -> bool:
    """Ensure latest Practice Analysis keys are present after disk/cloud restore."""
    summary = session_state.get(LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY)
    if isinstance(summary, dict) and any(str(v or "").strip() for v in summary.values()):
        return True

    full_report = session_state.get(LATEST_PRACTICE_ANALYSIS_FULL_REPORT_KEY)
    if not isinstance(full_report, dict) or not full_report:
        return False

    evidence_counts = session_state.get(LATEST_PRACTICE_ANALYSIS_EVIDENCE_COUNTS_KEY)
    counts = evidence_counts if isinstance(evidence_counts, dict) else {}
    synthetic_payload: dict[str, Any] = {
        "progress_report": full_report,
        "practice_log_summary": {
            "entry_count_total": int(counts.get("practice_logs") or 0),
            "window_days": 14,
        },
        "upload_analysis_summary": {"analysis_count_total": int(counts.get("upload_analyses") or 0)},
        "tone_history_summary": {"tone_take_count_total": int(counts.get("tone_takes") or 0)},
        "multitrack_export_summary": {"export_count_total": int(counts.get("multitrack_exports") or 0)},
    }
    session_state[LATEST_PRACTICE_ANALYSIS_SUMMARY_KEY] = build_log_page_analysis_summary(synthetic_payload)
    return True


def build_practice_history_ami_payload(
    session_state: dict[str, Any],
    entries: list[dict[str, Any]] | None = None,
    *,
    window_days: int = 14,
    st: Any | None = None,
) -> dict[str, Any]:
    """Full practice-history synthesis payload for Analyze My Practice."""
    from practice_log_state import load_entries, normalize_practice_log_entries

    if entries is None:
        entries = load_entries(session_state)
    else:
        entries = normalize_practice_log_entries(entries)

    media_window = max(window_days, 30)
    catalog: dict[str, Any] = {}
    try:
        from media_persistence import build_media_ami_payload

        media_payload = build_media_ami_payload(st, window_days=media_window)
        catalog_uploads = media_payload.get("uploaded_recordings") or []
    except Exception:
        catalog_uploads = []
        media_payload = {}

    try:
        from media_persistence import load_media_catalog
        from media_state import (
            normalize_multitrack_exports,
            normalize_tone_takes,
            normalize_uploaded_recordings,
            _within_window,
        )

        catalog = load_media_catalog(st=st)
        raw_uploads = normalize_uploaded_recordings(
            catalog.get("uploaded_recordings") if isinstance(catalog.get("uploaded_recordings"), list) else []
        )
        raw_exports = normalize_multitrack_exports(
            catalog.get("multitrack_exports") if isinstance(catalog.get("multitrack_exports"), list) else []
        )
        raw_tones = normalize_tone_takes(
            catalog.get("tone_takes") if isinstance(catalog.get("tone_takes"), list) else []
        )
        uploads = [u for u in raw_uploads if _within_window(u, window_days=media_window)]
        exports = [e for e in raw_exports if _within_window(e, window_days=media_window)]
        tones = [t for t in raw_tones if _within_window(t, window_days=media_window)]
    except Exception:
        uploads = catalog_uploads
        exports = []
        tones = []

    upload_summary = build_upload_analysis_ami_summary(uploads, window_days=media_window)
    compact_uploads = upload_summary.get("recent_analyses") or []
    export_summary = build_multitrack_export_context_summary(
        exports,
        compact_uploads,
        window_days=media_window,
    )

    tone_summary: dict[str, Any] = dict(media_payload.get("tone_history") or {})
    if not tone_summary and tones:
        try:
            from media_state import build_tone_ami_summary

            tone_summary = build_tone_ami_summary(tones, window_days=media_window)
        except Exception:
            tone_summary = {}

    practice_log_summary = build_practice_log_ami_summary(entries, window_days=window_days)

    payload: dict[str, Any] = {
        "practice_log_summary": practice_log_summary,
        "upload_analysis_summary": upload_summary,
        "tone_history_summary": tone_summary,
        "multitrack_export_summary": export_summary,
        "user_request": "analyze_practice",
        "generated_at": _utc_now_iso(),
    }
    payload["safety_checks"] = ami_payload_safety_checks(payload)
    payload["diagnostics"] = ami_payload_diagnostics(payload)
    payload["progress_report"] = build_practice_progress_report(payload)
    payload["log_page_summary"] = build_log_page_analysis_summary(payload)
    return payload
