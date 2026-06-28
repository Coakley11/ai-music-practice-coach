"""Canonical Practice Log API — schema, CRUD, prefill, filter, and summary."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

FOCUS_AREAS: tuple[str, ...] = (
    "tone",
    "timing/rhythm",
    "melody",
    "chords",
    "soloing/improv",
    "transcription",
    "ear training",
    "lyrics/cues",
    "backing track",
    "performance",
    "technical exercise",
    "general",
)

PRACTICE_TYPES: tuple[str, ...] = (
    "song practice",
    "backing track",
    "custom progression",
    "metronome",
    "karaoke/performance",
    "multitrack/upload",
    "technique",
    "improvisation",
    "ear training",
    "performance prep",
    "warmup",
    "other",
)

SECTIONS_PRACTICED: tuple[str, ...] = (
    "intro",
    "verse",
    "chorus",
    "bridge",
    "solo",
    "whole song",
    "custom",
    "unspecified",
)

_LEGACY_MODE_TO_PRACTICE_TYPE: dict[str, str] = {
    "song work": "song practice",
    "technique": "technique",
    "improvisation": "improvisation",
    "ear training": "ear training",
    "performance prep": "performance prep",
    "warmup": "warmup",
    "other": "other",
}

_STUDIO_PAGE_TO_PRACTICE_TYPE: dict[str, str] = {
    "practice": "song practice",
    "backing": "backing track",
    "custom": "custom progression",
    "karaoke": "karaoke/performance",
    "multitrack": "multitrack/upload",
    "analysis": "multitrack/upload",
    "log": "song practice",
    "picker": "song practice",
    "creative": "custom progression",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso_ts(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_log_date(entry: dict[str, Any]) -> date | None:
    raw = str(entry.get("date") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _legacy_fingerprint(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("date") or ""),
        str(entry.get("song") or entry.get("active_song") or ""),
        str(entry.get("minutes") or entry.get("duration_minutes") or ""),
        str(entry.get("practice") or entry.get("notes") or ""),
        str(entry.get("rating") or ""),
        str(entry.get("mode") or entry.get("practice_type") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def deterministic_session_id(entry: dict[str, Any]) -> str:
    return f"legacy-{_legacy_fingerprint(entry)}"


def is_tombstone(entry: dict[str, Any]) -> bool:
    return bool(entry.get("deleted")) and bool(str(entry.get("session_id") or "").strip())


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_practice_type(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return "song practice"
    low = text.lower()
    if low in PRACTICE_TYPES:
        return low
    mapped = _LEGACY_MODE_TO_PRACTICE_TYPE.get(low)
    if mapped:
        return mapped
    return text


def _normalize_focus_area(raw: Any, *, legacy_focus: Any = None) -> str:
    text = str(raw or legacy_focus or "").strip()
    if not text:
        return "general"
    low = text.lower()
    for area in FOCUS_AREAS:
        if low == area.lower():
            return area
    legacy_map = {
        "chord transitions": "chords",
        "scales": "technical exercise",
        "rhythm": "timing/rhythm",
        "improv": "soloing/improv",
    }
    for key, val in legacy_map.items():
        if key in low:
            return val
    return text if text else "general"


def _sync_legacy_aliases(entry: dict[str, Any]) -> dict[str, Any]:
    """Keep legacy read fields in sync with canonical names."""
    out = dict(entry)
    mins = _coerce_int(out.get("duration_minutes"), _coerce_int(out.get("minutes"), 0))
    if mins is not None:
        out["duration_minutes"] = mins
        out["minutes"] = mins
    notes = str(out.get("notes") or out.get("practice") or "").strip()
    if notes:
        out["notes"] = notes
        out["practice"] = notes
    song = str(out.get("active_song") or out.get("song") or "").strip()
    if song:
        out["active_song"] = song
        out["song"] = song
    ptype = _normalize_practice_type(out.get("practice_type") or out.get("mode"))
    out["practice_type"] = ptype
    out["mode"] = ptype.title() if ptype == "song practice" else ptype.replace("/", " ").title()
    if not out.get("source_mode"):
        out["source_mode"] = ptype
    ratings = out.get("ratings")
    if not isinstance(ratings, dict):
        ratings = {}
    legacy_rating = _coerce_int(out.get("rating"))
    if legacy_rating is not None and "confidence" not in ratings:
        ratings["confidence"] = max(1, min(5, round(legacy_rating / 2)))
    if ratings:
        out["ratings"] = ratings
        if legacy_rating is None and ratings.get("confidence") is not None:
            out["rating"] = int(ratings["confidence"]) * 2
    return out


def migrate_practice_log_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single practice log row (legacy or canonical)."""
    if not isinstance(entry, dict):
        return {}
    if is_tombstone(entry):
        sid = str(entry.get("session_id") or "").strip()
        return {
            "session_id": sid,
            "deleted": True,
            "updated_at": str(entry.get("updated_at") or _utc_now_iso()),
        }

    out = dict(entry)
    sid = str(out.get("session_id") or "").strip()
    if not sid:
        sid = deterministic_session_id(out)
    out["session_id"] = sid

    now = _utc_now_iso()
    out.setdefault("created_at", now)
    out.setdefault("updated_at", out.get("created_at") or now)

    if not str(out.get("date") or "").strip():
        parsed = _parse_log_date(out)
        out["date"] = parsed.isoformat() if parsed else date.today().isoformat()

    mins = _coerce_int(out.get("duration_minutes"), _coerce_int(out.get("minutes"), 30))
    out["duration_minutes"] = mins if mins is not None else 30

    out["active_song"] = str(out.get("active_song") or out.get("song") or "").strip()
    out["song_id"] = str(out.get("song_id") or out.get("pick_key") or "").strip()
    out["instrument"] = str(out.get("instrument") or "").strip()
    out["original_key"] = str(out.get("original_key") or "").strip()
    out["display_key"] = str(out.get("display_key") or "").strip()
    out["guitar_shape_key"] = str(out.get("guitar_shape_key") or "").strip()
    capo = _coerce_int(out.get("capo_fret"), 0)
    out["capo_fret"] = capo if capo is not None else 0
    bpm = _coerce_int(out.get("bpm"))
    if bpm is not None:
        out["bpm"] = bpm

    section = str(out.get("section_practiced") or "").strip().lower()
    if not section:
        count = _coerce_int(out.get("section_count"), 0) or 0
        section = "whole song" if count == 0 else "custom"
    out["section_practiced"] = section if section in SECTIONS_PRACTICED else "custom"

    out["focus_area"] = _normalize_focus_area(out.get("focus_area"), legacy_focus=out.get("focus"))
    out["practice_type"] = _normalize_practice_type(out.get("practice_type") or out.get("mode"))
    out["source_mode"] = str(out.get("source_mode") or out["practice_type"]).strip()

    for key in ("notes", "what_went_well", "what_was_hard", "next_step"):
        out[key] = str(out.get(key) or (out.get("practice") if key == "notes" else "") or "").strip()

    tags = out.get("tags")
    out["tags"] = [str(t).strip() for t in tags if str(t).strip()] if isinstance(tags, list) else []

    out["source_page"] = str(out.get("source_page") or "").strip()

    return _sync_legacy_aliases(out)


