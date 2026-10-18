"""MC4 — the Mission recording backing is real, correct accompaniment from the shared arranger.

Human review: "some chords do not sound correct" and "one static chord per change". Findings:

* MC4 passed the Mission style unresolved ("Song Default" / "Auto"), so the shared arranger fell
  back to generic held block chords — the Backing page resolves "Auto" from the song first;
* the shared arranger itself had wrong notes: the bass played its half-step approach on beat 3 of
  two-hit bars (E# under C#m7b5, A# under Bm), the jazz "9th" was built on the 3rd (C natural on
  F#7, #11 on every maj7) and the walking bass mixed octaves (C#3 -> E2 -> G2);
* comping never sounded on the bar line in Jazz / Pop, every chord was voiced independently in
  root position, and comps used an organ-like held sine;
* chord_notes misread ø7, °7, -7, Δ7, M7, min7, aug, 7#5, m(maj7) and doubled b9 / #9 with 9.

The same engine renders Backing, Mission Backing and the Mission recorder, so these are tested on
the engine itself; MC4 then resolves its arrangement exactly like the Backing page.
"""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import backing_audio as ba
from backing_audio import COMP_REGISTER, chord_notes
from backing_musical_profile import resolve_backing_musical_profile
from songs.meter import meter_timing

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SPAN = ["C#m7b5", "F#7", "Bm", "Bm"]  # iiø–V–i, Bm held two bars


def pcs(chord: str) -> set[str]:
    return {NAMES[n % 12] for n in chord_notes(chord)}


@contextmanager
def _capture():
    """Every bass / comp tone the arranger renders: (start_sec, dur_sec, midi, wave)."""
    tones: list[tuple[float, float, int, str]] = []
    real = ba._add_tone

    def tone(audio, sr, start, dur, midi, vol, wave="sine"):
        tones.append((float(start), float(dur), int(midi), str(wave)))
        return real(audio, sr, start, dur, midi, vol, wave)

    real_piano = ba._kv.add_piano_note

    def piano(bus, sr, start, dur, midi, vol, vel=0.72):
        # The keys comp is voiced through the shared piano voice; record it like any other tone.
        tones.append((float(start), float(dur), int(midi), "piano"))
        return real_piano(bus, sr, start, dur, midi, vol, vel)

    with mock.patch.object(ba, "_add_tone", tone), mock.patch.object(ba._kv, "add_piano_note", piano):
        yield tones


def _render(chords, style, *, bpm=82, loops=1):
    prof = resolve_backing_musical_profile(style=style, mood="Mellow", intensity="Auto", tempo=bpm)
    with _capture() as tones:
        audio, sr = ba.synthesize_chords_to_numpy(chords, bpm=bpm, loops=loops, style=style, musical_profile=prof)
    return tones, audio, sr


class TestChordSpelling(unittest.TestCase):
    def test_qualities(self) -> None:
        cases = {
            "C#m7b5": {"C#", "E", "G", "B"}, "C#ø7": {"C#", "E", "G", "B"}, "Cm7(b5)": {"C", "D#", "F#", "A#"},
            "F#7": {"F#", "A#", "C#", "E"}, "Bm": {"B", "D", "F#"},
            "Cmaj7": {"C", "E", "G", "B"}, "CM7": {"C", "E", "G", "B"}, "CΔ7": {"C", "E", "G", "B"},
            "Cm7": {"C", "D#", "G", "A#"}, "C-7": {"C", "D#", "G", "A#"}, "Cmin7": {"C", "D#", "G", "A#"},
            "Cdim7": {"C", "D#", "F#", "A"}, "C°7": {"C", "D#", "F#", "A"}, "Cdim": {"C", "D#", "F#"},
            "Csus4": {"C", "F", "G"}, "C7sus4": {"C", "F", "G", "A#"},
            "C7b9": {"C", "E", "G", "A#", "C#"}, "C7#9": {"C", "E", "G", "A#", "D#"},
            "C7alt": {"C", "E", "G#", "A#", "C#", "D#"}, "C7b9b13": {"C", "E", "G", "A#", "C#", "G#"},
            "C+": {"C", "E", "G#"}, "C7#5": {"C", "E", "G#", "A#"},
            "CmMaj7": {"C", "D#", "G", "B"}, "Cm(maj7)": {"C", "D#", "G", "B"}, "Cm6": {"C", "D#", "G", "A"},
            "G": {"G", "B", "D"}, "G7": {"G", "B", "D", "F"}, "C9": {"C", "E", "G", "A#", "D"},
        }
        for chord, want in cases.items():
            self.assertEqual(pcs(chord), want, chord)

    def test_slash_chord_bass(self) -> None:
        self.assertEqual(pcs("C/E"), {"C", "E", "G"})
        self.assertEqual(ba.bass_note("C/E") % 12, 4)


