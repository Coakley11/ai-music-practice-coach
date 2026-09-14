"""Shape-seeded regressions: SBI/Jam ownership, Send to Practice, Focus, icons."""

from __future__ import annotations

import inspect
import unittest

from music_feature_icons import FEATURE_ICONS, semantic_field_icon
from song_catalog.catalog import format_pick_key

SHAPE_PICK = format_pick_key("Pop", "Shape of You — Ed Sheeran")


def _shape_catalog_session(**extra: object) -> dict:
    session = {
        "studio_page": "backing",
        "instrument": "Piano",
        "focus": "Harmony",
        "song": "Shape of You",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "genre": "Pop",
            "key": "Bm",
            "pick_key": SHAPE_PICK,
        },
        "active_catalog_pick_key": SHAPE_PICK,
        "display_key": "Bm",
        "concert_key": "Bm",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "guitar_capo_enabled": True,
        "guitar_capo_shape_key": "C",
        "_capo_shape_seed_source_id": SHAPE_PICK,
    }
    session.update(extra)
    return session


class TestSbiHasNoSendToPractice(unittest.TestCase):
    def test_sbi_entry_row_never_passes_practice_callback(self) -> None:
        from improvisation_intelligence_ui import _tab_entry_modes

        src = inspect.getsource(_tab_entry_modes)
        self.assertIn("workflow=\"sbi\"", src.replace("'", '"'))
        self.assertIn("on_open_practice=None", src)
        self.assertIn("SBI Active / Custom / Composition", src)


class TestSbiCustomCatalogIsolation(unittest.TestCase):
    def test_shape_seeded_custom_chart_identity_has_no_shape(self) -> None:
        from backing_context import build_song_improv_context, owned_backing_chart_identity
        from songs.backing_chart import render_backing_chord_chart

        session = _shape_catalog_session(
            improv_song_source="Custom progression",
            sbi_preview_source="Custom progression",
            cpl_active_progression={
                "name": "Trial Song",
                "id": "trial-leak-1",
                "original_key_center": "E",
                "bpm": 120,
                "progression_style": "Blues",
                "groove_style": "Blues",
                "time_signature": "4/4",
                "original_sections": {
                    "A": [
                        {"chord": "Em/D", "bars": 2},
                        {"chord": "D", "bars": 2},
                    ],
                },
            },
        )
        ctx = build_song_improv_context(session)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        html_out = render_backing_chord_chart(
            ident["song_name"],
            ident["song_data"],
            {"A": ["Em/D", "Em/D", "D", "D"]},
            display_key=ident["original_key"],
            bpm=int(ident["bpm"]),
            groove_style="Blues",
        )
        blob = " ".join(
            [
                ident["song_name"],
                str(ident["song_data"]),
                ident["coaching"],
                html_out,
            ]
        )
        self.assertEqual(ident["song_name"], "Trial Song")
        self.assertNotIn("Shape of You", blob)
        self.assertNotIn("Ed Sheeran", blob)
        self.assertNotIn("Shape of You — Backing chart", html_out)
        self.assertIn("Trial Song", html_out)
        self.assertNotEqual(str(ident["song_data"].get("key") or ""), "Bm")

    def test_composition_sbi_chart_identity_has_no_catalog(self) -> None:
        from backing_context import build_song_improv_context, owned_backing_chart_identity

        session = _shape_catalog_session(
            improv_song_source="Composition",
            sbi_preview_source="Composition",
            composition_active_title="My Composition",
        )
        ctx = build_song_improv_context(session)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertIsNotNone(ident)
        blob = ident["song_name"] + str(ident["song_data"]) + ident["coaching"]
        self.assertNotIn("Shape of You", blob)
        self.assertNotIn("Ed Sheeran", blob)
        self.assertNotIn("Bm", str(ident["song_data"].get("key") or ""))


