"""Key Cycle Practice preview is inert — no canonical Practice Key or source mutation."""

from __future__ import annotations

import copy
import unittest

from backing_display import render_backing_advanced_settings_future_previews
from key_cycle_practice_preview import (
    KEY_CYCLE_ENGINE_SESSION_KEYS,
    KEY_CYCLE_PREVIEW_OPTIONS,
    KEY_CYCLE_PREVIEW_STATUS,
    KEY_CYCLE_PREVIEW_TITLE,
    key_cycle_preview_writes_session,
    render_key_cycle_practice_preview,
)


class _FakeSt:
    def __init__(self, session: dict) -> None:
        self.session_state = session
        self.markdown_calls: list[tuple[str, dict]] = []

    def markdown(self, body: str, **kwargs: object) -> None:
        self.markdown_calls.append((str(body), dict(kwargs)))


class TestKeyCyclePracticePreviewInert(unittest.TestCase):
    def test_preview_does_not_write_session_or_canonical_keys(self) -> None:
        session = {
            "display_key": "Bm",
            "concert_key": "Bm",
            "song": "Shape of You",
            "studio_page": "backing",
            "active_music_source": "catalog",
            "backing_track_scope": "Full song",
            "backing_track_loops": 2,
            "improv_song_source": "Active song",
        }
        before = copy.deepcopy(session)
        st = _FakeSt(session)
        render_key_cycle_practice_preview(st)
        self.assertEqual(session, before)
        self.assertFalse(key_cycle_preview_writes_session())
        self.assertTrue(st.markdown_calls)
        html = "\n".join(body for body, _ in st.markdown_calls)
        self.assertIn(KEY_CYCLE_PREVIEW_TITLE, html)
        self.assertIn(KEY_CYCLE_PREVIEW_STATUS, html)
        for opt in KEY_CYCLE_PREVIEW_OPTIONS:
            self.assertIn(opt, html)
        self.assertIn("aria-disabled", html)

    def test_shared_advanced_settings_helper_is_also_inert(self) -> None:
        session = {
            "display_key": "C",
            "concert_key": "C",
            "song": "Trial Song",
            "active_music_source": "custom_progression",
        }
        before = copy.deepcopy(session)
        st = _FakeSt(session)
        render_backing_advanced_settings_future_previews(st)
        self.assertEqual(session, before)

    def test_engine_session_keys_are_not_persist_keys(self) -> None:
        from creative_workspace_persistence import CREATIVE_WORKSPACE_EXTRA_KEYS
        from music_persistent_state import _PERSIST_KEYS

        persist = set(_PERSIST_KEYS) | set(CREATIVE_WORKSPACE_EXTRA_KEYS)
        overlap = persist & KEY_CYCLE_ENGINE_SESSION_KEYS
        self.assertFalse(overlap, f"Key Cycle engine keys must not persist yet: {overlap}")

    def test_preview_does_not_expose_interactive_widgets(self) -> None:
        st = _FakeSt({})
        st.radio = lambda *a, **k: self.fail("preview must not create a radio widget")  # type: ignore[method-assign]
        st.selectbox = lambda *a, **k: self.fail("preview must not create a selectbox")  # type: ignore[method-assign]
        st.checkbox = lambda *a, **k: self.fail("preview must not create a checkbox")  # type: ignore[method-assign]
        render_key_cycle_practice_preview(st)


if __name__ == "__main__":
    unittest.main()
