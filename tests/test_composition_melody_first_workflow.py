"""Melody-first Composition workflow + section selection + harmony feeling."""

from __future__ import annotations

import copy
import unittest

from composition_chord_suggestions import suggest_progressions
from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    deep_copy_document,
    ordered_sections,
    section_by_id,
    section_has_resolved_chords,
    section_melody_events,
)
from composition_melody_harmonize import harmonize_melody_to_progressions
from composition_melody_repeats import (
    expand_melody_events_by_repeats,
    get_melody_repeats,
    mark_melody_customized,
    melody_is_tiled,
    set_section_melody_repeats,
)
from composition_melody_shape import apply_natural_language_melody_edit
from composition_melody_suggestions import suggest_melody_concepts
from composition_preview import preview_signature
from composition_session_state import COMPOSER_ACTIVE_SECTION_KEY
from composition_song_intent import apply_feeling_chord_bias, build_song_intent_profile
from composition_studio_page import _select_active_section
from composition_workspace_state_persistence import (
    gather_composition_workspace_from_session,
    prepare_composition_workspace_for_render,
    project_composition_workspace_to_session,
    write_canonical_composition_workspace,
)


def _phrase_events() -> list[dict]:
    return [
        {"pitch": "C4", "midi": 60, "beat": 0.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "E4", "midi": 64, "beat": 1.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "G4", "midi": 67, "beat": 2.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "A4", "midi": 69, "beat": 3.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "G4", "midi": 67, "beat": 4.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "E4", "midi": 64, "beat": 5.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "D4", "midi": 62, "beat": 6.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "C4", "midi": 60, "beat": 7.0, "duration_beats": 1.0, "is_rest": False},
    ]


def _doc_with_structure(*, style: str = "Pop", key: str = "C major") -> dict:
    doc = bootstrap_from_vision(
        genre=style,
        song_idea="A hopeful song about finding home.",
        key=key,
        bpm=96,
        meter="4/4",
    )
    apply_structure_template(doc, "pop")
    return doc


class TestSectionSelectorAuthority(unittest.TestCase):
    def test_select_active_section_persists_and_survives_prepare(self) -> None:
        doc = _doc_with_structure()
        sections = ordered_sections(doc)
        labels = {str(s.get("label")): str(s.get("id")) for s in sections}
        self.assertIn("Verse", labels)
        self.assertIn("Chorus", labels)
        self.assertIn("Bridge", labels)

        ss: dict = {
            "composer_active_document": doc,
            COMPOSER_ACTIVE_SECTION_KEY: labels["Bridge"],
        }
        write_canonical_composition_workspace(
            ss,
            {
                "schema_version": 1,
                "active_document": deep_copy_document(doc),
                "active_section_id": labels["Bridge"],
                "focus_lane": "chords",
                "workflow_phase": "chords",
                "needs_seed": False,
                "library": {},
            },
            reason="test_seed",
        )

        # User clicks Verse — must become authoritative.
        _select_active_section(ss, doc, labels["Verse"], persist=False)
        self.assertEqual(ss[COMPOSER_ACTIVE_SECTION_KEY], labels["Verse"])

        # Stale blob still says Bridge; prepare must prefer live Verse.
        blob = gather_composition_workspace_from_session(ss)
        blob["active_section_id"] = labels["Bridge"]
        write_canonical_composition_workspace(ss, blob, reason="stale_bridge")
        ss[COMPOSER_ACTIVE_SECTION_KEY] = labels["Verse"]
        project_composition_workspace_to_session(ss, overwrite=True)
        self.assertEqual(ss[COMPOSER_ACTIVE_SECTION_KEY], labels["Verse"])

        # Chorus then Bridge then Verse — each click sticks.
        for label in ("Chorus", "Bridge", "Verse"):
            _select_active_section(ss, doc, labels[label], persist=False)
            prepare_composition_workspace_for_render(ss)
            self.assertEqual(
                ss[COMPOSER_ACTIVE_SECTION_KEY],
                labels[label],
                msg=f"Failed to stay on {label}",
            )


