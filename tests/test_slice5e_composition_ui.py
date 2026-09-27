"""Slice 5E — Composition UI: no redundant Edit, gated nav, chord/melody alignment."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock


class TestSlice5ERedundantEditRemoved(unittest.TestCase):
    def test_review_has_no_return_to_editing_jump_row(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertNotIn('st.markdown("**Return to editing**")', src)
        self.assertNotIn("composer_review_edit_", src)
        # Per-section edit actions in Review may remain.
        self.assertIn("composer_review_ed_ch_", src)


class TestSlice5EStudioNav(unittest.TestCase):
    def test_library_sidebar_has_practice_songs_backing_keys(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn('key="composer_nav_practice"', src)
        self.assertIn('key="composer_nav_songs"', src)
        self.assertIn('key="composer_nav_backing"', src)
        self.assertIn("navigate_studio_page", src)
        # Nav sits under Start new song in the same sidebar function.
        new_i = src.index('key="composer_new_song"')
        prac_i = src.index('key="composer_nav_practice"')
        self.assertLess(new_i, prac_i)

    def test_editing_active_gate(self) -> None:
        from composition_document import bootstrap_from_vision
        from composition_session_state import set_active_document
        from composition_songs_bridge import composition_pick_key_for
        from composition_studio_page import _editing_composition_is_global_active
        from songs.state import ACTIVE_CATALOG_PICK_KEY

        doc = bootstrap_from_vision(genre="Pop", song_idea="x", title="Gate", key="C major", bpm=100)
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        self.assertFalse(_editing_composition_is_global_active(ss))

        pick = composition_pick_key_for(doc)
        ss[ACTIVE_CATALOG_PICK_KEY] = pick
        with mock.patch(
            "songs.music_source.composition_song_is_active",
            return_value=True,
        ):
            self.assertTrue(_editing_composition_is_global_active(ss))

        ss[ACTIVE_CATALOG_PICK_KEY] = "composition::other-id"
        with mock.patch(
            "songs.music_source.composition_song_is_active",
            return_value=True,
        ):
            self.assertFalse(_editing_composition_is_global_active(ss))

    def test_nav_uses_history_api_no_direct_studio_page_write(self) -> None:
        src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        # Within the library sidebar nav block, use navigate_studio_page only.
        block_start = src.index('key="composer_nav_practice"')
        block_end = src.index("def _editing_composition_is_global_active")
        block = src[block_start:block_end]
        self.assertIn('navigate_studio_page(session_state, "practice")', block)
        self.assertIn('navigate_studio_page(session_state, "picker")', block)
        self.assertIn('navigate_studio_page(session_state, "backing")', block)
        self.assertNotIn('session_state["studio_page"]', block)

    def test_render_library_sidebar_includes_nav_labels(self) -> None:
        import composition_studio_page as csp

        labels: list[str] = []
        keys: list[str] = []

        class _Btn:
            def __init__(self, label, **kwargs):
                labels.append(str(label))
                keys.append(str(kwargs.get("key") or ""))

            def __bool__(self):
                return False

        class _Exp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class _Col:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake_st = mock.MagicMock()
        fake_st.button.side_effect = lambda label, **kw: _Btn(label, **kw)
        fake_st.expander.side_effect = lambda *a, **k: _Exp()

        def _cols(*a, **_k):
            n = a[0] if a and isinstance(a[0], int) else 2
            return tuple(_Col() for _ in range(n))

        fake_st.columns.side_effect = _cols

        with mock.patch.object(csp, "st", fake_st):
            with mock.patch.object(csp, "_editing_composition_is_global_active", return_value=False):
                csp._render_library_sidebar({})

        self.assertIn("composer_new_song", keys)
        self.assertIn("composer_nav_practice", keys)
        self.assertIn("composer_nav_songs", keys)
        self.assertIn("composer_nav_backing", keys)


class TestSlice5EChordMelodyAlignment(unittest.TestCase):
    def test_abc_embeds_chord_annotations_at_onsets(self) -> None:
        from composition_melody_notation import build_abc_from_melody_events

        events = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "E4", "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "G4", "duration_beats": 1.0, "beat": 2.0, "measure": 1},
            {"pitch": "C5", "duration_beats": 1.0, "beat": 3.0, "measure": 1},
            {"pitch": "D4", "duration_beats": 2.0, "beat": 0.0, "measure": 2},
            {"pitch": "F4", "duration_beats": 2.0, "beat": 2.0, "measure": 2},
        ]
        chords = [
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        abc = build_abc_from_melody_events(
            events, key="C major", meter="4/4", bpm=100, chords=chords
        )
        self.assertIn('"C"', abc)
        self.assertIn('"G"', abc)
        # G should appear after the first barline (measure 2 onset).
        music = abc.split("K:")[-1]
        self.assertLess(music.index('"C"'), music.index('"G"'))

    def test_proportional_strip_uses_duration_flex(self) -> None:
        from composition_melody_notation import build_chord_strip_html

        chords = [
            {"chord": "C", "bars": 2},
            {"chord": "Am", "bars": 1},
            {"chord": "F", "bars": 1},
        ]
        html = build_chord_strip_html(chords, meter="4/4")
        self.assertIn('data-duration-beats="8"', html)  # 2 bars * 4
        self.assertIn('data-duration-beats="4"', html)
        self.assertIn(">C<", html)
        self.assertIn(">Am<", html)
        self.assertIn("flex:8", html.replace(" ", ""))

    def test_score_model_wires_chords_into_abc(self) -> None:
        from composition_melody_notation import build_section_score_model

        events = [
            {"pitch": "G4", "duration_beats": 2.0},
            {"pitch": "A4", "duration_beats": 2.0},
            {"pitch": "B4", "duration_beats": 2.0},
            {"pitch": "D5", "duration_beats": 2.0},
        ]
        chords = [{"chord": "G", "bars": 1}, {"chord": "D", "bars": 1}]
        score = build_section_score_model(
            events=events,
            chords=chords,
            key="G major",
            meter="4/4",
            bpm=96,
            title="Verse",
        )
        self.assertIn('"G"', score["abc"])
        self.assertIn('"D"', score["abc"])
        self.assertIn("data-duration-beats", score["chord_strip_html"])


if __name__ == "__main__":
    unittest.main()
