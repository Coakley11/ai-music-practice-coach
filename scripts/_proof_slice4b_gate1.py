"""Minimal real-browser proof for Slice 4B Gate 1 only.

Sequence: Practice -> Songs -> Upload -> Back/Forward cycles, then Back ->
Custom to prove a genuine new branch clears Forward.  The Streamlit server must
be started with SLICE4B_GATE1_TRACE pointing at the same trace file as this
process.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import click_nav, expand_pages_nav, expand_sidebar, wait_idle  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8690"
TRACE = Path(os.environ.get("SLICE4B_GATE1_TRACE") or ROOT / "_runtime_slice4b_gate1" / "gate1-trace.jsonl")
OUT = SCRIPTS / "evidence-slice4b-gate1"
OUT.mkdir(parents=True, exist_ok=True)


def records() -> list[dict[str, Any]]:
    if not TRACE.exists():
        return []
    result: list[dict[str, Any]] = []
    for raw in TRACE.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(raw)
        except Exception:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def latest(event: str = "") -> dict[str, Any]:
    for item in reversed(records()):
        if not event or item.get("event") == event:
            return item
    return {}


def wait_record(event: str, *, after_ns: int = 0, current: str = "", timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in reversed(records()):
            if item.get("event") != event:
                continue
            if int(item.get("ts_ns") or 0) <= after_ns:
                continue
            if current and item.get("current") != current:
                continue
            return item
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {event} current={current!r}")


def checkpoint(name: str) -> dict[str, Any]:
    state = latest("H6_before_arrow_render")
    with TRACE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, "state": state}, ensure_ascii=False) + "\n")
    return state


def visible_history_button(page, label: str):
    key_fragment = "studio_nav_back_btn" if label.startswith("←") else "studio_nav_forward_btn"
    keyed = page.locator(f'[class*="st-key-{key_fragment}"] button')
    visible = [keyed.nth(i) for i in range(keyed.count()) if keyed.nth(i).is_visible()]
    if len(visible) == 1:
        return visible[0]
    buttons = page.get_by_role("button", name=label, exact=True)
    visible = [buttons.nth(i) for i in range(buttons.count()) if buttons.nth(i).is_visible()]
    assert len(visible) == 1, f"expected one visible {label!r}, found {len(visible)}"
    return visible[0]


def click_pages_nav_exact(page, name: str) -> bool:
    """Click a sidebar Pages control without matching Practice Log for Practice."""
    from walk_creative_backing_matrix import NAV

    expand_pages_nav(page)
    label = NAV.get(name, name)
    buttons = page.locator('section[data-testid="stSidebar"] button')
    candidates = []
    for i in range(buttons.count()):
        el = buttons.nth(i)
        try:
            if not el.is_visible():
                continue
            text = " ".join((el.inner_text() or "").split())
            if name == "Practice" and re.search(r"Practice\s+Log", text, re.I):
                continue
            if re.search(re.escape(label), text, re.I):
                candidates.append((text, el))
        except Exception:
            continue
    # Prefer the shortest matching label (Practice over Practice Log already filtered).
    candidates.sort(key=lambda item: len(item[0]))
    for _text, el in candidates:
        try:
            el.evaluate("node => node.scrollIntoView({block: 'center'})")
            box = el.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            else:
                el.click(timeout=5000, force=True)
            wait_idle(page, 4000)
            return True
        except Exception:
            continue
    return click_nav(page, name)


def navigate(page, label: str, expected: str) -> dict[str, Any]:
    start = time.time_ns()
    ok = click_pages_nav_exact(page, label)
    assert ok, f"could not navigate to {label}"
    return wait_record("H6_before_arrow_render", after_ns=start, current=expected)


def history_click(page, which: str, expected: str) -> dict[str, Any]:
    label = "← Back" if which == "back" else "Forward →"
    callback = "H2_back_requested" if which == "back" else "forward_requested"
    wait_idle(page, 1500)
    start = time.time_ns()
    button = visible_history_button(page, label)
    assert button.is_enabled(), f"{label} is disabled before click"
    # Floating history sits in the sidebar/main gutter; sidebar chrome can
    # intercept hit-testing. Prefer a real DOM click on the keyed control.
    # Disabled Forward remains a hard failure via is_enabled() above.
    try:
        button.evaluate(
            """(el) => {
              el.scrollIntoView({block: 'center'});
              el.focus();
              el.click();
            }"""
        )
    except Exception:
        button.click(timeout=8000, force=True)
    wait_record(callback, after_ns=start, timeout=60.0)
    wait_idle(page, 2500)
    return wait_record("H6_before_arrow_render", after_ns=start, current=expected, timeout=60.0)


def main() -> int:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    TRACE.write_text("", encoding="utf-8")
    result: dict[str, Any] = {"GATE1_FORWARD_BROWSER_PASS": False, "url": URL, "checks": {}}
    checks: dict[str, bool] = result["checks"]

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(60_000)
            page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
            wait_idle(page, 6000)
            expand_sidebar(page)
            expand_pages_nav(page)

            h0 = latest("H6_before_arrow_render")
            if h0.get("current") != "practice":
                h0 = navigate(page, "Practice", "practice")
            checkpoint("HARNESS_H0_AFTER_A")
            checks["h0_practice"] = h0.get("current") == "practice"

            navigate(page, "Songs", "picker")
            h1 = navigate(page, "Upload", "analysis")
            checkpoint("HARNESS_H1_AFTER_ABC")
            checks["h1_analysis"] = h1.get("current") == "analysis"
            checks["h1_forward_empty"] = h1.get("forward") == []

            h6_back = history_click(page, "back", "picker")
            checkpoint("HARNESS_H6_AFTER_BACK")
            checks["back_to_songs"] = h6_back.get("current") == "picker"
            checks["forward_contains_upload"] = h6_back.get("forward_target") == "analysis"
            checks["forward_enabled_after_back"] = visible_history_button(page, "Forward →").is_enabled()

            h6_forward = history_click(page, "forward", "analysis")
            checks["forward_to_upload"] = h6_forward.get("current") == "analysis"

            for cycle in range(2):
                history_click(page, "back", "picker")
                history_click(page, "forward", "analysis")
                checks[f"repeat_cycle_{cycle + 1}"] = True

            history_click(page, "back", "picker")
            branched = navigate(page, "Custom", "custom")
            checkpoint("HARNESS_AFTER_NEW_BRANCH")
            checks["branch_to_custom"] = branched.get("current") == "custom"
            checks["branch_forward_empty"] = branched.get("forward") == []
            checks["branch_forward_disabled"] = not visible_history_button(page, "Forward →").is_enabled()

            page.screenshot(path=str(OUT / "gate1-final.png"), full_page=True)
            browser.close()
    except Exception as exc:
        result["error"] = repr(exc)

    result["trace"] = str(TRACE)
    result["GATE1_FORWARD_BROWSER_PASS"] = bool(checks) and all(checks.values()) and not result.get("error")
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["GATE1_FORWARD_BROWSER_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
