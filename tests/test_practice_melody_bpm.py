"""The Practice Melody follows the BPM being practised, without becoming a different melody (user, 2026-11-11).

Reported on "I'll Remember April" in E: the Backing BPM went to 148 and the Lead Sheet said 148, but the Practice
Melody's heading and its staff tempo still said the 160 it was generated at. A tempo change re-times the stored
melody in place (as a key change transposes it): the heading, the ABC ``Q:`` marking and therefore the notation's
audio preview follow, and every note, rest and rhythm stays exactly the same.
"""
from __future__ import annotations

from pathlib import Path

from practice_melody_generator import generate_practice_melody
from practice_melody_notation import practice_melody_full_song_abc
from practice_melody_transpose import retime_practice_melody

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _melody(bpm=160.0):
    return generate_practice_melody(
        song_id="catalog::april", song_title="I'll Remember April", sections={"A": ["Emaj7", "Emaj7", "Em7", "A7"]},
        key_center="E", level="Intermediate", tempo_bpm=bpm,
    )


def _notes(m):
    return [(s.section_id, [(e.pitch, e.midi, e.duration_beats, e.is_rest, e.measure, e.beat) for e in s.events]) for s in m.sections]


def test_retime_changes_only_the_tempo() -> None:
    m = _melody()
    r = retime_practice_melody(m, bpm=148)
    assert r.tempo_bpm == 148
    assert _notes(r) == _notes(m)
    assert (r.key_center, r.level, r.seed, r.alt_index, r.melody_id) == (m.key_center, m.level, m.seed, m.alt_index, m.melody_id)


def test_the_staff_tempo_follows() -> None:
    m = _melody()
    assert "Q:1/4=160" in practice_melody_full_song_abc(m).replace(" ", "")
    abc = practice_melody_full_song_abc(retime_practice_melody(m, bpm=148)).replace(" ", "")
    assert "Q:1/4=148" in abc and "Q:1/4=160" not in abc


def test_no_op_when_there_is_nothing_to_change() -> None:
    m = _melody()
    for bpm in (None, 0, -5, "x", 160, 160.0):
        assert retime_practice_melody(m, bpm=bpm) is m


def test_both_panels_show_the_retimed_melody() -> None:
    practice = APP[APP.index("_pm_melody = _pm_resolve()"):][:400]
    assert "retime_practice_melody(_pm_melody, bpm=_practice_bpm)" in practice
    backing = APP[APP.index("_pmb_melody = consume_pending_practice_melody_handoff("):][:1400]
    assert 'retime_practice_melody(_pmb_melody, bpm=st.session_state.get("backing_track_bpm"))' in backing
    # The heading reads the re-timed melody.
    assert APP.count("_melody.tempo_bpm:g} BPM") >= 2
