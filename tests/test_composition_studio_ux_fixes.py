"""Focused tests for Composition Studio UX/audio/harmony fixes."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from composition_chord_manual_editor import (
    annotate_chromatic,
    build_chord_symbol,
    chord_timeline,
    insert_draft_chord,
    is_chromatic_to_key,
    parse_chord_parts,
    suggest_insert_chords,
    update_draft_chord,
)
from composition_document import (
    apply_melody_events,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
    section_melody_events,
)
from composition_key_transpose import (
    composition_key_interval,
    push_key_undo,
    transpose_composition_to_key,
    apply_undo_key_change,
)
from composition_melody_improve import (
    apply_plain_language_improvement,
    apply_quick_action,
    preserve_original_take,
    restore_original_take,
)
from composition_melody_repeats import (
    EDIT_SCOPE_FIRST,
    apply_transform_with_repeat_scope,
    expand_melody_events_by_repeats,
    phrase_length_beats,
)
from composition_sync_transport import (
    active_span_index_at,
    bar_seconds,
    build_chord_span_timeline,
    build_synced_transport_html,
    count_in_seconds,
    prepend_count_in_clicks,
)
from composition_hum_transcription import segments_to_melody_events
from composition_preview import generate_preview_wav
from composition_workspace_state_persistence import (
    apply_composition_workspace_to_session,
    gather_composition_workspace_from_session,
)
from composition_session_state import COMPOSER_ACTIVE_KEY, COMPOSER_ACTIVE_SECTION_KEY
from custom_progression_lab import expand_entries_to_chords
from backing_audio import chord_notes


def _doc_with_section() -> tuple[dict, str]:
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="Test",
        title="Chord Edit Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    sec = ordered_sections(doc)[0]
    sid = str(sec["id"])
    apply_section_chords(doc, sid, parse_chord_paste("C F G G7"))
    return doc, sid


class TestManualChordEditor(unittest.TestCase):
    def test_timeline_positions(self) -> None:
        entries = parse_chord_paste("C F G G7")
        rows = chord_timeline(entries, meter="4/4")
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["measure"], 1)
        self.assertEqual(rows[2]["chord"], "G")
        self.assertEqual(rows[3]["chord"], "G7")

    def test_build_and_parse_qualities(self) -> None:
        sym = build_chord_symbol(root="G", quality="7", alteration="", bass="")
        self.assertEqual(sym, "G7")
        parts = parse_chord_parts("F#m7b5/A")
        self.assertTrue(parts["root"].startswith("F"))
        slash = build_chord_symbol(root="C", quality="maj7", bass="E")
        self.assertIn("/", slash)

    def test_insert_suggestions_and_chromatic(self) -> None:
        ideas = suggest_insert_chords(key_token="C", before="C", after="G")
        self.assertTrue(ideas)
        self.assertTrue(any(not i["chromatic"] for i in ideas))
        self.assertTrue(is_chromatic_to_key("C#", "C"))
        self.assertFalse(is_chromatic_to_key("Am", "C"))
        annotated = annotate_chromatic(chord_timeline(parse_chord_paste("C C# G")), "C")
        self.assertTrue(annotated[1]["chromatic"])

    def test_draft_edit_insert_accept_path(self) -> None:
        draft = parse_chord_paste("C F G")
        draft = update_draft_chord(draft, 1, chord="Dm")
        draft = insert_draft_chord(draft, 2, "G7")
        chords = expand_entries_to_chords(draft)
        self.assertEqual(chords[1], "Dm")
        self.assertIn("G7", chords)

    def test_accepted_chords_update_canonical_section(self) -> None:
        doc, sid = _doc_with_section()
        apply_section_chords(doc, sid, parse_chord_paste("C Am F G"))
        self.assertEqual(expand_entries_to_chords(ordered_sections(doc)[0]["chords"])[1], "Am")
        wav = generate_preview_wav(doc, section_id=sid, loops=1, include_melody=False)
        self.assertTrue(wav and wav.startswith(b"RIFF"))


class TestMelodyRepeats(unittest.TestCase):
    def test_expand_repeats_aligns_beats(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
        ]
        out = expand_melody_events_by_repeats(events, 3)
        self.assertEqual(len(out), 6)
        self.assertEqual(out[2]["beat"], 4.0)
        self.assertEqual(out[4]["beat"], 8.0)
        self.assertEqual(phrase_length_beats(events), 4.0)

    def test_first_occurrence_scope_leaves_later_repeats(self) -> None:
        base = [
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
        ]
        tiled = expand_melody_events_by_repeats(base, 2)

        def bump(evs):
            out = copy.deepcopy(evs)
            for e in out:
                e["midi"] = int(e["midi"]) + 1
            return out

        scoped = apply_transform_with_repeat_scope(tiled, bump, scope=EDIT_SCOPE_FIRST)
        first = [e for e in scoped if int(e.get("repeat_index") or 0) == 0]
        second = [e for e in scoped if int(e.get("repeat_index") or 0) == 1]
        self.assertEqual(int(first[0]["midi"]), 61)
        self.assertEqual(int(second[0]["midi"]), 60)


class TestSyncTransport(unittest.TestCase):
    def test_span_timeline_matches_loops(self) -> None:
        spans = build_chord_span_timeline(["C", "F", "G", "G7"], bpm=120, meter="4/4", loops=2)
        self.assertEqual(len(spans), 8)
        self.assertEqual(spans[0]["chord"], "C")
        self.assertEqual(spans[4]["chord"], "C")
        self.assertAlmostEqual(spans[0]["start_sec"], 0.0)
        self.assertAlmostEqual(spans[0]["end_sec"], 2.0)
        self.assertAlmostEqual(spans[1]["start_sec"], 2.0)
        self.assertEqual(spans[2]["chord"], "G")
        self.assertEqual(spans[3]["chord"], "G7")

    def test_active_index_follows_audio_clock(self) -> None:
        spans = build_chord_span_timeline(["C", "F", "G", "G7"], bpm=120, meter="4/4", loops=1)
        self.assertEqual(active_span_index_at(spans, 0.5), 0)
        self.assertEqual(active_span_index_at(spans, 2.5), 1)
        self.assertEqual(active_span_index_at(spans, 4.5), 2)
        self.assertEqual(active_span_index_at(spans, 6.5), 3)
        self.assertEqual(active_span_index_at(spans, 0.0, stopped_at_start=True), -1)

    def test_g_versus_g7_pitch_classes(self) -> None:
        g_pcs = {n % 12 for n in chord_notes("G")}
        g7_pcs = {n % 12 for n in chord_notes("G7")}
        self.assertEqual(g_pcs, {7, 11, 2})  # G B D
        self.assertIn(5, g7_pcs)  # F natural (minor 7th)
        self.assertNotEqual(g_pcs, g7_pcs)

    def test_html_embeds_audio_and_spans(self) -> None:
        spans = build_chord_span_timeline(["C", "G"], bpm=100, loops=1)
        html = build_synced_transport_html(b"RIFF....WAVE", spans, dom_id="testsync")
        self.assertIn("testsync-audio", html)
        self.assertIn("currentTime", html)
        self.assertIn("is-active", html)

    def test_browser_smoke_highlight_tracks_seek(self) -> None:
        """Real Chromium: audio clock seek updates the active chord chip."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright not installed")

        spans = build_chord_span_timeline(["C", "F", "G", "G7"], bpm=120, meter="4/4", loops=1)
        # Tiny valid-enough WAV for browser decode is optional; we drive currentTime directly.
        html = build_synced_transport_html(b"RIFF....WAVE", spans, dom_id="smoke")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sync_smoke.html"
            path.write_text(html, encoding="utf-8")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(path.as_uri())
                    page.wait_for_selector(".csync-chord")
                    # Force clock without relying on decode of placeholder WAV.
                    page.evaluate(
                        """() => {
                          const audio = document.querySelector('.csync-audio');
                          Object.defineProperty(audio, 'paused', { get: () => false });
                          audio.currentTime = 2.5;
                          window.__csyncTick();
                        }"""
                    )
                    active = page.evaluate(
                        "() => Array.from(document.querySelectorAll('.csync-chord')).findIndex(b => b.classList.contains('is-active'))"
                    )
                    self.assertEqual(active, 1)
                    page.evaluate(
                        """() => {
                          const audio = document.querySelector('.csync-audio');
                          audio.currentTime = 6.25;
                          window.__csyncTick();
                        }"""
                    )
                    active2 = page.evaluate(
                        "() => Array.from(document.querySelectorAll('.csync-chord')).findIndex(b => b.classList.contains('is-active'))"
                    )
                    self.assertEqual(active2, 3)
                    label = page.evaluate(
                        "() => document.querySelectorAll('.csync-chord')[3].textContent"
                    )
                    self.assertEqual(label.strip(), "G7")
                finally:
                    browser.close()


