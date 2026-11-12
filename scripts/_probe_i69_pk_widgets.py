"""Issue 69: which Practice Key widgets exist on the karaoke performance surface?

The Part E run moved "the" Practice Key to D and the retune never fired. The probe
readings ('after': 'DBb') looked like two controls answering at once, so this lists
every selectbox on the page with its Streamlit widget-key class and current value,
before and during a performance.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"

DUMP = r"""() => {
  const out = [];
  document.querySelectorAll('[data-testid="stSelectbox"]').forEach(el => {
    let keyed = el.closest('[class*="st-key-"]');
    let cls = '';
    while (keyed) {
      const m = (keyed.className || '').match(/st-key-[^\s]+/g);
      if (m) { cls = m.join(' ') + (cls ? ' < ' + cls : ''); }
      keyed = keyed.parentElement ? keyed.parentElement.closest('[class*="st-key-"]') : null;
    }
    out.push({
      label: (el.innerText || '').split('\n')[0].slice(0, 60),
      text: (el.innerText || '').replace(/\n/g, ' | ').slice(0, 80),
      keys: cls,
      sidebar: !!el.closest('section[data-testid="stSidebar"]'),
      visible: !!(el.offsetWidth || el.offsetHeight),
    });
  });
  return out;
}"""


def dump(page, when):
    print(f"\n== {when} ==", flush=True)
    try:
        rows = page.evaluate(DUMP)
    except Exception as exc:
        print(f"  dump failed: {exc}", flush=True)
        return
    for r in rows:
        line = ("  side=%d vis=%d keys=%-50s text=%s"
                % (r["sidebar"], r["visible"], r["keys"] or "-", r["text"]))
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(URL, timeout=120_000)
        wait_idle(page, 20_000)
        expand_sidebar(page)
        wait_idle(page, 3_000)
        pick_song(page, [], "Say", "pop")
        wait_idle(page, 6_000)
        dump(page, "Songs page, no performance")

        for label in ("Add to Karaoke Set", "Karaoke", "Start Karaoke Set"):
            for el in page.get_by_text(label, exact=False).all():
                try:
                    if el.is_visible():
                        el.click(timeout=4_000)
                        wait_idle(page, 6_000)
                        break
                except Exception:
                    continue
            dump(page, f"after clicking {label!r}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
