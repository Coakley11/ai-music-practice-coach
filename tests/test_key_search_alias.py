"""Practice Key dropdown search: ordinary spellings find the musical names, and a stated mode is kept.

"Eb" / "F#" find E♭ / F♯. "F#m" means F♯ minor: it finds F♯ minor in a minor list and nothing in a
major-only list; it never silently substitutes F♯ major. The rewrite runs in the browser
(song_card_keys.KEY_SEARCH_ALIAS_JS) from the same rule table these tests exercise, with the
dropdowns filtering by prefix. Key values, saved keys and callbacks are untouched.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from music_theory import conventional_key_options
from song_card_keys import (
    KEY_SEARCH_ALIAS_SLOT_KEY,
    KEY_SEARCH_FILTER_MODE,
    KEY_SEARCH_RULES,
    key_search_alias_html,
    key_search_text,
    pretty_key_name,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CSS = (ROOT / "app_ui.py").read_text(encoding="utf-8")
MAJOR = [pretty_key_name(k) for k in conventional_key_options("C", "C")]
MINOR = [pretty_key_name(k) for k in conventional_key_options("Cm", "Cm")]


def typed(keys: str) -> str:
    """The search box after typing ``keys`` one character at a time, as the script sees it."""
    box = ""
    for ch in keys:
        box = key_search_text(box + ch)
    return box


def found(keys: str, options: list[str]) -> list[str]:
    """Options the dropdown keeps: case-insensitive prefix of the search text."""
    box = typed(keys).lower()
    return [o for o in options if o.lower().startswith(box)]


def test_the_lists_are_one_mode_each() -> None:
    assert all(o.endswith("major") for o in MAJOR) and all(o.endswith("minor") for o in MINOR)
    assert KEY_SEARCH_FILTER_MODE == "prefix"


@pytest.mark.parametrize(
    "keys, options, want",
    [
        ("Eb", MAJOR, ["E♭ major"]),  # finds it in a major list
        ("F#", MAJOR, ["F♯ major"]),
        ("F#m", MINOR, ["F♯ minor"]),  # an explicit minor finds minor
        ("F#m", MAJOR, []),  # ... and nothing in a major-only list: never F♯ major
        ("Bbm", MINOR, ["B♭ minor"]),
        ("Bbm", MAJOR, []),
        ("Am", MINOR, ["A minor"]),
        ("Am", MAJOR, []),
        ("FM", MAJOR, ["F major"]),  # an explicit major is kept too
        ("FM", MINOR, []),
        ("F#maj", MAJOR, ["F♯ major"]),
        ("F#maj", MINOR, []),
        ("F#min", MINOR, ["F♯ minor"]),
        ("F#minor", MINOR, ["F♯ minor"]),
        ("F#minor", MAJOR, []),
        ("F minor", MAJOR, []),
        ("F major", MINOR, []),
    ],
)
def test_search_keeps_the_stated_mode(keys: str, options: list[str], want: list[str]) -> None:
    assert found(keys, options) == want


def test_a_bare_note_names_no_mode_and_narrows_by_note() -> None:
    assert found("Eb", MINOR) == ["E♭ minor"]
    assert set(found("E", MAJOR)) == {"E♭ major", "E major"}
    assert found("b", MAJOR) == [o for o in MAJOR if o.startswith("B")]


def test_pasted_text_gets_the_same_result_as_typing() -> None:
    for text in ("F#m", "F#maj", "F#min", "Eb", "Bbm"):
        assert key_search_text(text) == typed(text)


def test_script_uses_the_rule_table_and_targets_only_the_key_dropdowns() -> None:
    js = key_search_alias_html()
    assert "picker_active_song_practice_key_row input[role=\\\"combobox\\\"]" in js
    assert "backing_card_key_row input[role=\\\"combobox\\\"]" in js
    for pattern, replacement in KEY_SEARCH_RULES:
        assert replacement in js
    # Only the typed search text changes: no value, option or callback is touched.
    assert "stopImmediatePropagation" in js and "setter.call(el, nv)" in js


def test_each_new_frame_replaces_the_listener_so_search_survives_navigation() -> None:
    # The script's frame is destroyed on a page change and its listener stops firing, so a
    # once-only guard left "Eb" / "F#m" finding nothing after moving between Songs and Backing.
    js = key_search_alias_html()
    assert "__keySearchAliasInstalled" not in js
    assert "removeEventListener('input', W.__keySearchAliasListener, true)" in js
    assert "addEventListener('input', W.__keySearchAliasListener, true)" in js
    assert js.index("removeEventListener") < js.index("addEventListener")


def test_both_cards_use_prefix_filtering_and_install_the_script_every_run() -> None:
    assert APP.count("filter_mode=KEY_SEARCH_FILTER_MODE") == 1  # Songs card
    assert 'proxy["filter_mode"] = KEY_SEARCH_FILTER_MODE' in APP  # Backing card
    for fn in ("def _render_backing_card_practice_key(", "def _render_card_practice_key_selector("):
        i = APP.index(fn)
        assert "render_key_search_alias(st)" in APP[i:i + 2500]


def test_slot_is_out_of_flow() -> None:
    i = CSS.index(f".st-key-{KEY_SEARCH_ALIAS_SLOT_KEY},")
    rule = CSS[i:i + 400]
    assert "position: absolute !important;" in rule and "height: 0 !important;" in rule
