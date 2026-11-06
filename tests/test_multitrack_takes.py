"""A recorded Multitrack take can be thrown away in one click and re-recorded cleanly."""
import unittest

from multitrack_slots import MULTITRACK_SLOTS
from multitrack_takes import (
    adopt_restored_layers_as_saved,
    discard_button_label,
    discard_take,
    is_take_saved,
    mark_take_saved,
    mark_take_unsaved,
    recorder_widget_key,
    take_nonce,
    take_status_line,
)

SLOT = "Sax / winds"
OTHER = "Guitar"


def _session(**tracks):
    base = {slot: None for slot in MULTITRACK_SLOTS}
    base.update(tracks)
    return {
        "mt_tracks": base,
        "mt_track_filenames": {slot: f"{slot}.wav" for slot in MULTITRACK_SLOTS},
    }


class TestTakeLifecycle(unittest.TestCase):
    def test_a_fresh_recording_is_an_unsaved_take(self):
        s = _session(**{SLOT: b"audio"})
        mark_take_unsaved(s, SLOT)
        self.assertFalse(is_take_saved(s, SLOT))
        self.assertIn("Unsaved take", take_status_line(s, SLOT))
        self.assertIn("Discard take", discard_button_label(s, SLOT))

    def test_saving_turns_the_take_into_a_layer(self):
        s = _session(**{SLOT: b"audio"})
        mark_take_unsaved(s, SLOT)
        mark_take_saved(s, SLOT)
        self.assertTrue(is_take_saved(s, SLOT))
        self.assertIn("Saved layer", take_status_line(s, SLOT))
        self.assertIn("Delete layer", discard_button_label(s, SLOT))

    def test_no_audio_means_no_status_line(self):
        self.assertEqual(take_status_line(_session(), SLOT), "")


class TestDiscard(unittest.TestCase):
    def test_discard_clears_the_audio_and_reports_it(self):
        s = _session(**{SLOT: b"audio"})
        mark_take_unsaved(s, SLOT)
        self.assertTrue(discard_take(s, SLOT))
        self.assertIsNone(s["mt_tracks"][SLOT])
        self.assertFalse(is_take_saved(s, SLOT))
        self.assertFalse(discard_take(s, SLOT))            # nothing left to discard

    def test_discard_only_touches_its_own_layer(self):
        s = _session(**{SLOT: b"sax", OTHER: b"gtr"})
        mark_take_saved(s, OTHER)
        s["multitrack_backing_music_wav"] = b"backing"
        s["mixed_track_wav"] = b"mix"
        discard_take(s, SLOT)
        self.assertEqual(s["mt_tracks"][OTHER], b"gtr")
        self.assertTrue(is_take_saved(s, OTHER))
        self.assertEqual(s["multitrack_backing_music_wav"], b"backing")
        self.assertEqual(s["mixed_track_wav"], b"mix")

    def test_discard_rebuilds_the_recorder_so_the_old_take_stops_playing(self):
        s = _session(**{SLOT: b"audio"})
        first = recorder_widget_key(s, SLOT, "record")
        s[first] = "stale-recording-object"
        discard_take(s, SLOT)
        second = recorder_widget_key(s, SLOT, "record")
        self.assertNotEqual(first, second)                 # a NEW widget, so the old take is gone
        self.assertNotIn(first, s)
        self.assertEqual(take_nonce(s, SLOT), 1)

    def test_record_discard_record_again_repeats_cleanly(self):
        s = _session()
        keys = set()
        for take in range(3):
            key = recorder_widget_key(s, SLOT, "record")
            keys.add(key)
            s["mt_tracks"][SLOT] = f"take{take}".encode()
            mark_take_unsaved(s, SLOT)
            discard_take(s, SLOT)
            self.assertIsNone(s["mt_tracks"][SLOT])
        self.assertEqual(len(keys), 3)                     # every attempt got its own widget

    def test_the_first_widget_key_is_the_legacy_one(self):
        s = _session()
        self.assertEqual(recorder_widget_key(s, SLOT, "record"), f"mt_record_{SLOT}")
        self.assertEqual(recorder_widget_key(s, SLOT, "upload"), f"mt_upload_{SLOT}")


class TestRestoredProjects(unittest.TestCase):
    def test_layers_restored_from_a_project_count_as_saved(self):
        s = _session(**{SLOT: b"audio", OTHER: None})
        adopt_restored_layers_as_saved(s, MULTITRACK_SLOTS)
        self.assertTrue(is_take_saved(s, SLOT))
        self.assertIn("Saved layer", take_status_line(s, SLOT))
        self.assertFalse(is_take_saved(s, OTHER))

    def test_a_take_in_progress_keeps_its_unsaved_state_across_reruns(self):
        s = _session(**{SLOT: b"audio"})
        mark_take_unsaved(s, SLOT)
        for _ in range(3):
            adopt_restored_layers_as_saved(s, MULTITRACK_SLOTS)
        self.assertFalse(is_take_saved(s, SLOT))

    def test_it_is_safe_without_a_track_map(self):
        s = {}
        adopt_restored_layers_as_saved(s, MULTITRACK_SLOTS)
        self.assertEqual(s, {})


if __name__ == "__main__":
    unittest.main()
