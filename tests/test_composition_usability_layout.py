"""Usability slice: chord-over-staff, local players, record workspace."""

from __future__ import annotations

import copy
import inspect
import unittest

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
    set_workflow_phase,
)
from composition_melody_notation import (
    align_notes_to_chords,
    build_live_chord_follow_html,
    build_section_score_model,
    span_at_beat,
    timed_chord_spans,
)
from composition_preview import (
    COMPOSER_PREVIEW_SLOT_KEY,
    play_composer_preview,
    render_local_composer_playback,
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    COMPOSER_NEEDS_SEED_KEY,
)
from composition_studio_page import (
    _attach_local_preview,
    _play_chord_idea,
    _render_hum_sing_panel,
    _render_melody_concept_card,
    _render_melody_staff,
    _render_section_transport,
    _render_suggestion_card,
    render_composition_studio_page,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


class FakeStreamlit:
    def __init__(self) -> None:
        self.markdowns: list[str] = []
        self.audio_calls: list[tuple] = []
        self.buttons: list[str] = []

    def markdown(self, text: str, **_kwargs) -> None:
        self.markdowns.append(str(text))

    def caption(self, text: str, **_kwargs) -> None:
        self.markdowns.append(str(text))

    def columns(self, _spec):
        return (self, self)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def button(self, label: str, **_kwargs) -> bool:
        self.buttons.append(str(label))
        return False

    def audio(self, data, **kwargs) -> None:
        self.audio_calls.append((data, kwargs))

    def rerun(self) -> None:
        return None


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss


def _song():
    doc = bootstrap_from_vision(genre="Pop", song_idea="Layout", key="C major", bpm=100, meter="4/4")
    apply_structure_template(doc, "simple")
    verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    apply_melody_events(
        doc,
        str(verse["id"]),
        [
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
            {"pitch": "C5", "midi": 72, "duration_beats": 2.0, "beat": 8.0, "measure": 3},
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 12.0, "measure": 4},
        ],
        replace=True,
    )
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("F G C C"))
    apply_melody_events(
        doc,
        str(chorus["id"]),
        [{"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
        replace=True,
    )
    return doc, verse, chorus


class TestChordSymbolToNoteAlignment(unittest.TestCase):
    def test_timed_spans_keep_repeats_and_half_bar_changes(self) -> None:
        chords = [
            {"chord": "C", "bars": 1},
            {"chord": "C", "bars": 1},
            {"chord": "F", "duration_beats": 2.0},
            {"chord": "G", "duration_beats": 2.0},
        ]
        spans = timed_chord_spans(chords, meter="4/4")
        self.assertEqual([s["chord"] for s in spans], ["C", "C", "F", "G"])
        self.assertAlmostEqual(spans[0]["start_beat"], 0.0)
        self.assertAlmostEqual(spans[1]["start_beat"], 4.0)
        self.assertAlmostEqual(spans[2]["start_beat"], 8.0)
        self.assertAlmostEqual(spans[2]["duration_beats"], 2.0)
        self.assertAlmostEqual(spans[3]["start_beat"], 10.0)
        self.assertEqual(span_at_beat(spans, 4.0)["chord"], "C")
        self.assertEqual(span_at_beat(spans, 9.0)["chord"], "F")
        self.assertEqual(span_at_beat(spans, 10.0)["chord"], "G")

    def test_notes_and_rests_map_across_meter_and_section_boundary(self) -> None:
        chords = parse_chord_paste("C F G")
        events = [
            {"pitch": "E4", "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "rest", "is_rest": True, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "A4", "duration_beats": 1.0, "beat": 3.0},
            {"pitch": "B4", "duration_beats": 1.0, "beat": 6.0},
        ]
        rows = align_notes_to_chords(events, chords, meter="3/4", section_bars=3)
        self.assertEqual([r["chord"] for r in rows], ["C", "C", "F", "G"])
        self.assertTrue(rows[1]["is_rest"])
        score = build_section_score_model(
            events=events,
            chords=chords,
            key="C major",
            meter="3/4",
            bpm=90,
            title="Waltz",
            section_bars=3,
        )
        self.assertIn('"C"', score["abc"])
        self.assertIn('"F"', score["abc"])
        self.assertIn('"G"', score["abc"])
        self.assertIn('data-onset="0"', score["chord_strip_html"])
        self.assertIn("composer-score-measures", score["chord_strip_html"])
        self.assertIn('data-measure="1"', score["chord_strip_html"])
        self.assertGreaterEqual(len(score["timed_spans"]), 3)
        self.assertEqual(score["note_chord_alignment"][0]["chord"], "C")

    def test_multiple_notes_per_chord_and_full_section_pad(self) -> None:
        chords = parse_chord_paste("C Am F G")
        events = [
            {"pitch": "E4", "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "G4", "duration_beats": 1.0, "beat": 1.0},
        ]
        score = build_section_score_model(
            events=events,
            chords=chords,
            key="C major",
            meter="4/4",
            bpm=100,
            title="Verse",
            section_bars=4,
        )
        self.assertEqual([s["chord"] for s in score["timed_spans"][:4]], ["C", "Am", "F", "G"])
        self.assertEqual([r["chord"] for r in score["note_chord_alignment"]], ["C", "C"])
        self.assertIn('"C"', score["abc"])
        self.assertIn('"Am"', score["abc"])
        self.assertIn('"F"', score["abc"])
        self.assertIn('"G"', score["abc"])
        self.assertIn('data-measure="1"', score["chord_strip_html"])
        self.assertIn('data-measure="2"', score["chord_strip_html"])
        self.assertIn('data-measure="3"', score["chord_strip_html"])
        self.assertIn('data-measure="4"', score["chord_strip_html"])
        self.assertRegex(score["chord_strip_html"], r'data-measure="1"[^>]*>C<')
        self.assertRegex(score["chord_strip_html"], r'data-measure="2"[^>]*>Am<')

    def test_staff_render_uses_aligned_model(self) -> None:
        src = inspect.getsource(_render_melody_staff)
        self.assertIn("note_chord_alignment", src)
        self.assertIn("chord_strip_html", src)
        self.assertIn("Notes over chords", src)
        self.assertNotIn("progression_line", src)


class TestLocalPlayerPlacement(unittest.TestCase):
    def test_player_stays_on_armed_slot_only(self) -> None:
        doc, verse, _chorus = _song()
        ss: dict = {}
        self.assertTrue(
            _play_chord_idea(
                ss,
                doc,
                str(verse["id"]),
                ["C", "Am"],
                loops=1,
                slot="chords:idea-a",
                label="Playing · Idea A",
            )
        )
        self.assertEqual(ss.get(COMPOSER_PREVIEW_SLOT_KEY), "chords:idea-a")
        fake = FakeStreamlit()
        self.assertFalse(render_local_composer_playback(fake, ss, slot="chords:idea-b"))
        self.assertFalse(fake.audio_calls)
        self.assertTrue(render_local_composer_playback(fake, ss, slot="chords:idea-a"))
        self.assertTrue(fake.audio_calls)
        joined = "\n".join(fake.markdowns)
        self.assertIn('data-preview-slot="chords:idea-a"', joined)
        self.assertIn("Playing · Idea A", joined)

    def test_page_attaches_players_locally_not_at_bottom(self) -> None:
        page = inspect.getsource(render_composition_studio_page)
        self.assertNotIn("flush_composer_preview_dock", page)
        self.assertIn("_attach_local_preview", inspect.getsource(_render_section_transport))
        self.assertIn("_attach_local_preview", inspect.getsource(_render_suggestion_card))
        self.assertIn("_attach_local_preview", inspect.getsource(_render_melody_concept_card))
        self.assertIn("slot=", inspect.getsource(_play_chord_idea))
        attach = inspect.getsource(_attach_local_preview)
        self.assertIn("render_local_composer_playback", attach)


class TestSectionSwitchAndActiveChord(unittest.TestCase):
    def test_section_scores_do_not_share_alignment(self) -> None:
        doc, verse, chorus = _song()
        s1 = build_section_score_model(
            events=section_melody_events(verse),
            chords=verse.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="Verse",
            section_bars=4,
        )
        s2 = build_section_score_model(
            events=section_melody_events(chorus),
            chords=chorus.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="Chorus",
            section_bars=4,
        )
        self.assertEqual(s1["note_chord_alignment"][0]["chord"], "C")
        self.assertEqual(s2["note_chord_alignment"][0]["chord"], "F")
        self.assertIn('"C"', s1["abc"])
        self.assertIn('"F"', s2["abc"])
        self.assertNotEqual(s1["abc"], s2["abc"])

    def test_live_follow_marks_active_chord_class(self) -> None:
        spans = timed_chord_spans(parse_chord_paste("C F G"), meter="4/4")
        html = build_live_chord_follow_html(spans, bpm=100, count_in_beats=4.0, section_label="Now")
        self.assertIn("composer-live-chord", html)
        self.assertIn("is-active", html)
        self.assertIn('data-bpm="100"', html)
        self.assertIn('data-count-in="4"', html)
        self.assertIn(">C<", html)
        self.assertIn(">F<", html)
        self.assertIn(">G<", html)
        hum = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("build_live_chord_follow_html", hum)
        self.assertIn("record-workspace:", hum)


class TestRecordingTimelineAndReboot(unittest.TestCase):
    def test_record_workspace_keeps_signed_origin_and_alignment(self) -> None:
        hum = inspect.getsource(_render_hum_sing_panel)
        self.assertIn("prepare_armed_record_transport", hum)
        self.assertIn("apply_record_origin", hum)
        self.assertIn("span_events_across_section_timeline", hum)
        self.assertIn("backing_origin_in_capture_beats", hum)
        self.assertIn("mic_lead_beats", hum)
        self.assertIn("Record your melody over these chords.", hum)
        self.assertIn("Notes landed on the wrong chord?", hum)
        self.assertNotIn("**1. Arm the microphone**", hum)

    def test_preview_uses_same_section_chords_as_score(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        score = build_section_score_model(
            events=section_melody_events(verse),
            chords=verse.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="Verse",
            section_bars=4,
        )
        result = play_composer_preview({}, doc, section_id=sid, include_melody=True, loops=1)
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertEqual(list(result["chords"])[:4], [s["chord"] for s in score["timed_spans"][:4]])

    def test_cold_restore_keeps_aligned_score(self) -> None:
        from composition_workspace_state_persistence import (
            prepare_composition_workspace_for_render,
            sync_composition_workspace_before_persist,
        )

        doc, verse, chorus = _song()
        set_workflow_phase(doc, "melody")
        ss: dict = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_LIBRARY_KEY: {str(doc["id"]): copy.deepcopy(doc)},
            COMPOSER_ACTIVE_SECTION_KEY: str(chorus["id"]),
            COMPOSER_FOCUS_LANE_KEY: "melody",
            COMPOSER_NEEDS_SEED_KEY: False,
        }
        sync_composition_workspace_before_persist(ss, reason="composer_edit")
        blob = build_music_disk_state(_FakeSt(ss))
        fresh = _FakeSt({})
        apply_music_disk_state(
            fresh,
            blob,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_composition_workspace_for_render(fresh.session_state)
        restored = fresh.session_state.get(COMPOSER_ACTIVE_KEY)
        self.assertEqual(fresh.session_state.get(COMPOSER_ACTIVE_SECTION_KEY), str(chorus["id"]))
        rverse = ordered_sections(restored)[0]
        rchorus = next(s for s in ordered_sections(restored) if s.get("id") == chorus["id"])
        vscore = build_section_score_model(
            events=section_melody_events(rverse),
            chords=rverse.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="Verse",
            section_bars=4,
        )
        cscore = build_section_score_model(
            events=section_melody_events(rchorus),
            chords=rchorus.get("chords") or [],
            key="C major",
            meter="4/4",
            bpm=100,
            title="Chorus",
            section_bars=4,
        )
        self.assertEqual(vscore["note_chord_alignment"][0]["chord"], "C")
        self.assertEqual(cscore["note_chord_alignment"][0]["chord"], "F")
        self.assertIn('"C"', vscore["abc"])
        self.assertIn('"F"', cscore["abc"])
        self.assertEqual(section_melody_events(rverse)[0]["pitch"], "E4")
        self.assertEqual(section_melody_events(rchorus)[0]["pitch"], "A4")


class TestMelodyWorkspaceUnclutter(unittest.TestCase):
    def test_side_panels_are_on_demand(self) -> None:
        from composition_studio_page import (
            COMPOSER_MELODY_SIDE_PANEL_KEY,
            _render_melody_side_tools,
            _render_phase_melody,
            render_composition_studio_page,
        )

        side = inspect.getsource(_render_melody_side_tools)
        self.assertIn("Guided Path", side)
        self.assertIn("Song Settings", side)
        self.assertIn("Song Sections", side)
        self.assertIn("Write the line", side)
        self.assertIn("Now working on:", side)
        self.assertIn(COMPOSER_MELODY_SIDE_PANEL_KEY, side)
        melody = inspect.getsource(_render_phase_melody)
        self.assertIn("_render_melody_side_tools", melody)
        self.assertIn("Now writing:", melody)
        self.assertNotIn("_render_compact_song_settings", melody)
        self.assertNotIn("_render_section_nav_strip", melody)
        self.assertNotIn("_render_journey_rail", melody)
        self.assertNotIn("_render_section_workspace_header", melody)
        page = inspect.getsource(render_composition_studio_page)
        self.assertIn('if phase != "melody"', page)

    def test_repeated_chord_sits_over_each_measure(self) -> None:
        chords = [{"chord": "C", "bars": 1}, {"chord": "C", "bars": 1}, {"chord": "F", "bars": 1}]
        score = build_section_score_model(
            events=[
                {"pitch": "E4", "duration_beats": 4.0, "beat": 0.0},
                {"pitch": "G4", "duration_beats": 4.0, "beat": 4.0},
                {"pitch": "A4", "duration_beats": 4.0, "beat": 8.0},
            ],
            chords=chords,
            key="C major",
            meter="4/4",
            bpm=100,
            title="Repeat C",
            section_bars=3,
        )
        html = score["chord_strip_html"]
        self.assertRegex(html, r'data-measure="1"[^>]*>C<')
        self.assertRegex(html, r'data-measure="2"[^>]*>C<')
        self.assertRegex(html, r'data-measure="3"[^>]*>F<')
        self.assertGreaterEqual(score["abc"].count('"C"'), 2)
        self.assertIn('"F"', score["abc"])


class TestMelodyChoiceCopy(unittest.TestCase):
    def test_blurbs_are_one_sentence_not_lessons(self) -> None:
        from composition_melody_suggestions import melody_choice_blurb, suggest_melody_concepts

        doc, verse, _chorus = _song()
        concepts = suggest_melody_concepts(doc, verse, "energetic", "simple", limit=3)
        self.assertTrue(concepts)
        for concept in concepts:
            blurb = melody_choice_blurb(concept)
            self.assertTrue(concept.get("name"))
            self.assertEqual(blurb.count("."), 1, blurb)
            lower = blurb.lower()
            self.assertNotIn("designed to sit", lower)
            self.assertNotIn("full harmony", lower)
            self.assertNotIn("chorus or pre-chorus", lower)
            self.assertNotIn("how hooks", lower)
            self.assertLessEqual(len(blurb.split()), 16, blurb)
        climb = next((c for c in concepts if "climb" in str(c.get("name") or "").lower()), concepts[0])
        self.assertTrue(melody_choice_blurb(climb))


if __name__ == "__main__":
    unittest.main()
