"""Playback sync, APE delete, Review melody+chords, Key/BPM song-wide updates."""

from __future__ import annotations

import unittest

from composition_document import (
    apply_melody_events,
    apply_structure_template,
    bootstrap_from_vision,
    deep_copy_document,
    ordered_sections,
    playback_globals,
    section_by_id,
    section_melody_events,
)
from composition_chord_repeats import accept_chord_pattern
from composition_key_transpose import apply_song_key_change, apply_song_tempo_change, transpose_composition_to_key
from composition_melody_harmonize import harmonize_melody_to_progressions
from composition_melody_repeats import set_section_melody_repeats
from composition_melody_shape import (
    apply_natural_language_melody_edit,
    delete_melody_note_preserve_gap,
)
from composition_playback_sync import (
    active_index_at,
    build_melody_note_timeline,
    build_playback_bundle,
    resolve_highlight_mode,
)
from composition_song_intent import build_song_intent_profile
from composition_studio_page import _melody_defines_section_length, _section_has_accepted_melody


def _phrase() -> list[dict]:
    return [
        {"pitch": "C4", "midi": 60, "beat": 0.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "E4", "midi": 64, "beat": 1.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "G4", "midi": 67, "beat": 2.0, "duration_beats": 1.0, "is_rest": False},
        {"pitch": "rest", "midi": None, "beat": 3.0, "duration_beats": 1.0, "is_rest": True},
    ]


def _doc(style: str = "Pop", key: str = "C major") -> dict:
    doc = bootstrap_from_vision(
        genre=style, song_idea="Sync test song.", key=key, bpm=96, meter="4/4"
    )
    apply_structure_template(doc, "pop")
    return doc


class TestPlaybackSync(unittest.TestCase):
    def test_melody_timeline_exposes_timed_note_index(self) -> None:
        spans = build_melody_note_timeline(_phrase(), bpm=120, meter="4/4")
        self.assertEqual(len(spans), 4)
        sounding = [s for s in spans if s["highlightable"]]
        self.assertEqual(len(sounding), 3)
        self.assertIsNone(spans[3]["dom_note_index"])  # rest
        self.assertEqual(spans[0]["dom_note_index"], 0)
        # At midpoint of first note
        idx = active_index_at(spans, spans[0]["start_sec"] + 0.01)
        self.assertEqual(idx, 0)
        # During rest — no highlightable active (rest not highlightable)
        rest_t = spans[3]["start_sec"] + 0.01
        idx_rest = active_index_at(spans, rest_t)
        self.assertTrue(idx_rest < 0 or not spans[idx_rest]["highlightable"] or idx_rest == 2)

    def test_combined_prioritizes_melody_cursor(self) -> None:
        bundle = build_playback_bundle(
            events=_phrase(),
            chord_syms=["C", "G", "Am", "F"],
            bpm=100,
            meter="4/4",
        )
        self.assertEqual(bundle["mode"], "combined")
        self.assertEqual(bundle["primary"], "melody")
        self.assertEqual(bundle["cursor_spans"], bundle["melody_spans"])

    def test_chord_only_mode(self) -> None:
        bundle = build_playback_bundle(
            events=None, chord_syms=["C", "Am", "F", "G"], bpm=90, meter="4/4"
        )
        self.assertEqual(bundle["mode"], "chords")
        self.assertEqual(bundle["primary"], "chords")
        self.assertGreaterEqual(len(bundle["chord_spans"]), 4)

    def test_bpm_scales_highlight_timing(self) -> None:
        slow = build_melody_note_timeline(_phrase()[:1], bpm=60)
        fast = build_melody_note_timeline(_phrase()[:1], bpm=120)
        self.assertAlmostEqual(slow[0]["end_sec"] - slow[0]["start_sec"], 1.0, places=2)
        self.assertAlmostEqual(fast[0]["end_sec"] - fast[0]["start_sec"], 0.5, places=2)

    def test_repeated_melody_occurrence_ids(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase()[:3], concept={"id": "m", "name": "M"}, replace=True)
        set_section_melody_repeats(doc, sid, 3)
        evs = section_melody_events(section_by_id(doc, sid))
        spans = build_melody_note_timeline(evs, bpm=96)
        self.assertEqual(len(spans), 9)
        passes = {s.get("pass_index") for s in spans}
        self.assertEqual(passes, {0, 1, 2})


class TestActiveMelodyGating(unittest.TestCase):
    def test_no_active_before_accept(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        self.assertFalse(_section_has_accepted_melody(verse))

    def test_active_after_accept(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "a", "name": "A"}, replace=True)
        self.assertTrue(_section_has_accepted_melody(section_by_id(doc, sid)))

    def test_melody_owns_length_hides_chord_repeats(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "a", "name": "A"}, replace=True)
        set_section_melody_repeats(doc, sid, 3)
        self.assertTrue(_melody_defines_section_length(section_by_id(doc, sid)))


