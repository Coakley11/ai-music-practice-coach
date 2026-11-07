"""The artistic song cards: identity rules, established icons, and honest instrument headings."""

from __future__ import annotations

import pytest

import song_card_art as A
from music_feature_icons import FEATURE_ICONS, SEMANTIC_FIELD_ICONS
from practice_studio import genre_visual_style
from practice_ui_labels import FOCUS_ICONS, LEVEL_ICONS

GUIDE = {"harmony": "A loop in G.", "melody": "Land on chord tones.", "focus": "Voice the changes.", "focus_label": "Voicings", "challenge": "Comp the verse."}


def body(identity, title="Song", general="Piano, Guitar, Voice"):
    return A.songs_body_html(
        identity, title=title, bpm=100, meter="4/4", level="Advanced", instrument="Piano", focus="Voicings",
        levels=["Beginner", "Intermediate", "Advanced"], instruments_general=general, guide=GUIDE, shown_in="G major",
    )


@pytest.mark.parametrize("genre", ["Pop", "Rock", "Jazz", "Blues", "Country", "Soul", "Funk", "Jewish", "Classical"])
def test_catalog_songs_live_in_their_genre(genre: str) -> None:
    i = A.card_identity("Catalog Song", genre)
    assert (i.source, i.family, i.art) == ("catalog", genre.lower(), genre.lower())
    assert i.crest == genre_visual_style(genre)["emoji"]
    assert (A.ART_DIR / f"{i.art}.svg").is_file()


@pytest.mark.parametrize(
    "source, style, world",
    [("Custom", "Blues", "blues"), ("Custom", "Pop", "pop"), ("Custom", "Rock", "rock"),
     ("Composition", "Blues", "blues"), ("Composition", "Classical", "classical"), ("Composition", "Jazz", "jazz")],
)
def test_the_saved_style_picks_the_world_and_the_source_keeps_its_marks(source: str, style: str, world: str) -> None:
    i = A.card_identity(source, style)
    assert i.family == world and i.art == world and f"src-{source.lower()}" in i.classes
    assert i.crest == FEATURE_ICONS[source.lower()]
    assert (A.ART_DIR / f"{world}.svg").is_file()


@pytest.mark.parametrize("source", ["Custom", "Composition"])
def test_a_song_without_a_style_keeps_its_source_world(source: str) -> None:
    i = A.card_identity(source, "")
    assert (i.family, i.art, i.style_name) == (source.lower(), source.lower(), "")
    assert "src-" not in i.classes


def test_every_catalog_genre_has_lower_body_artwork_css() -> None:
    for genre in A.GENRES:
        assert A._family_vars(genre), genre
    assert A._family_vars("custom") and A._family_vars("composition")


def test_card_uses_the_apps_own_icons() -> None:
    out = body(A.card_identity("Catalog", "Jazz"))
    for icon, label in (
        (SEMANTIC_FIELD_ICONS["bpm"], "BPM"), (SEMANTIC_FIELD_ICONS["meter"], "Meter"), (SEMANTIC_FIELD_ICONS["style"], "Style"),
        (SEMANTIC_FIELD_ICONS["source"], "Source"),
    ):
        assert f"<i>{icon}</i><span>{label}</span>" in out
    assert f'<i>{FEATURE_ICONS["practice_setup"]}</i>Your setup' in out
    assert f'<i>{SEMANTIC_FIELD_ICONS["level"]}</i>Chart levels' in out
    assert f'<i>{FOCUS_ICONS["Harmony"]}</i>Harmony' in out
    assert f'<i>{FOCUS_ICONS["Melody"]}</i>Melody' in out
    assert f'<i>{FEATURE_ICONS["practice_focus"]}</i>Your focus: Voicings' in out
    assert "<i>\U0001F525</i>Your challenge" in out
    for level, icon in LEVEL_ICONS.items():
        assert f'<em class="pg">{icon}</em> {level}' in out
    assert '<span class="lvl lvl-on"><em class="pg">🧠</em> Advanced</span>' in out


def test_reviewed_song_says_great_on() -> None:
    assert A.song_instruments("Let It Be", "Catalog", "Rock", "Guitar, Bass") == ("Great on", ("Piano", "Voice", "Guitar", "Bass"))


def test_unreviewed_song_never_claims_a_recommendation() -> None:
    heading, names = A.song_instruments("Some Other Song", "Catalog", "Rock", "Guitar, Bass, Drums, Voice")
    assert heading == "Common in Rock"
    assert names == ("Guitar", "Bass", "Drums", "Voice")


def test_a_custom_song_with_a_reviewed_title_is_still_general() -> None:
    assert A.song_instruments("Let It Be", "Custom", "Rock", "Guitar")[0] == "Common in Rock"


def test_general_classical_list_leaves_voice_to_each_song() -> None:
    assert A.song_instruments("New Piece", "Composition", "Classical", "Piano, Guitar, Voice") == ("Common in Classical", ("Piano", "Violin", "Flute"))
    assert "Voice" in A.REVIEWED_INSTRUMENTS["Ode to Joy"]


def test_text_is_escaped() -> None:
    out = A.hero_html(A.card_identity("Custom", "Pop"), title="<b>Mine</b>", artist="A & B", bars=["<x>"], bars_note="Your progression")
    assert "<b>Mine</b>" not in out and "&lt;b&gt;Mine" in out and "A &amp; B" in out and "&lt;x&gt;" in out


def test_hero_shows_the_style_logo_beside_the_source_crest() -> None:
    out = A.hero_html(A.card_identity("Composition", "Blues"), title="Midnight Walk")
    assert 'class="sc-stylelogo"' in out and "/blues.svg" in out and "src-composition" in out
    assert 'class="sc-stylelogo"' not in A.hero_html(A.card_identity("Catalog", "Blues"), title="X")


def test_switch_is_on_by_default_and_rolls_back_with_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSIC_SONG_ART_CARDS", raising=False)
    assert A.song_art_cards_enabled() is True
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "0")
    assert A.song_art_cards_enabled() is False
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "1")
    assert A.song_art_cards_enabled() is True
