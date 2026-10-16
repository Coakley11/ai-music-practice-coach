"""The Songs-page Favorite control lives inside the active song card."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
CSS = (ROOT / "app_ui.py").read_text(encoding="utf-8")


def test_favorite_renders_inside_the_card_shell() -> None:
    shell = APP.index('with st.container(key="picker_active_song_card_shell"):')
    card = APP.index("_render_active_song_card(active_rec, show_nav_actions=False)", shell)
    fav = APP.index('with st.container(key="picker_active_song_favorite_row"):', shell)
    assert shell < card < fav
    # Same control and persistence as before: one keyed button, song-owned.
    assert APP.count('key="picker_active_song_favorite"') == 1
    block = APP[fav : fav + 900]
    assert "toggle_catalog_favorite(st.session_state, _fav_pk)" in block
    assert "persist_catalog_favorites(st)" in block


def test_shell_positions_the_favorite_inside_the_card() -> None:
    assert ".st-key-picker_active_song_card_shell {\n  position: relative !important;" in CSS
    i = CSS.index(".st-key-picker_active_song_card_shell .st-key-picker_active_song_favorite_row {")
    assert "position: absolute !important;" in CSS[i : i + 200]
