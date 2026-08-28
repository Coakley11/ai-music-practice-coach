"""Custom page style presets append and use a local Preset Key only."""

from __future__ import annotations

import copy
import unittest

from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    CPL_PRESET_KEY,
    apply_cpl_style_preset_append,
    cpl_draft_written_key,
    cpl_workspace_practice_key,
    display_sections_for_key,
    export_cpl_widget_state,
    import_cpl_widget_state,
    preset_key_options_for_style,
    preset_tonal_family,
    preview_style_preset_chords,
    set_cpl_preset_key,
    start_new_progression,
    sync_custom_workspace_practice_key,
)
from songs.music_source import SOURCE_CATALOG


PK_SHAPE = "Pop\x1fShape of You"


def _symbols(entries: list[dict]) -> list[str]:
    return [str(e.get("chord") or "").strip() for e in entries]


def _session(*, original: str = "C", practice: str = "C") -> dict:
    active = start_new_progression()
    active["name"] = "Trial Song"
    active["original_key_center"] = original
    active["user_locked_home_key"] = True
    active["progression_style"] = "Blues"
    session = {
        "studio_page": "custom",
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": PK_SHAPE,
        "song": "Shape of You",
        "display_key": practice,
        "concert_key": practice,
        "written_key": "C",
        "guitar_shape_key": "C",
        CPL_ACTIVE_KEY: active,
        "practice_key_by_source": {PK_SHAPE: "Bm"},
    }
    sync_custom_workspace_practice_key(session, practice_key=practice, active=active)
    set_cpl_preset_key(session, "C", style="Blues")
    return session


def _identity(session: dict) -> dict:
    active = session.get(CPL_ACTIVE_KEY) or {}
    return {
        "original": cpl_draft_written_key(active),
        "practice": cpl_workspace_practice_key(session, active),
        "display": str(session.get("display_key") or ""),
        "concert": str(session.get("concert_key") or ""),
        "written": str(session.get("written_key") or ""),
        "shape": str(session.get("guitar_shape_key") or ""),
        "owner": session.get("active_music_source"),
        "ga_song": session.get("song"),
        "preset": str(session.get(CPL_PRESET_KEY) or ""),
    }


class TestCustomPagePresetAppend(unittest.TestCase):
    def test_existing_chords_are_preserved_and_preset_appended(self) -> None:
        session = _session()
        active = session[CPL_ACTIVE_KEY]
        active["original_sections"]["Chorus"] = [
            {"chord": "Am", "bars": 1},
            {"chord": "Dm", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["Am", "Dm", "G", "C7", "F7", "C7", "G7"],
        )

    def test_empty_section_inserts_preset(self) -> None:
        session = _session()
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["C7", "F7", "C7", "G7"],
        )
        self.assertEqual(session[CPL_ACTIVE_KEY]["original_sections"]["Verse"], [])

    def test_second_preset_appends_after_first(self) -> None:
        session = _session()
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="ii–V–I", section_name="Chorus"
        )
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["C7", "F7", "C7", "G7", "Dm7", "F7", "Cmaj7"],
        )

    def test_preset_key_c_to_d_major_transposes_blues_batch(self) -> None:
        self.assertEqual(
            preview_style_preset_chords("Blues", "Quick change", "C"),
            ["C7", "F7", "C7", "G7"],
        )
        self.assertEqual(
            preview_style_preset_chords("Blues", "Quick change", "D"),
            ["D7", "G7", "D7", "A7"],
        )
        session = _session()
        session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"] = [
            {"chord": "Am", "bars": 1},
            {"chord": "Dm", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        set_cpl_preset_key(session, "D", style="Blues")
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["Am", "Dm", "G", "D7", "G7", "D7", "A7"],
        )

    def test_changing_preset_key_does_not_mutate_song_or_owner(self) -> None:
        session = _session(original="C", practice="C")
        before = _identity(session)
        set_cpl_preset_key(session, "D", style="Blues")
        after = _identity(session)
        self.assertEqual(after["preset"], "D")
        for field in (
            "original",
            "practice",
            "display",
            "concert",
            "written",
            "shape",
            "owner",
            "ga_song",
        ):
            self.assertEqual(after[field], before[field], field)

    def test_changing_preset_key_does_not_transpose_existing_chords(self) -> None:
        session = _session()
        session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"] = [
            {"chord": "Am", "bars": 1},
            {"chord": "Dm", "bars": 1},
            {"chord": "G", "bars": 1},
        ]
        set_cpl_preset_key(session, "D", style="Blues")
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["Am", "Dm", "G"],
        )
        self.assertEqual(
            _symbols(display_sections_for_key(session[CPL_ACTIVE_KEY], "C")["Chorus"]),
            ["Am", "Dm", "G"],
        )

    def test_minor_family_preset_uses_minor_keys_and_keeps_qualities(self) -> None:
        self.assertEqual(preset_tonal_family("Funk", "i7–IV7"), "minor")
        self.assertEqual(preset_tonal_family("Blues", "Quick change"), "major")
        options = preset_key_options_for_style("Funk")
        self.assertIn("Dm", options)
        self.assertIn("D", options)
        self.assertEqual(
            preview_style_preset_chords("Funk", "i7–IV7", "D"),
            ["Dm7", "G7", "Dm7", "G7"],
        )
        self.assertEqual(
            preview_style_preset_chords("Funk", "i7–IV7", "Dm"),
            ["Dm7", "G7", "Dm7", "G7"],
        )
        self.assertEqual(
            preview_style_preset_chords("Funk", "I7 vamp", "D"),
            ["D7", "D7", "D7", "D7"],
        )

    def test_preset_key_survives_insertion(self) -> None:
        session = _session()
        set_cpl_preset_key(session, "D", style="Blues")
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        self.assertEqual(session.get(CPL_PRESET_KEY), "D")
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        self.assertEqual(session.get(CPL_PRESET_KEY), "D")
        self.assertEqual(
            _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            ["D7", "G7", "D7", "A7", "D7", "G7", "D7", "A7"],
        )

    def test_refresh_keeps_preset_key_and_does_not_reappend(self) -> None:
        session = _session()
        set_cpl_preset_key(session, "D", style="Blues")
        apply_cpl_style_preset_append(
            session, style="Blues", preset_id="Quick change", section_name="Chorus"
        )
        chords = _symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Chorus"])
        blob = export_cpl_widget_state(session)
        restored = {
            CPL_ACTIVE_KEY: copy.deepcopy(session[CPL_ACTIVE_KEY]),
            "display_key": session.get("display_key"),
            "concert_key": session.get("concert_key"),
            "active_music_source": session.get("active_music_source"),
            "song": session.get("song"),
        }
        import_cpl_widget_state(restored, blob)
        self.assertEqual(restored.get(CPL_PRESET_KEY), "D")
        self.assertEqual(
            _symbols(restored[CPL_ACTIVE_KEY]["original_sections"]["Chorus"]),
            chords,
        )
        self.assertEqual(chords, ["D7", "G7", "D7", "A7"])


if __name__ == "__main__":
    unittest.main()
