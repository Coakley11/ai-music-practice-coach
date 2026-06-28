"""Canonical multitrack layer slot names (single source of truth)."""

from __future__ import annotations

MULTITRACK_SLOTS: tuple[str, ...] = (
    "Guitar",
    "Bass",
    "Piano / Keys",
    "Vocals",
    "Sax / winds",
    "Extra layer",
)

# Backward-compatible alias used by the multitrack page loop.
MT_SLOTS: list[str] = list(MULTITRACK_SLOTS)
