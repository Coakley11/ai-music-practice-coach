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
    apply_record_origin,
    build_section_record_timeline,
    delete_melody_event,
    nudge_event_pitch,
    prepare_armed_record_transport,
    set_event_duration,
    shift_event_onset,
    transcribe_hum_audio,
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
        timeline = prepare_armed_record_transport(doc, sid, recorder_start_delay_beats=0.0, count_in_bars=1)
        ss: dict = {}
        result = play_composer_preview(
            ss, doc, section_id=sid, include_melody=False, loops=1, count_in_bars=1
        )
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertFalse(result["include_melody"])
        self.assertEqual(result["bpm"], timeline["bpm"])
        self.assertEqual(result["meter"], timeline["meter"])
        self.assertEqual(timeline["origin"], "armed_count_in")
        self.assertFalse(timeline["sync_locked"])
        self.assertGreaterEqual(float(timeline["expected_duration_beats"]), 16.0)
        self.assertTrue(timeline["chord_changes"])

        hummed = [
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
            {"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 8.0, "measure": 3},
        ]
        aligned = align_events_to_record_timeline(hummed, timeline)
        self.assertEqual([e.get("pitch") for e in aligned], ["B4", "A4"])
        self.assertEqual(aligned[0]["chord"], "G")
        self.assertAlmostEqual(float(aligned[0]["beat"]), 0.0)
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

    def test_nonzero_recorder_delay_maps_first_event_to_backing_beat_and_chord(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Delay", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        verse["bars"] = 8
        sid = str(verse["id"])
        # Started the recorder 2 beats after backing/count-in origin, no extra count-in.
        timeline = apply_record_origin(
            build_section_record_timeline(doc, sid),
            recorder_start_delay_beats=2.0,
            count_in_beats=0.0,
            origin="armed_count_in",
        )
        self.assertAlmostEqual(float(timeline["recording_onset_beat"]), 2.0)
        self.assertAlmostEqual(float(timeline["backing_origin_in_capture_beats"]), -2.0)
        self.assertAlmostEqual(float(timeline["recorder_late_beats"]), 2.0)
        self.assertAlmostEqual(float(timeline["mic_lead_beats"]), 0.0)
        capture = [
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ]
        aligned = align_events_to_record_timeline(capture, timeline)
        self.assertEqual(len(aligned), 2)
        self.assertAlmostEqual(float(aligned[0]["beat"]), 2.0)
        self.assertEqual(aligned[0]["chord"], "C")
        self.assertAlmostEqual(float(aligned[1]["beat"]), 4.0)
        self.assertEqual(aligned[1]["chord"], "Am")

        # Count-in + late start: capture 0 is still in the count-in and must not land on beat 0.
        armed = prepare_armed_record_transport(
            doc, sid, recorder_start_delay_beats=2.0, count_in_bars=1
        )
        self.assertAlmostEqual(float(armed["count_in_beats"]), 4.0)
        self.assertAlmostEqual(float(armed["recording_onset_beat"]), -2.0)
        self.assertAlmostEqual(float(armed["backing_origin_in_capture_beats"]), 2.0)
        mixed = align_events_to_record_timeline(
            [
                {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
                {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 2.0, "measure": 1},
                {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 6.0, "measure": 2},
            ],
            armed,
        )
        self.assertEqual([e.get("pitch") for e in mixed], ["E4", "G4"])
        self.assertAlmostEqual(float(mixed[0]["beat"]), 0.0)
        self.assertEqual(mixed[0]["chord"], "C")
        self.assertAlmostEqual(float(mixed[1]["beat"]), 4.0)
        self.assertEqual(mixed[1]["chord"], "Am")

        transcribed = transcribe_hum_audio(b"", bpm=100, meter="4/4", key="C", timeline=armed)
        self.assertIn(transcribed["status"], {"unclear", "unavailable"})

    def test_primary_mic_first_lead_maps_capture_6_to_section_0(self) -> None:
        """Mic starts first; backing begins 2 beats later; 4-beat count-in.

        A note sung on section beat 0 appears at capture beat 6
        (lead 2 + count-in 4). section_beat = capture - backing_origin.
        """
        doc = bootstrap_from_vision(genre="Pop", song_idea="Lead", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        verse["bars"] = 8
        sid = str(verse["id"])
        timeline = apply_record_origin(
            build_section_record_timeline(doc, sid),
            mic_lead_beats=2.0,
            recorder_late_beats=0.0,
            count_in_beats=4.0,
            origin="armed_count_in",
        )
        self.assertAlmostEqual(float(timeline["mic_lead_beats"]), 2.0)
        self.assertAlmostEqual(float(timeline["recorder_late_beats"]), 0.0)
        self.assertAlmostEqual(float(timeline["count_in_beats"]), 4.0)
        self.assertAlmostEqual(float(timeline["backing_origin_in_capture_beats"]), 6.0)
        self.assertAlmostEqual(float(timeline["recording_onset_beat"]), -6.0)
        self.assertEqual(timeline["origin"], "armed_count_in")
        self.assertFalse(timeline["sync_locked"])

        capture = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 2.0, "measure": 1},
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 4.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 6.0, "measure": 2},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 10.0, "measure": 3},
        ]
        aligned = align_events_to_record_timeline(capture, timeline)
        self.assertEqual([e.get("pitch") for e in aligned], ["E4", "G4"])
        self.assertAlmostEqual(float(aligned[0]["beat"]), 0.0)
        self.assertEqual(aligned[0]["chord"], "C")
        self.assertAlmostEqual(float(aligned[1]["beat"]), 4.0)

        armed = prepare_armed_record_transport(
            doc, sid, mic_lead_beats=2.0, recorder_late_beats=0.0, count_in_bars=1
        )
        self.assertAlmostEqual(float(armed["backing_origin_in_capture_beats"]), 6.0)
        first = align_events_to_record_timeline(
            [{"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 6.0, "measure": 2}],
            armed,
        )
        self.assertEqual(len(first), 1)
        self.assertAlmostEqual(float(first[0]["beat"]), 0.0)
        self.assertEqual(first[0]["chord"], "C")

    def test_panel_offsets_prefer_mic_lead_over_late_alias(self) -> None:
        from composition_studio_page import _armed_record_offsets_from_panel

        lead, late = _armed_record_offsets_from_panel(
            {
                "composer_record_origin_mode_s1": "mic_first",
                "composer_mic_lead_s1": 2.0,
                "composer_record_delay_s1": 9.0,
            },
            "s1",
            bpm=120,
        )
        self.assertAlmostEqual(lead, 2.0)
        self.assertAlmostEqual(late, 0.0)
        lead, late = _armed_record_offsets_from_panel(
            {
                "composer_record_origin_mode_s1": "recorder_late",
                "composer_mic_lead_s1": 2.0,
                "composer_record_delay_s1": 3.0,
            },
            "s1",
            bpm=120,
        )
        self.assertAlmostEqual(lead, 0.0)
        self.assertAlmostEqual(late, 3.0)

    def test_hum_panel_render_exposes_origin_not_false_sync(self) -> None:
        import inspect

        from composition_studio_page import _render_hum_sing_panel

        src = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("prepare_armed_record_transport", src)
        self.assertIn("apply_record_origin", src)
        self.assertIn("mic_lead_beats", src)
        self.assertIn("backing_origin_in_capture_beats", src)
        self.assertIn("Backing began this many beats after I started recording", src)
        self.assertIn("Recorder started after backing", src)
        self.assertIn("Mark I'm recording now", src)
        self.assertIn("cannot start with the backing from one click", src)
        self.assertIn("count_in_bars=1", src)
        self.assertIn("Not a locked", src)
        self.assertNotIn("Play backing and record", src)
        self.assertNotIn("Recorder started late by (beats)", src)
        self.assertIn("▶ Hear the chords", src)
        self.assertIn("Record your melody over these chords.", src)
        self.assertIn("Notes landed on the wrong chord?", src)
        self.assertIn("progression_line", src)
        self.assertIn("span_events_across_section_timeline", src)
        self.assertIn("over the chords", src)
        self.assertNotIn("**1. Arm the microphone**", src)
        self.assertNotIn("**2. Start count-in + backing**", src)


class TestShapeAndRefineAcceptedMelody(unittest.TestCase):
    def _prepared(self):
        doc = bootstrap_from_vision(genre="Pop", song_idea="Shape", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
            {"pitch": "C5", "midi": 72, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
        ]
        apply_melody_events(doc, str(verse["id"]), events, replace=True, source="ai")
        apply_lyrics_text(doc, str(verse["id"]), "Home again now")
        return doc, verse

    def test_shape_rewrites_contour_keeps_rhythm_and_one_authority(self) -> None:
        from composition_melody_suggestions import apply_shaped_or_refined_melody

        doc, verse = self._prepared()
        sid = str(verse["id"])
        before = [dict(e) for e in section_melody_events(verse)]
        abc_before = build_abc_from_melody_events(before, key="C major", meter="4/4", bpm=100)
        sig_before = preview_signature(doc, section_id=sid, include_melody=True, loops=1)
        msg = apply_shaped_or_refined_melody(doc, sid, action="shape")
        self.assertTrue(msg)
        self.assertIn("Shaped", msg)
        after = section_melody_events(verse)
        self.assertEqual(len(after), len(before))
        self.assertEqual(
            [float(e.get("duration_beats") or 0) for e in after],
            [float(e.get("duration_beats") or 0) for e in before],
        )
        self.assertEqual(
            [float(e.get("beat") or 0) for e in after],
            [float(e.get("beat") or 0) for e in before],
        )
        self.assertNotEqual([e.get("midi") for e in after], [e.get("midi") for e in before])
        self.assertEqual(section_melody_events(verse), (verse.get("melody") or {}).get("events"))
        abc_after = build_abc_from_melody_events(after, key="C major", meter="4/4", bpm=100)
        self.assertNotEqual(abc_before, abc_after)
        self.assertNotEqual(
            sig_before,
            preview_signature(doc, section_id=sid, include_melody=True, loops=1),
        )
        play = play_composer_preview({}, doc, section_id=sid, include_melody=True, loops=1)
        self.assertTrue(play["ok"], play.get("reason"))
        self.assertTrue(section_lyric_alignment(verse))

    def test_refine_smooths_without_replacing_the_line(self) -> None:
        from composition_melody_suggestions import apply_shaped_or_refined_melody

        doc, verse = self._prepared()
        sid = str(verse["id"])
        before = [dict(e) for e in section_melody_events(verse)]
        msg = apply_shaped_or_refined_melody(doc, sid, action="refine")
        self.assertTrue(msg)
        self.assertIn("Refined", msg)
        after = section_melody_events(verse)
        self.assertEqual(len(after), len(before))
        self.assertEqual(
            [float(e.get("beat") or 0) for e in after],
            [float(e.get("beat") or 0) for e in before],
        )
        self.assertNotEqual([e.get("midi") for e in after], [e.get("midi") for e in before])
        leaps = [
            abs(int(after[i]["midi"]) - int(after[i - 1]["midi"]))
            for i in range(1, len(after))
        ]
        before_leaps = [
            abs(int(before[i]["midi"]) - int(before[i - 1]["midi"]))
            for i in range(1, len(before))
        ]
        self.assertLessEqual(max(leaps), max(before_leaps))
        self.assertTrue((verse.get("melody") or {}).get("edited"))

    def test_shape_refine_buttons_are_wired_through_persist(self) -> None:
        import inspect

        from composition_studio_page import _render_phase_melody

        src = inspect.getsource(_render_phase_melody)
        self.assertIn("Shape accepted melody", src)
        self.assertIn("Refine accepted melody", src)
        self.assertIn('action="shape"', src)
        self.assertIn('action="refine"', src)
        self.assertIn("apply_shaped_or_refined_melody", src)
        self.assertIn("_save_doc", src)
        self.assertIn("composer_melody_action_", src)


class TestSectionSwitchWithoutStaleState(unittest.TestCase):
    def _two_sections(self):
        doc = bootstrap_from_vision(genre="Pop", song_idea="Switch", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C F G C"))
        apply_melody_events(
            doc,
            str(verse["id"]),
            [{"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("Am F C G"))
        apply_melody_events(
            doc,
            str(chorus["id"]),
            [{"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        return doc, verse, chorus

    def test_select_active_section_persists_and_does_not_snap_back(self) -> None:
        from composition_session_state import COMPOSER_ACTIVE_KEY, COMPOSER_ACTIVE_SECTION_KEY, COMPOSER_FOCUS_LANE_KEY, COMPOSER_NEEDS_SEED_KEY
        from composition_studio_page import _hum_proposal_key, _select_active_section
        from composition_workspace_state_persistence import (
            COMPOSITION_WORKSPACE_STATE_KEY,
            gather_composition_workspace_from_session,
            project_composition_workspace_to_session,
            sync_composition_workspace_before_persist,
        )

        doc, verse, chorus = self._two_sections()
        ss: dict = {
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: str(verse["id"]),
            COMPOSER_FOCUS_LANE_KEY: "melody",
            COMPOSER_NEEDS_SEED_KEY: False,
            _hum_proposal_key(str(verse["id"])): {"status": "ok", "events": [{"pitch": "C4"}]},
        }
        _select_active_section(ss, doc, str(chorus["id"]))
        self.assertEqual(ss[COMPOSER_ACTIVE_SECTION_KEY], str(chorus["id"]))
        self.assertIsNone(ss.get(_hum_proposal_key(str(verse["id"]))))
        blob = gather_composition_workspace_from_session(ss)
        self.assertEqual(str(blob.get("active_section_id") or ""), str(chorus["id"]))
        # Hydrate must keep the live chorus — not snap back to a stale verse blob.
        ss[COMPOSITION_WORKSPACE_STATE_KEY] = {
            **blob,
            "active_section_id": str(verse["id"]),
        }
        project_composition_workspace_to_session(ss, overwrite=True)
        self.assertEqual(ss[COMPOSER_ACTIVE_SECTION_KEY], str(chorus["id"]))
        verse_events = section_melody_events(verse)
        chorus_events = section_melody_events(chorus)
        self.assertEqual(verse_events[0]["pitch"], "C4")
        self.assertEqual(chorus_events[0]["pitch"], "A4")
        sync_composition_workspace_before_persist(ss, reason="test")

    def test_nav_strip_uses_select_and_save(self) -> None:
        import inspect

        from composition_studio_page import _render_section_nav_strip, _select_active_section

        nav = inspect.getsource(_render_section_nav_strip)
        self.assertIn("_select_active_section", nav)
        sel = inspect.getsource(_select_active_section)
        self.assertIn("_save_doc", sel)
        self.assertIn("_clear_hum_proposal", sel)
        self.assertIn("invalidate_composer_preview", sel)


class TestTranscriptionOverChordProgression(unittest.TestCase):
    def test_events_map_across_every_chord_boundary_and_span_section(self) -> None:
        from composition_hum_transcription import (
            align_events_to_record_timeline,
            build_section_record_timeline,
            span_events_across_section_timeline,
        )

        doc = bootstrap_from_vision(genre="Pop", song_idea="Align", key="C major", bpm=100, meter="4/4")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
        verse["bars"] = 4
        sid = str(verse["id"])
        timeline = build_section_record_timeline(doc, sid)
        self.assertGreaterEqual(len(timeline.get("chord_changes") or []), 4)
        chords = [c["chord"] for c in timeline["chord_changes"][:4]]
        self.assertEqual(chords, ["C", "Am", "F", "G"])
        hummed = [
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 4.0, "measure": 2},
            {"pitch": "C5", "midi": 72, "duration_beats": 1.0, "beat": 8.0, "measure": 3},
            {"pitch": "B4", "midi": 71, "duration_beats": 1.0, "beat": 12.0, "measure": 4},
        ]
        aligned = align_events_to_record_timeline(hummed, timeline)
        self.assertEqual([e.get("chord") for e in aligned], ["C", "Am", "F", "G"])
        self.assertEqual([float(e.get("beat") or 0) for e in aligned], [0.0, 4.0, 8.0, 12.0])
        spanned = span_events_across_section_timeline(aligned, timeline)
        end = max(float(e.get("beat") or 0) + float(e.get("duration_beats") or 0) for e in spanned)
        self.assertGreaterEqual(end, float(timeline["expected_duration_beats"]) - 0.01)
        self.assertTrue(any(e.get("is_rest") for e in spanned))
        pitched = [e for e in spanned if not e.get("is_rest")]
        self.assertEqual([e.get("chord") for e in pitched], ["C", "Am", "F", "G"])
        apply_melody_events(doc, sid, aligned, replace=True, source="recorded")
        accepted = section_melody_events(verse)
        self.assertEqual([e.get("chord") or "" for e in accepted if e.get("chord")], ["C", "Am", "F", "G"])
        abc = build_abc_from_melody_events(spanned, key="C major", meter="4/4", bpm=100)
        self.assertTrue(abc)


if __name__ == "__main__":
    unittest.main()

