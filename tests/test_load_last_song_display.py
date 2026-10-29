"""Load Last Song shows the song's own genre icon and saved Favorite star, on every hub."""
from __future__ import annotations

from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")


def _shortcut() -> str:
    return APP[APP.index("def _render_last_catalog_song_shortcut("):][:2600]


def test_icon_comes_from_the_canonical_genre_style() -> None:
    body = _shortcut()
    assert "genre_visual_style(_last_genre)" in body
    assert 'sel.get("genre")' in body


def test_star_is_the_saved_favorite_not_the_browse_filter() -> None:
    body = _shortcut()
    assert "is_catalog_favorite(st.session_state, _last_pick)" in body
    assert "favorites_only" not in body.lower()


def test_shortcut_rendered_on_catalog_custom_and_composition_hubs() -> None:
    for prefix in ("catalog_hub", "custom_hub", "composition_hub"):
        assert f'_render_last_catalog_song_shortcut(key_prefix="{prefix}")' in APP
