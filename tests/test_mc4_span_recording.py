"""MC4 — optional recording + Upload Analysis for 2- and 3-chord Missions.

Context block, timeline, alignment, assignment/coverage, Mission evaluators, naming for
transposing instruments, Practice Key re-keying, song isolation, envelope v1/v2 and the
Practice Log snapshot. Synthetic note lists keep these fast and exact; the real-audio upload
cases (transcription + detected alignment) live in test_mc4_span_upload_audio.py.
"""

from __future__ import annotations

import copy
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

import mission_span_recording_context as src
from mission_practice_context import (
    MISSION_RECORDING_SEAL_KEY,
    MissionPracticeContext,
    build_mission_practice_context,
    enrich_analysis_context,
    recording_context_stale_warning,
    seal_recording_context,
)
from mission_span_recording_alignment import (
    SOURCE_ADJUSTED,
    SOURCE_CONFIRMED,
    SOURCE_DETECTED,
    SOURCE_LIVE,
    Alignment,
    assign_events,
    build_grid,
    confirm,
    coverage,
    live_alignment,
    nudge,
    reset,
)
from mission_span_take import (
    SPAN_TAKE_KEY,
    analysis_span_take,
    get_alignment,
    record_span_take,
    restore_span_take_from_envelope,
    set_alignment,
    span_take_for_envelope,
)
from mission_span_take_evaluation import UNALIGNED_MESSAGE, evaluate_span_take, span_metric_overrides
from tests.mc4_audio_fixtures import II_V_I_GUIDE, TWO_CHORD_TARGETS, midi

SCOPE_KEY = "_improv_mission_target_scope_choice"
IIVI = ["Gm7", "C7", "Fmaj7"]

# One-chord context fingerprint for a fixed session, captured on b9b408b0 (pre-MC4).
GOLDEN_SESSION = {
    "improv_active_mission": "Target tone drill",
    "improv_mission_chord_options": ["Bm", "Em", "G", "A"] * 2,
    "ii_selected_chord": "A",
    "ii_selected_section": "Chorus",
    "ii_selected_chord_index": 7,
    "backing_track_bpm": 92,
    "improv_style_meta": {"style": "Pop", "groove": "Pop groove", "bpm": 92},
    "song": "Golden",
    "instrument": "Clarinet",
}
GOLDEN_FINGERPRINT = "ddc53b05178d7db5d70bdb90"
GOLDEN_KEYS = [
    "backing_groove", "backing_style", "chord", "context_fingerprint", "count_in_bars", "display_key",
    "evaluation_focus", "loop", "loops", "meter", "mission_pick", "mission_type", "pick_key",
    "recording_association", "score_against_example", "sealed_at", "song_title", "tempo_bpm", "version", "volume",
]


def _span(chords, bars=None, *, span_id="sp1", section="A", rel="ii–V–I in F"):
    bars = bars or [1] * len(chords)
    return SimpleNamespace(
        span_id=span_id,
        section_label=section,
        chords=tuple(chords),
        raw_events=tuple(SimpleNamespace(chord=c, bars=b) for c, b in zip(chords, bars)),
        relationship="ii_v_i",
        relationship_label=rel,
        key_center="F",
    )


class _World:
    """Patches the live song / Practice Key / chart key resolvers for one test."""

    def __init__(self, *, song="song-A", key="F", chart_key=""):
        self.song, self.key, self.chart_key = song, key, chart_key

    def __enter__(self):
        self._stack = ExitStack()
        self._stack.enter_context(mock.patch.object(src, "_song_session", lambda s: self.song))
        self._stack.enter_context(mock.patch.object(src, "_live_practice_key", lambda s: self.key))
        self._stack.enter_context(mock.patch.object(src, "_live_chart_key", lambda s: self.chart_key or self.key))
        return self

    def __exit__(self, *exc):
        self._stack.close()


def _stage(session, chords=IIVI, bars=None, *, mission_id="guide_tone_voice_leading",
           label="Voice-lead the guide tones", key="F", chart_key="", chart=None, instrument="Piano",
           level="Intermediate", scope=None):
    session[SCOPE_KEY] = scope or ("span3" if len(chords) == 3 else "span2")
    session.setdefault("instrument", instrument)
    return src.store_span_recording_base(
        session, span=_span(chords, bars), scope=session[SCOPE_KEY], mission_id=mission_id, mission_label=label,
        concert_key=key, chart_key=chart_key or key, chart_chords=chart or chords, instrument=instrument,
        level=level, style="Jazz", focus="", example=None,
    )


