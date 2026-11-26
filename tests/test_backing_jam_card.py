"""Backing's own cards for the generated jams: their facts are the jam being played, each in its own design.

User, 2026-11-25: Style Jam and the Generator still wore one generic blue card on Backing.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import backing_jam_card as card
import jam_card_art as art
from backing_owner_original_key import resolve_owner_original_key

APP = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
SECTIONS = {"Head (Jazz Swing)": ["F#m7", "B7", "Emaj7", "C#7"], "Bridge (Jazz Swing)": ["Am7", "D7", "Gmaj7", "B7"]}
POP = {"Verse (Pop)": ["C", "Am", "F", "G"]}


def _ctx(entry, sections=SECTIONS, **kw):
    generator = entry == "Jam Session Generator"
    base = dict(
        source="entry_jam", entry_mode=entry, style="Jazz Swing" if generator else "Pop", groove="Jazz swing" if generator else "Pop groove",
        ensemble="Jazz trio" if generator else "", mood="Dark", difficulty="Intermediate", groove_intensity="Medium", meter="4/4", bpm=132,
        key="E", concert_key="E", progression=[c for s in sections.values() for c in s], song_title="x",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _state(sections=SECTIONS, **kw):
    base = dict(show_chart_badge=False, chart_badge_label="", chart_badge_value="", concert_sections=sections, chart_sections=sections, instrument="Piano")
    base.update(kw)
    return SimpleNamespace(**base)


def _html(ctx, state, **kw):
    return card.jam_card_html(card.jam_card_facts(ctx, state=state, **{"groove": ctx.groove, "meter": "4/4", "bpm": 132, **kw}))


def _words(html):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", re.sub(r"<svg.*?</svg>", " ", html, flags=re.S)))


def test_each_jam_has_its_own_card_and_nothing_else_does():
    assert card.jam_card_key(_ctx("Style Jam Mode")) == card.BACKING_STYLE_JAM_CARD
    assert card.jam_card_key(_ctx("Jam Session Generator")) == card.BACKING_GENERATOR_CARD
    for source in ("mission", "song_improv", "regular_song", "custom_progression", "composition_song"):
        assert card.jam_card_key(SimpleNamespace(source=source, entry_mode="Style Jam Mode")) == ""
    assert card.jam_card_key(None) == ""
    style, generator = _html(_ctx("Style Jam Mode", POP), _state(POP)), _html(_ctx("Jam Session Generator"), _state())
    assert 'data-jam-owner="style_jam"' in style and "jc-hero-style_jam" in style
    assert 'data-jam-owner="jam_session_generator"' in generator and "jc-hero-jam_generator" in generator
    # Each wears its own identity: Style Jam the saxophone, the Generator the dice (user, 2026-11-26).
    assert card.SAX_ICON in style.split("jb-names")[0] and card.DICE_ICON not in style
    assert card.DICE_ICON in generator.split("jb-names")[0]


def test_the_generator_names_its_band_form_chords_tempo_and_settings():
    words = _words(_html(_ctx("Jam Session Generator"), _state()))
    for want in ("Jam Session Generator", "Jazz trio", "Piano", "Upright bass", "Drums", "Head (Jazz Swing)", "Bridge (Jazz Swing)",
                 "F#m7", "Gmaj7", "132 BPM", "4/4", "Dark", "Intermediate", "Medium"):
        assert want in words, want


def test_style_jam_names_its_style_sections_and_chords():
    words = _words(_html(_ctx("Style Jam Mode", POP), _state(POP)))
    for want in ("Entry & Style Jam", "Pop jam", "Verse (Pop)", "Am", "132 BPM"):
        assert want in words.replace("&amp;", "&"), want


@pytest.mark.parametrize("entry", ["Style Jam Mode", "Jam Session Generator"])
def test_the_concert_key_is_not_repeated_and_the_written_key_only_when_charts_use_it(entry):
    plain = _words(_html(_ctx(entry), _state()))
    assert "oncert" not in plain and "E major" not in plain  # the key row under the artwork names it, once
    written = _state(show_chart_badge=True, chart_badge_label="Tenor sax written key", chart_badge_value="F# major",
                     chart_sections={"Head (Jazz Swing)": ["G#m7", "C#7", "F#maj7", "D#7"]}, instrument="Saxophone")
    words = _words(_html(_ctx(entry), written))
    assert words.count("F# major") == 1 and "Tenor sax written key" in words
    assert "G#m7" in words and "F#m7" not in words  # the chords are in the key the chart says


def test_the_facts_never_come_from_the_creative_controls_or_another_song():
    src = Path("backing_jam_card.py").read_text(encoding="utf-8").split('"""', 2)[2]
    for foreign in ("improv_", "song_data", "active_catalog", "display_key"):
        assert foreign not in src


