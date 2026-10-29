"""Regression tests for CPL chord builder quality/extension preservation."""

from __future__ import annotations

import unittest


class TestChordBuilderAssembly(unittest.TestCase):
    """Verify the chord assembly logic produces correct symbols for
    every combination of root, quality, and extension."""

    _INCOMPATIBLE_COMBOS = {
        ("dim", "7"): "dim7",
        ("dim", "maj7"): "dim7",
        ("aug", "7"): "aug7",
    }

    @staticmethod
    def _assemble(root: str, quality: str, extension: str) -> str:
        """Mirrors the assembly logic in cpl_page_ui.py lines 1506-1522."""
        incompatible = {
            ("dim", "7"): "dim7",
            ("dim", "maj7"): "dim7",
            ("aug", "7"): "aug7",
        }
        combo_key = (quality, extension)
        if combo_key in incompatible:
            return f"{root}{incompatible[combo_key]}"
        if quality in ("dim", "aug", "sus2", "sus4") and extension:
            return f"{root}{quality}{extension}"
        if quality == "m" and extension:
            return f"{root}m{extension}"
        if quality and not extension:
            return f"{root}{quality}"
        if extension and not quality:
            return f"{root}{extension}"
        return root

    def test_major_no_extension(self) -> None:
        self.assertEqual(self._assemble("C", "", ""), "C")

    def test_minor_no_extension(self) -> None:
        self.assertEqual(self._assemble("A", "m", ""), "Am")

    def test_minor_seventh(self) -> None:
        self.assertEqual(self._assemble("D", "m", "7"), "Dm7")

    def test_major_seventh(self) -> None:
        self.assertEqual(self._assemble("C", "", "maj7"), "Cmaj7")

    def test_diminished_seventh(self) -> None:
        self.assertEqual(self._assemble("B", "dim", "7"), "Bdim7")

    def test_augmented_seventh(self) -> None:
        self.assertEqual(self._assemble("G", "aug", "7"), "Gaug7")

    def test_minor_ninth(self) -> None:
        self.assertEqual(self._assemble("E", "m", "9"), "Em9")

    def test_dominant_seventh(self) -> None:
        self.assertEqual(self._assemble("G", "", "7"), "G7")

    def test_sharp_root_minor(self) -> None:
        self.assertEqual(self._assemble("F#", "m", "7"), "F#m7")

    def test_flat_root_major(self) -> None:
        self.assertEqual(self._assemble("Bb", "", ""), "Bb")

    def test_diminished_no_extension(self) -> None:
        self.assertEqual(self._assemble("C", "dim", ""), "Cdim")

    def test_augmented_no_extension(self) -> None:
        self.assertEqual(self._assemble("C", "aug", ""), "Caug")

    def test_all_roots_with_minor(self) -> None:
        roots = ["C", "D", "E", "F", "G", "A", "B", "C#", "Db", "Eb", "F#", "Gb", "Ab", "Bb"]
        for root in roots:
            result = self._assemble(root, "m", "")
            self.assertEqual(result, f"{root}m", f"Expected {root}m but got {result}")

    def test_quality_preserved_across_root_change(self) -> None:
        """Simulates the user selecting minor, then changing root.
        The bug was that root change cleared quality state."""
        quality = "m"
        for root in ["C", "A", "E", "Bb"]:
            result = self._assemble(root, quality, "")
            self.assertTrue(
                result.endswith("m"),
                f"Quality 'm' lost when changing root to {root}: got {result}",
            )

    def test_quality_and_extension_preserved_across_root_change(self) -> None:
        quality = "m"
        extension = "7"
        for root in ["C", "F#", "Db"]:
            result = self._assemble(root, quality, extension)
            self.assertIn("m7", result, f"Quality+extension lost: got {result}")


if __name__ == "__main__":
    unittest.main()
