"""A take promoted from the prepared bag is never adopted as an explicit Play.

Reproduced on a Mission (2026-11-13): after the natural handoff Bm -> Cm the
page saw Cm's prepared URL differ from the Play-time WAV, adopted it as an
arrangement replace, and its sticky markers (cleared only by a forcePlay
publish) made the pass bridge drop every later natural ack as
``explicit_play_owns``. The browser advanced to C#m, Python stayed on Cm and
the next republish snapped the audio back: advance-then-revert, audible
stop / restart, for ~30 s until a manual Next cleared the markers.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import backing_key_cycle as kc


class TestPromotedTakeIsNotAPlay(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.paths = {}
        for key in ("Bm", "Cm"):
            p = root / f"{key}.wav"
            p.write_bytes(b"RIFF")
            self.paths[key] = str(p)
        patches = [
            mock.patch.object(kc, "_prepared_entry_current", return_value=True),
            mock.patch.object(kc, "publish_cycle_wav_static_url", side_effect=lambda p, signature=None: f"app/static/kc/{Path(p).name}"),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch("monetization_entitlements.can_use", return_value=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "Bm", "concert_key": "Bm"}
        kc.start_key_cycle(self.ss, start_key="Bm", interval=1, direction="up")
        self.ss[kc.BACKING_KEY_CYCLE_PREPARED_KEY] = {
            k: {"path": self.paths[k], "signature": ("sig", k), "static_url": f"app/static/kc/{k}.wav"}
            for k in ("Bm", "Cm")
        }
        # The explicit Play's own take (Bm) has been adopted.
        self.ss["_last_backing_wav_path"] = self.paths["Bm"]
        self.assertTrue(kc.play_wav_adoption_needed(self.ss, "app/static/kc/Bm.wav", ""))

    def _natural_step(self) -> None:
        # The pass bridge's natural handoff: step to the next key, install its prepared take.
        kc._advance_owner_cycle(self.ss, force=False, queue_continue=False, allow_wrap=False)
        self.assertEqual(kc.temporary_playback_key(self.ss), "Cm")

    def test_natural_handoff_take_is_not_adopted(self) -> None:
        self._natural_step()
        self.assertEqual(self.ss["_last_backing_wav_path"], self.paths["Cm"])
        # Before the fix this was True: Cm's URL differs from the Play-time Bm URL.
        self.assertFalse(
            kc.play_wav_adoption_needed(self.ss, "app/static/kc/Cm.wav", "app/static/kc/Cm.wav")
        )
        # So no sticky explicit-Play marker can hold the pass bridge.
        for marker in ("_kc_arrangement_url", "_kc_force_arrangement_replace"):
            self.assertFalse(self.ss.get(marker))

    def test_explicit_play_after_handoff_still_adopts_its_take(self) -> None:
        self._natural_step()
        kc.arm_key_cycle_for_explicit_play(self.ss)
        # Play generates a fresh take (new file) for the first key.
        fresh = str(Path(self._tmp.name) / "Bm_new.wav")
        Path(fresh).write_bytes(b"RIFF")
        self.ss["_last_backing_wav_path"] = fresh
        self.assertTrue(kc.play_wav_adoption_needed(self.ss, "app/static/kc/Bm_new.wav", "app/static/kc/Cm.wav"))

    def test_settings_rebuild_after_handoff_still_adopts(self) -> None:
        self._natural_step()
        self.ss["_kc_user_arrangement_edit"] = True
        try:
            kc.note_key_cycle_arrangement_settings_changed(self.ss)
        except Exception:
            pass  # the rebuild itself needs a full page; only the marker matters here
        self.assertNotIn(kc.KC_PROMOTED_WAV_PATH_KEY, self.ss)
        fresh = str(Path(self._tmp.name) / "Cm_bpm120.wav")
        Path(fresh).write_bytes(b"RIFF")
        self.ss["_last_backing_wav_path"] = fresh
        self.assertTrue(kc.play_wav_adoption_needed(self.ss, "app/static/kc/Cm_bpm120.wav", "app/static/kc/Cm.wav"))

    def test_manual_next_take_is_not_adopted(self) -> None:
        kc.advance_key_cycle_now(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), "Cm")
        self.assertFalse(
            kc.play_wav_adoption_needed(self.ss, "app/static/kc/Cm.wav", "app/static/kc/Cm.wav")
        )


if __name__ == "__main__":
    unittest.main()
