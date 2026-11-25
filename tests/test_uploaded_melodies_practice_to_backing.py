"""Uploaded Melodies Slice 2: the references chosen on Practice are the ones Backing shows."""
from __future__ import annotations

from contextlib import nullcontext

import pytest

import backing_melody_modes as bmm

OWNER = {"source_type": "catalog", "source_id": "Pop|Shallow", "song_title": "Shallow"}
OTHER = {"source_type": "custom", "source_id": "custom::song-a", "song_title": "Song A"}
ROWS = [{"document_id": d, "title": d.upper()} for d in ("a", "b", "c")]
IDENT = bmm.owner_identity(OWNER)


class _St:
    def __init__(self, session, press=False):
        self.session, self.press, self.panels = session, press, {}

    def multiselect(self, _label, _ids, *, key, **_kw):
        return list(self.session.get(key) or [])

    def button(self, *_a, **_k):
        return self.press

    def caption(self, *_a, **_k):
        pass

    def expander(self, _label, *, expanded, key):
        self.panels[key[len(bmm.UPLOADED_PANEL_KEY_PREFIX):]] = expanded
        return nullcontext()


@pytest.fixture
def library(monkeypatch):
    import song_document_catalog as cat
    import song_document_panel as panel

    state = {"owner": OWNER, "rows": list(ROWS)}
    monkeypatch.setattr(cat, "active_song_owner", lambda *_a, **_k: state["owner"])
    monkeypatch.setattr(cat, "documents_for_owner", lambda *_a, **_k: list(state["rows"]))
    monkeypatch.setattr(panel, "render_song_document_reference", lambda *_a, **_k: None)
    return state


def practice(session, *, rows=ROWS, choose=None, press=False):
    """Draw Practice's choice; ``choose`` is the user changing the widget (Streamlit stores it, runs on_change)."""
    if choose is not None:
        key = bmm.practice_picker_key(IDENT)
        session[key] = list(choose)
        bmm.commit_reference_choice(session, IDENT, key, [r["document_id"] for r in rows], from_practice=True)
    return bmm.render_practice_reference_choice(_St(session, press), session, owner=OWNER, rows=list(rows))


def backing(session):
    st = _St(session)
    bmm.render_uploaded_references(st, session)
    return st.panels


def test_a_choice_on_practice_shows_on_backing_in_its_order_and_selects_the_mode(library):
    s = {}
    practice(s, choose=["c", "a"])
    assert bmm.apply_pending_melody_mode(s) == bmm.MODE_UPLOADED
    assert list(backing(s)) == ["c", "a"]


def test_plain_navigation_starts_closed_and_open_in_backing_opens_the_chosen_panels(library):
    s = {}
    practice(s, choose=["a", "b"])
    assert backing(s) == {"a": False, "b": False}
    assert practice(s, press=True) is True
    assert backing(s) == {"a": True, "b": True}
    assert backing(s) == {"a": True, "b": True}  # steady over reruns: never snaps shut by itself
    practice(s)  # back on Practice: the one-time open is spent
    assert backing(s) == {"a": False, "b": False}


def test_the_two_pickers_edit_one_choice(library):
    s = {}
    practice(s, choose=["a"])
    key = bmm.picker_key(IDENT)
    s[key] = ["b"]
    bmm.commit_reference_choice(s, IDENT, key, ["a", "b", "c"])
    practice(s)
    assert s[bmm.practice_picker_key(IDENT)] == ["b"]


def test_a_leftover_widget_value_never_replaces_the_stored_choice(library):
    s = {}
    practice(s, choose=["a"])
    s[bmm.picker_key(IDENT)] = ["b", "c"]  # e.g. an old Backing page snapshot
    assert list(backing(s)) == ["a"]
    assert bmm.selected_reference_ids(s, IDENT, ["a", "b", "c"]) == ["a"]


def test_a_choice_belongs_to_its_song(library):
    s = {}
    practice(s, choose=["a"], press=True)
    library["owner"], library["rows"] = OTHER, [{"document_id": "z"}]
    assert backing(s) == {}
    library["owner"], library["rows"] = OWNER, list(ROWS)
    assert list(backing(s)) == ["a"]


