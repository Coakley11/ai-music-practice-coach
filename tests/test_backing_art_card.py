"""The Backing card as an album cover: same widgets, approved artwork, the app's own icons, off by default."""

from __future__ import annotations

import pathlib

import pytest

import backing_art_card as B
import song_card_art as A
from music_feature_icons import FEATURE_ICONS, SEMANTIC_FIELD_ICONS, SONG_SOURCE_ICONS
from practice_ui_labels import GROOVE_ICONS

ROOT = pathlib.Path(A.__file__).resolve().parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def test_on_by_default_with_a_switch_to_roll_back(monkeypatch):
    monkeypatch.delenv("MUSIC_SONG_ART_CARDS", raising=False)
    assert B.backing_art_enabled("song")
    for off in ("0", "off", "false", "no"):
        monkeypatch.setenv("MUSIC_SONG_ART_CARDS", off)
        assert not B.backing_art_enabled("song")


@pytest.mark.parametrize("kind,on", [("song", True), ("custom", True), ("composition", True), ("creative", False)])
def test_catalog_custom_and_composition_cards_get_artwork_style_jam_keeps_todays(monkeypatch, kind, on):
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "1")
    assert B.backing_art_enabled(kind) is on


@pytest.mark.parametrize("source,on", [("mission", True), ("song_improv", True), ("entry_jam", False), ("", False)])
def test_missions_and_sbi_wear_their_songs_card_style_jam_keeps_todays(monkeypatch, source, on):
    """A Mission or Song-Based Improvisation handoff plays a real song and wears its card; Style Jam and the
    Jam Session Generator ("entry_jam") keep today's Creative card."""
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "1")
    assert B.backing_art_enabled("creative", creative_source=source) is on
    monkeypatch.setenv("MUSIC_SONG_ART_CARDS", "0")
    assert not B.backing_art_enabled("creative", creative_source=source)


def test_a_catalog_song_lives_in_its_own_genre_not_its_groove():
    facts = B.catalog_card_facts({"title": "Let It Be", "artist": "The Beatles", "genre": "Rock"})
    identity = B.identity_for("song", source_label="Catalog song", style=facts["style"])
    assert (identity.source, identity.family) == ("catalog", "rock")


@pytest.mark.parametrize("kind,source", [("custom", "custom"), ("composition", "composition")])
def test_custom_and_composition_keep_their_own_world(kind, source):
    assert B.identity_for(kind, style="Blues").source == source


def test_the_facts_use_the_apps_own_icons():
    identity = A.card_identity("Catalog song", "Rock")
    html = A.backing_chips_html(identity, groove="Ballad", meter="4/4")
    for icon in (SEMANTIC_FIELD_ICONS["style"], SEMANTIC_FIELD_ICONS["groove"], SEMANTIC_FIELD_ICONS["meter"], SEMANTIC_FIELD_ICONS["source"], GROOVE_ICONS["Ballad"], SONG_SOURCE_ICONS["catalog"]):
        assert icon in html
    for words in ("Style", "Backing groove", "Ballad", "Meter", "4/4", "Source", "Catalog"):
        assert words in html


def test_charts_in_another_key_are_named():
    identity = A.card_identity("Catalog song", "Pop")
    assert "Charts in" in A.backing_chips_html(identity, groove="Pop groove", meter="4/4", written="B♭ major", written_label="Charts in")
    assert "Charts in" not in A.backing_chips_html(identity, groove="Pop groove", meter="4/4")


def test_the_key_panels_say_what_they_are_with_the_key_icons():
    assert FEATURE_ICONS["original_key"] in A.backing_key_label("original") and "Original key" in A.backing_key_label("original")
    assert FEATURE_ICONS["practice_concert_key"] in A.backing_key_label("practice") and "playing in" in A.backing_key_label("practice")


@pytest.mark.parametrize("genre", ["Rock", "Jazz", "Pop", "Jewish", "Classical"])
def test_play_takes_the_cards_colors(genre):
    theme = A.play_theme(A.card_identity("Catalog song", genre))
    assert theme["bg"] and theme["ink"]


def test_the_same_widgets_sit_inside_one_framed_container():
    i = APP.index("def _create_backing_card_slots(")
    body = APP[i:i + 2400]
    assert 'st.container(key="backing_art_card")' in body
    # The controls keep their key, so the Practice Key, BPM and Play widgets are the same ones.
    assert body.count('st.container(key="backing_card_controls")') == 2
    assert "theme=_backing_art_play_theme()" in APP


def test_the_transport_control_accepts_a_theme_and_keeps_its_green_without_one():
    js = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
    assert "var(--theme-bg, linear-gradient(135deg, #22c55e" in js
    assert 'document.body.style.removeProperty("--theme-bg")' in js


def test_the_style_sheet_frees_the_controls_from_the_fixed_overlay_row():
    css = (ROOT / "song_card_art.css").read_text(encoding="utf-8")
    assert ".st-key-backing_art_card .st-key-backing_card_controls{height:auto!important" in css
    assert "container-name:card" in css.split(".st-key-backing_art_card{", 1)[1].split("}", 1)[0]


def test_a_source_name_in_the_artist_place_is_replaced_by_the_real_artist():
    facts = B.catalog_card_facts({"title": "Let It Be", "artist": "Catalog song", "genre": "Rock"}, source_label="Catalog song")
    assert facts["artist"] == "The Beatles"


def test_keys_and_play_are_drawn_for_both_card_layouts():
    i = APP.index("# Keys and Play in their row: today's card and the album-cover card alike.")
    assert "if _backing_card_slot is not None and _backing_card_cols is not None:" in APP[i:i + 200]


def test_a_karaoke_entry_names_its_own_source_on_the_card():
    # A Custom setlist entry once showed as a Catalog card: the Karaoke branch named every entry "Catalog song".
    i = APP.index("A Karaoke entry may be a Custom progression or a Composition")
    body = APP[i:i + 900]
    assert "_TRANSITION_SOURCE_LABELS.get(" in body and "km.current_session_entry(st.session_state)" in body
    from karaoke_ui import _TRANSITION_SOURCE_LABELS

    assert B.identity_for("song", source_label=_TRANSITION_SOURCE_LABELS["custom_progression"]).source == "custom"
    assert B.identity_for("song", source_label=_TRANSITION_SOURCE_LABELS["composition_song"]).source == "composition"


def test_fixed_keys_read_only_key_uses_the_cards_ink():
    css = (ROOT / "song_card_art.css").read_text(encoding="utf-8")
    assert ".st-key-backing_art_card .ui-skp-locked span" in css and "color:inherit!important" in css.split("Fixed Key's read-only key", 1)[1]


def test_a_karaoke_custom_entry_is_not_given_a_source_as_its_style_or_artist(monkeypatch):
    import songs.music_source as ms

    monkeypatch.setattr(ms, "custom_progression_for_pick_key", lambda session, pk: {"progression_style": "Blues"}, raising=False)
    record = {"title": "Blues in F minor", "artist": "Your progression", "genre": "Custom", "pick_key": "custom::blues-in-f-minor"}
    facts = B.catalog_card_facts(record, source_label="Custom progression", session={})
    assert facts["artist"] == "" and facts["style"] == "Blues"
    identity = B.identity_for("song", source_label="Custom progression", style=facts["style"])
    assert identity.source == "custom" and identity.style_name == "Blues"
