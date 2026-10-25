"""A stale queued sidebar display_key change must never roll the Practice Key back.

Reproduced in the browser: Practice Key Am -> Gm -> Dm -> Bm (the Original Key). Each pick queued a
pending change; picking Bm (== the persisted value) returned early without retiring the Dm entry, and a
later flush wrote display_key = Dm again, so Mission Backing re-opened in Dm.
"""

from __future__ import annotations

import time
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from display_key_startup_save_queue import (
    QUEUED_DISPLAY_KEY_CHANGE_KEY,
    flush_queued_display_key_change_once,
    has_queued_display_key_change,
    queue_explicit_display_key_change,
    queued_change_is_superseded,
    retire_queued_change_superseded_by_save,
)
from improvisation_intelligence_ui import _run_mission_example_generate
from improvisation_missions import MISSION_EXAMPLE_KEY, transpose_stored_mission_example

ORIGINAL = "Bm"
PICK = "Pop\x1fShape of You"


def _commit(ss: dict[str, Any], key: str, at: float) -> None:
    """What the Backing/sidebar Practice Key commit stamps before the save outcome is known."""
    ss["display_key"] = ss["concert_key"] = key
    ss["_pk_user_commit_token"] = key
    ss["_pk_user_commit_at"] = at


def _pick(ss: dict[str, Any], key: str, at: float, *, persisted: str = ORIGINAL) -> None:
    """A sidebar pick whose save did not confirm: the pick is queued against the persisted value."""
    _commit(ss, key, at)
    queue_explicit_display_key_change(ss, transaction_id=f"tx-{key}-{at}", old_value=persisted, new_value=key)


def _flush(ss: dict[str, Any], *, save_ok: bool = False) -> bool:
    st = MagicMock()
    st.session_state = ss
    with patch("display_key_sidebar_save_pipeline.run_explicit_display_key_cloud_save", return_value=save_ok):
        return flush_queued_display_key_change_once(st)


def _session() -> dict[str, Any]:
    return {"display_key": ORIGINAL, "concert_key": ORIGINAL, "display_key_change_source": "sidebar_on_change",
            "active_catalog_pick_key": PICK, "original_key": ORIGINAL}


