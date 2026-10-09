"""R9 — a Mission example's staff must follow the musician-facing chart key.

For a transposing instrument with written charts on, concert E projects to
written C# on alto saxophone. The Practice-Key transposer rebuilt the stored
example's ABC with the *concert* key as its key signature, so after a key change
on Mission Backing the staff read `K:E` while the note names and chord were
spelled in the written C# domain — written pitches on a concert signature. It
also dropped `_projected_display_key`, leaving the artifact with no record of
which domain its display material was in.

The concert copy (`_concert_chord` / `_concert_notes`) stays canonical; only the
player-facing fields move with the chart.
"""

from __future__ import annotations

import pytest

from improvisation_missions import (
    _reproject_mission_example_to_chart,
    _transpose_mission_example_payload,
    parse_abc_k_field,
)

ALTO_WRITTEN = {
    "instrument": "Saxophone",
    "selected_transposing_instrument": "Alto saxophone (Eb)",
    "show_chart_in_instrument_key": True,
}
ALTO_CONCERT = dict(ALTO_WRITTEN, show_chart_in_instrument_key=False)
PIANO = {"instrument": "Piano"}


def _payload(*, concert: str, chart: str, notes: list[str], chord: str, concert_chord: str):
    """Stored example whose display material sits in the ``chart`` domain."""
    return {
        "mission": "Improvise using only chord tones",
        "chord": concert_chord,
        "concert_key": concert,
        "display_key": chart,
        "bpm": 100,
        "abc": f"X:1\nT:Mission — {chord}\nM:4/4\nL:1/4\nK:{chart}\nA B c d|\n",
        "motif": {
            "notes": list(notes),
            "chord": chord,
            "display": " – ".join(notes),
            "_concert_chord": concert_chord,
            "_concert_notes": ["F", "A", "C", "E"],
            "_projected_display_key": chart,
        },
    }


def test_written_chart_staff_follows_the_written_key_not_concert():
    """Alto sax, written charts on: concert F->E must give a C# staff, not E."""
    raw = _payload(
        concert="F", chart="D", notes=["E", "G", "B", "D"], chord="Em7", concert_chord="F#m7"
    )
    out = _transpose_mission_example_payload(
        raw, from_key="F", to_key="E", session_state=dict(ALTO_WRITTEN)
    )
    assert out is not None
    assert out["concert_key"] == "E", "concert identity still follows the Practice Key"
    assert out["display_key"] == "C#", "player-facing domain is the written key"
    assert parse_abc_k_field(out["abc"]) == "C#", "staff key signature must be written"
    assert out["motif"]["_projected_display_key"] == "C#"


def test_concert_charts_keep_the_concert_staff():
    """Same instrument with written charts off: the staff stays at concert E."""
    raw = _payload(
        concert="F", chart="F", notes=["F", "A", "C", "E"], chord="F#m7", concert_chord="F#m7"
    )
    out = _transpose_mission_example_payload(
        raw, from_key="F", to_key="E", session_state=dict(ALTO_CONCERT)
    )
    assert out is not None
    assert out["display_key"] == "E"
    assert parse_abc_k_field(out["abc"]) == "E"
    assert out["motif"]["_projected_display_key"] == "E"


def test_concert_pitch_instrument_is_unaffected():
    raw = _payload(
        concert="F", chart="F", notes=["F", "A", "C", "E"], chord="F#m7", concert_chord="F#m7"
    )
    out = _transpose_mission_example_payload(
        raw, from_key="F", to_key="E", session_state=dict(PIANO)
    )
    assert out is not None
    assert out["display_key"] == "E"
    assert parse_abc_k_field(out["abc"]) == "E"


def test_no_session_falls_back_to_the_concert_key():
    """Callers without a session must not crash and must stay concert-spelled."""
    raw = _payload(
        concert="F", chart="F", notes=["F", "A", "C", "E"], chord="F#m7", concert_chord="F#m7"
    )
    out = _transpose_mission_example_payload(raw, from_key="F", to_key="E", session_state=None)
    assert out is not None
    assert out["display_key"] == "E"
    assert parse_abc_k_field(out["abc"]) == "E"


