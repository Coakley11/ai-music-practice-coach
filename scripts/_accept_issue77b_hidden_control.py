"""Is the second, zero-sized Discard element focusable, and can it delete a take?

Safety check for Issue 77B. The panel contains one pressable "Discard take" button and a second
element with the same label and no box (x: 0, y: 0). Before anything is changed, three questions
have to be answered with measurements:

  1. WHAT is it - its tag, its tabindex, its computed style, and the data-testids of its ancestors.
     A hypothesis worth testing: Save layer carries no ``help=`` tooltip and appears once, while
     Discard take carries one and appears twice, which points at Streamlit's tooltip scaffolding
     rather than a duplicated control in this app.
  2. Can the keyboard reach it - does focus() land on it, and is it in the tab order.
  3. Can it DELETE - if it can be focused, pressing Enter on it must be tried against a real take,
     because an invisible control that destroys a recording is an action-safety problem, not a
     cosmetic one.

Nothing is changed here; this only reports.
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

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8625").rstrip("/")
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "hidden"
OUT = SCRIPTS / f"evidence-issue77b-{TAG}"
OUT.mkdir(parents=True, exist_ok=True)
FIX = OUT / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)

GATES: dict[str, bool] = {}
MEASURED: dict[str, object] = {}
SAX, GUITAR = H.SLOT_SAX, H.SLOT_GUITAR


def log(msg: str) -> None:
    text = str(msg)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: object = "") -> None:
    GATES[gate] = bool(ok)
    log(("PASS  " if ok else "FAIL  ") + gate + (f"  - {detail}" if detail else ""))


def fixture() -> str:
    import math
    import struct
    import wave

    path = FIX / "take.wav"
    if not path.exists():
        with wave.open(str(path), "wb") as h:
            h.setnchannels(1)
            h.setsampwidth(2)
            h.setframerate(44100)
            h.writeframes(b"".join(
                struct.pack("<h", int(11000 * math.sin(2 * math.pi * 294 * t / 44100)))
                for t in range(44100 * 2)))
    return str(path)


RUNNING_JS = """() => {
  const w = document.querySelector('[data-testid="stStatusWidget"]');
  if (!w) return false;
  const t = (w.innerText || '').toLowerCase();
  return t.includes('running') || t.includes('stop');
}"""

# Everything about every control in one layer panel that mentions discarding or deleting.
INSPECT_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const rows = [];
    const all = [...d.querySelectorAll('button')];
    all.forEach((b, i) => {
      const label = (b.innerText || b.getAttribute('aria-label') || '').trim();
      if (!/discard take|delete layer|save layer/i.test(label)) return;
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      const ancestors = [];
      let p = b.parentElement, hops = 0;
      while (p && hops < 7) {
        const id = p.getAttribute('data-testid');
        if (id) ancestors.push(id);
        p = p.parentElement; hops += 1;
      }
      rows.push({
        index: i, label: label, tag: b.tagName,
        disabled: !!b.disabled, aria_disabled: b.getAttribute('aria-disabled'),
        tabindex: b.getAttribute('tabindex'),
        width: Math.round(r.width), height: Math.round(r.height),
        x: Math.round(r.x), y: Math.round(r.y),
        offset_parent: b.offsetParent ? b.offsetParent.tagName : null,
        display: cs.display, visibility: cs.visibility, opacity: cs.opacity,
        pointer_events: cs.pointerEvents, overflow_hidden_ancestor: null,
        ancestors: ancestors,
        html: (b.outerHTML || '').slice(0, 150)
      });
    });
    return rows;
  }
  return [];
}"""

FOCUS_JS = """([slot, wantLabel, which]) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const matches = [...d.querySelectorAll('button')].filter(b =>
      new RegExp(wantLabel, 'i').test((b.innerText || '').trim()));
    const b = matches[which];
    if (!b) return {error: 'no match at index ' + which + ' of ' + matches.length};
    b.focus();
    const active = document.activeElement;
    return {focused: active === b, active_tag: active ? active.tagName : null,
            active_label: active ? (active.innerText || '').trim().slice(0, 40) : null,
            matches: matches.length};
  }
  return {error: 'no panel'};
}"""