class TestJamOwnsKeys(unittest.TestCase):
    def test_c_major_jam_ignores_shape_capo_and_title(self) -> None:
        from backing_context import BackingContext, owned_backing_chart_identity, set_backing_context
        from backing_musical_state import resolve_current_backing_musical_state
        from backing_practice_key_control import commit_backing_practice_key

        session = _shape_catalog_session(
            improv_entry_mode="Jam Session Generator",
            improv_jam_key="C",
            display_key="C",
            concert_key="C",
            studio_page="backing",
            instrument="Guitar",
        )
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry Style Jam",
            active_song_id="generated::Jam Session Generator::cmaj",
            song_title="Jam Session Generator",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=110,
            style="Jazz Swing",
            groove="Jazz Swing",
            meter="4/4",
            progression=["C", "Am", "F", "G"],
            entry_mode="Jam Session Generator",
            mode_label="Jam Session",
        )
        set_backing_context(session, ctx)
        ident = owned_backing_chart_identity(session, ctx)
        self.assertEqual(ident["song_name"], "Jam Session Generator")
        self.assertNotIn("Shape of You", ident["song_name"])
        self.assertNotIn("Shape of You", ident["coaching"])
        state = resolve_current_backing_musical_state(session, rec=None, applied_bpm=110)
        self.assertTrue(str(state.practice_concert_key).startswith("C"))
        self.assertFalse(state.guitar_shape_on)
        self.assertEqual(state.chart_display_key, state.practice_concert_key)
        applied = commit_backing_practice_key(session, "D")
        self.assertTrue(str(applied or session.get("improv_jam_key") or "").startswith("D"))
        self.assertEqual(session.get("improv_jam_key"), "D")
        self.assertNotEqual(str(session.get("song") or ""), "D")


class TestPracticeFocusSurfaces(unittest.TestCase):
    def test_catalog_preview_does_not_keep_trial_song(self) -> None:
        from practice_focus_creative import format_creative_practice_focus_caption

        session = _shape_catalog_session(
            studio_page="creative",
            improv_song_source="Active song",
            sbi_preview_source="Active song",
            cpl_active_progression={"name": "Trial Song", "original_key_center": "E"},
        )
        caption = format_creative_practice_focus_caption(session)
        self.assertIn("Shape of You", caption)
        self.assertNotIn("Trial Song", caption)
        self.assertNotIn("SBI Custom", caption)

    def test_focus_changes_coaching_not_identity(self) -> None:
        from practice_focus_creative import (
            format_focus_surface_guidance,
            resolve_creative_practice_focus,
        )
        from practice_setup_globals import set_active_focus, set_active_instrument

        session = _shape_catalog_session(
            studio_page="creative",
            instrument="Piano",
        )
        set_active_instrument(session, "Piano")
        frozen_kind = None
        frozen_id = None
        copies = {}
        for focus in ("Harmony", "Rhythm", "Dynamics", "Improvisation", "Voicings"):
            set_active_focus(session, focus)
            ctx = resolve_creative_practice_focus(session)
            if frozen_kind is None:
                frozen_kind = ctx["kind"]
                frozen_id = ctx["identity"]
            self.assertEqual(ctx["kind"], frozen_kind)
            self.assertEqual(ctx["identity"], frozen_id)
            copies[focus] = {
                "live": format_focus_surface_guidance(session, "live_coach"),
                "missions": format_focus_surface_guidance(session, "missions"),
                "harmony": format_focus_surface_guidance(session, "harmony"),
                "motif": format_focus_surface_guidance(session, "motif"),
                "backing": format_focus_surface_guidance(session, "backing"),
            }
        self.assertNotEqual(copies["Harmony"]["live"], copies["Rhythm"]["live"])
        self.assertNotEqual(copies["Harmony"]["missions"], copies["Dynamics"]["missions"])
        self.assertNotEqual(copies["Improvisation"]["motif"], copies["Voicings"]["motif"])
        self.assertNotEqual(copies["Harmony"]["backing"], copies["Rhythm"]["backing"])


class TestCanonicalIcons(unittest.TestCase):
    def test_return_catalog_uses_songs_icon(self) -> None:
        from backing_context import build_regular_song_context
        from backing_source_navigation import return_to_source_button_label

        catalog = build_regular_song_context(
            {"song": "Day Tripper", "display_key": "G", "concert_key": "G"}
        )
        label = return_to_source_button_label(catalog)
        self.assertTrue(label.startswith(FEATURE_ICONS["songs"]))
        self.assertNotIn("🎵", label)

    def test_level_and_shape_key_registry(self) -> None:
        self.assertEqual(FEATURE_ICONS["level"], "📈")
        self.assertEqual(semantic_field_icon("level"), "📈")
        self.assertEqual(semantic_field_icon("shape_key"), "🎸")
        self.assertEqual(semantic_field_icon("written_key"), "🎷")
        self.assertNotEqual(semantic_field_icon("shape_key"), semantic_field_icon("written_key"))


if __name__ == "__main__":
    unittest.main()
