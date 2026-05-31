"""Persistent user lyrics, cues, and performance data (never overwrites core catalog)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_catalog.user_overrides import USER_VERIFIED, override_storage_key

USER_CONTENT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "user_song_content.json"
)

CONTENT_MY_VERSION = "my_version"
CONTENT_USER_VERIFIED = "user_verified"
CONTENT_SESSION = "session"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_content_document() -> dict[str, Any]:
    if not USER_CONTENT_PATH.is_file():
        return {"version": 1, "songs": {}}
    try:
        raw = json.loads(USER_CONTENT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "songs": {}}
    if not isinstance(raw, dict):
        return {"version": 1, "songs": {}}
    raw.setdefault("version", 1)
    raw.setdefault("songs", {})
    return raw


def save_content_document(doc: dict[str, Any]) -> None:
    USER_CONTENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=False)
    tmp = USER_CONTENT_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    tmp.replace(USER_CONTENT_PATH)


def get_user_song_content(title: str, artist: str) -> dict[str, Any] | None:
    doc = load_content_document()
    entry = (doc.get("songs") or {}).get(override_storage_key(title, artist))
    return copy.deepcopy(entry) if entry else None


def delete_user_song_content(title: str, artist: str) -> bool:
    doc = load_content_document()
    key = override_storage_key(title, artist)
    songs = doc.get("songs") or {}
    if key not in songs:
        return False
    del songs[key]
    doc["songs"] = songs
    save_content_document(doc)
    return True


def _clean_section_lyrics(raw: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, text in (raw or {}).items():
        section = str(name or "").strip()
        if not section:
            continue
        val = str(text or "").strip()
        if val:
            out[section] = val
    return out


def _clean_lyric_cues(raw: dict[str, Any] | None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, cues in (raw or {}).items():
        section = str(name or "").strip()
        if not section:
            continue
        if isinstance(cues, str):
            lines = [ln.strip() for ln in cues.splitlines() if ln.strip()]
        elif isinstance(cues, list):
            lines = [str(c).strip() for c in cues if str(c).strip()]
        else:
            lines = []
        if lines:
            out[section] = lines
    return out


def save_user_song_content(
    *,
    title: str,
    artist: str,
    genre: str,
    section_lyrics: dict[str, str] | None = None,
    lyric_cues: dict[str, list[str]] | None = None,
    section_layout: list[str] | None = None,
    performance_notes: str = "",
    karaoke_markers: dict[str, Any] | None = None,
    content_status: str = CONTENT_MY_VERSION,
) -> dict[str, Any]:
    entry = {
        "title": title,
        "artist": artist,
        "genre": genre,
        "section_lyrics": _clean_section_lyrics(section_lyrics),
        "lyric_cues": _clean_lyric_cues(lyric_cues),
        "section_layout": [str(s).strip() for s in (section_layout or []) if str(s).strip()],
        "performance_notes": str(performance_notes or "").strip(),
        "karaoke_markers": copy.deepcopy(karaoke_markers or {}),
        "content_status": content_status,
        "saved_at": _utc_now_iso(),
    }
    doc = load_content_document()
    doc.setdefault("songs", {})
    doc["songs"][override_storage_key(title, artist)] = entry
    save_content_document(doc)
    return entry


def apply_user_song_content_to_record(record: dict[str, Any]) -> dict[str, Any]:
    """Attach user content metadata; does not mutate catalog lyric fields."""
    entry = get_user_song_content(record.get("title", ""), record.get("artist", ""))
    if not entry:
        return record
    out = copy.deepcopy(record)
    out["user_song_content"] = {
        "status": entry.get("content_status", CONTENT_MY_VERSION),
        "saved_at": entry.get("saved_at"),
        "has_lyrics": bool(entry.get("section_lyrics")),
        "has_cues": bool(entry.get("lyric_cues")),
        "has_performance_notes": bool(entry.get("performance_notes")),
        "has_karaoke_markers": bool(entry.get("karaoke_markers")),
    }
    return out


def apply_user_song_content_to_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [apply_user_song_content_to_record(r) for r in records]


def mark_content_user_verified(title: str, artist: str) -> bool:
    entry = get_user_song_content(title, artist)
    if not entry:
        return False
    entry["content_status"] = CONTENT_USER_VERIFIED
    entry["saved_at"] = _utc_now_iso()
    doc = load_content_document()
    doc.setdefault("songs", {})
    doc["songs"][override_storage_key(title, artist)] = entry
    save_content_document(doc)
    return True


def content_is_user_verified(status: str | None) -> bool:
    return status in {CONTENT_USER_VERIFIED, USER_VERIFIED}
