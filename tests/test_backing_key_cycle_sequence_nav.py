"""Descending whole-tone Next/Previous follow displayed sequence order."""
from __future__ import annotations

import unittest

from backing_key_cycle import (
    BACKING_KEY_CYCLE_SESSIONS_KEY,
    cycle_key_sequence,
    cycle_sequence_index,
    hard_stop_key_cycle_audio,
    peek_cycle_key_at_delta,
    restart_key_cycle_audio,
    start_key_cycle,
    temporary_playback_key,
)
import backing_key_cycle as k


class TestKeyCycleSequenceNav(unittest.TestCase):
    def _session(self):
        return {
            "backing_source_kind": "catalog",
            "practice_key": "Bm",
            "concert_practice_key": "Bm",
            BACKING_KEY_CYCLE_SESSIONS_KEY: {},
        }

    def test_descending_whole_tone_sequence(self):
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        seq = cycle_key_sequence(ss)
        self.assertEqual(seq, ["Bm", "Am", "Gm", "Fm", "Ebm", "Dbm"])
        for i, expect in enumerate(seq):
            self.assertEqual(temporary_playback_key(ss), expect)
            self.assertEqual(seq[cycle_sequence_index(ss)], expect)
            self.assertEqual(peek_cycle_key_at_delta(ss, steps=1), seq[(i + 1) % 6])
            self.assertEqual(peek_cycle_key_at_delta(ss, steps=-1), seq[(i - 1) % 6])
            k._step_owner_cycle(ss, steps=1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Bm")

    def test_bm_next_am_previous_returns_bm(self):
        """Manual Next Bm→Am then Previous must restore Bm (not wrap to Gm)."""
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        self.assertEqual(temporary_playback_key(ss), "Bm")
        k._step_owner_cycle(ss, steps=1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Am")
        self.assertEqual(cycle_sequence_index(ss), 1)
        self.assertEqual(peek_cycle_key_at_delta(ss, steps=-1), "Bm")
        k._step_owner_cycle(ss, steps=-1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Bm")
        self.assertEqual(cycle_sequence_index(ss), 0)

    def test_gm_next_fm_prev_am(self):
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        for _ in range(2):
            k._step_owner_cycle(ss, steps=1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Gm")
        k._step_owner_cycle(ss, steps=1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Fm")
        k._step_owner_cycle(ss, steps=-1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Gm")
        k._step_owner_cycle(ss, steps=-1, force=True, queue_continue=False)
        self.assertEqual(temporary_playback_key(ss), "Am")

    def test_pause_resume_flags_preserve_hold_not_restart(self):
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        hard_stop_key_cycle_audio(ss)
        self.assertTrue(ss.get("_kc_pause_audio") or ss.get("_kc_hard_stop"))
        restart_key_cycle_audio(ss)
        self.assertTrue(ss.get("_kc_resume_play"))
        self.assertFalse(bool(ss.get("_kc_restart_play")))
        self.assertFalse(bool(ss.get("_kc_pause_audio")))

    def test_stop_resume_does_not_request_restart_seek(self):
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        hard_stop_key_cycle_audio(ss)
        self.assertTrue(ss.get("_kc_hard_stop"))
        restart_key_cycle_audio(ss)
        self.assertTrue(ss.get("_kc_resume_play"))
        self.assertFalse(bool(ss.get("_kc_restart_play")))


class _FakeSt:
    def markdown(self, *_a, **_kw):
        return None


class TestManualNextAutoplayOnCacheHit(unittest.TestCase):
    """Regression for: Manual Next landing on a prefetch-cached key published
    autoplay=False (skip_remount vetoed it unconditionally), leaving the new
    buffer loaded but silent — the Pause/Resume label stayed "Pause" while the
    audio element sat paused+muted indefinitely. A forced restart must win.
    """

    def _session(self):
        return {
            "backing_source_kind": "catalog",
            "practice_key": "Bm",
            "concert_practice_key": "Bm",
            BACKING_KEY_CYCLE_SESSIONS_KEY: {},
        }

    def _captured_cmd(self, session, **kwargs):
        import json as _json
        import backing_key_cycle as k

        captured = {}

        def _fake_bridge_html(*, cmd_json):
            captured["cmd"] = _json.loads(cmd_json)
            return "<div></div>"

        orig_bridge = k.cycle_persistent_player_bridge_html
        orig_on_disk = k._kc_static_url_on_disk
        k.cycle_persistent_player_bridge_html = _fake_bridge_html
        k._kc_static_url_on_disk = lambda url: True
        try:
            k.render_backing_key_cycle_persistent_player(
                _FakeSt(),
                session,
                current_url="/app/static/kc/fake0000000000000000.wav",
                **kwargs,
            )
        finally:
            k.cycle_persistent_player_bridge_html = orig_bridge
            k._kc_static_url_on_disk = orig_on_disk
        return captured.get("cmd") or {}

    def test_restart_play_forces_autoplay_despite_skip_remount(self):
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        ss["_backing_autoplay"] = True
        # Mirrors _step_owner_cycle(force=True) landing on a prefetch cache hit.
        ss["_kc_skip_audio_remount"] = True
        ss["_kc_restart_play"] = True
        cmd = self._captured_cmd(ss, autoplay=True)
        self.assertTrue(cmd.get("autoplay"), cmd)
        self.assertTrue(cmd.get("restart"), cmd)
        self.assertFalse(cmd.get("paused"), cmd)

    def test_skip_remount_alone_still_suppresses_autoplay(self):
        """Without a forced restart, skip_remount keeps its original job: don't
        re-autoplay on a routine prefetch-driven remount."""
        ss = self._session()
        start_key_cycle(ss, start_key="Bm", interval=2, direction="down")
        ss["_backing_autoplay"] = True
        ss["_kc_skip_audio_remount"] = True
        cmd = self._captured_cmd(ss, autoplay=True)
        self.assertFalse(cmd.get("autoplay"), cmd)


if __name__ == "__main__":
    unittest.main()
