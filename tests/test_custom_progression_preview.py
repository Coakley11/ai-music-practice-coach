"""Custom Progressions preview: timeline, audio and player markup (pure, no Streamlit)."""

from __future__ import annotations

import io
import re
import unittest
import wave
from pathlib import Path

import custom_progression_preview as cpp

ROOT = Path(__file__).resolve().parents[1]


def tl(sections, order, ts="4/4", bpm=120, **kw):
    return cpp.build_preview_timeline(sections, order, time_signature=ts, bpm=bpm, **kw)


def ev(t):
    return t["events"]


class TestTimeline(unittest.TestCase):
    def test_four_chords_one_bar_each(self):
        s = {"Verse": [{"chord": c, "bars": 1} for c in ("C", "Am", "F", "G")]}
        t = tl(s, ["Verse"])
        self.assertEqual([e["chord"] for e in ev(t)], ["C", "Am", "F", "G"])
        self.assertEqual([e["start_beat"] for e in ev(t)], [0, 4, 8, 12])
        self.assertTrue(all(e["duration_beats"] == 4 for e in ev(t)))
        self.assertEqual([e["bar_in_section"] for e in ev(t)], [0, 1, 2, 3])
        self.assertEqual(t["total_beats"], 16)

    def test_split_measure_c2_f2(self):
        s = {"Verse": [{"chord": "C:2|F:2", "bars": 1}, {"chord": "G", "bars": 1}]}
        e = ev(tl(s, ["Verse"]))
        self.assertEqual(
            [(x["chord"], x["start_beat"], x["duration_beats"]) for x in e],
            [("C", 0, 2), ("F", 2, 2), ("G", 4, 4)],
        )
        self.assertEqual([x["bar_in_section"] for x in e], [0, 0, 1])

    def test_unweighted_split_equal_and_weights(self):
        s = {"Verse": [{"chord": "C|F|G|Am", "bars": 1}, {"chord": "C:3|G:1", "bars": 1}]}
        e = ev(tl(s, ["Verse"]))
        self.assertEqual([x["duration_beats"] for x in e], [1, 1, 1, 1, 3, 1])

    def test_multi_bar_entry_is_one_long_event(self):
        s = {"Verse": [{"chord": "Am", "bars": 4}, {"chord": "F", "bars": 2}]}
        e = ev(tl(s, ["Verse"]))
        self.assertEqual([(x["duration_beats"], x["bar_in_section"]) for x in e], [(16, 0), (8, 4)])

    def test_three_four(self):
        s = {"Verse": [{"chord": "C", "bars": 1}, {"chord": "G|D", "bars": 1}]}
        t = tl(s, ["Verse"], ts="3/4", bpm=90)
        self.assertEqual(t["bpb"], 3)
        self.assertEqual([x["duration_beats"] for x in ev(t)], [3, 1.5, 1.5])
        self.assertAlmostEqual(t["pulse_sec"], 60 / 90)

    def test_six_eight_pulse_rules(self):
        s = {"Verse": [{"chord": "C:3|G:3", "bars": 1}, {"chord": "Am", "bars": 1}]}
        t = tl(s, ["Verse"], ts="6/8", bpm=60)
        self.assertEqual(t["bpb"], 6)
        # bpm is the dotted quarter: bar = 2 s, pulse = 1/3 s
        self.assertAlmostEqual(t["pulse_sec"], 1 / 3)
        spans = cpp.timeline_spans(t)
        self.assertAlmostEqual(spans[0]["end_sec"], 1.0, places=3)
        self.assertAlmostEqual(spans[-1]["end_sec"], 4.0, places=3)

    def test_percent_hold_and_repeat_flag(self):
        s = {"Verse": [{"chord": "Dm", "bars": 1}, {"repeat": True, "bars": 2}, {"chord": "%", "bars": 1}]}
        e = ev(tl(s, ["Verse"]))
        self.assertEqual([x["chord"] for x in e], ["Dm", "Dm", "Dm"])
        self.assertEqual([x["label"] for x in e], ["Dm", "%", "%"])
        self.assertEqual([x["duration_beats"] for x in e], [4, 8, 4])
        self.assertTrue(e[1]["is_repeat"] and not e[1]["is_rest"])

    def test_percent_without_previous_is_rest(self):
        e = ev(tl({"Verse": [{"repeat": True, "bars": 1}]}, ["Verse"]))
        self.assertTrue(e[0]["is_rest"])

    def test_no_chord_is_silent_but_timed(self):
        s = {"Verse": [{"chord": "N.C.", "bars": 1}, {"chord": "C", "bars": 1}]}
        e = ev(tl(s, ["Verse"]))
        self.assertTrue(e[0]["is_rest"])
        self.assertEqual(e[1]["start_beat"], 4)

    def test_hit_token(self):
        e = ev(tl({"Verse": [{"chord": "Bm.hit", "bars": 1}]}, ["Verse"]))
        self.assertEqual(e[0]["chord"], "Bm")
        self.assertTrue(e[0]["hit"])

    def test_empty_section_and_unknown_skipped(self):
        s = {"Verse": [], "Chorus": [{"chord": "C", "bars": 1}]}
        t = tl(s, ["Verse", "Chorus", "Bridge"])
        self.assertEqual([x["section"] for x in ev(t)], ["Chorus"])
        self.assertEqual(ev(t)[0]["start_beat"], 0)
        self.assertEqual(ev(tl({}, [])), [])

    def test_section_repeated_twice(self):
        s = {"Verse": [{"chord": "C", "bars": 1}, {"chord": "G", "bars": 1}]}
        e = ev(tl(s, ["Verse", "Verse"]))
        self.assertEqual([x["start_beat"] for x in e], [0, 4, 8, 12])
        self.assertEqual([x["section_instance"] for x in e], [0, 0, 1, 1])
        self.assertEqual([x["section_label"] for x in e], ["Verse 1", "Verse 1", "Verse 2", "Verse 2"])
        self.assertEqual([x["bar_index"] for x in e], [0, 1, 2, 3])
        self.assertEqual([x["section_start"] for x in e], [True, False, True, False])

    def test_single_occurrence_unnumbered(self):
        e = ev(tl({"Intro": [{"chord": "C", "bars": 1}]}, ["Intro"]))
        self.assertEqual(e[0]["section_label"], "Intro")

    def test_long_song_cap(self):
        s = {"Verse": [{"chord": "C", "bars": 64}]}
        t = tl(s, ["Verse"] * 40, bpm=60, max_seconds=100)
        self.assertTrue(t["truncated"])
        self.assertLessEqual(t["total_beats"] * t["pulse_sec"], 100.0001)
        t2 = tl({"Verse": [{"chord": "C", "bars": 1}] * 50}, ["Verse"] * 50, max_events=100, max_seconds=1e6)
        self.assertEqual(len(ev(t2)), 100)
        self.assertTrue(t2["truncated"])

    def test_spans_seconds_and_shape(self):
        s = {"Verse": [{"chord": "C:2|F:2", "bars": 1}]}
        spans = cpp.timeline_spans(tl(s, ["Verse"], bpm=120))
        self.assertEqual([(x["start_sec"], x["end_sec"]) for x in spans], [(0.0, 1.0), (1.0, 2.0)])
        self.assertTrue(all(x["highlightable"] and x["kind"] == "chord" for x in spans))
        self.assertIn("Verse", spans[0]["now_label"])


