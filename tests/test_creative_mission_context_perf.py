"""Performance smoke: cached mission context vs cold build."""

from __future__ import annotations

import time
import unittest

from mission_practice_context import build_mission_practice_context, ensure_mission_practice_context


class TestCreativeMissionContextPerf(unittest.TestCase):
    def test_cached_ensure_faster_than_repeated_build(self) -> None:
        session = {
            "improv_active_mission": "Guide-tone targeting",
            "improv_mission_chord_options": ["Dm7"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Dm7",
            "backing_track_bpm": 100,
        }
        refresh = build_mission_practice_context(session)
        session["improv_mission_practice_context"] = refresh.to_dict()

        t0 = time.perf_counter()
        for _ in range(2000):
            build_mission_practice_context(session)
        cold_ms = (time.perf_counter() - t0) * 1000

        ensure_mission_practice_context(session, force=True)
        t1 = time.perf_counter()
        for _ in range(2000):
            ensure_mission_practice_context(session)
        warm_ms = (time.perf_counter() - t1) * 1000

        self.assertLess(warm_ms, cold_ms * 0.85)


if __name__ == "__main__":
    unittest.main()
