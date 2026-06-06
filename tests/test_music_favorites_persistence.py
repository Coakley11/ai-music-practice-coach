"""Favorites list is included in music disk/cloud persistence payload."""

from __future__ import annotations

from types import SimpleNamespace

from music_persistent_state import apply_music_disk_state, build_music_disk_state


class _FakeSession(dict):
    @property
    def session_state(self):
        return self


def test_build_music_disk_state_includes_favorites():
    st = _FakeSession(
        {
            "catalog_favorite_pick_keys": [
                "Jazz|Autumn Leaves — Joseph Kosma",
                "Pop|Shallow — Lady Gaga",
            ],
            "song_picker_favorites_only": True,
            "studio_page": "picker",
        }
    )
    payload = build_music_disk_state(st)
    assert payload["session"]["catalog_favorite_pick_keys"] == [
        "Jazz|Autumn Leaves — Joseph Kosma",
        "Pop|Shallow — Lady Gaga",
    ]
    assert payload["session"]["song_picker_favorites_only"] is True


def test_apply_music_disk_state_restores_favorites():
    st = _FakeSession({})
    payload = {
        "core": {},
        "session": {
            "catalog_favorite_pick_keys": ["Jazz|Autumn Leaves — Joseph Kosma"],
            "song_picker_favorites_only": False,
        },
    }
    apply_music_disk_state(
        st,
        payload,
        song_picker_catalog={},
        song_library={},
    )
    assert st["catalog_favorite_pick_keys"] == ["Jazz|Autumn Leaves — Joseph Kosma"]
    assert st["song_picker_favorites_only"] is False
