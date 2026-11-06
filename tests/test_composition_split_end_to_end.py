"""Composition split measures, end to end: edit, accept, save, reopen, transpose, play.

A split bar is one measure carrying two chords. These tests follow one through the whole Composition
pipeline - the editor draft, the saved document, the playback chord list, the melody/chord alignment
used by the score, and transposition - and check the bar still holds exactly its meter's worth of beats
with each chord sounding in its own half.
"""
import unittest

from chord_subdivisions import (
    chord_at_beat,
    chord_names_label,
    is_subdivided_bar,
    parse_subdivisions,
    split_measure_token,
)
from composition_chord_manual_editor import (
    chord_timeline,
    ensure_draft,
    split_draft_chord,
    unsplit_draft_chord,
)
from composition_chord_repeats import accept_chord_pattern
from composition_document import new_composition_document, ordered_sections, section_by_id
from composition_songs_bridge import composition_playback_sections
from custom_progression_lab import suggest_split_second_chords

SECTION_CHORDS = ["Am", "F7", "Cmaj7", "G7"]
SPLIT_AT = 1          # the F7 bar
SECOND = "B7"


def _doc_with_section():
    doc = new_composition_document(title="Split Test")
    doc.setdefault("global", {})["original_key_center"] = "C"
    doc["global"]["time_signature"] = "4/4"
    sid = str(ordered_sections(doc)[0].get("id"))
    accept_chord_pattern(doc, sid, [{"chord": c, "bars": 1} for c in SECTION_CHORDS])
    return doc, sid


def _entries(doc, sid):
    sec = section_by_id(doc, sid) or {}
    return list(sec.get("chords") or [])


def _section_chords(doc, sid):
    return [str((e or {}).get("chord") or "") for e in _entries(doc, sid)]


class TestEditingAndAccepting(unittest.TestCase):
    def test_a_split_is_saved_into_the_document(self):
        doc, sid = _doc_with_section()
        draft = ensure_draft({}, sid, _entries(doc, sid))
        split = split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=SECOND)
        self.assertTrue(accept_chord_pattern(doc, sid, split))
        saved = _section_chords(doc, sid)
        self.assertEqual(saved[SPLIT_AT], "F7:2|B7:2")
        self.assertEqual(len(saved), len(SECTION_CHORDS))          # still four bars
        self.assertEqual(saved[0], "Am")
        self.assertEqual(saved[-1], "G7")

    def test_cancelling_leaves_the_saved_document_untouched(self):
        doc, sid = _doc_with_section()
        before = _section_chords(doc, sid)
        draft = ensure_draft({}, sid, _entries(doc, sid))
        split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=SECOND)   # never accepted
        self.assertEqual(_section_chords(doc, sid), before)

    def test_unsplit_returns_the_bar_to_one_chord(self):
        doc, sid = _doc_with_section()
        draft = ensure_draft({}, sid, _entries(doc, sid))
        split = split_draft_chord(draft, SPLIT_AT, pattern="3+1", second_chord=SECOND)
        accept_chord_pattern(doc, sid, split)
        back = unsplit_draft_chord(split, SPLIT_AT)
        accept_chord_pattern(doc, sid, back)
        self.assertEqual(_section_chords(doc, sid)[SPLIT_AT], "F7")

    def test_an_unsaved_draft_for_another_section_is_not_disturbed(self):
        doc, sid = _doc_with_section()
        session = {}
        other = ensure_draft(session, "other-section", [{"chord": "Dm7", "bars": 2}])
        draft = ensure_draft(session, sid, _entries(doc, sid))
        accept_chord_pattern(doc, sid, split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=SECOND))
        self.assertEqual(other, [{"chord": "Dm7", "bars": 2}])


