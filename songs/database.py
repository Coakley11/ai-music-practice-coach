"""
Bridge to the merged song catalog.

Hand-authored charts live in ``song_catalog/curated_songs.py``; bulk shells in
``song_catalog/bulk_songs.py``. Optional JSON/CSV loaders can be added here later
without changing the Streamlit UI.
"""

from __future__ import annotations

# Re-export for a stable ``from songs.database import load_song_catalog`` path.
from song_catalog.catalog import load_song_catalog  # noqa: F401

__all__ = ["load_song_catalog"]
