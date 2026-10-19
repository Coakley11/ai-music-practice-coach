"""Slice 1 — Lyrics beneath melody in Composition score views.

Tests that lyrics are extracted, passed through the score model, and
rendered wherever the existing rendering supports it.
"""

from __future__ import annotations

import unittest

from composition_melody_notation import build_section_score_model


def _section_with_lyrics(raw_text: str = "Home again, home again") -> dict:
    return {
        "id": "sec-1",
        "label": "Verse",
        "label_variant": "Verse 1",
        "chords": [{"chord": "G", "bars": 1}, {"chord": "D", "bars": 1}],
        "melody": {
            "intent": {},
            "phrases": [],
            "events": [
                {"pitch": "G4", "duration_beats": 2, "is_rest": False},
                {"pitch": "A4", "duration_beats": 2, "is_rest": False},
            ],
        },
        "lyrics": {"lines": [raw_text], "raw_text": raw_text},
    }


def _section_without_lyrics() -> dict:
    sec = _section_with_lyrics()
    del sec["lyrics"]
    return sec


class TestSectionLyricsText(unittest.TestCase):
    """_section_lyrics_text extracts raw_text from section lyrics dict."""

    def test_extracts_raw_text(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = _section_with_lyrics("Walking down the road")
        self.assertEqual(_section_lyrics_text(sec), "Walking down the road")

    def test_returns_empty_for_missing_lyrics(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = _section_without_lyrics()
        self.assertEqual(_section_lyrics_text(sec), "")

    def test_returns_empty_for_none_section(self) -> None:
        from composition_studio_page import _section_lyrics_text

        self.assertEqual(_section_lyrics_text(None), "")

    def test_returns_empty_for_empty_raw_text(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = {"lyrics": {"raw_text": "", "lines": []}}
        self.assertEqual(_section_lyrics_text(sec), "")

    def test_strips_whitespace(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = {"lyrics": {"raw_text": "  hello world  ", "lines": ["hello world"]}}
        self.assertEqual(_section_lyrics_text(sec), "hello world")

    def test_returns_empty_for_non_dict_lyrics(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = {"lyrics": "just a string"}
        self.assertEqual(_section_lyrics_text(sec), "")


class TestScoreModelLyrics(unittest.TestCase):
    """build_section_score_model surfaces lyrics_text in the score dict."""

    def test_lyrics_present_in_score(self) -> None:
        score = build_section_score_model(
            events=[{"pitch": "C4", "duration_beats": 4, "is_rest": False}],
            chords=[{"chord": "C", "bars": 1}],
            key="C",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text="Home again",
        )
        self.assertTrue(score["has_lyrics"])
        self.assertEqual(score["lyrics_text"], "Home again")

    def test_lyrics_absent_when_empty(self) -> None:
        score = build_section_score_model(
            events=[{"pitch": "C4", "duration_beats": 4, "is_rest": False}],
            chords=[{"chord": "C", "bars": 1}],
            key="C",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text="",
        )
        self.assertFalse(score["has_lyrics"])
        self.assertEqual(score["lyrics_text"], "")

    def test_lyrics_absent_when_whitespace_only(self) -> None:
        score = build_section_score_model(
            events=[{"pitch": "C4", "duration_beats": 4, "is_rest": False}],
            chords=[{"chord": "C", "bars": 1}],
            key="C",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text="   \n  ",
        )
        self.assertFalse(score["has_lyrics"])

    def test_multiline_lyrics_preserved(self) -> None:
        text = "Line one\nLine two\nLine three"
        score = build_section_score_model(
            events=[{"pitch": "C4", "duration_beats": 4, "is_rest": False}],
            chords=[{"chord": "C", "bars": 1}],
            key="C",
            meter="4/4",
            bpm=96,
            title="Chorus",
            lyrics_text=text,
        )
        self.assertTrue(score["has_lyrics"])
        self.assertEqual(score["lyrics_text"], text)


class TestScoreViewPassesLyrics(unittest.TestCase):
    """_render_section_score_view extracts and passes lyrics to the staff."""

    def test_lyrics_extracted_from_section(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = _section_with_lyrics("Walking through the fields")
        lyrics = _section_lyrics_text(sec)
        self.assertEqual(lyrics, "Walking through the fields")
        score = build_section_score_model(
            events=sec["melody"]["events"],
            chords=sec["chords"],
            key="G",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text=lyrics,
        )
        self.assertTrue(score["has_lyrics"])
        self.assertEqual(score["lyrics_text"], "Walking through the fields")

    def test_no_lyrics_when_section_has_none(self) -> None:
        from composition_studio_page import _section_lyrics_text

        sec = _section_without_lyrics()
        lyrics = _section_lyrics_text(sec)
        self.assertEqual(lyrics, "")
        score = build_section_score_model(
            events=sec["melody"]["events"],
            chords=sec["chords"],
            key="G",
            meter="4/4",
            bpm=96,
            title="Verse 1",
            lyrics_text=lyrics,
        )
        self.assertFalse(score["has_lyrics"])


class TestConceptCardLyricsParameter(unittest.TestCase):
    """_render_melody_concept_card accepts lyrics_text and only passes it when active."""

    def test_signature_accepts_lyrics_text(self) -> None:
        import inspect
        from composition_studio_page import _render_melody_concept_card

        sig = inspect.signature(_render_melody_concept_card)
        self.assertIn("lyrics_text", sig.parameters)
        param = sig.parameters["lyrics_text"]
        self.assertEqual(param.default, "")

    def test_staff_function_accepts_lyrics_text(self) -> None:
        import inspect
        from composition_studio_page import _render_melody_staff

        sig = inspect.signature(_render_melody_staff)
        self.assertIn("lyrics_text", sig.parameters)
        param = sig.parameters["lyrics_text"]
        self.assertEqual(param.default, "")


class TestAllStaffCallsPassLyrics(unittest.TestCase):
    """Every _render_melody_staff call site passes lyrics_text (regression guard)."""

    def test_every_call_passes_lyrics_text(self) -> None:
        import re
        import inspect
        import composition_studio_page as mod

        source = inspect.getsource(mod)
        call_pattern = re.compile(
            r"_render_melody_staff\s*\(", re.MULTILINE
        )
        matches = list(call_pattern.finditer(source))
        # Skip the definition (def _render_melody_staff)
        def_pattern = re.compile(r"def\s+_render_melody_staff\s*\(")
        call_only = [m for m in matches if not def_pattern.match(source[m.start() - 4 : m.end()])]
        self.assertGreaterEqual(len(call_only), 5, "Expected at least 5 call sites")
        for m in call_only:
            # Extract from the opening paren to its matching close
            start = m.end() - 1  # at the '('
            depth, pos = 0, start
            while pos < len(source):
                if source[pos] == "(":
                    depth += 1
                elif source[pos] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                pos += 1
            call_body = source[start : pos + 1]
            line_no = source[:m.start()].count("\n") + 1
            self.assertIn(
                "lyrics_text=",
                call_body,
                f"_render_melody_staff call at ~line {line_no} is missing lyrics_text",
            )


if __name__ == "__main__":
    unittest.main()
