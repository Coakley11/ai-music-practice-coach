"""Chords/Melody QA: compare removal, refinements, transcription, chord audio."""

from __future__ import annotations

import inspect
import io
import math
import unittest
import wave

import numpy as np

from backing_audio import bass_note, chord_notes, generate_backing_track
from composition_document import (
    apply_accepted_melody_edits,
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
)
from composition_hum_transcription import (
    align_events_to_record_timeline,
    build_section_record_timeline,
    quantize_beats,
    segment_f0_track,
    segments_to_melody_events,
    stabilize_midi_octaves,
    transcribe_hum_audio,
)
from composition_melody_suggestions import (
    MELODY_REFINEMENTS,
    add_rhythmic_variety,
    apply_melody_refinement_to_section,
    apply_shaped_or_refined_melody,
    refine_accepted_melody_events,
    shape_accepted_melody_events,
)
from composition_preview import generate_preview_wav, play_composer_preview, preview_signature
from composition_studio_page import (
    _compare_queue_key,
    _push_melody_undo,
    _render_accepted_melody_tools,
    _render_melody_concept_card,
    _render_phase_melody,
    _render_suggestion_card,
    _undo_melody_adjustment,
)


def _song():
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="QA",
        title="QA Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("F G C C"))
    return doc, verse, chorus


class TestCompareRemoved(unittest.TestCase):
    def test_suggestion_card_has_no_compare_button(self) -> None:
        src = inspect.getsource(_render_suggestion_card)
        self.assertNotIn("+ Compare", src)
        self.assertNotIn("Comparing ✓", src)
        self.assertIn("▶ Preview", src)
        self.assertIn("Use this", src)

    def test_compare_queue_helper_still_namespaced(self) -> None:
        self.assertEqual(_compare_queue_key("sec-1"), "composer_compare_sec-1")

    def test_suggestion_melody_cards_are_preview_and_accept_only(self) -> None:
        src = inspect.getsource(_render_melody_concept_card)
        self.assertNotIn("Edit this melody", src)
        self.assertIn("▶ Preview with chords", src)
        self.assertIn("Use this melody", src)

    def test_accepted_controls_sit_directly_below_score(self) -> None:
        src = inspect.getsource(_render_phase_melody)
        score_at = src.find("_render_section_score_view")
        tools_at = src.find("_render_accepted_melody_tools")
        explore_at = src.find("Explore melody ideas")
        self.assertGreater(score_at, 0)
        self.assertGreater(tools_at, score_at)
        self.assertGreater(explore_at, tools_at)
        tools_src = inspect.getsource(_render_accepted_melody_tools)
        self.assertIn("1. Shape / refine accepted melody", tools_src)
        self.assertIn("2. More local refinements", tools_src)
        self.assertIn("3. Advanced phrase editor", tools_src)
        self.assertIn("Undo previous adjustment", tools_src)


