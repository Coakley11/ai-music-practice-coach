"""The first Off click after the current player is playing must be honoured.

``_kc_suppress_spurious_cycle_off`` swallows Off+user_toggled snaps from remount churn right
after Key Cycling is armed, but a real click looks identical and no rerun happens while audio
plays. The JS player now sends ``play_started`` (same handoff channel) when the current
cycle/epoch first plays audibly; Python then disarms the guard, only for the cycle that armed it.
"""
from __future__ import annotations

from pathlib import Path

import backing_key_cycle as kc
from backing_key_cycle import (
    disarm_spurious_off_on_play_started,
    is_cycle_active,
    render_backing_key_cycle_controls,
    start_key_cycle,
    stop_key_cycle,
)
from tests.test_backing_key_cycle_ui_contract import _ControlsSt, _session

MODE = "backing_key_cycle_enabled_ui"
RUNS = "_kc_suppress_spurious_cycle_off_runs"
FLAG = "_kc_suppress_spurious_cycle_off"


def _turn_on(session: dict) -> None:
    session["_kc_cycle_user_toggled"] = True
    render_backing_key_cycle_controls(_ControlsSt(session, cycling="On"), session)
    assert is_cycle_active(session)


def _remount_off_snap(session: dict) -> None:
    session[MODE] = "Off"
    session["_kc_cycle_user_toggled"] = True
    render_backing_key_cycle_controls(_ControlsSt(session, cycling="Off"), session)


def _ack(session: dict, **over) -> dict:
    ack = {
        "kind": "play_started",
        "ackId": over.pop("ackId", "ps_test"),
        "cycleId": str(session.get("_kc_cycle_id") or ""),
        "epoch": int(session.get("_kc_player_cmd_epoch") or 0),
        "passId": 0,
        "playingKey": "C",
    }
    ack.update(over)
    return ack


def test_enable_arms_suppression_for_the_current_cycle() -> None:
    session = _session()
    _turn_on(session)
    assert session.get(FLAG)
    assert int(session.get(RUNS) or 0) >= 12
    assert "_kc_suppress_arm_epoch" in session


def test_remount_storm_after_enable_keeps_cycle_on() -> None:
    session = _session()
    _turn_on(session)
    for i in range(8):
        _remount_off_snap(session)
        assert is_cycle_active(session), f"collapsed on remount {i}"
        assert session.get(MODE) == "On"


def test_current_play_started_ack_disarms() -> None:
    session = _session()
    _turn_on(session)
    ok, reason = disarm_spurious_off_on_play_started(session, _ack(session))
    assert (ok, reason) == (True, "disarmed")
    assert not session.get(FLAG)
    assert not session.get(RUNS)


def test_stale_cycle_ack_does_not_disarm_a_newer_session() -> None:
    session = _session()
    _turn_on(session)  # session A
    stale = _ack(session, ackId="ps_A")
    stop_key_cycle(session)
    _turn_on(session)  # session B (new cycle id, guard re-armed)
    assert stale["cycleId"] != session["_kc_cycle_id"]

    ok, reason = disarm_spurious_off_on_play_started(session, stale)
    assert (ok, reason) == (False, "stale_cycle")
    assert session.get(FLAG) and int(session.get(RUNS) or 0) >= 12
    _remount_off_snap(session)  # still protected
    assert is_cycle_active(session)


def test_stale_epoch_ack_does_not_disarm() -> None:
    session = _session()
    session["_kc_player_cmd_epoch"] = 7
    _turn_on(session)
    old = _ack(session, epoch=3)
    ok, reason = disarm_spurious_off_on_play_started(session, old)
    assert (ok, reason) == (False, "stale_epoch")
    assert session.get(FLAG)
    ok, _ = disarm_spurious_off_on_play_started(session, _ack(session, epoch=7))
    assert ok


