"""Issue 85 through the app's real song switch: the previous song's Mission chord never becomes the next song's.

Autumn Leaves' half-diminished chord is chosen in a Mission, Blackbird is opened the way the app opens it, and Mission
Backing (what is heard) and the lick panel (what is shown) must be Blackbird's, in G and after moving to C#.
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("SUITE_AUTH_ENABLED", "0")
os.environ.setdefault("MUSIC_APP_DATA_DIR", tempfile.mkdtemp(prefix="i85s_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backing_context as bc
from chart_level_arrangement import sections_for_level
from creative_chord_selection_authority import (
    note_mission_selection_song,
    read_authoritative_mission_chord_selection,
    write_authoritative_chord_selection,
)
from creative_key_sync import apply_specialized_mission_practice_key
from mission_projection_state import resolve_mission_projection_state
from music_theory import transpose_sections_dict
from song_catalog.catalog import load_song_catalog
from songs.music_source import (
    begin_explicit_catalog_selection,
    ensure_song_picker_catalog,
    note_active_source_change,
    set_catalog_source,
)
from songs.state import activate_active_song_by_pick_key

LIBRARY, PICKER, _G, _R = load_song_catalog()
CLICK = "_mission_chord_click_authority"


def _find(title):
    return next((d.get("pick_key") or f"{g}\x1f{label}", d) for g, songs in PICKER.items()
                for label, d in songs.items() if label.startswith(title))


LEAVES_PICK, LEAVES = _find("Autumn Leaves")
BLACKBIRD_PICK, BLACKBIRD = _find("Blackbird")


def _hd(chord):
    return any(t in str(chord) for t in ("m7b5", "ø"))


def _run(ss):
    """What every app run does about the active song."""
    note_active_source_change(SimpleNamespace(session_state=ss), invalidate_backing=lambda _st: None)


def _open(ss, pick):
    begin_explicit_catalog_selection(ss)
    ss.setdefault("active_catalog_pick_key", pick)
    set_catalog_source(ss)
    activate_active_song_by_pick_key(SimpleNamespace(session_state=ss), pick, PICKER, song_library=LIBRARY, origin="user")
    _run(ss)


def _map(song):
    return [(n, list(c)) for n, c in sections_for_level(song, "Advanced").items()]


def _choose(ss, section_map, want):
    sec, chord, idx = next((n, c, i) for i, (n, c) in enumerate((n, c) for n, cs in section_map for c in cs) if want(c))
    ss["_improv_mission_section_map"] = section_map
    ss["improv_mission_chord_options"] = [c for _n, cs in section_map for c in cs]
    write_authoritative_chord_selection(ss, section_map, chord_symbol=chord, section_label=sec, chord_index=idx)
    _run(ss)
    return chord, idx


def _session(page="creative"):
    ss = {"studio_page": page, "instrument": "Guitar", "level": "Advanced", "improv_intelligence_tab": "Missions",
          "improv_active_mission": "Improvise using only chord tones", "improv_mission_pick": "Improvise using only chord tones"}
    ensure_song_picker_catalog(ss, PICKER)
    return ss


def _seen_and_heard(ss):
    s = copy.deepcopy({k: v for k, v in ss.items() if "picker" not in k and "library" not in k})
    shown = resolve_mission_projection_state(copy.deepcopy(s), section_map=s.get("_improv_mission_section_map"), fallback_key="G")
    ctx = bc.build_mission_context(s)
    return [read_authoritative_mission_chord_selection(copy.deepcopy(s))[0], shown.concert_chord, shown.display_chord,
            *[str(c) for c in (ctx.progression or [])]]


@pytest.mark.parametrize("page", ["creative", "backing"])
@pytest.mark.parametrize("new_key", [None, "C#"])
def test_the_previous_songs_chord_is_neither_shown_nor_played(page, new_key):
    ss = _session(page)
    _open(ss, LEAVES_PICK)
    _choose(ss, _map(LEAVES), _hd)
    _open(ss, BLACKBIRD_PICK)
    if new_key:
        ss["studio_page"] = "backing"
        ss.setdefault("improv_mission_concert_key", ss.get("concert_key") or "G")
        apply_specialized_mission_practice_key(ss, new_key)
    assert not [c for c in _seen_and_heard(ss) if _hd(c)], _seen_and_heard(ss)


def test_the_map_alone_does_not_survive_the_switch():
    """No chord was clicked: the previous song's map must not supply the next song's first chord."""
    ss = _session()
    _open(ss, LEAVES_PICK)
    ss["_improv_mission_section_map"] = _map(LEAVES)
    _run(ss)
    _open(ss, BLACKBIRD_PICK)
    assert not ss.get("_improv_mission_section_map")


def test_choosing_in_the_new_song_works_and_stays():
    ss = _session()
    _open(ss, LEAVES_PICK)
    _choose(ss, _map(LEAVES), _hd)
    _open(ss, BLACKBIRD_PICK)
    chord, _idx = _choose(ss, _map(BLACKBIRD), lambda c: c == "Am7")
    for _ in range(3):
        _run(ss)
    assert read_authoritative_mission_chord_selection(ss)[0] == chord == "Am7"


def test_instrument_and_key_changes_in_the_same_song_keep_the_choice():
    ss = _session("backing")
    _open(ss, BLACKBIRD_PICK)
    _chord, idx = _choose(ss, _map(BLACKBIRD), lambda c: c == "Am7")
    ss["instrument"] = "Saxophone"
    _run(ss)
    assert read_authoritative_mission_chord_selection(copy.deepcopy(ss))[0] == "Am7"
    ss.setdefault("improv_mission_concert_key", "G")
    apply_specialized_mission_practice_key(ss, "C#")
    _run(ss)
    moved = [c for cs in transpose_sections_dict(dict(_map(BLACKBIRD)), "G", "C#").values() for c in cs]
    assert read_authoritative_mission_chord_selection(copy.deepcopy(ss))[0] == moved[idx]


def test_a_choice_restored_together_with_the_new_song_is_kept():
    """Return to Mission writes the song and its chord in one step, with no click."""
    ss = _session()
    _open(ss, LEAVES_PICK)
    _choose(ss, _map(LEAVES), _hd)
    ss.pop(CLICK, None)
    ss.pop("_mission_chord_snapshot", None)
    ss.update({"ii_selected_chord": "Am7", "ii_selected_section": "Intro / Verse", "ii_selected_chord_index": 1})
    ss["active_catalog_pick_key"] = BLACKBIRD_PICK
    _run(ss)
    assert ss["ii_selected_chord"] == "Am7"


def test_a_carried_choice_without_a_click_is_dropped():
    ss = _session()
    _open(ss, LEAVES_PICK)
    _choose(ss, _map(LEAVES), _hd)
    ss.pop(CLICK, None)
    ss.pop("_mission_chord_snapshot", None)
    _run(ss)
    _open(ss, BLACKBIRD_PICK)
    assert not _hd(ss.get("ii_selected_chord"))


def test_the_first_run_of_a_restored_session_drops_nothing():
    ss = {"ii_selected_chord": "Am7", "ii_selected_section": "Intro / Verse", "ii_selected_chord_index": 1,
          "active_catalog_pick_key": BLACKBIRD_PICK, "_improv_mission_section_map": _map(BLACKBIRD)}
    assert note_mission_selection_song(ss, song_changed=False) is False
    assert ss["ii_selected_chord"] == "Am7" and ss["_improv_mission_section_map"]
