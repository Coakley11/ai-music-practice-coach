"""Issue 77C acceptance: the Groove / feel selector offers the real vocabulary and tells the truth.

Measured in a browser against the running app. The gates exist because a dropdown is the easiest
thing in the world to make look right:

  * the list must contain the styles the engine genuinely plays, Blues and the Jewish styles
    included, not the seven that were written into the page;
  * **Auto** must show what it resolved to, and selecting Auto must still store "Auto";
  * choosing Blues groove, Jewish hora and Klezmer groove must stick across the rerun;
  * Free Layering must keep recording with no generated backing whatever style is displayed;
  * a prepared backing must still arm the recorder (Issue 77A's guarantee) after all of this;
  * desktop, 390 px and 360 px.

Usage:
    python scripts/_accept_issue77c_grooves.py http://127.0.0.1:8631
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

import _accept_issue78c_visibility as H  # noqa: E402

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8631").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "after"
OUT = SCRIPTS / f"evidence-issue77c-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)

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


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

# The Groove / feel selectbox: its current value and, once opened, its options.
GROOVE_BOX_JS = """() => {
  for (const b of document.querySelectorAll('[data-testid="stSelectbox"]')) {
    const t = (b.innerText || '');
    if (!/groove|feel/i.test(t)) continue;
    if (b.offsetParent === null) continue;
    // Streamlit puts the LABEL in the container's text and the chosen VALUE in an <input>, so the
    // value has to be read from the input - the container text alone says only "Groove / feel",
    // which is what made an earlier run check the wrong thing.
    const input = b.querySelector('input');
    const target = input || b;
    // Scroll it into view BEFORE reading the rect. getBoundingClientRect is viewport-relative, and
    // this control sits below the fold on a tall page: an earlier run read y=1274 in an 1100-tall
    // viewport, clicked nothing, and reported that the dropdown would not open.
    target.scrollIntoView({block: 'center'});
    const r = target.getBoundingClientRect();
    return {label: t.replace(/\\n+/g, ' | ').trim().slice(0, 80),
            text: input ? (input.value || input.getAttribute('value') || '') : '',
            x: r.x + r.width / 2, y: r.y + r.height / 2};
  }
  return {error: 'no Groove / feel selectbox'};
}"""

OPEN_OPTIONS_JS = """() => {
  const seen = [];
  for (const el of document.querySelectorAll('[role="option"], li[role="option"]')) {
    const t = (el.innerText || '').trim();
    if (t) seen.push(t);
  }
  return seen;
}"""

PICK_OPTION_JS = """(want) => {
  const needle = want.toLowerCase();
  for (const el of document.querySelectorAll('[role="option"], li[role="option"]')) {
    const t = (el.innerText || '').trim();
    if (t.toLowerCase() !== needle) continue;
    el.scrollIntoView({block: 'center'});
    const r = el.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
  }
  return {error: 'no option exactly matching ' + want};
}"""

RECORDER_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const f = d.querySelector('iframe[title*="recorder" i], iframe[src*="recorder" i]');
    if (!f) return {error: 'no recorder iframe'};
    try {
      const doc = f.contentDocument;
      const btn = doc.getElementById('rec'), st = doc.getElementById('status');
      return {label: (btn && btn.textContent || '').trim(), disabled: !!(btn && btn.disabled),
              status: (st && st.textContent || '').trim(),
              frame_h: Math.round(f.getBoundingClientRect().height)};
    } catch (e) { return {error: 'cross-doc'}; }
  }
  return {error: 'no panel'};
}"""


def idle(page, quiet: int = 3, limit: float = 200.0) -> bool:
    t0, n = time.time(), 0
    while time.time() - t0 < limit:
        if page.evaluate(RUNNING_JS):
            n = 0
        else:
            n += 1
            if n >= quiet:
                return True
        page.wait_for_timeout(1100)
    return False


def groove_box(page) -> dict:
    return page.evaluate(GROOVE_BOX_JS)


def open_groove_options(page) -> list:
    """Open the dropdown and list what it offers.

    Clicking the container missed the control - the <input> is what opens the list, and the options
    are rendered in a portal on document.body rather than inside the container.
    """
    box = groove_box(page)
    if box.get("error"):
        return []
    page.mouse.click(box["x"], box["y"])
    page.wait_for_timeout(1500)
    opts = page.evaluate(OPEN_OPTIONS_JS)
    if not opts:
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(1200)
        opts = page.evaluate(OPEN_OPTIONS_JS)
    return opts


