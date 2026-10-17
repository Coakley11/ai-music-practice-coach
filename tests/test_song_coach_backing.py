"""Song-Aware Coaching S5 — practice loops from the shared backing arranger.

Three layers of evidence that a loop plays the right music:

1. **Note level** — a test-only spy on the arranger's tone generator records every note it
   actually renders in the loop's pass: bass on each chord's downbeat (slash basses included),
   comping only from the sounding chord, every chord change present, none extra.
2. **Signal level** — the delivered WAV: exact length, onsets on the meter's pulse grid,
   several onsets per bar (a groove, not one held chord), no silent beat, no clipping, a
   continuous loop wrap, and the downbeat bass read back from the mix.
3. **Browser** — the in-page transport in real Chromium (skipped when Playwright is absent).
"""

from __future__ import annotations

import base64
import dataclasses
import json
import re
import unittest
from fractions import Fraction
from functools import lru_cache
from unittest import mock

import numpy as np

from music_theory import normalize_chord_for_theory
from song_coach_backing import (
    LOOP_SAMPLE_RATE,
    REFUSAL_EMPTY,
    REFUSAL_SPLIT_BAR,
    REFUSAL_VOICING,
    check_loop,
    clear_loop_cache,
    decode_wav,
    loop_events,
    loop_request,
    render_loop,
)
from song_coach_context import SOURCE_CUSTOM, build_song_coach_context
from song_coach_harmony import HOLDABLE, chord_facts, note_use
from song_coach_player import loop_bars, player_html
from song_coach_scope import build_scope, harmony_events
from song_coach_state import LOOP_RANGE_CHALLENGE, LOOP_RANGE_SELECTION, CoachState, with_loop
from tests import audio_checks as A
from tests.test_song_coach_examples import _plan, _scope

TRIAL = {"Verse": ["E", "E", "C#m7", "A", "A", "B7", "E", "E"]}
SLOW_BLUES = {"Blues": ["C7", "F7", "C7", "C7", "F7", "F7", "C7", "C7", "G7", "F7", "C7", "G7"]}
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
# (case, arranger style, tempo) — contrasting meters, feels, slash basses and sources
MATERIAL = {
    "perfect": ("Ballad", 63),
    "ipanema": ("Bossa nova", 128),
    "hotel": ("Rock groove", 74),
    "blues": ("Blues groove", 96),
    "custom": ("Pop groove", 92),
    "composition": ("Pop groove", 100),
    "shuffle": ("Blues groove", 60),  # 12/8 slow blues
}


@lru_cache(maxsize=None)
def _material(name: str):
    if name == "custom":
        ctx = build_song_coach_context(identity="custom|custom::trial", source_kind=SOURCE_CUSTOM,
                                       concert_sections=TRIAL, concert_key="E", style="pop", meter="4/4",
                                       instrument="Piano")
        return ctx, build_scope(ctx, "verse")
    if name == "shuffle":
        ctx = build_song_coach_context(identity="custom|custom::shuffle", source_kind=SOURCE_CUSTOM,
                                       concert_sections=SLOW_BLUES, concert_key="C", style="blues", meter="12/8",
                                       instrument="Piano")
        return ctx, build_scope(ctx, "blues")
    return _scope(name)


def _request(name: str, bpm: int | None = None, **kw):
    ctx, scope = _material(name)
    style, tempo = MATERIAL[name]
    return loop_request(ctx, scope, start_bar=kw.pop("start_bar", scope.start_bar),
                        end_bar=kw.pop("end_bar", scope.end_bar), bpm=bpm or tempo, style=style, **kw)


def _spy_render(request):
    """Render ``request`` fresh and return (loop, notes in the loop's pass) — every tone the
    arranger synthesizes (bass, pads …) and, where present, its piano comp voice."""
    import backing_audio

    clear_loop_cache()
    calls = []
    orig = backing_audio._add_tone

    def spy(audio, sr, start, dur, midi, vol, wave_type="sine"):
        calls.append((float(start), float(dur), int(midi), str(wave_type)))
        return orig(audio, sr, start, dur, midi, vol, wave_type)

    patches = [mock.patch.object(backing_audio, "_add_tone", spy)]
    try:
        import backing_keys_voice

        orig_piano = backing_keys_voice.add_piano_note

        def piano(bus, sr, start, held, midi, gain, velocity):
            calls.append((float(start), float(held), int(midi), "piano"))
            return orig_piano(bus, sr, start, held, midi, gain, velocity)

        patches.append(mock.patch.object(backing_keys_voice, "add_piano_note", piano))
    except ImportError:  # an arranger without the piano voice
        pass
    for p in patches:
        p.start()
    try:
        loop = render_loop(request)
    finally:
        for p in patches:
            p.stop()
    lo, n = loop.loop_seconds, loop.loop_seconds  # the second pass is the loop
    edge = 0.08  # humanised notes may start a few milliseconds before their beat
    notes = [(s - lo, d, m, w) for s, d, m, w in calls if lo - edge <= s < lo + n - edge]
    clear_loop_cache()
    return loop, notes


