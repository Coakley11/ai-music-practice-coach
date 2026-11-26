"""Backing-card UI round (user, 2026-11-26).

1  The jam cards are Backing cards: their artwork is the band that plays (a trio three instruments, a quintet five),
   their style, their energy; Style Jam wears its saxophone, the Generator its dice.
3  Style logo for a style, groove logo for a groove; Charts in = chart icon, Shape key = guitar, Written key = the
   instrument.
4  Shape Mode names the concert key and the shape key together.
5  The lead-sheet control is compact. 6  The highlight follows what is heard. 7  Practice Melody's controls are small.
"""

from __future__ import annotations

import re
import xml.dom.minidom
from pathlib import Path
from types import SimpleNamespace

import pytest

import backing_jam_card as card
import jam_backing_art as stage
from music_feature_icons import (
    CHART_ICON, FEATURE_ICONS, INSTRUMENT_ICONS, chart_key_badge, groove_logo, semantic_field_icon, style_logo,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _instruments(svg: str) -> list[str]:
    return re.findall(r'data-instrument="([a-z_]+)"', svg)


# --- 1. the artwork is the band ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "playing,not_yet,count",
    [
        (["Piano", "Upright bass", "Drums"], [], 3),
        (["Piano", "Upright bass", "Drums"], ["Tenor sax"], 4),
        (["Piano", "Upright bass", "Drums", "Trumpet", "Tenor sax"], [], 5),
        (["Electric guitar", "Bass", "Drums"], [], 3),
        (["Keys", "Drums"], [], 2),
    ],
)
def test_the_generator_stage_draws_each_member_of_the_band(playing, not_yet, count):
    svg = stage.jam_stage_svg(stage.GENERATOR, playing=playing, not_yet=not_yet, style="Jazz")
    assert len(_instruments(svg)) == count
    assert svg.count("jb-ghost") == len(not_yet)  # a member the backing cannot play yet stands in outline
    xml.dom.minidom.parseString(svg)  # well-formed, one line
    assert "\n" not in svg


def test_a_quintet_shows_its_horns_by_instrument():
    svg = stage.jam_stage_svg(stage.GENERATOR, playing=["Piano", "Upright bass", "Drums", "Trumpet", "Tenor sax"])
    assert sorted(_instruments(svg)) == sorted(["keys", "upright_bass", "drums", "trumpet", "sax"])


def test_style_jam_keeps_its_saxophone_at_the_front():
    svg = stage.jam_stage_svg(stage.STYLE_JAM, playing=["Keys", "Bass", "Drums"], featured="Saxophone")
    assert "sax" in _instruments(svg) and len(_instruments(svg)) == 4


@pytest.mark.parametrize("mood,intensity,level", [("Mellow", "Light", 0), ("Mellow", "Medium", 0), ("", "Medium", 1),
                                                  ("Energetic", "Medium", 2), ("Bright", "Heavy", 2), ("Dark", "Heavy", 1)])
def test_energy_follows_intensity_and_mood(mood, intensity, level):
    assert stage.energy_level(mood, intensity) == level


def test_a_calm_jam_is_lit_softly_and_an_intense_one_has_every_light_and_the_sound_in_the_air():
    calm = stage.jam_stage_svg(stage.GENERATOR, playing=["Piano", "Drums"], mood="Mellow", intensity="Light")
    loud = stage.jam_stage_svg(stage.GENERATOR, playing=["Piano", "Drums"], mood="Energetic", intensity="Heavy")
    assert calm.count("<polygon") < loud.count("<polygon")
    assert 'stroke-linecap="round" opacity' not in calm and 'stroke-linecap="round" opacity' in loud


@pytest.mark.parametrize("style,groove,family", [("Latin", "Bossa nova", "latin"), ("Bossa Nova", "", "latin"),
                                                 ("Jazz Swing", "", "jazz"), ("Rock", "", "rock"), ("Lo-fi", "", "lofi"),
                                                 ("", "Funk groove", "funk")])
def test_the_stage_takes_the_jams_style(style, groove, family):
    assert stage.style_family(style, groove) == family
    assert f"jb-f-{family}" in stage.jam_stage_svg(stage.STYLE_JAM, style=style, groove=groove)


