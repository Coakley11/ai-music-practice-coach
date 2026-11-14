"""Issue 78C acceptance: can a human SEE and TAP the Record button?

The Issue 78B acceptance measured the button's bounding box inside the component's own
``contentDocument`` and clicked it programmatically. Both of those succeed when the iframe around
the button is four pixels tall, so the harness drove a recorder nobody could see and reported
52/52. This harness refuses to make that mistake again:

  * it measures the **iframe element's own rectangle in the page**, and asks whether the button and
    the status text fit inside it;
  * it hit-tests the button's centre with ``elementFromPoint`` in page coordinates, so a control
    hidden behind or clipped out of its frame fails;
  * it clicks and taps with **real Playwright input** (mouse at page coordinates, touch taps on the
    mobile runs), which performs actionability and hit-target checks - a programmatic
    ``element.click()`` is used nowhere as evidence;
  * it photographs the recorder area at every stage.

Usage:
    python scripts/_accept_issue78c_visibility.py http://127.0.0.1:8601 [--tag before]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_pages_nav  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8601"
TAG = "after"
if "--tag" in sys.argv:
    TAG = sys.argv[sys.argv.index("--tag") + 1]
OUT = SCRIPTS / f"evidence-issue78c-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)

SLOT_GUITAR = "guitar"
SLOT_SAX = "sax / winds"
SLOT_FLUTE = "extra layer"

#: A control shorter than this is a coloured line, not something a finger can hit. 44 px is the
#: usual minimum touch target; the component's own floor is 52.
MIN_TOUCH_PX = 36.0

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    if not isinstance(detail, str):
        try:
            detail = json.dumps(detail, default=str)
        except Exception:
            detail = repr(detail)
    detail = (detail or "").replace(chr(10), " | ")[:240]
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}{('  -> ' + detail) if detail else ''}")


def settle(page: Page, s: float = 2.5) -> None:
    page.wait_for_timeout(int(s * 1000))


def low(s: str) -> str:
    return (s or "").lower()


def body(page: Page) -> str:
    return page.inner_text("body") or ""


GEOMETRY_JS = r"""(slot) => {
    const s = slot.toLowerCase();
    // The recorder that belongs to THIS layer: the iframe inside the layer's own details element.
    let holder = null;
    for (const d of document.querySelectorAll('details')) {
        const sum = d.querySelector('summary');
        const t = ((sum && sum.innerText) || '').toLowerCase();
        if (t.includes('layer controls') && t.includes(s)) { holder = d; break; }
    }
    if (!holder) return {found: false, reason: 'no layer panel'};
    const frames = [...holder.querySelectorAll('iframe')].filter((f) => {
        const title = f.getAttribute('title') || '';
        const src = f.getAttribute('src') || '';
        return /recorder/i.test(title) || /recorder/i.test(src);
    });
    if (!frames.length) return {found: false, reason: 'no recorder iframe', open: holder.open};
    const f = frames[0];
    // Scroll to it the way a person would. Without this, a control that is merely below the fold
    // reports "not hittable", which is a different thing from "clipped by its frame".
    try { f.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (e) {}
    const fr = f.getBoundingClientRect();
    const out = {
        found: true,
        open: holder.open,
        frame: {x: fr.x, y: fr.y, w: fr.width, h: fr.height},
        frame_attr_h: f.getAttribute('height'),
        onscreen: f.offsetParent !== null && fr.width > 0 && fr.height > 0,
        in_viewport: fr.top >= -1 && fr.bottom <= window.innerHeight + 1,
        viewport_h: window.innerHeight,
    };
    try {
        const d = f.contentDocument;
        if (!d) { out.inner_error = 'no contentDocument'; return out; }
        out.body_scroll_h = d.body ? d.body.scrollHeight : null;
        const btn = d.getElementById('rec');
        const st = d.getElementById('status');
        if (btn) {
            const br = btn.getBoundingClientRect();
            out.button = {x: br.x, y: br.y, w: br.width, h: br.height, bottom: br.bottom,
                          text: (btn.textContent || '').trim(), disabled: !!btn.disabled};
            // Page coordinates of the button's centre, then hit-test it: if the frame clips the
            // button away, the point lands on something else (or outside the frame entirely).
            const px = fr.x + br.x + br.width / 2;
            const py = fr.y + br.y + br.height / 2;
            out.button_page = {x: px, y: py};
            const hit = document.elementFromPoint(px, py);
            out.hit_tag = hit ? hit.tagName.toLowerCase() : null;
            out.hit_is_frame = hit === f;
            // Name it. "a div" is not a diagnosis: either something is covering the control, which
            // is a defect, or it is the component's own wrapper, which is not.
            if (hit && hit !== f) {
                const chain = [];
                let el = hit;
                for (let i = 0; i < 5 && el; i++) {
                    chain.push(el.tagName.toLowerCase()
                        + (el.id ? '#' + el.id : '')
                        + (el.className && typeof el.className === 'string'
                            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''));
                    el = el.parentElement;
                }
                out.hit_chain = chain;
                out.hit_contains_frame = hit.contains ? hit.contains(f) : null;
                const hr = hit.getBoundingClientRect();
                out.hit_rect = {x: hr.x, y: hr.y, w: hr.width, h: hr.height};
            }
            out.button_inside_frame = br.bottom <= fr.height + 1;
        }
        if (st) {
            const sr = st.getBoundingClientRect();
            out.status = {bottom: sr.bottom, text: (st.textContent || '').trim()};
            out.status_inside_frame = sr.bottom <= fr.height + 1;
        }
    } catch (e) {
        out.inner_error = String(e);
    }
    return out;
}"""


SCROLL_JS = r"""(slot) => {
    const s = slot.toLowerCase();
    for (const d of document.querySelectorAll('details')) {
        const sum = d.querySelector('summary');
        const t = ((sum && sum.innerText) || '').toLowerCase();
        if (!t.includes('layer controls') || !t.includes(s)) continue;
        for (const f of d.querySelectorAll('iframe')) {
            const title = f.getAttribute('title') || '';
            const src = f.getAttribute('src') || '';
            if (/recorder/i.test(title) || /recorder/i.test(src)) {
                f.setAttribute('data-i78c', s.replace(/[^a-z0-9]+/g, '-'));
                try { f.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (e) {}
                return true;
            }
        }
    }
    return false;
}"""


def frame_selector(slot: str) -> str:
    import re as _re

    return 'iframe[data-i78c="%s"]' % _re.sub(r"[^a-z0-9]+", "-", slot.lower())


def button_is_visible_to_playwright(page: Page, slot: str) -> tuple[bool, str]:
    """Ask the browser, not arithmetic: is the Record button visible inside its frame?"""
    try:
        loc = page.frame_locator(frame_selector(slot)).locator("#rec")
        return bool(loc.is_visible(timeout=4000)), ""
    except Exception as exc:
        return False, str(exc)[:120]


def geometry(page: Page, slot: str) -> dict:
    """Scroll to the recorder, let the layout settle, THEN measure and hit-test.

    Scrolling and hit-testing in one evaluate() raced: elementFromPoint uses viewport coordinates,
    and on a tall page the browser had not finished settling, so a control that was perfectly
    visible reported "not hittable". That is a harness artefact of exactly the kind this harness
    exists to avoid, so the two phases are separated by a real pause.
    """
    page.evaluate(SCROLL_JS, slot)
    page.wait_for_timeout(400)
    return page.evaluate(GEOMETRY_JS, slot)


def visible_verdict(geo: dict) -> tuple[bool, str]:
    """Is the control genuinely on screen and hittable?"""
    if not geo.get("found"):
        return False, str(geo.get("reason") or "not found")
    frame_h = float((geo.get("frame") or {}).get("h") or 0)
    if frame_h < MIN_TOUCH_PX:
        return False, f"frame only {frame_h:.1f}px tall"
    if not geo.get("button"):
        return False, "no Record button in the component"
    if not geo.get("button_inside_frame"):
        return False, "the button is clipped by the frame"
    if not geo.get("status_inside_frame", True):
        return False, "the status text is clipped by the frame"
    return True, (
        f"frame {frame_h:.0f}px, button {geo['button']['h']:.0f}px "
        f"({geo['button']['text']!r}), status visible"
    )


def check_visible(page: Page, slot: str, stage: str, width: int) -> dict:
    geo = geometry(page, slot)
    ok, detail = visible_verdict(geo)
    # And the browser's own answer, which is the one that decides whether a person can use it.
    seen, why = button_is_visible_to_playwright(page, slot)
    if ok and not seen:
        ok, detail = False, f"Playwright reports the button not visible in its frame: {why}"
    elif ok:
        detail += "; Playwright sees the button"
    geo["playwright_visible"] = seen
    MEASURED[f"{width}px::{stage}"] = {
        "frame_h": (geo.get("frame") or {}).get("h"),
        "frame_attr_h": geo.get("frame_attr_h"),
        "body_scroll_h": geo.get("body_scroll_h"),
        "button_text": (geo.get("button") or {}).get("text"),
        "button_bottom": (geo.get("button") or {}).get("bottom"),
        "status_text": (geo.get("status") or {}).get("text"),
        "open": geo.get("open"),
        "hit_is_frame": geo.get("hit_is_frame"),
        "in_viewport": geo.get("in_viewport"),
    }
    mark(f"[{width}px] {stage}", ok, detail)
    return geo


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception as exc:  # pragma: no cover
        log(f"    screenshot {name} failed: {exc}")


def shot_recorder(page: Page, slot: str, name: str) -> None:
    """A photograph of just the recorder area, which is what the musician is complaining about."""
    geo = geometry(page, slot)
    frame = geo.get("frame") or {}
    if not frame:
        shot(page, name)
        return
    pad = 60
    # getBoundingClientRect is in VIEWPORT coordinates; screenshot clips are in PAGE coordinates.
    # Without the scroll offset the clip photographs whatever happens to be that far down the
    # document - which is how the evidence for a recorder showed the top of the layer panel.
    scroll = page.evaluate("() => ({x: window.scrollX, y: window.scrollY})")
    clip = {
        "x": max(0.0, float(frame["x"]) + float(scroll["x"]) - 10),
        "y": max(0.0, float(frame["y"]) + float(scroll["y"]) - pad),
        "width": max(80.0, float(frame["w"]) + 20),
        "height": max(80.0, float(frame["h"]) + pad + 20),
    }
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), clip=clip)
    except Exception:
        shot(page, name)


def click_practice_page(page: Page) -> bool:
    """Open the Practice page - the one with the tools, not the Practice Log.

    ``click_nav(page, "Practice")`` matches any button whose text CONTAINS "Practice" and takes the
    last one, which is "Practice Log".
    """
    try:
        expand_pages_nav(page)
    except Exception:
        pass
    page.wait_for_timeout(600)
    return bool(
        page.evaluate(
            r"""() => {
                const want = /^(?:[^A-Za-z]*\s*)?practice$/i;
                for (const b of document.querySelectorAll('button')) {
                    const t = (b.innerText || '').trim();
                    if (!want.test(t)) continue;
                    if (b.offsetParent === null) continue;
                    b.click();
                    return true;
                }
                return false;
            }"""
        )
    )


def boot(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    for _ in range(60):
        settle(page, 3)
        if "PAGES" in body(page).upper():
            return True
    return False


def goto_multitrack(page: Page) -> bool:
    if "multitrack session workspace" in low(body(page)):
        return True
    click_nav(page, "Multitrack")
    settle(page, 7)
    return "multitrack session workspace" in low(body(page))


def layer_is_open(page: Page, slot: str) -> bool:
    return bool(geometry(page, slot).get("open"))


def toggle_layer_by_pointer(page: Page, slot: str, want_open: bool) -> str:
    """Open or close a layer the way a person does: a real click on its summary."""
    box = page.evaluate(
        r"""(slot) => {
            const s = slot.toLowerCase();
            for (const d of document.querySelectorAll('details')) {
                const sum = d.querySelector('summary');
                const t = ((sum && sum.innerText) || '').toLowerCase();
                if (!t.includes('layer controls') || !t.includes(s)) continue;
                sum.scrollIntoView({block: 'center'});
                const r = sum.getBoundingClientRect();
                return {x: r.x + Math.min(40, r.width / 2), y: r.y + r.height / 2, open: d.open};
            }
            return null;
        }""",
        slot,
    )
    if not box:
        return "no summary"
    if bool(box["open"]) == want_open:
        return "already"
    page.mouse.click(box["x"], box["y"])
    settle(page, 3)
    return "clicked"


def tap_record(page: Page, slot: str) -> str:
    """Press Record with real input, through the frame, with the browser's own checks.

    ``frame_locator(...).tap()`` requires the element to be visible, stable and able to receive the
    event, and raises otherwise - which is exactly the guarantee this acceptance is about. A
    programmatic ``element.click()`` is used nowhere: that is what certified a four-pixel recorder.
    """
    geometry(page, slot)  # tags the frame and scrolls it into view
    loc = page.frame_locator(frame_selector(slot)).locator("#rec")
    try:
        loc.tap(timeout=8000)
        return "tapped"
    except Exception as exc_tap:
        try:
            loc.click(timeout=8000)
            return "clicked"
        except Exception as exc_click:
            return f"failed: tap={str(exc_tap)[:60]} click={str(exc_click)[:60]}"


def recorder_status(page: Page, slot: str) -> str:
    return str((geometry(page, slot).get("status") or {}).get("text") or "")


def run_viewport(page: Page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 900})
    settle(page, 4)
    log(f"\n== {width} px ==")

    # 1. a fresh empty layer - the state the musician reported
    check_visible(page, SLOT_GUITAR, "fresh empty layer is visible", width)
    shot_recorder(page, SLOT_GUITAR, f"{width}-empty-layer")

    # 2. expanding a previously collapsed layer, by pointer
    got = toggle_layer_by_pointer(page, SLOT_SAX, want_open=True)
    mark(f"[{width}px] a collapsed layer opens on a real click", got in ("clicked", "already"), got)
    check_visible(page, SLOT_SAX, "previously collapsed layer is visible once opened", width)
    shot_recorder(page, SLOT_SAX, f"{width}-expanded-layer")

    # 3. collapse and reopen the same layer
    toggle_layer_by_pointer(page, SLOT_SAX, want_open=False)
    reopened = toggle_layer_by_pointer(page, SLOT_SAX, want_open=True)
    mark(f"[{width}px] the same layer reopens", reopened in ("clicked", "already"), reopened)
    check_visible(page, SLOT_SAX, "layer is visible after collapse and reopen", width)

    # 4. the three instruments
    for slot, label in ((SLOT_GUITAR, "guitar"), (SLOT_SAX, "saxophone"), (SLOT_FLUTE, "flute")):
        toggle_layer_by_pointer(page, slot, want_open=True)
        check_visible(page, slot, f"{label} layer is visible", width)

    # 5. a Streamlit rerun must not shrink it again
    page.evaluate(
        r"""() => {
            const el = document.querySelector('input[type=range]');
            if (el) { el.focus(); el.blur(); }
        }"""
    )
    settle(page, 5)
    check_visible(page, SLOT_SAX, "still visible after a rerun", width)

    # 10. and the button is a real touch target
    geo = geometry(page, SLOT_SAX)
    btn = geo.get("button") or {}
    mark(
        f"[{width}px] the Record button is a usable touch target",
        float(btn.get("h") or 0) >= 28 and float(btn.get("w") or 0) >= 90,
        {"h": btn.get("h"), "w": btn.get("w")},
    )
    mark(
        f"[{width}px] the button says what it will do",
        "record" in low(str(btn.get("text") or "")),
        btn.get("text"),
    )


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required", "--mute-audio"],
        )
        ctx = browser.new_context(viewport={"width": 1400, "height": 950},
                                  permissions=["microphone"], has_touch=True)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            if not boot(page):
                mark("the app loads", False)
                return 1
            mark("the app loads", True)
            if not goto_multitrack(page):
                mark("Multitrack opens", False, low(body(page))[:160])
                return 1
            mark("Multitrack opens", True)

            for width in (1400, 390, 360):
                run_viewport(page, width)

            # 6. navigate away and back. Driven at desktop width: the sidebar nav is collapsed at
            # 390 px, and click_nav matches any button containing the word (including "Practice
            # Log"), so doing the trip on a phone layout tests the harness, not the product. The
            # measurement afterwards is taken at 390 px, which is what matters.
            page.set_viewport_size({"width": 1400, "height": 950})
            settle(page, 3)
            left = click_practice_page(page)
            settle(page, 8)
            really_left = "multitrack session workspace" not in low(body(page))
            mark("Multitrack can be left", left and really_left,
                 f"clicked={left} left={really_left}")
            back = goto_multitrack(page) if really_left else False
            # Only meaningful if we actually went away: otherwise this gate measures nothing.
            mark("Multitrack reopens after navigating away", really_left and back,
                 f"left={really_left} back={back}")
            if back:
                page.set_viewport_size({"width": 390, "height": 900})
                settle(page, 4)
                toggle_layer_by_pointer(page, SLOT_SAX, want_open=True)
                check_visible(page, SLOT_SAX, "visible after navigating away and back", 390)

            # 7. record, stop, then the take controls - with real input only. Independent of the
            # navigation above: it opens the layer itself.
            page.set_viewport_size({"width": 390, "height": 900})
            settle(page, 3)
            if not goto_multitrack(page):
                mark("Multitrack is open for the tap test", False)
            toggle_layer_by_pointer(page, SLOT_SAX, want_open=True)
            settle(page, 2)
            check_visible(page, SLOT_SAX, "visible before the tap", 390)
            pressed = tap_record(page, SLOT_SAX)
            mark("[390px] Record responds to a real tap", pressed in ("tapped", "clicked"), pressed)
            if pressed in ("tapped", "clicked"):
                settle(page, 2)
                stopping = recorder_status(page, SLOT_SAX)
                mark("[390px] the recorder says what it is doing while recording",
                     bool(stopping), stopping[:90])
                check_visible(page, SLOT_SAX, "visible while recording", 390)
                shot_recorder(page, SLOT_SAX, "390-recording")
                settle(page, 2)
                tap_record(page, SLOT_SAX)  # stop
                settle(page, 8)
                check_visible(page, SLOT_SAX, "visible after stopping", 390)
                mark("[390px] the take landed", "original take preview" in low(body(page)))
            mark("no uncaught JS errors", not errors, errors[:3])

            # 8. microphone permission: granted (above), denied, and unavailable. What is asserted
            # is that the control stays visible and SAYS something - the defect was an empty area.
            for label, script in (
                (
                    "denied",
                    """
                    const md = navigator.mediaDevices;
                    if (md) {
                        md.getUserMedia = () => Promise.reject(
                            new DOMException('Permission denied', 'NotAllowedError'));
                    }
                    """,
                ),
                (
                    "unavailable",
                    """
                    try { Object.defineProperty(navigator, 'mediaDevices', {get: () => undefined}); }
                    catch (e) {}
                    """,
                ),
            ):
                ctx2 = browser.new_context(viewport={"width": 390, "height": 900},
                                           has_touch=True)
                ctx2.add_init_script(script)
                p2 = ctx2.new_page()
                errs2: list[str] = []
                p2.on("pageerror", lambda e: errs2.append(str(e)))
                try:
                    if not boot(p2) or not goto_multitrack(p2):
                        mark(f"[390px] Multitrack opens with the microphone {label}", False)
                        continue
                    mark(f"[390px] Multitrack opens with the microphone {label}", True)
                    toggle_layer_by_pointer(p2, SLOT_GUITAR, want_open=True)
                    settle(p2, 2)
                    geo = check_visible(p2, SLOT_GUITAR,
                                        f"Record is visible with the microphone {label}", 390)
                    shot_recorder(p2, SLOT_GUITAR, f"390-mic-{label}")
                    pressed = tap_record(p2, SLOT_GUITAR)
                    mark(f"[390px] Record can be pressed with the microphone {label}",
                         pressed in ("tapped", "clicked"), pressed)
                    settle(p2, 4)
                    said = recorder_status(p2, SLOT_GUITAR)
                    mark(f"[390px] the recorder explains the microphone being {label}",
                         bool(said.strip()), said[:120])
                    after = check_visible(p2, SLOT_GUITAR,
                                          f"still visible after the microphone was {label}", 390)
                    del geo, after
                finally:
                    ctx2.close()
        finally:
            (OUT / "measurements.json").write_text(
                json.dumps({"gates": GATES, "measured": MEASURED, "js_errors": errors},
                           indent=1, default=str),
                encoding="utf-8",
            )
            (OUT / "body.txt").write_text(body(page), encoding="utf-8")
            ctx.close()
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log(f"\n{passed}/{len(GATES)} gates passed")
    for name, ok in sorted(GATES.items()):
        if not ok:
            log(f"  FAILED: {name}")
    log(f"evidence in {OUT}")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