def test_concert_copy_stays_canonical_across_the_key_change():
    raw = _payload(
        concert="F", chart="D", notes=["E", "G", "B", "D"], chord="Em7", concert_chord="F#m7"
    )
    out = _transpose_mission_example_payload(
        raw, from_key="F", to_key="E", session_state=dict(ALTO_WRITTEN)
    )
    motif = out["motif"]
    # F#m7 down one semitone with the concert key F->E.
    assert motif["_concert_chord"] == "Fm7"
    assert motif["chord"] != motif["_concert_chord"], "written chord differs from concert"
    assert len(motif["notes"]) == len(raw["motif"]["notes"])
    assert len(motif["midi"]) == len(motif["notes"])


@pytest.mark.parametrize(
    "session,expect",
    [(ALTO_WRITTEN, "C#"), (ALTO_CONCERT, "E"), (PIANO, "E")],
)
def test_toggle_only_reprojection_moves_the_staff(session, expect):
    """Toggling written charts moves the chart domain with the key unchanged."""
    raw = _payload(
        concert="E", chart="E", notes=["F#", "A", "C#", "E"], chord="F#m7", concert_chord="F#m7"
    )
    out = _reproject_mission_example_to_chart(raw, dict(session))
    if expect == "E":
        assert out is None, "already in the live chart domain — nothing to redo"
        return
    assert out is not None
    assert out["display_key"] == expect
    assert parse_abc_k_field(out["abc"]) == expect
    assert out["motif"]["_projected_display_key"] == expect
    assert out["concert_key"] == "E", "the concert Practice Key must not move"


def test_reprojection_is_idempotent():
    raw = _payload(
        concert="E", chart="C#", notes=["D#", "F#", "A#", "C#"], chord="D#m7", concert_chord="F#m7"
    )
    assert _reproject_mission_example_to_chart(raw, dict(ALTO_WRITTEN)) is None


# --------------------------------------------------------------------------
# One projection authority: Mission Backing and the Missions tab both refresh
# through mission_projection_state.project_complete_mission_example. Toggling
# written charts must re-key the staff on the spot, on either surface, without
# regenerating the Mission.
# --------------------------------------------------------------------------

ALTO_WRITTEN_SESSION = dict(ALTO_WRITTEN, concert_key="E", display_key="E")
ALTO_CONCERT_SESSION = dict(ALTO_CONCERT, concert_key="E", display_key="E")


def _ipanema_example():
    """Stored Mission example as Mission Backing holds it: concert E, written C#."""
    from improvisation_missions import MissionExample

    return MissionExample(
        mission="Improvise using only chord tones",
        variant="normal",
        chord="F#m7",
        section="Intro",
        song_title="The Girl from Ipanema",
        display_key="C#",
        concert_key="E",
        instrument="Saxophone",
        level="Intermediate",
        focus="Improvisation",
        motif={
            "notes": ["F#", "A#", "C#", "D#"],
            "midi": [66, 70, 73, 75],
            "chord": "D#m7",
            "display": "F# – A# – C# – D#",
            "_concert_chord": "F#m7",
            "_concert_notes": ["A", "C#", "E", "F#"],
            "_projected_display_key": "C#",
            "rhythm": "♩ ♩ ♩ ♩",
        },
        abc="X:1\nT:Mission — D#m7\nM:4/4\nL:1/4\nK:C#\nF A c d|\n",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=None,
        show_tab=False,
        show_piano=False,
    )


def _project(session):
    from mission_projection_state import project_complete_mission_example

    return project_complete_mission_example(
        dict(session), _ipanema_example(), instrument="Saxophone", bpm=100
    )