def _ctx(entry="Jam Session Generator", **kw):
    base = dict(source="entry_jam", entry_mode=entry, style="Latin", groove="Bossa nova", ensemble="Jazz trio", mood="Mellow",
                difficulty="Beginner", groove_intensity="Light", meter="4/4", bpm=120, progression=["Dm7", "G7", "Cmaj7"])
    base.update(kw)
    return SimpleNamespace(**base)


def _state(**kw):
    sections = {"A": ["Dm7", "G7", "Cmaj7", "Cmaj7"]}
    base = dict(show_chart_badge=False, chart_badge_label="", chart_badge_value="", concert_sections=sections, chart_sections=sections,
                instrument="Piano", chart_mode="concert", shape_key="", practice_concert_key="C")
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_card_names_the_band_size_and_wears_the_dice_style_and_groove_logos():
    facts = card.jam_card_facts(_ctx(), state=_state(), groove="Bossa nova", meter="4/4", bpm=120)
    head = card.jam_card_head_html(facts)
    assert "Trio · 3 players" in head and card.DICE_ICON in head
    assert style_logo("Latin") in head and groove_logo("Bossa nova") in head
    assert len(_instruments(head)) == 3


def test_style_and_groove_are_labelled_tiles_on_the_artwork_and_never_repeated_below():
    facts = card.jam_card_facts(_ctx(), state=_state(), groove="Bossa nova", meter="4/4", bpm=120)
    head, body = card.jam_card_head_html(facts), card.jam_card_facts_html(facts)
    assert f'title="Style: Latin"><i>Style</i><b>{style_logo("Latin")}</b><small>Latin</small>' in head
    assert f'title="Groove: Bossa nova"><i>Groove</i><b>{groove_logo("Bossa nova")}</b><small>Bossa nova</small>' in head
    assert "Mellow · Light intensity · 120 BPM" in head
    for twice in ("<span>Style</span>", "<span>Groove</span>", "<span>Mood</span>", "<span>Intensity</span>", "Your band · Jazz trio"):
        assert twice not in body, twice  # no fact or heading said twice
    assert "<span>Meter</span>" in body and "<span>Level</span>" in body
    assert "<details class=\"jb-prog\">" in body  # the chords are folded away, not a block of text


def test_a_member_whose_sound_is_off_is_grey_tagged_and_named_as_not_heard(monkeypatch):
    import backing_horns

    monkeypatch.setattr(backing_horns, "enabled", lambda: False)
    svg = stage.jam_stage_svg(stage.GENERATOR, playing=["Piano", "Upright bass", "Drums"], not_yet=["Tenor sax"], mood="Energetic")
    ghost = svg[svg.index('class="jb-ghost"') - 120:]
    assert 'filter="url(#jb-mute)"' in ghost[:400] and "SOUND OFF" in svg
    facts = card.jam_card_facts(_ctx(ensemble="Jazz quartet", style="Jazz"), state=_state(), groove="Jazz swing", meter="4/4", bpm=120)
    if facts["not_yet"]:  # the horn switch is off in tests
        body = card.jam_card_facts_html(facts)
        assert "🔇 sound off" in body and "recorded horns are switched off" in body
    assert card.silent_reason("Latin percussion") == "no percussion sound yet"


def test_a_shape_chart_key_on_the_card_is_the_shape_key_with_the_guitar_and_the_capo():
    st = _state(show_chart_badge=True, chart_badge_label="Shape key", chart_badge_value="A major", chart_mode="shape", shape_key="A",
                instrument="Guitar")
    icon, label, value = card.chart_key_chip(card.jam_card_facts(_ctx(), state=st, groove="Bossa nova", meter="4/4", bpm=120))
    assert (icon, label, value) == (INSTRUMENT_ICONS["Guitar"], "Shape key", "A major · capo 3")


def test_a_written_key_on_the_card_wears_the_instrument():
    st = _state(show_chart_badge=True, chart_badge_label="Written key", chart_badge_value="D major", chart_mode="written",
                instrument="Tenor Saxophone")
    icon, label, _v = card.chart_key_chip(card.jam_card_facts(_ctx(), state=st, groove="Bossa nova", meter="4/4", bpm=120))
    assert icon == INSTRUMENT_ICONS["Saxophone"] and label == "Written key"


