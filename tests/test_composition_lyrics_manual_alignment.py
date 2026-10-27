"""Tests for manual alignment editing — Slice 6B Stage 3."""
from __future__ import annotations

import copy
import json
import unittest
from typing import Any

from composition_lyrics_alignment import (
    align_lyrics_to_melody,
    alignment_to_abc_w_lines,
    clear_assignment,
    confirm_alignment,
    describe_staleness,
    get_alignment,
    merge_syllables,
    reassign_syllable,
    restore_confirmed_snapshot,
    set_alignment,
    set_melisma,
    split_syllable,
    validate_alignment_for_confirm,
)


# ---------------------------------------------------------------------------
# Helpers (same pattern as Stage 1 tests)
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


def _make_alignment(lyrics: str, events: list[dict]) -> dict[str, Any]:
    return align_lyrics_to_melody(lyrics, events)


# ===========================================================================
# 1. reassign_syllable
# ===========================================================================

class TestReassignSyllable(unittest.TestCase):
    def test_reassign_changes_assignment(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("Hel lo world", events)
        self.assertEqual(a["event_assignments"][0]["syllable_index"], 0)
        updated = reassign_syllable(a, 0, 2, events=events)
        self.assertEqual(updated["event_assignments"][0]["syllable_index"], 2)
        self.assertEqual(updated["event_assignments"][0]["type"], "syllable")

    def test_reassign_does_not_mutate_original(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        original_si = a["event_assignments"][0]["syllable_index"]
        reassign_syllable(a, 0, 1, events=events)
        self.assertEqual(a["event_assignments"][0]["syllable_index"], original_si)

    def test_reassign_to_rest_rejected(self):
        events = [_rest(), _ev("D4")]
        a = _make_alignment("word", events)
        before = copy.deepcopy(a["event_assignments"][0])
        updated = reassign_syllable(a, 0, 0, events=events)
        self.assertEqual(updated["event_assignments"][0], before)

    def test_reassign_out_of_bounds_event(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        updated = reassign_syllable(a, 5, 0, events=events)
        self.assertEqual(updated["event_assignments"], a["event_assignments"])

    def test_reassign_out_of_bounds_syllable(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        updated = reassign_syllable(a, 0, 99, events=events)
        self.assertEqual(updated["event_assignments"][0]["syllable_index"], 0)


# ===========================================================================
# 2. set_melisma
# ===========================================================================

class TestSetMelisma(unittest.TestCase):
    def test_melisma_marks_type(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("Hel lo", events)
        updated = set_melisma(a, 2, 1, events=events)
        self.assertEqual(updated["event_assignments"][2]["type"], "melisma")
        self.assertEqual(updated["event_assignments"][2]["syllable_index"], 1)

    def test_melisma_on_rest_rejected(self):
        events = [_ev("C4"), _rest()]
        a = _make_alignment("word", events)
        updated = set_melisma(a, 1, 0, events=events)
        self.assertEqual(updated["event_assignments"][1]["type"], "rest")


# ===========================================================================
# 3. clear_assignment
# ===========================================================================

class TestClearAssignment(unittest.TestCase):
    def test_clear_sets_unassigned(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        updated = clear_assignment(a, 0)
        self.assertEqual(updated["event_assignments"][0]["type"], "unassigned")
        self.assertEqual(updated["event_assignments"][0]["syllable_index"], -1)

    def test_clear_rest_unchanged(self):
        events = [_rest(), _ev("D4")]
        a = _make_alignment("word", events)
        updated = clear_assignment(a, 0)
        self.assertEqual(updated["event_assignments"][0]["type"], "rest")

    def test_clear_does_not_mutate_original(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        clear_assignment(a, 0)
        self.assertEqual(a["event_assignments"][0]["type"], "syllable")


# ===========================================================================
# 4. split_syllable
# ===========================================================================

class TestSplitSyllable(unittest.TestCase):
    def test_split_creates_two_syllables(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("world great", events)
        syl_count_before = len(a["syllables"])
        updated = split_syllable(a, 0, 3)
        self.assertEqual(len(updated["syllables"]), syl_count_before + 1)
        self.assertEqual(updated["syllables"][0]["text"], "wor")
        self.assertEqual(updated["syllables"][1]["text"], "ld")

    def test_split_shifts_assignment_indices(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("cat dog fox", events)
        si_last_before = a["event_assignments"][2]["syllable_index"]
        updated = split_syllable(a, 0, 2)
        self.assertEqual(updated["event_assignments"][2]["syllable_index"], si_last_before + 1)

    def test_split_repairs_word_metadata(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hello world", events)
        updated = split_syllable(a, 0, 3)
        left = updated["syllables"][0]
        right = updated["syllables"][1]
        self.assertEqual(left["word_index"], right["word_index"])
        self.assertFalse(left["is_word_end"])
        self.assertTrue(right["is_word_end"])
        self.assertEqual(left["position_in_word"], 0)
        self.assertEqual(right["position_in_word"], 1)

    def test_split_at_invalid_position_noop(self):
        events = [_ev("C4")]
        a = _make_alignment("Hi", events)
        updated_zero = split_syllable(a, 0, 0)
        self.assertEqual(len(updated_zero["syllables"]), len(a["syllables"]))
        updated_end = split_syllable(a, 0, 2)
        self.assertEqual(len(updated_end["syllables"]), len(a["syllables"]))

    def test_split_out_of_bounds_noop(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        updated = split_syllable(a, 99, 2)
        self.assertEqual(len(updated["syllables"]), len(a["syllables"]))


# ===========================================================================
# 5. merge_syllables
# ===========================================================================

class TestMergeSyllables(unittest.TestCase):
    def test_merge_concatenates_text(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("beautiful day", events)
        syls = a["syllables"]
        beau_idx = None
        for i, s in enumerate(syls):
            if s["text"].lower().startswith("beau"):
                beau_idx = i
                break
        if beau_idx is not None and beau_idx + 1 < len(syls):
            left_text = syls[beau_idx]["text"]
            right_text = syls[beau_idx + 1]["text"]
            if syls[beau_idx]["word_index"] == syls[beau_idx + 1]["word_index"]:
                updated = merge_syllables(a, beau_idx)
                self.assertEqual(
                    updated["syllables"][beau_idx]["text"],
                    left_text + right_text,
                )
                self.assertEqual(len(updated["syllables"]), len(syls) - 1)

    def test_merge_different_words_rejected(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("cat dog", events)
        updated = merge_syllables(a, 0)
        self.assertEqual(len(updated["syllables"]), len(a["syllables"]))

    def test_merge_shifts_assignment_indices(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4"), _ev("F4")]
        a = _make_alignment("Hel lo world foo", events)
        syls = a["syllables"]
        if len(syls) >= 2 and syls[0]["word_index"] == syls[1]["word_index"]:
            last_si = a["event_assignments"][3]["syllable_index"]
            updated = merge_syllables(a, 0)
            self.assertEqual(updated["event_assignments"][3]["syllable_index"], last_si - 1)

    def test_merge_last_syllable_noop(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        updated = merge_syllables(a, 0)
        self.assertEqual(len(updated["syllables"]), len(a["syllables"]))


# ===========================================================================
# 6. validate_alignment_for_confirm
# ===========================================================================

class TestValidateAlignmentForConfirm(unittest.TestCase):
    def test_clean_alignment_no_errors(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("Hel lo world", events)
        issues = validate_alignment_for_confirm(a, events)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(len(errors), 0)

    def test_syllable_on_rest_is_error(self):
        events = [_rest(), _ev("D4")]
        a = _make_alignment("word", events)
        a["event_assignments"][0] = {"syllable_index": 0, "type": "syllable"}
        issues = validate_alignment_for_confirm(a, events)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertTrue(any("rest" in e["message"].lower() for e in errors))

    def test_no_assignments_is_error(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hello world", events)
        for asn in a["event_assignments"]:
            asn["type"] = "unassigned"
            asn["syllable_index"] = -1
        issues = validate_alignment_for_confirm(a, events)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertTrue(any("no syllables" in e["message"].lower() for e in errors))

    def test_unassigned_pitched_notes_is_warning(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("word", events)
        a["event_assignments"][1] = {"syllable_index": -1, "type": "unassigned"}
        a["event_assignments"][2] = {"syllable_index": -1, "type": "unassigned"}
        issues = validate_alignment_for_confirm(a, events)
        warnings = [i for i in issues if i["level"] == "warning"]
        self.assertTrue(any("no syllable" in w["message"].lower() for w in warnings))

    def test_empty_assignments_is_error(self):
        a = {"event_assignments": [], "syllables": []}
        issues = validate_alignment_for_confirm(a, [])
        self.assertTrue(any(i["level"] == "error" for i in issues))


# ===========================================================================
# 7. restore_confirmed_snapshot
# ===========================================================================

class TestRestoreConfirmedSnapshot(unittest.TestCase):
    def test_restore_creates_provisional(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        confirmed = confirm_alignment(a)
        confirmed["status"] = "stale"
        restored = restore_confirmed_snapshot(confirmed)
        self.assertEqual(restored["status"], "provisional")
        self.assertEqual(len(restored["syllables"]), len(a["syllables"]))
        self.assertEqual(len(restored["event_assignments"]), len(a["event_assignments"]))

    def test_restore_preserves_snapshot(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        confirmed = confirm_alignment(a)
        confirmed["status"] = "stale"
        restored = restore_confirmed_snapshot(confirmed)
        self.assertIn("confirmed_snapshot", restored)
        self.assertIsInstance(restored["confirmed_snapshot"], dict)

    def test_restore_without_snapshot_returns_original(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        result = restore_confirmed_snapshot(a)
        self.assertEqual(result["status"], a["status"])

    def test_restore_adds_warning(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        confirmed = confirm_alignment(a)
        confirmed["status"] = "stale"
        restored = restore_confirmed_snapshot(confirmed)
        self.assertTrue(any("restored" in str(w).lower() for w in restored.get("warnings", [])))


# ===========================================================================
# 8. describe_staleness
# ===========================================================================

class TestDescribeStaleness(unittest.TestCase):
    def test_non_stale_returns_empty(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        self.assertEqual(describe_staleness(a), "")

    def test_melody_changed(self):
        a = {
            "status": "stale",
            "current_melody_fingerprint": "aaaa",
            "confirmed_melody_fingerprint": "bbbb",
            "current_lyrics_fingerprint": "cccc",
            "confirmed_lyrics_fingerprint": "cccc",
        }
        desc = describe_staleness(a)
        self.assertIn("melody", desc.lower())
        self.assertNotIn("lyrics", desc.lower())

    def test_lyrics_changed(self):
        a = {
            "status": "stale",
            "current_melody_fingerprint": "aaaa",
            "confirmed_melody_fingerprint": "aaaa",
            "current_lyrics_fingerprint": "cccc",
            "confirmed_lyrics_fingerprint": "dddd",
        }
        desc = describe_staleness(a)
        self.assertIn("lyrics", desc.lower())
        self.assertNotIn("melody", desc.lower())

    def test_both_changed(self):
        a = {
            "status": "stale",
            "current_melody_fingerprint": "aaaa",
            "confirmed_melody_fingerprint": "bbbb",
            "current_lyrics_fingerprint": "cccc",
            "confirmed_lyrics_fingerprint": "dddd",
        }
        desc = describe_staleness(a)
        self.assertIn("melody", desc.lower())
        self.assertIn("lyrics", desc.lower())

    def test_fallback_fingerprint_fields(self):
        a = {
            "status": "stale",
            "current_melody_fingerprint": "aaaa",
            "melody_fingerprint": "bbbb",
            "current_lyrics_fingerprint": "cccc",
            "lyrics_fingerprint": "cccc",
        }
        desc = describe_staleness(a)
        self.assertIn("melody", desc.lower())


# ===========================================================================
# 9. ABC rendering after manual edits
# ===========================================================================

class TestABCAfterManualEdits(unittest.TestCase):
    def test_reassigned_syllable_appears_in_abc(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("Hel lo world", events)
        updated = reassign_syllable(a, 0, 2, events=events)
        updated = reassign_syllable(updated, 2, 0, events=events)
        w_line = alignment_to_abc_w_lines(updated, events)
        self.assertTrue(len(w_line) > 0)
        self.assertIn("world", w_line)
        self.assertIn("Hel", w_line)

    def test_melisma_renders_underscore(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        a = _make_alignment("Hel lo", events)
        updated = set_melisma(a, 2, 1, events=events)
        w_line = alignment_to_abc_w_lines(updated, events)
        self.assertIn("_", w_line)

    def test_cleared_note_renders_star(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        updated = clear_assignment(a, 1)
        w_line = alignment_to_abc_w_lines(updated, events)
        self.assertIn("*", w_line)


# ===========================================================================
# 10. Confirmation flow
# ===========================================================================

class TestConfirmationFlow(unittest.TestCase):
    def test_confirm_sets_status(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        self.assertEqual(a["status"], "provisional")
        confirmed = confirm_alignment(a)
        self.assertEqual(confirmed["status"], "confirmed")

    def test_confirm_stores_snapshot(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        confirmed = confirm_alignment(a)
        snap = confirmed.get("confirmed_snapshot")
        self.assertIsInstance(snap, dict)
        self.assertEqual(len(snap["syllables"]), len(a["syllables"]))
        self.assertEqual(len(snap["event_assignments"]), len(a["event_assignments"]))

    def test_confirm_stamps_fingerprints(self):
        events = [_ev("C4")]
        a = _make_alignment("word", events)
        confirmed = confirm_alignment(a)
        self.assertTrue(confirmed.get("confirmed_melody_fingerprint"))
        self.assertTrue(confirmed.get("confirmed_lyrics_fingerprint"))


# ===========================================================================
# 11. Persistence roundtrip
# ===========================================================================

class TestPersistenceRoundtrip(unittest.TestCase):
    def test_manual_edits_survive_deepcopy(self):
        events = [_ev("C4"), _ev("D4"), _ev("E4")]
        sec = _section("Hel lo world", events)
        a = _make_alignment("Hel lo world", events)
        updated = reassign_syllable(a, 0, 2, events=events)
        set_alignment(sec, updated)
        cloned = copy.deepcopy(sec)
        cloned_a = get_alignment(cloned)
        self.assertEqual(cloned_a["event_assignments"][0]["syllable_index"], 2)

    def test_manual_edits_survive_json_roundtrip(self):
        events = [_ev("C4"), _ev("D4")]
        a = _make_alignment("Hel lo", events)
        updated = set_melisma(a, 1, 0, events=events)
        serialized = json.dumps(updated)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["event_assignments"][1]["type"], "melisma")


# ===========================================================================
# 12. Section isolation
# ===========================================================================

class TestSectionIsolation(unittest.TestCase):
    def test_editing_one_section_does_not_affect_another(self):
        events = [_ev("C4"), _ev("D4")]
        sec1 = _section("Hel lo", events)
        sec2 = _section("bye now", events)
        a1 = _make_alignment("Hel lo", events)
        a2 = _make_alignment("bye now", events)
        set_alignment(sec1, a1)
        set_alignment(sec2, a2)
        updated_a1 = clear_assignment(get_alignment(sec1), 0)
        set_alignment(sec1, updated_a1)
        a2_check = get_alignment(sec2)
        self.assertEqual(a2_check["event_assignments"][0]["type"], "syllable")


if __name__ == "__main__":
    unittest.main()
