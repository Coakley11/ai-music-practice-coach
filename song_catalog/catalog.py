"""Build SONG_LIBRARY / SONG_PICKER_CATALOG and search index from curated core data.

Song records may include optional ``composer`` and ``extensions`` keys
(``midi_path``, ``musicxml_path``, ``harmonic_analysis``, etc.) for future features.

To extend the main library: edit ``curated_songs.py`` for hand-crafted charts.
Generated shells in ``bulk_songs.py`` are intentionally hidden from the main app
until they are upgraded beyond ``chart_status="placeholder"``.
Optional JSON merge can be wired in here later.
"""

from __future__ import annotations

import re
from typing import Any

from .bulk_songs import bulk_song_records
from .curated_songs import curated_song_records
from .user_overrides import apply_user_overrides_to_records

INCLUDE_PLACEHOLDER_CHARTS = False

TRUSTED_CORE_KEYS = {
    ("Piano Man", "Billy Joel"),
    ("Just the Way You Are", "Billy Joel"),
    ("Turn the Lights Back On", "Billy Joel"),
    ("Vienna", "Billy Joel"),
    ("Say", "John Mayer"),
    ("Why Georgia", "John Mayer"),
    ("Gravity", "John Mayer"),
    ("Perfect", "Ed Sheeran"),
    ("Thinking Out Loud", "Ed Sheeran"),
    ("Shape of You", "Ed Sheeran"),
    ("Photograph", "Ed Sheeran"),
    ("Viva La Vida", "Coldplay"),
    ("Let It Be", "The Beatles"),
    ("Hey Jude", "The Beatles"),
    ("Yesterday", "The Beatles"),
    ("Here Comes the Sun", "The Beatles"),
    ("Don't Stop Believin'", "Journey"),
    ("The Girl from Ipanema", "Antonio Carlos Jobim"),
    ("Wave", "Antonio Carlos Jobim"),
    ("Blue Bossa", "Kenny Dorham"),
    ("Autumn Leaves", "Jazz Standard"),
    ("Autumn Leaves", "Eric Clapton"),
    ("All the Things You Are", "Jazz Standard"),
    ("Satin Doll", "Duke Ellington"),
    ("Fly Me to the Moon", "Bart Howard"),
    ("So Nice (Summer Samba)", "Marcos Valle"),
    ("One Note Samba", "Antonio Carlos Jobim"),
    ("Shallow", "Lady Gaga / Bradley Cooper"),
    ("All of Me", "John Legend"),
    ("Attention", "Charlie Puth"),
    ("Dance Monkey", "Tones and I"),
    ("I'm Yours", "Jason Mraz"),
    ("Hotel California", "Eagles"),
    ("Californication", "Red Hot Chili Peppers"),
    ("Iris", "Goo Goo Dolls"),
    ("Take Me Home, Country Roads", "John Denver"),
    ("How Deep Is Your Love", "Bee Gees"),
    ("Isn't She Lovely", "Stevie Wonder"),
    ("Just the Two of Us", "Grover Washington Jr. / Bill Withers"),
    ("Rocket Man", "Elton John"),
    ("In My Life", "The Beatles"),
    ("Across the Universe", "The Beatles"),
    ("Uptown Girl", "Billy Joel"),
    ("Kiss Me", "Sixpence None the Richer"),
    ("Girls Just Want to Have Fun", "Cyndi Lauper"),
    ("Every Breath You Take", "The Police"),
    ("Careless Whisper", "George Michael"),
    ("We Are the Champions", "Queen"),
    ("Take On Me", "a-ha"),
    ("Take On Me (MTV Unplugged Version)", "a-ha"),
    ("I Want It That Way", "Backstreet Boys"),
    ("I Won't Say (I'm in Love)", "Disney · Hercules"),
    ("How Far I'll Go", "Disney · Moana"),
    ("Billie Jean", "Michael Jackson"),
    ("Love Story", "Taylor Swift"),
    ("Breakaway", "Kelly Clarkson"),
    ("Complicated", "Avril Lavigne"),
    ("Imagine", "John Lennon"),
    ("Wonderwall", "Oasis"),
    ("You've Got a Friend in Me", "Randy Newman"),
    ("Hava Nagila", "Traditional"),
    ("Hevenu Shalom Aleichem", "Traditional"),
    ("Oseh Shalom", "Traditional"),
    ("Am Yisrael Chai", "Traditional"),
    ("Siman Tov U'Mazal Tov", "Traditional"),
    ("Yerushalayim Shel Zahav", "Traditional"),
    ("Hinei Ma Tov", "Traditional"),
    ("Shalom Aleichem", "Traditional Jewish Sabbath Song"),
    ("Adon Olam", "Traditional"),
}


