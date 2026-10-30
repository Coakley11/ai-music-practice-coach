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
from concurrent.futures import Future

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

    def test_poller_keeps_completion_marker_for_full_run_consumer(self) -> None:
        session: dict = {}
        app._backing_mark_wav_building(session, SIG)
        BACKING_WAV_CACHE[SIG] = b"RIFFfake"

        class _PollerSt:
            def __init__(self):
                self.session_state = session
                self.reruns: list[str] = []

            def caption(self, _message):
                return None

            def fragment(self, **_kwargs):
                return lambda func: func

            def rerun(self, *, scope):
                self.reruns.append(scope)

        fake = _PollerSt()
        app._render_backing_wav_building_poller(fake)

        self.assertEqual(fake.reruns, ["app"])
        self.assertEqual(session.get(app.BACKING_WAV_BUILDING_KEY), SIG)


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

    def test_failed_future_is_consumed_as_bounded_error(self) -> None:
        failed = Future()
        failed.set_exception(RuntimeError("synthesis exploded"))
        BACKING_WAV_FUTURES[SIG] = failed

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

        self.assertIsNone(wav)
        self.assertEqual(status, "error")
        self.assertNotIn(SIG, BACKING_WAV_FUTURES)


class TestAsyncInstallControlFlow(unittest.TestCase):
    def test_pending_path_cannot_reach_b64_install_writer(self) -> None:
        source = __import__("inspect").getsource(app)
        generation = source.split("_wav_pending = False", 1)[1].split(
            "if _play_clicked:", 1
        )[0]
        guard = generation.index("if _wav_pending or _wav_failed:")
        b64_writer = generation.index(
            'st.session_state["_last_backing_signature"] = _current_backing_signature'
        )
        self.assertLess(guard, b64_writer)
        self.assertIn("_arr_stale = bool(_wav_pending or _wav_failed or _take_stale)", generation)

    def test_completed_background_build_reenters_generation_install(self) -> None:
        source = __import__("inspect").getsource(app)
        self.assertIn("_async_wav_ready = backing_wav_build_ready", source)
        self.assertIn(
            "(_play_clicked and not _backing_audio_ready) or _async_wav_ready",
            source,
        )


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


class TestPendingRequestIdentity(unittest.TestCase):
    def test_same_signature_source_back_replaces_old_pending_job(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from backing_take_identity import capture_take_request
        from backing_transport_intent import begin_playback, stop_playback
        old = Future();old.set_running_or_notify_cancel()
        new = Future()
        ss={'active_music_source':'custom_progression','active_catalog_pick_key':'custom::trial',
            'display_key':'D','concert_key':'D','practice_key_by_source':{'custom::trial':'D'}}
        begin_playback(ss)
        old._backing_take_request=capture_take_request(ss)
        BACKING_WAV_FUTURES[SIG]=old;BACKING_WAV_CACHE.pop(SIG,None)
        stop_playback(ss);begin_playback(ss)
        request=capture_take_request(ss)
        kwargs=dict(backing_events=[],bpm=100,loops=1,style='Pop groove',level='Intermediate',
                    song_title='Trial Song',song_artist='',time_signature='4/4',take_request=request)
        try:
            with patch.object(app,'_BACKING_WAV_EXECUTOR',SimpleNamespace(submit=lambda *a,**k:new)):
                wav,status=app._cached_backing_wav_nonblocking(SIG,**kwargs)
            self.assertEqual(status,'started');self.assertIsNone(wav)
            self.assertIs(BACKING_WAV_FUTURES[SIG],new)
            old.set_result(b'old-request')
            self.assertNotIn(SIG,BACKING_WAV_CACHE)
            new.set_result(b'current-request')
            wav,status=app._cached_backing_wav_nonblocking(SIG,**kwargs)
            self.assertEqual((wav,status),(b'current-request','ready'))
        finally:
            BACKING_WAV_FUTURES.pop(SIG,None);BACKING_WAV_CACHE.pop(SIG,None)

    def test_readiness_does_not_advertise_old_completed_job_after_stop(self):
        from backing_take_identity import capture_take_request
        from backing_transport_intent import begin_playback,stop_playback
        ss={};begin_playback(ss)
        fut=Future();fut._backing_take_request=capture_take_request(ss);fut.set_result(b'old')
        BACKING_WAV_FUTURES[SIG]=fut;BACKING_WAV_CACHE.pop(SIG,None)
        app._backing_mark_wav_building(ss,SIG);stop_playback(ss)
        try:
            self.assertFalse(app.backing_wav_build_ready(ss))
            self.assertNotIn(SIG,BACKING_WAV_FUTURES)
            self.assertNotIn(SIG,BACKING_WAV_CACHE)
        finally:BACKING_WAV_FUTURES.pop(SIG,None)


def tearDownModule() -> None:
    """Importing the app runs it once in bare mode, which fills Streamlit's
    session state and the cached cloud config. Leave neither to later test
    files (the cold-entry hydration tests read both)."""
    import streamlit as st

    try:
        st.session_state.clear()
    except Exception:
        pass
    from suite_storage_config import reset_cloud_config_cache

    reset_cloud_config_cache()
