"""Composition Studio songs must use their own time signature on Backing.

Bug: a Composition saved at 3/4 / 6/8 showed a 4/4 Backing badge and rendered
4/4-length audio, because the chart bundle's ``song_data`` carried no meter and
the Backing page default came from ``default_time_signature_for_record``.
"""

from __future__ import annotations

import io
import types
import unittest
import wave

from backing_track_state import (
    BACKING_STATE_KEY,
    _apply_filters_to_session_keys,
    _normalize_filters,
    prepare_backing_meter_for_widget,
)
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import save_document_to_library, set_active_document
from composition_songs_bridge import commit_composition_active_song
from songs.meter import default_time_signature_for_record, meter_timing
from songs.meter_state import BACKING_METER_OVERRIDE_SONG_KEY, apply_backing_meter_for_song
from songs.music_source import build_active_chart_bundle, on_active_song_identity_changed


class _FakeSt:
    def __init__(self, ss: dict):
        self.session_state = ss

    def rerun(self) -> None:
        return None


def _doc(meter: str | None, title: str = "Meter Comp", bpm: int = 96) -> dict:
    doc = bootstrap_from_vision(genre="Pop", song_idea="meter", title=title, key="C major", bpm=bpm)
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("C F G C"))
    if meter is None:
        doc["global"].pop("time_signature", None)
    else:
        doc["global"]["time_signature"] = meter
    return doc


def _bundle(doc: dict) -> dict:
    ss: dict = {}
    set_active_document(ss, doc, checkpoint=False)
    save_document_to_library(ss, doc)
    commit_composition_active_song(_FakeSt(ss), doc, reset_practice_to_original=True)
    return build_active_chart_bundle(
        ss,
        catalog_genre="Pop",
        catalog_song="Imagine",
        catalog_song_data={"title": "Imagine", "artist": "x", "key": "C", "sections": {"V": ["C"]}},
        level="Intermediate",
        display_key="C",
        cpl_active_key="cpl_active",
        sections_for_level=lambda sd, _lv: dict(sd.get("sections") or {}),
        transpose_sections=lambda sd, _dk: dict(sd.get("sections") or {}),
        song_picker_catalog={},
        song_library={},
    )


def _page_default_meter(bundle: dict) -> str:
    # exactly what streamlit_music_practice_app.py feeds _default_meter
    return default_time_signature_for_record(bundle["song_data"], bundle["sections"], song_title=bundle["song"])


class CompositionDefaultMeter(unittest.TestCase):
    def test_each_meter_is_the_page_default(self) -> None:
        for meter in ("3/4", "6/8", "4/4", "2/4", "12/8"):
            with self.subTest(meter=meter):
                b = _bundle(_doc(meter))
                self.assertEqual(b["source"], "composition_song")
                self.assertEqual(_page_default_meter(b), meter)

    def test_missing_meter_is_4_4(self) -> None:
        self.assertEqual(_page_default_meter(_bundle(_doc(None))), "4/4")

    def test_title_heuristics_do_not_beat_the_composition_meter(self) -> None:
        self.assertEqual(_page_default_meter(_bundle(_doc("4/4", title="Perfect Piano Man 3/4"))), "4/4")
        self.assertEqual(_page_default_meter(_bundle(_doc("3/4", title="Perfect"))), "3/4")


def _load(session: dict, *, sync_id: str, meter: str):
    st = types.SimpleNamespace(session_state=session)
    on_active_song_identity_changed(
        st, pick_key=sync_id, title=sync_id, artist="X", original_key="C", is_custom=False,
        sync_id=sync_id, default_bpm=90, default_groove="Pop groove", default_meter=meter,
        invalidate_backing=lambda _st: None, force_reset=True,
    )
    prepare_backing_meter_for_widget(session, default_meter=meter)
    return apply_backing_meter_for_song(st, song_id=sync_id, default_time_signature=meter)


class CompositionOverrideAndSwitching(unittest.TestCase):
    def test_switch_composition_catalog_composition_resets(self) -> None:
        comp = "composition::abc"
        session: dict = {}
        self.assertEqual(_load(session, sync_id=comp, meter="3/4")[:2], ("3/4", False))
        self.assertEqual(_load(session, sync_id="cat::imagine", meter="4/4")[:2], ("4/4", False))
        self.assertEqual(_load(session, sync_id=comp, meter="3/4")[:2], ("3/4", False))

    def test_explicit_override_wins_and_survives_reload(self) -> None:
        comp = "composition::abc"
        blob = {
            "backing_track_scope": "Full song", "backing_track_loops": 1,
            "backing_time_signature": "4/4", "backing_time_signature_override": True,
            BACKING_METER_OVERRIDE_SONG_KEY: comp, "backing_track_state_version": 1,
        }
        session = {BACKING_STATE_KEY: blob}
        _apply_filters_to_session_keys(session, _normalize_filters(blob))
        self.assertEqual(_load(session, sync_id=comp, meter="3/4")[:2], ("4/4", True))

    def test_override_of_other_song_not_inherited(self) -> None:
        blob = {
            "backing_track_scope": "Full song", "backing_track_loops": 1,
            "backing_time_signature": "4/4", "backing_time_signature_override": True,
            BACKING_METER_OVERRIDE_SONG_KEY: "cat::x", "backing_track_state_version": 1,
        }
        session = {BACKING_STATE_KEY: blob}
        _apply_filters_to_session_keys(session, _normalize_filters(blob))
        self.assertEqual(_load(session, sync_id="composition::abc", meter="6/8")[:2], ("6/8", False))


