"""A jam's Practice Melody is composed from that jam: its chords, concert key and identity, never another song's.

Dev review 2026-11-25: an Entry & Style Jam in concert C showed a Practice Melody in E minor, because only the
title followed the jam.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from music_theory import transpose_sections_dict
from practice_melody_backing import (
    begin_practice_melody_backing_handoff,
    consume_pending_practice_melody_handoff,
    resolve_active_backing_practice_melody,
)
from practice_melody_model import validate_practice_melody
from practice_melody_session import resolve_practice_melody
from practice_melody_source import jam_melody_source

POP_C = {"Verse (Pop)": ["C", "Am", "F", "G"], "Chorus (Pop)": ["F", "G", "C", "Am"]}
JAZZ_D = {"Head (Jazz Swing)": ["Em7", "A7", "Dmaj7", "B7"], "Bridge (Jazz Swing)": ["Gm7", "C7", "F#m7", "B7"]}


def _ctx(entry: str, sections: dict, key: str, made_in: str = "", **kw):
    base = dict(
        source="entry_jam",
        entry_mode=entry,
        concert_key=key,
        key=key,
        style="Pop" if sections is POP_C else "Jazz Swing",
        ensemble="" if entry == "Style Jam Mode" else "Jazz trio",
        difficulty="Intermediate",
        progression=[c for chs in sections.values() for c in chs],
        sealed_jam_snapshot={"section_map": sections, "practice_tonic": made_in or key, "practice_mode": "major"},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _compose(src, session=None, instrument="Guitar"):
    return resolve_practice_melody(
        {} if session is None else session,
        song_identity=src.identity,
        song_id_for_generation=src.identity,
        song_title=src.title,
        sections=src.sections,
        section_order=list(src.sections),
        key_center=src.concert_key,
        level=src.level,
        tempo_bpm=112,
        style=src.style,
        instrument=instrument,
    )


def _chords(melody):
    return [c for s in melody.sections for c in s.chords]


def test_style_jam_in_c_gets_its_own_c_major_melody():
    src = jam_melody_source(_ctx("Style Jam Mode", POP_C, "C"), SimpleNamespace(practice_concert_key="C", chart_display_key="C"))
    melody = _compose(src)
    assert src.title == melody.song_title == "Entry Style Jam"
    assert melody.key_center == "C" and _chords(melody) == [c for chs in POP_C.values() for c in chs]
    assert validate_practice_melody(melody) == []


def test_generator_in_d_gets_its_own_jazz_melody():
    src = jam_melody_source(_ctx("Jam Session Generator", JAZZ_D, "D"))
    melody = _compose(src)
    assert melody.song_title == "Jam Session Generator" and melody.key_center == "D" and melody.style == "Jazz Swing"
    assert _chords(melody) == [c for chs in JAZZ_D.values() for c in chs]


@pytest.mark.parametrize("source", ["regular_song", "composition_song", "custom_progression", "mission", "song_improv"])
def test_a_song_is_not_a_jam(source):
    assert jam_melody_source(SimpleNamespace(source=source, entry_mode="Style Jam Mode")) is None


def test_no_progression_means_no_melody_never_another_songs():
    src = jam_melody_source(_ctx("Style Jam Mode", {}, "C", progression=[]))
    assert src is not None and src.sections == {} and src.identity.startswith("jam::style_jam")
    session = {"practice_melody_result": "a song's melody"}
    assert _compose(src, session) is None and "practice_melody_result" not in session


def test_a_key_change_keeps_the_jams_identity_and_follows_its_key():
    in_c = jam_melody_source(_ctx("Style Jam Mode", POP_C, "C"))
    # Practice Key moved to D: the sealed sections may still be in C, or already in D.
    moved = jam_melody_source(_ctx("Style Jam Mode", POP_C, "D", made_in="C"))
    in_d = transpose_sections_dict(POP_C, "C", "D")
    rebuilt = jam_melody_source(_ctx("Style Jam Mode", in_d, "D", style="Pop"))
    assert moved.sections == {k: list(v) for k, v in in_d.items()} == rebuilt.sections
    assert in_c.identity == moved.identity == rebuilt.identity


def test_different_jams_have_their_own_identity():
    ids = {
        jam_melody_source(_ctx("Style Jam Mode", POP_C, "C")).identity,
        jam_melody_source(_ctx("Jam Session Generator", POP_C, "C")).identity,
        jam_melody_source(_ctx("Jam Session Generator", JAZZ_D, "D")).identity,
        jam_melody_source(_ctx("Jam Session Generator", JAZZ_D, "D", ensemble="Jazz quartet")).identity,
    }
    assert len(ids) == 4


def test_a_catalog_melody_never_stays_on_a_jam():
    song = _compose(SimpleNamespace(identity="pk::Pop::Perfect", title="Perfect", sections={"Verse": ["Em7", "C"]},
                                    concert_key="Em", level="Intermediate", style="Pop"))
    session = {}
    begin_practice_melody_backing_handoff(session, melody=song, song_identity="pk::Pop::Perfect")
    assert consume_pending_practice_melody_handoff(session, current_song_identity="pk::Pop::Perfect", current_key_center="Em")
    jam = jam_melody_source(_ctx("Style Jam Mode", POP_C, "C"))
    assert resolve_active_backing_practice_melody(session, current_song_identity=jam.identity, current_key_center="C") is None


@pytest.mark.parametrize("lap", [
    ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb", "B", "E", "A", "D", "G"],
    ["C", "G", "D", "A", "E", "B", "Gb", "Db", "Ab", "Eb", "Bb", "F"],
    ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"],
])
def test_key_cycling_laps_transpose_without_drifting_away(lap):
    src = jam_melody_source(_ctx("Style Jam Mode", POP_C, "C"))
    melody = _compose(src)
    session = {}
    begin_practice_melody_backing_handoff(session, melody=melody, song_identity=src.identity)
    consume_pending_practice_melody_handoff(session, current_song_identity=src.identity, current_key_center="C")
    notes = [e.midi for s in melody.sections for e in s.events if not e.is_rest]
    for _ in range(3):
        for key in lap:
            now = resolve_active_backing_practice_melody(session, current_song_identity=src.identity, current_key_center=key)
            got = [e.midi for s in now.sections for e in s.events if not e.is_rest]
            steps = {a - b for a, b in zip(got, notes)}
            assert now.key_center == key and len(steps) == 1 and abs(steps.pop()) <= 6
            assert now.melody_id == melody.melody_id
    back = resolve_active_backing_practice_melody(session, current_song_identity=src.identity, current_key_center="C")
    assert back == melody
