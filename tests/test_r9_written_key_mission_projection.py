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
