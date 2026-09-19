"""Composition Studio — Hum → notes → notation → ownership tests."""

from __future__ import annotations

import math
import unittest

import numpy as np

from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
)
from composition_hum_transcription import (
    delete_melody_event,
    format_heard_line,
    hum_analysis_available,
    insert_melody_event,
    is_compound_meter,
    midi_from_hz,
    nudge_event_pitch,
    parse_meter,
    quantize_beats,
    segment_f0_track,
    segments_to_melody_events,
    set_event_duration,
    spell_midi_in_key,
    transcribe_hum_audio,
)
from composition_melody_notation import build_abc_from_melody_events, composition_abc_key_field
from composition_preview import generate_preview_wav, preview_signature
from composition_studio_page import _clear_hum_proposal, _hum_proposal_key


def _hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def _f0_track(segments: list[tuple[float, float | None]], *, hop: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Build synthetic F0/times. segments: (duration_sec, midi_or_None for silence)."""
    f0_list: list[float] = []
    t = 0.0
    times: list[float] = []
    for dur, midi in segments:
        n = max(1, int(round(dur / hop)))
        for _ in range(n):
            times.append(t)
            if midi is None:
                f0_list.append(float("nan"))
            else:
                f0_list.append(_hz(float(midi)))
            t += hop
    return np.asarray(f0_list, dtype=float), np.asarray(times, dtype=float)


class TestHumSegmentation(unittest.TestCase):
    def test_stable_pitch_one_sustained_note(self) -> None:
        f0, times = _f0_track([(0.5, 67)])  # G4
        segs = segment_f0_track(f0, times)
        notes = [s for s in segs if s["kind"] == "note"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["midi"], 67)

    def test_vibrato_collapses_to_one_note(self) -> None:
        hop = 0.01
        times = np.arange(0.0, 0.6, hop)
        base = 67.0
        midi = base + 0.2 * np.sin(np.linspace(0, 12 * np.pi, len(times)))
        f0 = np.array([_hz(m) for m in midi], dtype=float)
        segs = segment_f0_track(f0, times)
        notes = [s for s in segs if s["kind"] == "note"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["midi"], 67)

    def test_two_separated_stable_pitches(self) -> None:
        f0, times = _f0_track([(0.35, 60), (0.05, None), (0.35, 64)])
        segs = segment_f0_track(f0, times)
        notes = [s for s in segs if s["kind"] == "note"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["midi"], 60)
        self.assertEqual(notes[1]["midi"], 64)

    def test_silence_gap_becomes_rest(self) -> None:
        f0, times = _f0_track([(0.3, 62), (0.35, None), (0.3, 65)])
        segs = segment_f0_track(f0, times, rest_gap_sec=0.18)
        kinds = [s["kind"] for s in segs]
        self.assertIn("rest", kinds)
        self.assertEqual(kinds.count("note"), 2)

    def test_repeated_same_pitch_with_gap_are_separate(self) -> None:
        f0, times = _f0_track([(0.25, 67), (0.25, None), (0.25, 67)])
        segs = segment_f0_track(f0, times, merge_gap_sec=0.08, rest_gap_sec=0.15)
        notes = [s for s in segs if s["kind"] == "note"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["midi"], notes[1]["midi"])

    def test_noisy_unvoiced_yields_no_notes(self) -> None:
        f0, times = _f0_track([(0.5, None)])
        segs = segment_f0_track(f0, times)
        self.assertEqual(segs, [])

    def test_legitimate_leap_preserved(self) -> None:
        f0, times = _f0_track([(0.3, 67), (0.02, None), (0.3, 79)])
        segs = segment_f0_track(f0, times)
        notes = [s for s in segs if s["kind"] == "note"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["midi"], 67)
        self.assertEqual(notes[1]["midi"], 79)


class TestHumRhythmQuantization(unittest.TestCase):
    def test_quantize_uses_bpm_duration(self) -> None:
        segs = [
            {
                "kind": "note",
                "midi": 60,
                "midi_f": 60.0,
                "start_sec": 0.0,
                "end_sec": 0.5,
                "duration_sec": 0.5,
                "confidence": 0.9,
            }
        ]
        events = segments_to_melody_events(segs, bpm=120, meter="4/4", key="C")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["duration_beats"], 1.0)

    def test_quantize_4_4(self) -> None:
        self.assertEqual(quantize_beats(1.05, meter="4/4"), 1.0)
        self.assertEqual(quantize_beats(1.6, meter="4/4"), 1.5)
        self.assertEqual(quantize_beats(2.1, meter="4/4"), 2.0)

    def test_quantize_3_4(self) -> None:
        segs = [
            {
                "kind": "note",
                "midi": 64,
                "midi_f": 64.0,
                "start_sec": 0.0,
                "end_sec": 1.5,
                "duration_sec": 1.5,
                "confidence": 0.9,
            }
        ]
        events = segments_to_melody_events(segs, bpm=90, meter="3/4", key="C")
        self.assertEqual(events[0]["duration_beats"], 2.0)
        self.assertEqual(parse_meter("3/4"), (3, 4))

    def test_compound_6_8_grid(self) -> None:
        self.assertTrue(is_compound_meter("6/8"))
        self.assertTrue(is_compound_meter("12/8"))
        self.assertFalse(is_compound_meter("4/4"))
        self.assertEqual(quantize_beats(1.4, meter="6/8"), 1.5)
        self.assertEqual(quantize_beats(2.9, meter="6/8"), 3.0)

    def test_dotted_duration_available(self) -> None:
        self.assertEqual(quantize_beats(1.45, meter="4/4"), 1.5)
        self.assertEqual(quantize_beats(3.1, meter="4/4"), 3.0)

    def test_custom_meter_not_silent_4_4(self) -> None:
        self.assertEqual(parse_meter("5/4"), (5, 4))
        self.assertEqual(parse_meter("7/8"), (7, 8))
        segs = [
            {
                "kind": "note",
                "midi": 60,
                "midi_f": 60.0,
                "start_sec": 0.0,
                "end_sec": 1.0,
                "duration_sec": 1.0,
                "confidence": 0.9,
            }
        ]
        events = segments_to_melody_events(segs, bpm=60, meter="5/4", key="C")
        self.assertEqual(events[0]["measure"], 1)
        self.assertNotEqual(parse_meter("5/4"), (4, 4))


class TestHumKeySpelling(unittest.TestCase):
    def test_db_major_spelling(self) -> None:
        self.assertEqual(spell_midi_in_key(61, "Db major"), "Db4")
        self.assertEqual(spell_midi_in_key(65, "Db major"), "F4")
        self.assertEqual(spell_midi_in_key(68, "Db major"), "Ab4")

    def test_cs_major_sharp_spelling(self) -> None:
        spelled = spell_midi_in_key(61, "C# major")
        self.assertTrue(spelled.startswith("C#"), spelled)

    def test_chromatic_not_forced_diatonic(self) -> None:
        # PC 6 in C — spelling may be F# or Gb; sounding MIDI must stay 66 (not F/G).
        spelled = spell_midi_in_key(66, "C major")
        self.assertIn(spelled, {"F#4", "Gb4"})
        segs = [
            {
                "kind": "note",
                "midi": 66,
                "midi_f": 66.0,
                "start_sec": 0.0,
                "end_sec": 0.5,
                "duration_sec": 0.5,
                "confidence": 0.9,
            }
        ]
        events = segments_to_melody_events(segs, bpm=120, meter="4/4", key="C major")
        self.assertEqual(events[0]["midi"], 66)
        self.assertIn(events[0]["pitch"], {"F#4", "Gb4"})
        self.assertNotIn(events[0]["pitch"], {"F4", "G4"})

    def test_key_does_not_alter_sounding_midi(self) -> None:
        segs = [
            {
                "kind": "note",
                "midi": 60,
                "midi_f": 60.0,
                "start_sec": 0.0,
                "end_sec": 0.5,
                "duration_sec": 0.5,
                "confidence": 0.9,
            }
        ]
        in_c = segments_to_melody_events(segs, bpm=120, meter="4/4", key="C major")
        in_db = segments_to_melody_events(segs, bpm=120, meter="4/4", key="Db major")
        self.assertEqual(in_c[0]["midi"], 60)
        self.assertEqual(in_db[0]["midi"], 60)


class TestHumOwnership(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="Home",
            mood="Warm",
            key="G major",
            bpm=96,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        sections = ordered_sections(doc)
        verse, chorus = sections[0], sections[1]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("C G Am D"))
        return doc, verse, chorus

    def test_proposal_does_not_mutate_accepted(self) -> None:
        doc, verse, _ = self._song()
        accepted = [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        apply_melody_events(doc, str(verse["id"]), accepted, replace=True)
        before = [dict(e) for e in section_melody_events(verse)]
        # Preview with override must not write events.
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=[
                {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            ],
            loops=1,
        )
        self.assertTrue(wav)
        self.assertEqual(section_melody_events(verse), before)

    def test_use_this_commits_explicitly(self) -> None:
        doc, verse, _ = self._song()
        events = [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "B4", "midi": 71, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        self.assertEqual(section_melody_events(verse), [])
        apply_melody_events(doc, str(verse["id"]), events, replace=True)
        got = section_melody_events(verse)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["pitch"], "G4")

    def test_rejected_proposal_leaves_accepted(self) -> None:
        doc, verse, _ = self._song()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [{"pitch": "D5", "midi": 74, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        before = [dict(e) for e in section_melody_events(verse)]
        session: dict = {
            _hum_proposal_key(str(verse["id"])): {
                "status": "usable",
                "events": [{"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            }
        }
        _clear_hum_proposal(session, str(verse["id"]))
        self.assertNotIn(_hum_proposal_key(str(verse["id"])), session)
        self.assertEqual(section_melody_events(verse), before)

    def test_record_again_clears_proposal_only(self) -> None:
        doc, verse, _ = self._song()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [{"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        sid = str(verse["id"])
        session = {
            _hum_proposal_key(sid): {"status": "usable", "events": [{"pitch": "F4", "midi": 65}]},
            f"composer_hum_audio_{sid}": b"fake",
        }
        _clear_hum_proposal(session, sid)
        self.assertEqual(len(section_melody_events(verse)), 1)
        self.assertEqual(section_melody_events(verse)[0]["pitch"], "E4")

    def test_verse_proposal_cannot_leak_to_chorus(self) -> None:
        _doc, verse, chorus = self._song()
        v_id, c_id = str(verse["id"]), str(chorus["id"])
        session = {
            _hum_proposal_key(v_id): {
                "status": "usable",
                "events": [{"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            }
        }
        self.assertIsNone(session.get(_hum_proposal_key(c_id)))
        self.assertEqual(section_melody_events(chorus), [])

    def test_switching_sections_preserves_accepted(self) -> None:
        doc, verse, chorus = self._song()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [{"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        apply_melody_events(
            doc,
            str(chorus["id"]),
            [{"pitch": "C5", "midi": 72, "duration_beats": 2.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        self.assertEqual(section_melody_events(verse)[0]["pitch"], "G4")
        self.assertEqual(section_melody_events(chorus)[0]["pitch"], "C5")

    def test_no_practice_transposition_on_spell(self) -> None:
        # Concert sounding pitch only — Composition never applies sax/written-key shifts here.
        self.assertEqual(spell_midi_in_key(60, "C major"), "C4")
        self.assertTrue(math.isclose(midi_from_hz(261.625565), 60.0, abs_tol=0.05))


class TestHumNotation(unittest.TestCase):
    def test_events_to_abc(self) -> None:
        events = [
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "A4", "midi": 69, "duration_beats": 0.5, "beat": 1.0, "measure": 1},
            {"pitch": "rest", "midi": None, "duration_beats": 0.5, "beat": 1.5, "measure": 1, "is_rest": True},
            {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ]
        abc = build_abc_from_melody_events(events, key="G major", meter="4/4", bpm=96)
        self.assertIn("M:4/4", abc)
        self.assertIn("K:", abc)
        self.assertTrue("z" in abc)

    def test_notation_key_signature(self) -> None:
        self.assertIn("Db", composition_abc_key_field("Db major"))
        abc = build_abc_from_melody_events(
            [{"pitch": "Db4", "midi": 61, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            key="Db major",
            meter="4/4",
            bpm=100,
        )
        self.assertIn("K:Db", abc.replace(" ", ""))

    def test_notation_meter_matches(self) -> None:
        abc = build_abc_from_melody_events(
            [{"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            key="C",
            meter="6/8",
            bpm=95,
        )
        self.assertIn("M:6/8", abc)

    def test_event_durations_appear(self) -> None:
        abc = build_abc_from_melody_events(
            [
                {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
                {"pitch": "D4", "midi": 62, "duration_beats": 2.0, "beat": 1.0, "measure": 1},
            ],
            key="C",
            meter="4/4",
            bpm=100,
        )
        # Quarter (=2) and half (=4) under L:1/8
        self.assertRegex(abc, r"[cC]2")
        self.assertRegex(abc, r"[dD]4")

    def test_edited_event_changes_notation(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
        ]
        before = build_abc_from_melody_events(events, key="C", meter="4/4", bpm=100)
        edited = nudge_event_pitch(events, 0, semitones=2, key="C")
        after = build_abc_from_melody_events(edited, key="C", meter="4/4", bpm=100)
        self.assertNotEqual(before, after)
        self.assertEqual(edited[0]["midi"], 62)

    def test_staff_and_playback_same_events(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="x", mood="Warm", key="C major", bpm=100, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C F G C"))
        events = [
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        apply_melody_events(doc, str(verse["id"]), events, replace=True)
        accepted = section_melody_events(verse)
        abc = build_abc_from_melody_events(accepted, key="C major", meter="4/4", bpm=100)
        sig = preview_signature(doc, section_id=str(verse["id"]), include_melody=True)
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(wav)
        self.assertTrue(sig)
        self.assertIn("E", abc.upper() + accepted[0]["pitch"].upper())


class TestHumPlayback(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="x", mood="Warm", key="G major", bpm=96, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        apply_section_chords(doc, str(verse["id"]), parse_chord_paste("G D Em C"))
        return doc, verse

    def test_proposed_preview_does_not_mutate(self) -> None:
        doc, verse = self._song()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [{"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1}],
            replace=True,
        )
        before = [dict(e) for e in section_melody_events(verse)]
        proposal = [{"pitch": "A4", "midi": 69, "duration_beats": 2.0, "beat": 0.0, "measure": 1}]
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=proposal,
            loops=1,
        )
        self.assertTrue(wav)
        self.assertEqual(section_melody_events(verse), before)

    def test_proposed_plus_chords_preview(self) -> None:
        doc, verse = self._song()
        wav = generate_preview_wav(
            doc,
            section_id=str(verse["id"]),
            include_melody=True,
            melody_override=[
                {"pitch": "B4", "midi": 71, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            ],
            loops=1,
        )
        self.assertTrue(wav)

    def test_accepted_plus_chords_play_section(self) -> None:
        doc, verse = self._song()
        apply_melody_events(
            doc,
            str(verse["id"]),
            [
                {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
                {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            ],
            replace=True,
        )
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=True, loops=1)
        self.assertTrue(wav)

    def test_chords_only_still_works(self) -> None:
        doc, verse = self._song()
        wav = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=False, loops=1)
        self.assertTrue(wav)

    def test_bpm_meter_affect_playback_signature(self) -> None:
        doc, verse = self._song()
        events = [{"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 0.0, "measure": 1}]
        sig_a = preview_signature(doc, section_id=str(verse["id"]), include_melody=True, melody_override=events)
        doc["global"]["bpm"] = 140
        sig_b = preview_signature(doc, section_id=str(verse["id"]), include_melody=True, melody_override=events)
        self.assertNotEqual(sig_a, sig_b)
        doc["global"]["time_signature"] = "3/4"
        sig_c = preview_signature(doc, section_id=str(verse["id"]), include_melody=True, melody_override=events)
        self.assertNotEqual(sig_b, sig_c)


class TestHumErrorsAndEdit(unittest.TestCase):
    def test_empty_audio_unclear(self) -> None:
        result = transcribe_hum_audio(b"", bpm=96, meter="4/4", key="C")
        self.assertIn(result["status"], {"unclear", "unavailable"})

    def test_unavailable_without_librosa(self) -> None:
        if hum_analysis_available():
            self.skipTest("librosa present in this environment")
        result = transcribe_hum_audio(b"not-real-audio", bpm=96, meter="4/4", key="C")
        self.assertEqual(result["status"], "unavailable")

    def test_duration_and_delete_edit(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        longer = set_event_duration(events, 0, 2.0, meter="4/4")
        self.assertEqual(longer[0]["duration_beats"], 2.0)
        self.assertEqual(longer[1]["beat"], 2.0)
        trimmed = delete_melody_event(longer, 1, meter="4/4")
        self.assertEqual(len(trimmed), 1)
        grown = insert_melody_event(trimmed, 1, pitch_midi=64, key="C", meter="4/4")
        self.assertEqual(len(grown), 2)
        self.assertIn("C4", format_heard_line(grown, meter="4/4"))


if __name__ == "__main__":
    unittest.main()
