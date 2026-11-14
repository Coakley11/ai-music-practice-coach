"""Issue 79 - Tone Sustain Practice measures the playing, not the silence around it.

Three defects, each reproduced here against audio whose truth is known exactly:

1. **silence in the volume measurement.** A steady E5 with a second of silence at each end scored
   4% for volume consistency where the same tone trimmed scored 95%. The silence was most of the
   RMS spread.
2. **a saturating pitch score.** ``100 - 4.5 * stdev`` reaches zero at 22 cents, so a quarter-tone
   waver, a semitone change and an octave jump were all 0% and the number could not say which had
   happened. Onset and release frames were in the same standard deviation.
3. **an assumed target octave.** The selector offered pitch classes and the analysis stapled octave
   4 on, so a flute's E5 was reported as ~1169 cents sharp of E4 while the readout said "E5".

The assertions below are about the arithmetic, not about staying inside 0-100: a 60-cent drift must
score lower than a 20-cent one, a vibrato must be *identified* as a vibrato, an octave jump must be
distinguishable from a semitone, and a recording that cannot be measured must not come back as 0%.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.tone_test_signals import (  # noqa: E402
    E5_HZ,
    SR,
    noise,
    ramp,
    signal_catalog,
    silence,
    tone,
    wav_bytes,
)
from tone_sustain_analysis import (  # noqa: E402
    MIN_SUSTAIN_SEC,
    PITCH_STABILITY_ANCHORS,
    SCORING_VERSION,
    VOLUME_CONSISTENCY_ANCHORS,
    correct_detection_octaves,
    explain,
    frames_from_arrays,
    hz_to_midi,
    join_dropouts,
    longest_run,
    measure_tone,
    midi_to_note_label,
    pitch_stability_from_spread,
    resolve_target,
    robust_spread,
    tuning_against_target,
    usable_mask,
    volume_consistency_from_fluctuation,
)
from tuner_tone import analyze_tone_practice  # noqa: E402

# pyin is slow, and every case below wants a different view of the same handful of recordings.
_ANALYSED: dict[str, object] = {}


def analysed(name: str):
    """The analysis of one catalog signal, computed once for the whole suite."""
    if name not in _ANALYSED:
        audio, target, _ = signal_catalog()[name]
        _ANALYSED[name] = analyze_tone_practice(audio, target_note=target)
    return _ANALYSED[name]


def score(name: str) -> float:
    r = analysed(name)
    assert r is not None and r.pitch_stability_score is not None, name
    return float(r.pitch_stability_score)


class SilenceIsNotPartOfThePlaying(unittest.TestCase):
    """Defect 1: the same note, with and without silence around it, is the same note."""

    def test_surrounding_silence_does_not_change_volume_consistency(self) -> None:
        trimmed = analysed("steady_e5_trimmed")
        padded = analysed("steady_e5_with_silence")
        self.assertIsNotNone(trimmed.volume_stability_score)
        self.assertIsNotNone(padded.volume_stability_score)
        self.assertAlmostEqual(
            float(trimmed.volume_stability_score),
            float(padded.volume_stability_score),
            delta=2.0,
            msg="silence around the note still reaches the volume measurement",
        )

    def test_a_steady_tone_with_silence_scores_well_not_badly(self) -> None:
        padded = analysed("steady_e5_with_silence")
        self.assertGreaterEqual(float(padded.volume_stability_score), 90.0)
        self.assertGreaterEqual(float(padded.pitch_stability_score), 95.0)

    def test_an_even_tone_with_silence_is_even(self) -> None:
        r = analysed("constant_volume_with_silence")
        self.assertGreaterEqual(float(r.volume_stability_score), 95.0)
        self.assertLessEqual(r.volume_fluctuation_db, 1.0)

    def test_the_sustain_excludes_the_silence_it_was_padded_with(self) -> None:
        # 3 s of tone inside 5 s of recording: the measured sustain is the tone, less the edges.
        r = analysed("steady_e5_with_silence")
        self.assertGreater(r.duration_sec, 4.5)
        self.assertLess(r.sustain_seconds, 3.1)
        self.assertGreater(r.sustain_seconds, 2.0)

    def test_the_attack_and_release_are_trimmed_from_the_sustain(self) -> None:
        r = analysed("steady_e5_trimmed")
        self.assertLess(r.sustain_seconds, 3.0, "the whole clip was used, edges included")
        self.assertGreater(r.sustain_seconds, 2.3)


class PitchStabilityDoesNotSaturate(unittest.TestCase):
    """Defect 2: how far the pitch moved has to be answerable, not just "badly"."""

    def test_a_steady_note_is_steady(self) -> None:
        r = analysed("steady_e5_trimmed")
        self.assertGreaterEqual(float(r.pitch_stability_score), 95.0)
        self.assertLessEqual(r.pitch_spread_cents, 5.0)

    def test_a_sharp_but_steady_note_is_still_steady(self) -> None:
        # The old score measured cents against the TARGET, so being 30 cents sharp read as 30 cents
        # of movement. Stability is now measured around the note's own centre.
        r = analysed("mild_offset_30c_sharp")
        self.assertGreaterEqual(float(r.pitch_stability_score), 95.0)
        self.assertAlmostEqual(float(r.tuning_offset_cents), 30.0, delta=10.0)

    def test_a_bigger_drift_scores_lower_than_a_smaller_one(self) -> None:
        self.assertGreater(score("drift_20c"), score("drift_60c"))

    def test_the_drift_is_reported_with_its_size_and_direction(self) -> None:
        small = analysed("drift_20c")
        big = analysed("drift_60c")
        self.assertGreater(small.pitch_drift_cents, 8.0)
        self.assertGreater(big.pitch_drift_cents, small.pitch_drift_cents + 10.0)

    def test_drift_semitone_and_octave_are_three_different_answers(self) -> None:
        drift = score("drift_60c")
        semitone = score("semitone_jump")
        octave = score("octave_jump")
        self.assertGreater(drift, semitone + 10.0, "a drift and a semitone look the same")
        self.assertGreater(semitone, octave + 10.0, "a semitone and an octave look the same")

    def test_an_octave_jump_is_not_scored_as_zero(self) -> None:
        # Zero is reserved for "not measured". An octave jump is measured, and badly.
        r = analysed("octave_jump")
        self.assertIsNotNone(r.pitch_stability_score)
        self.assertGreater(float(r.pitch_stability_score), 0.0)
        self.assertLess(float(r.pitch_stability_score), 20.0)

    def test_a_note_change_is_named_as_a_note_change(self) -> None:
        semitone = analysed("semitone_jump")
        octave = analysed("octave_jump")
        self.assertTrue(semitone.note_change_detected)
        self.assertTrue(octave.note_change_detected)
        self.assertGreaterEqual(semitone.largest_step_cents, 70.0)
        self.assertGreaterEqual(octave.largest_step_cents, 1000.0)

    def test_a_steady_note_is_not_called_a_note_change(self) -> None:
        for name in ("steady_e5_trimmed", "drift_20c", "vibrato_regular"):
            self.assertFalse(analysed(name).note_change_detected, name)

    def test_a_regular_vibrato_is_identified_as_vibrato(self) -> None:
        r = analysed("vibrato_regular")
        self.assertGreaterEqual(r.vibrato_rate_hz, 3.0)
        self.assertLessEqual(r.vibrato_rate_hz, 9.0)
        # Depth read through a 93 ms analysis window is attenuated relative to the true +/-35c.
        self.assertGreaterEqual(r.vibrato_depth_cents, 15.0)

    def test_vibrato_movement_is_preserved_in_the_measurement(self) -> None:
        # The requirement is that vibrato is not quietly removed: it IS movement, and the number
        # must reflect it, while the explanation says it was intentional.
        self.assertLess(score("vibrato_regular"), score("steady_e5_trimmed"))
        self.assertIn("vibrato", " ".join(analysed("vibrato_regular").feedback).lower())

    def test_irregular_wandering_scores_below_a_steady_drift(self) -> None:
        self.assertLess(score("fluctuation_irregular"), score("drift_60c"))

    def test_an_unsteady_note_is_not_called_steady(self) -> None:
        text = " ".join(analysed("fluctuation_irregular").feedback).lower()
        self.assertNotIn("very steadily", text)


class AScoreNeverReadsBetterThanItIs(unittest.TestCase):
    """A positive floor on the scale must not become reassurance."""

    def test_a_very_poor_score_says_so_in_words(self) -> None:
        r = analysed("octave_jump")
        text = " ".join(r.feedback).lower()
        self.assertIn("very unstable", text)
        self.assertLess(float(r.pitch_stability_score), 35.0)

    def test_the_verdict_comes_before_the_detail(self) -> None:
        r = analysed("octave_jump")
        self.assertIn("pitch stability", r.feedback[0].lower())

    def test_a_good_score_is_not_given_a_warning_it_has_not_earned(self) -> None:
        text = " ".join(analysed("steady_e5_trimmed").feedback).lower()
        self.assertNotIn("very unstable", text)
        self.assertNotIn("a lot for a long tone", text)

    def test_the_band_words_cover_the_scale_in_order(self) -> None:
        from tone_sustain_analysis import pitch_stability_band, volume_consistency_band

        self.assertEqual(pitch_stability_band(100.0), "very steady")
        self.assertEqual(pitch_stability_band(80.0), "steady")
        self.assertEqual(pitch_stability_band(60.0), "some movement")
        self.assertEqual(pitch_stability_band(40.0), "unsteady")
        self.assertEqual(pitch_stability_band(8.0), "very unstable")
        self.assertEqual(volume_consistency_band(99.0), "very even")
        self.assertEqual(volume_consistency_band(40.3), "very uneven")

    def test_no_score_at_all_is_not_a_band_but_not_measured(self) -> None:
        from tone_sustain_analysis import pitch_stability_band, volume_consistency_band

        self.assertEqual(pitch_stability_band(None), "not measured")
        self.assertEqual(volume_consistency_band(None), "not measured")

    def test_an_unmeasurable_take_shows_not_measured_rather_than_a_floor_score(self) -> None:
        for name in ("breath_noise_only", "weak_input", "too_short"):
            r = analysed(name)
            self.assertIsNone(r.pitch_stability_score, name)
            self.assertNotEqual(r.pitch_stability_score, 0.0, name)
            self.assertTrue(r.reason, name)

    def test_the_panel_prints_the_band_word_beside_the_number(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        self.assertIn("pitch_stability_band(result.pitch_stability_score)", source)
        self.assertIn("volume_consistency_band(result.volume_stability_score)", source)


def prose(lines: list[str]) -> str:
    """Feedback as a musician reads it: markdown emphasis removed, lower case.

    Asserting on the raw string is asserting on where the asterisks fall - "**not** a constant
    volume" does not contain "not a constant volume" - which tests the formatting instead of the
    sentence.
    """
    return " ".join(lines).replace("**", "").lower()


class VolumeTrendIsNeverMistakenForSteadiness(unittest.TestCase):
    """98% short-term steadiness must not read as "I held a constant volume"."""

    def test_a_crescendo_is_stated_as_not_a_constant_volume(self) -> None:
        text = prose(analysed("crescendo").feedback)
        self.assertIn("grew", text)
        self.assertIn("not a constant volume", text)

    def test_a_decrescendo_is_stated_as_not_a_constant_volume(self) -> None:
        text = prose(analysed("decrescendo").feedback)
        self.assertIn("faded", text)
        self.assertIn("not a constant volume", text)

    def test_the_evenness_sentence_is_never_bare_under_a_trend(self) -> None:
        # "The sound grew by 8 dB" followed by "Volume stayed even through the sustain" reads as a
        # contradiction and invites exactly the misreading this guards against.
        for name in ("crescendo", "decrescendo"):
            text = " ".join(analysed(name).feedback)
            self.assertNotIn("**Volume stayed even** through the sustain.", text, name)
            self.assertIn("Apart from that change in level", text, name)

    def test_an_actually_even_note_still_says_so_plainly(self) -> None:
        text = " ".join(analysed("steady_e5_trimmed").feedback)
        self.assertIn("**Volume stayed even** through the sustain.", text)

    def test_the_trend_is_a_separate_reported_number(self) -> None:
        self.assertGreaterEqual(analysed("crescendo").volume_trend_db, 4.0)
        self.assertLessEqual(analysed("decrescendo").volume_trend_db, -4.0)
        self.assertAlmostEqual(analysed("steady_e5_trimmed").volume_trend_db, 0.0, delta=1.0)

    def test_the_panel_shows_the_trend_beside_the_consistency_number(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        self.assertIn("grew {_trend_db:.0f} dB overall", source)
        self.assertIn("Volume trend:", source)
        self.assertIn("It is NOT a ", source)

    def test_the_five_measurements_stay_distinct(self) -> None:
        # pitch stability, tuning accuracy, octave difference, volume steadiness, volume trend.
        r = analysed("flat31_e5_target_e4")
        self.assertIsNotNone(r.pitch_stability_score)
        self.assertIsNotNone(r.tuning_offset_cents)
        self.assertEqual(r.octave_offset_semitones, 12)
        self.assertIsNotNone(r.volume_stability_score)
        self.assertIsNotNone(r.volume_trend_db)
        stored = r.measurement
        for key in (
            "pitch_stability_score",
            "tuning_offset_cents",
            "octave_offset_semitones",
            "volume_consistency_score",
            "volume_trend_db",
        ):
            self.assertIn(key, stored)


class TheWordsMatchTheSizeOfWhatHappened(unittest.TestCase):
    def test_a_seventy_cent_wobble_is_not_called_two_notes(self) -> None:
        text = " ".join(analysed("fluctuation_irregular").feedback).lower()
        self.assertIn("wide wobble", text)
        self.assertNotIn("two notes", text)

    def test_a_semitone_step_is_called_a_change_of_note(self) -> None:
        text = " ".join(analysed("semitone_jump").feedback).lower()
        self.assertIn("two notes", text)

    def test_an_octave_step_is_called_a_change_of_note(self) -> None:
        text = " ".join(analysed("octave_jump").feedback).lower()
        self.assertIn("two notes", text)
        self.assertIn("about an octave", text)


class TheScoringCurvesAreMonotonicAndDocumented(unittest.TestCase):
    """The map from a measurement to a score, checked as a function."""

    def test_pitch_stability_never_increases_with_more_movement(self) -> None:
        last = 101.0
        for spread in (0, 1, 3, 6, 12, 25, 50, 100, 200, 400, 800, 1200, 2400, 5000):
            value = pitch_stability_from_spread(spread)
            self.assertLessEqual(value, last, f"not monotonic at {spread} cents")
            last = value

    def test_pitch_stability_hits_its_documented_anchors(self) -> None:
        for spread, expected in PITCH_STABILITY_ANCHORS:
            self.assertAlmostEqual(pitch_stability_from_spread(spread), expected, delta=0.051)

    def test_pitch_stability_keeps_a_semitone_and_an_octave_apart(self) -> None:
        semitone = pitch_stability_from_spread(100.0)
        octave = pitch_stability_from_spread(1200.0)
        self.assertGreater(semitone - octave, 20.0)
        self.assertGreater(octave, 0.0)

    def test_volume_consistency_never_increases_with_more_fluctuation(self) -> None:
        last = 101.0
        for db in (0, 0.5, 1, 2, 3, 5, 8, 12, 20, 30, 60):
            value = volume_consistency_from_fluctuation(db)
            self.assertLessEqual(value, last, f"not monotonic at {db} dB")
            last = value

    def test_volume_consistency_hits_its_documented_anchors(self) -> None:
        for db, expected in VOLUME_CONSISTENCY_ANCHORS:
            self.assertAlmostEqual(volume_consistency_from_fluctuation(db), expected, delta=0.051)

    def test_a_perfect_measurement_is_a_hundred(self) -> None:
        self.assertEqual(pitch_stability_from_spread(0.0), 100.0)
        self.assertEqual(volume_consistency_from_fluctuation(0.0), 100.0)


class VolumeConsistencyIsAboutEvennessNotLoudness(unittest.TestCase):
    def test_a_smooth_crescendo_is_not_punished_as_unevenness(self) -> None:
        r = analysed("crescendo")
        self.assertGreaterEqual(float(r.volume_stability_score), 88.0)
        self.assertGreaterEqual(r.volume_trend_db, 4.0)

    def test_a_smooth_decrescendo_is_reported_as_a_shape(self) -> None:
        r = analysed("decrescendo")
        self.assertGreaterEqual(float(r.volume_stability_score), 88.0)
        self.assertLessEqual(r.volume_trend_db, -4.0)
        self.assertIn("faded", " ".join(r.feedback).lower())

    def test_a_dropout_is_caught(self) -> None:
        r = analysed("volume_dropout")
        self.assertLessEqual(float(r.volume_stability_score), 65.0)
        self.assertGreaterEqual(r.volume_fluctuation_db, 3.0)

    def test_a_dropout_does_not_contaminate_the_pitch_score(self) -> None:
        r = analysed("volume_dropout")
        self.assertGreaterEqual(float(r.pitch_stability_score), 85.0)

    def test_loudness_itself_is_not_scored(self) -> None:
        # The same tone at a quarter of the amplitude: same evenness, same steadiness.
        loud = analyze_tone_practice(wav_bytes(tone(E5_HZ, 2.5, amp=0.4)), target_note="E5")
        quiet = analyze_tone_practice(wav_bytes(tone(E5_HZ, 2.5, amp=0.1)), target_note="E5")
        self.assertAlmostEqual(
            float(loud.volume_stability_score), float(quiet.volume_stability_score), delta=3.0
        )
        self.assertAlmostEqual(
            float(loud.pitch_stability_score), float(quiet.pitch_stability_score), delta=3.0
        )


class TheTargetOctaveIsExplicit(unittest.TestCase):
    """Defect 3: which octave the reference is in must never be an assumption again."""

    def test_a_named_octave_is_a_named_octave(self) -> None:
        midi, pitch_class_only = resolve_target("E4")
        self.assertEqual(midi, 64.0)
        self.assertFalse(pitch_class_only)

    def test_a_bare_letter_is_a_pitch_class_contract(self) -> None:
        midi, pitch_class_only = resolve_target("E")
        self.assertTrue(pitch_class_only)
        self.assertEqual(midi % 12, 4.0)

    def test_flats_and_sharps_both_parse(self) -> None:
        self.assertEqual(resolve_target("Bb3")[0], resolve_target("A#3")[0])

    def test_nonsense_is_no_target_rather_than_a_wrong_one(self) -> None:
        for token in ("", "   ", "H4", "zzz", None):
            self.assertEqual(resolve_target(token)[0], None, repr(token))

    def test_an_octave_apart_is_reported_as_an_octave_not_as_1200_cents(self) -> None:
        detected = hz_to_midi(E5_HZ)
        offset, raw, octave_semitones, pitch_class_only, _ = tuning_against_target(detected, "E4")
        self.assertEqual(octave_semitones, 12)
        self.assertAlmostEqual(offset, 0.0, delta=1.0)
        self.assertAlmostEqual(raw, 1200.0, delta=1.0)
        self.assertFalse(pitch_class_only)

    def test_the_users_own_case_reads_as_31_cents_flat(self) -> None:
        # A flute E5 played 31 cents flat, against the E4 the app used to assume: the musician is
        # told 31 cents flat and one octave up, not 1169 cents sharp.
        r = analysed("flat31_e5_target_e4")
        self.assertEqual(r.detected_note, "E5")
        self.assertEqual(r.octave_offset_semitones, 12)
        self.assertAlmostEqual(float(r.tuning_offset_cents), -31.0, delta=12.0)
        self.assertAlmostEqual(float(r.raw_offset_cents), 1169.0, delta=15.0)
        self.assertGreaterEqual(float(r.pitch_stability_score), 95.0)

    def test_the_octave_difference_is_explained_in_words(self) -> None:
        text = " ".join(analysed("flat31_e5_target_e4").feedback).lower()
        self.assertIn("octave", text)
        self.assertIn("e4", text)

    def test_a_pitch_class_target_accepts_the_octave_that_was_played(self) -> None:
        r = analysed("steady_e5_target_pitch_class")
        self.assertTrue(r.target_is_pitch_class_only)
        self.assertEqual(r.octave_offset_semitones, 0)
        self.assertAlmostEqual(float(r.tuning_offset_cents), 0.0, delta=10.0)

    def test_the_same_octave_needs_no_octave_notice(self) -> None:
        r = analysed("steady_e5_trimmed")
        self.assertEqual(r.octave_offset_semitones, 0)
        self.assertNotIn("octave", " ".join(r.feedback).lower())

    def test_tuning_and_stability_are_separate_numbers(self) -> None:
        sharp = analysed("mild_offset_30c_sharp")
        steady = analysed("steady_e5_trimmed")
        self.assertAlmostEqual(
            float(sharp.pitch_stability_score), float(steady.pitch_stability_score), delta=3.0
        )
        self.assertGreater(abs(float(sharp.tuning_offset_cents)), 15.0)


class UnmeasurableRecordingsSayWhyInsteadOfScoringZero(unittest.TestCase):
    def test_breath_noise_is_not_a_zero_percent_performance(self) -> None:
        r = analysed("breath_noise_only")
        self.assertEqual(r.status, "insufficient")
        self.assertIsNone(r.pitch_stability_score)
        self.assertIsNone(r.volume_stability_score)
        self.assertIn("reliable pitch", r.reason.lower())

    def test_a_recording_too_quiet_to_measure_says_so(self) -> None:
        r = analysed("weak_input")
        self.assertEqual(r.status, "insufficient")
        self.assertIn("quiet", r.reason.lower())

    def test_a_clip_too_short_to_hold_says_so(self) -> None:
        r = analysed("too_short")
        self.assertEqual(r.status, "insufficient")
        self.assertIn("hold one note", r.reason.lower())

    def test_an_insufficient_result_still_reports_what_it_saw(self) -> None:
        r = analysed("weak_input")
        self.assertGreater(r.duration_sec, 2.0)
        self.assertLess(r.peak_dbfs, -40.0)

    def test_the_explanation_is_the_reason_and_nothing_invented(self) -> None:
        r = analysed("breath_noise_only")
        self.assertEqual(r.feedback, [r.reason])


class KnownPitchesAcrossInstrumentRanges(unittest.TestCase):
    def test_a_flute_d5_is_detected_as_d5(self) -> None:
        self.assertEqual(analysed("flute_d5").detected_note, "D5")

    def test_a_tenor_saxophones_concert_bb3_is_spelled_as_bb3(self) -> None:
        # Same pitch as A#3, but Bb3 is the name the player chose.
        self.assertEqual(analysed("tenor_sax_bb3_concert").detected_note, "Bb3")

    def test_a_bass_range_e2_is_detected_as_e2(self) -> None:
        self.assertEqual(analysed("low_e2_steady").detected_note, "E2")

    def test_every_range_is_measurable(self) -> None:
        for name in ("flute_d5", "tenor_sax_bb3_concert", "low_e2_steady"):
            r = analysed(name)
            self.assertEqual(r.status, "measured", f"{name}: {r.reason}")
            self.assertGreaterEqual(float(r.pitch_stability_score), 90.0, name)


class TheGraphTheNumbersAndTheWordsAgree(unittest.TestCase):
    def test_the_trace_describes_the_same_frames_as_the_numbers(self) -> None:
        r = analysed("steady_e5_with_silence")
        self.assertTrue(r.pitch_trace_hz)
        self.assertEqual(len(r.pitch_trace_hz), len(r.time_trace_sec))
        # The trace is the sustained portion, so it starts after the silence, not at zero.
        self.assertGreater(r.time_trace_sec[0], 0.5)
        self.assertAlmostEqual(
            float(np.median(r.pitch_trace_hz)), r.detected_hz, delta=max(1.0, r.detected_hz * 0.01)
        )

    def test_a_high_score_never_comes_with_an_unsteady_explanation(self) -> None:
        r = analysed("steady_e5_trimmed")
        text = " ".join(r.feedback).lower()
        self.assertNotIn("unstable", text)
        self.assertNotIn("drifted", text)

    def test_a_low_score_never_comes_with_a_praising_explanation(self) -> None:
        r = analysed("octave_jump")
        text = " ".join(r.feedback).lower()
        self.assertNotIn("held very steadily", text)

    def test_the_reported_spread_matches_the_score(self) -> None:
        for name in ("steady_e5_trimmed", "drift_20c", "drift_60c", "semitone_jump", "octave_jump"):
            r = analysed(name)
            self.assertAlmostEqual(
                float(r.pitch_stability_score),
                pitch_stability_from_spread(r.pitch_spread_cents),
                delta=0.11,
                msg=name,
            )

    def test_the_reported_fluctuation_matches_the_volume_score(self) -> None:
        for name in ("steady_e5_trimmed", "crescendo", "volume_dropout"):
            r = analysed(name)
            self.assertAlmostEqual(
                float(r.volume_stability_score),
                volume_consistency_from_fluctuation(r.volume_fluctuation_db),
                delta=0.11,
                msg=name,
            )


class TheMeasurementPrimitives(unittest.TestCase):
    """The pieces, tested directly, so a failure above can be located."""

    def test_robust_spread_matches_the_standard_deviation_for_clean_data(self) -> None:
        rng = np.random.default_rng(3)
        values = rng.normal(0.0, 10.0, 4000)
        self.assertAlmostEqual(robust_spread(values), float(np.std(values)), delta=1.0)

    def test_robust_spread_ignores_a_single_wild_frame(self) -> None:
        # The first implementation returned 351 cents here, because its zero-MAD fallback was the
        # plain standard deviation and one frame then decided the whole score.
        values = np.concatenate([np.full(200, 5.0), np.array([5000.0])])
        self.assertLess(robust_spread(values), 1.0)

    def test_robust_spread_still_sees_a_real_minority(self) -> None:
        # A fifth of the note an octave away is not an outlier, it is what happened.
        values = np.concatenate([np.zeros(80), np.full(20, 1200.0)])
        self.assertGreater(robust_spread(values), 300.0)

    def test_the_trim_factor_keeps_the_spread_on_sigma(self) -> None:
        # Re-derive the published constant rather than trusting it: the standard deviation of a
        # standard normal truncated at the trim fraction.
        from statistics import NormalDist

        from tone_sustain_analysis import SPREAD_TRIM_FACTOR, SPREAD_TRIM_FRACTION

        nd = NormalDist()
        n = 20001
        xs = np.array([nd.inv_cdf((i + 0.5) / n) for i in range(n)])
        k = int(SPREAD_TRIM_FRACTION * n)
        self.assertAlmostEqual(float(xs[k : n - k].std()), SPREAD_TRIM_FACTOR, delta=0.002)

    def test_an_isolated_octave_slip_is_repaired(self) -> None:
        midi = np.full(60, 76.0)
        midi[30] = 88.0  # one frame an octave up: the tracker, not the player
        fixed, repaired = correct_detection_octaves(midi, hop_sec=0.023)
        self.assertEqual(repaired, 1)
        self.assertAlmostEqual(float(fixed[30]), 76.0, delta=0.01)

    def test_a_real_octave_change_is_left_alone(self) -> None:
        midi = np.concatenate([np.full(60, 76.0), np.full(60, 88.0)])
        fixed, repaired = correct_detection_octaves(midi, hop_sec=0.023)
        self.assertEqual(repaired, 0)
        self.assertAlmostEqual(float(fixed[-1]), 88.0, delta=0.01)

    def test_an_unrelated_frequency_is_never_folded_into_the_centre(self) -> None:
        midi = np.full(60, 76.0)
        midi[10] = 90.5  # not an octave of anything here
        fixed, repaired = correct_detection_octaves(midi, hop_sec=0.023)
        self.assertEqual(repaired, 0)
        self.assertAlmostEqual(float(fixed[10]), 90.5, delta=0.01)

    def test_the_longest_run_wins(self) -> None:
        mask = np.array([1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0], dtype=bool)
        self.assertEqual(longest_run(mask, hop_sec=0.023), (6, 10))

    def test_a_tracker_length_gap_does_not_end_the_note(self) -> None:
        mask = np.array([1, 1, 1, 0, 1, 1, 1], dtype=bool)  # one frame = 23 ms
        self.assertEqual(longest_run(mask, hop_sec=0.023), (0, 7))

    def test_runs_of_the_same_note_are_joined_across_a_dropout(self) -> None:
        midi = np.concatenate([np.full(40, 69.0), np.full(20, np.nan), np.full(40, 69.0)])
        runs = [(0, 40), (60, 100)]
        (start, end), dropout_sec, count = join_dropouts(runs, midi, hop_sec=0.023)
        self.assertEqual((start, end), (0, 100))
        self.assertEqual(count, 1)
        self.assertAlmostEqual(dropout_sec, 20 * 0.023, delta=0.01)

    def test_runs_of_different_notes_are_not_joined(self) -> None:
        midi = np.concatenate([np.full(40, 69.0), np.full(20, np.nan), np.full(40, 76.0)])
        (start, end), _, count = join_dropouts([(0, 40), (60, 100)], midi, hop_sec=0.023)
        self.assertEqual(count, 0)
        self.assertEqual(end - start, 40)

    def test_quiet_and_unconfident_frames_are_not_usable(self) -> None:
        frames = frames_from_arrays(
            times_sec=[0.0, 0.1, 0.2, 0.3],
            hz=[440.0, 440.0, 440.0, 0.0],
            voiced=[True, True, True, False],
            voiced_prob=[0.9, 0.2, 0.9, 0.0],
            rms=[0.5, 0.5, 0.0001, 0.0],
            hop_sec=0.1,
            sample_rate=22050,
            duration_sec=0.4,
            peak_dbfs=-6.0,
        )
        self.assertEqual(list(usable_mask(frames)), [True, False, False, False])

    def test_note_labels_can_be_spelled_with_flats(self) -> None:
        self.assertEqual(midi_to_note_label(58.0), "A#3")
        self.assertEqual(midi_to_note_label(58.0, prefer_flats=True), "Bb3")

    def test_a_measurement_with_no_frames_is_insufficient_not_zero(self) -> None:
        frames = frames_from_arrays(
            times_sec=[0.0, 0.1],
            hz=[0.0, 0.0],
            voiced=[False, False],
            voiced_prob=[0.0, 0.0],
            rms=[0.0, 0.0],
            hop_sec=0.1,
            sample_rate=22050,
            duration_sec=0.2,
            peak_dbfs=-10.0,
        )
        m = measure_tone(frames, target_note="A4")
        self.assertEqual(m.status, "insufficient")
        self.assertIsNone(m.pitch_stability_score)
        self.assertIsNone(m.volume_consistency_score)
        self.assertEqual(explain(m), [m.reason])


class StoredScoresSayWhichAlgorithmMadeThem(unittest.TestCase):
    def test_a_new_measurement_carries_its_scoring_version(self) -> None:
        self.assertEqual(analysed("steady_e5_trimmed").scoring_version, SCORING_VERSION)

    def test_a_row_without_a_version_is_legacy(self) -> None:
        from media_tone_catalog import tone_take_scoring_is_legacy

        self.assertTrue(tone_take_scoring_is_legacy({"pitch_stability_score": 62}))
        self.assertFalse(
            tone_take_scoring_is_legacy({"pitch_stability_score": 62, "scoring_version": "x"})
        )

    def test_an_unmeasured_take_is_not_filed_as_badly_played(self) -> None:
        from media_tone_catalog import tone_take_quality

        self.assertEqual(
            tone_take_quality({"pitch_stability_score": None, "analysis_status": "insufficient"}),
            "unmeasured",
        )
        # And the old ranking still works for rows that do have scores.
        self.assertEqual(tone_take_quality({"pitch_stability_score": 85, "mean_cents": 2}), "best")
        self.assertEqual(tone_take_quality({"pitch_stability_score": 40, "mean_cents": 2}), "needs_work")

    def test_an_absent_score_is_stored_as_absent_not_as_zero(self) -> None:
        from media_tone_catalog import build_tone_take_fields

        r = analysed("breath_noise_only")
        fields = build_tone_take_fields({}, r, target_note="E5", instrument="Flute")
        self.assertIsNone(fields["pitch_stability_score"])
        self.assertIsNone(fields["volume_stability_score"])
        self.assertIsNone(fields["tone_consistency_score"])
        self.assertEqual(fields["analysis_status"], "insufficient")
        self.assertTrue(fields["analysis_reason"])

    def test_a_measured_take_stores_its_separated_numbers(self) -> None:
        from media_tone_catalog import build_tone_take_fields

        r = analysed("flat31_e5_target_e4")
        fields = build_tone_take_fields({}, r, target_note="E4", instrument="Flute")
        self.assertEqual(fields["octave_offset_semitones"], 12)
        self.assertAlmostEqual(float(fields["tuning_offset_cents"]), -31.0, delta=12.0)
        self.assertEqual(fields["scoring_version"], SCORING_VERSION)
        self.assertEqual(fields["analysis_status"], "measured")


class TheOldAnalysisIsKeptOnlyAsEvidence(unittest.TestCase):
    """The pre-Issue-79 function stays in the tree so its numbers can be reproduced on demand.

    A report that says "this was 4% and is now 99.9%" should be able to produce the 4%. But the app
    must never call it again, so that is pinned rather than assumed.
    """

    def test_the_old_implementation_is_still_runnable(self) -> None:
        from tuner_tone import _legacy_analyze_tone_practice

        audio, target, _ = signal_catalog()["steady_e5_with_silence"]
        old = _legacy_analyze_tone_practice(audio, target_note=target)
        self.assertIsNotNone(old)
        # The defect, on demand: the same recording the new analysis scores in the high nineties.
        self.assertLess(float(old.volume_stability_score), 20.0)
        new = analysed("steady_e5_with_silence")
        self.assertGreater(float(new.volume_stability_score), 90.0)

    def test_nothing_in_the_app_calls_the_old_implementation(self) -> None:
        for name in ("tuner_tone_ui.py", "media_tone_catalog.py", "tone_take_history_ui.py",
                     "streamlit_music_practice_app.py"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("_legacy_analyze_tone_practice", source, name)

    def test_the_panel_uses_the_corrected_analysis(self) -> None:
        source = (ROOT / "tuner_tone.py").read_text(encoding="utf-8")
        self.assertIn("from tone_sustain_analysis import explain, measure_tone", source)


class TheStoredRowKeepsWhatWasMeasured(unittest.TestCase):
    """Both of these were found by the real-app acceptance, not by a unit test."""

    def test_the_scoring_version_survives_normalisation(self) -> None:
        # migrate_tone_take returns an explicit whitelist of fields and discards the rest, so a
        # take saved by this build came back with no scoring version - and therefore came back
        # labelled "Legacy measurement" in the musician's own history.
        from media_state import migrate_tone_take

        row = migrate_tone_take(
            {
                "tone_take_id": "n1",
                "scoring_version": SCORING_VERSION,
                "pitch_stability_score": 100.0,
                "analysis_status": "measured",
            }
        )
        self.assertEqual(row["scoring_version"], SCORING_VERSION)
        self.assertEqual(row["analysis_status"], "measured")

    def test_the_separated_measurements_survive_normalisation(self) -> None:
        from media_state import migrate_tone_take

        row = migrate_tone_take(
            {
                "tone_take_id": "n2",
                "scoring_version": SCORING_VERSION,
                "tuning_offset_cents": -30.5,
                "raw_offset_cents": 1169.5,
                "octave_offset_semitones": 12,
                "pitch_spread_cents": 4.25,
                "volume_fluctuation_db": 1.5,
                "volume_trend_db": -6.0,
                "detection_confidence": 0.97,
                "target_is_pitch_class_only": True,
            }
        )
        self.assertAlmostEqual(row["tuning_offset_cents"], -30.5)
        self.assertAlmostEqual(row["raw_offset_cents"], 1169.5)
        self.assertEqual(row["octave_offset_semitones"], 12)
        self.assertAlmostEqual(row["pitch_spread_cents"], 4.25)
        self.assertAlmostEqual(row["volume_fluctuation_db"], 1.5)
        self.assertAlmostEqual(row["volume_trend_db"], -6.0)
        self.assertAlmostEqual(row["detection_confidence"], 0.97)
        self.assertTrue(row["target_is_pitch_class_only"])

    def test_a_row_saved_before_this_build_is_still_recognised_as_legacy(self) -> None:
        from media_state import migrate_tone_take
        from media_tone_catalog import tone_take_scoring_is_legacy

        row = migrate_tone_take({"tone_take_id": "l1", "pitch_stability_score": 62.0})
        self.assertEqual(row["scoring_version"], "")
        self.assertTrue(tone_take_scoring_is_legacy(row))
        self.assertEqual(row["pitch_stability_score"], 62.0)

    def test_a_stored_score_of_zero_is_kept_as_zero(self) -> None:
        # ``row.get("a") or row.get("b")`` discards a stored 0.0, so a legacy take that really was
        # scored 0% came back as "not measured" - a different claim about the musician's practice,
        # made silently. Pre-existing; it matters more now that 0 and "unknown" differ.
        from media_state import migrate_tone_take

        row = migrate_tone_take(
            {
                "tone_take_id": "z1",
                "pitch_stability_score": 0.0,
                "volume_stability_score": 0.0,
                "mean_cents": 0.0,
            }
        )
        self.assertEqual(row["pitch_stability_score"], 0.0)
        self.assertEqual(row["volume_stability_score"], 0.0)
        self.assertEqual(row["mean_cents"], 0.0)

    def test_an_alias_is_used_only_when_the_main_field_is_absent(self) -> None:
        from media_state import migrate_tone_take

        row = migrate_tone_take({"tone_take_id": "a1", "pitch_stability": 77.0})
        self.assertEqual(row["pitch_stability_score"], 77.0)


class TheTargetContractReachesTheAnalyzer(unittest.TestCase):
    def test_an_explicit_octave_is_passed_through(self) -> None:
        from media_tone_catalog import resolve_tone_target_from_pitch_class

        ctx = resolve_tone_target_from_pitch_class("E", "", is_transposing=False, octave=5)
        self.assertEqual(ctx["analysis_target_note"], "E5")
        self.assertFalse(ctx["pitch_class_only"])

    def test_any_octave_is_a_pitch_class_target(self) -> None:
        from media_tone_catalog import resolve_tone_target_from_pitch_class

        ctx = resolve_tone_target_from_pitch_class("E", "", is_transposing=False, octave=None)
        self.assertEqual(ctx["analysis_target_note"], "E")
        self.assertTrue(ctx["pitch_class_only"])

    def test_existing_callers_keep_the_old_behaviour(self) -> None:
        from media_tone_catalog import resolve_tone_target_from_pitch_class

        ctx = resolve_tone_target_from_pitch_class("E", "", is_transposing=False)
        self.assertEqual(ctx["analysis_target_note"], "E4")

    def test_transposition_ownership_is_unchanged(self) -> None:
        from media_tone_catalog import resolve_tone_target_from_pitch_class

        specific = resolve_tone_target_from_pitch_class(
            "C", "Tenor saxophone (Bb)", is_transposing=True, octave=4
        )
        self.assertEqual(specific["written_note"], "C4")
        self.assertEqual(specific["analysis_target_note"], "A#3")
        any_octave = resolve_tone_target_from_pitch_class(
            "C", "Tenor saxophone (Bb)", is_transposing=True, octave=None
        )
        self.assertEqual(any_octave["written_note"], "C")
        self.assertEqual(any_octave["analysis_target_note"], "A#")

    def test_the_panel_offers_an_octave_and_an_any_octave_contract(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        self.assertIn('"Target octave"', source)
        self.assertIn("ANY_OCTAVE_LABEL", source)
        self.assertIn("tone_target_octave_select", source)

    def test_the_panel_states_which_contract_is_in_force(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        self.assertIn("tuning is measured against the octave you", source)
        self.assertIn("a specific", source)

    def test_the_panel_shows_an_insufficient_result_instead_of_zero(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        self.assertIn("Not enough reliable pitch detected", source)
        self.assertIn('if not getattr(result, "measured", True):', source)

    def test_the_panel_separates_the_five_readings(self) -> None:
        source = (ROOT / "tuner_tone_ui.py").read_text(encoding="utf-8")
        for token in (
            "Detected note:",
            "Tuning offset:",
            "Confidence:",
            "Pitch stability",
            "Volume consistency",
        ):
            self.assertIn(token, source)


class TheSustainDurationIsUsableSound(unittest.TestCase):
    def test_a_long_tone_reports_most_of_itself_as_sustain(self) -> None:
        r = analyze_tone_practice(wav_bytes(tone(E5_HZ, 5.0)), target_note="E5")
        self.assertGreater(r.sustain_seconds, 4.0)

    def test_a_note_shorter_than_the_minimum_is_not_scored(self) -> None:
        clip = np.concatenate([silence(0.3), tone(E5_HZ, 0.4), silence(0.3)])
        r = analyze_tone_practice(wav_bytes(clip), target_note="E5")
        self.assertEqual(r.status, "insufficient")
        self.assertLess(r.sustain_seconds, MIN_SUSTAIN_SEC)

    def test_noise_before_the_note_does_not_count_as_sustain(self) -> None:
        clip = np.concatenate([noise(1.0, amp=0.01), tone(E5_HZ, 2.5)])
        r = analyze_tone_practice(wav_bytes(clip), target_note="E5")
        self.assertEqual(r.status, "measured", r.reason)
        self.assertLess(r.sustain_seconds, 2.6)
        self.assertGreater(r.sustain_seconds, 1.5)

    def test_a_fade_to_nothing_still_measures_the_part_that_sounded(self) -> None:
        clip = tone(E5_HZ, 3.0, amp_curve=lambda t: np.clip(ramp(t, 1.0, -0.2), 0.0, 1.0))
        r = analyze_tone_practice(wav_bytes(clip), target_note="E5")
        self.assertEqual(r.status, "measured", r.reason)
        self.assertLess(r.volume_trend_db, 0.0)
        self.assertLess(r.sustain_seconds, 3.0)


if __name__ == "__main__":
    unittest.main()
