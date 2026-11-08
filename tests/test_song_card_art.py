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
    "source, style, art",
    [("Custom", "Blues", "custom_blues"), ("Custom", "Pop", "custom_pop"), ("Custom", "Rock", "custom_rock"),
     ("Composition", "Blues", "composition_blues"), ("Composition", "Classical", "composition_classical"), ("Composition", "Pop", "composition_pop")],
)
def test_source_keeps_its_world_and_style_adds_the_art(source: str, style: str, art: str) -> None:
    i = A.card_identity(source, style)
    assert i.family == source.lower() and i.art == art
    assert i.crest == FEATURE_ICONS[source.lower()]
    assert (A.ART_DIR / f"{art}.svg").is_file()


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
    assert 'class="sc-stylelogo"' in out and "composition_blues.svg" in out
    assert 'class="sc-stylelogo"' not in A.hero_html(A.card_identity("Catalog", "Blues"), title="X")


def test_switch_is_on_by_default_and_rolls_back_with_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSIC_SONG_ART_CARDS", raising=False)
    assert A.song_art_cards_enabled() is True
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "0")
    assert A.song_art_cards_enabled() is False
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "1")
    assert A.song_art_cards_enabled() is True


@pytest.mark.parametrize("source", ["custom", "composition"])
@pytest.mark.parametrize("genre", list(A.GENRES))
def test_every_style_has_its_own_variation_inside_the_source_world(source: str, genre: str) -> None:
    """Three distinct families: a Custom or Composition song in any style keeps its source world (its own art file,
    built on the green notebook or the navy-and-gold manuscript) and never shows the Catalog album art."""
    i = A.card_identity(source.title(), genre.title())
    assert (i.family, i.art) == (source, f"{source}_{genre}")
    art = (A.ART_DIR / f"{i.art}.svg").read_text(encoding="utf-8")
    base = (A.ART_DIR / f"{source}.svg").read_text(encoding="utf-8")
    catalog = (A.ART_DIR / f"{genre}.svg").read_text(encoding="utf-8")
    assert art != catalog and art != base
    # The source's own background is the base of every variation.
    bg = base[base.index('<linearGradient id="bg"'):].split("</linearGradient>", 1)[0]
    assert bg in art


def _window(name: str) -> tuple[float, float, float, float]:
    x, y, w, h = (float(v) for v in A._PHONE_VIEW[name].split(","))
    return x, y, x + w, y + h


def test_phone_crops_keep_each_genre_defining_instrument() -> None:
    """On a phone the Catalog card keeps what makes the genre recognisable (coordinates in the 1600-wide artwork):
    Jewish keeps the Star of David (x 910-1210) and the clarinet (to x 1595); Country keeps the hat (x 1110-1480,
    brim at y 612) beside the guitar."""
    x0, _y0, x1, _y1 = _window("jewish")
    assert x0 <= 905 and x1 >= 1595
    x0, _y0, x1, y1 = _window("country")
    assert x0 <= 1105 and x1 >= 1485 and y1 >= 615


def test_custom_soul_record_stays_small_beside_the_chord_chart() -> None:
    """Custom Soul's vinyl record is drawn at half size near the top-right corner, so the handwritten chord chart
    stays the subject on a phone (the shared Custom layout draws instruments at .72)."""
    art = (A.ART_DIR / "custom_soul.svg").read_text(encoding="utf-8")
    assert 'scale(0.5) translate(-1340 -40)' in art
    assert art.count('<circle r="330" fill="url(#gsou_vinyl)"/>') == 1