def test_wrong_kind_or_inactive_cycle_does_not_disarm() -> None:
    session = _session()
    _turn_on(session)
    assert disarm_spurious_off_on_play_started(session, _ack(session, kind="playing"))[0] is False
    stop_key_cycle(session)
    assert disarm_spurious_off_on_play_started(session, _ack(session))[0] is False


def test_first_off_click_after_current_playback_is_honoured_and_tears_down() -> None:
    session = _session()
    _turn_on(session)
    assert disarm_spurious_off_on_play_started(session, _ack(session))[0]
    session["_backing_autoplay"] = True

    _remount_off_snap(session)  # the user's single Off click

    assert not is_cycle_active(session)
    assert session.get(MODE) == "Off"
    assert session.get("backing_key_cycle_enabled") is False
    assert session.get("_kc_hard_stop") is True
    assert session.get("_kc_pause_audio") is True
    assert session.get("_backing_autoplay") is False
    assert session.get("_backing_transport_user_stopped") is True
    assert session.get("_kc_persistent_player_mounted") is False


def test_off_on_play_off_works_again() -> None:
    session = _session()
    for _ in range(3):
        _turn_on(session)
        assert session.get(FLAG)  # re-armed on every enable
        assert disarm_spurious_off_on_play_started(session, _ack(session))[0]
        _remount_off_snap(session)
        assert not is_cycle_active(session)


def test_off_before_play_is_still_suppressed_known_limitation() -> None:
    """No player-playing proof exists yet, so a quick Off right after On is swallowed."""
    session = _session()
    _turn_on(session)
    _remount_off_snap(session)
    assert is_cycle_active(session)


def test_playbar_turn_off_path_unchanged() -> None:
    session = _session()
    start_key_cycle(session, start_key="C")
    stop_key_cycle(session)
    assert not is_cycle_active(session)
    assert session.get("_kc_hard_stop") is True
    assert session.get("_key_cycle_force_ui_off") is True


def test_handoff_receiver_forwards_play_started_single_and_batch(monkeypatch) -> None:
    import json

    import backing_key_cycle_handoff as h

    session = _session()
    single = {"kind": "play_started", "ackId": "a1", "cycleId": "c1", "epoch": 1}
    monkeypatch.setattr(h, "_kc_handoff_component", lambda **_k: single)
    assert h.render_handoff_component(None, session, expect_cycle_id="c1") == single

    batch = {
        "kind": "playing_batch",
        "acks_json": json.dumps(
            [single, {"kind": "playing", "ackId": "a2", "cycleId": "c1", "passId": 1, "playingKey": "D"}]
        ),
    }
    monkeypatch.setattr(h, "_kc_handoff_component", lambda **_k: batch)
    first = h.render_handoff_component(None, session, expect_cycle_id="c1")
    assert first["kind"] == "play_started"
    assert session["_kc_handoff_pending_acks"][0]["kind"] == "playing"


def test_pass_bridge_play_started_disarms_without_advancing(monkeypatch) -> None:
    import backing_key_cycle_handoff as h

    session = _session()
    _turn_on(session)
    key_before = kc.temporary_playback_key(session)
    ack = _ack(session)
    monkeypatch.setattr(h, "render_handoff_component", lambda *_a, **_k: ack)

    kc.render_backing_key_cycle_pass_bridge(object(), session)

    assert not session.get(FLAG) and not session.get(RUNS)
    assert kc.temporary_playback_key(session) == key_before
    assert "ps_test" in (session.get(h.ACKED_IDS_KEY) or [])


def test_parent_realm_watchdog_emits_play_started_once_per_cycle_epoch() -> None:
    src = Path(kc.__file__).read_text(encoding="utf-8")
    assert "kind: 'play_started'" in src
    # Parent-realm watchdog (iframe-realm timers die when Streamlit remounts the frame).
    assert "st._playStartedAckKey !== psKey" in src
    assert "act && !act.paused && !act.muted && Number(act.currentTime || 0) >= 0.2" in src
    assert "__kcWatchVersion = 31" in src and "__kcWatchVersion !== 31" in src
