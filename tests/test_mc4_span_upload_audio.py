"""MC4 — upload proof cases A–F on rendered audio (transcription + detected alignment).

A  2-chord span, known start          → confident, chord-by-chord feedback
B  ii–V–I                              → confident, names the 7th→3rd resolution
C  start offset 2.4 s                  → detected near 2.4 s; ±1 beat nudges move by one beat
D  wrong tempo (80 vs 100 BPM)         → low confidence → honest unaligned message
E  partial take (2 of 3 bars)          → after confirming: "covers about 2 of the 3 bars …"
F  two loops                           → both passes scored, the analyzed one is named

Also: alignment nudges re-use the cached transcription (no new pitch detection).
"""

from __future__ import annotations

import unittest
from unittest import mock

from melodic_pattern_engine import build_context
from mission_span_recording_alignment import build_grid, confirm, estimate_upload_alignment, nudge
from mission_span_recording_context import build_timeline
from mission_span_take_evaluation import UNALIGNED_MESSAGE, evaluate_span_take
from mission_span_transcription import transcribe
from tests.mc4_audio_fixtures import II_V_I_GUIDE, TWO_CHORD_TARGETS, phrase_wav

IIVI = ["Gm7", "C7", "Fmaj7"]
BEAT = 0.6  # 100 BPM


def _block(chords, mission="guide_tone_voice_leading"):
    tl = build_timeline([{"chord": c, "bars": 1} for c in chords], meter="4/4")
    return {"mission_id": mission, "mission_label": mission, "practice_key": "F", "chart_key": "F", "timeline": tl,
            "bpm": 100, "meter": "4/4", "level": "Intermediate", "relationship_label": ""}


def _run(block, wav):
    grid = build_grid(block["timeline"], bpm=100, meter="4/4")
    tr = transcribe(wav)
    al = estimate_upload_alignment(tr, grid, chord_pcs=[build_context("F", t["chord"]).chord_pcs
                                                        for t in block["timeline"]])
    return grid, tr, al


class TestUploadCases(unittest.TestCase):
    def test_a_two_chords(self) -> None:
        block = _block(["Gm7", "C7"], "target_each_change")
        _grid, tr, al = _run(block, phrase_wav(TWO_CHORD_TARGETS, bpm=100, lead_silence_sec=0.8, loop_beats=8))
        self.assertAlmostEqual(al.offset_sec, 0.8, delta=0.1)
        self.assertTrue(al.trusted)
        r = evaluate_span_take(block, tr, al)
        self.assertTrue(r["aligned"])
        self.assertGreaterEqual(r["score"], 80)
        self.assertTrue(any("of C7) landed" in t for t in r["what_worked"]))

    def test_b_ii_v_i(self) -> None:
        block = _block(IIVI)
        _grid, tr, al = _run(block, phrase_wav(II_V_I_GUIDE, bpm=100, lead_silence_sec=1.3, loop_beats=12))
        self.assertAlmostEqual(al.offset_sec, 1.3, delta=0.1)
        self.assertTrue(al.trusted)
        r = evaluate_span_take(block, tr, al)
        self.assertGreaterEqual(r["score"], 80)
        self.assertTrue(any("7th-to-3rd resolution" in t for t in r["what_worked"]))

    def test_c_offset_and_nudges(self) -> None:
        block = _block(IIVI)
        grid, _tr, al = _run(block, phrase_wav(II_V_I_GUIDE, bpm=100, lead_silence_sec=2.4, loop_beats=12))
        self.assertAlmostEqual(al.offset_sec, 2.4, delta=0.1)
        self.assertAlmostEqual(nudge(al, grid, beats=1).offset_sec - al.offset_sec, BEAT, places=3)
        self.assertAlmostEqual(al.offset_sec - nudge(al, grid, beats=-1).offset_sec, BEAT, places=3)
        self.assertAlmostEqual(nudge(al, grid, bars=1).offset_sec - al.offset_sec, 4 * BEAT, places=3)

    def test_d_misaligned_is_honest(self) -> None:
        block = _block(IIVI)
        _grid, tr, al = _run(block, phrase_wav(II_V_I_GUIDE, bpm=80, lead_silence_sec=1.0, loop_beats=12))
        self.assertFalse(al.trusted)
        r = evaluate_span_take(block, tr, al)
        self.assertEqual(r["message"], UNALIGNED_MESSAGE)
        self.assertEqual(r["chord_detail"], [])
        self.assertTrue(r["general"])

    def test_e_partial(self) -> None:
        block = _block(IIVI)
        wav = phrase_wav([n for n in II_V_I_GUIDE if n[1] < 8], bpm=100, lead_silence_sec=1.0, loop_beats=8,
                         tail_sec=0.2)
        grid, tr, al = _run(block, wav)
        if not al.trusted:
            self.assertEqual(evaluate_span_take(block, tr, al)["message"], UNALIGNED_MESSAGE)
        # The player lines bar 1 up (as in the UI) and confirms.
        from mission_span_recording_alignment import Alignment

        fixed = confirm(Alignment(1.0, al.confidence, "detected", al.detected_offset_sec))
        r = evaluate_span_take(block, tr, fixed)
        self.assertIn("covers about 2 of the 3 bars, so the Fmaj7 part wasn't available to score", r["message"])
        self.assertEqual([d["chord"] for d in r["chord_detail"] if d.get("notes")], ["Gm7", "C7"])

    def test_f_multi_loop(self) -> None:
        block = _block(IIVI)
        _grid, tr, al = _run(block, phrase_wav(II_V_I_GUIDE, bpm=100, lead_silence_sec=1.0, loop_beats=12, repeat=2))
        self.assertAlmostEqual(al.offset_sec, 1.0, delta=0.1)
        r = evaluate_span_take(block, tr, al)
        self.assertEqual(len(r["loop_scores"]), 2)
        self.assertIn("You played 2 complete passes", r["message"])


class TestNudgeDoesNotRetranscribe(unittest.TestCase):
    def test_nudge_reuses_cached_notes(self) -> None:
        import mission_span_transcription as mst
        from mission_span_recording_context import build_timeline as bt
        from mission_span_take import record_span_take, run_span_take_analysis, set_alignment

        tl = bt([{"chord": c, "bars": 1} for c in IIVI], meter="4/4")
        span = {"mission_id": "guide_tone_voice_leading", "mission_label": "Voice-lead the guide tones",
                "practice_key": "F", "chart_key": "F", "timeline": tl, "bpm": 100, "meter": "4/4",
                "level": "Intermediate", "span_fingerprint": "sf", "song_session": "s"}
        wav = phrase_wav(II_V_I_GUIDE, bpm=100, lead_silence_sec=1.3, loop_beats=12)
        session: dict = {}
        with mock.patch("mission_span_take._song_session", lambda s: "s"):
            take = record_span_take(session, audio_bytes=wav, source="upload", span=span)
            calls = []
            real = mst.transcribe
            with mock.patch.object(mst, "transcribe", side_effect=lambda *a, **k: calls.append(1) or real(*a, **k)):
                first = run_span_take_analysis(session, take, wav)
                grid = build_grid(tl, bpm=100, meter="4/4")
                from mission_span_take import get_alignment

                al = get_alignment(session, take["audio_fp"], span)
                set_alignment(session, take["audio_fp"], nudge(al, grid, beats=1), span)
                second = run_span_take_analysis(session, take, wav)
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(first["alignment"]["offset_sec"], second["alignment"]["offset_sec"])


if __name__ == "__main__":
    unittest.main()
