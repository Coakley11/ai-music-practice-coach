"""Custom chord builder: the selected root is shown selected (red), and only that root."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _page() -> None:
    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


def _root_buttons(at: AppTest) -> dict[str, str]:
    """root name -> button style ("primary" is the selected, red state)."""
    out: dict[str, str] = {}
    for b in at.button:
        m = re.fullmatch(r"cpl_extroot_C_Verse_(.+)", str(b.key or ""))
        if m:
            out[m.group(1)] = b.proto.type
    return out


def _selected(at: AppTest) -> list[str]:
    return sorted(root for root, kind in _root_buttons(at).items() if kind == "primary")


def _preview(at: AppTest) -> str:
    for m in at.markdown:
        if "Selected chord:" in str(m.value):
            return re.sub(r"<[^>]+>", "", str(m.value))
    return ""


class TestRootSelectionState(unittest.TestCase):
    def test_exactly_one_root_is_selected_and_it_follows_each_click(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120).run()
        self.assertFalse(at.exception)
        self.assertIn("Ab", _root_buttons(at))  # chromatic roots are offered too
        self.assertEqual(len(_selected(at)), 1)

        for root in ("F", "G", "Ab", "Bb"):
            at.button(key=f"cpl_extroot_C_Verse_{root}").click().run()
            self.assertEqual(_selected(at), [root], root)
            self.assertIn(f"Selected chord: {root}", _preview(at))

    def test_selection_survives_ordinary_reruns_and_does_not_snap_back(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120).run()
        at.button(key="cpl_extroot_C_Verse_G").click().run()
        for _ in range(3):
            at.run()
            self.assertEqual(_selected(at), ["G"])

    def test_root_and_quality_selections_combine_in_the_preview(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120).run()
        at.button(key="cpl_extroot_C_Verse_F").click().run()
        at.button(key="cpl_extqual_C_Verse_Minor").click().run()
        self.assertEqual(_selected(at), ["F"])
        self.assertIn("Selected chord: Fm", _preview(at))
        at.button(key="cpl_extroot_C_Verse_Bb").click().run()
        self.assertEqual(_selected(at), ["Bb"])
        self.assertIn("Selected chord: Bbm", _preview(at))

    def test_a_stale_root_from_another_key_is_not_left_selected(self) -> None:
        at = AppTest.from_function(_page, default_timeout=120)
        at.session_state["cpl_ext_root_note"] = "Z#"
        at.run()
        self.assertEqual(len(_selected(at)), 1)


class TestFinishedSongStructureHasNoRomanNumerals(unittest.TestCase):
    def test_every_overview_of_the_song_omits_roman_numerals(self) -> None:
        src = (Path(__file__).resolve().parents[1] / "cpl_page_ui.py").read_text(encoding="utf-8")
        calls = [m.start() for m in re.finditer(r"song_structure_overview_html\(", src)]
        # the finished view and the "Song structure" summary above Launch in the studio
        bodies = [src[i : src.index(")", src.index("only_filled=True", i)) + 1] for i in calls]
        self.assertEqual(len(bodies), 2)
        for body in bodies:
            self.assertIn("show_roman=False", body)


if __name__ == "__main__":
    unittest.main()
