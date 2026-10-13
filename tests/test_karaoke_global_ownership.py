"""KARAOWNER / KARAEDIT / KARANEXT: a Karaoke selection IS the global active song.

Live first wrong steps:

* Setlist click on Love Story (Original C): activation ran, then on the next run
  ``restore_sbi_active_catalog_identity_before_widgets`` reinstalled the
  previous song. ``resolve_sbi_active_catalog_identity`` skipped any catalog
  blob whose Original Key is C as a suspected placeholder, so an older blob for
  Perfect (G) won over the live Love Story blob.
* Next Song only moved Karaoke's own set position (a separate "now singing"
  identity); the global song never followed. Once it was activated, identity
  reconciliation reverted it to the last *explicit* Songs-page pick, because
  the Karaoke activation was not recorded as an explicit committed pick.
* "Editing" was a separate Karaoke entry id, so the highlight could disagree
  with the global song, and identical duplicates never highlighted together.
"""

from __future__ import annotations

import karaoke_mode as km
from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base, _FakeSt

LOVE_STORY = ("Country", "Love Story — Taylor Swift")
SHALLOW = ("Pop", "Shallow — Lady Gaga / Bradley Cooper")


def test_key_identity_keeps_tonic_and_mode() -> None:
    kid = km.karaoke_key_identity
    assert kid("A") == kid("A major") != kid("Am")
    assert kid("B") != kid("Bm")
    assert kid("Gb") == kid("F#")
    assert kid("Eb") != kid("E")


class TestNowEditingFollowsTheGlobalSongAndKey(_Base):
    def _setlist(self, session: dict) -> list[dict]:
        from song_catalog.catalog import format_pick_key

        for genre_title, key in ((PERFECT, "A"), (LOVE_STORY, "C"), (PERFECT, "G"), (PERFECT, "A")):
            km.add_to_queue(session, format_pick_key(*genre_title), title=genre_title[1].split(" — ")[0])
            q = km.get_queue(session)
            q[-1]["practice_key"] = key
            session[km.KARAOKE_QUEUE_KEY] = q
        return km.get_queue(session)

    def _select(self, session: dict, entry: dict) -> None:
        from song_catalog.catalog import parse_pick_key

        self.activate_catalog(session, *parse_pick_key(entry["pick_key"]))
        km.commit_entry_practice_key(session, entry)

    def test_duplicates_match_and_other_keys_do_not(self) -> None:
        session = self.new_session()
        q = self._setlist(session)
        ids = [e["entry_id"] for e in q]
        self._select(session, q[0])                                   # Perfect A
        self.assertEqual(km.now_editing_entry_ids(session), {ids[0], ids[3]})
        self._select(session, q[2])                                   # Perfect G
        self.assertEqual(km.now_editing_entry_ids(session), {ids[2]})
        self._select(session, q[1])                                   # Love Story C
        self.assertEqual(km.now_editing_entry_ids(session), {ids[1]})

    def test_entry_key_becomes_the_songs_own_practice_key(self) -> None:
        from songs.practice_key_state import get_practice_concert_key

        session = self.new_session()
        q = self._setlist(session)
        self._select(session, q[0])
        self.assertEqual(get_practice_concert_key(session, q[0]["pick_key"], default=""), "A")
        self.assertEqual(session.get("_pending_display_key"), "A")
        self.assertEqual((session.get("_pk_user_commit_token"), session.get("_pk_user_commit_pick")), ("A", q[0]["pick_key"]))

    def test_live_song_with_original_c_is_not_replaced_by_an_older_blob(self) -> None:
        from source_session_state import resolve_sbi_active_catalog_identity

        session = self.new_session()
        perfect = self.activate_catalog(session, *PERFECT)
        session["_last_catalog_song_state"] = {"pick_key": perfect, "original_key": "G", "selected_song": {"title": "Perfect"}}
        love = self.activate_catalog(session, *LOVE_STORY)
        session["catalog_session"] = {"pick_key": love, "original_key": "C", "selected_song": {"title": "Love Story"}}
        pick, sel, orig = resolve_sbi_active_catalog_identity(session)
        self.assertEqual((pick, orig), (love, "C"), "Perfect's older blob won over live Love Story")

    def test_explicit_karaoke_commit_survives_identity_reconciliation(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.state import (
            ACTIVE_CATALOG_PICK_KEY,
            apply_explicit_catalog_dropdown_pick,
            reconcile_active_song_identity,
        )

        session = self.new_session()
        st = _FakeSt(session)
        apply_explicit_catalog_dropdown_pick(st, format_pick_key(*SHALLOW), self.picker, song_library=self.library)
        love = format_pick_key(*LOVE_STORY)
        apply_explicit_catalog_dropdown_pick(st, love, self.picker, song_library=self.library)  # Karaoke Next
        reconcile_active_song_identity(session, self.picker)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], love, "reverted to the last Songs-page pick")


class TestOldActivationPathIsReverted(_Base):
    def test_plain_activation_is_reverted_to_the_last_songs_page_pick(self) -> None:
        """Documents the old Next-Song path: why the explicit commit is needed."""
        from song_catalog.catalog import format_pick_key
        from songs.state import (
            ACTIVE_CATALOG_PICK_KEY,
            activate_active_song_by_pick_key,
            apply_explicit_catalog_dropdown_pick,
            reconcile_active_song_identity,
        )

        session = self.new_session()
        st = _FakeSt(session)
        shallow = format_pick_key(*SHALLOW)
        apply_explicit_catalog_dropdown_pick(st, shallow, self.picker, song_library=self.library)
        activate_active_song_by_pick_key(st, format_pick_key(*LOVE_STORY), self.picker, song_library=self.library)
        reconcile_active_song_identity(session, self.picker)
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], shallow)
