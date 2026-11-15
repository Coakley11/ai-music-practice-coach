"""What is actually on the page: instrument, buttons, karaoke keys. A harness diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8599"

from _accept_issue69_karaoke_transposition import settle, wait_for_app  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []

KEYS_JS = """
() => {
  const out = [];
  for (const el of document.querySelectorAll('[class*="st-key-"]')) {
    for (const c of el.className.split(/\\s+/)) {
      if (c.startsWith('st-key-') && /karaoke|add/i.test(c)) out.push(c);
    }
  }
  return [...new Set(out)];
}
"""

BTN_JS = """
() => [...document.querySelectorAll('button')]
  .filter(b => b.offsetParent !== null)
  .map(b => (b.innerText || '').trim().replace(/\\s+/g, ' '))
  .filter(Boolean)
"""


def report(page, label: str) -> None:
    body = page.inner_text("body") or ""
    (OUT / f"diag-{label}.txt").write_text(body[:40000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"diag-{label}.png"), full_page=True)
    inst = page.evaluate(
        """() => {
          const el = [...document.querySelectorAll('[role="combobox"],input[aria-label]')]
            .find(e => /instrument/i.test(e.getAttribute('aria-label') || ''));
          return el ? String(el.value || '') : '(no instrument control)';
        }"""
    )
    keys = page.evaluate(KEYS_JS)
    btns = page.evaluate(BTN_JS)
    print(f"\n==== {label} ====")
    print(f"  instrument: {inst!r}")
    print(f"  karaoke/add widget keys: {keys}")
    print(f"  buttons ({len(btns)}):")
    for b in btns:
        print(f"    - {b[:70].encode('ascii', 'replace').decode('ascii')}")


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        page.goto(URL, wait_until="domcontentloaded")
        settle(page, 5)
        wait_for_app(page)
        report(page, "01-landing")

        pick_song(page, NOTES, "Say", "pop")
        settle(page, 4)
        report(page, "02-say-active")

        expand_sidebar(page)
        set_baseweb_select(page, "Instrument", "Voice")
        settle(page, 6)
        report(page, "03-voice")

        click_nav(page, "Songs")
        settle(page, 4)
        report(page, "04-songs")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
