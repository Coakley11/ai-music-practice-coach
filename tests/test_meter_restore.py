"""A stale saved meter must never beat the active catalog song's own time signature.

Root cause (fixed): ``backing_track_state._normalize_filters`` records a missing
meter as ``"4/4"`` with ``backing_time_signature_override`` False. On the first
load after a restore, ``prepare_backing_meter_for_widget`` /
``apply_backing_meter_for_song`` / ``bind_backing_rendered_widgets_from_canonical``
/ ``_apply_filters_to_session_keys`` copied that saved "4/4" into the live
``backing_time_signature`` even though the musician never overrode anything, so
Piano Man (3/4) or Perfect (6/8) played, followed and clicked at 4/4.

Rules pinned here:
* no genuine user override (flag False)  -> the song's own meter wins;
* explicit saved override (flag True)    -> the saved meter wins;
* song change resets to the new song's meter and back again;
* the renderer, the follow-along timeline and the metronome all see that meter.
"""

from __future__ import annotations

import io
import json
import re
import types
import unittest
import wave

from backing_track_state import (
    BACKING_RESTORED_KEY,
    BACKING_STATE_KEY,
    BACKING_WIDGETS_SEEDED_KEY,
    _apply_filters_to_session_keys,
    bind_backing_rendered_widgets_from_canonical,
    prepare_backing_meter_for_widget,
)
from songs.meter import meter_timing
from songs.meter_state import (
    BACKING_METER_KEY,
    BACKING_METER_OVERRIDE_KEY,
    apply_backing_meter_for_song,
)

CASES = [("3/4", "Piano Man"), ("6/8", "Perfect"), ("4/4", "Plain 4/4"), ("12/8", "Twelve Eight")]


def _blob(meter: str | None, override: bool, loops: int = 1) -> dict:
    blob = {
        "backing_track_scope": "Full song",
        "backing_track_loops": loops,
        "backing_time_signature_override": override,
        "backing_track_state_version": 1,
    }
    if meter is not None:
        blob["backing_time_signature"] = meter
    return blob


def _st(session: dict):
    return types.SimpleNamespace(session_state=session)


def _first_load(session: dict, song_id: str, default: str) -> tuple[str, bool, str]:
    """The app's order on a Backing render: prepare (widget seed) then apply."""
    prepare_backing_meter_for_widget(session, default_meter=default)
    return apply_backing_meter_for_song(_st(session), song_id=song_id, default_time_signature=default)


