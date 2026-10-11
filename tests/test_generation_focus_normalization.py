"""One canonical Practice Focus -> generation-key mapping.

``chord_navigation_notation`` and ``practice_melody_generator`` each carried a
near-copy of this matcher and had already drifted: the notation copy accepted a
"tone " prefix, the melody copy did not. Both now delegate to
``practice_focus_policy.generation_focus_key``.

These prove the consolidation did not change what any reachable UI focus maps
to, and that the two surfaces can no longer disagree.
"""

from __future__ import annotations

import unittest

from chord_navigation_notation import normalize_generation_focus
from practice_focus_policy import (
    GENERATION_FOCUS_KEYS,
    append_shared_coaching_focuses,
    generation_focus_key,
)
from practice_melody_generator import _normalize_focus
from practice_setup_controls import FOCUS_OPTIONS_BY_INSTRUMENT, focus_options_for_instrument


def _reachable_ui_focuses() -> list[str]:
    out: set[str] = set()
    for instrument in FOCUS_OPTIONS_BY_INSTRUMENT:
        options = focus_options_for_instrument(instrument)
        out |= set(options)
        out |= set(append_shared_coaching_focuses(options))
    return sorted(out)


# The mapping as it stood before consolidation, reproduced verbatim.
def _legacy_notation(focus: str) -> str:
    f = str(focus or "").strip().lower()
    if "pentaton" in f:
        return "pentatonics"
    if "guide" in f and "tone" in f:
        return "guide_tones"
    if "scale" in f:
        return "scales"
    if "articulat" in f:
        return "articulation"
    if "dynamic" in f:
        return "dynamics"
    if f == "tone" or f.startswith("tone "):
        return "tone"
    return ""


def _legacy_melody(focus: str) -> str:
    f = str(focus or "").strip().lower()
    if "pentaton" in f:
        return "pentatonics"
    if "guide" in f and "tone" in f:
        return "guide_tones"
    if "scale" in f:
        return "scales"
    if "articulat" in f:
        return "articulation"
    if "dynamic" in f:
        return "dynamics"
    if f == "tone":
        return "tone"
    return ""


class TestEquivalenceForReachableFocuses(unittest.TestCase):
    def test_every_reachable_ui_focus_maps_exactly_as_before(self) -> None:
        for label in _reachable_ui_focuses():
            self.assertEqual(normalize_generation_focus(label), _legacy_notation(label), label)
            self.assertEqual(_normalize_focus(label), _legacy_melody(label), label)

    def test_the_two_surfaces_now_agree_everywhere(self) -> None:
        for label in _reachable_ui_focuses() + ["", "  ", "Unknown", "Tone Quality"]:
            self.assertEqual(
                normalize_generation_focus(label), _normalize_focus(label), label
            )

    def test_recognized_keys_are_unchanged(self) -> None:
        expected = {
            "Pentatonics": "pentatonics",
            "Guide Tones": "guide_tones",
            "Scales": "scales",
            "Articulation": "articulation",
            "Dynamics": "dynamics",
            "Tone": "tone",
        }
        for label, key in expected.items():
            self.assertEqual(generation_focus_key(label), key, label)
            self.assertIn(key, GENERATION_FOCUS_KEYS)

    def test_unrecognized_focus_still_yields_plain_behaviour(self) -> None:
        for label in ("Rhythm Guitar", "Soloing", "Comping", "Ear Training", "Unknown", ""):
            self.assertEqual(generation_focus_key(label), "", label)

    def test_blank_and_none_are_safe(self) -> None:
        for label in ("", "   ", None):
            self.assertEqual(generation_focus_key(label), "")


class TestDriftIsClosed(unittest.TestCase):
    def test_tone_prefix_now_resolves_identically_on_both_surfaces(self) -> None:
        """The one legacy divergence, converged on the superset.

        "Tone Quality" is a recording-analysis metric title, never a Practice
        Focus label, so no reachable UI option changes behaviour.
        """
        self.assertEqual(normalize_generation_focus("Tone Quality"), "tone")
        self.assertEqual(_normalize_focus("Tone Quality"), "tone")
        self.assertNotIn("Tone Quality", _reachable_ui_focuses())


if __name__ == "__main__":
    unittest.main()
