"""Persistent user-edited chord charts (override catalog entries)."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "data" / "user_chart_overrides.json"

USER_CORRECTED = "user_corrected"
USER_VERIFIED = "user_verified"


def override_storage_key(title: str, artist: str) -> str:
    return f"{title.strip().lower()}|{artist.strip().lower()}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def overrides_disk_revision() -> str:
    """Revision token for catalog cache invalidation (mtime of overrides file)."""
    try:
        return str(OVERRIDES_PATH.stat().st_mtime_ns)
    except OSError:
        return "0"


def load_overrides_document() -> dict[str, Any]:
    if not OVERRIDES_PATH.is_file():
        return {"version": 1, "overrides": {}}
    try:
        raw = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "overrides": {}}
    if not isinstance(raw, dict):
        return {"version": 1, "overrides": {}}
    raw.setdefault("version", 1)
    raw.setdefault("overrides", {})
    return raw


def save_overrides_document(doc: dict[str, Any]) -> None:
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=False)
    tmp = OVERRIDES_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    tmp.replace(OVERRIDES_PATH)


def get_user_override(title: str, artist: str) -> dict[str, Any] | None:
    doc = load_overrides_document()
    entry = (doc.get("overrides") or {}).get(override_storage_key(title, artist))
    return copy.deepcopy(entry) if entry else None


def list_user_override_keys() -> list[str]:
    doc = load_overrides_document()
    return sorted((doc.get("overrides") or {}).keys())


def delete_user_override(title: str, artist: str) -> bool:
    doc = load_overrides_document()
    key = override_storage_key(title, artist)
    overrides = doc.get("overrides") or {}
    if key not in overrides:
        return False
    del overrides[key]
    doc["overrides"] = overrides
    save_overrides_document(doc)
    return True


def normalize_chord_token(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    return raw


def normalize_sections(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, chords in (sections or {}).items():
        section = str(name or "").strip()
        if not section:
            continue
        cleaned = [normalize_chord_token(c) for c in (chords or [])]
        cleaned = [c for c in cleaned if c]
        if cleaned:
            out[section] = cleaned
    return out


def reorder_sections(
    sections: dict[str, list[str]],
    section_order: list[str] | None,
) -> dict[str, list[str]]:
    if not section_order:
        return sections
    ordered: dict[str, list[str]] = {}
    seen: set[str] = set()
    for name in section_order:
        if name in sections and name not in seen:
            ordered[name] = sections[name]
            seen.add(name)
    for name, chords in sections.items():
        if name not in seen:
            ordered[name] = chords
    return ordered


def save_user_override(
    *,
    title: str,
    artist: str,
    genre: str,
    key: str,
    sections: dict[str, list[str]],
    chart_versions: dict[str, dict[str, list[str]]] | None = None,
    section_order: list[str] | None = None,
    override_status: str,
    edited_level: str | None = None,
    catalog_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sections = reorder_sections(normalize_sections(sections), section_order)
    versions: dict[str, dict[str, list[str]]] = {}
    if chart_versions:
        for level, level_sections in chart_versions.items():
            versions[level] = reorder_sections(
                normalize_sections(level_sections),
                section_order,
            )

    entry = {
        "title": title,
        "artist": artist,
        "genre": genre,
        "key": key,
        "sections": sections,
        "chart_versions": versions,
        "section_order": list(section_order or sections.keys()),
        "override_status": override_status,
        "edited_level": edited_level,
        "saved_at": _utc_now_iso(),
        "catalog_snapshot": catalog_snapshot,
    }

    doc = load_overrides_document()
    doc.setdefault("overrides", {})
    doc["overrides"][override_storage_key(title, artist)] = entry
    save_overrides_document(doc)
    return entry


def apply_user_override_to_record(record: dict[str, Any]) -> dict[str, Any]:
    """Merge saved user chart onto catalog row (verified/corrected override wins over catalog)."""
    title = str(record.get("title") or "")
    artist = str(record.get("artist") or "")
    entry = get_user_override(title, artist)
    if not entry:
        return record

    out = copy.deepcopy(record)
    catalog_status = out.get("chart_status")
    section_order = entry.get("section_order")

    out["sections"] = reorder_sections(
        copy.deepcopy(entry.get("sections") or {}),
        section_order,
    )
    if entry.get("key"):
        out["key"] = entry["key"]

    merged_versions = copy.deepcopy(out.get("chart_versions") or {})
    for level, level_sections in (entry.get("chart_versions") or {}).items():
        merged_versions[level] = reorder_sections(
            copy.deepcopy(level_sections),
            section_order,
        )
    if merged_versions:
        out["chart_versions"] = merged_versions
        if entry.get("edited_level") and entry["edited_level"] in merged_versions:
            out["sections"] = copy.deepcopy(merged_versions[entry["edited_level"]])

    out["chart_status"] = entry.get("override_status", USER_CORRECTED)
    out["user_override"] = {
        "status": entry.get("override_status", USER_CORRECTED),
        "saved_at": entry.get("saved_at"),
        "edited_level": entry.get("edited_level"),
        "catalog_chart_status": catalog_status,
        "section_order": section_order,
    }
    if section_order:
        out["section_order"] = section_order
    return out


def apply_user_overrides_to_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [apply_user_override_to_record(r) for r in records]


def export_overrides_json() -> str:
    return json.dumps(load_overrides_document(), indent=2, ensure_ascii=False)


def import_overrides_json(text: str, *, merge: bool = True) -> int:
    incoming = json.loads(text)
    if not isinstance(incoming, dict):
        raise ValueError("Override file must be a JSON object.")
    new_overrides = incoming.get("overrides")
    if not isinstance(new_overrides, dict):
        raise ValueError('Override file must contain an "overrides" object.')

    doc = load_overrides_document() if merge else {"version": 1, "overrides": {}}
    doc.setdefault("overrides", {})
    count = 0
    for key, entry in new_overrides.items():
        if not isinstance(entry, dict):
            continue
        title = entry.get("title") or ""
        artist = entry.get("artist") or ""
        if title and artist:
            key = override_storage_key(title, artist)
        entry = copy.deepcopy(entry)
        entry["sections"] = normalize_sections(entry.get("sections") or {})
        doc["overrides"][key] = entry
        count += 1
    save_overrides_document(doc)
    return count


def catalog_snapshot_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": record.get("key"),
        "chart_status": record.get("chart_status"),
        "sections": copy.deepcopy(record.get("sections") or {}),
        "chart_versions": copy.deepcopy(record.get("chart_versions") or {}),
    }


def parse_pipe_chord_line(line: str) -> list[str]:
    parts = re.split(r"[|,]+", str(line or ""))
    return [c for c in (normalize_chord_token(p) for p in parts) if c]
