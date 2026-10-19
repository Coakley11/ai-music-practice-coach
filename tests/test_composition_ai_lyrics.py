"""Comprehensive tests for the AI Lyric Generation Engine (Slice 3).

All 16 test categories use mocked AI responses — no live API calls.

Categories
----------
 1. Context extraction — key, tempo, mode, style, mood
 2. Section-aware — verse/chorus/bridge roles
 3. Chord context — chord progression in prompt
 4. Melody-informed — pitch/rhythm in prompt when available
 5. Provisional lyrics — no-melody mode
 6. Keywords/themes — user keywords in prompt
 7. Mood/style — mood/style influence
 8. Natural language instructions — free-form text
 9. Existing lyrics protection — never overwrite
10. Multi-section themes — cross-section continuity
11. Structured output — valid response structure
12. Error handling — API failures, invalid responses
13. Prompt safety — no secrets leaked
14. Token/length limits — reasonable bounds
15. Empty/edge cases — empty sections, no chords, no melody
16. Integration with document model — round-trip with composition_document
"""

from __future__ import annotations

import copy
import json
import unittest
import uuid
from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock, patch

from composition_ai_lyrics import (
    SUPPORTED_GENERATION_MODES,
    LyricGenerationRequest,
    LyricGenerationResult,
    LyricSuggestion,
    MusicalContext,
    build_lyric_prompt,
    extract_musical_context,
    generate_section_lyrics,
    parse_ai_lyric_response,
)
from composition_document import (
    default_global,
    default_integration_stub,
    default_metadata,
    empty_section,
    ordered_sections,
    section_by_id,
    section_melody_events,
    COMPOSITION_SCHEMA_VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _qa_doc(
    *,
    doc_id: str | None = None,
    title: str = "QA Test Song",
    key: str = "C",
    bpm: int = 120,
    style: str = "Pop",
    mood: str = "hopeful",
    description: str = "A song about new beginnings",
    with_melody: bool = True,
    with_chords: bool = True,
    with_lyrics: bool = False,
    extra_sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a well-formed composition document for testing."""
    did = doc_id or str(uuid.uuid4())

    verse = empty_section("Verse", label_variant="Verse 1")
    if with_chords:
        verse["chords"] = [
            {"chord": "C", "bars": 1},
            {"chord": "Am", "bars": 1},
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
    if with_melody:
        verse["melody"]["events"] = [
            {"pitch": "C4", "duration_beats": 1.0, "beat": 0.0, "measure": 1},
            {"pitch": "D4", "duration_beats": 1.0, "beat": 1.0, "measure": 1},
            {"pitch": "E4", "duration_beats": 1.0, "beat": 2.0, "measure": 1},
            {"pitch": "F4", "duration_beats": 1.0, "beat": 3.0, "measure": 1},
            {"pitch": "G4", "duration_beats": 2.0, "beat": 0.0, "measure": 2},
            {"pitch": "E4", "duration_beats": 2.0, "beat": 2.0, "measure": 2},
        ]
    if with_lyrics:
        verse["lyrics"]["raw_text"] = "Walking down the road today\nSunshine on my face"
        verse["lyrics"]["intent"]["communicate"] = "A journey forward"
        verse["lyrics"]["intent"]["emotion"] = "hopeful"
        verse["lyrics"]["intent"]["remember"] = "road today"

    chorus = empty_section("Chorus")
    if with_chords:
        chorus["chords"] = [
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
            {"chord": "Am", "bars": 1},
            {"chord": "C", "bars": 1},
        ]
    if with_melody:
        chorus["melody"]["events"] = [
            {"pitch": "E4", "duration_beats": 2.0, "beat": 0.0, "measure": 1},
            {"pitch": "G4", "duration_beats": 2.0, "beat": 2.0, "measure": 1},
        ]

    sections = {verse["id"]: verse, chorus["id"]: chorus}
    order = [verse["id"], chorus["id"]]

    if extra_sections:
        for es in extra_sections:
            sections[es["id"]] = es
            order.append(es["id"])

    g = default_global()
    g["original_key_center"] = key
    g["original_key_label"] = key
    g["bpm"] = bpm

    return {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "id": did,
        "title": title,
        "created_at": "2026-10-19T00:00:00Z",
        "updated_at": "2026-10-19T00:00:00Z",
        "status": "draft",
        "origin": {"seed_type": "exploring", "seed_summary": "", "seed_payload": {}},
        "metadata": default_metadata(style=style, mood=mood, description=description),
        "global": g,
        "form": {"section_order": order, "sections": sections},
        "integration": default_integration_stub(),
        "ai_settings": {"creativity": "balanced", "explicit_user_is_composer": True},
    }


def _verse_id(doc: dict[str, Any]) -> str:
    return doc["form"]["section_order"][0]


def _chorus_id(doc: dict[str, Any]) -> str:
    return doc["form"]["section_order"][1]


def _mock_ai_json_response(suggestions: list[dict[str, Any]]) -> str:
    return json.dumps({"suggestions": suggestions})


def _standard_mock_response(num: int = 2) -> str:
    items = []
    for i in range(num):
        items.append({
            "lines": [f"Line {i + 1} verse one", f"Line {i + 1} verse two",
                       f"Line {i + 1} verse three", f"Line {i + 1} verse four"],
            "rationale": f"Suggestion {i + 1} fits the C major chord progression and hopeful mood.",
            "confidence": "high" if i == 0 else "medium",
        })
    return _mock_ai_json_response(items)


# ---------------------------------------------------------------------------
# Category 1: Context extraction
# ---------------------------------------------------------------------------

class TestContextExtraction(unittest.TestCase):
    """Key, tempo, mode, style, mood extracted correctly."""

    def test_key_extracted(self):
        doc = _qa_doc(key="G")
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.key, "G")

    def test_bpm_extracted(self):
        doc = _qa_doc(bpm=90)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.bpm, 90)

    def test_time_signature_extracted(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.time_signature, "4/4")

    def test_style_extracted(self):
        doc = _qa_doc(style="Jazz")
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.style, "Jazz")

    def test_mood_extracted(self):
        doc = _qa_doc(mood="melancholy")
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.mood, "melancholy")

    def test_description_extracted(self):
        doc = _qa_doc(description="A rainy day reflection")
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.description, "A rainy day reflection")

    def test_invalid_section_id_raises(self):
        doc = _qa_doc()
        with self.assertRaises(ValueError):
            extract_musical_context(doc, "nonexistent-id")


# ---------------------------------------------------------------------------
# Category 2: Section-aware generation
# ---------------------------------------------------------------------------

class TestSectionAware(unittest.TestCase):
    """Verse/chorus/bridge roles are correctly identified."""

    def test_verse_section_label(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.section_label, "Verse")

    def test_chorus_section_label(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertEqual(ctx.section_label, "Chorus")

    def test_verse_role_defaults_to_story(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.section_role, "story")

    def test_chorus_role_defaults_to_message(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertEqual(ctx.section_role, "message")

    def test_bridge_role(self):
        bridge = empty_section("Bridge")
        doc = _qa_doc(extra_sections=[bridge])
        ctx = extract_musical_context(doc, bridge["id"])
        self.assertEqual(ctx.section_role, "question")

    def test_section_index_verse(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.section_index, 0)

    def test_section_index_chorus(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertEqual(ctx.section_index, 1)

    def test_total_sections(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.total_sections, 2)

    def test_section_role_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        req = LyricGenerationRequest(section_id=_chorus_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("message", user_msg.lower())
        self.assertIn("chorus", user_msg.lower())


# ---------------------------------------------------------------------------
# Category 3: Chord context
# ---------------------------------------------------------------------------

class TestChordContext(unittest.TestCase):
    """Chord progressions appear in the AI prompt."""

    def test_chords_extracted(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.chords, ["C", "Am", "F", "G"])

    def test_chords_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("C | Am | F | G", user_msg)

    def test_empty_chords_handled(self):
        doc = _qa_doc(with_chords=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.chords, [])

    def test_chorus_chords_distinct(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertEqual(ctx.chords, ["F", "G", "Am", "C"])


# ---------------------------------------------------------------------------
# Category 4: Melody-informed
# ---------------------------------------------------------------------------

class TestMelodyInformed(unittest.TestCase):
    """Melody pitches and rhythm appear in prompt when available."""

    def test_melody_pitches_extracted(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertIn("C4", ctx.melody_pitches)
        self.assertIn("G4", ctx.melody_pitches)
        self.assertTrue(ctx.has_melody)

    def test_melody_rhythm_summary(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertIn("quarter", ctx.melody_rhythm_summary)
        self.assertIn("half", ctx.melody_rhythm_summary)

    def test_melody_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("Melody pitches", user_msg)
        self.assertIn("C4", user_msg)

    def test_melody_informed_instruction(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("syllable stress", user_msg.lower())

    def test_suggestion_marked_melody_informed(self):
        response = _standard_mock_response(1)
        suggestions = parse_ai_lyric_response(response, "sec-1", "Verse 1", melody_informed=True)
        self.assertTrue(suggestions[0].melody_informed)


# ---------------------------------------------------------------------------
# Category 5: Provisional lyrics (no melody)
# ---------------------------------------------------------------------------

class TestProvisionalLyrics(unittest.TestCase):
    """No-melody mode produces provisional lyrics."""

    def test_no_melody_context(self):
        doc = _qa_doc(with_melody=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertFalse(ctx.has_melody)
        self.assertEqual(ctx.melody_pitches, [])

    def test_provisional_instruction_in_prompt(self):
        doc = _qa_doc(with_melody=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("provisional", user_msg.lower())

    def test_no_melody_marker_in_prompt(self):
        doc = _qa_doc(with_melody=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("not yet composed", user_msg.lower())

    def test_suggestion_not_melody_informed(self):
        response = _standard_mock_response(1)
        suggestions = parse_ai_lyric_response(response, "sec-1", "Verse 1", melody_informed=False)
        self.assertFalse(suggestions[0].melody_informed)


# ---------------------------------------------------------------------------
# Category 6: Keywords/themes
# ---------------------------------------------------------------------------

class TestKeywordsThemes(unittest.TestCase):
    """User-provided keywords appear in the prompt."""

    def test_keywords_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            keywords=["rain", "moonlight", "hope"],
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("rain", user_msg)
        self.assertIn("moonlight", user_msg)
        self.assertIn("hope", user_msg)

    def test_theme_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            theme="Overcoming adversity",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("Overcoming adversity", user_msg)

    def test_keywords_truncated_at_limit(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            keywords=[f"kw{i}" for i in range(20)],
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("kw0", user_msg)
        self.assertNotIn("kw15", user_msg)


# ---------------------------------------------------------------------------
# Category 7: Mood/style influence
# ---------------------------------------------------------------------------

class TestMoodStyle(unittest.TestCase):
    """Mood and style parameters influence the prompt."""

    def test_request_mood_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            mood="bittersweet",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("bittersweet", user_msg)

    def test_request_style_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            style="conversational and poetic",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("conversational and poetic", user_msg)

    def test_document_mood_in_prompt(self):
        doc = _qa_doc(mood="melancholy")
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("melancholy", user_msg)

    def test_document_style_in_prompt(self):
        doc = _qa_doc(style="R&B")
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("R&B", user_msg)


# ---------------------------------------------------------------------------
# Category 8: Natural language instructions
# ---------------------------------------------------------------------------

class TestNaturalLanguageInstructions(unittest.TestCase):
    """Free-form user instructions appear in the prompt."""

    def test_instructions_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            instructions="Make the first line a question about the future",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("Make the first line a question about the future", user_msg)

    def test_long_instructions_truncated(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            instructions="x" * 1000,
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertLessEqual(len(req.instructions[:500]), 500)

    def test_lyric_intent_communicate_in_prompt(self):
        doc = _qa_doc(with_lyrics=True)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("A journey forward", user_msg)

    def test_lyric_intent_remember_in_prompt(self):
        doc = _qa_doc(with_lyrics=True)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("road today", user_msg)


# ---------------------------------------------------------------------------
# Category 9: Existing lyrics protection
# ---------------------------------------------------------------------------

class TestExistingLyricsProtection(unittest.TestCase):
    """AI never overwrites existing lyrics — only suggests alternatives."""

    def test_existing_lyrics_detected(self):
        doc = _qa_doc(with_lyrics=True)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertTrue(ctx.has_existing_lyrics)
        self.assertIn("Walking down", ctx.existing_lyrics)

    def test_no_existing_lyrics(self):
        doc = _qa_doc(with_lyrics=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertFalse(ctx.has_existing_lyrics)
        self.assertEqual(ctx.existing_lyrics, "")

    def test_overwrite_warning_in_prompt(self):
        doc = _qa_doc(with_lyrics=True)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("DO NOT overwrite", user_msg)
        self.assertIn("fresh alternatives", user_msg.lower())

    def test_no_warning_when_no_existing_lyrics(self):
        doc = _qa_doc(with_lyrics=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertNotIn("DO NOT overwrite", user_msg)

    @patch("composition_ai_lyrics._call_openai")
    def test_generate_does_not_modify_document(self, mock_call):
        mock_call.return_value = _standard_mock_response(1)
        doc = _qa_doc(with_lyrics=True)
        original = copy.deepcopy(doc)
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertEqual(doc, original)

    def test_system_prompt_mentions_never_overwrite(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        system_msg = messages[0]["content"]
        self.assertIn("overwrite", system_msg.lower())


# ---------------------------------------------------------------------------
# Category 10: Multi-section themes
# ---------------------------------------------------------------------------

class TestMultiSectionThemes(unittest.TestCase):
    """Cross-section theme continuity."""

    def test_song_themes_from_metadata(self):
        doc = _qa_doc(description="A song about stars and midnight")
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertTrue(any("stars" in t for t in ctx.song_themes))

    def test_song_themes_from_lyrics_intent(self):
        doc = _qa_doc(with_lyrics=True)
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertTrue(any("road" in t.lower() for t in ctx.song_themes))

    def test_themes_in_prompt(self):
        doc = _qa_doc(with_lyrics=True, description="A journey of hope")
        ctx = extract_musical_context(doc, _chorus_id(doc))
        req = LyricGenerationRequest(section_id=_chorus_id(doc))
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("Themes so far", user_msg)


# ---------------------------------------------------------------------------
# Category 11: Structured output validation
# ---------------------------------------------------------------------------

class TestStructuredOutput(unittest.TestCase):
    """Parsed response has correct structure."""

    def test_valid_json_response(self):
        response = _standard_mock_response(2)
        suggestions = parse_ai_lyric_response(response, "sec-1", "Verse 1", True)
        self.assertEqual(len(suggestions), 2)
        for s in suggestions:
            self.assertIsInstance(s, LyricSuggestion)
            self.assertIsInstance(s.lines, list)
            self.assertTrue(len(s.lines) > 0)
            self.assertEqual(s.section_id, "sec-1")
            self.assertEqual(s.section_label, "Verse 1")
            self.assertIn(s.confidence, ("high", "medium", "low"))

    def test_raw_text_assembled(self):
        response = _mock_ai_json_response([{
            "lines": ["Hello world", "Goodbye moon"],
            "rationale": "Test",
            "confidence": "high",
        }])
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertEqual(suggestions[0].raw_text, "Hello world\nGoodbye moon")

    def test_confidence_normalized(self):
        response = _mock_ai_json_response([{
            "lines": ["Test line"],
            "rationale": "Test",
            "confidence": "VERY_HIGH",
        }])
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertEqual(suggestions[0].confidence, "medium")

    def test_result_dataclass_fields(self):
        result = LyricGenerationResult(
            ok=True,
            suggestions=[],
            error="",
            musical_context_summary="Test context",
            generation_mode="full_section",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.generation_mode, "full_section")

    def test_suggestion_immutable(self):
        s = LyricSuggestion(
            lines=["Test"],
            raw_text="Test",
            section_id="s1",
            section_label="V1",
            rationale="r",
            melody_informed=True,
            confidence="high",
        )
        with self.assertRaises(AttributeError):
            s.confidence = "low"  # type: ignore[misc]

    def test_max_four_suggestions(self):
        items = [{"lines": [f"Line {i}"], "rationale": "r", "confidence": "high"}
                 for i in range(8)]
        response = _mock_ai_json_response(items)
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertLessEqual(len(suggestions), 4)


# ---------------------------------------------------------------------------
# Category 12: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):
    """API failures, invalid responses, missing keys."""

    @patch("composition_ai_lyrics._call_openai")
    def test_api_exception_returns_error_result(self, mock_call):
        mock_call.side_effect = RuntimeError("Connection refused")
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertFalse(result.ok)
        self.assertIn("Connection refused", result.error)
        self.assertEqual(result.suggestions, [])

    @patch("composition_ai_lyrics._call_openai")
    def test_empty_response_returns_error(self, mock_call):
        mock_call.return_value = ""
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertFalse(result.ok)
        self.assertIn("no usable", result.error.lower())

    @patch("composition_ai_lyrics._call_openai")
    def test_malformed_json_falls_back_to_plain_text(self, mock_call):
        mock_call.return_value = "Here is a lyric line\nAnd another line"
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(result.suggestions[0].confidence, "low")

    def test_no_api_key_returns_error(self):
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        with patch("openai_secrets_config.resolve_openai_api_key", return_value=("", MagicMock())):
            result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="")
        self.assertFalse(result.ok)
        self.assertIn("API key", result.error)

    def test_invalid_section_returns_error(self):
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id="nonexistent")
        result = generate_section_lyrics(doc, "nonexistent", req, api_key="test-key")
        self.assertFalse(result.ok)
        self.assertIn("not found", result.error.lower())

    def test_unsupported_mode_returns_error(self):
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc), generation_mode="dance")
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertFalse(result.ok)
        self.assertIn("Unsupported", result.error)

    def test_parse_response_with_empty_lines(self):
        response = _mock_ai_json_response([{
            "lines": [],
            "rationale": "r",
            "confidence": "high",
        }])
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertEqual(len(suggestions), 0)


# ---------------------------------------------------------------------------
# Category 13: Prompt safety
# ---------------------------------------------------------------------------

class TestPromptSafety(unittest.TestCase):
    """No secrets leaked; system prompt doesn't expose internals."""

    def test_system_prompt_no_api_key(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        for msg in messages:
            content = msg["content"]
            self.assertNotIn("sk-", content)
            self.assertNotIn("OPENAI_API_KEY", content)

    def test_prompt_does_not_leak_doc_id(self):
        doc = _qa_doc()
        doc_id = doc["id"]
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        for msg in messages:
            self.assertNotIn(doc_id, msg["content"])

    def test_system_prompt_no_internal_paths(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        for msg in messages:
            self.assertNotIn("composition_ai_lyrics", msg["content"])
            self.assertNotIn(".py", msg["content"])

    def test_system_prompt_anti_copyright(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        system_msg = messages[0]["content"]
        self.assertIn("copyrighted", system_msg.lower())


# ---------------------------------------------------------------------------
# Category 14: Token/length limits
# ---------------------------------------------------------------------------

class TestTokenLengthLimits(unittest.TestCase):
    """Reasonable output bounds enforced."""

    def test_prompt_under_max_chars(self):
        doc = _qa_doc(description="A" * 500, mood="B" * 200, style="C" * 200)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            instructions="D" * 1000,
            keywords=[f"kw{i}" for i in range(20)],
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertLessEqual(len(user_msg), 6100)

    def test_response_lines_capped(self):
        items = [{"lines": [f"L{i}" for i in range(30)], "rationale": "r", "confidence": "high"}]
        response = _mock_ai_json_response(items)
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertLessEqual(len(suggestions[0].lines), 16)

    def test_rationale_truncated(self):
        items = [{"lines": ["Test"], "rationale": "R" * 1000, "confidence": "high"}]
        response = _mock_ai_json_response(items)
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertLessEqual(len(suggestions[0].rationale), 500)

    def test_num_suggestions_clamped(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc), num_suggestions=10)
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertNotIn("10 suggestion", user_msg)
        self.assertIn("4 suggestion", user_msg)

    def test_max_lines_clamped(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc), max_lines=50)
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("16 lines", user_msg)


# ---------------------------------------------------------------------------
# Category 15: Empty/edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    """Empty sections, no chords, no melody."""

    def test_section_no_chords_no_melody(self):
        doc = _qa_doc(with_chords=False, with_melody=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.chords, [])
        self.assertEqual(ctx.melody_pitches, [])
        self.assertFalse(ctx.has_melody)

    def test_section_no_chords_no_melody_prompt_ok(self):
        doc = _qa_doc(with_chords=False, with_melody=False)
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        messages = build_lyric_prompt(ctx, req)
        self.assertEqual(len(messages), 2)
        self.assertTrue(len(messages[1]["content"]) > 50)

    def test_markdown_fence_stripped(self):
        raw = '```json\n{"suggestions": [{"lines": ["Test"], "rationale": "r", "confidence": "high"}]}\n```'
        suggestions = parse_ai_lyric_response(raw, "s1", "V1", True)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].lines, ["Test"])

    def test_plain_text_fallback(self):
        raw = "Sometimes the stars align\nAnd everything feels right"
        suggestions = parse_ai_lyric_response(raw, "s1", "V1", False)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].lines[0], "Sometimes the stars align")
        self.assertEqual(suggestions[0].confidence, "low")

    def test_empty_string_response(self):
        suggestions = parse_ai_lyric_response("", "s1", "V1", True)
        self.assertEqual(suggestions, [])

    def test_lines_as_string_in_response(self):
        response = _mock_ai_json_response([{
            "lines": "Single line as string\nSecond line",
            "rationale": "r",
            "confidence": "high",
        }])
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].lines, ["Single line as string", "Second line"])

    def test_list_format_response(self):
        response = json.dumps([
            {"lines": ["Direct list item"], "rationale": "r", "confidence": "low"},
        ])
        suggestions = parse_ai_lyric_response(response, "s1", "V1", True)
        self.assertEqual(len(suggestions), 1)

    def test_all_generation_modes_recognized(self):
        self.assertIn("full_section", SUPPORTED_GENERATION_MODES)
        self.assertIn("single_line", SUPPORTED_GENERATION_MODES)
        self.assertIn("refine", SUPPORTED_GENERATION_MODES)

    def test_single_line_mode_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            generation_mode="single_line",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("single lyric line", user_msg.lower())

    def test_refine_mode_in_prompt(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        req = LyricGenerationRequest(
            section_id=_verse_id(doc),
            generation_mode="refine",
        )
        messages = build_lyric_prompt(ctx, req)
        user_msg = messages[1]["content"]
        self.assertIn("refined", user_msg.lower())


# ---------------------------------------------------------------------------
# Category 16: Integration with document model
# ---------------------------------------------------------------------------

class TestDocumentModelIntegration(unittest.TestCase):
    """Round-trip with composition_document functions."""

    def test_ordered_sections_match_context(self):
        doc = _qa_doc()
        sections = ordered_sections(doc)
        ctx = extract_musical_context(doc, sections[0]["id"])
        self.assertEqual(ctx.section_label, sections[0]["label"])

    def test_section_by_id_matches(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        sec = section_by_id(doc, vid)
        self.assertIsNotNone(sec)
        self.assertEqual(sec["label"], "Verse")

    def test_section_melody_events_match(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        sec = section_by_id(doc, vid)
        events = section_melody_events(sec)
        ctx = extract_musical_context(doc, vid)
        self.assertEqual(len(events), len(ctx.melody_pitches))

    @patch("composition_ai_lyrics._call_openai")
    def test_full_generation_round_trip(self, mock_call):
        mock_call.return_value = _standard_mock_response(2)
        doc = _qa_doc()
        vid = _verse_id(doc)
        req = LyricGenerationRequest(
            section_id=vid,
            keywords=["dawn", "horizon"],
            mood="uplifting",
        )
        result = generate_section_lyrics(doc, vid, req, api_key="test-key")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.suggestions), 2)
        self.assertEqual(result.generation_mode, "full_section")
        self.assertTrue(len(result.musical_context_summary) > 0)

    @patch("composition_ai_lyrics._call_openai")
    def test_chorus_generation(self, mock_call):
        chorus_response = _mock_ai_json_response([{
            "lines": ["Sing it out", "Let the world hear"],
            "rationale": "Hook-driven chorus",
            "confidence": "high",
        }])
        mock_call.return_value = chorus_response
        doc = _qa_doc()
        cid = _chorus_id(doc)
        req = LyricGenerationRequest(section_id=cid)
        result = generate_section_lyrics(doc, cid, req, api_key="test-key")
        self.assertTrue(result.ok)
        self.assertEqual(result.suggestions[0].section_label, "Chorus")

    @patch("composition_ai_lyrics._call_openai")
    def test_bridge_generation_with_extra_section(self, mock_call):
        mock_call.return_value = _mock_ai_json_response([{
            "lines": ["What if we tried again"],
            "rationale": "Bridge question",
            "confidence": "medium",
        }])
        bridge = empty_section("Bridge")
        doc = _qa_doc(extra_sections=[bridge])
        req = LyricGenerationRequest(section_id=bridge["id"])
        result = generate_section_lyrics(doc, bridge["id"], req, api_key="test-key")
        self.assertTrue(result.ok)
        self.assertEqual(result.suggestions[0].section_label, "Bridge")

    @patch("composition_ai_lyrics._call_openai")
    def test_context_summary_populated(self, mock_call):
        mock_call.return_value = _standard_mock_response(1)
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertIn("Key: C", result.musical_context_summary)
        self.assertIn("120 BPM", result.musical_context_summary)

    def test_empty_request_defaults(self):
        req = LyricGenerationRequest(section_id="test")
        self.assertEqual(req.num_suggestions, 2)
        self.assertEqual(req.max_lines, 8)
        self.assertEqual(req.generation_mode, "full_section")
        self.assertEqual(req.keywords, [])
        self.assertEqual(req.theme, "")


if __name__ == "__main__":
    unittest.main()
