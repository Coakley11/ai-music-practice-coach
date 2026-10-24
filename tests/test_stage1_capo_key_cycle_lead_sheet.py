"""Backing lead sheet capo follows the Key Cycling sounding key; guitar shapes stay fixed."""

from __future__ import annotations

import unittest

from backing_key_cycle import (
    advance_key_cycle_now,
    is_cycle_active,
    note_backing_pass_finished,
    start_key_cycle,
    stop_key_cycle,
    temporary_playback_key,
)
from guitar_capo import (
    CAPO_ENABLED_KEY,
    CAPO_SHAPE_KEY,
    build_capo_context,
    playback_capo_fret,
    playback_sounding_key,
    shape_tonic_only,
)
from music_theory import semitone_distance

PICK = "Blues|Blues Test"
# Blues in G, as saved at Practice Key G.
SECTIONS = {"Chorus": ["G7", "C7", "G7", "G7", "C7", "C7", "G7", "G7", "D7", "C7", "G7", "D7"]}


def _guitar_shape_d_session() -> dict:
    return {
        "studio_page": "backing",
        "instrument": "Guitar",
        "active_catalog_pick_key": PICK,
        "display_key": "G",
        "concert_key": "G",
        "practice_key_by_source": {PICK: "G"},
        "_backing_explicit_handoff_source": "regular_song",
        "backing_key_cycle_step": "semitone",
        "backing_key_cycle_direction": "up",
        CAPO_ENABLED_KEY: True,
        CAPO_SHAPE_KEY: "D",
    }


def _ctx(session: dict):
    return build_capo_context(session, SECTIONS, concert_key="G", instrument="Guitar")


class TestCapoFollowsCycleSoundingKey(unittest.TestCase):
    def test_d_shapes_ab_sounding_requires_capo_6(self) -> None:
        session = _guitar_shape_d_session()
        ctx = _ctx(session)
        self.assertEqual(ctx.capo_fret, 5)  # saved G with D shapes
        start_key_cycle(session, start_key="G")
        self.assertTrue(note_backing_pass_finished(session, pass_signature="p1"))
        self.assertEqual(temporary_playback_key(session), "Ab")
        self.assertEqual(playback_sounding_key(session, ctx), "Ab")
        self.assertEqual(playback_capo_fret(session, ctx), 6)
        self.assertEqual(shape_tonic_only(ctx.shape_key), "D")
        self.assertEqual(session[CAPO_SHAPE_KEY], "D")
        self.assertEqual(session["practice_key_by_source"][PICK], "G")

    def test_every_cycle_key_derives_capo_from_fixed_d_shape(self) -> None:
        session = _guitar_shape_d_session()
        ctx = _ctx(session)
        start_key_cycle(session, start_key="G")
        seen = set()
        for i in range(12):
            key = temporary_playback_key(session)
            seen.add(key)
            want = semitone_distance("D", key)
            self.assertEqual(playback_capo_fret(session, ctx), want, key)
            self.assertTrue(0 <= want <= 11)
            self.assertEqual(shape_tonic_only(ctx.shape_key), "D")
            self.assertIsNotNone(advance_key_cycle_now(session))
        self.assertEqual(len(seen), 12)

    def test_stopping_cycle_restores_saved_practice_key_capo(self) -> None:
        session = _guitar_shape_d_session()
        ctx = _ctx(session)
        start_key_cycle(session, start_key="G")
        note_backing_pass_finished(session, pass_signature="p1")
        self.assertEqual(playback_capo_fret(session, ctx), 6)
        stop_key_cycle(session)
        self.assertFalse(is_cycle_active(session))
        self.assertEqual(playback_capo_fret(session, ctx), 5)
        self.assertEqual(playback_sounding_key(session, ctx), "G")
        self.assertEqual(session["practice_key_by_source"][PICK], "G")

    def test_capo_off_is_zero(self) -> None:
        session = _guitar_shape_d_session()
        session[CAPO_ENABLED_KEY] = False
        ctx = _ctx(session)
        start_key_cycle(session, start_key="G")
        note_backing_pass_finished(session, pass_signature="p1")
        self.assertEqual(playback_capo_fret(session, ctx), 0)


class TestLeadSheetCapoLabels(unittest.TestCase):
    def test_shape_chart_names_sounding_key_and_capo_6(self) -> None:
        from songs.backing_chart import render_backing_chord_chart

        shapes = {"Chorus": ["D7", "G7", "D7", "A7"]}
        html = render_backing_chord_chart(
            "Blues Test",
            {"title": "Blues Test", "key": "G"},
            shapes,
            display_key="D",
            groove_style="Bossa Nova",
            bpm=133,
            shape_sections=shapes,
            capo_fret=6,
            capo_shape_key="D",
            sounding_key="Ab",
        )
        self.assertIn("Charts in D major · capo 6", html)
        self.assertNotIn("capo 5", html)
        self.assertIn("You&#x27;re working in Ab major (D major shapes, capo 6)", html)
        self.assertNotIn("feel in D ", html)

    def test_concert_chart_with_capo_keeps_plain_sounding_line(self) -> None:
        from songs.backing_chart import render_backing_chord_chart

        html = render_backing_chord_chart(
            "Blues Test",
            {"title": "Blues Test", "key": "G"},
            {"Chorus": ["Ab7", "Db7"]},
            display_key="Ab",
            bpm=133,
            shape_sections={"Chorus": ["D7", "G7"]},
            capo_fret=6,
            capo_shape_key="D",
            sounding_key="Ab",
        )
        self.assertIn("Charts in D major · capo 6", html)
        self.assertIn("You&#x27;re working in Ab major at 133 BPM", html)

    def test_prepared_cycle_lead_sheet_carries_cycle_capo(self) -> None:
        from backing_key_cycle_handoff import build_cycle_lead_sheet_html

        session = _guitar_shape_d_session()
        html = build_cycle_lead_sheet_html(
            sounding_key="Ab",
            sections={"Chorus": ["Ab7", "Db7", "Ab7", "Eb7"]},
            song_name="Blues Test",
            song_data={"title": "Blues Test", "key": "G"},
            bpm=133,
            chart_display_key="D",
            session=session,
        )
        self.assertIn("Charts in D major · capo 6", html)
        self.assertIn(">G7<", html)  # Db7 sounds, read as the G7 shape
        self.assertNotIn(">Db7<", html)


class TestFollowAlongChordSpaceLabel(unittest.TestCase):
    def test_component_labels_chord_space(self) -> None:
        # Source check: importing the app runs its page script (data-dir dependent).
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        fn = src[src.index("def live_follow_along_component_html(") :]
        fn = fn[: fn.index("\ndef ", 10)]
        self.assertIn('chord_space_label: str = ""', fn)
        self.assertIn('id="live-chord-label"', fn)
        self.assertIn('id="live-chord-sounding"', fn)
        self.assertIn("let chordSpace = {chord_space_label_js};", fn)
        self.assertIn('kcMode === "shape" ? "guitar shape"', fn)
        self.assertIn("`sounds ${{concertChord}}`", fn)
        self.assertIn('chord_space_label="sounding" if _capo_ctx.enabled else ""', src)


if __name__ == "__main__":
    unittest.main()
