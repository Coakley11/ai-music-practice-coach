"""Backing audio is accompaniment only; the musician plays the composed melody."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestBackingAudioHasNoMelodyVoice(unittest.TestCase):
    def test_backing_modules_never_reference_the_composed_melody(self) -> None:
        offenders = []
        for path in ROOT.glob("backing_*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"include_melody|melody_override|composition_section_melody_events|generate_preview_wav", text):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_backing_page_never_requests_melody_audio(self) -> None:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        start = src.index("Original Melody panel (Composition songs only)")
        end = src.index("\n    try:", start + 100)
        self.assertNotIn("include_melody", src[start:end])


if __name__ == "__main__":
    unittest.main()
