"""Practice tools launcher registry and persistence key normalization."""

from __future__ import annotations

from practice_tools_ui import (
    PRACTICE_ACTIVE_TOOL_KEY,
    PRACTICE_TOOLS,
    normalize_practice_active_tool,
)


def test_all_tool_ids_unique():
    ids = [t.tool_id for t in PRACTICE_TOOLS]
    assert len(ids) == len(set(ids))


def test_normalize_valid_tool():
    session = {PRACTICE_ACTIVE_TOOL_KEY: "timing"}
    assert normalize_practice_active_tool(session) == "timing"


def test_normalize_legacy_tab_label():
    session = {PRACTICE_ACTIVE_TOOL_KEY: "Tuner, Tone & Metronome"}
    assert normalize_practice_active_tool(session) == "tuner"
    assert session[PRACTICE_ACTIVE_TOOL_KEY] == "tuner"


def test_normalize_unknown_clears_key():
    session = {PRACTICE_ACTIVE_TOOL_KEY: "not-a-tool"}
    assert normalize_practice_active_tool(session) == ""
    assert PRACTICE_ACTIVE_TOOL_KEY not in session


def test_normalize_empty():
    assert normalize_practice_active_tool({}) == ""


def test_normalize_all_legacy_tab_labels():
    from practice_tools_ui import _LEGACY_TAB_TO_TOOL

    for legacy, expected in _LEGACY_TAB_TO_TOOL.items():
        session = {PRACTICE_ACTIVE_TOOL_KEY: legacy}
        assert normalize_practice_active_tool(session) == expected
        assert session[PRACTICE_ACTIVE_TOOL_KEY] == expected


def test_practice_page_snapshot_includes_active_tool():
    from studio_page_persistence import _PAGE_LOCAL_KEYS

    assert "practice_active_tool" in _PAGE_LOCAL_KEYS["practice"]
