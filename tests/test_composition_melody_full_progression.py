"""Melody consumes full Chords progression; active highlight; no redundant repeats."""

from __future__ import annotations

import inspect
import unittest

from composition_chord_repeats import accept_full_progression
from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    get_active_melody_source_id,
    melody_harmony_is_stale,
    ordered_sections,
    parse_chord_paste,
    section_by_id,
    section_melody_events,
)
from composition_melody_suggestions import build_melody_events_over_chords, suggest_melody_concepts
from composition_preview import generate_preview_wav
from composition_studio_page import _render_hum_sing_panel, _render_melody_concept_card, render_composition_studio_page


class TestMelodyFullProgression(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="Full harmony melody", key="A minor", bpm=96, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        return doc

    def test_consumes_full_section_chords(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        accept_full_progression(
            doc,
            str(verse["id"]),
            parse_chord_paste("Am C G F Am C G7b5/A Bb"),
            tiled=False,
        )
        chords = chords_for_playback(doc, scope="section", section_id=str(verse["id"]))
        self.assertEqual(chords, ["Am", "C", "G", "F", "Am", "C", "G7b5/A", "Bb"])
        concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=2)
        events = list(concepts[0].get("events") or [])
        self.assertEqual(concepts[0].get("chord_span"), 8)
        self.assertEqual([e.get("chord") for e in events], chords)

    def test_later_pass_uses_edited_harmony(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        accept_full_progression(
            doc,
            str(verse["id"]),
            parse_chord_paste("C F G C C Am G7 C"),
            tiled=False,
        )
        concepts = suggest_melody_concepts(doc, verse, "bold", limit=1)
        events = list(concepts[0].get("events") or [])
        by_index = {}
        for e in events:
            by_index.setdefault(int(e.get("chord_index") or 0), e.get("chord"))
        self.assertEqual(
            [by_index[i] for i in range(8)],
            ["C", "F", "G", "C", "C", "Am", "G7", "C"],
        )
        # Corresponding positions: F (idx1) vs Am (idx5) must differ.
        midis_by_idx = {}
        for e in events:
            midis_by_idx.setdefault(int(e.get("chord_index") or 0), int(e.get("midi") or 0))
        self.assertNotEqual(midis_by_idx[1], midis_by_idx[5])

    def test_build_over_chords_event_count(self) -> None:
        events = build_melody_events_over_chords(
            ["Am", "C", "G", "F", "Am", "C", "G7b5/A", "Bb"],
            key="Am",
            meter="4/4",
            style="simple",
        )
        self.assertEqual(len(events), 8)
        self.assertAlmostEqual(sum(float(e["duration_beats"]) for e in events), 32.0)

    def test_no_independent_melody_repeat_control(self) -> None:
        src = inspect.getsource(_render_hum_sing_panel)
        self.assertNotIn("Section progression repeats", src)
        self.assertNotIn("backing length", src)
        card = inspect.getsource(_render_melody_concept_card)
        self.assertNotIn("Repeat phrase", card)

    def test_record_again_absent(self) -> None:
        src = inspect.getsource(_render_hum_sing_panel)
        self.assertNotIn("Record again", src)
        self.assertIn("Hum or sing your melody", src)

    def test_preview_does_not_mark_active(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("Am C G F"), tiled=False)
        concepts = suggest_melody_concepts(doc, verse, "smooth", limit=2)
        before = get_active_melody_source_id(verse)
        generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=concepts[0]["events"],
            loops=1,
        )
        self.assertEqual(get_active_melody_source_id(verse), before)
        self.assertEqual(section_melody_events(verse), [])

    def test_use_marks_one_active_melody(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("Am C G F"), tiled=False)
        concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=2)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        self.assertEqual(get_active_melody_source_id(verse), concepts[0]["id"])
        apply_melody_events(doc, str(verse["id"]), concepts[1]["events"], concept=concepts[1])
        self.assertEqual(get_active_melody_source_id(verse), concepts[1]["id"])
        self.assertNotEqual(concepts[0]["id"], concepts[1]["id"])

    def test_active_melody_section_scoped(self) -> None:
        doc = self._song()
        verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("Am C G F"), tiled=False)
        accept_full_progression(doc, str(chorus["id"]), parse_chord_paste("C G Am F"), tiled=False)
        v_concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=1)
        c_concepts = suggest_melody_concepts(doc, chorus, "bold", limit=1)
        apply_melody_events(doc, str(verse["id"]), v_concepts[0]["events"], concept=v_concepts[0])
        apply_melody_events(doc, str(chorus["id"]), c_concepts[0]["events"], concept=c_concepts[0])
        self.assertEqual(get_active_melody_source_id(verse), v_concepts[0]["id"])
        self.assertEqual(get_active_melody_source_id(chorus), c_concepts[0]["id"])

    def test_stale_harmony_flag(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_full_progression(doc, sid, parse_chord_paste("Am C G F"), tiled=False)
        concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=1)
        apply_melody_events(doc, sid, concepts[0]["events"], concept=concepts[0])
        self.assertFalse(melody_harmony_is_stale(doc, sid))
        accept_full_progression(doc, sid, parse_chord_paste("Am C G7b5/A Bb"), tiled=False)
        self.assertTrue(melody_harmony_is_stale(doc, sid))

    def test_playback_uses_full_progression_once(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        accept_full_progression(
            doc, str(verse["id"]), parse_chord_paste("Am C G F Am C G7b5/A Bb"), tiled=False
        )
        concepts = suggest_melody_concepts(doc, verse, "lyrical", limit=1)
        apply_melody_events(doc, str(verse["id"]), concepts[0]["events"], concept=concepts[0])
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(wav)
        chords = chords_for_playback(doc, scope="section", section_id=str(verse["id"]))
        self.assertEqual(len(chords), 8)

    def test_compare_absent_and_right_panel(self) -> None:
        card = inspect.getsource(_render_melody_concept_card)
        self.assertNotIn("+ Compare", card)
        page = inspect.getsource(render_composition_studio_page)
        self.assertIn("st.columns([2.6, 1.0])", page)

    def test_concept_card_highlight_wiring(self) -> None:
        src = inspect.getsource(_render_melody_concept_card)
        self.assertIn("is-active", src)
        self.assertIn("is_active", src)
        self.assertIn("Use this melody", src)
        self.assertIn('data-composer-active="1"', src)
        self.assertNotIn("expand_melody_events_by_repeats", src)
        import composition_studio_page as csp

        self.assertTrue(hasattr(csp, "_accepted_melody_concept_from_section"))
        phase = inspect.getsource(csp._render_phase_melody)
        self.assertIn("_accepted_melody_concept_from_section", phase)
        self.assertIn("_render_active_melody_inplace_tools", phase)
        self.assertIn("is_active", phase)
        # No page-top Active Melody heading
        self.assertNotIn('st.markdown("**Active Melody**")', phase)
        self.assertIn("st.columns([2.6, 1.0])", inspect.getsource(render_composition_studio_page))


if __name__ == "__main__":
    unittest.main()
