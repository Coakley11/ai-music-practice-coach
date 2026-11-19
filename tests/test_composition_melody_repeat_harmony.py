"""Melody repeats x2-x4 keep their harmony (Composition stabilization, 2026-11-19).

Tiling the accepted phrase past one pass of the section's chords used to leave every repeated
pass with no chord symbols on the staff, no chord highlight, and no backing under the melody
in the preview audio (the backing was one pass long and the rest was silence).
"""

import re
import unittest
from unittest import mock

from composition_document import (
    apply_melody_concept,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    ordered_sections,
    parse_chord_paste,
)
from composition_melody_preview import harmony_covering_melody, melody_end_beat
from composition_melody_repeats import set_section_melody_repeats
from composition_melody_suggestions import suggest_melody_concepts


def _doc_with_repeated_melody(repeats: int):
    doc = bootstrap_from_vision(genre="Pop", song_idea="Repeat harmony.")
    apply_structure_template(doc, "simple")
    sec = ordered_sections(doc)[0]
    sid = str(sec["id"])
    apply_section_chords(doc, sid, parse_chord_paste("D Bm A G"))
    concept = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=1)[0]
    apply_melody_concept(doc, sid, concept)
    assert set_section_melody_repeats(doc, sid, repeats)
    sec = next(s for s in ordered_sections(doc) if str(s["id"]) == sid)
    return doc, sec, sid


def _page_module():
    """composition_studio_page with its real renderers.

    test_composition_melody_preview_timeline's AppTest script swaps module functions for counting
    fakes and never restores them; load a private copy when that has happened in this process.
    """
    import importlib.util

    import composition_studio_page as page

    if all(getattr(page, n).__name__ == n for n in ("_render_melody_staff", "_attach_synced_score_preview")):
        return page
    spec = importlib.util.spec_from_file_location("composition_studio_page_repeat_harmony", page.__file__)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bar_chords(abc: str) -> list[list[str]]:
    body = abc.split("\nK:", 1)[1].split("\n", 1)[1]
    return [re.findall(r'"([^"]+)"', b) for b in body.split("|") if b.strip()]


class TestHarmonyCoveringMelody(unittest.TestCase):
    def _events(self, bars: int) -> list[dict]:
        return [{"pitch": "D4", "beat": float(4 * i), "duration_beats": 4.0} for i in range(bars)]

    def test_symbols_cycle_to_melody_length(self) -> None:
        self.assertEqual(
            harmony_covering_melody(["D", "Bm", "A", "G"], self._events(8)),
            ["D", "Bm", "A", "G", "D", "Bm", "A", "G"],
        )

    def test_entries_cycle_and_last_entry_is_trimmed(self) -> None:
        entries = [{"chord": "D", "bars": 2}, {"chord": "G", "bars": 2}]
        out = harmony_covering_melody(entries, self._events(7))
        self.assertEqual([(e["chord"], e["bars"]) for e in out], [("D", 2), ("G", 2), ("D", 2), ("G", 1)])
        self.assertEqual(entries[1]["bars"], 2)  # input entries are not mutated

    def test_partial_final_bar_gets_harmony_to_the_bar_line_only(self) -> None:
        # Melody ends half-way through bar 8: harmony runs to the end of bar 8, never into a 9th bar.
        evs = [{"pitch": "D4", "beat": 2.0 * i, "duration_beats": 2.0} for i in range(15)]
        self.assertEqual(melody_end_beat(evs), 30.0)
        self.assertEqual(len(harmony_covering_melody(["D", "Bm", "A", "G"], evs)), 8)

    def test_durations_and_onsets_follow_the_meter(self) -> None:
        from composition_melody_notation import _chord_onset_beats

        entries = [{"chord": "D", "bars": 2}, {"chord": "G", "bars": 1}, {"chord": "", "repeat": True, "bars": 1}]
        for meter, bar in (("4/4", 4.0), ("3/4", 3.0), ("6/8", 6.0)):
            evs = [{"pitch": "D4", "beat": bar * i, "duration_beats": bar} for i in range(8)]
            out = harmony_covering_melody(entries, evs, meter=meter)
            self.assertEqual([e["bars"] for e in out], [2, 1, 1, 2, 1, 1], meter)
            onsets = _chord_onset_beats(out, meter=meter)
            self.assertEqual(
                onsets,
                [(0.0, "D"), (2 * bar, "G"), (3 * bar, "G"), (4 * bar, "D"), (6 * bar, "G"), (7 * bar, "G")],
                meter,
            )

    def test_progression_already_long_enough_is_unchanged(self) -> None:
        chords = ["D", "Bm", "A", "G"]
        self.assertEqual(harmony_covering_melody(chords, self._events(3)), chords)
        self.assertEqual(harmony_covering_melody(chords, self._events(4)), chords)
        self.assertEqual(harmony_covering_melody(chords, []), chords)
        self.assertEqual(harmony_covering_melody([], self._events(8)), [])


