"""Canonical Practice Log API — schema, CRUD, prefill, filter, and summary."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

PRACTICE_LOG_LOADED_WS_KEY = "_practice_log_loaded_workspace_id"
PRACTICE_LOG_DEFERRED_EMPTY_KEY = "_practice_log_deferred_empty_load"

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

DEFAULT_PRACTICE_LOG_TZ = "America/New_York"

_BPM_SOURCE_LABELS: dict[str, str] = {
    "backing_track": "backing track",
    "song_setting": "song setting",
    "metronome": "metronome",
    "default": "default",
}


def get_practice_log_timezone(session_state: dict[str, Any] | None = None) -> ZoneInfo:
    """User/app timezone for practice log dates (defaults to America/New_York)."""
    ss = session_state or {}
    tz_name = str(
        ss.get("user_timezone")
        or ss.get("practice_log_timezone")
        or DEFAULT_PRACTICE_LOG_TZ
    ).strip()
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_PRACTICE_LOG_TZ)


def practice_log_local_date(
    session_state: dict[str, Any] | None = None,
    *,
    now_utc: datetime | None = None,
) -> date:
    """Local calendar date for practice log entries (not server UTC)."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(get_practice_log_timezone(session_state)).date()


def resolve_practice_log_bpm(session_state: dict[str, Any]) -> tuple[int | None, str | None]:
    """Resolve BPM + source label for quick-save.

    Priority: backing-track BPM → active song BPM → metronome/current BPM → default.
    Returns (None, None) when no trustworthy BPM exists.
    """
    ss = session_state or {}
    studio_page = str(ss.get("studio_page") or "practice").strip().lower()
    last_mode = str(ss.get("last_practice_mode") or "").strip().lower()

    live_bpm = _coerce_int(ss.get("backing_track_bpm"))
    canon_bpm: int | None = None
    try:
        from backing_track_state import canonical_backing_filters

        backing = canonical_backing_filters(ss) or {}
        canon_bpm = _coerce_int(backing.get("backing_track_bpm"))
    except ImportError:
        pass

    backing_bpm = live_bpm if live_bpm is not None else canon_bpm
    if backing_bpm is not None and (
        studio_page == "backing"
        or last_mode in ("backing", "backing track")
        or str(ss.get("practice_type") or "").strip().lower() == "backing track"
    ):
        return backing_bpm, "backing track"

    song_bpm = _coerce_int(ss.get("active_song_bpm"))
    selected: dict[str, Any] = {}
    try:
        from active_song_state import gather_active_song_context

        song_ctx = gather_active_song_context(ss)
        raw = song_ctx.get("selected_song")
        selected = raw if isinstance(raw, dict) else {}
    except ImportError:
        raw = ss.get("selected_song")
        selected = raw if isinstance(raw, dict) else {}

    if song_bpm is None and selected:
        try:
            from songs.playback_defaults import canonical_active_song_bpm

            song_bpm = canonical_active_song_bpm(selected)
        except ImportError:
            pass

    if song_bpm is not None and backing_bpm is not None and backing_bpm == song_bpm:
        return song_bpm, "song setting"
    if song_bpm is not None and backing_bpm is None:
        return song_bpm, "song setting"

    if backing_bpm is not None:
        if studio_page == "practice" or last_mode in ("practice", "song practice", "song work"):
            return backing_bpm, "metronome"
        return backing_bpm, "metronome"

    if song_bpm is not None:
        return song_bpm, "song setting"

    return None, None


def format_bpm_display(entry: dict[str, Any]) -> str:
    """Human-readable BPM line for session cards."""
    bpm = _coerce_int(entry.get("bpm"))
    if bpm is None:
        return "—"
    source_key = str(entry.get("bpm_source") or "").strip().lower()
    source = _BPM_SOURCE_LABELS.get(source_key) or source_key
    if source:
        return f"{bpm} · {source}"
    return str(bpm)


