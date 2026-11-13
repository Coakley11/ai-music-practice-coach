"""M3: two-bar count-in on a fresh Backing start (never on Resume), meter-aware, accented downbeat.

The timing in the browser is proven in the real app; these pin the grid and the wiring.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backing_count_in import (  # noqa: E402
    COUNT_IN_BARS,
    COUNT_IN_SETTING_KEY,
    backing_count_in_for_card,
    count_in_spec,
)

COMPONENT = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "meter,bpm,pulses,pulse_sec,compound",
    [("4/4", 120, 4, 0.5, False), ("3/4", 90, 3, 60 / 90, False), ("6/8", 60, 6, 1 / 3, True), ("12/8", 50, 12, 0.4, True)],
)
def test_exactly_two_bars_of_the_take_grid(meter, bpm, pulses, pulse_sec, compound):
    from songs.meter import meter_timing

    s = count_in_spec(bpm=bpm, time_signature=meter)
    t = meter_timing(bpm, meter)
    assert s["bars"] == COUNT_IN_BARS == 2
    assert s["pulses"] == pulses == t.pulses_per_bar
    assert s["pulse_sec"] == pytest.approx(pulse_sec) == pytest.approx(t.pulse_sec)
    assert s["bars"] * s["pulses"] * s["pulse_sec"] == pytest.approx(2 * t.bar_sec)
    assert s["compound"] is compound


def test_off_karaoke_and_key_cycling_get_no_count_in():
    on = {"backing_track_bpm": 100, "backing_time_signature": "4/4"}
    assert backing_count_in_for_card(on, karaoke=False, cycle_active=False)["bpm"] == 100
    assert backing_count_in_for_card({**on, COUNT_IN_SETTING_KEY: False}, karaoke=False, cycle_active=False) is None
    assert backing_count_in_for_card(on, karaoke=True, cycle_active=False) is None
    assert backing_count_in_for_card(on, karaoke=False, cycle_active=True) is None
    assert count_in_spec(bpm=0, time_signature="4/4") is None


def test_play_arms_it_and_resume_does_not():
    play = COMPONENT[COMPONENT.index("} else if (args.enabled) {"):][:300]
    assert "armCountIn();" in play
    resume = COMPONENT[COMPONENT.index("function doResume(handled)"):][:500]
    # Only a Resume that restarts a changed selection from the top counts in.
    assert "if (restart) armCountIn();" in resume
    assert resume.count("armCountIn") == 1


def test_accented_first_beat_and_meter_grouping():
    assert "down ? 1568 : group ? 1175 : 880" in COMPONENT
    assert "i % s.pulses === 0" in COMPONENT and "!!s.compound && i % 3 === 0" in COMPONENT


def test_waits_for_the_audio_and_stop_cancels_it():
    assert "a.readyState >= 3" in COMPONENT          # clicks only once the take can play
    stop = COMPONENT[COMPONENT.index('if (btn.dataset.state !== "stopped") {'):][:400]
    assert "ci.cancel()" in stop
    # No nudges or missed-autoplay restarts under the count-in.
    assert "if (!ciRun && !playing && now > stoppingUntil" in COMPONENT


def test_lead_sheet_player_is_hooked_before_it_can_autoplay():
    i = APP.index("window.parent.__backingCountIn.watchDoc(document)")
    assert i < APP.index('const audio = document.getElementById("live-audio");', i - 400)


def test_setting_in_advanced_playback_settings():
    assert '"Count-in (2 bars)"' in APP and "key=_CI_WIDGET" in APP


def test_the_choice_survives_widget_cleanup():
    """The choice is a plain key the toggle writes on change, never the widget key itself (the widget's value was
    reset to Off once Play opened the Lead Sheet, and Stop -> Play stopped counting in)."""
    from backing_count_in import COUNT_IN_WIDGET_KEY, set_count_in_enabled

    assert COUNT_IN_WIDGET_KEY != COUNT_IN_SETTING_KEY
    s = {COUNT_IN_WIDGET_KEY: False}          # a reset widget value must not switch it off
    assert backing_count_in_for_card({**s, "backing_track_bpm": 100}, karaoke=False, cycle_active=False) is not None
    set_count_in_enabled(s, False)
    assert backing_count_in_for_card({**s, "backing_track_bpm": 100}, karaoke=False, cycle_active=False) is None
    assert "on_change=lambda: _ci_set(" in APP
