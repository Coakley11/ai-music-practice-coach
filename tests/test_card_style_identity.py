"""The saved style decides what a song LOOKS like; the Backing groove decides how it SOUNDS.

A Custom song changed from Blues to Rock on the Custom page kept its Blues artwork on Backing: the card read a
Backing play-session snapshot (ctx.style) that is not refreshed when the song is re-saved. These pin the rule:

* Catalog: the catalog genre. Custom: the progression's saved style. Composition: Composition Studio's Genre / Style.
* Read fresh from the source record, so a re-saved style reaches the card for the same song.
* The groove (Advanced playback settings) never changes the artwork, the Style chip or the Source.
* A song saved without a style gets none: nothing is invented or written back.
"""

from __future__ import annotations

import copy
import inspect
from types import SimpleNamespace

import pytest

import backing_art_card as B
import song_card_art as A
import song_identity_style as S
from composition_document import COMPOSITION_GENRES
from custom_progression_lab import CPL_PROGRESSION_STYLES
from music_feature_icons import SONG_SOURCE_ICONS

CUSTOM_PK = "custom::song-1"


def custom_session(style: str | None, *, saved_only: bool = False) -> dict:
    prog = {"id": "song-1", "name": "Blues in F minor", "original_key_center": "Fm"}
    if style is not None:
        prog["progression_style"] = style
    session: dict = {"cpl_saved_progressions": {"Blues in F minor": copy.deepcopy(prog)},
                     "backing_groove_style": "Pop groove"}
    if not saved_only:
        session["cpl_active_progression"] = prog
    return session


def composition_doc(genre: str | None, rhythm_style: str | None = "Pop") -> dict:
    doc = {"id": "c1", "metadata": {}, "global": {}}
    if genre is not None:
        doc["metadata"]["style"] = genre
    if rhythm_style is not None:
        doc["global"]["progression_style"] = rhythm_style
    return doc


# --- Every style the source pages offer looks like its genre, with the source's own marks. ----------------------

SUPPORTED = sorted({*CPL_PROGRESSION_STYLES, *[g for g in COMPOSITION_GENRES if g != "Other"]})


@pytest.mark.parametrize("source", ["Custom", "Composition"])
@pytest.mark.parametrize("style", SUPPORTED)
def test_every_supported_style_wears_a_genre_world_with_the_source_branding(source: str, style: str) -> None:
    i = A.card_identity(source, style)
    assert i.family in A.GENRES and i.art == i.family, (style, i)
    assert (A.ART_DIR / f"{i.art}.svg").is_file()
    assert f"g-{i.family}" in i.classes and f"src-{source.lower()}" in i.classes
    assert i.crest == i.source_logo == SONG_SOURCE_ICONS[source.lower()]
    assert i.style_name and i.style_logo != SONG_SOURCE_ICONS["catalog"], "a style never borrows the Catalog logo"


@pytest.mark.parametrize("source", ["Custom", "Composition"])
def test_custom_rock_has_the_whole_rock_world_not_a_rock_badge(source: str) -> None:
    rock = A.card_identity(source, "Rock")
    catalog_rock = A.card_identity("Catalog", "Rock")
    assert (rock.family, rock.art) == (catalog_rock.family, catalog_rock.art) == ("rock", "rock")
    assert A._family_vars(rock.family) == A._family_vars("rock")  # the same palette on the card's container
    hero = A.hero_html(rock, title="Blues in F minor", page="backing")
    assert "g-rock" in hero and "rock.svg" in hero and f"src-{source.lower()}" in hero
    assert A.card_identity(source, "Rock").art not in {"custom", "composition", "custom_blues", "custom_pop"}


def test_styles_without_artwork_of_their_own_keep_their_real_name() -> None:
    for style, world in (("Bossa", "jazz"), ("Folk", "country"), ("Hip-Hop", "funk"), ("Electronic", "pop"), ("Soul/R&B", "soul")):
        i = A.card_identity("Composition", style)
        assert i.family == world and i.style_name == A.style_world(style)[1]
        assert style.split("/")[0] in i.style_name


