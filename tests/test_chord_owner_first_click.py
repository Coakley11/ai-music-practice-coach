"""Selected chord owner must win on first click (Motif / Mission)."""

from __future__ import annotations

import unittest


class TestClickSymbolBeatsStaleIndex(unittest.TestCase):
    def test_resolve_prefers_clicked_bb_over_index_g(self) -> None:
        from creative_chord_selection_authority import resolve_authoritative_chord_selection

        section_map = [("Verse", ["G", "Bb", "Cm", "F"])]
        session = {
            "ii_selected_chord": "G",
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
            "_mission_chord_click_authority": {
                "chord": "Bb",
                "section": "Verse",
                # Stale index still pointing at G — the old first-click failure mode.
                "chord_index": 0,
            },
        }
        sym, sec, idx = resolve_authoritative_chord_selection(session, section_map)
        self.assertEqual(sym, "Bb")
        self.assertEqual(sec, "Verse")
        self.assertEqual(idx, 1)

    def test_mission_projection_does_not_overwrite_bb_with_index_g(self) -> None:
        from mission_projection_state import resolve_mission_projection_state

        section_map = [("Verse", ["G", "Bb", "Cm", "F"])]
        session = {
            "display_key": "Eb",
            "concert_key": "Eb",
            "ii_selected_chord": "G",
            "ii_selected_section": "Verse",
            "ii_selected_chord_index": 0,
            "_mission_chord_click_authority": {
                "chord": "Bb",
                "section": "Verse",
                "chord_index": 0,
            },
        }
        proj = resolve_mission_projection_state(
            session, section_map=section_map, fallback_key="Eb"
        )
        self.assertEqual(proj.concert_chord, "Bb")
        self.assertEqual(session.get("ii_selected_chord"), "Bb")
        self.assertEqual(int(session.get("ii_selected_chord_index") or -1), 1)


class TestClickSurvivesStaleChordOptions(unittest.TestCase):
    def test_click_gbm_not_rewritten_to_abm_after_pk(self) -> None:
        """After Practice Key transpose, stale Eb options must not beat a Gbm click."""
        from creative_mission_config_persistence import (
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY,
            SAVE_REASON_MISSION_TARGET,
            reconcile_mission_target_identity,
        )
        from creative_workspace_state_persistence import (
            CREATIVE_WORKSPACE_STATE_KEY,
            default_creative_workspace_state,
        )

        live_map = [("Verse 1", ["Dbm", "Gbm", "A", "B"])]
        session = {
            CREATIVE_WORKSPACE_STATE_KEY: {
                **default_creative_workspace_state(),
                "ii_selected_chord": "Abm",
                "ii_selected_section": "Verse 1",
                "ii_selected_chord_index": 1,
                "ii_selected_chord_label": "Verse 1 · Abm",
                "improv_mission_chord_options": ["Ebm", "Abm", "B", "Db"] * 4,
            },
            IMPROV_MISSION_SECTION_MAP_SESSION_KEY: live_map,
            "improv_mission_chord_options": ["Ebm", "Abm", "B", "Db"] * 4,
            "ii_selected_chord": "Abm",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 1,
            "ii_selected_chord_label": "Verse 1 · Abm",
        }
        values = {
            "ii_selected_chord": "Gbm",
            "ii_selected_section": "Verse 1",
            "ii_selected_chord_index": 1,
            "ii_selected_chord_label": "Verse 1 · Gbm",
            "improv_mission_chord_options": ["Ebm", "Abm", "B", "Db"] * 4,
        }
        out = reconcile_mission_target_identity(
            session,
            values,
            save_reason=SAVE_REASON_MISSION_TARGET,
            function="test_click_gbm",
        )
        self.assertEqual(out.get("ii_selected_chord"), "Gbm")
        self.assertEqual(out.get("ii_selected_chord_index"), 1)
        self.assertEqual(out.get("improv_mission_chord_options")[:4], ["Dbm", "Gbm", "A", "B"])


class TestMotifOwnerMatchesSelection(unittest.TestCase):
    def test_stale_motif_chord_g_blocked_when_selected_bb(self) -> None:
        from creative_mission_artifact_persistence import project_mission_artifacts_from_canonical
        from creative_workspace_state_persistence import (
            CREATIVE_WORKSPACE_STATE_KEY,
            default_creative_workspace_state,
        )

        ws = default_creative_workspace_state()
        arts = ws.setdefault("mission_artifacts", {})
        arts["improv_motif"] = {
            "chord": "G",
            "notes": ["G", "Bb", "C", "D"],
            "display": "G – Bb – C – D",
        }
        session = {
            CREATIVE_WORKSPACE_STATE_KEY: ws,
            "ii_selected_chord": "Bb",
        }
        project_mission_artifacts_from_canonical(session, overwrite=False)
        # Must not resurrect Motif-on-G while Bb is selected.
        self.assertNotIn("improv_motif", session)


if __name__ == "__main__":
    unittest.main()
