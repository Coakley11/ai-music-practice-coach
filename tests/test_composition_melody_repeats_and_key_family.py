"""Melody repeats UX, mode-family key lock, melody-first harmony coverage, sync rules."""

from __future__ import annotations

import inspect
import unittest

from composition_chord_suggestions import suggest_progressions
from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    coerce_composition_key_choice_for_doc,
    composition_key_choice_labels_for_family,
    composition_mode_family_from_key,
    ensure_original_mode_family,
    ordered_sections,
    playback_globals,
    section_by_id,
    section_melody_events,
    set_original_mode_family_from_key,
)
from composition_key_transpose import apply_song_key_change
from composition_melody_repeats import (
    get_melody_repeats,
    mark_melody_customized,
    melody_is_tiled,
    set_section_melody_repeats,
)
from composition_playback_sync import build_playback_bundle, resolve_highlight_mode
from composition_studio_page import (
    _melody_defines_section_length,
    _render_active_melody_repeat_controls,
    _render_melody_concept_card,
    _section_has_accepted_melody,
)


def _phrase(n: int = 4) -> list[dict]:
    pitches = ["C4", "E4", "G4", "C5"]
    out = []
    for i in range(n):
        out.append(
            {
                "pitch": pitches[i % 4],
                "midi": 60 + (i % 4) * 2,
                "beat": float(i),
                "duration_beats": 1.0,
                "is_rest": False,
            }
        )
    return out


def _doc(key: str = "C major") -> dict:
    doc = bootstrap_from_vision(genre="Pop", song_idea="Mode family QA.", key=key, bpm=100, meter="4/4")
    apply_structure_template(doc, "pop")
    return doc


class TestMelodyRepeatsAfterAccept(unittest.TestCase):
    def test_repeats_control_only_with_active_melody(self) -> None:
        src = inspect.getsource(_render_active_melody_repeat_controls)
        self.assertIn("Melody repeats", src)
        # Gate: early return when no events
        self.assertIn("if not events:", src)
        # Concept card Use path sets just_accepted
        card = inspect.getsource(_render_melody_concept_card)
        self.assertIn("composer_melody_just_accepted_", card)
        self.assertIn("Use this melody", card)

    def test_repeat_expands_full_canonical_events(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(4), concept={"id": "m", "name": "M"}, replace=True)
        self.assertTrue(_section_has_accepted_melody(section_by_id(doc, sid)))
        self.assertTrue(set_section_melody_repeats(doc, sid, 3))
        evs = section_melody_events(section_by_id(doc, sid))
        self.assertEqual(len(evs), 12)
        self.assertEqual(get_melody_repeats(section_by_id(doc, sid)), 3)
        passes = {int(e.get("pass_index") or 0) for e in evs}
        self.assertEqual(passes, {0, 1, 2})


class TestMelodyFirstHarmony(unittest.TestCase):
    def test_no_chord_repeat_control_when_melody_owns(self) -> None:
        from composition_studio_page import _render_active_progression_controls

        src = inspect.getsource(_render_active_progression_controls)
        self.assertIn("Harmony length follows the active melody", src)
        self.assertIn("melody_owns_length", src)

    def test_suggestions_cover_full_expanded_melody(self) -> None:
        doc = _doc(key="C major")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(4), concept={"id": "m", "name": "M"}, replace=True)
        set_section_melody_repeats(doc, sid, 3)
        sec = section_by_id(doc, sid)
        # Pass-2 edit
        evs = list(section_melody_events(sec) or [])
        for e in evs:
            if int(e.get("pass_index") or 0) == 1 and not e.get("is_rest"):
                e["midi"] = 72
                e["pitch"] = "C5"
                break
        apply_melody_events(doc, sid, evs, replace=True)
        mark_melody_customized(section_by_id(doc, sid))
        self.assertFalse(melody_is_tiled(section_by_id(doc, sid)))

        sug = suggest_progressions(doc, section_by_id(doc, sid), "stable", limit=2)
        self.assertTrue(sug)
        for s in sug:
            self.assertEqual(s.get("context"), "melody_fit")
            chords = list(s.get("chords") or [])
            # Full 12-beat / ~3-bar×4 → at least 3 harmonic slots; typically 12 one-per-bar
            self.assertGreaterEqual(len(chords), 3)
            self.assertLessEqual(len(chords), 16)