def _event_at(loop, t, early: float = 0.06):
    """The chord sounding at ``t`` — a note up to ``early`` seconds before a change belongs to it."""
    t = (t + early) % loop.loop_seconds
    return next((ev for ev in loop.events if ev.start - 1e-6 <= t < ev.end - 1e-6), loop.events[-1])


def _beat(loop):
    meter = loop.request.meter
    return loop.bar_seconds / {"6/8": 2, "12/8": 4}.get(meter, int(meter.split("/")[0]) if "/" in meter else 4)


# --------------------------------------------------------------------------- timelines


class TestTimeline(unittest.TestCase):
    def test_events_follow_the_coaching_scope(self) -> None:
        for name in MATERIAL:
            req = _request(name)
            ctx, scope = _material(name)
            bar = render_loop(req).bar_seconds
            want = [e for e in harmony_events(list(scope.bars), meter=scope.meter, first_bar=scope.start_bar)]
            got = loop_events(req)
            with self.subTest(song=name):
                self.assertEqual([e.chord for e in got], [w.chord for w in want])
                self.assertEqual([e.bar for e in got], [w.start_bar for w in want])
                for e, w in zip(got, want):
                    self.assertAlmostEqual(e.start, w.start_beat / scope.beats_per_bar * bar, places=5)
                self.assertAlmostEqual(got[-1].end, req.bar_count * bar, places=5)

    def test_slash_basses_are_the_expected_bass(self) -> None:
        perfect = {e.chord: NAMES[e.bass_pc] for e in loop_events(_request("perfect"))}
        self.assertEqual(perfect["D/F#"], "F#")
        hotel = {e.chord: NAMES[e.bass_pc] for e in loop_events(_request("hotel"))}
        self.assertEqual(hotel["F#7/A#"], "Bb")

    def test_loop_bars_for_challenge_or_selection(self) -> None:
        plan = _plan("perfect")
        ch = plan.challenges[0]
        self.assertEqual(loop_bars(plan, ch, LOOP_RANGE_CHALLENGE), (ch.loop_start, ch.loop_end))
        self.assertEqual(loop_bars(plan, ch, LOOP_RANGE_SELECTION), (plan.start_bar, plan.end_bar))
        req = _request("perfect", start_bar=5, end_bar=8)
        self.assertEqual((req.start_bar, req.end_bar, req.bars), (5, 8, ("Cadd9", "Cadd9", "D/F#", "D/F#")))


# --------------------------------------------------------------------------- identity / staleness


class TestIdentity(unittest.TestCase):
    def test_signature_changes_with_everything_that_changes_the_music(self) -> None:
        base = _request("perfect")
        variants = [
            dataclasses.replace(base, bpm=base.bpm + 1),
            dataclasses.replace(base, concert_key="A"),
            dataclasses.replace(base, fingerprint="other-chart"),
            dataclasses.replace(base, identity="catalog|Other"),
            dataclasses.replace(base, bars=base.bars[:-1] + ("D",)),
            dataclasses.replace(base, start_bar=2),
            dataclasses.replace(base, style="Pop groove"),
            dataclasses.replace(base, level="Advanced"),
            dataclasses.replace(base, meter="3/4"),
        ]
        sigs = {v.signature() for v in variants}
        self.assertEqual(len(sigs), len(variants))
        self.assertNotIn(base.signature(), sigs)
        self.assertEqual(base.signature(), _request("perfect").signature(), "deterministic")
        self.assertEqual(dataclasses.replace(base, bpm=70).range_key(), base.range_key(), "tempo keeps the range")
        self.assertNotEqual(dataclasses.replace(base, concert_key="A").range_key(), base.range_key())

    def test_rendering_is_deterministic_and_cached(self) -> None:
        clear_loop_cache()
        a = render_loop(_request("blues"))
        self.assertIs(render_loop(_request("blues")), a)
        clear_loop_cache()
        b = render_loop(_request("blues"))
        self.assertEqual(a.wav, b.wav)


# --------------------------------------------------------------------------- note level


