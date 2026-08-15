"""Workflow key/progression ownership and mission notation payload tests."""

from __future__ import annotations

import unittest
from typing import Any

from backing_context import build_entry_jam_context, build_song_improv_context, set_backing_context
from backing_nav_actions import build_backing_nav_actions
from backing_source_navigation import resolve_entry_jam_entry_mode
from creative_key_sync import retranspose_generated_sections
from harmonic_spelling import apply_motif_chord_spelling
from improvisation_missions import generate_mission_example, rebuild_mission_outputs, sync_motif_midi
from improvisation_intelligence import ImprovSessionContext
from improvisation_motif import generate_motif_for_chord
from workflow_musical_authority import (
    restore_workflow_snapshot,
    save_workflow_snapshot,
    switch_workflow_owner,
    sync_song_improv_sections_to_practice_key,
)


class TestMissionNotationPayload(unittest.TestCase):
    def test_abc_contains_sharp_spellings_for_b_major(self) -> None:
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
        abc = str(ex.abc or "")
        self.assertIn("^D", abc)
        self.assertNotIn("_e", abc.lower())
        self.assertNotIn("_g", abc.lower())
        notes = " ".join(ex.motif.get("notes") or [])
        self.assertIn("D#", notes)
        self.assertNotIn("Eb", notes)

    def test_apply_motif_spelling_from_midi(self) -> None:
        motif = generate_motif_for_chord("B", key_center="Ebm", level="Beginner")
        motif = sync_motif_midi(motif)
        apply_motif_chord_spelling(motif, "B", song_display_key="Ebm")
        self.assertIn("D#", " ".join(motif.get("notes") or []))
        self.assertNotIn("Eb", motif.get("display") or "")


class TestGeneratorIsolation(unittest.TestCase):
    def test_no_jewish_ballad_on_bossa_generator(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Bossa Nova",
            "improv_jam_key": "C",
            "improv_jam_bpm": 100,
            "improv_style_meta": {"style": "Jewish ballad", "groove": "Jewish ballad"},
            "song": "Hevenu Shalom Aleichem",
            "improv_jam_session": {"sections": {"A": ["Dm7", "G7", "Cmaj7"]}},
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(str(ctx.style), "Bossa Nova")
        self.assertNotIn("Hevenu", str(ctx.song_title))
        self.assertIn("A", list(ctx.section_labels or []))

    def test_style_jam_not_classified_as_generator(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_jam_session": {"sections": {"B": ["C", "F", "G"]}},
            "improv_generated_sections": {"A": ["C", "Am", "F", "G"]},
        }
        self.assertEqual(resolve_entry_jam_entry_mode(session), "Style Jam Mode")

    def test_generator_nav_has_catalog_return_not_use(self) -> None:
        session = {
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_style": "Rock",
            "improv_jam_key": "C",
            "improv_jam_session": {"sections": {"A": ["C", "G", "Am", "F"]}},
            "active_catalog_pick_key": "catalog::x",
        }
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        actions, _ = build_backing_nav_actions(session)
        labels = [a.label for a in actions]
        self.assertTrue(any("Return to Catalog Song Backing" in l for l in labels))
        self.assertFalse(any(l.lower().startswith("use catalog song backing") for l in labels))


class TestWorkflowKeyIsolation(unittest.TestCase):
    def test_style_jam_d_major_restored_after_song_switch(self) -> None:
        session: dict[str, Any] = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "D",
            "improv_style": "Disco",
            "improv_generated_sections": {"A": ["D", "G", "A"]},
            "display_key": "D",
            "concert_key": "D",
        }
        save_workflow_snapshot(session, "style_jam")
        session["display_key"] = "Ebm"
        session["concert_key"] = "Ebm"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        save_workflow_snapshot(session, "song_based_improvisation")
        switch_workflow_owner(session, "style_jam")
        self.assertEqual(str(session.get("improv_style_key")), "D")
        self.assertEqual(str(session.get("display_key")), "Ebm")

    def test_jam_key_change_transposes_sections(self) -> None:
        sections = {"A": ["C", "F", "G"]}
        out = retranspose_generated_sections(sections, from_key="C", to_key="D")
        self.assertNotEqual(out["A"], sections["A"])


if __name__ == "__main__":
    unittest.main()
