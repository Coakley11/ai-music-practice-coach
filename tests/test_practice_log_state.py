"""Canonical practice log state API tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from practice_log_state import (
    add_practice_log_entry,
    compute_practice_log_summary,
    delete_practice_log_entry,
    deterministic_session_id,
    entry_key_display_parts,
    filter_practice_log_entries,
    gather_practice_log_keys,
    migrate_practice_log_entry,
    normalize_practice_log_entries,
    practice_log_form_key_spec,
    PRACTICE_CONCERT_KEY_LABEL,
    WRITTEN_KEY_LABEL,
    SHAPE_KEY_LABEL,
    update_practice_log_entry,
)


class TestPracticeLogMigration(unittest.TestCase):
    def test_legacy_migration_creates_session_id_and_fields(self) -> None:
        legacy = {
            "date": "2026-06-01",
            "song": "Autumn Leaves",
            "minutes": 25,
            "practice": "Worked chorus transitions",
            "rating": 8,
            "mode": "Song Work",
        }
        out = migrate_practice_log_entry(legacy)
        self.assertTrue(out.get("session_id"))
        self.assertEqual(out.get("duration_minutes"), 25)
        self.assertEqual(out.get("notes"), "Worked chorus transitions")
        self.assertEqual(out.get("active_song"), "Autumn Leaves")
        self.assertIn("created_at", out)
        self.assertIn("updated_at", out)
        self.assertEqual(out.get("practice_type"), "song practice")

    def test_deterministic_session_id_stable(self) -> None:
        entry = {"date": "2026-06-01", "song": "A", "minutes": 10, "practice": "x", "rating": 5, "mode": "Other"}
        self.assertEqual(deterministic_session_id(entry), deterministic_session_id(dict(entry)))


class TestPracticeLogCrud(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = Path(self._tmpdir.name) / "practice_history.json"
        self._patch = patch("practice_log_persistence._local_path", lambda *, st=None: self._path)
        self._patch_ws = patch("practice_log_persistence._resolve_workspace_id", lambda *, st=None: "daniel")
        self._patch_cloud = patch("practice_log_persistence._load_cloud_logs", lambda *, st=None: ([], None))
        self._patch.start()
        self._patch_ws.start()
        self._patch_cloud.start()
        self.session: dict = {}

    def tearDown(self) -> None:
        self._patch.stop()
        self._patch_ws.stop()
        self._patch_cloud.stop()
        self._tmpdir.cleanup()

    def test_add_entry_creates_canonical_fields(self) -> None:
        entry = add_practice_log_entry(
            self.session,
            {
                "active_song": "Perfect",
                "instrument": "Piano",
                "duration_minutes": 20,
                "notes": "Chorus work",
                "what_was_hard": "Timing at bar 9",
                "next_step": "Loop chorus slowly",
            },
        )
        self.assertEqual(entry.get("active_song"), "Perfect")
        self.assertEqual(entry.get("what_was_hard"), "Timing at bar 9")
        self.assertIn("session_id", entry)

    def test_update_bumps_updated_at(self) -> None:
        from unittest.mock import patch

        entry = add_practice_log_entry(self.session, {"active_song": "Song A", "duration_minutes": 15})
        before = entry.get("updated_at")
        with patch("practice_log_state._utc_now_iso", return_value="2099-01-02T00:00:00+00:00"):
            updated = update_practice_log_entry(
                self.session,
                str(entry["session_id"]),
                {"notes": "Updated notes"},
            )
        self.assertEqual(updated.get("notes"), "Updated notes")
        self.assertNotEqual(updated.get("updated_at"), before)

    def test_delete_hides_entry(self) -> None:
        entry = add_practice_log_entry(self.session, {"active_song": "Delete Me", "duration_minutes": 10})
        sid = str(entry["session_id"])
        self.assertTrue(delete_practice_log_entry(self.session, sid))
        visible = normalize_practice_log_entries(
            [e for e in (self.session.get("practice_log_entries") or [])]
        )
        self.assertFalse(any(e.get("session_id") == sid for e in visible))


class TestPracticeLogFilterSummary(unittest.TestCase):
    def _sample_entries(self) -> list[dict]:
        today = date.today().isoformat()
        old = (date.today() - timedelta(days=40)).isoformat()
        return normalize_practice_log_entries(
            [
                migrate_practice_log_entry(
                    {
                        "session_id": "s1",
                        "date": today,
                        "active_song": "Autumn Leaves",
                        "instrument": "Tenor Sax",
                        "duration_minutes": 30,
                        "focus_area": "timing/rhythm",
                        "practice_type": "song practice",
                        "what_was_hard": "rush the bridge",
                    }
                ),
                migrate_practice_log_entry(
                    {
                        "session_id": "s2",
                        "date": old,
                        "active_song": "Blue Bossa",
                        "instrument": "Piano",
                        "duration_minutes": 20,
                        "focus_area": "chords",
                        "practice_type": "song practice",
                    }
                ),
            ]
        )

    def test_filter_by_instrument_and_focus(self) -> None:
        entries = self._sample_entries()
        filtered = filter_practice_log_entries(
            entries,
            {"instrument": "Tenor Sax", "focus_area": "timing/rhythm", "window_days": 14},
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].get("active_song"), "Autumn Leaves")

    def test_summary_computes_top_song_and_focus(self) -> None:
        entries = self._sample_entries()
        summary = compute_practice_log_summary(entries, window_days=14)
        self.assertGreaterEqual(summary.get("session_count", 0), 1)
        self.assertIn("Autumn Leaves", summary.get("most_practiced_songs") or [])
        self.assertIn("timing/rhythm", summary.get("most_common_focus_areas") or [])


class TestPracticeLogSearchFilter(unittest.TestCase):
    def _entries(self) -> list[dict]:
        today = date.today().isoformat()
        return normalize_practice_log_entries(
            [
                migrate_practice_log_entry(
                    {
                        "session_id": "say-piano",
                        "date": today,
                        "active_song": "Say",
                        "instrument": "Piano",
                        "duration_minutes": 30,
                        "focus_area": "chords",
                        "practice_type": "song practice",
                        "display_key": "D",
                        "original_key": "D",
                    }
                ),
                migrate_practice_log_entry(
                    {
                        "session_id": "sax-tone",
                        "date": today,
                        "active_song": "Autumn Leaves",
                        "instrument": "Alto Saxophone",
                        "duration_minutes": 25,
                        "focus_area": "tone",
                        "practice_type": "song practice",
                        "display_key": "G",
                        "notes": "Worked long tones",
                    }
                ),
                migrate_practice_log_entry(
                    {
                        "session_id": "legacy-row",
                        "date": today,
                        "song": "Blue Bossa",
                        "minutes": 20,
                        "mode": "Song Work",
                        "practice": "Transcription warmup",
                        "instrument": "Tenor Sax",
                        "rating": 8,
                    }
                ),
            ]
        )

    def test_search_piano_matches_instrument(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "piano"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Piano")

    def test_search_tone_matches_focus_area(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "tone"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("focus_area"), "tone")

    def test_search_tone_matches_notes_text(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "long tone"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("session_id"), "sax-tone")

    def test_search_say_matches_song(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "say"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("active_song"), "Say")

    def test_search_sax_matches_saxophone_entries(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "sax"})
        self.assertEqual(len(rows), 2)
        instruments = {r.get("instrument") for r in rows}
        self.assertIn("Alto Saxophone", instruments)
        self.assertIn("Tenor Sax", instruments)

    def test_instrument_dropdown_piano(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"instrument": "Piano"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Piano")

    def test_focus_dropdown_tone(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"focus_area": "tone"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("focus_area"), "tone")

    def test_search_and_dropdown_combined(self) -> None:
        rows = filter_practice_log_entries(
            self._entries(),
            {"search": "say", "instrument": "Piano"},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("active_song"), "Say")

    def test_search_and_dropdown_no_match(self) -> None:
        rows = filter_practice_log_entries(
            self._entries(),
            {"search": "say", "instrument": "Alto Saxophone"},
        )
        self.assertEqual(len(rows), 0)

    def test_legacy_fields_searchable(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"search": "transcription"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("active_song"), "Blue Bossa")

    def test_legacy_mode_filter(self) -> None:
        rows = filter_practice_log_entries(self._entries(), {"practice_type": "song practice"})
        self.assertGreaterEqual(len(rows), 2)


class TestPracticeLogInstrumentSpecificity(unittest.TestCase):
    def _sax_entries(self) -> list[dict]:
        today = date.today().isoformat()
        return normalize_practice_log_entries(
            [
                migrate_practice_log_entry(
                    {
                        "session_id": "tenor",
                        "date": today,
                        "active_song": "Autumn Leaves",
                        "instrument": "Tenor Saxophone",
                        "focus_area": "tone",
                        "notes": "long tones",
                    }
                ),
                migrate_practice_log_entry(
                    {
                        "session_id": "alto",
                        "date": today,
                        "active_song": "Blue Bossa",
                        "instrument": "Alto Saxophone",
                        "focus_area": "chords",
                    }
                ),
            ]
        )

    def test_filter_tenor_vs_alto(self) -> None:
        entries = self._sax_entries()
        tenor = filter_practice_log_entries(entries, {"instrument": "Tenor Saxophone"})
        alto = filter_practice_log_entries(entries, {"instrument": "Alto Saxophone"})
        self.assertEqual(len(tenor), 1)
        self.assertEqual(tenor[0].get("instrument"), "Tenor Saxophone")
        self.assertEqual(len(alto), 1)
        self.assertEqual(alto[0].get("instrument"), "Alto Saxophone")

    def test_search_sax_matches_both(self) -> None:
        entries = self._sax_entries()
        rows = filter_practice_log_entries(entries, {"search": "sax"})
        self.assertEqual(len(rows), 2)

    def test_search_tenor_matches_tenor_only(self) -> None:
        entries = self._sax_entries()
        rows = filter_practice_log_entries(entries, {"search": "tenor"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Tenor Saxophone")

    def test_search_alto_matches_alto_only(self) -> None:
        entries = self._sax_entries()
        rows = filter_practice_log_entries(entries, {"search": "alto"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("instrument"), "Alto Saxophone")


class TestPracticeLogKeyLabels(unittest.TestCase):
    def test_piano_shows_practice_concert_and_original_only(self) -> None:
        entry = migrate_practice_log_entry(
            {"instrument": "Piano", "display_key": "C#m", "original_key": "Bm"}
        )
        labels = [label for label, _ in entry_key_display_parts(entry)]
        self.assertIn(PRACTICE_CONCERT_KEY_LABEL, labels)
        self.assertIn("Original key", labels)
        self.assertNotIn(SHAPE_KEY_LABEL, labels)
        self.assertNotIn(WRITTEN_KEY_LABEL, labels)

    def test_alto_sax_shows_all_three_key_fields(self) -> None:
        entry = migrate_practice_log_entry(
            {
                "instrument": "Saxophone",
                "practice_concert_key": "G",
                "display_key": "G",
                "written_key": "E",
                "original_key": "G",
            }
        )
        parts = dict(entry_key_display_parts(entry))
        self.assertEqual(parts[PRACTICE_CONCERT_KEY_LABEL], "G")
        self.assertEqual(parts[WRITTEN_KEY_LABEL], "E")
        self.assertEqual(parts["Original key"], "G")
        self.assertNotIn(SHAPE_KEY_LABEL, parts)

    def test_guitar_shows_shape_not_written(self) -> None:
        entry = migrate_practice_log_entry(
            {
                "instrument": "Guitar",
                "display_key": "C#m",
                "guitar_shape_key": "Am",
                "original_key": "Bm",
            }
        )
        parts = dict(entry_key_display_parts(entry))
        self.assertEqual(parts[PRACTICE_CONCERT_KEY_LABEL], "C#m")
        self.assertEqual(parts[SHAPE_KEY_LABEL], "Am")
        self.assertNotIn(WRITTEN_KEY_LABEL, parts)

    def test_non_guitar_clears_stale_shape_key_on_migrate(self) -> None:
        entry = migrate_practice_log_entry(
            {"instrument": "Piano", "guitar_shape_key": "Am", "display_key": "C"}
        )
        self.assertEqual(entry.get("guitar_shape_key"), "")
        labels = [label for label, _ in entry_key_display_parts(entry)]
        self.assertNotIn(SHAPE_KEY_LABEL, labels)

    def test_guitar_form_spec_uses_shape_not_written(self) -> None:
        spec = practice_log_form_key_spec("Guitar")
        self.assertTrue(spec["shape_key"])
        self.assertFalse(spec["written_key"])

    def test_sax_form_spec_uses_written_not_shape(self) -> None:
        spec = practice_log_form_key_spec("Saxophone")
        self.assertTrue(spec["written_key"])
        self.assertFalse(spec["shape_key"])

    def test_gather_keys_from_alto_sax_session(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            written_key_for_type,
        )

        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "G",
            "selected_song": {"key": "G", "title": "Say"},
        }
        keys = gather_practice_log_keys(session)
        self.assertEqual(keys["practice_concert_key"], "G")
        self.assertEqual(keys["original_key"], "G")
        expected_written = written_key_for_type("G", "Alto saxophone (Eb)")
        self.assertEqual(keys["written_key"], expected_written)
        self.assertEqual(keys["guitar_shape_key"], "")

    def test_gather_keys_from_guitar_capo_session(self) -> None:
        from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

        session = {
            "instrument": "Guitar",
            ACTIVE_CATALOG_PICK_KEY: "pk::1",
            SELECTED_SONG_STATE_KEY: {"pick_key": "pk::1", "key": "Bm"},
            "active_song_state": {"pick_key": "pk::1", "display_key": "C#m"},
            "display_key": "C#m",
            "guitar_capo_enabled": True,
            "guitar_capo_shape_key": "Am",
            "guitar_capo_sounding_key": "C#m",
        }
        keys = gather_practice_log_keys(session)
        self.assertEqual(keys["practice_concert_key"], "C#m")
        self.assertEqual(keys["guitar_shape_key"], "Am")
        self.assertEqual(keys["written_key"], "")

    def test_quick_save_prefill_uses_canonical_keys(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
        )
        from practice_log_state import build_practice_log_prefill

        session = {
            "instrument": "Saxophone",
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            "display_key": "E",
            "selected_song": {"key": "E", "title": "Test"},
            "studio_page": "practice",
        }
        prefill = build_practice_log_prefill(session)
        self.assertEqual(prefill["practice_concert_key"], "E")
        self.assertTrue(prefill.get("written_key"))
        self.assertNotEqual(prefill["written_key"], prefill["practice_concert_key"])


if __name__ == "__main__":
    unittest.main()