def test_the_source_branding_css_exists_for_both_sources() -> None:
    css = A._base_css()
    for source in ("custom", "composition"):
        assert f".sc-frag.src-{source} .sc-logo" in css
        assert f":has(.src-{source}) .st-key-backing_card_key_row" in css


# --- The groove is a playback choice: it never changes the artwork, the style or the source. --------------------

@pytest.mark.parametrize("groove", ["Pop groove", "Jazz swing", "Ballad", "Funk groove", "Auto"])
def test_a_groove_override_leaves_custom_rock_looking_like_rock(groove: str) -> None:
    rock = A.card_identity("Custom", "Rock")
    chips = A.backing_chips_html(rock, groove=groove, meter="4/4")
    assert "g-rock" in chips and "src-custom" in chips
    style_chip = chips.split("Style", 1)[1].split("</span></span>", 1)[0]
    groove_chip = chips.split("Backing groove", 1)[1].split("</span></span>", 1)[0]
    source_chip = chips.split("Source", 1)[1]
    assert "Rock" in style_chip and groove in groove_chip and "Custom" in source_chip


def test_style_and_groove_carry_different_labels_and_icons() -> None:
    chips = A.backing_chips_html(A.card_identity("Custom", "Rock"), groove="Pop groove", meter="4/4")
    assert f"<i>{A.SEMANTIC_FIELD_ICONS['style']}</i><span>Style</span>" in chips
    assert f"<i>{A.FEATURE_ICONS['backing']}</i><span>Backing groove</span>" in chips


def test_the_card_style_ignores_the_groove_and_the_play_session_snapshot() -> None:
    session = custom_session("Rock")
    session["backing_groove_style"] = "Pop groove"
    session["backing_context"] = {"source": "custom_progression", "style": "Blues", "active_song_id": CUSTOM_PK}
    assert B.song_style_for_card("custom", session=session, pick_key=CUSTOM_PK) == "Rock"


def test_the_backing_card_no_longer_reads_the_play_session_style() -> None:
    import streamlit_music_practice_app as app

    src = inspect.getsource(app._render_backing_art_head_for_card)
    assert 'getattr(ctx, "style"' not in src and "progression_style" not in src
    assert "song_style_for_card" in src


def test_the_playback_groove_control_is_named_as_a_groove() -> None:
    import streamlit_music_practice_app as app

    src = inspect.getsource(app)
    block = src.split('with st.expander("Advanced playback settings"', 1)[1][:2600]
    assert "Backing groove</span>" in block and "Feel</span>" not in block
    assert 'FEATURE_ICONS.get("backing")' in block
    assert "The song keeps its own style." in block


# --- Read fresh from the source record: a re-saved style reaches the same song's card. ---------------------------

def test_a_custom_style_change_reaches_the_card_for_the_same_song() -> None:
    session = custom_session("Blues")
    assert S.saved_song_style(session, CUSTOM_PK) == "Blues"
    assert A.card_identity("Custom", B.song_style_for_card("custom", session=session, pick_key=CUSTOM_PK)).family == "blues"
    session["cpl_active_progression"]["progression_style"] = "Rock"  # the Custom page autosaves its draft here
    assert S.saved_song_style(session, CUSTOM_PK) == "Rock"
    assert A.card_identity("Custom", B.song_style_for_card("custom", session=session, pick_key=CUSTOM_PK)).family == "rock"
    session["cpl_active_progression"]["progression_style"] = "Jazz"
    assert A.card_identity("Custom", B.saved_style(session, CUSTOM_PK)).family == "jazz"


def test_a_saved_custom_song_that_is_not_open_on_the_custom_page() -> None:
    session = custom_session("Funk", saved_only=True)
    assert S.saved_song_style(session, CUSTOM_PK) == "Funk"


def test_karaoke_and_catalog_records_for_a_custom_song_read_its_saved_style() -> None:
    session = custom_session("Rock")
    record = {"title": "Blues in F minor", "artist": "Your progression", "genre": "Blues", "pick_key": CUSTOM_PK}
    assert B.catalog_card_facts(record, source_label="Custom", session=session)["style"] == "Rock"


