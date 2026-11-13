"""Every render_abc_html caller shows each title at most once, and never a generic duplicate."""
import inspect
import unittest

from composition_melody_notation import build_section_score_model, render_abc_html

EV = [{"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 0.0}]


class TestScoreTitles(unittest.TestCase):
    def test_empty_title_renders_no_heading_and_no_T_line(self) -> None:
        sc = build_section_score_model(events=EV, chords=["C"], key="C", meter="4/4", bpm=100, title="")
        h = render_abc_html(sc["abc"])
        self.assertNotIn('id="score-title"></div>', h)
        self.assertNotIn('<div id="score-title">', h)
        self.assertNotIn("T:", h.split("renderAbc")[1])

    def test_named_title_appears_exactly_once_as_html(self) -> None:
        sc = build_section_score_model(events=EV, chords=["C"], key="C", meter="4/4", bpm=100, title="Verse - imported")
        h = render_abc_html(sc["abc"])
        self.assertEqual(h.count("Verse - imported"), 1)
        self.assertIn('<div id="score-title">Verse - imported</div>', h)

    def test_improvisation_surface_passes_no_generic_title(self) -> None:
        import improvisation_intelligence_ui as ui

        src = inspect.getsource(ui)
        i = src.index("render_abc_html(abc_str")
        block = src[src.rindex("build_section_score_model(", 0, i):i]
        self.assertIn('title=""', block)

    def test_candidate_card_static_fallback_has_no_second_title(self) -> None:
        import composition_studio_page as page

        src = inspect.getsource(page._render_melody_concept_card)
        self.assertNotIn("title=name,", src)
        self.assertIn('title="",', src)
