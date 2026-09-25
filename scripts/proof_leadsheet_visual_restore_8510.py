"""Visual verify: Off / On / after natural key change lead sheet (full Verse, no SHORT)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, set_cycle_mode
from proof_verse_verify_8510 import (
    configure_verse,
    goto_backing_shape,
    open_lead_sheet,
    wait_key_change,
)

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"


def ensure_sheet_open(page, *, wait_s: float = 20.0) -> bool:
    """Open lead sheet; require Close + live-follow iframe (retry while remounting)."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        close = page.evaluate(
            "() => [...document.querySelectorAll('button')].some(b => /Close lead sheet/i.test(b.innerText||''))"
        )
        open_btn = page.evaluate(
            "() => [...document.querySelectorAll('button')].some(b => /Open lead sheet/i.test(b.innerText||''))"
        )
        live = page.evaluate(
            """() => {
              for (const f of document.querySelectorAll('iframe')) {
                try {
                  const d = f.contentDocument;
                  if (d && d.querySelector('.live-follow-shell #live-chart-root')) return true;
                } catch (e) {}
              }
              return false;
            }"""
        )
        if close and live:
            return True
        if open_btn and not close:
            page.evaluate(
                """() => {
                  const b = [...document.querySelectorAll('button')].find(el =>
                    /Open lead sheet/i.test(el.innerText || '')
                  );
                  if (b) b.click();
                }"""
            )
            page.wait_for_timeout(1500)
            continue
        if close and not live:
            # Streamlit remount in progress — wait for iframe
            page.wait_for_timeout(800)
            continue
        # No Open/Close yet — audio may not be ready
        page.wait_for_timeout(800)
    return False