def test_a_groove_changed_on_backing_is_shown_beside_the_jams_style():
    words = _words(_html(_ctx("Jam Session Generator"), _state(), groove="Bossa nova"))
    assert "Jazz Swing" in words and "Bossa nova" in words


def test_only_the_chosen_sections_are_shown():
    words = _words(_html(_ctx("Jam Session Generator"), _state(), selected=["Bridge (Jazz Swing)"]))
    assert "Bridge" in words and "Head (Jazz Swing)" not in words


def test_a_jam_without_a_progression_says_so():
    words = _words(_html(_ctx("Style Jam Mode", {}, progression=[]), _state({})))
    assert "Generate this jam on Creative" in words


def test_text_is_escaped():
    assert "<b>x</b>" not in _html(_ctx("Style Jam Mode", {"<b>x</b>": ["C"]}), _state({"<b>x</b>": ["C"]}))


def test_the_css_only_touches_the_jam_cards():
    css = card.backing_jam_css()
    assert "\n" not in css and "url(" not in css and css.count("<style>") == 1
    body = re.sub(r"</?style>", "", css)
    for rule in re.findall(r"([^{}]+)\{", body):
        rule = rule.strip()
        if rule.startswith("@"):
            continue
        rule = re.sub(r":where\(.*\)", "", rule)
        for sel in rule.split(","):
            sel = sel.strip()
            assert "jam_card_backing" in sel or sel.startswith(('[class*="st-key-jam_card_', ".st-key-jam_card_")), sel
    assert art.STYLE_JAM_CARD + "{" not in body  # Creative's own cards keep their own rules


def test_the_page_draws_it_with_the_same_widgets():
    i = APP.index("def _create_backing_card_slots(")
    body = APP[i : i + 2600]
    assert "st.container(key=jam) if jam else st.container(key=\"backing_art_card\")" in body
    assert "jam=_backing_jam_card_key(_creative_backing_ctx) if _backing_card_kind == \"creative\" else \"\"" in APP
    assert APP.count("render_backing_jam_card(") == 1


# --- the jam's home key -------------------------------------------------------------------------------


@pytest.mark.parametrize("owner,entry,widget,pick", [
    ("jam_session_generator", "Jam Session Generator", "improv_jam_key", "creative::jam_session_generator"),
    ("style_jam", "Style Jam Mode", "improv_style_key", "creative::entry_style_jam"),
])
def test_the_original_key_is_the_key_the_jam_was_generated_in(owner, entry, widget, pick, monkeypatch):
    from creative_key_sync import apply_specialized_jam_practice_key
    from music_workflow_pending_generated_progression import consume_pending_generated_progression, queue_generated_progression_intent
    from songs.practice_key_state import set_practice_concert_key

    monkeypatch.setattr("music_persistent_state.flush_active_song_edits_and_save", lambda *_a, **_k: None)
    generator = owner == "jam_session_generator"
    s = {
        "_suite_active_workspace_id": "qa", "studio_page": "creative", "improv_intelligence_tab": "Entry & Jam", "improv_entry_mode": entry,
        widget: "E", "display_key": "Eb", "concert_key": "Eb",
        "_improv_jam_key_mounted_this_run" if generator else "_improv_style_key_mounted_this_run": True,
        "improv_ensemble": "Jazz trio", "improv_jam_style": "Jazz Swing", "improv_jam_mood": "Dark", "improv_jam_intensity": "Medium",
        "improv_jam_difficulty": "Intermediate", "improv_jam_bpm": 120, "improv_style": "Pop", "improv_mood": "Bright",
        "improv_groove": "Light", "improv_difficulty": "Intermediate", "improv_style_bpm": 100,
    }
    set_practice_concert_key(s, "E", pick_key=pick)
    queue_generated_progression_intent(s, owner=owner)
    assert consume_pending_generated_progression(s) == "done"
    ctx = SimpleNamespace(source="entry_jam", entry_mode=entry, key="E", concert_key="E", song_title="x", bound_pick_key="")
    assert resolve_owner_original_key(s, ctx).key == "E"
    apply_specialized_jam_practice_key(s, "G")  # practise it in G
    ctx.key = ctx.concert_key = "G"
    assert resolve_owner_original_key(s, ctx).key == "E"  # it is still the jam generated in E
