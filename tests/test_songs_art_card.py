"""The Songs page card as the song's album cover: same Practice Key widget, same facts, the switch rolls it back."""

from __future__ import annotations

import pathlib

import song_card_art as A
from music_feature_icons import SEMANTIC_FIELD_ICONS, SONG_SOURCE_ICONS

ROOT = pathlib.Path(A.__file__).resolve().parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CSS = (ROOT / "song_card_art.css").read_text(encoding="utf-8")


def test_the_songs_card_uses_the_artwork_when_the_switch_is_on():
    i = APP.index("def _render_active_song_card(")
    body = APP[i:i + 30000]
    assert "_songs_art_identity = _card_identity(_source_label, _style_label)" in body
    assert "_card_style_tag(_songs_art_identity) + _hero_html(" in body
    assert "_songs_body_html(" in body
    # Today's card stays for the rollback switch.
    assert "song_card_header_html(" in body and "_song_card_guidance_html(details" in body


def test_the_practice_key_widget_is_the_same_one():
    i = APP.index("def _render_card_practice_key_selector(")
    body = APP[i:i + 6000]
    assert 'widget_key = f"card_practice_key::{pk}"' in body and "on_change=_apply_card_practice_key_change" in body
    assert '_pk_label_html = _key_label("practice")' in body


def test_the_written_key_is_named_on_the_songs_card():
    identity = A.card_identity("Catalog song", "Pop")
    out = A.songs_body_html(identity, title="S", bpm=90, meter="4/4", level="Intermediate", instrument="Guitar", focus="Voicings",
                            levels=["Beginner"], instruments_general="Guitar", guide={}, written="E", written_label="Shape Key")
    assert SEMANTIC_FIELD_ICONS["written_key"] in out and "Shape Key" in out
    assert SONG_SOURCE_ICONS["catalog"] in out


def test_the_songs_styles_leave_todays_card_alone():
    block = CSS.split("Songs: the same album cover", 1)[1]
    rules = [r.strip() for r in block.split("}") if "{" in r and not r.strip().startswith(("@", "/*"))]
    scoped = [r for r in rules if r.startswith(".st-key-picker_active_song_card_content")]
    assert scoped and all(":has(.sc-frag)" in r.split("{")[0] or "sc-" in r.split("{")[0] for r in scoped)
