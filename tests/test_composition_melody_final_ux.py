"""Final Melody UX: page order, shape transforms, select-note editor, NL edits."""

from __future__ import annotations

import inspect
import unittest

from composition_chord_repeats import accept_full_progression
from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    get_active_melody_source_id,
    ordered_sections,
    parse_chord_paste,
    section_by_id,
    section_melody_events,
)
from composition_melody_shape import (
    MELODY_REFINEMENTS,
    apply_natural_language_melody_edit,
    events_signature,
    insert_melody_note,
    propose_melody_refinement,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_studio_page import (
    _render_active_melody_phrase_editor,
    _render_hum_sing_panel,
    _render_phase_melody,
    render_composition_studio_page,
)


class TestMelodyFinalUx(unittest.TestCase):
    def _song_with_melody(self):
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="Am", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sec = ordered_sections(doc)[0]
        sid = str(sec["id"])
        accept_full_progression(doc, sid, parse_chord_paste("Am C G F Am C G7b5/A Bb"), tiled=False)
        concepts = suggest_melody_concepts(doc, sec, "bold", limit=1)
        apply_melody_events(doc, sid, concepts[0]["events"], concept=concepts[0])
        return doc, section_by_id(doc, sid), sid

    def test_no_score_above_feel_and_notes(self) -> None:
        src = inspect.getsource(_render_phase_melody)
        feel_i = src.index("**Melody Feel & Notes**")
        # Top score view removed from before Feel
        self.assertNotIn('_render_section_score_view(\n                session_state,\n                doc,\n                section,\n                play_key=f"composer_melody_hear_structure_', src[:feel_i])
        self.assertLess(feel_i, src.index("**AI Melody Suggestions**"))
        self.assertLess(src.index("_render_hum_sing_panel"), src.index("**AI Melody Suggestions**"))
        self.assertLess(src.index("**AI Melody Suggestions**"), src.index("**Active Melody**"))
        self.assertLess(src.index("**Active Melody**"), src.index("**Shape / refine active melody**"))
        self.assertLess(src.index("**Shape / refine active melody**"), src.index("Advanced Phrase Editor"))

    def test_friendly_recording_warning(self) -> None:
        src = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("For the clearest results, record one melody line at a time", src)
        self.assertNotIn("not reliable in V1", src)

    def test_each_refinement_changes_events_or_explains(self) -> None:
        doc, sec, sid = self._song_with_melody()
        events = list(section_melody_events(sec))
        self.assertGreaterEqual(len(events), 4)
        changed = 0
        for rid, label, _ in MELODY_REFINEMENTS:
            result = propose_melody_refinement(events, rid, key="Am")
            if result.get("ok") and not result.get("unchanged"):
                self.assertNotEqual(events_signature(result["events"]), events_signature(events), label)
                changed += 1
            else:
                self.assertTrue(str(result.get("summary") or ""), label)
        self.assertGreaterEqual(changed, 5)

    def test_refinement_proposal_does_not_mutate_until_accept_pattern(self) -> None:
        src = inspect.getsource(_render_phase_melody)
        self.assertIn("propose_melody_refinement", src)
        self.assertIn("Accept refinement", src)
        # Choosing a shape stores proposal key — does not call apply_melody_events until Accept
        shape_block = src[src.index("propose_melody_refinement") : src.index("Accept refinement")]
        self.assertNotIn("apply_melody_events(", shape_block)

    def test_editor_select_one_note_not_all_forms(self) -> None:
        src = inspect.getsource(_render_active_melody_phrase_editor)
        self.assertIn("Select note", src)
        self.assertIn("Selected note", src)
        self.assertIn("Add note", src)
        self.assertIn("Describe a change", src)
        self.assertIn("Accept changes", src)
        self.assertNotIn("Pitch {i + 1}", src)

    def test_insert_note_and_nl_hold_add(self) -> None:
        events = [
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "F4", "midi": 65, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 2.0},
            {"pitch": "C5", "midi": 72, "duration_beats": 1.0, "beat": 3.0},
        ]
        inserted = insert_melody_note(events, at_index=1, pitch="E4", duration_beats=0.5, key="Am", before=True)
        self.assertEqual(len(inserted), 5)
        self.assertEqual(inserted[1]["pitch"][:1], "E")

        result = apply_natural_language_melody_edit(
            events,
            "Hold D in the first bar longer and add a short E before the F note.",
            key="Am",
            meter="4/4",
        )
        self.assertTrue(result.get("ok"), result.get("message"))
        out = list(result.get("events") or [])
        self.assertNotEqual(events_signature(out), events_signature(events))
        # D should be longer
        d_ev = next(e for e in out if str(e.get("pitch") or "").startswith("D"))
        self.assertGreater(float(d_ev.get("duration_beats") or 0), 1.0)
        pitches = [str(e.get("pitch") or "") for e in out]
        self.assertTrue(any(p.startswith("E") for p in pitches))

    def test_ambiguous_nl_does_not_silently_pick(self) -> None:
        events = [
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "F4", "midi": 65, "duration_beats": 1.0, "beat": 2.0},
        ]
        result = apply_natural_language_melody_edit(
            events, "Hold D longer", key="Am", meter="4/4"
        )
        self.assertTrue(result.get("needs_choice"))
        self.assertEqual(events_signature(result.get("events")), events_signature(events))

    def test_right_panel_intact(self) -> None:
        self.assertIn("st.columns([2.6, 1.0])", inspect.getsource(render_composition_studio_page))

    def test_accept_sets_active_source(self) -> None:
        doc, sec, sid = self._song_with_melody()
        before = list(section_melody_events(sec))
        result = propose_melody_refinement(before, "range_up", key="Am")
        self.assertTrue(result.get("ok"))
        apply_melody_events(
            doc,
            sid,
            result["events"],
            concept={"id": "refined_range_up", "name": "Range", "motif_hint": "x", "contour": "x"},
            replace=True,
        )
        self.assertEqual(get_active_melody_source_id(section_by_id(doc, sid)), "refined_range_up")


if __name__ == "__main__":
    unittest.main()
