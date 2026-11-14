"""Merge-forward polish: library title formats and no blank band under the drawn score."""
from __future__ import annotations

import unittest


class TestLibraryTitle(unittest.TestCase):
    def test_title_formats(self) -> None:
        from composition_library import _title

        self.assertEqual(_title({"title": "Top"}), "Top")
        self.assertEqual(_title({"metadata": {"title": "Meta"}}), "Meta")
        self.assertEqual(_title({"title": " ", "global": {"title": "Glob"}}), "Glob")
        self.assertEqual(_title({"name": "Named"}), "Named")
        self.assertEqual(_title({}), "Untitled")
        self.assertEqual(_title({"title": "Top", "metadata": {"title": "Meta"}}), "Top")


class TestScoreFrameHasNoBlankBand(unittest.TestCase):
    def test_notation_frame_sizes_paper_to_svg(self) -> None:
        from composition_melody_notation import render_abc_html

        h = render_abc_html("X:1\nM:4/4\nL:1/4\nK:C\nCDEF|")
        self.assertIn('pp.style.paddingBottom = "0"', h)
        self.assertIn("sv.getBoundingClientRect().height", h)

    def test_player_paper_min_height_only_when_empty(self) -> None:
        import io, struct, wave
        from composition_playback_sync import build_playback_bundle, render_synced_score_playback_html

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            w.writeframes(struct.pack("<" + "h" * 80, *([0] * 80)))
        b = build_playback_bundle(chord_syms=["C", "G"], bpm=100, meter="4/4")
        h = render_synced_score_playback_html(wav_bytes=buf.getvalue(), bundle=b, abc_text="X:1\nM:4/4\nK:C\nCDEF|", dom_id="t9")
        self.assertIn(".cplay-paper:empty", h)
        self.assertNotIn(".cplay-paper { min-height", h)
        self.assertIn('pp.style.paddingBottom = "0"', h)


if __name__ == "__main__":
    unittest.main()