class TestArrangerNotes(unittest.TestCase):
    def test_bass_comp_and_changes_follow_the_chart(self) -> None:
        for name in MATERIAL:
            req = _request(name)
            loop, notes = _spy_render(req)
            beat = _beat(loop)
            tol = 0.06
            with self.subTest(song=name):
                bass = sorted((s, m) for s, d, m, w in notes if w == "bass")
                comp = [(s, m) for s, d, m, w in notes if w != "bass"]
                self.assertTrue(bass and comp)
                for ev in loop.events:  # downbeat bass on every chord = its (slash) bass
                    if not ev.chord:
                        continue
                    first = [m for s, m in bass if abs(s - ev.start) <= tol]
                    self.assertTrue(first, (ev.chord, ev.start))
                    self.assertEqual(first[0] % 12, ev.bass_pc, (ev.chord, NAMES[first[0] % 12]))
                for s, m in comp:  # comping only from the sounding chord (or the next, within a pushed eighth)
                    here = _event_at(loop, s)
                    nxt = _event_at(loop, s + beat / 2)
                    ok = [ev for ev in (here, nxt) if ev.chord]
                    fits = any(note_use(chord_facts(normalize_chord_for_theory(ev.chord)), m % 12, key=req.concert_key)
                               .category in HOLDABLE for ev in ok)
                    self.assertTrue(fits, (round(s, 3), NAMES[m % 12], here.chord))
                for ev in loop.events:  # each change is heard: the chord is comped while it sounds
                    if ev.chord:  # (styles comp on different beats — Pop on the off-beats)
                        heard = [m for s, m in comp if ev.start - beat / 2 <= s < ev.end - beat / 4]
                        self.assertTrue(heard, (ev.chord, ev.start))

    def test_bass_moves_only_by_approach_between_roots(self) -> None:
        """Between downbeats the arranger's bass may walk: chord tones and scale (passing) tones
        freely; anything chromatic or tense must move on by step (an approach note)."""
        for name in MATERIAL:
            req = _request(name)
            loop, notes = _spy_render(req)
            bass = sorted((s, m) for s, d, m, w in notes if w == "bass")
            with self.subTest(song=name):
                for i, (s, m) in enumerate(bass):
                    ev = _event_at(loop, s)
                    if not ev.chord:
                        continue
                    use = note_use(chord_facts(normalize_chord_for_theory(ev.chord)), m % 12, key=req.concert_key)
                    if use.category in HOLDABLE or use.category == "passing" or m % 12 == ev.bass_pc:
                        continue
                    nxt = bass[i + 1][1] if i + 1 < len(bass) else bass[0][1]
                    self.assertLessEqual(min(abs(nxt - m) % 12, 12 - abs(nxt - m) % 12), 2,
                                         (name, round(s, 2), NAMES[m % 12], ev.chord))


# --------------------------------------------------------------------------- signal level


class TestAudioSignal(unittest.TestCase):
    def test_length_tempo_meter_groove_and_level(self) -> None:
        for name in MATERIAL:
            req = _request(name)
            loop = render_loop(req)
            x, sr = decode_wav(loop.wav)
            beat = _beat(loop)
            with self.subTest(song=name):
                self.assertEqual(sr, LOOP_SAMPLE_RATE)
                self.assertEqual(len(x), int(round(req.bar_count * loop.bar_seconds * sr)))
                self.assertEqual(int(np.sum(np.abs(x) >= 0.999)), 0, "no clipping")
                quiet = min(A.rms_db(x[int(i * beat * sr): int((i + 1) * beat * sr)]) for i in range(int(len(x) / sr / beat)))
                self.assertGreater(quiet, -45.0, "no silent beat")
                onsets = A.onset_times(x, sr)
                self.assertGreaterEqual(len(onsets) / req.bar_count, 1.8, "a groove, not one held chord per bar")
                swung = req.style in ("Blues groove", "Jazz swing")  # off-beats on the triplet
                grid = loop.bar_seconds / (12 if req.meter in ("6/8", "12/8") or swung else 16)
                on_grid = [min(t % grid, grid - t % grid) <= 0.03 for t in onsets]
                self.assertGreaterEqual(sum(on_grid) / len(on_grid), 0.8, "onsets sit on the meter's grid")
                period = A.beat_period(x, sr, beat * 0.8, beat * 1.2)
                self.assertAlmostEqual(period / beat, 1.0, delta=0.04, msg="tempo: the beat period")
                jump, step = A.wrap_jump(x)
                self.assertLessEqual(jump, step * 1.5, "continuous loop wrap")
                # (the wrap itself is checked sample-exactly against the arranger's render in
                # TestLoopBoundary)

    def test_downbeat_bass_read_back_from_the_mix(self) -> None:
        for name in MATERIAL:
            loop = render_loop(_request(name))
            x, sr = decode_wav(loop.wav)
            beat = _beat(loop)
            heard = []
            for ev in loop.events:
                if ev.chord:
                    a = int(ev.start * sr)
                    heard.append(A.bass_pc(x[a: a + int(0.9 * beat * sr)], sr) == ev.bass_pc)
            with self.subTest(song=name):
                self.assertGreaterEqual(sum(heard) / len(heard), 0.85, heard)

    def test_tempo_scales_the_loop(self) -> None:
        slow, fast = render_loop(_request("blues", bpm=60)), render_loop(_request("blues", bpm=120))
        self.assertAlmostEqual(slow.loop_seconds, 2 * fast.loop_seconds, places=3)
        self.assertAlmostEqual(fast.loop_seconds, 12 * 2.0, places=3)


