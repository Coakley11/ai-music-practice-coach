"""Musician-facing coaching (no chart encoding in default copy)."""

from __future__ import annotations

from musician_coaching import (
    build_musician_summary_meta,
    format_key_for_musicians,
    humanize_lyric_cue,
    is_internal_arrangement_note,
    musician_summary_paragraph,
    plain_section_harmony_tip,
    section_coaching_html,
)
from song_coaching import build_song_coaching, coaching_markdown


def test_format_key_for_musicians():
    assert format_key_for_musicians("C#m") == "C# minor"
    assert format_key_for_musicians("G") == "G major"


def test_internal_arrangement_note_detects_chart_docs():
    internal = (
        "**C# minor, 4/4.** Transposed from Am. One chart bar = one playback bar."
    )
    assert is_internal_arrangement_note(internal)
    assert not is_internal_arrangement_note("A warm pop ballad — sing softly in the verse.")


def test_internal_arrangement_note_detects_transpose_maps():
    internal = (
        "**C# minor (concert), 4/4, ~112 BPM.** Transposed from the Am "
        "reference: **Am→C#m, G→B.** One chart bar = one playback bar; "
        "pipe tokens are in-bar half-bar splits."
    )
    assert is_internal_arrangement_note(internal)


def test_musician_harmony_blurb_flagship():
    from musician_coaching import musician_harmony_blurb

    record = {
        "title": "California Dreamin'",
        "artist": "The Mamas & the Papas",
        "genre": "Pop",
        "key": "C#m",
    }
    tip = musician_harmony_blurb(record, {"Verse 1": ["C#m7", "G#sus4"]}, level="Beginner")
    assert "suspended" in tip.lower() or "listen" in tip.lower()
    assert "dominant 7th" not in tip.lower()
    assert "pipe" not in tip.lower()


def test_musician_challenge_blurb_no_tempo_creep():
    from musician_coaching import musician_challenge_blurb

    record = {"title": "Unknown Song XYZ", "genre": "Pop", "key": "G"}
    tip = musician_challenge_blurb(record, {"Verse": ["G", "Em"]}, level="Beginner")
    assert "tempo creep" not in tip.lower()
    assert tip
    internal = (
        "**C# minor, 4/4.** Transposed from Am. One chart bar = one playback bar."
    )
    assert is_internal_arrangement_note(internal)
    assert not is_internal_arrangement_note("A warm pop ballad — sing softly in the verse.")


def test_musician_summary_omits_transpose_jargon():
    record = {
        "title": "California Dreamin'",
        "artist": "The Mamas & the Papas",
        "genre": "Pop",
        "key": "C#m",
        "extensions": {
            "default_bpm": 112,
            "time_signature": "4/4",
            "arrangement_notes": (
                "**C# minor.** Transposed from Am. One chart bar = one playback bar."
            ),
        },
        "sections": {"Verse 1": ["C#m|B", "A|B"]},
    }
    text = musician_summary_paragraph(
        record,
        record["sections"],
        practice_key="C#m",
        instrument="Guitar",
        level="Intermediate",
    )
    assert "transposed" not in text.lower()
    assert "chart bar" not in text.lower()
    assert "112 BPM" in text or "C# minor" in text
    assert (
        "porch" in text.lower()
        or "strumming workout" in text.lower()
        or "november" in text.lower()
    )


def test_coaching_markdown_teacher_mode():
    record = {"title": "Perfect", "genre": "Pop", "key": "G", "extensions": {"default_bpm": 75}}
    block = build_song_coaching(record, {}, instrument="Piano", level="Beginner", practice_key="G")
    md = coaching_markdown(
        block,
        record,
        instrument="Piano",
        level="Intermediate",
        practice_key="G",
        sections={"Verse 1": ["G"], "Chorus 1": ["G"]},
    )
    assert "Your practice plan" in md
    assert "Masterclass" in md or "slow-dance" in md.lower() or "wedding" in md.lower()


def test_plain_section_harmony_no_roman():
    tip = plain_section_harmony_tip("Verse 1", ["C#m", "B", "A", "B"])
    assert "i7" not in tip.lower()
    assert "verse" in tip.lower() or "pattern" in tip.lower()


def test_section_coaching_guitar_beginner_unknown_song():
    html = section_coaching_html(
        section_name="Verse 1",
        instrument="Guitar",
        level="Beginner",
        groove_style="Pop groove",
        bpm=112,
        chords=["C#m", "B"],
        title="Totally Unknown Song XYZ",
    )
    assert "strum" in html.lower() or "capo" in html.lower()


def test_section_coaching_california_specific():
    html = section_coaching_html(
        section_name="Verse 1",
        instrument="Guitar",
        level="Beginner",
        groove_style="Pop groove",
        bpm=112,
        chords=["C#m", "B"],
        title="California Dreamin'",
    )
    assert "vocal is the star" in html.lower() or "intimate" in html.lower() or "harmony gently" in html.lower()


def test_humanize_lyric_cue():
    assert "root" in humanize_lyric_cue("Left hand roots/fifths").lower()
    assert "verse repeats" in humanize_lyric_cue("Verse loop: i7–VI–v").lower()


def test_summary_meta():
    meta = build_musician_summary_meta(
        {"genre": "Pop", "extensions": {"default_bpm": 112, "time_signature": "4/4"}},
        practice_key="C#m",
    )
    assert meta["key"] == "C# minor"
    assert meta["tempo"] == "112 BPM"


def test_transpose_lyric_cues_to_practice_key():
    from musician_coaching import transpose_lyric_cues

    cues = {
        "Verse 1": ["half-bar bass walk C#m–B–A–B"],
    }
    out = transpose_lyric_cues(cues, catalog_key="C#m", practice_key="Am")
    line = out["Verse 1"][0]
    assert "C#m" not in line
    assert "Am" in line
    assert "G" in line


def test_adapt_text_to_practice_key():
    from musician_coaching import adapt_text_to_practice_key

    text = adapt_text_to_practice_key(
        "Three bars of C# minor then G#sus4.",
        catalog_key="C#m",
        practice_key="Am",
    )
    assert "A minor" in text
    assert "Esus4" in text
    assert "C# minor" not in text


def test_lyric_cues_use_written_chart_key_not_concert():
    from musician_coaching import musician_facing_chart_key, transpose_lyric_cues
    from instrument_transposition import written_key_for_type

    written = written_key_for_type("Am", "Alto saxophone (Eb)")
    assert written == "F#m"
    chart_key = musician_facing_chart_key(
        chart_key=written,
        instrument="Saxophone",
    )
    assert chart_key == "F#m"
    cues = {
        "Verse 3": ["Final verse — short tag on C#m into Outro"],
    }
    out = transpose_lyric_cues(cues, catalog_key="C#m", practice_key=chart_key)
    line = out["Verse 3"][0]
    assert "F#m" in line
    assert "C#m" not in line
    assert "Am" not in line
