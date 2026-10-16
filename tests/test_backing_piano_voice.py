"""Piano comp (A1): rendered harmony per style, register, dynamics, decay."""

from __future__ import annotations

import unittest

import numpy as np

import backing_audio as ba
import backing_keys_voice as kv


def _chroma(seg: np.ndarray, sr: int) -> np.ndarray:
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    band = (f > 120) & (f < 2500)
    c = np.zeros(12)
    np.add.at(c, np.rint(69 + 12 * np.log2(f[band] / 440.0)).astype(int) % 12, spec[band] ** 2)
    return c / (c.max() + 1e-12)


def _events(prog):
    return [{"chord": c, "section": "Verse 1", "bar_in_section": i, "section_bars": len(prog)} for i, c in enumerate(prog)]


CASES = [
    (["C", "F", "Dm", "G7"], "Pop groove", 100),
    (["Cm", "Ab", "Eb", "Bb"], "Ballad", 72),
    (["Cmaj7", "Am7", "Dm7", "G7"], "Jazz swing", 140),
    (["Cm", "Ab", "Eb", "Bb"], "Bossa nova", 120),
    (["C7", "F7", "C7", "G7"], "Funk groove", 104),
    (["C", "F", "Am", "G"], "Rock groove", 120),
]


class PianoLayerHarmonyTests(unittest.TestCase):
    def test_keys_layer_plays_the_chart_in_every_style(self) -> None:
        for prog, style, bpm in CASES:
            with self.subTest(style=style):
                keys, sr = ba.synthesize_chords_to_numpy(
                    _events(prog), bpm=bpm, loops=1, style=style, song_title="T", layers=["keys"]
                )
                bar = ba.meter_timing(bpm, "4/4").bar_sec
                for i, chord in enumerate(prog):
                    ch = _chroma(keys[int((i + 0.1) * bar * sr): int((i + 0.95) * bar * sr)], sr)
                    notes = ba.chord_notes(chord)
                    root = notes[0] % 12
                    # Chord tones plus the 9th / 13th colour of jazz-family voicings.
                    allowed = {n % 12 for n in notes} | {(root + 2) % 12, (root + 9) % 12}
                    strong = {k for k in range(12) if ch[k] > 0.25}
                    self.assertLessEqual(strong, allowed, f"{style} {chord}: {sorted(strong - allowed)}")
                    self.assertGreater(ch[notes[1] % 12], 0.15, f"{style} {chord}: third missing")

    def test_keys_sit_under_the_rhythm_section_at_the_style_balance(self) -> None:
        for prog, style, bpm in CASES:
            with self.subTest(style=style):
                ba.synthesize_chords_to_numpy(_events(prog), bpm=bpm, loops=2, style=style, song_title="T")
                ratio = ba.LAST_MIX_STATS["keys_rms"] / ba.LAST_MIX_STATS["rhythm_rms"]
                self.assertAlmostEqual(ratio, ba._KEYS_BALANCE[style], delta=0.05)


class VoiceLeadingTests(unittest.TestCase):
    def test_comp_stays_in_the_piano_window_and_moves_by_steps(self) -> None:
        prev = None
        for chord in ["C", "Am", "F", "G", "C", "Em", "Dm", "G7"]:
            led = kv.lead_voicing(ba.chord_notes(chord), prev)
            self.assertGreaterEqual(min(led), kv.PIANO_LOW - 5)
            self.assertLessEqual(max(led), kv.PIANO_HIGH + 3)
            self.assertEqual({n % 12 for n in led}, {n % 12 for n in ba.chord_notes(chord)})
            if prev is not None:
                self.assertLessEqual(abs(max(led) - max(prev)), 5, f"top voice leapt into {chord}")
            prev = led

    def test_wide_voicings_are_moved_by_octaves_into_range(self) -> None:
        led = kv.lead_voicing([96, 100, 103, 110], None)  # stuck four octaves up
        self.assertLessEqual(max(led), kv.PIANO_HIGH + 3)
        self.assertEqual([n - led[0] for n in led], [0, 4, 7, 14])


class DynamicsTests(unittest.TestCase):
    def test_velocity_accents_the_downbeat_and_varies_repeats(self) -> None:
        down = [kv.hit_velocity(0, seed=s) for s in range(16)]
        off = [kv.hit_velocity(1.5, seed=s) for s in range(16)]
        self.assertGreater(np.mean(down), np.mean(off) + 0.15)
        self.assertGreater(len({round(v, 4) for v in down}), 8)
        self.assertEqual(kv.hit_velocity(2, seed=7), kv.hit_velocity(2, seed=7))

    def test_top_voice_sings_over_inner_voices(self) -> None:
        g = kv.voice_gains([60, 64, 67, 72])
        self.assertEqual(int(np.argmax(g)), 3)

    def test_piano_note_decays_and_harder_hits_are_brighter(self) -> None:
        sr = 44100

        def note(vel):
            bus = np.zeros(sr * 3)
            kv.add_piano_note(bus, sr, 0.0, 2.5, 60, 1.0, vel)
            return bus

        x = note(0.8)
        early = np.sqrt(np.mean(x[int(0.05 * sr): int(0.3 * sr)] ** 2))
        late = np.sqrt(np.mean(x[int(2.0 * sr): int(2.4 * sr)] ** 2))
        self.assertLess(late, 0.5 * early)

        def centroid(sig):
            spec = np.abs(np.fft.rfft(sig[: int(0.25 * sr)]))
            f = np.fft.rfftfreq(int(0.25 * sr), 1 / sr)
            return float((spec * f).sum() / spec.sum())

        self.assertGreater(centroid(note(0.95)), centroid(note(0.35)))


if __name__ == "__main__":
    unittest.main()