def test_a_composition_style_change_reaches_the_card(monkeypatch) -> None:
    doc = composition_doc("Classical", rhythm_style="Pop")
    import composition_songs_bridge as bridge

    monkeypatch.setattr(bridge, "find_composition_document", lambda _s, _pk: copy.deepcopy(doc))
    pk = "composition::c1"
    assert S.saved_song_style({}, pk) == "Classical"  # Genre / Style, not the Rhythm style's default Pop
    assert A.card_identity("Composition", B.song_style_for_card("composition", session={}, pick_key=pk)).family == "classical"
    doc["metadata"]["style"] = "Jazz"
    doc["global"]["progression_style"] = "Jazz"
    i = A.card_identity("Composition", B.song_style_for_card("composition", session={}, pick_key=pk))
    assert (i.family, i.crest) == ("jazz", SONG_SOURCE_ICONS["composition"])


@pytest.mark.parametrize(
    "genre, rhythm, want",
    [("Classical", "Pop", "Classical"), ("Jazz", "Jazz", "Jazz"), ("Other", "Funk", "Funk"), (None, "Blues", "Blues"),
     ("Other", None, ""), (None, None, ""), ("", "", "")],
)
def test_composition_style_rules(genre, rhythm, want) -> None:
    assert S.composition_style(composition_doc(genre, rhythm)) == want


# --- Catalog: the catalog genre, whatever the groove. --------------------------------------------------------------

def test_a_catalog_song_keeps_its_catalog_genre() -> None:
    pk = "Rock\x1fLet It Be — The Beatles"
    assert B.song_style_for_card("song", session={"backing_groove_style": "Pop groove"}, pick_key=pk) == "Rock"
    record = {"title": "Let It Be", "artist": "The Beatles", "genre": "Pop groove", "pick_key": pk}
    assert B.catalog_card_facts(record, source_label="Catalog song", session={})["style"] == "Rock"


# --- No saved style: nothing invented, nothing written back. -------------------------------------------------------

def test_a_custom_song_without_a_saved_style_shows_the_custom_pages_default_and_nothing_is_written() -> None:
    """Option 1 (user, 2026-11-07): the Custom page shows Pop in its selector for such a song, so the cards
    show Pop artwork too; the default is display only and never written into the saved record."""
    session = custom_session(None)
    before = copy.deepcopy(session)
    style = B.song_style_for_card("custom", session=session, pick_key=CUSTOM_PK)
    assert style == S.custom_display_default() == "Pop"
    i = A.card_identity("Custom", style)
    assert (i.family, i.style_name) == ("pop", "Pop") and "src-custom" in i.classes
    assert session == before  # nothing written: not the active draft, not the saved library copy
    saved_only = custom_session(None, saved_only=True)
    assert S.saved_song_style(saved_only, CUSTOM_PK) == "Pop"  # Karaoke reads the saved copy: the same default
    assert "progression_style" not in saved_only["cpl_saved_progressions"]["Blues in F minor"]


def test_the_default_is_the_custom_pages_own() -> None:
    from custom_progression_lab import load_saved_progression

    assert load_saved_progression({"x": {"name": "x"}}, "x")["progression_style"] == S.custom_display_default()


def test_a_composition_without_a_genre_still_gets_none() -> None:
    assert S.composition_style(composition_doc("Other", None)) == ""
    assert A.card_identity("Composition", "").family == "composition"


def test_no_pick_key_means_no_style() -> None:
    assert B.song_style_for_card("custom", session=custom_session("Rock"), pick_key="") == ""
    assert S.saved_song_style({}, "custom::unknown") == ""  # no such progression: nothing to show
    assert S.saved_song_style(SimpleNamespace(), "composition::missing") == ""


def test_the_karaoke_card_looks_up_the_entry_being_sung() -> None:
    """In Karaoke the card's record names the sung entry's pick key, not the Backing context's (which can still
    be the song edited before the set), so a Custom entry's saved style or the Custom page's default shows."""
    import pathlib

    app = (pathlib.Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    assert '"pick_key": _kr_card_pick or _pick_now,' in app
    assert '_kr_card_pick = str((km.current_session_entry(st.session_state) or {}).get("pick_key") or "").strip()' in app
