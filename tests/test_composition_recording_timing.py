"""A Composition take's alignment comes from measurement, or it is reported as unknown.

These are unit tests over the timing contract only. They do not render the recorder and they
do not prove the browser behaves - that needs a real microphone and is explicitly outstanding.
"""

from __future__ import annotations

import unittest

from composition_recording_timing import (
    SOURCE_BASIC_RECORDER,
    SOURCE_SHARED_CLOCK,
    SOURCE_UPLOAD,
    accept_take,
    alignment_caption,
    count_in_sec_for_transcription,
    forget_take,
    measured_music_offset_sec,
    stored_timing,
    sync_status,
    take_id_key,
)

SR = 48000


def _measured(*, music_start_frame: int, capture_first_frame: int = 0, **extra) -> dict:
    """A timing mapping of the shape the shared recorder returns."""
    out = {
        "source": SOURCE_SHARED_CLOCK,
        "sample_rate": SR,
        "capture_first_frame": capture_first_frame,
        "music_start_frame": music_start_frame,
        "music_offset_sec": (music_start_frame - capture_first_frame) / SR,
    }
    out.update(extra)
    return out


class TestMeasuredOffset(unittest.TestCase):
    def test_a_measured_take_reports_its_offset(self) -> None:
        timing = _measured(music_start_frame=SR * 2)
        self.assertAlmostEqual(measured_music_offset_sec(timing), 2.0, places=6)

    def test_zero_is_a_real_offset_not_a_missing_one(self) -> None:
        """A take that demonstrably starts on the downbeat is measured, not unknown."""
        timing = _measured(music_start_frame=0)
        self.assertEqual(measured_music_offset_sec(timing), 0.0)
        self.assertIsNotNone(measured_music_offset_sec(timing))

    def test_an_incomplete_report_is_unmeasured_even_with_frames(self) -> None:
        """Frame counters alone are not enough: the shared contract requires every field.

        ``sync_state`` names ``music_offset_sec`` among the fields it must see, so a take
        missing it is reported unsynchronized rather than reconstructed from the frames.
        """
        timing = _measured(music_start_frame=SR)
        timing.pop("music_offset_sec", None)
        self.assertIsNone(measured_music_offset_sec(timing))
        self.assertFalse(sync_status(timing)["synchronized"])

    def test_capture_start_is_subtracted(self) -> None:
        timing = _measured(music_start_frame=SR * 3, capture_first_frame=SR)
        self.assertAlmostEqual(measured_music_offset_sec(timing), 2.0, places=6)

    def test_nothing_measured_is_none(self) -> None:
        self.assertIsNone(measured_music_offset_sec(None))
        self.assertIsNone(measured_music_offset_sec({}))

    def test_a_basic_recorder_take_is_not_measured(self) -> None:
        self.assertIsNone(
            measured_music_offset_sec({"source": SOURCE_BASIC_RECORDER, "sample_rate": SR})
        )

    def test_an_upload_is_not_measured(self) -> None:
        self.assertIsNone(measured_music_offset_sec({"source": SOURCE_UPLOAD}))

    def test_a_partial_report_is_not_measured(self) -> None:
        timing = _measured(music_start_frame=SR)
        timing.pop("sample_rate")
        self.assertIsNone(measured_music_offset_sec(timing))


class TestSyncStatusIsReportedWithAReason(unittest.TestCase):
    def test_a_measured_take_is_synchronized(self) -> None:
        status = sync_status(_measured(music_start_frame=SR))
        self.assertTrue(status["synchronized"])
        self.assertEqual(status["reason"], "")

    def test_an_unmeasured_take_says_why(self) -> None:
        status = sync_status({"source": SOURCE_UPLOAD})
        self.assertFalse(status["synchronized"])
        self.assertTrue(str(status["reason"]).strip())

    def test_nothing_at_all_says_why(self) -> None:
        status = sync_status(None)
        self.assertFalse(status["synchronized"])
        self.assertTrue(str(status["reason"]).strip())

    def test_the_caption_never_claims_alignment_it_cannot_prove(self) -> None:
        caption = alignment_caption({"source": SOURCE_BASIC_RECORDER})
        self.assertIn("not aligned", caption)

    def test_the_caption_states_the_measurement_when_there_is_one(self) -> None:
        caption = alignment_caption(_measured(music_start_frame=SR * 2))
        self.assertIn("2.00s", caption)