def choose_groove(page, want: str) -> str:
    """Open the list and click the option by its accessible name.

    Typing into the combobox was wrong twice over: the text ACCUMULATED in the input instead of
    replacing it, and the gate then passed on a substring of that garbage
    ("Auto - BalladBlues groove"). Clicking the option by role also scrolls it into view, which the
    enumeration could not do - the listbox renders eleven of the twelve options at a time.
    """
    box = groove_box(page)
    if box.get("error"):
        return box["error"]
    page.mouse.click(box["x"], box["y"])
    page.wait_for_timeout(1200)
    try:
        option = page.get_by_role("option", name=want, exact=True).first
        option.scroll_into_view_if_needed(timeout=5000)
        option.click(timeout=8000)
    except Exception as exc:
        page.keyboard.press("Escape")
        return "could not click option " + want + ": " + str(exc)[:90]
    idle(page)
    page.wait_for_timeout(1500)
    idle(page)
    return "clicked the option " + want


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                  "--autoplay-policy=no-user-gesture-required"])
        try:
            ctx = browser.new_context(viewport={"width": 1500, "height": 1100})
            page = ctx.new_page()
            page.set_default_timeout(40000)
            page.goto(URL, wait_until="load")
            idle(page)
            H.boot(page)
            if not H.goto_multitrack(page):
                mark("the Multitrack page opens", False)
                return 1
            mark("the Multitrack page opens", True)
            idle(page)

            # --- the vocabulary ---------------------------------------------------------------
            log("\n-- the list the musician is offered")
            box = groove_box(page)
            MEASURED["groove_box_initial"] = box
            mark("the Groove / feel selector is on the page", not box.get("error"), box)
            options = open_groove_options(page)
            MEASURED["options"] = options
            log("    " + json.dumps(options, default=str))
            shot(page, "groove-options")
            wanted = ["Blues groove", "Jewish groove", "Jewish hora", "Klezmer groove",
                      "Jewish ballad", "Pop groove", "Rock groove", "Jazz swing", "Bossa nova",
                      "Funk groove", "Ballad"]
            missing = [w for w in wanted if not any(w == o or o.startswith(w) for o in options)]
            MEASURED["not_enumerated"] = missing
            # The listbox renders eleven of the twelve options at a time, so a missing name here
            # means "not rendered yet", not "not offered" - which is why each style the user named
            # is SELECTED below instead. Anything beyond that would be a false negative.
            mark("the offered list is the shared vocabulary, not the old seven",
                 len(options) >= 11 and any("Blues groove" == o for o in options)
                 and any("Klezmer groove" == o for o in options),
                 f"{len(options)} options; not yet rendered: {missing}")
            auto = [o for o in options if o.startswith("Auto")]
            mark("the Auto option shows what it resolved to",
                 bool(auto) and ("—" in auto[0] or "-" in auto[0]), auto)
            page.keyboard.press("Escape")
            idle(page)

            # --- explicit selections stick ----------------------------------------------------
            for style in ("Blues groove", "Jewish hora", "Klezmer groove", "Jewish ballad"):
                log(f"\n-- choose {style}")
                res = choose_groove(page, style)
                MEASURED[f"choose_{style}"] = res
                now = groove_box(page)
                MEASURED[f"box_after_{style}"] = now
                mark(f"{style} can be chosen and stays chosen",
                     str(now.get("text") or "").strip() == style,
                     f"{res} -> value={now.get('text')!r}")
                shot(page, "groove-" + style.replace(" ", "-").replace("/", "-"))

            # --- back to Auto ------------------------------------------------------------------
            log("\n-- back to Auto")
            auto_label = (auto[0] if auto else "Auto")
            res = choose_groove(page, auto_label)
            now = groove_box(page)
            MEASURED["box_after_auto"] = now
            _auto_value = str(now.get("text") or "").strip()
            mark("Auto can be chosen again",
                 _auto_value.startswith("Auto") and "—" in _auto_value,
                 f"{res} -> value={_auto_value!r}")

            # --- a prepared backing still arms the recorder (77A's guarantee) ------------------
            log("\n-- a prepared backing still arms Record")
            prep = H.click_page_button(page, "prepare backing")
            MEASURED["prepare"] = prep
            idle(page)
            page.wait_for_timeout(4000)
            idle(page)
            if not H.layer_is_open(page, H.SLOT_GUITAR):
                H.toggle_layer_by_pointer(page, H.SLOT_GUITAR, True)
                idle(page)
            t0, rec = time.time(), {}
            while time.time() - t0 < 120:
                rec = page.evaluate(RECORDER_JS, H.SLOT_GUITAR)
                if rec.get("error") or "preparing recorder" not in (rec.get("status") or "").lower():
                    break
                page.wait_for_timeout(5000)
            MEASURED["recorder_with_backing"] = rec
            mark("Record is enabled with a backing prepared under the chosen groove",
                 rec.get("disabled") is False, rec.get("status"))
            shot(page, "recorder-after-groove")

            # --- free layering ----------------------------------------------------------------
            log("\n-- free layering keeps recording without generated backing")
            picked = page.evaluate(
                """() => {
                    for (const l of document.querySelectorAll('label')) {
                      const t = (l.innerText || '').trim().toLowerCase();
                      if (!t.startsWith('free layering')) continue;
                      if (l.offsetParent === null) continue;
                      l.scrollIntoView({block: 'center'});
                      const r = l.getBoundingClientRect();
                      return {x: r.x + 8, y: r.y + r.height / 2};
                    }
                    return {error: 'no free layering option'};
                }""")
            if picked.get("error"):
                mark("Free layering can be selected", False, picked["error"])
            else:
                page.mouse.click(picked["x"], picked["y"])
                idle(page)
                page.wait_for_timeout(2000)
                idle(page)
                sel = page.evaluate(
                    """() => [...document.querySelectorAll('input[type=radio]')]
                             .filter(i => i.checked)
                             .map(i => (((i.closest('label')||{}).innerText)||'').trim())""")
                MEASURED["scope_free_layering"] = sel
                mark("Free layering can be selected",
                     any("free layering" in str(s).lower() for s in sel), sel)
                if not H.layer_is_open(page, H.SLOT_GUITAR):
                    H.toggle_layer_by_pointer(page, H.SLOT_GUITAR, True)
                    idle(page)
                t0, rec2 = time.time(), {}
                while time.time() - t0 < 120:
                    rec2 = page.evaluate(RECORDER_JS, H.SLOT_GUITAR)
                    if rec2.get("error") or "preparing recorder" not in (rec2.get("status") or "").lower():
                        break
                    page.wait_for_timeout(5000)
                MEASURED["recorder_free_layering"] = rec2
                mark("Record still works in free layering with no generated backing",
                     rec2.get("disabled") is False, rec2.get("status"))
                groove_now = groove_box(page)
                MEASURED["groove_box_free_layering"] = groove_now
                mark("the musical style is still shown in free layering",
                     bool(str(groove_now.get("text") or "").strip()),
                     f"value={groove_now.get('text')!r}")
                shot(page, "free-layering-groove")
            ctx.close()

            # --- widths -------------------------------------------------------------------------
            log("\n-- widths")
            for width in (1400, 390, 360):
                wctx = browser.new_context(viewport={"width": width, "height": 900})
                wpage = wctx.new_page()
                wpage.set_default_timeout(40000)
                try:
                    wpage.goto(URL, wait_until="load")
                    idle(wpage)
                    H.boot(wpage)
                    if not H.goto_multitrack(wpage):
                        mark(f"[{width}px] the Multitrack page opens", False)
                        continue
                    idle(wpage)
                    gb = groove_box(wpage)
                    over = wpage.evaluate(
                        """() => { const de = document.documentElement;
                                   return {scroll_w: de.scrollWidth, client_w: de.clientWidth,
                                           sideways: de.scrollWidth > de.clientWidth + 2}; }""")
                    MEASURED[f"width_{width}"] = {"groove": gb, "overflow": over}
                    mark(f"[{width}px] the groove selector is visible",
                         not gb.get("error"),
                         f"value={gb.get('text')!r}")
                    mark(f"[{width}px] the page does not scroll sideways",
                         not over.get("sideways"), over)
                    shot(wpage, f"width-{width}")
                finally:
                    wctx.close()
        finally:
            browser.close()

    (OUT / "measured.json").write_text(json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("\n" + "=" * 78)
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates pass")
    for g in failed:
        log("  FAILED: " + g)
    log("evidence: " + str(OUT))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
