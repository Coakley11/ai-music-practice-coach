"""Issue 85 (second half): a chord clicked in one song never becomes another song's Mission chord.

Owner report 2026-11-22: Blackbird, Alto Saxophone, Practice Key C#, Mission chord A#m7b5. Blackbird's chart has no
half-diminished chord in any key. A chord click carries its song and Practice Key; the resolver transposed an old
click into the live Practice Key and kept it although it was not on the current song's chart, without asking which
song it belonged to, and then sealed it again under the current song.
"""
from __future__ import annotations

import copy
import itertools
import os
import tempfile

import pytest

os.environ.setdefault("SUITE_AUTH_ENABLED", "0")
os.environ.setdefault("MUSIC_APP_DATA_DIR", tempfile.mkdtemp(prefix="i85c_"))

from chart_level_arrangement import sections_for_level
from creative_chord_selection_authority import (
    MISSION_CHORD_SNAPSHOT_KEY,
    resolve_authoritative_chord_selection,
)
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
from mission_projection_state import resolve_mission_projection_state
from music_theory import transpose_sections_dict
from song_catalog.curated_songs import curated_song_records

BLACKBIRD = "Rock\x1fBlackbird - The Beatles"
OTHER = "Jazz\x1fAnother Song"
CLICK = "_mission_chord_click_authority"
ALTO, TENOR, SOPRANO = "Alto saxophone (Eb)", "Tenor saxophone (Bb)", "Soprano saxophone (Bb)"
KEYS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _chart(key, level="Advanced"):
    rec = next(r for r in curated_song_records() if r.get("title") == "Blackbird")
    return transpose_sections_dict(sections_for_level(rec, level), str(rec["key"]), key)


def _map(key, level="Advanced"):
    return [(name, list(chords)) for name, chords in _chart(key, level).items()]


def _click(chord, *, song, key, section="Intro / Verse", index=2):
    return {"chord": chord, "section": section, "chord_index": index, "practice_key": key,
            "mission_id": "Improvise using only chord tones", "session_id": "", "source_identity": song}


def _session(key="C#", *, click=None, selected="", instrument="Guitar", transposing=""):
    ss = {"studio_page": "backing", "improv_intelligence_tab": "Missions", "instrument": instrument,
          "active_catalog_pick_key": BLACKBIRD, "improv_active_mission": "Improvise using only chord tones",
          "improv_mission_concert_key": key, "display_key": key, "concert_key": key}
    if click:
        ss[CLICK] = copy.deepcopy(click)
        ss.update({"ii_selected_chord": click["chord"], "ii_selected_section": click["section"],
                   "ii_selected_chord_index": click["chord_index"]})
    if selected:
        ss["ii_selected_chord"] = selected
    if transposing:
        ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = transposing
        ss["show_chart_in_instrument_key"] = True
    return ss


def _half_diminished(chord):
    return any(t in str(chord) for t in ("m7b5", "m7♭5", "ø"))


# ---- the report ----------------------------------------------------------------------------------------------------

def test_a_chord_clicked_in_another_song_and_key_never_becomes_blackbirds_chord():
    """Em7b5 clicked in another song in G, then Blackbird in C#: that click became A#m7b5 for Blackbird."""
    ss = _session("C#", click=_click("Em7b5", song=OTHER, key="G"))
    chart = {c for _n, cs in _map("C#") for c in cs}
    state = resolve_mission_projection_state(ss, section_map=_map("C#"), fallback_key="C#")
    assert not _half_diminished(state.concert_chord), state.concert_chord
    assert state.concert_chord in chart
    assert ss[CLICK]["source_identity"] == BLACKBIRD and not _half_diminished(ss[CLICK]["chord"])
    assert not _half_diminished((ss.get(MISSION_CHORD_SNAPSHOT_KEY) or {}).get("concert_chord", ""))


@pytest.mark.parametrize("other_key, live_key", [(a, b) for a, b in itertools.product(KEYS, ["C#", "G", "A"])])
def test_no_pair_of_practice_keys_carries_another_songs_chord_in(other_key, live_key):
    ss = _session(live_key, click=_click("Em7b5", song=OTHER, key=other_key))
    chord, _sec, _idx = resolve_authoritative_chord_selection(ss, _map(live_key))
    assert chord in {c for _n, cs in _map(live_key) for c in cs}


def test_the_snapshot_of_another_song_is_not_kept_either():
    ss = _session("C#", click=_click("A#m7b5", song=OTHER, key="C#"))
    ss[MISSION_CHORD_SNAPSHOT_KEY] = {"mission_id": "Improvise using only chord tones", "source_identity": OTHER,
                                      "section": "Intro / Verse", "chord_index": 2, "concert_chord": "A#m7b5",
                                      "concert_practice_key": "C#"}
    state = resolve_mission_projection_state(ss, section_map=_map("C#"), fallback_key="C#")
    assert not _half_diminished(state.concert_chord), state.concert_chord


# ---- what must keep working: the same song's own click -------------------------------------------------------------

def test_the_songs_own_click_still_follows_a_practice_key_change():
    """D7 clicked in Blackbird in G is G#7 (Ab7) in C#: same slot, same chord, new key."""
    flat = [c for _n, cs in _map("G") for c in cs]
    idx = flat.index("D7")
    ss = _session("C#", click=_click("D7", song=BLACKBIRD, key="G", section="Return", index=idx))
    chord, _sec, at = resolve_authoritative_chord_selection(ss, _map("C#"))
    assert at == idx and chord == [c for _n, cs in _map("C#") for c in cs][idx]


def test_a_click_without_a_song_behaves_as_before():
    flat = [c for _n, cs in _map("C#") for c in cs]
    click = _click(flat[2], song="", key="C#")
    ss = _session("C#", click=click)
    assert resolve_authoritative_chord_selection(ss, _map("C#"))[0] == flat[2]


# ---- instrument and Practice Key changes ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
@pytest.mark.parametrize("instrument, transposing", [
    ("Guitar", ""), ("Saxophone", ALTO), ("Saxophone", TENOR), ("Saxophone", SOPRANO), ("Flute", "")])
def test_no_instrument_or_practice_key_gives_blackbird_a_half_diminished_chord(level, instrument, transposing):
    for key in KEYS:
        section_map = _map(key, level)
        total = sum(len(cs) for _n, cs in section_map)
        for idx in range(total):
            ss = _session(key, instrument=instrument, transposing=transposing)
            ss["ii_selected_chord_index"] = idx
            state = resolve_mission_projection_state(ss, section_map=section_map, fallback_key=key)
            assert not _half_diminished(state.concert_chord) and not _half_diminished(state.display_chord), (
                key, idx, state)


def test_guitar_to_alto_then_practice_key_keeps_the_clicked_slot():
    flat_g, flat_cs = ([c for _n, cs in _map(k) for c in cs] for k in ("G", "C#"))
    idx = flat_g.index("Am7")
    ss = _session("G", click=_click("Am7", song=BLACKBIRD, key="G", index=idx))
    assert resolve_mission_projection_state(ss, section_map=_map("G"), fallback_key="G").concert_chord == "Am7"
    ss.update({"instrument": "Saxophone", SELECTED_TRANSPOSING_INSTRUMENT_KEY: ALTO,
               "show_chart_in_instrument_key": True})
    assert resolve_mission_projection_state(ss, section_map=_map("G"), fallback_key="G").concert_chord == "Am7"
    ss.update({"improv_mission_concert_key": "C#", "display_key": "C#", "concert_key": "C#"})
    state = resolve_mission_projection_state(ss, section_map=_map("C#"), fallback_key="C#")
    assert state.concert_chord == flat_cs[idx]
