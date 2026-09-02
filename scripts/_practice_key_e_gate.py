"""Practice Key E gate for Composition (My Composition / original C).

Verifies:
  - Select Practice / Concert Key → E via the live selectbox
  - Practice key shows E / E major
  - Transposed progression includes E–C#m–A–B (from C Am F G)
  - Original key remains C
  - E + progression survive refresh and Songs → Backing
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _practice_key_harness as pkh  # noqa: E402
import _source_identity_browser_verify as v  # noqa: E402

OUT = v.OUT
RESULTS: list[dict] = []


def log(step: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"step": step, "ok": ok, "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}", flush=True)


def _practice_key_line(text: str) -> str:
    for ln in text.splitlines():
        if re.search(r"Practice(?:\s*/\s*Concert)?(?:\s+concert)?\s*key", ln, re.I):
            return ln.strip()
    return ""


def _has_practice_e(text: str) -> bool:
    if re.search(r"Practice\s+concert\s+key:\s*E(\s+major)?\b", text, re.I):
        return True
    if re.search(
        r"Practice(?:\s*/\s*Concert)?(?:\s+concert)?\s*key:\s*E(\s+major)?\b",
        text,
        re.I,
    ):
        return True
    if re.search(r"\bE\s+major\b", text, re.I):
        return True
    return False


def _has_original_c(text: str) -> bool:
    if re.search(r"Original\s+key:\s*C\b", text, re.I):
        return True
    if re.search(r"Song\s+Original\s+Key:\s*C\b", text, re.I):
        return True
    return False


def _has_e_progression(text: str, html: str) -> bool:
    """C Am F G → E C#m A B (or close spelling variants)."""
    blob = f"{text}\n{html}"
    if re.search(r"E\s*[–—\-]\s*C[#♯]m\s*[–—\-]\s*A\s*[–—\-]\s*B", blob, re.I):
        return True
    if re.search(r"E\s*[–—]\s*C[#♯]m\s*[–—]\s*A\s*[–—]\s*B", blob, re.I):
        return True
    if "E–C#m–A–B" in blob or "E – C#m – A – B" in blob:
        return True
    return False


def _open_composition_backing_keep_key(page) -> None:
    """Open Composition Backing without re-clicking the radio (reselect resets PK)."""
    if v._on_backing_studio(page) and v._live_mode_card(
        page, "mode-composition-song-backing"
    ):
        v.wait_streamlit_idle(page)
        return
    v.ensure_songs(page)
    if not v.assert_radio_selected(page, "Composition"):
        raise RuntimeError("Composition radio not selected; refusing reselect (would reset PK)")
    v.wait_composition_hub_ready(page, timeout_ms=25000)
    v.open_composition_backing_from_hub(page)
    deadline = time.time() + 25
    while time.time() < deadline:
        if v._live_mode_card(page, "mode-composition-song-backing"):
            v.wait_streamlit_idle(page)
            return
        page.wait_for_timeout(250)
    raise RuntimeError("Composition Backing card not live")


def set_practice_key_e(page) -> bool:
    """Open the Practice / Concert Key selectbox and choose E; verify live value."""
    ok, _before, _after = pkh.select_practice_key_option(page, "E", v.wait_streamlit_idle)
    if ok:
        v.wait_streamlit(page, 1500)
    return ok