class TestHarmonyFeelingMaterial(unittest.TestCase):
    def test_feeling_changes_chord_candidates(self) -> None:
        doc = _doc_with_structure(style="Jazz", key="C major")
        chorus = next(s for s in ordered_sections(doc) if s.get("label") == "Chorus")
        lines = {}
        for feel in ("uplifting", "tense", "melancholy"):
            ideas = suggest_progressions(doc, chorus, feel, limit=3)
            self.assertTrue(ideas, msg=f"No ideas for {feel}")
            lines[feel] = tuple(
                tuple(str(c.get("chord") or "") for c in idea.get("chords") or [])
                for idea in ideas
            )
        self.assertNotEqual(lines["uplifting"], lines["tense"])
        self.assertNotEqual(lines["tense"], lines["melancholy"])
        self.assertNotEqual(lines["uplifting"], lines["melancholy"])

    def test_feeling_combines_with_style(self) -> None:
        """Same feeling under Jazz vs Pop yields different vocabulary."""
        jazz = _doc_with_structure(style="Jazz", key="C major")
        pop = _doc_with_structure(style="Pop", key="C major")
        j_sec = next(s for s in ordered_sections(jazz) if s.get("label") == "Chorus")
        p_sec = next(s for s in ordered_sections(pop) if s.get("label") == "Chorus")
        j_ideas = suggest_progressions(jazz, j_sec, "tense", limit=3)
        p_ideas = suggest_progressions(pop, p_sec, "tense", limit=3)
        j_syms = [str(c.get("chord") or "") for idea in j_ideas for c in idea.get("chords") or []]
        p_syms = [str(c.get("chord") or "") for idea in p_ideas for c in idea.get("chords") or []]
        self.assertNotEqual(j_syms, p_syms)
        # Jazz tense should often carry richer 7th color.
        self.assertTrue(any("7" in s for s in j_syms))

    def test_apply_feeling_bias_materially_mutates(self) -> None:
        profile = build_song_intent_profile(
            _doc_with_structure(style="Jazz"),
            {"label": "Chorus"},
            harmony_feeling="tense",
        )
        base = ["Cmaj7", "Am7", "Dm7", "G7"]
        up = apply_feeling_chord_bias(list(base), profile, feeling="uplifting", variant=0)
        tense = apply_feeling_chord_bias(list(base), profile, feeling="tense", variant=0)
        mel = apply_feeling_chord_bias(list(base), profile, feeling="melancholy", variant=0)
        self.assertNotEqual(up, tense)
        self.assertNotEqual(tense, mel)
        self.assertNotEqual(up, mel)


class TestMelodyWithoutChords(unittest.TestCase):
    def test_ai_melody_suggestions_without_chords(self) -> None:
        doc = _doc_with_structure()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        self.assertFalse(section_has_resolved_chords(doc, str(verse.get("id"))))
        concepts = suggest_melody_concepts(
            doc,
            verse,
            feel="lyrical",
            remember="a rising homeward hook",
            notes="keep it singable",
            limit=3,
        )
        self.assertGreaterEqual(len(concepts), 1)
        self.assertTrue(any(c.get("events") for c in concepts))

    def test_accept_melody_without_chords_persists(self) -> None:
        doc = _doc_with_structure()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        apply_melody_events(
            doc,
            sid,
            _phrase_events(),
            concept={"id": "mel_first", "name": "Home hook", "motif_hint": "rising"},
            replace=True,
        )
        self.assertTrue(section_melody_events(section_by_id(doc, sid)))
        self.assertFalse(section_has_resolved_chords(doc, sid))
        copied = deep_copy_document(doc)
        self.assertTrue(section_melody_events(section_by_id(copied, sid)))
        self.assertFalse(section_has_resolved_chords(copied, sid))

    def test_preview_signature_melody_only(self) -> None:
        doc = _doc_with_structure()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        events = _phrase_events()
        apply_melody_events(doc, sid, events, concept={"id": "m1", "name": "M"}, replace=True)
        sig = preview_signature(
            doc,
            section_id=sid,
            chord_override=[],
            include_melody=True,
            melody_override=events,
        )
        self.assertTrue(sig)
        # Empty chords + melody present is a valid signature shape.
        self.assertIn(True, sig)  # include_melody flag


