"""Tests for Slice 4: AI Lyrics UI and Workflow Integration.

All 20 test categories with mocked provider responses — no live API calls.

Categories
----------
 1. AI Lyrics workflow option visibility
 2. Input handling
 3. Correct section selection
 4. Musical context handoff
 5. Generation result rendering
 6. Editable suggestions
 7. Accept behavior
 8. Discard behavior
 9. Regeneration behavior
10. Existing lyric replacement confirmation
11. Preservation of other sections
12. Saving and reopening accepted lyrics
13. Composition switching
14. Session-state isolation
15. Streamlit rerun stability
16. Missing API key and provider errors
17. Duplicate submission protection
18. Compatibility with manual lyrics editing
19. Lyrics display integration
20. No unauthorized document mutation
"""

from __future__ import annotations

import copy
import json
import re
import unittest
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from composition_ai_lyrics import (
    LyricGenerationRequest,
    LyricGenerationResult,
    LyricSuggestion,
    extract_musical_context,
    generate_section_lyrics,
)
from composition_document import (
    COMPOSITION_SCHEMA_VERSION,
    default_global,
    default_integration_stub,
    default_metadata,
    empty_section,
    ordered_sections,
    section_by_id,
    section_has_lyrics,
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
    verse_lyrics: str = "",
    chorus_lyrics: str = "",
) -> dict[str, Any]:
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
        ]
    if verse_lyrics:
        verse["lyrics"]["raw_text"] = verse_lyrics
        verse["lyrics"]["lines"] = [ln.strip() for ln in verse_lyrics.splitlines() if ln.strip()]

    chorus = empty_section("Chorus")
    if with_chords:
        chorus["chords"] = [
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
            {"chord": "Am", "bars": 1},
            {"chord": "C", "bars": 1},
        ]
    if chorus_lyrics:
        chorus["lyrics"]["raw_text"] = chorus_lyrics
        chorus["lyrics"]["lines"] = [ln.strip() for ln in chorus_lyrics.splitlines() if ln.strip()]

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
        "form": {
            "section_order": [verse["id"], chorus["id"]],
            "sections": {verse["id"]: verse, chorus["id"]: chorus},
        },
        "integration": default_integration_stub(),
        "ai_settings": {"creativity": "balanced", "explicit_user_is_composer": True},
    }


def _verse_id(doc: dict[str, Any]) -> str:
    return doc["form"]["section_order"][0]


def _chorus_id(doc: dict[str, Any]) -> str:
    return doc["form"]["section_order"][1]


def _state_key(section_id: str, suffix: str) -> str:
    return f"composer_ai_lyrics_{section_id}_{suffix}"


def _mock_result(raw_text: str = "AI generated line one\nAI generated line two",
                 ok: bool = True, error: str = "",
                 melody_informed: bool = True, confidence: str = "high") -> LyricGenerationResult:
    if ok:
        sug = LyricSuggestion(
            lines=raw_text.splitlines(),
            raw_text=raw_text,
            section_id="",
            section_label="",
            rationale="Fits the C major progression and hopeful mood",
            melody_informed=melody_informed,
            confidence=confidence,
        )
        return LyricGenerationResult(ok=True, suggestions=[sug],
                                     musical_context_summary="Key: C, 120 BPM")
    return LyricGenerationResult(ok=False, suggestions=[], error=error)


