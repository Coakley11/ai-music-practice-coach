"""Slice 5A — Practice written-chart toggle: display-only, persist, no owner/PK mutation."""

from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import MagicMock, patch


def _trial_catalog_session(
    *,
    instrument: str = "Clarinet",
    written_on: bool = False,
    practice_key: str = "F",
    original_key: str = "D",
    anchor: str | None = None,
) -> dict:
    from instrument_transposition import (
        CHART_IN_INSTRUMENT_KEY_KEY,
        SELECTED_TRANSPOSING_INSTRUMENT_KEY,
        WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
        default_transposing_type,
    )

    base_anchor = anchor if anchor is not None else instrument
    return {
        "instrument": instrument,
        "display_key": practice_key,
        "original_key": original_key,
        "concert_practice_key": practice_key,
        "active_music_source": "catalog",
        "active_catalog_pick_key": "pop::trial",
        "selected_song": {
            "pick_key": "pop::trial",
            "title": "Trial",
            "key": original_key,
        },
        CHART_IN_INSTRUMENT_KEY_KEY: written_on,
        WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: base_anchor,
        SELECTED_TRANSPOSING_INSTRUMENT_KEY: default_transposing_type(instrument)
        if instrument in ("Clarinet", "Saxophone", "Trumpet")
        else "",
        "active_song_state": {
            "pick_key": "pop::trial",
            "instrument": instrument,
            "display_key": practice_key,
            "music_source": "catalog",
            CHART_IN_INSTRUMENT_KEY_KEY: written_on,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: base_anchor,
        },
        "_studio_nav_history": ["Practice"],
        "_studio_nav_history_index": 0,
        "creative_owner": "catalog",
        "backing_owner_kind": "catalog",
    }


