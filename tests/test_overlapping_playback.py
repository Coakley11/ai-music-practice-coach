"""Regression tests for overlapping playback prevention (P7).

Ensures audio players set window.top.__pmActivePlayback and check it
to prevent concurrent audio across iframes.
"""

from __future__ import annotations

import unittest


class TestSyncedScorePlaybackOverlapPrevention(unittest.TestCase):
    """render_synced_score_playback_html must set __pmActivePlayback."""

    def test_sets_active_playback_on_play(self):
        from pathlib import Path
        src = Path("composition_playback_sync.py").read_text(encoding="utf-8")
        self.assertIn("__pmActivePlayback", src)

    def test_checks_active_playback_in_interval(self):
        from pathlib import Path
        src = Path("composition_playback_sync.py").read_text(encoding="utf-8")
        fn_start = src.index("def render_synced_score_playback_html")
        fn_end = src.index("\ndef ", fn_start + 1)
        fn_body = src[fn_start:fn_end]
        self.assertIn("__pmActivePlayback", fn_body)
        self.assertIn("audio.pause()", fn_body)


class TestComposerPlaybackOverlapPrevention(unittest.TestCase):
    """build_composer_playback_html must also set __pmActivePlayback."""

    def test_sets_active_playback(self):
        from pathlib import Path
        src = Path("composition_preview.py").read_text(encoding="utf-8")
        fn_start = src.index("def build_composer_playback_html")
        fn_end = src.index("\ndef ", fn_start + 1)
        fn_body = src[fn_start:fn_end]
        self.assertIn("__pmActivePlayback", fn_body)


if __name__ == "__main__":
    unittest.main()
