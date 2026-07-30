"""Curated song-specific performance coaching."""

from __future__ import annotations

from song_performance_coaching import (
    CURATED_PERFORMANCE,
    harmony_tip_for_song,
    has_curated_performance,
    section_coaching_for_song,
    teacher_intro_for_song,
)


def test_california_dreamin_curated():
    assert has_curated_performance("California Dreamin'")


def test_california_piano_verse_beginner():
    text = section_coaching_for_song(
        "California Dreamin'",
        section_name="Verse 1",
        instrument="Piano",
        level="Beginner",
    )
    assert "pattern" in text.lower() or "daydream" in text.lower()
    assert "rush" not in text.lower() or "don't rush" in text.lower() or "speed" in text.lower()


def test_california_piano_verse3_beginner_evolved():
    v1 = section_coaching_for_song(
        "California Dreamin'",
        section_name="Verse 1",
        instrument="Piano",
        level="Beginner",
    )
    v3 = section_coaching_for_song(
        "California Dreamin'",
        section_name="Verse 3",
        instrument="Piano",
        level="Beginner",
    )
    assert v1 != v3
    assert "emotion" in v3.lower() or "feeling" in v3.lower() or "breathe" in v3.lower()


def test_california_guitar_verse_not_generic_strum():
    text = section_coaching_for_song(
        "California Dreamin'",
        section_name="Verse 2",
        instrument="Guitar",
        level="Beginner",
    )
    assert "vocal is the star" in text.lower() or "intimate" in text.lower() or "harmony gently" in text.lower()


def test_california_sax_instrumental():
    text = section_coaching_for_song(
        "California Dreamin'",
        section_name="Instrumental",
        instrument="Saxophone",
        level="Intermediate",
    )
    assert "breath" in text.lower()
    assert "singing" in text.lower() or "sing" in text.lower()


def test_teacher_intro():
    intro = teacher_intro_for_song(
        "California Dreamin'",
        instrument="Guitar",
        level="Beginner",
    )
    assert "winter" in intro.lower() or "daydream" in intro.lower() or "strumming" in intro.lower()


def test_harmony_tip_no_roman():
    tip = harmony_tip_for_song("California Dreamin'", "Verse 1")
    assert "i7" not in tip.lower()
    assert tip


def test_perfect_has_profile():
    assert has_curated_performance("Perfect")
    text = section_coaching_for_song(
        "Perfect",
        section_name="Verse 1",
        instrument="Guitar",
        level="Intermediate",
    )
    assert "fingerpick" in text.lower() or "vocal" in text.lower()


def test_unknown_song_returns_empty():
    assert not section_coaching_for_song(
        "Totally Unknown Song XYZ",
        section_name="Verse",
        instrument="Piano",
        level="Beginner",
    )


def test_california_masterclass_has_arc():
    from song_performance_coaching import masterclass_lesson_markdown

    md = masterclass_lesson_markdown(
        "California Dreamin'",
        instrument="Piano",
        level="Intermediate",
        sections={"Intro": [], "Verse 1": [], "Instrumental": [], "Outro": []},
    )
    assert "Masterclass" in md or "masterclass" in md.lower() or "Your practice plan" not in md
    assert "window" in md.lower() or "daydream" in md.lower()
    assert "Opening the window" in md or "walking daydream" in md
    if "Opening the window" in md and "walking daydream" in md:
        assert md.index("Opening the window") < md.index("walking daydream")
    assert "dissolve" in md.lower() or "outro" in md.lower() or "dream" in md.lower()
    assert "emotional_character" not in md  # keys hidden, values shown
    assert "grey-sky" in md.lower() or "daydream" in md.lower() or "window" in md.lower()


def test_interpretation_fields():
    from song_performance_coaching import lookup_performance_profile

    p = lookup_performance_profile("Hotel California")
    assert p
    interp = p.get("interpretation") or {}
    assert interp.get("rush_prone")
    assert interp.get("master_challenge")


def test_section_lesson_heading():
    from song_performance_coaching import section_lesson_heading

    h = section_lesson_heading(
        "California Dreamin'",
        section_name="Verse 1",
        instrument="Piano",
        level="Intermediate",
    )
    assert "walk" in h.lower() or "daydream" in h.lower()


def test_instructor_lesson_opener_woven():
    from song_performance_coaching import instructor_card_summary, instructor_lesson_opener

    text = instructor_lesson_opener(
        "California Dreamin'",
        instrument="Piano",
        level="Beginner",
    )
    assert "daydream" in text.lower()
    assert "fancy chords can wait" in text.lower()
    assert "grey-sky longing" not in text.lower()  # card stays brief
    assert len(text) < 400
    card = instructor_card_summary(
        "California Dreamin'", instrument="Piano", level="Beginner"
    )
    assert card == text


def test_curated_library_not_empty():
    assert len(CURATED_PERFORMANCE) >= 5
