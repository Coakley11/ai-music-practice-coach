"""Tests for Creative key sync and analysis mode persistence."""

from __future__ import annotations

import unittest

from creative_key_sync import (
    IMPROV_STYLE_KEY_TRACKER,
    creative_entry_concert_key,
    ensure_creative_analysis_mode_restored,
    persist_creative_analysis_mode,
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

    def test_retranspose_preserves_c_sharp_spelling(self) -> None:
        sections = {"Head": ["Dmaj7"]}
        out_cs = retranspose_generated_sections(sections, from_key="D", to_key="C#")
        out_db = retranspose_generated_sections(sections, from_key="D", to_key="Db")
        self.assertEqual(out_cs["Head"][0], "C#maj7")
        self.assertEqual(out_db["Head"][0], "Dbmaj7")

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

    def test_analysis_mode_survives_backing_navigation(self) -> None:
        from studio_page_persistence import restore_page_snapshot, save_page_snapshot

        session: dict = {
            "studio_page": "creative",
            "creative_lab_analysis_mode": "Improvisation Intelligence",
            "creative_lab_last_mode": "Improvisation Intelligence",
        }
        save_page_snapshot(session, "creative")
        session["studio_page"] = "backing"
        session["creative_lab_analysis_mode"] = "Deep Harmonic Analyzer"
        session["studio_page"] = "creative"
        restore_page_snapshot(session, "creative")
        mode = ensure_creative_analysis_mode_restored(session)
        self.assertEqual(mode, "Improvisation Intelligence")
        self.assertEqual(session["creative_lab_analysis_mode"], "Improvisation Intelligence")

    def test_persist_analysis_mode_never_writes_widget_key(self) -> None:
        session = {
            "creative_lab_analysis_mode": "Improvisation Intelligence",
            "creative_lab_last_mode": "Deep Harmonic Analyzer",
        }
        mode = persist_creative_analysis_mode(session)
        self.assertEqual(mode, "Improvisation Intelligence")
        self.assertEqual(session["creative_lab_analysis_mode"], "Improvisation Intelligence")
        self.assertEqual(session["creative_lab_last_mode"], "Improvisation Intelligence")
        self.assertTrue(session.get("_creative_mode_user_touched"))

    def test_persist_analysis_mode_falls_back_to_last_mode(self) -> None:
        session = {
            "creative_lab_last_mode": "Creative Arrangement Assistant",
        }
        mode = persist_creative_analysis_mode(session)
        self.assertEqual(mode, "Creative Arrangement Assistant")
        self.assertEqual(session["creative_lab_last_mode"], "Creative Arrangement Assistant")
        self.assertNotIn("creative_lab_analysis_mode", session)


    def test_entry_jam_handoff_includes_style_jam_meta(self) -> None:
        session = {
            "active_catalog_pick_key": "say|artist",
            "song": "Say",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Jazz Swing",
            "improv_style_key": "F",
            "improv_style_bpm": 110,
            "improv_mood": "Bright",
            "improv_groove": "Light",
            "improv_difficulty": "Intermediate",
            "improv_style_meta": {
                "style": "Jazz Swing",
                "bpm": 110,
                "groove": "Light",
                "groove_intensity": "Light",
                "mood": "Bright",
                "difficulty": "Intermediate",
                "key": "F",
                "meter": "4/4",
            },
            "improv_generated_sections": {
                "Head (Jazz Swing)": ["Dm7", "G7", "Cmaj7", "A7"],
            },
        }
        ctx = build_entry_jam_context(session)
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(ctx.bpm, 110)
        self.assertEqual(ctx.mood, "Bright")
        self.assertEqual(ctx.groove_intensity, "Light")
        self.assertEqual(ctx.difficulty, "Intermediate")
        self.assertEqual(ctx.style, "Jazz Swing")

    def test_sections_chart_display_transposes_for_written_key(self) -> None:
        from backing_context import sections_dict_for_chart_display

        session = {
            "instrument": "Saxophone",
            "chart_in_instrument_key": True,
            "selected_transposing_instrument": "Alto saxophone (Eb)",
            "concert_key": "Eb",
            "display_key": "Eb",
        }
        concert_sections = {"Head": ["Fm7", "Bb7", "Ebmaj7"]}
        out = sections_dict_for_chart_display(
            session,
            concert_sections,
            concert_key="Eb",
        )
        self.assertNotEqual(out["Head"][0], concert_sections["Head"][0])

    def test_improv_tab_restores_missions_after_refresh(self) -> None:
        from studio_page_state import ensure_improv_intelligence_tab_restored

        session = {"creative_improv_intelligence_tab": "Missions", "improv_intelligence_tab": "Entry & Jam"}
        tab = ensure_improv_intelligence_tab_restored(session)
        self.assertEqual(tab, "Missions")
        self.assertEqual(session["improv_intelligence_tab"], "Missions")

    def test_improv_tab_persist_does_not_write_widget(self) -> None:
        from studio_page_state import persist_improv_intelligence_tab

        session = {"improv_intelligence_tab": "Metrics & AI"}
        tab = persist_improv_intelligence_tab(session)
        self.assertEqual(tab, "Metrics & AI")
        self.assertEqual(session["creative_improv_intelligence_tab"], "Metrics & AI")

    def test_creative_key_sync_exports_sidebar_change_handler(self) -> None:
        from creative_key_sync import on_sidebar_practice_concert_key_change

        self.assertTrue(callable(on_sidebar_practice_concert_key_change))


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
