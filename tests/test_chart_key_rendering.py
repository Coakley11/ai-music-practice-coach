"""Charts must use transposed chart_key, not original catalog home key."""

from __future__ import annotations

import unittest

from chart_level_arrangement import level_view_of_sections, resolve_level_chart
from music_theory import transpose_sections
from songs.music_source import build_active_chart_bundle


def _catalog_song() -> dict:
    return {
        "title": "Test Song",
        "artist": "Artist",
        "genre": "Pop",
        "key": "Bm",
        "sections": {"Verse": ["Bm", "G", "D", "A"]},
        "extensions": {"default_bpm": 100, "default_groove": "Pop groove"},
    }


class TestChartKeyRendering(unittest.TestCase):
    def test_bundle_transpose_survives_level_view(self) -> None:
        """Regression: resolve_level_chart must not replace transposed chord sections."""
        song_data = _catalog_song()
        bundle = build_active_chart_bundle(
            {"active_music_source": "catalog_song"},
            catalog_genre="Pop",
            catalog_song="Test Song — Artist",
            catalog_song_data=song_data,
            level="Advanced",
            display_key="C#m",
            cpl_active_key="cpl_active_progression",
            sections_for_level=lambda data, _level: dict(data.get("sections") or {}),
            transpose_sections=transpose_sections,
        )
        sections = bundle["sections"]
        level_view, _untransposed = resolve_level_chart(bundle["song_data"], "Advanced")
        self.assertEqual(_untransposed["Verse"][0], "Bm")

        if level_view:
            order = list(level_view.get("section_order") or [])
            if order:
                sections = level_view_of_sections(sections, section_order_for_level=order)

        self.assertEqual(sections["Verse"][0], "C#m")
        self.assertNotEqual(sections["Verse"][0], "Bm")


if __name__ == "__main__":
    unittest.main()