def test_the_card_says_what_backing_is_set_to_do():
    s = {"backing_key_cycle_enabled_ui": "On", "backing_key_cycle_step_ui": "Fourth", "backing_key_cycle_direction_ui": "Up",
         "backing_track_scope": "Selected sections", "backing_track_loops": 3}
    words = " ".join(t for _i, t in card.backing_state_items(s, sheet_visible=False, sheet_on_play=True))
    assert "Key Cycling on · fourth up" in words and "Lead sheet opens on Play" in words and "Selected sections × 3" in words


def test_the_jam_card_draws_the_lead_sheet_settings_and_key_cycling_row():
    body = APP[APP.index("def _render_backing_art_actions("):]
    body = body[:body.index("\ndef ")]
    assert "_backing_art_identity is None and not _backing_jam_card_on" in body
    assert "backing_state_items(st.session_state" in body
    assert "facts_slot=_backing_card_cols[3]" in APP


# --- 3. icons ----------------------------------------------------------------------------------------------------


def test_style_and_groove_logos():
    assert style_logo("Latin") == "\U0001F483" and groove_logo("Bossa nova") == "\U0001F334"
    assert style_logo("Jazz Swing") == "\U0001F3B7" and groove_logo("Rock groove") == "\U0001F918"
    for jam_style in ("Fusion", "Modal Vamp", "Lo-fi", "Samba"):
        assert style_logo(jam_style), jam_style  # every Style Jam style has its own logo
    assert style_logo("") == "" and groove_logo("") == ""


@pytest.mark.parametrize("mode,label,instrument,icon,text", [
    ("shape", "", "Guitar", INSTRUMENT_ICONS["Guitar"], "Shape key"),
    ("", "Charts in", "Guitar", CHART_ICON, "Charts in"),
    ("written", "", "Tenor Saxophone", INSTRUMENT_ICONS["Saxophone"], "Written key"),
    ("written", "", "Bb Trumpet", INSTRUMENT_ICONS["Trumpet"], "Written key"),
    ("written", "", "Clarinet", INSTRUMENT_ICONS["Clarinet"], "Written key"),
    ("", "Shape Key", "", INSTRUMENT_ICONS["Guitar"], "Shape key"),
])
def test_the_label_decides_the_chart_key_icon(mode, label, instrument, icon, text):
    assert chart_key_badge(mode, label=label, instrument=instrument) == (icon, text)


def test_the_field_icons():
    assert semantic_field_icon("charts") == FEATURE_ICONS["chord_chart"]
    assert semantic_field_icon("shape_key") == INSTRUMENT_ICONS["Guitar"]
    assert semantic_field_icon("groove") != semantic_field_icon("style")


# --- 4. Shape Mode names both keys ---------------------------------------------------------------------------------


def test_shape_mode_names_the_concert_key_and_the_shape_key():
    from musician_coaching import playback_settings_working_line as line

    assert line(practice_key="C", bpm=100, shape_key="E").startswith(
        "You're working in concert key C major, using shape key E major (capo 8), at 100 BPM")
    assert line(practice_key="C", bpm=100) == "You're working in C major at 100 BPM (4/4, Pop)."
    assert line(practice_key="C", bpm=100, shape_key="C").startswith("You're working in C major at")  # no capo: one key


def test_the_backing_sheet_header_names_both_keys():
    from songs.backing_chart import render_backing_chord_chart

    html = render_backing_chord_chart("Song", {"title": "Song", "key": "C"}, {"V": ["C", "F", "G", "C"]}, display_key="C",
                                      shape_sections={"V": ["C", "F", "G", "C"]}, capo_fret=3, capo_shape_key="A")
    assert "Concert Key: C" in html and "🎸 Shape Key: A major · capo 3" in html
    assert "working in concert key C major, using shape key A major (capo 3)" in html


def test_the_card_key_and_the_creative_line_name_the_shape_key_under_the_concert_key():
    body = APP[APP.index("def _backing_card_shape_caption("):]
    body = body[:body.index("\ndef ")]
    assert 'f"Concert key · 🎸 shape key {shape_chart_label_for_concert(concert, shape)}, capo {fret}"' in body
    assert "_shape_cap = _backing_card_shape_caption(" in APP
    import creative_key_sync as cks

    out = []

    class _St:
        def markdown(self, text, **_k):
            out.append(re.sub("<[^>]+>", "", text))

    s = {"instrument": "Guitar", "guitar_capo_enabled": True, "guitar_capo_shape_key": "A", "concert_key": "C", "display_key": "C"}
    cks.render_creative_progression_block(_St(), s, {"Verse": ["C", "F", "G", "C"]}, concert_key="C")
    assert "Practice concert key: C · 🎸 Shape key: A major (capo 3)" in " ".join(out)


