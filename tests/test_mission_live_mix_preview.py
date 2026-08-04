"""Performance + Backing preview — live mix regression."""

from __future__ import annotations

import struct
import unittest

import numpy as np

from mission_live_recording_mix import (
    backing_energy_in_mixed,
    build_live_recording_previews,
    mix_dry_mic_with_backing,
)


def _tone_wav(freq: float, ms: int, *, sr: int = 44100) -> bytes:
    n = int(sr * ms / 1000)
    t = np.linspace(0, ms / 1000, n, endpoint=False)
    samples = (0.35 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sr,
        sr * 2,
        2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


class TestMissionLiveMixPreview(unittest.TestCase):
    def test_looping_mix_differs_from_dry_with_backing_energy(self) -> None:
        dry = _tone_wav(440, 500)
        back = _tone_wav(220, 200)
        mixed = mix_dry_mic_with_backing(
            dry, back, backing_offset_samples=0, backing_gain=0.85, loop_backing=True
        )
        self.assertNotEqual(mixed, dry)
        self.assertGreater(backing_energy_in_mixed(mixed, dry), 0.001)

    def test_previews_survive_rerun_simulation(self) -> None:
        session: dict = {
            "improv_active_mission": "Develop one motif for the entire solo",
            "ii_selected_chord": "Em",
            "backing_track_bpm": 100,
            "mission_exact_backing_count_in": False,
        }
        dry = _tone_wav(330, 400)
        back = _tone_wav(110, 300)

        def _fake_gen(_s):
            return back, "Em"

        import mission_upload_recording_ui as ui

        with unittest.mock.patch(
            "mission_upload_recording_ui.generate_exact_chord_backing_wav",
            side_effect=_fake_gen,
        ):
            p1 = ui._refresh_live_previews(session, dry, bpm=100, meter="4/4", backing_gain=0.8)
            mixed1 = bytes(session["_mission_live_mic_mixed"])
            p2 = ui._refresh_live_previews(session, dry, bpm=100, meter="4/4", backing_gain=0.8)
        self.assertEqual(mixed1, session["_mission_live_mic_mixed"])
        self.assertTrue(p2["has_backing_mix"])
        self.assertTrue(session.get("_mission_live_mix_diag", {}).get("mixed_differs_from_dry"))

    def test_missions_ui_has_no_upload_existing_take(self) -> None:
        import inspect
        from mission_upload_recording_ui import render_mission_live_recording_studio

        src = inspect.getsource(render_mission_live_recording_studio)
        self.assertNotIn("Upload Existing Take", src)


if __name__ == "__main__":
    unittest.main()
