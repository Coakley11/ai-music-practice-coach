"""Music correctness tests — Creative key spelling, BPM/style handoff, sidebar sync."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import (
    _backing_groove_style_from_ctx,
    BackingContext,
    build_entry_jam_context,
    flush_pending_backing_handoff_keys,
)
from creative_key_sync import (
    creative_sidebar_key_options,
    is_creative_major_jam_active,
    prepare_creative_sidebar_display_key,
    retranspose_generated_sections,
    sync_sidebar_creative_concert_key,
)
from improvisation_intelligence import generate_style_progression
from improvisation_motif import chord_tone_names
from music_theory import transpose_chord


class TestCreativeMusicCorrectness(unittest.TestCase):
    def test_f_minor_uses_flat_spellings(self) -> None:
        prog = generate_style_progression(style="Blues", key_center="Fm")
        flat = " · ".join(ch for chs in prog.values() for ch in chs)
        self.assertNotIn("A#", flat)
        self.assertNotIn("D#", flat)
        self.assertTrue("Bb" in flat or "Eb" in flat or "Ab" in flat)

    def test_eb_major_uses_flats(self) -> None:
        prog = generate_style_progression(style="Bossa Nova", key_center="Eb")
        flat = " · ".join(ch for chs in prog.values() for ch in chs)
        self.assertNotIn("A#", flat)
        self.assertNotIn("G#", flat)
        self.assertTrue("Bb" in flat or "Eb" in flat or "Ab" in flat)

    def test_c_sharp_spelling_preserved(self) -> None:
        out = retranspose_generated_sections({"Head": ["Dmaj7"]}, from_key="D", to_key="C#")
        self.assertEqual(out["Head"][0], "C#maj7")

    def test_db_spelling_preserved(self) -> None:
        out = retranspose_generated_sections({"Head": ["Dmaj7"]}, from_key="D", to_key="Db")
        self.assertEqual(out["Head"][0], "Dbmaj7")

    def test_style_jam_c_stays_concert_c_not_d(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "C",
            "concert_key": "C",
            "display_key": "D",
            "instrument": "Trumpet",
            "show_chart_in_instrument_key": True,
        }
        st = SimpleNamespace(session_state=session)
        options = prepare_creative_sidebar_display_key(st, session)
        self.assertEqual(session["display_key"], "C")
        self.assertIn("C", options)
        self.assertNotEqual(session["display_key"], "D")

    def test_sidebar_key_change_retransposes_style_jam(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "C",
            "improv_generated_sections": {"Head": ["Dm7", "G7", "Cmaj7"]},
            "_improv_style_key_tracker": "C",
            "display_key": "F",
        }
        sync_sidebar_creative_concert_key(session)
        self.assertEqual(session["improv_style_key"], "F")
        head = session["improv_generated_sections"]["Head"]
        self.assertNotEqual(head[0], "Dm7")

    def test_major_jam_uses_major_sidebar_options_after_minor_song(self) -> None:
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Jam Session Generator",
            "improv_jam_key": "C",
            "active_catalog_pick_key": "shape|artist",
            "song": "Shape of You",
            "display_key": "Bm",
        }
        self.assertTrue(is_creative_major_jam_active(session))
        options = creative_sidebar_key_options(session)
        self.assertIn("C", options)
        self.assertNotIn("Bm", options)

    def test_eb_minor_shape_key_becomes_eb_not_d_sharp(self) -> None:
        from creative_key_sync import sanitize_creative_major_chart_keys, to_major_key_preserve_spelling

        self.assertEqual(to_major_key_preserve_spelling("Eb minor"), "Eb")
        self.assertEqual(to_major_key_preserve_spelling("D# minor"), "D#")
        self.assertEqual(to_major_key_preserve_spelling("F# minor"), "F#")
        session = {
            "studio_page": "creative",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "A",
            "concert_key": "A",
            "display_key": "A",
            "guitar_capo_shape_key": "Eb minor",
        }
        sanitize_creative_major_chart_keys(session)
        self.assertEqual(session["guitar_capo_shape_key"], "Eb")

    def test_regular_song_backing_disables_creative_major_jam(self) -> None:
        from backing_context import restore_regular_song_backing

        session = {
            "studio_page": "backing",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "A",
            "backing_context": {"source": "regular_song"},
        }
        restore_regular_song_backing(session)
        self.assertFalse(is_creative_major_jam_active(session))

    def test_entry_jam_context_maps_bossa_style_to_backing_groove(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "F",
            "improv_style_bpm": 75,
            "improv_groove": "Medium",
            "improv_style_meta": {"style": "Bossa Nova", "bpm": 75, "groove": "Medium"},
            "improv_generated_sections": {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.bpm, 75)
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(_backing_groove_style_from_ctx(ctx), "Bossa nova")

    def test_pending_bpm_flushes_to_slider_key(self) -> None:
        from songs.bpm_state import BPM_WIDGET_KEY, PENDING_BACKING_TRACK_BPM
        from songs.playback_defaults import backing_bpm_slider_widget_key

        session = {
            PENDING_BACKING_TRACK_BPM: 75,
            "_backing_trace_sync_id": "creative:entry_jam:test",
        }
        flush_pending_backing_handoff_keys(session, sync_id="creative:entry_jam:test")
        self.assertEqual(session[BPM_WIDGET_KEY], 75)
        self.assertEqual(session[backing_bpm_slider_widget_key("creative:entry_jam:test")], 75)

    def test_motif_chord_tones_use_key_spelling(self) -> None:
        tones = chord_tone_names("Bb7", reference_key="Fm")
        self.assertIn("Bb", tones[0])

    def test_backing_context_style_not_intensity_for_groove(self) -> None:
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="x",
            song_title="Jazz Swing",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=110,
            style="Jazz Swing",
            groove="Jazz swing",
            groove_intensity="Medium",
        )
        self.assertEqual(_backing_groove_style_from_ctx(ctx), "Jazz swing")


if __name__ == "__main__":
    unittest.main()
