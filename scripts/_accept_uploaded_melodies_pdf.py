"""My Uploaded Melodies acceptance: a real 26.5 MB scan must upload, PREVIEW, save and reopen.

"Do not treat successful upload alone as sufficient" - so this measures the three things that come
after it, and watches what they cost:

  * the limit is stated on the page BEFORE a file is chosen;
  * a ~26.5 MB PDF (the size that was refused) is accepted and appears in the song's list;
  * it is rendered - a page image actually appears, which is where a big scan would fail or hang;
  * it survives navigating away and coming back, and a page reload;
  * an oversized file is refused with BOTH numbers, and leaves the existing documents alone;
  * the server's memory is sampled around the upload, because a byte limit that triples has to be
    paid for somewhere.

The PDFs are generated here: real page content, no personal material.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import _accept_issue78c_visibility as H  # noqa: E402

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8641").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "after"
OUT = SCRIPTS / f"evidence-melodies-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIX = OUT / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


# --------------------------------------------------------------------------------------------
# fixtures: generated PDFs with real page content, padded to a chosen size
# --------------------------------------------------------------------------------------------
def make_pdf(path: Path, target_bytes: int, *, pages: int = 2, label: str = "Scanned music") -> Path:
    """A structurally valid, renderable PDF of roughly ``target_bytes``.

    Written by hand rather than with a library so the test has no new dependency: each page is a
    real content stream, and the file is padded with a comment block to reach the wanted size,
    which is what a photographed page looks like to the size check.
    """
    if path.exists() and abs(path.stat().st_size - target_bytes) < 64 * 1024:
        return path
    objs: list[bytes] = []
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    for i in range(pages):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {3 + pages * 2} 0 R >> >> "
            f"/Contents {4 + i * 2} 0 R >>".encode()
        )
        text = f"BT /F1 24 Tf 72 700 Td ({label} - page {i + 1}) Tj ET"
        objs.append(f"<< /Length {len(text)} >>\nstream\n{text}\nendstream".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    body = b"%PDF-1.7\n"
    offsets = []
    for n, obj in enumerate(objs, start=1):
        offsets.append(len(body))
        body += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    pad = max(0, target_bytes - len(body) - 400)
    if pad:
        body += b"% " + (b"0" * pad) + b"\n"
    xref_at = len(body)
    body += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode()
    body += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n"
             "%%EOF\n").encode()
    path.write_bytes(body)
    return path


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

PANEL_JS = """() => {
  for (const d of document.querySelectorAll('details')) {
    const sum = d.querySelector('summary');
    const t = ((sum && sum.innerText) || '').toLowerCase();
    if (!(t.includes('melod') && t.includes('upload'))) continue;   // NOT "Generated Practice Melody"
    return {open: !!d.open, text: (d.innerText || '').slice(0, 1800),
            images: d.querySelectorAll('img').length,
            buttons: [...d.querySelectorAll('button')].map(b => (b.innerText || '').trim())
                       .filter(Boolean).slice(0, 14)};
  }
  return {missing: true};
}"""

OPEN_PANEL_JS = """() => {
  for (const d of document.querySelectorAll('details')) {
    const sum = d.querySelector('summary');
    const t = ((sum && sum.innerText) || '').toLowerCase();
    if (!t.includes('melod') || !t.includes('upload')) continue;
    if (!d.open) { sum.scrollIntoView({block: 'center'});
                   const r = sum.getBoundingClientRect();
                   return {x: r.x + Math.min(40, r.width / 2), y: r.y + r.height / 2}; }
    return {already: true};
  }
  return {error: 'no My Uploaded Melodies panel'};
}"""

# The panel lives inside the Practice page's "Chart & Melody" tool, not on the page itself: until
# that tool is opened the Practice page has no expanders at all, which is why an earlier run failed
# from its first gate. The button also sits far below the fold (measured y=2349 in an 1100-tall
# viewport), so it must be scrolled to before it can be clicked.
OPEN_CHART_TOOL_JS = """() => {
  for (const el of document.querySelectorAll('button')) {
    const t = (el.innerText || '').trim();
    if (!/chart\\s*(&|and|\\/)\\s*(melody|tab)/i.test(t)) continue;
    if (el.offsetParent === null) continue;
    el.scrollIntoView({block: 'center'});
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
  }
  return {error: 'no Chart & Melody tool button'};
}"""


def idle(page, quiet: int = 3, limit: float = 240.0) -> bool:
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


def panel(page) -> dict:
    return page.evaluate(PANEL_JS)


def reach_panel(page) -> dict:
    """Practice page -> the Chart & Melody tool -> the My Uploaded Melodies expander, open."""
    report: dict = {}
    for attempt in range(3):
        report["practice_clicked"] = H.click_practice_page(page)
        idle(page)
        body = str(page.evaluate("() => document.body.innerText")).lower()
        report["on_practice"] = "section focus" in body
        if report["on_practice"]:
            break
        page.wait_for_timeout(1500)
    report["panel_in_page"] = False
    for attempt in range(4):
        body_now = str(page.evaluate("() => document.body.innerText")).lower()
        if "uploaded melod" in body_now:
            report["panel_in_page"] = True
            break
        tool = page.evaluate(OPEN_CHART_TOOL_JS)
        report["tool"] = tool
        if tool.get("error"):
            break
        page.mouse.click(tool["x"], tool["y"])
        idle(page)
        page.wait_for_timeout(2500)
        idle(page)
    report["tool_attempts"] = attempt + 1
    # A collapsed <details> has empty innerText, so nothing inside it can be read until it is open.
    for _ in range(3):
        open_panel(page)
        page.wait_for_timeout(1200)
        if (panel(page).get("open")):
            break
    report["panel_open"] = bool(panel(page).get("open"))
    return report


def open_panel(page) -> None:
    hit = page.evaluate(OPEN_PANEL_JS)
    if hit.get("x") is not None:
        page.mouse.click(hit["x"], hit["y"])
        idle(page)


def server_rss_mb() -> float:
    """The app server's resident memory, so a bigger limit is not paid for invisibly."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*streamlit run*' } | "
             "Measure-Object -Property WorkingSetSize -Sum).Sum"],
            capture_output=True, text=True, timeout=30)
        return round(float((out.stdout or "0").strip() or 0) / (1024 * 1024), 1)
    except Exception:
        return -1.0


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