class StaleSavedMeterLosesToSong(unittest.TestCase):
    def test_restored_stale_4_4_no_override_song_meter_wins(self) -> None:
        for meter, title in CASES:
            for restored_flag in (True, False):
                with self.subTest(song=title, restored_flag=restored_flag):
                    session = {BACKING_STATE_KEY: _blob("4/4", False)}
                    if restored_flag:
                        session[BACKING_RESTORED_KEY] = True
                    applied, override, default = _first_load(session, f"cat::{title}", meter)
                    self.assertEqual((applied, override, default), (meter, False, meter))
                    self.assertEqual(session[BACKING_METER_KEY], meter)
                    self.assertFalse(session[BACKING_METER_OVERRIDE_KEY])

    def test_apply_alone_on_restored_session(self) -> None:
        for meter, title in CASES:
            with self.subTest(song=title):
                session = {BACKING_STATE_KEY: _blob("4/4", False)}
                applied, override, _ = apply_backing_meter_for_song(
                    _st(session), song_id=f"cat::{title}", default_time_signature=meter
                )
                self.assertEqual((applied, override), (meter, False))

    def test_blob_without_any_meter_key(self) -> None:
        session = {BACKING_STATE_KEY: _blob(None, False)}
        applied, override, _ = _first_load(session, "cat::Piano Man", "3/4")
        self.assertEqual((applied, override), ("3/4", False))

    def test_stale_non_default_meter_without_override_also_loses(self) -> None:
        # e.g. a leftover 6/8 saved with override False on a 4/4 song.
        session = {BACKING_STATE_KEY: _blob("6/8", False)}
        applied, override, _ = _first_load(session, "cat::Plain", "4/4")
        self.assertEqual((applied, override), ("4/4", False))

    def test_explicit_override_true_still_wins(self) -> None:
        for default, saved in (("3/4", "4/4"), ("6/8", "4/4"), ("4/4", "3/4"), ("4/4", "12/8"), ("3/4", "6/8")):
            with self.subTest(default=default, saved=saved):
                session = {BACKING_STATE_KEY: _blob(saved, True), BACKING_RESTORED_KEY: True}
                applied, override, d = _first_load(session, "cat::X", default)
                self.assertEqual((applied, override, d), (saved, True, default))
                self.assertEqual(session[BACKING_METER_KEY], saved)
                self.assertTrue(session[BACKING_METER_OVERRIDE_KEY])

    def test_live_session_override_true_survives_reapply(self) -> None:
        session = {BACKING_METER_KEY: "4/4", BACKING_METER_OVERRIDE_KEY: True, "_last_backing_meter_song": "cat::PM"}
        applied, override, _ = apply_backing_meter_for_song(
            _st(session), song_id="cat::PM", default_time_signature="3/4"
        )
        self.assertEqual((applied, override), ("4/4", True))

    def test_song_change_3_4_to_4_4_and_back(self) -> None:
        session = {BACKING_STATE_KEY: _blob("4/4", False)}
        st = _st(session)
        seq = [("cat::PM", "3/4"), ("cat::Plain", "4/4"), ("cat::PM", "3/4"), ("cat::Perfect", "6/8"), ("cat::PM", "3/4")]
        for i, (sid, meter) in enumerate(seq):
            if i == 0:
                prepare_backing_meter_for_widget(session, default_meter=meter)
            applied, override, _ = apply_backing_meter_for_song(st, song_id=sid, default_time_signature=meter)
            self.assertEqual((applied, override), (meter, False), (i, sid))
            self.assertEqual(session[BACKING_METER_KEY], meter)

    def test_song_change_canonicalize_clears_override_then_song_meter_wins(self) -> None:
        # In the app the song-change reset is owned by canonicalize_backing_defaults_for_song.
        from songs.playback_defaults import canonicalize_backing_defaults_for_song

        session = {BACKING_STATE_KEY: _blob("4/4", True), BACKING_RESTORED_KEY: True}
        st = _st(session)
        canonicalize_backing_defaults_for_song(  # first call after restore = same-song restore
            st, sync_id="cat::PM", active_song_bpm=88, active_song_groove="Pop groove", active_song_meter="3/4"
        )
        a, o, _ = _first_load(session, "cat::PM", "3/4")
        self.assertEqual((a, o), ("4/4", True))
        for sid, meter in (("cat::Perfect", "6/8"), ("cat::PM", "3/4"), ("cat::Plain", "4/4")):
            canonicalize_backing_defaults_for_song(
                st, sync_id=sid, active_song_bpm=90, active_song_groove="Pop groove", active_song_meter=meter
            )
            a, o, _ = apply_backing_meter_for_song(st, song_id=sid, default_time_signature=meter)
            self.assertEqual((a, o), (meter, False), sid)

    def test_session_hydration_does_not_copy_stale_meter(self) -> None:
        # music_resume_payload / write_canonical_backing_state path.
        session: dict = {}
        _apply_filters_to_session_keys(session, {"backing_time_signature": "4/4", "backing_time_signature_override": False})
        self.assertNotIn("backing_time_signature", session)
        self.assertFalse(session["backing_time_signature_override"])
        applied, override, _ = apply_backing_meter_for_song(
            _st(session), song_id="cat::Perfect", default_time_signature="6/8"
        )
        self.assertEqual((applied, override), ("6/8", False))

    def test_session_hydration_keeps_explicit_override(self) -> None:
        session: dict = {}
        _apply_filters_to_session_keys(session, {"backing_time_signature": "4/4", "backing_time_signature_override": True})
        self.assertEqual(session["backing_time_signature"], "4/4")
        self.assertTrue(session["backing_time_signature_override"])

    def test_widget_rebind_from_canonical_uses_song_meter(self) -> None:
        for meter, title in CASES:
            with self.subTest(song=title):
                session = {BACKING_STATE_KEY: _blob("4/4", False), BACKING_RESTORED_KEY: True, "backing_track_bpm": 90}
                bind_backing_rendered_widgets_from_canonical(
                    session, sync_id=f"cat::{title}", default_bpm=90, default_groove="Pop groove", default_meter=meter
                )
                self.assertEqual(session["backing_time_signature"], meter)
                self.assertFalse(session["backing_time_signature_override"])
                self.assertTrue(session.get(BACKING_WIDGETS_SEEDED_KEY))
                # and the following apply must NOT promote it to a fake override
                a, o, _ = apply_backing_meter_for_song(
                    _st(session), song_id=f"cat::{title}", default_time_signature=meter
                )
                self.assertEqual((a, o), (meter, False))

    def test_widget_rebind_keeps_explicit_override(self) -> None:
        session = {BACKING_STATE_KEY: _blob("4/4", True), BACKING_RESTORED_KEY: True}
        bind_backing_rendered_widgets_from_canonical(
            session, sync_id="cat::PM", default_bpm=88, default_groove="Pop groove", default_meter="3/4"
        )
        self.assertEqual(session["backing_time_signature"], "4/4")
        self.assertTrue(session["backing_time_signature_override"])

    def test_source_default_meter_is_song_meter_without_creative_context(self) -> None:
        from backing_context import backing_page_transport_defaults, backing_source_default_meter

        # The transport helper itself falls back to "4/4" with no Creative context ...
        self.assertEqual(backing_page_transport_defaults({})[2], "4/4")
        # ... so the page must take the active song's meter instead.
        for meter, _t in CASES:
            self.assertEqual(
                backing_source_default_meter(creative_ctx=None, transport_meter="4/4", song_meter=meter), meter
            )
        creative = object()
        self.assertEqual(
            backing_source_default_meter(creative_ctx=creative, transport_meter="6/8", song_meter="4/4"), "6/8"
        )

    def test_page_uses_helper_for_source_default(self) -> None:
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("_backing_source_default_meter = backing_source_default_meter(", src)
        self.assertNotIn("_backing_source_default_meter = str(_td_meter)", src)

    def test_catalog_meters_for_real_songs(self) -> None:
        from song_catalog.catalog import load_song_catalog
        from songs.meter import default_time_signature_for_record

        want = {"Piano Man": "3/4", "Perfect": "6/8", "Hava Nagila": "6/8", "Siman Tov U'Mazal Tov": "6/8"}
        recs = load_song_catalog()[3]
        got = {r["title"]: default_time_signature_for_record(r, r.get("sections")) for r in recs if r["title"] in want}
        self.assertEqual(got, want)
        non44 = {r["title"] for r in recs if default_time_signature_for_record(r, r.get("sections")) != "4/4"}
        # the four known compound/triple songs must be non-4/4; other songs may legitimately join
        # the list when a catalog correction sets a real meter (e.g. We Are the Champions, 6/8).
        self.assertTrue(set(want) <= non44, sorted(set(want) - non44))

    def test_composition_studio_chord_duration_counts_compound_meters_in_dotted_quarters(self) -> None:
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "composition_studio_page.py").read_text(encoding="utf-8")
        i = src.index("beats_per_bar = int(meter_str.split")
        block = src[i : i + 600]
        self.assertIn("is_compound_meter(meter_str)", block)
        self.assertIn("beats_per_bar // 3", block)
        # arithmetic the page now performs: 6/8 at 60 BPM, 4 bars = 8 s (not 24 s)
        from songs.meter import is_compound_meter

        num = 6
        beats = num // 3 if is_compound_meter("6/8") else num
        self.assertEqual(4 * beats * 60.0 / 60, 8.0)

    def test_wav_cache_signature_includes_meter(self) -> None:
        import re
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        i = src.index("def _backing_signature_for_bpm")
        self.assertIn("backing_time_signature,", src[i : i + 2500])


