"""Melody workflow: undo key ownership, recorded preview, feel gating, active refine."""

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
    ordered_sections,
    parse_chord_paste,
    section_by_id,
    section_melody_events,
)
from composition_melody_improve import (
    improve_undo_button_key,
    improve_undo_key,
    pop_improve_undo,
    push_improve_undo,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_preview import generate_preview_wav, play_composer_preview
from composition_studio_page import (
    _melody_intent_ready,
    _render_hum_sing_panel,
    _render_melody_concept_card,
    _render_phase_melody,
    render_composition_studio_page,
)


class TestMelodyWorkflowCrashAndAudio(unittest.TestCase):
    def test_improve_undo_keys_are_distinct(self) -> None:
        sid = "39ced138-cad4-4456-a801-f45ef74403f9"
        self.assertNotEqual(improve_undo_key(sid), improve_undo_button_key(sid))
        self.assertTrue(improve_undo_key(sid).endswith(sid))
        self.assertIn("_stack_", improve_undo_key(sid))

    def test_push_pop_does_not_write_button_widget_key(self) -> None:
        sid = "39ced138-cad4-4456-a801-f45ef74403f9"
        btn = improve_undo_button_key(sid)

        class Guard(dict):
            def __setitem__(self, k, v):
                if k == btn:
                    raise AssertionError(f"illegal write to button key {k}")
                return super().__setitem__(k, v)

        ss: dict = Guard()
        dict.__setitem__(ss, btn, False)  # widget already registered (bypass guard)
        push_improve_undo(ss, sid, [{"pitch": "C4"}])
        push_improve_undo(ss, sid, [{"pitch": "D4"}])
        prev = pop_improve_undo(ss, sid)
        self.assertEqual(prev, [{"pitch": "D4"}])
        self.assertEqual(ss[btn], False)
        self.assertEqual(ss[improve_undo_key(sid)], [[{"pitch": "C4"}]])

    def test_hum_panel_uses_button_key_helper_not_stack_prefix(self) -> None:
        src = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("improve_undo_button_key", src)
        self.assertIn("recorded_audio", src)
        self.assertIn("Use this melody", src)
        self.assertNotIn("Record again", src)

    def test_recorded_preview_mix_flag(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="Am", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sec = ordered_sections(doc)[0]
        sid = str(sec["id"])
        accept_full_progression(doc, sid, parse_chord_paste("Am C G F Am C G7b5/A Bb"), tiled=False)
        # Minimal silent-ish PCM won't mix without real audio; ensure API accepts recorded_audio
        import struct
        import wave
        import io

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            # 0.3s of low-level noise (not silence so playable checks can pass on mix)
            frames = b"".join(struct.pack("<h", int(800 * ((i % 20) / 20.0))) for i in range(22050 // 3))
            wf.writeframes(frames)
        rec = buf.getvalue()
        wav = generate_preview_wav(
            doc,
            section_id=sid,
            loops=1,
            include_melody=False,
            recorded_audio=rec,
            recorded_trim_sec=0.0,
            count_in_bars=0,
        )
        self.assertTrue(wav and len(wav) > 44)
        ss: dict = {}
        result = play_composer_preview(
            ss,
            doc,
            section_id=sid,
            loops=1,
            recorded_audio=rec,
            recorded_trim_sec=0.0,
            slot="test-hum",
            label="rec",
        )
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("recorded_audio"))

    def test_feel_ready_gating(self) -> None:
        self.assertFalse(_melody_intent_ready({}))
        self.assertFalse(_melody_intent_ready({"feel": "bold"}))
        self.assertTrue(_melody_intent_ready({"feel": "bold", "remember": "hook"}))
        self.assertTrue(_melody_intent_ready({"feel": "bold", "feel_confirmed": True}))

    def test_suggestions_consume_feel_notes(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="Am", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sec = ordered_sections(doc)[0]
        accept_full_progression(
            doc, str(sec["id"]), parse_chord_paste("Am C G F Am C G7b5/A Bb"), tiled=False
        )
        concepts = suggest_melody_concepts(
            doc, sec, "bold", "simple", limit=2, remember="soaring leap", notes="stay high"
        )
        self.assertTrue(concepts)
        self.assertEqual(concepts[0].get("remember"), "soaring leap")
        self.assertEqual(concepts[0].get("notes_intent"), "stay high")
        self.assertEqual(concepts[0].get("chord_span"), 8)
        # Description is event-grounded, not a canned recipe + intent echo
        desc = str(concepts[0].get("contour") or "")
        self.assertTrue(desc)
        self.assertNotIn("Strategic leaps make a chorus", desc)

    def test_phase_order_feel_before_hum_before_ai(self) -> None:
        src = inspect.getsource(_render_phase_melody)
        feel_i = src.index("**Melody Feel & Notes**")
        hum_i = src.index("_render_hum_sing_panel")
        ai_i = src.index("**AI Melody Suggestions**")
        self.assertLess(feel_i, hum_i)
        self.assertLess(hum_i, ai_i)
        self.assertIn("Continue with this feel", src)
        self.assertIn("_refine_proposal_key", src)
        self.assertIn("_render_active_melody_phrase_editor", src)

    def test_active_card_no_separate_active_caption(self) -> None:
        src = inspect.getsource(_render_melody_concept_card)
        self.assertNotIn('st.caption("Active melody for this section")', src)
        self.assertIn('data-composer-active="1"', src)

    def test_right_panel_intact(self) -> None:
        self.assertIn("st.columns([2.6, 1.0])", inspect.getsource(render_composition_studio_page))

    def test_refine_accept_moves_active(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="Am", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sec = ordered_sections(doc)[0]
        sid = str(sec["id"])
        accept_full_progression(doc, sid, parse_chord_paste("Am C G F Am C G7b5/A Bb"), tiled=False)
        concepts = suggest_melody_concepts(doc, sec, "bold", limit=1)
        apply_melody_events(doc, sid, concepts[0]["events"], concept=concepts[0])
        self.assertEqual(get_active_melody_source_id(sec), concepts[0]["id"])
        before = list(section_melody_events(sec))
        apply_melody_events(
            doc,
            sid,
            before,
            concept={"id": "refined_test", "name": "Refined", "motif_hint": "x", "contour": "x"},
            replace=True,
        )
        self.assertEqual(get_active_melody_source_id(section_by_id(doc, sid)), "refined_test")
        self.assertEqual(len(chords_for_playback(doc, scope="section", section_id=sid)), 8)


if __name__ == "__main__":
    unittest.main()
