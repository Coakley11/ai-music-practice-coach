"""New Idea + rerun/hydrate regression for mission examples."""

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
    MISSION_NEW_IDEA_DIAG_KEY,
    apply_mission_motif_transform,
    load_mission_example,
    mission_example_fingerprint,
    motif_material_fingerprint,
)


class TestMissionNewIdeaRerunFlow(unittest.TestCase):
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
            "home_sections": {"Chorus": ["Em"], "Melody A": ["Ab7"]},
            "improv_mission_chord_options": ["Em", "Ab7"],
            "ii_selected_chord_index": 1,
            "ii_selected_chord": "Ab7",
            "ii_selected_section": "Melody A",
            "backing_track_bpm": 100,
            "creative_workspace_state": {},
        }

    def _ctx(self) -> ImprovSessionContext:
        return ImprovSessionContext(
            song_title="Shape",
            artist="Artist",
            key_center="F#m",
            display_key="F#m",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            sections={"Melody A": ["Ab7"]},
        )

    def test_new_idea_callback_survives_canonical_projection_rerun(self) -> None:
        session = self._session()
        _run_mission_example_generate(session, "normal")
        first_mat = motif_material_fingerprint(
            (session.get(MISSION_EXAMPLE_KEY) or {}).get("motif")
        )
        _run_mission_example_generate(session, "new")
        diag = session.get(MISSION_NEW_IDEA_DIAG_KEY) or {}
        self.assertNotEqual(diag.get("previous_material_fp"), diag.get("generated_material_fp"))
        self.assertNotEqual(diag.get("previous_fp"), diag.get("generated_fp"))
        gen_fp = str(session.get("_mission_example_output_fp") or "")
        commit_mission_artifacts_to_canonical(
            session,
            reason="creative_mission_example_change",
            values={MISSION_EXAMPLE_KEY: copy.deepcopy(session[MISSION_EXAMPLE_KEY])},
        )
        session[MISSION_EXAMPLE_KEY] = {"motif": {"display": "stale"}}
        session["_mission_example_output_fp"] = "stale"
        project_mission_artifacts_from_canonical(session, overwrite=True)
        loaded = load_mission_example(session, self._ctx())
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(mission_example_fingerprint(loaded), gen_fp)
        self.assertNotEqual(motif_material_fingerprint(loaded.motif), first_mat)

    def test_sequence_down_persists_through_hydrate(self) -> None:
        session = self._session()
        ctx = self._ctx()
        _run_mission_example_generate(session, "normal")
        before = motif_material_fingerprint((session.get(MISSION_EXAMPLE_KEY) or {}).get("motif"))
        apply_mission_motif_transform(session, ctx, "sequence_down", bpm=100)
        after = motif_material_fingerprint((session.get(MISSION_EXAMPLE_KEY) or {}).get("motif"))
        self.assertNotEqual(before, after)
        commit_mission_artifacts_to_canonical(
            session,
            reason="creative_mission_example_change",
            values={MISSION_EXAMPLE_KEY: copy.deepcopy(session[MISSION_EXAMPLE_KEY])},
        )
        session.pop(MISSION_EXAMPLE_KEY, None)
        project_mission_artifacts_from_canonical(session, overwrite=True)
        restored = load_mission_example(session, ctx)
        assert restored is not None
        self.assertEqual(motif_material_fingerprint(restored.motif), after)


if __name__ == "__main__":
    unittest.main()
