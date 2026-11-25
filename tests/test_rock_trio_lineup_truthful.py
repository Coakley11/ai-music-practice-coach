"""A Rock trio whose recorded guitar is unavailable keeps its piano fallback (compatibility), and every line-up says so.

The fallback itself is unchanged: without a guitar renderer the piano plays the guitar's part rather than leaving a
bass-and-drums duo. What changed is that neither the Generator card nor the Backing card shows that band as if it
were a piano trio the musician chose.
"""

from __future__ import annotations

import re

import backing_performance_plan as pp
import jam_card_art as ja


def _plan(guitar: bool):
    return pp.resolve_performance_plan(style="Rock groove", ensemble="Rock trio", guitar_available=guitar)


def test_the_fallback_itself_is_unchanged():
    off = _plan(False)
    assert off.roles[:1] == ("keys",) and not off.plays("guitar") and "guitar" in off.unavailable
    assert pp.keys_stand_in_for_guitar(off) and off.fallbacks == (pp.KEYS_FOR_GUITAR,)
    on = _plan(True)
    assert on.plays("guitar") and not on.plays("keys") and not pp.keys_stand_in_for_guitar(on)


def test_the_backing_card_says_the_piano_plays_the_guitars_part():
    assert pp.band_summary(_plan(False)) == "Piano (playing the guitar's part), bass, drums · recorded guitar not available"
    assert pp.band_summary(_plan(True)) == "Guitar, bass, drums"


def test_other_bands_read_as_before():
    assert pp.band_summary(pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz trio")) == "Piano, bass, drums"
    style_jam = pp.resolve_performance_plan(style="Rock groove", guitar_available=False)  # Style Jam's own band
    assert not pp.keys_stand_in_for_guitar(style_jam) and "playing the guitar" not in pp.band_summary(style_jam)


def test_the_generator_card_names_the_stand_in(monkeypatch):
    real = pp.resolve_performance_plan
    monkeypatch.setattr(pp, "resolve_performance_plan", lambda **k: real(**k, guitar_available=False))
    playing, later = ja.ensemble_lineup("Rock trio", "Rock")
    assert [n for _, n in playing] == [ja.STAND_IN_PIANO, "Bass", "Drums"]
    assert [n for _, n in later] == ["Electric guitar"]  # still named as not playing
    text = re.sub("<[^>]+>", " ", ja.lineup_html("Rock trio", "Rock"))
    assert "the piano plays the guitar's part" in text and "Not in the backing yet" not in text
    monkeypatch.setattr(pp, "resolve_performance_plan", lambda **k: real(**k, guitar_available=True))
    playing, later = ja.ensemble_lineup("Rock trio", "Rock")
    assert [n for _, n in playing] == ["Electric guitar", "Bass", "Drums"]
    assert "guitar's part" not in ja.lineup_html("Rock trio", "Rock")
