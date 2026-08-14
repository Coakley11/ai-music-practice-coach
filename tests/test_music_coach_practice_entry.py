"""Practice-page Ask the Music Coach: one card, one question field, canonical AMI submit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from suite_analytical_question import render_music_coach_page_entry


def _button_by_key(*, ask: bool = False):
    def _side_effect(*args, **kwargs):
        key = str(kwargs.get("key") or "")
        if key == "ami_submit_music_practice_page":
            return ask
        return False

    return _side_effect


def test_practice_music_coach_entry_is_visible() -> None:
    st = MagicMock()
    ss: dict = {}
    st.session_state = ss
    st.button.side_effect = _button_by_key()
    st.text_area.return_value = ""

    render_music_coach_page_entry(st, source_page="practice", session_state=ss)

    markdown = " ".join(str(c.args[0]) for c in st.markdown.call_args_list if c.args)
    assert "Ask the Music Coach" in markdown
    assert st.text_area.call_count == 1
    ask_buttons = [
        c for c in st.button.call_args_list if c.args and "Ask the Music Coach" in str(c.args[0])
    ]
    assert len(ask_buttons) == 1
    assert ask_buttons[0].kwargs.get("key") == "ami_submit_music_practice_page"
    open_buttons = [
        c for c in st.button.call_args_list if c.args and "Open full Music Coach" in str(c.args[0])
    ]
    assert open_buttons == []
    st.expander.assert_not_called()


def test_practice_music_coach_entry_submits_via_canonical_ami_pipeline() -> None:
    st = MagicMock()
    ss: dict = {"studio_page": "practice", "practice_focus_section": "Verse"}
    st.session_state = ss
    st.button.side_effect = _button_by_key(ask=True)
    st.text_area.return_value = "Give me an improvisation over the verse."
    extra = {"song": "Motion Tune", "coach_page": "practice"}
    source = {"page": "practice", "song": "Motion Tune"}

    with patch(
        "suite_analytical_question._execute_coach_question_submit",
        return_value={"routed": True},
    ) as submit:
        render_music_coach_page_entry(
            st,
            source_page="practice",
            session_state=ss,
            context_extra_builder=lambda: extra,
            source_state_builder=lambda: source,
        )

    submit.assert_called_once()
    kwargs = submit.call_args.kwargs
    assert kwargs["question_raw"] == "Give me an improvisation over the verse."
    assert kwargs["source_app"] == "music"
    assert kwargs["source_page"] == "practice"
    assert kwargs["surface_tag"] == "practice_page"
    assert kwargs["context_extra_builder"]() == extra
    assert kwargs["source_state_builder"]() == source
    st.expander.assert_not_called()


def test_practice_page_still_calls_music_coach_entry() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(
        encoding="utf-8"
    )
    assert "render_music_coach_page_entry" in text
    saq = Path(__file__).resolve().parents[1].joinpath("suite_analytical_question.py").read_text(
        encoding="utf-8"
    )
    assert "Ask the Music Coach" in saq
    entry_fn = saq.split("def render_music_coach_page_entry")[1].split("def render_music_coach_sidebar_entry")[0]
    assert 'expander("Ask the Music Coach"' not in entry_fn
    assert "_execute_coach_question_submit" in entry_fn
    assert "text_area" in entry_fn
    assert "Open full Music Coach" not in entry_fn
    assert "practice_open_music_coach" not in entry_fn
    assert entry_fn.count("Ask the Music Coach") >= 2