# --------------------------------------------------------------------------- loop boundary


def _full_render(req):
    """The arranger's own render of every pass (what the loop is cut from)."""
    import backing_audio

    from song_coach_backing import LOOP_SAMPLE_RATE, _passes

    events = [{"chord": t, "section": req.section_label, "bar_in_section": i, "section_bars": req.bar_count}
              for i, t in enumerate(req.bars)]
    full, _sr = backing_audio.synthesize_chords_to_numpy(
        events, bpm=req.bpm, loops=_passes(req), sr=LOOP_SAMPLE_RATE, style=req.style, level=req.level,
        song_title=req.song_title, song_artist=req.artist, time_signature=req.meter)
    return np.asarray(full, dtype=np.float64)


class TestLoopBoundary(unittest.TestCase):
    QUANT = 1.5 / 32767.0  # 16-bit rounding

    def test_the_first_downbeat_is_the_arrangers_own(self) -> None:
        """The cross-fade sits at the end of the loop: the downbeat attack is never blended."""
        for name in MATERIAL:
            req = _request(name)
            loop = render_loop(req)
            x, sr = decode_wav(loop.wav)
            full = _full_render(req)
            n = len(x)
            head = int(0.25 * loop.bar_seconds * sr)
            with self.subTest(song=name):
                self.assertLessEqual(float(np.max(np.abs(x[:head] - full[n: n + head]))), self.QUANT)
                # the last sample flows into the downbeat as the real render does
                self.assertLessEqual(abs(float(x[-1]) - float(full[n - 1])), self.QUANT)
                # everything but the last 12 ms is the middle pass untouched
                body = n - int(0.012 * sr)
                self.assertLessEqual(float(np.max(np.abs(x[:body] - full[n: n + body]))), self.QUANT)

    def test_exact_duration_in_every_meter(self) -> None:
        for name, meter in (("perfect", "6/8"), ("hotel", "4/4"), ("blues", "4/4"), ("shuffle", "12/8")):
            req = _request(name)
            loop = render_loop(req)
            x, sr = decode_wav(loop.wav)
            with self.subTest(song=name, meter=meter):
                self.assertEqual(req.meter, meter)
                self.assertEqual(len(x), int(round(req.bar_count * loop.bar_seconds * sr)))
                self.assertAlmostEqual(loop.events[-1].end, loop.loop_seconds, places=4)
                self.assertAlmostEqual(loop.events[0].start, 0.0, places=6)

    def test_last_chord_leads_into_the_first(self) -> None:
        """Across the wrap: the last chord sounds to the end, its closing bass notes are its own
        chord tones or a step-wise approach into the first chord's bass, and the downbeat after
        the wrap is the first chord's bass — what the full render really plays next."""
        for name in MATERIAL:
            req = _request(name)
            loop, notes = _spy_render(req)
            beat = _beat(loop)
            first, last = loop.events[0], loop.events[-1]
            bass = sorted((s, m) for s, d, m, w in notes if w == "bass")
            with self.subTest(song=name):
                tail = [(s, m) for s, m in bass if s >= loop.loop_seconds - beat * 1.01 - 0.06]
                for s, m in tail:
                    use = note_use(chord_facts(normalize_chord_for_theory(last.chord)), m % 12, key=req.concert_key)
                    to_first = min((m - first.bass_pc) % 12, (first.bass_pc - m) % 12)
                    self.assertTrue(use.category in HOLDABLE or use.category == "passing" or to_first <= 2,
                                    (name, round(s, 2), NAMES[m % 12], last.chord, "->", first.chord))
                head = [m for s, m in bass if abs(s) <= 0.06]
                self.assertTrue(head and head[0] % 12 == first.bass_pc, (name, [NAMES[h % 12] for h in head]))

    def test_no_extra_or_missing_beat_across_the_wrap(self) -> None:
        for name in MATERIAL:
            req = _request(name)
            loop = render_loop(req)
            x, sr = decode_wav(loop.wav)
            bar = int(round(loop.bar_seconds * sr))
            joined = np.concatenate([x[-bar:], x[:bar]])  # last bar, then the first bar again
            onsets = A.onset_times(joined, sr)
            swung = req.style in ("Blues groove", "Jazz swing")
            grid = loop.bar_seconds / (12 if req.meter in ("6/8", "12/8") or swung else 16)
            with self.subTest(song=name):
                on_grid = [min(t % grid, grid - t % grid) <= 0.03 for t in onsets]
                self.assertGreaterEqual(sum(on_grid) / len(on_grid), 0.8, "the beat grid runs straight through the wrap")
                near_wrap = [t for t in onsets if abs(t - loop.bar_seconds) <= 0.05]
                self.assertTrue(near_wrap, "the downbeat after the wrap is heard")


