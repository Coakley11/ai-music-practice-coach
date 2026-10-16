"""Resume must never un-pause the OLD key's buffer while a new anchor / arrangement is pending.

Paused on key A, Practice Key changed to D: Python re-anchors immediately but the buffer in
the page still holds A. Pressing Resume used to un-pause that buffer (the old key sounded
while the new Practice Key was already accepted). The playbar now marks the hold
(``data-hold-stale``) and the page script refuses a user Resume while it is set; the new WAV
starts playing once it is installed.
"""
from __future__ import annotations

import inspect

import backing_key_cycle as kc
from backing_key_cycle import (
    pause_key_cycle,
    render_backing_key_cycle_playback_bar,
    resume_key_cycle,
    start_key_cycle,
)


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    def __init__(self) -> None:
        self.html_calls: list[str] = []

    def html(self, value: str) -> None:
        self.html_calls.append(value)

    def markdown(self, *_a, **_k) -> None:
        return None

    def columns(self, count):
        return [_Ctx() for _ in range(count)]

    def button(self, *_a, **_k) -> bool:
        return False

    def rerun(self) -> None:
        return None


def _session() -> dict:
    s = {
        "backing_source_kind": "catalog",
        "practice_key": "G",
        "concert_practice_key": "G",
        "instrument": "Piano",
        "_backing_key_cycle_sessions": {},
        "_kc_current_static_url": "/app/static/kc/old_a.wav",
    }
    start_key_cycle(s, start_key="G", interval=1, direction="up")
    return s


def _bar_html(session: dict) -> str:
    fake = _FakeSt()
    render_backing_key_cycle_playback_bar(fake, session)
    return "\n".join(fake.html_calls)


def test_plain_pause_has_no_stale_hold() -> None:
    s = _session()
    pause_key_cycle(s)
    assert 'data-hold-stale="1"' not in _bar_html(s)
    resume_key_cycle(s)
    assert 'data-hold-stale="1"' not in _bar_html(s)


def test_pending_practice_key_while_paused_marks_the_buffer_stale() -> None:
    from backing_practice_key_control import commit_backing_practice_key

    s = _session()
    pause_key_cycle(s)
    s["_backing_transport_user_stopped"] = True
    commit_backing_practice_key(s, "D")
    assert s.get(kc.BACKING_KEY_CYCLE_SETTINGS_PENDING_KEY)
    assert 'data-hold-stale="1"' in _bar_html(s)


def test_resume_with_pending_practice_key_keeps_the_hold_until_the_new_wav_is_installed() -> None:
    from backing_practice_key_control import commit_backing_practice_key

    s = _session()
    pause_key_cycle(s)
    s["_backing_transport_user_stopped"] = True
    commit_backing_practice_key(s, "D")
    resume_key_cycle(s)
    assert s.get("_kc_pk_regen_pending")
    assert 'data-hold-stale="1"' in _bar_html(s)
    # Installing the replacement WAV releases the hold.
    kc.adopt_explicit_arrangement_url(s, "/app/static/kc/new_d.wav")
    # The generate path that installs the WAV also consumes the regeneration flags.
    s.pop(kc.BACKING_KEY_CYCLE_CONTINUE_PLAY_KEY, None)
    s["backing_needs_regen"] = False
    try:
        from songs.key_state import BACKING_NEEDS_REGEN

        s[BACKING_NEEDS_REGEN] = False
    except Exception:
        pass
    assert not s.get("_kc_pk_regen_pending")
    assert 'data-hold-stale="1"' not in _bar_html(s)


def test_page_script_refuses_a_user_resume_while_the_hold_is_set() -> None:
    src = inspect.getsource(kc)
    assert 'ui-key-cycle-playbar[data-hold-stale="1"]' in src
    assert "__kcStaleResumeBlocked" in src
    # Back to loop start keeps its explicit contract (starts immediately).
    assert "__kcResumeAudio({{ force: true }})" in src


def test_commands_older_than_a_user_pause_click_cannot_undo_it() -> None:
    src = inspect.getsource(kc)
    # The click stamps the epoch current at click time ...
    assert "parentWin.__kcPauseGuard = {{" in src
    # ... and applyCmd drops older-epoch commands that would change transport state.
    assert "Number(cmd.epoch || 0) <= Number(pg.epoch || 0)" in src
    assert "__kcStalePauseCmdDrops" in src
    # Python bumps the epoch when it handles the toggle, which is what releases the guard.
    s = {"_kc_player_cmd_epoch": 5}
    from backing_key_cycle import start_key_cycle as _start

    sess = {
        "backing_source_kind": "catalog",
        "practice_key": "G",
        "concert_practice_key": "G",
        "instrument": "Piano",
        "_backing_key_cycle_sessions": {},
        "_kc_player_cmd_epoch": 5,
    }
    _start(sess, start_key="G", interval=1, direction="up")
    before = int(sess.get("_kc_player_cmd_epoch") or 0)
    pause_key_cycle(sess)
    assert int(sess["_kc_player_cmd_epoch"]) == before + 1
    resume_key_cycle(sess)
    assert int(sess["_kc_player_cmd_epoch"]) == before + 2
