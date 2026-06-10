"""Tests for song_coaching curated and fallback paths."""

from __future__ import annotations

from song_coaching import (
    build_song_coaching,
    coaching_markdown,
    coaching_practice_focus,
    coaching_scale_summary,
    lookup_curated,
)


def test_curated_perfect():
    block = lookup_curated("Perfect")
    assert block is not None
    assert "loop" in block["what_matters"].lower()


def test_build_song_coaching_curated_instrument_tip():
    record = {"title": "Perfect", "genre": "Pop", "key": "G"}
    block = build_song_coaching(record, {}, instrument="Piano")
    assert block["instrument_tip"]
    assert "left hand" in block["instrument_tip"].lower() or "hand" in block["instrument_tip"].lower()


def test_fallback_unknown_song():
    record = {"title": "Obscure Demo Track XYZ", "genre": "Rock", "key": "E"}
    block = build_song_coaching(record, {"Verse": ["E", "A"]}, instrument="Guitar")
    assert block["what_matters"]
    assert block["instrument_tip"]


def test_coaching_markdown_has_five_sections():
    block = build_song_coaching({"title": "Shallow", "key": "G", "genre": "Pop"}, {})
    md = coaching_markdown(block)
    assert "What matters most" in md
    assert "Biggest challenge" in md
    assert "Instrument tip" in md
    assert "Practice next" in md
    assert "Performance next" in md


def test_scale_summary_capped():
    block = build_song_coaching({"title": "Hotel California", "key": "Bm", "genre": "Rock"}, {})
    summary = coaching_scale_summary(block)
    assert "pentatonic" in summary.lower() or "minor" in summary.lower()
    assert summary.count("**") <= 6


def test_practice_focus_short():
    block = build_song_coaching({"title": "Perfect", "key": "G", "genre": "Pop"}, {})
    focus = coaching_practice_focus(block)
    assert len(focus) <= 123


def test_fallback_coaching_uses_practice_key():
    record = {"title": "Obscure Demo Track XYZ", "genre": "Rock", "key": "Db"}
    block = build_song_coaching(
        record,
        {"Verse": ["Eb", "Ab"]},
        instrument="Guitar",
        practice_key="Eb",
    )
    assert "Eb" in block["primary_scale"]
    assert "Db" not in block["primary_scale"]
    assert "Eb" in block["improv_approach"]


def test_curated_coaching_remaps_practice_key():
    record = {"title": "All of Me", "genre": "Jazz", "key": "Ab"}
    block = build_song_coaching(record, {}, practice_key="Eb")
    assert "Eb" in block["primary_scale"]
    assert "Eb" in block["improv_approach"]
    assert "Ab major pentatonic" not in block["improv_approach"]


def test_written_key_tenor_practice_key_in_coaching():
    record = {"title": "Unknown Tune QRS", "genre": "Pop", "key": "Db"}
    block = build_song_coaching(
        record,
        {"Verse": ["Eb"]},
        instrument="Saxophone",
        practice_key="Eb",
    )
    summary = coaching_scale_summary(block)
    assert "Eb" in summary
    assert "Db major" not in summary.lower()