def test_backing_toggle_reprojects_the_staff_on_the_spot():
    """ON -> OFF -> ON re-keys the staff each time with no visit to Missions."""
    on1 = _project(ALTO_WRITTEN_SESSION)
    off = _project(ALTO_CONCERT_SESSION)
    on2 = _project(ALTO_WRITTEN_SESSION)

    assert parse_abc_k_field(on1.abc) == "C#"
    assert parse_abc_k_field(off.abc) == "E", "concert charts must show a concert staff"
    assert parse_abc_k_field(on2.abc) == "C#", "written charts must come straight back"

    assert list(on1.motif["notes"]) == ["F#", "A#", "C#", "D#"]
    assert list(off.motif["notes"]) == ["A", "C#", "E", "F#"]
    assert list(on2.motif["notes"]) == list(on1.motif["notes"])


def test_backing_toggle_keeps_the_mission_identity_and_idea():
    """The musical idea and its identity survive a display-only reprojection."""
    on1, off, on2 = (
        _project(ALTO_WRITTEN_SESSION),
        _project(ALTO_CONCERT_SESSION),
        _project(ALTO_WRITTEN_SESSION),
    )
    for got in (on1, off, on2):
        assert got.mission == "Improvise using only chord tones"
        assert got.section == "Intro"
        assert got.song_title == "The Girl from Ipanema"
        assert got.concert_key == "E", "the concert Practice Key never moves"
        assert list(got.motif["_concert_notes"]) == ["A", "C#", "E", "F#"]
        assert got.motif["_concert_chord"] == "F#m7"
        assert got.motif.get("rhythm") == "♩ ♩ ♩ ♩", "same rhythm — not a new idea"
    assert on2.motif["display"] == on1.motif["display"]


# --------------------------------------------------------------------------
# MIDI semantics. `motif["midi"]` is NOTATION midi: sync_motif_midi keeps it in
# step with `notes[]`, and its only consumer is build_motif_abc, which turns
# (note, midi) into the staff pitch and octave. Nothing sounds it — the notation
# component renders silently and the synth takes chord symbols — so the written
# display cannot move the sounding concert pitch.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("session", [ALTO_WRITTEN_SESSION, ALTO_CONCERT_SESSION])
def test_display_midi_tracks_the_displayed_note_names(session):
    """Notation midi must agree with the spelling drawn on the staff."""
    from improvisation_motif import _midi_from_note

    motif = _project(session).motif
    notes = list(motif["notes"])
    midi = list(motif["midi"])
    assert len(midi) == len(notes)
    for name, pitch in zip(notes, midi):
        assert int(pitch) % 12 == _midi_from_note(str(name), 4) % 12


def test_written_display_does_not_move_the_sounding_pitch():
    """The concert copy is identical in both display modes."""
    on = _project(ALTO_WRITTEN_SESSION).motif
    off = _project(ALTO_CONCERT_SESSION).motif
    assert list(on["_concert_notes"]) == list(off["_concert_notes"])
    assert on["_concert_chord"] == off["_concert_chord"]
    # The written staff really is a different spelling, not a no-op.
    assert list(on["notes"]) != list(off["notes"])


def test_mission_notation_component_has_no_audio_playback():
    """Guard the semantics: if the staff ever gains a synth, notation midi
    would start sounding and would have to carry concert pitch instead."""
    import inspect

    from improvisation_intelligence_ui import _render_abc

    src = inspect.getsource(_render_abc)
    assert "renderAbc" in src
    for audio_api in ("CreateSynth", "midiBuffer", "AudioContext", "synthController"):
        assert audio_api not in src, f"{audio_api} would make notation midi audible"


def test_backing_synth_is_independent_of_mission_motifs():
    """The sounding path takes chord symbols and never imports motif/mission code."""
    import inspect

    import backing_audio

    src = inspect.getsource(backing_audio)
    assert "improvisation_motif" not in src
    assert "improvisation_missions" not in src
    assert "chords" in inspect.signature(backing_audio.synthesize_chords_to_numpy).parameters