def normalize_practice_log_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Migrate all entries, apply tombstones, return visible entries newest-first."""
    migrated = [migrate_practice_log_entry(e) for e in (entries or []) if isinstance(e, dict)]
    tombstones: dict[str, datetime] = {}
    visible: dict[str, dict[str, Any]] = {}

    for row in migrated:
        sid = str(row.get("session_id") or "").strip()
        if not sid:
            continue
        if is_tombstone(row):
            ts = _parse_iso_ts(row.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
            prev = tombstones.get(sid)
            if prev is None or ts > prev:
                tombstones[sid] = ts
            continue
        ts = _parse_iso_ts(row.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        tomb = tombstones.get(sid)
        if tomb is not None and tomb >= ts:
            continue
        prev = visible.get(sid)
        if prev is None:
            visible[sid] = row
            continue
        prev_ts = _parse_iso_ts(prev.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if ts >= prev_ts:
            visible[sid] = row

    out = list(visible.values())
    out.sort(
        key=lambda e: (
            _parse_log_date(e) or date.min,
            str(e.get("updated_at") or ""),
            str(e.get("session_id") or ""),
        ),
        reverse=True,
    )
    return out


def _st_wrapper(session_state: dict[str, Any] | None) -> Any | None:
    if session_state is None:
        return None

    class _Wrap:
        pass

    wrap = _Wrap()
    wrap.session_state = session_state
    return wrap


def load_entries(session_state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from practice_log_persistence import load_practice_logs

    raw = load_practice_logs(st=_st_wrapper(session_state))
    entries = normalize_practice_log_entries(raw)
    if session_state is not None:
        session_state["practice_log_entries"] = entries
    return entries


def _persist_raw(session_state: dict[str, Any] | None, raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from practice_log_persistence import save_practice_logs

    migrated = [migrate_practice_log_entry(e) for e in (raw_rows or []) if isinstance(e, dict)]
    save_practice_logs(migrated, st=_st_wrapper(session_state))
    visible = normalize_practice_log_entries(migrated)
    if session_state is not None:
        session_state["practice_log_entries"] = visible
    return visible


def save_entries(session_state: dict[str, Any] | None, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist visible entries; preserve existing tombstones from storage."""
    raw_existing = load_raw_with_tombstones(session_state)
    tombstones = [migrate_practice_log_entry(e) for e in raw_existing if is_tombstone(e)]
    visible = [migrate_practice_log_entry(e) for e in entries if isinstance(e, dict) and not is_tombstone(e)]
    return _persist_raw(session_state, tombstones + visible)


