"""Failing reproduction — cross-workflow Creative artifact corruption (Phase 1).

These tests encode the target owner/artifact contract. They MUST fail on safety branch
base 5049c17 until Phase 2 snapshot correction lands.

Expected failure themes (5049c17):
- resolve_entry_jam_entry_mode forces Jam Session Generator when stale improv_jam_session exists
  and entry radio still reads Song-Based (continuous session lag)
- build_entry_jam_context binds catalog pick + global display_key C over Style E
- mood defaults to Mellow; stale Eb generator progression on Style Jam backing
- validate_workflow_consistency: STYLE_JAM_OPENED_AS_GENERATOR, GENERATED_JAM_CATALOG_STYLE_LEAK
- Mission/Harmony navigation drops saved Eb-minor practice key on Song-Based return
"""

from __future__ import annotations

import unittest
from typing import Any

from creative_lifecycle_harness_support import (
    HEVENU_ORIGINAL_MODE,
    HEVENU_ORIGINAL_TONIC,
    HEVENU_PRACTICE_MODE,
    HEVENU_PRACTICE_TONIC,
    OwnerIntegrityExpectation,
    analyze_backing_context_integrity,
    apply_hevenu_practice_eb_minor,
    assert_owner_integrity,
    harmony_map_focus_chord,
    mission_select_single_chord,
    open_backing_entry_jam_production,
    restore_song_based_tab,
    seed_hevenu_catalog_session,
    seed_stale_generator_artifact,
    simulate_style_jam_backing_open_with_entry_widget_lag,
    song_based_progression_chord_count,
    sync_creative_before_open,
)

LIFECYCLE_HARNESS = "streamlit_creative_lifecycle_harness.py"