def snap(page, label: str) -> dict:
    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)
    except Exception:
        pass
    page.screenshot(path=str(OUT / f"leadsheet_{label}.png"), full_page=True)
    # Dedicated crop of the live-follow iframe (actual lead sheet surface)
    try:
        for fr in page.frames:
            try:
                if fr.query_selector(".live-follow-shell"):
                    el = fr.frame_element()
                    el.screenshot(path=str(OUT / f"leadsheet_{label}_iframe.png"))
                    break
            except Exception:
                continue
    except Exception:
        pass
    info = page.evaluate(
        """() => {
          const host = document.getElementById('kc-lead-sheet-host');
          const parentSheets = [...document.querySelectorAll('.backing-chart-sheet, .lead-sheet')]
            .filter((s) => !s.closest('iframe'))
            .filter((s) => !s.closest('#kc-chart-staged'))
            .filter((s) => {
              // Ignore absolute off-screen preload hosts
              const id = (s.parentElement && s.parentElement.id) || '';
              return id !== 'kc-chart-staged';
            })
            .map((s) => ({
              title: ((s.querySelector('.lead-title') || {}).textContent || '').trim(),
              parentId: (s.parentElement && s.parentElement.id) || '',
              inHost: !!s.closest('#kc-lead-sheet-host'),
            }));
          let live = null;
          for (const f of document.querySelectorAll('iframe')) {
            try {
              const d = f.contentDocument;
              if (!d || !d.querySelector('.live-follow-shell')) continue;
              const sheet = d.querySelector('.backing-chart-sheet, .lead-sheet');
              const hi = d.querySelectorAll('.live-chart-cell.current-chord, .chord-cell.current-chord').length;
              live = {
                hasLiveFollow: true,
                hasLivePlayer: !!d.querySelector('.live-player'),
                hasStatusGrid: !!d.querySelector('.live-status-grid'),
                hasChartRoot: !!d.querySelector('#live-chart-root'),
                title: ((d.querySelector('.lead-title') || {}).textContent || '').trim(),
                keyPill: ([...d.querySelectorAll('.meta-pill')]
                  .map((e) => (e.textContent || '').trim())
                  .find((t) => /^Key:/i.test(t)) || ''),
                keyAttr: sheet ? (sheet.getAttribute('data-kc-playing-key') || '') : '',
                highlighted: hi,
                closeVisible: true,
              };
              break;
            } catch (e) {}
          }
          return {
            hostPresent: !!host,
            parentSheetCount: parentSheets.length,
            parentSheets,
            live,
            closeBtn: [...document.querySelectorAll('button')].some((b) =>
              /Close lead sheet/i.test(b.innerText || '')
            ),
            openBtn: [...document.querySelectorAll('button')].some((b) =>
              /Open lead sheet/i.test(b.innerText || '')
            ),
            sounding: window.__kcLastSounding || '',
          };
        }"""
    )
    info["label"] = label
    (OUT / f"leadsheet_{label}_dom.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(label, json.dumps(info, indent=2))
    return info


def assert_actual_sheet(info: dict, *, expect_host: bool = False) -> None:
    assert info.get("closeBtn") and not info.get("openBtn"), info
    assert not info.get("hostPresent"), f"wrong host still present: {info}"
    assert info.get("parentSheetCount", 0) == 0, f"parent duplicate chart: {info}"
    live = info.get("live") or {}
    assert live.get("hasLiveFollow"), f"missing live-follow shell: {info}"
    assert live.get("hasLivePlayer"), f"missing Live Follow-Along Player: {info}"
    assert live.get("hasChartRoot"), f"missing #live-chart-root: {info}"
    assert "Backing chart" in (live.get("title") or ""), info


def main() -> int:
    report: dict = {"ok": False}
    assert not os.environ.get("KC_SHORT_PASS_BARS")
    assert not os.environ.get("KC_SHORT_PASS_LOOPS")
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = b.new_page(viewport={"width": 1400, "height": 1800})
        page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        assert goto_backing_shape(page)
        configure_verse(page, loops=1)

        # --- Off ---
        set_cycle_mode(page, False)
        try:
            click_playbar(page, "off")
        except Exception:
            pass
        click_play(page)
        opened = False
        t0 = time.time()
        while time.time() - t0 < 240:
            if ensure_sheet_open(page):
                opened = True
                break
            click_play(page)
            page.wait_for_timeout(3000)
        assert opened, "live-follow lead sheet never opened"
        page.wait_for_timeout(1500)
        off = snap(page, "OFF")
        assert_actual_sheet(off)
        report["off"] = off

        # --- On (same sheet type) ---
        set_cycle_mode(page, True)
        page.wait_for_timeout(2000)
        click_play(page)
        audio = wait_kc_audio(page, 180)
        if not audio.get("ok"):
            click_play(page)
            audio = wait_kc_audio(page, 120)
        report["audio"] = audio
        assert audio.get("ok"), audio
        page.wait_for_timeout(2000)
        assert ensure_sheet_open(page, wait_s=45.0), "live-follow sheet missing after cycle On"
        on = snap(page, "ON")
        assert_actual_sheet(on)
        report["on"] = on

        # --- Natural key change (full verse, ~40s+) ---
        start = str(cycle_ui(page).get("sounding") or on.get("sounding") or "")
        ch = wait_key_change(page, start, 120.0)
        report["change"] = ch
        assert ch.get("ok"), ch
        page.wait_for_timeout(2000)
        # Must remain open without clicking Open again
        assert page.evaluate(
            "() => [...document.querySelectorAll('button')].some(b => /Close lead sheet/i.test(b.innerText||''))"
        ), "Close lead sheet missing after handoff (user would need to reopen)"
        after = snap(page, "AFTER_KEY")
        assert_actual_sheet(after)
        live = after["live"]
        new_key = str(ch.get("to") or after.get("sounding") or "")
        pill = live.get("keyPill") or ""
        attr = live.get("keyAttr") or ""
        assert new_key and ((new_key in pill) or (new_key == attr) or (new_key in attr)), (
            new_key,
            pill,
            attr,
        )
        if int(live.get("highlighted") or 0) < 1:
            page.wait_for_timeout(1200)
            after2 = snap(page, "AFTER_KEY_HL")
            live = after2["live"]
            report["after_hl"] = after2
        assert int(live.get("highlighted") or 0) >= 1, live
        report["after"] = after
        report["ok"] = True

        try:
            click_playbar(page, "off")
        except Exception:
            pass
        set_cycle_mode(page, False)
        b.close()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "leadsheet_visual_restore_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("WROTE report ok=", report["ok"])
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