def _block(chords=IIVI, *, mission_id="guide_tone_voice_leading", key="F", chart_key="", chart=None,
           level="Intermediate", bpm=100, meter="4/4", bars=None, instrument="Piano"):
    session: dict = {}
    with _World(key=key, chart_key=chart_key):
        _stage(session, chords, bars, mission_id=mission_id, label=mission_id, key=key, chart_key=chart_key,
               chart=chart, level=level, instrument=instrument)
        return src.build_span_block(session, bpm=bpm, meter=meter, loops=2, count_in_bars=1)


def _transcription(notes, *, bpm=100, offset=1.0, loop_beats=12, repeat=1, tail=0.3):
    beat = 60.0 / bpm
    out = []
    for r in range(repeat):
        for p, start, dur in notes:
            out.append({"t": offset + (r * loop_beats + start) * beat, "dur": dur * beat * 0.9,
                        "midi": midi(p) if isinstance(p, str) else p, "cents": 0})
    return {"fingerprint": "fp-test", "notes": out, "duration": offset + repeat * loop_beats * beat + tail,
            "onsets": [n["t"] for n in out], "beats": [], "tempo": float(bpm)}


CONFIRMED = Alignment(1.0, 1.0, SOURCE_CONFIRMED, 1.0)


# --------------------------------------------------------------------------- context block


class TestSpanContextBlock(unittest.TestCase):
    def test_single_chord_context_unchanged(self) -> None:
        ctx = build_mission_practice_context(dict(GOLDEN_SESSION))
        self.assertIsNone(ctx.span)
        self.assertEqual(ctx.context_fingerprint, GOLDEN_FINGERPRINT)
        self.assertEqual(sorted(ctx.to_dict()), GOLDEN_KEYS)
        self.assertNotIn("span", ctx.to_dict())

    def test_span_block_ignored_without_span_scope(self) -> None:
        session = dict(GOLDEN_SESSION)
        with _World(song="song-A"):
            _stage(session)
            session[SCOPE_KEY] = "single"
            ctx = build_mission_practice_context(session)
        self.assertIsNone(ctx.span)
        self.assertEqual(ctx.context_fingerprint, GOLDEN_FINGERPRINT)

    def test_span_context_carries_exact_timeline(self) -> None:
        session = dict(GOLDEN_SESSION)
        with _World(song="song-A"):
            _stage(session, IIVI, bars=[2, 1, 2])
            ctx = build_mission_practice_context(session)
        self.assertIsNotNone(ctx.span)
        tl = ctx.span["timeline"]
        self.assertEqual([t["chord"] for t in tl], IIVI)  # never collapses to the selected one-chord "A"
        self.assertEqual([(t["start_bar"], t["bars"]) for t in tl], [(0, 2), (2, 1), (3, 2)])
        self.assertEqual(ctx.span["loop_bars"], 5)
        self.assertEqual(ctx.mission_type, "Voice-lead the guide tones")
        self.assertNotEqual(ctx.context_fingerprint, GOLDEN_FINGERPRINT)
        restored = MissionPracticeContext.from_dict(ctx.to_dict())
        self.assertEqual(restored.span["timeline"], tl)

    def test_span_fingerprint_tracks_identity(self) -> None:
        base = _block()
        for change in ({"bpm": 120}, {"meter": "3/4"}, {"key": "G"}, {"mission_id": "target_each_change"},
                       {"instrument": "Clarinet"}):
            other = _block(**change)
            self.assertNotEqual(base["span_fingerprint"], other["span_fingerprint"], change)
        self.assertEqual(base["span_fingerprint"], _block()["span_fingerprint"])

    def test_stale_reasons(self) -> None:
        sealed, live = _block(), _block(bpm=120, key="G")
        reasons = src.span_stale_reasons(sealed, live)
        self.assertTrue(any("Practice Key changed from F to G" in r for r in reasons))
        self.assertTrue(any("tempo changed from 100 to 120" in r for r in reasons))
        self.assertEqual(src.span_stale_reasons(sealed, copy.deepcopy(sealed)), [])
        self.assertEqual(src.span_stale_reasons(sealed, None), ["the span Mission is no longer selected"])

    def test_summary_shows_written_key_for_transposing_chart(self) -> None:
        rows = dict(src.span_summary_rows(_block(chart_key="G", chart=["Am7", "D7", "Gmaj7"], instrument="Clarinet")))
        self.assertEqual((rows["Practice key"], rows["Written key"]), ("F major", "G major"))
        self.assertTrue(rows["Span"].startswith("Am7 → D7 → Gmaj7"))

    def test_summary_rows_have_no_internal_ids(self) -> None:
        rows = dict(src.span_summary_rows(_block(bars=[2, 1, 2])))
        self.assertEqual(list(rows), ["Mission", "Span", "Practice key", "Tempo", "Meter", "Length"])
        self.assertIn("→", rows["Span"])
        self.assertEqual(rows["Practice key"], "F major")
        self.assertTrue(rows["Length"].startswith("5 bars"))
        self.assertNotIn("sp1", " ".join(rows.values()))


