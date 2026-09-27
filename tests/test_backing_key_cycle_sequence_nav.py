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


if __name__ == "__main__":
    unittest.main()