def build_practice_log_prefill(session_state: dict[str, Any]) -> dict[str, Any]:
    """Build default field values from active song / practice setup."""
    ss = session_state or {}
    prefill: dict[str, Any] = {
        "date": date.today().isoformat(),
        "duration_minutes": 30,
        "section_practiced": "unspecified",
        "focus_area": "general",
        "practice_type": "song practice",
        "source_page": str(ss.get("studio_page") or "practice").strip(),
        "source_mode": "song practice",
        "tags": [],
        "ratings": {},
    }

    try:
        from active_song_state import gather_active_song_context

        song_ctx = gather_active_song_context(ss)
    except ImportError:
        song_ctx = {}

    pick_key = str(
        song_ctx.get("pick_key")
        or ss.get("active_catalog_pick_key")
        or ""
    ).strip()
    selected = song_ctx.get("selected_song") if isinstance(song_ctx.get("selected_song"), dict) else {}
    if not selected:
        raw = ss.get("selected_song")
        selected = raw if isinstance(raw, dict) else {}

    title = str(selected.get("title") or ss.get("active_song_title") or "").strip()
    artist = str(selected.get("artist") or "").strip()
    prefill["active_song"] = title
    prefill["song_id"] = pick_key
    prefill["artist"] = artist
    prefill["original_key"] = str(selected.get("key") or song_ctx.get("custom_home_key") or "").strip()
    prefill["display_key"] = str(song_ctx.get("display_key") or ss.get("display_key") or "").strip()

    try:
        from practice_setup_globals import get_active_focus, get_active_instrument, get_active_level

        prefill["instrument"] = str(get_active_instrument(ss) or "").strip()
        prefill["level"] = str(get_active_level(ss) or "").strip()
        legacy_focus = str(get_active_focus(ss) or "").strip()
    except ImportError:
        prefill["instrument"] = str(ss.get("instrument") or "").strip()
        prefill["level"] = str(ss.get("level") or "").strip()
        legacy_focus = str(ss.get("focus") or "").strip()

    prefill["focus_area"] = _normalize_focus_area(None, legacy_focus=legacy_focus)
    prefill["focus"] = legacy_focus

    try:
        from practice_state import gather_practice_filters

        practice = gather_practice_filters(ss)
    except ImportError:
        practice = {}

    section = str(practice.get("practice_focus_section") or ss.get("practice_focus_section") or "").strip()
    if section:
        low = section.lower()
        prefill["section_practiced"] = low if low in SECTIONS_PRACTICED else "custom"
    prefill["last_practice_mode"] = str(practice.get("last_practice_mode") or ss.get("last_practice_mode") or "").strip()

    bpm = _coerce_int(ss.get("backing_track_bpm"), _coerce_int(ss.get("bpm")))
    if bpm is None:
        try:
            from backing_track_state import canonical_backing_filters

            backing = canonical_backing_filters(ss) or {}
            bpm = _coerce_int(backing.get("backing_track_bpm"))
        except ImportError:
            pass
    if bpm is not None:
        prefill["bpm"] = bpm

    prefill["guitar_shape_key"] = str(ss.get("guitar_capo_shape_key") or "").strip()
    prefill["capo_fret"] = _coerce_int(ss.get("guitar_capo_fret"), 0) or 0

    studio_page = str(ss.get("studio_page") or "practice").strip().lower()
    prefill["source_page"] = studio_page
    prefill["practice_type"] = _STUDIO_PAGE_TO_PRACTICE_TYPE.get(studio_page, "song practice")
    prefill["source_mode"] = prefill["practice_type"]

    genre = str(selected.get("genre") or ss.get("active_genre") or "").strip()
    if genre:
        prefill["genre"] = genre
    groove = str(practice.get("practice_groove_style") or ss.get("practice_groove_style") or genre or "").strip()
    if groove:
        prefill["groove"] = groove

    return prefill