class TestTimeline(unittest.TestCase):
    def test_unequal_durations_and_meter(self) -> None:
        tl = src.build_timeline([{"chord": "Gm7", "bars": 2}, {"chord": "C7", "bars": 1}, {"chord": "Fmaj7", "bars": 2}],
                                meter="4/4")
        self.assertEqual([(t["start_beat"], t["beats"]) for t in tl], [(0, 8), (8, 4), (12, 8)])
        tl34 = src.retime_timeline(tl, meter="3/4")
        self.assertEqual([(t["start_beat"], t["beats"]) for t in tl34], [(0, 6), (6, 3), (9, 6)])
        self.assertEqual(src.per_bar_chords(tl), ["Gm7", "Gm7", "C7", "Fmaj7", "Fmaj7"])
        geo = src.loop_geometry(tl, bpm=120, meter="4/4")
        self.assertEqual(geo["loop_bars"], 5)
        self.assertAlmostEqual(geo["loop_sec"], 10.0, places=3)

    def test_repeated_chord_kept_in_order(self) -> None:
        tl = src.build_timeline([{"chord": "C", "bars": 1}, {"chord": "F", "bars": 1}, {"chord": "C", "bars": 1}],
                                meter="4/4")
        self.assertEqual(src.per_bar_chords(tl), ["C", "F", "C"])

    def test_count_in_follows_meter(self) -> None:
        b44 = _block(bpm=120, meter="4/4")
        b34 = _block(bpm=120, meter="3/4")
        self.assertAlmostEqual(b44["count_in_sec"], 2.0, places=3)
        self.assertAlmostEqual(b34["count_in_sec"], 1.5, places=3)


# --------------------------------------------------------------------------- Practice Key / song / instrument


class TestSpanIdentity(unittest.TestCase):
    def test_practice_key_change_rekeys_span(self) -> None:
        session: dict = {}
        with _World(key="F"):
            _stage(session, IIVI)
        with _World(key="G"):
            block = src.build_span_block(session, bpm=100, meter="4/4", loops=1, count_in_bars=1)
        self.assertEqual([t["chord"] for t in block["timeline"]], ["Am7", "D7", "Gmaj7"])
        self.assertEqual(block["practice_key"], "G")
        self.assertEqual(block["rekeyed_from"], "F")

    def test_other_song_span_is_never_used(self) -> None:
        session: dict = {}
        with _World(song="song-A"):
            _stage(session, IIVI)
        with _World(song="song-B"):
            self.assertIsNone(src.current_span_base(session))
            self.assertIsNone(src.build_span_block(session, bpm=100, meter="4/4", loops=1, count_in_bars=1))

    def test_song_a_take_does_not_analyze_song_b(self) -> None:
        session: dict = {"analysis_recording_type": "Practice take"}
        block = _block()
        session[SPAN_TAKE_KEY] = {"version": 1, "span": block, "source": "upload", "audio_fp": "fpA",
                                  "song_session": "song-A"}
        with _World(song="song-A"):
            self.assertIsNotNone(analysis_span_take(session, "fpA"))
        with _World(song="song-B"):
            self.assertIsNone(analysis_span_take(session, "fpA"))

    def test_transposing_chart_spelling(self) -> None:
        block = _block(chart_key="G")  # B♭ clarinet: concert F → written G
        self.assertEqual([t["chord"] for t in block["timeline"]], IIVI)
        self.assertEqual([t["chart_chord"] for t in block["timeline"]], ["Am7", "D7", "Gmaj7"])


# --------------------------------------------------------------------------- alignment / assignment / coverage


