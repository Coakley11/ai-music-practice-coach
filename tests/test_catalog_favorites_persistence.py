"""FAV: Catalog Favorites are song-owned and every toggle reaches the profile.

The store already existed (``catalog_favorite_pick_keys``, saved in the
profile's session slice) but nothing persisted a toggle explicitly, and the
canonical workspace fingerprint did not include it -- the same gap that lost
Karaoke setlist edits: a favorite-only change looked "unchanged" to startup
save suppression and was not written. Favorites are now fingerprinted and every
toggle saves with the deliberate reason ``catalog_favorite_edit``.
"""

from __future__ import annotations

from songs.picker_session import (
    CATALOG_FAVORITE_SAVE_REASON,
    CATALOG_FAVORITES_KEY,
    is_catalog_favorite,
    persist_catalog_favorites,
    toggle_catalog_favorite,
)
from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base, _FakeSt

LOVE_STORY = ("Country", "Love Story — Taylor Swift")


def _fp(favs):
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    return workspace_canonical_content_fingerprint({"core": {"instrument": "Voice"}, "session": {CATALOG_FAVORITES_KEY: favs}})


def test_canonical_fingerprint_sees_favorite_changes() -> None:
    assert _fp(["a"]) != _fp([])
    assert _fp(["a", "b"]) != _fp(["a"])
    assert _fp(["b", "a"]) == _fp(["a", "b"])            # order is not content


def test_favorite_toggle_is_a_deliberate_save() -> None:
    from music_egress_config import is_intentional_user_save_reason
    from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY, should_suppress_music_workspace_save

    hydrated = {STARTUP_FINGERPRINT_MATCHES_KEY: True}
    assert should_suppress_music_workspace_save(dict(hydrated), "autosave")[0], "precondition"
    assert not should_suppress_music_workspace_save(dict(hydrated), CATALOG_FAVORITE_SAVE_REASON)[0]
    assert is_intentional_user_save_reason(CATALOG_FAVORITE_SAVE_REASON)


class TestFavoritesPersist(_Base):
    def setUp(self) -> None:
        super().setUp()
        import tempfile
        from pathlib import Path

        import suite_user_persistence as sup

        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "music_user_state.json"
        self._orig = sup.state_file_path
        sup.state_file_path = lambda *_a, **_k: path

    def tearDown(self) -> None:
        import suite_user_persistence as sup

        sup.state_file_path = self._orig
        self._tmp.cleanup()
        super().tearDown()

    def _restored(self) -> list:
        from music_persistent_state import apply_music_disk_state
        from suite_user_persistence import load_user_state

        state, _w = load_user_state("music")
        fresh = self.new_session()
        apply_music_disk_state(_FakeSt(fresh), state, song_picker_catalog=self.picker, song_library=self.library)
        return sorted(fresh.get(CATALOG_FAVORITES_KEY) or [])

    def test_favorite_and_unfavorite_survive_a_reload(self) -> None:
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY

        session = self.new_session()
        session[STARTUP_FINGERPRINT_MATCHES_KEY] = True          # right after a profile hydrate
        perfect = self.activate_catalog(session, *PERFECT)
        love = self.activate_catalog(session, *LOVE_STORY)
        toggle_catalog_favorite(session, perfect); persist_catalog_favorites(_FakeSt(session))
        self.assertEqual(self._restored(), [perfect])
        toggle_catalog_favorite(session, love); persist_catalog_favorites(_FakeSt(session))
        self.assertEqual(self._restored(), sorted([perfect, love]))
        toggle_catalog_favorite(session, perfect); persist_catalog_favorites(_FakeSt(session))
        self.assertEqual(self._restored(), [love])

    def test_favorite_belongs_to_the_song_not_the_practice_key(self) -> None:
        from songs.practice_key_state import set_practice_concert_key

        session = self.new_session()
        perfect = self.activate_catalog(session, *PERFECT)
        toggle_catalog_favorite(session, perfect)
        for key in ("A", "C#", "G"):
            set_practice_concert_key(session, key, pick_key=perfect, allow_restore_original=True)
            self.assertTrue(is_catalog_favorite(session, perfect), key)
        self.assertEqual(session[CATALOG_FAVORITES_KEY], [perfect])