def section_display_label(entry: dict[str, Any]) -> str:
    """Map internal section codes to user-facing labels."""
    raw_name = str(entry.get("section_name") or "").strip()
    if raw_name:
        try:
            from practice_state import normalize_practice_focus_section

            norm = normalize_practice_focus_section(raw_name)
        except ImportError:
            norm = raw_name
        low = norm.lower()
        if low in ("full song", "whole song", "full form"):
            return "Full song"
        if low not in ("custom", "unspecified", ""):
            return norm

    section = str(entry.get("section_practiced") or "").strip().lower()
    ptype = str(entry.get("practice_type") or entry.get("source_mode") or "").strip().lower()
    page = str(entry.get("source_page") or "").strip().lower()

    if section in ("whole song", "unspecified", ""):
        return "Full song"
    if section == "custom":
        if ptype == "custom progression" or page in ("creative", "custom"):
            return "Custom progression"
        return "Custom section"
    return section.replace("_", " ").title()


def format_quick_save_success_message(entry: dict[str, Any]) -> str:
    """Success toast after quick-save."""
    song = str(entry.get("active_song") or entry.get("song") or "Session").strip()
    instrument = str(entry.get("instrument") or "").strip()
    mins = _coerce_int(entry.get("duration_minutes"), 0) or 0
    parts = [f"Practice session saved: {song}"]
    if instrument:
        parts.append(instrument)
    parts.append(f"{mins} min")
    bpm = _coerce_int(entry.get("bpm"))
    if bpm is not None:
        source_key = str(entry.get("bpm_source") or "").strip().lower()
        source = _BPM_SOURCE_LABELS.get(source_key) or source_key
        if source:
            parts.append(f"BPM {bpm} from {source}")
        else:
            parts.append(f"BPM {bpm}")
    return " · ".join(parts)


PRACTICE_CONCERT_KEY_LABEL = "Practice/Concert key"
WRITTEN_KEY_LABEL = "Written key"
SHAPE_KEY_LABEL = "Shape key"
ORIGINAL_KEY_LABEL = "Original key"


def is_guitar_instrument(instrument: str) -> bool:
    return str(instrument or "").strip().lower() == "guitar"


def is_transposing_log_instrument(instrument: str) -> bool:
    if is_guitar_instrument(instrument):
        return False
    try:
        from instrument_transposition import is_transposing_instrument

        return bool(is_transposing_instrument(instrument))
    except ImportError:
        inst = str(instrument or "").strip().lower()
        return inst in ("saxophone", "trumpet", "clarinet")


def practice_log_form_key_spec(instrument: str) -> dict[str, bool]:
    """Which key fields to show on manual/edit forms for this instrument."""
    guitar = is_guitar_instrument(instrument)
    transposing = is_transposing_log_instrument(instrument)
    return {
        "practice_concert_key": True,
        "written_key": transposing,
        "shape_key": guitar,
        "original_key": True,
    }


def practice_key_field_label(instrument: str) -> str:
    """Primary key field label — always Practice/Concert key."""
    return PRACTICE_CONCERT_KEY_LABEL


def _written_key_value_for_log(ctx: Any) -> str:
    """Written chart key shown in the left panel for transposing instruments."""
    if ctx.chart_key_mode == "written" and str(ctx.chart_key or "").strip():
        return str(ctx.chart_key).strip()
    return str(ctx.written_key or "").strip()


