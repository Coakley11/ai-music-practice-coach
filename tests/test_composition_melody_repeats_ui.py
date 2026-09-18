"""UI/render regressions: in-place active melody + Melody repeats (no top Active block)."""

from __future__ import annotations

import inspect
import unittest

from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    get_active_melody_source_id,
    ordered_sections,
    section_by_id,
    section_melody_events,
)
from composition_melody_repeats import (
    get_melody_repeats,
    heal_melody_tiling_if_safe,
    mark_melody_customized,
    melody_is_tiled,
    melody_repeats_are_editable,
    set_section_melody_repeats,
)
from composition_studio_page import (
    _render_active_melody_inplace_tools,
    _render_active_melody_repeat_controls,
    _render_active_melody_workspace,
    _render_hum_sing_panel,
    _render_phase_melody,
)


def _doc() -> dict:
    doc = bootstrap_from_vision(genre="Pop", song_idea="repeats ui", key="C major", bpm=96, meter="4/4")
    apply_structure_template(doc, "pop")
    return doc


def _phrase() -> list[dict]:
    return [
        {"pitch": "C4", "midi": 60, "beat": 0.0, "duration_beats": 1.0},
        {"pitch": "E4", "midi": 64, "beat": 1.0, "duration_beats": 1.0},
        {"pitch": "G4", "midi": 67, "beat": 2.0, "duration_beats": 1.0},
        {"pitch": "C5", "midi": 72, "beat": 3.0, "duration_beats": 1.0},
    ]


class TestMelodyRepeatsUiRender(unittest.TestCase):
    def test_phase_feel_before_hum_before_ai_no_top_active_block(self) -> None:
        src = inspect.getsource(_render_phase_melody)
        feel_i = src.index("**Melody Feel & Notes**")
        hum_i = src.index("_render_hum_sing_panel")
        ai_i = src.index("**AI Melody Suggestions**")
        self.assertLess(feel_i, hum_i)
        self.assertLess(hum_i, ai_i)
        # Must NOT hoist a separate Active Melody workspace above Feel
        self.assertNotIn("Explore other ideas", src)
        early = src[:feel_i]
        self.assertNotIn("_render_active_melody_inplace_tools", early)
        self.assertNotIn("_render_active_melody_workspace", early)
        self.assertNotIn('st.markdown("**Active Melody**")', src)
        # In-place tools under matching suggestion / sticky fallback
        self.assertIn("_render_active_melody_inplace_tools", src)
        self.assertIn("is_active", src)
        self.assertIn("matched_active_in_list", src)

    def test_inplace_tools_have_repeats_shape_ape_no_top_heading(self) -> None:
        src = inspect.getsource(_render_active_melody_inplace_tools)
        self.assertIn("_render_active_melody_repeat_controls", src)
        self.assertIn("Shape / refine active melody", src)
        self.assertIn("Advanced Phrase Editor", src)
        self.assertNotIn('st.markdown("**Active Melody**")', src)
        self.assertNotIn("_accepted_melody_concept_from_section", src)
        self.assertLess(
            src.index("_render_active_melody_repeat_controls"),
            src.index("Shape / refine active melody"),
        )
        self.assertLess(
            src.index("Shape / refine active melody"),
            src.index("Advanced Phrase Editor"),
        )

    def test_workspace_alias_delegates_to_inplace_tools(self) -> None:
        src = inspect.getsource(_render_active_melody_workspace)
        self.assertIn("_render_active_melody_inplace_tools", src)

    def test_hum_panel_renders_inplace_tools_for_recorded_active(self) -> None:
        src = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("hum_transcription", src)
        self.assertIn("_render_active_melody_inplace_tools", src)
        self.assertIn("composer_melody_hum_active_", src)

    def test_repeat_control_source_has_visible_buttons(self) -> None:
        src = inspect.getsource(_render_active_melody_repeat_controls)
        self.assertIn("Melody repeats", src)
        self.assertIn("composer_melody_repeats_", src)
        self.assertIn("Repeats are locked", src)
        self.assertIn("composer_melody_repeats_btn_", src)
        self.assertIn("st.button(", src)
        self.assertNotIn('label_visibility="collapsed"', src)
        self.assertNotIn("st.slider(", src)

    def test_ai_accept_heals_and_expands(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "ai", "name": "AI"}, replace=True)
        sec = section_by_id(doc, sid)
        self.assertTrue(melody_repeats_are_editable(sec))
        self.assertTrue(set_section_melody_repeats(doc, sid, 3))
        self.assertEqual(len(section_melody_events(sec)), 12)
        self.assertEqual(get_melody_repeats(sec), 3)

    def test_hum_accept_path_sets_tiled(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(
            doc,
            sid,
            _phrase(),
            concept={"id": "hum_transcription", "name": "Recorded melody"},
            replace=True,
        )
        sec = section_by_id(doc, sid)
        self.assertTrue(heal_melody_tiling_if_safe(sec))
        self.assertTrue(melody_is_tiled(sec))
        self.assertEqual(get_active_melody_source_id(sec), "hum_transcription")

    def test_missing_tiled_meta_heals(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "x", "name": "X"}, replace=True)
        sec = section_by_id(doc, sid)
        sec["melody"]["melody_tiled"] = False
        del sec["melody"]["melody_pattern"]
        self.assertTrue(heal_melody_tiling_if_safe(sec))
        self.assertTrue(melody_is_tiled(sec))
        self.assertTrue(set_section_melody_repeats(doc, sid, 2))
        self.assertEqual(len(section_melody_events(sec)), 8)

    def test_customized_locks_repeats(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "x", "name": "X"}, replace=True)
        set_section_melody_repeats(doc, sid, 3)
        sec = section_by_id(doc, sid)
        mark_melody_customized(sec)
        self.assertFalse(melody_repeats_are_editable(sec))
        self.assertFalse(set_section_melody_repeats(doc, sid, 4))

    def test_section_scoped_repeat_keys(self) -> None:
        src = inspect.getsource(_render_active_melody_repeat_controls)
        self.assertIn("composer_melody_repeats_{section_id}", src)


if __name__ == "__main__":
    unittest.main()