# --------------------------------------------------------------------------- shared-arranger defects


class TestSharedArrangerDefects(unittest.TestCase):
    """Reproduction cases for the Shared Backing Harmony Accuracy repair (not fixed in S5).

    These assert the shared arranger's *current* wrong output. When the repair lands they will
    fail — then the matching refusal in ``song_coach_backing.check_loop`` can be relaxed."""

    WRONG_VOICINGS = {  # chord: (pitch classes ``backing_audio.chord_notes`` adds wrongly)
        "Dsus2": {"G"}, "Csus2": {"F"}, "Caug": {"G"}, "C+": {"G"}, "C5": {"E"}, "Cm(maj7)": {"E"},
        "F9sus4": {"A"}, "C7b9": {"D"}, "C7#9": {"D"}, "C7b13": {"D", "A"}, "C69": {"Bb"}, "Dbmaj13": {"B"},
    }

    def test_chord_notes_voices_these_qualities_wrongly(self) -> None:
        from backing_audio import chord_notes

        for chord, wrong in self.WRONG_VOICINGS.items():
            facts = chord_facts(normalize_chord_for_theory(chord))
            added = {NAMES[n % 12] for n in chord_notes(chord)} - {NAMES[p] for p in facts.charted_pcs}
            with self.subTest(chord=chord):
                self.assertEqual(added, wrong)
                self.assertIsNotNone(check_loop(_custom_request(["C", chord])), "coaching refuses it")

    def test_split_bar_second_chord_is_not_on_its_root(self) -> None:
        """A chord that starts mid-bar does not get its root in the bass. At ``b9b408b0`` the
        slot was a half-step approach to the next bar (A♭ under the G of ``C:2|G:2``); dev's
        bass rework (``befcea9b`` and later) now plays a chord tone there — G's 5th, D — which
        is no longer a wrong note but still not the charted root, so coaching keeps refusing
        split bars until that is approved as acceptable or repaired."""
        import backing_audio

        calls = []
        orig = backing_audio._add_tone

        def spy(audio, sr, start, dur, midi, vol, wave_type="sine"):
            calls.append((float(start), int(midi), str(wave_type)))
            return orig(audio, sr, start, dur, midi, vol, wave_type)

        events = [{"chord": c, "section": "Verse", "bar_in_section": i, "section_bars": 2}
                  for i, c in enumerate(["C:2|G:2", "Am"])]
        with mock.patch.object(backing_audio, "_add_tone", spy):
            backing_audio.synthesize_chords_to_numpy(events, bpm=90, loops=1, sr=LOOP_SAMPLE_RATE,
                                                     style="Pop groove", time_signature="4/4")
        beat = 60.0 / 90
        at_g = [NAMES[m % 12] for s, m, w in calls if w == "bass" and abs(s - 2 * beat) < 0.06]
        self.assertTrue(at_g, "a bass note where G arrives")
        self.assertNotEqual(at_g[0], "G", "the arriving chord is not on its root")
        self.assertIn(at_g[0], {"G", "B", "D", "Ab"}, at_g)  # D on dev (a chord tone); Ab before
        self.assertIsNotNone(check_loop(_custom_request(["C:2|G:2", "Am"])), "coaching refuses split bars")

    def test_blues_walking_flat_seven_is_the_fourth(self) -> None:
        """In "Blues groove" the walking line's ``flat7 = fifth - 2`` is the 4th (F under C7)."""
        from backing_audio import _bass_motion_pitch

        self.assertEqual(NAMES[_bass_motion_pitch("C7", None, "Blues groove", 2, 7) % 12], "F")


# --------------------------------------------------------------------------- refusals


def _custom_request(bars: list[str], key: str = "C", meter: str = "4/4"):
    ctx = build_song_coach_context(identity="custom|custom::r", source_kind=SOURCE_CUSTOM, concert_sections={"A": bars},
                                   concert_key=key, style="pop", meter=meter, instrument="Piano")
    scope = build_scope(ctx, "a")
    return loop_request(ctx, scope, start_bar=1, end_bar=len(bars), bpm=96, style="Pop groove")