def gather_practice_log_keys(session_state: dict[str, Any]) -> dict[str, str]:
    """Resolve keys from canonical active setup (same source as left panel)."""
    ss = session_state or {}
    instrument = ""
    try:
        from practice_setup_globals import get_active_instrument

        instrument = str(get_active_instrument(ss) or "").strip()
    except ImportError:
        instrument = str(ss.get("instrument") or "").strip()

    selected: dict[str, Any] = {}
    try:
        from active_song_state import gather_active_song_context

        song_ctx = gather_active_song_context(ss)
        raw = song_ctx.get("selected_song")
        selected = raw if isinstance(raw, dict) else {}
    except ImportError:
        raw = ss.get("selected_song")
        selected = raw if isinstance(raw, dict) else {}

    fallback_original = str(selected.get("key") or ss.get("custom_home_key") or "").strip()
    fallback_concert = str(ss.get("display_key") or ss.get("concert_practice_key") or "").strip()

    try:
        from songs.key_state import resolve_active_musical_key

        ctx = resolve_active_musical_key(ss, rec=selected or None, instrument=instrument or None)
    except ImportError:
        return {
            "original_key": fallback_original,
            "display_key": fallback_concert,
            "practice_concert_key": fallback_concert,
            "written_key": "",
            "guitar_shape_key": "",
        }

    written = _written_key_value_for_log(ctx) if is_transposing_log_instrument(instrument) else ""
    shape = str(ctx.shape_key or "").strip() if is_guitar_instrument(instrument) else ""

    return {
        "original_key": str(ctx.original_key or fallback_original or "").strip(),
        "display_key": str(ctx.practice_concert_key or fallback_concert or "").strip(),
        "practice_concert_key": str(ctx.practice_concert_key or fallback_concert or "").strip(),
        "written_key": written,
        "guitar_shape_key": shape,
    }


def entry_key_display_parts(entry: dict[str, Any]) -> list[tuple[str, str]]:
    """User-facing key label/value pairs for session cards."""
    instrument = str(entry.get("instrument") or "")
    concert = str(entry.get("practice_concert_key") or entry.get("display_key") or "—").strip() or "—"
    original = str(entry.get("original_key") or "—").strip() or "—"
    parts: list[tuple[str, str]] = [(PRACTICE_CONCERT_KEY_LABEL, concert)]

    if is_guitar_instrument(instrument):
        shape = str(entry.get("guitar_shape_key") or "").strip()
        parts.append((SHAPE_KEY_LABEL, shape or "—"))
    elif is_transposing_log_instrument(instrument):
        written = str(entry.get("written_key") or "").strip()
        parts.append((WRITTEN_KEY_LABEL, written or "—"))
    else:
        written = str(entry.get("written_key") or "").strip()
        if written and written.lower() != concert.lower() and concert != "—":
            parts.append((WRITTEN_KEY_LABEL, written))

    parts.append((ORIGINAL_KEY_LABEL, original))
    return parts


def format_entry_keys_display(entry: dict[str, Any]) -> str:
    """Plain-text key summary (label: value pairs)."""
    return " · ".join(f"{label}: {value}" for label, value in entry_key_display_parts(entry))


def _normalize_search_token(text: str) -> str:
    """Lowercase alphanumeric-only token for partial matching."""
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def _entry_search_blob(entry: dict[str, Any]) -> str:
    """Concatenate all searchable entry text (normalized)."""
    tags = entry.get("tags")
    tag_text = " ".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")
    ratings = entry.get("ratings")
    rating_text = ""
    if isinstance(ratings, dict):
        rating_text = " ".join(f"{k} {v}" for k, v in ratings.items())
    legacy_rating = entry.get("rating")
    bpm_source = _BPM_SOURCE_LABELS.get(str(entry.get("bpm_source") or "").strip().lower(), "")
    parts = [
        entry.get("active_song"),
        entry.get("song"),
        entry.get("artist"),
        entry.get("instrument"),
        entry.get("instrument_family"),
        entry.get("focus_area"),
        entry.get("focus"),
        entry.get("practice_type"),
        entry.get("mode"),
        entry.get("source_mode"),
        entry.get("section_practiced"),
        entry.get("section_name"),
        section_display_label(entry),
        entry.get("notes"),
        entry.get("practice"),
        entry.get("what_went_well"),
        entry.get("what_was_hard"),
        entry.get("next_step"),
        tag_text,
        entry.get("original_key"),
        entry.get("display_key"),
        entry.get("practice_concert_key"),
        entry.get("written_key"),
        entry.get("guitar_shape_key"),
        PRACTICE_CONCERT_KEY_LABEL,
        WRITTEN_KEY_LABEL,
        SHAPE_KEY_LABEL,
        entry.get("bpm"),
        entry.get("bpm_source"),
        bpm_source,
        format_bpm_display(entry),
        entry.get("source_page"),
        entry.get("genre"),
        entry.get("groove"),
        entry.get("level"),
        rating_text,
        legacy_rating,
        entry.get("minutes"),
        entry.get("duration_minutes"),
    ]
    return _normalize_search_token(" ".join(str(p) for p in parts if p not in (None, "")))