# --- 5. compact lead sheet -------------------------------------------------------------------------------------------


def test_the_lead_sheet_control_is_compact_and_not_doubled_on_a_card():
    i = APP.index("_ls_compact_css = (")
    css = APP[i:i + 2200]
    assert "min-height:30px" in css and "border-radius:999px" in css and "width:auto" in css
    assert "_ls_hide_row = bool(_ls_card_has_button and not _leadsheet_open)" in APP
    assert ":has(.st-key-backing_leadsheet_show_btn){display:none" in css


# --- 6. the highlight follows what is heard --------------------------------------------------------------------------


def test_the_highlight_follows_what_is_heard_not_the_media_clock():
    i = APP.index("function updateHighlight(force = false)")
    head = APP[i:i + 400]
    assert "audioTime = Math.max(0, audioTime - heardLatency());" in head and "measureHeardLatency();" in head
    helper = APP[APP.index("function measureHeardLatency()"):i]
    assert "outputLatency" in helper and "Math.min(0.5" in helper and "ctx.close()" in helper
    kc = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
    j = kc.index("function kcUpdateChordHighlight(force)")
    assert "__bkHeardLatency" in kc[j:j + 900]
    pm = APP[APP.index("      function tick() {{"):]
    assert "(Date.now() - (pos.ts || 0)) / 1000" in pm[:900]  # the Practice Melody staff is carried forward to now


# --- 7. compact Practice Melody ------------------------------------------------------------------------------------


def test_practice_melody_controls_are_a_slim_row_of_small_buttons():
    panel = (ROOT / "practice_melody_panel.py").read_text(encoding="utf-8")
    labels = re.findall(r'st\.button\(\s*f?"([^"]+)"', panel)
    assert "◀" in labels and "▶" in labels and "☆ Keep" in labels and "★ Kept" in labels
    assert not [x for x in labels if "Previous" in x or "Next" in x or "Generate Another Melody" in x]
    assert 'horizontal=True' in panel and "st.popover(" in panel and 'key="backing_practice_melody_steps"' in panel
    assert "FEATURE_ICONS['practice_melody_generated']} Practice Melody" in APP


def _melody_row_app():
    import streamlit as st

    import practice_melody_library as lib
    import practice_melody_panel as panel

    st.session_state.setdefault("at", 1)
    st.session_state.setdefault("count", 3)
    st.session_state.setdefault("calls", [])
    lib.alternatives = lambda s, i, r: (st.session_state["at"], st.session_state["count"])
    lib.viewing = lambda s, i: ""
    lib.kept_melodies = lambda s, i: []

    def choose(**kw):
        st.session_state["calls"].append(kw)
        if kw.get("another"):
            st.session_state["count"] += 1
            st.session_state["at"] = st.session_state["count"] - 1
        else:
            st.session_state["at"] = min(max(0, st.session_state["at"] + kw["step"]), st.session_state["count"] - 1)

    panel.render_melody_controls(st, identity="x", recipe="r", melody=None, sections={"A": ["C"]}, section_order=["A"],
                                 sections_key="k", choose=choose)


def test_next_selects_an_existing_melody_and_only_new_melody_composes_one():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_melody_row_app).run(timeout=60)
    assert not at.exception
    at.button(key="backing_practice_melody_next").click().run()
    assert at.session_state["at"] == 2 and at.session_state["count"] == 3  # moved to the existing third; nothing composed
    assert at.button(key="backing_practice_melody_next").disabled  # at the newest, ▶ never composes
    at.button(key="backing_practice_melody_another").click().run()
    assert (at.session_state["at"], at.session_state["count"]) == (3, 4)  # a deliberate new one, the others kept
    at.button(key="backing_practice_melody_prev").click().run()
    assert at.session_state["calls"] == [{"step": 1}, {"another": True}, {"step": -1}]
