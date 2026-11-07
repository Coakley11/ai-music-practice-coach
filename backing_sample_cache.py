"""One memory-limited store for every recorded instrument's decoded audio.

A sample is decoded the first time it is played. When the store is over its limit the least
recently played samples go first, so memory follows what a song plays, not the library's size.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict

import numpy as np

DEFAULT_LIMIT_MB = 96


def cache_limit_bytes() -> int:
    try:
        return max(8, int(os.environ.get("MUSIC_SAMPLE_CACHE_MB") or DEFAULT_LIMIT_MB)) * 1024 * 1024
    except ValueError:
        return DEFAULT_LIMIT_MB * 1024 * 1024


class SampleCache:
    """Safe for the app's background render threads."""

    def __init__(self) -> None:
        self._items: OrderedDict[tuple, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()
        self.bytes = 0

    def get(self, key: tuple) -> np.ndarray | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: tuple, value: np.ndarray) -> None:
        with self._lock:
            if key in self._items:
                return
            self._items[key] = value
            self.bytes += int(value.nbytes)
            limit = cache_limit_bytes()
            while self.bytes > limit and len(self._items) > 1:
                _, old = self._items.popitem(last=False)
                self.bytes -= int(old.nbytes)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.bytes = 0


SHARED = SampleCache()
