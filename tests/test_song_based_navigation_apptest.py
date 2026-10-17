"""Manual navigation to Song-Based Improvisation (characterization) — the real app.

Pins what choosing Entry & Jam and then Song-Based Improvisation by hand does today, so the
shared helper (``creative_sbi_navigation``) can be adopted by the entry-mode radio without a
behaviour change: the tab and entry mode, the full-song scope reset, navigation history and
Back, the source lane, and that Practice Key / instrument / Backing transport are untouched.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from tests.test_song_coach_apptest import _no_exception, _open, require_isolated_data_dir


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="sbi_nav_apptest_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        require_isolated_data_dir(data_dir)
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
        at.run(timeout=300)
        btn = next(b for b in at.button if str(b.key) == "studio_quick_nav_btn_picker")
        btn.click()
        at.run(timeout=300)
        dropdown = at.selectbox(key="matching_song_dropdown")
        dropdown.set_value([o for o in dropdown.options if o.startswith("Perfect")][0])
        at.run(timeout=300)
        _open(at)
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _get(at, key, default=None):
    return at.session_state[key] if key in at.session_state else default


def _back_destinations(at) -> list[str]:
    from studio_nav_history import NAV_BACK_STACK, history_destination_id

    return [history_destination_id(entry=e) for e in (_get(at, NAV_BACK_STACK) or [])]


def _globals(at) -> dict:
    return {k: _get(at, k) for k in ("concert_key", "display_key", "instrument", "active_music_source",
                                     "active_catalog_pick_key", "backing_transport_status", "_backing_autoplay")}


def test_manual_entry_jam_then_song_based(app):
    at = app
    assert _get(at, "improv_intelligence_tab") == "Song-Aware Coaching"
    before = _globals(at)
    at.radio(key="improv_intelligence_tab").set_value("Entry & Jam")
    at.run(timeout=300)
    _no_exception(at)
    entry = at.radio(key="improv_entry_mode")
    entry.set_value([o for o in entry.options if "Style Jam" in o][0])
    at.run(timeout=300)
    at.radio(key="improv_entry_mode").set_value("Song-Based Improvisation")
    at.run(timeout=300)
    _no_exception(at)
    assert _get(at, "improv_intelligence_tab") == "Entry & Jam"
    assert _get(at, "creative_improv_intelligence_tab") == "Entry & Jam"
    assert _get(at, "improv_entry_mode") == "Song-Based Improvisation"
    assert _get(at, "backing_track_scope") == "Full song", "Song-Based entry resets to the full song"
    assert _get(at, "_song_improv_scope_last_reset_source") in ("entry_mode_song_based", "song_improv_entry_hydrate")
    assert _get(at, "_history_live_creative_dest") == "creative::SBI"
    back = _back_destinations(at)
    assert back[-3:] == ["creative::Song-Aware Coaching", "creative::SBI", "creative::Entry Mode"], back
    assert _get(at, "improv_song_source") == "Active song"
    after = _globals(at)
    assert after == before, "manual navigation changes no key, instrument, source or transport"


def _back(at):
    btn = next(b for b in at.button if str(b.key) == "studio_nav_back_btn")
    assert not btn.disabled
    btn.click()
    at.run(timeout=300)


def test_back_after_the_manual_steps(app):
    """Today: one Back from the two-click path pops one step and stays on Entry & Jam in
    Song-Based mode (the shared history keeps the live Song-Based workspace)."""
    at = app
    depth = len(_back_destinations(at))
    _back(at)
    _no_exception(at)
    assert len(_back_destinations(at)) == depth - 1
    assert _get(at, "improv_intelligence_tab") == "Entry & Jam"
    assert _get(at, "improv_entry_mode") == "Song-Based Improvisation"
