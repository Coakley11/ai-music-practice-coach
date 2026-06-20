"""Custom Progression Lab — chord tile rendering and display-key sync."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    commit_home_sections,
    cpl_apply_pending_chord_to_section,
    cpl_progression_bar_chart_html,
    cpl_section_progression_view,
    default_active_progression,
    display_entries_for_section,
    entries_chord_tiles_html,
    ensure_original_structure,
    song_structure_overview_html,
    written_home_key,
)


class TestCplChordDisplay(unittest.TestCase):
    def test_progression_tiles_render_after_adding_chords(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        home = ensure_original_structure(active)["original_sections"]
        home["Verse"] = [{"chord": "C", "bars": 2}, {"chord": "G", "bars": 2}]
        active = commit_home_sections(active, home)
        display = display_entries_for_section(active, "C", "Verse")
        html = entries_chord_tiles_html(display, time_signature="4/4")
        self.assertEqual(len(display), 2)
        self.assertIn("chord-symbol", html)
        self.assertIn(">C<", html)
        self.assertIn(">G<", html)

    def test_display_key_transpose_updates_tiles(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        home = ensure_original_structure(active)["original_sections"]
        home["Verse"] = [{"chord": "Am", "bars": 1}, {"chord": "Dm", "bars": 1}]
        active = commit_home_sections(active, home)
        home_key = written_home_key(active)
        display = display_entries_for_section(active, "G", "Verse")
        html = entries_chord_tiles_html(display)
        self.assertEqual(home_key, "C")
        self.assertEqual(display[0]["chord"], "Em")
        self.assertIn(">Em<", html)

    def test_flat_home_key_keeps_flat_spelling_when_transposed(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "Db"
        active["user_locked_home_key"] = True
        home = ensure_original_structure(active)["original_sections"]
        home["Verse"] = [{"chord": "Db", "bars": 1}, {"chord": "Gb", "bars": 1}]
        active = commit_home_sections(active, home)
        display = display_entries_for_section(active, "Eb", "Verse")
        self.assertEqual(display[0]["chord"], "Eb")
        self.assertEqual(display[1]["chord"], "Ab")

    def test_bar_chart_expands_each_bar(self) -> None:
        entries = [{"chord": "Em", "bars": 4}, {"chord": "Dm", "bars": 4}]
        html = cpl_progression_bar_chart_html(entries)
        self.assertEqual(html.count(">Em<"), 4)
        self.assertEqual(html.count(">Dm<"), 4)
        self.assertIn("cpl-bar-chart-line", html)
        self.assertIn("cpl-measure-bar", html)

    def test_song_structure_uses_bar_charts(self) -> None:
        active = default_active_progression()
        active["name"] = "Trial Song"
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        home = ensure_original_structure(active)["original_sections"]
        home["Verse"] = [{"chord": "C", "bars": 4}, {"chord": "Am", "bars": 4}]
        home["Chorus"] = [{"chord": "F", "bars": 4}, {"chord": "G", "bars": 4}]
        active = commit_home_sections(active, home)
        html = song_structure_overview_html(active, "C", only_filled=True)
        self.assertIn("Trial Song", html)
        self.assertIn("Verse:", html)
        self.assertIn("Chorus:", html)
        self.assertEqual(html.count("cpl-bar-chart-line"), 2)
        self.assertEqual(html.count(">C<"), 4)

    def test_page_path_apply_chord_then_build_view(self) -> None:
        active = default_active_progression()
        active["original_key_center"] = "C"
        active["user_locked_home_key"] = True
        active = cpl_apply_pending_chord_to_section(
            active,
            section_name="Verse",
            pending_chord="C",
            bars=1,
        )
        view = cpl_section_progression_view(
            active,
            section_name="Verse",
            preview_key=written_home_key(active),
        )
        self.assertTrue(view["has_chords"])
        self.assertGreater(len(view["native_rows"]), 0)
        self.assertEqual(view["native_rows"][0][0], "C")
        self.assertIn("C — 1 bar", view["native_lines"])
        self.assertIn("cpl-bar-chart-line", view["chart_html"])
        self.assertIn(">C<", view["panel_html"])


if __name__ == "__main__":
    unittest.main()
