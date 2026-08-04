"""Regression: New Idea must change fingerprint and survive artifact projection (rerun)."""

from __future__ import annotations

import copy
import unittest

from creative_mission_artifact_persistence import (
    commit_mission_artifacts_to_canonical,
    project_mission_artifacts_from_canonical,
)
from improvisation_intelligence import ImprovSessionContext
from improvisation_intelligence_ui import _run_mission_example_generate
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    load_mission_example,
    mission_example_fingerprint,
)


class TestMissionNewIdeaButton(unittest.TestCase):
    def _session(self) -> dict:
        return {
            "song": "Shape",
            "artist": "Artist",
            "display_key": "F#m",
            "concert_key": "F#m",
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "Improvisation",
            "improv_active_mission": "Improvise using only chord tones",
            "improv_mission_pick": "Improvise using only chord tones",
            "home_sections": {"Chorus": ["Em"]},
            "improv_mission_chord_options": ["Em"],
            "ii_selected_chord_index": 0,
            "ii_selected_chord": "Em",
            "ii_selected_section": "Chorus",
            "backing_track_bpm": 100,
        }

    def test_new_idea_changes_fingerprint_and_survives_projection(self) -> None:
        session = self._session()
        _run_mission_example_generate(session, "normal")
        first_fp = str(session.get("_mission_example_output_fp") or "")
        self.assertTrue(first_fp)
        first_display = (session.get(MISSION_EXAMPLE_KEY) or {}).get("motif", {}).get("display")

        _run_mission_example_generate(session, "new")
        second_fp = str(session.get("_mission_example_output_fp") or "")
        second_display = (session.get(MISSION_EXAMPLE_KEY) or {}).get("motif", {}).get("display")
        self.assertNotEqual(first_fp, second_fp)
        self.assertNotEqual(first_display, second_display)

        saved = copy.deepcopy(session.get(MISSION_EXAMPLE_KEY))
        commit_mission_artifacts_to_canonical(
            session,
            reason="creative_mission_example_change",
            values={MISSION_EXAMPLE_KEY: saved},
        )
        session[MISSION_EXAMPLE_KEY] = {"motif": {"display": "stale-placeholder"}}
        project_mission_artifacts_from_canonical(session, overwrite=True)

        ctx = ImprovSessionContext(
            song_title="Shape",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Chorus": ["Em"]},
        )
        ex = load_mission_example(session, ctx)
        self.assertIsNotNone(ex)
        assert ex is not None
        self.assertEqual(ex.motif.get("display"), second_display)
        self.assertEqual(mission_example_fingerprint(ex), second_fp)


if __name__ == "__main__":
    unittest.main()
