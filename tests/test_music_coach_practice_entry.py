"""Practice-page Ask the Music Coach entry opens the real Music Coach page."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from suite_analytical_question import render_music_coach_page_entry


def test_practice_music_coach_entry_is_visible() -> None:
    st = MagicMock()
    ss: dict = {}
    st.session_state = ss
    st.button.return_value = False

    render_music_coach_page_entry(st, source_page="practice", session_state=ss)

    markdown = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
    assert "Ask the Music Coach" in markdown
    st.button.assert_called()
    assert st.button.call_args.args[0] == "Ask the Music Coach"
    assert st.button.call_args.kwargs.get("key") == "practice_open_music_coach"


def test_practice_music_coach_entry_navigates_to_coach_page() -> None:
    st = MagicMock()
    ss: dict = {"studio_page": "practice"}
    st.session_state = ss
    st.button.return_value = True

    with patch("app_ui.navigate_studio_page") as nav:
        render_music_coach_page_entry(st, source_page="practice", session_state=ss)

    nav.assert_called_once_with(ss, "openai")
    st.rerun.assert_called_once()


def test_practice_page_still_calls_music_coach_entry() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(
        encoding="utf-8"
    )
    assert "render_music_coach_page_entry" in text
    assert "Ask the Music Coach" in Path(__file__).resolve().parents[1].joinpath(
        "suite_analytical_question.py"
    ).read_text(encoding="utf-8")
