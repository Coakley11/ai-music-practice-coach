"""Music Coach staged insight survives workspace apply and renders on-page."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from applied_math_return_insight import (
    SESSION_PENDING_KEY,
    local_ami_insight_should_preserve,
    render_suite_applied_math_insight_for_page,
)
from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami.submit_integration import stage_routed_music_coach_insight
from music_coach_ami.submit_diagnostics import build_music_coach_submit_diagnostics
from music_persistent_state import apply_music_disk_state


class MusicCoachInsightLifecycleTests(unittest.TestCase):
    def test_local_preserve_blocks_empty_disk_overwrite(self) -> None:
        st = MagicMock()
        insight = {
            "insight_id": "ins-scale",
            "source_app": "music",
            "source_page": "practice",
            "conclusion": "**Eb major** scale",
            "question": "Show me Eb major",
            "canonical_instant": True,
            "coach_submit_diagnostics": {"result_path": "routed_coach"},
        }
        st.session_state = {
            SESSION_PENDING_KEY: insight,
            "studio_page": "practice",
            "_ami_submit_render_insight_this_run": True,
        }
        self.assertTrue(local_ami_insight_should_preserve(st))
        payload = {
            "core": {"studio_page": "practice"},
            "session": {SESSION_PENDING_KEY: {}},
            "music_workspace_state": {"studio_page": "practice"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True):
            apply_music_disk_state(
                st,
                payload,
                song_picker_catalog={},
                song_library={},
            )
        self.assertEqual(st.session_state[SESSION_PENDING_KEY]["insight_id"], "ins-scale")

    def test_empty_disk_pending_does_not_clobber_staged_insight(self) -> None:
        st = MagicMock()
        insight = {
            "insight_id": "ins-staged",
            "source_app": "music",
            "source_page": "practice",
            "conclusion": "Tone plan ready",
            "question": "30-minute plan",
            "canonical_instant": True,
        }
        st.session_state = {"_ami_pending_insight": insight, "studio_page": "practice"}
        payload = {
            "core": {"studio_page": "practice"},
            "session": {"_ami_pending_insight": {}},
            "music_workspace_state": {"studio_page": "practice"},
        }
        with patch("music_persistent_state.apply_saved_music_context", return_value=True):
            apply_music_disk_state(st, payload, song_picker_catalog={}, song_library={})
        self.assertEqual(st.session_state["_ami_pending_insight"]["insight_id"], "ins-staged")

    def test_render_suite_emits_markdown_for_routed_scale(self) -> None:
        st = MagicMock()
        ss: dict = {"studio_page": "practice", "_ami_submit_render_insight_this_run": True}
        st.session_state = ss
        q = "Show me the E\u266d major scale in sheet music."
        req, resp = run_coach_submit(q, ss, ami_ctx={"coach_page": "practice"})
        assert resp is not None
        diag = build_music_coach_submit_diagnostics(req, resp, result_path="routed_coach")
        with patch(
            "applied_math_return_insight.store_applied_math_insight",
            return_value="ins-1",
        ), patch("applied_math_return_insight.stage_pending_insight"):
            stage_routed_music_coach_insight(
                st,
                ss,
                question=q,
                source_page="practice",
                coach_req=req,
                coach_resp=resp,
                diagnostics=diag,
                question_id="q1",
            )
        markdown_calls: list[str] = []

        def _markdown(text: str, *args, **kwargs) -> None:
            markdown_calls.append(str(text))

        st.markdown = _markdown
        st.container = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=st), __exit__=MagicMock()))
        st.columns = MagicMock(return_value=(st, st))
        st.button = MagicMock(return_value=False)
        st.caption = MagicMock()
        st.code = MagicMock()
        st.expander = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=st), __exit__=MagicMock()))
        st.json = MagicMock()
        with patch("streamlit.components.v1.html"):
            ok = render_suite_applied_math_insight_for_page(
                st,
                source_app="music",
                source_page="practice",
            )
        self.assertTrue(ok)
        self.assertTrue(ss.get("_music_coach_insight_markdown_rendered"))
        self.assertTrue(any("Eb" in c or "major" in c for c in markdown_calls))


if __name__ == "__main__":
    unittest.main()