class TestRenderedHarmony(unittest.TestCase):
    def _bars(self, style, bpm=82):
        tones, _audio, _sr = _render(SPAN, style, bpm=bpm)
        bar = meter_timing(bpm, "4/4").bar_sec
        pulse = bar / 4
        out = []
        for i, chord in enumerate(SPAN):
            start, end = i * bar, (i + 1) * bar
            # Humanize / swing moves notes by tens of ms; a note belongs to the bar it is closest to.
            mine = [t for t in tones if start - 0.06 <= t[0] < end - 0.06]
            comp = [t for t in mine if t[3] != "bass"]
            bass = [t for t in mine if t[3] == "bass"]
            out.append((chord, start, pulse, comp, bass))
        return out

    def test_jazz_shells_are_the_right_chords(self) -> None:
        bars = self._bars("Jazz swing")
        allowed = {  # chord tones + the tensions a shell may add
            "C#m7b5": pcs("C#m7b5") | {"F#"},       # 11 on half-diminished
            "F#7": pcs("F#7") | {"G#", "D#"},        # 9, 13
            "Bm": pcs("Bm") | {"C#", "A"},            # 9, 7
        }
        for chord, _s, _p, comp, _b in bars:
            sounded = {NAMES[t[2] % 12] for t in comp}
            self.assertTrue(comp, chord)
            self.assertLessEqual(sounded, allowed[chord], (chord, sounded))
        f7 = {NAMES[t[2] % 12] for t in bars[1][3]}
        self.assertIn("A#", f7)  # 3rd
        self.assertIn("E", f7)   # 7th
        self.assertNotIn("C", f7)  # the old "9th built on the 3rd"

    def test_comping_is_correct_in_pop_and_ballad(self) -> None:
        for style in ("Pop groove", "Ballad"):
            for chord, _s, _p, comp, _b in self._bars(style):
                sounded = {NAMES[t[2] % 12] for t in comp}
                self.assertTrue(sounded, (style, chord))
                self.assertLessEqual(sounded, pcs(chord), (style, chord, sounded))

    def test_bass_root_on_the_bar_and_no_early_approach(self) -> None:
        for style in ("Jazz swing", "Pop groove", "Ballad"):
            for chord, start, pulse, _c, bass in self._bars(style):
                downbeat = [t for t in bass if abs(t[0] - start) < 0.06]
                self.assertTrue(downbeat, (style, chord))
                self.assertEqual(downbeat[0][2] % 12, chord_notes(chord)[0] % 12, (style, chord))
                tones_pc = {n % 12 for n in chord_notes(chord)}
                for t in bass:
                    if t[0] >= start + 3 * pulse - 0.06:
                        continue  # the last beat may approach the next chord
                    beat = round((t[0] - start) / pulse)
                    if style == "Jazz swing" and beat % 2 == 1:
                        # walking bass: a step from a chord tone on beats 2 / 4 (passing tone)
                        self.assertTrue(any(min((t[2] - p) % 12, (p - t[2]) % 12) <= 2 for p in tones_pc),
                                        (style, chord, t))
                    else:  # strong beats (and every beat outside walking styles): chord tones only
                        self.assertIn(NAMES[t[2] % 12], pcs(chord), (style, chord, t))
                for t in bass:
                    self.assertTrue(33 <= t[2] <= 60, (style, chord, t))  # bass register

    def test_comp_is_voice_led_in_a_piano_register(self) -> None:
        for style in ("Jazz swing", "Pop groove"):
            tones, _a, _sr = _render(SPAN, style)
            comp = sorted((t for t in tones if t[3] != "bass"), key=lambda t: t[0])
            hits: dict[float, list[int]] = {}
            for t in comp:
                hits.setdefault(round(t[0], 3), []).append(t[2])
            voicings = [sorted(v) for _k, v in sorted(hits.items())]
            for v in voicings:
                self.assertGreaterEqual(v[0], COMP_REGISTER[0], style)
                self.assertLessEqual(v[-1], COMP_REGISTER[1], style)
            moves = [abs(sum(b) / len(b) - sum(a) / len(a)) for a, b in zip(voicings, voicings[1:])]
            self.assertLessEqual(max(moves), 5.0, (style, moves))  # no root-position jumps

    def test_comp_sounds_on_each_bar_line(self) -> None:
        for style in ("Jazz swing", "Pop groove", "Ballad"):
            for chord, start, _p, comp, _b in self._bars(style):
                self.assertTrue(any(abs(t[0] - start) < 0.06 for t in comp), (style, chord))

    def test_piano_comping_and_timeline_length(self) -> None:
        for bpm in (82, 129):
            tones, audio, sr = _render(SPAN, "Jazz swing", bpm=bpm, loops=2)
            self.assertIn("piano", {t[3] for t in tones})
            bar = meter_timing(bpm, "4/4").bar_sec
            self.assertEqual(len(audio), int(sr * bar * len(SPAN) * 2) + sr)  # exact bars (+1 s tail)


