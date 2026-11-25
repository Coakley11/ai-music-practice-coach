"""The Jazz quartet's horn is the recorded tenor sax when MUSIC_HORNS is on; off, nothing changes.

The ensemble is only presented with a horn when the horn has working audio (the switch is on and the pack is
present); otherwise the Backing card keeps saying "horns not available yet".
"""

from __future__ import annotations

import numpy as np

import backing_audio as ba
import backing_horns as bh
import backing_performance_plan as pp

CHORDS = [
    {"chord": c, "section": "A", "bar_in_section": i, "section_bars": 8}
    for i, c in enumerate(["Cm7", "F7", "Bbmaj7", "Bbmaj7", "Cm7", "F7", "Bbmaj7", "G7"])
]


def _render(plan):
    audio, _ = ba.synthesize_chords_to_numpy(CHORDS, bpm=120, loops=1, style="Jazz swing", performance=plan)
    return audio, dict(ba.LAST_MIX_STATS)


def test_switch_on_the_quartet_plays_the_tenor_sax(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    assert plan.plays("horns") and "horns" not in plan.unavailable
    assert pp.band_summary(plan) == "Piano, tenor sax, bass, drums"
    assert plan.tag().endswith("-k.h.b.d")  # a quartet take with the horn is its own take
    trio = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz trio")
    assert not trio.plays("horns")  # only an ensemble with a horn gets one


def test_switch_off_the_quartet_renders_exactly_as_before(monkeypatch):
    monkeypatch.delenv("MUSIC_HORNS", raising=False)
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    a, stats = _render(plan)
    assert "horns_rms" not in stats
    calls = []
    monkeypatch.setattr(ba, "_horn_background", lambda *a, **k: calls.append(1))
    b, _ = _render(plan)
    assert np.array_equal(a, b) and calls  # the hook runs and adds nothing


def test_the_horn_sits_under_the_rhythm_section(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    plan = pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet")
    with_horn, stats = _render(plan)
    assert stats["horns_rms"] > 0
    ratio_db = 20 * np.log10(stats["horns_rms"] / stats["rhythm_rms"])
    assert -9.5 < ratio_db < -5.5, ratio_db  # HORNS_BALANCE 0.42 = -7.5 dB
    monkeypatch.delenv("MUSIC_HORNS")
    without, _ = _render(pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet"))
    n = min(len(with_horn), len(without))
    assert not np.allclose(with_horn[:n], without[:n])


def test_the_horn_line_follows_the_takes_bars(monkeypatch):
    monkeypatch.setenv("MUSIC_HORNS", "1")
    seen = {}
    real = bh.sustained_background

    def spy(timeline, **kw):
        seen["spans"] = list(timeline)
        return real(timeline, **kw)

    monkeypatch.setattr(bh, "sustained_background", spy)
    _render(pp.resolve_performance_plan(style="Jazz swing", ensemble="Jazz quartet"))
    spans = seen["spans"]
    assert [s.chord for s in spans] == [e["chord"] for e in CHORDS]
    bar = 4 * 60.0 / 120
    assert all(abs(s.start_sec - i * bar) < 1e-9 for i, s in enumerate(spans))
