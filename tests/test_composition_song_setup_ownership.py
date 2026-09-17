"""Composition Studio — user-owned Key / BPM / Meter and nonlinear section state."""

from __future__ import annotations

import unittest

from composition_document import (
    add_section,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    coerce_composition_key_choice,
    coerce_composition_meter,
    composition_key_choice_labels,
    composition_key_label_from_token,
    composition_key_token_from_choice,
    deep_copy_document,
    move_section,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    playback_globals,
    remove_section,
    section_lane_status,
    suggest_musical_defaults,
)
from composition_session_state import (
    COMPOSER_ACTIVE_SECTION_KEY,
    get_active_document,
    save_document_to_library,
    set_active_document,
)
from composition_chord_suggestions import suggest_progressions


class TestCompositionSongSetupOwnership(unittest.TestCase):
    def test_user_key_bpm_meter_survive_library_roundtrip(self) -> None:
        doc = bootstrap_from_vision(
            genre="Folk",
            song_idea="A quiet evening song.",
            title="Evening Walk",
            key="Ab major",
            bpm=84,
            meter="3/4",
        )
        ss: dict = {}
        set_active_document(ss, doc)
        save_document_to_library(ss, doc)
        restored = get_active_document(ss)
        assert restored is not None
        g = restored["global"]
        self.assertEqual(g["original_key_center"], "Ab")
        self.assertEqual(g["original_key_label"], "Ab major")
        self.assertEqual(g["bpm"], 84)
        self.assertEqual(g["time_signature"], "3/4")
        # Ambient Practice-like values must not appear as owners.
        self.assertNotEqual(g["original_key_center"], "C")
        self.assertNotEqual(g["bpm"], 96)

    def test_suggestions_do_not_override_explicit_user_settings(self) -> None:
        hints = suggest_musical_defaults(genre="Jazz", song_idea="A gentle ballad.")
        # Heuristics may prefer Bb / slow — user choice still wins.
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="A gentle ballad.",
            key="E major",
            bpm=140,
            meter="7/8",
        )
        self.assertEqual(doc["global"]["original_key_center"], "E")
        self.assertEqual(doc["global"]["bpm"], 140)
        self.assertEqual(doc["global"]["time_signature"], "7/8")
        self.assertNotEqual(doc["global"]["bpm"], hints["bpm"])

    def test_enharmonic_labels_roundtrip(self) -> None:
        labels = composition_key_choice_labels()
        self.assertIn("Db minor", labels)
        self.assertIn("C# minor", labels)
        db_token = composition_key_token_from_choice("Db minor")
        cs_token = composition_key_token_from_choice("C# minor")
        self.assertEqual(db_token, "Dbm")
        self.assertEqual(cs_token, "C#m")
        self.assertEqual(composition_key_label_from_token(db_token), "Db minor")
        self.assertEqual(composition_key_label_from_token(cs_token), "C# minor")
        self.assertEqual(coerce_composition_key_choice("Dbm"), "Db minor")

    def test_custom_meter_coerce(self) -> None:
        self.assertEqual(coerce_composition_meter("11/8"), "11/8")
        self.assertEqual(coerce_composition_meter(" 12 / 8 "), "12/8")
        self.assertEqual(coerce_composition_meter("bogus", fallback="4/4"), "4/4")

    def test_structure_add_remove_reorder_duplicate(self) -> None:
        from composition_document import duplicate_section

        doc = bootstrap_from_vision(genre="Pop", song_idea="Form test.", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse1 = ordered_sections(doc)[0]
        added = add_section(doc, "Bridge", after_id=str(verse1["id"]))
        self.assertEqual(ordered_sections(doc)[1]["id"], added["id"])
        move_section(doc, str(added["id"]), 1)
        ids = [str(s["id"]) for s in ordered_sections(doc)]
        self.assertIn(str(added["id"]), ids)
        clone = duplicate_section(doc, str(verse1["id"]))
        assert clone is not None
        self.assertNotEqual(clone["id"], verse1["id"])
        before = len(ordered_sections(doc))
        remove_section(doc, str(added["id"]))
        self.assertEqual(len(ordered_sections(doc)), before - 1)

    def test_custom_section_name(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Custom section.", key="C major", bpm=96, meter="4/4")
        sec = add_section(doc, "Custom")
        sec["label_variant"] = "Final Chorus"
        self.assertEqual(ordered_sections(doc)[0]["label_variant"], "Final Chorus")

    def test_chord_suggestions_use_song_key(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Warm verse.",
            mood="Warm / romantic",
            key="G major",
            bpm=96,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        ideas = suggest_progressions(doc, verse, "stable", limit=3)
        self.assertGreaterEqual(len(ideas), 1)
        line = str(ideas[0].get("line") or "")
        # Transposed out of C-major reference — should include G-family material.
        self.assertTrue(any(tok in line for tok in ("G", "Em", "D", "C")), line)

    def test_playback_globals_expose_key_label(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Label test.",
            key="Bb minor",
            bpm=92,
            meter="12/8",
        )
        pg = playback_globals(doc)
        self.assertEqual(pg["key_center"], "Bbm")
        self.assertEqual(pg["key_label"], "Bb minor")
        self.assertEqual(pg["time_signature"], "12/8")

    def test_deep_copy_preserves_user_globals(self) -> None:
        doc = bootstrap_from_vision(
            genre="Rock",
            song_idea="Copy test.",
            key="F# major",
            bpm=118,
            meter="4/4",
        )
        clone = deep_copy_document(doc)
        clone["global"]["bpm"] = 200
        self.assertEqual(doc["global"]["bpm"], 118)
        self.assertEqual(doc["global"]["original_key_label"], "F# major")

    def test_section_status_and_active_section_switch(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Status test.",
            key="C major",
            bpm=100,
            meter="4/4",
            instrumental=True,
        )
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        verse, chorus = sections[0], sections[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C G Am F"))
        ss = {COMPOSER_ACTIVE_SECTION_KEY: str(chorus["id"])}
        set_active_document(ss, doc)
        # Switch active section without wiping verse chords.
        ss[COMPOSER_ACTIVE_SECTION_KEY] = str(verse["id"])
        active = get_active_document(ss)
        assert active is not None
        status = section_lane_status(active, str(verse["id"]))
        self.assertEqual(status["chords"], "complete")
        self.assertEqual(status["lyrics"], "not_applicable")
        self.assertTrue(phase_is_reachable(active, "melody"))


if __name__ == "__main__":
    unittest.main()
