"""Backing-track generation helpers — timing profile and audio prep caches."""

from __future__ import annotations

import base64
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from studio_cache import session_cache_get, session_cache_get_or_set


@dataclass
class BackingGenProfile:
    """Timing breakdown for one generate pass (developer diagnostics)."""

    events_ms: float = 0.0
    timeline_ms: float = 0.0
    synthesis_ms: float = 0.0
    b64_ms: float = 0.0
    total_ms: float = 0.0
    cache_hit_wav: bool = False
    cache_hit_timeline: bool = False
    cache_hit_b64: bool = False
    bar_count: int = 0
    wav_kb: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["extra"] = dict(self.extra)
        return row


def prepare_wav_b64(session_state: dict, signature: tuple, wav: bytes) -> tuple[str, float, bool]:
    """Encode WAV to base64 once; cache in session for fast Play reruns."""
    if session_cache_get(session_state, "backing_wav_b64", signature) is not None:
        return str(session_cache_get(session_state, "backing_wav_b64", signature)), 0.0, True
    t0 = time.perf_counter()
    encoded = base64.b64encode(wav).decode("ascii")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    session_cache_get_or_set(
        session_state,
        "backing_wav_b64",
        signature,
        lambda: encoded,
        max_entries=8,
    )
    return encoded, elapsed_ms, False


def profile_elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