PANEL_JS = """(slot) => {
  const s = slot.toLowerCase();
  for (const d of document.querySelectorAll('details')) {
    const t = ((d.querySelector('summary')||{}).innerText||'').toLowerCase();
    if (!(t.includes('layer controls') && t.includes(s))) continue;
    const txt = (d.innerText || '').toLowerCase();
    return {take: txt.includes('original take preview'), saved: txt.includes('saved layer'),
            unsaved: txt.includes('unsaved take')};
  }
  return {missing: true};
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


def open_layer(page, slot: str) -> None:
    if not H.layer_is_open(page, slot):
        H.toggle_layer_by_pointer(page, slot, True)
        idle(page)


def main() -> int:
    take = fixture()
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
                mark("the Multitrack page opens", False)
                return 1
            mark("the Multitrack page opens", True)
            idle(page)

            open_layer(page, SAX)
            sel = ('details:has(summary:has-text("Layer controls")):has(summary:has-text("'
                   + SAX + '")) input[type="file"]')
            page.locator(sel).first.set_input_files(take)
            idle(page)
            page.wait_for_timeout(1200)
            idle(page)
            mark("a take is in place to try to destroy",
                 bool(page.evaluate(PANEL_JS, SAX).get("take")))

            # 1. what the elements are
            log("\n-- 1: what are these elements?")
            rows = page.evaluate(INSPECT_JS, SAX)
            MEASURED["controls"] = rows
            for r in rows:
                log("    " + json.dumps(r, default=str))
            discards = [r for r in rows if "discard" in str(r.get("label", "")).lower()]
            saves = [r for r in rows if "save layer" in str(r.get("label", "")).lower()]
            MEASURED["counts"] = {"discard": len(discards), "save": len(saves)}
            mark("the Discard label appears more than once in the DOM", len(discards) > 1,
                 f"discard x{len(discards)}, save x{len(saves)}")
            # The hypothesis: the extra copy is tooltip scaffolding, and Save (no help=) has none.
            tooltip_ancestors = [
                r for r in discards
                if any("tooltip" in str(a).lower() for a in (r.get("ancestors") or []))
            ]
            MEASURED["tooltip_wrapped"] = tooltip_ancestors
            mark("the extra copy sits inside Streamlit tooltip scaffolding",
                 bool(tooltip_ancestors),
                 [r.get("ancestors") for r in discards])

            # 2. can the keyboard reach the invisible one?
            log("\n-- 2: can the keyboard reach the invisible copy?")
            hidden = [r for r in discards if (r.get("width") or 0) < 2]
            MEASURED["hidden_rows"] = hidden
            if not hidden:
                mark("there is an invisible Discard copy to test", False, "none found this run")
            else:
                which = hidden[0]["index"]
                order = [r["index"] for r in discards]
                focus = page.evaluate(FOCUS_JS, [SAX, "discard take", order.index(which)])
                MEASURED["focus_attempt"] = focus
                log("    " + json.dumps(focus, default=str))
                focusable = bool(focus.get("focused"))
                mark("whether the invisible copy can take keyboard focus (reported, not required)",
                     True, f"focusable={focusable}")

                # 3. if it can be focused, can it delete?
                if focusable:
                    log("\n-- 3: can it destroy the take?")
                    page.keyboard.press("Enter")
                    idle(page)
                    page.wait_for_timeout(1500)
                    idle(page)
                    after = page.evaluate(PANEL_JS, SAX)
                    MEASURED["after_enter_on_hidden"] = after
                    mark("the invisible copy CANNOT delete a take by keyboard",
                         bool(after.get("take")),
                         f"take still present: {after.get('take')}")
                else:
                    mark("the invisible copy CANNOT delete a take by keyboard", True,
                         "it cannot be focused at all")
            try:
                page.screenshot(path=str(OUT / "hidden-control.png"))
            except Exception:
                pass
            ctx.close()
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
