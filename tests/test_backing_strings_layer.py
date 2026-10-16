"""Optional strings layer (A2): off is a no-op, on is supportive and in the chord."""

from __future__ import annotations

import unittest

import numpy as np

import backing_audio as ba
import backing_keys_voice as kv

NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _chroma(seg: np.ndarray, sr: int) -> np.ndarray:
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    band = (f > 120) & (f < 2500)
    c = np.zeros(12)
    np.add.at(c, np.rint(69 + 12 * np.log2(f[band] / 440.0)).astype(int) % 12, spec[band] ** 2)
    return c / (c.max() + 1e-12)


def _events(prog, section="Chorus 1"):
    return [{"chord": c, "section": section, "bar_in_section": i, "section_bars": len(prog)} for i, c in enumerate(prog)]


class StringsOffTests(unittest.TestCase):
    def test_off_renders_exactly_what_the_default_renders(self) -> None:
        ev = _events(["C", "F", "Dm", "G7"])
        a, _ = ba.synthesize_chords_to_numpy(ev, bpm=100, loops=1, style="Pop groove", song_title="T")
        b, _ = ba.synthesize_chords_to_numpy(ev, bpm=100, loops=1, style="Pop groove", song_title="T", strings=False)
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(ba.LAST_MIX_STATS["strings_rms"], 0.0)

    def test_on_changes_only_the_strings_layer(self) -> None:
        ev = _events(["C", "F", "Dm", "G7"])
        off, _ = ba.synthesize_chords_to_numpy(ev, bpm=100, loops=1, style="Ballad", song_title="T", layers=["rhythm", "keys"])
        on, _ = ba.synthesize_chords_to_numpy(
            ev, bpm=100, loops=1, style="Ballad", song_title="T", strings=True, layers=["rhythm", "keys"]
        )
        self.assertTrue(np.array_equal(off, on))
        self.assertEqual(len(off), len(on))


class StringsOnTests(unittest.TestCase):
    CASES = [
        (["C", "F", "Dm", "G7"], "Pop groove", 100),
        (["Cm", "Ab", "Eb", "Bb"], "Ballad", 72),
        (["Cmaj7", "Am7", "Dm7", "G7"], "Jazz swing", 140),
        (["C7", "F7", "C7", "G7"], "Funk groove", 104),
    ]

    def test_strings_hold_chord_tones(self) -> None:
        for prog, style, bpm in self.CASES:
            with self.subTest(style=style):
                so, sr = ba.synthesize_chords_to_numpy(
                    _events(prog), bpm=bpm, loops=1, style=style, song_title="T", strings=True, layers=["strings"]
                )
                bar = ba.meter_timing(bpm, "4/4").bar_sec
                for i, chord in enumerate(prog):
                    ch = _chroma(so[int((i + 0.35) * bar * sr): int((i + 0.95) * bar * sr)], sr)
                    strong = {k for k in range(12) if ch[k] > 0.3}
                    tones = {n % 12 for n in ba.chord_notes(chord)}
                    self.assertLessEqual(strong, tones, f"{style} {chord}: {[NAMES[k] for k in strong - tones]}")

    def test_strings_stay_under_the_piano_and_recede_in_groove_styles(self) -> None:
        ratios = {}
        for prog, style, bpm in self.CASES:
            ba.synthesize_chords_to_numpy(_events(prog), bpm=bpm, loops=2, style=style, song_title="T", strings=True)
            st = ba.LAST_MIX_STATS
            self.assertLess(st["strings_rms"], st["keys_rms"], style)
            ratios[style] = st["strings_rms"] / st["rhythm_rms"]
        self.assertGreater(ratios["Ballad"], ratios["Pop groove"])
        self.assertGreater(ratios["Pop groove"], ratios["Funk groove"])

    def test_strings_follow_the_key(self) -> None:
        for prog, triad in ((["C", "F", "G", "C"], {0, 4, 7}), (["D", "G", "A", "D"], {2, 6, 9})):
            so, sr = ba.synthesize_chords_to_numpy(
                _events(prog), bpm=100, loops=1, style="Ballad", song_title="T", strings=True, layers=["strings"]
            )
            bar = ba.meter_timing(100, "4/4").bar_sec
            ch = _chroma(so[int(0.35 * bar * sr): int(0.95 * bar * sr)], sr)
            self.assertEqual({int(k) for k in np.argsort(ch)[::-1][:3]}, triad)

    def test_strings_lay_out_on_no_chord_bars(self) -> None:
        so, sr = ba.synthesize_chords_to_numpy(
            _events(["C", "N.C.", "N.C.", "G"]), bpm=100, loops=1, style="Ballad", song_title="T", strings=True, layers=["strings"]
        )
        bar = ba.meter_timing(100, "4/4").bar_sec
        held = np.sqrt(np.mean(so[int(0.3 * bar * sr): int(0.9 * bar * sr)] ** 2))
        rest = np.sqrt(np.mean(so[int(2.2 * bar * sr): int(2.9 * bar * sr)] ** 2))
        self.assertLess(rest, 0.05 * held)

    def test_strings_voicing_stays_in_the_style_register(self) -> None:
        for style in ("Ballad", "Jazz swing", "Rock groove"):
            _level, low, high, voices = kv.strings_style(style)
            prev = None
            for chord in ["C", "Am", "F", "G7"]:
                v = kv.strings_voicing(ba.chord_notes(chord), prev, style)
                self.assertLessEqual(len(v), voices)
                self.assertGreaterEqual(min(v), low - 5)
                self.assertLessEqual(max(v), high + 3)
                prev = v


class GenerateBackingTrackTests(unittest.TestCase):
    def test_wav_length_is_the_same_with_and_without_strings(self) -> None:
        ev = _events(["C", "F", "G", "C"])
        off = ba.generate_backing_track(ev, bpm=100, loops=1, style="Ballad", song_title="T")
        on = ba.generate_backing_track(ev, bpm=100, loops=1, style="Ballad", song_title="T", strings=True)
        self.assertEqual(len(off), len(on))
        self.assertNotEqual(off, on)


if __name__ == "__main__":
    unittest.main()