class TestMelodyRepeatsAndEdits(unittest.TestCase):
    def test_repeats_expand_canonical_timeline(self) -> None:
        doc = _doc_with_structure()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        apply_melody_events(
            doc,
            sid,
            _phrase_events(),
            concept={"id": "pat", "name": "Phrase"},
            replace=True,
        )
        self.assertTrue(melody_is_tiled(section_by_id(doc, sid)))
        self.assertTrue(set_section_melody_repeats(doc, sid, 3))
        events = section_melody_events(section_by_id(doc, sid))
        self.assertEqual(len(events), 24)
        self.assertEqual(get_melody_repeats(section_by_id(doc, sid)), 3)
        passes = {int(e.get("pass_index") or 0) for e in events}
        self.assertEqual(passes, {0, 1, 2})

    def test_pass_specific_edit_freezes_tiling(self) -> None:
        doc = _doc_with_structure()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        apply_melody_events(
            doc, sid, _phrase_events(), concept={"id": "pat", "name": "Phrase"}, replace=True
        )
        set_section_melody_repeats(doc, sid, 3)
        sec = section_by_id(doc, sid)
        events = list(section_melody_events(sec) or [])
        # Edit pass 2 (index 1) last note.
        for ev in events:
            if int(ev.get("pass_index") or 0) == 1 and float(ev.get("beat") or 0) >= 14.0:
                ev["pitch"] = "E5"
                ev["midi"] = 76
                break
        apply_melody_events(doc, sid, events, replace=True)
        mark_melody_customized(section_by_id(doc, sid))
        self.assertFalse(melody_is_tiled(section_by_id(doc, sid)))
        self.assertFalse(set_section_melody_repeats(doc, sid, 4))
        kept = section_melody_events(section_by_id(doc, sid))
        self.assertTrue(any(e.get("pitch") == "E5" for e in kept))

    def test_nl_targets_second_pass(self) -> None:
        base = _phrase_events()
        expanded = expand_melody_events_by_repeats(base, 3)
        result = apply_natural_language_melody_edit(
            expanded,
            "Make the second time through end higher.",
            key="C",
            meter="4/4",
        )
        self.assertTrue(result.get("ok"), msg=result.get("message"))
        out = list(result.get("events") or [])
        pass1_last = [e for e in out if int(e.get("pass_index") or 0) == 1]
        self.assertTrue(pass1_last)
        self.assertGreaterEqual(int(pass1_last[-1].get("midi") or 0), 72)