class _SessionAdapter:
    """AppTest session_state wrapper — matches full production harness tests."""

    def __init__(self, ss: Any) -> None:
        self._ss = ss

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._ss[key]
        except (KeyError, TypeError, AttributeError):
            return default

    def __getitem__(self, key: str) -> Any:
        return self._ss[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._ss[key] = value

    def __contains__(self, key: object) -> bool:
        try:
            self._ss[str(key)]  # type: ignore[index]
            return True
        except (KeyError, TypeError, AttributeError):
            return False


def _adapt(at: Any) -> _SessionAdapter:
    return _SessionAdapter(at.session_state)


def _session(**extra: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "_suite_active_workspace_id": "lifecycle-harness",
        "_suite_account_id": "lifecycle-harness-acct",
        "_music_restore_phase_complete": True,
        "_music_startup_restore_finalized": True,
        "studio_page": "creative",
    }
    s.update(extra)
    return s


class TestLifecycleBackingHybridRepro(unittest.TestCase):
    """Direct production-path repro (no AppTest) — documents contradictory field sources."""

    def test_style_jam_open_backing_must_be_coherent_style_jam_artifact(self) -> None:
        """Steps 12–17: Style Jam UI + stale Generator blob + sidebar C + entry radio lag."""
        session = _session()
        seed_hevenu_catalog_session(session)
        apply_hevenu_practice_eb_minor(session)
        seed_stale_generator_artifact(session)
        simulate_style_jam_backing_open_with_entry_widget_lag(session)
        sync_creative_before_open(session)
        ctx = open_backing_entry_jam_production(session)
        assert_owner_integrity(
            session,
            ctx,
            expect=OwnerIntegrityExpectation(
                workflow_owner="style_jam",
                practice_tonic="E",
                practice_mode="major",
                mood="Light",
                style="Jazz Swing",
                min_progression_chords=4,
                forbid_stale_generator_sections=True,
            ),
        )

    def test_generator_open_backing_must_not_leak_hevenu_bound_pick(self) -> None:
        session = _session()
        seed_hevenu_catalog_session(session)
        seed_stale_generator_artifact(session)
        session["improv_entry_mode"] = "Jam Session Generator"
        session["improv_jam_key"] = "G"
        session["improv_jam_mood"] = "Bright"
        session["improv_jam_style"] = "Latin Fusion"
        sync_creative_before_open(session)
        ctx = open_backing_entry_jam_production(session)
        assert_owner_integrity(
            session,
            ctx,
            expect=OwnerIntegrityExpectation(
                workflow_owner="jam_session_generator",
                practice_tonic="G",
                mood="Bright",
                style="Latin Fusion",
                forbid_catalog_tokens=("hevenu",),
            ),
        )

    def test_song_based_full_progression_survives_mission_and_harmony(self) -> None:
        session = _session()
        seed_hevenu_catalog_session(session)
        apply_hevenu_practice_eb_minor(session)
        before = song_based_progression_chord_count(session)
        self.assertGreaterEqual(before, 4, "Hevenu full song baseline")
        mission_select_single_chord(session, chord="Dm", section="Verse")
        restore_song_based_tab(session)
        after_mission = song_based_progression_chord_count(session)
        self.assertGreaterEqual(
            after_mission,
            4,
            "Mission single-chord focus must not replace Song-Based full progression",
        )
        harmony_map_focus_chord(session, chord="Gm", section="Verse")
        restore_song_based_tab(session)
        after_harmony = song_based_progression_chord_count(session)
        self.assertGreaterEqual(after_harmony, 4)
        self.assertEqual(str(session.get("concert_key") or ""), "Ebm")
        self.assertEqual(str(session.get("display_key") or ""), "Ebm")

    def test_hevenu_original_key_metadata_unchanged_after_generated_collision(self) -> None:
        session = _session()
        seed_hevenu_catalog_session(session)
        apply_hevenu_practice_eb_minor(session)
        seed_stale_generator_artifact(session)
        simulate_style_jam_backing_open_with_entry_widget_lag(session)
        open_backing_entry_jam_production(session)
        sel = session.get("selected_song") or {}
        self.assertEqual(str(sel.get("key") or ""), "Dm")
        self.assertEqual(str(session.get("original_key") or ""), "Dm")


class TestLifecycleContinuousSessionAppTest(unittest.TestCase):
    @unittest.skipUnless(
        __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
        "streamlit.testing.v1 unavailable",
    )
    def test_continuous_session_owner_integrity_contract(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(LIFECYCLE_HARNESS, default_timeout=180)
        at.run(timeout=240)

        btn_eb = at.button(key="lc_hevenu_eb")
        self.assertIsNotNone(btn_eb)
        btn_eb.click().run()
        at.run(timeout=120)

        btn_sbi = at.button(key="lc_sbi_mission_harmony")
        self.assertIsNotNone(btn_sbi)
        btn_sbi.click().run()
        at.run(timeout=120)

        at.radio(key="improv_entry_mode").set_value("Style Jam Mode").run()
        at.run(timeout=120)
        if "improv_style" in at.session_state:
            at.selectbox(key="improv_style").set_value("Jazz Swing")
        if "improv_mood" in at.session_state:
            at.selectbox(key="improv_mood").set_value("Light")
        if "improv_style_key" in at.session_state:
            at.selectbox(key="improv_style_key").set_value("E")
        at.run(timeout=120)

        gen = at.button(key="improv_gen_style")
        if gen is not None:
            gen.click().run()
            at.run(timeout=120)

        at.session_state["improv_entry_mode"] = "Song-Based Improvisation"
        at.session_state["display_key"] = "C"
        at.session_state["concert_key"] = "C"
        if "improv_generated_sections" in at.session_state:
            del at.session_state["improv_generated_sections"]

        open_btn = at.button(key="improv_to_backing_jam")
        self.assertIsNotNone(open_btn)
        open_btn.click().run()
        at.run(timeout=120)

        session = _adapt(at)
        from backing_context import get_backing_context

        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        assert_owner_integrity(
            session,
            ctx,
            expect=OwnerIntegrityExpectation(
                workflow_owner="style_jam",
                practice_tonic="E",
                mood="Light",
                forbid_stale_generator_sections=True,
                min_progression_chords=4,
            ),
        )


if __name__ == "__main__":
    unittest.main()