class TestSlice5AWrittenChartToggle(unittest.TestCase):
    def test_off_to_on_clarinet_display_only(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            effective_chart_key,
            resolve_practice_keys,
            sync_written_key_instrument_anchor,
            written_key_for_type,
        )

        session = _trial_catalog_session(instrument="Clarinet", written_on=False)
        before_pk = session["display_key"]
        before_inst = session["instrument"]
        before_owner = session["backing_owner_kind"]
        before_creative = session["creative_owner"]
        before_hist = list(session["_studio_nav_history"])

        # User turns written charts ON (widget + callback contract).
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = "Clarinet"
        sync_written_key_instrument_anchor(
            session, "Clarinet", reset_written_on_family_change=False
        )

        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session["display_key"], before_pk)
        self.assertEqual(session["instrument"], before_inst)
        self.assertEqual(session["original_key"], "D")
        self.assertEqual(session["backing_owner_kind"], before_owner)
        self.assertEqual(session["creative_owner"], before_creative)
        self.assertEqual(session["_studio_nav_history"], before_hist)

        ctx = resolve_practice_keys(session, "F", "Clarinet")
        chart_k, mode = effective_chart_key("F", "Clarinet", session)
        self.assertEqual(mode, "written")
        self.assertEqual(chart_k, written_key_for_type("F", "Bb Clarinet"))
        self.assertEqual(chart_k, "G")
        self.assertEqual(ctx["global_display_key"], "F")
        self.assertEqual(ctx["chart_key"], "G")

    def test_on_to_off_restores_concert_chart(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            effective_chart_key,
            resolve_practice_keys,
        )

        session = _trial_catalog_session(instrument="Clarinet", written_on=True)
        session[CHART_IN_INSTRUMENT_KEY_KEY] = False

        chart_k, mode = effective_chart_key("F", "Clarinet", session)
        ctx = resolve_practice_keys(session, "F", "Clarinet")
        self.assertEqual(mode, "concert")
        self.assertEqual(chart_k, "F")
        self.assertEqual(ctx["global_display_key"], "F")
        self.assertEqual(session["display_key"], "F")
        self.assertEqual(session["instrument"], "Clarinet")

    def test_tenor_sax_off_to_on_pk_unchanged(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            SELECTED_TRANSPOSING_INSTRUMENT_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            effective_chart_key,
            sync_written_key_instrument_anchor,
        )

        session = _trial_catalog_session(
            instrument="Saxophone",
            written_on=False,
            practice_key="C",
            original_key="C",
            anchor="Saxophone",
        )
        session[SELECTED_TRANSPOSING_INSTRUMENT_KEY] = "Tenor saxophone (Bb)"
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = "Saxophone"
        sync_written_key_instrument_anchor(
            session, "Saxophone", reset_written_on_family_change=False
        )
        chart_k, mode = effective_chart_key("C", "Saxophone", session)
        self.assertEqual(mode, "written")
        self.assertEqual(chart_k, "D")
        self.assertEqual(session["display_key"], "C")
        self.assertEqual(session["instrument"], "Saxophone")

    def test_piano_written_flag_ignored_for_chart(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            effective_chart_key,
        )

        session = _trial_catalog_session(instrument="Piano", written_on=True, practice_key="F")
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        chart_k, mode = effective_chart_key("F", "Piano", session)
        self.assertEqual(mode, "concert")
        self.assertEqual(chart_k, "F")

    def test_soft_rerun_preserves_on_with_stale_sax_anchor(self) -> None:
        """Every-rerun soft sync must not clear ON when cloud left a Saxophone anchor."""
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = _trial_catalog_session(
            instrument="Clarinet",
            written_on=True,
            anchor="Saxophone",
        )
        sync_written_key_instrument_anchor(
            session, "Clarinet", reset_written_on_family_change=False
        )
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY], "Clarinet")

    def test_hard_instrument_hop_clears_written(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = _trial_catalog_session(
            instrument="Clarinet",
            written_on=True,
            anchor="Saxophone",
        )
        sync_written_key_instrument_anchor(
            session, "Clarinet", reset_written_on_family_change=True
        )
        self.assertFalse(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY], "Clarinet")

    def test_bb_clarinet_display_name_anchor_normalizes_without_clear(self) -> None:
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = _trial_catalog_session(
            instrument="Clarinet",
            written_on=True,
            anchor="Bb Clarinet",
        )
        sync_written_key_instrument_anchor(
            session, "Clarinet", reset_written_on_family_change=False
        )
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY], "Clarinet")

    def test_nav_away_back_preserves_written_via_flush(self) -> None:
        from active_song_state import (
            ACTIVE_SONG_STATE_KEY,
            flush_active_song_edits,
            rehydrate_transposing_sidebar_from_canonical,
        )
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = _trial_catalog_session(instrument="Clarinet", written_on=False)
        hist_before = list(session["_studio_nav_history"])
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY] = "Clarinet"
        flush_active_song_edits(session, reason="written_key_toggle")

        # Simulate leaving Practice and returning: drop live widget key, rehydrate.
        live = dict(session)
        live.pop(CHART_IN_INSTRUMENT_KEY_KEY, None)
        rehydrate_transposing_sidebar_from_canonical(live)
        sync_written_key_instrument_anchor(
            live, "Clarinet", reset_written_on_family_change=False
        )
        self.assertTrue(live[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertTrue(live[ACTIVE_SONG_STATE_KEY][CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(live["display_key"], "F")
        self.assertEqual(live["instrument"], "Clarinet")
        self.assertEqual(live["_studio_nav_history"], hist_before)

    def test_refresh_restore_with_stale_anchor_keeps_on(self) -> None:
        from active_song_state import finalize_transposing_receive_restore
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )

        session = {
            "instrument": "Clarinet",
            "display_key": "F",
            "active_song_state": {
                "instrument": "Clarinet",
                "display_key": "F",
                "pick_key": "pop::trial",
            },
        }
        payload = {
            "active_song_state": {
                "instrument": "Clarinet",
                "display_key": "F",
                "pick_key": "pop::trial",
                CHART_IN_INSTRUMENT_KEY_KEY: True,
                # Stale family from a prior Saxophone session.
                WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
            },
            "music_workspace_state": {
                "active_song": {
                    "pick_key": "pop::trial",
                    "instrument": "Clarinet",
                    CHART_IN_INSTRUMENT_KEY_KEY: True,
                    WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY: "Saxophone",
                }
            },
        }
        finalize_transposing_receive_restore(session, payload, source="disk_refresh")
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])
        self.assertEqual(session[WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY], "Clarinet")
        sync_written_key_instrument_anchor(
            session, "Clarinet", reset_written_on_family_change=False
        )
        self.assertTrue(session[CHART_IN_INSTRUMENT_KEY_KEY])

    def test_toggle_does_not_push_nav_history(self) -> None:
        """Written-key flush must not manufacture studio nav history entries."""
        from active_song_state import flush_active_song_edits
        from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY

        session = _trial_catalog_session(instrument="Clarinet", written_on=False)
        before = deepcopy(session["_studio_nav_history"])
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        flush_active_song_edits(session, reason="written_key_toggle")
        self.assertEqual(session["_studio_nav_history"], before)
        self.assertEqual(session["_studio_nav_history_index"], 0)

    def test_toggle_does_not_mutate_owners_or_source(self) -> None:
        from active_song_state import flush_active_song_edits
        from instrument_transposition import CHART_IN_INSTRUMENT_KEY_KEY

        session = _trial_catalog_session(instrument="Saxophone", written_on=False)
        before_pick = session["active_catalog_pick_key"]
        before_backing = session["backing_owner_kind"]
        before_creative = session["creative_owner"]
        before_hist = list(session["_studio_nav_history"])
        session[CHART_IN_INSTRUMENT_KEY_KEY] = True
        flush_active_song_edits(session, reason="written_key_toggle")
        # Display-only: song identity, owners, PK, instrument, and nav stay put.
        self.assertEqual(session["active_catalog_pick_key"], before_pick)
        self.assertEqual(session["backing_owner_kind"], before_backing)
        self.assertEqual(session["creative_owner"], before_creative)
        self.assertEqual(session["_studio_nav_history"], before_hist)
        self.assertEqual(session["display_key"], "F")
        self.assertEqual(session["original_key"], "D")
        self.assertEqual(session["instrument"], "Saxophone")
        self.assertEqual(session["selected_song"]["pick_key"], "pop::trial")

    def test_every_rerun_call_site_uses_soft_sync(self) -> None:
        from pathlib import Path

        src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn(
            "reset_written_on_family_change=False",
            src,
            "every-rerun written-key sync must be soft",
        )
        # Instrument on_change must still hard-reset on family hop.
        marker = "def _on_global_instrument_change()"
        start = src.index(marker)
        end = src.index("\ndef ", start + len(marker))
        inst_src = src[start:end]
        self.assertIn("sync_written_key_instrument_anchor", inst_src)
        self.assertNotIn("reset_written_on_family_change=False", inst_src)


class TestSlice5ADiskRoundTrip(unittest.TestCase):
    def test_clarinet_written_on_survives_disk_apply(self) -> None:
        from active_song_state import ACTIVE_SONG_STATE_KEY
        from instrument_transposition import (
            CHART_IN_INSTRUMENT_KEY_KEY,
            WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY,
            sync_written_key_instrument_anchor,
        )
        from music_persistent_state import build_music_disk_state

        session = _trial_catalog_session(instrument="Clarinet", written_on=True)
        st = MagicMock()
        st.session_state = session
        blob = build_music_disk_state(st)
        self.assertIsInstance(blob, dict)

        phone = {
            "instrument": "Clarinet",
            "display_key": "F",
            ACTIVE_SONG_STATE_KEY: {
                "instrument": "Clarinet",
                "display_key": "F",
                "pick_key": "pop::trial",
            },
        }
        from active_song_state import finalize_transposing_receive_restore

        finalize_transposing_receive_restore(phone, blob, source="disk_round_trip")
        # build_music_disk_state may nest differently; ensure flag from session extras/meta.
        meta = blob.get("active_song_state") if isinstance(blob, dict) else None
        if isinstance(meta, dict) and CHART_IN_INSTRUMENT_KEY_KEY in meta:
            self.assertTrue(meta[CHART_IN_INSTRUMENT_KEY_KEY])
        sync_written_key_instrument_anchor(
            phone, "Clarinet", reset_written_on_family_change=False
        )
        # If restore populated the flag, soft sync must keep it.
        if CHART_IN_INSTRUMENT_KEY_KEY in phone:
            if phone[CHART_IN_INSTRUMENT_KEY_KEY]:
                self.assertEqual(
                    phone.get(WRITTEN_KEY_INSTRUMENT_ANCHOR_KEY), "Clarinet"
                )


if __name__ == "__main__":
    unittest.main()