class TestMelodyImprove(unittest.TestCase):
    def test_change_last_note(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0},
            {"pitch": "D4", "midi": 62, "duration_beats": 1.0, "beat": 1.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
        ]
        result = apply_plain_language_improvement(events, "Change the last note to G", key="C")
        self.assertTrue(result["ok"])
        self.assertEqual(int(result["events"][-1]["midi"]) % 12, 7)

    def test_ambiguous_asks_clarification(self) -> None:
        events = [{"pitch": "C4", "midi": 60, "duration_beats": 1.0, "beat": 0.0}]
        result = apply_plain_language_improvement(
            events, "make it totally different and jazzier forever", key="C"
        )
        self.assertTrue(result["needs_clarification"])

    def test_quick_shorten_and_original_restore(self) -> None:
        events = [
            {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0},
            {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
        ]
        ss: dict = {}
        preserve_original_take(ss, "sec1", events)
        result = apply_quick_action(events, "shorten_first", key="C")
        self.assertTrue(result["ok"])
        self.assertLess(float(result["events"][0]["duration_beats"]), 2.0)
        orig = restore_original_take(ss, "sec1")
        self.assertEqual(float(orig[0]["duration_beats"]), 2.0)


class TestMixBalance(unittest.TestCase):
    def test_melody_gain_higher_changes_mix(self) -> None:
        doc, sid = _doc_with_section()
        events = [{"pitch": "C4", "midi": 60, "duration_beats": 4.0, "beat": 0.0}]
        apply_melody_events(doc, sid, events, replace=True)
        soft = generate_preview_wav(
            doc, section_id=sid, loops=1, include_melody=True, melody_gain=0.2, backing_gain=0.9
        )
        loud = generate_preview_wav(
            doc, section_id=sid, loops=1, include_melody=True, melody_gain=0.7, backing_gain=0.5
        )
        self.assertTrue(soft and loud)
        self.assertNotEqual(soft, loud)
        self.assertTrue(loud.startswith(b"RIFF"))


class TestKeyTranspose(unittest.TestCase):
    def test_whole_song_transpose_chords_and_melody(self) -> None:
        doc, sid = _doc_with_section()
        secs = ordered_sections(doc)
        if len(secs) > 1:
            apply_section_chords(doc, str(secs[1]["id"]), parse_chord_paste("Am Dm E7"))
        apply_melody_events(
            doc,
            sid,
            [
                {"pitch": "C4", "midi": 60, "duration_beats": 2.0, "beat": 0.0},
                {"pitch": "E4", "midi": 64, "duration_beats": 2.0, "beat": 2.0},
            ],
            replace=True,
        )
        ss: dict = {}
        push_key_undo(ss, doc)
        self.assertEqual(composition_key_interval("C", "G"), 7)
        transpose_composition_to_key(doc, "G", new_key_label="G major")
        self.assertEqual((doc.get("global") or {}).get("original_key_center"), "G")
        chords = expand_entries_to_chords((ordered_sections(doc)[0].get("chords")))
        self.assertEqual(chords[0], "G")
        self.assertEqual(chords[1], "C")
        mel = section_melody_events(ordered_sections(doc)[0])
        self.assertEqual(int(mel[0]["midi"]), 67)
        self.assertTrue(apply_undo_key_change(ss, doc))
        self.assertEqual((doc.get("global") or {}).get("original_key_center"), "C")
        self.assertEqual(expand_entries_to_chords(ordered_sections(doc)[0].get("chords"))[0], "C")

    def test_no_double_transpose_zero_interval(self) -> None:
        doc, _sid = _doc_with_section()
        before = copy.deepcopy(doc)
        transpose_composition_to_key(doc, "C", new_key_label="C major")
        self.assertEqual(
            expand_entries_to_chords(ordered_sections(doc)[0].get("chords")),
            expand_entries_to_chords(ordered_sections(before)[0].get("chords")),
        )

    def test_slash_altered_flat_sharp_and_mode_policy(self) -> None:
        doc, sid = _doc_with_section()
        apply_section_chords(doc, sid, parse_chord_paste("Cmaj7/E F#m7b5"))
        transpose_composition_to_key(doc, "D", new_key_label="D major")
        chords = expand_entries_to_chords(ordered_sections(doc)[0].get("chords"))
        self.assertTrue(chords[0].startswith("D"))
        self.assertIn("/", chords[0])
        # major → minor token: interval tonic-only; destination mode label kept
        transpose_composition_to_key(doc, "Em", new_key_label="E minor")
        self.assertEqual((doc.get("global") or {}).get("original_key_center"), "Em")

    def test_cold_restore_keeps_transposed_doc(self) -> None:
        doc, sid = _doc_with_section()
        apply_melody_events(
            doc,
            sid,
            [{"pitch": "C5", "midi": 72, "duration_beats": 1.0, "beat": 0.0}],
            replace=True,
        )
        transpose_composition_to_key(doc, "Bb", new_key_label="Bb major")
        live = {
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_ACTIVE_SECTION_KEY: sid,
        }
        blob = gather_composition_workspace_from_session(live)
        fresh: dict = {}
        apply_composition_workspace_to_session(fresh, blob)
        restored = fresh.get(COMPOSER_ACTIVE_KEY) or {}
        self.assertEqual((restored.get("global") or {}).get("original_key_center"), "Bb")
        chords = expand_entries_to_chords(ordered_sections(restored)[0].get("chords"))
        self.assertTrue(chords[0].startswith("Bb") or chords[0].startswith("A#"))


class TestHumLoopsAndNoNoteTable(unittest.TestCase):
    def test_hum_loops_extend_span_timeline(self) -> None:
        spans = build_chord_span_timeline(["C", "G"], bpm=100, loops=3)
        self.assertEqual(len(spans), 6)
        self.assertEqual(spans[4]["chord"], "C")

    def test_studio_page_removed_note_table_editor(self) -> None:
        import composition_studio_page as page

        self.assertFalse(hasattr(page, "_render_hum_event_editor"))
        src = Path(page.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Edit any note before you use this melody", src)
        self.assertIn("Slight improvements", src)
        self.assertNotIn("Section progression repeats", src)
        self.assertIn("Hum or sing your melody", src)
        self.assertNotIn("Record again", src)
        self.assertIn("render_synced_transport", src)
        self.assertIn("no redundant top transport", src)
        self.assertIn("Count-in", src)
        self.assertIn("count_in_bars", src)


class TestCountInTransport(unittest.TestCase):
    def test_count_in_off_starts_at_zero(self) -> None:
        spans = build_chord_span_timeline(
            ["C", "F"], bpm=120, meter="4/4", loops=1, count_in_bars=0
        )
        self.assertAlmostEqual(spans[0]["start_sec"], 0.0)
        self.assertEqual(active_span_index_at(spans, 0.1), 0)
        self.assertAlmostEqual(count_in_seconds(bpm=120, meter="4/4", bars=0), 0.0)

    def test_one_bar_count_in_4_4(self) -> None:
        cin = count_in_seconds(bpm=120, meter="4/4", bars=1)
        self.assertAlmostEqual(cin, 2.0)  # 4 beats @ 120
        self.assertAlmostEqual(bar_seconds(bpm=120, meter="4/4"), 2.0)
        spans = build_chord_span_timeline(
            ["C", "F", "G", "G7"], bpm=120, meter="4/4", loops=1, count_in_bars=1
        )
        self.assertAlmostEqual(spans[0]["start_sec"], 2.0)
        self.assertEqual(active_span_index_at(spans, 0.5), -1)  # during count-in
        self.assertEqual(active_span_index_at(spans, 1.9), -1)
        self.assertEqual(active_span_index_at(spans, 2.1), 0)  # first chord
        self.assertEqual(spans[0]["chord"], "C")

    def test_one_bar_count_in_3_4_and_6_8(self) -> None:
        cin34 = count_in_seconds(bpm=120, meter="3/4", bars=1)
        self.assertAlmostEqual(cin34, 1.5)  # 3 beats @ 120
        spans34 = build_chord_span_timeline(
            ["C", "G"], bpm=120, meter="3/4", loops=1, count_in_bars=1
        )
        self.assertAlmostEqual(spans34[0]["start_sec"], cin34)
        self.assertEqual(active_span_index_at(spans34, cin34 / 2), -1)

        cin68 = count_in_seconds(bpm=120, meter="6/8", bars=1)
        # meter_timing: 6/8 bar = 2 * (60/bpm) at this BPM
        self.assertAlmostEqual(cin68, bar_seconds(bpm=120, meter="6/8"))
        spans68 = build_chord_span_timeline(
            ["Dm", "A"], bpm=120, meter="6/8", loops=1, count_in_bars=1
        )
        self.assertAlmostEqual(spans68[0]["start_sec"], cin68)
        self.assertEqual(active_span_index_at(spans68, cin68 * 0.25), -1)
        self.assertEqual(active_span_index_at(spans68, cin68 + 0.05), 0)

    def test_repeats_do_not_repeat_count_in(self) -> None:
        spans = build_chord_span_timeline(
            ["C", "G"], bpm=120, meter="4/4", loops=3, count_in_bars=1
        )
        self.assertEqual(len(spans), 6)
        # Only one count-in: first chord at 2.0, then continuous
        self.assertAlmostEqual(spans[0]["start_sec"], 2.0)
        self.assertAlmostEqual(spans[2]["start_sec"], 6.0)  # loop 1 start, no extra count-in
        self.assertAlmostEqual(spans[4]["start_sec"], 10.0)
        for s in spans:
            self.assertAlmostEqual(float(s["count_in_sec"]), 2.0)

    def test_prepend_clicks_lengthens_wav_once(self) -> None:
        doc, sid = _doc_with_section()
        body = generate_preview_wav(doc, section_id=sid, loops=2, include_melody=False, count_in_bars=0)
        with_cin = generate_preview_wav(
            doc, section_id=sid, loops=2, include_melody=False, count_in_bars=1
        )
        self.assertTrue(body and with_cin)
        self.assertGreater(len(with_cin), len(body))
        # Prepending again should add another bar — but generate does once
        again = prepend_count_in_clicks(body, bpm=100, meter="4/4", bars=1)
        self.assertGreater(len(again), len(body))

    def test_transcription_removes_count_in_early_and_downbeat(self) -> None:
        # count-in 2s @ 120bpm; early note at 0.5s; first valid at 2.0s → beat 0
        segs = [
            {
                "kind": "note",
                "start_sec": 0.5,
                "duration_sec": 0.4,
                "midi": 60,
                "midi_f": 60.0,
                "confidence": 0.9,
            },
            {
                "kind": "note",
                "start_sec": 2.0,
                "duration_sec": 0.5,
                "midi": 64,
                "midi_f": 64.0,
                "confidence": 0.9,
            },
            {
                "kind": "note",
                "start_sec": 3.0,
                "duration_sec": 0.5,
                "midi": 67,
                "midi_f": 67.0,
                "confidence": 0.9,
            },
        ]
        events = segments_to_melody_events(
            segs, bpm=120, meter="4/4", key="C", count_in_sec=2.0
        )
        pitched = [e for e in events if not e.get("is_rest")]
        self.assertGreaterEqual(len(pitched), 2)
        self.assertAlmostEqual(float(pitched[0]["beat"]), 0.0, places=1)
        self.assertEqual(int(pitched[0]["midi"]), 64)
        self.assertFalse(pitched[0].get("during_count_in"))
        # Early note dropped but counted
        self.assertEqual(int(pitched[0].get("early_count_in_notes") or 0), 1)


if __name__ == "__main__":
    unittest.main()
