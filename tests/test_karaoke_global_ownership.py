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


class TestNowEditingAndNowSingingAreIndependent(_Base):
    """Now Editing = setlist row click (global song + key). Now Singing = set
    position (Start / Next / Previous / auto-advance), Karaoke Backing only."""

    def _setlist(self, session: dict) -> list[dict]:
        from song_catalog.catalog import format_pick_key

        shape = ("Pop", "Shape of You — Ed Sheeran")
        for genre_title, key in ((PERFECT, "A"), (LOVE_STORY, "C"), (shape, "Bm")):
            km.add_to_queue(session, format_pick_key(*genre_title), title=genre_title[1].split(" — ")[0])
            q = km.get_queue(session)
            q[-1]["practice_key"] = key
            session[km.KARAOKE_QUEUE_KEY] = q
        return km.get_queue(session)

    def _edit(self, session: dict, entry: dict) -> None:
        from song_catalog.catalog import parse_pick_key

        self.activate_catalog(session, *parse_pick_key(entry["pick_key"]))
        km.commit_entry_practice_key(session, entry)

    def test_set_transitions_never_change_the_global_song_or_its_key(self) -> None:
        from songs.practice_key_state import get_practice_concert_key
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        session = self.new_session()
        q = self._setlist(session)
        self._edit(session, q[2])                                       # Now Editing: Shape of You Bm
        before = (session[ACTIVE_CATALOG_PICK_KEY], get_practice_concert_key(session, q[0]["pick_key"], default=""))
        km.start_session(session)                                       # Now Singing: Perfect A
        self.assertEqual(km.current_session_practice_key(session), "A")
        km.advance_session(session)                                     # Love Story C
        self.assertEqual(km.current_session_practice_key(session), "C")
        km.regress_session(session)
        self.assertEqual(
            (session[ACTIVE_CATALOG_PICK_KEY], get_practice_concert_key(session, q[0]["pick_key"], default="")),
            before,
        )
        self.assertEqual(km.now_editing_entry_ids(session), {q[2]["entry_id"]})
        self.assertEqual(km.now_singing_entry_id(session), q[0]["entry_id"])

    def test_same_song_in_another_key_keeps_its_editing_key_while_singing(self) -> None:
        from song_catalog.catalog import format_pick_key
        from songs.practice_key_state import get_practice_concert_key

        session = self.new_session()
        for key in ("A", "G"):
            km.add_to_queue(session, format_pick_key(*PERFECT), title="Perfect")
            q = km.get_queue(session)
            q[-1]["practice_key"] = key
            session[km.KARAOKE_QUEUE_KEY] = q
        q = km.get_queue(session)
        self._edit(session, q[1])                                       # editing Perfect G
        km.start_session(session)                                       # singing Perfect A
        self.assertEqual(km.current_session_practice_key(session), "A")
        self.assertEqual(get_practice_concert_key(session, q[1]["pick_key"], default=""), "G")
        self.assertEqual(km.now_editing_entry_ids(session), {q[1]["entry_id"]})

    def test_set_position_never_activates_globally_and_a_click_never_moves_it(self) -> None:
        import inspect
        from pathlib import Path

        import karaoke_ui

        app = (Path(__file__).resolve().parent.parent / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        block = app[app.index("if km.is_voice_mode(st.session_state):\n    _kr_advanced_pk"):]
        block = block[: block.index("\nelse:\n")]
        self.assertNotIn("_activate_karaoke_entry(", block, "set position must not activate the global song")
        self.assertFalse(hasattr(km, "focus_session_on_entry"))
        self.assertNotIn("focus_session_on_entry", inspect.getsource(karaoke_ui))

    def test_singing_a_different_song_ends_the_editing_songs_play_session(self) -> None:
        """Start onto Perfect while editing Shape of You: Karaoke Backing must
        not inherit Shape of You's play-session tempo (96 shown on Perfect 95)."""
        from unittest import mock

        import backing_context as bc
        import backing_play_session as bps
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        session = self.new_session()
        session["instrument"] = "Voice"
        q = self._setlist(session)
        self._edit(session, q[2])                                       # Now Editing: Shape of You Bm
        shape_pick = session[ACTIVE_CATALOG_PICK_KEY]
        calls: list[bool] = []
        real_expire = bps.expire_backing_play_session

        def _spy(s, *, song_changed=False):
            calls.append(bool(song_changed))
            return real_expire(s, song_changed=song_changed)

        with mock.patch.object(bps, "expire_backing_play_session", _spy):
            try:
                bc.restore_regular_song_backing(session)                # Backing owned by Shape of You
            except Exception:
                pass
            km.start_session(session)                                   # Now Singing: Perfect A
            calls.clear()
            try:
                bc.restore_regular_song_backing(session)
            except Exception:
                pass
        self.assertEqual(calls[:1], [True], "Karaoke switch must expire as a song change")
        self.assertEqual(session[ACTIVE_CATALOG_PICK_KEY], shape_pick, "global Now Editing song untouched")
