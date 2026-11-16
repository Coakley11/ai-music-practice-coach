"""A temporary karaoke key must never become the song's permanent Practice Key.

These tests exist because the previous ones could not fail. ``durable_commit`` in
``test_karaoke_performance_key_persistence.py`` is *copied* from the real lane ("Copied rather
than called because the real one needs a Streamlit script run") and copies it in the order
retune-then-commit. The real sidebar callback on the Backing page does the opposite: it writes
the durable store through ``commit_backing_practice_key`` (app line 17715) and only 43 lines
later registers the performance retune (line 17758). The freeze asked a predicate that is True
only once that register is filled, so it protected the second retune of a set and never the
first. 44 tests passed over a live defect that cost a musician their saved key:

    before   practice_key_by_source {"Pop<US>Say - John Mayer": "D"}   entry Bb
    after    practice_key_by_source {"Pop<US>Say - John Mayer": "Ab"}  entry Bb   <- for good

So everything here calls PRODUCTION functions - ``commit_backing_practice_key``,
``km.start_session``, ``km.retune_now_singing_entry``, ``km.advance_session``,
``km.stop_session``, ``set_practice_concert_key`` - and reads the key back from the state file
that ``persist_music_disk_state`` actually writes, not from the session dict alone.

``test_the_real_lane_is_live_and_still_saves_outside_karaoke`` is the control: it proves these
tests are not passing because the lane silently declines to write. Remove the fix and the
first-retune tests must fail.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The data dir is resolved when the persistence module loads, so it has to be pointed at a
# throwaway directory BEFORE any app import - setting it later wrote this test's keys into the
# worktree's own data/workspaces/daniel/music_user_state.json instead.
_DATA_DIR = tempfile.mkdtemp(prefix="pk-hotfix-tests-")
os.environ["MUSIC_APP_DATA_DIR"] = _DATA_DIR
atexit.register(lambda: shutil.rmtree(_DATA_DIR, ignore_errors=True))

import karaoke_mode as km  # noqa: E402
from backing_practice_key_control import commit_backing_practice_key  # noqa: E402
from songs.practice_key_state import (  # noqa: E402
    PRACTICE_KEY_BY_SOURCE_KEY,
    get_practice_concert_key,
    saved_practice_concert_key,
    set_practice_concert_key,
)

SAY = "Pop\x1fSay — John Mayer"
PERFECT = "Pop\x1fPerfect — Ed Sheeran"


class _Stub:
    """Just enough of ``st`` for the real persistence writer."""

    def __init__(self, session: dict) -> None:
        self.session_state = session


def norm(key: str) -> str:
    return str(key or "").strip().replace("♭", "b").replace(" major", "").lower()


def saved_for(session: dict, pick: str = SAY) -> str:
    return norm(saved_practice_concert_key(session, pick))


def entry_for(session: dict, pick: str = SAY) -> str:
    for row in km.get_queue(session) or []:
        if str(row.get("pick_key") or "") == pick:
            return norm(km.entry_default_practice_key(row))
    return ""


def saved_on_disk(session: dict, pick: str = SAY) -> str:
    """What the persisted state file really holds - the thing the musician comes back to.

    Written by the production writer and read back from the file, because "the session dict
    says D" is not the same claim as "D is what was saved".
    """
    import music_persistent_state as mps

    # Where the writer puts the file depends on when the app modules were imported, so in a
    # full-suite run another module can win that race and this would read an empty temp dir and
    # report "nothing saved" for every assertion. So: clear both candidates, write, then read
    # whichever one the app actually used.
    roots = [Path(_DATA_DIR), ROOT / "data"]
    for root in roots:
        for stale in root.rglob("music_user_state.json"):
            stale.unlink(missing_ok=True)
    mps.persist_music_disk_state(_Stub(session))
    found: list[str] = []
    written = [p for root in roots for p in root.rglob("music_user_state.json")]
    for path in written:
        data = json.loads(path.read_text(encoding="utf-8"))
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                store = cur.get("practice_key_by_source")
                if isinstance(store, dict) and pick in store:
                    found.append(str(store[pick]))
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return norm(found[0]) if found else ""


def song_session(pick: str = SAY, saved: str = "D") -> dict:
    """A session with ``pick`` as the active catalog song, saved in ``saved``."""
    session: dict = {
        "active_catalog_pick_key": pick,
        "instrument": "Voice",
        "studio_page": "backing",
    }
    # The musician's own choice, made with nothing performing, through the real primitive.
    set_practice_concert_key(session, saved, pick_key=pick)
    return session


def performing(entry_key: str = "Bb", saved: str = "D", pick: str = SAY) -> dict:
    """``pick`` queued at ``entry_key`` and a set running, all through production calls."""
    session = song_session(pick, saved)
    km.add_to_queue(session, pick, practice_key=entry_key, title="Say", artist="John Mayer")
    km.start_session(session)
    return session


def sidebar_gesture_on_backing(session: dict, token: str) -> None:
    """The real callback's order: durable commit first, retune second.

    This is the sequence that lost the key - ``_on_mission_or_global_pk_change`` commits at app
    line 17715 and retunes at 17758 - so it is the sequence the test drives.
    """
    commit_backing_practice_key(session, token)
    km.retune_now_singing_entry(session, token)


class TheLaneIsReal(unittest.TestCase):
    """Anti-vacuity: if the production lane declined to write, every test below would pass."""

    def test_the_real_lane_is_live_and_still_saves_outside_karaoke(self) -> None:
        session = song_session(saved="D")
        self.assertEqual(saved_for(session), "d")
        commit_backing_practice_key(session, "F")
        self.assertEqual(saved_for(session), "f", "the real lane must still save with no set")
        self.assertEqual(saved_on_disk(session), "f", "and it must reach the state file")

    def test_the_write_freeze_does_not_depend_on_a_retune_having_happened(self) -> None:
        session = performing()
        # Nothing retuned yet - the exact window the durable commit used to slip through.
        self.assertEqual(km.performance_retuned_entry_ids(session), [])
        self.assertTrue(km.performance_locks_song_key(session, SAY))

    def test_the_read_layer_still_waits_for_a_real_retune(self) -> None:
        session = performing()
        self.assertFalse(km.performance_owns_song_key(session, SAY))
        self.assertEqual(norm(get_practice_concert_key(session, SAY)), "d")


class FirstAndLaterRetunes(unittest.TestCase):
    def test_the_first_retune_of_a_set_keeps_the_saved_key(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        self.assertEqual(saved_for(session), "d", "the song's own Practice Key must survive")
        self.assertEqual(entry_for(session), "bb", "the saved setlist entry must survive")
        self.assertEqual(saved_on_disk(session), "d", "and the state file must hold D")

    def test_the_performance_really_is_in_the_temporary_key(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        # What the musician HEARS is tonight's key, which is the whole point of the retune.
        self.assertEqual(norm(km.current_session_practice_key(session)), "ab")
        self.assertEqual(norm(get_practice_concert_key(session, SAY)), "ab")
        # ... while what is SAVED is still theirs.
        self.assertEqual(saved_for(session), "d")

    def test_the_second_and_later_retunes_keep_it_too(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        for token in ("Ab", "F", "C", "Eb"):
            sidebar_gesture_on_backing(session, token)
            self.assertEqual(saved_for(session), "d", f"lost after retuning to {token}")
        self.assertEqual(norm(km.current_session_practice_key(session)), "eb")
        self.assertEqual(entry_for(session), "bb")
        self.assertEqual(saved_on_disk(session), "d")

    def test_the_other_call_order_is_protected_as_well(self) -> None:
        """Whichever order a future edit puts them in, the saved key survives."""
        session = performing(entry_key="Bb", saved="D")
        km.retune_now_singing_entry(session, "Ab")
        commit_backing_practice_key(session, "Ab")
        self.assertEqual(saved_for(session), "d")
        self.assertEqual(saved_on_disk(session), "d")

    def test_a_retune_straight_to_the_songs_own_saved_key_still_keeps_it(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "D")
        self.assertEqual(saved_for(session), "d")
        self.assertEqual(entry_for(session), "bb")


class TransportAndTransitions(unittest.TestCase):
    def test_stop_leaves_both_keys_alone(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        from backing_transport_intent import stop_playback

        stop_playback(session, reason="test-stop")
        self.assertEqual(saved_for(session), "d")
        self.assertEqual(entry_for(session), "bb")
        self.assertEqual(saved_on_disk(session), "d")

    def test_pause_and_resume_leave_both_keys_alone(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        from backing_transport_intent import note_playback_settings_changed, pause_playback

        pause_playback(session, reason="test-pause")
        self.assertEqual(saved_for(session), "d")
        note_playback_settings_changed(session, reason="test-resume")
        self.assertEqual(saved_for(session), "d")
        self.assertEqual(entry_for(session), "bb")

    def test_ending_the_set_leaves_the_saved_key_and_the_entry(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        km.stop_session(session)
        self.assertEqual(saved_for(session), "d", "End Set must not leave Ab behind")
        self.assertEqual(entry_for(session), "bb")
        self.assertEqual(saved_on_disk(session), "d")

    def test_reopening_the_song_after_the_set_shows_the_saved_key(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        km.stop_session(session)
        # Nothing is performing now, so both the read layer and the store must say D.
        self.assertEqual(norm(get_practice_concert_key(session, SAY)), "d")
        self.assertEqual(saved_for(session), "d")

    def test_skip_to_the_next_song_keeps_each_songs_own_saved_key(self) -> None:
        session = song_session(SAY, "D")
        set_practice_concert_key(session, "G", pick_key=PERFECT)
        km.add_to_queue(session, SAY, practice_key="Bb", title="Say")
        km.add_to_queue(session, PERFECT, practice_key="Ab", title="Perfect")
        km.start_session(session)
        sidebar_gesture_on_backing(session, "Ab")          # retune Say for tonight
        self.assertEqual(saved_for(session, SAY), "d")

        km.advance_session(session)                        # Skip to Perfect
        session["active_catalog_pick_key"] = PERFECT
        sidebar_gesture_on_backing(session, "C")           # retune Perfect for tonight
        self.assertEqual(saved_for(session, PERFECT), "g", "Perfect's own key must survive")
        self.assertEqual(saved_for(session, SAY), "d", "and Say's must still be there")
        self.assertEqual(entry_for(session, SAY), "bb")
        self.assertEqual(entry_for(session, PERFECT), "ab")

    def test_another_song_is_never_frozen_by_the_one_being_sung(self) -> None:
        """The freeze must stay narrow: only the song being sung.

        One saving write per pick here on purpose. A SECOND write to the same pick is refused by
        an older, unrelated protection - "a recent explicit user Practice Key commit" is held
        against stale remount writes that land a second or two later - and a test that tripped
        over that would be reporting someone else's rule as this freeze.
        """
        session = performing(entry_key="Bb", saved="D")
        self.assertFalse(km.performance_locks_song_key(session, PERFECT))
        set_practice_concert_key(session, "G", pick_key=PERFECT)
        self.assertEqual(saved_for(session, PERFECT), "g",
                         "a song that is not being sung must save normally during a set")
        self.assertEqual(saved_for(session, SAY), "d")
        self.assertEqual(saved_on_disk(session, PERFECT), "g")


class RerunsAndNavigation(unittest.TestCase):
    def test_repeated_commits_during_the_performance_never_move_it(self) -> None:
        """A rerun re-runs the same hydration and commit paths; none may move the saved key."""
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        for _ in range(5):
            commit_backing_practice_key(session, "Ab")
            self.assertEqual(saved_for(session), "d")
        self.assertEqual(saved_on_disk(session), "d")

    def test_navigating_between_pages_during_a_performance_keeps_it(self) -> None:
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        for page in ("songs", "practice", "creative", "backing"):
            session["studio_page"] = page
            commit_backing_practice_key(session, "Ab")
            self.assertEqual(saved_for(session), "d", f"lost while on the {page} page")
        self.assertEqual(saved_on_disk(session), "d")

    def test_the_store_is_not_quietly_emptied_instead(self) -> None:
        """Refusing the write must not mean deleting the entry - D has to still be in there."""
        session = performing(entry_key="Bb", saved="D")
        sidebar_gesture_on_backing(session, "Ab")
        store = session.get(PRACTICE_KEY_BY_SOURCE_KEY) or {}
        self.assertIn(SAY, store)
        self.assertEqual(norm(store[SAY]), "d")


if __name__ == "__main__":
    unittest.main()