class TestOrder(unittest.TestCase):
    def secs(self, *names):
        return {n: [{"chord": "C", "bars": 1}] for n in names}

    def test_default_form(self):
        o = cpp.song_play_order(self.secs("Intro", "Verse", "Chorus", "Bridge", "Outro"))
        self.assertEqual(o, ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"])

    def test_prechorus_and_solo(self):
        o = cpp.song_play_order(self.secs("Verse", "Pre-Chorus", "Chorus", "Solo", "Bridge"))
        self.assertEqual(
            o,
            ["Verse", "Pre-Chorus", "Chorus", "Verse", "Pre-Chorus", "Chorus", "Solo", "Bridge", "Chorus"],
        )

    def test_solo_without_bridge_precedes_final_chorus(self):
        o = cpp.song_play_order(self.secs("Verse", "Chorus", "Solo"))
        self.assertEqual(o, ["Verse", "Chorus", "Verse", "Chorus", "Solo", "Chorus"])

    def test_single_section_plays_once(self):
        self.assertEqual(cpp.song_play_order(self.secs("Verse")), ["Verse"])
        self.assertEqual(cpp.song_play_order(self.secs("Chorus")), ["Chorus"])

    def test_empty(self):
        self.assertEqual(cpp.song_play_order({}), [])
        self.assertEqual(cpp.song_play_order({"Verse": []}), [])

    def test_explicit_arrangement_wins(self):
        o = cpp.song_play_order(self.secs("Verse", "Chorus"), ["Chorus", "Verse", "Verse", "Bridge"])
        self.assertEqual(o, ["Chorus", "Verse", "Verse"])

    def test_full_song_timeline_labels(self):
        s = {"Verse": [{"chord": "C", "bars": 1}], "Chorus": [{"chord": "F", "bars": 2}]}
        o = cpp.song_play_order(s)
        e = ev(tl(s, o))
        self.assertEqual([x["section_label"] for x in e], ["Verse 1", "Chorus 1", "Verse 2", "Chorus 2"])
        self.assertEqual([x["bar_index"] for x in e], [0, 1, 3, 4])
        self.assertEqual(e[-1]["start_beat"], 4 + 8 + 4)


class TestAudio(unittest.TestCase):
    def _wav(self, sections, order, **kw):
        t = tl(sections, order, **kw)
        return t, cpp.render_preview_wav(t)

    def test_wav_length_and_audible(self):
        import numpy as np

        s = {"Verse": [{"chord": "C", "bars": 1}, {"chord": "G7", "bars": 1}]}
        t, data = self._wav(s, ["Verse"], bpm=120)
        with wave.open(io.BytesIO(data)) as w:
            self.assertEqual(w.getnchannels(), 1)
            n, sr = w.getnframes(), w.getframerate()
        self.assertGreaterEqual(n / sr, 4.0)
        self.assertLess(n / sr, 6.0)
        pcm = np.frombuffer(data[44:], dtype="<i2")
        self.assertGreater(int(np.abs(pcm).max()), 5000)

    def test_rest_bar_is_silent_and_chord_bar_is_not(self):
        import numpy as np

        s = {"Verse": [{"chord": "N.C.", "bars": 1}, {"chord": "C", "bars": 1}]}
        t, data = self._wav(s, ["Verse"], bpm=120)
        pcm = np.frombuffer(data[44:], dtype="<i2").astype(float)
        sr = cpp.PREVIEW_SAMPLE_RATE
        self.assertLess(np.abs(pcm[: int(1.9 * sr)]).max(), 50)
        self.assertGreater(np.abs(pcm[int(2.0 * sr): int(2.5 * sr)]).max(), 3000)

    def test_unsaved_edit_changes_audio(self):
        a = {"Verse": [{"chord": "C", "bars": 1}]}
        b = {"Verse": [{"chord": "F#m7", "bars": 1}]}
        self.assertNotEqual(self._wav(a, ["Verse"])[1], self._wav(b, ["Verse"])[1])

    def test_extended_and_slash_chords_voice(self):
        for ch in ("Cmaj13", "G7alt", "D/F#", "Bbm7b5", "Fsus4"):
            self.assertTrue(cpp._voicing(ch, None), ch)

    def test_concert_pitch_bass_register(self):
        self.assertEqual(cpp._bass_midi("C") % 12, 0)
        self.assertEqual(cpp._bass_midi("D/F#") % 12, 6)
        self.assertTrue(36 <= cpp._bass_midi("B") <= 47)


class TestPlayerHtml(unittest.TestCase):
    def _inputs(self, sections, **kw):
        base = {"sections": sections, "key": "C", "time_signature": "4/4", "bpm": 100, "arrangement": None}
        base.update(kw)
        return base

    def test_section_player_chips(self):
        s = {"Verse": [{"chord": "C:2|F:2", "bars": 1}, {"chord": "G", "bars": 1}]}
        html_doc, h, meta = cpp.build_player_html(self._inputs(s), "section", "Verse", 3)
        self.assertEqual(len(re.findall(r'class="cplay-chord-chip"', html_doc)), 3)
        self.assertIn("cplprev-section-3", html_doc)
        self.assertIn("is-grid", html_doc)
        self.assertGreater(h, 150)
        for lab in ("Play", "Stop", "Pause"):
            self.assertIn(lab, html_doc)

    def test_song_player_has_section_headers_in_play_order(self):
        s = {"Verse": [{"chord": "C", "bars": 1}], "Chorus": [{"chord": "F", "bars": 1}]}
        html_doc, h, meta = cpp.build_player_html(self._inputs(s), "song", "", 1)
        heads = re.findall(r'class="cplay-sec" data-sec="\d+">([^<]+)<', html_doc)
        self.assertEqual(heads, ["Verse 1", "Chorus 1", "Verse 2", "Chorus 2"])
        self.assertIn("max-height:220px", html_doc)
        self.assertIn('id="cplprev-song-1-now"', html_doc)
        self.assertLessEqual(h, 150 + 220)

    def test_empty_returns_no_html(self):
        self.assertEqual(cpp.build_player_html(self._inputs({"Verse": []}), "section", "Verse")[0], "")

    def test_mobile_css_four_chips_per_row(self):
        s = {"Verse": [{"chord": "C", "bars": 1}]}
        html_doc = cpp.build_player_html(self._inputs(s), "section", "Verse")[0]
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr))", html_doc)
        self.assertIn("@media (min-width: 640px)", html_doc)

    def test_repeat_chip_shows_percent_label(self):
        s = {"Verse": [{"chord": "C", "bars": 1}, {"repeat": True, "bars": 1}]}
        html_doc = cpp.build_player_html(self._inputs(s), "section", "Verse")[0]
        self.assertIn('<span class="cplay-chip-sym">%</span>', html_doc)


class TestSourceGuards(unittest.TestCase):
    def test_preview_module_never_writes_draft_or_active_identity(self):
        src = (ROOT / "custom_progression_preview.py").read_text(encoding="utf-8")
        for bad in (
            "CPL_ACTIVE_KEY]",
            "save_progression",
            "set_custom_source",
            "queue_custom_active",
            "persist_cpl_draft_state",
            "generate_backing_track",
        ):
            self.assertNotIn(bad, src, bad)
        self.assertEqual(src.count("session_state[PREVIEW_STATE_KEY] ="), 1)


if __name__ == "__main__":
    unittest.main()