def main() -> int:
    failures = 0
    import _gate_workspace as gw

    _ws, start_url = gw.prepare_isolated_workspace("gate_practice_key_e", seed="empty")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        page.set_default_timeout(60_000)
        page.goto(start_url, wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        gw.land_songs_with_source_radio(page, v)

        v.ensure_songs(page)
        v.select_music_source(page, "Composition")
        v.wait_composition_hub_ready(page, timeout_ms=25000)

        text0 = v.body_text(page)
        widget0 = pkh.read_practice_key_widget_value(page)
        log(
            "baseline_original_c",
            _has_original_c(text0) or "My Composition" in text0,
            f"line={_practice_key_line(text0)!r} widget={widget0!r}",
        )

        # Change PK on Songs (product path). Re-clicking Composition after this
        # resets Practice Key to original C.
        changed = set_practice_key_e(page)
        widget = pkh.read_practice_key_widget_value(page)
        sidebar = pkh.read_sidebar_displayed_practice_key(page)
        songs_e = pkh.key_token_in_text(widget or sidebar, "E")
        log(
            "practice_key_set_e_songs",
            changed and songs_e,
            f"changed={changed} widget={widget!r} sidebar={sidebar!r}",
        )
        if not (changed and songs_e):
            failures += 1
            v.dump_debug(page, "practice_key_set_e")

        try:
            _open_composition_backing_keep_key(page)
        except Exception as exc:
            log("practice_key_open_backing", False, str(exc))
            failures += 1
            v.dump_debug(page, "practice_key_open_backing")

        text = v.body_text(page)
        html = v.body_html(page)
        has_e = _has_practice_e(text) or pkh.key_token_in_text(
            pkh.read_card_practice_key(text) or "", "E"
        )
        has_prog = _has_e_progression(text, html)
        orig_c = _has_original_c(text)
        ok_set = has_e and has_prog and orig_c
        log(
            "practice_key_set_e",
            ok_set,
            f"has_e={has_e} prog_E_Cshm_A_B={has_prog} original_c={orig_c} "
            f"pk={_practice_key_line(text)!r}",
        )
        if not ok_set:
            failures += 1
            v.dump_debug(page, "practice_key_set_e_backing")
        v.shot(page, "practice_e_before_refresh")

        page.reload(wait_until="domcontentloaded", timeout=180_000)
        v.wait_streamlit(page, 5000)
        try:
            _open_composition_backing_keep_key(page)
        except Exception as exc:
            log("practice_key_reopen_after_reload", False, str(exc))
            failures += 1
            v.dump_debug(page, "practice_key_reopen")
        text = v.body_text(page)
        html = v.body_html(page)
        still_e = _has_practice_e(text) or pkh.key_token_in_text(
            pkh.read_card_practice_key(text) or "", "E"
        )
        still_prog = _has_e_progression(text, html)
        still_orig = _has_original_c(text)
        ok_ref = still_e and still_prog and still_orig
        log(
            "practice_key_e_after_refresh",
            ok_ref,
            f"still_e={still_e} prog={still_prog} original_c={still_orig} "
            f"card={v._live_mode_card(page, 'mode-composition-song-backing')}",
        )
        if not ok_ref:
            failures += 1
            v.dump_debug(page, "practice_key_refresh")
        v.shot(page, "practice_e_after_refresh")

        # Songs → Backing coherence with E (do not reselect Composition radio)
        v.ensure_songs(page)
        try:
            _open_composition_backing_keep_key(page)
        except Exception as exc:
            log("practice_key_songs_backing_open", False, str(exc))
            failures += 1
        text = v.body_text(page)
        html = v.body_html(page)
        still_e2 = _has_practice_e(text) or pkh.key_token_in_text(
            pkh.read_card_practice_key(text) or "", "E"
        )
        still_prog2 = _has_e_progression(text, html)
        still_orig2 = _has_original_c(text)
        ok_nav = still_e2 and still_prog2 and still_orig2
        log(
            "practice_key_e_songs_backing",
            ok_nav,
            f"still_e={still_e2} prog={still_prog2} original_c={still_orig2}",
        )
        if not ok_nav:
            failures += 1
            v.dump_debug(page, "practice_key_songs_backing")
        v.shot(page, "practice_e_songs_backing")

        browser.close()

    (OUT / "practice_key_e_results.json").write_text(
        json.dumps(RESULTS, indent=2), encoding="utf-8"
    )
    print(f"Failures: {failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
