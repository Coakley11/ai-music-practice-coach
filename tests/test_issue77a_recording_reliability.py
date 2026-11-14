"""Issue 77A: the recorder must arm for a backing it can actually play, and name what it cannot.

These tests pin the three failures that reached the musician as one sentence, "One of the parts to
play along with could not be loaded":

1. the expected duration was PREDICTED (bars x bar_seconds x loops) while the renderer always leaves
   a second of decay after the music, so every prepared backing was rejected by the component's
   0.6 s tolerance and Record was disabled on every layer;
2. the estimate also counted a different set of bars from the one the render uses;
3. a monitored layer whose bytes are not decodable audio blocked every OTHER layer, and the
   acknowledgement carrying its identity was discarded.

The headline test is :meth:`TheRenderedBackingIsAccepted.test_a_rendered_backing_passes_the_tolerance`:
it builds audio shaped exactly like a rendered backing (music plus a one-second tail) and asserts
the number handed to the recorder now matches what the browser will measure.
"""

from __future__ import annotations

import io
import struct
import unittest
import wave


# --------------------------------------------------------------------------------------------
# helpers: real WAV bytes, written the way the app and other tools write them
# --------------------------------------------------------------------------------------------
def wav_bytes(seconds: float, *, rate: int = 44100, channels: int = 1, width: int = 2) -> bytes:
    frames = int(round(seconds * rate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(b"\x00" * (frames * channels * width))
    return buf.getvalue()


def wav_with_extra_chunk(seconds: float, *, rate: int = 44100) -> bytes:
    """A WAV carrying a LIST chunk before ``data``, as other editors write."""
    base = wav_bytes(seconds, rate=rate)
    head, rest = base[:12], base[12:]
    extra = b"LIST" + struct.pack("<I", 10) + b"INFOhello0"
    out = head + extra + rest
    return out[:4] + struct.pack("<I", len(out) - 8) + out[8:]


class WavDurationIsMeasuredNotGuessed(unittest.TestCase):
    def setUp(self) -> None:
        from multitrack_monitor_assets import wav_duration_sec

        self.duration = wav_duration_sec

    def test_a_plain_wav_reports_its_real_length(self) -> None:
        self.assertAlmostEqual(self.duration(wav_bytes(3.0)), 3.0, places=4)

    def test_sample_rates_and_channel_counts_this_app_does_not_prefer_still_read(self) -> None:
        # A legacy recording at 22.05 kHz, and a 48 kHz stereo file, are both valid audio.
        self.assertAlmostEqual(self.duration(wav_bytes(2.0, rate=22050)), 2.0, places=4)
        self.assertAlmostEqual(
            self.duration(wav_bytes(1.5, rate=48000, channels=2)), 1.5, places=4
        )
        self.assertAlmostEqual(
            self.duration(wav_bytes(1.0, rate=48000, channels=2, width=3)), 1.0, places=4
        )

    def test_a_chunk_before_data_does_not_hide_the_audio(self) -> None:
        self.assertAlmostEqual(self.duration(wav_with_extra_chunk(2.5)), 2.5, places=3)

    def test_a_truncated_file_reports_the_audio_that_is_actually_there(self) -> None:
        full = wav_bytes(4.0)
        cut = full[: len(full) // 2]
        measured = self.duration(cut)
        self.assertIsNotNone(measured)
        self.assertLess(measured, 4.0)
        self.assertGreater(measured, 0.5)

    def test_bytes_that_are_not_wav_are_refused_rather_than_guessed(self) -> None:
        self.assertIsNone(self.duration(b"RIFF" + b"\x00" * 4 + b"WAVEjunk" + b"\x7f" * 900))
        self.assertIsNone(self.duration(b"not audio at all"))
        self.assertIsNone(self.duration(b""))
        self.assertIsNone(self.duration(None))
        self.assertIsNone(self.duration("a string"))


class TheRenderedBackingIsAccepted(unittest.TestCase):
    """The defect that disabled Record for every song, and the fix, in one number."""

    def test_the_predicted_duration_never_matched_the_render(self) -> None:
        # What the page predicted, and what the renderer produced, for an 8-bar pass at 120 BPM
        # repeated twice. The 1.0 s difference is the decay headroom the renderer always leaves.
        predicted = 8 * 2.0 * 2
        rendered = wav_bytes(predicted + 1.0)
        from multitrack_monitor_assets import wav_duration_sec

        self.assertAlmostEqual(wav_duration_sec(rendered), predicted + 1.0, places=4)
        self.assertGreater(abs((predicted + 1.0) - predicted), 0.6, "the old tolerance was 0.6 s")

    def test_a_rendered_backing_passes_the_tolerance(self) -> None:
        from multitrack_monitor_assets import backing_duration_for_recorder, wav_duration_sec

        predicted = 8 * 2.0 * 2
        rendered = wav_bytes(predicted + 1.0)          # music + the one-second tail
        told = backing_duration_for_recorder(rendered, predicted)
        measured = wav_duration_sec(rendered)
        self.assertAlmostEqual(told, measured, places=6)
        self.assertLessEqual(
            abs(measured - told), 0.6,
            "the recorder would refuse the very backing the app just made",
        )

    def test_a_long_real_world_case_is_also_accepted(self) -> None:
        # The figures measured in the browser: 72 bars predicted, 78 rendered at 82 BPM, plus tail.
        bar = 4 * 60 / 82
        predicted = 72 * bar * 2
        rendered_sec = 78 * bar * 2 + 1.0
        from multitrack_monitor_assets import backing_duration_for_recorder

        rendered = wav_bytes(rendered_sec, rate=8000)   # small file, same arithmetic
        self.assertGreater(abs(rendered_sec - predicted), 30.0)
        told = backing_duration_for_recorder(rendered, predicted)
        self.assertLessEqual(abs(rendered_sec - told), 0.05)

    def test_unreadable_bytes_fall_back_instead_of_breaking_the_page(self) -> None:
        from multitrack_monitor_assets import backing_duration_for_recorder

        self.assertEqual(backing_duration_for_recorder(b"junk", 12.5), 12.5)
        self.assertEqual(backing_duration_for_recorder(None, 0), 0.0)
        self.assertEqual(backing_duration_for_recorder(b"junk", "not a number"), 0.0)


class TheFailedAssetIsNamed(unittest.TestCase):
    def setUp(self) -> None:
        from multitrack_monitor_assets import record_layer_recorder_ack

        self.record = record_layer_recorder_ack
        self.ss: dict = {"mt_name_Guitar": "Rhythm guitar"}

    def test_an_acknowledgement_is_kept_instead_of_discarded(self) -> None:
        self.assertTrue(self.record(self.ss, "Sax / winds", {
            "state": "failed", "error": "Unable to decode audio data",
            "failed_asset": "layer:Guitar", "bytes": 916, "mime": "audio/wav",
        }))
        from multitrack_monitor_assets import asset_load_failed, layer_recorder_ack

        self.assertTrue(asset_load_failed(self.ss, "Sax / winds"))
        self.assertEqual(layer_recorder_ack(self.ss, "Sax / winds")["bytes"], 916)

    def test_junk_is_not_recorded(self) -> None:
        self.assertFalse(self.record(self.ss, "Sax / winds", None))
        self.assertFalse(self.record(self.ss, "Sax / winds", {"state": "whatever"}))
        self.assertFalse(self.record(self.ss, "Sax / winds", "failed"))

    def test_the_asset_id_is_recovered_from_the_trace_when_not_sent_directly(self) -> None:
        self.record(self.ss, "Sax / winds", {
            "state": "failed", "error": "Unable to decode audio data",
            "trace": [{"step": "attempt", "asset": "backing"},
                      {"step": "attempt_failed", "asset": "layer:Extra layer"},
                      {"step": "failed", "asset": "layer:Extra layer"}],
        })
        from multitrack_monitor_assets import layer_recorder_ack

        self.assertEqual(
            layer_recorder_ack(self.ss, "Sax / winds")["failed_asset"], "layer:Extra layer"
        )

    def test_the_message_names_the_backing_and_says_what_to_do(self) -> None:
        from multitrack_monitor_assets import monitor_failure_message

        self.record(self.ss, "Sax / winds", {
            "state": "failed", "failed_asset": "backing",
            "error": "decoded 457.59 s, expected 421.46 s",
            "duration_sec": 457.59, "expected_duration_sec": 421.46,
        })
        msg = monitor_failure_message(self.ss, "Sax / winds")
        self.assertIn("generated backing track", msg)
        self.assertIn("457.6", msg)
        self.assertIn("Prepare the backing again", msg)
        self.assertNotIn("decoded 457.59 s, expected", msg)

    def test_the_message_names_the_layer_by_the_name_the_musician_gave_it(self) -> None:
        from multitrack_monitor_assets import monitor_failure_message

        self.record(self.ss, "Sax / winds", {
            "state": "failed", "failed_asset": "layer:Guitar",
            "error": "Unable to decode audio data",
        })
        msg = monitor_failure_message(self.ss, "Sax / winds")
        self.assertIn("Rhythm guitar", msg)
        self.assertIn("could not be played by this browser", msg)
        self.assertNotIn("Unable to decode audio data", msg)

    def test_nothing_is_said_when_the_load_succeeded(self) -> None:
        from multitrack_monitor_assets import monitor_failure_message

        self.record(self.ss, "Sax / winds", {"state": "ready", "duration_sec": 33.0})
        self.assertEqual(monitor_failure_message(self.ss, "Sax / winds"), "")

    def test_the_raw_detail_is_available_separately(self) -> None:
        from multitrack_monitor_assets import failure_detail

        self.record(self.ss, "Sax / winds", {
            "state": "failed", "failed_asset": "layer:Guitar", "bytes": 916,
            "mime": "audio/wav", "error": "Unable to decode audio data",
        })
        detail = failure_detail(self.ss, "Sax / winds")
        self.assertIn("layer:Guitar", detail)
        self.assertIn("916", detail)
        self.assertIn("Unable to decode audio data", detail)


class RecordingWithoutABadPartStaysHonest(unittest.TestCase):
    """Excluding a monitor must change the REQUEST, so the take's verdict stays truthful."""

    def setUp(self) -> None:
        self.slots = ("Guitar", "Bass", "Sax / winds")
        self.ss: dict = {
            "mt_tracks": {"Guitar": b"g" * 600, "Bass": b"b" * 600, "Sax / winds": None},
        }

    def test_an_excluded_layer_leaves_the_monitor_request(self) -> None:
        from multitrack_live_recorder import monitor_slots
        from multitrack_monitor_assets import exclude_monitor

        before = monitor_slots(self.ss, recording_slot="Sax / winds", slots=self.slots)
        self.assertEqual(sorted(before), ["Bass", "Guitar"])
        exclude_monitor(self.ss, "Guitar")
        after = monitor_slots(self.ss, recording_slot="Sax / winds", slots=self.slots)
        self.assertEqual(after, ["Bass"])

    def test_including_it_again_restores_it(self) -> None:
        from multitrack_live_recorder import monitor_slots
        from multitrack_monitor_assets import exclude_monitor, include_monitor

        exclude_monitor(self.ss, "Guitar")
        include_monitor(self.ss, "Guitar")
        self.assertEqual(
            sorted(monitor_slots(self.ss, recording_slot="Sax / winds", slots=self.slots)),
            ["Bass", "Guitar"],
        )

    def test_excluding_asks_the_recorder_to_load_again(self) -> None:
        from multitrack_monitor_assets import exclude_monitor, retry_nonce

        first = retry_nonce(self.ss)
        exclude_monitor(self.ss, "Guitar")
        self.assertGreater(retry_nonce(self.ss), first)

    def test_the_exclusion_is_announced_rather_than_applied_silently(self) -> None:
        from multitrack_monitor_assets import exclude_monitor, excluded_notice

        self.assertEqual(excluded_notice(self.ss), "")
        exclude_monitor(self.ss, "Guitar")
        notice = excluded_notice(self.ss)
        self.assertIn("Guitar", notice)
        self.assertIn("Recording without", notice)

    def test_a_take_that_lost_a_part_is_still_reported_unsynchronized(self) -> None:
        """The existing guarantee 77A relies on: fewer parts played than were requested."""
        from multitrack_live_recorder import sync_state

        verdict = sync_state({
            "source": "shared-clock", "sample_rate": 48000, "capture_first_frame": 0,
            "music_start_frame": 4800, "music_offset_sec": 0.1,
            "monitors_expected": 2, "monitor_count": 1,
        })
        self.assertFalse(verdict["synchronized"])
        self.assertIn("should have played along", verdict["reason"])


class IncomingAudioIsChecked(unittest.TestCase):
    def test_a_real_wav_is_accepted(self) -> None:
        from multitrack_audio_validation import check_audio_bytes

        check = check_audio_bytes(wav_bytes(1.0), "take.wav")
        self.assertTrue(check.ok, check.reason)
        self.assertAlmostEqual(float(check.duration_sec or 0), 1.0, places=2)

    def test_a_legacy_sample_rate_or_stereo_file_is_not_turned_away(self) -> None:
        from multitrack_audio_validation import check_audio_bytes

        self.assertTrue(check_audio_bytes(wav_bytes(1.0, rate=22050), "old.wav").ok)
        self.assertTrue(check_audio_bytes(wav_bytes(1.0, rate=48000, channels=2), "st.wav").ok)

    def test_the_file_that_disabled_recording_is_refused(self) -> None:
        from multitrack_audio_validation import check_audio_bytes

        junk = b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900
        check = check_audio_bytes(junk, "layer.wav")
        self.assertFalse(check.ok)
        self.assertTrue(check.reason)

    def test_a_tiny_file_is_refused_without_needing_a_decoder(self) -> None:
        from multitrack_audio_validation import check_audio_bytes

        check = check_audio_bytes(b"RIFF" + b"\x00" * 40, "tiny.wav")
        self.assertFalse(check.ok)
        self.assertIn("bytes", check.reason)

    def test_with_no_decoder_installed_the_check_accepts_rather_than_blocks(self) -> None:
        import multitrack_audio_validation as mav

        original_sf, original_lr = mav._try_soundfile, mav._try_librosa
        try:
            mav._try_soundfile = lambda data: None          # type: ignore[assignment]
            mav._try_librosa = lambda data, suffix: None     # type: ignore[assignment]
            check = mav.check_audio_bytes(wav_bytes(1.0), "take.wav")
        finally:
            mav._try_soundfile, mav._try_librosa = original_sf, original_lr
        self.assertTrue(check.ok)
        self.assertIn("not checked", check.reason)

    def test_the_rejection_says_nothing_was_changed(self) -> None:
        from multitrack_audio_validation import check_audio_bytes, rejection_message

        junk = b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900
        msg = rejection_message(check_audio_bytes(junk, "bad.wav"), "bad.wav", layer_name="Flute")
        self.assertIn("bad.wav", msg)
        self.assertIn("Nothing was changed", msg)
        self.assertIn("Flute", msg)


class ACachedBackingIsCheckedBeforeUse(unittest.TestCase):
    def test_a_readable_wav_is_adopted(self) -> None:
        from media_multitrack_catalog import _cached_backing_is_readable

        self.assertTrue(_cached_backing_is_readable(wav_bytes(5.0)))

    def test_a_corrupt_wav_is_not_adopted(self) -> None:
        from media_multitrack_catalog import _cached_backing_is_readable

        # Claims to be a WAV, cannot be read as one: this is the measured failure.
        self.assertFalse(_cached_backing_is_readable(
            b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900))

    def test_bytes_that_do_not_claim_to_be_a_wav_are_left_alone(self) -> None:
        """The check must not turn away other containers, or a stored placeholder.

        Narrow on purpose: refusing everything unparseable would break the standing contract that
        whatever is cached on disk comes back to the session, and would reject audio in containers
        this function has no business judging.
        """
        from media_multitrack_catalog import _cached_backing_is_readable

        self.assertTrue(_cached_backing_is_readable(b"disk-backing"))
        self.assertTrue(_cached_backing_is_readable(b"\x00\x00\x00 ID3 mp3 ish"))
        self.assertTrue(_cached_backing_is_readable(b""))

    def test_the_resolver_reports_the_reason_and_keeps_the_file(self) -> None:
        """A bad cached backing is skipped and explained; nothing is deleted."""
        import media_multitrack_catalog as cat

        ss: dict = {}
        original = cat._backing_bytes_from_local_path
        corrupt = b"RIFF" + (900).to_bytes(4, "little") + b"WAVEjunk" + b"\x7f" * 900
        try:
            cat._backing_bytes_from_local_path = lambda ws, rel: (  # type: ignore[assignment]
                corrupt if rel else None
            )
            got = cat.resolve_multitrack_backing_bytes(
                ss, "mt-1", existing_session={"backing_local_path": "x.wav"}
            )
        finally:
            cat._backing_bytes_from_local_path = original
        self.assertIsNone(got)
        self.assertEqual(ss.get("_mt_backing_load_error"), "cached_backing_not_readable")
        self.assertNotIn("multitrack_backing_music_wav", ss)


class TheComponentSendsTheAssetIdentity(unittest.TestCase):
    """Read from the component source: Python can only name the part if the id is sent."""

    def test_the_acknowledgement_carries_the_failed_asset(self) -> None:
        from pathlib import Path

        html = (Path(__file__).resolve().parents[1]
                / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
        self.assertIn("failed_asset: bk.failedAsset", html)
        self.assertIn("bk.failedAsset = String(asset.id", html)

    def test_the_duration_tolerance_is_still_enforced(self) -> None:
        from pathlib import Path

        html = (Path(__file__).resolve().parents[1]
                / "mission_recorder_component" / "index.html").read_text(encoding="utf-8")
        self.assertIn("DURATION_TOL_SEC = 0.6", html)
        self.assertIn("expectedDuration > 0", html)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
