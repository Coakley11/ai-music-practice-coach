"""The developer line reports what each instrument actually plays on this server."""

from __future__ import annotations

import pathlib

import pytest

import backing_sound_status as S

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWITCHES = ("MUSIC_DRUM_KIT_V2", "MUSIC_UPRIGHT_BASS", "MUSIC_PIANO_V2", "MUSIC_ROCK_GUITAR", "MUSIC_BACKING_LOUDNESS")


@pytest.fixture()
def clean(monkeypatch):
    for k in SWITCHES:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_all_off_reads_todays_band(clean) -> None:
    rows = dict(S.sound_engine_status())
    assert rows["Drums"] == "synthesized" and rows["Upright bass"] == "synthesized"
    assert rows["Piano"] == "synthesized" and rows["Rock guitar"] == "off"
    assert rows["Master"] == "peak-normalised"
    assert S.switch_values() == {k: "" for k in SWITCHES}


def test_each_switch_shows_on_its_own_row(clean) -> None:
    clean.setenv("MUSIC_DRUM_KIT_V2", "1")
    rows = dict(S.sound_engine_status())
    assert rows["Drums"].startswith("recorded kit (") and rows["Upright bass"] == "synthesized"
    clean.setenv("MUSIC_UPRIGHT_BASS", "recorded")
    clean.setenv("MUSIC_PIANO_V2", "recorded")
    clean.setenv("MUSIC_ROCK_GUITAR", "recorded")
    rows = dict(S.sound_engine_status())
    assert rows["Upright bass"] == "recorded (Jazz swing)"
    assert rows["Piano"] == "Steinway pianist"
    assert rows["Rock guitar"] == "recorded (Rock groove)"
    assert "Drums: recorded kit" in S.sound_engine_line()


def test_only_developers_see_it_inside_advanced_settings() -> None:
    app = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = app.index("from backing_sound_status import sound_engine_line")
    block = app[i - 400:i]
    assert "if _developer_mode_enabled():" in block
    exp = app.rindex('with st.expander("Advanced playback settings"', 0, i)
    assert i - exp < 12000  # inside the Advanced playback settings block, beside the Key Cycling controls
