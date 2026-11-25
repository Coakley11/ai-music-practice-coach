"""Backing's Practice Key control for a jam is a view of that jam's own concert key.

Dev review 2026-11-25: a Generator jam made in concert E (tenor sax, written F#) showed F# in the Practice Key
control and "Concert Key: F#, Written Key: G#" in the sidebar; another, made in D, turned into F#. The control
is one widget for every jam of its kind and is saved with the page: the value of an earlier jam won over the
current jam's key and was written into the concert key.
"""

from __future__ import annotations

import pytest

import backing_practice_key_control as control

STYLE, GENERATOR = "Entry & Style Jam", "Jam Session Generator"
WIDGET = {STYLE: control.WIDGET_STYLE_JAM, GENERATOR: control.WIDGET_JAM_GENERATOR}
OPTIONS = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def _jam_on_backing(entry: str, key: str, leftover: str, **extra) -> dict:
    style = entry == STYLE
    return {
        "studio_page": "backing",
        "improv_entry_mode": entry,
        "improv_style_key" if style else "improv_jam_key": key,
        "practice_key_by_source": {f"creative::{'entry_style_jam' if style else 'jam_session_generator'}": key},
        "backing_context": {"source": "entry_jam", "entry_mode": entry, "key": key, "concert_key": key},
        "_backing_pk_control_owner": control.OWNER_STYLE_JAM if style else control.OWNER_JAM_GENERATOR,
        WIDGET[entry]: leftover,
        **extra,
    }


@pytest.mark.parametrize("entry", [STYLE, GENERATOR])
@pytest.mark.parametrize("key", ["C", "D", "E", "F#"])
@pytest.mark.parametrize("leftover", ["", "F#", "G#", "Em", "C", "G"])
def test_an_earlier_jams_key_never_becomes_this_jams(entry, key, leftover):
    extra = {"improv_jam_key": "B"} if entry == STYLE else {}  # the Generator's own key is not Style Jam's
    s = _jam_on_backing(entry, key, leftover, **extra)
    assert control.seed_backing_practice_key_widget(s, options=list(OPTIONS)) == key
    assert s[WIDGET[entry]] == key and s["concert_key"] == key and s["display_key"] == key


def test_a_stale_commit_token_does_not_bring_the_old_key_back():
    s = _jam_on_backing(GENERATOR, "E", "F#", _pk_user_commit_token="F#")
    assert control.seed_backing_practice_key_widget(s, options=list(OPTIONS)) == "E"


def test_seeding_is_stable_over_reruns():
    s = _jam_on_backing(GENERATOR, "D", "F#")
    assert [control.seed_backing_practice_key_widget(s, options=list(OPTIONS)) for _ in range(3)] == ["D"] * 3


def test_guitar_sounding_key_is_the_jam_on_screen_not_the_other_jam():
    import guitar_capo

    both = {
        "improv_style_key": "C",
        "improv_jam_key": "F#",
        "practice_key_by_source": {"creative::entry_style_jam": "C", "creative::jam_session_generator": "F#"},
    }
    for entry, want in (("Style Jam Mode", "C"), ("Jam Session Generator", "F#")):
        ctx = {"source": "entry_jam", "entry_mode": entry, "key": want, "concert_key": want}
        backing = {**both, "studio_page": "backing", "improv_entry_mode": entry, "backing_context": ctx}
        assert guitar_capo.owner_guitar_concert_key(backing, fallback="E") == want
        creative = {**both, "studio_page": "creative", "improv_entry_mode": entry, "improv_intelligence_tab": "Entry & Jam"}
        assert guitar_capo.owner_guitar_concert_key(creative, fallback="E") == want


def test_an_active_composition_does_not_own_the_sounding_key_of_a_jam_on_backing(monkeypatch):
    import guitar_capo
    import songs.music_source as ms

    monkeypatch.setattr(ms, "composition_song_is_active", lambda *_a, **_k: True)
    s = {
        "studio_page": "backing",
        "improv_entry_mode": "Style Jam Mode",
        "improv_style_key": "C",
        "practice_key_by_source": {"creative::entry_style_jam": "C"},
        "active_catalog_pick_key": "composition::abc",
        "backing_context": {"source": "entry_jam", "entry_mode": "Style Jam Mode", "key": "C", "concert_key": "C"},
    }
    assert guitar_capo.live_capo_shape_source_id(s).startswith("generated::jam")
    assert guitar_capo.live_capo_shape_source_id({**s, "studio_page": "practice"}) == "composition::abc"
