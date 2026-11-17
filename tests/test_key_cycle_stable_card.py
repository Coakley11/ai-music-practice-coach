"""The normal Backing / song card keeps the saved Practice Key while Key Cycling runs.

Root cause on dev: ``resolve_current_backing_musical_state`` built the Written /
Charts-in badge from the cycling sounding key, so every cycle step rewrote the
card's Written Key (the Mission notation underneath did not move). Audio and
the lead sheet still follow the sounding key; the card reads ``card_*``.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
from backing_context import BackingContext, set_backing_context
from backing_musical_state import card_view, resolve_current_backing_musical_state
from instrument_transposition import written_key_for_instrument
from songs.music_source import ACTIVE_MUSIC_SOURCE_KEY, SOURCE_CATALOG
from songs.practice_key_state import set_practice_concert_key

_PICK = "Pop\x1fShape of You"


def _session(*, instrument: str = "Saxophone", written: bool = True) -> dict:
    ss: dict = {
        "active_catalog_pick_key": _PICK,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        "display_key": "Bm",
        "concert_key": "Bm",
        "instrument": instrument,
        "show_chart_in_instrument_key": written,
    }
    set_practice_concert_key(ss, "Bm", pick_key=_PICK, allow_restore_original=True)
    set_backing_context(
        ss,
        BackingContext(
            source="regular_song",
            source_label="Catalog song",
            active_song_id=_PICK,
            song_title="Shape of You",
            key="Bm",
            concert_key="Bm",
            display_key="Bm",
            bpm=96,
            style="Pop",
            groove="Auto",
            bound_pick_key=_PICK,
        ),
    )
    return ss


def _state(ss: dict):
    return resolve_current_backing_musical_state(
        ss, rec={"title": "Shape of You", "key": "Bm", "pick_key": _PICK}
    )


class TestStableCardWhileCycling(unittest.TestCase):
    def setUp(self) -> None:
        self._pro = mock.patch("monetization_entitlements.can_use", return_value=True)
        self._pro.start()
        self._persist = mock.patch.object(kc, "persist_key_cycle_position", return_value=True)
        self._persist.start()

    def tearDown(self) -> None:
        self._persist.stop()
        self._pro.stop()

    def _start(self, ss: dict, *, interval: int = 5) -> None:
        kc.start_key_cycle(ss, start_key="Bm", interval=interval, direction="up")

    def test_written_badge_on_card_ignores_cycle_steps(self) -> None:
        ss = _session()
        before = _state(ss)
        saved_written = written_key_for_instrument("Bm", "Saxophone", ss)
        self.assertEqual(before.card_written_key, saved_written)
        self.assertTrue(before.card_show_chart_badge)

        self._start(ss)
        for _ in range(3):
            kc.advance_key_cycle_now(ss)
            sounding = kc.temporary_playback_key(ss)
            self.assertNotEqual(sounding, "Bm")
            st = _state(ss)
            # The saved Practice Key never changes.
            self.assertEqual(st.practice_concert_key, "Bm")
            # Sounding fields follow the cycle (audio / lead sheet)...
            self.assertEqual(st.progression_key_audio, sounding)
            self.assertEqual(st.written_key, written_key_for_instrument(sounding, "Saxophone", ss))
            # ...the card does not.
            self.assertEqual(st.card_written_key, saved_written)
            self.assertEqual(st.card_chart_badge_value, before.chart_badge_value)
            self.assertEqual(st.card_show_chart_badge, before.show_chart_badge)
            view = card_view(st)
            self.assertEqual(view.chart_badge_value, before.chart_badge_value)
            self.assertEqual(view.written_key, saved_written)
            self.assertEqual(view.progression_key_audio, "Bm")

    def test_deliberate_instrument_change_still_updates_card(self) -> None:
        ss = _session()
        self._start(ss)
        kc.advance_key_cycle_now(ss)
        alto = _state(ss).card_written_key
        from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY

        ss[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Tenor saxophone (Bb)"
        tenor = _state(ss).card_written_key
        self.assertEqual(tenor, written_key_for_instrument("Bm", "Saxophone", ss))
        self.assertNotEqual(alto, tenor)

    def test_guitar_shape_badge_stays_when_cycle_reaches_shape_tonic(self) -> None:
        ss = _session(instrument="Guitar", written=False)
        ss["guitar_capo_enabled"] = True
        ss["guitar_capo_shape_key"] = "Am"
        before = _state(ss)
        self.assertEqual(before.card_chart_mode, "shape")
        self.assertTrue(before.card_show_chart_badge)
        # Semitone cycle from Bm reaches Am (the shape tonic, capo 0) after 10 steps.
        self._start(ss, interval=1)
        for _ in range(10):
            kc.advance_key_cycle_now(ss)
        self.assertEqual(kc.temporary_playback_key(ss), "Am")
        st = _state(ss)
        # Sounding view: capo 0, nothing to badge.
        self.assertFalse(st.show_chart_badge)
        # Card: still the saved Bm with Am shapes (capo 2).
        self.assertTrue(st.card_show_chart_badge)
        self.assertEqual(st.card_chart_badge_value, before.chart_badge_value)

    def test_identical_outside_cycling(self) -> None:
        ss = _session()
        st = _state(ss)
        self.assertEqual(st.card_written_key, st.written_key)
        self.assertEqual(st.card_chart_badge_value, st.chart_badge_value)
        self.assertEqual(st.card_chart_mode, st.chart_mode)
        self.assertEqual(st.card_chart_sections, st.chart_sections)

    def test_card_view_leaves_hand_built_state_alone(self) -> None:
        st = _state(_session())
        from dataclasses import replace

        bare = replace(st, card_chart_display_key="")
        self.assertIs(card_view(bare), bare)
        self.assertIsNone(card_view(None))


if __name__ == "__main__":
    unittest.main()
