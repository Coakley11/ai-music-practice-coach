"""The Songs picker selectbox must be a projection of the canonical active
song, never an independent authority.

Streamlit only sends a selectbox's value to the browser when its key was
assigned in the current run. When the picker is unmounted (another page is
shown) and later redrawn, ``sync_matching_song_dropdown_before_widget`` used to
skip the assignment because the stored value already equalled the active
pick -- so the browser rebuilt the widget at its default option (index 0),
and the next unrelated interaction reported that option as a user change,
firing ``_on_song_dropdown_change`` and committing a song nobody picked
(captured live: ATTYA -> Say on a routine Level change).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from songs.state import (
    ACTIVE_CATALOG_PICK_KEY,
    EXPLICIT_CATALOG_PICK_COMMITTED_KEY,
    PENDING_MATCHING_SONG_DROPDOWN,
    sync_matching_song_dropdown_before_widget,
)
from streamlit.testing.v1 import AppTest

PK_SAY = "Pop\x1fSay — John Mayer"
PK_ATTYA = "Jazz\x1fAll the Things You Are — Jazz Standard"
PK_PERFECT = "Pop\x1fPerfect — Ed Sheeran"
OPTIONS = [PK_SAY, PK_ATTYA, PK_PERFECT]


class _RecordingSession(dict):
    """Dict that records every assignment, including same-value ones."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.writes: list[tuple[str, object]] = []

    def __setitem__(self, key, value):
        self.writes.append((key, value))
        super().__setitem__(key, value)


def _st(session: dict) -> SimpleNamespace:
    return SimpleNamespace(session_state=session, rerun=lambda: None)


class TestSameValueSynchronization(unittest.TestCase):
    def test_assigns_widget_key_even_when_value_already_equal(self) -> None:
        session = _RecordingSession({
            ACTIVE_CATALOG_PICK_KEY: PK_ATTYA,
            "matching_song_dropdown": PK_ATTYA,
        })
        session.writes.clear()
        active = sync_matching_song_dropdown_before_widget(_st(session), list(OPTIONS), PK_ATTYA)
        self.assertEqual(active, PK_ATTYA)
        self.assertIn(("matching_song_dropdown", PK_ATTYA), session.writes)

    def test_projects_canonical_over_stale_widget_value(self) -> None:
        session = _RecordingSession({
            ACTIVE_CATALOG_PICK_KEY: PK_ATTYA,
            "matching_song_dropdown": PK_SAY,
        })
        sync_matching_song_dropdown_before_widget(_st(session), list(OPTIONS), PK_ATTYA)
        self.assertEqual(session["matching_song_dropdown"], PK_ATTYA)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], PK_ATTYA)


class TestPendingPickUnchanged(unittest.TestCase):
    def test_pending_equal_to_active_is_applied(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_ATTYA,
            "matching_song_dropdown": PK_SAY,
            PENDING_MATCHING_SONG_DROPDOWN: PK_ATTYA,
        }
        sync_matching_song_dropdown_before_widget(_st(session), list(OPTIONS), PK_ATTYA)
        self.assertEqual(session["matching_song_dropdown"], PK_ATTYA)
        self.assertNotIn(PENDING_MATCHING_SONG_DROPDOWN, session)

    def test_stale_pending_does_not_overwrite_visible_widget(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_ATTYA,
            "matching_song_dropdown": PK_ATTYA,
            PENDING_MATCHING_SONG_DROPDOWN: PK_SAY,
            EXPLICIT_CATALOG_PICK_COMMITTED_KEY: PK_ATTYA,
        }
        sync_matching_song_dropdown_before_widget(_st(session), list(OPTIONS), PK_ATTYA)
        self.assertEqual(session["matching_song_dropdown"], PK_ATTYA)

    def test_pending_without_visible_widget_is_applied(self) -> None:
        session = {
            ACTIVE_CATALOG_PICK_KEY: PK_ATTYA,
            PENDING_MATCHING_SONG_DROPDOWN: PK_PERFECT,
        }
        sync_matching_song_dropdown_before_widget(_st(session), list(OPTIONS), PK_ATTYA)
        self.assertEqual(session["matching_song_dropdown"], PK_PERFECT)


