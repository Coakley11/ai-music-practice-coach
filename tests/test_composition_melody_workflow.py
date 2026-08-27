"""Full-section melody coverage, canonical edits, and record-over-backing."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_accepted_melody_edits,
    apply_lyrics_text,
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_lyric_alignment,
    section_melody_events,
    section_playback_bars,
)
from composition_hum_transcription import (
    align_events_to_record_timeline,
    build_section_record_timeline,
    delete_melody_event,
    nudge_event_pitch,
    set_event_duration,
    shift_event_onset,
)
from composition_melody_notation import build_abc_from_melody_events
from composition_melody_suggestions import (
    expand_melody_events_to_section,
    melody_section_coverage,
    suggest_melody_concepts,
)
from composition_preview import play_composer_preview, preview_signature


class TestFullSectionMelodyCoverage(unittest.TestCase):
    def _verse(self):
        doc = bootstrap_from_vision(genre="Pop", song_idea="Coverage", key="C major", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        verse["bars"] = 8
        return doc, verse

    def test_suggested_melody_spans_declared_section_and_each_chord(self) -> None:
        doc, verse = self._verse()
        concepts = suggest_melody_concepts(doc, verse, "lyrical", "simple", limit=2)
        self.assertGreaterEqual(len(concepts), 1)
        events = list(concepts[0].get("events") or [])
        self.assertTrue(events)
        bars = section_playback_bars(doc, verse)
        self.assertGreaterEqual(bars, 4)
        coverage = melody_section_coverage(events, doc, verse)
        self.assertTrue(coverage["covers"], coverage)
        self.assertTrue(coverage["aligned"], coverage)
        self.assertGreaterEqual(coverage["end"], coverage["target_beats"] - 0.51)
        self.assertLessEqual(coverage["start"], 0.26)
        self.assertFalse(coverage["missing_chords"])

    def test_fragment_is_expanded_to_section_timeline(self) -> None:
        doc, verse = self._verse()
        fragment = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        expanded = expand_melody_events_to_section(fragment, doc, verse, key="C")
        coverage = melody_section_coverage(expanded, doc, verse)
        self.assertTrue(coverage["covers"], coverage)
        self.assertTrue(coverage["aligned"], coverage)
        self.assertGreater(len(expanded), len(fragment))


class TestCanonicalMelodyEdits(unittest.TestCase):
    def _prepared(self):
        doc = bootstrap_from_vision(genre="Pop", song_idea="Edit", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C F G C"))
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ]
        apply_melody_events(doc, str(verse["id"]), events, replace=True, source="ai")
        apply_lyrics_text(doc, str(verse["id"]), "Home again now")
        return doc, verse

    def test_pitch_duration_remove_and_timing_update_staff_play_persist_lyrics(self) -> None:
        doc, verse = self._prepared()
        sid = str(verse["id"])
        before = section_melody_events(verse)
        abc_before = build_abc_from_melody_events(before, key="C major", meter="4/4", bpm=100)
        sig_before = preview_signature(doc, section_id=sid, include_melody=True, loops=1)
        align_before = section_lyric_alignment(verse)
        self.assertTrue(align_before)

        pitched = nudge_event_pitch(before, 0, semitones=2, key="C")
        apply_accepted_melody_edits(doc, sid, pitched)
        after_pitch = section_melody_events(verse)
        self.assertEqual(after_pitch[0]["midi"], 62)
        abc_pitch = build_abc_from_melody_events(after_pitch, key="C major", meter="4/4", bpm=100)
        self.assertNotEqual(abc_before, abc_pitch)
        self.assertNotEqual(
            sig_before,
            preview_signature(doc, section_id=sid, include_melody=True, loops=1),
        )
        self.assertTrue(section_lyric_alignment(verse))

        stretched = set_event_duration(after_pitch, 1, 2.0, meter="4/4")
        apply_accepted_melody_edits(doc, sid, stretched)
        after_dur = section_melody_events(verse)
        self.assertEqual(after_dur[1]["duration_beats"], 2.0)
        self.assertEqual(after_dur[2]["beat"], 3.0)

        shifted = shift_event_onset(after_dur, 2, 0.5, meter="4/4", max_beats=32.0)
        apply_accepted_melody_edits(doc, sid, shifted)
        after_shift = section_melody_events(verse)
        self.assertAlmostEqual(float(after_shift[2]["beat"]), 3.5, places=5)

        trimmed = delete_melody_event(after_shift, 1, meter="4/4")
        apply_accepted_melody_edits(doc, sid, trimmed)
        final = section_melody_events(verse)
        self.assertEqual(len(final), 2)
        self.assertEqual(final[0]["midi"], 62)
        abc_final = build_abc_from_melody_events(final, key="C major", meter="4/4", bpm=100)
        self.assertNotEqual(abc_pitch, abc_final)
        play = play_composer_preview({}, doc, section_id=sid, include_melody=True, loops=1)
        self.assertTrue(play["ok"], play.get("reason"))
        self.assertTrue(play["include_melody"])
        alignment = section_lyric_alignment(verse)
        self.assertTrue(alignment)
        self.assertTrue(all(row.get("event_index") is None or row["event_index"] < len(final) for row in alignment))

    def test_edits_do_not_create_a_second_melody_store(self) -> None:
        doc, verse = self._prepared()
        sid = str(verse["id"])
        melody = verse.get("melody") or {}
        self.assertIn("events", melody)
        apply_accepted_melody_edits(
            doc,
            sid,
            nudge_event_pitch(section_melody_events(verse), 0, semitones=-1, key="C"),
        )
        melody_after = verse.get("melody") or {}
        self.assertEqual(set(melody_after.keys()), set(melody.keys()) | set(melody_after.keys()))
        self.assertTrue(melody_after.get("edited"))
        self.assertEqual(section_melody_events(verse), melody_after.get("events"))


class TestRecordOverBacking(unittest.TestCase):
    def test_play_backing_and_timeline_share_section_reference(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Record", key="G major", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        verse["bars"] = 8
        sid = str(verse["id"])
        timeline = build_section_record_timeline(doc, sid)
        ss: dict = {}
        result = play_composer_preview(ss, doc, section_id=sid, include_melody=False, loops=1)
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertFalse(result["include_melody"])
        self.assertEqual(result["bpm"], timeline["bpm"])
        self.assertEqual(result["meter"], timeline["meter"])
        self.assertGreaterEqual(float(timeline["expected_duration_beats"]), 16.0)
        self.assertTrue(timeline["chord_changes"])

        hummed = [
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
        ]
        aligned = align_events_to_record_timeline(hummed, timeline)
        self.assertEqual(aligned[0]["chord"], "G")
        apply_melody_events(doc, sid, aligned, replace=True, source="recorded")
        accepted = section_melody_events(verse)
        edited = nudge_event_pitch(accepted, 0, semitones=1, key="G")
        apply_accepted_melody_edits(doc, sid, edited)
        self.assertEqual(section_melody_events(verse)[0]["midi"], 72)
        audition = play_composer_preview(
            ss, doc, section_id=sid, include_melody=True, loops=1
        )
        self.assertTrue(audition["ok"])
        self.assertTrue(audition["include_melody"])


if __name__ == "__main__":
    unittest.main()
