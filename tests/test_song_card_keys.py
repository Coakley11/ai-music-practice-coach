"""v12 key-caption rule and readable key names for the Songs / Backing cards."""
from __future__ import annotations

import pytest

from song_card_keys import key_relation_caption, pretty_key_name, same_key


@pytest.mark.parametrize(
    "raw, want",
    [
        ("Db", "D♭ major"),
        ("C#m", "C♯ minor"),
        ("Eb minor", "E♭ minor"),
        ("Bb major", "B♭ major"),
        ("Cm", "C minor"),
        ("A", "A major"),
        ("D♭ major", "D♭ major"),
        ("F#", "F♯ major"),
        ("", ""),
    ],
)
def test_pretty_key_name(raw: str, want: str) -> None:
    assert pretty_key_name(raw) == want


@pytest.mark.parametrize(
    "orig, practice, want",
    [
        ("Db", "Eb", "2 semitones higher"),
        ("Db", "D", "1 semitone higher"),
        ("D", "Db", "1 semitone lower"),
        ("C", "F", "5 semitones higher"),
        ("C", "G", "5 semitones lower"),  # shortest distance, not 7 up
        ("C", "F#", "a tritone away"),
        ("Cm", "Dm", "2 semitones higher"),
        ("Db", "C#", ""),  # enharmonic: same key
        ("D", "D", ""),
        ("D", "Bm", ""),  # mode differs: hidden
        ("Cm", "Eb", ""),
        ("??", "D", ""),
    ],
)
def test_key_relation_caption(orig: str, practice: str, want: str) -> None:
    assert key_relation_caption(orig, practice) == want


def test_same_key_counts_enharmonics() -> None:
    assert same_key("Db", "C# major") and same_key("Ebm", "D#m")
    assert not same_key("D", "Dm")