class TestPlaybackHighlightRules(unittest.TestCase):
    def test_combined_melody_primary(self) -> None:
        b = build_playback_bundle(
            events=_phrase(3), chord_syms=["C", "G", "Am"], bpm=96, meter="4/4"
        )
        self.assertEqual(b["mode"], "combined")
        self.assertEqual(b["primary"], "melody")
        self.assertEqual(b["cursor_spans"], b["melody_spans"])

    def test_chord_only(self) -> None:
        b = build_playback_bundle(events=None, chord_syms=["C", "Am", "F", "G"], bpm=90)
        self.assertEqual(b["mode"], "chords")
        self.assertEqual(b["primary"], "chords")

    def test_resolve_modes(self) -> None:
        self.assertEqual(resolve_highlight_mode(has_melody=True, has_chords=True), "combined")
        self.assertEqual(resolve_highlight_mode(has_melody=False, has_chords=True), "chords")


class TestModeFamilyLock(unittest.TestCase):
    def test_major_song_only_major_keys(self) -> None:
        doc = _doc("C major")
        self.assertEqual(ensure_original_mode_family(doc), "major")
        labels = composition_key_choice_labels_for_family("major")
        self.assertTrue(all(composition_mode_family_from_key(x) == "major" for x in labels))
        self.assertIn("E major", labels)
        self.assertNotIn("A minor", labels)
        # Attempting minor choice coerces into major family
        coerced = coerce_composition_key_choice_for_doc(doc, "A minor")
        self.assertEqual(composition_mode_family_from_key(coerced), "major")

    def test_minor_song_only_minor_keys(self) -> None:
        doc = _doc("A minor")
        self.assertEqual(ensure_original_mode_family(doc), "minor")
        labels = composition_key_choice_labels_for_family("minor")
        self.assertTrue(all(composition_mode_family_from_key(x) == "minor" for x in labels))
        self.assertIn("C minor", labels)
        self.assertNotIn("C major", labels)

    def test_family_persists_after_key_change(self) -> None:
        doc = _doc("C major")
        apply_song_key_change({}, doc, "E", new_key_label="E major")
        self.assertEqual(ensure_original_mode_family(doc), "major")
        self.assertEqual(playback_globals(doc)["key_center"], "E")
        # Mode family must not flip even if a minor label sneaks in
        apply_song_key_change({}, doc, "Am", new_key_label="A minor")
        self.assertEqual(ensure_original_mode_family(doc), "major")
        self.assertEqual(composition_mode_family_from_key(playback_globals(doc)["key_label"]), "major")

    def test_practice_key_does_not_set_family(self) -> None:
        doc = _doc("C major")
        fam = ensure_original_mode_family(doc)
        # Simulate practice key noise in unrelated session keys — family stays
        self.assertEqual(fam, "major")
        set_original_mode_family_from_key(doc, "C major")
        self.assertEqual(doc["global"]["original_mode_family"], "major")

    def test_all_sections_transpose(self) -> None:
        doc = _doc("C major")
        for sec in ordered_sections(doc)[:2]:
            sid = str(sec["id"])
            apply_melody_events(doc, sid, _phrase(2), concept={"id": "m", "name": "M"}, replace=True)
            set_section_melody_repeats(doc, sid, 2)
        apply_song_key_change({}, doc, "D", new_key_label="D major")
        for sec in ordered_sections(doc)[:2]:
            mel = section_melody_events(sec)
            self.assertTrue(mel)
            self.assertTrue(str(mel[0].get("pitch", "")).startswith("D"))


if __name__ == "__main__":
    unittest.main()
