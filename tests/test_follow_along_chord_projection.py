"""Current/Next Chord must show in written pitch for transposing instruments.

Regression: the follow-along status and live component must include
chord transposition for written-key and shape modes.
"""

from __future__ import annotations

import unittest
from pathlib import Path


class TestFollowAlongStatusTransposes(unittest.TestCase):
    """follow_along_status_html transposes for written AND shape modes."""

    def test_status_handles_written_and_shape_modes(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        fn_start = src.index("def follow_along_status_html")
        fn_end = src.index("\nfrom ", fn_start)
        fn_src = src[fn_start:fn_end]
        self.assertIn("written", fn_src)
        self.assertIn("shape", fn_src)
        self.assertIn("transpose_chord", fn_src)


class TestLiveComponentLocalFallback(unittest.TestCase):
    """live_follow_along_component_html includes local transposition fallback."""

    def test_function_accepts_display_semitones(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        fn_start = src.index("def live_follow_along_component_html")
        fn_sig_end = src.index("):", fn_start) + 2
        fn_sig = src[fn_start:fn_sig_end]
        self.assertIn("display_semitones", fn_sig)
        self.assertIn("reading_key", fn_sig)

    def test_js_contains_local_transpose_fallback(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        fn_start = src.index("def live_follow_along_component_html")
        next_def = src.index("\ndef ", fn_start + 1)
        fn_src = src[fn_start:next_def]
        self.assertIn("_localDisplaySemitones", fn_src)
        self.assertIn("_localTransposeChord", fn_src)
        self.assertIn("_localReadingKey", fn_src)

    def test_project_chord_label_uses_local_fallback(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        proj_start = src.index("function projectChordLabel(ch, eventSpace, projection)")
        proj_end = src.index("const shownChord", proj_start)
        proj_src = src[proj_start:proj_end]
        self.assertIn("__kcProjectChordLabel", proj_src)
        self.assertIn("_localDisplaySemitones", proj_src)
        self.assertIn("_localTransposeChord", proj_src)


class TestCallSitePassesProjection(unittest.TestCase):
    """The live component call site computes and passes display_semitones."""

    def test_call_site_passes_display_semitones(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        call_start = src.index("_kr_component_html = live_follow_along_component_html(")
        call_end = src.index("\n        if _karaoke_engaged:", call_start + 100)
        call_src = src[call_start:call_end]
        self.assertIn("display_semitones=", call_src)
        self.assertIn("reading_key=", call_src)

    def test_projection_computed_for_written_and_shape(self):
        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        proj_start = src.index("_fa_display_semis")
        proj_end = src.index("_kr_component_html", proj_start)
        proj_src = src[proj_start:proj_end]
        self.assertIn("written", proj_src)
        self.assertIn("shape", proj_src)
        self.assertIn("display_projection_bundle", proj_src)


if __name__ == "__main__":
    unittest.main()
