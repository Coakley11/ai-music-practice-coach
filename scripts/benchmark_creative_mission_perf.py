"""Benchmark mission practice context caching (Creative / Missions hot path)."""

from __future__ import annotations

import sys
import timeit
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mission_practice_context import (
    build_mission_practice_context,
    ensure_mission_practice_context,
    refresh_mission_practice_context,
)


def _sample_session() -> dict:
    return {
        "improv_active_mission": "Target tone drill",
        "improv_mission_pick": "Target tone drill",
        "improv_mission_chord_options": ["Bm", "Em", "G", "A"] * 2,
        "ii_selected_chord_index": 7,
        "ii_selected_chord": "A",
        "ii_selected_section": "Chorus",
        "backing_track_bpm": 92,
        "backing_groove_style": "Pop groove",
        "backing_time_signature": "4/4",
        "backing_track_loops": 4,
        "mission_exact_backing_volume": 0.85,
        "mission_exact_backing_loop": True,
    }


def main() -> None:
    session = _sample_session()
    n = 5000
    cold = timeit.timeit(lambda: build_mission_practice_context(dict(session)), number=n)
    refresh_mission_practice_context(session)
    warm = timeit.timeit(lambda: ensure_mission_practice_context(session), number=n)
    print(f"build_mission_practice_context x{n}: {cold:.4f}s ({cold / n * 1e6:.1f} µs/op)")
    print(f"ensure_mission_practice_context (cached) x{n}: {warm:.4f}s ({warm / n * 1e6:.1f} µs/op)")


if __name__ == "__main__":
    main()
