"""Unit tests for Composition Studio document and snapshot."""

import unittest

from composition_document import (
    advance_workflow,
    apply_structure_template,
    bootstrap_from_seed,
    bootstrap_from_vision,
    break_chord_link,
    chords_for_playback,
    duplicate_section,
    ensure_workflow,
    get_workflow_phase,
    next_workflow_phase,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    suggest_musical_defaults,
    touch_composition,
    STRUCTURE_TEMPLATES,
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

    def test_chords_for_playback_resolves_linked_harmony(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        verse1 = sections[0]
        verse1["chords"] = parse_chord_paste("C G Am F")
        verse2 = next(s for s in sections if str(s.get("label_variant") or "").startswith("Verse 2"))
        link = verse2.setdefault("chord_link", {"source_section_id": None, "linked": False})
        link["source_section_id"] = str(verse1["id"])
        link["linked"] = True
        verse2["chords"] = []
        v2_chords = chords_for_playback(doc, scope="section", section_id=str(verse2["id"]))
        self.assertEqual(v2_chords[:2], ["C", "G"])

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

    def test_apply_structure_template_pop(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="An upbeat pop song.")
        created = apply_structure_template(doc, "pop")
        self.assertEqual(len(created), len(STRUCTURE_TEMPLATES["pop"]))
        sections = ordered_sections(doc)
        self.assertEqual(sections[1].get("label_variant"), "Verse 1")
        verse2 = next(s for s in sections if s.get("label_variant") == "Verse 2")
        link = verse2.get("chord_link") or {}
        self.assertTrue(link.get("linked"))

    def test_duplicate_section_links_verse(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse1 = ordered_sections(doc)[0]
        verse1["chords"] = parse_chord_paste("G Am C D")
        clone = duplicate_section(doc, str(verse1["id"]))
        self.assertIsNotNone(clone)
        assert clone is not None
        self.assertTrue((clone.get("chord_link") or {}).get("linked"))
        self.assertEqual(parse_chord_paste("G Am C D")[0]["chord"], clone["chords"][0]["chord"])

    def test_break_chord_link(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse2 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 2")
        self.assertTrue(break_chord_link(doc, str(verse2["id"])))
        self.assertFalse((verse2.get("chord_link") or {}).get("linked"))


if __name__ == "__main__":
    unittest.main()
