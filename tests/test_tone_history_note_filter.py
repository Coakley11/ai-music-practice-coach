"""Tone History note filter — dropdown options and transposing semantics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from media_state import migrate_tone_take
from media_tone_catalog import (
    CHROMATIC_NOTE_OPTIONS,
    NOTE_FILTER_MODE_CONCERT,
    NOTE_FILTER_MODE_PLAYER,
    TONE_HISTORY_NOTE_FILTER_ALL,
    TONE_HISTORY_NOTE_FILTER_OPTIONS,
    list_tone_takes,
    note_filter_matches_row,
    tone_history_note_filter_label,
    tone_take_row_summary,
)
from tone_take_history_ui import render_tone_take_history_section


def _tenor_f_sharp_row(**overrides) -> dict:
    base = {
        "tone_take_id": "tenor-fs",
        "instrument": "Tenor Saxophone",
        "written_note": "F#4",
        "concert_note": "E4",
        "selected_pitch_class": "F#/Gb",
        "target_note": "F#4",
        "transposing_type": "Tenor saxophone (Bb)",
        "duration_seconds": 5,
        "mean_cents": 6,
        "pitch_stability_score": 80,
        "created_at": "2026-06-28T21:42:00+00:00",
    }
    base.update(overrides)
    return migrate_tone_take(base)


def _flute_f_sharp_row(**overrides) -> dict:
    base = {
        "tone_take_id": "flute-fs",
        "instrument": "Flute",
        "concert_note": "F#4",
        "selected_pitch_class": "F#/Gb",
        "target_note": "F#4",
        "duration_seconds": 5,
        "mean_cents": 4,
        "pitch_stability_score": 82,
        "created_at": "2026-06-28T21:42:00+00:00",
    }
    base.update(overrides)
    return migrate_tone_take(base)


def _alto_f_sharp_row(**overrides) -> dict:
    base = {
        "tone_take_id": "alto-fs",
        "instrument": "Alto Saxophone",
        "written_note": "F#4",
        "concert_note": "A4",
        "selected_pitch_class": "F#/Gb",
        "target_note": "F#4",
        "transposing_type": "Alto saxophone (Eb)",
        "duration_seconds": 5,
        "mean_cents": 7,
        "pitch_stability_score": 80,
        "created_at": "2026-06-28T21:42:00+00:00",
    }
    base.update(overrides)
    return migrate_tone_take(base)


class TestToneHistoryNoteFilterOptions(unittest.TestCase):
    def test_dropdown_options_include_all_notes_and_chromatic_set(self) -> None:
        self.assertEqual(TONE_HISTORY_NOTE_FILTER_OPTIONS[0], TONE_HISTORY_NOTE_FILTER_ALL)
        self.assertEqual(TONE_HISTORY_NOTE_FILTER_OPTIONS[1:], CHROMATIC_NOTE_OPTIONS)
        self.assertEqual(len(TONE_HISTORY_NOTE_FILTER_OPTIONS), 13)

    def test_history_ui_uses_selectbox_not_free_text_note_filter(self) -> None:
        source = open(render_tone_take_history_section.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("TONE_HISTORY_NOTE_FILTER_OPTIONS", source)
        self.assertIn("selectbox", source)
        self.assertNotIn('text_input(\n            "Filter by note"', source)
        self.assertNotIn('text_input("Filter by note"', source)


class TestToneHistoryCurrentInstrumentFilter(unittest.TestCase):
    def test_tenor_sax_label_is_written_note(self) -> None:
        label = tone_history_note_filter_label(
            all_instruments_view=False,
            instrument_is_transposing=True,
        )
        self.assertEqual(label, "Filter by written note")

    def test_flute_label_is_concert_note(self) -> None:
        label = tone_history_note_filter_label(
            all_instruments_view=False,
            instrument_is_transposing=False,
        )
        self.assertEqual(label, "Filter by concert note")

    def test_tenor_current_instrument_filters_by_written_note(self) -> None:
        row = _tenor_f_sharp_row()
        catalog = {"tone_takes": [row]}
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            by_written = list_tone_takes(
                st=None,
                instrument="Tenor Saxophone",
                note_filter="F#/Gb",
                current_instrument_is_transposing=True,
            )
            by_concert = list_tone_takes(
                st=None,
                instrument="Tenor Saxophone",
                note_filter="E",
                current_instrument_is_transposing=True,
            )
        self.assertEqual(len(by_written), 1)
        self.assertEqual(len(by_concert), 0)

    def test_tenor_written_row_summary_disambiguates_concert(self) -> None:
        summary = tone_take_row_summary(_tenor_f_sharp_row())
        self.assertIn("Tenor Saxophone", summary)
        self.assertIn("written F#/Gb / concert E", summary)

    def test_flute_row_summary_uses_target_label(self) -> None:
        summary = tone_take_row_summary(_flute_f_sharp_row())
        self.assertIn("Flute", summary)
        self.assertIn("target F#/Gb", summary)
        self.assertNotIn("written", summary)


class TestToneHistoryAllInstrumentsFilter(unittest.TestCase):
    def test_player_facing_matches_transposing_written_and_non_transposing_target(self) -> None:
        rows = [
            _flute_f_sharp_row(),
            _tenor_f_sharp_row(),
            _alto_f_sharp_row(),
        ]
        catalog = {"tone_takes": rows}
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            filtered = list_tone_takes(
                st=None,
                instrument=None,
                note_filter="F#/Gb",
                note_filter_mode=NOTE_FILTER_MODE_PLAYER,
                all_instruments_view=True,
            )
        self.assertEqual(len(filtered), 3)
        ids = {str(r.get("tone_take_id") or "") for r in filtered}
        self.assertEqual(ids, {"flute-fs", "tenor-fs", "alto-fs"})

    def test_concert_pitch_filters_by_concert_note_only(self) -> None:
        rows = [
            _flute_f_sharp_row(),
            _tenor_f_sharp_row(),
            _alto_f_sharp_row(),
            migrate_tone_take(
                {
                    "tone_take_id": "flute-e",
                    "instrument": "Flute",
                    "concert_note": "E4",
                    "selected_pitch_class": "E",
                    "target_note": "E4",
                }
            ),
        ]
        catalog = {"tone_takes": rows}
        with patch("media_tone_catalog.load_media_catalog", lambda *, st=None: catalog):
            fs_filtered = list_tone_takes(
                st=None,
                instrument=None,
                note_filter="F#/Gb",
                note_filter_mode=NOTE_FILTER_MODE_CONCERT,
                all_instruments_view=True,
            )
            e_filtered = list_tone_takes(
                st=None,
                instrument=None,
                note_filter="E",
                note_filter_mode=NOTE_FILTER_MODE_CONCERT,
                all_instruments_view=True,
            )
        self.assertEqual(len(fs_filtered), 1)
        self.assertEqual(fs_filtered[0].get("tone_take_id"), "flute-fs")
        self.assertEqual(len(e_filtered), 2)
        e_ids = {str(r.get("tone_take_id") or "") for r in e_filtered}
        self.assertEqual(e_ids, {"flute-e", "tenor-fs"})

    def test_note_filter_matches_row_player_vs_concert_modes(self) -> None:
        tenor = _tenor_f_sharp_row()
        self.assertTrue(
            note_filter_matches_row(
                tenor,
                "F#/Gb",
                filter_mode=NOTE_FILTER_MODE_PLAYER,
                all_instruments_view=True,
            )
        )
        self.assertFalse(
            note_filter_matches_row(
                tenor,
                "F#/Gb",
                filter_mode=NOTE_FILTER_MODE_CONCERT,
                all_instruments_view=True,
            )
        )
        self.assertTrue(
            note_filter_matches_row(
                tenor,
                "E",
                filter_mode=NOTE_FILTER_MODE_CONCERT,
                all_instruments_view=True,
            )
        )

    def test_alto_row_summary_disambiguates_written_and_concert(self) -> None:
        summary = tone_take_row_summary(_alto_f_sharp_row())
        self.assertIn("Alto Saxophone", summary)
        self.assertIn("written F#/Gb / concert A", summary)


if __name__ == "__main__":
    unittest.main()