class TestRefusals(unittest.TestCase):
    def test_split_bars_are_not_looped(self) -> None:
        refusal = check_loop(_custom_request(["C:2|G:2", "Am", "F", "G"]))
        self.assertEqual(refusal.kind, REFUSAL_SPLIT_BAR)
        self.assertIn("Bar 1", refusal.message)
        refusal = check_loop(_custom_request(["C", "Am", "Em:3.5|D:0.5p", "D"]))
        self.assertEqual(refusal.kind, REFUSAL_SPLIT_BAR)
        self.assertIn("3", refusal.message)
        self.assertIsNone(check_loop(_custom_request(["C", "Am", "F", "G"])))

    def test_chords_the_arranger_would_voice_wrongly_are_named(self) -> None:
        for chord, wrong in (("Dsus2", "G"), ("C5", "E"), ("Cm(maj7)", "E"), ("Caug", "G"), ("F9sus4", "A"),
                             ("C7b9", "D"), ("C7b13", "A"), ("C69", "Bb")):
            refusal = check_loop(_custom_request(["C", chord, "C", chord]))
            with self.subTest(chord=chord):
                self.assertIsNotNone(refusal)
                self.assertEqual(refusal.kind, REFUSAL_VOICING)
                self.assertIn(chord, refusal.message)
                self.assertIn(wrong, refusal.message)

    def test_real_songs_play(self) -> None:
        for name in MATERIAL:
            self.assertIsNone(check_loop(_request(name)), name)

    def test_no_chords_no_loop(self) -> None:
        ctx = build_song_coach_context(identity="custom|custom::nc", source_kind=SOURCE_CUSTOM,
                                       concert_sections={"A": ["C", "N.C.", "N.C.", "G"]}, concert_key="C",
                                       style="pop", meter="4/4", instrument="Piano")
        req = loop_request(ctx, build_scope(ctx, "a"), start_bar=2, end_bar=3, bpm=96, style="Pop groove")
        self.assertEqual(check_loop(req).kind, REFUSAL_EMPTY)


# --------------------------------------------------------------------------- isolation & player


class TestIsolation(unittest.TestCase):
    def test_modules_never_touch_backing_or_key_cycling(self) -> None:
        import inspect

        import song_coach_backing
        import song_coach_player

        for module in (song_coach_backing, song_coach_player):
            src = inspect.getsource(module)
            for forbidden in ("backing_wav_runtime_cache", "BACKING_WAV_CACHE", "__kc", "kc-buf", "st.audio(",
                              "backing_track_", "backing_key_cycle", "concert_key\"]", "session[\"focus", "<audio"):
                self.assertNotIn(forbidden, src, (module.__name__, forbidden))

    def test_player_says_which_bars_it_loops(self) -> None:
        loop = render_loop(_request("perfect", start_bar=5, end_bar=8))
        challenge = player_html(loop, scope=LOOP_RANGE_CHALLENGE)
        whole = player_html(loop, scope=LOOP_RANGE_SELECTION)
        self.assertIn("Looping this challenge&#x27;s bars", challenge)
        self.assertIn("Looping the whole selection", whole)
        self.assertIn("Bars 5–8", challenge)
        cfg = json.loads(re.search(r"var CFG = (\{.*?\});", challenge).group(1))
        self.assertEqual((cfg["first"], cfg["bars"]), (5, 4))
        self.assertEqual([e[2] for e in cfg["events"]], ["Cadd9", "D/F#"])

    def test_player_html_is_deterministic_and_self_contained(self) -> None:
        loop = render_loop(_request("perfect", start_bar=1, end_bar=4))
        a, b = player_html(loop, style_label="Ballad"), player_html(loop, style_label="Ballad")
        self.assertEqual(a, b)
        self.assertIn(loop.signature, a)
        self.assertIn("Bars 1–4 · 6/8 · 63 BPM · Practice Key G (concert) · Ballad feel", a)
        self.assertNotIn("<audio", a)
        payload = re.search(r'var B64 = "([A-Za-z0-9+/=]+)"', a).group(1)
        self.assertEqual(base64.b64decode(payload), loop.wav)
        cfg = json.loads(re.search(r"var CFG = (\{.*?\});", a).group(1))
        self.assertEqual(cfg["bars"], 4)
        self.assertEqual([e[2] for e in cfg["events"]], ["G", "Em7"])
        self.assertAlmostEqual(cfg["loop"], loop.loop_seconds, places=4)

    def test_loop_preferences_round_trip(self) -> None:
        state = with_loop(CoachState(identity="x"), bpm=72, loop_range=LOOP_RANGE_SELECTION)
        self.assertEqual(CoachState.from_dict(json.loads(json.dumps(state.to_dict()))), state)
        self.assertEqual(with_loop(state, loop_range="bogus").loop_range, LOOP_RANGE_SELECTION)
        legacy = {k: v for k, v in state.to_dict().items() if not k.startswith("loop_")}
        old = CoachState.from_dict(legacy)
        self.assertEqual((old.loop_bpm, old.loop_range), (0, LOOP_RANGE_CHALLENGE))


# --------------------------------------------------------------------------- browser transport


def _chromium():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    return sync_playwright


