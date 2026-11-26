"""Key Cycling takes only its own Previous / Next controls (user, 2026-11-26).

Its page script used to claim any Backing button labelled just "Previous" / "Next" as a key step, and cancelled
the click, so a PDF page turn during a cycle stepped the key instead. Each label fallback now first checks that
the button sits inside Key Cycling's own transport row or carries a backing_key_cycle_* key.
"""

from __future__ import annotations

import re

import backing_key_cycle as kc


def _bridge() -> str:
    return kc.cycle_persistent_player_bridge_html(cmd_json="{}")


def test_key_cycling_knows_its_own_controls_by_their_containers():
    js = _bridge()
    m = re.search(r"function kcOwnsStepButton\(b\) \{(.*?)\n  \}", js, re.S)
    assert m, "kcOwnsStepButton missing"
    body = m.group(1)
    assert 'st-key-kc_transport_row' in body and 'st-key-backing_key_cycle_' in body
    assert "Previous" not in body and "Next" not in body          # by where it is, never by what it says


def test_every_previous_next_label_fallback_is_limited_to_key_cyclings_own_buttons():
    js = _bridge()
    lines = js.splitlines()
    sites = [i for i, line in enumerate(lines) if "Previous( key)?$/i.test(" in line]
    assert len(sites) == 3, sites
    for i in sites:
        window = "\n".join(lines[max(0, i - 4): i + 1])
        assert "kcOwnsStepButton(" in window, window


def test_key_cyclings_own_buttons_stay_in_the_row_the_check_looks_for():
    src = open(kc.__file__, encoding="utf-8").read()
    row = src.index('key="kc_transport_row"')
    for key in ("backing_key_cycle_prev_btn", "backing_key_cycle_advance_btn"):
        assert src.index(f'"{key}"', row) > row
