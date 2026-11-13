"""Issue 78 Slice 78A: one Align offset must mean one thing everywhere.

The defect these tests pin: the transport preview computed ``musicStart + Math.max(0,
delay)``, so a negative Align moved nothing, while the export mixer did ``y = y[-ds:]``
and really did drop that much from the front. The musician checked a take by ear in the
preview and a different take was written to the file.

So the tests are mostly about agreement rather than about either surface alone:
``multitrack_align_contract`` states the rule once, the mixer applies it, and the
transport receives the same two numbers in its track payload. The transport's own
scheduling is measured in a browser by ``scripts/_accept_issue78a_transport.py``; what is
checked here is that it is handed the right instructions and that the file it has to
agree with is built the same way.

Also pinned here: the stored recording is never modified, which is what makes a negative
offset recoverable by returning the slider to 0.
"""

from __future__ import annotations

import io
import unittest
import wave

import numpy as np

import multitrack_align_contract as align
from backing_audio import wav_bytes_from_float
from streamlit_music_practice_app import mix_multitrack, multitrack_studio_track_payloads

SR = 44100
TONE_HZ = 440.0


def _take_with_transient(*, seconds: float = 4.0, click_at: float = 1.0,
                         sr: int = SR) -> bytes:
    """A quiet tone carrying one unmistakable full-scale spike.

    The spike is what makes a position measurable: after mixing, the sample index of the
    largest value says exactly where this take ended up.
    """
    n = int(sr * seconds)
    t = np.arange(n) / sr
    y = 0.12 * np.sin(2 * np.pi * TONE_HZ * t)
    i = int(round(sr * click_at))
    if 0 <= i < n:
        y[i] = 0.98
    if sr == SR:
        return wav_bytes_from_float(y.astype(np.float32))
    # wav_bytes_from_float always writes 44.1 kHz, so a legacy-rate fixture is written
    # here instead. Asserting the rate below is what caught that.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _item(wav: bytes, *, name: str = "Guitar", delay: float = 0.0,
          volume: float = 1.0, mute: bool = False, solo: bool = False) -> dict:
    return {
        "slot": name,
        "name": name,
        "audio_bytes": wav,
        "filename": f"{name.lower()}.wav",
        "volume": volume,
        "delay": delay,
        "mute": mute,
        "solo": solo,
    }


def _peak_sec(mixed: np.ndarray, sr: int = SR) -> float:
    return float(int(np.argmax(np.abs(mixed)))) / sr


class TheContractSaysWhereAudioGoes(unittest.TestCase):
    def test_a_positive_offset_delays_the_start_and_keeps_everything(self):
        s = align.resolve(0.75)
        self.assertAlmostEqual(s.start_delay_sec, 0.75)
        self.assertAlmostEqual(s.buffer_offset_sec, 0.0)

    def test_zero_puts_the_first_sample_on_bar_one(self):
        s = align.resolve(0.0)
        self.assertEqual((s.start_delay_sec, s.buffer_offset_sec), (0.0, 0.0))

    def test_a_negative_offset_starts_part_way_into_the_take(self):
        s = align.resolve(-0.75)
        self.assertAlmostEqual(s.start_delay_sec, 0.0)
        self.assertAlmostEqual(s.buffer_offset_sec, 0.75)

    def test_the_offset_can_be_read_back_off_the_schedule(self):
        for d in (-3.0, -0.05, 0.0, 0.05, 3.0):
            self.assertAlmostEqual(align.resolve(d).delay, d, places=9)

    def test_nonsense_is_treated_as_no_offset_rather_than_crashing(self):
        for bad in (None, "", "later", float("nan"), float("inf"), float("-inf"), {}):
            s = align.resolve(bad)
            self.assertEqual((s.start_delay_sec, s.buffer_offset_sec), (0.0, 0.0), bad)

    def test_the_description_says_which_audio_is_left_out(self):
        self.assertIn("not heard", align.describe(-1.0))
        self.assertIn("set Align back to 0", align.describe(-1.0))
        self.assertIn("Nothing is left out", align.describe(1.0))
        self.assertIn("whole recording", align.describe(0.0))


class TheSamplesMoveTheWayTheContractSays(unittest.TestCase):
    def setUp(self):
        self.y = np.arange(1000, dtype=np.float32)

    def test_a_positive_offset_pads_the_front_and_loses_nothing(self):
        out = align.apply_to_samples(self.y, 0.1, 1000)
        self.assertEqual(out.size, 1100)
        self.assertTrue(np.all(out[:100] == 0))
        np.testing.assert_array_equal(out[100:], self.y)

    def test_a_negative_offset_skips_the_head_only(self):
        out = align.apply_to_samples(self.y, -0.1, 1000)
        self.assertEqual(out.size, 900)
        np.testing.assert_array_equal(out, self.y[100:])

    def test_zero_changes_nothing_at_all(self):
        np.testing.assert_array_equal(align.apply_to_samples(self.y, 0.0, 1000), self.y)

    def test_reading_an_offset_never_modifies_the_caller_s_array(self):
        before = self.y.copy()
        for d in (-0.25, 0.0, 0.25):
            align.apply_to_samples(self.y, d, 1000)
        np.testing.assert_array_equal(self.y, before)

    def test_dragged_past_the_end_leaves_a_sliver_not_silence(self):
        out = align.apply_to_samples(self.y, -5.0, 1000)
        self.assertGreater(out.size, 0)
        self.assertEqual(out.size, int(align.MIN_AUDIBLE_SEC * 1000))

    def test_an_empty_take_stays_empty(self):
        self.assertEqual(align.apply_to_samples(np.zeros(0), -1.0, SR).size, 0)

    def test_the_transport_payload_carries_the_same_two_numbers(self):
        for d in (-2.5, -0.1, 0.0, 0.1, 2.5):
            s = align.resolve(d)
            p = align.transport_payload(d)
            self.assertAlmostEqual(p["startDelaySec"], s.start_delay_sec)
            self.assertAlmostEqual(p["bufferOffsetSec"], s.buffer_offset_sec)


