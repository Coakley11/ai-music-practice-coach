"""Karaoke Set settings lifecycle (user rules 2026-11-19).

PER ENTRY - reset whenever an entry begins (Start, Next, Previous, rewind): key = the entry's
saved setlist key, groove = the song's own, scope = Full song, BPM = the song's own. Temporary
changes during the song last for that performance only and are never saved.
SET LEVEL - carried to later songs, reset by a fresh Start: Repeat count (Loop Count, 1),
Lead Sheet On/Off (Off), Key Cycling On/Off + settings (Off; the Key Cycling owner's hook).
"""
from __future__ import annotations

import sys
import types

import pytest

import karaoke_mode as km
from song_catalog.catalog import load_song_catalog


def _pick(title: str) -> str:
    _lib, picker, _g, _r = load_song_catalog()
    for genre, songs in picker.items():
        for label, data in songs.items():
            if label.startswith(title + " "):
                return data.get("pick_key") or f"{genre}\x1f{label}"
    raise AssertionError(title)


SET = (("Shallow", "E"), ("Blue Bossa", "D"), ("Shape of You", "C"))


def _new_set(**extra) -> dict:
    session: dict = {"instrument": "Voice", **extra}
    for title, key in SET:
        km.add_to_queue(session, _pick(title), title=title, practice_key=key)
    return session


def _saved(session) -> list[tuple[str, str, str]]:
    return [(e["practice_key"], e["groove"], e["meter"]) for e in km.normalize_karaoke_queue(session[km.KARAOKE_QUEUE_KEY])]


@pytest.fixture()
def hooks(monkeypatch):
    calls: list[str] = []
    bps = types.ModuleType("backing_play_session")
    kc = types.ModuleType("backing_key_cycle")
    for mod, names in ((bps, ("reset_backing_after_karaoke_set",)),
                       (kc, ("key_cycle_karaoke_set_started", "key_cycle_karaoke_set_ended"))):
        for n in names:
            setattr(mod, n, (lambda name: (lambda s: calls.append(
                f"{name}@{'active' if s.get(km.KARAOKE_SESSION_ACTIVE_KEY) else 'inactive'}")))(n))
    monkeypatch.setitem(sys.modules, "backing_play_session", bps)
    monkeypatch.setitem(sys.modules, "backing_key_cycle", kc)
    return calls


def test_fresh_start_initialises_the_set_level_settings(hooks) -> None:
    s = _new_set()
    km.start_session(s)
    assert km.karaoke_set_loops(s) == 1
    assert s[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] is False
    # Key Cycling's hook before the set flag goes up (its owner's order). Backing takes no snapshot
    # any more (user rule 2026-11-20): End Set gives ordinary defaults, not the pre-set values.
    assert hooks == ["key_cycle_karaoke_set_started@inactive"]


def test_each_entry_starts_in_its_saved_key() -> None:
    s = _new_set()
    km.start_session(s)
    got = [km.current_session_practice_key(s)]
    km.advance_session(s)
    got.append(km.current_session_practice_key(s))
    km.advance_session(s)
    got.append(km.current_session_practice_key(s))
    assert got == ["E", "D", "C"]


def test_temporary_key_and_groove_do_not_reach_the_next_song_or_the_setlist() -> None:
    s = _new_set()
    km.start_session(s)
    km.advance_session(s)                                    # Blue Bossa, saved D
    entry = km.current_session_entry(s)
    km.set_performance_key(s, entry["entry_id"], "E")        # temporary E ...
    km.record_entry_feel_override(s, groove="Jazz Swing")    # ... and Jazz Swing
    assert km.current_session_practice_key(s) == "E"
    assert km.resolve_karaoke_entry_groove(s) == "Jazz Swing"
    km.advance_session(s)                                    # Shape of You, saved C
    assert km.current_session_practice_key(s) == "C"
    assert km.resolve_karaoke_entry_groove(s) == "Pop groove"
    assert _saved(s) == [("E", "", ""), ("D", "", ""), ("C", "", "")]


def test_previous_song_reinitialises_the_entry_but_keeps_set_settings() -> None:
    s = _new_set()
    km.start_session(s)
    km.advance_session(s)                                    # Blue Bossa D
    entry = km.current_session_entry(s)
    km.set_performance_key(s, entry["entry_id"], "E")
    km.record_entry_feel_override(s, groove="Jazz Swing", meter="3/4")
    km.note_karaoke_set_loops(s, 3)
    s[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] = True
    km.advance_session(s)
    km.regress_session(s)                                    # back to Blue Bossa
    assert km.current_session_entry(s)["entry_id"] == entry["entry_id"]
    assert km.current_session_practice_key(s) == "D"
    assert km.resolve_karaoke_entry_groove(s) == "Bossa nova"
    assert km.resolve_karaoke_entry_meter(s) == "4/4"
    assert km.karaoke_set_loops(s) == 3
    assert s[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] is True


