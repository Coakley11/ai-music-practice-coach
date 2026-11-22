"""Recorded melodies must land on the beat they were played on.

These tests synthesise real WAV bytes and put them through the real transcription
path (librosa pyin), rather than asserting on hand-written event arrays. A hand-made
array cannot catch the defect these pin: the onset of every transcribed note used to
be snapped to the DURATION grid ``(0.5, 1.0, 1.5, 2.0, 3.0, 4.0)``, whose largest
value acted as a ceiling. Eight quarter notes came back as
``0, 0.5, 1.5, 2.5, 3.5, 3.5, 3.5, 3.5``: the melody stopped advancing after one bar
and four notes piled onto one beat, while the chords played on to the end.
"""

from __future__ import annotations

import io
import unittest
import wave

import numpy as np

from composition_hum_transcription import (
    ONSET_GRID_BEATS,
    hum_analysis_available,
    quantize_beats,
    quantize_onset,
    transcribe_hum_audio,
)

BPM = 120
SPB = 60.0 / BPM  # 0.5 s per beat
METER = "4/4"
SR = 22050
BAR_SEC = 4 * SPB  # 2.0 s


def _tone(midi: int, dur: float) -> np.ndarray:
    f = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    t = np.arange(int(SR * dur)) / SR
    y = (
        np.sin(2 * np.pi * f * t)
        + 0.35 * np.sin(2 * np.pi * 2 * f * t)
        + 0.15 * np.sin(2 * np.pi * 3 * f * t)
    )
    env = np.ones_like(y)
    a = max(1, int(0.012 * SR))
    env[:a] = np.linspace(0, 1, a)
    env[-a:] = np.linspace(1, 0, a)
    return (y / 1.5) * env


def _quiet(dur: float, seed: int = 7) -> np.ndarray:
    """Near-silence, not digital zero: a real room is never perfectly silent."""
    return np.random.default_rng(seed).normal(0, 0.0008, max(0, int(SR * dur)))


