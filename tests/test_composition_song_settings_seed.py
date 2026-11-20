"""Song settings widgets follow the song, so Apply never writes back stale values (2026-11-19).

The widgets were seeded once per session. After "Undo key change" (song back in D) the Original Key widget still
held E, and a BPM-only Apply transposed the whole song back to E.
"""

import unittest

import composition_studio_page as page
from composition_document import bootstrap_from_vision

PREFIX = "composer_utility_settings_t"


def _doc(key_label: str = "D major", key: str = "D", bpm: int = 96, meter: str = "4/4", style: str = "Pop") -> dict:
    doc = bootstrap_from_vision(genre=style, song_idea="Settings seed.")
    g = doc.setdefault("global", {})
    g.update({"original_key_label": key_label, "original_key_center": key, "bpm": bpm, "time_signature": meter})
    doc.setdefault("metadata", {})["style"] = style
    return doc


class TestSongSettingsSeed(unittest.TestCase):
    def test_first_render_seeds_from_the_song(self) -> None:
        ss: dict = {}
        page._seed_song_settings_widgets(ss, _doc(bpm=104, meter="6/8"), key_prefix=PREFIX)
        self.assertEqual(ss[f"{PREFIX}_bpm"], 104)
        self.assertEqual(ss[f"{PREFIX}_meter"], "6/8")
        self.assertEqual(ss[f"{PREFIX}_key"], "D major")
        self.assertEqual(ss[f"{PREFIX}_genre"], "Pop")

    def test_unsaved_panel_edits_survive_reruns(self) -> None:
        ss: dict = {}
        doc = _doc()
        page._seed_song_settings_widgets(ss, doc, key_prefix=PREFIX)
        ss[f"{PREFIX}_bpm"] = 120  # typed, not applied
        ss[f"{PREFIX}_key"] = "E major"
        page._seed_song_settings_widgets(ss, doc, key_prefix=PREFIX)  # rerun, song unchanged
        self.assertEqual(ss[f"{PREFIX}_bpm"], 120)
        self.assertEqual(ss[f"{PREFIX}_key"], "E major")

    def test_song_changed_elsewhere_reseeds_every_widget(self) -> None:
        # D -> E applied, then Undo restores D: the panel must show D again, not the undone E.
        ss: dict = {}
        doc = _doc(key_label="E major", key="E", bpm=96)
        page._seed_song_settings_widgets(ss, doc, key_prefix=PREFIX)
        self.assertEqual(ss[f"{PREFIX}_key"], "E major")
        doc["global"].update({"original_key_label": "D major", "original_key_center": "D"})
        page._seed_song_settings_widgets(ss, doc, key_prefix=PREFIX)
        self.assertEqual(ss[f"{PREFIX}_key"], "D major")
        doc["global"]["bpm"] = 132
        doc["global"]["time_signature"] = "7/8"
        page._seed_song_settings_widgets(ss, doc, key_prefix=PREFIX)
        self.assertEqual(ss[f"{PREFIX}_bpm"], 132)
        self.assertEqual((ss[f"{PREFIX}_meter"], ss[f"{PREFIX}_meter_custom"]),
                         ("7/8", "") if "7/8" in page.COMPOSITION_METERS else (page.COMPOSITION_METER_CUSTOM, "7/8"))

    def test_each_song_has_its_own_namespace(self) -> None:
        a, b = _doc(), _doc()
        self.assertNotEqual(page._utility_settings_prefix(a), page._utility_settings_prefix(b))


if __name__ == "__main__":
    unittest.main()
