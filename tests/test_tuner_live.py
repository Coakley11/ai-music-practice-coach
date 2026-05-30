"""Tests for live tuner config (browser widget bootstrap)."""

from __future__ import annotations

from tuner_live import build_live_tuner_html, live_tuner_config


def test_live_tuner_config_parses_target_note():
    cfg = live_tuner_config(key_prefix="practice_tuner_test", target_note="A4")
    assert cfg["targetMidi"] == 69
    assert cfg["targetNote"] == "A4"
    assert "practice_tuner_test" in cfg["domId"]


def test_live_tuner_html_includes_start_stop():
    html_doc = build_live_tuner_html(live_tuner_config(key_prefix="x"))
    assert "Start Tuner" in html_doc
    assert "Stop Tuner" in html_doc
    assert "getUserMedia" in html_doc
    assert "autoCorrelate" in html_doc
