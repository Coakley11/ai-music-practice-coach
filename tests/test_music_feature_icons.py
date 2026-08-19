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


def test_practice_log_header_accent_is_not_custom_green() -> None:
    from pathlib import Path

    css = Path(__file__).resolve().parents[1].joinpath("app_ui.py").read_text(encoding="utf-8")
    log_css = css.split(".ui-studio-script-header--log")[1].split(".ui-studio-script-header--openai")[0]
    custom_block = css.split(".ui-studio-script-header--custom")[1].split(
        ".ui-studio-script-header--creative"
    )[0]
    assert "#db2777" in log_css
    assert "#059669" in custom_block
    assert "#db2777" not in custom_block
    assert "#059669" not in log_css
    assert "#0d9488" not in log_css

