"""Practice -> Lyrics presentation: a lyrics card plus an honest, non-duplicating guide."""

from __future__ import annotations

import unittest
from pathlib import Path

from lyrics_presentation import (
    lyrics_card_html,
    phrasing_guide_html,
    phrasing_insights,
    split_stanzas,
)

_VERSE = (
    "I walked along the river\n"
    "Where the evening light was low\n"
    "\n"
    "I walked along the river\n"
    "And I learned to let it go"
)


class TestLyricsCard(unittest.TestCase):
    def test_stanzas_and_line_breaks_are_kept(self) -> None:
        self.assertEqual(
            split_stanzas(_VERSE),
            [
                ["I walked along the river", "Where the evening light was low"],
                ["I walked along the river", "And I learned to let it go"],
            ],
        )
        html_out = lyrics_card_html({"Verse 1": _VERSE}, song_title="River")
        self.assertEqual(html_out.count('class="lyr-stanza"'), 2)
        self.assertEqual(html_out.count('class="lyr-line"'), 4)
        self.assertIn("\U0001F3B5 Verse 1", html_out)

    def test_windows_line_endings_and_extra_blank_lines(self) -> None:
        self.assertEqual(split_stanzas("a\r\nb\r\n\r\n\r\nc"), [["a", "b"], ["c"]])

    def test_lyrics_are_html_escaped(self) -> None:
        html_out = lyrics_card_html({"Verse": "<script>alert(1)</script> & more"})
        self.assertNotIn("<script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)
        self.assertIn("&amp; more", html_out)

    def test_active_section_is_marked_and_others_are_not(self) -> None:
        html_out = lyrics_card_html({"Verse 1": "la la", "Chorus": "oh oh"}, active_section="Chorus")
        self.assertEqual(html_out.count("Now practicing"), 1)
        self.assertEqual(html_out.count("is-active"), 1)

    def test_empty_sections_are_skipped_and_nothing_renders_without_text(self) -> None:
        html_out = lyrics_card_html({"Intro": "  \n ", "Verse": "words here"})
        self.assertNotIn("Intro", html_out)
        self.assertEqual(lyrics_card_html({"Intro": ""}), "")

    def test_section_order_is_preserved(self) -> None:
        html_out = lyrics_card_html({"Verse 1": "a", "Chorus": "b", "Verse 2": "c"})
        self.assertLess(html_out.index("Verse 1"), html_out.index("Chorus"))
        self.assertLess(html_out.index("Chorus"), html_out.index("Verse 2"))


class TestPhrasingGuide(unittest.TestCase):
    def test_guide_never_prints_the_lyrics_again(self) -> None:
        guide = phrasing_guide_html({"Verse": _VERSE}, {}, section_names=["Verse"])
        for line in ("I walked along the river", "Where the evening light was low"):
            self.assertNotIn(line, guide)

    def test_notes_are_derived_from_the_text(self) -> None:
        notes = " ".join(phrasing_insights(_VERSE))
        self.assertIn("Repeated line", notes)
        self.assertIn("lines 1, 3", notes)
        self.assertIn("Phrase shape", notes)
        self.assertIn("2 phrases", notes)

    def test_breath_plan_names_the_longest_line(self) -> None:
        text = "Go\nI have been wandering through all of these unfamiliar streets tonight"
        notes = " ".join(phrasing_insights(text))
        self.assertIn("Breath plan", notes)
        self.assertIn("Line 2", notes)

    def test_a_single_short_line_gets_no_invented_coaching(self) -> None:
        self.assertEqual(phrasing_insights("Hello"), [])
        guide = phrasing_guide_html({"Verse": "Hello"}, {}, section_names=["Verse"])
        self.assertIn("No phrasing cues yet", guide)
        self.assertNotIn("Breathe", guide)

    def test_user_cues_are_shown_as_cues(self) -> None:
        guide = phrasing_guide_html({}, {"Chorus": ["Lift into the high note", "Let the last word ring"]}, section_names=["Chorus"])
        self.assertIn("Lift into the high note", guide)
        self.assertIn("<li>", guide)

    def test_cues_that_are_just_the_lyrics_are_not_listed(self) -> None:
        # Composition songs feed their own lyric lines in as "cues".
        cues = {"Verse": ["I walked along the river", "Where the evening light was low"]}
        guide = phrasing_guide_html({"Verse": _VERSE}, cues, section_names=["Verse"])
        self.assertNotIn("<li>", guide)
        self.assertNotIn("I walked along the river", guide)
        self.assertIn("Repeated line", guide)

    def test_a_real_cue_survives_next_to_lyric_lines(self) -> None:
        cues = {"Verse": ["I walked along the river", "Breathe here and drop the volume"]}
        guide = phrasing_guide_html({"Verse": _VERSE}, cues, section_names=["Verse"])
        self.assertIn("Breathe here and drop the volume", guide)
        self.assertEqual(guide.count("<li>"), 1)

    def test_section_title_is_not_a_streamlit_heading(self) -> None:
        self.assertNotIn("<h4", lyrics_card_html({"Verse": "la la la"}))

    def test_cues_are_escaped(self) -> None:
        guide = phrasing_guide_html({}, {"Verse": ["<b>x</b>"]})
        self.assertNotIn("<b>x</b>", guide)

    def test_no_lyrics_at_all_gets_an_honest_empty_state(self) -> None:
        guide = phrasing_guide_html({}, {})
        self.assertIn("No lyrics or cues yet", guide)

    def test_text_is_not_modified(self) -> None:
        original = dict(a=_VERSE)
        lyrics_card_html(original)
        phrasing_guide_html(original, {})
        self.assertEqual(original, dict(a=_VERSE))


class TestPracticeToolWiring(unittest.TestCase):
    def _src(self) -> str:
        return (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")

    def test_lyrics_tool_uses_the_shared_card_for_every_source(self) -> None:
        src = self._src()
        start = src.index('elif _practice_active_tool == "lyrics":')
        end = src.index("close_practice_tool_workspace(st)", start)
        block = src[start:end]
        self.assertIn("_lyrics_card_html(", block)
        self.assertNotIn("st.markdown(_cl_text)", block)
        self.assertIn("lyric_guide_html(", block)

    def test_legacy_guide_function_delegates_to_the_shared_guide(self) -> None:
        src = self._src()
        start = src.index("def lyric_guide_html(")
        end = src.index("def lyric_guide_markdown(", start)
        self.assertIn("phrasing_guide_html", src[start:end])


if __name__ == "__main__":
    unittest.main()
