"""Unit tests for Composition Studio document and snapshot."""

import unittest

from composition_document import (
    advance_workflow,
    apply_structure_template,
    bootstrap_from_seed,
    bootstrap_from_vision,
    break_chord_link,
    chords_for_playback,
    composition_key_choice_labels,
    composition_key_label_from_token,
    duplicate_section,
    ensure_workflow,
    get_workflow_phase,
    next_workflow_phase,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    section_has_melody,
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

    def test_bootstrap_from_vision_user_owned_key_bpm_meter(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="A warm romantic song.",
            key="Db minor",
            bpm=72,
            meter="6/8",
        )
        g = doc["global"]
        self.assertEqual(g["original_key_center"], "Dbm")
        self.assertEqual(g["original_key_label"], "Db minor")
        self.assertEqual(g["bpm"], 72)
        self.assertEqual(g["time_signature"], "6/8")
        # Must not silently rewrite Db minor → C# minor.
        self.assertNotEqual(g["original_key_center"], "C#m")
        self.assertEqual(composition_key_label_from_token(g["original_key_center"]), "Db minor")

    def test_bootstrap_preserves_cs_sharp_minor_distinct_from_db(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="Dark jazz tune.",
            key="C# minor",
            bpm=88,
            meter="5/4",
        )
        self.assertEqual(doc["global"]["original_key_center"], "C#m")
        self.assertEqual(doc["global"]["original_key_label"], "C# minor")
        self.assertEqual(doc["global"]["time_signature"], "5/4")

    def test_bootstrap_custom_meter(self) -> None:
        doc = bootstrap_from_vision(
            genre="Other",
            song_idea="Odd-meter sketch.",
            key="G major",
            bpm=110,
            meter="11/8",
        )
        self.assertEqual(doc["global"]["time_signature"], "11/8")
        self.assertEqual(doc["global"]["original_key_center"], "G")

    def test_phase_reachable_after_structure_exists_nonlinear(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test song.", key="G major", bpm=100, meter="4/4")
        advance_workflow(doc, from_phase="vision")
        self.assertFalse(phase_is_reachable(doc, "chords"))
        apply_structure_template(doc, "simple")
        self.assertTrue(phase_is_reachable(doc, "chords"))
        self.assertTrue(phase_is_reachable(doc, "melody"))
        self.assertTrue(phase_is_reachable(doc, "lyrics"))
        self.assertTrue(phase_is_reachable(doc, "review"))

    def test_nonlinear_section_state_survives(self) -> None:
        from composition_document import apply_section_chords, apply_melody_concept

        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Nonlinear workflow test.",
            key="G major",
            bpm=100,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        verse = sections[0]
        chorus = next(s for s in sections if str(s.get("label") or "") == "Chorus")
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("C G Am D"))
        apply_melody_concept(
            doc,
            str(verse["id"]),
            {
                "id": "test_concept",
                "name": "Rising open",
                "motif_hint": "Rise then settle",
                "contour": "up",
                "notes": "G A B D",
            },
        )
        # Switching "focus" must not erase the other section.
        self.assertEqual(chords_for_playback(doc, scope="section", section_id=str(verse["id"]))[:2], ["G", "D"])
        self.assertEqual(chords_for_playback(doc, scope="section", section_id=str(chorus["id"]))[:2], ["C", "G"])
        verse_reload = next(s for s in ordered_sections(doc) if s["id"] == verse["id"])
        self.assertTrue(section_has_melody(verse_reload))
        self.assertEqual(doc["global"]["original_key_center"], "G")
        self.assertEqual(doc["global"]["bpm"], 100)

    def test_section_lane_status_instrumental_lyrics_na(self) -> None:
        from composition_document import section_lane_status

        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Instrumental piece.",
            instrumental=True,
            key="A minor",
            bpm=90,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        sid = str(ordered_sections(doc)[0]["id"])
        status = section_lane_status(doc, sid)
        self.assertEqual(status["lyrics"], "not_applicable")
        self.assertEqual(status["chords"], "incomplete")

    def test_composition_key_labels_include_enharmonics(self) -> None:
        labels = composition_key_choice_labels()
        self.assertIn("Db minor", labels)
        self.assertIn("C# minor", labels)
        self.assertIn("Gb major", labels)
        self.assertIn("F# major", labels)

    def test_phase_is_reachable_backward_only(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test song.")
        advance_workflow(doc, from_phase="vision")
        self.assertTrue(phase_is_reachable(doc, "vision"))
        self.assertTrue(phase_is_reachable(doc, "structure"))
        # No sections yet — creative phases stay closed.
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
        clone = duplicate_section(doc, str(verse1["id"]), link_chords=True)
        self.assertIsNotNone(clone)
        assert clone is not None
        self.assertTrue((clone.get("chord_link") or {}).get("linked"))
        self.assertEqual(parse_chord_paste("G Am C D")[0]["chord"], clone["chords"][0]["chord"])

    def test_duplicate_section_default_is_independent(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse1 = ordered_sections(doc)[0]
        verse1["chords"] = parse_chord_paste("G Am C D")
        clone = duplicate_section(doc, str(verse1["id"]))
        self.assertIsNotNone(clone)
        assert clone is not None
        self.assertFalse((clone.get("chord_link") or {}).get("linked"))
        self.assertEqual(clone["chords"][0]["chord"], "G")
        self.assertNotEqual(clone["id"], verse1["id"])

    def test_break_chord_link(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse2 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 2")
        self.assertTrue(break_chord_link(doc, str(verse2["id"])))
        self.assertFalse((verse2.get("chord_link") or {}).get("linked"))


if __name__ == "__main__":
    unittest.main()