class TestWhatTranscriptionIsTold(unittest.TestCase):
    def test_a_measured_take_hands_over_its_offset(self) -> None:
        got = count_in_sec_for_transcription(
            _measured(music_start_frame=SR * 2), requested_sec=2.0
        )
        self.assertTrue(got["measured"])
        self.assertAlmostEqual(got["count_in_sec"], 2.0, places=6)

    def test_an_unmeasured_take_hands_over_nothing(self) -> None:
        """None, not the requested count-in: the requested value is not a measurement."""
        got = count_in_sec_for_transcription(
            {"source": SOURCE_BASIC_RECORDER}, requested_sec=2.0
        )
        self.assertFalse(got["measured"])
        self.assertIsNone(got["count_in_sec"])
        self.assertEqual(got["requested_sec"], 2.0)
        self.assertTrue(got["reason"])

    def test_a_measured_downbeat_take_hands_over_zero(self) -> None:
        got = count_in_sec_for_transcription(_measured(music_start_frame=0))
        self.assertTrue(got["measured"])
        self.assertEqual(got["count_in_sec"], 0.0)


class TestTakeIdentityIsPerSection(unittest.TestCase):
    def _take(self, take_id: str, frame: int = SR) -> dict:
        return {
            "take_id": take_id,
            "wav": b"RIFF-not-really-audio",
            "timing": _measured(music_start_frame=frame),
        }

    def test_a_take_is_accepted_once(self) -> None:
        ss: dict = {}
        self.assertIsNotNone(accept_take(ss, "verse", self._take("t1")))
        self.assertIsNone(accept_take(ss, "verse", self._take("t1")))

    def test_a_new_take_for_the_same_section_is_accepted(self) -> None:
        ss: dict = {}
        accept_take(ss, "verse", self._take("t1"))
        self.assertIsNotNone(accept_take(ss, "verse", self._take("t2")))

    def test_two_sections_do_not_suppress_each_other(self) -> None:
        ss: dict = {}
        accept_take(ss, "verse", self._take("t1"))
        self.assertIsNotNone(
            accept_take(ss, "chorus", self._take("t1")),
            "a chorus take was swallowed by the verse's take id",
        )

    def test_the_sections_keep_their_own_timing(self) -> None:
        ss: dict = {}
        accept_take(ss, "verse", self._take("t1", frame=SR))
        accept_take(ss, "chorus", self._take("t2", frame=SR * 3))
        self.assertAlmostEqual(
            measured_music_offset_sec(stored_timing(ss, "verse")), 1.0, places=6
        )
        self.assertAlmostEqual(
            measured_music_offset_sec(stored_timing(ss, "chorus")), 3.0, places=6
        )

    def test_an_empty_or_malformed_take_is_ignored(self) -> None:
        ss: dict = {}
        self.assertIsNone(accept_take(ss, "verse", None))
        self.assertIsNone(accept_take(ss, "verse", {"take_id": "", "wav": b"x"}))
        self.assertIsNone(accept_take(ss, "verse", {"take_id": "t", "wav": b""}))
        self.assertNotIn(take_id_key("verse"), ss)

    def test_forgetting_a_take_lets_the_same_id_back_in(self) -> None:
        ss: dict = {}
        accept_take(ss, "verse", self._take("t1"))
        forget_take(ss, "verse")
        self.assertIsNotNone(accept_take(ss, "verse", self._take("t1")))
        self.assertEqual(stored_timing(ss, "verse").get("sample_rate"), SR)


class TestNoMultitrackStateIsTouched(unittest.TestCase):
    """Composition must not acquire slots, mixers or Multitrack take bookkeeping."""

    def test_only_composition_keys_are_written(self) -> None:
        ss: dict = {}
        accept_take(
            ss,
            "verse",
            {"take_id": "t1", "wav": b"RIFF", "timing": _measured(music_start_frame=SR)},
        )
        for key in ss:
            self.assertTrue(
                str(key).startswith("_composer_"),
                f"{key!r} is not a Composition-owned session key",
            )

    def test_no_mt_prefixed_keys_appear(self) -> None:
        ss: dict = {}
        accept_take(
            ss,
            "verse",
            {"take_id": "t1", "wav": b"RIFF", "timing": _measured(music_start_frame=SR)},
        )
        self.assertFalse([k for k in ss if str(k).startswith(("mt_", "_mt_"))])


if __name__ == "__main__":
    unittest.main()
