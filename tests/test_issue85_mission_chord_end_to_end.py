"""Issue 85: the Missions page's own path - choose a chord in one song, open Blackbird in another Practice Key.

Runs what the page runs (``_ensure_chord_selection``) and then what the Mission shows
(``resolve_mission_projection_state``). Before the fix the first step re-sealed the other song's chord as Blackbird's,
so the second step kept it.
"""
from __future__ import annotations

import pytest

try:
    from test_issue85_mission_chord_belongs_to_its_song import (
        ALTO, BLACKBIRD, CLICK, OTHER, _click, _half_diminished, _map, _session)
except ImportError:
    from tests.test_issue85_mission_chord_belongs_to_its_song import (
        ALTO, BLACKBIRD, CLICK, OTHER, _click, _half_diminished, _map, _session)
from improvisation_intelligence_ui import _ensure_chord_selection
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
from mission_projection_state import resolve_mission_projection_state


@pytest.mark.parametrize("instrument, transposing", [("Guitar", ""), ("Saxophone", ALTO)])
@pytest.mark.parametrize("page", ["creative", "backing"])
def test_another_songs_chord_never_reaches_blackbirds_mission(instrument, transposing, page):
    ss = _session("C#", click=_click("Em7b5", song=OTHER, key="G"), instrument=instrument)
    ss["studio_page"] = page
    if transposing:
        ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = transposing
        ss["show_chart_in_instrument_key"] = True
    section_map = _map("C#")
    chords = [c for _n, cs in section_map for c in cs]
    _ensure_chord_selection(ss, list(chords), section_map)
    assert str(ss.get("ii_selected_chord")) in chords, ss.get("ii_selected_chord")
    state = resolve_mission_projection_state(ss, section_map=section_map, fallback_key="C#")
    assert state.concert_chord in chords and not _half_diminished(state.display_chord), state
    click = ss.get(CLICK)
    assert not (isinstance(click, dict) and click.get("source_identity") == BLACKBIRD
                and _half_diminished(click.get("chord")))


def test_the_same_songs_chord_still_follows_the_practice_key_on_the_page():
    flat_g, flat_cs = ([c for _n, cs in _map(k) for c in cs] for k in ("G", "C#"))
    idx = flat_g.index("Am7")
    ss = _session("C#", click=_click("Am7", song=BLACKBIRD, key="G", index=idx))
    ss["studio_page"] = "creative"
    _ensure_chord_selection(ss, list(flat_cs), _map("C#"))
    state = resolve_mission_projection_state(ss, section_map=_map("C#"), fallback_key="C#")
    assert state.concert_chord == flat_cs[idx]
