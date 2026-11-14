"""Issue 78 helper: dump the real DOM shape of the Count-in select and the Align slider.

Two readers in probe 3 reported 'not-found' / the label text instead of the value, which
made one leg bail after it had already changed the control. Rather than guess at the
markup a third time, this prints what is actually there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _probe_i78_recording_clock import (  # noqa: E402
    click_text_button,
    expand_layer,
    make_wav,
    upload_into_slot,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8590"
OUT = SCRIPTS / "evidence-issue78"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def settle(page: Page, s: float = 2.5) -> None:
    wait_idle(page, int(s * 1000))


def main() -> int:
    guitar = make_wav("gdom.wav", freq=196.0, seconds=6.0, click_at=0.0)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(25000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            waited = 0
            while waited < 120:
                b = page.inner_text("body") or ""
                if len(b.strip()) > 400 and "PAGES" in b.upper():
                    break
                settle(page, 3)
                waited += 3
            expand_sidebar(page)
            try:
                pick_song(page, NOTES, "Let It Be", "Rock")
                settle(page, 4)
            except Exception as exc:
                log(f"pick_song raised {exc}")
            click_nav(page, "Multitrack")
            settle(page, 6)
            log(f"on multitrack: {'multitrack session workspace' in (page.inner_text('body') or '').lower()}")

            info = page.evaluate(
                """() => {
                  const out = {selectboxes: [], sliders: [], testids: {}};
                  document.querySelectorAll('[data-testid]').forEach((e) => {
                    const t = e.getAttribute('data-testid');
                    out.testids[t] = (out.testids[t] || 0) + 1;
                  });
                  [...document.querySelectorAll('[data-testid="stSelectbox"]')]
                    .forEach((b, i) => {
                      const sel = b.querySelector('[data-baseweb="select"]');
                      out.selectboxes.push({
                        i: i,
                        innerText: (b.innerText || '').slice(0, 80),
                        cls: (b.className || '').slice(0, 90),
                        parentCls: ((b.parentElement && b.parentElement.className) || '').slice(0, 90),
                        selText: sel ? (sel.innerText || '').slice(0, 60) : null,
                        inputVal: (() => { const x = b.querySelector('input');
                                           return x ? x.value : null; })(),
                        singleValue: (() => {
                          const x = b.querySelector('[data-baseweb="select"] div');
                          return x ? (x.innerText || '').slice(0, 40) : null; })(),
                      });
                    });
                  return out;
                }"""
            )
            log("== testid census (audio/slider/select related) ==")
            for k, v in sorted(info["testids"].items()):
                if any(w in k.lower() for w in
                       ("slider", "select", "audio", "expander", "checkbox", "widget")):
                    log(f"   {k}: {v}")
            log("\n== selectboxes ==")
            for s in info["selectboxes"]:
                log(f"   [{s['i']}] innerText={s['innerText']!r}")
                log(f"        selText={s['selText']!r} input={s['inputVal']!r} "
                    f"single={s['singleValue']!r}")
                log(f"        cls={s['cls']!r}")

            expand_layer(page, "guitar")
            settle(page, 2)
            upload_into_slot(page, "guitar", Path(guitar))
            settle(page, 6)
            expand_layer(page, "guitar")
            settle(page, 3)
            sl = page.evaluate(
                """() => {
                  const all = [...document.querySelectorAll('details')];
                  const el = all.find((d) => {
                    const sum = d.querySelector('summary');
                    const t = ((sum && sum.innerText) || '').toLowerCase();
                    return t.includes('layer controls') && t.includes('guitar');
                  });
                  if (!el) return {err: 'no-layer'};
                  const out = {found: true, sliders: [], roleSliders: 0, testids: {}};
                  el.querySelectorAll('[data-testid]').forEach((e) => {
                    const t = e.getAttribute('data-testid');
                    out.testids[t] = (out.testids[t] || 0) + 1;
                  });
                  out.roleSliders = el.querySelectorAll('[role="slider"]').length;
                  [...el.querySelectorAll('[role="slider"]')].forEach((th, i) => {
                    let lbl = '';
                    for (let n = th; n && n !== el; n = n.parentElement) {
                      const t = (n.innerText || '');
                      if (t && t.length < 160) { lbl = t; }
                    }
                    out.sliders.push({i: i,
                      now: th.getAttribute('aria-valuenow'),
                      min: th.getAttribute('aria-valuemin'),
                      max: th.getAttribute('aria-valuemax'),
                      label: lbl.replace(/\\n/g, ' | ').slice(0, 90)});
                  });
                  return out;
                }"""
            )
            log("\n== guitar layer sliders ==")
            log(json.dumps(sl, indent=2)[:2500])
        finally:
            (OUT / "dom-log.txt").write_text("\n".join(NOTES), encoding="utf-8")
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