def _norm_key(title: str, artist: str) -> tuple[str, str]:
    return title.strip().lower(), artist.strip().lower()


def _is_trusted_core(row: dict[str, Any]) -> bool:
    return (row.get("title"), row.get("artist")) in TRUSTED_CORE_KEYS


def _with_reliability(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    trusted = _is_trusted_core(out)
    out["trusted_core"] = trusted
    return out


def _merge_records() -> list[dict[str, Any]]:
    """Curated entries win over bulk on duplicate (title, artist).

    Also skips bulk rows when the same genre already has a song with that
    title (SONG_LIBRARY is keyed by title per genre in the Streamlit UI).
    """
    seen_ta: set[tuple[str, str]] = set()
    seen_gt: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in curated_song_records():
        row = _with_reliability(row)
        ta = _norm_key(row["title"], row["artist"])
        gt = (row["genre"], row["title"].strip().lower())
        seen_ta.add(ta)
        seen_gt.add(gt)
        out.append(row)
    for row in bulk_song_records():
        if not INCLUDE_PLACEHOLDER_CHARTS and row.get("chart_status") == "placeholder":
            continue
        row = _with_reliability(row)
        ta = _norm_key(row["title"], row["artist"])
        gt = (row["genre"], row["title"].strip().lower())
        if ta in seen_ta:
            continue
        if gt in seen_gt:
            continue
        seen_ta.add(ta)
        seen_gt.add(gt)
        out.append(row)
    return apply_user_overrides_to_records(out)


def clear_catalog_cache() -> None:
    global _CACHE
    _CACHE = None


def reload_song_catalog():
    """Drop in-memory cache and rebuild libraries (after user override save)."""
    clear_catalog_cache()
    return load_song_catalog()


def build_libraries(records: list[dict[str, Any]]):
    picker: dict[str, dict[str, dict[str, Any]]] = {}
    library: dict[str, dict[str, dict[str, Any]]] = {}

    for r in records:
        g = r["genre"]
        title = r["title"]
        artist = r["artist"]
        label = f"{title} — {artist}"

        _row_common = {
            "title": title,
            "artist": artist,
            "genre": g,
            "key": r["key"],
            "sections": r["sections"],
            "chart_versions": r.get("chart_versions") or {},
            "chart_status": r.get("chart_status", "practice_simplified"),
            "trusted_core": bool(r.get("trusted_core")),
            "guitar_tabs": r.get("guitar_tabs") or {},
            "composer": r.get("composer"),
            "lyric_cues": r.get("lyric_cues") or {},
            "extensions": r.get("extensions") or {},
            "user_override": r.get("user_override"),
            "section_order": r.get("section_order"),
        }
        picker.setdefault(g, {})[label] = dict(_row_common)

        library.setdefault(g, {})[title] = dict(_row_common)

    genres_preferred = ["Jazz", "Pop", "Rock", "Funk", "Blues", "Jewish", "Jewish Traditional", "Classical"]
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
    ext = r.get("extensions") or {}
    levels = list((r.get("chart_versions") or {}).keys())
    rep_tags = ext.get("repertoire_tags") or []
    parts = [
        r.get("title") or "",
        r.get("artist") or "",
        r.get("composer") or "",
        r.get("genre") or "",
        ext.get("default_groove") or "",
        ext.get("time_signature") or "",
        r.get("chart_status") or "",
        " ".join(str(t) for t in rep_tags),
        " ".join(str(v) for v in (ext.get("transliteration") or {}).values()),
        " ".join(str(v) for v in (ext.get("hebrew_lyrics") or {}).values()),
        "jazz standard flagship" if ext.get("jazz_standard_flagship") else "",
        " ".join(levels),
        "beginner" if "Beginner" in levels else "",
        "intermediate" if "Intermediate" in levels else "",
        "advanced" if "Advanced" in levels else "",
    ]
    return " ".join(str(p) for p in parts if p).lower()


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
    genres: list[str] | None = None,
    limit: int = 120,
) -> list[dict[str, Any]]:
    """
    Filter songs by title, artist, composer, genre, groove/style, or chart level.
    Supports partial typing; all space-separated tokens must match somewhere in the blob.

    When ``genres`` is a non-empty list, keep rows whose genre is in that list (OR).
    Legacy ``genre`` (single) is used only when ``genres`` is empty/None.
    """
    q = (query or "").strip().lower()
    genre_set = {g for g in (genres or []) if g}
    if genre_set:
        pool = [r for r in records if r.get("genre") in genre_set]
    elif genre:
        pool = [r for r in records if r.get("genre") == genre]
    else:
        pool = list(records)

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