def test_a_slow_library_does_not_lose_choices(library):
    s = {}
    practice(s, choose=["a", "c"])
    library["rows"] = ROWS[:1]
    assert list(backing(s)) == ["a"]  # c is not listed right now
    practice(s, rows=ROWS[:1], choose=["a"])
    library["rows"] = list(ROWS)
    assert list(backing(s)) == ["a", "c"]  # back once it is listed again


def test_clearing_the_choice_clears_it_on_backing_and_does_not_switch_mode(library):
    s = {}
    practice(s, choose=["a"])
    bmm.apply_pending_melody_mode(s)
    s[bmm.MODE_KEY] = bmm.MODE_PRACTICE
    practice(s, choose=[])
    assert bmm.apply_pending_melody_mode(s) == bmm.MODE_PRACTICE
    assert backing(s) == {}


def test_choosing_changes_nothing_musical(library):
    s = {"display_key": "D", "concert_key": "D", "instrument": "Flute", "backing_track_bpm": 90,
         "backing_track_loops": 2, "active_catalog_pick_key": "Pop|Shallow"}
    before = dict(s)
    practice(s, choose=["a"], press=True)
    backing(s)
    assert {k: s[k] for k in before} == before


def test_the_real_widgets_carry_a_choice_from_practice_to_backing():
    """The same two pickers as real Streamlit widgets, each drawn on its own page."""
    from streamlit.testing.v1 import AppTest

    def app():
        import streamlit as st

        import backing_melody_modes as m
        import song_document_catalog as cat
        import song_document_panel as panel

        owner = {"source_type": "catalog", "source_id": "Pop|Shallow", "song_title": "Shallow"}
        rows = [{"document_id": d, "title": d.upper()} for d in ("a", "b", "c")]
        cat.active_song_owner = lambda *_a, **_k: owner
        cat.documents_for_owner = lambda *_a, **_k: rows
        panel.render_song_document_reference = lambda *_a, **_k: None
        if st.session_state.get("page", "practice") == "practice":
            if m.render_practice_reference_choice(st, st.session_state, owner=owner, rows=rows):
                st.session_state["pressed"] = True
        else:
            m.apply_pending_melody_mode(st.session_state)
            m.render_uploaded_references(st, st.session_state)

    import song_document_catalog as cat
    import song_document_panel as panel

    saved = (cat.active_song_owner, cat.documents_for_owner, panel.render_song_document_reference)
    try:
        at = AppTest.from_function(app, default_timeout=60).run()
        at.multiselect[0].set_value(["b", "c"]).run()
        assert not at.exception
        at.session_state["page"] = "backing"
        at.run()
        assert at.multiselect[0].value == ["b", "c"]
        assert at.session_state[bmm.MODE_KEY] == bmm.MODE_UPLOADED
        at.multiselect[0].set_value(["c"]).run()
        assert at.multiselect[0].value == ["c"]
        at.session_state["page"] = "practice"
        at.run()
        assert at.multiselect[0].value == ["c"] and not at.exception
        at.button[0].click().run()
        assert at.session_state["pressed"] is True
    finally:
        cat.active_song_owner, cat.documents_for_owner, panel.render_song_document_reference = saved


def test_the_practice_page_offers_the_choice_and_the_panel_stays_free_of_backing(library):
    from pathlib import Path

    app = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    block = app[app.index("_open_uploaded_in_backing = render_active_song_reference_choice"):]
    assert block.index('navigate_studio_page(st.session_state, "backing")') < block.index("render_song_documents_panel(st")
    s = {}
    practice(s, choose=["b"])
    assert bmm.render_active_song_reference_choice(_St(s, press=True), s) is True
    assert backing(s) == {"b": True}
    library["owner"] = {}
    assert bmm.render_active_song_reference_choice(_St(s, press=True), s) is False
    library["owner"], library["rows"] = OWNER, []
    assert bmm.render_active_song_reference_choice(_St(s, press=True), s) is False
