"""Practice Log quick-save UX/data polish tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from practice_log_state import (
    build_practice_log_prefill,
    format_bpm_display,
    format_quick_save_success_message,
    migrate_practice_log_entry,
    practice_log_local_date,
    resolve_practice_log_bpm,
    section_display_label,
)


class TestPracticeLogLocalDate(unittest.TestCase):
    def test_new_york_date_when_utc_is_next_day(self) -> None:
        # UTC June 28 03:00 = June 27 23:00 in New York (EDT, UTC-4)
        utc_now = datetime(2026, 6, 28, 3, 0, 0, tzinfo=timezone.utc)
        local = practice_log_local_date({}, now_utc=utc_now)
        self.assertEqual(local.isoformat(), "2026-06-27")

    def test_prefill_uses_local_date_not_utc(self) -> None:
        utc_now = datetime(2026, 6, 28, 3, 0, 0, tzinfo=timezone.utc)
        with patch("practice_log_state.practice_log_local_date", return_value=utc_now.date().replace(day=27)):
            prefill = build_practice_log_prefill({})
        self.assertEqual(prefill["date"], "2026-06-27")


class TestPracticeLogBpmSource(unittest.TestCase):
    def test_backing_track_bpm_on_backing_page(self) -> None:
        ss = {"studio_page": "backing", "backing_track_bpm": 82}
        bpm, source = resolve_practice_log_bpm(ss)
        self.assertEqual(bpm, 82)
        self.assertEqual(source, "backing track")

    def test_song_bpm_when_no_live_bpm(self) -> None:
        ss = {"studio_page": "log", "active_song_bpm": 95, "selected_song": {"title": "Say", "bpm": 95}}
        bpm, source = resolve_practice_log_bpm(ss)
        self.assertEqual(bpm, 95)
        self.assertEqual(source, "song setting")

    def test_metronome_bpm_on_practice_page(self) -> None:
        ss = {"studio_page": "practice", "backing_track_bpm": 82, "active_song_bpm": 90}
        bpm, source = resolve_practice_log_bpm(ss)
        self.assertEqual(bpm, 82)
        self.assertEqual(source, "metronome")

    def test_bpm_display_includes_source(self) -> None:
        entry = migrate_practice_log_entry({"bpm": 82, "bpm_source": "backing_track"})
        self.assertEqual(format_bpm_display(entry), "82 · backing track")

    def test_no_bpm_without_source_when_unset(self) -> None:
        ss = {"studio_page": "log"}
        bpm, source = resolve_practice_log_bpm(ss)
        self.assertIsNone(bpm)
        self.assertIsNone(source)


class TestPracticeLogSectionLabels(unittest.TestCase):
    def test_custom_from_creative_page(self) -> None:
        entry = migrate_practice_log_entry(
            {
                "section_practiced": "custom",
                "practice_type": "custom progression",
                "source_page": "creative",
            }
        )
        self.assertEqual(section_display_label(entry), "Custom progression")

    def test_unspecified_shows_full_song(self) -> None:
        entry = migrate_practice_log_entry({"section_practiced": "unspecified"})
        self.assertEqual(section_display_label(entry), "Full song")

    def test_named_section_uses_section_name(self) -> None:
        entry = migrate_practice_log_entry(
            {
                "section_practiced": "custom",
                "section_name": "Chorus",
            }
        )
        self.assertEqual(section_display_label(entry), "Chorus")

    def test_custom_without_name_shows_custom_section(self) -> None:
        entry = migrate_practice_log_entry({"section_practiced": "custom", "practice_type": "song practice"})
        self.assertEqual(section_display_label(entry), "Custom section")


class TestPracticeLogQuickSavePayload(unittest.TestCase):
    def test_prefill_instrument_from_canonical_setup(self) -> None:
        ss = {
            "instrument": "Saxophone",
            "level": "Intermediate",
            "focus": "Scales",
            "studio_page": "practice",
            "selected_song": {"title": "Say", "artist": "Ed Sheeran", "key": "D"},
            "practice_focus_section": "Chorus",
            "backing_track_bpm": 82,
        }
        with patch("practice_log_state.resolve_practice_log_bpm", return_value=(82, "metronome")):
            prefill = build_practice_log_prefill(ss)
        self.assertEqual(prefill["instrument"], "Saxophone")
        self.assertEqual(prefill["active_song"], "Say")
        self.assertEqual(prefill["section_name"], "Chorus")
        self.assertEqual(prefill["bpm"], 82)
        self.assertEqual(prefill["bpm_source"], "metronome")

    def test_stale_instrument_key_not_used_when_canonical_differs(self) -> None:
        ss = {
            "instrument": "Piano",
            "legacy_instrument": "Saxophone",
            "studio_page": "practice",
            "selected_song": {"title": "Say"},
        }
        prefill = build_practice_log_prefill(ss)
        self.assertEqual(prefill["instrument"], "Piano")

    def test_success_message_human_readable(self) -> None:
        entry = migrate_practice_log_entry(
            {
                "active_song": "Say",
                "instrument": "Saxophone",
                "duration_minutes": 30,
                "bpm": 82,
                "bpm_source": "backing_track",
            }
        )
        msg = format_quick_save_success_message(entry)
        self.assertIn("Practice session saved: Say", msg)
        self.assertIn("Saxophone", msg)
        self.assertIn("30 min", msg)
        self.assertIn("BPM 82 from backing track", msg)


if __name__ == "__main__":
    unittest.main()