PICK_KEY_SEP = "\x1f"


def format_pick_key(genre: str, label: str) -> str:
    """Stable option id for selectbox (genre and label may contain unicode)."""
    return f"{genre}{PICK_KEY_SEP}{label}"


def parse_pick_key(key: str) -> tuple[str, str]:
    """Parse a pick key; never raises.

    Canonical keys are ``genre\\x1flabel``. Plain titles/labels (no separator) return
    ``("", text)`` so callers can resolve via :func:`resolve_pick_key`.
    """
    raw = (key or "").strip()
    if not raw:
        return "", ""
    if PICK_KEY_SEP in raw:
        genre, label = raw.split(PICK_KEY_SEP, 1)
        return genre.strip(), label.strip()
    return "", raw


def _match_record_from_plain(
    records: list[dict[str, Any]],
    text: str,
) -> dict[str, Any] | None:
    """Match catalog row from ``Title — Artist`` or title-only text."""
    text = (text or "").strip()
    if not text or not records:
        return None
    title, _, artist = text.partition(" — ")
    title = title.strip()
    artist = artist.strip()
    if artist:
        for r in records:
            if r.get("title") == title and r.get("artist") == artist:
                return r
        return None
    matches = [r for r in records if r.get("title") == text or r.get("title") == title]
    if len(matches) == 1:
        return matches[0]
    return None


def resolve_pick_key(
    key: str,
    *,
    song_picker_catalog: dict[str, dict[str, dict]] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> str | None:
    """Resolve dropdown/session value to canonical ``genre\\x1flabel`` key.

    Handles legacy/plain values (display label only, title only, stale session keys).
    Returns ``None`` when no unique catalog match exists (e.g. unknown custom title).
    """
    raw = (key or "").strip()
    if not raw:
        return None

    genre_hint, label_part = parse_pick_key(raw)
    search_text = label_part or raw

    if song_picker_catalog:
        if genre_hint and label_part:
            labels = song_picker_catalog.get(genre_hint) or {}
            if label_part in labels:
                return format_pick_key(genre_hint, label_part)

        exact: list[tuple[str, str]] = []
        for g, labels in song_picker_catalog.items():
            for lab in labels:
                if lab == search_text:
                    exact.append((g, lab))
        if len(exact) == 1:
            g, lab = exact[0]
            return format_pick_key(g, lab)

        title, _, artist = search_text.partition(" — ")
        title = title.strip()
        artist = artist.strip()
        by_row: list[tuple[str, str]] = []
        for g, labels in song_picker_catalog.items():
            for lab, data in labels.items():
                row_title = str(data.get("title") or "")
                row_artist = str(data.get("artist") or "")
                if row_title != title and row_title != search_text:
                    continue
                if artist and row_artist != artist:
                    continue
                by_row.append((g, lab))
        if len(by_row) == 1:
            g, lab = by_row[0]
            return format_pick_key(g, lab)

    if records:
        rec = _match_record_from_plain(records, search_text)
        if rec:
            lab = f"{rec['title']} — {rec['artist']}"
            return format_pick_key(str(rec.get("genre") or ""), lab)

    return None


def record_for_pick_key(records: list[dict[str, Any]], pick_key: str) -> dict[str, Any] | None:
    """Resolve a picker/session key back to the merged catalog row."""
    canonical = resolve_pick_key(pick_key, records=records)
    genre, label = parse_pick_key(canonical or pick_key)
    title, _, artist = label.partition(" — ")
    title = title.strip()
    artist = artist.strip()
    if genre:
        for r in records:
            if r.get("genre") == genre and r.get("title") == title:
                return r
    rec = _match_record_from_plain(records, label or pick_key)
    if rec:
        return rec
    return None