def _new_entry_fields(session_state: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    prefill = build_practice_log_prefill(session_state)
    merged = {**prefill, **(fields or {})}
    now = _utc_now_iso()
    merged.setdefault("session_id", str(uuid.uuid4()))
    merged.setdefault("created_at", now)
    merged["updated_at"] = now
    if not str(merged.get("date") or "").strip():
        merged["date"] = date.today().isoformat()
    return migrate_practice_log_entry(merged)


def add_practice_log_entry(session_state: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    entry = _new_entry_fields(session_state, fields)
    visible = load_entries(session_state)
    visible = [entry] + [e for e in visible if e.get("session_id") != entry.get("session_id")]
    save_entries(session_state, visible)
    return entry


def load_raw_with_tombstones(session_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    from practice_log_persistence import load_practice_logs

    return load_practice_logs(st=_st_wrapper(session_state))


def update_practice_log_entry(
    session_state: dict[str, Any], session_id: str, updates: dict[str, Any]
) -> dict[str, Any]:
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("session_id required")
    raw = load_raw_with_tombstones(session_state)
    visible = normalize_practice_log_entries(raw)
    target = next((e for e in visible if e.get("session_id") == sid), None)
    if target is None:
        raise KeyError(sid)
    merged = {**target, **(updates or {}), "session_id": sid}
    merged["updated_at"] = _utc_now_iso()
    merged.setdefault("created_at", target.get("created_at") or merged["updated_at"])
    updated = migrate_practice_log_entry(merged)
    new_visible = [updated if e.get("session_id") == sid else e for e in visible]
    save_entries(session_state, new_visible)
    return updated


def delete_practice_log_entry(session_state: dict[str, Any], session_id: str) -> bool:
    sid = str(session_id or "").strip()
    if not sid:
        return False
    raw = load_raw_with_tombstones(session_state)
    visible = normalize_practice_log_entries(raw)
    if not any(e.get("session_id") == sid for e in visible):
        return False
    tombstone = {
        "session_id": sid,
        "deleted": True,
        "updated_at": _utc_now_iso(),
    }
    remaining = [e for e in visible if e.get("session_id") != sid]
    tombstones = [migrate_practice_log_entry(e) for e in raw if is_tombstone(e)]
    tombstones = [t for t in tombstones if t.get("session_id") != sid]
    tombstones.append(tombstone)
    _persist_raw(session_state, remaining + tombstones)
    return True


def filter_practice_log_entries(entries: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    rows = normalize_practice_log_entries(entries)
    search = str(filters.get("search") or "").strip().lower()
    instrument = str(filters.get("instrument") or "").strip()
    focus_area = str(filters.get("focus_area") or "").strip().lower()
    practice_type = str(filters.get("practice_type") or "").strip().lower()
    window_days = filters.get("window_days")
    start_date: date | None = None
    if window_days is not None:
        try:
            days = int(window_days)
            if days > 0:
                start_date = date.today() - timedelta(days=days - 1)
        except (TypeError, ValueError):
            pass

    out: list[dict[str, Any]] = []
    for entry in rows:
        log_date = _parse_log_date(entry)
        if start_date and (log_date is None or log_date < start_date):
            continue
        if instrument and instrument.lower() not in ("all", "all instruments"):
            if str(entry.get("instrument") or "").strip() != instrument:
                continue
        if focus_area and focus_area not in ("all", "all focus areas"):
            if str(entry.get("focus_area") or "").strip().lower() != focus_area:
                continue
        if practice_type and practice_type not in ("all", "all types", "all modes"):
            if _normalize_practice_type(entry.get("practice_type")) != _normalize_practice_type(practice_type):
                continue
        if search:
            blob = " ".join(
                str(entry.get(k) or "")
                for k in (
                    "active_song",
                    "song",
                    "artist",
                    "notes",
                    "practice",
                    "what_went_well",
                    "what_was_hard",
                    "next_step",
                    "genre",
                    "groove",
                    "practice_type",
                    "mode",
                    "tags",
                )
            ).lower()
            if search not in blob:
                continue
        out.append(entry)
    return out


def compute_practice_log_summary(entries: list[dict[str, Any]], *, window_days: int = 14) -> dict[str, Any]:
    from collections import Counter

    rows = filter_practice_log_entries(entries, {"window_days": window_days})
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    sessions_this_week = 0
    minutes_this_week = 0
    for entry in rows:
        d = _parse_log_date(entry)
        mins = _coerce_int(entry.get("duration_minutes"), 0) or 0
        if d and d >= week_start:
            sessions_this_week += 1
            minutes_this_week += mins

    songs = Counter(str(e.get("active_song") or e.get("song") or "").strip() for e in rows if e.get("active_song") or e.get("song"))
    focuses = Counter(str(e.get("focus_area") or e.get("focus") or "").strip() for e in rows if e.get("focus_area") or e.get("focus"))
    challenges = Counter(
        str(e.get("what_was_hard") or "").strip().lower()
        for e in rows
        if str(e.get("what_was_hard") or "").strip()
    )
    next_steps = [str(e.get("next_step") or "").strip() for e in rows if str(e.get("next_step") or "").strip()]

    top_song = songs.most_common(1)[0][0] if songs else ""
    top_focus = focuses.most_common(1)[0][0] if focuses else ""
    repeated_challenge = challenges.most_common(1)[0][0] if challenges else ""
    suggested_next_focus = next_steps[0] if next_steps else top_focus or "timing/rhythm"

    total_minutes = sum(_coerce_int(e.get("duration_minutes"), 0) or 0 for e in rows)

    return {
        "window_days": window_days,
        "session_count": len(rows),
        "sessions_this_week": sessions_this_week,
        "minutes_this_week": minutes_this_week,
        "total_minutes": total_minutes,
        "most_practiced_songs": [s for s, _ in songs.most_common(5)],
        "most_common_focus_areas": [f for f, _ in focuses.most_common(5)],
        "top_song": top_song,
        "top_focus": top_focus,
        "repeated_challenges": [c for c, _ in challenges.most_common(5)],
        "repeated_challenge": repeated_challenge,
        "suggested_next_focus": suggested_next_focus,
        "last_session_summary": rows[0] if rows else {},
    }
