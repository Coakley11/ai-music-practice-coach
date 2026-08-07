"""Studio page dispatch vs session authority after Return-to-Creative."""

from __future__ import annotations

import unittest

from studio_page_route_trace import (
    SESSION_LAST_KEY,
    SESSION_LOG_KEY,
    build_route_trace_journal_payload,
    emit_route_trace,
    snapshot_route_authorities,
)


class StudioPageRouteTraceTests(unittest.TestCase):
    def test_dispatch_mismatch_surfaces_in_trace(self) -> None:
        session: dict = {
            "_script_run_seq": 12,
            "studio_page": "creative",
            "studio_nav_state": {"studio_page": "backing", "last_write_reason": "workspace_restore"},
            "_creative_restore_from_backing": True,
        }
        snap = snapshot_route_authorities(session, dispatch_local="backing")
        self.assertEqual(snap["studio_page"], "creative")
        self.assertEqual(snap["dispatch_local_studio_page"], "backing")
        self.assertEqual(snap["canonical_studio_nav_state"], "backing")

        emit_route_trace(
            session,
            "PAGE_DISPATCH_BRANCH",
            dispatch_local="backing",
            render_target="backing",
            extra={"session_vs_dispatch_disagree": True},
        )
        last = session.get(SESSION_LAST_KEY)
        self.assertIsInstance(last, dict)
        assert isinstance(last, dict)
        self.assertEqual(last.get("render_target"), "backing")
        self.assertTrue(last.get("extra", {}).get("session_vs_dispatch_disagree"))

    def test_journal_payload_includes_event_log(self) -> None:
        session: dict = {"_script_run_seq": 3}
        emit_route_trace(session, "RUN_START_AFTER_ENSURE_STUDIO_PAGE", dispatch_local="backing")
        payload = build_route_trace_journal_payload(session)
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(len(payload["events"]), 1)
        log = session.get(SESSION_LOG_KEY)
        self.assertIsInstance(log, list)


if __name__ == "__main__":
    unittest.main()