class TestMelodyRefinementsAreMusical(unittest.TestCase):
    def test_smoother_and_rhythm_change_accepted_events(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        apply_melody_events(
            doc,
            sid,
            [
                {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
                {"pitch": "B4", "midi": 71, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
                {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
            ],
            replace=True,
        )
        before = [int(e.get("midi") or 0) for e in section_melody_events(verse)]
        apply_melody_refinement_to_section(doc, sid, "smoother")
        after_smooth = [int(e.get("midi") or 0) for e in section_melody_events(verse)]
        self.assertNotEqual(before, after_smooth)
        apply_melody_refinement_to_section(doc, sid, "rhythm")
        after_rhythm = section_melody_events(verse)
        self.assertNotEqual(len(after_rhythm), 3)
        self.assertTrue(any(float(e.get("duration_beats") or 0) == 0.5 for e in after_rhythm))

    def test_shape_refine_and_undo(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        seed = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 1.0, "measure": 1},
        ]
        apply_melody_events(doc, sid, seed, replace=True)
        ss: dict = {}
        _push_melody_undo(ss, sid, section_melody_events(verse))
        apply_shaped_or_refined_melody(doc, sid, action="shape")
        self.assertNotEqual(
            [e.get("midi") for e in section_melody_events(verse)],
            [60, 67],
        )
        self.assertTrue(_undo_melody_adjustment(ss, doc, sid))
        self.assertEqual([e.get("midi") for e in section_melody_events(verse)], [60, 67])

    def test_rhythmic_variety_keeps_pitches(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "is_rest": False},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0, "is_rest": False},
        ]
        out = add_rhythmic_variety(events, key="C")
        pitches = [e.get("pitch") for e in out if not e.get("is_rest")]
        self.assertTrue(set(pitches) <= {"C4", "E4"})
        self.assertGreater(len(out), 2)

    def test_every_local_refinement_changes_accepted_events(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        seed = [
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
            {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 4.0, "measure": 2},
            {"pitch": "C5", "midi": 72, "duration_beats": 2.0, "beat": 6.0, "measure": 2},
        ]
        apply_melody_events(doc, sid, seed, replace=True)
        seen: list[tuple] = []
        for rid, _label, _hint in MELODY_REFINEMENTS:
            before = [
                (e.get("midi"), e.get("duration_beats"), e.get("beat"), e.get("is_rest"))
                for e in section_melody_events(verse)
            ]
            apply_melody_refinement_to_section(doc, sid, rid)
            after = [
                (e.get("midi"), e.get("duration_beats"), e.get("beat"), e.get("is_rest"))
                for e in section_melody_events(verse)
            ]
            self.assertNotEqual(before, after, msg=f"{rid} was a no-op")
            seen.append(tuple(after))
        self.assertEqual(len(seen), len(MELODY_REFINEMENTS))

    def test_refinements_are_composable_from_current_events(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        apply_melody_events(
            doc,
            sid,
            [
                {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0, "measure": 1},
                {"pitch": "G4", "midi": 67, "duration_beats": 2.0, "beat": 2.0, "measure": 1},
            ],
            replace=True,
        )
        apply_melody_refinement_to_section(doc, sid, "smoother")
        mid = [e.get("midi") for e in section_melody_events(verse)]
        apply_melody_refinement_to_section(doc, sid, "rhythm")
        later = section_melody_events(verse)
        self.assertNotEqual([e.get("midi") for e in later], mid)
        self.assertGreater(len(later), 2)


class TestTranscriptionEvidence(unittest.TestCase):
    def test_stabilize_octave_folds_stray_jump(self) -> None:
        self.assertEqual(stabilize_midi_octaves([60, 72, 64]), [60, 60, 64])

    def test_segment_repeated_notes_and_rest(self) -> None:
        import numpy as np

        times = np.linspace(0, 2.0, 80)
        f0 = np.full(80, np.nan)
        f0[0:20] = 261.63  # C4
        f0[30:50] = 261.63  # repeated C4 after rest
        f0[55:75] = 329.63  # E4
        segs = segment_f0_track(f0, times)
        kinds = [s.get("kind") for s in segs]
        self.assertIn("note", kinds)
        self.assertGreaterEqual(sum(1 for k in kinds if k == "note"), 2)
        events = segments_to_melody_events(segs, bpm=120, meter="4/4", key="C")
        pitched = [e for e in events if not e.get("is_rest")]
        self.assertGreaterEqual(len(pitched), 2)
        self.assertTrue(all("midi" in e and "beat" in e and "duration_beats" in e for e in pitched))

    def test_quantize_and_chord_alignment_origin(self) -> None:
        self.assertEqual(quantize_beats(0.92, meter="4/4"), 1.0)
        doc, verse, _chorus = _song()
        timeline = build_section_record_timeline(doc, str(verse["id"]))
        timeline["backing_origin_in_capture_beats"] = 4.0  # count-in
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 4.0, "is_rest": False},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 5.0, "is_rest": False},
        ]
        aligned = align_events_to_record_timeline(events, timeline)
        self.assertAlmostEqual(float(aligned[0]["beat"]), 0.0)
        self.assertIn(str(aligned[0].get("pitch") or ""), {"C4", "C"})
        self.assertTrue("duration_beats" in aligned[0])
        self.assertEqual(str(aligned[0].get("chord") or ""), "C")
        self.assertEqual(str(aligned[1].get("chord") or ""), "C")

    def test_note_spanning_chord_change_keeps_onset_chord(self) -> None:
        doc, verse, _chorus = _song()
        timeline = build_section_record_timeline(doc, str(verse["id"]))
        events = [
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 3.0, "is_rest": False},
            {"pitch": "A4", "midi": 69, "duration_beats": 1.0, "beat": 4.5, "is_rest": False},
        ]
        aligned = align_events_to_record_timeline(events, timeline)
        self.assertEqual(str(aligned[0].get("chord") or ""), "C")
        self.assertEqual(str(aligned[1].get("chord") or ""), "Am")
        self.assertAlmostEqual(float(aligned[0]["beat"]), 3.0)
        self.assertAlmostEqual(float(aligned[1]["beat"]), 4.5)


