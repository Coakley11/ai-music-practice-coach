"""Written charts never change the concert pitch of the backing.

A tenor player's Catalog Backing in concert Am played in Bm: the chart bundle is
built in the instrument's written key and normal Backing used those sections as
the audio. The Key Cycling sheet then projected that "concert" timeline into the
written key again (C#m over a Bm take).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from instrument_transposition import written_key_for_type
from music_theory import semitone_distance, transpose_sections_dict

APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

MINOR_KEYS = ["Am", "Bbm", "Bm", "Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m"]
MAJOR_KEYS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
TYPES = {
    "Tenor saxophone (Bb)": 2,
    "Soprano saxophone (Bb)": 2,
    "Alto saxophone (Eb)": -3,
    "Baritone saxophone (Eb)": -3,
    "Bb Trumpet": 2,
    "Bb Clarinet": 2,
}
BLUE_BOSSA_A = ["Cm7", "Fm7", "Dm7b5", "G7#5", "Ebm7", "Ab7", "Dbmaj7", "G7/B"]


@pytest.mark.parametrize("ttype,steps", TYPES.items())
@pytest.mark.parametrize("concert", MINOR_KEYS + MAJOR_KEYS)
def test_written_key_is_one_interval_from_concert(ttype: str, steps: int, concert: str) -> None:
    written = written_key_for_type(concert, ttype)
    assert semitone_distance(concert, written) % 12 == steps % 12
    assert concert.endswith("m") == written.endswith("m")


@pytest.mark.parametrize("ttype", TYPES)
@pytest.mark.parametrize("concert", MINOR_KEYS)
def test_written_bundle_moves_back_to_concert_exactly_once(ttype: str, concert: str) -> None:
    concert_secs = transpose_sections_dict({"A": BLUE_BOSSA_A}, "Cm", concert)
    written = written_key_for_type(concert, ttype)
    written_secs = transpose_sections_dict(concert_secs, concert, written)
    back = transpose_sections_dict(written_secs, written, concert)
    assert back == concert_secs


def test_tenor_reported_case() -> None:
    assert written_key_for_type("Am", "Tenor saxophone (Bb)") == "Bm"
    assert written_key_for_type("Bbm", "Tenor saxophone (Bb)") == "Cm"
    assert written_key_for_type("Bm", "Tenor saxophone (Bb)") == "C#m"
    assert written_key_for_type("Cm", "Tenor saxophone (Bb)") == "Dm"
    assert written_key_for_type("C#m", "Tenor saxophone (Bb)") == "D#m"


def test_catalog_backing_sections_move_from_written_to_concert() -> None:
    block = APP[APP.index("    guitar_shape_chart_key = chart_key\n"):][:1200]
    assert "_written_charts_on(st.session_state, instrument)" in block
    assert "sections_for_backing = transpose_sections_dict(sections, chart_key, concert_key)" in block


def test_audio_key_fallback_is_concert_under_written_charts() -> None:
    assert "else (concert_key if _written_charts_on(st.session_state, instrument) else chart_key)" in APP


def test_non_cycling_sheet_projects_concert_grid_and_timeline_once() -> None:
    grid = APP[APP.index('    _sheet_written_from = ""'):][:1500]
    assert "and not _wr_cycling" in grid
    assert "and not _chart_sections_projected" in grid
    assert "chart_sections, _sheet_written_from, chart_display_key" in grid
    tl = APP[APP.index("            if _sheet_written_from and isinstance(_follow_timeline, list):"):][:1200]
    assert '"chordSpace": _WR_TL_SPACE' in tl
