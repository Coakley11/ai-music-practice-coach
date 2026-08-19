"""Canonical feature icons — uniqueness and Tutorial ↔ app wiring."""

from __future__ import annotations

from app_tutorial import TUTORIAL_STEPS
from app_ui import STUDIO_PAGE_META, nav_icon_button_label
from music_feature_icons import FEATURE_ICONS, PAGE_FEATURE_KEYS, feature_label, page_feature_icon
from practice_tools_ui import PRACTICE_TOOLS
from studio_page_state import CREATIVE_TOOL_ICONS, creative_song_source_display_label


_MAJOR_UNIQUE = (
    "practice",
    "practice_setup",
    "practice_focus",
    "section_focus",
    "original_key",
    "practice_concert_key",
    "pitch_tone_tuner",
    "timing_tempo_metronome",
    "mission",
    "upload_analysis",
    "backing",
    "creative",
    "composition",
    "custom",
    "karaoke",
    "music_coach",
    "chord_song_coach",
    "charts_lyrics",
)


def _tutorial_card(step_id: str, title: str) -> dict:
    step = next(s for s in TUTORIAL_STEPS if s["id"] == step_id)
    return next(c for c in step["cards"] if c["title"] == title)


def test_major_feature_icons_are_unique() -> None:
    glyphs = [FEATURE_ICONS[k] for k in _MAJOR_UNIQUE]
    assert len(glyphs) == len(set(glyphs))


def test_page_meta_uses_canonical_page_icons() -> None:
    for page_id, concept in PAGE_FEATURE_KEYS.items():
        assert STUDIO_PAGE_META[page_id]["icon"] == FEATURE_ICONS[concept]
        assert nav_icon_button_label(page_id).startswith(FEATURE_ICONS[concept] + " ")


def test_mission_icon_matches_creative_tool_registry() -> None:
    assert CREATIVE_TOOL_ICONS["Missions"] == FEATURE_ICONS["mission"]


def test_custom_uses_writing_hand_not_plain_pencil() -> None:
    assert FEATURE_ICONS["custom"] == "✍️"
    assert creative_song_source_display_label("Custom progression").startswith("✍️ ")
    assert "✏️" not in feature_label("custom", "Custom")


def test_composition_is_not_piano_instrument() -> None:
    assert FEATURE_ICONS["composition"] == "🪶"
    assert FEATURE_ICONS["composition"] != "🎹"
    assert FEATURE_ICONS["practice_concert_key"] == "🗝️"
    assert FEATURE_ICONS["practice_concert_key"] not in {"🔄", "🎵", "🎶", "🎼", "🎹"}
    assert FEATURE_ICONS["original_key"] != FEATURE_ICONS["practice_concert_key"]
    assert FEATURE_ICONS["composition"] != FEATURE_ICONS["custom"]
    assert FEATURE_ICONS["composition"] != FEATURE_ICONS["creative"]


def test_practice_focus_and_section_focus_differ() -> None:
    assert FEATURE_ICONS["practice_focus"] == "🔍"
    assert FEATURE_ICONS["section_focus"] == "🔁"
    assert FEATURE_ICONS["practice_focus"] != FEATURE_ICONS["section_focus"]


def test_tutorial_cards_use_canonical_icons() -> None:
    expected = [
        ("setup", "Who are you playing as?", "practice_setup"),
        ("setup", "What do you want to work on?", "practice_focus"),
        ("keys", "Original Key", "original_key"),
        ("keys", "Practice / Concert Key", "practice_concert_key"),
        ("practice", "Time", "timing_tempo_metronome"),
        ("practice", "Pitch & Tone", "pitch_tone_tuner"),
        ("practice", "Section Focus", "section_focus"),
        ("composer", "Custom Progression", "custom"),
        ("composer", "Composition Studio", "composition"),
        ("recording", "One take", "upload_analysis"),
        ("recording", "Mission take", "mission"),
        ("saving", "Custom songs", "custom"),
        ("saving", "Charts & lyrics", "charts_lyrics"),
        ("which_tool", "Accompaniment", "backing"),
        ("which_tool", "Create my own progression", "custom"),
        ("which_tool", "Write a fuller song idea", "composition"),
        ("which_tool", "Feedback on one take", "upload_analysis"),
        ("which_tool", "Guidance", "music_coach"),
        ("which_tool", "Sing with lyrics", "karaoke"),
        ("welcome", "Practice", "practice"),
        ("welcome", "Create", "creative"),
    ]
    for step_id, title, concept in expected:
        card = _tutorial_card(step_id, title)
        assert card["icon"] == FEATURE_ICONS[concept], (step_id, title, concept)


def test_practice_tools_time_pitch_uses_both_canonical_icons() -> None:
    tool = next(t for t in PRACTICE_TOOLS if t.tool_id == "time_and_pitch")
    assert FEATURE_ICONS["timing_tempo_metronome"] in tool.icon
    assert FEATURE_ICONS["pitch_tone_tuner"] in tool.icon
    transpose = next(t for t in PRACTICE_TOOLS if t.tool_id == "transpose")
    assert transpose.icon == FEATURE_ICONS["transpose_helpers"]
    assert transpose.icon != FEATURE_ICONS["composition"]


    coach = next(t for t in PRACTICE_TOOLS if t.tool_id == "coach")
    assert coach.icon == FEATURE_ICONS["chord_song_coach"]
    assert coach.icon != FEATURE_ICONS["practice_setup"]


