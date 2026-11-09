"""Issue 62 — the Multitrack mixer must not silence or truncate a recorded take.

`st.slider(label, min, max, step=..., key=...)` with no `value=` starts at `min_value`.
The Volume and Align sliders were declared that way, so every fresh layer began at
Volume 0.0 (inaudible) and Align -3.0 s (first three seconds cut off). A 4-second take
exported as 1.000 s of silence. These tests pin the fixed defaults and the warning that
protects sessions which already stored the bad values.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from multitrack_capture_quality import mix_contribution_warnings

APP = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"


def _slider_call(label: str) -> str:
    src = APP.read_text(encoding="utf-8")
    i = src.index(f'"{label}"')
    start = src.rindex("st.slider(", 0, i)
    end = src.index(")", src.index(f"key=f\"mt_", i))
    return src[start:end]


class SliderDefaults(unittest.TestCase):
    def test_volume_slider_declares_an_audible_default(self):
        call = _slider_call("Volume")
        self.assertIn("value=1.0", call.replace(" ", ""))

    def test_align_slider_declares_a_neutral_default(self):
        call = _slider_call("Align timing")
        self.assertIn("value=0.0", call.replace(" ", ""))

    def test_neither_slider_relies_on_the_min_value_fallback(self):
        for label in ("Volume", "Align timing"):
            call = _slider_call(label).replace(" ", "").replace("\n", "")
            self.assertRegex(call, r"value=-?\d", f"{label} has no explicit default")


class SilentMixIsReported(unittest.TestCase):
    def _items(self, **over):
        base = {"name": "Flute", "slot": "Sax / winds", "volume": 1.0, "delay": 0.0,
                "mute": False, "solo": False}
        base.update(over)
        return base

    def test_all_layers_at_zero_volume_is_called_out(self):
        items = [self._items(volume=0.0), self._items(name="Guitar", volume=0.0)]
        warnings = mix_contribution_warnings(items)
        self.assertTrue(any("would be silent" in w for w in warnings))

    def test_one_silent_layer_is_named(self):
        items = [self._items(volume=0.0), self._items(name="Guitar", volume=1.0)]
        warnings = mix_contribution_warnings(items)
        self.assertTrue(any("Flute" in w and "not be heard" in w for w in warnings))
        self.assertFalse(any("would be silent" in w for w in warnings))

    def test_negative_align_is_reported_as_cutting_the_start(self):
        warnings = mix_contribution_warnings([self._items(delay=-3.0)])
        self.assertTrue(any("cuts that much off the START" in w for w in warnings))
        self.assertTrue(any("-3s" in w for w in warnings))

    def test_the_exact_buggy_default_pair_raises_both_warnings(self):
        items = [self._items(volume=0.0, delay=-3.0), self._items(name="G", volume=0.0, delay=-3.0)]
        warnings = mix_contribution_warnings(items)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any("silent" in w for w in warnings))
        self.assertTrue(any("START" in w for w in warnings))

    def test_healthy_settings_produce_no_warning(self):
        self.assertEqual(mix_contribution_warnings([self._items(), self._items(name="G")]), [])

    def test_positive_align_is_not_a_truncation(self):
        self.assertEqual(mix_contribution_warnings([self._items(delay=1.5)]), [])

    def test_a_muted_layer_is_not_counted(self):
        items = [self._items(volume=0.0, mute=True), self._items(name="G", volume=1.0)]
        self.assertEqual(mix_contribution_warnings(items), [])

    def test_solo_narrows_the_check_to_the_soloed_layer(self):
        items = [self._items(volume=0.0), self._items(name="G", volume=1.0, solo=True)]
        self.assertEqual(mix_contribution_warnings(items), [])

    def test_empty_and_malformed_input_is_safe(self):
        for bad in ([], None, ["not a dict"], [{}]):
            self.assertIsInstance(mix_contribution_warnings(bad), list)

    def test_non_numeric_settings_fall_back_to_neutral(self):
        self.assertEqual(mix_contribution_warnings([self._items(volume="x", delay="y")]), [])


class MixArithmeticMatchesTheObservedFailure(unittest.TestCase):
    """A 4 s layer at Align -3 s really does become 1.000 s."""

    def test_negative_align_trims_from_the_front(self):
        import numpy as np

        y = np.ones(4 * 44100, dtype=np.float32)
        ds = int(-3.0 * 44100)
        trimmed = y[-ds:]
        self.assertEqual(len(trimmed), 44100)
        self.assertAlmostEqual(len(trimmed) / 44100, 1.0, places=6)

    def test_zero_volume_removes_all_signal(self):
        import numpy as np

        y = np.ones(1000, dtype=np.float32) * 0.8
        self.assertEqual(float(np.max(np.abs(y * 0.0))), 0.0)


if __name__ == "__main__":
    unittest.main()
