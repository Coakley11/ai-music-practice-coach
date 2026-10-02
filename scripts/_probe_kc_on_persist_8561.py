"""Focused browser probe: clean Backing Off → On must stay On (single click).

Does not spam-retry On. Reopens Advanced during settle only.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]

BASE = os.environ.get("KC_SMOKE_URL", "http://127.0.0.1:8561").rstrip("/")
OUT = ROOT / "scripts" / "evidence-key-cycle" / "probe_kc_on_persist_8561.json"

from playwright.sync_api import sync_playwright

from proof_key_cycle_ux_8510 import open_advanced, cycle_ui
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_guitar_shape_key import pick_song
from walk_practice_loop_backing import goto_studio


def _radio_ui(page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.querySelector('[class*="st-key-backing_key_cycle_enabled_ui"]');
          const opts = root
            ? [...root.querySelectorAll('[data-testid="stRadioOption"]')].map((el, i) => ({
                i,
                text: (el.innerText || '').trim(),
                checked: !!(
                  el.querySelector('input:checked')
                  || el.getAttribute('aria-checked') === 'true'
                ),
              }))
            : [];
          const radios = [...document.querySelectorAll('[data-testid="stRadio"]')].map((el) =>
            (el.innerText || '').replace(/\\s+/g, ' ').trim()
          );
          return {
            opts,
            selected: ((opts.find((o) => o.checked) || {}).text || '').trim(),
            onChecked: !!(opts[1] && opts[1].checked),
            interval: radios.some((t) => /\\bInterval\\b/.test(t)),
            direction: radios.some((t) => /\\bDirection\\b/.test(t)),
            spelling: [...document.querySelectorAll('[data-testid="stExpander"]')].some((el) =>
              /Key Spelling/i.test(el.innerText || '')
            ),
            playbar: !!(
              document.querySelector('[class*="st-key-backing_key_cycle_pause_btn"]')
              || document.querySelector('[class*="st-key-backing_key_cycle_advance_btn"]')
            ),
          };
        }"""
    )


def _practice_key_label(page) -> str:
    return str(
        page.evaluate(
            """() => {
              const body = document.body ? (document.body.innerText || '') : '';
              const m =
                body.match(/Practice Key[^\\n]{0,40}?\\b([A-G](?:#|b|♯|♭)?m?)\\b/i)
                || body.match(/Concert Key[^\\n]{0,40}?\\b([A-G](?:#|b|♯|♭)?m?)\\b/i)
                || body.match(/Song Original Key:\\s*([A-G](?:#|b|♯|♭)?m?)/i);
              return m ? m[1].replace('♯','#').replace('♭','b') : '';
            }"""
        )
        or ""
    )


def _boot_backing(page) -> bool:
    expand_sidebar(page)
    expand_pages_nav(page)
    notes: list[str] = []
    pick_song(page, notes, "Shape of You", "Pop")
    for _ in range(12):
        goto_studio(page, "Backing")
        page.wait_for_timeout(2000)
        body = page.inner_text("body") or ""
        if "Play Backing" in body and "Advanced" in body:
            return True
    return False


def main() -> int:
    report: dict = {"ok": False, "base": BASE, "checks": {}, "traces": {}}
    try:
        with urllib.request.urlopen(BASE + "/_stcore/health", timeout=8) as resp:
            report["server"] = {"http": int(resp.status)}
    except Exception as exc:
        report["server"] = {"reachable": False, "error": str(exc)}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(60_000)
        try:
            page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180_000)
            page.wait_for_timeout(4000)
            report["traces"]["landed"] = _boot_backing(page)

            open_advanced(page)
            page.wait_for_timeout(800)
            before = _radio_ui(page)
            pk_before = _practice_key_label(page)
            report["traces"]["before"] = before
            report["traces"]["pk_before"] = pk_before
            report["checks"]["starts_off"] = bool(
                before.get("opts")
                and (before.get("opts")[0] or {}).get("checked")
                and not before.get("interval")
            )

            clicked = bool(
                page.evaluate(
                    """() => {
                      const root = document.querySelector(
                        '[class*="st-key-backing_key_cycle_enabled_ui"]'
                      );
                      if (!root) return false;
                      const opts = [...root.querySelectorAll('[data-testid="stRadioOption"]')];
                      if (!opts[1]) return false;
                      opts[1].click();
                      return true;
                    }"""
                )
            )
            report["traces"]["clicked_on"] = clicked
            report["checks"]["clicked"] = clicked

            settled = None
            for _ in range(10):
                page.wait_for_timeout(1000)
                open_advanced(page)
                page.wait_for_timeout(500)
                settled = _radio_ui(page)
                if settled.get("onChecked") and settled.get("interval") and settled.get("playbar"):
                    break
            report["traces"]["settled"] = settled
            ui = cycle_ui(page) or {}
            report["traces"]["cycle_ui"] = {
                k: ui.get(k) for k in ("playbar", "sounding", "saved", "pause")
            }
            pk_after = _practice_key_label(page)
            report["traces"]["pk_after"] = pk_after

            report["checks"]["stays_on_ui"] = bool(
                settled and (settled.get("onChecked") or settled.get("interval"))
            )
            report["checks"]["subcontrols_appear"] = bool(
                settled
                and settled.get("interval")
                and settled.get("direction")
                and settled.get("spelling")
            )
            report["checks"]["playbar_mounted"] = bool(
                (settled and settled.get("playbar")) or ui.get("playbar")
            )
            report["checks"]["practice_key_unchanged"] = bool(
                pk_before and pk_after and pk_before == pk_after
            ) or (not pk_before)

            report["ok"] = all(report["checks"].values())
        except Exception as exc:
            report["error"] = repr(exc)
            report["ok"] = False
        finally:
            browser.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
