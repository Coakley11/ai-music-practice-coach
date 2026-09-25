"""Process-lifetime backing WAV/timeline caches (survive Streamlit script reruns).

The main Streamlit script re-executes top-to-bottom each run. A plain
``_BACKING_WAV_CACHE = {}`` in that file would wipe neighbor prefetch between
Play and Key-cycle CONTINUE_PLAY. Imported module globals persist for the
server process lifetime.
"""

from __future__ import annotations

BACKING_WAV_CACHE: dict = {}
BACKING_TIMELINE_CACHE: dict = {}
BACKING_CACHE_MAX = 12


def evict_oldest(cache: dict) -> None:
    while len(cache) > BACKING_CACHE_MAX:
        try:
            first_key = next(iter(cache))
        except StopIteration:
            return
        cache.pop(first_key, None)


__all__ = [
    "BACKING_CACHE_MAX",
    "BACKING_TIMELINE_CACHE",
    "BACKING_WAV_CACHE",
    "evict_oldest",
]
