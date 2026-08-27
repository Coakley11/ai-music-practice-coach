"""Composition Studio — Chords → Hear → Refine → Melody creative pass."""

from __future__ import annotations

import unittest

from composition_chord_refinements import CHORD_REFINEMENT_INTENTS, propose_chord_refinement
from composition_chord_suggestions import (
    guided_chord_vocabulary,
    progression_bar_count,
    suggest_progressions,
)
from composition_document import (
    apply_melody_concept,
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    break_chord_link,
    chords_for_playback,
    insert_section_chord,
    ordered_sections,
    parse_chord_paste,
    phase_is_reachable,
    remove_section_chord,
    replace_section_chord,
    section_has_melody,
    section_lane_status,
    section_melody_events,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_preview import generate_preview_wav, preview_signature
from composition_session_state import COMPOSER_ACTIVE_SECTION_KEY, set_active_document


class TestCompositionChordCreativeLoop(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="A warm romantic song about finding home.",
            mood="Warm / romantic",
            key="G major",
            bpm=96,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        return doc

    def test_suggestions_use_composition_key_major(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        ideas = suggest_progressions(doc, verse, "stable", limit=3)
        self.assertGreaterEqual(len(ideas), 1)
        line = " ".join(str(ideas[0].get("line") or ""))
        # G-major family material — not a random Gm/Am-only slate.
        self.assertTrue(any(tok in line for tok in ("G", "Em", "C", "D", "Bm")), line)
        self.assertNotIn("| Gm |", line)

    def test_suggestions_vary_by_section_role_and_neighbor(self) -> None:
        doc = self._song()
        verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("Em C G D"))
        chorus_ideas = suggest_progressions(doc, chorus, "uplifting", limit=3)
        contexts = [str(i.get("context") or "") for i in chorus_ideas]
        self.assertIn("neighbor", contexts)
        self.assertTrue(any("lift" in str(i.get("name") or "").lower() or i.get("context") == "neighbor" for i in chorus_ideas))

    def test_use_this_mutates_preview_does_not(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        ideas = suggest_progressions(doc, verse, "uplifting", limit=2)
        sug = ideas[0]
        before = list(verse.get("chords") or [])
        # Preview path uses chord_override only — document unchanged.
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            chord_override=[c["chord"] for c in sug["chords"]],
            loops=1,
        )
        self.assertTrue(wav)
        self.assertEqual(verse.get("chords") or [], before)
        apply_section_chords(doc, str(verse["id"]), sug["chords"])
        self.assertTrue(verse.get("chords"))
        self.assertNotEqual(verse.get("chords"), before)

    def test_suggestions_span_full_section_and_more_options(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        self.assertEqual(int(verse.get("bars") or 0), 8)
        ideas = suggest_progressions(doc, verse, "stable", limit=3)
        self.assertGreaterEqual(len(ideas), 2)
        for idea in ideas:
            self.assertGreaterEqual(progression_bar_count(list(idea.get("chords") or [])), 8, idea.get("name"))
        more = suggest_progressions(doc, verse, "stable", limit=3, more=True)
        self.assertGreater(len(more), len(ideas))
        more_ids = {str(i.get("id") or "") for i in more}
        first_ids = {str(i.get("id") or "") for i in ideas}
        self.assertTrue(more_ids - first_ids)

    def test_guided_vocab_pop_vs_jazz(self) -> None:
        pop = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=96, meter="4/4")
        jazz = bootstrap_from_vision(genre="Jazz", song_idea="x", key="C major", bpm=96, meter="4/4")
        pop_vocab = guided_chord_vocabulary(pop)
        jazz_vocab = guided_chord_vocabulary(jazz)
        self.assertIn("C", pop_vocab)
        self.assertIn("Am", pop_vocab)
        self.assertIn("G/B", pop_vocab)
        self.assertNotIn("G7alt", pop_vocab)
        self.assertNotIn("Cmaj7#11", pop_vocab)
        self.assertTrue(any(sym.endswith("maj7") or sym.endswith("7") for sym in jazz_vocab))
        self.assertIn("Cmaj7", jazz_vocab)

    def test_guided_vocab_follows_song_key(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="G major", bpm=100, meter="4/4")
        vocab = guided_chord_vocabulary(doc)
        self.assertIn("G", vocab)
        self.assertIn("Em", vocab)
        self.assertIn("D/F#", vocab)
        self.assertNotIn("Cmaj7#11", vocab)

    def test_manual_replace_insert_remove(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        self.assertTrue(replace_section_chord(doc, str(verse["id"]), 1, "D7"))
        self.assertEqual(verse["chords"][1]["chord"], "D7")
        self.assertTrue(insert_section_chord(doc, str(verse["id"]), 2, "Bm"))
        self.assertEqual(verse["chords"][2]["chord"], "Bm")
        self.assertTrue(remove_section_chord(doc, str(verse["id"]), 2))
        self.assertEqual([c["chord"] for c in verse["chords"]], ["G", "D7", "Em", "C"])

    def test_refinement_proposal_does_not_mutate_until_accept(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        original = [c["chord"] for c in verse["chords"]]
        proposal = propose_chord_refinement(doc, verse, "darker")
        self.assertIsNotNone(proposal)
        assert proposal is not None
        self.assertFalse(proposal.get("mutates"))
        self.assertTrue(proposal.get("why"))
        self.assertTrue(proposal.get("line"))
        self.assertEqual([c["chord"] for c in verse["chords"]], original)
        apply_section_chords(doc, str(verse["id"]), list(proposal["chords"]))
        self.assertNotEqual([c["chord"] for c in verse["chords"]], original)

    def test_refinement_intents_generate_proposals(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        for intent, _label in CHORD_REFINEMENT_INTENTS:
            proposal = propose_chord_refinement(doc, verse, intent)
            self.assertIsNotNone(proposal, intent)
            assert proposal is not None
            self.assertTrue(proposal.get("chords"), intent)
            self.assertTrue(proposal.get("why"), intent)

    def test_linked_harmony_and_break_link(self) -> None:
        doc = self._song()
        sections = ordered_sections(doc)
        verse1 = sections[0]
        verse2 = next(s for s in sections if str(s.get("label_variant") or "").startswith("Verse 2"))
        apply_section_chords(doc, str(verse1["id"]), parse_chord_paste("G Am C D"))
        link = verse2.setdefault("chord_link", {})
        link["linked"] = True
        link["source_section_id"] = str(verse1["id"])
        verse2["chords"] = []
        resolved = chords_for_playback(doc, scope="section", section_id=str(verse2["id"]))
        self.assertEqual(resolved[:2], ["G", "Am"])
        status = section_lane_status(doc, str(verse2["id"]))
        self.assertEqual(status["chords"], "complete")
        self.assertTrue(break_chord_link(doc, str(verse2["id"])))
        self.assertFalse((verse2.get("chord_link") or {}).get("linked"))

    def test_section_switch_preserves_progressions(self) -> None:
        doc = self._song()
        verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("C G Am D"))
        ss = {COMPOSER_ACTIVE_SECTION_KEY: str(chorus["id"])}
        set_active_document(ss, doc)
        ss[COMPOSER_ACTIVE_SECTION_KEY] = str(verse["id"])
        self.assertEqual(chords_for_playback(doc, scope="section", section_id=str(verse["id"]))[:2], ["G", "D"])
        self.assertEqual(chords_for_playback(doc, scope="section", section_id=str(chorus["id"]))[:2], ["C", "G"])


class TestCompositionMelodyCreativeLoop(unittest.TestCase):
    def _prepared(self):
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Melody over harmony.",
            key="C major",
            bpm=100,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C G Am F"))
        return doc, verse, chorus

    def test_melody_suggestions_have_playable_events(self) -> None:
        doc, verse, _chorus = self._prepared()
        concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=3)
        self.assertGreaterEqual(len(concepts), 1)
        events = list(concepts[0].get("events") or [])
        self.assertGreaterEqual(len(events), 3)
        self.assertTrue(events[0].get("pitch"))
        self.assertTrue(events[0].get("duration_beats"))

    def test_accept_melody_updates_only_selected_section(self) -> None:
        doc, verse, chorus = self._prepared()
        concepts = suggest_melody_concepts(doc, verse, "bold", limit=1)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        self.assertTrue(section_has_melody(verse))
        self.assertFalse(section_has_melody(chorus))
        self.assertEqual(section_lane_status(doc, str(verse["id"]))["melody"], "complete")
        self.assertEqual(section_lane_status(doc, str(chorus["id"]))["melody"], "incomplete")

    def test_melody_persists_after_section_switch(self) -> None:
        doc, verse, chorus = self._prepared()
        concepts = suggest_melody_concepts(doc, verse, "smooth", limit=1)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        ss = {COMPOSER_ACTIVE_SECTION_KEY: str(chorus["id"])}
        set_active_document(ss, doc)
        ss[COMPOSER_ACTIVE_SECTION_KEY] = str(verse["id"])
        self.assertTrue(section_melody_events(verse))

    def test_preview_melody_does_not_mutate_accepted(self) -> None:
        doc, verse, _ = self._prepared()
        concepts = suggest_melody_concepts(doc, verse, "energetic", limit=2)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        before = section_melody_events(verse)
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=concepts[1]["events"],
            loops=1,
        )
        self.assertTrue(wav)
        self.assertEqual(section_melody_events(verse), before)

    def test_play_section_chords_plus_melody(self) -> None:
        doc, verse, _ = self._prepared()
        concepts = suggest_melody_concepts(doc, verse, "bold", limit=1)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        sig = preview_signature(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(sig[-2])  # include_melody flag
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(wav)
        chords_only = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=False, loops=1)
        self.assertTrue(chords_only)

    def test_hum_capture_alone_is_not_transcription(self) -> None:
        doc, verse, _ = self._prepared()
        melody = verse.setdefault("melody", {"intent": {}, "phrases": [], "events": []})
        melody["intent"]["hum_capture"] = {
            "captured": True,
            "bytes_len": 1200,
            "analysis_status": "coming_soon",
            "note_detection": False,
        }
        # Capture metadata alone must not invent note events or complete melody.
        self.assertFalse(section_melody_events(verse))
        self.assertFalse(section_has_melody(verse))

    def test_ownership_and_nonlinear_still_green(self) -> None:
        doc = bootstrap_from_vision(
            genre="Folk",
            song_idea="Ownership check.",
            key="Db minor",
            bpm=72,
            meter="6/8",
        )
        self.assertEqual(doc["global"]["original_key_center"], "Dbm")
        self.assertEqual(doc["global"]["bpm"], 72)
        apply_structure_template(doc, "simple")
        self.assertTrue(phase_is_reachable(doc, "chords"))
        self.assertTrue(phase_is_reachable(doc, "melody"))
        # No instrument field on composition.
        self.assertNotIn("instrument", doc.get("global") or {})
        self.assertNotIn("instrument", doc.get("metadata") or {})


if __name__ == "__main__":
    unittest.main()
