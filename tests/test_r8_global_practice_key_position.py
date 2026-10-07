"""R8 — a global Practice Key change must keep the chord POSITION, not the spelling.

Every chord seal (Mission snapshot, click authority) records the Practice Key it
was written in. The Mission-owned key widget re-keys those seals itself via
``apply_specialized_mission_practice_key``, but the global sidebar key widget
(Live Coach / Harmony Map / Phrase-Motif, and any catalog-owned key edit) does
not. The resolver therefore has to honor the stamp it was given.

"All of Me" A section in C is ``Cmaj7 E7 A7 Dm7 E7 Am7 D7 G7``; in D it is
``Dmaj7 F#7 B7 Em7 F#7 Bm7 E7 A7``. A7 sits at index 2 in C and at index 7 in D,
so trusting the stale spelling silently moves the selection to an unrelated
chord. These tests are spelled out over several keys and chords so nothing can
pass by special-casing one symbol.
"""

from __future__ import annotations

import pytest

from creative_chord_selection_authority import (
    MISSION_CHORD_SNAPSHOT_KEY,
    resolve_authoritative_chord_selection,
)

A_SECTION_C = ["Cmaj7", "E7", "A7", "Dm7", "E7", "Am7", "D7", "G7"]
A_SECTION_D = ["Dmaj7", "F#7", "B7", "Em7", "F#7", "Bm7", "E7", "A7"]
A_SECTION_F = ["Fmaj7", "A7", "D7", "Gm7", "A7", "Dm7", "G7", "C7"]
A_SECTION_EB = ["Ebmaj7", "G7", "C7", "Fm7", "G7", "Cm7", "F7", "Bb7"]


def _map(chords: list[str]) -> list[tuple[str, list[str]]]:
    return [("A", list(chords))]


def _session(*, sealed_chord: str, sealed_index: int, sealed_key: str, live_key: str) -> dict:
    """Session holding one sealed selection plus a live Practice Key."""
    return {
        "studio_page": "creative",
        "active_catalog_pick_key": "all-of-me-jazz-standard",
        "concert_key": live_key,
        "display_key": live_key,
        "ii_selected_chord": sealed_chord,
        "ii_selected_section": "A",
        "ii_selected_chord_index": sealed_index,
        MISSION_CHORD_SNAPSHOT_KEY: {
            "mission_id": "",
            "session_id": "",
            "source_identity": "all-of-me-jazz-standard",
            "section": "A",
            "chord_index": sealed_index,
            "concert_chord": sealed_chord,
            "concert_practice_key": sealed_key,
        },
    }


@pytest.mark.parametrize(
    "sealed_chord,sealed_index,sealed_key,live_key,new_map,expected",
    [
        # GPK1/2/3 — the reported defect: A7 at index 2 in C must become B7 at
        # index 2 in D, not the A7 that now sits at index 7.
        ("A7", 2, "C", "D", A_SECTION_D, ("B7", "A", 2)),
        # GPK5 — a non-adjacent key keeps the same slot.
        ("A7", 2, "C", "F", A_SECTION_F, ("D7", "A", 2)),
        # GPK10 — flat keys too.
        ("A7", 2, "C", "Eb", A_SECTION_EB, ("C7", "A", 2)),
        # GPK7 — a different chord proves nothing is special-cased to A7.
        ("Am7", 5, "C", "D", A_SECTION_D, ("Bm7", "A", 5)),
        # GPK8 — the old spelling is absent from the new map entirely.
        ("Cmaj7", 0, "C", "D", A_SECTION_D, ("Dmaj7", "A", 0)),
        # GPK9 — index 7, the slot the stale A7 used to steal.
        ("G7", 7, "C", "D", A_SECTION_D, ("A7", "A", 7)),
        # The defect only bites when the stale spelling ALSO exists somewhere in
        # the new key, which is what made it look A7-specific. E7 sits at 1 and 4
        # in C and at 6 in D, so both duplicate slots must stay put.
        ("E7", 1, "C", "D", A_SECTION_D, ("F#7", "A", 1)),
        ("E7", 4, "C", "D", A_SECTION_D, ("F#7", "A", 4)),
        # D7 sits at 6 in C and at 2 in F.
        ("D7", 6, "C", "F", A_SECTION_F, ("G7", "A", 6)),
        # Dm7 sits at 3 in C and at 5 in F.
        ("Dm7", 3, "C", "F", A_SECTION_F, ("Gm7", "A", 3)),
        # Reverse direction: D back to C restores the original spelling in place.
        ("B7", 2, "D", "C", A_SECTION_C, ("A7", "A", 2)),
    ],
)
def test_sealed_selection_follows_position_across_practice_key(
    sealed_chord, sealed_index, sealed_key, live_key, new_map, expected
):
    session = _session(
        sealed_chord=sealed_chord,
        sealed_index=sealed_index,
        sealed_key=sealed_key,
        live_key=live_key,
    )
    assert resolve_authoritative_chord_selection(session, _map(new_map)) == expected


def test_seal_in_the_live_key_is_untouched():
    """No key change: the sealed spelling and index are returned verbatim."""
    session = _session(sealed_chord="A7", sealed_index=2, sealed_key="C", live_key="C")
    assert resolve_authoritative_chord_selection(session, _map(A_SECTION_C)) == ("A7", "A", 2)


def test_unstamped_seal_keeps_legacy_symbol_resolution():
    """A seal with no key stamp cannot be re-spelled, so the old path still runs."""
    session = _session(sealed_chord="A7", sealed_index=2, sealed_key="", live_key="D")
    sym, sec, _idx = resolve_authoritative_chord_selection(session, _map(A_SECTION_D))
    assert (sym, sec) == ("A7", "A")


def test_stale_click_seal_does_not_bypass_resolution():
    """``_ensure_chord_selection`` must not treat an old-key seal as a fresh click."""
    from improvisation_intelligence_ui import _click_seal_predates_live_practice_key

    session = {"concert_key": "D", "display_key": "D"}
    stale = {"chord": "A7", "section": "A", "chord_index": 2, "practice_key": "C"}
    fresh = {"chord": "B7", "section": "A", "chord_index": 2, "practice_key": "D"}
    assert _click_seal_predates_live_practice_key(session, stale) is True
    assert _click_seal_predates_live_practice_key(session, fresh) is False
    assert _click_seal_predates_live_practice_key(session, None) is False


def test_ensure_chord_selection_retargets_stale_click_to_its_position():
    """End-to-end through the UI helper: stale A7/idx2 click lands on B7/idx2."""
    from improvisation_intelligence_ui import _ensure_chord_selection

    session = _session(sealed_chord="A7", sealed_index=2, sealed_key="C", live_key="D")
    session["_mission_chord_click_authority"] = {
        "chord": "A7",
        "section": "A",
        "chord_index": 2,
        "practice_key": "C",
        "mission_id": "",
        "session_id": "",
        "source_identity": "all-of-me-jazz-standard",
    }
    _ensure_chord_selection(session, list(A_SECTION_D), _map(A_SECTION_D))
    assert session["ii_selected_chord"] == "B7"
    assert session["ii_selected_chord_index"] == 2
    assert session["ii_selected_section"] == "A"
