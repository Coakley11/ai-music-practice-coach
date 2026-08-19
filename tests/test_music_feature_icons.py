"""Canonical feature icons — uniqueness and Tutorial ↔ app wiring."""

from __future__ import annotations

from app_tutorial import TUTORIAL_STEPS
from app_ui import STUDIO_PAGE_META, nav_icon_button_label
from music_feature_icons import FEATURE_ICONS, PAGE_FEATURE_KEYS, feature_label, page_feature_icon
from practice_tools_ui import PRACTICE_TOOLS
from studio_page_state import CREATIVE_TOOL_ICONS, creative_song_source_display_label


_MAJOR_UNIQUE = (
    "practice",
    "practice_focus",
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


def test_composition_keeps_piano_and_keys_do_not() -> None:
    piano = FEATURE_ICONS["composition"]
    assert piano == "🎹"
    assert FEATURE_ICONS["original_key"] != piano
    assert FEATURE_ICONS["practice_concert_key"] != piano
    assert FEATURE_ICONS["practice_concert_key"] != FEATURE_ICONS["songs"]


def test_tutorial_cards_use_canonical_icons() -> None:
    expected = [
        ("setup", "What do you want to work on?", "practice_focus"),
        ("keys", "Original Key", "original_key"),
        ("keys", "Practice / Concert Key", "practice_concert_key"),
        ("practice", "Time", "timing_tempo_metronome"),
        ("practice", "Pitch & Tone", "pitch_tone_tuner"),
        ("composer", "Custom Progression", "custom"),
        ("composer", "Composition Studio", "composition"),
        ("recording", "One take", "upload_analysis"),
        ("recording", "Mission take", "mission"),
        ("which_tool", "Accompaniment", "backing"),
        ("which_tool", "Create my own progression", "custom"),
        ("which_tool", "Write a fuller song idea", "composition"),
        ("which_tool", "Feedback on one take", "upload_analysis"),
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


def test_page_feature_icon_helper() -> None:
    assert page_feature_icon("composer") == FEATURE_ICONS["composition"]
    assert page_feature_icon("analysis") == FEATURE_ICONS["upload_analysis"]
    assert page_feature_icon("custom") == FEATURE_ICONS["custom"]
