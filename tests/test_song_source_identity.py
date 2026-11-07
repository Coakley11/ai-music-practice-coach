"""Song sources keep their own established logos everywhere: Catalog ♫, Custom ✍️, Composition 🪶.

A Source badge once showed the Songs page score (🎼) for Catalog. Sources are not genres and not pages:
this pins the one mapping and checks every card surface against it.
"""

from __future__ import annotations

import pytest

import app_ui
import song_card_art as A
from music_feature_icons import FEATURE_ICONS, SONG_SOURCE_ICONS, song_source_icon
from practice_studio import genre_visual_style
from practice_ui_labels import FOCUS_ICONS

CATALOG_NOTES = "\U0001F3B5"  # the purple pair of beamed eighth notes
MELODY_NOTES = "\U0001F3B6"
GENRES = ["Pop", "Rock", "Jazz", "Blues", "Country", "Soul", "Funk", "Jewish", "Classical"]


def test_the_three_source_logos_are_the_established_ones():
    assert SONG_SOURCE_ICONS == {"catalog": CATALOG_NOTES, "custom": "✍️", "composition": "\U0001FAB6"}
    assert SONG_SOURCE_ICONS["custom"] == FEATURE_ICONS["custom"]
    assert SONG_SOURCE_ICONS["composition"] == FEATURE_ICONS["composition"]


def test_catalog_is_not_the_melody_notes_or_the_songs_page_icon():
    assert SONG_SOURCE_ICONS["catalog"] not in {MELODY_NOTES, FEATURE_ICONS["songs"], FOCUS_ICONS.get("Melody")}


@pytest.mark.parametrize("label,key", [("Catalog song", "catalog"), ("Custom Progression song", "custom"), ("Custom Song", "custom"), ("Composition song", "composition"), ("Composed Song", "composition"), ("", "catalog")])
def test_every_source_label_finds_its_logo(label, key):
    assert song_source_icon(label) == SONG_SOURCE_ICONS[key]


@pytest.mark.parametrize("label,key", [("Catalog Song", "catalog"), ("Custom Song", "custom"), ("Composed Song", "composition")])
def test_the_app_badges_and_the_cards_use_the_same_logo(label, key):
    assert SONG_SOURCE_ICONS[key] in app_ui.song_source_icon_parts(label)[0]
    assert A.card_identity(label, "Jazz").source_logo == SONG_SOURCE_ICONS[key]


@pytest.mark.parametrize("source,key", [("Catalog song", "catalog"), ("Custom", "custom"), ("Composition", "composition")])
@pytest.mark.parametrize("genre", GENRES)
def test_the_source_badge_on_backing_and_songs_cards(source, key, genre):
    identity = A.card_identity(source, genre)
    others = [v for k, v in SONG_SOURCE_ICONS.items() if k != key]
    backing = A.backing_chips_html(identity, groove="Ballad", meter="4/4")
    badge = backing.split("Source", 1)[1]
    assert SONG_SOURCE_ICONS[key] in badge and not any(o in badge for o in others)
    songs = A.songs_body_html(identity, title="Song", bpm=100, meter="4/4", level="Intermediate", instrument="Piano", focus="Voicings",
                              levels=["Beginner", "Intermediate", "Advanced"], instruments_general="Piano", guide={})
    s_badge = songs.split("Source", 1)[1].split("</span></span>", 1)[0]
    assert SONG_SOURCE_ICONS[key] in s_badge and not any(o in s_badge for o in others)


@pytest.mark.parametrize("genre", GENRES)
def test_genre_artwork_is_unchanged_by_the_source(genre):
    """Catalog wears its genre's crest; Custom and Composition wear their source logo; the artwork world stays."""
    catalog = A.card_identity("Catalog song", genre)
    assert catalog.crest == genre_visual_style(genre)["emoji"]
    assert catalog.art == genre.lower()
    for source, key in (("Custom", "custom"), ("Composition", "composition")):
        identity = A.card_identity(source, genre)
        assert identity.crest == SONG_SOURCE_ICONS[key]
        assert identity.crest not in {genre_visual_style(g)["emoji"] for g in GENRES}
