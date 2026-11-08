"""Missions and Song-Based Improvisation on the Backing page wear the card of the song they play.

The song's own source (Catalog, Custom, Composition) and saved style pick the artwork -- never the Backing groove
the Mission or SBI handoff carries -- and the Mission's own facts (mission, section, target chord or span,
Default vs Current style / meter, the written key's instrument) stay on the card.
"""

from __future__ import annotations

import pathlib
from types import SimpleNamespace

import pytest

import backing_art_card as B
import song_card_art as A

ROOT = pathlib.Path(A.__file__).resolve().parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
UI = (ROOT / "backing_context_ui.py").read_text(encoding="utf-8")
CSS = (ROOT / "song_card_art.css").read_text(encoding="utf-8")


def _ctx(source: str, *, pick: str = "", title: str = "", style: str = "Jazz swing") -> SimpleNamespace:
    # ctx.style is the Backing groove the handoff carries: it must never decide the artwork.
    return SimpleNamespace(source=source, bound_pick_key=pick, active_song_id="", song_title=title, style=style)


@pytest.fixture
def owner(monkeypatch):
    """The Mission's current owner song, as mission_owner_contract resolves it."""
    import mission_owner_contract as M

    current = {"pick": ""}

    def resolve(_session):
        return SimpleNamespace(underlying_pick=current["pick"])

    monkeypatch.setattr(M, "resolve_mission_owner_context", resolve)
    return current


def test_a_mission_uses_its_current_owner_song_not_a_stale_link(owner):
    owner["pick"] = "Rock\x1fLet It Be — The Beatles"
    ctx = _ctx("mission", pick="Jazz\x1fAutumn Leaves — Jazz Standard")  # sealed before the song changed
    assert B.creative_owner_pick({}, ctx) == "Rock\x1fLet It Be — The Beatles"


def test_a_mission_falls_back_to_its_sealed_song_when_no_owner_resolves(owner):
    owner["pick"] = ""
    ctx = _ctx("mission", pick="Jazz\x1fAutumn Leaves — Jazz Standard")
    assert B.creative_owner_pick({}, ctx) == "Jazz\x1fAutumn Leaves — Jazz Standard"


def test_a_catalog_mission_wears_the_catalog_genre_not_the_groove(owner):
    owner["pick"] = "Rock\x1fLet It Be — The Beatles"
    identity, title, _artist = B.creative_identity({}, _ctx("mission", title="Let It Be", style="Jazz swing"))
    assert (identity.source, identity.family, identity.art) == ("catalog", "rock", "rock")
    assert title == "Let It Be"


@pytest.mark.parametrize(
    "pick,style,art,family",
    [
        ("custom::rev-1", "Blues", "custom_blues", "custom"),
        ("custom::rev-2", "Soul", "custom_soul", "custom"),
        ("composition::doc-1", "Classical", "composition_classical", "composition"),
        ("composition::doc-2", "Jazz", "composition_jazz", "composition"),
    ],
)
def test_custom_and_composition_songs_keep_their_own_world_in_their_saved_style(monkeypatch, pick, style, art, family):
    import song_identity_style as S

    monkeypatch.setattr(S, "saved_song_style", lambda _session, pk, **_k: style if pk == pick else "")
    identity, _title, _artist = B.creative_identity({}, _ctx("song_improv", pick=pick, title="My Song", style="Rock groove"))
    assert (identity.family, identity.art) == (family, art)


def test_sbi_custom_without_its_prefix_reads_the_active_custom_progression(monkeypatch):
    import source_session_state as SS
    from custom_progression_lab import CPL_ACTIVE_KEY

    monkeypatch.setattr(SS, "resolve_sbi_material_kind", lambda _session, ctx=None, owner=None: "custom")
    session = {CPL_ACTIVE_KEY: {"id": "rev-9", "name": "Late Night"}}
    assert B.creative_owner_pick(session, _ctx("song_improv", pick="")) == "custom::rev-9"


def test_the_mission_facts_block_escapes_and_wraps():
    identity = A.card_identity("Custom", "Blues")
    html = A.backing_mission_html(
        identity, kicker="Mission", line="Improvise using only chord tones · Verse · Dm7 <b>",
        details=["Default style: Jazz swing · Current style: Bossa nova", ""],
    )
    assert "sc-frag-mission" in html and "g-custom" in html
    assert "&lt;b&gt;" in html and "<b>Improvise" in html
    assert html.count('class="sc-mission-d"') == 1
    assert A.backing_mission_html(identity, kicker="Mission", line="") == ""
    assert "overflow-wrap:anywhere" in CSS and ".sc-prog-bars{flex-wrap:wrap" in CSS


def test_a_missions_written_key_wears_the_instrument():
    from music_feature_icons import SEMANTIC_FIELD_ICONS, semantic_field_icon

    identity = A.card_identity("Catalog", "Jazz")
    plain = A.backing_chips_html(identity, groove="Jazz swing", meter="4/4", written="Bb major", written_label="Charts in")
    clar = A.backing_chips_html(
        identity, groove="Jazz swing", meter="4/4", written="Bb major", written_label="Charts in", written_instrument="Clarinet"
    )
    assert SEMANTIC_FIELD_ICONS["written_key"] in plain
    assert semantic_field_icon("written_key", instrument="Clarinet") in clar


def test_a_span_shows_each_chord_in_the_card_strip():
    identity = A.card_identity("Catalog", "Jazz")
    html = A.hero_html(identity, title="Autumn Leaves", page="backing", status="Mission backing jam",
                       bars=["Cm7", "F7", "Bbmaj7"], bars_note="Mission span")
    assert html.count('class="sc-bar"') == 3 and "Mission span" in html and "Mission backing jam" in html


def test_todays_creative_card_and_the_album_cover_card_read_the_same_facts():
    # One source of truth for the heading and Default / Current style: today's card (rollback) and the art card.
    assert "_head = creative_card_headline(" in UI and "_live = creative_live_style_meter(" in UI
    assert "creative_card_headline(" in APP and "creative_live_style_meter(" in APP
    # The art switch passes the handoff's source; today's Creative card stays for rollback and Style Jam.
    assert '_backing_card_kind == "creative" else ""' in APP
    assert "render_backing_creative_context_card(" in APP
