"""Editing a RECORDED melody in the Advanced Phrase Editor.

The editor itself is the one the AI suggestions use; what a recording adds is a second place
to go back to. "Reset proposal" returns to the accepted melody, which after a few edits is no
longer what the musician played. These pin the state the editor's "Restore original
transcription" depends on, and that the recorded audio is never part of that state.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from composition_melody_engine import build_concept_events
from composition_melody_improve import (
    improve_undo_key,
    original_take_key,
    preserve_original_take,
    push_improve_undo,
    restore_original_take,
)
from composition_melody_shape import (
    MELODY_REFINEMENTS,
    propose_melody_refinement,
    timeline_span,
)

CHORDS = ["D", "Bm", "G", "A", "D", "Bm", "G", "A"]
SECTION = "sec-verse-1"
AUDIO_KEY = f"composer_hum_audio_{SECTION}"
TAKE_BYTES = b"RIFF....fake wav bytes, not melody events...."


def transcribed() -> list[dict]:
    """Stand-in for what a take transcribes to: a real generated line over the section."""
    return build_concept_events("direct_line", CHORDS, key="D", meter="4/4")


class TestTheOriginalTranscriptionIsKept(unittest.TestCase):
    def test_it_is_written_once_and_later_accepts_do_not_replace_it(self) -> None:
        """A second Use this melody must not redefine what "original" means."""
        ss: dict = {}
        first = transcribed()
        preserve_original_take(ss, SECTION, first)
        later = propose_melody_refinement(first, "simplify", key="D")["events"]
        preserve_original_take(ss, SECTION, later)
        self.assertEqual(restore_original_take(ss, SECTION), first)

    def test_restoring_hands_back_a_copy_not_the_stored_list(self) -> None:
        """An edit to the restored draft must not rewrite the stored original."""
        ss: dict = {}
        preserve_original_take(ss, SECTION, transcribed())
        got = restore_original_take(ss, SECTION)
        got[0]["midi"] = 1
        got[0]["pitch"] = "C-1"
        again = restore_original_take(ss, SECTION)
        self.assertNotEqual(again[0]["pitch"], "C-1")

    def test_nothing_to_restore_before_a_take_is_accepted(self) -> None:
        """The editor must not offer the button for a purely generated melody."""
        self.assertIsNone(restore_original_take({}, SECTION))

    def test_every_refinement_leaves_the_original_reachable(self) -> None:
        ss: dict = {}
        original = transcribed()
        preserve_original_take(ss, SECTION, original)
        draft = list(original)
        for rid, _label, _why in MELODY_REFINEMENTS:
            out = propose_melody_refinement(draft, rid, key="D").get("events")
            if out:
                draft = out
            with self.subTest(refinement=rid):
                self.assertEqual(restore_original_take(ss, SECTION), original)

    def test_the_restored_transcription_still_covers_the_section(self) -> None:
        """Going back must not go back to a melody that stops before the last chord."""
        ss: dict = {}
        preserve_original_take(ss, SECTION, transcribed())
        self.assertAlmostEqual(
            timeline_span(restore_original_take(ss, SECTION)), 32.0, places=2
        )


class TestTheRecordingIsNotPartOfTheEditedState(unittest.TestCase):
    """The audio is the musician's performance; edits are notes. They never mix."""

    def test_the_audio_lives_under_its_own_key(self) -> None:
        self.assertNotEqual(AUDIO_KEY, original_take_key(SECTION))

    def test_preserving_and_restoring_leaves_the_audio_untouched(self) -> None:
        ss: dict = {AUDIO_KEY: TAKE_BYTES}
        preserve_original_take(ss, SECTION, transcribed())
        restore_original_take(ss, SECTION)
        self.assertEqual(ss[AUDIO_KEY], TAKE_BYTES)

    def test_the_stored_original_holds_notes_and_not_audio(self) -> None:
        ss: dict = {}
        preserve_original_take(ss, SECTION, transcribed())
        stored = ss[original_take_key(SECTION)]
        self.assertTrue(all(isinstance(row, dict) for row in stored))
        self.assertTrue(all("midi" in row or row.get("is_rest") for row in stored))


class TestRestoreIsUndoable(unittest.TestCase):
    def test_the_pre_restore_draft_goes_on_the_undo_stack(self) -> None:
        """Restoring is itself an edit, so Undo has to be able to take it back."""
        ss: dict = {}
        original = transcribed()
        preserve_original_take(ss, SECTION, original)
        edited = propose_melody_refinement(original, "simplify", key="D")["events"]
        push_improve_undo(ss, SECTION, edited)
        stack = ss[improve_undo_key(SECTION)]
        self.assertEqual(stack[-1], edited)
        self.assertNotEqual(stack[-1], original)


if __name__ == "__main__":
    unittest.main()