class TestMissionArrangement(unittest.TestCase):
    def _ctx(self, groove="Auto", style="Song Default"):
        return SimpleNamespace(backing_groove=groove, backing_style=style, song_title="Autumn Leaves", display_key="Bm")

    def test_auto_is_resolved_from_the_song_like_the_backing_page(self) -> None:
        from mission_exact_chord_backing import mission_backing_arrangement

        for song, want in (({"genre": "Jazz", "title": "Autumn Leaves"}, "Jazz swing"),
                           ({"genre": "Pop", "title": "Some Song"}, "Pop groove")):
            with mock.patch("mission_song_backing_style._song_row_for_mission", return_value=(song, "catalog", "k")):
                for groove, style in (("Auto", "Song Default"), ("", ""), ("auto", "")):
                    arr = mission_backing_arrangement({"level": "Intermediate"}, self._ctx(groove, style), bpm=82, meter="4/4")
                    self.assertEqual(arr["style"], ba.infer_groove_style(song, "Auto"))
                    self.assertEqual(arr["style"], want)
                    self.assertIsNotNone(arr["profile"])
        with mock.patch("mission_song_backing_style._song_row_for_mission", return_value=({"genre": "Jazz"}, "catalog", "k")):
            arr = mission_backing_arrangement({}, self._ctx("Ballad", "Ballad"), bpm=70, meter="4/4")
        self.assertEqual(arr["style"], "Ballad")  # an explicit style is kept


class TestMissionRecorderUsesTheArrangement(unittest.TestCase):
    def test_span_backing_renders_resolved_style_and_seals_it(self) -> None:
        import mission_exact_chord_backing as meb
        from mission_live_recording_mix import resolve_backing_wav_for_live_mix
        from mission_practice_context import MISSION_BACKING_SOUNDING_SPAN_KEY
        from mission_span_take import record_span_take
        from tests.test_mc4_mission_tempo_sync import IIVI, _Env, _mission

        calls = []
        real = ba.generate_backing_track

        def spy(chords, **k):
            calls.append(k)
            return real(chords, **k)

        with _Env(), \
             mock.patch("mission_song_backing_style._song_row_for_mission",
                        return_value=({"genre": "Jazz", "title": "Autumn Leaves"}, "catalog", "k")), \
             mock.patch("backing_audio.generate_backing_track", spy):
            s = _mission(IIVI)
            meb._WAV_CACHE.clear()
            wav1, _ = meb.generate_exact_chord_backing_wav(s)
            self.assertEqual(calls[-1]["style"], "Jazz swing")
            self.assertIsNotNone(calls[-1]["musical_profile"])
            claim = s[MISSION_BACKING_SOUNDING_SPAN_KEY]
            self.assertEqual(claim["arrangement"]["style"], "Jazz swing")
            take = record_span_take(s, audio_bytes=b"take", source="live")
            self.assertEqual(take["backing"]["arrangement"]["style"], "Jazz swing")  # sealed with the take
            wav_preview, source = resolve_backing_wav_for_live_mix(s)
            self.assertEqual((wav_preview, source), (wav1, "session_play"))  # preview = what was played
            meb._WAV_CACHE.clear()
            meb.invalidate_exact_chord_backing_cache(s)
            wav2, _ = meb.generate_exact_chord_backing_wav(s)
            self.assertEqual(wav1, wav2)  # deterministic: a re-render is the same accompaniment

    def test_single_chord_backing_also_resolves_style(self) -> None:
        import mission_exact_chord_backing as meb
        from tests.test_mc4_mission_tempo_sync import _Env, _mission

        calls = []
        with _Env(), \
             mock.patch("mission_song_backing_style._song_row_for_mission",
                        return_value=({"genre": "Jazz"}, "catalog", "k")), \
             mock.patch("backing_audio.generate_backing_track", lambda chords, **k: calls.append(k) or b"RIFF"):
            s = _mission([], single=True)
            meb._WAV_CACHE.clear()
            meb.generate_exact_chord_backing_wav(s)
        self.assertEqual(calls[-1]["style"], "Jazz swing")


if __name__ == "__main__":
    unittest.main()
