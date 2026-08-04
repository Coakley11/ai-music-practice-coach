"""Navigation speed — artifact projection skip and route baseline helpers."""

from __future__ import annotations

import time
import unittest
from typing import Any

from creative_mission_artifact_persistence import (
    CREATIVE_WORKSPACE_STATE_KEY,
    mission_artifact_canonical_fingerprint,
    project_mission_artifacts_from_canonical,
    should_skip_mission_artifact_projection,
)
from music_dev_route_baseline import route_perf_begin, route_perf_end


class TestMissionArtifactProjectionSkip(unittest.TestCase):
    def _session_with_example(self) -> dict[str, Any]:
        example = {"motif": {"notes": ["C4", "E4", "G4"]}, "variant": "normal"}
        return {
            CREATIVE_WORKSPACE_STATE_KEY: {
                "improv_mission_example": example,
            },
            "improv_mission_example": example,
        }

    def test_second_projection_skipped_when_unchanged(self) -> None:
        session = self._session_with_example()
        self.assertFalse(should_skip_mission_artifact_projection(session))
        project_mission_artifacts_from_canonical(session, overwrite=False)
        self.assertTrue(should_skip_mission_artifact_projection(session))

    def test_projection_skip_is_faster_on_repeat(self) -> None:
        session = self._session_with_example()
        t0 = time.perf_counter()
        for _ in range(5):
            project_mission_artifacts_from_canonical(session, overwrite=False)
        first_pass_ms = (time.perf_counter() - t0) * 1000.0
        session2 = self._session_with_example()
        project_mission_artifacts_from_canonical(session2, overwrite=False)
        t1 = time.perf_counter()
        for _ in range(5):
            if not should_skip_mission_artifact_projection(session2):
                project_mission_artifacts_from_canonical(session2, overwrite=False)
        skip_pass_ms = (time.perf_counter() - t1) * 1000.0
        self.assertLess(skip_pass_ms, first_pass_ms * 0.5)
        self.assertTrue(mission_artifact_canonical_fingerprint(session2))


class TestRouteBaseline(unittest.TestCase):
    def test_route_perf_records_wall_ms(self) -> None:
        session: dict[str, Any] = {"dev_mode": True}
        route_perf_begin(session, "test.route")
        route_perf_end(session, "test.route")
        baselines = session.get("_music_dev_route_baselines") or {}
        rec = baselines.get("test.route")
        self.assertIsInstance(rec, dict)
        self.assertIn("wall_ms", rec)


if __name__ == "__main__":
    unittest.main()
