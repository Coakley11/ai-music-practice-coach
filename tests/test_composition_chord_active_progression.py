"""Active chord progression: repeats, highlight, refine/manual handoff."""

from __future__ import annotations

import inspect
import unittest

from composition_chord_refinements import propose_chord_refinement
from composition_chord_repeats import (
    COMPLETION_COPY,
    accept_chord_pattern,
    accept_full_progression,
    chords_are_tiled,
    entry_symbols,
    expand_chord_entries_by_repeats,
    format_full_progression_display,
    get_chord_repeats,
    get_chord_source_id,
    set_section_chord_repeats,
)
from composition_document import (
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    ordered_sections,
    parse_chord_paste,
    section_by_id,
)
from composition_preview import generate_preview_wav, preview_signature
from composition_studio_page import _render_phase_chords, _render_suggestion_card


class TestActiveChordProgression(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="Active chords", key="C major", bpm=100, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        return doc

    def test_no_separate_current_progression_display(self) -> None:
        src = inspect.getsource(_render_phase_chords)
        self.assertNotIn("**Current progression**", src)
        self.assertNotIn("Current progression", src)
        self.assertIn("COMPLETION_COPY", src)
        self.assertIn("is_active", src)

    def test_completion_copy_exact(self) -> None:
        self.assertEqual(
            COMPLETION_COPY,
            "Your chords are ready. Build or hum a melody over them — or keep refining harmony.",
        )
        src = inspect.getsource(_render_phase_chords)
        self.assertIn("st.info(COMPLETION_COPY)", src)

    def test_use_this_sets_one_active_source(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        pattern = parse_chord_paste("C F G C")
        self.assertTrue(accept_chord_pattern(doc, sid, pattern, source_id="pop_stable_1", repeats=1))
        sec = section_by_id(doc, sid)
        self.assertEqual(get_chord_source_id(sec), "pop_stable_1")
        self.assertEqual(entry_symbols(sec.get("chords")), ["C", "F", "G", "C"])
        self.assertTrue(chords_are_tiled(sec))

    def test_repeat_slider_expands_full_progression(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        pattern = parse_chord_paste("C F G C")
        accept_chord_pattern(doc, sid, pattern, source_id="x", repeats=1)
        self.assertTrue(set_section_chord_repeats(doc, sid, 3))
        sec = section_by_id(doc, sid)
        self.assertEqual(get_chord_repeats(sec), 3)
        symbols = entry_symbols(sec.get("chords"))
        self.assertEqual(len(symbols), 12)
        self.assertEqual(symbols, ["C", "F", "G", "C"] * 3)
        display = format_full_progression_display(sec.get("chords"), pattern_len=4)
        self.assertEqual(display.count("\n"), 2)
        self.assertIn("C | F | G | C", display)

    def test_expand_helper_event_count(self) -> None:
        pattern = parse_chord_paste("Am F C G")
        expanded = expand_chord_entries_by_repeats(pattern, 4)
        self.assertEqual(len(entry_symbols(expanded)), 16)

    def test_active_playback_signature_uses_full_repeats(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="x", repeats=3)
        chords = chords_for_playback(doc, scope="section", section_id=sid)
        self.assertEqual(len(chords), 12)
        sig = preview_signature(doc, section_id=sid, loops=1, chord_override=chords)
        wav = generate_preview_wav(doc, section_id=sid, loops=1, chord_override=chords)
        self.assertTrue(wav)
        self.assertIsInstance(sig, tuple)

    def test_refinement_receives_full_progression(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="x", repeats=3)
        sec = section_by_id(doc, sid)
        before = entry_symbols(sec.get("chords"))
        proposal = propose_chord_refinement(doc, sec, "darker", entries=list(sec.get("chords") or []))
        self.assertIsNotNone(proposal)
        assert proposal is not None
        proposed = entry_symbols(proposal.get("chords"))
        self.assertEqual(len(proposed), 12)
        self.assertEqual(proposed[:11], before[:11])
        # darker mutates the last chord of the full progression
        self.assertNotEqual(proposed[-1], before[-1])

    def test_preview_refinement_does_not_commit(self) -> None:
        from composition_preview import play_composer_preview

        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="x", repeats=2)
        sec = section_by_id(doc, sid)
        before = list(sec.get("chords") or [])
        proposal = propose_chord_refinement(doc, sec, "happier", entries=before)
        assert proposal is not None
        ss: dict = {}
        result = play_composer_preview(
            ss,
            doc,
            section_id=sid,
            chord_override=entry_symbols(proposal.get("chords")),
            loops=1,
            slot="refine-test",
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(sec.get("chords"), before)

    def test_use_refinement_replaces_active(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="base", repeats=2)
        sec = section_by_id(doc, sid)
        proposal = propose_chord_refinement(doc, sec, "surprise", entries=list(sec.get("chords") or []))
        assert proposal is not None
        accept_full_progression(
            doc, sid, list(proposal.get("chords") or []), source_id=str(proposal.get("id")), tiled=False
        )
        sec = section_by_id(doc, sid)
        self.assertEqual(get_chord_source_id(sec), str(proposal.get("id")))
        self.assertFalse(chords_are_tiled(sec))
        self.assertEqual(len(entry_symbols(sec.get("chords"))), 8)

    def test_manual_edit_one_occurrence(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="x", repeats=3)
        sec = section_by_id(doc, sid)
        full = list(sec.get("chords") or [])
        # Second pass, second chord (index 5): F → Am
        full[5] = {"chord": "Am", "bars": 1}
        accept_full_progression(doc, sid, full, tiled=False)
        sec = section_by_id(doc, sid)
        symbols = entry_symbols(sec.get("chords"))
        self.assertEqual(symbols[5], "Am")
        self.assertEqual(symbols[1], "F")
        self.assertEqual(symbols[9], "F")
        self.assertFalse(chords_are_tiled(sec))
        # Repeat slider must not wipe custom edits
        self.assertFalse(set_section_chord_repeats(doc, sid, 4))
        self.assertEqual(entry_symbols(sec.get("chords"))[5], "Am")

    def test_section_switching_preserves_progressions(self) -> None:
        doc = self._song()
        sections = ordered_sections(doc)
        v = sections[0]
        c = sections[1]
        accept_chord_pattern(doc, str(v["id"]), parse_chord_paste("C F G C"), source_id="verse", repeats=2)
        accept_chord_pattern(doc, str(c["id"]), parse_chord_paste("Am F C G"), source_id="chorus", repeats=4)
        v2 = section_by_id(doc, str(v["id"]))
        c2 = section_by_id(doc, str(c["id"]))
        self.assertEqual(len(entry_symbols(v2.get("chords"))), 8)
        self.assertEqual(len(entry_symbols(c2.get("chords"))), 16)
        self.assertEqual(get_chord_source_id(v2), "verse")
        self.assertEqual(get_chord_source_id(c2), "chorus")

    def test_melody_handoff_receives_full_progression(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        sid = str(verse["id"])
        accept_chord_pattern(doc, sid, parse_chord_paste("C F G C"), source_id="x", repeats=3)
        sec = section_by_id(doc, sid)
        full = list(sec.get("chords") or [])
        full[5] = {"chord": "Am", "bars": 1}
        accept_full_progression(doc, sid, full, tiled=False)
        handed = chords_for_playback(doc, scope="section", section_id=sid)
        self.assertEqual(len(handed), 12)
        self.assertEqual(handed[5], "Am")
        self.assertEqual(handed, entry_symbols(section_by_id(doc, sid).get("chords")))

    def test_suggestion_card_highlight_and_no_compare(self) -> None:
        src = inspect.getsource(_render_suggestion_card)
        self.assertIn("is-active", src)
        self.assertIn("is_active", src)
        self.assertNotIn("+ Compare", src)
        self.assertIn("accept_chord_pattern", src)

    def test_right_panel_page_split_intact(self) -> None:
        from composition_studio_page import render_composition_studio_page

        src = inspect.getsource(render_composition_studio_page)
        self.assertIn("st.columns([2.6, 1.0])", src)
        self.assertIn("_render_page_right_utility", src)


if __name__ == "__main__":
    unittest.main()
