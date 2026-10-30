"""The Backing card's Practice Key ▼ is the Backing owner's Practice Key widget itself.

On Backing the sidebar renders no second copy, only a slot for runs that draw
no card. A mirrored second widget (card and sidebar, each written from the
other's change) sent its stale frontend value back during Key Cycling's
reruns and reverted the key; one widget has one frontend value.

Browser acceptance (Just the Two of Us, 1500 / 390 px): the card shows the
Backing key; a card change moves the banner and generated audio; Songs,
Practice and a return to Backing agree; a change while Key Cycling plays
re-anchors the cycle and stays; Practice and other pages keep their sidebar
control.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _load(names: list[str], namespace: dict) -> dict:
    tree = ast.parse(APP)
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=fns, type_ignores=[]), "app", "exec"), namespace)
    return namespace


def _fn(name: str) -> str:
    body = APP[APP.index(f"def {name}("):]
    return body[: body.index("\ndef ")]


class _Slot:
    def __init__(self, log: list) -> None:
        self.log = log

    def __enter__(self):
        self.log.append("slot")
        return self

    def __exit__(self, *_a):
        return False


class _St:
    def __init__(self) -> None:
        self.calls: list = []

    def selectbox(self, label, options, **kw):
        self.calls.append((label, list(options), kw))


def _proxy(log: list) -> dict:
    return {
        "key": "display_key_catalog_backing",
        "on_change": "commit",
        "options": ["C", "Db", "D"],
        "label": "Practice / Concert Key",
        "slot": _Slot(log),
        "rendered": False,
    }


def test_owner_select_is_the_owner_widget_with_its_own_commit() -> None:
    st = _St()
    ns = _load(["_render_backing_pk_owner_select"], {"st": st, "Any": object})
    proxy = _proxy([])
    ns["_render_backing_pk_owner_select"](proxy, ["C", "D"], label_visibility="collapsed")
    (label, options, kw), = st.calls
    assert kw["key"] == "display_key_catalog_backing" and kw["on_change"] == "commit"
    assert options == ["C", "D"] and kw["label_visibility"] == "collapsed"
    assert proxy["rendered"] is True


def test_sidebar_slot_renders_only_when_no_card_rendered_the_widget() -> None:
    log: list = []
    st = _St()
    proxy = _proxy(log)
    ns = _load(["_render_backing_pk_owner_select", "_render_pending_sidebar_practice_key"], {"st": st, "Any": object})
    ns["_sidebar_pk_proxy"] = proxy
    ns["_render_pending_sidebar_practice_key"]()
    assert log == ["slot"] and len(st.calls) == 1
    assert st.calls[0][2]["label_visibility"] == "visible"
    ns["_render_pending_sidebar_practice_key"]()  # once per run: never a duplicate widget
    assert len(st.calls) == 1
    ns.pop("_sidebar_pk_proxy")
    ns["_render_pending_sidebar_practice_key"]()  # other pages: nothing pending
    assert len(st.calls) == 1


def test_sidebar_keeps_only_a_slot_on_backing() -> None:
    assert APP.count("_sidebar_pk_proxy = {") == 2
    for widget, cb in (
        ("CUSTOM_WORKSPACE_PRACTICE_KEY_WIDGET", "_on_custom_workspace_practice_key_change"),
        ("_pk_widget_key", "_on_mission_or_global_pk_change"),
    ):
        i = APP.index(f'"key": {widget},')
        block = APP[i - 400:i + 900]
        assert '== "backing":' in block[:400]
        assert f'"on_change": {cb},' in block
        assert '"slot": st.sidebar.empty(),' in block
        # Every other page keeps its sidebar control.
        assert f"key={widget}," in block and f"on_change={cb}," in block


def test_card_renders_the_owner_widget_no_mirror() -> None:
    i = APP.index("with _backing_card_cols[0]:")
    assert "_render_backing_card_practice_key(" in APP[i:i + 300]
    fn = _fn("_render_backing_card_practice_key")
    assert 'globals().get("_sidebar_pk_proxy")' in fn
    assert '_render_backing_pk_owner_select(proxy, options, label_visibility="collapsed")' in fn
    assert "conventional_key_options(" in fn
    # Without an owner widget this run, the keys show as text, as before.
    assert "if not proxy or proxy.get(\"rendered\"):" in fn
    assert "active_song_key_row_html(original_key, practice_key)" in fn
    # No second widget, no hide rule: nothing to mirror.
    assert "backing_card_practice_key::" not in APP
    assert "_backing_card_practice_key_changed" not in APP
    assert "display:none !important;" not in fn


def test_fallback_runs_after_the_card_and_at_script_end() -> None:
    card = APP.index("with _backing_card_cols[0]:")
    after = APP.index("    _render_pending_sidebar_practice_key()\n    _current_backing_signature")
    assert card < after
    end = APP.rindex("_render_pending_sidebar_practice_key()")
    assert end > APP.rindex("render_music_startup_ready_marker(")
    assert APP.count("_render_pending_sidebar_practice_key()\n") == 2  # calls, not the def