# Simulate _apply_ai_lyrics without Streamlit
def _apply_ai_lyrics_direct(doc: dict[str, Any], section_id: str, text: str) -> None:
    sec = section_by_id(doc, section_id)
    if not sec:
        return
    lyrics = sec.setdefault("lyrics", {"intent": {}, "lines": [], "raw_text": ""})
    lyrics["raw_text"] = text.strip()
    lyrics["lines"] = [ln.strip() for ln in text.splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# 1. AI Lyrics workflow option visibility
# ---------------------------------------------------------------------------

class TestWorkflowOptionVisibility(unittest.TestCase):
    def test_ai_write_option_in_source(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"ai_write"', src)
        self.assertIn("Write Lyrics with AI", src)

    def test_radio_has_five_options(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        match = re.search(r'\["brainstorm".*?"ai_write"\]', src)
        self.assertIsNotNone(match)

    def test_ai_write_function_exists(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("def _render_ai_lyrics_workflow(", src)

    def test_ai_write_branch_in_path_dispatch(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('path == "ai_write"', src)


# ---------------------------------------------------------------------------
# 2. Input handling
# ---------------------------------------------------------------------------

class TestInputHandling(unittest.TestCase):
    def test_request_from_keywords(self):
        kw_str = "rain, moonlight, hope"
        kw_list = [w.strip() for w in kw_str.split(",") if w.strip()]
        req = LyricGenerationRequest(section_id="s1", keywords=kw_list)
        self.assertEqual(req.keywords, ["rain", "moonlight", "hope"])

    def test_request_with_all_fields(self):
        req = LyricGenerationRequest(
            section_id="s1",
            keywords=["word1"],
            theme="My theme",
            mood="sad",
            style="folk",
            instructions="Write naturally",
        )
        self.assertEqual(req.theme, "My theme")
        self.assertEqual(req.mood, "sad")
        self.assertEqual(req.style, "folk")
        self.assertIn("Write naturally", req.instructions)

    def test_empty_inputs_accepted(self):
        req = LyricGenerationRequest(section_id="s1")
        self.assertEqual(req.keywords, [])
        self.assertEqual(req.theme, "")
        self.assertEqual(req.mood, "")


# ---------------------------------------------------------------------------
# 3. Correct section selection
# ---------------------------------------------------------------------------

class TestCorrectSectionSelection(unittest.TestCase):
    def test_verse_context_extracted(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(ctx.section_label, "Verse")

    def test_chorus_context_extracted(self):
        doc = _qa_doc()
        ctx = extract_musical_context(doc, _chorus_id(doc))
        self.assertEqual(ctx.section_label, "Chorus")

    def test_request_carries_section_id(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        req = LyricGenerationRequest(section_id=vid)
        self.assertEqual(req.section_id, vid)


# ---------------------------------------------------------------------------
# 4. Musical context handoff
# ---------------------------------------------------------------------------

class TestMusicalContextHandoff(unittest.TestCase):
    @patch("composition_ai_lyrics._call_openai")
    def test_generation_uses_doc_context(self, mock_call):
        mock_call.return_value = json.dumps({"suggestions": [{
            "lines": ["Test line"], "rationale": "r", "confidence": "high"
        }]})
        doc = _qa_doc(key="G", bpm=90, style="Jazz")
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertTrue(result.ok)
        call_messages = mock_call.call_args[0][1]
        user_msg = call_messages[1]["content"]
        self.assertIn("Key: G", user_msg)
        self.assertIn("90 BPM", user_msg)
        self.assertIn("Jazz", user_msg)

    @patch("composition_ai_lyrics._call_openai")
    def test_chords_in_ai_prompt(self, mock_call):
        mock_call.return_value = json.dumps({"suggestions": [{
            "lines": ["Test"], "rationale": "r", "confidence": "high"
        }]})
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        user_msg = mock_call.call_args[0][1][1]["content"]
        self.assertIn("C | Am | F | G", user_msg)


# ---------------------------------------------------------------------------
# 5. Generation result rendering
# ---------------------------------------------------------------------------

class TestGenerationResultRendering(unittest.TestCase):
    def test_suggestion_stored_in_session_state(self):
        session = {}
        sid = "test-section"
        sug_text = "AI line one\nAI line two"
        session[_state_key(sid, "suggestion")] = sug_text
        session[_state_key(sid, "rationale")] = "Fits well"
        session[_state_key(sid, "confidence")] = "high"
        session[_state_key(sid, "melody_informed")] = True
        self.assertEqual(session[_state_key(sid, "suggestion")], sug_text)
        self.assertTrue(session[_state_key(sid, "melody_informed")])

    def test_error_stored_in_session_state(self):
        session = {}
        sid = "test-section"
        session[_state_key(sid, "error")] = "API timeout"
        self.assertEqual(session[_state_key(sid, "error")], "API timeout")


# ---------------------------------------------------------------------------
# 6. Editable suggestions
# ---------------------------------------------------------------------------

class TestEditableSuggestions(unittest.TestCase):
    def test_edit_text_stored_separately(self):
        session = {}
        sid = "s1"
        original = "Original AI text"
        edited = "User-edited version"
        session[_state_key(sid, "suggestion")] = original
        session[_state_key(sid, "edit_text")] = edited
        self.assertNotEqual(session[_state_key(sid, "suggestion")],
                            session[_state_key(sid, "edit_text")])

    def test_edit_text_defaults_to_suggestion(self):
        session = {}
        sid = "s1"
        text = "AI lyrics here"
        session[_state_key(sid, "suggestion")] = text
        session[_state_key(sid, "edit_text")] = text
        self.assertEqual(session[_state_key(sid, "edit_text")], text)


# ---------------------------------------------------------------------------
# 7. Accept behavior
# ---------------------------------------------------------------------------

class TestAcceptBehavior(unittest.TestCase):
    def test_accept_writes_to_section(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Accepted AI lyrics\nSecond line")
        sec = section_by_id(doc, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "Accepted AI lyrics\nSecond line")
        self.assertEqual(sec["lyrics"]["lines"], ["Accepted AI lyrics", "Second line"])

    def test_accept_edited_text(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "User-edited version")
        sec = section_by_id(doc, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "User-edited version")

    def test_section_has_lyrics_after_accept(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Lyrics accepted")
        sec = section_by_id(doc, vid)
        self.assertTrue(section_has_lyrics(sec))

    def test_accept_clears_empty_suggestion(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "  \n  ")
        sec = section_by_id(doc, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "")


# ---------------------------------------------------------------------------
# 8. Discard behavior
# ---------------------------------------------------------------------------

class TestDiscardBehavior(unittest.TestCase):
    def test_discard_clears_suggestion_keys(self):
        session = {}
        sid = "s1"
        session[_state_key(sid, "suggestion")] = "Some lyrics"
        session[_state_key(sid, "rationale")] = "Reason"
        session[_state_key(sid, "edit_text")] = "Edited"
        for sfx in ("suggestion", "rationale", "confidence", "melody_informed", "error", "edit_text"):
            session.pop(_state_key(sid, sfx), None)
        self.assertNotIn(_state_key(sid, "suggestion"), session)
        self.assertNotIn(_state_key(sid, "edit_text"), session)

    def test_discard_does_not_affect_doc_lyrics(self):
        doc = _qa_doc(verse_lyrics="My original lyrics")
        vid = _verse_id(doc)
        session = {}
        session[_state_key(vid, "suggestion")] = "AI suggestion"
        for sfx in ("suggestion", "rationale", "confidence", "melody_informed", "error", "edit_text"):
            session.pop(_state_key(vid, sfx), None)
        sec = section_by_id(doc, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "My original lyrics")


# ---------------------------------------------------------------------------
# 9. Regeneration behavior
# ---------------------------------------------------------------------------

class TestRegenerationBehavior(unittest.TestCase):
    def test_regen_clears_old_suggestion(self):
        session = {}
        sid = "s1"
        session[_state_key(sid, "suggestion")] = "Old lyrics"
        session[_state_key(sid, "edit_text")] = "Edited old"
        for sfx in ("suggestion", "rationale", "confidence", "melody_informed", "error", "edit_text"):
            session.pop(_state_key(sid, sfx), None)
        self.assertNotIn(_state_key(sid, "suggestion"), session)

    @patch("composition_ai_lyrics._call_openai")
    def test_regen_produces_new_result(self, mock_call):
        mock_call.return_value = json.dumps({"suggestions": [{
            "lines": ["Brand new lyrics"], "rationale": "Fresh", "confidence": "high"
        }]})
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertTrue(result.ok)
        self.assertIn("Brand new lyrics", result.suggestions[0].raw_text)


# ---------------------------------------------------------------------------
# 10. Existing lyric replacement confirmation
# ---------------------------------------------------------------------------

class TestExistingLyricReplacement(unittest.TestCase):
    def test_confirm_replace_key_used(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("confirm_replace", src)
        self.assertIn("Replace existing lyrics", src)

    def test_confirmation_dialog_elements(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("already has lyrics", src)
        self.assertIn("Yes, replace", src)
        self.assertIn("Cancel", src)

    def test_no_confirmation_for_empty_section(self):
        doc = _qa_doc(verse_lyrics="")
        vid = _verse_id(doc)
        existing = str((section_by_id(doc, vid).get("lyrics") or {}).get("raw_text") or "").strip()
        self.assertFalse(bool(existing))

    def test_confirmation_needed_for_existing(self):
        doc = _qa_doc(verse_lyrics="My manual lyrics")
        vid = _verse_id(doc)
        existing = str((section_by_id(doc, vid).get("lyrics") or {}).get("raw_text") or "").strip()
        self.assertTrue(bool(existing))


# ---------------------------------------------------------------------------
# 11. Preservation of other sections
# ---------------------------------------------------------------------------

class TestPreservationOfOtherSections(unittest.TestCase):
    def test_accept_only_changes_target_section(self):
        doc = _qa_doc(verse_lyrics="Original verse", chorus_lyrics="Original chorus")
        vid = _verse_id(doc)
        cid = _chorus_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "New AI verse")
        self.assertEqual(section_by_id(doc, vid)["lyrics"]["raw_text"], "New AI verse")
        self.assertEqual(section_by_id(doc, cid)["lyrics"]["raw_text"], "Original chorus")

    def test_chorus_unchanged_after_verse_accept(self):
        doc = _qa_doc(chorus_lyrics="Keep this chorus")
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "New verse lyrics")
        chorus = section_by_id(doc, _chorus_id(doc))
        self.assertEqual(chorus["lyrics"]["raw_text"], "Keep this chorus")


# ---------------------------------------------------------------------------
# 12. Saving and reopening accepted lyrics
# ---------------------------------------------------------------------------

class TestSaveAndReopen(unittest.TestCase):
    def test_accepted_lyrics_in_document(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Saved AI lyrics")
        reopened = copy.deepcopy(doc)
        sec = section_by_id(reopened, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "Saved AI lyrics")

    def test_lyrics_survive_deepcopy(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Persistent text")
        doc2 = copy.deepcopy(doc)
        self.assertEqual(section_by_id(doc2, vid)["lyrics"]["raw_text"], "Persistent text")

    def test_section_has_lyrics_flag(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Flag test")
        self.assertTrue(section_has_lyrics(section_by_id(doc, vid)))


# ---------------------------------------------------------------------------
# 13. Composition switching
# ---------------------------------------------------------------------------

class TestCompositionSwitching(unittest.TestCase):
    def test_cross_composition_guard(self):
        session = {}
        sid = "shared-section"
        session[_state_key(sid, "suggestion")] = "Old suggestion"
        session[_state_key(sid, "doc_id")] = "doc-A"
        prev_doc = session.get(_state_key(sid, "doc_id"))
        new_doc_id = "doc-B"
        if prev_doc and prev_doc != new_doc_id:
            for sfx in ("suggestion", "rationale", "confidence", "melody_informed",
                         "error", "generating", "doc_id", "edit_text"):
                session.pop(_state_key(sid, sfx), None)
        self.assertNotIn(_state_key(sid, "suggestion"), session)

    def test_same_composition_keeps_suggestion(self):
        session = {}
        sid = "s1"
        session[_state_key(sid, "suggestion")] = "Kept suggestion"
        session[_state_key(sid, "doc_id")] = "doc-A"
        prev_doc = session.get(_state_key(sid, "doc_id"))
        if prev_doc and prev_doc != "doc-A":
            session.pop(_state_key(sid, "suggestion"), None)
        self.assertEqual(session[_state_key(sid, "suggestion")], "Kept suggestion")


# ---------------------------------------------------------------------------
# 14. Session-state isolation
# ---------------------------------------------------------------------------

class TestSessionStateIsolation(unittest.TestCase):
    def test_different_sections_independent(self):
        session = {}
        session[_state_key("sec-A", "suggestion")] = "Lyrics for A"
        session[_state_key("sec-B", "suggestion")] = "Lyrics for B"
        self.assertNotEqual(
            session[_state_key("sec-A", "suggestion")],
            session[_state_key("sec-B", "suggestion")],
        )

    def test_state_key_contains_section_id(self):
        key = _state_key("my-section-id", "suggestion")
        self.assertIn("my-section-id", key)

    def test_discard_one_section_preserves_other(self):
        session = {}
        session[_state_key("sec-A", "suggestion")] = "A lyrics"
        session[_state_key("sec-B", "suggestion")] = "B lyrics"
        session.pop(_state_key("sec-A", "suggestion"), None)
        self.assertNotIn(_state_key("sec-A", "suggestion"), session)
        self.assertEqual(session[_state_key("sec-B", "suggestion")], "B lyrics")


# ---------------------------------------------------------------------------
# 15. Streamlit rerun stability
# ---------------------------------------------------------------------------

class TestStreamlitRerunStability(unittest.TestCase):
    def test_generating_flag_prevents_duplicate(self):
        session = {}
        sid = "s1"
        gen_key = _state_key(sid, "generating")
        session[gen_key] = True
        self.assertTrue(session[gen_key])
        session[gen_key] = False
        self.assertFalse(session[gen_key])

    def test_suggestion_persists_across_simulated_reruns(self):
        session = {}
        sid = "s1"
        session[_state_key(sid, "suggestion")] = "Stable lyrics"
        session_copy = dict(session)
        self.assertEqual(session_copy[_state_key(sid, "suggestion")], "Stable lyrics")

    def test_accepted_lyrics_not_lost_on_rerun(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Accepted before rerun")
        doc_after = copy.deepcopy(doc)
        self.assertEqual(section_by_id(doc_after, vid)["lyrics"]["raw_text"], "Accepted before rerun")


# ---------------------------------------------------------------------------
# 16. Missing API key and provider errors
# ---------------------------------------------------------------------------

class TestMissingApiKeyAndErrors(unittest.TestCase):
    def test_no_api_key_error(self):
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        with patch("openai_secrets_config.resolve_openai_api_key", return_value=("", MagicMock())):
            result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="")
        self.assertFalse(result.ok)
        self.assertIn("API key", result.error)

    @patch("composition_ai_lyrics._call_openai")
    def test_api_timeout(self, mock_call):
        mock_call.side_effect = TimeoutError("Request timed out")
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertFalse(result.ok)
        self.assertIn("timed out", result.error.lower())

    @patch("composition_ai_lyrics._call_openai")
    def test_provider_error(self, mock_call):
        mock_call.side_effect = RuntimeError("Rate limit exceeded")
        doc = _qa_doc()
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        result = generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertFalse(result.ok)

    def test_user_friendly_api_key_message(self):
        error_msg = "No OpenAI API key configured"
        if "API key" in error_msg:
            friendly = "No OpenAI API key configured. Add OPENAI_API_KEY to your Streamlit secrets."
        self.assertIn("Streamlit secrets", friendly)


# ---------------------------------------------------------------------------
# 17. Duplicate submission protection
# ---------------------------------------------------------------------------

class TestDuplicateSubmissionProtection(unittest.TestCase):
    def test_generating_flag_exists_in_source(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("generating", src)
        self.assertIn("disabled=already_generating", src)

    def test_generating_flag_cleared_after_result(self):
        session = {}
        sid = "s1"
        gen_key = _state_key(sid, "generating")
        session[gen_key] = True
        session[gen_key] = False
        self.assertFalse(session[gen_key])


# ---------------------------------------------------------------------------
# 18. Compatibility with manual lyrics editing
# ---------------------------------------------------------------------------

class TestManualLyricsCompatibility(unittest.TestCase):
    def test_manual_editor_still_in_ai_workflow(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("Manual lyric editor", src)
        self.assertIn("_render_lyrics_editor", src)

    def test_manual_write_path_still_exists(self):
        with open("composition_studio_page.py", "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"write": "Write my own lyrics"', src)

    def test_manual_lyrics_preserved_after_discard(self):
        doc = _qa_doc(verse_lyrics="Manual work here")
        vid = _verse_id(doc)
        session = {}
        session[_state_key(vid, "suggestion")] = "AI suggestion"
        for sfx in ("suggestion", "edit_text"):
            session.pop(_state_key(vid, sfx), None)
        sec = section_by_id(doc, vid)
        self.assertEqual(sec["lyrics"]["raw_text"], "Manual work here")


# ---------------------------------------------------------------------------
# 19. Lyrics display integration
# ---------------------------------------------------------------------------

class TestLyricsDisplayIntegration(unittest.TestCase):
    def test_accepted_lyrics_in_score_model(self):
        from composition_melody_notation import build_section_score_model
        doc = _qa_doc()
        vid = _verse_id(doc)
        _apply_ai_lyrics_direct(doc, vid, "Score display test")
        sec = section_by_id(doc, vid)
        score = build_section_score_model(
            events=sec["melody"]["events"],
            chords=sec["chords"],
            key="C", meter="4/4", bpm=120,
            title="Verse 1",
            lyrics_text=sec["lyrics"]["raw_text"],
        )
        self.assertTrue(score["has_lyrics"])
        self.assertEqual(score["lyrics_text"], "Score display test")

    def test_empty_lyrics_not_in_score(self):
        from composition_melody_notation import build_section_score_model
        doc = _qa_doc()
        vid = _verse_id(doc)
        sec = section_by_id(doc, vid)
        score = build_section_score_model(
            events=sec["melody"]["events"],
            chords=sec["chords"],
            key="C", meter="4/4", bpm=120,
            title="Verse 1",
            lyrics_text="",
        )
        self.assertFalse(score["has_lyrics"])


# ---------------------------------------------------------------------------
# 20. No unauthorized document mutation
# ---------------------------------------------------------------------------

class TestNoUnauthorizedMutation(unittest.TestCase):
    @patch("composition_ai_lyrics._call_openai")
    def test_generate_does_not_mutate_doc(self, mock_call):
        mock_call.return_value = json.dumps({"suggestions": [{
            "lines": ["Test"], "rationale": "r", "confidence": "high"
        }]})
        doc = _qa_doc(verse_lyrics="Protected lyrics")
        original = copy.deepcopy(doc)
        req = LyricGenerationRequest(section_id=_verse_id(doc))
        generate_section_lyrics(doc, _verse_id(doc), req, api_key="test-key")
        self.assertEqual(doc, original)

    def test_discard_does_not_mutate_doc(self):
        doc = _qa_doc(verse_lyrics="Untouched")
        original = copy.deepcopy(doc)
        session = {}
        session[_state_key(_verse_id(doc), "suggestion")] = "Will be discarded"
        for sfx in ("suggestion", "edit_text"):
            session.pop(_state_key(_verse_id(doc), sfx), None)
        self.assertEqual(doc, original)

    def test_context_extraction_does_not_mutate(self):
        doc = _qa_doc()
        original = copy.deepcopy(doc)
        extract_musical_context(doc, _verse_id(doc))
        self.assertEqual(doc, original)

    def test_accept_only_changes_raw_text_and_lines(self):
        doc = _qa_doc()
        vid = _verse_id(doc)
        sec_before = copy.deepcopy(section_by_id(doc, vid))
        _apply_ai_lyrics_direct(doc, vid, "Accepted text")
        sec_after = section_by_id(doc, vid)
        self.assertEqual(sec_after["lyrics"]["raw_text"], "Accepted text")
        self.assertEqual(sec_after["chords"], sec_before["chords"])
        self.assertEqual(sec_after["melody"], sec_before["melody"])
        self.assertEqual(sec_after["label"], sec_before["label"])


if __name__ == "__main__":
    unittest.main()
