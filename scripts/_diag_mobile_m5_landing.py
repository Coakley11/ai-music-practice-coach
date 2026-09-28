# -*- coding: utf-8 -*-
"""Diagnose M5 page landing + real main-scroll metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import expand_sidebar, click_nav  # noqa: E402
from _walk_pass8_nav_first_click import expand_pages, wait  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8585"
OUT = SCRIPTS / "evidence-mobile-m5"
OUT.mkdir(parents=True, exist_ok=True)


def measure(page) -> dict:
    return page.evaluate(
        """() => {
          const main = document.querySelector('section[data-testid="stMain"]');
          const block = document.querySelector('.block-container')
            || document.querySelector('[data-testid="stAppViewContainer"]');
          const mainEl = main || document.body;
          const scrollRoot = main || document.documentElement;
          const text = (main ? main.innerText : document.body.innerText || '')
            .replace(/\\s+/g, ' ');
          const classes = [...document.querySelectorAll('[class*="st-key-"]')]
            .map(e => [...e.classList].find(c => c.includes('st-key-')) || '')
            .filter(Boolean)
            .slice(0, 40);
          const pick = (sels) => {
            for (const s of sels) {
              const el = document.querySelector(s);
              if (el) return el;
            }
            return null;
          };
          const box = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {
              h: Math.round(r.height),
              y: Math.round(r.top),
              w: Math.round(r.width),
            };
          };
          return {
            bodyClass: document.body.className,
            dataPage: document.body.getAttribute('data-studio-page'),
            mainScrollH: scrollRoot.scrollHeight,
            mainClientH: scrollRoot.clientHeight,
            blockH: block ? Math.round(block.getBoundingClientRect().height) : null,
            blockScrollH: block ? block.scrollHeight : null,
            docScrollH: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
            hOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth)
              > window.innerWidth + 4,
            practicePanel: box(pick([
              '[class*="st-key-practice_control_panel"]',
              '.ui-practice-control-head',
              '.ui-practice-top',
            ])),
            backingDeck: box(pick([
              '[class*="st-key-backing_playback_setup"]',
              '.ui-backing-studio-deck-head',
              '[class*="st-key-backing_quick_playback"]',
              '.ui-backing-setup-group',
            ])),
            creativeStudio: box(pick([
              '[class*="st-key-creative_studio_panel"]',
              '.ui-creative-studio-head',
              '.ui-creative-studio-shell',
            ])),
            scriptHeader: box(pick([
              '.ui-studio-script-header',
              '[class*="ui-studio-script-header"]',
              '.ui-page-head',
            ])),
            keys: classes,
            snippet: text.slice(0, 500),
          };
        }"""
    )


def main() -> int:
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 6000)
        expand_sidebar(page)
        expand_pages(page)
        wait(page, 1500)
        for label in ("Practice", "Backing", "Creative"):
            ok = click_nav(page, label)
            wait(page, 5500)
            info = measure(page)
            info["click_ok"] = ok
            results[label] = info
            page.screenshot(path=str(OUT / f"diag390_{label.lower()}.png"), full_page=False)
            print(label, json.dumps({k: info[k] for k in info if k != "keys"}, indent=2))
            print("keys", info.get("keys"))
        browser.close()
    (OUT / "m5_diag_landing.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
