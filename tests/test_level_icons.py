"""The three proficiency levels share one visual identity, and it stays presentation only."""

from __future__ import annotations

import ast
import pathlib

import pytest
from streamlit.testing.v1 import AppTest

from practice_ui_labels import LEVEL_ICONS, decorate_levels, level_icon, level_label

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every widget in the app where a person chooses a proficiency level: file -> number of such widgets.
LEVEL_WIDGETS = {
    "streamlit_music_practice_app.py": 3,  # sidebar, setup row, Songs chart level filter
    "app_ui.py": 1,
    "improvisation_intelligence_ui.py": 1,  # Style Jam Difficulty
    "practice_setup_controls.py": 1,
    "song_coach_ui.py": 1,
    "upload_analysis_setup_ui.py": 1,
    "youtube_ui.py": 1,
}
LEVEL_OPTION_NAMES = {"LEVEL_OPTIONS", "DIFFICULTY_LEVELS", "LEVELS", "_opts_level", "level_options"}


def test_the_three_icons() -> None:
    assert LEVEL_ICONS == {"Beginner": "🌱", "Intermediate": "🚀", "Advanced": "🧠"}


@pytest.mark.parametrize(
    "value, shown",
    [
        ("Beginner", "🌱 Beginner"),
        ("Intermediate", "🚀 Intermediate"),
        ("Advanced", "🧠 Advanced"),
        ("Any level", "Any level"),
        ("easy", "easy"),
        ("", ""),
        (None, ""),
    ],
)
def test_level_label(value: object, shown: str) -> None:
    assert level_label(value) == shown


def test_level_icon_unknown_is_empty() -> None:
    assert level_icon("Any level") == ""
    assert level_icon(None) == ""


@pytest.mark.parametrize(
    "text, shown",
    [
        ("Beginner / Intermediate / Advanced", "🌱 Beginner / 🚀 Intermediate / 🧠 Advanced"),
        ("Intermediate–Advanced", "🚀 Intermediate–🧠 Advanced"),
        ("Beginner-friendly", "🌱 Beginner-friendly"),
        ("Intermediate · Saxophone · Guide Tones", "🚀 Intermediate · Saxophone · Guide Tones"),
        ("No level here", "No level here"),
    ],
)
def test_decorate_levels(text: str, shown: str) -> None:
    assert decorate_levels(text) == shown


def test_decorate_levels_never_doubles_an_icon() -> None:
    once = decorate_levels("Beginner / Intermediate / Advanced")
    assert decorate_levels(once) == once


def _uses_level_options(call: ast.Call) -> bool:
    if len(call.args) < 2 and not any(k.arg == "options" for k in call.keywords):
        return False
    opts = call.args[1] if len(call.args) >= 2 else next(k.value for k in call.keywords if k.arg == "options")
    if isinstance(opts, ast.Call) and opts.args:  # list(LEVELS)
        opts = opts.args[0]
    if isinstance(opts, ast.Name):
        return opts.id in LEVEL_OPTION_NAMES
    if isinstance(opts, ast.List):
        return any(isinstance(e, ast.Constant) and e.value == "Beginner" for e in opts.elts)
    return False


@pytest.mark.parametrize("filename, expected", sorted(LEVEL_WIDGETS.items()))
def test_every_level_widget_shows_the_icons(filename: str, expected: int) -> None:
    """A new level selector without the icons fails here rather than slipping through."""
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"selectbox", "radio", "pills", "segmented_control", "select_slider"}
            and _uses_level_options(node)
        ):
            found.append(node)
    assert len(found) == expected, f"{filename}: expected {expected} level widgets, found {len(found)}"
    for call in found:
        fmt = next((k.value for k in call.keywords if k.arg == "format_func"), None)
        assert isinstance(fmt, ast.Name) and fmt.id == "level_label", f"{filename}:{call.lineno} has no level_label"


def test_tutorial_teaches_the_same_icons() -> None:
    text = (ROOT / "app_tutorial.py").read_text(encoding="utf-8")
    for name, icon in LEVEL_ICONS.items():
        assert f"{icon} {name}" in text


def _selector_app() -> None:
    import streamlit as st

    from practice_ui_labels import level_label

    st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"], key="level", format_func=level_label)
    st.radio("Radio level", ["Beginner", "Intermediate", "Advanced"], key="radio_level", format_func=level_label)
    st.write(f"stored={st.session_state.level}")


def test_widgets_show_icons_but_keep_the_plain_value() -> None:
    at = AppTest.from_function(_selector_app)
    at.session_state["level"] = "Intermediate"
    at.run()
    box = at.selectbox(key="level")
    assert box.options == ["🌱 Beginner", "🚀 Intermediate", "🧠 Advanced"]
    assert box.value == "Intermediate"

    box.set_value("Advanced").run()
    assert not at.exception
    assert at.session_state["level"] == "Advanced"
    assert at.selectbox(key="level").value == "Advanced"
    assert at.markdown[0].value == "stored=Advanced"
    assert at.radio(key="radio_level").options == ["🌱 Beginner", "🚀 Intermediate", "🧠 Advanced"]
