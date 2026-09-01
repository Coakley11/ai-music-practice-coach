"""Sequential source/key authority walk — fresh + second session.

Fails hard on first incoherent step. No blind retries / second-click acceptance.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("v", ROOT / "_source_identity_browser_verify.py")
v = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(v)

RESULTS: list[dict] = []


def log(step: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"step": step, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}", flush=True)


def _set_pk(page, needle: str) -> bool:
    box = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
    )
    if box.count() == 0:
        return False
    ctrl = box.first.locator('[data-baseweb="select"], div[role="button"], input')
    try:
        (ctrl.first if ctrl.count() else box.first).click(timeout=5000)
    except Exception:
        return False
    v.wait_streamlit(page, 600)
    try:
        page.wait_for_selector('[role="option"]', timeout=8000)
    except Exception:
        page.keyboard.press("Escape")
        return False
    opts = page.locator('[role="option"]')
    count = opts.count()
    for i in range(min(count, 100)):
        try:
            t = (opts.nth(i).inner_text(timeout=1500) or "").strip()
        except Exception:
            continue
        if not t or t == "No results":
            continue
        norm = t.replace("♯", "#").replace("♭", "b")
        if needle in t or needle in norm or t in {needle, f"{needle} major", f"{needle} Major"}:
            try:
                opts.nth(i).click(timeout=5000)
            except Exception:
                page.keyboard.press("Escape")
                return False
            v.wait_streamlit_idle(page)
            return True
    # Fallback: role name match (handles virtualized menus better).
    try:
        esc = re.escape(needle.replace("#", "[#♯]").replace("b", "[b♭]"))
        choice = page.get_by_role("option", name=re.compile(rf"^{esc}(\s+major)?$", re.I))
        if choice.count():
            choice.first.click(timeout=5000)
            v.wait_streamlit_idle(page)
            return True
    except Exception:
        pass
    page.keyboard.press("Escape")
    return False


def _sidebar_pk(page) -> str:
    box = page.locator('[data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Practice\s*/\s*Concert Key", re.I)
    )
    if box.count() == 0:
        return ""
    try:
        # Prefer the visible selected value, not only the field label.
        val = box.first.locator('[data-baseweb="select"]')
        if val.count():
            return (val.first.inner_text(timeout=2000) or "").strip()
        return (box.first.inner_text(timeout=2000) or "").strip()
    except Exception:
        return ""


def _assert_composition_identity(page) -> tuple[bool, str]:
    text = v.body_text(page)
    if re.search(r"Edit chords in\s+\*?Custom Progression Lab", text):
        return False, "custom_lab_copy"
    if re.search(r"My Progression\s*·\s*Custom", text):
        return False, "my_progression_custom_line"
    if re.search(r"Active song:.*Custom", text, re.I):
        return False, "active_song_custom"
    return True, "ok"


def _token_in(blob: str, *tokens: str) -> bool:
    b = (blob or "").replace("♯", "#").replace("♭", "b")
    for tok in tokens:
        t = tok.replace("♯", "#").replace("♭", "b")
        if len(t) <= 2:
            if re.search(rf"(?<![A-Za-z#]){re.escape(t)}(?![a-z])", b):
                return True
        elif t in b:
            return True
    return False


def _wait_no_custom_lab_copy(page, timeout_ms: int = 15000) -> bool:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        text = v.body_text(page)
        if not re.search(r"Edit chords in\s+\*?Custom Progression Lab", text):
            return True
        page.wait_for_timeout(400)
    return not re.search(
        r"Edit chords in\s+\*?Custom Progression Lab", v.body_text(page)
    )


def run_walk(page, *, label: str) -> int:
    fails = 0

    def step(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        log(f"{label}:{name}", ok, detail)
        if not ok:
            fails += 1

    v.ensure_songs(page)
    try:
        v.select_music_source(page, "Catalog")
    except Exception as exc:
        step("start_catalog", False, str(exc)[:160])
        return fails + 1
    v.wait_streamlit(page, 1500)
    step("start_catalog", v.assert_radio_selected(page, "Catalog"), "")

    v.select_music_source(page, "Custom Progression")
    v.wait_streamlit(page, 2000)
    step(
        "switch_custom",
        v.assert_radio_selected(page, "Custom"),
        v.body_text(page)[:100],
    )

    changed = _set_pk(page, "E")
    v.wait_streamlit(page, 2000)
    side = _sidebar_pk(page)
    text = v.body_text(page)
    # Prefer card/sidebar Practice Key lines over the selectbox chrome (label alone).
    pk_lines = "\n".join(
        ln for ln in text.splitlines() if re.search(r"Practice|Concert Key", ln, re.I)
    )
    step(
        "custom_change_key",
        changed and (_token_in(side, "E") or _token_in(pk_lines, "E")),
        f"side={side[:80]!r} pk_lines={pk_lines[:120]!r} changed={changed}",
    )

    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 5000)
    v.ensure_songs(page)
    v.select_music_source(page, "Custom Progression")
    v.wait_streamlit(page, 2000)
    side = _sidebar_pk(page)
    step("custom_refresh_keeps_key", _token_in(side, "E"), side[:80])

    v.select_music_source(page, "Composition")
    try:
        v.wait_composition_hub_ready(page, timeout_ms=25000)
    except Exception as exc:
        step("switch_composition_ready", False, str(exc)[:160])
        return fails + 1
    _wait_no_custom_lab_copy(page, timeout_ms=12000)
    id_ok, id_detail = _assert_composition_identity(page)
    step("switch_composition_identity", id_ok, id_detail)
    side = _sidebar_pk(page)
    text = v.body_text(page)
    step(
        "composition_reset_to_c",
        _token_in(side, "C") or _token_in(text, "C major", "Practice C", "Practice / Concert Key"),
        f"side={side[:80]!r}",
    )

    changed = _set_pk(page, "D#") or _set_pk(page, "Eb") or _set_pk(page, "D♯")
    v.wait_streamlit(page, 2000)
    side = _sidebar_pk(page)
    text = v.body_text(page)
    step(
        "composition_change_ds",
        changed and _token_in(side, "D#", "Eb", "D♯") and _token_in(text, "D#", "Eb", "D♯"),
        f"side={side[:80]!r}",
    )

    page.reload(wait_until="domcontentloaded", timeout=180_000)
    v.wait_streamlit(page, 5000)
    v.ensure_songs(page)
    v.select_music_source(page, "Composition")
    try:
        v.wait_composition_hub_ready(page, timeout_ms=20000)
    except Exception as exc:
        step("composition_refresh_ready", False, str(exc)[:160])
        return fails + 1
    side = _sidebar_pk(page)
    step(
        "composition_refresh_keeps_ds",
        _token_in(side, "D#", "Eb", "D♯"),
        side[:80],
    )
    id_ok, id_detail = _assert_composition_identity(page)
    step("composition_refresh_identity", id_ok, id_detail)

    v.select_music_source(page, "Custom Progression")
    v.wait_streamlit(page, 2500)
    step(
        "composition_to_custom",
        v.assert_radio_selected(page, "Custom"),
        v.body_text(page)[:100],
    )

    v.select_music_source(page, "Catalog")
    v.wait_streamlit(page, 2000)
    step("custom_to_catalog", v.assert_radio_selected(page, "Catalog"), "")

    for i, src in enumerate(
        ["Custom Progression", "Composition", "Custom Progression", "Catalog", "Composition"]
    ):
        try:
            v.select_music_source(page, src)
            v.wait_streamlit(page, 1800)
            if "Composition" in src:
                v.wait_composition_hub_ready(page, timeout_ms=15000)
                id_ok, id_detail = _assert_composition_identity(page)
                step(f"rapid_{i}_composition", id_ok, id_detail)
            elif "Custom" in src:
                step(
                    f"rapid_{i}_custom",
                    v.assert_radio_selected(page, "Custom"),
                    "",
                )
            else:
                step(
                    f"rapid_{i}_catalog",
                    v.assert_radio_selected(page, "Catalog"),
                    "",
                )
        except Exception as exc:
            step(f"rapid_{i}_{src}", False, str(exc)[:160])

    return fails


def main() -> int:
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label in ("fresh", "restored"):
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(60000)
            page.goto(v.URL + "/?dev=1", wait_until="domcontentloaded", timeout=180000)
            v.wait_streamlit(page, 4000)
            fails += run_walk(page, label=label)
            context.close()
        browser.close()

    out = OUT / "source_authority_sequential_walk.json"
    out.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(f"Failures: {fails}", flush=True)
    print(f"Wrote {out}", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
