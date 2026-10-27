"""Song-Aware Coaching S3 — Custom and Composition sources in the real app.

One booted studio: Catalog (Perfect) → Custom progression → a generated Style Jam → back to
coaching → Composition → back to Catalog. At every step coaching must show the global owner's
own chords at the live Practice Key, never another source's or the Jam's, and never another
song's plan. A refresh must not reactivate a different source.

**Empty Composition (documented blocker).** The real Composition source always installs the
user's "My Composition" with a starter progression (``composition_songs_bridge``), and emptying
it needs the multi-step Composition Studio editor, so an empty active Composition is not
reachable here. ``test_empty_composition_...`` therefore reproduces the baseline at integration
level with the real Creative page resolver: it shows the existing page-level fallback handing
the previous song's chords to an empty Composition, and coaching failing closed on it.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
from types import SimpleNamespace

import pytest

from music_theory import transpose_sections_dict

TAB = "Song-Aware Coaching"
TRIAL = {
    "id": "trial-rev-1", "name": "Trial Song", "original_key_center": "E", "time_signature": "4/4", "bpm": 92,
    "original_sections": {
        "Verse": [{"chord": "E", "bars": 2}, {"chord": "C#m7", "bars": 1}, {"chord": "A", "bars": 1}],
        "Chorus": [{"chord": "A", "bars": 1}, {"chord": "B7", "bars": 1}, {"chord": "E", "bars": 2}],
    },
}
TRIAL_BARS_IN_E = {"Verse": ["E", "E", "C#m7", "A"], "Chorus": ["A", "B7", "E", "E"]}


def require_isolated_data_dir(data_dir: str) -> None:
    """The app fixes its data folder when ``suite_workspace`` is first imported. If an earlier
    test in this process imported it, this app would run against the worktree's own data
    folder instead of ``data_dir`` — so the module must run in its own pytest process."""
    import pathlib
    import sys

    mod = sys.modules.get("suite_workspace")
    if mod is not None and pathlib.Path(mod.DATA_DIR).resolve() != pathlib.Path(data_dir).resolve():
        pytest.skip("run this real-app module in its own pytest process: the app's data folder was "
                    "already fixed by an earlier import, so isolation to a temp folder cannot be guaranteed")


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest

    data_dir = tempfile.mkdtemp(prefix="song_coach_sources_")
    prior = os.environ.get("MUSIC_APP_DATA_DIR")
    os.environ["MUSIC_APP_DATA_DIR"] = data_dir
    try:
        require_isolated_data_dir(data_dir)
        at = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
        at.run(timeout=300)
        _click(at, "studio_quick_nav_btn_picker")
        _pick_song(at, "Perfect")
        _open(at)
        _click(at, "song_coach_build")  # a Catalog plan that must never follow us to other sources
        yield at
    finally:
        if prior is None:
            os.environ.pop("MUSIC_APP_DATA_DIR", None)
        else:
            os.environ["MUSIC_APP_DATA_DIR"] = prior
        shutil.rmtree(data_dir, ignore_errors=True)


def _button(at, key):
    return next((w for w in at.button if str(w.key) == key), None)


def _click(at, key):
    _button(at, key).click()
    at.run(timeout=300)


def _pick_song(at, prefix):
    dropdown = at.selectbox(key="matching_song_dropdown")
    dropdown.set_value([o for o in dropdown.options if o.startswith(prefix)][0])
    at.run(timeout=300)


def _source(at, needle):
    if at.session_state["studio_page"] != "picker":
        _click(at, "studio_quick_nav_btn_picker")
    radio = at.radio(key="song_picker_active_source")
    radio.set_value([o for o in radio.options if needle in o][0])
    at.run(timeout=300)


def _open(at, needle=TAB):
    if at.session_state["studio_page"] != "creative":
        _click(at, "studio_quick_nav_btn_creative")
    try:
        at.selectbox(key="creative_lab_analysis_mode").set_value("Improvisation Intelligence")
        at.run(timeout=300)
    except Exception:
        pass
    options = at.radio(key="improv_intelligence_tab").options
    at.radio(key="improv_intelligence_tab").set_value([o for o in options if needle in o][0])
    at.run(timeout=300)


def _ctx(at) -> dict:
    return at.session_state["_song_coach_ctx_diag"]


def _sections(at) -> dict:
    return {name: list(bars) for name, bars in _ctx(at)["sections"]}


def _state(at):
    return at.session_state["song_coach_session"] if "song_coach_session" in at.session_state else None


def _header(at) -> str:
    return next((m.value for m in at.markdown if "data-song-coach-concert-key" in m.value), "")


def _plan_shown(at) -> bool:
    return any(m.value.startswith("#### Your plan") for m in at.markdown)


def _no_exception(at):
    assert not at.exception, [str(getattr(e, "value", e))[:800] for e in at.exception]


def test_custom_progression_coaches_its_own_chords_at_the_live_practice_key(app):
    at = app
    catalog_state = _state(at)
    perfect = _sections(at)
    at.session_state["cpl_active_progression"] = copy.deepcopy(TRIAL)  # a saved Custom progression
    _source(at, "Custom")
    _open(at)
    _no_exception(at)
    assert at.session_state["active_music_source"] == "custom_progression"
    ctx = _ctx(at)
    assert ctx["identity"] == "custom|custom::trial-rev-1" and ctx["reason"] == ""
    assert ctx["concert_key"] == at.session_state["concert_key"], "coaching key must be the live Practice Key"
    assert _sections(at) == transpose_sections_dict(TRIAL_BARS_IN_E, "E", ctx["concert_key"])
    assert _sections(at) != perfect
    header = _header(at)
    assert "Trial Song" in header and "Custom progression" in header and "Your own progression" in header
    assert any("for a different song" in i.value for i in at.info) and not _plan_shown(at)
    assert _state(at) == catalog_state, "visiting must not rewrite the stored Catalog plan"
    _click(at, "song_coach_build")
    assert "custom::trial-rev-1" in _state(at)["identity"] and _plan_shown(at)


def test_refresh_keeps_the_custom_source(app):
    from streamlit.testing.v1 import AppTest

    at = app
    saved = _state(at)
    fresh = AppTest.from_file("streamlit_music_practice_app.py", default_timeout=300)
    fresh.run(timeout=300)
    _no_exception(fresh)
    assert fresh.session_state["active_music_source"] == "custom_progression"
    assert fresh.session_state["improv_intelligence_tab"] == TAB
    assert _ctx(fresh)["identity"] == "custom|custom::trial-rev-1"
    assert _state(fresh)["plan_id"] == saved["plan_id"] and _plan_shown(fresh)


def test_a_generated_style_jam_never_reaches_coaching(app):
    at = app
    before, plan_id = _sections(at), _state(at)["plan_id"]
    _open(at, "Entry & Jam")
    entry = at.radio(key="improv_entry_mode")
    entry.set_value([o for o in entry.options if "Style Jam" in o][0])
    at.run(timeout=300)
    _click(at, "improv_gen_style")
    jam = at.session_state["improv_generated_sections"]
    assert jam, "a Jam progression exists"
    _open(at)
    _no_exception(at)
    assert _sections(at) == before
    assert not any("(" in name for name in _sections(at)), "Jam section names must not appear"
    assert _state(at)["plan_id"] == plan_id and _plan_shown(at)


def test_composition_coaches_the_active_documents_own_progression(app):
    from song_coach_context import composition_reference_chart

    at = app
    custom_state = _state(at)
    _source(at, "Composition")
    _open(at)
    _no_exception(at)
    assert at.session_state["active_music_source"] == "composition_song"
    doc = at.session_state["composer_active_document"]
    reference, home_key, _record = composition_reference_chart(doc)
    ctx = _ctx(at)
    assert ctx["identity"] == f"composition|composition::{doc['id']}" and ctx["reason"] == ""
    assert _sections(at) == transpose_sections_dict(reference, home_key, ctx["concert_key"])
    assert "Composition" in _header(at)
    assert any("for a different song" in i.value for i in at.info) and not _plan_shown(at)
    assert _state(at) == custom_state


def test_back_to_catalog_shows_the_catalog_song_only(app):
    from song_catalog.catalog import curated_song_records

    at = app
    _source(at, "catalog")
    _pick_song(at, "Perfect")
    _open(at)
    _no_exception(at)
    assert at.session_state["active_music_source"] == "catalog_song"
    ctx = _ctx(at)
    assert ctx["identity"].startswith("catalog|") and "Perfect" in ctx["identity"]
    record = next(r for r in curated_song_records() if r["title"] == "Perfect")
    assert _sections(at) == transpose_sections_dict(record["sections"], record["key"], ctx["concert_key"])
    assert "Verified chord chart" in _header(at)
    assert not _plan_shown(at), "the Custom plan must not appear under the Catalog song"


def test_empty_composition_fails_closed_instead_of_borrowing_the_previous_songs_chords():
    """Baseline reproduction (see module docstring): the real Creative page resolver falls back to
    the previous Catalog song's ``home_sections`` for an empty Composition; coaching refuses it."""
    from composition_document import new_composition_document
    from improvisation_intelligence_ui import _authoritative_concert_sections
    from song_catalog.catalog import curated_song_records
    from song_coach_context import REASON_NO_CHORDS, SOURCE_COMPOSITION
    from song_coach_ui import creative_coach_context

    perfect = next(r for r in curated_song_records() if r["title"] == "Perfect")
    doc = new_composition_document(title="My Composition")
    doc["global"]["original_key_center"] = "C"
    session = {
        "active_catalog_pick_key": f"composition::{doc['id']}",
        "active_music_source": "composition_song",
        "composer_active_document": doc,
        "home_sections": copy.deepcopy(perfect["sections"]),  # left behind by the previous Catalog song
        "display_key": "C",
        "concert_key": "C",
    }
    page_sections = _authoritative_concert_sections(session, {})
    assert page_sections == perfect["sections"], "baseline: the page resolver hands over Perfect's chords"
    improv = SimpleNamespace(key_center="C", display_key="C", instrument="Piano", sections=page_sections,
                             section_order=list(page_sections), song_title="My Composition", artist="", bpm=100)
    ctx = creative_coach_context(session, improv)
    assert (ctx.available, ctx.reason, ctx.source_kind) == (False, REASON_NO_CHORDS, SOURCE_COMPOSITION)
    assert ctx.sections == ()
