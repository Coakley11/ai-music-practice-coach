"""Karaoke Play / Next / Previous transport (Now Singing playback).

Live first wrong steps (Now Editing = Shape of You Bm, singing Perfect A):

* Play was silent: during a Karaoke set ``restore_regular_song_backing``
  compared the Backing context with the singing pick while the Catalog rebuild
  binds it to the global pick, so every run "changed song", rebuilt and
  invalidated the WAV the Karaoke auto-generate had just made. Readiness also
  counted a leftover key-cycle static URL (cycling off) as audio, so Play
  skipped generating and the plain player mounted nothing.
* Next / Previous: the destination played the previous song's tempo (the play
  session kept it as an override) and its new take never started -- the
  per-song Backing presentation was only initialized by Play, so every run
  after Next reset autoplay.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest import mock

import karaoke_mode as km
from tests.test_r11_empty_and_composition_sbi import PERFECT, _Base

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
LOVE_STORY = ("Country", "Love Story — Taylor Swift")


class TestKaraokeRestoreKeepsTheGeneratedTake(_Base):
    def _singing(self) -> dict:
        from song_catalog.catalog import format_pick_key

        session = self.new_session()
        session["instrument"] = "Voice"
        shape = ("Pop", "Shape of You — Ed Sheeran")
        for genre_title in (PERFECT, LOVE_STORY):
            km.add_to_queue(session, format_pick_key(*genre_title), title=genre_title[1].split(" — ")[0])
        self.activate_catalog(session, *shape)                          # Now Editing: Shape of You
        km.start_session(session)                                       # Now Singing: Perfect
        return session

    def test_same_singing_song_keeps_context_and_audio(self) -> None:
        import backing_context as bc
        import songs.key_state as ks

        session = self._singing()
        try:
            bc.restore_regular_song_backing(session)                   # first restore for Perfect
        except Exception:
            pass
        session["_last_backing_wav_path"] = "take.wav"
        session["_last_backing_signature"] = ("Perfect",)
        with mock.patch.object(ks, "invalidate_backing_cache") as inv:
            try:
                bc.restore_regular_song_backing(session)
            except Exception:
                pass
        self.assertFalse(inv.called, "a rerun for the same singing song must not invalidate its take")
        self.assertEqual(session.get("_last_backing_wav_path"), "take.wav")

    def test_a_new_singing_song_is_a_song_change(self) -> None:
        import backing_context as bc
        import backing_play_session as bps

        session = self._singing()
        try:
            bc.restore_regular_song_backing(session)
        except Exception:
            pass
        km.advance_session(session)                                     # Now Singing: Love Story
        calls: list[bool] = []
        real = bps.expire_backing_play_session

        def spy(s, *, song_changed=False):
            calls.append(bool(song_changed))
            return real(s, song_changed=song_changed)

        with mock.patch.object(bps, "expire_backing_play_session", spy):
            try:
                bc.restore_regular_song_backing(session)
            except Exception:
                pass
        self.assertEqual(calls[:1], [True])


class TestTransitionStartsTheDestinationAtItsOwnTempo(_Base):
    def test_transition_ends_the_play_session_and_queues_a_tempo_reset(self) -> None:
        from backing_play_session import BACKING_PLAY_SESSION_KEY, get_backing_play_session
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition

        session = self.new_session()
        session[BACKING_PLAY_SESSION_KEY] = {
            "play_session_id": "p", "launch_id": "l", "source_identity": "s",
            "expired": False, "defaults": {"bpm": 95}, "overrides": {"bpm": 95},
        }
        session["backing_track_bpm"] = 95
        session["backing_track_bpm::pk::Pop\x1fPerfect"] = 95
        _invalidate_stale_backing_for_karaoke_transition(session)
        ps = get_backing_play_session(session) or {}
        self.assertTrue(ps.get("expired"))
        self.assertEqual(ps.get("overrides"), {})
        self.assertNotIn("backing_track_bpm", session)
        self.assertFalse(any(str(k).startswith("backing_track_bpm::") for k in session))
        self.assertTrue(session.get(km.KARAOKE_TEMPO_RESET_PENDING_KEY))

    def test_backing_applies_the_tempo_reset_before_song_defaults(self) -> None:
        i = APP.index("km.KARAOKE_TEMPO_RESET_PENDING_KEY, False")
        j = APP.index("_backing_canon = canonicalize_backing_defaults_for_song(", i)
        self.assertIn("_force_backing_reset = True", APP[i:j])

    def test_auto_generate_initializes_the_destination_presentation(self) -> None:
        i = APP.index("km.consume_pending_auto_generate(st.session_state)")
        block = APP[i : i + 900]
        self.assertIn("initialize_backing_presentation(st.session_state, _bpm_sync_id)", block)


def test_static_url_is_ready_only_while_key_cycling_plays_it() -> None:
    i = APP.index("def _session_backing_audio_ready(")
    body = APP[i : APP.index("\ndef ", i + 10)]
    assert "(has_static and cycle_on)" in body
    assert "if not (has_bytes or has_path or has_static):" not in body


def test_card_intent_is_consumed_once_per_click() -> None:
    from backing_card_transport import (
        BACKING_CARD_TRANSPORT_KEY,
        consume_backing_card_transport_action,
    )

    session: dict = {BACKING_CARD_TRANSPORT_KEY: {"action": "play", "nonce": 1, "session": "a"}}
    assert consume_backing_card_transport_action(session) == "play"
    assert consume_backing_card_transport_action(session) == ""
    session[BACKING_CARD_TRANSPORT_KEY] = {"action": "stop", "nonce": 2, "session": "a"}
    assert consume_backing_card_transport_action(session) == "stop"
    session[BACKING_CARD_TRANSPORT_KEY] = {"action": "bogus", "nonce": 3, "session": "a"}
    assert consume_backing_card_transport_action(session) == ""


def test_one_transport_control_and_transition_hook() -> None:
    html = (ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")
    assert "karaoke_skip_to_next" in html and "karaoke_previous_song" in html
    assert "__backingTransportSilenced" in html
    assert 'key="play_backing_btn"' not in APP and 'key="stop_backing_btn"' not in APP
    import backing_card_transport

    assert "musical state" in inspect.getsource(backing_card_transport)