def _wav(midis: list[int], *, lead_silence: float = 0.0, note_beats: float = 1.0) -> bytes:
    """One note per entry, each ``note_beats`` long, after ``lead_silence`` seconds."""
    gap = 0.03
    parts = [_quiet(lead_silence)]
    for m in midis:
        parts.append(_tone(m, note_beats * SPB - gap))
        parts.append(_quiet(gap, seed=m))
    y = np.clip(np.concatenate(parts), -1, 1)
    pcm = (y * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _beats(result: dict) -> list[float]:
    return [
        float(e.get("beat") or 0.0)
        for e in (result.get("events") or [])
        if not e.get("is_rest")
    ]


SCALE_8 = [72, 74, 76, 77, 79, 77, 76, 74]


class TestOnsetGrid(unittest.TestCase):
    """The onset grid is a position grid: no ceiling, no floor, sign preserved."""

    def test_beat_zero_is_reachable(self) -> None:
        self.assertEqual(quantize_onset(0.0, meter=METER), 0.0)

    def test_no_ceiling_at_four(self) -> None:
        # The duration grid stops at 4.0. A section is longer than one bar.
        self.assertEqual(quantize_onset(7.0, meter=METER), 7.0)
        self.assertEqual(quantize_onset(31.0, meter=METER), 31.0)

    def test_offbeat_positions_are_expressible(self) -> None:
        self.assertEqual(quantize_onset(2.5, meter=METER), 2.5)
        self.assertEqual(quantize_onset(0.75, meter=METER), 0.75)

    def test_snaps_to_the_sixteenth_grid(self) -> None:
        self.assertEqual(ONSET_GRID_BEATS, 0.25)
        self.assertEqual(quantize_onset(1.03, meter=METER), 1.0)
        self.assertEqual(quantize_onset(1.2, meter=METER), 1.25)

    def test_count_in_notes_stay_negative(self) -> None:
        """A note before beat 0 must not read as a note ON beat 0."""
        self.assertLess(quantize_onset(-2.0, meter=METER), 0.0)

    def test_duration_grid_is_untouched(self) -> None:
        """Durations keep their own grid - this fix must not widen note lengths."""
        self.assertEqual(quantize_beats(1.05, meter=METER), 1.0)
        self.assertEqual(quantize_beats(1.6, meter=METER), 1.5)
        self.assertEqual(quantize_beats(2.1, meter=METER), 2.0)


@unittest.skipUnless(hum_analysis_available(), "librosa not installed")
class TestRecordedMelodyKeepsItsTiming(unittest.TestCase):
    """Real audio in, real beats out."""

    def test_eight_quarter_notes_span_eight_beats(self) -> None:
        res = transcribe_hum_audio(
            _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=0
        )
        self.assertEqual(res.get("status"), "usable", res.get("message"))
        self.assertEqual(_beats(res), [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    def test_nothing_piles_onto_one_beat(self) -> None:
        """The old ceiling stacked every note after bar 1 on the same onset."""
        beats = _beats(
            transcribe_hum_audio(
                _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=0
            )
        )
        self.assertEqual(len(beats), len(set(beats)), f"duplicate onsets: {beats}")
        self.assertEqual(beats, sorted(beats))

    def test_melody_reaches_the_last_bar_it_was_played_in(self) -> None:
        beats = _beats(
            transcribe_hum_audio(
                _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=0
            )
        )
        self.assertGreaterEqual(max(beats), 7.0 - 0.25)

    def test_no_note_is_lost(self) -> None:
        res = transcribe_hum_audio(
            _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=0
        )
        self.assertEqual(len(_beats(res)), len(SCALE_8))


@unittest.skipUnless(hum_analysis_available(), "librosa not installed")
class TestCountInIsOnlyRemovedWhenItIsThere(unittest.TestCase):
    """The count-in plays in a separate iframe; the take may not contain it.

    Subtracting one regardless pushed the opening bars before beat 0, where they were
    dropped - the musician's first bar was deleted, and the "your recording + chords"
    preview trimmed the same seconds off the audio.
    """

    def test_humming_without_a_count_in_keeps_every_note(self) -> None:
        res = transcribe_hum_audio(
            _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=1
        )
        self.assertFalse(res.get("count_in_applied"))
        self.assertEqual(res.get("count_in_sec"), 0.0)
        self.assertEqual(res.get("count_in_requested_sec"), BAR_SEC)
        self.assertEqual(_beats(res), [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    def test_a_real_count_in_is_removed(self) -> None:
        res = transcribe_hum_audio(
            _wav(SCALE_8, lead_silence=BAR_SEC),
            bpm=BPM,
            meter=METER,
            key="C",
            count_in_bars=1,
        )
        self.assertTrue(res.get("count_in_applied"))
        self.assertEqual(res.get("count_in_sec"), BAR_SEC)
        self.assertEqual(_beats(res), [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    def test_the_downbeat_note_survives_a_counted_in_take(self) -> None:
        """pyin reports an onset a frame early; an exact boundary dropped it."""
        res = transcribe_hum_audio(
            _wav(SCALE_8, lead_silence=BAR_SEC),
            bpm=BPM,
            meter=METER,
            key="C",
            count_in_bars=1,
        )
        midis = [
            int(e.get("midi") or 0)
            for e in (res.get("events") or [])
            if not e.get("is_rest")
        ]
        self.assertEqual(midis, SCALE_8)

    def test_the_proposal_says_what_it_did(self) -> None:
        """Flag it, do not silently alter it."""
        res = transcribe_hum_audio(
            _wav(SCALE_8), bpm=BPM, meter=METER, key="C", count_in_bars=1
        )
        for field in ("count_in_applied", "count_in_requested_sec", "first_note_sec"):
            self.assertIn(field, res)
        events = [e for e in (res.get("events") or []) if not e.get("is_rest")]
        self.assertIn("origin_shift_beats", events[0])

    def test_a_late_entry_is_not_dragged_to_the_downbeat(self) -> None:
        """Two beats of rest before the first note is music, not misalignment."""
        res = transcribe_hum_audio(
            _wav([72, 74, 76, 77], lead_silence=2 * SPB),
            bpm=BPM,
            meter=METER,
            key="C",
            count_in_bars=0,
        )
        beats = _beats(res)
        self.assertGreaterEqual(beats[0], 1.5, f"late entrance was re-anchored: {beats}")


def _synth(notes: list[tuple[float, int, float]], *, bpm: int, gap: float = 0.03,
           tail: float = 0.3) -> bytes:
    """WAV bytes for ``[(start_beat, midi, duration_beats)]`` laid on one timeline."""
    spb = 60.0 / bpm
    end = max(b + d for b, _m, d in notes) * spb + tail
    buf = _quiet(end)
    for start_beat, midi, dur_beats in notes:
        seg = _tone(midi, max(0.04, dur_beats * spb - gap))
        i0 = int(start_beat * spb * SR)
        i1 = min(len(buf), i0 + len(seg))
        buf[i0:i1] += seg[: i1 - i0]
    pcm = (np.clip(buf, -1, 1) * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def _transcribe(notes, *, bpm: int, meter: str = "4/4", count_in_bars: int = 0,
                gap: float = 0.03) -> dict:
    return transcribe_hum_audio(
        _synth(notes, bpm=bpm, gap=gap),
        bpm=bpm,
        meter=meter,
        key="C",
        count_in_bars=count_in_bars,
    )


def _durations(result: dict) -> list[float]:
    return [
        float(e.get("duration_beats") or 0.0)
        for e in (result.get("events") or [])
        if not e.get("is_rest")
    ]


def _span(result: dict) -> float:
    rows = [e for e in (result.get("events") or []) if not e.get("is_rest")]
    return max(float(e["beat"]) + float(e["duration_beats"]) for e in rows)


RISING = [72, 74, 76, 77, 79, 81, 83, 84]


@unittest.skipUnless(hum_analysis_available(), "librosa not installed")
class TestRhythmicExpressionSurvives(unittest.TestCase):
    """Fixture results: synthesised tones, not a live microphone.

    Every case here is the owner's item-4A validation matrix. The point of each is
    that intentional rhythm reaches the staff unaltered - the transcriber may not
    tidy a performance into something squarer than it was.
    """

    def test_a_note_starting_on_beat_zero_is_kept(self) -> None:
        res = _transcribe([(0.0, 72, 1.0), (1.0, 74, 1.0)], bpm=120)
        self.assertEqual(_beats(res)[0], 0.0)

    def test_four_bars_of_quarter_notes_land_exactly(self) -> None:
        notes = [(float(i), RISING[i % 8], 1.0) for i in range(16)]
        res = _transcribe(notes, bpm=120)
        self.assertEqual(_beats(res), [float(i) for i in range(16)])

    def test_the_melody_spans_what_was_played(self) -> None:
        notes = [(float(i), RISING[i % 8], 1.0) for i in range(16)]
        self.assertEqual(_span(_transcribe(notes, bpm=120)), 16.0)

    def test_onsets_are_strictly_increasing(self) -> None:
        notes = [(float(i), RISING[i % 8], 1.0) for i in range(16)]
        beats = _beats(_transcribe(notes, bpm=120))
        self.assertEqual(beats, sorted(set(beats)))

    def test_eighth_notes_keep_their_offbeats(self) -> None:
        notes = [(i * 0.5, RISING[i % 8], 0.5) for i in range(16)]
        res = _transcribe(notes, bpm=120)
        self.assertEqual(_beats(res), [i * 0.5 for i in range(16)])
        self.assertEqual(set(_durations(res)), {0.5})

    def test_sixteenth_onsets_are_exact(self) -> None:
        notes = [(i * 0.25, RISING[i % 8], 0.25) for i in range(8)]
        res = _transcribe(notes, bpm=72, gap=0.02)
        self.assertEqual(_beats(res), [i * 0.25 for i in range(8)])

    def test_syncopated_entries_are_not_pulled_onto_the_downbeat(self) -> None:
        """A phrase sung on the second eighth of each bar must stay there."""
        notes = [(0.5, 72, 0.5), (1.5, 76, 0.5), (2.5, 79, 0.5), (3.5, 72, 0.5)]
        res = _transcribe(notes, bpm=100)
        self.assertEqual(_beats(res), [0.5, 1.5, 2.5, 3.5])
        first = [e for e in res["events"] if not e.get("is_rest")][0]
        self.assertEqual(first.get("origin_shift_beats"), 0.0)

    def test_dotted_eighth_onsets_survive(self) -> None:
        notes = [(0.0, 72, 0.75), (0.75, 74, 0.75), (1.5, 76, 0.5), (2.0, 77, 2.0)]
        self.assertEqual(_beats(_transcribe(notes, bpm=96)), [0.0, 0.75, 1.5, 2.0])

    def test_a_deliberate_late_entry_keeps_its_beat(self) -> None:
        notes = [(2.0, 72, 1.0), (3.0, 74, 1.0), (4.0, 76, 1.0)]
        self.assertEqual(_beats(_transcribe(notes, bpm=120)), [2.0, 3.0, 4.0])

    def test_a_rest_between_phrases_is_kept_and_timing_holds(self) -> None:
        notes = [(0.0, 72, 1.0), (1.0, 74, 1.0), (4.0, 76, 1.0), (5.0, 77, 1.0)]
        res = _transcribe(notes, bpm=120)
        self.assertEqual(_beats(res), [0.0, 1.0, 4.0, 5.0])
        self.assertTrue([e for e in res["events"] if e.get("is_rest")])

    def test_repeated_pitches_with_a_real_gap_stay_separate(self) -> None:
        """Three re-articulated Cs are three notes, not one long one."""
        notes = [(0.0, 72, 0.6), (1.0, 72, 0.6), (2.0, 72, 0.6), (3.0, 74, 0.6)]
        res = _transcribe(notes, bpm=110)
        self.assertEqual(_beats(res), [0.0, 1.0, 2.0, 3.0])
        self.assertEqual(
            [int(e["midi"]) for e in res["events"] if not e.get("is_rest")],
            [72, 72, 72, 74],
        )


@unittest.skipUnless(hum_analysis_available(), "librosa not installed")
class TestTemposAndMeters(unittest.TestCase):
    def test_bpm_60(self) -> None:
        notes = [(float(i), RISING[i], 1.0) for i in range(6)]
        self.assertEqual(_beats(_transcribe(notes, bpm=60)), [0.0, 1, 2, 3, 4, 5])

    def test_bpm_180(self) -> None:
        notes = [(float(i), RISING[i], 1.0) for i in range(8)]
        self.assertEqual(_beats(_transcribe(notes, bpm=180)), [float(i) for i in range(8)])

    def test_three_four(self) -> None:
        notes = [(float(i), RISING[i % 8], 1.0) for i in range(9)]
        res = _transcribe(notes, bpm=120, meter="3/4")
        self.assertEqual(_beats(res), [float(i) for i in range(9)])
        # Bar lines follow the meter: 3 pulses to a bar.
        measures = [int(e["measure"]) for e in res["events"] if not e.get("is_rest")]
        self.assertEqual(measures[:6], [1, 1, 1, 2, 2, 2])

    def test_six_eight_compound(self) -> None:
        """6/8 counts eighth-note pulses here (``_beats_per_bar`` = numerator)."""
        notes = [(float(i), RISING[i % 8], 1.0) for i in range(12)]
        res = _transcribe(notes, bpm=150, meter="6/8")
        self.assertEqual(_beats(res), [float(i) for i in range(12)])
        measures = [int(e["measure"]) for e in res["events"] if not e.get("is_rest")]
        self.assertEqual(measures[0], 1)
        self.assertEqual(measures[6], 2)


@unittest.skipUnless(hum_analysis_available(), "librosa not installed")
class TestDurationGridLimits(unittest.TestCase):
    """What this fix does NOT reach, pinned so nobody reads the gap as success.

    Note LENGTHS are quantized to the duration grid, whose finest value is an eighth.
    That matches the staff: ``_duration_to_abc_eighths`` renders ``L:1/8`` integer
    units with a ``max(0.5, ...)`` floor, so widening the grid alone would make the
    stored melody disagree with the notation it is drawn from. Onsets are exact to a
    sixteenth either way, which is what recording/chord alignment depends on.
    """

    def test_sixteenth_lengths_become_eighths(self) -> None:
        notes = [(i * 0.25, RISING[i % 8], 0.25) for i in range(8)]
        res = _transcribe(notes, bpm=72, gap=0.02)
        self.assertEqual(set(_durations(res)), {0.5})

    def test_consecutive_sixteenths_therefore_overlap(self) -> None:
        """A documented consequence, not an accident: 0.25 apart, 0.5 long."""
        notes = [(i * 0.25, RISING[i % 8], 0.25) for i in range(8)]
        res = _transcribe(notes, bpm=72, gap=0.02)
        self.assertGreater(_span(res), 2.0)

    def test_dotted_eighth_length_is_not_expressible(self) -> None:
        notes = [(0.0, 72, 0.75), (0.75, 74, 0.75), (1.5, 76, 0.5), (2.0, 77, 2.0)]
        self.assertEqual(_durations(_transcribe(notes, bpm=96))[0], 0.5)


if __name__ == "__main__":
    unittest.main()
