"""Tests for composition_lyrics_alignment — Slice 6B Stage 1.

Covers all 34 required categories from the specification.
"""
from __future__ import annotations

import copy
import json
import unittest
from typing import Any

from composition_lyrics_alignment import (
    ALIGNMENT_STATUSES,
    align_lyrics_to_melody,
    align_section,
    alignment_from_json,
    alignment_to_abc_w_lines,
    alignment_to_json,
    build_abc_with_lyrics,
    check_staleness,
    confirm_alignment,
    empty_alignment,
    get_alignment,
    lyrics_fingerprint,
    melody_fingerprint,
    realign_section,
    section_alignment_is_compatible,
    segment_word_into_syllables,
    set_alignment,
    tokenize_lyrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ev(pitch: str = "C4", dur: float = 1.0, beat: float = 0, measure: int = 1,
         is_rest: bool = False) -> dict[str, Any]:
    return {"pitch": pitch, "duration_beats": dur, "beat": beat, "measure": measure,
            "is_rest": is_rest}


def _rest(dur: float = 1.0, beat: float = 0, measure: int = 1) -> dict[str, Any]:
    return _ev(pitch="rest", dur=dur, beat=beat, measure=measure, is_rest=True)


def _section(lyrics: str = "", events: list | None = None,
             alignment: dict | None = None) -> dict[str, Any]:
    sec: dict[str, Any] = {
        "id": "test-section-1",
        "label": "Verse",
        "melody": {"events": events or [], "intent": {}, "phrases": []},
        "lyrics": {"raw_text": lyrics, "lines": lyrics.split("\n") if lyrics else [], "intent": {}},
    }
    if alignment is not None:
        sec["lyrics_alignment"] = alignment
    return sec


# ===========================================================================
# 1. Single-syllable words
# ===========================================================================

class TestSingleSyllableWords(unittest.TestCase):
    def test_single_word(self):
        syls = segment_word_into_syllables("love")
        self.assertEqual(syls, ["love"])

    def test_short_words(self):
        for w in ("I", "a", "we", "no", "go", "me"):
            syls = segment_word_into_syllables(w)
            self.assertEqual(len(syls), 1, f"Expected 1 syllable for '{w}'")

    def test_tokenize_single_syllable_line(self):
        tokens = tokenize_lyrics("I love you")
        self.assertEqual(len(tokens), 3)
        for t in tokens:
            self.assertTrue(t["is_word_end"])


# ===========================================================================
# 2. Multisyllabic words
# ===========================================================================

class TestMultisyllabicWords(unittest.TestCase):
    def test_two_syllable(self):
        syls = segment_word_into_syllables("hello")
        self.assertEqual(len(syls), 2)

    def test_three_syllable(self):
        syls = segment_word_into_syllables("beautiful")
        self.assertGreaterEqual(len(syls), 2)

    def test_tokenize_preserves_word_index(self):
        tokens = tokenize_lyrics("beautiful morning")
        word_indices = {t["word_index"] for t in tokens}
        self.assertEqual(word_indices, {0, 1})

    def test_syllable_continuation(self):
        tokens = tokenize_lyrics("hello world")
        hello_syls = [t for t in tokens if t["word_index"] == 0]
        if len(hello_syls) > 1:
            self.assertFalse(hello_syls[0]["is_word_end"])
            self.assertTrue(hello_syls[-1]["is_word_end"])


# ===========================================================================
# 3. Punctuation and contractions
# ===========================================================================

class TestPunctuationContractions(unittest.TestCase):
    def test_contraction_dont(self):
        tokens = tokenize_lyrics("don't")
        self.assertGreaterEqual(len(tokens), 1)
        reconstructed = "".join(t["text"] for t in tokens)
        self.assertIn("don", reconstructed)

    def test_contraction_ill(self):
        tokens = tokenize_lyrics("I'll")
        self.assertGreaterEqual(len(tokens), 1)

    def test_punctuation_preserved_in_text(self):
        tokens = tokenize_lyrics("Oh! Yeah?")
        texts = [t["text"] for t in tokens]
        self.assertTrue(any("Oh" in t for t in texts))


# ===========================================================================
# 4. Hyphenated words
# ===========================================================================

class TestHyphenatedWords(unittest.TestCase):
    def test_hyphenated_word(self):
        tokens = tokenize_lyrics("rock-and-roll")
        self.assertGreaterEqual(len(tokens), 3)

    def test_single_word_index(self):
        tokens = tokenize_lyrics("well-known")
        word_indices = {t["word_index"] for t in tokens}
        self.assertEqual(len(word_indices), 1)


# ===========================================================================
# 5. Multiple lyric lines
# ===========================================================================

class TestMultipleLyricLines(unittest.TestCase):
    def test_two_lines(self):
        tokens = tokenize_lyrics("line one\nline two")
        self.assertGreater(len(tokens), 2)

    def test_empty_line_between(self):
        tokens = tokenize_lyrics("verse one\n\nverse two")
        self.assertGreater(len(tokens), 0)

    def test_word_index_spans_lines(self):
        tokens = tokenize_lyrics("hello\nworld")
        word_indices = {t["word_index"] for t in tokens}
        self.assertGreater(len(word_indices), 1)


# ===========================================================================
# 6. Equal note and syllable counts
# ===========================================================================

class TestEqualCounts(unittest.TestCase):
    def test_four_syllables_four_notes(self):
        events = [_ev("C4", 1.0, i, 1) for i in range(4)]
        alignment = align_lyrics_to_melody("I love New York", events)
        syllable_assigns = [a for a in alignment["event_assignments"] if a["type"] == "syllable"]
        self.assertEqual(len(syllable_assigns), 4)
        self.assertEqual(alignment["status"], "provisional")
        self.assertEqual(len(alignment["warnings"]), 0)

    def test_no_melisma_when_equal(self):
        events = [_ev("C4", 1.0, i, 1) for i in range(3)]
        alignment = align_lyrics_to_melody("one two three", events)
        melisma = [a for a in alignment["event_assignments"] if a["type"] == "melisma"]
        self.assertEqual(len(melisma), 0)


# ===========================================================================
# 7. More notes than syllables
# ===========================================================================

class TestMoreNotesThanSyllables(unittest.TestCase):
    def test_excess_notes_become_melisma(self):
        events = [_ev("C4", 1.0, i, 1) for i in range(6)]
        alignment = align_lyrics_to_melody("la la", events)
        melisma = [a for a in alignment["event_assignments"] if a["type"] == "melisma"]
        self.assertGreater(len(melisma), 0)

    def test_melisma_references_last_syllable(self):
        events = [_ev("C4", 1.0, i, 1) for i in range(4)]
        alignment = align_lyrics_to_melody("love", events)
        for a in alignment["event_assignments"]:
            if a["type"] == "melisma":
                self.assertEqual(a["syllable_index"], 0)


# ===========================================================================
# 8. More syllables than notes
# ===========================================================================

class TestMoreSyllablesThanNotes(unittest.TestCase):
    def test_excess_syllables_warning(self):
        events = [_ev("C4", 1.0, 0, 1)]
        alignment = align_lyrics_to_melody("I love New York City", events)
        self.assertTrue(any("could not be assigned" in w for w in alignment["warnings"]))

    def test_no_squeeze_onto_final_notes(self):
        events = [_ev("C4", 1.0, 0, 1), _ev("D4", 1.0, 1, 1)]
        alignment = align_lyrics_to_melody("one two three four five", events)
        assigned_count = sum(1 for a in alignment["event_assignments"] if a["type"] == "syllable")
        self.assertEqual(assigned_count, 2)


# ===========================================================================
# 9. Melismas
# ===========================================================================

class TestMelismas(unittest.TestCase):
    def test_melisma_in_abc(self):
        events = [_ev("C4", 1.0, 0, 1), _ev("D4", 1.0, 1, 1), _ev("E4", 1.0, 2, 1)]
        alignment = align_lyrics_to_melody("ah", events)
        w_line = alignment_to_abc_w_lines(alignment, events)
        self.assertIn("*", w_line)

    def test_melisma_type_in_assignments(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        alignment = align_lyrics_to_melody("one", events)
        types = [a["type"] for a in alignment["event_assignments"]]
        self.assertEqual(types, ["syllable", "melisma", "melisma"])


# ===========================================================================
# 10. Sustained notes
# ===========================================================================

class TestSustainedNotes(unittest.TestCase):
    def test_long_note_gets_syllable(self):
        events = [_ev("C4", 4.0, 0, 1), _ev("D4", 1.0, 4, 2)]
        alignment = align_lyrics_to_melody("hold it", events)
        assigns = alignment["event_assignments"]
        self.assertEqual(assigns[0]["type"], "syllable")
        self.assertEqual(assigns[1]["type"], "syllable")


# ===========================================================================
# 11. Rests
# ===========================================================================

class TestRests(unittest.TestCase):
    def test_rest_gets_rest_type(self):
        events = [_ev("C4"), _rest(), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        self.assertEqual(alignment["event_assignments"][1]["type"], "rest")

    def test_rest_not_assigned_syllable(self):
        events = [_rest(), _ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        self.assertEqual(alignment["event_assignments"][0]["syllable_index"], -1)

    def test_syllable_skips_rest(self):
        events = [_ev("C4"), _rest(), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        assigns = alignment["event_assignments"]
        self.assertEqual(assigns[0]["syllable_index"], 0)
        self.assertEqual(assigns[2]["syllable_index"], 1)


# ===========================================================================
# 12. Phrase boundaries
# ===========================================================================

class TestPhraseBoundaries(unittest.TestCase):
    def test_rest_creates_natural_phrase_break(self):
        events = [_ev("C4"), _ev("D4"), _rest(2.0), _ev("E4"), _ev("F4")]
        alignment = align_lyrics_to_melody("one two three four", events)
        assigns = alignment["event_assignments"]
        self.assertEqual(assigns[2]["type"], "rest")
        self.assertEqual(assigns[3]["type"], "syllable")


# ===========================================================================
# 13. Measure boundaries
# ===========================================================================

class TestMeasureBoundaries(unittest.TestCase):
    def test_abc_barlines_in_w_line(self):
        events = [
            _ev("C4", 1.0, 0, 1), _ev("D4", 1.0, 1, 1),
            _ev("E4", 1.0, 2, 1), _ev("F4", 1.0, 3, 1),
            _ev("G4", 1.0, 0, 2), _ev("A4", 1.0, 1, 2),
            _ev("B4", 1.0, 2, 2), _ev("C5", 1.0, 3, 2),
        ]
        alignment = align_lyrics_to_melody(
            "one two three four five six sev en", events, meter="4/4"
        )
        w_line = alignment_to_abc_w_lines(alignment, events, meter="4/4")
        self.assertIn("|", w_line)


# ===========================================================================
# 14. Repeated melody patterns
# ===========================================================================

class TestRepeatedPatterns(unittest.TestCase):
    def test_repeated_pitch_different_syllables(self):
        events = [_ev("C4"), _ev("C4"), _ev("C4")]
        alignment = align_lyrics_to_melody("la la la", events)
        indices = [a["syllable_index"] for a in alignment["event_assignments"]]
        self.assertEqual(indices, [0, 1, 2])


# ===========================================================================
# 15. Missing melody
# ===========================================================================

class TestMissingMelody(unittest.TestCase):
    def test_no_events(self):
        alignment = align_lyrics_to_melody("hello world", [])
        self.assertEqual(alignment["status"], "provisional")
        self.assertTrue(any("No melody" in w for w in alignment["warnings"]))
        self.assertEqual(len(alignment["event_assignments"]), 0)


# ===========================================================================
# 16. Missing lyrics
# ===========================================================================

class TestMissingLyrics(unittest.TestCase):
    def test_no_lyrics(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("", events)
        self.assertEqual(alignment["status"], "provisional")
        self.assertTrue(any("No lyrics" in w for w in alignment["warnings"]))
        for a in alignment["event_assignments"]:
            self.assertIn(a["type"], ("unassigned", "rest"))


# ===========================================================================
# 17. Empty or malformed sections
# ===========================================================================

class TestEmptyMalformed(unittest.TestCase):
    def test_both_empty(self):
        alignment = align_lyrics_to_melody("", [])
        self.assertEqual(alignment["status"], "unaligned")

    def test_none_events(self):
        alignment = align_lyrics_to_melody("hello", None)
        self.assertEqual(alignment["status"], "provisional")

    def test_malformed_event_dicts(self):
        alignment = align_lyrics_to_melody("hello", [None, "bad", 42])
        self.assertEqual(len(alignment["event_assignments"]), 0)

    def test_whitespace_only_lyrics(self):
        alignment = align_lyrics_to_melody("   \n  ", [_ev("C4")])
        self.assertTrue(any("No lyrics" in w for w in alignment["warnings"]))


# ===========================================================================
# 18. Provisional alignment creation
# ===========================================================================

class TestProvisionalCreation(unittest.TestCase):
    def test_new_alignment_is_provisional(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        self.assertEqual(alignment["status"], "provisional")
        self.assertIsNone(alignment["confirmed_at"])

    def test_align_section_creates_provisional(self):
        sec = _section("hello world", [_ev("C4"), _ev("D4")])
        alignment = align_section(sec)
        self.assertEqual(alignment["status"], "provisional")


# ===========================================================================
# 19. Explicit confirmation behavior
# ===========================================================================

class TestConfirmation(unittest.TestCase):
    def test_confirm_sets_status(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        confirmed = confirm_alignment(alignment, timestamp="2026-10-21T12:00:00Z")
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(confirmed["confirmed_at"], "2026-10-21T12:00:00Z")

    def test_confirm_records_fingerprints(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        mel_fp = alignment["melody_fingerprint"]
        lyr_fp = alignment["lyrics_fingerprint"]
        confirmed = confirm_alignment(alignment)
        self.assertEqual(confirmed["confirmed_melody_fingerprint"], mel_fp)
        self.assertEqual(confirmed["confirmed_lyrics_fingerprint"], lyr_fp)

    def test_confirm_does_not_change_mappings(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        original_assigns = copy.deepcopy(alignment["event_assignments"])
        confirm_alignment(alignment)
        self.assertEqual(alignment["event_assignments"], original_assigns)


# ===========================================================================
# 20. Melody fingerprint construction
# ===========================================================================

class TestMelodyFingerprint(unittest.TestCase):
    def test_deterministic(self):
        events = [_ev("C4", 1.0), _ev("D4", 2.0)]
        self.assertEqual(melody_fingerprint(events), melody_fingerprint(events))

    def test_pitch_change_changes_fingerprint(self):
        e1 = [_ev("C4")]
        e2 = [_ev("D4")]
        self.assertNotEqual(melody_fingerprint(e1), melody_fingerprint(e2))

    def test_duration_change_changes_fingerprint(self):
        e1 = [_ev("C4", 1.0)]
        e2 = [_ev("C4", 2.0)]
        self.assertNotEqual(melody_fingerprint(e1), melody_fingerprint(e2))

    def test_rest_change_changes_fingerprint(self):
        e1 = [_ev("C4")]
        e2 = [_rest()]
        self.assertNotEqual(melody_fingerprint(e1), melody_fingerprint(e2))

    def test_order_matters(self):
        e1 = [_ev("C4"), _ev("D4")]
        e2 = [_ev("D4"), _ev("C4")]
        self.assertNotEqual(melody_fingerprint(e1), melody_fingerprint(e2))

    def test_empty(self):
        fp = melody_fingerprint([])
        self.assertTrue(len(fp) > 0)


# ===========================================================================
# 21. Lyrics fingerprint construction
# ===========================================================================

class TestLyricsFingerprint(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(lyrics_fingerprint("hello"), lyrics_fingerprint("hello"))

    def test_whitespace_normalized(self):
        self.assertEqual(lyrics_fingerprint("hello  world"), lyrics_fingerprint("hello world"))

    def test_content_change(self):
        self.assertNotEqual(lyrics_fingerprint("hello"), lyrics_fingerprint("world"))

    def test_empty(self):
        fp = lyrics_fingerprint("")
        self.assertTrue(len(fp) > 0)


# ===========================================================================
# 22. Stale alignment detection
# ===========================================================================

class TestStalenessDetection(unittest.TestCase):
    def test_melody_change_makes_stale(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        confirm_alignment(alignment)
        new_events = [_ev("D4")]
        result = check_staleness(alignment, new_events, "word")
        self.assertEqual(result["status"], "stale")
        self.assertTrue(any("Melody" in w for w in result["warnings"]))

    def test_lyrics_change_makes_stale(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        confirm_alignment(alignment)
        result = check_staleness(alignment, events, "changed")
        self.assertEqual(result["status"], "stale")
        self.assertTrue(any("Lyrics" in w for w in result["warnings"]))

    def test_no_change_stays_confirmed(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        confirm_alignment(alignment)
        result = check_staleness(alignment, events, "word")
        self.assertEqual(result["status"], "confirmed")

    def test_provisional_not_affected(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        result = check_staleness(alignment, [_ev("D4")], "changed")
        self.assertEqual(result["status"], "provisional")


# ===========================================================================
# 23. Preservation of previous confirmed mappings
# ===========================================================================

class TestPreserveConfirmedMappings(unittest.TestCase):
    def test_stale_preserves_event_assignments(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        original_assigns = copy.deepcopy(alignment["event_assignments"])
        confirm_alignment(alignment)
        check_staleness(alignment, [_ev("E4"), _ev("F4")], "one two")
        self.assertEqual(alignment["event_assignments"], original_assigns)

    def test_stale_preserves_confirmed_fingerprints(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        confirm_alignment(alignment)
        original_mel_fp = alignment["confirmed_melody_fingerprint"]
        check_staleness(alignment, [_ev("D4")], "word")
        self.assertEqual(alignment["confirmed_melody_fingerprint"], original_mel_fp)

    def test_realign_replaces_stale(self):
        sec = _section("one two", [_ev("C4"), _ev("D4")])
        align_section(sec)
        confirm_alignment(sec["lyrics_alignment"])
        sec["melody"]["events"] = [_ev("E4"), _ev("F4"), _ev("G4")]
        sec["lyrics"]["raw_text"] = "one two three"
        new_alignment = realign_section(sec)
        self.assertEqual(new_alignment["status"], "provisional")
        self.assertEqual(len(new_alignment["event_assignments"]), 3)


# ===========================================================================
# 24. JSON serialization and restoration
# ===========================================================================

class TestSerialization(unittest.TestCase):
    def test_roundtrip(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        serialized = alignment_to_json(alignment)
        restored = alignment_from_json(serialized)
        self.assertEqual(restored["status"], alignment["status"])
        self.assertEqual(restored["syllables"], alignment["syllables"])
        self.assertEqual(restored["event_assignments"], alignment["event_assignments"])

    def test_invalid_json(self):
        result = alignment_from_json("not json")
        self.assertEqual(result["status"], "unaligned")

    def test_empty_json(self):
        result = alignment_from_json("{}")
        self.assertEqual(result["status"], "unaligned")

    def test_json_string_type(self):
        serialized = alignment_to_json(empty_alignment())
        self.assertIsInstance(serialized, str)
        parsed = json.loads(serialized)
        self.assertIsInstance(parsed, dict)


# ===========================================================================
# 25. Composition/section identity
# ===========================================================================

class TestSectionIdentity(unittest.TestCase):
    def test_alignment_stored_on_section(self):
        sec = _section("hello", [_ev("C4")])
        align_section(sec)
        self.assertIn("lyrics_alignment", sec)
        self.assertEqual(sec["lyrics_alignment"]["status"], "provisional")

    def test_get_alignment_absent(self):
        sec = {"id": "s1", "melody": {}, "lyrics": {}}
        alignment = get_alignment(sec)
        self.assertEqual(alignment["status"], "unaligned")

    def test_set_alignment(self):
        sec = {"id": "s1"}
        a = empty_alignment()
        a["status"] = "provisional"
        set_alignment(sec, a)
        self.assertEqual(sec["lyrics_alignment"]["status"], "provisional")


# ===========================================================================
# 26. Multiple-section isolation
# ===========================================================================

class TestMultipleSectionIsolation(unittest.TestCase):
    def test_two_sections_independent(self):
        sec1 = _section("verse one", [_ev("C4"), _ev("D4")])
        sec2 = _section("chorus yeah", [_ev("E4"), _ev("F4"), _ev("G4")])
        a1 = align_section(sec1)
        a2 = align_section(sec2)
        self.assertNotEqual(a1["lyrics_fingerprint"], a2["lyrics_fingerprint"])
        self.assertNotEqual(a1["melody_fingerprint"], a2["melody_fingerprint"])
        self.assertEqual(len(a1["event_assignments"]), 2)
        self.assertEqual(len(a2["event_assignments"]), 3)

    def test_confirming_one_does_not_affect_other(self):
        sec1 = _section("one", [_ev("C4")])
        sec2 = _section("two", [_ev("D4")])
        align_section(sec1)
        align_section(sec2)
        confirm_alignment(sec1["lyrics_alignment"])
        self.assertEqual(sec1["lyrics_alignment"]["status"], "confirmed")
        self.assertEqual(sec2["lyrics_alignment"]["status"], "provisional")


# ===========================================================================
# 27. Compatibility with AI-accepted lyrics
# ===========================================================================

class TestAILyricsCompatibility(unittest.TestCase):
    def test_ai_accepted_text_aligns_normally(self):
        sec = _section("", [_ev("C4"), _ev("D4"), _ev("E4")])
        sec["lyrics"]["raw_text"] = "Stars above shine"
        sec["lyrics"]["lines"] = ["Stars above shine"]
        alignment = align_section(sec)
        self.assertEqual(alignment["status"], "provisional")
        syllable_assigns = [a for a in alignment["event_assignments"] if a["type"] == "syllable"]
        self.assertGreater(len(syllable_assigns), 0)


# ===========================================================================
# 28. No unaccepted AI suggestion leakage
# ===========================================================================

class TestNoAILeakage(unittest.TestCase):
    def test_alignment_uses_only_raw_text(self):
        sec = _section("", [_ev("C4"), _ev("D4")])
        sec["lyrics"]["raw_text"] = "accepted text"
        alignment = align_section(sec)
        all_texts = [s["text"] for s in alignment["syllables"]]
        joined = " ".join(all_texts)
        self.assertNotIn("pending", joined)
        self.assertIn("ac", joined.lower())

    def test_empty_raw_text_falls_back_to_lines(self):
        sec = _section("", [_ev("C4")])
        sec["lyrics"]["raw_text"] = ""
        sec["lyrics"]["lines"] = ["fallback line"]
        alignment = align_section(sec)
        self.assertGreater(len(alignment["syllables"]), 0)


# ===========================================================================
# 29. Practice Key independence
# ===========================================================================

class TestPracticeKeyIndependence(unittest.TestCase):
    def test_transposition_does_not_change_alignment(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        alignment_c = align_lyrics_to_melody("one two three", events)
        events_bb = [_ev("D4"), _ev("E4"), _ev("F#4")]
        alignment_bb = align_lyrics_to_melody("one two three", events_bb)
        assigns_c = [(a["syllable_index"], a["type"]) for a in alignment_c["event_assignments"]]
        assigns_bb = [(a["syllable_index"], a["type"]) for a in alignment_bb["event_assignments"]]
        self.assertEqual(assigns_c, assigns_bb)


# ===========================================================================
# 30. Instrument independence
# ===========================================================================

class TestInstrumentIndependence(unittest.TestCase):
    def test_same_syllable_mapping_regardless_of_pitch(self):
        events_piano = [_ev("C4"), _ev("D4")]
        events_tenor_sax = [_ev("D4"), _ev("E4")]
        a1 = align_lyrics_to_melody("la la", events_piano)
        a2 = align_lyrics_to_melody("la la", events_tenor_sax)
        types1 = [(a["syllable_index"], a["type"]) for a in a1["event_assignments"]]
        types2 = [(a["syllable_index"], a["type"]) for a in a2["event_assignments"]]
        self.assertEqual(types1, types2)


# ===========================================================================
# 31. No mutation of authoritative melody
# ===========================================================================

class TestNoMelodyMutation(unittest.TestCase):
    def test_alignment_does_not_modify_events(self):
        events = [_ev("C4", 1.0, 0, 1), _ev("D4", 2.0, 1, 1)]
        original = copy.deepcopy(events)
        align_lyrics_to_melody("one two", events)
        self.assertEqual(events, original)

    def test_section_melody_unchanged(self):
        sec = _section("hello world", [_ev("C4"), _ev("D4")])
        original_melody = copy.deepcopy(sec["melody"])
        align_section(sec)
        self.assertEqual(sec["melody"], original_melody)


# ===========================================================================
# 32. No mutation of authoritative lyrics
# ===========================================================================

class TestNoLyricsMutation(unittest.TestCase):
    def test_alignment_does_not_modify_raw_text(self):
        sec = _section("hello world", [_ev("C4"), _ev("D4")])
        original_text = sec["lyrics"]["raw_text"]
        align_section(sec)
        self.assertEqual(sec["lyrics"]["raw_text"], original_text)

    def test_syllables_are_read_only_copy(self):
        events = [_ev("C4")]
        alignment = align_lyrics_to_melody("hello", events)
        alignment["syllables"][0]["text"] = "MODIFIED"
        fresh = align_lyrics_to_melody("hello", events)
        self.assertNotEqual(fresh["syllables"][0]["text"], "MODIFIED")


# ===========================================================================
# 33. Compatibility with existing ABC generation
# ===========================================================================

class TestABCCompatibility(unittest.TestCase):
    def test_build_abc_with_lyrics_adds_w_line(self):
        events = [_ev("C4", 1.0), _ev("D4", 1.0)]
        alignment = align_lyrics_to_melody("one two", events)
        abc = "X:1\nT:Test\nM:4/4\nL:1/8\nQ:1/4=120\nK:C\nCD |"
        result = build_abc_with_lyrics(abc, alignment, events)
        self.assertIn("w:", result)
        self.assertIn("one", result)
        self.assertIn("two", result)

    def test_unaligned_leaves_abc_unchanged(self):
        abc = "X:1\nT:Test\nK:C\nCDE |"
        result = build_abc_with_lyrics(abc, empty_alignment(), [])
        self.assertEqual(result, abc)

    def test_w_line_format(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        w_line = alignment_to_abc_w_lines(alignment, events)
        self.assertTrue(w_line.startswith("w: "))

    def test_abc_not_modified_without_alignment(self):
        events = [_ev("C4")]
        alignment = {"status": "unaligned"}
        abc = "X:1\nK:C\nC |"
        result = build_abc_with_lyrics(abc, alignment, events)
        self.assertEqual(result, abc)


# ===========================================================================
# 34. Existing composition schema backward compatibility
# ===========================================================================

class TestBackwardCompatibility(unittest.TestCase):
    def test_section_without_alignment_is_compatible(self):
        sec = {"id": "s1", "label": "Verse", "melody": {"events": []}, "lyrics": {"raw_text": ""}}
        self.assertTrue(section_alignment_is_compatible(sec))

    def test_get_alignment_on_old_section(self):
        sec = {"id": "s1", "label": "Verse"}
        alignment = get_alignment(sec)
        self.assertEqual(alignment["status"], "unaligned")
        self.assertNotIn("lyrics_alignment", sec)

    def test_old_section_can_be_aligned(self):
        sec = {"id": "s1", "label": "Verse",
               "melody": {"events": [_ev("C4")], "intent": {}, "phrases": []},
               "lyrics": {"raw_text": "hello", "lines": ["hello"], "intent": {}}}
        alignment = align_section(sec)
        self.assertEqual(alignment["status"], "provisional")

    def test_alignment_key_not_required_for_section(self):
        sec = {"id": "s1", "melody": {"events": [_ev("C4")]},
               "lyrics": {"raw_text": "hi"}}
        alignment = align_section(sec)
        self.assertIn("lyrics_alignment", sec)


# ===========================================================================
# Additional edge cases
# ===========================================================================

class TestAlignmentStatusValues(unittest.TestCase):
    def test_all_statuses_defined(self):
        self.assertEqual(set(ALIGNMENT_STATUSES),
                         {"unaligned", "provisional", "confirmed", "stale"})


class TestABCWLineWithRests(unittest.TestCase):
    def test_rests_omitted_from_w_line(self):
        events = [_ev("C4"), _rest(), _ev("D4")]
        alignment = align_lyrics_to_melody("one two", events)
        w_line = alignment_to_abc_w_lines(alignment, events)
        tokens = w_line.replace("w: ", "").split()
        non_bar = [t for t in tokens if t != "|"]
        self.assertEqual(len(non_bar), 2)

    def test_multiple_rests(self):
        events = [_rest(), _rest(), _ev("C4")]
        alignment = align_lyrics_to_melody("word", events)
        w_line = alignment_to_abc_w_lines(alignment, events)
        self.assertIn("word", w_line)


class TestMultisyllableABCHyphen(unittest.TestCase):
    def test_hyphen_between_syllables(self):
        events = [_ev("C4"), _ev("D4")]
        alignment = align_lyrics_to_melody("hello", events)
        syls = alignment["syllables"]
        if len(syls) >= 2:
            w_line = alignment_to_abc_w_lines(alignment, events)
            self.assertIn("-", w_line)


class TestEmptyAlignmentDefaults(unittest.TestCase):
    def test_empty_has_all_keys(self):
        a = empty_alignment()
        expected_keys = {"status", "syllables", "event_assignments",
                         "melody_fingerprint", "lyrics_fingerprint",
                         "confirmed_at", "confirmed_melody_fingerprint",
                         "confirmed_lyrics_fingerprint", "warnings"}
        self.assertEqual(set(a.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
