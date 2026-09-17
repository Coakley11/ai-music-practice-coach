"""AI melody suggestions: event-grounded descriptions + intent-driven events."""

from __future__ import annotations

import unittest

from composition_chord_repeats import accept_full_progression
from composition_document import (
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_melody_suggestions import (
    describe_melody_from_events,
    suggest_melody_concepts,
)
from composition_melody_shape import events_signature


class TestMelodyIntentDescriptions(unittest.TestCase):
    def _section(self, chords: str = "Am C G F Am C G7b5/A Bb"):
        doc = bootstrap_from_vision(genre="Pop", song_idea="hook song", key="Am", bpm=96, meter="4/4")
        apply_structure_template(doc, "simple")
        sec = ordered_sections(doc)[0]
        accept_full_progression(doc, str(sec["id"]), parse_chord_paste(chords), tiled=False)
        return doc, sec

    def test_description_matches_opening_interval(self) -> None:
        events = [
            {"pitch": "A3", "midi": 57, "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 2.0},
        ]
        desc = describe_melody_from_events(events)
        self.assertIn("7-semitone leap", desc)
        self.assertIn("A3", desc)
        self.assertIn("E4", desc)
        self.assertNotIn("octave leap", desc.lower())

    def test_high_point_and_held_note_claims(self) -> None:
        events = [
            {"pitch": "A3", "midi": 57, "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "G4", "midi": 67, "duration_beats": 1.0, "beat": 2.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 3.0, "beat": 3.0},
        ]
        desc = describe_melody_from_events(events)
        self.assertIn("G4", desc)  # high point
        self.assertIn("3 beats", desc)  # held closing note

    def test_repeated_motif_claim(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 0.5, "beat": 0.0},
            {"pitch": "D4", "midi": 62, "duration_beats": 0.5, "beat": 0.5},
            {"pitch": "E4", "midi": 64, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "C4", "midi": 60, "duration_beats": 0.5, "beat": 2.0},
            {"pitch": "D4", "midi": 62, "duration_beats": 0.5, "beat": 2.5},
            {"pitch": "A3", "midi": 57, "duration_beats": 1.0, "beat": 3.0},
        ]
        desc = describe_melody_from_events(events)
        self.assertIn("repeats a short", desc)
        self.assertIn("C4", desc)

    def test_suggestions_receive_all_intent_fields(self) -> None:
        doc, sec = self._section()
        concepts = suggest_melody_concepts(
            doc,
            sec,
            "energetic",
            "expressive",
            limit=3,
            remember="A rising hook that peaks near the end.",
            notes="Start fairly low, repeat a short motif, leave a little space in the middle, and hold the final note.",
        )
        self.assertEqual(len(concepts), 3)
        for c in concepts:
            self.assertEqual(c.get("feel"), "energetic")
            self.assertEqual(c.get("style"), "expressive")
            self.assertIn("rising hook", str(c.get("remember") or ""))
            self.assertIn("Start fairly low", str(c.get("notes_intent") or ""))
            self.assertEqual(c.get("chord_span"), 8)
            self.assertTrue(c.get("events"))

    def test_descriptions_are_unique_and_event_grounded(self) -> None:
        doc, sec = self._section()
        concepts = suggest_melody_concepts(
            doc,
            sec,
            "energetic",
            "simple",
            limit=3,
            remember="A rising hook that peaks near the end.",
            notes="Start fairly low and hold the final note.",
        )
        descs = [str(c.get("contour") or "") for c in concepts]
        self.assertEqual(len(descs), len(set(descs)), descs)
        for c in concepts:
            desc = str(c.get("contour") or "")
            self.assertEqual(desc, str(c.get("why") or ""))
            # No canned library prose
            self.assertNotIn("Strategic leaps make a chorus", desc)
            self.assertNotIn("Open with a confident interval jump", desc)
            events = list(c.get("events") or [])
            midis = [int(e.get("midi") or 60) for e in events if not e.get("is_rest")]
            peak = max(range(len(midis)), key=lambda i: midis[i])
            peak_pitch = str(events[[i for i, e in enumerate(events) if not e.get("is_rest")][peak]].get("pitch"))
            if "high point on" in desc:
                claimed = desc.split("high point on", 1)[1].split()[0].rstrip(".,;")
                self.assertEqual(claimed, peak_pitch)

    def test_intent_changes_events(self) -> None:
        doc, sec = self._section()
        a = suggest_melody_concepts(doc, sec, "smooth", "simple", limit=1, remember="", notes="")[0]
        b = suggest_melody_concepts(
            doc,
            sec,
            "energetic",
            "expressive",
            limit=1,
            remember="A rising hook that peaks near the end.",
            notes="Start fairly low, hold the final note.",
        )[0]
        self.assertNotEqual(events_signature(a["events"]), events_signature(b["events"]))

    def test_style_changes_events(self) -> None:
        doc, sec = self._section()
        a = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=1, remember="hook", notes="")[0]
        b = suggest_melody_concepts(doc, sec, "lyrical", "expressive", limit=1, remember="hook", notes="")[0]
        self.assertNotEqual(events_signature(a["events"]), events_signature(b["events"]))

    def test_suggestions_differ_from_each_other(self) -> None:
        doc, sec = self._section()
        concepts = suggest_melody_concepts(
            doc,
            sec,
            "bold",
            "simple",
            limit=3,
            remember="memorable opening phrase",
            notes="Keep the range comfortable.",
        )
        sigs = [events_signature(c["events"]) for c in concepts]
        self.assertEqual(len(sigs), len(set(sigs)))


if __name__ == "__main__":
    unittest.main()
