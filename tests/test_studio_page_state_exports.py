"""Import/export smoke tests for studio_page_state handoff helpers."""

from __future__ import annotations


def test_custom_progression_song_source_label_uses_pencil() -> None:
    from studio_page_state import (
        IMPROV_SONG_SOURCES,
        creative_song_source_display_label,
    )

    assert "Custom progression" in IMPROV_SONG_SOURCES
    assert "Composition" in IMPROV_SONG_SOURCES
    assert creative_song_source_display_label("Custom progression") == "✏️ Custom Progression"
    assert creative_song_source_display_label("Active song") == "Active Source"
    assert creative_song_source_display_label("Composition") == "🎹 Composition"


def test_entry_jam_song_source_radio_uses_display_label() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath("improvisation_intelligence_ui.py").read_text(
        encoding="utf-8"
    )
    assert "format_func=creative_song_source_display_label" in text
    assert 'key="improv_song_source"' in text


def test_studio_page_state_exports_improv_song_source_helpers() -> None:
    from studio_page_state import (
        flush_pending_improv_song_source,
        resolve_improv_song_source,
        sync_improv_song_source_for_handoff,
    )

    assert callable(resolve_improv_song_source)
    assert callable(sync_improv_song_source_for_handoff)
    assert callable(flush_pending_improv_song_source)


def test_studio_page_state_exports_improv_tab_helpers() -> None:
    from studio_page_state import (
        CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY,
        ensure_improv_intelligence_tab_restored,
        persist_improv_intelligence_tab,
    )

    assert CREATIVE_IMPROV_INTELLIGENCE_TAB_KEY == "creative_improv_intelligence_tab"
    assert callable(ensure_improv_intelligence_tab_restored)
    assert callable(persist_improv_intelligence_tab)


def test_streamlit_app_imports_improv_handoff_helpers() -> None:
    import streamlit_music_practice_app as app

    assert callable(app.resolve_improv_song_source)
    assert callable(app.sync_improv_song_source_for_handoff)
