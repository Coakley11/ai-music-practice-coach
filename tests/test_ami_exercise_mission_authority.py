"""AMI exercises: a Mission wins key and chord only while it is *actively* authoritative for the request."""

from __future__ import annotations

import unittest

from tests.test_ami_exercise_bridge import MISSION_SESSION, exercise_of, submit

MISSION = "Improvise using only chord tones"

# The Creative page's default state: the Missions tab value is present and the first chord is
# auto-selected, but the user has not engaged a Mission.
DEFAULT_TAB = {
    "studio_page": "creative",
    "improv_intelligence_tab": "Missions",
    "improv_active_mission": MISSION,
    "ii_selected_chord": "Em7",
    "ii_selected_section": "Verse 1",
    "improv_mission_concert_key": "Bm",
}
CHART = {
    "chart_sections": {"Verse 1": ["Am7", "D7", "Gmaj7"]},
    "chart_sections_key": "Am",
    "chart_sections_in_practice_key": True,
    "practice_focus_section": "Verse 1",
}


def ctx_of(resp):
    return exercise_of(resp)["context"]


class TestMissionAuthority(unittest.TestCase):
    def test_missions_as_the_default_tab_is_not_mission_authority(self) -> None:
        _r, resp, _s = submit("Give me a guide-tone pattern over E7", key="Am", extra_session=DEFAULT_TAB, ami=CHART)
        ctx = ctx_of(resp)
        self.assertFalse(ctx["mission_active"])
        self.assertIn("no Mission engaged", ctx["mission_authority"]["reason"])
        self.assertEqual(ctx["key_source"], "practice_chart_key")
        self.assertEqual(ctx["concert_key"], "Am")                      # not the leftover Mission key Bm
        self.assertEqual(exercise_of(resp)["chord"], "E7")              # the explicit chord
        self.assertEqual(exercise_of(resp)["provenance"]["chord_source"], "explicit_request")
        self.assertNotIn("Mission Practice Key", resp.direct_answer)
        self.assertIn("your Practice key", resp.direct_answer)

    def test_a_stale_mission_chord_never_overrides_the_chart_chord(self) -> None:
        _r, resp, _s = submit("Give me a guide-tone pattern.", key="Am", extra_session=DEFAULT_TAB, ami=CHART)
        ex = exercise_of(resp)
        self.assertEqual(ex["chord"], "Am7")                            # first chord of the active chart section
        self.assertEqual(ex["context"]["chord_source"], "chart_active_section_first_chord")
        self.assertNotIn("Mission", resp.direct_answer.split("**Collection:**")[0])

    def test_without_a_chart_the_tonic_chord_is_used_not_the_stale_mission_chord(self) -> None:
        _r, resp, _s = submit("Give me a chord-tone exercise.", key="Am", extra_session=DEFAULT_TAB)
        ex = exercise_of(resp)
        self.assertEqual(ex["chord"], "Am7")
        self.assertEqual(ex["context"]["chord_source"], "tonic_of_key")

    def test_a_seeded_chord_click_and_snapshot_are_not_engagement(self) -> None:
        # The Creative page writes these itself, with a default chord, when the Missions tab is shown.
        seeded = dict(
            DEFAULT_TAB,
            _mission_chord_click_authority={"chord": "Em7", "section": "Verse 1", "chord_index": 7, "mission_id": MISSION},
            _mission_chord_snapshot={"concert_chord": "Em7", "mission_id": MISSION, "concert_practice_key": "Bm"},
        )
        _r, resp, _s = submit("Give me a guide-tone pattern", key="Am", extra_session=seeded, ami=CHART)
        ctx = ctx_of(resp)
        self.assertFalse(ctx["mission_active"])
        self.assertEqual((ctx["concert_key"], ctx["key_source"]), ("Am", "practice_chart_key"))
        self.assertEqual(exercise_of(resp)["chord"], "Am7")
        self.assertNotIn("Mission", resp.direct_answer.split("**Collection:**")[0])

    def test_a_generated_example_on_the_missions_tab_gives_mission_key_and_chord(self) -> None:
        ami = {"display_key": "Am", **CHART}
        _r, resp, _s = submit("Give me a guide-tone pattern", key="Dm", extra_session=MISSION_SESSION, ami=ami)
        ctx = ctx_of(resp)
        self.assertTrue(ctx["mission_active"])
        self.assertEqual(ctx["mission_authority"]["surface"], "creative_missions_tab")
        self.assertEqual((ctx["concert_key"], ctx["key_source"]), ("Dm", "mission_practice_key"))
        self.assertEqual((exercise_of(resp)["chord"], ctx["chord_source"]), ("Dm7", "mission_selected_chord"))
        self.assertIn("your Mission Practice Key", resp.direct_answer)
        self.assertIn("your selected Mission chord", resp.direct_answer)

    def test_a_generated_mission_example_is_mission_authority(self) -> None:
        extra = dict(DEFAULT_TAB, improv_mission_example={"mission": MISSION, "chord": "Em7"})
        _r, resp, _s = submit("Give me a guide-tone pattern", key="Bm", extra_session=extra)
        ctx = ctx_of(resp)
        self.assertTrue(ctx["mission_active"])
        self.assertEqual(ctx["mission_authority"]["evidence"], ["generated_example"])
        self.assertEqual(exercise_of(resp)["chord"], "Em7")
        self.assertEqual(ctx["chord_source"], "mission_selected_chord")

    def test_asking_about_this_mission_on_the_missions_tab_counts(self) -> None:
        _r, resp, _s = submit("Give me a guide-tone pattern for this Mission", key="Bm", extra_session=DEFAULT_TAB)
        ctx = ctx_of(resp)
        self.assertTrue(ctx["mission_active"])
        self.assertIn("request_mentions_mission", ctx["mission_authority"]["evidence"])

    def test_leaving_the_missions_surface_ends_mission_authority(self) -> None:
        for leave in (
            {"studio_page": "practice"},
            {"studio_page": "creative", "improv_intelligence_tab": "Harmony Map"},
            {"studio_page": "songs"},
        ):
            extra = {**MISSION_SESSION, "improv_mission_concert_key": "Dm", **leave}   # click and keys remain in session
            _r, resp, _s = submit("Give me a guide-tone pattern", key="Am", extra_session=extra, ami=CHART)
            ctx = ctx_of(resp)
            self.assertFalse(ctx["mission_active"], leave)
            self.assertEqual((ctx["concert_key"], ctx["key_source"]), ("Am", "practice_chart_key"), leave)
            self.assertEqual(exercise_of(resp)["chord"], "Am7", leave)
            self.assertEqual(ctx["mission_authority"]["reason"], "not on a Mission-owned surface", leave)

    def test_restored_stale_mission_state_without_a_mission_surface(self) -> None:
        stale = {
            "studio_page": "practice",
            "improv_active_mission": MISSION,
            "ii_selected_chord": "Dm7",
            "improv_mission_concert_key": "Dm",
            "improv_mission_example": {"mission": MISSION, "chord": "Dm7"},
            "_mission_chord_snapshot": {"concert_chord": "Dm7", "mission_id": MISSION},
            "_mission_chord_click_authority": {"chord": "Dm7", "mission_id": MISSION},
        }
        _r, resp, session = submit("Give me a chord-tone exercise.", key="Am", extra_session=stale, ami=CHART)
        ctx = ctx_of(resp)
        self.assertFalse(ctx["mission_active"])
        self.assertEqual(ctx["concert_key"], "Am")
        self.assertEqual(exercise_of(resp)["chord"], "Am7")
        for k in ("improv_mission_concert_key", "ii_selected_chord", "improv_mission_example", "_mission_chord_snapshot"):
            self.assertEqual(session[k], stale[k], k)                   # nothing was written back

    def test_mission_backing_page_with_live_mission_ownership_counts(self) -> None:
        from mission_owner_contract import BACKING_HANDOFF_SOURCE_KEY

        extra = {"studio_page": "backing", BACKING_HANDOFF_SOURCE_KEY: "mission", "ii_selected_chord": "Dm7",
                 "improv_active_mission": MISSION}
        _r, resp, _s = submit("Give me a guide-tone pattern", key="Dm", extra_session=extra)
        ctx = ctx_of(resp)
        self.assertTrue(ctx["mission_active"])
        self.assertEqual(ctx["mission_authority"]["surface"], "mission_backing")

    def test_an_explicit_key_still_beats_an_active_mission(self) -> None:
        _r, resp, _s = submit("Give me a D minor pentatonic line", key="Am", extra_session=MISSION_SESSION)
        ctx = ctx_of(resp)
        self.assertTrue(ctx["mission_active"])
        self.assertEqual((ctx["concert_key"], ctx["key_source"]), ("Dm", "explicit_request"))
        self.assertIn("mission_practice_key", ctx["key_candidates"])


if __name__ == "__main__":
    unittest.main()
