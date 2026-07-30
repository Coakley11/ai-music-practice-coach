"""Tests for Composition Studio lyric suggestions (CS-B4)."""

import unittest

from composition_document import (
    apply_lyric_prompt_to_section,
    apply_structure_template,
    bootstrap_from_vision,
    lyrics_section_count,
    ordered_sections,
    section_has_lyrics,
)
from composition_lyric_suggestions import (
    collect_song_lyric_themes,
    default_role_for_section,
    suggest_lyric_brainstorm_ideas,
    suggest_lyric_prompts,
)


class TestCompositionLyricSuggestions(unittest.TestCase):
    def test_default_role_for_chorus(self) -> None:
        sec = {"label": "Chorus", "label_variant": "Chorus"}
        self.assertEqual(default_role_for_section(sec), "message")

    def test_suggest_lyric_prompts(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A hopeful song about home.")
        apply_structure_template(doc, "simple")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        prompts = suggest_lyric_prompts(doc, chorus, "message", limit=2)
        self.assertGreaterEqual(len(prompts), 1)
        self.assertTrue(all(p.get("prompt") for p in prompts))

    def test_brainstorm_uses_communicate(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        ideas = suggest_lyric_brainstorm_ideas(
            doc,
            verse,
            "story",
            communicate="Leaving the small town",
            limit=2,
        )
        self.assertIn("Leaving the small town", ideas[0]["prompt"])

    def test_apply_lyric_prompt_to_section(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        prompt = suggest_lyric_prompts(doc, verse, "story", limit=1)[0]
        apply_lyric_prompt_to_section(doc, str(verse["id"]), prompt)
        self.assertTrue(section_has_lyrics(verse))

    def test_collect_song_lyric_themes(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="A song about stars.")
        apply_structure_template(doc, "simple")
        verse = ordered_sections(doc)[0]
        verse.setdefault("lyrics", {"intent": {}, "lines": [], "raw_text": ""})
        verse["lyrics"]["intent"]["remember"] = "We are made of stardust"
        themes = collect_song_lyric_themes(doc)
        self.assertTrue(any("stardust" in t for t in themes))

    def test_lyrics_section_count(self) -> None:
        doc = bootstrap_from_vision(genre="Pop", song_idea="Test.")
        apply_structure_template(doc, "simple")
        done, total = lyrics_section_count(doc)
        self.assertEqual(done, 0)
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
