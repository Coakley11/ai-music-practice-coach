"""What does the musician see when a 56 MB PDF is refused?

With max_upload_size=50 the browser refuses the file before any app code runs, so the app's own
message ("... is 56.0 MB. The maximum allowed document size is 50 MB.") never fires. That is better
behaviour - the bytes never travel - but it changes WHO writes the message, so the requirement
"show both the actual file size and the permitted size" has to be checked against what Streamlit
itself says.
"""
import json
import sys
import time
from pathlib import Path

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8646").rstrip("/")
WT = sys.argv[2] if len(sys.argv) > 2 else "/c/tmp/ai-music-pdf"
sys.argv = [sys.argv[0], URL, "--tag", "oversize"]
sys.path.insert(0, str(Path(WT) / "scripts"))
sys.path.insert(0, WT)
import _accept_issue78c_visibility as H          # noqa: E402
from playwright.sync_api import sync_playwright   # noqa: E402

FIX = Path(WT) / "scripts" / "evidence-melodies-final" / "fixtures"

RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

PANEL_TEXT_JS = """() => {
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('melod') && t.includes('upload'))) continue;
    return (d.innerText || '');
  }
  return '(panel not found)';
}"""

CHART_TOOL_JS = """() => {
  for (const el of document.querySelectorAll('button')) {
    const t = (el.innerText || '').trim();
    if (!/chart\\s*(&|and|\\/)\\s*(melody|tab)/i.test(t)) continue;
    if (el.offsetParent === null) continue;
    el.scrollIntoView({block: 'center'});
    const r = el.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
  }
  return {error: 'no tool'};
}"""

OPEN_PANEL_JS = """() => {
  for (const d of document.querySelectorAll('details')) {
    const sum = d.querySelector('summary');
    const t = ((sum && sum.innerText) || '').toLowerCase();
    if (!(t.includes('melod') && t.includes('upload'))) continue;
    if (!d.open) { sum.scrollIntoView({block: 'center'});
                   const r = sum.getBoundingClientRect();
                   return {x: r.x + 20, y: r.y + r.height / 2}; }
    return {already: true};
  }
  return {error: 'no panel'};
}"""


def idle(page, quiet=3, limit=220.0):
    t0, n = time.time(), 0
    while time.time() - t0 < limit:
        if page.evaluate(RUNNING_JS):
            n = 0
        else:
            n += 1
            if n >= quiet:
                return True
        page.wait_for_timeout(1200)
    return False


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    try:
        page = browser.new_context(viewport={"width": 1500, "height": 1100}).new_page()
        page.set_default_timeout(90000)
        page.goto(URL, wait_until="load")
        idle(page)
        H.boot(page)
        H.click_practice_page(page)
        idle(page)
        for _ in range(4):
            if "uploaded melod" in str(page.evaluate("() => document.body.innerText")).lower():
                break
            hit = page.evaluate(CHART_TOOL_JS)
            if hit.get("error"):
                break
            page.mouse.click(hit["x"], hit["y"])
            idle(page)
            page.wait_for_timeout(2500)
            idle(page)
        hit = page.evaluate(OPEN_PANEL_JS)
        if hit.get("x") is not None:
            page.mouse.click(hit["x"], hit["y"])
            idle(page)

        big = FIX / "oversize_56mb.pdf"
        print("attaching " + big.name + " ("
              + str(round(big.stat().st_size / (1024 * 1024), 1)) + " MB)", flush=True)
        page.locator('details:has(summary:has-text("Uploaded Melod")) input[type="file"]').first \
            .set_input_files(str(big), timeout=90000)
        page.wait_for_timeout(4000)
        idle(page)
        text = str(page.evaluate(PANEL_TEXT_JS))
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        print("\npanel lines mentioning MB or size:", flush=True)
        for ln in lines:
            if "mb" in ln.lower() or "size" in ln.lower() or "large" in ln.lower():
                print("   " + ln, flush=True)
        print("\nwhole panel text (first 700 chars):", flush=True)
        print(json.dumps(text[:700], default=str), flush=True)
    finally:
        browser.close()