def _search_matches(entry: dict[str, Any], search: str) -> bool:
    token = _normalize_search_token(search)
    if not token:
        return True
    return token in _entry_search_blob(entry)


def _instrument_filter_matches(entry: dict[str, Any], filter_instrument: str) -> bool:
    choice = str(filter_instrument or "").strip()
    if not choice or choice.lower() in ("all", "all instruments"):
        return True
    entry_inst = str(entry.get("instrument") or "").strip()
    return entry_inst.lower() == choice.lower()


def _focus_filter_matches(entry: dict[str, Any], filter_focus: str) -> bool:
    choice = str(filter_focus or "").strip().lower()
    if not choice or choice in ("all", "all focus areas"):
        return True
    entry_focus = _normalize_focus_area(entry.get("focus_area"), legacy_focus=entry.get("focus")).lower()
    legacy = str(entry.get("focus") or "").strip().lower()
    return entry_focus == choice or legacy == choice or choice in entry_focus or choice in legacy


def _practice_type_filter_matches(entry: dict[str, Any], filter_type: str) -> bool:
    choice = str(filter_type or "").strip()
    if not choice or choice.lower() in ("all", "all types", "all modes"):
        return True
    return _normalize_practice_type(entry.get("practice_type")) == _normalize_practice_type(choice)


def _normalize_section_prefill(
    session_state: dict[str, Any],
    *,
    practice: dict[str, Any],
) -> tuple[str, str]:
    """Return (section_practiced canonical, section_name display raw)."""
    ss = session_state or {}
    section = str(practice.get("practice_focus_section") or ss.get("practice_focus_section") or "").strip()
    if not section:
        return "unspecified", ""
    try:
        from practice_state import normalize_practice_focus_section

        section = normalize_practice_focus_section(section)
    except ImportError:
        pass
    low = section.lower()
    if low in ("full song", "whole song", "full form"):
        return "whole song", section
    if low in SECTIONS_PRACTICED:
        return low, section
    return "custom", section


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
        out["date"] = parsed.isoformat() if parsed else practice_log_local_date().isoformat()

    mins = _coerce_int(out.get("duration_minutes"), _coerce_int(out.get("minutes"), 30))
    out["duration_minutes"] = mins if mins is not None else 30

    out["active_song"] = str(out.get("active_song") or out.get("song") or "").strip()
    out["song_id"] = str(out.get("song_id") or out.get("pick_key") or "").strip()
    out["instrument"] = str(out.get("instrument") or "").strip()
    out["instrument_family"] = str(out.get("instrument_family") or "").strip()
    out["original_key"] = str(out.get("original_key") or "").strip()
    concert = str(out.get("practice_concert_key") or out.get("display_key") or "").strip()
    out["practice_concert_key"] = concert
    out["display_key"] = concert
    out["written_key"] = str(out.get("written_key") or "").strip()
    if is_guitar_instrument(out.get("instrument") or ""):
        out["guitar_shape_key"] = str(out.get("guitar_shape_key") or "").strip()
    else:
        out["guitar_shape_key"] = ""
    capo = _coerce_int(out.get("capo_fret"), 0)
    out["capo_fret"] = capo if capo is not None else 0
    bpm = _coerce_int(out.get("bpm"))
    if bpm is not None:
        out["bpm"] = bpm
    bpm_source = str(out.get("bpm_source") or "").strip().lower()
    if bpm_source:
        out["bpm_source"] = bpm_source

    section_name = str(out.get("section_name") or "").strip()
    if section_name:
        out["section_name"] = section_name

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


def _current_workspace_id(session_state: dict[str, Any] | None) -> str:
    try:
        return _resolve_workspace_from_session(session_state)
    except Exception:
        pass
    ss = session_state or {}
    raw = str(ss.get("_suite_active_workspace_id") or "").strip()
    return raw or "daniel"


