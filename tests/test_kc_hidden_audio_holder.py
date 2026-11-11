"""The Key Cycling dual-buffer holder on <body> is never visible (a phone showed its "Key cycling off" line)."""

from __future__ import annotations

import re

from backing_key_cycle import KC_HOLDER_HIDDEN_CSS, cycle_persistent_player_bridge_html


def test_holder_css_hides_it_without_display_none() -> None:
    css = KC_HOLDER_HIDDEN_CSS
    for rule in ("position:fixed", "width:1px", "height:1px", "overflow:hidden", "clip-path:inset(50%)",
                 "opacity:0", "pointer-events:none"):
        assert rule in css
    assert "display:none" not in css  # the buffers keep loading and playing
    assert "'" not in css and "\\" not in css  # safe inside the JS string literal


def test_bridge_applies_it_when_creating_and_when_reusing_the_holder() -> None:
    html = cycle_persistent_player_bridge_html(cmd_json="{}")
    assert f"const KC_HOLDER_HIDDEN_CSS = '{KC_HOLDER_HIDDEN_CSS}';" in html
    assert "position:relative;z-index:20" not in html  # the old in-flow placement
    ensure = html[html.index("function ensurePlayer()"):]
    ensure = ensure[: ensure.index("parentWin.__kcDual")]
    create = ensure[ensure.index("if (!root) {"): ensure.index("} else {")]
    reuse = ensure[ensure.index("} else {"):]
    assert "hideHolder(root);" in create and "hideHolder(root);" in reuse
    assert re.search(r"appendChild\(root\)", create)  # still lives on <body>
