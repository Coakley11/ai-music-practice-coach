"""One Melody symbol, everywhere the musician meets the word.

The Songs page Melody card and Composition Studio must show the same glyph, so the
value lives once in ``FEATURE_ICONS["phase_melody"]`` and every surface reads it.
Chords keeps the guitar and Lyrics the microphone.
"""

from __future__ import annotations

import inspect

from composition_document import COMPOSITION_PHASE_LABELS
from music_feature_icons import FEATURE_ICONS, SONG_SOURCE_ICONS
from practice_ui_labels import FOCUS_ICONS

MELODY = FEATURE_ICONS["phase_melody"]


def test_the_melody_glyph_is_the_three_beamed_notes() -> None:
    assert MELODY == "\U0001F3B6"  # 🎶


def test_the_songs_page_card_and_the_registry_are_the_same_value() -> None:
    """``song_card_art`` renders ``FOCUS_ICONS["Melody"]`` on the Songs Melody card."""
    assert FOCUS_ICONS["Melody"] == MELODY


def test_composition_phase_label_uses_it() -> None:
    assert COMPOSITION_PHASE_LABELS["melody"] == f"{MELODY} Melody"


def test_composition_section_lane_button_uses_it() -> None:
    """The "Work on" lane switcher must not hard-code a second note glyph."""
    from composition_studio_page import _render_section_lane_switcher

    src = inspect.getsource(_render_section_lane_switcher)
    assert "\U0001F3B5" not in src, "the single note 🎵 is back in the lane switcher"
    assert 'COMPOSITION_PHASE_LABELS["melody"]' in src


def test_melody_is_not_the_catalog_source_logo() -> None:
    """🎵 identifies a Catalog song's *source*; it must not also mean Melody."""
    assert SONG_SOURCE_ICONS["catalog"] == "\U0001F3B5"
    assert MELODY != SONG_SOURCE_ICONS["catalog"]


def test_chords_keeps_the_guitar_and_lyrics_the_microphone() -> None:
    assert COMPOSITION_PHASE_LABELS["chords"] == "\U0001F3B8 Chords"  # 🎸
    assert COMPOSITION_PHASE_LABELS["lyrics"] == "\U0001F3A4 Lyrics"  # 🎤
    assert FEATURE_ICONS["phase_chords"] == "\U0001F3B8"
    assert FEATURE_ICONS["phase_lyrics"] == "\U0001F3A4"


def test_no_surface_hard_codes_a_melody_glyph_of_its_own() -> None:
    """Every "<note> Melody" in the shipped UI must be the shared glyph."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in sorted(root.glob("*.py")):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for glyph in ("\U0001F3B5", "\U0001F3BC"):  # 🎵 🎼
                if f"{glyph} Melody" in line:
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert not offenders, offenders


def test_the_score_itself_is_untouched() -> None:
    """Notation glyphs inside a score are musical content, not UI chrome."""
    assert "notation" not in MELODY
    # The icon registry must never be consulted for note heads / accidentals.
    assert all(len(value) <= 4 or value.startswith("<") for value in FEATURE_ICONS.values())
