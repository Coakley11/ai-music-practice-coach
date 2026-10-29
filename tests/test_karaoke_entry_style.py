"""Each Karaoke entry plays its own style; an explicit Feel stays with its entry.

A set started with Shallow (Ballad) generated every later entry -- Blue Bossa,
Shape of You -- as a Ballad: groove came from Now Editing / the live Feel
widget, while BPM was already per entry.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import karaoke_mode as km
from backing_context import catalog_default_groove_for_pick
from song_catalog.catalog import load_song_catalog

APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
OWNERSHIP = (Path(__file__).resolve().parents[1] / "music_source_ownership.py").read_text(encoding="utf-8")


def _pick(title: str) -> str:
    _lib, picker, _g, _r = load_song_catalog()
    for genre, songs in picker.items():
        for label, data in songs.items():
            if label.startswith(title + " "):
                return data.get("pick_key") or f"{genre}\x1f{label}"
    raise AssertionError(title)


@pytest.fixture()
def karaoke_set():
    session: dict = {"instrument": "Voice", "backing_groove_style": "Ballad"}
    for title in ("Shallow", "Blue Bossa", "Shape of You"):
        km.add_to_queue(session, _pick(title), title=title)
    km.start_session(session)
    return session


def test_catalog_default_groove_is_per_song() -> None:
    assert catalog_default_groove_for_pick(_pick("Shallow")) == "Ballad"
    assert catalog_default_groove_for_pick(_pick("Blue Bossa")) == "Bossa nova"
    assert catalog_default_groove_for_pick(_pick("Shape of You")) == "Pop groove"
    assert catalog_default_groove_for_pick("custom::x") == ""


def test_each_entry_resolves_its_own_groove_not_the_live_widget(karaoke_set) -> None:
    queue = km.get_queue(karaoke_set)
    got = [km.resolve_karaoke_entry_groove(karaoke_set, e) for e in queue]
    assert got == ["Ballad", "Bossa nova", "Pop groove"]
    assert all(km.resolve_karaoke_entry_meter(karaoke_set, e) == "4/4" for e in queue)


def test_override_is_stored_on_the_sung_entry_only(karaoke_set) -> None:
    karaoke_set[km.KARAOKE_SESSION_INDEX_KEY] = 1
    assert km.record_entry_feel_override(karaoke_set, groove="Samba")
    queue = km.get_queue(karaoke_set)
    assert [e["groove"] for e in queue] == ["", "Samba", ""]
    assert km.resolve_karaoke_entry_groove(karaoke_set, queue[1]) == "Samba"
    # The next entry keeps its own style; the overridden one survives a reload.
    assert km.resolve_karaoke_entry_groove(karaoke_set, queue[2]) == "Pop groove"
    restored = km.normalize_karaoke_queue(karaoke_set[km.KARAOKE_QUEUE_KEY])
    assert restored[1]["groove"] == "Samba"


def test_no_override_outside_an_active_set() -> None:
    session: dict = {"instrument": "Voice"}
    km.add_to_queue(session, _pick("Shallow"), title="Shallow")
    assert not km.record_entry_feel_override(session, groove="Samba")


def test_catalog_record_path_takes_the_picks_own_groove() -> None:
    assert "catalog_default_groove_for_pick(pick_key)" in OWNERSHIP


def test_backing_page_uses_entry_groove_and_meter_during_karaoke() -> None:
    block = APP[APP.index("_entry_groove = str(km.resolve_karaoke_entry_groove(st.session_state)"):][:600]
    assert "_backing_source_default_groove = _entry_groove" in block
    assert "_backing_source_default_meter = _entry_meter" in block
    assert "km.record_entry_feel_override(" in APP
