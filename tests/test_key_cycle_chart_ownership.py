"""Key Cycling: a chart or take is shown / played only under its own key.

Browser acceptance (KC-NAV-12) caught two forms of one defect:
- Next from the last key (wrap to key 1) put C's grid on screen labelled G; the
  audible-key sync trusted the label and never repaired it.
- Rapid Next x3 played Ab's take under B (chip, sheet and Current/Next said B).
"""
from __future__ import annotations

from pathlib import Path

import backing_key_cycle as kc
from backing_key_cycle_handoff import build_cycle_lead_sheet_html

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
SECTIONS = {"Verse": ["Em", "D", "G", "C"]}


def test_cycle_chart_names_its_sounding_key() -> None:
    html = build_cycle_lead_sheet_html(sounding_key="Ab", sections=SECTIONS, song_name="Shallow")
    assert 'data-kc-chart-key="Ab"' in html
    assert html.count("data-kc-chart-key=") == 1


def test_written_chart_names_the_concert_key() -> None:
    # A written projection still belongs to the concert take it follows.
    html = build_cycle_lead_sheet_html(
        sounding_key="Dm", sections=SECTIONS, song_name="Blue Bossa", chart_display_key="Em"
    )
    assert 'data-kc-chart-key="Dm"' in html


def _session_with_charts(keys: list[str]) -> dict:
    bag = {k: {"chart_html": f'<div class="lead-sheet backing-chart-sheet" data-kc-chart-key="{k}">{k}</div>'} for k in keys}
    return {kc.BACKING_KEY_CYCLE_PREPARED_KEY: bag}


def test_step_charts_wrap_from_the_last_key(monkeypatch) -> None:
    monkeypatch.setattr(kc, "_prepared_entry_current", lambda s, e: True)
    seq = ["G", "Ab", "A", "Bb", "B", "C", "Db", "D", "Eb", "E", "F", "F#"]
    ss = _session_with_charts(seq)
    out = kc._cycle_step_charts(ss, seq, "F#")
    assert set(out) == {"F", "G"}   # Previous, and Next wrapping to key 1
    assert 'data-kc-chart-key="G"' in out["G"]
    assert set(kc._cycle_step_charts(ss, seq, "G")) == {"F#", "Ab"}


def test_step_charts_skip_unprepared_keys(monkeypatch) -> None:
    monkeypatch.setattr(kc, "_prepared_entry_current", lambda s, e: True)
    seq = ["G", "Ab", "A"]
    assert kc._cycle_step_charts(_session_with_charts(["G"]), seq, "G") == {}
    assert kc._cycle_step_charts({}, seq, "Bb") == {}


def test_command_publishes_step_charts() -> None:
    assert '"stepCharts": _cycle_step_charts(session, _cmd_sequence, sounding)' in SRC


def test_browser_refuses_a_chart_under_another_key() -> None:
    i = SRC.index("function applyLeadSheetHtml(html, sounding)")
    body = SRC[i:i + 600]
    assert "chartKeyOfHtml(body)" in body and "owner !== key" in body


def test_sync_compares_the_chart_on_screen() -> None:
    i = SRC.index("const shown = shownChartKey();")
    window = SRC[i:i + 300]
    assert "shown === hold" in window
    # The old guard trusted the last label alone.
    assert "if (String(parentWin.__kcSheetKey || '') === hold) return;" not in SRC


def test_browser_never_labels_another_keys_take() -> None:
    i = SRC.index("function armIdleFromUrl(el, url, sounding, role)")
    assert "kcUrlKeyOf(url) !== String(sounding).trim()" in SRC[i:i + 500]
    assert "if (wantUrl && kcUrlKeyOf(wantUrl) && kcUrlKeyOf(wantUrl) !== target) wantUrl = '';" in SRC
    assert "if (url && kcUrlKeyOf(url) && kcUrlKeyOf(url) !== target) url = '';" in SRC
