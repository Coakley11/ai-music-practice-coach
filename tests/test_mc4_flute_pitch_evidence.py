"""MC4 — pitch evidence comes from the soloist's notes, not from accompaniment or frame counts.

Human flute take (Instrument = Flute, backing audible through speakers) reported "Estimated
center pitch: A♯3" and Pitch 42/100 with "intonation drifts" / "sustains trend flat". Causes:

* the centre was the median of *all voiced pYIN frames* (no confidence threshold) — long backing
  bleed between phrases outweighed the flute's shorter notes;
* the flute window started at A♯3 (C4 − 2), so sub-range bass energy piled up at that floor;
* "notes" were runs of voiced frames, so a legato phrase's intervals were scored as drift.
"""

from __future__ import annotations

import unittest

import numpy as np

from recording_analysis import AudioFeatures, _intonation_stats_from_f0, _pyin_features, compute_performance_scores

SR = 22050


def _tone(f: float, dur: float, amp: float, vib: float = 0.0) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * f * t + vib * np.sin(2 * np.pi * 5 * t)) + 0.2 * np.sin(4 * np.pi * f * t)
    env = np.minimum(1.0, np.minimum(t / 0.03, (dur - t) / 0.06))
    return (amp * x * env).astype(np.float32)


def flute_phrase_with_bass() -> tuple[np.ndarray, int]:
    """Six short flute notes (E5 … A5) plus a long, quieter A♯2 / C3 'speaker bleed' bass."""
    notes = [659.3, 784.0, 880.0, 784.0, 659.3, 587.3]
    flute = np.concatenate([np.concatenate([_tone(f, 0.45, 0.4, vib=0.15), np.zeros(int(0.05 * SR), np.float32)])
                            for f in notes])
    bass = np.concatenate([_tone(116.5, 4.0, 0.12), _tone(130.8, 4.0, 0.12)])
    y = np.zeros(bass.size, np.float32)
    y[: flute.size] += flute
    y[: bass.size] += bass
    return y, SR


def _features(**kw: object) -> AudioFeatures:
    base = dict(duration=8.0, sr=SR, tempo=126.0, beat_times=np.zeros(0), beat_interval_cv=0.1, tempo_drift_pct=0.0,
                onset_times=np.zeros(0), onset_strength_mean=1.0, onset_density=2.0, groove_tightness=0.5,
                pitch_median_hz=None, pitch_note=None, pitch_cents_std=None, pitch_sharp_bias=0.0, voiced_ratio=0.0,
                rms=np.zeros(4), dyn_range=0.1, dyn_flatness=0.2, spectral_centroid_mean=1500.0, zcr_mean=0.05,
                energy_curve=np.zeros(0), waveform_peaks=[], waveform_times=[])
    base.update(kw)
    return AudioFeatures(**base)  # type: ignore[arg-type]


def _f0(notes_hz: list[tuple[float, int]], *, gap: int = 0) -> np.ndarray:
    frames: list[float] = []
    for hz, n in notes_hz:
        frames.extend([hz] * n)
        frames.extend([float("nan")] * gap)
    return np.asarray(frames, dtype=float)


