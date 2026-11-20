"""A Catalog song saved without a Practice Key must come back in its Original Key, never in a made-up C.

Measured 2026-11-18 (user report, Shallow): Original Key G, but the Backing played, charted and key-cycled in C and
the Guitar sidebar said "Sounding Key: C". Three fallbacks each invented "C" when no Practice Key had been saved:
the workspace restore (``_resolve_display_key_from_music_blob``'s default), the practice-source snapshot the Backing
rebuild remembers, and the Practice Key that rebuild was told to preserve. A saved Practice Key is still kept.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _seed_and_restore(monkeypatch, tmp_path, *, instrument: str, saved_key: str = "") -> dict:
    monkeypatch.setenv("MUSIC_APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(ROOT)
    from music_persistent_state import persist_music_disk_state, prepare_music_workspace
    from song_catalog.catalog import load_song_catalog
    from songs.music_source import begin_explicit_catalog_selection, ensure_song_picker_catalog, set_catalog_source
    from songs.state import activate_active_song_by_pick_key

    library, picker, _g, _r = load_song_catalog()
    pick = next(d.get("pick_key") or f"{g}\x1f{l}" for g, s in picker.items() for l, d in s.items()
                if l.startswith("Shallow "))
    session: dict = {"studio_page": "backing", "instrument": instrument}
    ensure_song_picker_catalog(session, picker)
    begin_explicit_catalog_selection(session)
    session["active_catalog_pick_key"] = pick
    set_catalog_source(session)
    activate_active_song_by_pick_key(SimpleNamespace(session_state=session), pick, picker,
                                     song_library=library, origin="user")
    if saved_key:
        session["display_key"] = saved_key
        if isinstance(session.get("active_song_state"), dict):
            session["active_song_state"]["display_key"] = saved_key
    persist_music_disk_state(SimpleNamespace(session_state=session))
    # A new browser session: nothing in memory, everything from the saved workspace.
    fresh: dict = {}
    prepare_music_workspace(SimpleNamespace(session_state=fresh), song_picker_catalog=picker, song_library=library)
    return fresh


@pytest.mark.parametrize("instrument", ["Guitar", "Flute"])
def test_a_song_saved_without_a_practice_key_restores_in_its_original_key(monkeypatch, tmp_path, instrument):
    s = _seed_and_restore(monkeypatch, tmp_path, instrument=instrument)
    assert s.get("display_key") == "G", s.get("display_key")
    assert s.get("concert_key") == "G", s.get("concert_key")


def test_a_saved_practice_key_is_still_kept(monkeypatch, tmp_path):
    s = _seed_and_restore(monkeypatch, tmp_path, instrument="Guitar", saved_key="A")
    assert s.get("display_key") == "A"


def test_no_saved_key_resolves_to_nothing_not_c():
    from active_song_state import _resolve_display_key_from_music_blob
    from backing_source_navigation import (
        PRACTICE_SOURCE_DISPLAY_KEY,
        _resolved_practice_display_key,
        snapshot_practice_source_display_key,
    )

    assert _resolve_display_key_from_music_blob({}, home_key="") == ""
    assert _resolve_display_key_from_music_blob({"core": {"display_key": "Eb"}}, home_key="") == "Eb"
    assert _resolve_display_key_from_music_blob({}, home_key="F") == "F"      # a Custom song's own home key
    session: dict = {}
    snapshot_practice_source_display_key(session)
    assert PRACTICE_SOURCE_DISPLAY_KEY not in session
    assert _resolved_practice_display_key({}) == ""
    session = {"display_key": "G"}
    snapshot_practice_source_display_key(session)
    assert session[PRACTICE_SOURCE_DISPLAY_KEY] == "G"


class _UI:
    """Just enough of the sidebar for render_guitar_capo_sidebar: collects what it writes."""

    def __init__(self, capo_on: bool):
        self.lines: list[str] = []
        self.capo_on = capo_on

    def markdown(self, text, **_kw):
        self.lines.append(str(text))

    def checkbox(self, _label, **_kw):
        return self.capo_on

    def selectbox(self, _label, options, **_kw):
        return options[0] if options else None

    def caption(self, text, **_kw):
        self.lines.append(str(text))


def test_capo_shape_mode_off_shows_the_sounding_key_and_no_shape_key():
    """User, 2026-11-18: with Capo Shape Mode OFF the sidebar shows the Practice (sounding) Key -- G for Shallow
    in G -- and no active Shape Key."""
    from guitar_capo import render_guitar_capo_sidebar

    ui = _UI(capo_on=False)
    session: dict = {"instrument": "Guitar", "display_key": "G", "concert_key": "G"}
    render_guitar_capo_sidebar(ui, session, practice_display_key="G", persist_st=SimpleNamespace(session_state=session, rerun=lambda: None))
    text = " ".join(ui.lines)
    assert "<strong>Sounding Key:</strong> G" in text
    assert "Shape Key" not in text
    assert "Capo Fret" not in text


def _shallow_on_backing(leftover_style_jam: bool) -> dict:
    from song_catalog.catalog import load_song_catalog
    from songs.music_source import begin_explicit_catalog_selection, ensure_song_picker_catalog, set_catalog_source
    from songs.state import activate_active_song_by_pick_key

    library, picker, _g, _r = load_song_catalog()
    pick = next(d.get("pick_key") or f"{g}\x1f{l}" for g, s in picker.items() for l, d in s.items()
                if l.startswith("Shallow "))
    session: dict = {"studio_page": "picker", "instrument": "Guitar"}
    ensure_song_picker_catalog(session, picker)
    begin_explicit_catalog_selection(session)
    session["active_catalog_pick_key"] = pick
    set_catalog_source(session)
    activate_active_song_by_pick_key(SimpleNamespace(session_state=session), pick, picker, song_library=library,
                                     origin="user")
    session["studio_page"] = "backing"
    if leftover_style_jam:  # what a Style Jam in C used earlier leaves behind
        session.update({"improv_entry_mode": "Style Jam Mode", "improv_intelligence_tab": "Entry & Jam",
                        "improv_style_key": "C"})
    return session


@pytest.mark.parametrize("leftover", [False, True])
def test_leftover_style_jam_state_does_not_take_a_songs_key_on_backing(monkeypatch, tmp_path, leftover):
    """User screenshot 2026-11-18: Shallow in G on Backing, Guitar sidebar "Sounding Key: C". A Style Jam used
    earlier left its entry mode and key behind, and the sidebar took the jam's key for the song's."""
    monkeypatch.setenv("MUSIC_APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.chdir(ROOT)
    from creative_key_sync import entry_jam_practice_key_authority_active, is_creative_major_jam_active
    from guitar_capo import live_capo_shape_source_id

    s = _shallow_on_backing(leftover)
    assert not is_creative_major_jam_active(s)
    assert not entry_jam_practice_key_authority_active(s)
    assert not live_capo_shape_source_id(s).startswith("generated::jam")


def test_a_jam_playing_on_backing_still_owns_the_key(monkeypatch):
    """The guard is about LEFTOVER state: while Backing plays the Style Jam, the jam's key is the key."""
    import backing_context
    from creative_key_sync import _backing_plays_entry_jam, is_creative_major_jam_active

    monkeypatch.setattr(backing_context, "get_backing_context",
                        lambda _s: SimpleNamespace(source="entry_jam", entry_mode="Style Jam Mode"))
    s = {"studio_page": "backing", "improv_entry_mode": "Style Jam Mode", "improv_intelligence_tab": "Entry & Jam",
         "improv_style_key": "C"}
    assert _backing_plays_entry_jam(s)
    assert is_creative_major_jam_active(s)
