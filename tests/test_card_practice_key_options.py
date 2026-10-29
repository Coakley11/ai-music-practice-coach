"""The card's Practice Key dropdown lists the 12 keys of the song's mode, one spelling each."""
from __future__ import annotations

from music_theory import conventional_key_options


def test_card_practice_key_offers_twelve_conventional_keys() -> None:
    minor = conventional_key_options("Cm")
    assert len(minor) == 12 and minor[0] == "Cm"
    assert not {"Dbm", "Gbm", "D#m", "A#m"} & set(minor)
    major = conventional_key_options("G")
    assert len(major) == 12 and major[0] == "G" and not {"C#", "D#", "G#", "A#", "Gb"} & set(major)
    # A saved twin spelling stays offered in place of its twin.
    kept = conventional_key_options("Cm", "D#m")
    assert "D#m" in kept and "Ebm" not in kept and len(kept) == 12
