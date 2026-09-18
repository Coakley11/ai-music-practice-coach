"""UX + whole-song validation for style-aware Composition generation."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from composition_chord_repeats import accept_full_progression
from composition_chord_suggestions import suggest_progressions
from composition_document import (
    COMPOSITION_GENRES,
    COMPOSITION_JEWISH_DIRECTIONS,
    apply_structure_template,
    bootstrap_from_vision,
    coerce_jewish_direction,
    ordered_sections,
    parse_chord_paste,
)
from composition_melody_suggestions import suggest_melody_concepts
from composition_melody_shape import events_signature
from composition_song_intent import (
    build_song_intent_profile,
    normalize_style_family,
)


def _sig(idea: dict) -> tuple[str, ...]:
    return tuple(
        str(c.get("chord") or "")
        for c in (idea.get("chords") or [])
        if isinstance(c, dict) and str(c.get("chord") or "").strip()
    )


class TestBossaGenre(unittest.TestCase):
    def test_bossa_in_composition_genres(self) -> None:
        self.assertIn("Bossa", COMPOSITION_GENRES)

    def test_bossa_persists_on_document(self) -> None:
        doc = bootstrap_from_vision(
            genre="Bossa",
            song_idea="intimate love song",
            energy="Ballad — slow and intimate",
            references="piano-focused singer-songwriter",
            key="C",
            bpm=88,
            meter="4/4",
        )
        self.assertEqual(doc["metadata"]["style"], "Bossa")
        self.assertEqual(doc["global"]["progression_style"], "Bossa")
        profile = build_song_intent_profile(doc, None)
        self.assertEqual(profile["style_family"], "bossa")
        self.assertEqual(profile["song_style_family"], "bossa")
        # Reload-shaped copy reconstructs the same family
        reloaded = copy.deepcopy(doc)
        self.assertEqual(build_song_intent_profile(reloaded)["style_family"], "bossa")

    def test_bossa_combines_with_intimate_and_reference(self) -> None:
        doc = bootstrap_from_vision(
            genre="Bossa",
            song_idea="love song",
            energy="Ballad — slow and intimate",
            references="piano ballad",
            key="C",
            bpm=80,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        profile = build_song_intent_profile(doc, chorus)
        self.assertEqual(profile["style_family"], "bossa")
        self.assertTrue(profile["flags"]["love"] or profile["flags"]["intimate"] or profile["flags"]["ballad"])
        self.assertTrue(profile["reference_attrs"]["piano_driven"] or profile["flags"]["piano"])
        ideas = suggest_progressions(doc, chorus, "reflective", limit=3)
        flat = {c for i in ideas for c in _sig(i)}
        self.assertTrue(any(("maj7" in c or "m7" in c or "6" in c or "9" in c) for c in flat), flat)


class TestJewishDirection(unittest.TestCase):
    def test_direction_options_exist(self) -> None:
        self.assertIn("Contemporary Jewish pop", COMPOSITION_JEWISH_DIRECTIONS)
        self.assertIn("Klezmer-influenced", COMPOSITION_JEWISH_DIRECTIONS)
        self.assertIn("Let my description decide", COMPOSITION_JEWISH_DIRECTIONS)

    def test_direction_persists_and_changes_family(self) -> None:
        doc_pop = bootstrap_from_vision(
            genre="Jewish",
            song_idea="camp song",
            jewish_direction="Contemporary Jewish pop",
            key="C",
            bpm=110,
            meter="4/4",
        )
        doc_kl = bootstrap_from_vision(
            genre="Jewish",
            song_idea="dance",
            jewish_direction="Klezmer-influenced",
            key="C",
            bpm=120,
            meter="4/4",
        )
        self.assertEqual(doc_pop["metadata"]["jewish_direction"], "Contemporary Jewish pop")
        self.assertEqual(doc_kl["metadata"]["jewish_direction"], "Klezmer-influenced")
        pp = build_song_intent_profile(doc_pop)
        pk = build_song_intent_profile(doc_kl)
        self.assertEqual(pp["style_family"], "jewish_pop")
        self.assertEqual(pk["style_family"], "jewish_klezmer")
        self.assertEqual(pp["jewish_direction"], "Contemporary Jewish pop")

    def test_stale_direction_ignored_for_non_jewish(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="uplifting",
            key="C",
            bpm=110,
            meter="4/4",
        )
        doc["metadata"]["jewish_direction"] = "Klezmer-influenced"
        profile = build_song_intent_profile(doc)
        self.assertEqual(profile["style_family"], "pop")
        self.assertEqual(profile["jewish_direction"], "")
        self.assertEqual(
            normalize_style_family("Pop", jewish_direction="Klezmer-influenced"),
            "pop",
        )

    def test_freeform_can_nudge_section_within_jewish(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jewish",
            song_idea="contemporary Jewish pop",
            jewish_direction="Contemporary Jewish pop",
            key="C",
            bpm=110,
            meter="4/4",
        )
        apply_structure_template(doc, "pop")
        bridge = next(s for s in ordered_sections(doc) if s.get("label") == "Bridge")
        song_p = build_song_intent_profile(doc, bridge)
        self.assertEqual(song_p["song_style_family"], "jewish_pop")
        nudged = build_song_intent_profile(
            doc,
            bridge,
            melody_notes="I want the bridge to briefly feel more traditional and modal.",
        )
        self.assertEqual(nudged["song_style_family"], "jewish_pop")
        self.assertEqual(nudged["style_family"], "jewish_modal")

    def test_jewish_substyles_alter_harmony_and_melody(self) -> None:
        doc_a = bootstrap_from_vision(
            genre="Jewish",
            song_idea="pop",
            jewish_direction="Contemporary Jewish pop",
            key="C",
            bpm=110,
            meter="4/4",
        )
        doc_b = bootstrap_from_vision(
            genre="Jewish",
            song_idea="klezmer",
            jewish_direction="Klezmer-influenced",
            key="C",
            bpm=110,
            meter="4/4",
        )
        apply_structure_template(doc_a, "simple")
        apply_structure_template(doc_b, "simple")
        ca = next(s for s in ordered_sections(doc_a) if s.get("label") == "Chorus")
        cb = next(s for s in ordered_sections(doc_b) if s.get("label") == "Chorus")
        ha = {_sig(i) for i in suggest_progressions(doc_a, ca, "uplifting", limit=3)}
        hb = {_sig(i) for i in suggest_progressions(doc_b, cb, "uplifting", limit=3)}
        self.assertNotEqual(ha, hb)
        accept_full_progression(doc_a, str(ca["id"]), parse_chord_paste("C G Am F"), tiled=False)
        accept_full_progression(doc_b, str(cb["id"]), parse_chord_paste("Am Bb E Am"), tiled=False)
        ma = {events_signature(c["events"]) for c in suggest_melody_concepts(doc_a, ca, "lyrical", "simple", limit=3)}
        mb = {events_signature(c["events"]) for c in suggest_melody_concepts(doc_b, cb, "lyrical", "simple", limit=3)}
        self.assertNotEqual(ma, mb)


class TestWholeSongCoherence(unittest.TestCase):
    def test_song_wide_profile_stable_across_sections(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="medium-energy romantic piano song",
            references="Bill Evans",
            energy="Mid-tempo — steady groove",
            key="C",
            bpm=110,
            meter="4/4",
        )
        apply_structure_template(doc, "pop")
        families = set()
        goals = {}
        for sec in ordered_sections(doc):
            label = str(sec.get("label") or "")
            if label not in {"Verse", "Pre-Chorus", "Chorus", "Bridge"}:
                continue
            p = build_song_intent_profile(doc, sec)
            families.add(p["song_style_family"])
            goals[label] = p["section_goal"]
            self.assertEqual(p["style_family"], "jazz")
        self.assertEqual(families, {"jazz"})
        self.assertEqual(goals.get("Verse"), "story")
        self.assertEqual(goals.get("Pre-Chorus"), "build")
        self.assertEqual(goals.get("Chorus"), "hook_peak")
        self.assertEqual(goals.get("Bridge"), "contrast")

    def test_section_role_alters_harmony_within_style(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="uplifting song that starts restrained and builds",
            key="C",
            bpm=110,
            meter="4/4",
        )
        apply_structure_template(doc, "pop")
        primaries = {}
        by_label: dict[str, set] = {}
        for sec in ordered_sections(doc):
            label = str(sec.get("label") or "")
            if label not in {"Verse", "Pre-Chorus", "Chorus", "Bridge"}:
                continue
            feeling = {
                "Verse": "reflective",
                "Pre-Chorus": "tense",
                "Chorus": "uplifting",
                "Bridge": "tense",
            }[label]
            ideas = suggest_progressions(doc, sec, feeling, limit=3)
            by_label[label] = {_sig(i) for i in ideas}
            primaries[label] = _sig(ideas[0]) if ideas else ()
            # All suggestions share jazz family
            self.assertTrue(all(i.get("style_family") == "jazz" for i in ideas))
            # Three candidates distinct
            self.assertEqual(len(by_label[label]), len(ideas))
        self.assertNotEqual(primaries["Verse"], primaries["Chorus"])
        self.assertNotEqual(primaries["Chorus"], primaries["Bridge"])
        self.assertNotEqual(by_label["Verse"], by_label["Chorus"])

    def test_prior_section_informs_later_suggestions(self) -> None:
        doc = bootstrap_from_vision(
            genre="Pop",
            song_idea="uplifting song that starts restrained and builds",
            key="C",
            bpm=110,
            meter="4/4",
        )
        apply_structure_template(doc, "pop")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("C Am F G"), tiled=False)
        ideas = suggest_progressions(doc, chorus, "uplifting", limit=3)
        # Continuity card should appear when prior harmony exists
        contexts = [str(i.get("context") or "") for i in ideas]
        self.assertTrue("neighbor" in contexts or any("Lift" in str(i.get("name") or "") for i in ideas), ideas)

    def test_section_role_alters_melody_within_style(self) -> None:
        doc = bootstrap_from_vision(
            genre="Rock",
            song_idea="celebratory anthem",
            energy="Driving — high energy",
            key="C",
            bpm=128,
            meter="4/4",
        )
        apply_structure_template(doc, "simple")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        accept_full_progression(doc, str(verse["id"]), parse_chord_paste("C F C G"), tiled=False)
        accept_full_progression(doc, str(chorus["id"]), parse_chord_paste("C Bb F C"), tiled=False)
        mv = suggest_melody_concepts(
            doc, verse, "lyrical", "simple", limit=3, notes="Keep it conversational."
        )
        mc = suggest_melody_concepts(
            doc, chorus, "bold", "simple", limit=3, notes="Keep the chorus easy to sing."
        )
        self.assertTrue(all(c.get("style_family") == "rock" for c in mv + mc))
        self.assertNotEqual(
            {events_signature(c["events"]) for c in mv},
            {events_signature(c["events"]) for c in mc},
        )

    def test_reference_does_not_override_genre(self) -> None:
        doc = bootstrap_from_vision(
            genre="Jazz",
            song_idea="romantic ballad",
            references="Billy Joel",
            key="C",
            bpm=96,
            meter="4/4",
        )
        profile = build_song_intent_profile(doc)
        self.assertEqual(profile["style_family"], "jazz")
        self.assertTrue(profile["reference_attrs"]["piano_driven"])

    def test_three_candidates_distinct_within_style(self) -> None:
        for genre in ("Pop", "Jazz", "Rock", "Bossa"):
            doc = bootstrap_from_vision(genre=genre, song_idea="uplifting", key="C", bpm=110, meter="4/4")
            apply_structure_template(doc, "simple")
            chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
            ideas = suggest_progressions(doc, chorus, "uplifting", limit=3)
            sigs = [_sig(i) for i in ideas]
            self.assertEqual(len(sigs), len(set(sigs)), (genre, sigs))
            for idea in ideas:
                why = str(idea.get("why") or "")
                for chord in _sig(idea)[:2]:
                    self.assertIn(chord, why)

    def test_coerce_jewish_direction(self) -> None:
        self.assertEqual(coerce_jewish_direction("Klezmer-influenced"), "Klezmer-influenced")
        self.assertEqual(coerce_jewish_direction("nope"), "Let my description decide")


if __name__ == "__main__":
    unittest.main()
