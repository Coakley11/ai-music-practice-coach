"""The Backing card's Practice Key ▼ is the sidebar Practice Key control in a second place.

Browser acceptance (Just the Two of Us, 1500 / 390 px): the card shows the
sidebar's key; a card change moves the sidebar, banner and generated audio;
Songs, Practice and a return to Backing agree; a sidebar change shows on the
card; a change while playing plays the new key; on a phone the card ▼ is the
visible control.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _load(name: str, namespace: dict):
    tree = ast.parse(APP)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    code = compile(ast.Module(body=[fn], type_ignores=[]), "app", "exec")
    exec(code, namespace)
    return namespace[name]


class _St:
    def __init__(self, state: dict) -> None:
        self.session_state = state


def test_card_change_is_the_sidebar_widgets_own_change() -> None:
    calls: list[str] = []
    st = _St({"backing_card_practice_key::display_key_catalog_backing": "Eb",
              "display_key_catalog_backing": "C"})
    changed = _load("_backing_card_practice_key_changed", {"st": st})

    def commit() -> None:
        # The sidebar's callback sees its own widget already holding the choice.
        calls.append(st.session_state["display_key_catalog_backing"])

    changed("backing_card_practice_key::display_key_catalog_backing", "display_key_catalog_backing", commit)
    assert calls == ["Eb"]


def test_unchanged_or_empty_card_value_commits_nothing() -> None:
    calls: list[int] = []
    st = _St({"card": "C", "w": "C"})
    changed = _load("_backing_card_practice_key_changed", {"st": st})
    changed("card", "w", lambda: calls.append(1))
    st.session_state["card"] = ""
    changed("card", "w", lambda: calls.append(1))
    assert calls == []


def test_both_sidebar_practice_key_selects_offer_themselves_to_the_card() -> None:
    assert APP.count("_sidebar_pk_proxy = (") == 2
    for widget, cb in (
        ("CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET", "_on_custom_workspace_practice_key_change"),
        ("_pk_widget_key", "_on_mission_or_global_pk_change"),
    ):
        i = APP.index(f"_sidebar_pk_proxy = (\n            {widget},\n            {cb},")
        # Recorded right before that same select renders.
        nxt = APP[i:i + 600]
        assert f"key={widget}," in nxt and f"on_change={cb}," in nxt


def test_backing_card_renders_the_dropdown_not_static_text() -> None:
    i = APP.index("with _backing_card_cols[0]:")
    assert "_render_backing_card_practice_key(" in APP[i:i + 300]
    fn = APP[APP.index("def _render_backing_card_practice_key("):]
    fn = fn[: fn.index("\ndef ")]
    assert 'globals().get("_sidebar_pk_proxy")' in fn
    assert "on_change=_backing_card_practice_key_changed" in fn
    assert "conventional_key_options(" in fn
    # Without a sidebar control this run, the keys show as text as before.
    assert "active_song_key_row_html(original_key, practice_key)" in fn