def _pcm16_wav(samples: np.ndarray, sr: int = 22050) -> bytes:
    clipped = np.clip(np.asarray(samples, dtype=float), -1.0, 1.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes((clipped * 32767.0).astype(np.int16).tobytes())
    return buf.getvalue()


def _tone_phrase(notes: list[tuple[float, float]], *, sr: int = 22050, harmonic=0.0, noise=0.0) -> bytes:
    chunks: list[np.ndarray] = []
    for hz, dur in notes:
        n = max(1, int(sr * dur))
        t = np.arange(n, dtype=float) / sr
        wave_s = np.sin(2.0 * math.pi * hz * t)
        if harmonic:
            wave_s += float(harmonic) * np.sin(2.0 * math.pi * hz * 2.0 * t)
        if noise:
            wave_s += float(noise) * np.random.default_rng(7).normal(0.0, 1.0, size=n)
        env = np.ones(n)
        fade = min(n // 8, int(0.02 * sr))
        if fade:
            env[:fade] *= np.linspace(0.0, 1.0, fade)
            env[-fade:] *= np.linspace(1.0, 0.0, fade)
        chunks.append(wave_s * env * 0.35)
    return _pcm16_wav(np.concatenate(chunks), sr)


class TestSyntheticTranscription(unittest.TestCase):
    def test_sustained_and_stepwise_sine_tones(self) -> None:
        wav = _tone_phrase([(261.63, 0.7), (293.66, 0.7), (329.63, 0.7)])
        result = transcribe_hum_audio(wav, bpm=120, meter="4/4", key="C")
        if not result.get("available"):
            self.skipTest("librosa transcription unavailable")
        pitched = [e for e in result.get("events") or [] if not e.get("is_rest")]
        self.assertGreaterEqual(len(pitched), 2, result)
        pcs = [int(e["midi"]) % 12 for e in pitched]
        self.assertTrue(set(pcs) <= {0, 2, 4}, msg=str([(e.get("pitch"), e.get("midi"), e.get("beat")) for e in pitched]))
        self.assertTrue(all("beat" in e and "duration_beats" in e for e in pitched))

    def test_flute_like_harmonic_and_noise(self) -> None:
        wav = _tone_phrase([(523.25, 0.8), (587.33, 0.8)], harmonic=0.45, noise=0.04)
        result = transcribe_hum_audio(wav, bpm=100, meter="4/4", key="C")
        if not result.get("available"):
            self.skipTest("librosa transcription unavailable")
        pitched = [e for e in result.get("events") or [] if not e.get("is_rest")]
        self.assertGreaterEqual(len(pitched), 1, result)
        pcs = {int(e["midi"]) % 12 for e in pitched}
        self.assertTrue(pcs & {0, 2}, msg=str([(e.get("pitch"), e.get("midi")) for e in pitched]))

    def test_repeated_note_not_flattened(self) -> None:
        wav = _tone_phrase([(261.63, 0.45), (0.0, 0.25), (261.63, 0.45)])
        # zero-hz rest via silence
        silence = np.zeros(int(22050 * 0.25))
        first = np.sin(2.0 * math.pi * 261.63 * np.arange(int(22050 * 0.5)) / 22050.0)
        third = np.sin(2.0 * math.pi * 261.63 * np.arange(int(22050 * 0.5)) / 22050.0)
        wav = _pcm16_wav(np.concatenate([first * 0.4, silence, third * 0.4]))
        result = transcribe_hum_audio(wav, bpm=120, meter="4/4", key="C")
        if not result.get("available"):
            self.skipTest("librosa transcription unavailable")
        pitched = [e for e in result.get("events") or [] if not e.get("is_rest")]
        self.assertGreaterEqual(len(pitched), 2, result)


class TestChordAudioMatchesSymbols(unittest.TestCase):
    def _pcs(self, symbol: str) -> set[int]:
        return {int(n) % 12 for n in chord_notes(symbol)}

    def test_quality_pitch_classes(self) -> None:
        self.assertEqual(self._pcs("C"), {0, 4, 7})
        self.assertEqual(self._pcs("Am"), {9, 0, 4})
        self.assertEqual(self._pcs("G7"), {7, 11, 2, 5})
        self.assertEqual(self._pcs("Cmaj7"), {0, 4, 7, 11})
        self.assertEqual(self._pcs("Dm7"), {2, 5, 9, 0})
        self.assertEqual(self._pcs("Gsus4"), {7, 0, 2})
        self.assertEqual(self._pcs("Bdim"), {11, 2, 5})
        self.assertEqual(self._pcs("Bm7b5"), {11, 2, 5, 9})
        self.assertEqual(self._pcs("Caug"), {0, 4, 8})
        self.assertEqual(self._pcs("Cadd9"), {0, 4, 7, 2})
        self.assertEqual(self._pcs("G7#5"), {7, 11, 3, 5})
        self.assertEqual(self._pcs("C7b5"), {0, 4, 6, 10})
        self.assertEqual(self._pcs("C/E"), {0, 4, 7})
        self.assertEqual(int(bass_note("C/E")) % 12, 4)
        self.assertEqual(int(bass_note("G/B")) % 12, 11)

    def test_preview_authority_matches_displayed_symbols(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        apply_section_chords(
            doc,
            sid,
            [
                {"chord": "Cmaj7", "bars": 1},
                {"chord": "G7", "bars": 1},
                {"chord": "Am7", "bars": 1},
                {"chord": "Fadd9", "bars": 1},
            ],
        )
        playback = chords_for_playback(doc, section_id=sid)
        self.assertEqual([str(c).split()[0] for c in playback][:4], ["Cmaj7", "G7", "Am7", "Fadd9"])
        result = play_composer_preview({}, doc, section_id=sid, include_melody=False, loops=1)
        self.assertTrue(result.get("ok"), result)
        self.assertEqual(list(result.get("chords") or [])[:4], playback[:4])
        for symbol in playback[:4]:
            self.assertGreaterEqual(len(chord_notes(symbol)), 3)

    def test_half_bar_insert_and_section_change_keep_authority(self) -> None:
        doc, verse, chorus = _song()
        apply_section_chords(
            doc,
            str(verse["id"]),
            [
                {"chord": "C:2|G:2", "bars": 1},
                {"chord": "Am", "bars": 1},
                {"chord": "F", "bars": 1},
            ],
        )
        v = chords_for_playback(doc, section_id=str(verse["id"]))
        c = chords_for_playback(doc, section_id=str(chorus["id"]))
        self.assertTrue(any("C" in str(sym) and "G" in str(sym) for sym in v), v)
        self.assertNotEqual(v, c)
        played = play_composer_preview({}, doc, section_id=str(verse["id"]), loops=1)
        self.assertTrue(played.get("ok"), played)
        self.assertEqual(list(played.get("chords") or [])[:3], v[:3])

    def test_rendered_audio_chroma_includes_quality_tones(self) -> None:
        wav = generate_backing_track(
            ["Cmaj7"],
            bpm=80,
            loops=1,
            style="Ballad",
            level="Beginner",
            song_title="QA",
            song_artist="",
            time_signature="4/4",
        )
        self.assertTrue(wav)
        from composition_preview import _wav_to_mono_floats

        mono, sr = _wav_to_mono_floats(bytes(wav))
        start = int(0.2 * sr)
        end = min(len(mono), int(1.4 * sr))
        x = np.asarray(mono[start:end], dtype=float)
        window = x * np.hanning(len(x))
        spec = np.abs(np.fft.rfft(window))
        freqs = np.fft.rfftfreq(len(window), 1.0 / sr)
        chroma = np.zeros(12)
        for mag, hz in zip(spec, freqs):
            if 90.0 < hz < 1400.0 and mag > 0:
                midi = 69.0 + 12.0 * math.log2(hz / 440.0)
                chroma[int(round(midi)) % 12] += float(mag)
        expected = {0, 4, 7, 11}
        top = set(np.argsort(chroma)[-6:])
        self.assertTrue(expected <= top or len(expected & top) >= 3, msg=f"chroma top={top} vals={chroma}")

    def test_preview_uses_active_section_chords(self) -> None:
        doc, verse, chorus = _song()
        v_chords = chords_for_playback(doc, section_id=str(verse["id"]))
        c_chords = chords_for_playback(doc, section_id=str(chorus["id"]))
        self.assertNotEqual(v_chords, c_chords)
        sig_v = preview_signature(doc, section_id=str(verse["id"]))
        sig_c = preview_signature(doc, section_id=str(chorus["id"]))
        self.assertNotEqual(sig_v, sig_c)
        wav_v = generate_preview_wav(doc, section_id=str(verse["id"]), include_melody=False)
        wav_c = generate_preview_wav(doc, section_id=str(chorus["id"]), include_melody=False)
        self.assertTrue(wav_v)
        self.assertTrue(wav_c)
        self.assertNotEqual(wav_v, wav_c)


if __name__ == "__main__":
    unittest.main()