def upload_into_panel(page, path: str) -> str:
    try:
        page.locator('details:has(summary:has-text("Uploaded Melod")) input[type="file"]').first \
            .set_input_files(path, timeout=60000)
    except Exception as exc:
        return "could not attach: " + str(exc)[:110]
    idle(page)
    page.wait_for_timeout(2000)
    idle(page)
    return "attached"


def press_in_panel(page, needle: str) -> str:
    box = page.evaluate(
        """(needle) => {
            const want = needle.toLowerCase();
            for (const d of document.querySelectorAll('details')) {
                const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
                if (!(t.includes('melod') && t.includes('upload'))) continue;
                for (const b of d.querySelectorAll('button')) {
                    const bt = (b.innerText || '').toLowerCase();
                    if (!bt.includes(want) || b.disabled || b.offsetParent === null) continue;
                    b.scrollIntoView({block: 'center'});
                    const r = b.getBoundingClientRect();
                    if (r.width < 2) continue;
                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                }
                return {error: 'no enabled button matching ' + needle};
            }
            return {error: 'no panel'};
        }""", needle)
    if box.get("error"):
        return str(box["error"])
    page.mouse.click(box["x"], box["y"])
    idle(page)
    page.wait_for_timeout(2500)
    idle(page)
    return "clicked"


