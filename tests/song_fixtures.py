"""Real catalog songs for the song-aware warmup tests (the app's own catalog, activated the way the app activates it)."""
from __future__ import annotations

import hashlib
import json

from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY
from song_catalog.catalog import load_song_catalog
from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG, commit_explicit_music_source_choice, ensure_song_picker_catalog

_LIB, _PICK, _GENRES, _RECORDS = load_song_catalog()
ALTO, TENOR = "Alto saxophone (Eb)", "Tenor saxophone (Bb)"


def lib_song(title: str, genre: str = "Jazz", key: str | None = None) -> dict:
    """The chart as ``warmup_song.read_song`` returns it, straight from the catalog record (the song's own key)."""
    rec = _LIB[genre][title]
    sections = {k: list(v) for k, v in rec["sections"].items()}
    song = {"title": title, "practice_key": key or rec["key"], "original_key": rec["key"], "meter": "4/4", "source": "catalog", "sections": sections,
            "order": list(sections), "active_section": next(iter(sections))}
    song["hash"] = hashlib.sha1(json.dumps([song["title"], song["practice_key"], song["meter"], sections], sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return song


def song_session(title: str = "Blue Bossa", *, instrument: str = "Saxophone", sax: str | None = ALTO, level: str = "Intermediate", genre: str = "Jazz",
                 user: str = "u1", workspace: str = "daniel", practice_key: str | None = None) -> dict:
    s: dict = {"instrument": instrument, "level": level, "studio_page": "creative", "backing_track_bpm": 100, "_suite_auth_user_id": user, "_suite_active_workspace_id": workspace}
    if sax:
        s[SAX_KEY] = sax
    ensure_song_picker_catalog(s)
    activate_song(s, title, genre=genre, practice_key=practice_key)
    return s


def activate_song(s: dict, title: str, *, genre: str = "Jazz", practice_key: str | None = None) -> None:
    label = next(k for k, v in _PICK[genre].items() if v.get("title") == title)
    rec = _PICK[genre][label]
    key = practice_key or rec["key"]
    commit_explicit_music_source_choice(s, SOURCE_CATALOG)
    s[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CATALOG
    pick = f"{genre}\x1f{label}"
    s.update(active_catalog_pick_key=pick, song=title, artist=rec.get("artist", ""), display_key=key, concert_key=key,
             selected_song={"pick_key": pick, "title": title, "artist": rec.get("artist", ""), "genre": genre, "key": rec["key"]},
             improv_song_concert_sections={k: list(v) for k, v in _LIB[genre][title]["sections"].items()})
