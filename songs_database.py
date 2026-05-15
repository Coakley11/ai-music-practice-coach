"""Stable import path for the catalog (merges curated + bulk sources).

Prefer adding new material under ``song_catalog/`` or JSON/CSV loaded in
``songs/database.py`` as that layer grows.
"""

from songs.database import load_song_catalog

__all__ = ["load_song_catalog"]
