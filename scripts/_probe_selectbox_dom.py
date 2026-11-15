"""How is a Streamlit selectbox actually driven in this build?

The Groove / feel options would not enumerate and typing did not change the value, so this reports
the control's internals: whether the input is read-only, what happens to the DOM when it is clicked,
and where the option elements live. The same obstacle stopped a Mission walk in Issue 78C, so the
answer is worth recording rather than worked around twice.
"""
import json
import sys
import time
from pathlib import Path

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8633").rstrip("/")
WT = sys.argv[2] if len(sys.argv) > 2 else "/c/tmp/ai-music-i77c"
sys.argv = [sys.argv[0], URL, "--tag", "sbprobe"]
sys.path.insert(0, str(Path(WT) / "scripts"))
sys.path.insert(0, WT)
import _accept_issue78c_visibility as H          # noqa: E402
from playwright.sync_api import sync_playwright   # noqa: E402

RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

INPUT_JS = """() => {
  for (const b of document.querySelectorAll('[data-testid="stSelectbox"]')) {
    if (!/groove|feel/i.test(b.innerText || '')) continue;
    if (b.offsetParent === null) continue;
    const i = b.querySelector('input');
    (i || b).scrollIntoView({block: 'center'});
    const r = (i || b).getBoundingClientRect();
    return {
      has_input: !!i,
      readonly: i ? i.hasAttribute('readonly') : null,
      disabled: i ? !!i.disabled : null,
      role: i ? i.getAttribute('role') : null,
      aria_expanded: i ? i.getAttribute('aria-expanded') : null,
      aria_controls: i ? i.getAttribute('aria-controls') : null,
      value: i ? i.value : null,
      x: r.x + r.width / 2, y: r.y + r.height / 2,
      container_testids: [...b.querySelectorAll('[data-testid]')]
                           .map(e => e.getAttribute('data-testid')).slice(0, 8)
    };
  }
  return {error: 'no groove selectbox'};
}"""

AFTER_CLICK_JS = """() => {
  const out = {roles: {}, candidates: []};
  for (const el of document.querySelectorAll('[role]')) {
    const r = el.getAttribute('role');
    out.roles[r] = (out.roles[r] || 0) + 1;
  }
  const words = ['blues groove', 'jewish hora', 'klezmer groove', 'pop groove', 'auto'];
  for (const el of document.querySelectorAll('div, li, span')) {
    const t = (el.textContent || '').trim().toLowerCase();
    if (!t || t.length > 30) continue;
    if (!words.includes(t)) continue;
    if (el.children.length > 0) continue;
    const r = el.getBoundingClientRect();
    out.candidates.push({text: el.textContent.trim(), tag: el.tagName,
                         role: el.getAttribute('role'),
                         parent_role: el.parentElement ? el.parentElement.getAttribute('role') : null,
                         parent_testid: el.parentElement ? el.parentElement.getAttribute('data-testid') : null,
                         w: Math.round(r.width), h: Math.round(r.height),
                         x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)});
  }
  out.popovers = [...document.querySelectorAll('[data-baseweb="popover"], [data-baseweb="menu"], ul')]
                   .map(e => ({tag: e.tagName, baseweb: e.getAttribute('data-baseweb'),
                               items: e.querySelectorAll('li').length,
                               text: (e.innerText || '').replace(/\\n+/g, ' | ').slice(0, 120)}))
                   .slice(0, 6);
  return out;
}"""


def idle(page, quiet=3, limit=150.0):
    t0, n = time.time(), 0
    while time.time() - t0 < limit:
        if page.evaluate(RUNNING_JS):
            n = 0
        else:
            n += 1
            if n >= quiet:
                return True
        page.wait_for_timeout(1000)
    return False


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    try:
        ctx = browser.new_context(viewport={"width": 1500, "height": 1100})
        page = ctx.new_page()
        page.set_default_timeout(40000)
        page.goto(URL, wait_until="load")
        idle(page)
        H.boot(page)
        if not H.goto_multitrack(page):
            print("multitrack not reached")
        else:
            idle(page)
            info = page.evaluate(INPUT_JS)
            print("INPUT: " + json.dumps(info, default=str), flush=True)
            if not info.get("error"):
                page.mouse.click(info["x"], info["y"])
                page.wait_for_timeout(1800)
                after = page.evaluate(AFTER_CLICK_JS)
                print("\nAFTER CLICK roles: " + json.dumps(after.get("roles"), default=str), flush=True)
                print("popovers: " + json.dumps(after.get("popovers"), default=str)[:600], flush=True)
                print("option-like candidates:", flush=True)
                for c in after.get("candidates") or []:
                    print("   " + json.dumps(c, default=str), flush=True)
                # Try keyboard navigation and report what the value becomes
                for key in ("ArrowDown", "ArrowDown", "Enter"):
                    page.keyboard.press(key)
                    page.wait_for_timeout(600)
                idle(page)
                page.wait_for_timeout(1500)
                print("\nvalue after ArrowDown x2 + Enter: "
                      + json.dumps(page.evaluate(INPUT_JS).get("value"), default=str), flush=True)
    finally:
        browser.close()
