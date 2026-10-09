"""Backing audio regeneration must not block the Streamlit run.

Full-arrangement synthesis measured 16-27s for a 40-60MB WAV and used to run
inline on the main thread, freezing every control in the session and then
triggering a second full page render. It now goes to the shared background
executor whenever a backing experience is already underway, and the player /
transport stay mounted until the new take swaps in.
"""
from __future__ import annotations

import time
import unittest

import streamlit_music_practice_app as app
from backing_wav_runtime_cache import BACKING_WAV_CACHE, BACKING_WAV_FUTURES


SIG = ("async-test-song", "Am", "Intermediate", "Pop groove", 100, "4/4", 2, (), "Strong", False, "p", 4, 4, 0, "arr_v2")


def _events():
    return ["Am", "F", "C", "G"]


class TestBuildingStateHelpers(unittest.TestCase):
    def setUp(self) -> None:
        BACKING_WAV_CACHE.pop(SIG, None)
        BACKING_WAV_FUTURES.pop(SIG, None)

    tearDown = setUp

    def test_no_building_state_by_default(self) -> None:
        session: dict = {}
        self.assertFalse(app.backing_wav_is_building(session))
        self.assertFalse(app.backing_wav_build_ready(session))

    def test_marked_signature_reports_building_then_ready(self) -> None:
        session: dict = {}
        app._backing_mark_wav_building(session, SIG)
        # No future and no cache entry yet → nothing outstanding.
        self.assertFalse(app.backing_wav_is_building(session))
        # Once the bytes exist it reports ready, not building.
        BACKING_WAV_CACHE[SIG] = b"RIFFfake"
        self.assertFalse(app.backing_wav_is_building(session))
        self.assertTrue(app.backing_wav_build_ready(session))
        app._backing_clear_wav_building(session)
        self.assertFalse(app.backing_wav_build_ready(session))


class TestNonBlockingSynthesis(unittest.TestCase):
    def setUp(self) -> None:
        BACKING_WAV_CACHE.pop(SIG, None)
        BACKING_WAV_FUTURES.pop(SIG, None)

    tearDown = setUp

    def test_first_call_returns_immediately_and_schedules_work(self) -> None:
        t0 = time.perf_counter()
        wav, status = app._cached_backing_wav_nonblocking(
            SIG,
            backing_events=_events(),
            bpm=100,
            loops=1,
            style="Pop groove",
            level="Intermediate",
            song_title="Async Test",
            song_artist="",
            time_signature="4/4",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertEqual(status, "started")
        self.assertIsNone(wav)
        # The whole point: the caller is not paying synthesis time.
        self.assertLess(elapsed_ms, 2000, elapsed_ms)
        self.assertIn(SIG, BACKING_WAV_FUTURES)

    def test_result_lands_in_the_shared_cache(self) -> None:
        for _ in range(2):
            app._cached_backing_wav_nonblocking(
                SIG,
                backing_events=_events(),
                bpm=100,
                loops=1,
                style="Pop groove",
                level="Intermediate",
                song_title="Async Test",
                song_artist="",
                time_signature="4/4",
            )
        fut = BACKING_WAV_FUTURES.get(SIG)
        self.assertIsNotNone(fut)
        fut.result(timeout=180)
        wav, status = app._cached_backing_wav_nonblocking(
            SIG,
            backing_events=_events(),
            bpm=100,
            loops=1,
            style="Pop groove",
            level="Intermediate",
            song_title="Async Test",
            song_artist="",
            time_signature="4/4",
        )
        self.assertEqual(status, "ready")
        self.assertTrue(wav)
        self.assertIn(SIG, BACKING_WAV_CACHE)

    def test_cache_hit_is_immediate_and_never_schedules(self) -> None:
        BACKING_WAV_CACHE[SIG] = b"RIFFcached"
        wav, status = app._cached_backing_wav_nonblocking(
            SIG,
            backing_events=_events(),
            bpm=100,
            loops=1,
            style="Pop groove",
            level="Intermediate",
            song_title="Async Test",
            song_artist="",
            time_signature="4/4",
        )
        self.assertEqual(status, "ready")
        self.assertEqual(wav, b"RIFFcached")
        self.assertNotIn(SIG, BACKING_WAV_FUTURES)


class TestPlayerStaysMountedWhileRebuilding(unittest.TestCase):
    """The transport row must not blink out during a background rebuild."""

    def setUp(self) -> None:
        BACKING_WAV_CACHE.pop(SIG, None)
        BACKING_WAV_FUTURES.pop(SIG, None)

    tearDown = setUp

    def test_audio_ready_is_true_while_building(self) -> None:
        session: dict = {}
        app._backing_mark_wav_building(session, SIG)

        class _NeverDone:
            @staticmethod
            def done() -> bool:
                return False

        BACKING_WAV_FUTURES[SIG] = _NeverDone()
        try:
            self.assertTrue(app.backing_wav_is_building(session))
            self.assertTrue(app._session_backing_audio_ready(session, SIG))
        finally:
            BACKING_WAV_FUTURES.pop(SIG, None)

    def test_audio_ready_is_true_in_the_handoff_window(self) -> None:
        """Executor finished but bytes not installed in session yet."""
        session: dict = {}
        app._backing_mark_wav_building(session, SIG)
        BACKING_WAV_CACHE[SIG] = b"RIFFfake"
        self.assertFalse(app.backing_wav_is_building(session))
        self.assertTrue(app.backing_wav_build_ready(session))
        self.assertTrue(app._session_backing_audio_ready(session, SIG))

    def test_unrelated_session_is_unaffected(self) -> None:
        session: dict = {}
        self.assertFalse(app._session_backing_audio_ready(session, SIG))


if __name__ == "__main__":
    unittest.main()
