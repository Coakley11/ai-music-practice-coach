"""Verify open lead sheet across 2 natural key changes on 8510 (no duplicate chart)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

# Fast passes for verify only — cleared before leave-off.
os.environ["KC_SHORT_PASS_BARS"] = "2"
os.environ["KC_SHORT_PASS_LOOPS"] = "1"

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import (
    configure_verse,
    goto_backing_shape,
    open_lead_sheet,
    snap_chart,
    wait_key_change,
)

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle" / "leadsheet_open_2x_natural.json"


def sheet_state(page) -> dict:
    return page.evaluate(
        """() => {
          const sheets = [...document.querySelectorAll('.backing-chart-sheet, .lead-sheet')];
          const host = document.getElementById('kc-lead-sheet-host');
          const openBtn = [...document.querySelectorAll('button')].some((b) =>
            /Open lead sheet/i.test(b.innerText || '')
          );
          const closeBtn = [...document.querySelectorAll('button')].some((b) =>
            /Close lead sheet/i.test(b.innerText || '')
          );
          const highlighted = document.querySelectorAll(
            '.live-chart-cell.current-chord, .chord-cell.current-chord'
          ).length;
          const keyAttr = (sheets[0] && sheets[0].getAttribute('data-kc-playing-key')) || '';
          const keyPill = sheets[0]
            ? ([...sheets[0].querySelectorAll('.meta-pill')]
                .map((e) => (e.textContent || '').trim())
                .find((t) => /^Key:/i.test(t)) || '')
            : '';
          const titles = sheets.map((s) =>
            ((s.querySelector('.lead-title') || {}).textContent || '').trim()
          );
          return {
            sheet_count: sheets.length,
            host: !!host,
            open_btn: openBtn,
            close_btn: closeBtn,
            highlighted,
            key_attr: keyAttr,
            key_pill: keyPill,
            titles,
            sounding: window.__kcLastSounding || '',
          };
        }"""
    )


def main() -> int:
    report: dict = {"ok": False, "transitions": []}
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        assert goto_backing_shape(page), "goto backing/shape failed"
        configure_verse(page, loops=1)
        set_cycle_mode(page, True)
        click_play(page)
        audio = wait_kc_audio(page, 120)
        report["audio"] = audio
        assert audio.get("ok"), audio
        assert open_lead_sheet(page), "could not open lead sheet"
        page.wait_for_timeout(1500)
        base = sheet_state(page)
        report["after_open"] = base
        print("after_open", base)
        assert base["sheet_count"] == 1, base
        assert base["close_btn"] and not base["open_btn"], base
        assert base["host"] or base["sheet_count"] == 1, base

        key = str(cycle_ui(page).get("sounding") or base.get("sounding") or "")
        for i in range(2):
            ch = wait_key_change(page, key, 90.0)
            page.wait_for_timeout(800)
            st = sheet_state(page)
            # Highlight should appear quickly after the new key starts
            if st["highlighted"] < 1:
                page.wait_for_timeout(600)
                st = sheet_state(page)
            entry = {"i": i, "change": ch, "sheet": st}
            report["transitions"].append(entry)
            print("transition", i, ch.get("to") or ch, st)
            assert ch.get("ok") or ch.get("to") or ch.get("sounding"), ch
            assert st["sheet_count"] == 1, st
            assert st["close_btn"] and not st["open_btn"], "sheet closed/reopened"
            assert st["highlighted"] >= 1, "missing highlight after key change"
            new_key = str(
                st.get("sounding")
                or cycle_ui(page).get("sounding")
                or (ch.get("to") if isinstance(ch, dict) else "")
                or ""
            )
            assert new_key and new_key != key, (key, new_key, ch)
            # Chart should show the new key
            pill = st.get("key_pill") or ""
            attr = st.get("key_attr") or ""
            assert (new_key in pill) or (new_key == attr) or (new_key in attr), (
                "chart key not updated",
                new_key,
                pill,
                attr,
            )
            key = new_key

        report["ok"] = True
        # Soft off for leave script
        try:
            click_playbar(page, "off")
        except Exception:
            pass
        set_cycle_mode(page, False)
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("WROTE", OUT, "ok=", report["ok"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
