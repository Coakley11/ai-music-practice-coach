"""Practice Key dropdown search aliases: "Eb" / "F#" find E♭ / F♯ without changing any value.

The rewrite runs in the browser (song_card_keys.KEY_SEARCH_ALIAS_JS). Here: the script
targets only the two key dropdowns, maps b/# after a note letter, and both cards install
it on every run (an always-present slot, taken out of flow by app CSS).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from song_card_keys import KEY_SEARCH_ALIAS_SLOT_KEY, key_search_alias_html

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CSS = (ROOT / "app_ui.py").read_text(encoding="utf-8")


def _mirror(typed: str) -> str:
    """The script's replacement, in Python."""
    return re.sub(r"([A-Ga-g])#", "\\1♯", re.sub(r"([A-Ga-g])b", "\\1♭", typed))


@pytest.mark.parametrize(
    "typed, want",
    [("Eb", "E♭"), ("Bbm", "B♭m"), ("F#", "F♯"), ("f#m", "f♯m"), ("C", "C"), ("b", "b"), ("Ab maj", "A♭ maj")],
)
def test_alias_mapping(typed: str, want: str) -> None:
    assert _mirror(typed) == want


def test_script_targets_only_the_key_dropdowns_and_installs_once() -> None:
    js = key_search_alias_html()
    assert "picker_active_song_practice_key_row input[role=\\\"combobox\\\"]" in js
    assert "backing_card_key_row input[role=\\\"combobox\\\"]" in js
    assert "__keySearchAliasInstalled" in js
    assert "/([A-Ga-g])b/g" in js and "/([A-Ga-g])#/g" in js
    # Only the typed search text changes: no value, option or callback is touched.
    assert "stopImmediatePropagation" in js and "setter.call(el, nv)" in js


def test_both_cards_install_it_every_run() -> None:
    for fn in ("def _render_backing_card_practice_key(", "def _render_card_practice_key_selector("):
        i = APP.index(fn)
        body = APP[i:i + 2500]
        assert "render_key_search_alias(st)" in body


def test_slot_is_out_of_flow() -> None:
    i = CSS.index(f".st-key-{KEY_SEARCH_ALIAS_SLOT_KEY},")
    rule = CSS[i:i + 400]
    assert "position: absolute !important;" in rule and "height: 0 !important;" in rule
