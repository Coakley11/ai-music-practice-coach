"""Unit tests for Composition Studio document and snapshot."""

import unittest

from composition_document import (
    advance_workflow,
    bootstrap_from_seed,
    bootstrap_from_vision,
    chords_for_playback,
    ensure_workflow,
    get_workflow_phase,
    next_workflow_phase,
    parse_chord_paste,
    phase_is_reachable,
    suggest_musical_defaults,
    touch_composition,
)
from composition_snapshot import build_composition_snapshot, snapshot_invalidate_token


class TestCompositionDocument(unittest.TestCase):
    def test_bootstrap_from_chords_seed(self) -> None:
        doc = bootstrap_from_seed(seed_type="chords", seed_text="| G | Am | C |")
        self.assertEqual(doc["origin"]["seed_type"], "chords")
        chords = chords_for_playback(doc, scope="song")
        self.assertEqual(chords[:3], ["G", "Am", "C"])

    def test_bootstrap_style_intent_sets_style(self) -> None:
        doc = bootstrap_from_seed(seed_type="style_intent", seed_text="I want a jazz ballad")
        self.assertIn("Jazz", str(doc.get("metadata", {}).get("style", "")))

    def test_parse_chord_paste(self) -> None:
        entries = parse_chord_paste("G Am C D")
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["chord"], "G")

    def test_snapshot_updates_after_edit(self) -> None:
        doc = bootstrap_from_seed(seed_type="exploring", seed_text="")
        token_a = snapshot_invalidate_token(doc)
        sections = list((doc.get("form") or {}).get("section_order") or [])
        sec_id = sections[0]
        sec = doc["form"]["sections"][sec_id]
        sec["chords"] = parse_chord_paste("Em C G D")
        touch_composition(doc)
        token_b = snapshot_invalidate_token(doc)
        self.assertNotEqual(token_a, token_b)
        snap = build_composition_snapshot(doc, active_section_id=sec_id)
        self.assertTrue(snap.get("commitment", {}).get("has_chords"))
        self.assertEqual(snap["active_section"]["chord_symbols"][:2], ["Em", "C"])

    def test_bootstrap_from_vision_minimal(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="A melancholy ballad about distance.",
        )
        self.assertEqual(doc["origin"]["seed_type"], "vision")
        self.assertEqual(doc["metadata"]["style"], "Jazz")
        self.assertEqual(doc["metadata"]["description"], "A melancholy ballad about distance.")
        self.assertEqual(get_workflow_phase(doc), "vision")
        self.assertEqual(list((doc.get("form") or {}).get("section_order") or []), [])

    def test_bootstrap_from_vision_instrumental_skips_lyrics(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="An upbeat instrumental.", instrumental=True)
        self.assertTrue(ensure_workflow(doc).get("skip_lyrics"))
        self.assertEqual(next_workflow_phase(doc, "melody"), "review")

    def test_advance_workflow_marks_complete(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A hopeful pop song.")
        nxt = advance_workflow(doc, from_phase="vision")
        self.assertEqual(nxt, "structure")
        self.assertEqual(get_workflow_phase(doc), "structure")
        self.assertIn("vision", ensure_workflow(doc).get("completed_phases") or [])

    def test_phase_is_reachable_backward_only(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test song.")
        advance_workflow(doc, from_phase="vision")
        self.assertTrue(phase_is_reachable(doc, "vision"))
        self.assertTrue(phase_is_reachable(doc, "structure"))
        self.assertFalse(phase_is_reachable(doc, "chords"))

    def test_suggest_musical_defaults_ballad(self) -> None:
        hints = suggest_musical_defaults(genre="Pop", song_idea="A gentle ballad about loss.")
        self.assertLessEqual(hints["bpm"], 72)
        self.assertIn("Ballad", hints["energy"])


if __name__ == "__main__":
    unittest.main()
