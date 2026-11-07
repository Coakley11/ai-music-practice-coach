"""A catalog song's artwork, logo and Style label come from its catalog genre."""

from __future__ import annotations

import pytest

from practice_studio import active_song_card_details, genre_visual_style
from song_card_header import header_style_label, header_theme
from song_catalog.catalog import bulk_song_records, curated_song_records


def _records() -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    for rec in list(curated_song_records()) + list(bulk_song_records()):
        seen.setdefault((str(rec.get("title")), str(rec.get("artist"))), rec)
    return list(seen.values())


RECORDS = _records()


def test_the_catalog_is_covered() -> None:
    assert len(RECORDS) >= 119


def test_every_song_shows_its_catalog_genre() -> None:
    wrong = []
    for rec in RECORDS:
        details = active_song_card_details(rec, level="Intermediate", instrument="Piano")
        want = genre_visual_style(str(rec.get("genre") or ""))["label"]
        got = header_style_label(details["style_label"])
        if got != want:
            wrong.append((rec.get("title"), rec.get("genre"), details["style_label"], got))
    assert not wrong, wrong


@pytest.mark.parametrize("title", ["Let It Be", "Ode to Joy"])
def test_real_rock_and_classical_keep_their_own_style(title: str) -> None:
    rec = next(r for r in RECORDS if r.get("title") == title)
    details = active_song_card_details(rec, level="Intermediate", instrument="Piano")
    assert details["style_label"] == rec["genre"]


def test_pop_ballads_use_the_pop_artwork() -> None:
    ballads = [
        r for r in RECORDS
        if "pop" in str(r.get("genre") or "").lower()
        and "ballad" in str((r.get("extensions") or {}).get("arrangement_notes") or "").lower()
    ]
    assert ballads, "the catalog should contain Pop ballads"
    for rec in ballads:
        details = active_song_card_details(rec, level="Intermediate", instrument="Piano")
        assert header_style_label(details["style_label"]) == "Pop", rec.get("title")
        assert header_theme("Catalog", details["style_label"])["style_label"] == "Pop", rec.get("title")