class TestBrowserTransport(unittest.TestCase):
    """The real transport in headless Chromium: play, pause, stop, loop wrap, rapid clicks,
    volume and the short resume after a tempo re-render."""

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile
        from pathlib import Path

        sp = _chromium()
        if sp is None:
            raise unittest.SkipTest("Playwright is not installed")
        cls._pw = sp().start()
        try:
            cls._browser = cls._pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        except Exception as exc:  # no browser binary
            cls._pw.stop()
            raise unittest.SkipTest(f"Chromium unavailable: {exc}")
        cls._dir = Path(tempfile.mkdtemp(prefix="song_coach_player_"))
        req = _request("composition", bpm=220, start_bar=1, end_bar=1)
        cls.loop = render_loop(req)
        cls.page_a = cls._dir / "a.html"
        cls.page_a.write_text(player_html(cls.loop), encoding="utf-8")
        cls.page_b = cls._dir / "b.html"  # same range, another tempo
        cls.page_b.write_text(player_html(render_loop(dataclasses.replace(req, bpm=200))), encoding="utf-8")
        cls.page_c = cls._dir / "c.html"  # another range
        cls.page_c.write_text(player_html(render_loop(_request("composition", bpm=220, start_bar=2, end_bar=2))),
                              encoding="utf-8")
        from song_coach_player import resume_signal_html

        def with_signal(doc: str, range_key: str) -> str:  # the tempo signal, rendered before this player
            script = resume_signal_html(range_key).split("<body>", 1)[1].split("</body>", 1)[0]
            return doc.replace("<body>", "<body>" + script, 1)

        cls.page_b_signal = cls._dir / "b_signal.html"  # tempo change of the playing range
        cls.page_b_signal.write_text(with_signal(cls.page_b.read_text(encoding="utf-8"), req.range_key()), encoding="utf-8")
        cls.page_c_signal = cls._dir / "c_signal.html"  # a tempo signal for another range
        cls.page_c_signal.write_text(with_signal(cls.page_c.read_text(encoding="utf-8"), req.range_key()), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._browser.close()
        cls._pw.stop()

    def _state(self, page):
        return page.evaluate("() => { const p = window.__songCoachLoop; return {s: p.state, e: p.elapsed, l: p.loops,"
                             " buf: p.bufferSeconds, vol: p.volume, bar: p.position.bar, chord: p.position.chord}; }")

    def test_play_pause_stop_and_loop(self) -> None:
        page = self._browser.new_page()
        page.goto(self.page_a.as_uri())
        self.assertEqual(self._state(page)["s"], "stopped")
        page.click("#play")
        page.wait_for_function("() => window.__songCoachLoop.state === 'playing'")
        self.assertAlmostEqual(self._state(page)["buf"], self.loop.loop_seconds, places=3)
        page.wait_for_function(f"() => window.__songCoachLoop.elapsed > {self.loop.loop_seconds * 2.2}", timeout=15000)
        self.assertGreaterEqual(self._state(page)["l"], 2, "the loop wraps and keeps playing")
        page.click("#pause")
        held = self._state(page)
        page.wait_for_timeout(400)
        self.assertEqual(self._state(page)["s"], "paused")
        self.assertAlmostEqual(self._state(page)["e"], held["e"], places=6)
        page.click("#play")
        page.wait_for_function("() => window.__songCoachLoop.state === 'playing'")
        self.assertGreaterEqual(self._state(page)["e"], held["e"], "resumes where it paused")
        page.click("#stop")
        self.assertEqual((self._state(page)["s"], self._state(page)["e"]), ("stopped", 0))
        self.assertEqual(page.inner_text("#pos"), "Bar 1 (1 of 1)")
        page.close()

    def test_rapid_clicks_end_consistent(self) -> None:
        page = self._browser.new_page()
        page.goto(self.page_a.as_uri())
        for _ in range(8):
            page.click("#play")
            page.click("#pause", force=True)
            page.click("#play", force=True)
            page.click("#stop", force=True)
        page.wait_for_timeout(300)
        st = self._state(page)
        self.assertEqual((st["s"], st["e"]), ("stopped", 0))
        page.click("#play")
        page.wait_for_function("() => window.__songCoachLoop.state === 'playing'")
        page.close()

    def test_only_one_loop_sounds_and_leaving_stops_it(self) -> None:
        """Players in one page (as Streamlit iframes are): starting one stops the other; a new
        player for another loop stops a lingering one; removing a playing player stops it."""
        import html as _html
        import http.server
        import threading

        loops = [render_loop(_request("composition", bpm=220, start_bar=b, end_bar=b)) for b in (1, 2, 3)]
        frames = "".join(
            f'<iframe id="f{i}" srcdoc="{_html.escape(player_html(lp), quote=True)}" width="600" height="140"></iframe>'
            for i, lp in enumerate(loops[:2]))
        third = _html.escape(player_html(loops[2]), quote=False)
        page_html = (
            "<!doctype html><html><body>" + frames + f'<textarea id="t3" hidden>{third}</textarea>'
            "<script>window.heard=[];const bc=new BroadcastChannel('song-coach-loop');"
            "bc.onmessage=e=>window.heard.push(e.data.type);"
            "window.addThird=()=>{const f=document.createElement('iframe');f.id='f2';f.width=600;f.height=140;"
            "f.srcdoc=document.getElementById('t3').value;document.body.appendChild(f);};"
            "</script></body></html>")
        (self._dir / "multi.html").write_text(page_html, encoding="utf-8")
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(self._dir), **k)  # noqa: E731
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            page = self._browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/multi.html")
            page.wait_for_function("() => window.frames.length === 2 && Array.from({length: window.frames.length}, (_, i) => window.frames[i]).every(f => f.__songCoachLoop)")

            def states():
                return page.evaluate("() => Array.from({length: window.frames.length}, (_, i) => window.frames[i])"
                                     ".map(f => f.__songCoachLoop ? f.__songCoachLoop.state : 'gone')")

            pongs = ("() => new Promise(done => { const ids = new Set(); const ch = new BroadcastChannel('song-coach-loop');"
                     " ch.onmessage = e => { if (String(e.data.type).startsWith('pong')) ids.add(e.data.id); };"
                     " ch.postMessage({type: 'ping', id: 'test'}); setTimeout(() => { ch.close(); done(ids.size); }, 400); })")
            self.assertEqual(page.evaluate(pongs), 2, "exactly the players on the page answer")
            a, b = page.frame_locator("#f0"), page.frame_locator("#f1")
            a.locator("#play").click()
            page.wait_for_function("() => window.frames[0].__songCoachLoop.state === 'playing'")
            b.locator("#play").click()
            page.wait_for_function("() => window.frames[1].__songCoachLoop.state === 'playing'")
            page.wait_for_timeout(300)
            self.assertEqual(states(), ["stopped", "playing"], "starting one loop stops the other")
            for _ in range(6):  # rapid alternation never leaves two sounding
                a.locator("#play").click()
                b.locator("#play").click(force=True)
                self.assertLessEqual(states().count("playing"), 1)
            page.wait_for_timeout(400)
            self.assertLessEqual(states().count("playing"), 1)
            page.evaluate("() => window.addThird()")  # a player for another loop appears
            page.wait_for_function("() => window.frames.length === 3 && window.frames[2].__songCoachLoop")
            page.wait_for_timeout(300)
            self.assertNotIn("playing", states()[:2], "a newly mounted loop stops the old one")
            page.frame_locator("#f2").locator("#play").click()
            page.wait_for_function("() => window.frames[2].__songCoachLoop.state === 'playing'")
            page.evaluate("() => document.getElementById('f2').remove()")  # leaving the tab
            page.wait_for_function("() => window.heard.includes('stopped-on-leave')", timeout=5000)
            self.assertEqual(page.evaluate(pongs), 2, "the removed player is gone, nothing is left behind")
            page.close()
        finally:
            server.shutdown()

    def _playing(self, page):
        page.click("#play")
        page.wait_for_function("() => window.__songCoachLoop.state === 'playing'")

    def test_volume_and_the_tempo_resume_rule(self) -> None:
        page = self._browser.new_page()
        page.goto(self.page_a.as_uri())
        page.fill("#vol", "35")
        page.dispatch_event("#vol", "input")
        self._playing(page)
        page.goto(self.page_b.as_uri())  # same range again, but no tempo signal: never starts by itself
        page.wait_for_timeout(700)
        self.assertEqual(self._state(page)["s"], "stopped", "no revival without the musician's tempo change")
        self.assertEqual(self._state(page)["vol"], 35, "volume is remembered")
        page.goto(self.page_a.as_uri())
        self._playing(page)
        page.goto(self.page_b_signal.as_uri())  # the musician changed the tempo of the playing loop
        page.wait_for_function("() => window.__songCoachLoop.state === 'playing'", timeout=5000)
        page.goto(self.page_a.as_uri())
        self._playing(page)
        page.goto(self.page_c_signal.as_uri())  # a signal for another range is ignored
        page.wait_for_timeout(700)
        self.assertEqual(self._state(page)["s"], "stopped")
        page.close()

    def test_refresh_and_coming_back_never_restart_audio(self) -> None:
        page = self._browser.new_page()
        page.goto(self.page_a.as_uri())
        self._playing(page)
        page.reload()
        page.wait_for_function("() => !!window.__songCoachLoop")
        page.wait_for_timeout(700)
        self.assertEqual(self._state(page)["s"], "stopped", "a refresh never restarts audio")
        self._playing(page)
        page.goto("about:blank")  # leave …
        page.go_back()  # … and come straight back
        page.wait_for_function("() => !!window.__songCoachLoop")
        page.wait_for_timeout(700)
        self.assertEqual(self._state(page)["s"], "stopped", "returning never restarts audio")
        page.close()

if __name__ == "__main__":
    unittest.main()
