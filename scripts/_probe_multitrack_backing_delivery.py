"""What does the browser actually receive when Multitrack fetches its backing?

Reported from the app:

    Recording is unavailable: the generated backing track could not be loaded.
    asset=backing state=failed attempts=1 bytes=9782 type=text/html; charset=utf-8
    decoded_sec=0 expected_sec=86.33333333333333 error=Unable to decode audio data

9782 bytes of text/html is a web page, not a WAV. So this measures the delivery rather than the
decoder: every response the page and the recorder component receive is recorded - final URL,
status, redirect chain, content type, length and the first bytes - and the component's own
``backing_url`` argument is read out of the iframe so the exact URL it asked for is known.

Nothing is mocked. The real app renders, prepares a real backing, and the real component fetches
it; the point is to see the real response.

Usage:  python -X utf8 scripts/_probe_multitrack_backing_delivery.py http://127.0.0.1:8670
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8670"

import _accept_issue78c_visibility as H  # noqa: E402

OUT = SCRIPTS / "evidence-multitrack-delivery"
OUT.mkdir(parents=True, exist_ok=True)
RESPONSES: list[dict] = []
NOTES: list[str] = []

#: The component's own arguments, read from inside its iframe. Streamlit puts the latest render
#: arguments on the frame, so this is the URL the component really has - not one inferred.
COMPONENT_ARGS = """
() => {
  const out = [];
  for (const f of document.querySelectorAll('iframe')) {
    let doc = null;
    try { doc = f.contentDocument; } catch (e) { continue; }
    if (!doc) continue;
    const w = f.contentWindow;
    let args = null;
    try {
      args = (w && (w.__RECORDER_ARGS__ || (w.Streamlit && w.Streamlit.args))) || null;
    } catch (e) {}
    const hasRec = !!(doc.getElementById('rec') || doc.querySelector('[data-testid=recorder]')
                      || (doc.body && /record/i.test(doc.body.innerText || '')));
    if (!args && !hasRec) continue;
    out.push({
      src: String(f.getAttribute('src') || '').slice(0, 120),
      frame_url: String((w && w.location && w.location.href) || '').slice(0, 160),
      backing_url: args ? String(args.backing_url || '') : '(args unreadable)',
      backing_fp: args ? String(args.backing_fp || '') : '',
      backing_duration_sec: args ? args.backing_duration_sec : null,
      monitors: args && args.monitors ? args.monitors.length : null,
    });
  }
  return out;
}
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def note(msg: str) -> None:
    NOTES.append(msg)
    log(f"  OBS  {msg}")


def watch(page: Page) -> None:
    def on_response(res):
        url = res.url
        if "/media/" not in url and "/component/" not in url and not url.endswith(".wav"):
            return
        row = {"url": url[-110:], "status": res.status, "ok": res.ok}
        try:
            row["content_type"] = res.headers.get("content-type", "")
            row["length"] = res.headers.get("content-length", "")
        except Exception:
            pass
        try:
            req = res.request
            row["method"] = req.method
            chain = []
            r = req.redirected_from
            while r is not None and len(chain) < 6:
                chain.append(r.url[-70:])
                r = r.redirected_from
            if chain:
                row["redirected_from"] = chain
        except Exception:
            pass
        if "/media/" in url or url.endswith(".wav"):
            try:
                body = res.body()
                row["bytes"] = len(body)
                row["first_bytes"] = body[:16].hex()
                row["looks_like"] = (
                    "RIFF/WAV" if body[:4] == b"RIFF"
                    else "HTML" if body[:15].lower().lstrip().startswith(b"<!doctype")
                    or body[:6].lower().startswith(b"<html") else "other")
            except Exception as exc:
                row["body_error"] = str(exc)[:80]
        RESPONSES.append(row)
    page.on("response", on_response)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required",
                  "--use-fake-device-for-media-stream",
                  "--use-fake-ui-for-media-stream"],
        )
        context = browser.new_context(viewport={"width": 1400, "height": 950},
                                      permissions=["microphone"])
        page = context.new_page()
        page.set_default_timeout(45000)
        watch(page)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            H.settle(page, 6)
            if not H.boot(page):
                note("the app did not boot")
                return 2
            if not H.goto_multitrack(page):
                note("could not reach the Multitrack page")
                return 2
            log("on the Multitrack page")
            H.settle(page, 4)

            text = H.low(H.main_body(page))
            log(f"  page offers 'prepare backing': {'prepare backing' in text}")

            # Prepare a real backing, the way a musician does.
            clicked = H.click_page_button(page, "Prepare backing")
            log(f"  Prepare backing -> {clicked!r}")
            H.settle(page, 10)
            for _ in range(40):
                if "could not be loaded" in H.low(H.main_body(page)):
                    break
                if "backing ready" in H.low(H.main_body(page)):
                    break
                H.settle(page, 3)

            body_now = H.low(H.main_body(page))
            log(f"  'backing ready' on the page: {'backing ready' in body_now}")
            log(f"  'could not be loaded' on the page: {'could not be loaded' in body_now}")

            args = []
            try:
                args = page.evaluate(COMPONENT_ARGS) or []
            except Exception as exc:
                note(f"could not read the component arguments: {exc}")
            log("\ncomponent arguments:")
            for row in args:
                log("  " + json.dumps(row))

            # Ask for the same URL from the page's own context, so the response is attributable.
            checks = []
            for row in args:
                url = str(row.get("backing_url") or "")
                if not url or url.startswith("data:"):
                    continue
                try:
                    resp = page.request.get(url if url.startswith("http") else URL.rstrip("/") + url)
                    blob = resp.body()
                    checks.append({
                        "asked_for": url[-90:],
                        "final_url": resp.url[-90:],
                        "status": resp.status,
                        "content_type": resp.headers.get("content-type", ""),
                        "bytes": len(blob),
                        "first_bytes": blob[:16].hex(),
                        "looks_like": ("RIFF/WAV" if blob[:4] == b"RIFF" else "HTML"
                                       if blob[:15].lower().lstrip().startswith(b"<!doctype")
                                       else "other"),
                        "head": blob[:120].decode("utf-8", "replace") if blob[:4] != b"RIFF" else "",
                    })
                except Exception as exc:
                    checks.append({"asked_for": url[-90:], "error": str(exc)[:120]})
            log("\ndirect fetch of the component's own backing_url:")
            for c in checks:
                log("  " + json.dumps(c)[:400])

            log("\nevery media / component response seen:")
            for r in RESPONSES[-25:]:
                log("  " + json.dumps(r)[:260])

            (OUT / "delivery.json").write_text(
                json.dumps({"component_args": args, "direct_checks": checks,
                            "responses": RESPONSES, "notes": NOTES}, indent=2),
                encoding="utf-8")
            log(f"\nwrote {OUT / 'delivery.json'}")
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
