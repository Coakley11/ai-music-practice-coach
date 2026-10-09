"""The run that handles a Pause/Resume click must render the post-click label.

Streamlit semantics: on_click callbacks run before the script; during the
clicked run ``st.button(key)`` returns True. A label computed from session
state and then mutated inside ``if st.button(...):`` is drawn from the
pre-click state, so the click-handling run ships a stale label to the browser
(observed: "Resume" arriving ~5-6s after a Resume click, over live audio).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from backing_key_cycle import (
    STATUS_HELD,
    STATUS_RUNNING,
    get_owner_cycle_session,
    pause_key_cycle,
    render_backing_key_cycle_playback_bar,
    resume_key_cycle,
    start_key_cycle,
)

PAUSE_KEY = "backing_key_cycle_pause_btn"


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _ClickSt:
    def __init__(self, clicked_key: str | None = None) -> None:
        self.clicked_key = clicked_key
        self.labels: dict[str, str] = {}
        self.label_writes: list[tuple[str | None, str]] = []
        self.callbacks: dict[str, tuple] = {}
        self.reruns = 0
        self.pre_click: _ClickSt | None = None

    def html(self, _v) -> None:
        return None

    def markdown(self, *_a, **_k) -> None:
        return None

    def columns(self, count):
        return [_Ctx() for _ in range(count)]

    def button(self, label, key=None, on_click=None, args=(), kwargs=None, **_k) -> bool:
        self.labels[key] = label
        self.label_writes.append((key, label))
        if on_click is not None:
            self.callbacks[key] = (on_click, tuple(args or ()), dict(kwargs or {}))
        return key == self.clicked_key

    def rerun(self, *_a, **_k) -> None:
        self.reruns += 1


def _session() -> dict:
    s = {
        "backing_source_kind": "catalog",
        "practice_key": "G",
        "concert_practice_key": "G",
        "instrument": "Piano",
        "_backing_key_cycle_sessions": {},
    }
    start_key_cycle(s, start_key="G", interval=1, direction="up")
    s["_kc_current_static_url"] = "/app/static/kc/test.wav"
    return s


def _click(session: dict) -> _ClickSt:
    """Render, then simulate a click exactly as Streamlit sequences it."""
    before = _ClickSt()
    render_backing_key_cycle_playback_bar(before, session)
    cb = before.callbacks.get(PAUSE_KEY)
    if cb is not None:
        fn, args, kwargs = cb
        fn(*args, **kwargs)
    clicked = _ClickSt(clicked_key=PAUSE_KEY)
    render_backing_key_cycle_playback_bar(clicked, session)
    clicked.pre_click = before
    return clicked


def _status(session: dict) -> str:
    return str((get_owner_cycle_session(session) or {}).get("status") or "")


class TestClickRunRendersPostClickLabel(unittest.TestCase):
    def test_resume_click_run_renders_pause(self) -> None:
        session = _session()
        pause_key_cycle(session)
        self.assertEqual(_status(session), STATUS_HELD)
        epoch_before = int(session.get("_kc_player_cmd_epoch") or 0)
        with (
            patch("backing_key_cycle.resume_key_cycle", wraps=resume_key_cycle) as resume,
            patch("backing_key_cycle.pause_key_cycle", wraps=pause_key_cycle) as pause,
        ):
            run = _click(session)
        self.assertEqual(_status(session), STATUS_RUNNING)
        self.assertEqual(run.labels[PAUSE_KEY], "Pause")
        self.assertEqual(run.label_writes.count((PAUSE_KEY, "Pause")), 1)
        self.assertNotIn((PAUSE_KEY, "Resume"), run.label_writes)
        resume.assert_called_once_with(session)
        pause.assert_not_called()
        self.assertEqual(int(session.get("_kc_player_cmd_epoch") or 0), epoch_before + 1)
        self.assertEqual(run.reruns, 0)
        self.assertEqual(run.pre_click.reruns if run.pre_click else -1, 0)

    def test_pause_click_run_renders_resume(self) -> None:
        session = _session()
        self.assertEqual(_status(session), STATUS_RUNNING)
        epoch_before = int(session.get("_kc_player_cmd_epoch") or 0)
        with (
            patch("backing_key_cycle.pause_key_cycle", wraps=pause_key_cycle) as pause,
            patch("backing_key_cycle.resume_key_cycle", wraps=resume_key_cycle) as resume,
        ):
            run = _click(session)
        self.assertEqual(_status(session), STATUS_HELD)
        self.assertEqual(run.labels[PAUSE_KEY], "Resume")
        self.assertEqual(run.label_writes.count((PAUSE_KEY, "Resume")), 1)
        self.assertNotIn((PAUSE_KEY, "Pause"), run.label_writes)
        pause.assert_called_once_with(session)
        resume.assert_not_called()
        self.assertEqual(int(session.get("_kc_player_cmd_epoch") or 0), epoch_before + 1)
        self.assertEqual(run.reruns, 0)
        self.assertEqual(run.pre_click.reruns if run.pre_click else -1, 0)

    def test_click_does_not_double_toggle(self) -> None:
        session = _session()
        pause_key_cycle(session)
        _click(session)
        # One click → one transition, even though the clicked run sees True.
        self.assertEqual(_status(session), STATUS_RUNNING)


if __name__ == "__main__":
    unittest.main()
