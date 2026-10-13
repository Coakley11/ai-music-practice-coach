"""CATKEY: a Catalog song's Practice Key belongs to that song on normal Backing.

Live first wrong writer: every Catalog song shares one Backing Practice Key
widget (``display_key_catalog_backing``). After Love Story played in D, entering
Backing for Shallow (Original G) found the leftover D in that widget, the owner
was still "catalog" (no switch), the last commit token was Love Story's D, so
``seed_backing_practice_key_widget`` kept the widget value and wrote D into
``display_key`` / ``concert_key`` -- the previous song's key outranked Shallow's G.

The canonical fallback had the same leak: with no saved key for the new song
yet, ``canonical_concert_key_for_owner`` returned the shared widget's value.
"""

from __future__ import annotations

import unittest

from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base

LOVE_STORY = ("Country", "Love Story — Taylor Swift")
SHALLOW = ("Pop", "Shallow — Lady Gaga / Bradley Cooper")


class TestCatalogBackingWidgetIsPerSong(_Base):
    def _on_backing(self, session: dict) -> str:
        from backing_practice_key_control import seed_backing_practice_key_widget

        session["studio_page"] = "backing"
        return seed_backing_practice_key_widget(session, options=["C", "D", "E", "G"])

    def _commit(self, session: dict, pick: str, key: str) -> None:
        from songs.practice_key_state import mark_practice_key_user_override, set_practice_concert_key

        # What a sidebar Practice Key change commits for the active song.
        mark_practice_key_user_override(session, pick)
        set_practice_concert_key(
            session, key, pick_key=pick, allow_restore_original=True, commit_catalog_practice_key=True
        )
        session["display_key"] = key
        session["concert_key"] = key
        session["_pk_user_commit_token"] = key
        session["_pk_user_commit_pick"] = pick

    def test_previous_songs_backing_key_does_not_leak_into_the_next_song(self) -> None:
        from backing_practice_key_control import WIDGET_CATALOG, commit_backing_practice_key

        session = self.new_session()
        love = self.activate_catalog(session, *LOVE_STORY)
        self._commit(session, love, "D")
        self.assertEqual(self._on_backing(session), "D")
        commit_backing_practice_key(session, "D")          # Love Story's D played on Backing
        self.assertEqual(session[WIDGET_CATALOG], "D")

        self.activate_catalog(session, *SHALLOW)
        self.assertEqual(self._on_backing(session), "G", "Shallow got Love Story's D")
        self.assertEqual((session["display_key"], session["concert_key"]), ("G", "G"))

    def test_each_song_keeps_its_own_key_round_trip(self) -> None:
        session = self.new_session()
        perfect = self.activate_catalog(session, *PERFECT)
        self._commit(session, perfect, "E")
        self.assertEqual(self._on_backing(session), "E")
        love = self.activate_catalog(session, *LOVE_STORY)
        self.assertEqual(self._on_backing(session), "C")
        self._commit(session, love, "D")
        self.assertEqual(self._on_backing(session), "D")
        self.activate_catalog(session, *PERFECT)
        self.assertEqual(self._on_backing(session), "E", "Perfect got Love Story's D")
        self.activate_catalog(session, *LOVE_STORY)
        self.assertEqual(self._on_backing(session), "D")

    def test_a_change_made_on_backing_for_the_same_song_is_kept(self) -> None:
        from backing_practice_key_control import WIDGET_CATALOG, commit_backing_practice_key

        session = self.new_session()
        self.activate_catalog(session, *LOVE_STORY)
        self._on_backing(session)
        commit_backing_practice_key(session, "E")
        session[WIDGET_CATALOG] = "E"
        self.assertEqual(self._on_backing(session), "E")


if __name__ == "__main__":
    unittest.main()
