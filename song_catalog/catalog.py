"""Build SONG_LIBRARY / SONG_PICKER_CATALOG and search index from curated + bulk data.

Song records may include optional ``composer`` and ``extensions`` keys
(``midi_path``, ``musicxml_path``, ``harmonic_analysis``, etc.) for future features.

To extend the library: edit ``curated_songs.py`` for hand-crafted charts, or
``bulk_songs.py`` for generated shells. Optional JSON merge can be wired in here later.
"""

from __future__ import annotations

import re
from typing import Any

from .bulk_songs import bulk_song_records
from .curated_songs import curated_song_records


def _norm_key(title: str, artist: str) -> tuple[str, str]:
    return title.strip().lower(), artist.strip().lower()


def _merge_records() -> list[dict[str, Any]]:
    """Curated entries win over bulk on duplicate (title, artist).

    Also skips bulk rows when the same genre already has a song with that
    title (SONG_LIBRARY is keyed by title per genre in the Streamlit UI).
    """
    seen_ta: set[tuple[str, str]] = set()
    seen_gt: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in curated_song_records():
        ta = _norm_key(row["title"], row["artist"])
        gt = (row["genre"], row["title"].strip().lower())
        seen_ta.add(ta)
        seen_gt.add(gt)
        out.append(row)
    for row in bulk_song_records():
        ta = _norm_key(row["title"], row["artist"])
        gt = (row["genre"], row["title"].strip().lower())
        if ta in seen_ta:
            continue
        if gt in seen_gt:
            continue
        seen_ta.add(ta)
        seen_gt.add(gt)
        out.append(row)
    return out


def build_libraries(records: list[dict[str, Any]]):
    picker: dict[str, dict[str, dict[str, Any]]] = {}
    library: dict[str, dict[str, dict[str, Any]]] = {}

    for r in records:
        g = r["genre"]
        title = r["title"]
        artist = r["artist"]
        label = f"{title} — {artist}"

        picker.setdefault(g, {})[label] = {
            "title": title,
            "artist": artist,
            "genre": g,
            "key": r["key"],
            "sections": r["sections"],
            "guitar_tabs": r.get("guitar_tabs") or {},
            "composer": r.get("composer"),
            "extensions": r.get("extensions") or {},
        }

        library.setdefault(g, {})[title] = {
            "artist": artist,
            "key": r["key"],
            "sections": r["sections"],
            "guitar_tabs": r.get("guitar_tabs") or {},
            "composer": r.get("composer"),
            "genre": g,
            "extensions": r.get("extensions") or {},
        }

    genres_preferred = ["Jazz", "Pop", "Rock", "Funk", "Blues", "Classical"]
    genres = [g for g in genres_preferred if g in library]
    genres.extend(sorted(g for g in library if g not in genres))
    return library, picker, genres, records


_CACHE: tuple | None = None


def load_song_catalog():
    global _CACHE
    if _CACHE is None:
        records = _merge_records()
        _CACHE = build_libraries(records)
    return _CACHE


def build_search_blob(r: dict[str, Any]) -> str:
    parts = [
        r.get("title") or "",
        r.get("artist") or "",
        r.get("composer") or "",
        r.get("genre") or "",
    ]
    return " ".join(parts).lower()


def _token_match(token: str, blob: str) -> bool:
    if not token:
        return True
    if token in blob:
        return True
    if len(token) >= 2 and token in blob.replace(" ", ""):
        return True
    for word in re.findall(r"[a-z0-9]+", blob):
        if word.startswith(token):
            return True
    return False


def search_records(
    records: list[dict[str, Any]],
    query: str,
    *,
    genre: str | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    """
    Filter songs by title, artist, composer, or genre.
    Supports partial typing; all space-separated tokens must match somewhere in the blob.
    """
    q = (query or "").strip().lower()
    pool = [r for r in records if genre is None or r.get("genre") == genre]

    if not q:
        return pool[:limit]

    tokens = [t for t in re.split(r"\s+", q) if t]

    def ok(r: dict[str, Any]) -> bool:
        blob = build_search_blob(r)
        if not tokens:
            return True
        return all(_token_match(t, blob) for t in tokens)

    matched = [r for r in pool if ok(r)]

    def score(r: dict[str, Any]) -> int:
        blob = build_search_blob(r)
        title = (r.get("title") or "").lower()
        artist = (r.get("artist") or "").lower()
        s = 0
        if q in title:
            s += 50
        if q in artist:
            s += 40
        if q in blob:
            s += 20
        for t in tokens:
            if t in title:
                s += 15
            if t in artist:
                s += 12
        return s

    matched.sort(key=score, reverse=True)
    return matched[:limit]


def format_pick_key(genre: str, label: str) -> str:
    """Stable option id for selectbox (genre and label may contain unicode)."""
    return f"{genre}\x1f{label}"


def parse_pick_key(key: str) -> tuple[str, str]:
    genre, label = key.split("\x1f", 1)
    return genre, label


def record_for_pick_key(records: list[dict[str, Any]], pick_key: str) -> dict[str, Any] | None:
    """Resolve a picker/session key back to the merged catalog row."""
    try:
        genre, label = parse_pick_key(pick_key)
    except ValueError:
        return None
    title, _, _artist = label.partition(" — ")
    title = title.strip()
    for r in records:
        if r.get("genre") == genre and r.get("title") == title:
            return r
    return None
