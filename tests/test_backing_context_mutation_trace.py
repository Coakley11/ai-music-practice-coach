"""Direct backing_context writes vs set_backing_context preservation tracing."""

from __future__ import annotations

import copy
import unittest
from typing import Any

from backing_context import BACKING_CONTEXT_KEY, BackingContext, set_backing_context
from backing_creative_return_route import CREATIVE_RETURN_ROUTE_BLOB_KEY
from creative_return_trace import BACKING_CONTEXT_MUTATION_JOURNAL_KEY
from studio_page_persistence import apply_page_snapshot, capture_page_snapshot


class TestBackingContextMutationTrace(unittest.TestCase):
    def test_apply_page_snapshot_direct_write_traced(self) -> None:
        session: dict[str, Any] = {
            BACKING_CONTEXT_KEY: {
                "source": "entry_jam",
                "source_signature": "abc123",
                CREATIVE_RETURN_ROUTE_BLOB_KEY: {"entry_mode": "Jam Session Generator"},
            }
        }
        stale_snap = capture_page_snapshot(
            {
                BACKING_CONTEXT_KEY: {
                    "source": "entry_jam",
                    "source_signature": "abc123",
                }
            },
            "backing",
        )
        apply_page_snapshot(session, stale_snap)
        journal = session.get(BACKING_CONTEXT_MUTATION_JOURNAL_KEY)
        self.assertIsInstance(journal, list)
        assert isinstance(journal, list)
        direct = [r for r in journal if r.get("phase") == "DIRECT_BACKING_CONTEXT_WRITE"]
        self.assertTrue(direct)
        last = direct[-1]
        self.assertEqual(last.get("write_path"), "apply_page_snapshot")
        self.assertFalse(last.get("uses_set_backing_context"))
        self.assertTrue(last.get("route_dropped"))

    def test_set_backing_context_preservation_reason_traced(self) -> None:
        session: dict[str, Any] = {}
        ctx = BackingContext(
            source="entry_jam",
            source_label="Entry & Jam",
            active_song_id="",
            song_title="",
            key="C",
            display_key="C",
            concert_key="C",
            bpm=100,
            style="Jazz",
            groove="Swing",
            entry_mode="Jam Session Generator",
            source_signature="sig6378465d",
        )
        route = {"entry_mode": "Jam Session Generator", "intelligence_tab": "Entry & Jam"}
        set_backing_context(session, ctx, creative_return_route=route, trace_caller="test_launch")
        ctx2 = copy.deepcopy(ctx)
        set_backing_context(session, ctx2, trace_caller="test_reconcile_refresh")
        journal = session.get(BACKING_CONTEXT_MUTATION_JOURNAL_KEY)
        assert isinstance(journal, list)
        reasons = [r.get("preservation_reason") for r in journal if r.get("phase") == "SET_BACKING_CONTEXT"]
        self.assertEqual(reasons[0], "explicit_new_route")
        self.assertEqual(reasons[1], "preserved_same_signature")


if __name__ == "__main__":
    unittest.main()
