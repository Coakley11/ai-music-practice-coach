"""Tests for live tuner config (browser widget bootstrap)."""

from __future__ import annotations

from tuner_live import build_live_tuner_html, live_tuner_config


def test_live_tuner_config_parses_target_note():
    cfg = live_tuner_config(
        key_prefix="practice_tuner_test",
        target_note="A4",
        string_targets=["E2", "A2", "D3", "G3", "B3", "E4"],
    )
    assert cfg["targetMidi"] == 69
    assert cfg["targetNote"] == "A4"
    assert "practice_tuner_test" in cfg["domId"]
    assert cfg["stringTargetMidis"]["A2"] == 45


def test_live_tuner_html_includes_start_stop():
    html_doc = build_live_tuner_html(
        live_tuner_config(key_prefix="x", string_targets=["E2", "A2"])
    )
    assert "Start Tuner" in html_doc
    assert "Stop Tuner" in html_doc
    assert "getUserMedia" in html_doc
    assert "autoCorrelate" in html_doc
    assert "lt-str-btn" in html_doc
    assert "String targets" in html_doc


def test_live_tuner_config_transposing_display_fields():
    cfg = live_tuner_config(
        key_prefix="practice_tuner_test",
        display_mode="transposing_written",
        concert_to_written_semitones=2,
        instrument_label="Tenor Saxophone",
    )
    assert cfg["displayMode"] == "transposing_written"
    assert cfg["concertToWrittenSemitones"] == 2
    assert cfg["instrumentLabel"] == "Tenor Saxophone"
