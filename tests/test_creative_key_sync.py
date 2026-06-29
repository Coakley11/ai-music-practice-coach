"""Tests for Creative key sync and analysis mode persistence."""

from __future__ import annotations

import unittest

from creative_key_sync import (
    IMPROV_STYLE_KEY_TRACKER,
    creative_entry_concert_key,
    ensure_creative_analysis_mode_restored,
    retranspose_generated_sections,
    sync_creative_key_change,
)
from backing_context import build_entry_jam_context, compute_source_signature, format_backing_context_banner


class TestCreativeKeySync(unittest.TestCase):
    def test_style_jam_key_updates_practice_concert_key(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "Eb",
            "display_key": "G",
            "concert_key": "G",
            "improv_generated_sections": {
                "Head (Jazz Swing)": ["Dm7", "G7", "Cmaj7", "A7"],
            },
            IMPROV_STYLE_KEY_TRACKER: "G",
        }
        sync_creative_key_change(session, "Eb")
        self.assertEqual(session.get("concert_key"), "Eb")
        self.assertEqual(session.get("_pending_display_key"), "Eb")
        head = session["improv_generated_sections"]["Head (Jazz Swing)"]
        self.assertNotEqual(head[0], "Dm7")

    def test_style_jam_chords_transpose_after_key_change(self) -> None:
        from improvisation_intelligence import generate_style_progression

        in_g = generate_style_progression(style="Jazz Swing", key_center="G")
        out = retranspose_generated_sections(in_g, from_key="G", to_key="Eb")
        self.assertNotEqual(
            list(in_g.values())[0][0],
            list(out.values())[0][0],
        )

    def test_entry_jam_handoff_uses_creative_key_and_bpm(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "display_key": "G",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_key": "Eb",
            "improv_style_bpm": 85,
            "improv_style_meta": {"style": "Jazz Swing", "bpm": 85, "groove": "Medium"},
            "improv_generated_sections": {
                "Head (Jazz Swing)": ["Fm7", "Bb7", "Ebmaj7", "C7"],
            },
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.concert_key, "Eb")
        self.assertEqual(ctx.display_key, "Eb")
        self.assertEqual(ctx.bpm, 85)
        self.assertEqual(ctx.style, "Jazz Swing")
        banner = format_backing_context_banner(ctx)
        self.assertIn("Jazz Swing", banner)
        self.assertIn("Concert Eb", banner)
        self.assertIn("85 BPM", banner)

    def test_reopen_updates_signature_when_key_changes(self) -> None:
        session = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": "G",
            "improv_style_meta": {"bpm": 85, "groove": "Medium"},
            "improv_generated_sections": {"Head (Jazz Swing)": ["Dm7", "G7"]},
        }
        ctx1 = build_entry_jam_context(session)
        session["improv_style_key"] = "Eb"
        session["concert_key"] = "Eb"
        ctx2 = build_entry_jam_context(session)
        self.assertNotEqual(compute_source_signature(ctx1), compute_source_signature(ctx2))

    def test_creative_entry_concert_key_jam_session(self) -> None:
        session = {"improv_entry_mode": "Jam Session Generator", "improv_jam_key": "Eb"}
        self.assertEqual(creative_entry_concert_key(session), "Eb")

    def test_analysis_mode_restores_last_mode(self) -> None:
        session = {"creative_lab_last_mode": "Improvisation Intelligence"}
        mode = ensure_creative_analysis_mode_restored(session)
        self.assertEqual(mode, "Improvisation Intelligence")
        self.assertEqual(session["creative_lab_analysis_mode"], "Improvisation Intelligence")

    def test_analysis_mode_default_when_unset(self) -> None:
        session: dict = {}
        mode = ensure_creative_analysis_mode_restored(session)
        self.assertEqual(mode, "Deep Harmonic Analyzer")


class TestWrittenKeyLabels(unittest.TestCase):
    def test_alto_sax_written_key_for_concert_eb(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            written_key_for_instrument,
        )

        session = {
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Alto saxophone (Eb)",
        }
        self.assertEqual(written_key_for_instrument("Eb", "Saxophone", session), "C")

    def test_tenor_sax_written_key_for_concert_eb(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            written_key_for_instrument,
        )

        session = {
            CHART_IN_INSTRUMENT_KEY_KEY: True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        }
        self.assertEqual(written_key_for_instrument("Eb", "Saxophone", session), "F")


if __name__ == "__main__":
    unittest.main()
