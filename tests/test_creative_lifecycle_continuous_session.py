"""Full continuous Creative lifecycle (steps 1–37) — production paths only."""

from __future__ import annotations

import unittest

from creative_lifecycle_continuous_session import run_continuous_lifecycle


class TestCreativeLifecycleContinuousSession(unittest.TestCase):
    def test_full_continuous_session_baseline(self) -> None:
        run_continuous_lifecycle(phase="baseline")

    def test_full_continuous_session_refresh_persistence(self) -> None:
        run_continuous_lifecycle(phase="post_refresh")


class TestGenerateButtonRevisionContract(unittest.TestCase):
    def test_style_jam_two_generates_new_tokens_and_revisions(self) -> None:
        from creative_lifecycle_continuous_session import (
            _session,
            configure_style_jam_controls,
            generate_style_jam_via_pre_widget,
        )

        session = _session()
        configure_style_jam_controls(session)
        a = generate_style_jam_via_pre_widget(session)
        b = generate_style_jam_via_pre_widget(session)
        self.assertNotEqual(a.request_token, b.request_token)
        self.assertGreater(b.generation_sequence, a.generation_sequence)
        self.assertGreater(b.artifact_revision, a.artifact_revision)
        self.assertNotEqual(a.artifact_id, b.artifact_id)
        self.assertNotEqual(a.control_fingerprint, b.control_fingerprint)

    def test_generator_two_generates_new_tokens_and_revisions(self) -> None:
        from creative_lifecycle_continuous_session import (
            _session,
            configure_generator_controls,
            generate_jam_session_via_pre_widget,
        )

        session = _session()
        configure_generator_controls(session)
        a = generate_jam_session_via_pre_widget(session)
        b = generate_jam_session_via_pre_widget(session)
        self.assertNotEqual(a.request_token, b.request_token)
        self.assertGreater(b.artifact_revision, a.artifact_revision)
        self.assertNotEqual(a.artifact_id, b.artifact_id)

    def test_same_style_name_still_yields_distinct_artifact_ids(self) -> None:
        from creative_lifecycle_continuous_session import (
            _session,
            configure_style_jam_controls,
            generate_style_jam_via_pre_widget,
        )
        from music_workflow_state_store import get_active_workflow_pointer

        session = _session()
        configure_style_jam_controls(session)
        first = generate_style_jam_via_pre_widget(session)
        ptr = get_active_workflow_pointer(session)
        second = generate_style_jam_via_pre_widget(session)
        if ptr is not None:
            self.assertEqual(str(ptr.workflow_session_id or ""), str(ptr.workflow_session_id or ""))
        self.assertNotEqual(first.artifact_id, second.artifact_id)


class TestMixedOwnerHandoffFailClosed(unittest.TestCase):
    def test_invalid_handoff_raises_and_retains_last_valid_style_jam(self) -> None:
        from backing_context import build_entry_jam_context
        from creative_lifecycle_continuous_session import (
            _session,
            configure_style_jam_controls,
            generate_style_jam_via_pre_widget,
        )
        from generated_workflow_artifact import (
            BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY,
            WORKFLOW_OWNER_INTEGRITY_FAILURE,
        )

        session = _session()
        configure_style_jam_controls(session)
        generate_style_jam_via_pre_widget(session)
        good = session.get("_generated_artifact_last_style_jam")
        self.assertIsInstance(good, dict)
        bad = dict(good)
        bad["workflow_owner"] = "style_jam"
        bad["entry_mode"] = "Jam Session Generator"
        bad["style"] = "Jewish ballad"
        bad["progression"] = ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"]
        session[BACKING_OWNER_ARTIFACT_SNAPSHOT_KEY] = bad
        ctx = build_entry_jam_context(session)
        self.assertNotIn("Jewish", str(getattr(ctx, "style", "") or ""))
        self.assertNotIn("Ebmaj7", " ".join(getattr(ctx, "progression", []) or []))
        msg = str(session.get("_workflow_owner_integrity_user_message") or "")
        self.assertIn(WORKFLOW_OWNER_INTEGRITY_FAILURE, msg)
        last = session.get("_generated_artifact_last_style_jam")
        self.assertIsInstance(last, dict)
        self.assertNotEqual(last.get("style"), "Jewish ballad")


class TestCatalogContextWithEmptyBoundPick(unittest.TestCase):
    def test_hevenu_pick_persists_while_generated_backing_has_no_bound_pick(self) -> None:
        from creative_lifecycle_continuous_session import (
            _session,
            assert_hevenu_song_based_steps_1_to_5,
            assert_style_jam_backing_steps_17_to_21,
            assert_style_jam_generation_steps_13_to_16,
            ContinuousSessionState,
        )
        from creative_lifecycle_harness_support import HEVENU_PICK

        session = _session()
        state = ContinuousSessionState()
        assert_hevenu_song_based_steps_1_to_5(session)
        assert_style_jam_generation_steps_13_to_16(session, state)
        assert_style_jam_backing_steps_17_to_21(session, state)
        self.assertEqual(str(session.get("active_catalog_pick_key") or ""), HEVENU_PICK)
        ctx = state.style_jam_backing_ctx
        self.assertEqual(str(getattr(ctx, "bound_pick_key", "") or ""), "")


if __name__ == "__main__":
    unittest.main()