class TestRepeatedMelodyKeepsChords(unittest.TestCase):
    def test_staff_shows_chords_above_every_pass(self) -> None:
        page = _page_module()

        for n in (1, 2, 3, 4):
            doc, sec, _sid = _doc_with_repeated_melody(n)
            events = list(sec["melody"]["events"])
            self.assertEqual(len({e.get("repeat_index") for e in events}), n)
            with mock.patch("streamlit.components.v1.html") as html_mock, mock.patch.object(page, "st"):
                page._render_melody_staff(
                    events, key="D", meter="4/4", bpm=96, title="", chords=list(sec.get("chords") or []),
                )
            abc_html = html_mock.call_args.args[0]
            abc = "X:1\nT:\nM:4/4\nK:D\n" + abc_html.split("ABCJS.renderAbc(\"paper\", `", 1)[1].split("`", 1)[0].split("\nK:", 1)[1].split("\n", 1)[1]
            self.assertEqual(_bar_chords(abc), [["D"], ["Bm"], ["A"], ["G"]] * n, f"x{n}")

    def test_synced_player_staff_and_chord_highlight_cover_every_pass(self) -> None:
        import composition_playback_sync
        page = _page_module()
        from composition_preview import COMPOSER_PREVIEW_SLOT_KEY
        from composition_session_state import COMPOSER_PREVIEW_WAV_KEY

        doc, sec, sid = _doc_with_repeated_melody(2)
        events = list(sec["melody"]["events"])
        flat = [str(c) for c in chords_for_playback(doc, scope="section", section_id=sid)]
        self.assertEqual(flat, ["D", "Bm", "A", "G"])  # the stored section harmony stays one pass
        slot = f"melody:{sid}:active_loop"
        ss = {COMPOSER_PREVIEW_SLOT_KEY: slot, COMPOSER_PREVIEW_WAV_KEY: b"RIFF"}
        with mock.patch.object(composition_playback_sync, "mount_synced_score_playback") as mount, mock.patch.object(page, "st") as st_mock:
            st_mock.button.return_value = False
            self.assertTrue(page._attach_synced_score_preview(ss, doc, slot=slot, events=events, chord_syms=flat))
        kw = mount.call_args.kwargs
        self.assertEqual(_bar_chords(kw["abc_text"]), [["D"], ["Bm"], ["A"], ["G"]] * 2)
        spans = kw["bundle"]["chord_spans"]
        self.assertEqual([s["chord"] for s in spans], ["D", "Bm", "A", "G"] * 2)
        melody_end = max(float(s["end_sec"]) for s in kw["bundle"]["melody_spans"])
        self.assertAlmostEqual(max(float(s["end_sec"]) for s in spans), melody_end, places=3)

    def test_preview_backing_plays_under_every_pass(self) -> None:
        import backing_audio
        from composition_preview import generate_preview_wav

        doc, sec, sid = _doc_with_repeated_melody(3)
        flat = [str(c) for c in chords_for_playback(doc, scope="section", section_id=sid)]
        self.assertEqual(melody_end_beat(sec["melody"]["events"]), 48.0)
        seen: list[list[str]] = []
        real = backing_audio.generate_backing_track

        def capture(chords, **kw):
            seen.append(list(chords))
            return real(chords, **kw)

        with mock.patch.object(backing_audio, "generate_backing_track", side_effect=capture):
            wav = generate_preview_wav(doc, scope="section", section_id=sid, loops=1, include_melody=True, chord_override=flat)
        self.assertTrue(wav)
        self.assertEqual(seen, [["D", "Bm", "A", "G"] * 3])

    def test_chords_only_preview_is_unchanged(self) -> None:
        import backing_audio
        from composition_preview import generate_preview_wav

        doc, _sec, sid = _doc_with_repeated_melody(2)
        with mock.patch.object(backing_audio, "generate_backing_track", return_value=None) as gen:
            generate_preview_wav(doc, scope="section", section_id=sid, loops=2, include_melody=False)
        self.assertEqual(list(gen.call_args.args[0]), ["D", "Bm", "A", "G"])


if __name__ == "__main__":
    unittest.main()