class TestQueueOrdering(unittest.TestCase):
    def test_returning_to_the_persisted_original_key_retires_the_stale_entry(self) -> None:
        ss = _session()
        for i, k in enumerate(("Am", "Gm", "Dm"), start=1):
            _pick(ss, k, 100.0 + i)
        self.assertEqual(ss[QUEUED_DISPLAY_KEY_CHANGE_KEY]["new_value"], "Dm")
        _pick(ss, ORIGINAL, 110.0)
        self.assertFalse(has_queued_display_key_change(ss))

    def test_a_late_flush_cannot_restore_the_obsolete_key(self) -> None:
        ss = _session()
        for i, k in enumerate(("Am", "Gm", "Dm"), start=1):
            _pick(ss, k, 100.0 + i)
        _pick(ss, ORIGINAL, 110.0)
        for _ in range(3):                          # the flush runs on every rerun
            _flush(ss)
            self.assertEqual(ss["display_key"], ORIGINAL)

    def test_flush_discards_an_entry_made_obsolete_by_a_newer_commit_that_never_queued(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        _commit(ss, "Fm", 105.0)                    # a newer explicit commit whose save path never queued
        self.assertTrue(queued_change_is_superseded(ss))
        self.assertFalse(_flush(ss))
        self.assertEqual(ss["display_key"], "Fm")
        self.assertFalse(has_queued_display_key_change(ss))

    def test_latest_pick_replaces_every_earlier_pending_pick(self) -> None:
        ss = _session()
        for i, k in enumerate(("Am", "Gm", "Dm", "Em"), start=1):
            _pick(ss, k, 100.0 + i)
        self.assertEqual(ss[QUEUED_DISPLAY_KEY_CHANGE_KEY]["new_value"], "Em")
        _flush(ss)
        self.assertEqual(ss["display_key"], "Em")

    def test_repeated_picks_with_delayed_flushes_end_on_the_last_pick(self) -> None:
        ss = _session()
        for i, k in enumerate(("Am", "Gm", "Dm", ORIGINAL, "Am", ORIGINAL), start=1):
            _pick(ss, k, 100.0 + i)
            if i % 2:
                _flush(ss)                          # delayed flush landing between picks
                self.assertEqual(ss["display_key"], k)
        _flush(ss)
        self.assertEqual(ss["display_key"], ORIGINAL)
        self.assertFalse(has_queued_display_key_change(ss))

    def test_a_confirmed_save_of_a_newer_pick_retires_the_older_queued_change(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        self.assertTrue(retire_queued_change_superseded_by_save(ss, transaction_id="tx-newer"))
        self.assertFalse(has_queued_display_key_change(ss))

    def test_the_flush_of_its_own_transaction_is_not_retired(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        tx = ss[QUEUED_DISPLAY_KEY_CHANGE_KEY]["transaction_id"]
        self.assertFalse(retire_queued_change_superseded_by_save(ss, transaction_id=tx))
        self.assertTrue(has_queued_display_key_change(ss))


class TestLegitimatePendingChangeSurvives(unittest.TestCase):
    def test_cloud_unavailable_keeps_the_pending_pick_armed(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        self.assertFalse(queued_change_is_superseded(ss))
        self.assertFalse(_flush(ss, save_ok=False))
        self.assertEqual(ss["display_key"], "Dm")
        self.assertTrue(has_queued_display_key_change(ss))   # still retried on the next rerun

    def test_cloud_available_flush_confirms_and_clears(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        self.assertTrue(_flush(ss, save_ok=True))
        self.assertFalse(has_queued_display_key_change(ss))

    def test_startup_hydration_with_a_stale_display_value_does_not_drop_the_pending_pick(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        ss["display_key"] = "Cm"                    # startup hydrate wrote a stale display value
        ss["startup_suppression_armed"] = True
        self.assertFalse(queued_change_is_superseded(ss))   # ordering decides, not the live display value
        _flush(ss)
        self.assertEqual(ss["display_key"], "Dm")

    def test_an_unstamped_entry_is_never_dropped_on_a_guess(self) -> None:
        ss = _session()
        queue_explicit_display_key_change(ss, transaction_id="tx-old", old_value=ORIGINAL, new_value="Dm")
        ss[QUEUED_DISPLAY_KEY_CHANGE_KEY].pop("commit_at", None)
        ss["_pk_user_commit_token"], ss["_pk_user_commit_at"] = "Fm", time.time()
        self.assertFalse(queued_change_is_superseded(ss))

    def test_a_newer_commit_of_the_same_key_does_not_retire_it(self) -> None:
        ss = _session()
        _pick(ss, "Dm", 101.0)
        ss["_pk_user_commit_at"] = 200.0            # same token re-committed later
        self.assertFalse(queued_change_is_superseded(ss))


class TestSourceIsolation(unittest.TestCase):
    def test_a_pending_key_from_one_source_cannot_overwrite_another_sources_practice_key(self) -> None:
        for other_pick in ("custom::F Minor Prog", "composition::abc"):
            ss = _session()
            ss["practice_key_by_source"] = {PICK: "Bm", other_pick: "Fm"}
            _pick(ss, "Dm", 101.0)
            ss["active_catalog_pick_key"] = other_pick       # the user moved to another source
            ss["display_key"] = ss["concert_key"] = "Fm"
            self.assertFalse(_flush(ss))
            self.assertEqual(ss["display_key"], "Fm", other_pick)
            self.assertEqual(ss["practice_key_by_source"][other_pick], "Fm")
            self.assertFalse(has_queued_display_key_change(ss))


class TestMissionBackingReentry(unittest.TestCase):
    def test_resolver_keeps_the_sealed_original_key_once_the_queue_cannot_roll_display_key_back(self) -> None:
        from mission_owner_contract import HANDOFF_PRACTICE_KEY, resolve_mission_underlying_practice_key

        ss = _session()
        ss["practice_key_by_source"] = {PICK: ORIGINAL}
        for i, k in enumerate(("Am", "Gm", "Dm"), start=1):
            _pick(ss, k, 100.0 + i)
        _pick(ss, ORIGINAL, 110.0)
        _flush(ss)
        ss[HANDOFF_PRACTICE_KEY] = ORIGINAL
        ss["improv_mission_backing_handoff"] = True
        self.assertEqual(ss["display_key"], ORIGINAL)
        self.assertEqual(resolve_mission_underlying_practice_key(ss), ORIGINAL)

    def test_original_key_echo_protection_is_unchanged(self) -> None:
        """A sticky equal to Original still yields to a genuinely different live display key."""
        from mission_owner_contract import _sticky_mission_practice

        ss = _session()
        ss["practice_key_by_source"] = {PICK: ORIGINAL}
        ss["concert_key"] = ss["display_key"] = "Dm"
        self.assertEqual(_sticky_mission_practice(ss), "Dm")

    def test_mission_example_returns_to_its_exact_pitches_after_the_key_cycle(self) -> None:
        s = {"song": "Shape of You", "artist": "Ed Sheeran", "display_key": ORIGINAL, "concert_key": ORIGINAL,
             "instrument": "Piano", "level": "Intermediate", "focus": "Improvisation",
             "improv_active_mission": "Improvise using only chord tones",
             "improv_mission_pick": "Improvise using only chord tones", "home_sections": {"Verse 1": [ORIGINAL]},
             "improv_mission_chord_options": [ORIGINAL], "ii_selected_chord_index": 0, "ii_selected_chord": ORIGINAL,
             "ii_selected_section": "Verse 1", "backing_track_bpm": 100, "creative_workspace_state": {}}
        _run_mission_example_generate(s, "normal")
        orig = list(s[MISSION_EXAMPLE_KEY]["motif"]["midi"])
        cur = ORIGINAL
        for k in ("Am", "Gm", "Dm", ORIGINAL):
            transpose_stored_mission_example(s, from_key=cur, to_key=k)
            s["concert_key"] = s["display_key"] = cur = k
        self.assertEqual(list(s[MISSION_EXAMPLE_KEY]["motif"]["midi"]), orig)
        self.assertEqual(s["display_key"], ORIGINAL)


if __name__ == "__main__":
    unittest.main()