def test_page_feature_icon_helper() -> None:
    assert page_feature_icon("composer") == FEATURE_ICONS["composition"]
    assert page_feature_icon("analysis") == FEATURE_ICONS["upload_analysis"]
    assert page_feature_icon("custom") == FEATURE_ICONS["custom"]


def test_practice_setup_and_session_identities() -> None:
    assert FEATURE_ICONS["practice_setup"] == "🎸"
    assert FEATURE_ICONS["chord_song_coach"] == "📖"
    assert FEATURE_ICONS["chord_song_coach"] not in {
        FEATURE_ICONS["practice_setup"],
        FEATURE_ICONS["songs"],
        FEATURE_ICONS["music_coach"],
        FEATURE_ICONS["creative"],
        FEATURE_ICONS["karaoke"],
        FEATURE_ICONS["composition"],
    }
    assert FEATURE_ICONS["session"] == "⏱️"
    assert FEATURE_ICONS["session"] == FEATURE_ICONS["timing_tempo_metronome"]


def test_active_song_key_row_is_plain_text() -> None:
    from app_ui import active_song_key_row_html

    html = active_song_key_row_html("G", "G")
    assert "Original key" in html
    assert "Practice / Concert Key" in html
    assert FEATURE_ICONS["original_key"] not in html
    assert FEATURE_ICONS["practice_concert_key"] not in html


def test_key_badges_keep_canonical_icons() -> None:
    from app_ui import studio_song_meta_badges_html

    html = studio_song_meta_badges_html(original_key="G", display_key="A")
    assert FEATURE_ICONS["original_key"] in html
    assert FEATURE_ICONS["practice_concert_key"] in html


def test_tutorial_choose_clarinet_uses_practice_setup_not_style_jam() -> None:
    from music_feature_icons import FEATURE_ICONS

    which = next(s for s in TUTORIAL_STEPS if s.get("id") == "which_tool")
    journey = which.get("journey") or []
    clarinet = next(item for item in journey if "Choose Clarinet" in str(item))
    assert clarinet.startswith(f"{FEATURE_ICONS['practice_setup']} ")
    assert "🎷" not in clarinet


def test_charts_lyrics_identity() -> None:
    assert FEATURE_ICONS["charts_lyrics"] == "📝"
    assert feature_label("charts_lyrics", "Song content editor").startswith("📝 ")
    assert FEATURE_ICONS["charts_lyrics"] != FEATURE_ICONS["karaoke"]
    assert FEATURE_ICONS["charts_lyrics"] != FEATURE_ICONS["custom"]
    assert FEATURE_ICONS["charts_lyrics"] != FEATURE_ICONS["composition"]


def test_active_page_nav_css_uses_studio_page_accents() -> None:
    from app_ui import STUDIO_PAGE_ACCENTS, _studio_page_active_nav_css, studio_page_accent

    css = _studio_page_active_nav_css()
    assert studio_page_accent("log") == "#0d9488"
    assert studio_page_accent("analysis") == "#e11d48"
    assert studio_page_accent("composer") == "#0f172a"
    assert studio_page_accent("creative") == "#c026d3"
    assert studio_page_accent("picker") == "#4f46e5"
    assert studio_page_accent("backing") == "#2563eb"
    # Top nav: page word in page color
    assert ".ui-nav-art-cell.nav-log.is-active .ui-nav-script-label" in css
    assert "color: #0d9488" in css
    # Top nav Open stays red for every page
    assert "background: #dc2626 !important" in css
    assert 'st-key-studio_quick_nav_btn_log"' not in css
    # Sidebar: selected label in page color (not filled button)
    assert ".ui-sb-nav-wrap .sb-nav-log.nav-btn-active button" in css
    assert "color: #0d9488 !important" in css
    assert "background: rgba(255, 255, 255, 0.06)" in css
    for page_id, accent in STUDIO_PAGE_ACCENTS.items():
        assert f".ui-nav-art-cell.nav-{page_id}.is-active .ui-nav-script-label" in css
        assert f".ui-sb-nav-wrap .sb-nav-{page_id}.nav-btn-active button" in css
        assert accent in css


def test_practice_log_header_accent_is_teal_not_upload_pink() -> None:
    from app_ui import STUDIO_PAGE_ACCENTS, _studio_page_header_theme_css

    assert STUDIO_PAGE_ACCENTS["log"] == "#0d9488"
    assert STUDIO_PAGE_ACCENTS["analysis"] == "#e11d48"
    header_css = _studio_page_header_theme_css()
    assert "--ui-studio-header-accent: #0d9488" in header_css
    assert "--ui-studio-header-accent: #e11d48" in header_css
    assert "--ui-studio-header-accent: #0f172a" in header_css
    assert "--ui-studio-header-accent: #c026d3" in header_css


def test_practice_log_header_accent_is_not_custom_green() -> None:
    from app_ui import STUDIO_PAGE_ACCENTS

    assert STUDIO_PAGE_ACCENTS["log"] == "#0d9488"
    assert STUDIO_PAGE_ACCENTS["custom"] == "#059669"
    assert STUDIO_PAGE_ACCENTS["log"] != STUDIO_PAGE_ACCENTS["custom"]
    assert STUDIO_PAGE_ACCENTS["analysis"] == "#e11d48"
    assert STUDIO_PAGE_ACCENTS["log"] != STUDIO_PAGE_ACCENTS["analysis"]

