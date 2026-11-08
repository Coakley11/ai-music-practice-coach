"""The song's own style: what kind of song it is, as saved on its source page.

This decides what the song's card LOOKS like. It is never the Backing groove (how the accompaniment SOUNDS),
never a Backing play-session snapshot, and never written back. A Custom song saved without a style shows
what the Custom page shows for it (its own default, Pop); a Composition without a genre has none.

* Catalog      the catalog genre, fixed by the catalog (the genre part of its pick key, else its catalog row).
* Custom       the progression's saved ``progression_style`` (the Custom page autosaves its draft there);
               saved without one, the Custom page's own default (Pop), which it shows in its selector.
               That default is display only: nothing is written back.
* Composition  Composition Studio's Genre / Style (``metadata.style``); the Rhythm "Style"
               (``global.progression_style``) only where Genre / Style is unset or "Other".

Read fresh from the source record on every render, so a style changed on the source page reaches the Songs
and Backing cards for the same song, through navigation, playback and reloads.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

CUSTOM_PREFIX = "custom::"
COMPOSITION_PREFIX = "composition::"
_NO_GENRE = frozenset({"", "other", "auto", "none"})


def song_source(pick_key: str) -> str:
    pk = str(pick_key or "").strip()
    if pk.startswith(CUSTOM_PREFIX):
        return "custom"
    if pk.startswith(COMPOSITION_PREFIX):
        return "composition"
    return "catalog"


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _NO_GENRE else text


@lru_cache(maxsize=1)
def custom_display_default() -> str:
    """What the Custom page shows for a progression saved without a style: its own loader's default.

    A display value only: it is never written into the saved record (the record keeps no style until the
    user saves one on the Custom page)."""
    try:
        from custom_progression_lab import load_saved_progression

        return _clean(load_saved_progression({"_": {"name": "_"}}, "_").get("progression_style")) or "Pop"
    except Exception:
        return "Pop"


def custom_progression_style(progression: Mapping[str, Any] | None) -> str:
    """The style a Custom progression shows on the Custom page: its saved style, else the page's own default
    (Pop). "" only when there is no such progression."""
    if not progression:
        return ""
    prog = progression
    return _clean(prog.get("progression_style") or prog.get("style")) or custom_display_default()


def composition_style(doc: Mapping[str, Any] | None) -> str:
    """Composition Studio's saved Genre / Style, else its Rhythm style ("" when it has neither)."""
    doc = doc or {}
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), Mapping) else {}
    glob = doc.get("global") if isinstance(doc.get("global"), Mapping) else {}
    return _clean((meta or {}).get("style")) or _clean((glob or {}).get("progression_style"))


def _catalog_row(title: str) -> Mapping[str, Any]:
    try:
        from song_catalog.catalog import load_song_catalog

        for songs in load_song_catalog()[0].values():
            row = songs.get(title)
            if row:
                return row
    except Exception:
        pass
    return {}


def catalog_genre(pick_key: str = "", *, title: str = "", record: Mapping[str, Any] | None = None) -> str:
    """The catalog's genre for a catalog song: its pick key names it ("Rock\\x1fLet It Be — The Beatles")."""
    pk = str(pick_key or "").strip()
    if "\x1f" in pk:
        genre = _clean(pk.split("\x1f", 1)[0])
        if genre:
            return genre
    rec = record or {}
    row = _catalog_row(str(title or rec.get("title") or ""))
    return _clean(row.get("genre")) or _clean(rec.get("genre"))


def saved_song_style(
    session: Any,
    pick_key: str,
    *,
    title: str = "",
    record: Mapping[str, Any] | None = None,
) -> str:
    """The song's style as saved on its source page, read now ("" when it has none)."""
    pk = str(pick_key or "").strip()
    source = song_source(pk)
    try:
        if source == "custom":
            from songs.music_source import custom_progression_for_pick_key

            return custom_progression_style(custom_progression_for_pick_key(session, pk))
        if source == "composition":
            from composition_songs_bridge import find_composition_document

            return composition_style(find_composition_document(session, pk))
    except Exception:
        return ""
    return catalog_genre(pk, title=title, record=record)