def _picker_app():
    """Smallest app reproducing the Songs-picker unmount/remount lifecycle with
    the real ``sync_matching_song_dropdown_before_widget``. ``commits`` counts
    every call of the change handler -- the stand-in for the real
    ``_on_song_dropdown_change -> commit_catalog_active_song`` path."""
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    import streamlit as st
    from songs.state import ACTIVE_CATALOG_PICK_KEY, sync_matching_song_dropdown_before_widget

    say = "Pop\x1fSay — John Mayer"
    attya = "Jazz\x1fAll the Things You Are — Jazz Standard"
    perfect = "Pop\x1fPerfect — Ed Sheeran"
    options = [say, attya, perfect]
    ss = st.session_state
    if ACTIVE_CATALOG_PICK_KEY not in ss:
        ss[ACTIVE_CATALOG_PICK_KEY] = attya
    if "commits" not in ss:
        ss["commits"] = []

    def _on_song_change():
        ss["commits"] = ss["commits"] + [ss["matching_song_dropdown"]]
        ss[ACTIVE_CATALOG_PICK_KEY] = ss["matching_song_dropdown"]

    page = st.radio("page", ["songs", "practice"], key="page")
    if page == "songs":
        opts = list(options)
        sync_matching_song_dropdown_before_widget(st, opts, ss[ACTIVE_CATALOG_PICK_KEY])
        st.selectbox("Active song", opts, key="matching_song_dropdown", on_change=_on_song_change)
    else:
        st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"], key="level")
    st.checkbox("unrelated", key="unrelated")


class TestPickerRemount(unittest.TestCase):
    """Lifecycle guard in a real Streamlit runtime: unmount/remount must not
    commit, and a genuine selection must commit exactly once.

    Note: Streamlit's AppTest does not model a browser rebuilding a remounted
    selectbox at its default option (these tests also pass on the pre-fix
    code), so they guard against regressions in the commit/selection path
    rather than reproducing the original defect. The defect itself is pinned
    by ``TestSameValueSynchronization`` and by browser acceptance."""
    def _at(self) -> AppTest:
        at = AppTest.from_function(_picker_app, default_timeout=30)
        at.run()
        self.assertFalse(at.exception)
        return at

    def _go(self, at: AppTest, page: str) -> None:
        at.radio(key="page").set_value(page).run()
        self.assertFalse(at.exception)

    def test_remount_shows_canonical_song_and_unrelated_rerun_does_not_commit(self) -> None:
        at = self._at()
        self.assertEqual(at.selectbox(key="matching_song_dropdown").value, PK_ATTYA)
        for _ in range(3):
            self._go(at, "practice")
            at.selectbox(key="level").set_value("Advanced").run()
            self._go(at, "songs")
            self.assertEqual(at.selectbox(key="matching_song_dropdown").value, PK_ATTYA)
            at.checkbox(key="unrelated").check().run()
            at.checkbox(key="unrelated").uncheck().run()
        self.assertEqual(at.session_state["commits"], [])
        self.assertEqual(at.session_state[ACTIVE_CATALOG_PICK_KEY], PK_ATTYA)

    def test_genuine_selection_after_remount_commits_exactly_once(self) -> None:
        at = self._at()
        self._go(at, "practice")
        self._go(at, "songs")
        at.selectbox(key="matching_song_dropdown").set_value(PK_SAY).run()
        self.assertEqual(at.session_state["commits"], [PK_SAY])
        self.assertEqual(at.session_state[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        for _ in range(2):
            at.checkbox(key="unrelated").check().run()
            at.checkbox(key="unrelated").uncheck().run()
        self._go(at, "practice")
        self._go(at, "songs")
        at.run()
        self.assertEqual(at.session_state["commits"], [PK_SAY])
        self.assertEqual(at.session_state[ACTIVE_CATALOG_PICK_KEY], PK_SAY)
        self.assertEqual(at.selectbox(key="matching_song_dropdown").value, PK_SAY)


if __name__ == "__main__":
    unittest.main()