class TestSoloistPitchEvidence(unittest.TestCase):
    def test_centre_is_median_of_notes_not_frame_occupancy(self) -> None:
        # One very long low-register note + six short melody notes around E5.
        f0 = _f0([(261.6, 300)] + [(659.3, 12), (698.5, 12), (784.0, 12), (659.3, 12), (587.3, 12), (659.3, 12)], gap=2)
        stats = _intonation_stats_from_f0(f0, midi_range=(60, 106))
        self.assertEqual(stats["pitch_event_count"], 7)
        self.assertEqual(stats["pitch_note"], "E5")  # frame median would have been C4

    def test_sub_range_bass_never_becomes_the_flute_centre(self) -> None:
        y, sr = flute_phrase_with_bass()
        stats = _pyin_features(y, sr, midi_range=(60, 106))
        self.assertNotIn(stats["pitch_note"], ("A♯3", "A#3", "B3", "C3", "A♯2"))
        self.assertGreaterEqual(int(str(stats["pitch_note"])[-1]), 5)
        self.assertEqual(stats["pitch_event_count"], 6)  # exactly the six flute notes
        generic = _pyin_features(y, sr)  # without the instrument range the bass counts as a note
        self.assertGreater(generic["pitch_event_count"], stats["pitch_event_count"])

    def test_pitch_is_right_at_browser_sample_rates(self) -> None:
        # Browser takes are 48 kHz; pYIN used to assume 22.05 kHz and read every note ~13.5 semitones low.
        for sr in (44100, 48000):
            t = np.arange(int(3.0 * sr)) / sr
            notes = [659.3, 784.0, 880.0, 784.0, 659.3, 587.3]
            y = np.concatenate([0.4 * np.sin(2 * np.pi * f * t[: int(0.45 * sr)]) for f in notes]).astype(np.float32)
            y = np.concatenate([np.concatenate([seg, np.zeros(int(0.05 * sr), np.float32)])
                                for seg in np.split(y, len(notes))])
            stats = _pyin_features(y, sr, midi_range=(60, 106))
            self.assertEqual(stats["pitch_note"], "E5", sr)
            self.assertLess(abs(stats["pitch_sharp_bias"]), 15, sr)

    def test_legato_phrase_is_not_scored_as_drift(self) -> None:
        # A legato scale with no gaps between notes: each note is stable.
        f0 = _f0([(hz, 14) for hz in (523.3, 587.3, 659.3, 698.5, 784.0, 880.0, 987.8, 1046.5)])
        stats = _intonation_stats_from_f0(f0, midi_range=(60, 106))
        self.assertEqual(stats["pitch_event_count"], 8)
        self.assertLess(stats["pitch_cents_std"], 5)
        # A genuine drift on one held note is still caught.
        drift = np.asarray([440.0 * 2 ** (c / 1200.0) for c in np.linspace(-40, 40, 96)])
        self.assertGreater(_intonation_stats_from_f0(drift)["pitch_cents_std"], 15)

    def test_boundary_pileup_and_low_confidence_are_rejected(self) -> None:
        floor = 246.9  # B3: one semitone below the flute range = the pYIN search floor
        f0 = _f0([(floor, 40), (659.3, 10), (784.0, 10), (659.3, 10)], gap=2)
        prob = np.ones(len(f0)); prob[54:64] = 0.05  # one note pYIN barely believes in
        stats = _intonation_stats_from_f0(f0, voiced_prob=prob, midi_range=(60, 106))
        self.assertEqual(stats["pitch_rejected"]["out_of_range"], 1)
        self.assertEqual(stats["pitch_rejected"]["low_confidence"], 1)
        self.assertEqual(stats["pitch_event_count"], 2)
        self.assertNotEqual(stats["pitch_note"], "B3")

    def test_bleed_level_notes_are_set_aside(self) -> None:
        f0 = _f0([(659.3, 12)] * 6 + [(523.3, 12)] * 3, gap=2)
        rms = np.ones(len(f0)); rms[6 * 14:] = 0.05  # the last three notes are bleed-quiet
        stats = _intonation_stats_from_f0(f0, rms=rms, midi_range=(60, 106), instrument_specific=True)
        self.assertEqual(stats["pitch_rejected"]["bleed"], 3)
        self.assertEqual(stats["pitch_note"], "E5")

    def test_low_evidence_gives_no_centre_and_a_neutral_score(self) -> None:
        from recording_analysis import _pitch_analysis

        stats = _intonation_stats_from_f0(_f0([(659.3, 12), (784.0, 12)], gap=2), midi_range=(60, 106))
        self.assertEqual(stats["pitch_evidence"], "low")
        self.assertIsNone(stats["pitch_note"])
        f = _features(pitch_cents_std=60.0, voiced_ratio=0.1, pitch_sharp_bias=-30.0, pitch_evidence="low",
                      pitch_event_count=2, pitch_tail_drop_cents=-30.0, pitch_rejected={"out_of_range": 4})
        neutral = compute_performance_scores(f, "Flute")["pitch"]
        self.assertGreaterEqual(neutral, 70)  # not penalized for what was not clearly heard
        heard = _features(pitch_cents_std=60.0, voiced_ratio=0.1, pitch_sharp_bias=-30.0, pitch_evidence="high",
                          pitch_event_count=12, pitch_note="E5")
        self.assertLess(compute_performance_scores(heard, "Flute")["pitch"], neutral)  # real evidence still counts
        out = _pitch_analysis(f, "Flute", {"display_key": "C"})
        text = " ".join(out["findings"])
        self.assertIn("Not enough clearly attributed Flute notes", text)
        self.assertIn("set aside as likely accompaniment", text)
        self.assertNotIn("drift", text)
        self.assertNotIn("trend flat", text)
        self.assertNotIn("Pitch contour was unclear", text)


class TestMissionVersusChordToneScore(unittest.TestCase):
    RESULT = {
        "aligned": True, "score": 100,
        "chord_detail": [
            {"chord": "C/E", "notes": 3, "chord_tone_pct": 100, "colour_examples": []},
            {"chord": "G", "notes": 8, "chord_tone_pct": 50, "colour_examples": ["A (9th)"]},
            {"chord": "C", "notes": 6, "chord_tone_pct": 33, "colour_examples": ["B (major 7th)"]},
        ],
    }

    def test_explanation_text(self) -> None:
        from mission_span_take_evaluation import mission_vs_chord_tone_note

        text = mission_vs_chord_tone_note(self.RESULT)
        self.assertIn("You satisfied the Mission at every required chord change.", text)
        self.assertIn("Mission Compliance checks the target moments; the broader Chord-tone targeting score "
                      "evaluates all notes played across the pass.", text)
        self.assertIn("Across the analyzed pass: C/E 100% chord tones · G 50% chord tones · C 33% chord tones.", text)
        self.assertIn("B (major 7th)", text)
        self.assertEqual(mission_vs_chord_tone_note({"aligned": False, "score": 100}), "")

    def test_note_sits_next_to_the_chord_tone_card(self) -> None:
        from mission_analysis_ui import render_mission_analysis_html

        html = render_mission_analysis_html({
            "mission_results": [{"label": "Chord-tone targeting", "score": 56}, {"label": "Rhythm", "score": 70}],
            "mission_evaluation_active": True, "overall_improv_score": 63, "span_mission": self.RESULT,
        })
        self.assertIn("Mission vs. this score:", html)
        self.assertEqual(html.count("Mission vs. this score:"), 1)  # only on the chord-tone card
        self.assertIn("Overall Performance Coaching: 63%", html)

    def test_colour_tones_are_not_called_wrong(self) -> None:
        from mission_span_recording_context import build_timeline
        from mission_span_take_evaluation import build_harmony, note_function

        tl = build_timeline([{"chord": "C/E", "bars": 1}, {"chord": "G", "bars": 1}, {"chord": "C", "bars": 1}], meter="4/4")
        h = build_harmony({"practice_key": "C", "timeline": tl})
        self.assertEqual(note_function(h, 4, 2), "chord")   # E over C
        self.assertEqual(note_function(h, 11, 2), "colour")  # B = major 7th over C
        self.assertEqual(note_function(h, 9, 1), "colour")   # A = 9th over G
        self.assertEqual(note_function(h, 1, 2), "other")    # C♯ over C: chromatic / approach


if __name__ == "__main__":
    unittest.main()