def _resolve_workspace_from_session(session_state: dict[str, Any] | None) -> str:
    from practice_log_persistence import _resolve_workspace_id

    return _resolve_workspace_id(st=_st_wrapper(session_state))


def _workspace_persistence_ready(session_state: dict[str, Any] | None) -> bool:
    if not session_state:
        return True
    if session_state.get("_suite_workspace_initialized"):
        return True
    if session_state.get("_music_restore_phase_complete"):
        return True
    if session_state.get("_music_workspace_prepared_for_run"):
        return True
    return bool(str(session_state.get("_suite_active_workspace_id") or "").strip())


def invalidate_practice_log_cache(session_state: dict[str, Any]) -> None:
    session_state.pop(PRACTICE_LOG_LOADED_WS_KEY, None)
    session_state.pop(PRACTICE_LOG_DEFERRED_EMPTY_KEY, None)
    session_state.pop("practice_log_entries", None)


def reload_practice_log_entries(
    session_state: dict[str, Any],
    *,
    force: bool = True,
) -> list[dict[str, Any]]:
    """Dev/diagnostic: drop cached session list and reload from disk + cloud."""
    invalidate_practice_log_cache(session_state)
    return load_entries(session_state, force=force)


def load_entries(
    session_state: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    from practice_log_persistence import load_practice_logs

    ws = _current_workspace_id(session_state)
    prev_ws = str((session_state or {}).get(PRACTICE_LOG_LOADED_WS_KEY) or "").strip()
    workspace_ready = _workspace_persistence_ready(session_state)
    deferred = bool((session_state or {}).get(PRACTICE_LOG_DEFERRED_EMPTY_KEY))

    if session_state is not None and prev_ws and prev_ws != ws:
        session_state["_practice_log_workspace_changed"] = {"from": prev_ws, "to": ws}
        force = True

    if force or deferred and workspace_ready:
        invalidate_practice_log_cache(session_state)

    raw = load_practice_logs(st=_st_wrapper(session_state))
    entries = normalize_practice_log_entries(raw)
    if session_state is not None:
        if not entries and not workspace_ready and not prev_ws:
            session_state[PRACTICE_LOG_DEFERRED_EMPTY_KEY] = True
        elif entries or workspace_ready:
            session_state.pop(PRACTICE_LOG_DEFERRED_EMPTY_KEY, None)
        session_state[PRACTICE_LOG_LOADED_WS_KEY] = ws
        session_state["practice_log_entries"] = entries
        session_state["_practice_log_last_load_at"] = _utc_now_iso()
        session_state["_practice_log_last_load_count"] = len(entries)
    return entries


def _persist_raw(session_state: dict[str, Any] | None, raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from practice_log_persistence import load_practice_logs, save_practice_logs

    migrated = [migrate_practice_log_entry(e) for e in (raw_rows or []) if isinstance(e, dict)]
    ok, err = save_practice_logs(migrated, st=_st_wrapper(session_state))
    raw_reloaded = load_practice_logs(st=_st_wrapper(session_state))
    visible = normalize_practice_log_entries(raw_reloaded)
    if session_state is not None:
        session_state["_practice_log_last_save_ok"] = bool(ok)
        session_state[PRACTICE_LOG_LOADED_WS_KEY] = _current_workspace_id(session_state)
        if err:
            session_state["_practice_log_last_save_error"] = err
        else:
            session_state.pop("_practice_log_last_save_error", None)
        session_state.pop(PRACTICE_LOG_DEFERRED_EMPTY_KEY, None)
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
        "date": practice_log_local_date(ss).isoformat(),
        "duration_minutes": 30,
        "section_practiced": "unspecified",
        "section_name": "",
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
    key_fields = gather_practice_log_keys(ss)
    prefill["original_key"] = key_fields.get("original_key") or str(
        selected.get("key") or song_ctx.get("custom_home_key") or ""
    ).strip()
    prefill["display_key"] = key_fields.get("display_key") or ""
    prefill["practice_concert_key"] = key_fields.get("practice_concert_key") or prefill["display_key"]
    prefill["written_key"] = key_fields.get("written_key") or ""
    prefill["guitar_shape_key"] = key_fields.get("guitar_shape_key") or ""

    try:
        from practice_setup_globals import (
            get_active_focus,
            get_active_instrument,
            get_active_instrument_display_name,
            get_active_level,
        )

        instrument_family = str(get_active_instrument(ss) or "").strip()
        prefill["instrument"] = str(get_active_instrument_display_name(ss) or instrument_family).strip()
        prefill["instrument_family"] = instrument_family
        prefill["level"] = str(get_active_level(ss) or "").strip()
        legacy_focus = str(get_active_focus(ss) or "").strip()
    except ImportError:
        prefill["instrument"] = str(ss.get("instrument") or "").strip()
        prefill["instrument_family"] = prefill["instrument"]
        prefill["level"] = str(ss.get("level") or "").strip()
        legacy_focus = str(ss.get("focus") or "").strip()

    prefill["focus_area"] = _normalize_focus_area(None, legacy_focus=legacy_focus)
    prefill["focus"] = legacy_focus

    try:
        from practice_state import gather_practice_filters

        practice = gather_practice_filters(ss)
    except ImportError:
        practice = {}

    section_practiced, section_name = _normalize_section_prefill(ss, practice=practice)
    prefill["section_practiced"] = section_practiced
    prefill["section_name"] = section_name
    prefill["last_practice_mode"] = str(practice.get("last_practice_mode") or ss.get("last_practice_mode") or "").strip()

    mins = _coerce_int(practice.get("practice_minutes"), _coerce_int(ss.get("practice_minutes")))
    if mins is not None and mins > 0:
        prefill["duration_minutes"] = mins

    bpm, bpm_source = resolve_practice_log_bpm(ss)
    if bpm is not None:
        prefill["bpm"] = bpm
        if bpm_source:
            source_map = {
                "backing track": "backing_track",
                "song setting": "song_setting",
                "metronome": "metronome",
                "default": "default",
            }
            prefill["bpm_source"] = source_map.get(bpm_source, bpm_source.replace(" ", "_"))

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
        merged["date"] = practice_log_local_date(session_state).isoformat()
    return migrate_practice_log_entry(merged)


def add_practice_log_entry(session_state: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    entry = _new_entry_fields(session_state, fields)
    visible = load_entries(session_state)
    visible = [entry] + [e for e in visible if e.get("session_id") != entry.get("session_id")]
    saved = save_entries(session_state, visible)
    sid = str(entry.get("session_id") or "")
    if sid and not any(str(row.get("session_id") or "") == sid for row in saved):
        raise RuntimeError(
            str(session_state.get("_practice_log_last_save_error") or "practice_log_save_failed")
        )
    if session_state.get("_practice_log_last_save_ok") is False:
        raise RuntimeError(
            str(session_state.get("_practice_log_last_save_error") or "practice_log_save_failed")
        )
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


def filter_practice_log_entries(
    entries: list[dict[str, Any]],
    filters: dict[str, Any],
    *,
    session_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
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
                start_date = practice_log_local_date(session_state) - timedelta(days=days - 1)
        except (TypeError, ValueError):
            pass

    out: list[dict[str, Any]] = []
    for entry in rows:
        log_date = _parse_log_date(entry)
        if start_date and (log_date is None or log_date < start_date):
            continue
        if not _instrument_filter_matches(entry, instrument):
            continue
        if not _focus_filter_matches(entry, focus_area):
            continue
        if not _practice_type_filter_matches(entry, practice_type):
            continue
        if not _search_matches(entry, search):
            continue
        out.append(entry)
    return out


def compute_practice_log_summary(
    entries: list[dict[str, Any]],
    *,
    window_days: int = 14,
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from collections import Counter

    rows = filter_practice_log_entries(entries, {"window_days": window_days}, session_state=session_state)
    today = practice_log_local_date(session_state)
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
