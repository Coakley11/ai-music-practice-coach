"""Session key from fixed family + musical mode."""

from __future__ import annotations

import pytest

from practice_key_mode import resolve_session_key_from_family


@pytest.mark.parametrize(
    "family,mode,expected",
    [
        ("C|A", "major", "C"),
        ("C|A", "minor", "Am"),
        ("G|E", "major", "G"),
        ("G|E", "minor", "Em"),
    ],
)
def test_resolve_session_key_from_family(family: str, mode: str, expected: str) -> None:
    assert resolve_session_key_from_family(family, mode) == expected
