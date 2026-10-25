"""Bossa nova bass: two-feel on 1 and 3, real fifths, slash basses, every chord change,
E1..C3 voice leading, straight 8ths -- and the chord digest that keeps an edited
progression from replaying an old WAV."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

import backing_audio as ba
from backing_musical_profile import resolve_backing_musical_profile_from_session
from backing_wav_runtime_cache import backing_chord_digest

ROOT = Path(__file__).resolve().parents[1]
BLUES_TEST_G = ["G7", "C7", "G7", "D7#5/G"] * 4  # Blues Test at Practice Key G


def _events(chords, section="Verse 1"):
    return [{"chord": c, "section": section, "bar_in_section": i, "section_bars": len(chords)}
            for i, c in enumerate(chords)]


def _render_bass(chords, *, style="Bossa nova", bpm=120, key="C", title="Bass Test"):
    """Bass notes ``(time_sec, midi, dur_sec)`` the real synth plays for ``chords``."""
    captured = []
    orig = ba._add_tone

    def spy(audio, sr, start, dur, midi, vol, wave_type="sine"):
        if wave_type in ("bass", "bass_upright"):
            captured.append((float(start), int(midi), float(dur)))
        return orig(audio, sr, start, dur, midi, vol, wave_type)

    prof = resolve_backing_musical_profile_from_session({}, style=style, tempo=bpm, key=key)
    ba._add_tone = spy
    try:
        ba.synthesize_chords_to_numpy(_events(chords), bpm=bpm, loops=1, style=style, song_title=title,
                                      musical_profile=prof, strings=False)
    finally:
        ba._add_tone = orig
    return sorted(captured), 60.0 / bpm


def _bar(chord, next_chord=None, seed=0, **kw):
    state = {"prev": None, "planned": None}
    return ba._bossa_bass_bar(chord, next_chord, 4, state, np.random.default_rng(seed), **kw)


class TestBossaBarShape(unittest.TestCase):
    def test_root_on_one_fifth_on_three_every_time(self) -> None:
        for seed in range(40):
            notes = _bar("G7", "C7", seed=seed)
            beats = {n[0]: n[2] % 12 for n in notes}
            self.assertEqual(beats[0.0], 7)  # G
            self.assertEqual(beats[2.0], 2)  # D
            self.assertTrue(set(beats) <= {0.0, 1.5, 2.0, 3.5}, beats)

    def test_pickups_vary_between_bars(self) -> None:
        shapes = {tuple(n[0] for n in _bar("G7", "C7", seed=s, density=0.8)) for s in range(40)}
        self.assertGreater(len(shapes), 2)

    def test_and_of_two_anticipates_beat_three(self) -> None:
        for seed in range(40):
            notes = {n[0]: n[2] for n in _bar("Cmaj7", "Am7", seed=seed)}
            if 1.5 in notes:
                self.assertEqual(notes[1.5], notes[2.0])

    def test_notes_are_legato(self) -> None:
        notes = _bar("G7", "C7", seed=3)
        for a, b in zip(notes, notes[1:]):
            self.assertAlmostEqual(a[0] + a[1], b[0])
        self.assertAlmostEqual(notes[-1][0] + notes[-1][1], 4.0)


class TestBossaPitches(unittest.TestCase):
    def test_slash_chords_start_on_the_written_bass(self) -> None:
        cases = {
            "D7/F#": (6, 9),  # F# then A (the chord's fifth)
            "C/E": (4, 7),  # E then G
            "G/B": (11, 2),  # B then D
            "Am7/G": (7, 7),  # 7th in the bass: stays on G
            "C/G": (7, 0),  # 5th in the bass: then the root
            "C7#5/F": (5, 5),  # pedal bass (not a chord tone): stays on F
        }
        for chord, (one, three) in cases.items():
            self.assertEqual(ba._bossa_bass_pcs(chord), (one, three), chord)

    def test_fifth_is_the_one_the_chord_has(self) -> None:
        cases = {"Bm7b5": 5, "C#dim7": 7, "B7#5": 7, "G7alt": 3, "G7b5": 1, "Caug": 8, "Ebdim": 9, "G7": 2}
        for chord, fifth in cases.items():
            self.assertEqual(ba._bossa_bass_pcs(chord)[1], fifth, chord)

    def test_piano_voices_an_explicit_b5_or_sharp5_too(self) -> None:
        self.assertIn(1, {n % 12 for n in ba.chord_notes("G7b5")})
        self.assertNotIn(2, {n % 12 for n in ba.chord_notes("G7b5")})
        self.assertIn(8, {n % 12 for n in ba.chord_notes("Cmaj7#5")})
        self.assertEqual([n % 12 for n in ba.chord_notes("Cm7b5")], [0, 3, 6, 10])


class TestBossaInTheSynth(unittest.TestCase):
    def test_blues_test_register_and_voice_leading(self) -> None:
        notes, _beat = _render_bass(BLUES_TEST_G, bpm=133, key="G", title="Blues Test")
        midis = [m for _, m, _ in notes]
        self.assertTrue(all(ba.BOSSA_BASS_LOW <= m <= ba.BOSSA_BASS_HIGH for m in midis), midis)
        self.assertLessEqual(max(abs(b - a) for a, b in zip(midis, midis[1:])), 7)

    def test_offbeats_are_straight_eighths(self) -> None:
        # Song tweaks give Satin Doll swing in Bossa nova; the synth must still play it straight.
        notes, beat = _render_bass(BLUES_TEST_G, bpm=133, key="G", title="Satin Doll")
        for t, _, _ in notes:
            frac = (t / beat) % 1
            if 0.25 < frac < 0.75:
                self.assertLess(abs(frac - 0.5), 0.05, t / beat)

    def test_every_chord_change_gets_its_bass_on_its_beat(self) -> None:
        bars = ["Cmaj7:2|A7:2", "Dm7:2|G7/B:2", "Em7|A7|Dm7|G7", "C:3|G7:1", "Em7:2|Ebdim7:2", "C:3.5|D7:0.5p", "G7"]
        notes, beat = _render_bass(bars)
        for bar_i, token in enumerate(bars):
            cursor = 0.0
            for sub in ba._sub_parse_subdivisions(token):
                t0 = (bar_i * 4 + cursor) * beat
                near = [m for t, m, _ in notes if abs(t - t0) < 0.06 * beat + 0.02]
                self.assertTrue(near, (token, sub.chord))
                self.assertEqual(near[0] % 12, ba.bass_note(sub.chord) % 12, (token, sub.chord))
                cursor += sub.weight

    def test_bass_follows_the_sounding_chords_not_guitar_shapes(self) -> None:
        # Capo shapes (D shapes, capo 6) sound Ab: the backing gets the concert chords.
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, build_capo_context

        concert = {"Verse 1": ["Ab7", "Db7", "Ab7", "Eb7#5/Ab"]}
        ctx = build_capo_context({CAPO_ENABLED_KEY: True, CAPO_SHAPE_KEY: "D"}, concert, concert_key="Ab",
                                 instrument="Guitar")
        notes, beat = _render_bass(ctx.sounding_sections["Verse 1"], bpm=133, key="Ab")
        downbeats = [m % 12 for t, m, _ in notes if abs(t / beat / 4 - round(t / beat / 4)) * 4 < 0.05]
        self.assertEqual(downbeats, [8, 1, 8, 8])  # Ab Db Ab Ab(pedal), never D / G shapes


class TestOtherStylesApproachAndChanges(unittest.TestCase):
    def test_walking_approach_is_next_to_the_next_downbeat(self) -> None:
        target = ba._bass_register(ba.bass_note("C7"))
        self.assertIn(ba._bass_motion_pitch("G7", "C7", "Jazz swing", 3, 4), (target - 1, target + 1))

    def test_pop_pickup_lands_a_half_step_from_the_downbeat(self) -> None:
        notes, beat = _render_bass(["G7", "C7"], style="Pop groove", bpm=100, key="G")
        pickup = [m for t, m, _ in notes if 3.4 < t / beat < 3.7]
        downbeat = [m for t, m, _ in notes if abs(t / beat - 4) < 0.05]
        self.assertTrue(pickup and downbeat)
        self.assertEqual(abs(pickup[0] - downbeat[0]), 1)

    def test_pop_half_bar_change_plays_the_slash_bass(self) -> None:
        notes, beat = _render_bass(["Gmaj7:2|G/B:2", "C"], style="Pop groove", bpm=100, key="G")
        at_two = [m for t, m, _ in notes if abs(t / beat - 2) < 0.05]
        self.assertEqual(at_two[0] % 12, 11)


class TestChordDigest(unittest.TestCase):
    def test_edit_changes_digest(self) -> None:
        a = backing_chord_digest({"Verse": ["G7", "C7", "G7", "D7"]}, "G")
        b = backing_chord_digest({"Verse": ["G7", "C7", "G7", "D7#5"]}, "G")
        self.assertNotEqual(a, b)

    def test_transposed_or_respelled_chart_keeps_digest(self) -> None:
        g = backing_chord_digest({"Verse": ["G7", "C7:2|D7/F#:2", "Em7.hit"]}, "G")
        ab = backing_chord_digest({"Verse": ["Ab7", "Db7:2|Eb7/G:2", "Fm7.hit"]}, "Ab")
        cs = backing_chord_digest({"Verse": ["G#7", "C#7:2|D#7/G:2", "Fm7.hit"]}, "G#")
        self.assertEqual(g, ab)
        self.assertEqual(ab, cs)

    def test_only_selected_sections_count(self) -> None:
        base = {"Verse": ["C", "F"], "Chorus": ["G", "C"]}
        edited = {"Verse": ["C", "F"], "Chorus": ["G", "Am"]}
        self.assertEqual(backing_chord_digest(base, "C", ["Verse"]), backing_chord_digest(edited, "C", ["Verse"]))
        self.assertNotEqual(backing_chord_digest(base, "C"), backing_chord_digest(edited, "C"))

    def test_signatures_carry_the_digest_before_the_renderer_tag(self) -> None:
        src = ROOT.joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn('_BACKING_RENDERER_TAG = "arr_v4"', src)
        main = src[src.index("def _backing_signature_for_bpm") :][:2600]
        self.assertIn(
            "_backing_chord_digest(_backing_digest_sections, _audio_signature_key, selected_section_names),\n"
            "            _backing_arrangement_tag(),",
            main,
        )
        self.assertIn("_backing_chord_digest(_secs, tgt, snap[\"section_names\"]),", src)
        self.assertIn("and _ck[-2] == _pf_digest", src)


if __name__ == "__main__":
    unittest.main()