class TestBeatsAndPositions(unittest.TestCase):
    def test_the_bar_still_holds_exactly_four_beats(self):
        for pattern in ("2+2", "3+1", "1+3", "push", "4x1"):
            with self.subTest(pattern=pattern):
                token = split_measure_token(pattern, "F7", SECOND)
                total = sum(s.weight for s in parse_subdivisions(token, beats_per_bar=4))
                self.assertAlmostEqual(total, 4.0, places=6)

    def test_each_chord_sounds_in_its_own_part_of_the_bar(self):
        halves = split_measure_token("2+2", "F7", SECOND)
        self.assertEqual(chord_at_beat(halves, 0.0, beats_per_bar=4), "F7")
        self.assertEqual(chord_at_beat(halves, 1.9, beats_per_bar=4), "F7")
        self.assertEqual(chord_at_beat(halves, 2.0, beats_per_bar=4), SECOND)
        self.assertEqual(chord_at_beat(halves, 3.9, beats_per_bar=4), SECOND)

        three_one = split_measure_token("3+1", "F7", SECOND)
        self.assertEqual(chord_at_beat(three_one, 2.9, beats_per_bar=4), "F7")
        self.assertEqual(chord_at_beat(three_one, 3.0, beats_per_bar=4), SECOND)

    def test_the_editor_timeline_keeps_the_later_bars_in_place(self):
        doc, sid = _doc_with_section()
        draft = ensure_draft({}, sid, _entries(doc, sid))
        split = split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=SECOND)
        rows = chord_timeline(split, meter="4/4")
        self.assertEqual([r["measure"] for r in rows], [1, 2, 3, 4])
        self.assertEqual(rows[SPLIT_AT]["chord"], "F7:2|B7:2")
        self.assertEqual(rows[-1]["chord"], "G7")

    def test_the_label_shows_both_chords(self):
        label = chord_names_label(split_measure_token("2+2", "F7", SECOND))
        self.assertIn("F7", label)
        self.assertIn(SECOND, label)


class TestPlaybackAndTransposition(unittest.TestCase):
    def _split_doc(self):
        doc, sid = _doc_with_section()
        draft = ensure_draft({}, sid, _entries(doc, sid))
        accept_chord_pattern(doc, sid, split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=SECOND))
        return doc, sid

    def test_the_playback_progression_carries_the_split_bar(self):
        doc, _sid = self._split_doc()
        played = composition_playback_sections(doc, "C")
        flat = [c for chords in played.values() for c in chords]
        self.assertTrue(any(is_subdivided_bar(c) for c in flat), flat)
        split = next(c for c in flat if is_subdivided_bar(c))
        parts = [s.chord for s in parse_subdivisions(split, beats_per_bar=4)]
        self.assertEqual(parts, ["F7", SECOND])

    def test_transposing_moves_both_chords_of_the_bar_together(self):
        doc, _sid = self._split_doc()
        played = composition_playback_sections(doc, "D")        # up a tone
        flat = [c for chords in played.values() for c in chords]
        split = next(c for c in flat if is_subdivided_bar(c))
        parts = [s.chord for s in parse_subdivisions(split, beats_per_bar=4)]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts, ["G7", "C#7"])
        weights = [s.weight for s in parse_subdivisions(split, beats_per_bar=4)]
        self.assertEqual(weights, [2.0, 2.0])                   # the division is preserved

    def test_reopening_the_saved_document_still_has_the_split(self):
        import copy

        doc, sid = self._split_doc()
        reopened = copy.deepcopy(doc)                           # a save/load round trip is a deep copy
        self.assertEqual(_section_chords(reopened, sid)[SPLIT_AT], "F7:2|B7:2")
        played = composition_playback_sections(reopened, "C")
        flat = [c for chords in played.values() for c in chords]
        self.assertTrue(any(is_subdivided_bar(c) for c in flat))


class TestMelodyAlignment(unittest.TestCase):
    def test_the_score_places_the_second_chord_at_its_own_beat(self):
        from composition_melody_notation import _chord_onset_beats

        positions = _chord_onset_beats(["Am", split_measure_token("2+2", "F7", SECOND)], meter="4/4")
        beats = {round(float(b), 3): c for b, c in positions}
        self.assertEqual(beats.get(0.0), "Am")
        self.assertEqual(beats.get(4.0), "F7")
        self.assertEqual(beats.get(6.0), SECOND)               # halfway through the second bar


class TestSuggestionsExplainThemselves(unittest.TestCase):
    def test_the_suggestions_for_this_spot_are_ranked_and_reasoned(self):
        out = suggest_split_second_chords(
            current_chord="F7", next_chord="Cmaj7", prev_chord="Am", home_key="C", style="Jazz"
        )
        self.assertTrue(out)
        for chord, reason in out:
            self.assertTrue(chord and reason)
        self.assertIn("Cmaj7", out[0][1])                       # the best one explains the resolution

    def test_every_suggestion_can_actually_be_applied(self):
        doc, sid = _doc_with_section()
        for chord, _reason in suggest_split_second_chords(
            current_chord="F7", next_chord="Cmaj7", prev_chord="Am", home_key="C", style="Pop"
        ):
            with self.subTest(chord=chord):
                draft = ensure_draft({}, sid, _entries(doc, sid))
                split = split_draft_chord(draft, SPLIT_AT, pattern="2+2", second_chord=chord)
                token = split[SPLIT_AT]["chord"]
                self.assertTrue(is_subdivided_bar(token))
                self.assertAlmostEqual(
                    sum(s.weight for s in parse_subdivisions(token, beats_per_bar=4)), 4.0, places=6
                )


if __name__ == "__main__":
    unittest.main()