def test_a_repeat_of_the_same_entry_keeps_its_temporary_choices() -> None:
    s = _new_set()
    km.start_session(s)
    entry = km.current_session_entry(s)
    km.set_entry_play_count(s, entry["entry_id"], 2)
    s[km.KARAOKE_ENTRY_PLAYS_LEFT_KEY] = 2
    km.set_performance_key(s, entry["entry_id"], "F")
    km.record_entry_feel_override(s, groove="Samba")
    km.advance_session(s)                                    # plays again, same entry
    assert km.current_session_entry(s)["entry_id"] == entry["entry_id"]
    assert km.current_session_practice_key(s) == "F"
    assert km.resolve_karaoke_entry_groove(s) == "Samba"


def test_repeat_count_is_set_level_and_a_new_set_starts_at_one(hooks) -> None:
    s = _new_set()
    assert km.note_karaoke_set_loops(s, 3) == 0              # no set: Backing keeps its own
    assert km.karaoke_set_loops(s) == 0
    km.start_session(s)
    km.note_karaoke_set_loops(s, 2)
    km.advance_session(s)
    assert km.karaoke_set_loops(s) == 2
    km.note_karaoke_set_loops(s, 3)
    km.advance_session(s)
    assert km.karaoke_set_loops(s) == 3
    km.stop_session(s)
    assert km.karaoke_set_loops(s) == 0
    assert km.KARAOKE_SET_LOOPS_KEY not in s
    # End Set: Backing's ordinary reset, then Key Cycling's, both after the set flag has dropped.
    assert hooks[-2:] == ["reset_backing_after_karaoke_set@inactive", "key_cycle_karaoke_set_ended@inactive"]
    km.start_session(s)
    assert km.karaoke_set_loops(s) == 1


def test_a_new_set_forgets_everything_temporary_from_the_last_one() -> None:
    s = _new_set()
    km.start_session(s)
    km.advance_session(s)
    km.set_performance_key(s, km.current_session_entry(s)["entry_id"], "E")
    km.record_entry_feel_override(s, groove="Jazz Swing")
    s[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] = True
    # The set is restored without a Stop (a reload, a crash): the next Start still starts clean.
    km.start_session(s)
    assert km.performance_keys(s) == {}
    assert km.KARAOKE_PERFORMANCE_FEEL_KEY not in s
    assert s[km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY] is False
    km.advance_session(s)
    assert km.current_session_practice_key(s) == "D"
    assert km.resolve_karaoke_entry_groove(s) == "Bossa nova"


def test_end_set_keeps_the_saved_setlist_and_drops_the_temporaries() -> None:
    s = _new_set()
    km.start_session(s)
    km.advance_session(s)
    km.set_performance_key(s, km.current_session_entry(s)["entry_id"], "E")
    km.record_entry_feel_override(s, groove="Jazz Swing")
    km.stop_session(s)
    assert _saved(s) == [("E", "", ""), ("D", "", ""), ("C", "", "")]
    assert km.performance_keys(s) == {}
    assert km.KARAOKE_PERFORMANCE_FEEL_KEY not in s
    assert km.KARAOKE_SET_LEAD_SHEET_OPEN_KEY not in s


def test_a_groove_saved_on_a_row_by_the_old_override_is_kept_but_not_played() -> None:
    s = _new_set()
    queue = km.get_queue(s)
    queue[1]["groove"] = "Jazz Swing"                       # written by the pre-2026-11-19 design
    s[km.KARAOKE_QUEUE_KEY] = queue
    km.start_session(s)
    km.advance_session(s)
    assert km.resolve_karaoke_entry_groove(s) == "Bossa nova"
    assert km.get_queue(s)[1]["groove"] == "Jazz Swing"     # saved data untouched


def test_feel_outside_a_set_is_not_recorded() -> None:
    s = _new_set()
    assert not km.record_entry_feel_override(s, groove="Samba")
    assert km.KARAOKE_PERFORMANCE_FEEL_KEY not in s


def test_the_app_no_longer_saves_a_set_feel_change_to_the_setlist() -> None:
    from pathlib import Path

    app = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = app.index("km.record_entry_feel_override(")
    assert "persist_karaoke_setlist" not in app[i - 900:i + 700]


def test_the_backing_card_shows_the_sung_key_for_the_whole_set() -> None:
    from pathlib import Path

    app = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    i = app.index('_sing_pick = str(km.now_singing_pick_key(st.session_state) or "").strip()')
    cond = app[i:i + 400]
    assert "ACTIVE_CATALOG_PICK_KEY" not in cond
    assert "_render_backing_card_performance_key" in app[i:i + 2600]
