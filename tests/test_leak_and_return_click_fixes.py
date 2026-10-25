"""Two navigation/ownership defects found while investigating Practice Key re-entry.

1. A Catalog Practice Key pick made from Missions also wrote the saved Custom progression
   (``cpl_active_progression.practice_key`` and ``practice_key_by_source["custom::..."]``) although Custom was
   not the active source.
2. Return to Mission: the rerun request counter restarts at 1 for every click, so the stored "already requested
   for seq 1" suppressed the guarded rerun; the fallback rerun then used an identical loop-guard fingerprint, and
   the third consecutive return was blocked as a "loop". The server navigated, the browser never re-rendered.
"""

from __future__ import annotations

import unittest
from unittest import mock

from custom_progression_lab import CPL_ACTIVE_KEY
from creative_key_sync import apply_specialized_mission_practice_key
from mission_backing_alignment import build_mission_backing_alignment_payload
from mission_return_destination import (
    MISSION_CANONICAL_RETURN_DESTINATION_KEY,
    build_mission_return_destination,
)
from music_rerun_loop_guard import RERUN_LOOP_MAX_REPEATS, RERUN_LOOP_BLOCKED_KEY
from music_workflow_pending_mission_return import (
    PENDING_MISSION_RETURN_KEY,
    handle_return_to_mission_click,
)
from songs.music_source import SOURCE_CATALOG, SOURCE_CUSTOM, custom_pick_key_for

CATALOG_PICK = "Pop\x1fShape of You — Ed Sheeran"
CUSTOM = {"id": "abc123", "name": "F Minor Prog", "practice_key": "Fm", "key": "Fm"}
CUSTOM_PICK = custom_pick_key_for(CUSTOM)


def _mission_session(*, source: str) -> dict:
    s = {
        "studio_page": "creative", "improv_intelligence_tab": "Missions",
        "active_music_source": source, "original_key": "Bm",
        "display_key": "Bm", "concert_key": "Bm", "improv_mission_concert_key": "Bm",
        "selected_song": {"key": "Bm"},
        CPL_ACTIVE_KEY: dict(CUSTOM),
        "practice_key_by_source": {CATALOG_PICK: "Bm", CUSTOM_PICK: "Fm"},
    }
    if source == SOURCE_CATALOG:
        s["active_catalog_pick_key"] = CATALOG_PICK
    else:
        s["active_catalog_pick_key"] = CUSTOM_PICK
    return s


class TestCatalogPickDoesNotWriteCustom(unittest.TestCase):
    def test_catalog_mission_pick_leaves_the_saved_custom_progression_alone(self) -> None:
        s = _mission_session(source=SOURCE_CATALOG)
        apply_specialized_mission_practice_key(s, "Dm")
        self.assertEqual(s[CPL_ACTIVE_KEY]["practice_key"], "Fm")
        self.assertEqual(s["practice_key_by_source"][CUSTOM_PICK], "Fm")
        self.assertEqual(s["practice_key_by_source"][CATALOG_PICK], "Bm")  # Catalog's own store is written elsewhere
        self.assertEqual(s["improv_mission_concert_key"], "Dm")

    def test_composition_active_does_not_write_custom_either(self) -> None:
        s = _mission_session(source="composition")
        s["active_catalog_pick_key"] = "composition::doc1"
        apply_specialized_mission_practice_key(s, "Dm")
        self.assertEqual(s[CPL_ACTIVE_KEY]["practice_key"], "Fm")
        self.assertEqual(s["practice_key_by_source"][CUSTOM_PICK], "Fm")

    def test_custom_mission_pick_still_updates_its_own_progression(self) -> None:
        s = _mission_session(source=SOURCE_CUSTOM)
        apply_specialized_mission_practice_key(s, "Gm")
        self.assertEqual(s[CPL_ACTIVE_KEY]["practice_key"], "Gm")
        self.assertEqual(s["practice_key_by_source"][CUSTOM_PICK], "Gm")


def _backing_session() -> dict:
    align = build_mission_backing_alignment_payload(
        {}, mission="M", cur_chord="D", section_label="Chorus", chord_idx=0, song_title="S",
    )
    return {
        "studio_page": "backing",
        MISSION_CANONICAL_RETURN_DESTINATION_KEY: build_mission_return_destination(
            align, handoff_mode="mission_backing", with_practice_lick=False,
        ),
    }


class TestReturnToMissionNeverSuppressedByTheLoopGuard(unittest.TestCase):
    def _click_cycle(self, session: dict, st) -> None:
        """One user Return click followed by the pre-widget consume the next run performs."""
        with mock.patch("studio_page_persistence.save_page_snapshot"), mock.patch(
            "music_workflow_pending_mission_return.consume_pending_mission_return_handoff",
            side_effect=lambda ss, st=None: (ss.pop(PENDING_MISSION_RETURN_KEY, None), "applied")[1],
        ):
            handle_return_to_mission_click(st, session)
        session.pop(PENDING_MISSION_RETURN_KEY, None)   # consumed by the next run
        session["studio_page"] = "backing"               # user re-enters Backing

    def test_every_consecutive_click_issues_a_rerun(self) -> None:
        session = _backing_session()
        for n in range(1, 3 * RERUN_LOOP_MAX_REPEATS + 1):
            st = mock.Mock()
            self._click_cycle(session, st)
            self.assertGreaterEqual(st.rerun.call_count, 1, f"click #{n} issued no rerun")
            self.assertFalse(session.get(RERUN_LOOP_BLOCKED_KEY), f"click #{n} left the guard blocked")

    def test_a_genuine_loop_without_new_clicks_is_still_blocked(self) -> None:
        from music_rerun_loop_guard import safe_rerun

        session: dict = {"studio_page": "backing"}
        st = mock.Mock()
        results = [safe_rerun(st, session, reason="x", fingerprint="same") for _ in range(RERUN_LOOP_MAX_REPEATS + 2)]
        self.assertEqual(results[:RERUN_LOOP_MAX_REPEATS - 1], [True] * (RERUN_LOOP_MAX_REPEATS - 1))
        self.assertFalse(results[-1])
        self.assertTrue(session.get(RERUN_LOOP_BLOCKED_KEY))

    def test_a_new_request_does_not_inherit_the_previous_requests_rerun_stamp(self) -> None:
        from music_workflow_pending_mission_return import (
            PENDING_MISSION_RETURN_RERUN_SEQ_KEY,
            queue_pending_mission_return_from_backing,
            request_pending_mission_return_rerun,
        )

        session = _backing_session()
        queue_pending_mission_return_from_backing(session)
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            self.assertTrue(request_pending_mission_return_rerun(mock.Mock(), session))
        session.pop(PENDING_MISSION_RETURN_KEY, None)    # consumed
        queue_pending_mission_return_from_backing(session)
        with mock.patch("music_app_rerun.request_app_rerun", return_value=True):
            self.assertTrue(request_pending_mission_return_rerun(mock.Mock(), session))
        self.assertIsNotNone(session.get(PENDING_MISSION_RETURN_RERUN_SEQ_KEY))


if __name__ == "__main__":
    unittest.main()
