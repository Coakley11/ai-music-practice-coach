"""Practice-page Ask the Music Coach entry opens the real Music Coach page."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from suite_analytical_question import render_music_coach_page_entry


def _button_by_key(*, navigate: bool = False, submit: bool = False):
    def _side_effect(*args, **kwargs):
        key = str(kwargs.get("key") or "")
        if key == "practice_open_music_coach":
            return navigate
        if key.startswith("ami_submit_music_page_"):
            return submit
        return False

    return _side_effect


def test_practice_music_coach_entry_is_visible() -> None:
    st = MagicMock()
    ss: dict = {}
    st.session_state = ss
    st.button.side_effect = _button_by_key()
    st.expander.return_value = MagicMock(
        __enter__=MagicMock(return_value=st),
        __exit__=MagicMock(return_value=False),
    )

    render_music_coach_page_entry(st, source_page="practice", session_state=ss)

    markdown = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
    assert "Ask the Music Coach" in markdown
    nav_calls = [c for c in st.button.call_args_list if c.kwargs.get("key") == "practice_open_music_coach"]
    assert nav_calls
    assert nav_calls[0].args[0] == "Ask the Music Coach"
    st.expander.assert_called()
    assert st.expander.call_args.args[0] == "Ask the Music Coach"


def test_practice_music_coach_entry_navigates_to_coach_page() -> None:
    st = MagicMock()
    ss: dict = {"studio_page": "practice"}
    st.session_state = ss
    st.button.side_effect = _button_by_key(navigate=True)
    st.expander.return_value = MagicMock(
        __enter__=MagicMock(return_value=st),
        __exit__=MagicMock(return_value=False),
    )

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