class TestAlignment(unittest.TestCase):
    def setUp(self) -> None:
        self.block = _block()
        self.grid = build_grid(self.block["timeline"], bpm=100, meter="4/4")

    def test_live_alignment_is_authoritative(self) -> None:
        al = live_alignment(count_in_sec=2.4, loop_sec=7.2, loops=2)
        self.assertEqual(al.source, SOURCE_LIVE)
        self.assertTrue(al.trusted)
        self.assertAlmostEqual(al.offset_sec, 2.4)
        self.assertEqual(al.detail["loop_count"], 2)

    def test_nudge_confirm_reset(self) -> None:
        det = Alignment(2.0, 0.5, SOURCE_DETECTED, 2.0)
        self.assertFalse(det.trusted)
        self.assertAlmostEqual(nudge(det, self.grid, beats=1).offset_sec, 2.6, places=3)
        self.assertAlmostEqual(nudge(det, self.grid, bars=-1).offset_sec, 0.0, places=3)  # clamps at 0
        moved = nudge(det, self.grid, beats=-1)
        self.assertEqual(moved.source, SOURCE_ADJUSTED)
        self.assertTrue(moved.trusted)
        self.assertEqual(confirm(det).source, SOURCE_CONFIRMED)
        back = reset(moved)
        self.assertEqual((back.source, back.offset_sec), (SOURCE_DETECTED, 2.0))
        live = live_alignment(count_in_sec=2.4)
        self.assertEqual(reset(nudge(live, self.grid, beats=1)).source, SOURCE_LIVE)

    def test_alignment_stored_per_file_and_span(self) -> None:
        session: dict = {}
        set_alignment(session, "fp1", Alignment(1.2, 1.0, SOURCE_CONFIRMED, 1.0), self.block)
        self.assertAlmostEqual(get_alignment(session, "fp1", self.block).offset_sec, 1.2)
        self.assertIsNone(get_alignment(session, "fp2", self.block))

    def test_assignment_uses_chart_timeline(self) -> None:
        tr = _transcription(II_V_I_GUIDE)
        events = assign_events(tr["notes"], self.grid, offset_sec=1.0)
        self.assertEqual([e.chord for e in events[:5]], ["Gm7"] * 4 + ["C7"])
        self.assertEqual(events[-1].chord, "Fmaj7")
        early = dict(tr["notes"][4], t=tr["notes"][4]["t"] - 0.03)  # ~30 ms early still lands on C7
        self.assertEqual(assign_events([early], self.grid, offset_sec=1.0)[0].chord, "C7")

    def test_coverage_statuses(self) -> None:
        tr = _transcription(II_V_I_GUIDE)
        ev = assign_events(tr["notes"], self.grid, offset_sec=1.0)
        self.assertEqual(coverage(tr["duration"], self.grid, offset_sec=1.0, events=ev).status, "complete")
        two = _transcription(II_V_I_GUIDE, repeat=2)
        ev2 = assign_events(two["notes"], self.grid, offset_sec=1.0)
        cov2 = coverage(two["duration"], self.grid, offset_sec=1.0, events=ev2)
        self.assertEqual((cov2.status, cov2.complete_loops), ("multi", 2))
        part = _transcription([n for n in II_V_I_GUIDE if n[1] < 8], loop_beats=8, tail=0.1)
        ev3 = assign_events(part["notes"], self.grid, offset_sec=1.0)
        cov3 = coverage(part["duration"], self.grid, offset_sec=1.0, events=ev3)
        self.assertEqual((cov3.status, cov3.covered_chords, cov3.missing_chords), ("short", [0, 1], [2]))
        longer = _transcription(II_V_I_GUIDE, tail=3.0)
        ev4 = assign_events(longer["notes"], self.grid, offset_sec=1.0)
        self.assertEqual(coverage(longer["duration"], self.grid, offset_sec=1.0, events=ev4).status, "long")


# --------------------------------------------------------------------------- evaluation


BAD_LINE = [("F#4", 0, 1), ("C#5", 1, 1), ("G#4", 2, 1), ("D#4", 3, 1), ("F#4", 4, 1), ("C#5", 5, 1),
            ("G#4", 6, 1), ("D#4", 7, 1), ("F#4", 8, 2), ("C#5", 10, 2)]
