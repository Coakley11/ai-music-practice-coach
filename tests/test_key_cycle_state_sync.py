"""Key highlight / Python key / browser audio must stay one authoritative state.

Regressions found in a real multi-key browser run:
 * the Off-guard disarm exposed a Play-WAV re-adoption that froze later key acks;
 * a manual Previous acknowledgement was rejected, so Python snapped the highlight back;
 * a play_started ack queued ahead of a manual Next/Previous ack delayed it a whole rerun.
"""
from __future__ import annotations

import backing_key_cycle as kc
from backing_key_cycle import (
    _confirm_owner_cycle_to_playing_key,
    advance_key_cycle_now,
    play_wav_adoption_needed,
    start_key_cycle,
    temporary_playback_key,
)
from tests.test_backing_key_cycle_ui_contract import _session


def _running_session() -> dict:
    session = _session()
    start_key_cycle(session, start_key="C")
    return session


def test_play_wav_adopted_once_not_after_every_key_change() -> None:
    session = {}
    play_wav = "/app/static/kc/aaaaaaaaaaaaaaaaaaaa.wav"
    # First Play: generate already installed it as the current URL -> nothing to adopt.
    assert play_wav_adoption_needed(session, play_wav, play_wav) is False
    # After a Next/handoff the current key's URL differs from the Play WAV forever.
    other = "/app/static/kc/bbbbbbbbbbbbbbbbbbbb.wav"
    for _ in range(5):
        assert play_wav_adoption_needed(session, play_wav, other) is False
    # A genuinely NEW Play WAV (Feel/BPM/Scope change) is adopted exactly once.
    new_wav = "/app/static/kc/cccccccccccccccccccc.wav"
    assert play_wav_adoption_needed(session, new_wav, other) is True
    assert play_wav_adoption_needed(session, new_wav, other) is False


def test_play_wav_not_adopted_during_display_remount_guard() -> None:
    session = {}
    assert play_wav_adoption_needed(session, "/a.wav", "/b.wav", display_guard=True) is False
    assert play_wav_adoption_needed(session, "/a.wav", "/b.wav", display_guard=False) is False
    assert play_wav_adoption_needed(session, "/n.wav", "/b.wav", display_guard=True) is False
    assert play_wav_adoption_needed(session, "/n.wav", "/b.wav", display_guard=False) is True


def test_manual_previous_ack_steps_python_back() -> None:
    session = _running_session()
    advance_key_cycle_now(session)
    advance_key_cycle_now(session)
    here = temporary_playback_key(session)
    prev = kc.peek_cycle_key_at_delta(session, steps=-1)
    assert prev and prev != here

    changed, data = _confirm_owner_cycle_to_playing_key(session, prev, from_key=here, pass_id=3, manual=True)

    assert changed is True
    assert temporary_playback_key(session) == prev
    assert session.get("_kc_skip_audio_remount") is True  # browser already switched audio


def test_manual_previous_wraps_from_first_key() -> None:
    session = _running_session()
    first = temporary_playback_key(session)
    prev = kc.peek_cycle_key_at_delta(session, steps=-1)
    changed, _ = _confirm_owner_cycle_to_playing_key(session, prev, from_key=first, pass_id=1, manual=True)
    assert changed is True
    assert temporary_playback_key(session) == prev


def test_non_manual_backward_ack_is_still_rejected() -> None:
    session = _running_session()
    advance_key_cycle_now(session)
    advance_key_cycle_now(session)
    here = temporary_playback_key(session)
    prev = kc.peek_cycle_key_at_delta(session, steps=-1)
    changed, _ = _confirm_owner_cycle_to_playing_key(session, prev, from_key=here, pass_id=3, manual=False)
    assert changed is False
    assert temporary_playback_key(session) == here  # late natural acks must not walk back


def test_pass_bridge_handles_play_started_and_queued_manual_ack_in_one_run(monkeypatch) -> None:
    import backing_key_cycle_handoff as h

    session = _running_session()
    nxt = kc.peek_cycle_key_at_delta(session, steps=1)
    cycle = str(session["_kc_cycle_id"])
    play_started = {"kind": "play_started", "ackId": "ps_x", "cycleId": cycle, "epoch": 99}
    manual = {
        "kind": "playing",
        "ackId": "sw_x",
        "cycleId": cycle,
        "passId": 1,
        "playingKey": nxt,
        "fromKey": temporary_playback_key(session),
        "manualSwitch": True,
        "natural": False,
        "epoch": 99,
    }
    session["_kc_handoff_pending_acks"] = [manual]
    monkeypatch.setattr(h, "render_handoff_component", lambda *_a, **_k: play_started)

    class _St:
        reruns = 0

        def rerun(self):
            _St.reruns += 1

    kc.render_backing_key_cycle_pass_bridge(_St(), session)

    assert temporary_playback_key(session) == nxt, "manual Next ack was left waiting for another rerun"
    assert _St.reruns == 1


def test_consecutive_manual_acks_may_repeat_pass_id_but_natural_may_not() -> None:
    from backing_key_cycle_handoff import LAST_PASS_ID_KEY, validate_playing_ack

    s = {"_kc_cycle_id": "c1", LAST_PASS_ID_KEY: 1}
    base = {"kind": "playing", "cycleId": "c1", "passId": 1, "playingKey": "Ab"}
    ok, why = validate_playing_ack(s, {**base, "ackId": "m2", "manualSwitch": True}, expect_cycle_id="c1")
    assert (ok, why) == (True, "ok")
    ok, why = validate_playing_ack(s, {**base, "ackId": "n2"}, expect_cycle_id="c1")
    assert (ok, why) == (False, "stale_pass_id")


def test_pass_bridge_does_not_rerun_for_a_rejected_or_duplicate_ack(monkeypatch) -> None:
    import backing_key_cycle_handoff as h

    session = _running_session()
    cycle = str(session["_kc_cycle_id"])
    stale = {
        "kind": "playing", "ackId": "dup_1", "cycleId": cycle, "passId": 0,
        "playingKey": temporary_playback_key(session), "natural": True,
    }
    monkeypatch.setattr(h, "render_handoff_component", lambda *_a, **_k: stale)

    class _St:
        reruns = 0

        def rerun(self):
            _St.reruns += 1

    kc.render_backing_key_cycle_pass_bridge(_St(), session)

    assert _St.reruns == 0, "a no-op ack must not start a rerun loop that starves the player publish"
    assert h.ack_already_consumed(session, "dup_1")
