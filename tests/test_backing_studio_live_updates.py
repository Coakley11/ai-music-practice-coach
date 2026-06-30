"""Backing Studio — BPM init, written-key charts, and live context refresh."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backing_context import (
    BACKING_CONTEXT_KEY,
    build_entry_jam_context,
    refresh_backing_context_from_session,
    reconcile_backing_context_on_backing_page,
    sections_dict_for_chart_display,
    set_backing_context,
)
from instrument_transposition import (
    SELECTED_TRANSPOSING_INSTRUMENT_KEY,
    written_key_for_type,
)
from songs.bpm_state import BPM_WIDGET_KEY, LAST_BPM_SONG, PENDING_BACKING_TRACK_BPM
from songs.playback_defaults import (
    _CANONICAL_BACKING_ID_KEY,
    backing_bpm_slider_widget_key,
    canonicalize_backing_defaults_for_song,
    resolve_backing_bpm_for_slider,
)


def _entry_jam_session(*, bpm: int = 60, key: str = "C") -> dict:
    return {
        "active_catalog_pick_key": "say|artist",
        "song": "Say",
        "display_key": key,
        "concert_key": key,
        "improv_entry_mode": "Style Jam Mode",
        "improv_style": "Bossa Nova",
        "improv_style_key": key,
        "improv_style_bpm": bpm,
        "improv_style_meta": {"style": "Bossa Nova", "bpm": bpm, "groove": "Medium"},
        "improv_generated_sections": {"Head (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
    }


class TestBackingStudioBpmInit(unittest.TestCase):
    def test_style_jam_60_initializes_slider_not_catalog_108(self) -> None:
        session = _entry_jam_session(bpm=60)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[BPM_WIDGET_KEY] = 108
        session["bpm"] = 108
        session[LAST_BPM_SONG] = "pk::catalog_song"
        session[backing_bpm_slider_widget_key("pk::catalog_song")] = 108
        st = SimpleNamespace(session_state=session)

        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=108,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertTrue(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 60)

        slider_bpm = resolve_backing_bpm_for_slider(
            st,
            sync_id=sync_id,
            default_bpm=60,
            song_just_reset=bool(canon["did_reset"]),
        )
        self.assertEqual(slider_bpm, 60)
        self.assertEqual(session[backing_bpm_slider_widget_key(sync_id)], 60)

    def test_same_source_bpm_override_persists(self) -> None:
        session = _entry_jam_session(bpm=60)
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[_CANONICAL_BACKING_ID_KEY] = sync_id
        session[BPM_WIDGET_KEY] = 75
        session[LAST_BPM_SONG] = sync_id
        session[backing_bpm_slider_widget_key(sync_id)] = 75
        session["_backing_user_edited"] = True
        st = SimpleNamespace(session_state=session)

        with patch("backing_track_state.is_backing_user_dirty", return_value=True):
            canon = canonicalize_backing_defaults_for_song(
                st,
                sync_id=sync_id,
                active_song_bpm=60,
                active_song_groove="Pop groove",
                active_song_meter="4/4",
            )
        self.assertFalse(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 75)

    def test_new_source_resets_bpm(self) -> None:
        session = _entry_jam_session(bpm=80, key="G")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        sync_id = f"creative:entry_jam:{ctx.source_signature}"
        session[_CANONICAL_BACKING_ID_KEY] = "creative:entry_jam:old_sig"
        session[BPM_WIDGET_KEY] = 120
        st = SimpleNamespace(session_state=session)

        canon = canonicalize_backing_defaults_for_song(
            st,
            sync_id=sync_id,
            active_song_bpm=120,
            active_song_groove="Pop groove",
            active_song_meter="4/4",
        )
        self.assertTrue(canon["did_reset"])
        self.assertEqual(canon["applied_bpm"], 80)


class TestTenorWrittenChartTranspose(unittest.TestCase):
    def _tenor_session(self, concert: str) -> dict:
        return {
            "display_key": concert,
            "concert_key": concert,
            "instrument": "Saxophone",
            "show_chart_in_instrument_key": True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
            "improv_entry_mode": "Style Jam Mode",
            "improv_style_key": concert,
            "improv_generated_sections": {
                "Head": ["Bbm7", "Eb7", "Abmaj7", "Dbmaj7"],
            },
        }

    def test_tenor_concert_db_written_eb_chords(self) -> None:
        session = self._tenor_session("Db")
        written = written_key_for_type("Db", "Tenor saxophone (Bb)")
        self.assertEqual(written, "Eb")
        concert = {"Head": ["Bbm7", "Eb7", "Abmaj7", "Dbmaj7"]}
        chart = sections_dict_for_chart_display(session, concert, concert_key="Db")
        flat = " ".join(chart["Head"])
        self.assertIn("Cm7", flat)
        self.assertIn("Ebmaj7", flat)

    def test_tenor_concert_c_written_d_chords(self) -> None:
        session = {
            "display_key": "C",
            "concert_key": "C",
            "instrument": "Saxophone",
            "show_chart_in_instrument_key": True,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY: "Tenor saxophone (Bb)",
        }
        written = written_key_for_type("C", "Tenor saxophone (Bb)")
        self.assertEqual(written, "D")
        concert = {"Head": ["Dm7", "G7", "Cmaj7", "A7"]}
        chart = sections_dict_for_chart_display(session, concert, concert_key="C")
        flat = " ".join(chart["Head"])
        self.assertIn("Em7", flat)
        self.assertIn("Dmaj7", flat)


class TestBackingContextLiveRefresh(unittest.TestCase):
    def test_refresh_updates_concert_key_from_session(self) -> None:
        session = _entry_jam_session(bpm=60, key="F")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["display_key"] = "C"
        session["improv_style_key"] = "C"
        session["concert_key"] = "C"

        refreshed = refresh_backing_context_from_session(session)
        assert refreshed is not None
        self.assertEqual(refreshed.concert_key, "C")
        self.assertNotEqual(refreshed.concert_key, ctx.concert_key)

    def test_reconcile_refreshes_context_and_flushes_bpm(self) -> None:
        session = _entry_jam_session(bpm=60, key="C")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session[BACKING_CONTEXT_KEY]["concert_key"] = "F"
        session[BACKING_CONTEXT_KEY]["bpm"] = 110
        st_like = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            reconcile_backing_context_on_backing_page(session, st_like=st_like)
        self.assertEqual(session.get("backing_track_bpm"), 60)
        self.assertEqual(getattr(refresh_backing_context_from_session(session), "concert_key", None), "C")

    def test_invalidate_refreshes_not_clears_entry_jam(self) -> None:
        from backing_context import get_backing_context
        from creative_key_sync import invalidate_creative_backing_context

        session = _entry_jam_session(bpm=60, key="G")
        ctx = build_entry_jam_context(session)
        set_backing_context(session, ctx)
        session["improv_style_key"] = "A"
        session["display_key"] = "A"
        invalidate_creative_backing_context(session)
        live = get_backing_context(session)
        self.assertIsNotNone(live)
        self.assertEqual(live.source, "entry_jam")
        self.assertEqual(live.concert_key, "A")


if __name__ == "__main__":
    unittest.main()
