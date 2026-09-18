"""Melody pattern repeats: expand, accept, re-tile, customize freeze."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_melody_concept,
    apply_structure_template,
    bootstrap_from_vision,
    normalize_melody_events,
    ordered_sections,
    section_by_id,
    section_melody_events,
)
from composition_melody_repeats import (
    MELODY_REPEAT_MAX,
    MELODY_REPEAT_MIN,
    accept_full_melody,
    accept_melody_pattern,
    clamp_melody_repeats,
    expand_melody_events_by_repeats,
    get_melody_pattern,
    get_melody_repeats,
    mark_melody_customized,
    melody_is_tiled,
    set_section_melody_repeats,
)


def _phrase() -> list[dict]:
    return [
        {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0},
        {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
    ]


class TestCompositionMelodyRepeats(unittest.TestCase):
    def _song(self):
        doc = bootstrap_from_vision(
            genre="Pop", song_idea="Melody repeats", key="C major", bpm=100, meter="4/4"
        )
        apply_structure_template(doc, "simple")
        return doc

    def test_clamp_bounds(self) -> None:
        self.assertEqual(MELODY_REPEAT_MIN, 1)
        self.assertEqual(MELODY_REPEAT_MAX, 4)
        self.assertEqual(clamp_melody_repeats(0), 1)
        self.assertEqual(clamp_melody_repeats(99), 4)
        self.assertEqual(clamp_melody_repeats("3"), 3)

    def test_expand_preserves_pass_and_repeat_index(self) -> None:
        out = expand_melody_events_by_repeats(_phrase(), 3)
        self.assertEqual(len(out), 6)
        self.assertEqual(out[0]["repeat_index"], 0)
        self.assertEqual(out[0]["pass_index"], 0)
        self.assertEqual(out[2]["repeat_index"], 1)
        self.assertEqual(out[2]["pass_index"], 1)
        self.assertEqual(out[4]["repeat_index"], 2)
        self.assertEqual(out[4]["pass_index"], 2)
        self.assertEqual(out[2]["beat"], 4.0)
        self.assertEqual(out[4]["beat"], 8.0)

    def test_normalize_preserves_indices(self) -> None:
        expanded = expand_melody_events_by_repeats(_phrase(), 2)
        normalized = normalize_melody_events(expanded)
        self.assertEqual(len(normalized), 4)
        self.assertEqual(normalized[0]["repeat_index"], 0)
        self.assertEqual(normalized[0]["pass_index"], 0)
        self.assertEqual(normalized[2]["repeat_index"], 1)
        self.assertEqual(normalized[2]["pass_index"], 1)

    def test_accept_melody_pattern_tiles(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        self.assertTrue(accept_melody_pattern(doc, sid, _phrase(), source_id="idea_1", repeats=2))
        sec = section_by_id(doc, sid)
        self.assertTrue(melody_is_tiled(sec))
        self.assertEqual(get_melody_repeats(sec), 2)
        events = section_melody_events(sec)
        self.assertEqual(len(events), 4)
        self.assertEqual([e["pitch"] for e in events], ["C4", "E4", "C4", "E4"])
        self.assertEqual(events[2]["repeat_index"], 1)
        self.assertEqual(events[2]["pass_index"], 1)
        pattern = get_melody_pattern(sec)
        self.assertEqual(len(pattern), 2)
        self.assertEqual(sec["melody"].get("active_source_id"), "idea_1")

    def test_set_section_melody_repeats_when_tiled(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        accept_melody_pattern(doc, sid, _phrase(), source_id="x", repeats=1)
        self.assertTrue(set_section_melody_repeats(doc, sid, 3))
        sec = section_by_id(doc, sid)
        self.assertEqual(get_melody_repeats(sec), 3)
        events = section_melody_events(sec)
        self.assertEqual(len(events), 6)
        self.assertEqual(events[4]["repeat_index"], 2)
        self.assertEqual(events[4]["pass_index"], 2)

    def test_customize_freezes_tiling(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        accept_melody_pattern(doc, sid, _phrase(), source_id="x", repeats=3)
        sec = section_by_id(doc, sid)
        events = list(section_melody_events(sec))
        events[3]["pitch"] = "G4"
        events[3]["midi"] = 67
        sec["melody"]["events"] = events
        mark_melody_customized(sec)
        self.assertFalse(melody_is_tiled(sec))
        self.assertEqual(get_melody_repeats(sec), 1)
        self.assertEqual(get_melody_pattern(sec)[3]["pitch"], "G4")
        self.assertFalse(set_section_melody_repeats(doc, sid, 4))
        self.assertEqual(section_melody_events(sec)[3]["pitch"], "G4")

    def test_accept_full_melody_untiled(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        accept_melody_pattern(doc, sid, _phrase(), repeats=2)
        full = expand_melody_events_by_repeats(_phrase(), 2)
        full[1]["pitch"] = "F4"
        self.assertTrue(accept_full_melody(doc, sid, full, source_id="edit", tiled=False))
        sec = section_by_id(doc, sid)
        self.assertFalse(melody_is_tiled(sec))
        self.assertEqual(get_melody_repeats(sec), 1)
        self.assertEqual(section_melody_events(sec)[1]["pitch"], "F4")

    def test_accept_full_melody_tiled(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        self.assertTrue(
            accept_full_melody(
                doc,
                sid,
                _phrase(),
                source_id="full",
                tiled=True,
                pattern_events=_phrase(),
                repeats=2,
            )
        )
        sec = section_by_id(doc, sid)
        self.assertTrue(melody_is_tiled(sec))
        self.assertEqual(len(section_melody_events(sec)), 4)

    def test_apply_melody_concept_sets_tiled_pattern(self) -> None:
        doc = self._song()
        sid = str(ordered_sections(doc)[0]["id"])
        concept = {
            "id": "c1",
            "name": "Hook",
            "events": _phrase(),
            "motif_hint": "up",
        }
        apply_melody_concept(doc, sid, concept)
        sec = section_by_id(doc, sid)
        self.assertTrue(melody_is_tiled(sec))
        self.assertEqual(get_melody_repeats(sec), 1)
        self.assertEqual([e["pitch"] for e in get_melody_pattern(sec)], ["C4", "E4"])
        self.assertEqual([e["pitch"] for e in section_melody_events(sec)], ["C4", "E4"])


if __name__ == "__main__":
    unittest.main()