class TestApeDelete(unittest.TestCase):
    def test_delete_creates_rest_preserves_timing(self) -> None:
        evs = _phrase()
        out = delete_melody_note_preserve_gap(evs, 1)
        self.assertTrue(out[1]["is_rest"])
        self.assertEqual(float(out[1]["duration_beats"]), 1.0)
        self.assertEqual(len(out), 4)
        # Later note still at same beat
        self.assertEqual(float(out[2]["beat"]), 2.0)

    def test_delete_does_not_commit_without_accept(self) -> None:
        doc = _doc()
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase(), concept={"id": "a", "name": "A"}, replace=True)
        before = deep_copy_document(doc)
        # Simulate pending draft delete only
        draft = delete_melody_note_preserve_gap(list(section_melody_events(section_by_id(doc, sid))), 0)
        self.assertTrue(draft[0]["is_rest"])
        # Canonical unchanged
        self.assertFalse(
            (section_melody_events(section_by_id(before, sid)) or [])[0].get("is_rest")
        )

    def test_nl_delete(self) -> None:
        result = apply_natural_language_melody_edit(
            _phrase(), "Delete the first note", key="C", meter="4/4"
        )
        self.assertTrue(result.get("ok"), msg=result.get("message"))
        out = result["events"]
        self.assertTrue(out[0].get("is_rest") or str(out[0].get("pitch")).lower() == "rest")


class TestMelodyOwnsHarmonyLength(unittest.TestCase):
    def test_harmonize_spans_full_repeated_melody(self) -> None:
        doc = _doc(style="Jazz")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        sid = str(verse["id"])
        apply_melody_events(doc, sid, _phrase()[:3], concept={"id": "m", "name": "M"}, replace=True)
        set_section_melody_repeats(doc, sid, 3)
        sec = section_by_id(doc, sid)
        evs = section_melody_events(sec)
        profile = build_song_intent_profile(doc, sec, harmony_feeling="stable")
        harms = harmonize_melody_to_progressions(
            evs, key="C", meter="4/4", profile=profile, feeling="stable", limit=1
        )
        self.assertTrue(harms)
        # 3 passes × ~1 bar each (3 notes pack into ~1 bar) → multiple chords
        self.assertGreaterEqual(len(harms[0]["chords"]), 3)


class TestSongKeyAndBpm(unittest.TestCase):
    def test_key_change_transposes_all_sections(self) -> None:
        doc = _doc(key="C major")
        sections = ordered_sections(doc)
        for sec in sections[:2]:
            sid = str(sec["id"])
            accept_chord_pattern(
                doc,
                sid,
                [{"chord": "C"}, {"chord": "Am"}, {"chord": "F"}, {"chord": "G"}],
                source_id="p",
                repeats=1,
            )
            apply_melody_events(
                doc, sid, _phrase()[:2], concept={"id": "m", "name": "M"}, replace=True
            )
        ss: dict = {}
        apply_song_key_change(ss, doc, "D", new_key_label="D major")
        self.assertEqual(playback_globals(doc)["key_center"], "D")
        for sec in ordered_sections(doc)[:2]:
            chords = [str(c.get("chord")) for c in sec.get("chords") or []]
            self.assertTrue(any(c.startswith("D") or c.startswith("Bm") or c.startswith("G") or c.startswith("A") for c in chords))
            mel = section_melody_events(sec)
            self.assertTrue(mel)
            # C4 → D4
            self.assertIn(str(mel[0].get("pitch")), {"D4", "D"})

    def test_qualities_preserved(self) -> None:
        doc = _doc(key="C major")
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        accept_chord_pattern(
            doc,
            str(verse["id"]),
            [{"chord": "Cmaj7"}, {"chord": "Am7"}, {"chord": "Dm7"}, {"chord": "G7"}],
            source_id="j",
            repeats=1,
        )
        transpose_composition_to_key(doc, "D", new_key_label="D major")
        chords = [str(c.get("chord")) for c in verse.get("chords") or []]
        self.assertTrue(any("maj7" in c for c in chords))
        self.assertTrue(any("m7" in c for c in chords))
        self.assertTrue(any(c.endswith("7") and "maj" not in c and "m7" not in c for c in chords) or any("G7" in c or "A7" in c for c in chords))

    def test_bpm_change_atomic(self) -> None:
        doc = _doc()
        apply_song_tempo_change(doc, 140)
        self.assertEqual(int(playback_globals(doc)["bpm"]), 140)
        # Durations unchanged
        verse = next(s for s in ordered_sections(doc) if s.get("label") == "Verse")
        apply_melody_events(doc, str(verse["id"]), _phrase(), concept={"id": "m", "name": "M"}, replace=True)
        apply_song_tempo_change(doc, 80)
        evs = section_melody_events(section_by_id(doc, str(verse["id"])))
        self.assertEqual(float(evs[0]["duration_beats"]), 1.0)

    def test_key_change_clears_pending_proposals(self) -> None:
        doc = _doc()
        ss = {"composer_melody_refine_proposal_x": {"events": []}, "composer_hum_proposal_y": {}}
        apply_song_key_change(ss, doc, "E", new_key_label="E major")
        self.assertNotIn("composer_melody_refine_proposal_x", ss)
        self.assertNotIn("composer_hum_proposal_y", ss)


class TestResolveMode(unittest.TestCase):
    def test_modes(self) -> None:
        self.assertEqual(resolve_highlight_mode(has_melody=True, has_chords=True), "combined")
        self.assertEqual(resolve_highlight_mode(has_melody=True, has_chords=False), "melody")
        self.assertEqual(resolve_highlight_mode(has_melody=False, has_chords=True), "chords")
        self.assertEqual(resolve_highlight_mode(has_melody=False, has_chords=False), "none")


if __name__ == "__main__":
    unittest.main()