GOOD_LINES = {
    "guide_tone_voice_leading": II_V_I_GUIDE,
    "target_each_change": II_V_I_GUIDE,
    "ii_v_i_resolution": II_V_I_GUIDE,
    "chord_tones_each_chord": II_V_I_GUIDE,
    "common_tone_voice_leading": II_V_I_GUIDE,
    "one_common_scale": II_V_I_GUIDE,
    "resolve_to_third": [("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 1), ("E4", 4, 1), ("G4", 5, 1),
                         ("Bb4", 6, 1), ("G4", 7, 1), ("A4", 8, 2), ("C5", 10, 2)],
    "approach_next_chord": [("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 1), ("E4", 4, 1), ("G4", 5, 1),
                            ("Bb4", 6, 1), ("G#4", 7, 1), ("A4", 8, 2), ("C5", 10, 2)],
    "enclose_next_target": [("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 0.5), ("D#4", 3.5, 0.5),
                            ("E4", 4, 1), ("G4", 5, 1), ("Bb4", 6, 1), ("Bb4", 7, 0.5), ("G#4", 7.5, 0.5),
                            ("A4", 8, 2), ("C5", 10, 2)],
    "dominant_tension_resolution": [("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 1), ("E4", 4, 1),
                                    ("G4", 5, 1), ("Bb4", 6, 1), ("Db5", 7, 1), ("C5", 8, 2), ("A4", 10, 2)],
    "scalar_runs": [("G4", 0, .5), ("A4", .5, .5), ("Bb4", 1, .5), ("C5", 1.5, .5), ("D5", 2, .5), ("C5", 2.5, .5),
                    ("Bb4", 3, .5), ("A4", 3.5, .5), ("G4", 4, .5), ("F4", 4.5, .5), ("E4", 5, .5), ("F4", 5.5, .5),
                    ("G4", 6, .5), ("A4", 6.5, .5), ("Bb4", 7, .5), ("B4", 7.5, .5), ("C5", 8, .5),
                    ("Bb4", 8.5, .5), ("A4", 9, .5), ("G4", 9.5, .5), ("F4", 10, 2)],
    "syncopated_phrase": [("Bb4", 0.5, 1), ("D5", 1.5, 1), ("F4", 3.5, 1), ("E4", 4.5, 1), ("G4", 5.5, 1),
                          ("Bb4", 7.5, 1), ("A4", 8.5, 1), ("C5", 9.5, 1), ("E5", 10.5, 1)],
    "pentatonic_per_chord": [("G4", 0, 1), ("Bb4", 1, 1), ("C5", 2, 1), ("D5", 3, 1), ("C5", 4, 1), ("D5", 5, 1),
                             ("E5", 6, 1), ("G5", 7, 1), ("F5", 8, 1), ("G5", 9, 1), ("A5", 10, 1), ("C6", 11, 1)],
    "motif_through_changes": [("D5", 0, 1), ("Bb4", 1, 1), ("G4", 2, 2), ("E5", 4, 1), ("C5", 5, 1), ("G4", 6, 2),
                              ("E5", 8, 1), ("C5", 9, 1), ("A4", 10, 2)],
    "rhythm_over_notes": [("Bb4", 0, 1), ("Bb4", 1.5, 0.5), ("F4", 2, 1), ("Bb4", 4, 1), ("Bb4", 5.5, 0.5),
                          ("E4", 6, 1), ("A4", 8, 1), ("A4", 9.5, 0.5), ("E4", 10, 1)],
}
GOOD_LINES["bebop_line"] = GOOD_LINES["scalar_runs"]


class TestMissionEvaluators(unittest.TestCase):
    def _eval(self, mid, notes, *, level="Intermediate", **kw):
        return evaluate_span_take(_block(mission_id=mid, level=level, **kw), _transcription(notes), CONFIRMED)

    def test_every_span_mission_has_an_evaluator_that_separates_good_from_bad(self) -> None:
        from mission_span_engine import SPAN_MISSIONS
        from mission_span_take_evaluation import _EVALUATORS

        self.assertEqual({m.id for m in SPAN_MISSIONS}, set(_EVALUATORS))
        for mid, line in GOOD_LINES.items():
            good = self._eval(mid, line)
            self.assertGreaterEqual(good["score"], 80, (mid, good["try_next"]))
            if mid != "rhythm_over_notes":  # pitch-forgiving by design
                bad = self._eval(mid, BAD_LINE)
                self.assertLess(bad["score"] or 0, 50, (mid, bad["what_worked"]))

    def test_rhythm_mission_forgives_pitch(self) -> None:
        r = self._eval("rhythm_over_notes", BAD_LINE)
        self.assertGreaterEqual(r["score"], 60)

    def test_guide_tone_feedback_names_the_resolution(self) -> None:
        r = self._eval("guide_tone_voice_leading", II_V_I_GUIDE)
        self.assertIn("C7 → Fmaj7: B♭ moved down to A, the 3rd of Fmaj7 — a strong 7th-to-3rd resolution.",
                      r["what_worked"])
        self.assertEqual([d["chord"] for d in r["chord_detail"]], IIVI)

    def test_target_tolerance_by_level(self) -> None:
        late = [("G4", 0, 1), ("Bb4", 1, 1), ("D5", 2, 1), ("F4", 3, 1.75), ("E4", 4.75, 1), ("G4", 6, 2)]
        beg = evaluate_span_take(_block(["Gm7", "C7"], mission_id="target_each_change", level="Beginner"),
                                 _transcription(late, loop_beats=8), CONFIRMED)
        adv = evaluate_span_take(_block(["Gm7", "C7"], mission_id="target_each_change", level="Advanced"),
                                 _transcription(late, loop_beats=8), CONFIRMED)
        self.assertGreater(beg["score"], adv["score"])
        self.assertTrue(any("late" in t for t in beg["try_next"]))

    def test_approach_and_enclosure_spell_neighbours_by_letter(self) -> None:
        a = self._eval("approach_next_chord", GOOD_LINES["approach_next_chord"])
        self.assertIn("G♯ → A (3rd of Fmaj7): chromatic approach from below.", a["what_worked"])
        e = self._eval("enclose_next_target", GOOD_LINES["enclose_next_target"])
        self.assertIn("F and D♯ enclose E (the 3rd of C7).", e["what_worked"])

    def test_common_scale_names_the_collection(self) -> None:
        block = _block(mission_id="one_common_scale")
        block["common_collection"] = {"name": "F major", "pcs": [5, 7, 9, 10, 0, 2, 4], "notes": []}
        r = evaluate_span_take(block, _transcription(II_V_I_GUIDE), CONFIRMED)
        self.assertTrue(any("F major" in t for t in r["what_worked"]))

    def test_motif_repeat_that_clashes_is_not_praised(self) -> None:
        r = self._eval("motif_through_changes", BAD_LINE)
        self.assertFalse(any("adapted to the chord" in t for t in r["what_worked"]))
        self.assertTrue(any("didn't fit the chord" in t for t in r["try_next"] + [c for c in r["what_worked"]])
                        or r["score"] < 50)

    def test_not_graded_as_transcription_of_example(self) -> None:
        # Two different valid lines both satisfy the guide-tone Mission.
        alt = [("F4", 0, 2), ("Bb4", 2, 2), ("Bb4", 4, 2), ("E4", 6, 2), ("A4", 8, 4)]
        self.assertGreaterEqual(self._eval("guide_tone_voice_leading", alt)["score"], 80)
        self.assertGreaterEqual(self._eval("guide_tone_voice_leading", II_V_I_GUIDE)["score"], 80)

    def test_two_chord_span(self) -> None:
        r = evaluate_span_take(_block(["Gm7", "C7"], mission_id="target_each_change"),
                               _transcription(TWO_CHORD_TARGETS, loop_beats=8), CONFIRMED)
        self.assertEqual(r["score"], 100)
        self.assertIn("E (the 3rd of C7) landed right on the change.", r["what_worked"])

    def test_unaligned_take_never_gets_chord_by_chord_claims(self) -> None:
        low = Alignment(1.0, 0.5, SOURCE_DETECTED, 1.0)
        r = evaluate_span_take(_block(), _transcription(II_V_I_GUIDE), low)
        self.assertEqual(r["message"], UNALIGNED_MESSAGE)
        self.assertFalse(r["aligned"])
        self.assertEqual((r["what_worked"], r["try_next"], r["chord_detail"]), ([], [], []))
        self.assertIsNone(r["score"])
        self.assertTrue(r["general"])
        self.assertEqual(span_metric_overrides(r), {})

    def test_partial_and_multi_loop_messages(self) -> None:
        part = _transcription([n for n in II_V_I_GUIDE if n[1] < 8], loop_beats=8, tail=0.1)
        r = evaluate_span_take(_block(), part, CONFIRMED)
        self.assertIn("covers about 2 of the 3 bars, so the Fmaj7 part wasn't available to score", r["message"])
        two = evaluate_span_take(_block(), _transcription(II_V_I_GUIDE, repeat=2), CONFIRMED)
        self.assertEqual(len(two["loop_scores"]), 2)
        self.assertIn("You played 2 complete passes", two["message"])
        self.assertIn(two["loop_analyzed"], (1, 2))

    def test_transposing_instrument_feedback_uses_written_names(self) -> None:
        clar = evaluate_span_take(_block(chart_key="G", chart=["Am7", "D7", "Gmaj7"]),
                                  _transcription(II_V_I_GUIDE), CONFIRMED)
        self.assertIn("D7 → Gmaj7: C moved down to B, the 3rd of Gmaj7 — a strong 7th-to-3rd resolution.",
                      clar["what_worked"])
        sax = evaluate_span_take(_block(chart_key="D", chart=["Em7", "A7", "Dmaj7"]),
                                 _transcription(II_V_I_GUIDE), CONFIRMED)
        self.assertIn("A7 → Dmaj7: G moved down to F♯, the 3rd of Dmaj7 — a strong 7th-to-3rd resolution.",
                      sax["what_worked"])
        self.assertEqual(clar["score"], sax["score"])  # analysis is in concert pitch
        for inst in ("Guitar", "Piano"):
            r = evaluate_span_take(_block(instrument=inst), _transcription(II_V_I_GUIDE), CONFIRMED)
            self.assertIn("C7 → Fmaj7: B♭ moved down to A, the 3rd of Fmaj7 — a strong 7th-to-3rd resolution.",
                          r["what_worked"])

    def test_chord_tones_spelled_by_degree_in_written_key(self) -> None:
        block = _block(["C#m7b5", "F#7", "Bm"], key="Bm", chart_key="C#m", chart=["D#m7b5", "G#7", "C#m"])
        line = [("E4", 0, 1), ("G4", 1, 1), ("B4", 2, 1), ("B4", 3, 1), ("A#4", 4, 1), ("C#5", 5, 1),
                ("E5", 6, 1), ("E4", 7, 1), ("D4", 8, 2), ("F#4", 10, 2)]
        r = evaluate_span_take(block, _transcription(line, loop_beats=12), CONFIRMED)
        self.assertIn("D♯m7♭5 → G♯7: C♯ moved down to B♯, the 3rd of G♯7 — a strong 7th-to-3rd resolution.",
                      r["what_worked"])

    def test_short_take_wording(self) -> None:
        near_end = _transcription(II_V_I_GUIDE, tail=-0.6)  # stops one beat before the end of Fmaj7
        r = evaluate_span_take(_block(), near_end, CONFIRMED)
        self.assertIn("covers almost all of the 3 bars — it ends during Fmaj7", r["message"])

    def test_metric_overrides_are_per_chord(self) -> None:
        r = self._eval("guide_tone_voice_leading", II_V_I_GUIDE)
        ov = span_metric_overrides(r)
        self.assertEqual(set(ov), {"chord_tone_accuracy", "guide_tone_usage"})
        self.assertGreater(ov["chord_tone_accuracy"], 80)


# --------------------------------------------------------------------------- takes, seal, envelope, snapshot


class TestSpanTakeLifecycle(unittest.TestCase):
    def test_one_chord_take_records_nothing(self) -> None:
        session = {"_mission_span_take": {"stale": True}, "other": 1}
        self.assertIsNone(record_span_take(session, audio_bytes=b"abc", source="live"))
        self.assertNotIn(SPAN_TAKE_KEY, session)
        self.assertEqual(session["other"], 1)

    def test_live_take_seals_span_and_live_alignment(self) -> None:
        block = _block()
        session: dict = {}
        with _World():
            take = record_span_take(session, audio_bytes=b"live-take", source="live", span=block)
        self.assertEqual(take["alignment"]["source"], SOURCE_LIVE)
        self.assertAlmostEqual(take["alignment"]["offset_sec"], block["count_in_sec"])
        self.assertAlmostEqual(get_alignment(session, take["audio_fp"], block).offset_sec, block["count_in_sec"])

    def test_seal_and_stale_warning_for_span(self) -> None:
        session = dict(GOLDEN_SESSION)
        with _World():
            _stage(session)
            seal_recording_context(session, association="test")
            self.assertTrue(MissionPracticeContext.from_dict(session[MISSION_RECORDING_SEAL_KEY]).span)
            self.assertEqual(recording_context_stale_warning(session), "")
            session["backing_track_bpm"] = 140
            warn = recording_context_stale_warning(session)
        self.assertIn("tempo changed", warn)
        self.assertNotIn("chord changed", warn.lower())

    def test_one_chord_seal_cannot_stand_in_for_span(self) -> None:
        session = dict(GOLDEN_SESSION)
        with _World():
            seal_recording_context(session, association="test")
            _stage(session)
            warn = recording_context_stale_warning(session)
        self.assertIn("single-chord Mission", warn)

    def test_enrich_analysis_context_uses_span_not_selected_chord(self) -> None:
        session = dict(GOLDEN_SESSION)
        block = _block()
        session[SPAN_TAKE_KEY] = {"version": 1, "span": block, "source": "live", "audio_fp": "fpX",
                                  "song_session": "song-A"}
        session["_analysis_current_audio_fp"] = "fpX"
        with _World():
            out = enrich_analysis_context(session, {"sections": {"Chorus": ["A"]}})
        self.assertEqual(out["mission_chord"], "")
        self.assertEqual(out["mission_span_chords"], IIVI)
        self.assertEqual(out["target_chords"], IIVI)
        self.assertEqual(out["sections"], {"A": IIVI})

    def test_envelope_v2_round_trip_and_v1_compat(self) -> None:
        from mission_pending_upload_analysis import build_pending_upload_envelope

        block = _block()
        session = dict(GOLDEN_SESSION)
        with _World():
            take = record_span_take(session, audio_bytes=b"take-1", source="upload", span=block)
            set_alignment(session, take["audio_fp"], Alignment(1.4, 1.0, SOURCE_ADJUSTED, 1.0), block)
            env = build_pending_upload_envelope(session, dry_asset={"fingerprint": take["audio_fp"], "recording_id": "r1"})
        self.assertEqual(env["schema_version"], 2)
        self.assertEqual(env["mission"]["span_chords"], IIVI)
        self.assertEqual(env["mission"]["chord_symbol"], "")
        self.assertEqual(env["span_take"]["alignment"]["source"], SOURCE_ADJUSTED)

        fresh: dict = {}
        self.assertTrue(restore_span_take_from_envelope(fresh, env))
        self.assertAlmostEqual(get_alignment(fresh, take["audio_fp"], block).offset_sec, 1.4)
        self.assertEqual(span_take_for_envelope(fresh, take["audio_fp"])["span"]["timeline"], block["timeline"])

        one_chord = dict(GOLDEN_SESSION)
        env1 = build_pending_upload_envelope(one_chord, dry_asset={"fingerprint": "zz", "recording_id": "r2"})
        self.assertEqual(env1["schema_version"], 1)
        self.assertNotIn("span_take", env1)
        stale = {SPAN_TAKE_KEY: {"span": block, "audio_fp": "old"}}
        self.assertFalse(restore_span_take_from_envelope(stale, env1))  # v1 → a one-chord take
        self.assertNotIn(SPAN_TAKE_KEY, stale)

    def test_alignment_choice_written_back_to_envelope(self) -> None:
        from mission_pending_upload_analysis import PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY, build_pending_upload_envelope
        from mission_span_take import sync_alignment_to_envelope

        block = _block()
        session = dict(GOLDEN_SESSION)
        with _World():
            take = record_span_take(session, audio_bytes=b"take-2", source="upload", span=block)
            env = build_pending_upload_envelope(session, dry_asset={"fingerprint": take["audio_fp"], "recording_id": "r3"})
        session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY] = env
        session["creative_workspace_state"] = {PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY: copy.deepcopy(env)}
        set_alignment(session, take["audio_fp"], Alignment(2.2, 0.6, SOURCE_CONFIRMED, 1.6), block)
        self.assertTrue(sync_alignment_to_envelope(session, take["audio_fp"]))
        for e in (session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY],
                  session["creative_workspace_state"][PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY]):
            self.assertEqual((e["span_take"]["alignment"]["source"], e["span_take"]["alignment"]["offset_sec"]),
                             (SOURCE_CONFIRMED, 2.2))
        fresh: dict = {}
        restore_span_take_from_envelope(fresh, session[PENDING_UPLOAD_ANALYSIS_ENVELOPE_KEY])
        self.assertEqual(get_alignment(fresh, take["audio_fp"], block).source, SOURCE_CONFIRMED)
        self.assertFalse(sync_alignment_to_envelope(session, "another-file"))

    def test_practice_log_snapshot_has_durable_span(self) -> None:
        from recording_analysis_context import build_analysis_context_snapshot, coach_emphasis_notes

        block = _block(bars=[2, 1, 2])
        session = dict(GOLDEN_SESSION, analysis_recording_type="Mission Recording",
                       analysis_mission_parameters={"chord": "A", "mission_type": "Target tone drill"})
        session[SPAN_TAKE_KEY] = {"version": 1, "span": block, "source": "live", "audio_fp": "fpS",
                                  "song_session": "song-A"}
        session["_analysis_current_audio_fp"] = "fpS"
        with _World():
            snap = build_analysis_context_snapshot(session, association="test")
        self.assertEqual(snap["mission_type"], "guide_tone_voice_leading")
        span = snap["mission_span"]
        self.assertEqual([t["chord"] for t in span["timeline"]], IIVI)
        self.assertEqual([t["bars"] for t in span["timeline"]], [2, 1, 2])
        self.assertEqual((span["practice_key"], span["bpm"], span["meter"]), ("F", 100, "4/4"))
        self.assertNotEqual(snap["mission_parameters"].get("chord"), "A")
        self.assertTrue(any("Mission span:" in n for n in coach_emphasis_notes(snap)))


if __name__ == "__main__":
    unittest.main()
