"""R9 — an explicit Practice Key must survive Creative navigation and refresh.

Girl from Ipanema is a catalog song in F. With alto saxophone and written charts
on, an explicit concert Practice Key of E reads as C#. Walking Missions -> Live
Coach -> Harmony Map -> Phrase/Motif -> Missions, refreshing on each page, must
keep E/C# and the selected harmonic position: the song's Original Key stays
metadata and never reclaims Practice-Key authority.

Kept as live coverage for the reported-but-unreproduced reset to F/D.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

CREATIVE_TABS = ("Missions", "Live Coach", "Harmony Map", "Phrase / Motif", "Missions")


@pytest.fixture(scope="module")
def ipanema_alto_app():
    """Boot the studio on Ipanema with alto sax, written charts on, concert E."""
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="r9_nav_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=240)
        at.run(timeout=300)

        def button(key):
            for widget in at.button:
                if str(widget.key) == key:
                    return widget
            return None

        button("studio_quick_nav_btn_picker").click()
        at.run(timeout=240)
        dropdown = at.selectbox(key="matching_song_dropdown")
        song = [opt for opt in dropdown.options if "Ipanema" in opt][0]
        at.selectbox(key="matching_song_dropdown").set_value(song)
        at.run(timeout=240)

        at.selectbox(key="instrument").set_value("Saxophone")
        at.run(timeout=240)
        at.checkbox(key="show_chart_in_instrument_key").set_value(True)
        at.run(timeout=240)

        practice_key = [s for s in at.sidebar.selectbox if "Practice" in str(s.label)][0]
        practice_key.set_value("E")
        at.run(timeout=240)
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _chart_key(at):
    from effective_practice_context import musician_facing_chart_key

    return musician_facing_chart_key(dict(at.session_state.filtered_state))


def _open_tab(at, needle):
    if at.session_state["studio_page"] != "creative":
        for widget in at.button:
            if str(widget.key) == "studio_quick_nav_btn_creative":
                widget.click()
                break
        at.run(timeout=240)
    try:
        at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
        at.run(timeout=240)
    except Exception:
        pass
    options = at.radio(key="improv_intelligence_tab").options
    at.radio(key="improv_intelligence_tab").set_value(
        [opt for opt in options if needle in opt][0]
    )
    at.run(timeout=240)


def test_explicit_practice_key_survives_creative_navigation(ipanema_alto_app):
    at = ipanema_alto_app
    assert at.session_state["concert_key"] == "E", "explicit Practice Key established"
    assert _chart_key(at) == "C#", "alto written key for concert E"

    _open_tab(at, "Missions")
    position = (
        at.session_state["ii_selected_section"],
        at.session_state["ii_selected_chord_index"],
    )

    for tab in CREATIVE_TABS:
        _open_tab(at, tab)
        assert at.session_state["concert_key"] == "E", f"{tab}: concert key reset"
        assert _chart_key(at) == "C#", f"{tab}: written key reset"
        # The song's Original Key (F -> written D) must never reclaim authority.
        assert at.session_state["concert_key"] != "F", f"{tab}: Original Key reclaimed"

        at.run(timeout=240)  # refresh on this page
        assert at.session_state["concert_key"] == "E", f"{tab}: lost E on refresh"
        assert _chart_key(at) == "C#", f"{tab}: lost C# on refresh"
        assert (
            at.session_state["ii_selected_section"],
            at.session_state["ii_selected_chord_index"],
        ) == position, f"{tab}: harmonic position moved"
