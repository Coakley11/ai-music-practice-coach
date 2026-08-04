"""Backing nav dedupe, generator routing, B-major mission spelling regression tests."""

from __future__ import annotations

import unittest
from typing import Any

from backing_context import BackingContext, build_entry_jam_context, open_backing_from_creative, set_backing_context
from backing_nav_actions import build_backing_nav_actions, catalog_return_action_visible
from backing_source_navigation import _creative_handoff_entry_mode
from backing_workflow_context import get_backing_workflow_envelope, sync_backing_workflow_envelope
from generated_jam_key_context import (
    activate_generated_jam_key_ownership,
    deactivate_generated_jam_key_ownership,
)
from harmonic_spelling import assert_mission_spelling_consistency, harmonic_reference_for_chord
from improvisation_harmony import analyze_chord_for_harmony_map
from improvisation_intelligence import ImprovSessionContext, chord_coach_insight
from improvisation_missions import generate_mission_example
from improvisation_motif import chord_tone_names
from mission_pitch_spelling import coaching_reference_for_mission_chord


class TestBackingNavDedupe(unittest.TestCase):
    def test_mission_jam_has_creative_and_mission_not_duplicate_catalog_use(self) -> None:
        session: dict[str, Any] = {
            "improv_intelligence_tab": "Missions",
        }
        ctx = BackingContext(
            source="mission",
            source_label="Mission",
            song_title="Test Song",
            entry_mode="Missions",
            mode_label="Mission Jam",
            active_song_id="catalog::test",
            bound_pick_key="catalog::test",
            mission_id="m1",
            style="Pop groove",
            groove="Pop groove",
            bpm=100,
            key="Ebm",
            display_key="Ebm",
            concert_key="Ebm",
            progression=["B", "Ebm"],
            sections={"Verse": ["B", "Ebm"]},
            section_labels=["Verse"],
            scope="Mission chord",
        )
        set_backing_context(session, ctx)
        sync_backing_workflow_envelope(session, ctx)
        actions, removed = build_backing_nav_actions(session)
        labels = [a.label for a in actions]
        self.assertIn("Return to Creative Page", " ".join(labels))
        self.assertIn("Return to Mission", labels)
        self.assertTrue(catalog_return_action_visible(session))
        self.assertFalse(any("Use catalog song backing" in a.label for a in actions))

    def test_generator_catalog_return_without_use_button(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "improv_jam_style": "Bossa",
            "improv_jam_session": {"sections": {"A": ["C", "F", "G"]}},
        }
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_backing_workflow_envelope(session, ctx)
        actions, _ = build_backing_nav_actions(session)
        self.assertEqual(len([a for a in actions if a.purpose == "catalog_backing"]), 1)
        self.assertFalse(any("Use catalog song backing" in a.label.lower() for a in actions))


class TestGeneratorOpenBackingRoute(unittest.TestCase):
    def test_handoff_entry_mode_prefers_live_widget(self) -> None:
        session = {
            "improv_entry_mode": "Jam Session Generator",
            "creative_session": {"tool_type": "song_based_improvisation", "entry_mode": "Song-Based Improvisation"},
        }
        self.assertEqual(_creative_handoff_entry_mode(session), "Jam Session Generator")

    def test_open_backing_from_creative_entry_jam_workflow(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "improv_jam_style": "Rock",
            "improv_jam_bpm": 110,
            "improv_generated_sections": {"Jam": ["C", "G", "Am", "F"]},
        }
        open_backing_from_creative(session, source="entry_jam")
        env = get_backing_workflow_envelope(session) or {}
        self.assertEqual(env.get("workflow_type"), "jam_session_generator")
        self.assertEqual(env.get("source_type"), "generated")


class TestGeneratedJamKeyRestore(unittest.TestCase):
    def test_snapshot_and_restore_song_key(self) -> None:
        session = {
            "display_key": "Ebm",
            "concert_key": "Ebm",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "studio_page": "creative",
        }
        activate_generated_jam_key_ownership(session)
        self.assertIn("_song_practice_key_snapshot", session)
        deactivate_generated_jam_key_ownership(session)
        self.assertEqual(session.get("display_key"), "Ebm")
        self.assertEqual(session.get("concert_key"), "Ebm")


class TestBMajorMissionSpelling(unittest.TestCase):
    def test_coaching_reference_is_b_not_ebm(self) -> None:
        ref = coaching_reference_for_mission_chord("B", song_display_key="Ebm")
        self.assertEqual(ref, "B")
        self.assertEqual(harmonic_reference_for_chord("B", song_display_key="Ebm"), "B")

    def test_stable_tones_sharps_not_flats(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Hevenu",
            artist="",
            key_center="Ebm",
            display_key="Ebm",
            instrument="Piano",
            level="Intermediate",
            focus="Harmony",
            sections={"Verse": ["B"]},
        )
        guide = analyze_chord_for_harmony_map("B", improv_ctx=ctx, section="Verse")
        self.assertEqual(guide.stable_tones[:3], ["B", "D#", "F#"])
        joined = " ".join(guide.stable_tones + [c.note for c in guide.color_tones])
        self.assertNotIn("Eb", joined)
        self.assertNotIn("Gb", joined)

    def test_chord_coach_insight_tones(self) -> None:
        insight = chord_coach_insight("B", key_center="Ebm")
        self.assertEqual(insight.chord_tones[:3], ["B", "D#", "F#"])

    def test_mission_example_outputs_use_sharps(self) -> None:
        ctx = ImprovSessionContext(
            song_title="Hevenu",
            artist="",
            key_center="Ebm",
            display_key="Ebm",
            instrument="Piano",
            level="Beginner",
            focus="Chord tones",
            sections={"Verse": ["B"]},
        )
        ex = generate_mission_example(
            "Outline chord tones",
            improv_ctx=ctx,
            chord="B",
            section="Verse",
            level="Beginner",
            instrument="Piano",
            focus="Chord tones",
            bpm=90,
        )
        display = str(ex.motif.get("display") or "")
        self.assertNotIn("Eb", display)
        self.assertNotIn("Gb", display)
        diag = assert_mission_spelling_consistency(
            {},
            chord_symbol="B",
            stable_tones=ex.insight.chord_tones[:3],
            coaching_tones=ex.insight.chord_tones,
            motif_notes=list(ex.motif.get("notes") or []),
            notation_text=str(ex.abc or ""),
        )
        self.assertTrue(diag.get("consistent"), diag.get("violations"))

    def test_bb7_stays_flat(self) -> None:
        tones = chord_tone_names("Bb7", reference_key=harmonic_reference_for_chord("Bb7", song_display_key="Ebm"))
        self.assertIn("Bb", tones[0])
        self.assertIn("Ab", " ".join(tones))
        self.assertIn("Bb", chord_coach_insight("Bb7", key_center="Ebm").chord_tones[0])


if __name__ == "__main__":
    unittest.main()
