"""KARAPERSIST: every Karaoke setlist mutation reaches the durable profile.

Live first wrong step: after a setlist-only edit (add / remove / clear /
reorder / count) the end-of-run autosave returned ``startup_canonical_unchanged``
and wrote nothing. The workspace canonical fingerprint did not include
``session.karaoke_queue``, so a setlist edit looked like "no change" to startup
save suppression (and to the strict-egress duplicate planner). Disk caught up
only when some other save (a song activation) happened, one mutation late, and
a refresh restored that older setlist.

Fix: the setlist is part of the canonical fingerprint, and every mutation goes
through one save path (``karaoke_setlist_edit``) that is allowed past startup
suppression and strict egress. An empty setlist is a valid saved state.
"""

from __future__ import annotations

import pytest

import karaoke_mode as km
from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base, _FakeSt

LOVE_STORY = ("Country", "Love Story — Taylor Swift")
SHALLOW = ("Pop", "Shallow — Lady Gaga / Bradley Cooper")


def _fp(queue):
    from music_workspace_canonical_fingerprint import workspace_canonical_content_fingerprint

    return workspace_canonical_content_fingerprint({"core": {"instrument": "Voice"}, "session": {"karaoke_queue": queue}})


def test_canonical_fingerprint_sees_every_setlist_change() -> None:
    a = {"entry_id": "a", "pick_key": "pa", "title": "A", "play_count": 1}
    b = {"entry_id": "b", "pick_key": "pb", "title": "B", "play_count": 1}
    base = _fp([a, b])
    assert _fp([a, b, {"entry_id": "c", "pick_key": "pc", "title": "C"}]) != base   # add
    assert _fp([a]) != base                                                           # remove
    assert _fp([]) != base                                                            # clear
    assert _fp([b, a]) != base                                                        # reorder
    assert _fp([dict(a, play_count=3), b]) != base                                    # count
    assert _fp([a, b]) == base                                                        # stable


def test_setlist_edit_is_a_deliberate_save_reason() -> None:
    from music_egress_config import is_intentional_user_save_reason
    from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY, should_suppress_music_workspace_save
    from karaoke_ui import KARAOKE_SETLIST_SAVE_REASON

    hydrated = {STARTUP_FINGERPRINT_MATCHES_KEY: True}
    assert should_suppress_music_workspace_save(dict(hydrated), "autosave")[0], "precondition"
    assert not should_suppress_music_workspace_save(dict(hydrated), KARAOKE_SETLIST_SAVE_REASON)[0]
    assert is_intentional_user_save_reason(KARAOKE_SETLIST_SAVE_REASON)   # uploads under strict egress


class TestSetlistMutationsPersist(_Base):
    def setUp(self) -> None:
        super().setUp()
        import tempfile
        from pathlib import Path

        import suite_user_persistence as sup

        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "music_user_state.json"
        self._orig_path = sup.state_file_path
        sup.state_file_path = lambda *_a, **_k: path

    def tearDown(self) -> None:
        import suite_user_persistence as sup

        sup.state_file_path = self._orig_path
        self._tmp.cleanup()
        super().tearDown()

    def _hydrated_session(self) -> dict:
        from music_startup_save_suppression import STARTUP_FINGERPRINT_MATCHES_KEY

        session = self.new_session()
        session["instrument"] = "Voice"
        session[STARTUP_FINGERPRINT_MATCHES_KEY] = True       # as right after a profile hydrate
        return session

    def _save(self, session: dict) -> None:
        from karaoke_ui import persist_karaoke_setlist

        persist_karaoke_setlist(_FakeSt(session))

    def _disk_titles(self) -> list:
        from suite_user_persistence import load_user_state

        state, _warn = load_user_state("music")
        queue = (state.get("session") or {}).get("karaoke_queue")
        assert isinstance(queue, list), f"no saved setlist: {state.get('session', {}).keys()}"
        return [(e.get("title"), e.get("play_count", 1)) for e in queue]

    def _restored_titles(self) -> list:
        from music_persistent_state import apply_music_disk_state
        from suite_user_persistence import load_user_state

        state, _warn = load_user_state("music")
        fresh = self.new_session()
        fresh["karaoke_queue"] = [{"entry_id": "stale", "pick_key": "x", "title": "STALE"}]
        apply_music_disk_state(_FakeSt(fresh), state, song_picker_catalog=self.picker, song_library=self.library)
        return [(e.get("title"), e.get("play_count", 1)) for e in km.get_queue(fresh)]

    def _add(self, session, genre_title):
        from song_catalog.catalog import format_pick_key

        title = genre_title[1].split(" — ")[0]
        km.add_to_queue(session, format_pick_key(*genre_title), title=title)
        self._save(session)

    def test_add_remove_reorder_count_each_persist_and_restore(self) -> None:
        s = self._hydrated_session()
        self._add(s, PERFECT); self._add(s, SHALLOW)
        self.assertEqual(self._disk_titles(), [("Perfect", 1), ("Shallow", 1)])
        self._add(s, LOVE_STORY)                                                  # KARAPERSIST1
        self.assertEqual(self._restored_titles(), [("Perfect", 1), ("Shallow", 1), ("Love Story", 1)])
        km.remove_entry_at(s, 1); self._save(s)                                   # KARAPERSIST2
        self.assertEqual(self._restored_titles(), [("Perfect", 1), ("Love Story", 1)])
        km.move_entry_at(s, 1, -1); self._save(s)                                 # KARAPERSIST4
        self.assertEqual(self._restored_titles(), [("Love Story", 1), ("Perfect", 1)])
        km.set_entry_play_count(s, km.get_queue(s)[0]["entry_id"], 3); self._save(s)   # KARAPERSIST5
        self.assertEqual(self._restored_titles(), [("Love Story", 3), ("Perfect", 1)])

    def test_several_mutations_restore_the_exact_final_state(self) -> None:   # KARAPERSIST6
        s = self._hydrated_session()
        for song in (PERFECT, SHALLOW, LOVE_STORY):
            self._add(s, song)
        km.remove_entry_at(s, 0); self._save(s)
        km.move_entry_at(s, 1, -1); self._save(s)
        km.set_entry_play_count(s, km.get_queue(s)[1]["entry_id"], 2); self._save(s)
        self.assertEqual(self._restored_titles(), [("Love Story", 1), ("Shallow", 2)])

    def test_clear_saves_an_authoritative_empty_setlist(self) -> None:   # KARAPERSIST3
        s = self._hydrated_session()
        for song in (PERFECT, SHALLOW, LOVE_STORY):
            self._add(s, song)
        km.clear_queue(s); self._save(s)
        self.assertEqual(self._disk_titles(), [])
        self.assertEqual(self._restored_titles(), [], "old songs came back after Clear")
