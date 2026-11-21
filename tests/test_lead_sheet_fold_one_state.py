"""One Lead Sheet state: Backing "Lead sheet: Off" means the chart fold is collapsed, On means expanded.

Measured on 13de912d (ordinary Voice and Karaoke Set, 1280 / 390 / 360): Off chosen before Play left
``#live-chart-wrap`` OPEN under a "· Expand Lead Sheet" header. The fold was decided once, when the
switch value changed, from a DOM test for lyric lines (``chartIsPrimary()``) that is always "no
lyrics" before Play - the panel only says "Press play to follow the lyrics." - and the decision was
then latched. These pin the fix: the fold is driven from the switch (the page marker) on every tick,
"chart only" is a server-side fact about the song's lyrics, and the header is written from the fold.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

import streamlit_music_practice_app as app

PANEL = {"Verse 1": {"lyrics": ["first line", "second line"], "chords": ["C", "G", "Am", "F"]}}
INSTRUMENTAL_ONLY = {"Intro": {"lyrics": [], "chords": ["C", "G"]}}


def _surface(panel):
    return app.live_follow_along_component_html(
        b"", [], "<div class='lead-grid'></div>", audio_url="/app/static/x.wav",
        karaoke_hold_from_shared_controller=True, karaoke_lyrics_panel=panel, karaoke_hide_chart=True,
    )


def _function(html_: str, name: str) -> str:
    start = html_.index(f"function {name}() {{")
    end = html_.index("\n    }\n", start)
    return html_[start:end]


def test_the_rendered_fold_starts_collapsed_with_the_expand_header() -> None:
    html_ = _surface(PANEL)
    tag = re.search(r"<details[^>]*id=\"live-chart-wrap\"[^>]*>", html_).group(0)
    assert " open" not in tag  # never baked open: Off before Play stays collapsed from the first paint
    summary = html_[html_.index(tag):html_.index("</summary>", html_.index(tag))]
    assert "· Expand Lead Sheet" in summary and "Collapse" not in summary


def test_the_fold_html_is_the_same_whatever_the_switch_says() -> None:
    # The switch is read from the page marker, so On / Off never remounts the iframe (audio keeps going).
    assert _surface(PANEL) == _surface(PANEL)
    assert "backing_lead_sheet_open" not in _function(_surface(PANEL), "syncChartFold")


def test_with_lyrics_the_fold_follows_only_the_switch() -> None:
    html_ = _surface(PANEL)
    assert "const CHART_ALWAYS_SHOWN = false;" in html_
    body = _function(html_, "syncChartFold")
    assert "const want = CHART_ALWAYS_SHOWN || leadSheetOpenOnPage();" in body
    # The DOM lyric test that is "no lyrics" before Play (and in instrumental sections) cannot open it.
    assert "chartIsPrimary" not in body


def test_off_is_reapplied_every_tick_so_nothing_can_reopen_it() -> None:
    body = _function(_surface(PANEL), "syncChartFold")
    # While the card switch exists the wanted state is applied on every tick (not only on change),
    # so a stale first decision or any client-side restore of ``open`` is undone within one tick.
    assert "if (want !== lastFoldWanted || cardLeadSheetSwitch()) {" in body
    assert "if (wrap.open !== want) wrap.open = want;" in body
    assert "lastLeadSheetOpen" not in _surface(PANEL)
    assert "window.setInterval(syncChartFold, 300);" in _surface(PANEL)


def test_the_header_words_come_from_the_fold_itself() -> None:
    html_ = _surface(PANEL)
    body = _function(html_, "syncChartFold")
    assert body.rstrip().endswith("syncFoldHeader(wrap.open);")  # after the fold is set: open = Collapse
    header = _function(html_.replace("function syncFoldHeader(ls) {", "function syncFoldHeader() {"), "syncFoldHeader")
    assert 'ls ? "\u00b7 Collapse Lead Sheet" : "\u00b7 Expand Lead Sheet"' in header


def test_the_header_still_presses_the_one_card_switch() -> None:
    html_ = _surface(PANEL)
    assert '.st-key-backing_art_lead_sheet_btn button' in _function(html_, "cardLeadSheetSwitch")
    install = _function(html_, "installFoldHeader")
    assert "const btn = cardLeadSheetSwitch();" in install and "btn.click();" in install


def test_a_song_without_lyrics_keeps_its_chart_as_the_display() -> None:
    assert "const CHART_ALWAYS_SHOWN = true;" in _surface(INSTRUMENTAL_ONLY)
    assert "const CHART_ALWAYS_SHOWN = true;" in _surface(None)


@pytest.mark.parametrize(
    "panel, expected",
    [
        (None, False),
        ({}, False),
        (INSTRUMENTAL_ONLY, False),
        (PANEL, True),
        ({"Intro": {"lyrics": []}, "Verse": {"lyrics": ["la"]}}, True),
        ({"Solo": {"lyrics": [], "lyrics_by_key": {"G": ["Instrumental - G D"]}}}, True),
        ({"Solo": {"lyrics": [], "lyrics_by_key": {"G": []}}}, False),
        ({"Bad": "not a dict"}, False),
    ],
)
def test_panel_lyrics_fact(panel, expected) -> None:
    assert app._karaoke_panel_has_lyric_lines(panel) is expected


def test_off_before_play_publishes_a_closed_marker(monkeypatch) -> None:
    # Session-state side of the same state: Off before a take clears the open flag the marker is drawn from.
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state={}))
    s = app.st.session_state
    s[app.BACKING_LEAD_SHEET_ON_PLAY_KEY] = True
    s["backing_lead_sheet_open"] = True
    app._toggle_backing_lead_sheet_from_card(False, lambda _open: None)
    assert app.backing_lead_sheet_preference(s) is False
    assert s["backing_lead_sheet_open"] is False
    src = open(app.__file__, encoding="utf-8").read()
    assert 'data-ls-open="{"1" if _leadsheet_open else "0"}"' in src