class TheExportedMixLandsWhereTheContractSays(unittest.TestCase):
    """The spike's position in the mix is the measurement."""

    def setUp(self):
        self.wav = _take_with_transient(click_at=1.0)

    def test_no_offset_keeps_the_transient_where_it_was_played(self):
        mixed = mix_multitrack(None, [_item(self.wav, delay=0.0)], sr=SR)
        self.assertAlmostEqual(_peak_sec(mixed), 1.0, places=3)

    def test_a_positive_offset_moves_the_transient_later_by_exactly_that_much(self):
        mixed = mix_multitrack(None, [_item(self.wav, delay=0.5)], sr=SR)
        self.assertAlmostEqual(_peak_sec(mixed), 1.5, places=3)

    def test_a_negative_offset_moves_the_transient_earlier_by_exactly_that_much(self):
        mixed = mix_multitrack(None, [_item(self.wav, delay=-0.5)], sr=SR)
        self.assertAlmostEqual(_peak_sec(mixed), 0.5, places=3)

    def test_two_layers_at_the_same_offset_stay_together(self):
        a = _take_with_transient(click_at=1.0)
        b = _take_with_transient(click_at=1.0)
        mixed = mix_multitrack(
            None,
            [_item(a, name="Guitar", delay=0.25), _item(b, name="Vocals", delay=0.25)],
            sr=SR,
        )
        self.assertAlmostEqual(_peak_sec(mixed), 1.25, places=3)

    def test_two_layers_at_different_offsets_land_that_far_apart(self):
        a = _take_with_transient(click_at=0.5)
        b = _take_with_transient(click_at=0.5)
        mixed = mix_multitrack(
            None,
            [_item(a, name="Guitar", delay=0.0), _item(b, name="Vocals", delay=1.0)],
            sr=SR,
        )
        peaks = np.sort(np.argsort(np.abs(mixed))[-2:]) / SR
        self.assertAlmostEqual(float(peaks[1] - peaks[0]), 1.0, places=3)

    def test_a_note_at_the_very_start_survives_zero_and_positive_offsets(self):
        """The 'notes cut off' complaint: nothing may vanish unless asked for."""
        wav = _take_with_transient(click_at=0.0)
        for d in (0.0, 0.5, 2.0):
            mixed = mix_multitrack(None, [_item(wav, delay=d)], sr=SR)
            self.assertAlmostEqual(_peak_sec(mixed), d, places=3,
                                   msg=f"opening note lost at delay {d}")

    def test_the_end_of_a_take_is_never_truncated(self):
        wav = _take_with_transient(seconds=3.0, click_at=2.99)
        mixed = mix_multitrack(None, [_item(wav, delay=0.0)], sr=SR)
        self.assertGreaterEqual(mixed.size / SR, 2.99)

    def test_mixing_does_not_modify_the_stored_recording(self):
        """What makes a negative offset recoverable: the bytes are left alone."""
        original = bytes(self.wav)
        item = _item(self.wav, delay=-1.5)
        mix_multitrack(None, [item], sr=SR)
        self.assertEqual(item["audio_bytes"], original)
        self.assertEqual(self.wav, original)

    def test_returning_align_to_zero_brings_the_skipped_audio_back(self):
        trimmed = mix_multitrack(None, [_item(self.wav, delay=-0.5)], sr=SR)
        restored = mix_multitrack(None, [_item(self.wav, delay=0.0)], sr=SR)
        self.assertAlmostEqual(_peak_sec(trimmed), 0.5, places=3)
        self.assertAlmostEqual(_peak_sec(restored), 1.0, places=3)
        self.assertGreater(restored.size, trimmed.size)

    def test_a_legacy_sixteen_kilohertz_layer_aligns_the_same_way(self):
        """Takes recorded before the 48 kHz capture fix must still line up."""
        wav16 = _take_with_transient(seconds=4.0, click_at=1.0, sr=16000)
        with wave.open(io.BytesIO(wav16), "rb") as wf:
            self.assertEqual(wf.getframerate(), 16000)
        mixed = mix_multitrack(None, [_item(wav16, delay=0.5)], sr=SR)
        self.assertAlmostEqual(_peak_sec(mixed), 1.5, places=2)

    def test_mute_and_solo_still_decide_what_is_in_the_mix(self):
        a = _take_with_transient(click_at=0.5)
        b = _take_with_transient(click_at=2.0)
        muted = mix_multitrack(
            None,
            [_item(a, name="Guitar"), _item(b, name="Vocals", mute=True)],
            sr=SR,
        )
        self.assertAlmostEqual(_peak_sec(muted), 0.5, places=3)
        soloed = mix_multitrack(
            None,
            [_item(a, name="Guitar"), _item(b, name="Vocals", solo=True)],
            sr=SR,
        )
        self.assertAlmostEqual(_peak_sec(soloed), 2.0, places=3)