def main() -> int:
    big = make_pdf(FIX / "scanned_music_26mb.pdf", 27090 * 1024, pages=2,
                   label="I will Remember April")
    oversize = make_pdf(FIX / "oversize_56mb.pdf", 56 * 1024 * 1024, pages=1, label="Too big")
    small = make_pdf(FIX / "small_sheet.pdf", 120 * 1024, pages=1, label="Small sheet")
    MEASURED["fixture_sizes_mb"] = {
        p.name: round(p.stat().st_size / (1024 * 1024), 2) for p in (big, oversize, small)}
    log("fixtures: " + json.dumps(MEASURED["fixture_sizes_mb"], default=str))

    rss_start = server_rss_mb()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": 1500, "height": 1100})
            page = ctx.new_page()
            page.set_default_timeout(90000)
            page.goto(URL, wait_until="load")
            idle(page)
            H.boot(page)
            route = reach_panel(page)
            MEASURED["route"] = route
            mark("the Practice page opens", bool(route.get("on_practice")), route.get("tool"))
            mark("the Chart & Melody tool opens", bool(route.get("panel_in_page")),
                 route.get("tool"))
            info = panel(page)
            MEASURED["panel_initial"] = {k: v for k, v in info.items() if k != "text"}
            mark("the My Uploaded Melodies panel is present", not info.get("missing"), info.get("open"))
            text = str(info.get("text") or "")
            mark("the limit is stated before a file is chosen",
                 "maximum 50 MB per file" in text,
                 [ln for ln in text.splitlines() if "maximum" in ln.lower()][:2])
            mark("the save control carries the floppy disk",
                 any("Save to this song" in b and "\U0001f4be" in b
                     for b in (info.get("buttons") or [])),
                 info.get("buttons"))
            shot(page, "panel-before-upload")

            # --- the file that was refused ---------------------------------------------------
            log("\n-- upload the 26.5 MB scan")
            MEASURED["attach_big"] = upload_into_panel(page, str(big))
            MEASURED["save_click"] = press_in_panel(page, "save to this song")
            idle(page)
            page.wait_for_timeout(3000)
            idle(page)
            after = panel(page)
            MEASURED["panel_after_upload"] = {k: v for k, v in after.items() if k != "text"}
            atext = str(after.get("text") or "")
            MEASURED["notice_after_upload"] = [
                ln for ln in atext.splitlines()
                if any(w in ln.lower() for w in ("saved", "too large", "could not",
                                                 "device only", "or smaller"))][:4]
            rss_after_upload = server_rss_mb()
            MEASURED["rss_mb"] = {"start": rss_start, "after_upload": rss_after_upload}
            mark("the 26.5 MB scan is accepted",
                 "saved" in atext.lower() and "too large" not in atext.lower(),
                 MEASURED["notice_after_upload"])
            shot(page, "after-upload")

            # --- it must RENDER, not merely be stored ----------------------------------------
            log("\n-- it must actually render")
            open_panel(page)
            rendered = after.get("images") or 0
            if not rendered:
                press_in_panel(page, "open")
                page.wait_for_timeout(3000)
                rendered = (panel(page).get("images") or 0)
            MEASURED["rendered_images"] = rendered
            mark("a page of the scan is rendered on screen", rendered > 0, f"{rendered} image(s)")
            shot(page, "rendered")

            # --- navigate away and back ------------------------------------------------------
            log("\n-- leave and come back")
            H.goto_multitrack(page)
            idle(page)
            reach_panel(page)
            back = panel(page)
            btext = str(back.get("text") or "")
            MEASURED["after_navigation"] = {"images": back.get("images")}
            mark("the document is still listed after navigating away and back",
                 "remember april" in btext.lower() or (back.get("images") or 0) > 0,
                 btext[:120].replace("\n", " "))

            # --- reload ----------------------------------------------------------------------
            log("\n-- reload the app")
            page.reload(wait_until="load")
            idle(page)
            H.boot(page)
            reach_panel(page)
            reloaded = panel(page)
            rtext = str(reloaded.get("text") or "")
            MEASURED["after_reload"] = {"images": reloaded.get("images")}
            mark("the document reopens after a reload",
                 "remember april" in rtext.lower() or (reloaded.get("images") or 0) > 0,
                 rtext[:120].replace("\n", " "))
            shot(page, "after-reload")

            # --- an oversized file, refused with both numbers --------------------------------
            log("\n-- an oversized file")
            MEASURED["attach_oversize"] = upload_into_panel(page, str(oversize))
            # Read it NOW: the browser refuses the file as soon as it is chosen, and the form is
            # clear_on_submit, so pressing Save wipes the rejected entry before it can be read.
            # This is also the moment the musician sees it.
            over_panel = panel(page)
            otext = str(over_panel.get("text") or "")
            MEASURED["oversize_panel_text"] = otext[:600]
            press_in_panel(page, "save to this song")
            idle(page)
            page.wait_for_timeout(2000)
            idle(page)
            MEASURED["oversize_notice"] = [
                ln for ln in otext.splitlines()
                if "MB" in ln and any(w in ln.lower()
                                      for w in ("maximum", "smaller", " is "))][:4]
            # Both numbers must reach the musician; WHICH layer says so changed once the limit was
            # passed to the uploader. The browser now refuses the file before it travels and shows
            # "oversize_56mb.pdf / 56.0MB / Error: File must be 50.0MB or smaller." The app's own
            # sentence ("... is 56.0 MB. The maximum allowed document size is 50 MB.") remains for
            # bytes that do arrive, and is covered by unit tests.
            browser_refusal = "56.0MB" in otext and "50.0MB or smaller" in otext
            app_refusal = "56.0 MB" in otext and "50 MB" in otext
            mark("an oversized file is refused with its size AND the limit",
                 browser_refusal or app_refusal,
                 ("browser-side" if browser_refusal else "app-side")
                 + ": " + str(MEASURED["oversize_notice"]))
            after_attempt = panel(page)
            atext2 = str(after_attempt.get("text") or "")
            mark("the refusal did not remove the document already saved",
                 "scanned_music_26mb" in atext2.lower() or (after_attempt.get("images") or 0) > 0,
                 atext2[:120].replace(chr(10), " "))
            MEASURED["rss_mb"]["after_oversize"] = server_rss_mb()
            shot(page, "oversize-refused")
            ctx.close()

            # --- widths -----------------------------------------------------------------------
            log("\n-- widths")
            for width in (1400, 390, 360):
                wctx = browser.new_context(viewport={"width": width, "height": 900})
                wpage = wctx.new_page()
                wpage.set_default_timeout(60000)
                try:
                    wpage.goto(URL, wait_until="load")
                    idle(wpage)
                    H.boot(wpage)
                    wroute = reach_panel(wpage)
                    if not wroute.get("panel_in_page"):
                        mark(f"[{width}px] the Chart & Melody tool opens", False, wroute.get("tool"))
                        continue
                    p = panel(wpage)
                    over = wpage.evaluate(
                        """() => { const de = document.documentElement;
                                   return {sideways: de.scrollWidth > de.clientWidth + 2}; }""")
                    MEASURED[f"width_{width}"] = {"images": p.get("images"), **over}
                    mark(f"[{width}px] the panel shows the limit",
                         "maximum 50 MB per file" in str(p.get("text") or ""))
                    mark(f"[{width}px] the page does not scroll sideways", not over.get("sideways"))
                    shot(wpage, f"width-{width}")
                finally:
                    wctx.close()
        finally:
            browser.close()

    MEASURED["rss_mb"]["end"] = server_rss_mb()
    (OUT / "measured.json").write_text(json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    log("\nserver memory (MB): " + json.dumps(MEASURED.get("rss_mb"), default=str))
    failed = [g for g, ok in GATES.items() if not ok]
    log("\n" + "=" * 78)
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates pass")
    for g in failed:
        log("  FAILED: " + g)
    log("evidence: " + str(OUT))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