class MeterReachesRendererTimelineAndClick(unittest.TestCase):
    CHORDS = ["C", "Am", "F", "G"]

    @staticmethod
    def _wav_seconds(data: bytes) -> float:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate())

    def _events(self, bars: int) -> list[dict]:
        return [
            {"chord": self.CHORDS[i % 4], "section": "Verse", "bar_in_section": i, "section_bars": bars}
            for i in range(bars)
        ]

    def test_generated_audio_duration_matches_meter(self) -> None:
        import backing_audio as ba

        bars, bpm = 4, 120
        for meter, _title in CASES:
            with self.subTest(meter=meter):
                wav = ba.generate_backing_track(
                    self._events(bars), bpm=bpm, loops=1, style="Pop groove", level="Intermediate",
                    song_title="Meter Probe", song_artist="Test", time_signature=meter,
                )
                dur = self._wav_seconds(wav)
                expected = bars * meter_timing(bpm, meter).bar_sec
                # note tails / release may extend the file by a little; never shorter.
                self.assertGreaterEqual(dur, expected - 0.05, (meter, dur, expected))
                self.assertLess(dur, expected + 2.5, (meter, dur, expected))

    def test_audio_durations_differ_by_meter_so_a_stale_4_4_is_detectable(self) -> None:
        import backing_audio as ba

        durs = {}
        for meter in ("3/4", "4/4", "6/8"):
            wav = ba.generate_backing_track(
                self._events(4), bpm=120, loops=1, style="Pop groove", level="Intermediate",
                song_title="Meter Probe", song_artist="Test", time_signature=meter,
            )
            durs[meter] = self._wav_seconds(wav)
        self.assertLess(durs["3/4"], durs["4/4"] - 1.5)   # 3 beats vs 4 per bar
        self.assertLess(durs["6/8"], durs["4/4"] - 1.5)   # compound: 2 dotted-quarter beats per bar

    def test_follow_timeline_and_metronome_use_restored_song_meter(self) -> None:
        import streamlit_music_practice_app as app
        from practice_metronome import build_metronome_widget_html

        bars, bpm = 4, 100
        for meter, title in CASES:
            with self.subTest(meter=meter):
                session = {BACKING_STATE_KEY: _blob("4/4", False), BACKING_RESTORED_KEY: True}
                applied, _o, _ = _first_load(session, f"cat::{title}", meter)
                timing = meter_timing(bpm, applied)
                events = self._events(bars)
                tl = app.build_chord_event_timeline(events, bpm, 1, time_signature=session["backing_time_signature"])
                self.assertEqual(len(tl), bars)
                self.assertAlmostEqual(tl[1]["start_time"] - tl[0]["start_time"], timing.bar_sec, places=3)
                self.assertAlmostEqual(tl[-1]["end_time"], bars * timing.bar_sec, places=3)
                # the audio the same session would render ends where the timeline ends
                import backing_audio as ba

                wav = ba.generate_backing_track(
                    events, bpm=bpm, loops=1, style="Pop groove", level="Intermediate",
                    song_title="Meter Probe", song_artist="Test", time_signature=session["backing_time_signature"],
                )
                self.assertGreaterEqual(self._wav_seconds(wav), tl[-1]["end_time"] - 0.05)
                # metronome click pattern
                html = build_metronome_widget_html(default_bpm=bpm, default_signature=applied)
                m = re.search(r"const cfg = (\{[^\n]*\});?\r?\n", html)
                self.assertIsNotNone(m)
                cfg = json.loads(m.group(1))
                self.assertEqual(cfg["beatsPerMeasure"], timing.pulses_per_bar)
                self.assertEqual(cfg["signature"], meter)
                self.assertAlmostEqual(cfg["pulseIntervalMs"] / 1000.0, timing.pulse_sec, delta=0.002)


if __name__ == "__main__":
    unittest.main()