class TheTransportIsHandedTheSameSchedule(unittest.TestCase):
    def test_the_payload_resolves_the_offset_rather_than_passing_it_raw(self):
        wav = _take_with_transient()
        items = [_item(wav, name="Guitar")]
        controls = {"Guitar": {"volume": 1.0, "mute": False, "solo": False,
                               "delay": -0.4}}
        payload = multitrack_studio_track_payloads(items, controls)[0]
        self.assertAlmostEqual(payload["delay"], -0.4)
        self.assertAlmostEqual(payload["startDelaySec"], 0.0)
        self.assertAlmostEqual(payload["bufferOffsetSec"], 0.4)

    def test_a_positive_offset_reaches_the_transport_as_a_start_delay(self):
        wav = _take_with_transient()
        controls = {"Guitar": {"volume": 1.0, "mute": False, "solo": False,
                               "delay": 0.4}}
        payload = multitrack_studio_track_payloads([_item(wav)], controls)[0]
        self.assertAlmostEqual(payload["startDelaySec"], 0.4)
        self.assertAlmostEqual(payload["bufferOffsetSec"], 0.0)

    def test_every_layer_carries_the_schedule(self):
        wav = _take_with_transient()
        items = [_item(wav, name="Guitar"), _item(wav, name="Vocals")]
        controls = {
            "Guitar": {"volume": 1.0, "mute": False, "solo": False, "delay": 0.0},
            "Vocals": {"volume": 1.0, "mute": False, "solo": False, "delay": -1.0},
        }
        for p in multitrack_studio_track_payloads(items, controls):
            self.assertIn("startDelaySec", p)
            self.assertIn("bufferOffsetSec", p)


class TheTransportScriptNoLongerRacesItsOwnDecode(unittest.TestCase):
    """Source-level guards. The behaviour itself is measured in the browser harness.

    These are deliberately about the shape of the generated script, because the two
    defects were both shapes: a start time chosen before an ``await``, and a clamp that
    discarded half of a control's range.
    """

    def setUp(self):
        from streamlit_music_practice_app import multitrack_studio_html

        self.html = multitrack_studio_html(
            backing_b64=None,
            tracks=[],
            bpm=100,
            beats_per_bar=4,
            count_in_bars=1,
            metronome_during_playback=True,
            loop_backing=True,
            backing_monitor_enabled=False,
            backing_monitor_volume=0.75,
            scope_label="full song",
            time_signature="4/4",
            backing_duration_sec=12.0,
        )

    def test_the_negative_half_of_align_is_no_longer_clamped_away(self):
        self.assertNotIn("Math.max(0, track.delay)", self.html)

    def test_the_transport_uses_the_resolved_schedule(self):
        self.assertIn("startDelaySec", self.html)
        self.assertIn("bufferOffsetSec", self.html)
        self.assertIn("src.start(when, bufferOffset)", self.html)

    def test_the_start_is_chosen_after_the_decoding(self):
        play = self.html.split("async function playSession()")[1]
        decode_at = play.index("await decodeInto")
        start_at = play.index("const countInStart")
        self.assertLess(decode_at, start_at,
                        "musicStart must be chosen after every buffer is decoded")

    def test_nothing_is_scheduled_at_the_clock_s_present_value(self):
        self.assertIn("ctx.currentTime + scheduleLead(ctx)", self.html)
        self.assertIn("SCHEDULE_LEAD_MIN_SEC", self.html)

    def test_a_retired_run_cannot_schedule_over_a_new_one(self):
        self.assertIn("if (run !== generation || audioCtx !== ctx) return;", self.html)
        self.assertIn("generation += 1;", self.html)

    def test_the_metronome_is_scheduled_on_the_audio_clock(self):
        self.assertIn("startMetronome", self.html)
        self.assertNotIn("}}, beatDuration() * 1000);", self.html)

    def test_the_label_does_not_claim_a_count_in_that_did_not_happen(self):
        from streamlit_music_practice_app import multitrack_studio_html

        none_html = multitrack_studio_html(
            backing_b64=None, tracks=[], bpm=100, beats_per_bar=4, count_in_bars=0,
            metronome_during_playback=False, loop_backing=False,
            backing_monitor_enabled=False, backing_monitor_volume=0.75,
            scope_label="full song", time_signature="4/4", backing_duration_sec=12.0,
        )
        self.assertIn("countInBeats() > 0", none_html)
        self.assertNotIn("Count-in finished", none_html)


if __name__ == "__main__":
    unittest.main()