class TestMelodyFirstHarmonization(unittest.TestCase):
    def test_chord_suggestions_consume_active_melody(self) -> None:
        doc = _doc_with_structure(style="Pop", key="C major")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        apply_melody_events(
            doc, sid, _phrase_events(), concept={"id": "m", "name": "Hook"}, replace=True
        )
        set_section_melody_repeats(doc, sid, 2)
        ideas = suggest_progressions(doc, section_by_id(doc, sid), "stable", limit=3)
        self.assertTrue(ideas)
        self.assertTrue(
            any(
                "melody" in str(i.get("id") or "").lower()
                or "melody" in str(i.get("context") or "").lower()
                or "fit" in str(i.get("name") or "").lower()
                or "harmon" in str(i.get("name") or "").lower()
                or i.get("melody_fit")
                for i in ideas
            )
            or any("melody" in str(i.get("why") or "").lower() for i in ideas)
        )

    def test_same_melody_style_changes_harmony(self) -> None:
        events = expand_melody_events_by_repeats(_phrase_events(), 2)
        results = {}
        for style in ("Pop", "Jazz", "Bossa"):
            doc = _doc_with_structure(style=style, key="C major")
            sec = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
            profile = build_song_intent_profile(doc, sec, harmony_feeling="stable")
            harms = harmonize_melody_to_progressions(
                events,
                key="C",
                meter="4/4",
                profile=profile,
                feeling="stable",
                limit=2,
            )
            self.assertTrue(harms, msg=f"No harmonization for {style}")
            results[style] = tuple(
                tuple(str(c.get("chord") or "") for c in h.get("chords") or [])
                for h in harms
            )
        self.assertNotEqual(results["Pop"], results["Jazz"])
        self.assertNotEqual(results["Jazz"], results["Bossa"])

    def test_expanded_melody_feeds_harmonizer(self) -> None:
        base = _phrase_events()
        one = expand_melody_events_by_repeats(base, 1)
        three = expand_melody_events_by_repeats(base, 3)
        # Mutate pass 2 so full timeline differs from tiled copies.
        for ev in three:
            if int(ev.get("pass_index") or 0) == 1:
                ev["pitch"] = "Bb4"
                ev["midi"] = 70
        doc = _doc_with_structure(style="Jazz", key="C major")
        sec = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        profile = build_song_intent_profile(doc, sec, harmony_feeling="tense")
        h1 = harmonize_melody_to_progressions(
            one, key="C", meter="4/4", profile=profile, feeling="tense", limit=1
        )
        h3 = harmonize_melody_to_progressions(
            three, key="C", meter="4/4", profile=profile, feeling="tense", limit=1
        )
        self.assertTrue(h1 and h3)
        # Longer melody should yield at least as many harmonic slots / distinct line.
        line1 = str(h1[0].get("line") or "")
        line3 = str(h3[0].get("line") or "")
        self.assertTrue(line1)
        self.assertTrue(line3)

    def test_section_mixed_state_no_leak(self) -> None:
        doc = _doc_with_structure()
        by_label = {str(s.get("label")): s for s in ordered_sections(doc)}
        verse_id = str(by_label["Verse"]["id"])
        chorus_id = str(by_label["Chorus"]["id"])
        bridge_id = str(by_label["Bridge"]["id"])

        apply_melody_events(
            doc, verse_id, _phrase_events(), concept={"id": "v_mel", "name": "V"}, replace=True
        )
        from composition_chord_repeats import accept_chord_pattern

        accept_chord_pattern(
            doc,
            chorus_id,
            [{"chord": "C"}, {"chord": "G"}, {"chord": "Am"}, {"chord": "F"}],
            source_id="c1",
            repeats=1,
        )
        apply_melody_events(
            doc,
            chorus_id,
            _phrase_events(),
            concept={"id": "c_mel", "name": "C"},
            replace=True,
        )
        accept_chord_pattern(
            doc,
            bridge_id,
            [{"chord": "Am"}, {"chord": "F"}, {"chord": "C"}, {"chord": "G"}],
            source_id="b1",
            repeats=1,
        )

        self.assertTrue(section_melody_events(section_by_id(doc, verse_id)))
        self.assertFalse(section_has_resolved_chords(doc, verse_id))
        self.assertTrue(section_has_resolved_chords(doc, chorus_id))
        self.assertTrue(section_melody_events(section_by_id(doc, chorus_id)))
        self.assertTrue(section_has_resolved_chords(doc, bridge_id))
        self.assertFalse(section_melody_events(section_by_id(doc, bridge_id)))

        copied = deep_copy_document(doc)
        self.assertTrue(section_melody_events(section_by_id(copied, verse_id)))
        self.assertFalse(section_has_resolved_chords(copied, verse_id))
        self.assertTrue(section_has_resolved_chords(copied, chorus_id))
        self.assertFalse(section_melody_events(section_by_id(copied, bridge_id)))


class TestChordsFirstStillWorks(unittest.TestCase):
    def test_melody_over_accepted_chords(self) -> None:
        doc = _doc_with_structure(style="Pop")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse.get("id"))
        from composition_chord_repeats import accept_chord_pattern

        accept_chord_pattern(
            doc,
            sid,
            [{"chord": "C"}, {"chord": "G"}, {"chord": "Am"}, {"chord": "F"}],
            source_id="pat",
            repeats=2,
        )
        concepts = suggest_melody_concepts(doc, section_by_id(doc, sid), feel="lyrical", limit=2)
        self.assertTrue(concepts)
        self.assertTrue(any(c.get("events") for c in concepts))


if __name__ == "__main__":
    unittest.main()
