"""A song's own Backing never borrows a Creative jam's Mood / Groove intensity (browser check C2, 2026-11-25).

Found in the real app: a Composition song's take rendered Mellow / Medium on the first visit and Dark / Auto after a
reload, because the profile read Style Jam's and the Generator's controls from the session (``improv_mood``,
``improv_jam_mood``, ``improv_groove``, ``improv_style_meta``), and the reload restored another jam's values. The
same song then played a different take (a new audio file) after every reload.
"""

from __future__ import annotations

import pytest

from backing_context import BackingContext, set_backing_context
from backing_musical_profile import SONG_SOURCES, resolve_backing_musical_profile_from_session


def _ctx(source: str, **kw) -> BackingContext:
    base = dict(source=source, source_label="x", active_song_id="song-1", song_title="Jazz tune", key="D", display_key="D",
                concert_key="D", bpm=100, style="Jazz swing", groove="Jazz swing")
    base.update(kw)
    return BackingContext(**base)


def _session(ctx: BackingContext, **jam) -> dict:
    s: dict = {}
    set_backing_context(s, ctx)
    s.update(jam)
    return s


JAMS = (
    {"improv_mood": "Mellow", "improv_groove": "Medium"},  # Style Jam's controls (the first visit)
    {"improv_jam_mood": "Dark", "improv_style_meta": {"groove_intensity": "Auto"}},  # the Generator's (after the reload)
    {"improv_mood": "Energetic", "improv_groove": "Heavy", "improv_feel": "Straight"},
    {},
)


@pytest.mark.parametrize("source", sorted(SONG_SOURCES))
def test_a_songs_take_does_not_change_with_the_jams_controls(source):
    profiles = {resolve_backing_musical_profile_from_session(_session(_ctx(source), **jam), style="Jazz swing", tempo=100, key="D")
                for jam in JAMS}
    assert len(profiles) == 1
    (p,) = profiles
    assert (p.mood, p.intensity) == ("Mellow", "Medium")  # the profile's own defaults


def test_a_songs_own_context_mood_is_still_used():
    s = _session(_ctx("composition_song", mood="Dreamy", groove_intensity="Light"), improv_jam_mood="Dark")
    p = resolve_backing_musical_profile_from_session(s, style="Jazz swing", tempo=100, key="D")
    assert (p.mood, p.intensity) == ("Dreamy", "Light")


def test_a_jam_still_plays_its_own_controls():
    # A Creative jam's Backing (no mood in its context) keeps reading the jam's controls, as before.
    s = _session(_ctx("entry_jam", entry_mode="Style Jam Mode"), improv_mood="Energetic", improv_groove="Heavy")
    p = resolve_backing_musical_profile_from_session(s, style="Jazz swing", tempo=100, key="D")
    assert (p.mood, p.intensity) == ("Energetic", "Heavy")