class CompositionAudioAndFollow(unittest.TestCase):
    @staticmethod
    def _secs(data: bytes) -> float:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())

    def test_audio_duration_and_timeline_use_composition_meter(self) -> None:
        import backing_audio as ba
        from chord_events import sections_dict_to_events

        for meter, pulses in (("3/4", 3), ("6/8", 6), ("4/4", 4)):
            with self.subTest(meter=meter):
                b = _bundle(_doc(meter))
                m = _page_default_meter(b)
                self.assertEqual(m, meter)
                events = sections_dict_to_events({"Verse 1": ["C", "F", "G", "C"]}, time_signature=m)
                wav = ba.generate_backing_track(
                    events, bpm=96, loops=1, style="Pop groove", level="Intermediate",
                    song_title="Meter Comp", song_artist="Composition", time_signature=m,
                )
                expected = 4 * meter_timing(96, m).bar_sec
                dur = self._secs(wav)
                self.assertGreaterEqual(dur, expected - 0.05)
                self.assertLess(dur, expected + 2.5)
                if meter == "3/4":
                    self.assertAlmostEqual(expected, 12 * 60 / 96)


if __name__ == "__main__":
    unittest.main()


class CompositionProjectionRecords(unittest.TestCase):
    def test_projection_and_selected_song_records_use_their_meter(self) -> None:
        from composition_songs_bridge import composition_as_chart_active
        from songs.music_source import composition_song_context_from_session

        for meter in ("3/4", "6/8", "4/4"):
            with self.subTest(meter=meter):
                doc = _doc(meter)
                ss: dict = {}
                set_active_document(ss, doc, checkpoint=False)
                _g, _t, song_data = composition_song_context_from_session(ss)
                self.assertEqual(default_time_signature_for_record(song_data), meter)
                self.assertEqual(default_time_signature_for_record({**composition_as_chart_active(doc), "is_composition": True}), meter)

    def test_legacy_composition_without_meter_is_4_4(self) -> None:
        self.assertEqual(default_time_signature_for_record({"is_composition": True, "title": "Perfect"}), "4/4")


class CompositionBackingContextMeter(unittest.TestCase):
    """The Backing context writes backing_time_signature; it must be the song's."""

    def test_context_meter_is_the_composition_meter(self) -> None:
        from backing_context import build_composition_song_context

        for meter in ("3/4", "6/8", "4/4"):
            with self.subTest(meter=meter):
                doc = _doc(meter)
                ss: dict = {}
                set_active_document(ss, doc, checkpoint=False)
                save_document_to_library(ss, doc)
                ctx = build_composition_song_context(ss, doc=doc, write_global_keys=False)
                self.assertEqual(ctx.source, "composition_song")
                self.assertEqual(ctx.meter, meter)

    def test_legacy_composition_without_meter_context_is_4_4(self) -> None:
        from backing_context import build_composition_song_context

        doc = _doc(None)
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        self.assertEqual(build_composition_song_context(ss, doc=doc, write_global_keys=False).meter, "4/4")

    def test_apply_context_writes_composition_meter_and_keeps_tagged_override(self) -> None:
        from backing_context import apply_backing_context_to_session, build_composition_song_context

        doc = _doc("3/4")
        ss: dict = {}
        set_active_document(ss, doc, checkpoint=False)
        save_document_to_library(ss, doc)
        ctx = build_composition_song_context(ss, doc=doc, write_global_keys=False)
        apply_backing_context_to_session(ss, ctx, widget_safe=False)
        self.assertEqual(ss[BACKING_STATE_KEY]["backing_time_signature"], "3/4")
        self.assertFalse(ss[BACKING_STATE_KEY].get("backing_time_signature_override"))
        # explicit 4/4 override tagged with this song survives a context rebuild
        ss2: dict = {BACKING_STATE_KEY: {
            "backing_track_scope": "Full song", "backing_track_loops": 1,
            "backing_time_signature": "4/4", "backing_time_signature_override": True,
            BACKING_METER_OVERRIDE_SONG_KEY: f"pk::{ctx.bound_pick_key}", "backing_track_state_version": 1,
        }}
        _apply_filters_to_session_keys(ss2, _normalize_filters(ss2[BACKING_STATE_KEY]))
        set_active_document(ss2, doc, checkpoint=False)
        save_document_to_library(ss2, doc)
        apply_backing_context_to_session(ss2, ctx, widget_safe=False)
        self.assertEqual(ss2[BACKING_STATE_KEY]["backing_time_signature"], "4/4")
        self.assertTrue(ss2[BACKING_STATE_KEY]["backing_time_signature_override"])
