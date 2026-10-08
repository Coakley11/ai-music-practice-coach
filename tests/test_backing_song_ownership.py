"""Phase 2C: Backing song-state ownership across a song change.

Live failure this pins: Say active (Backing 82 BPM) -> explicit pick of
All the Things You Are (catalog 72 BPM) -> Backing showed "Default 72 /
Current 82". ``resolve_active_bpm_sync_id`` caches the BPM sync id, and that
cache is also the regular-song Backing source identity, so after the switch
it still named Say: every ``gather_backing_filters`` read Say's Quick BPM
slider (82) into ATTYA's canonical Backing state, and
``expire_backing_play_session`` treated the switch as the same owner and
projected the outgoing song's defaults (82 / Say's Pop groove).

Fix: the song-change path retargets the cached BPM sync id to the new song
before any Backing expire/gather, and a proven song change ends the old play
session without projecting its defaults. The incoming song is initialized by
its own defaults (tempo AND groove), Backing keeps its own per-song groove
(Say's Backing default is Pop groove even though Practice's is Ballad), and a
genuine tempo edit is scoped to the song it was made on.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_play_session import current_backing_play_bpm, expire_backing_play_session_on_page_exit
from backing_track_state import (
    canonical_backing_filters,
    commit_backing_state_from_session,
    gather_backing_filters,
    mark_backing_user_edit,
    prepare_backing_page,
)
from practice_state import resolve_practice_groove_style
from song_catalog.catalog import format_pick_key
from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY, activate_catalog_song_for_backing
from songs.playback_defaults import backing_bpm_slider_widget_key, resolve_active_bpm_sync_id

SAY = format_pick_key("Pop", "Say — John Mayer")
ATTYA = format_pick_key("Jazz", "All the Things You Are — Jazz Standard")
CATALOG = {
    "Pop": {
        "Say — John Mayer": {
            "title": "Say", "artist": "John Mayer", "key": "G", "bpm": 82, "genre": "Pop",
            "extensions": {"default_groove": "Ballad"},
        }
    },
    "Jazz": {
        "All the Things You Are — Jazz Standard": {
            "title": "All the Things You Are", "artist": "Jazz Standard", "key": "Ab", "bpm": 72,
            "genre": "Jazz", "extensions": {"default_groove": "Jazz swing"},
        }
    },
}
DEFAULTS = {SAY: (82, "Pop groove"), ATTYA: (72, "Jazz swing")}  # Backing's own per-song defaults


class _RecordingSession(dict):
    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.writes: list[tuple[str, object]] = []

    def __setitem__(self, key, value) -> None:
        self.writes.append((key, value))
        super().__setitem__(key, value)


def _new_session() -> _RecordingSession:
    return _RecordingSession({USER_CATALOG_SOURCE_CHOICE_KEY: True, "active_music_source": SOURCE_CATALOG})


def _pick(session: dict, pick_key: str) -> None:
    """Genuine Songs-dropdown pick through the real commit path, then one app
    render (which resolves -- and caches -- the BPM sync id)."""
    activate_catalog_song_for_backing(
        SimpleNamespace(session_state=session), pick_key, reason="catalog_pick", song_picker_catalog=CATALOG
    )
    resolve_active_bpm_sync_id(session, pick_key=pick_key)


def _visit_backing(session: dict, pick_key: str) -> None:
    """One Backing page render for the active song, mirroring the app: it
    caches the page sync id and the song's default tempo, (re)starts the play
    session, seals the live tempo on save, then the user leaves Backing."""
    from backing_play_session import seal_live_backing_tempo_for_persist, sync_backing_play_session_on_backing_page

    sid = f"pk::{pick_key}"
    session["_backing_page_bpm_sync_id"] = sid
    session["_backing_trace_sync_id"] = sid
    session["_active_bpm_sync_id"] = sid
    session["_backing_catalog_default_bpm"] = DEFAULTS[pick_key][0]
    session["_backing_source_default_bpm"] = DEFAULTS[pick_key][0]
    sync_backing_play_session_on_backing_page(session)
    prepare_backing_page(session)
    seal_live_backing_tempo_for_persist(session)
    commit_backing_state_from_session(session, reason="page_change")
    expire_backing_play_session_on_page_exit(session, previous_page="backing", new_page="picker")


def _rerun_and_save(session: dict, reason: str = "page_change") -> None:
    prepare_backing_page(session)
    commit_backing_state_from_session(session, reason=reason)


def _bpm(session: dict) -> dict:
    canon = canonical_backing_filters(session) or {}
    return {
        "domain": session.get("backing_track_bpm"),
        "gather": gather_backing_filters(session).get("backing_track_bpm"),
        "canonical": canon.get("backing_track_bpm"),
        "current": current_backing_play_bpm(session),
    }


def _edit_tempo(session: dict, pick_key: str, bpm: int) -> None:
    """A real Quick BPM slider edit for the current song."""
    session[backing_bpm_slider_widget_key(f"pk::{pick_key}")] = bpm
    session["backing_track_bpm"] = bpm
    mark_backing_user_edit(session)


class TestA_TempoSongSwitch(unittest.TestCase):
    def test_say_to_attya_initializes_attya_tempo(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _rerun_and_save(session)
        self.assertEqual(_bpm(session)["gather"], 82)
        _pick(session, ATTYA)
        commit_backing_state_from_session(session, reason="song_edit")
        self.assertEqual(session["_active_bpm_sync_id"], f"pk::{ATTYA}")
        self.assertEqual(_bpm(session), {"domain": 72, "gather": 72, "canonical": 72, "current": 72})

    def test_switch_after_visiting_says_backing_page(self) -> None:
        """The live repro: Say's Backing page cached Say's default tempo and ran a
        Say play session before the switch."""
        session = _new_session()
        _pick(session, SAY)
        _visit_backing(session, SAY)
        _pick(session, ATTYA)
        commit_backing_state_from_session(session, reason="song_edit")
        self.assertEqual(_bpm(session), {"domain": 72, "gather": 72, "canonical": 72, "current": 72})
        _visit_backing(session, ATTYA)
        self.assertEqual(_bpm(session), {"domain": 72, "gather": 72, "canonical": 72, "current": 72})


class TestB_Reruns(unittest.TestCase):
    def test_attya_stays_72_across_reruns(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _pick(session, ATTYA)
        for _ in range(4):
            _rerun_and_save(session)
            self.assertEqual(_bpm(session), {"domain": 72, "gather": 72, "canonical": 72, "current": 72})


class TestC_GenuineCurrentSongTempoEdit(unittest.TestCase):
    def test_edit_survives_reruns(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _pick(session, ATTYA)
        _edit_tempo(session, ATTYA, 90)
        for _ in range(3):
            _rerun_and_save(session)
            self.assertEqual(_bpm(session)["gather"], 90)
            self.assertEqual(_bpm(session)["canonical"], 90)


class TestD_EditDoesNotLeak(unittest.TestCase):
    def test_attya_edit_does_not_become_says_tempo(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _pick(session, ATTYA)
        _edit_tempo(session, ATTYA, 90)
        _rerun_and_save(session)
        _pick(session, SAY)
        _rerun_and_save(session)
        self.assertEqual(_bpm(session), {"domain": 82, "gather": 82, "canonical": 82, "current": 82})


class TestE_ReturnSemantics(unittest.TestCase):
    """Existing product semantics, made explicit: there is no per-song memory
    of Backing tempo overrides -- a song change ends the play session, and
    returning to a song re-initializes it from that song's own default."""

    def test_return_to_attya_gets_its_default_not_the_old_edit(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _pick(session, ATTYA)
        _edit_tempo(session, ATTYA, 90)
        _rerun_and_save(session)
        _pick(session, SAY)
        _rerun_and_save(session)
        _pick(session, ATTYA)
        _rerun_and_save(session)
        self.assertEqual(_bpm(session), {"domain": 72, "gather": 72, "canonical": 72, "current": 72})


class TestF_GrooveTransition(unittest.TestCase):
    def test_outgoing_songs_groove_and_tempo_are_never_written_during_the_switch(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _rerun_and_save(session)
        self.assertEqual(session.get("backing_groove_style"), "Pop groove")
        session.writes.clear()
        _pick(session, ATTYA)
        commit_backing_state_from_session(session, reason="song_edit")
        say_bpm, say_groove = DEFAULTS[SAY]
        leaked = [
            (k, v) for k, v in session.writes
            if (k == "backing_groove_style" and v == say_groove)
            or (k == "backing_track_bpm" and v == say_bpm)
            or (k == "backing_track_state" and isinstance(v, dict)
                and (v.get("backing_groove_style") == say_groove or v.get("backing_track_bpm") == say_bpm))
        ]
        self.assertEqual(leaked, [], "outgoing song's Backing state was written during the switch")
        self.assertEqual(session.get("backing_groove_style"), "Jazz swing")
        self.assertEqual((canonical_backing_filters(session) or {}).get("backing_groove_style"), "Jazz swing")

    def test_backing_keeps_its_own_per_song_groove(self) -> None:
        """Backing and Practice defaults may legitimately differ for one song."""
        session = _new_session()
        _pick(session, ATTYA)
        _pick(session, SAY)
        _rerun_and_save(session)
        self.assertEqual(session.get("backing_groove_style"), "Pop groove")


class TestG_PracticeIsolation(unittest.TestCase):
    def test_programmatic_backing_groove_does_not_become_practice_groove(self) -> None:
        session = _new_session()
        _pick(session, SAY)
        _pick(session, ATTYA)
        session["_active_song_identity"] = f"pk::{ATTYA}"
        self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")
        session["backing_groove_style"] = "Pop groove"  # programmatic, no user intent
        for _ in range(3):
            self.assertEqual(resolve_practice_groove_style(session, default_groove="Jazz swing"), "Jazz swing")


class TestH_RepeatedSwitchingWithBackingVisits(unittest.TestCase):
    def test_say_attya_say_attya(self) -> None:
        session = _new_session()
        for pick_key in (SAY, ATTYA, SAY, ATTYA):
            _pick(session, pick_key)
            bpm, groove = DEFAULTS[pick_key]
            for _ in range(2):
                _rerun_and_save(session)
            _visit_backing(session, pick_key)
            _rerun_and_save(session)
            self.assertEqual(_bpm(session), {"domain": bpm, "gather": bpm, "canonical": bpm, "current": bpm}, pick_key)
            self.assertEqual(session.get("backing_groove_style"), groove, pick_key)


if __name__ == "__main__":
    unittest.main()
