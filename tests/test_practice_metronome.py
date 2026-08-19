"""Practice metronome widget — BPM timing and shared component."""

from __future__ import annotations

import unittest

from practice_metronome import build_metronome_widget_html, render_metronome_widget
from songs.meter import meter_timing
from tuner_tone_ui import render_tuner_tone_section


class TestPracticeMetronomeWidget(unittest.TestCase):
    def test_html_includes_recompute_pulse_timing(self) -> None:
        html = build_metronome_widget_html(default_bpm=100, default_signature="4/4")
        self.assertIn("function recomputePulseTiming()", html)
        self.assertIn("recomputePulseTiming();", html)

    def test_bpm_change_updates_pulse_interval_before_restart(self) -> None:
        html = build_metronome_widget_html(default_bpm=100, default_signature="4/4")
        self.assertIn('bpmInput.addEventListener("input"', html)
        snippet = html.split('bpmInput.addEventListener("input"')[1][:220]
        self.assertIn("recomputePulseTiming()", snippet)
        self.assertIn("if (timer) start();", snippet)

    def test_start_recomputes_timing_and_clears_old_timer(self) -> None:
        html = build_metronome_widget_html(default_bpm=120, default_signature="4/4")
        start_block = html.split("function start()")[1].split("function stop()")[0]
        self.assertIn("stop();", start_block)
        self.assertIn("recomputePulseTiming();", start_block)
        self.assertIn("setInterval(tick, tickIntervalMs());", start_block)

    def test_tick_interval_uses_live_pulse_ms(self) -> None:
        html = build_metronome_widget_html(default_bpm=90, default_signature="3/4")
        self.assertIn("cfg.pulseIntervalMs", html)
        self.assertNotIn("if (cfg.pulseIntervalMs) return cfg.pulseIntervalMs;", html)

    def test_python_pulse_interval_tracks_bpm_change(self) -> None:
        slow = meter_timing(60, "4/4").pulse_sec
        fast = meter_timing(120, "4/4").pulse_sec
        self.assertAlmostEqual(fast, slow / 2.0, places=5)

    def test_compact_mode_uses_shorter_title(self) -> None:
        html = build_metronome_widget_html(default_bpm=100, compact=True)
        self.assertIn(">⏱️ Metronome<", html)
        self.assertNotIn("Practice Metronome", html)

    def test_render_metronome_widget_accepts_streamlit_module(self) -> None:
        source = open(render_metronome_widget.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("def render_metronome_widget(", source)
        self.assertIn("st_module: Any", source)


class TestTunerToneMetronomeIntegration(unittest.TestCase):
    def test_tuner_section_embeds_metronome_when_bpm_provided(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("practice_metronome", source)
        self.assertIn("metronome_bpm", source)
        self.assertIn("Tuner, Tone & Metronome", source)
        self.assertIn("render_metronome_widget", source)

    def test_tune_live_still_has_no_target_text_input(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertNotIn("Target note (optional)", source)
        self.assertNotIn("text_input", source)

    def test_tone_sustain_still_uses_chromatic_selectbox(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertIn("CHROMATIC_NOTE_OPTIONS", source)
        self.assertIn("render_tone_take_history_section", source)
        self.assertIn("render_pending_tone_save", source)

    def test_tone_history_still_rendered_in_both_modes(self) -> None:
        source = open(render_tuner_tone_section.__code__.co_filename, encoding="utf-8").read()
        self.assertGreaterEqual(source.count("render_tone_take_history_section("), 2)


if __name__ == "__main__":
    unittest.main()
