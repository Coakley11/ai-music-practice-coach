"""Lead Sheet reopened over a live take: its player takes over at the page player's position (one player, no
restart). Real app trace (Catalog, Let It Be, 2026-11-10): close the sheet, then reopen it while the page player
plays -> the reopened sheet player autoplayed from 0:00 beside the page player, and the hand-off recorded on the
click was never taken, because the reopen run was handed the first open's props (hand-off flag off).
"""
from __future__ import annotations

from pathlib import Path

from backing_sheet_mount import lead_sheet_mount_props

TAKE = "/app/static/kc/take.wav|3|"


def _mount(session, *, intent="playing", autoplay=False, countdown=False, handoff=False, take=TAKE):
    return lead_sheet_mount_props(session, take=take, intent=intent, autoplay=autoplay, countdown=countdown, handoff=handoff)


def test_reopen_over_a_live_take_hands_the_new_player_the_handoff() -> None:
    s: dict = {}
    # Play with Lead sheet On: the sheet mounts with autoplay (no hand-off: nothing was playing before it).
    assert _mount(s, autoplay=True) == (True, False, False)
    # Later runs while it stays open keep exactly those props.
    assert _mount(s, autoplay=False) == (True, False, False)
    # Closed (no sheet runs), then reopened over the live take: this run carries the open request.
    autoplay, _, handoff = _mount(s, autoplay=True, handoff=True)
    assert handoff is True, "the reopened sheet's player must take over from the page player"
    assert autoplay is True


def test_runs_after_the_reopen_keep_the_reopen_props_so_the_player_is_not_recreated() -> None:
    s: dict = {}
    _mount(s, autoplay=True)
    _mount(s, autoplay=True, handoff=True)  # reopened
    # The next run: the one-shot request is spent, autoplay may read differently; the HTML must not change.
    assert _mount(s, autoplay=False, handoff=False) == (True, False, True)
    assert _mount(s, autoplay=False, handoff=False) == (True, False, True)


def test_pause_run_while_open_still_keeps_the_first_props() -> None:
    s: dict = {}
    _mount(s, autoplay=True, handoff=True)
    # Pressing Pause triggers a run where autoplay and the request read False: same props (bca2a9c6).
    assert _mount(s, intent="paused", autoplay=False, handoff=False) == (True, False, True)


def test_a_new_take_or_a_stopped_transport_draws_fresh_props() -> None:
    s: dict = {}
    _mount(s, autoplay=True, handoff=True)
    assert _mount(s, take=TAKE.replace("|3|", "|4|"), autoplay=True) == (True, False, False)
    assert _mount(s, take=TAKE.replace("|3|", "|4|"), intent="stopped", autoplay=False) == (False, False, False)


def test_the_app_draws_the_sheet_with_these_props() -> None:
    app = (Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
    assert "lead_sheet_mount_props(" in app
    assert "sheet_open_handoff=bool(_ls_handoff_autoplay)," in app
