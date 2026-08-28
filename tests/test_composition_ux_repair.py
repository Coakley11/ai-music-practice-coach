"""Composition Studio — structure controls, preview UX, notation-first melody."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from composition_document import (
    COMPOSER_SECTION_LABELS,
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    duplicate_section,
    move_section,
    neighbor_section_after_remove,
    ordered_sections,
    parse_chord_paste,
    remove_section,
    section_melody_events,
)
from composition_melody_notation import (
    build_abc_from_melody_events,
    build_section_score_model,
    chord_symbols_by_measure,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_preview import generate_preview_wav, preview_signature
from composition_session_state import (
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_PREVIEW_WAV_KEY,
    set_active_document,
)
from composition_studio_page import (
    _compare_queue_key,
    _play_chord_idea,
    _render_phase_structure,
)


class TestStructureButtons(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Jewish", song_idea="Form", key="D minor", bpm=100, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        return doc

    def test_move_earlier_later(self) -> None:
        doc = self._song()
        order = list(doc["form"]["section_order"])
        mid = order[1]
        self.assertTrue(move_section(doc, mid, -1))
        self.assertEqual(doc["form"]["section_order"][0], mid)
        self.assertTrue(move_section(doc, mid, 1))
        self.assertEqual(doc["form"]["section_order"][1], mid)

    def test_move_edges_noop(self) -> None:
        doc = self._song()
        order = list(doc["form"]["section_order"])
        self.assertFalse(move_section(doc, order[0], -1))
        self.assertEqual(doc["form"]["section_order"], order)
        self.assertFalse(move_section(doc, order[-1], 1))
        self.assertEqual(doc["form"]["section_order"], order)

    def test_duplicate_independent(self) -> None:
        doc = self._song()
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("Dm Bb F C"))
        before = list(doc["form"]["section_order"])
        clone = duplicate_section(doc, str(verse["id"]), link_chords=False)
        self.assertIsNotNone(clone)
        assert clone is not None
        self.assertNotIn(clone["id"], before)
        self.assertFalse((clone.get("chord_link") or {}).get("linked"))
        self.assertEqual(clone["chords"][0]["chord"], "Dm")

    def test_remove_selects_neighbor(self) -> None:
        doc = self._song()
        order = list(doc["form"]["section_order"])
        removed = order[1]
        neighbor = neighbor_section_after_remove(doc, removed, order)
        self.assertTrue(remove_section(doc, removed))
        self.assertNotIn(removed, doc["form"]["section_order"])
        self.assertIn(neighbor, doc["form"]["section_order"])

    def test_remove_clears_dangling_links(self) -> None:
        doc = self._song()
        v1 = ordered_sections(doc)[0]
        v2 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 2")
        self.assertTrue((v2.get("chord_link") or {}).get("linked"))
        self.assertTrue(remove_section(doc, str(v1["id"])))
        v2b = next(s for s in ordered_sections(doc) if s.get("id") == v2["id"])
        self.assertFalse((v2b.get("chord_link") or {}).get("linked"))

    def test_more_sections_dropdown_removed(self) -> None:
        src = inspect.getsource(_render_phase_structure)
        self.assertNotIn("More sections", src)
        self.assertIn("Add section", src)
        for label in COMPOSER_SECTION_LABELS:
            self.assertIn(label, COMPOSER_SECTION_LABELS)


class TestHarmonyPreviewAndCompare(unittest.TestCase):
    def test_preview_does_not_mutate_and_sets_audio(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="G major", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        before = list(verse.get("chords") or [])
        ss: dict = {}
        set_active_document(ss, doc)
        ok = _play_chord_idea(ss, doc, str(verse["id"]), ["Am", "F", "C", "G"], loops=1)
        self.assertTrue(ok)
        self.assertTrue(ss.get(COMPOSER_PREVIEW_WAV_KEY))
        self.assertEqual(verse.get("chords") or [], before)

    def test_preview_respects_bpm_meter(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=72, meter="3/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        sig_a = preview_signature(doc, section_id=str(verse["id"]), chord_override=["C", "G", "Am"])
        doc["global"]["bpm"] = 140
        sig_b = preview_signature(doc, section_id=str(verse["id"]), chord_override=["C", "G", "Am"])
        self.assertNotEqual(sig_a, sig_b)
        doc["global"]["time_signature"] = "6/8"
        sig_c = preview_signature(doc, section_id=str(verse["id"]), chord_override=["C", "G", "Am"])
        self.assertNotEqual(sig_b, sig_c)

    def test_compare_queue_visible_key(self) -> None:
        sid = "sec-1"
        self.assertEqual(_compare_queue_key(sid), "composer_compare_sec-1")


class TestNotationFirstMelody(unittest.TestCase):
    def test_score_model_staff_and_chords(self) -> None:
        events = [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ]
        chords = parse_chord_paste("G D Em C")
        score = build_section_score_model(
            events=events,
            chords=chords,
            key="G major",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text="Home again",
        )
        self.assertTrue(score["has_melody"])
        self.assertTrue(score["has_chords"])
        self.assertTrue(score["has_lyrics"])
        self.assertIn("M:4/4", score["abc"])
        self.assertIn("K:", score["abc"])
        self.assertTrue(score["chord_labels"])
        self.assertIn("composer-score-chord", score["chord_strip_html"])

    def test_chord_alignment_measure_deterministic(self) -> None:
        labels = chord_symbols_by_measure(parse_chord_paste("G D Em C"), meter="4/4", measures=4)
        self.assertEqual(labels, ["G", "D", "Em", "C"])

    def test_short_melody_does_not_clip_section_progression(self) -> None:
        chords = parse_chord_paste("C Am F G")
        score = build_section_score_model(
            events=[{"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            chords=chords,
            key="C major",
            meter="4/4",
            bpm=100,
            title="Verse",
            section_bars=8,
        )
        self.assertEqual(score["chord_labels"][:4], ["C", "Am", "F", "G"])
        self.assertEqual(len(score["chord_labels"]), 8)
        self.assertEqual(score["chord_labels"][4:], ["C", "Am", "F", "G"])
        self.assertIn("C (1 bar)", score["progression_line"])
        self.assertIn("G (1 bar)", score["progression_line"])
        self.assertIn("composer-score-chord", score["chord_strip_html"])

    def test_suggestion_has_events_for_staff(self) -> None:
        doc = bootstrap_from_vision(genre="Jewish", song_idea="Nigun", key="D minor", bpm=88, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("Dm Bb F C"))
        concepts = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=2)
        self.assertGreaterEqual(len(concepts), 1)
        events = list(concepts[0].get("events") or [])
        self.assertTrue(events)
        abc = build_abc_from_melody_events(
            events, key="D minor", meter="4/4", bpm=88, title=str(concepts[0].get("name") or "idea")
        )
        self.assertIn("M:4/4", abc)
        # Letter-name line may exist internally but staff source is ABC from events.
        self.assertTrue(abc.strip())

    def test_melody_preview_does_not_accept(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C F G C"))
        proposal = [
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=proposal,
            loops=1,
        )
        self.assertTrue(wav)
        self.assertEqual(section_melody_events(verse), [])

    def test_accept_melody_uses_same_events_for_abc_and_play(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        apply_melody_events(doc, str(verse["id"]), events, replace=True)
        accepted = section_melody_events(verse)
        abc = build_abc_from_melody_events(accepted, key="C major", meter="4/4", bpm=100)
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(wav)
        self.assertIn("M:4/4", abc)
        self.assertIn("K:", abc)
        # Staff and playback both derive from the same accepted events.
        self.assertEqual(accepted[0]["pitch"], "C4")
        self.assertEqual(accepted[1]["pitch"], "E4")

    def test_chords_only_vs_complete_views(self) -> None:
        chords = parse_chord_paste("G D Em C")
        empty = build_section_score_model(
            events=[], chords=chords, key="G", meter="4/4", bpm=96, title="V"
        )
        self.assertFalse(empty["has_melody"])
        self.assertTrue(empty["has_chords"])
        with_mel = build_section_score_model(
            events=[{"pitch": "G4", "midi": 67, "duration_beats": 4.0, "beat": 0.0, "measure": 1}],
            chords=chords,
            key="G",
            meter="4/4",
            bpm=96,
            title="V",
            lyrics_text="line one",
        )
        self.assertTrue(with_mel["has_melody"] and with_mel["has_lyrics"])

    def test_recording_copy_mentions_instrument(self) -> None:
        from composition_studio_page import _render_hum_sing_panel

        src = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("Hum, sing, or play one melodic line", src)
        self.assertIn("Record your melody over these chords.", src)
        self.assertIn("Start mic count-in + chord backing", src)
        self.assertNotIn("What instrument did you record", src)
        # Primary result is staff, not a default note list dump.
        self.assertIn("You sang / played this", src)
        self.assertIn("Edit transcription", src)
        self.assertNotIn("Analyze recording", src)
        self.assertNotIn("Hear the chords", src)
        self.assertNotIn("Record again", src)

    def test_harmony_edit_updates_chords_not_melody(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="G major", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        # Four measures so measure-aligned chord strip includes every symbol.
        events = [
            {"pitch": "G4", "midi": 67, "duration_beats": 4.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 4.0, "beat": 0.0, "measure": 2},
            {"pitch": "B4", "midi": 71, "duration_beats": 4.0, "beat": 0.0, "measure": 3},
            {"pitch": "D5", "midi": 74, "duration_beats": 4.0, "beat": 0.0, "measure": 4},
        ]
        apply_melody_events(doc, str(verse["id"]), events, replace=True)
        before = [dict(e) for e in section_melody_events(verse)]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em Cm"))
        verse = ordered_sections(doc)[0]
        after = section_melody_events(verse)
        self.assertEqual([e.get("pitch") for e in after], [e.get("pitch") for e in before])
        score = build_section_score_model(
            events=after,
            chords=verse.get("chords") or [],
            key="G major",
            meter="4/4",
            bpm=96,
            title="V",
        )
        self.assertEqual(score["chord_labels"], ["G", "D", "Em", "Cm"])

    def test_section_switch_isolates_scores(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="x", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        secs = ordered_sections(doc)
        v1, v2 = secs[0], secs[1]
        apply_section_chords(doc, str(v1["id"]), parse_chord_paste("C F G C"))
        apply_melody_events(
            doc,
            str(v1["id"]),
            [{"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        apply_section_chords(doc, str(v2["id"]), parse_chord_paste("Am F C G"))
        apply_melody_events(
            doc,
            str(v2["id"]),
            [{"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        s1 = build_section_score_model(
            events=section_melody_events(v1),
            chords=v1.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="A",
        )
        s2 = build_section_score_model(
            events=section_melody_events(v2),
            chords=v2.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="B",
        )
        self.assertIn("C", s1["chord_labels"][0])
        self.assertIn("Am", s2["chord_labels"][0])
        self.assertEqual(section_melody_events(v1)[0]["pitch"], "C4")
        self.assertEqual(section_melody_events(v2)[0]["pitch"], "A4")

    def test_no_instrument_ownership_field(self) -> None:
        from composition_studio_page import _render_phase_melody

        src = inspect.getsource(_render_phase_melody)
        self.assertNotIn("instrument ownership", src.lower())
        self.assertNotIn("What instrument", src)


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestCompositionStructureAppTest(unittest.TestCase):
    HARNESS = str(Path(__file__).resolve().parents[1] / "composition_studio_welcome_harness.py")

    def test_welcome_still_renders(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))


if __name__ == "__main__":
    unittest.main()
