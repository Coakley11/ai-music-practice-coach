"""A command built before the musician's Stop must never start the take again.

Card Stop silences the dual buffer in the browser at once, and the Stop run publishes no
new player command (the cycle is stopped). If Streamlit re-creates the last player frame
during that run, the frame replays its embedded Play command. That command has the same
epoch the browser already holds, so the strictly-behind epoch check let it through and
the stopped key started again (TRANSPORT-13 / -14). The browser now remembers the epoch it
stopped at and drops older-or-equal commands while user-stopped; Python bumps the epoch on
Stop, so every command built after the Stop is newer and applies normally.
"""
from __future__ import annotations

from backing_key_cycle import (
    cycle_persistent_player_bridge_html,
    hard_stop_key_cycle_audio,
    start_key_cycle,
)


def _session() -> dict:
    s = {
        "backing_source_kind": "catalog",
        "practice_key": "G",
        "concert_practice_key": "G",
        "instrument": "Piano",
        "_backing_key_cycle_sessions": {},
    }
    start_key_cycle(s, start_key="G", interval=1, direction="up")
    return s


def test_stop_makes_every_later_command_newer() -> None:
    s = _session()
    before = int(s.get("_kc_player_cmd_epoch") or 0)
    hard_stop_key_cycle_audio(s)
    assert int(s.get("_kc_player_cmd_epoch") or 0) > before


def test_browser_stop_records_its_epoch() -> None:
    html = cycle_persistent_player_bridge_html(cmd_json="{}")
    hard_stop = html.split("parentWin.__kcHardStop = function", 1)[1].split("};", 1)[0]
    assert "state.stoppedEpoch = Number(state.epoch);" in hard_stop


def test_commands_from_before_the_stop_are_dropped_first() -> None:
    html = cycle_persistent_player_bridge_html(cmd_json="{}")
    apply = html.split("parentWin.__kcApplyCmd = function applyCmd(cmd)", 1)[1]
    guard = apply.index("state.stoppedEpoch != null")
    # Ahead of every path that can play: the existing stale-epoch check, Resume / Restart.
    assert guard < apply.index("Number(cmd.epoch) < Number(state.epoch)")
    assert guard < apply.index("if (cmd.restart || cmd.resume)")
    block = apply[guard:apply.index("// A command built before Python learned")]
    assert "Number(cmd.epoch) > Number(state.stoppedEpoch)" in block
    assert "state.stoppedEpoch = null;" in block
    assert "cmd.enabled && state.userPaused && !cmd.hardStop" in block
    assert "cancelPendingPlays();" in block and "return;" in block


def test_turning_cycling_off_forgets_the_stop() -> None:
    html = cycle_persistent_player_bridge_html(cmd_json="{}")
    off = html.split("state.epoch = -1;", 1)[1][:80]
    assert "state.stoppedEpoch = null;" in off
