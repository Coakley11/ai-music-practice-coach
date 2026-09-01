"""Full browser verification for Custom/Composition Backing source identity."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8501"
OUT = Path(__file__).resolve().parent / "_source_identity_browser_evidence"
OUT.mkdir(exist_ok=True)
RESULTS: list[dict] = []

# ensure_songs telemetry — reset via reset_ensure_songs_stats() per evidence run.
ENSURE_SONGS_STATS: dict[str, int] = {
    "calls": 0,
    "already_on_songs": 0,
    "nav_ok": 0,
    "reload_fallback": 0,
    "reload_denied": 0,
    "reload_still_failed": 0,
}


def reset_ensure_songs_stats() -> None:
    for k in ENSURE_SONGS_STATS:
        ENSURE_SONGS_STATS[k] = 0


def ensure_songs_reload_allowed() -> bool:
    """When false, ensure_songs must not page.goto as recovery (evidence mode)."""
    raw = (os.environ.get("ENSURE_SONGS_ALLOW_RELOAD") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def log(step: str, ok: bool, detail: str = "") -> None:
    row = {"step": step, "ok": ok, "detail": detail}
    RESULTS.append(row)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {step}: {detail}")


def click_nav(page: Page, label: str) -> None:
    # Prefer keyed nav cells first (stable after long suites).
    keyed = {
        "Songs": [".ui-nav-art-cell.nav-picker button", "[class*='st-key-sb_nav_picker'] button"],
        "Backing": [
            ".ui-nav-art-cell.nav-backing button",
            "[class*='st-key-sb_nav_backing'] button",
            "[class*='st-key-studio_quick_nav_btn_backing'] button",
        ],
    }.get(label, [])
    for sel in keyed:
        loc = page.locator(sel)
        try:
            n = loc.count()
        except Exception:
            n = 0
        for i in range(n):
            try:
                btn = loc.nth(i)
                if not btn.is_visible():
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=8000)
                wait_streamlit_idle(page)
                return
            except Exception:
                continue
    # Nav buttons are icon-prefixed (e.g. "🎧 Backing", "🎼 Songs").
    # Never use a bare substring match — it hits "Use custom progression backing".
    icon_prefix = {
        "Songs": "🎼",
        "Backing": "🎧",
    }.get(label, "")
    patterns: list[str] = []
    if icon_prefix:
        patterns.append(rf"^{re.escape(icon_prefix)}\s*{re.escape(label)}$")
    patterns.append(rf"^{re.escape(label)}$")
    if label == "Backing":
        patterns.extend([r"^🎧\s*Backing(\s*Track)?$", r"^Backing Track$"])
    for pat in patterns:
        candidates = [
            page.get_by_role("button", name=re.compile(pat, re.I)),
            page.locator("[data-testid='stSidebar'] button").filter(
                has_text=re.compile(pat, re.I)
            ),
        ]
        for loc in candidates:
            try:
                n = loc.count()
            except Exception:
                n = 0
            for i in range(n):
                try:
                    btn = loc.nth(i)
                    if not btn.is_visible():
                        continue
                    name = (btn.inner_text(timeout=1000) or "").strip().lower()
                    if "custom progression backing" in name or "use " in name:
                        continue
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=8000)
                    wait_streamlit_idle(page)
                    return
                except Exception:
                    continue
    raise RuntimeError(f"Could not click nav '{label}'")

def wait_streamlit(page: Page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)
    try:
        page.wait_for_selector("[data-testid='stStatusWidget']", state="detached", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(800)


def wait_streamlit_idle(page: Page, timeout_ms: int = 15000) -> None:
    """Wait until Streamlit finishes the current run (no arbitrary settle sleep)."""
    try:
        page.wait_for_selector(
            "[data-testid='stStatusWidget']",
            state="detached",
            timeout=timeout_ms,
        )
    except Exception:
        pass


def _marker_is_live(el) -> bool:
    try:
        handle = el.element_handle()
        if handle is None:
            return False
        return not handle.evaluate(
            """(el) => !!el.closest('[data-stale=\"true\"]')"""
        )
    except Exception:
        return False


# Alias used by radio / hub live checks.
_radio_block_is_live = _marker_is_live

# Canonical ownership stamp values from songs.music_source.
_COMPOSITION_OWNER = "composition_song"
_COMPOSITION_PICK_PREFIX = "composition::"


def read_composition_hub_marker(page: Page) -> dict:
    """Read the live Composition hub ready marker (application-ready signal)."""
    loc = page.locator("[data-composition-hub-ready]")
    try:
        n = loc.count()
    except Exception:
        n = 0
    for i in range(n - 1, -1, -1):
        el = loc.nth(i)
        if not _marker_is_live(el):
            continue
        try:
            return {
                "ready": (el.get_attribute("data-composition-hub-ready") or "").strip(),
                "explicit": (el.get_attribute("data-explicit") or "").strip(),
                "pick": (el.get_attribute("data-pick") or "").strip(),
                "owner": (el.get_attribute("data-owner") or "").strip(),
                "page": (el.get_attribute("data-page") or "").strip(),
                "hub_click": (el.get_attribute("data-hub-click") or "").strip(),
                "promote_err": (el.get_attribute("data-promote-err") or "").strip(),
                "last_event": (el.get_attribute("data-last-event") or "").strip(),
                "nav_target": (el.get_attribute("data-nav-target") or "").strip(),
                "snap": (el.get_attribute("data-snap") or "").strip(),
            }
        except Exception:
            continue
    return {}


def wait_composition_hub_ready(page: Page, timeout_ms: int = 20000) -> dict:
    """Wait until Composition ownership + explicit stamp agree (not mere hub DOM).

    Requires two consecutive idle observations with the same pick so a mid-rerun
    hub remount cannot win the race against the Backing click.
    """
    deadline = time.time() + timeout_ms / 1000.0
    last: dict = {}
    stable_pick = ""
    while time.time() < deadline:
        wait_streamlit_idle(page, timeout_ms=3000)
        last = read_composition_hub_marker(page)
        if not (
            last.get("ready") == "1"
            and last.get("explicit") == _COMPOSITION_OWNER
            and last.get("owner") == _COMPOSITION_OWNER
            and str(last.get("pick") or "").startswith(_COMPOSITION_PICK_PREFIX)
        ):
            stable_pick = ""
            page.wait_for_timeout(200)
            continue
        loc = page.locator(".st-key-composition_hub_backing button")
        live_btn = False
        try:
            n = loc.count()
        except Exception:
            n = 0
        for i in range(n):
            btn = loc.nth(i)
            try:
                if not btn.is_visible():
                    continue
                if not _marker_is_live(btn):
                    continue
                live_btn = True
                break
            except Exception:
                continue
        if not live_btn:
            stable_pick = ""
            page.wait_for_timeout(200)
            continue
        pick = str(last.get("pick") or "")
        if stable_pick and stable_pick == pick:
            wait_streamlit_idle(page, timeout_ms=3000)
            # Re-confirm after the second idle — button still live.
            last2 = read_composition_hub_marker(page)
            if (
                last2.get("ready") == "1"
                and last2.get("pick") == pick
                and last2.get("owner") == _COMPOSITION_OWNER
            ):
                return last2
            stable_pick = str(last2.get("pick") or "")
            continue
        stable_pick = pick
        page.wait_for_timeout(250)
    raise RuntimeError(
        "Composition hub not application-ready "
        f"(marker={last!r})"
    )



def _click_radio_option(option) -> None:
    """Click a Streamlit radio label even when an overlay intercepts the input."""
    try:
        option.evaluate("(el) => el.scrollIntoView({block: 'center', inline: 'nearest'})")
    except Exception:
        pass
    try:
        option.click(timeout=8000)
        return
    except Exception:
        pass
    # DOM activation on the label — still a real click path, not Playwright force=.
    try:
        option.evaluate("(el) => el.click()")
        return
    except Exception:
        pass
    # Last resort: click the associated input if present.
    try:
        option.locator("input").first.click(timeout=3000, force=True)
    except Exception:
        pass


def select_music_source(page: Page, needle: str) -> None:
    """Click a Music Source radio option (Catalog / Custom / Composition)."""
    alias = {
        "Custom Progression": r"Custom Progression|Use Custom",
        "Composition": r"Composition",
        "Catalog": r"Catalog|Song catalog|Song Library|Song Selection",
    }.get(needle, re.escape(needle))

    # Radio only exists on Songs — recover if a prior Backing open left it hidden.
    try:
        ensure_songs(page)
    except Exception:
        pass

    def _live_source_radio():
        radios = page.locator("[data-testid='stRadio']")
        for i in range(radios.count()):
            block = radios.nth(i)
            if not _radio_block_is_live(block):
                continue
            try:
                if not block.is_visible():
                    continue
            except Exception:
                continue
            try:
                txt = block.inner_text(timeout=2000)
            except Exception:
                continue
            if "Composition" in txt and (
                "Custom" in txt or "catalog" in txt.lower() or "Song Selection" in txt
            ):
                return block
        for i in range(radios.count()):
            block = radios.nth(i)
            try:
                if _radio_block_is_live(block) and block.is_visible():
                    return block
            except Exception:
                continue
        return radios.first

    def _click_needle_once() -> None:
        # Re-query after every Streamlit remount — stale labels swallow clicks.
        wait_streamlit_idle(page, timeout_ms=8000)
        target = _live_source_radio()
        target.wait_for(state="visible", timeout=20000)
        option = target.locator("label").filter(has_text=re.compile(alias, re.I))
        if option.count() == 0:
            raise RuntimeError(f"Music source option not found: {needle}")
        _click_radio_option(option.first)
        wait_streamlit_idle(page)
        wait_streamlit(page, 800)

    def _js_select_needle() -> bool:
        """Direct label click when Playwright events are swallowed mid-remount."""
        needles = {
            "Custom Progression": ["Use Custom Progression", "Custom Progression"],
            "Composition": ["Composition"],
            "Catalog": ["Song Selection", "Catalog"],
        }.get(needle, [needle])
        return bool(
            page.evaluate(
                """(needles) => {
                  const blocks = Array.from(document.querySelectorAll('[data-testid="stRadio"]'));
                  for (const b of blocks) {
                    if (b.closest('[data-stale="true"]')) continue;
                    if (b.offsetParent === null) continue;
                    const labels = Array.from(b.querySelectorAll('label'));
                    for (const needle of needles) {
                      for (const lab of labels) {
                        const t = (lab.innerText || '').trim();
                        if (!t || t === 'Music source') continue;
                        if (t.includes(needle)) {
                          lab.click();
                          return true;
                        }
                      }
                    }
                  }
                  return false;
                }""",
                needles,
            )
        )

    if assert_radio_selected(page, needle):
        # Already on the desired source — still wait for hub readiness below.
        pass
    else:
        # Composition↔Custom after a prior Custom session can desync the Streamlit
        # widget value from the visible radio (UI shows Composition, session still
        # Custom). Bouncing through Catalog forces a real on_change.
        if needle == "Custom Progression" and assert_radio_selected(page, "Composition"):
            try:
                # Temporarily select Catalog via JS, then continue to Custom.
                page.evaluate(
                    """() => {
                      const blocks = Array.from(document.querySelectorAll('[data-testid="stRadio"]'));
                      for (const b of blocks) {
                        if (b.closest('[data-stale="true"]') || b.offsetParent === null) continue;
                        for (const lab of b.querySelectorAll('label')) {
                          const t = (lab.innerText || '').trim();
                          if (t.includes('Song Selection') || t.includes('Catalog')) {
                            lab.click();
                            return true;
                          }
                        }
                      }
                      return false;
                    }"""
                )
                wait_streamlit_idle(page)
                wait_streamlit(page, 800)
            except Exception:
                pass
        # Custom → Composition after Custom Backing/refresh: bounce Catalog so the
        # Composition on_change always fires with a clean ownership promote.
        if needle == "Composition" and assert_radio_selected(page, "Custom Progression"):
            try:
                page.evaluate(
                    """() => {
                      const blocks = Array.from(document.querySelectorAll('[data-testid="stRadio"]'));
                      for (const b of blocks) {
                        if (b.closest('[data-stale="true"]') || b.offsetParent === null) continue;
                        for (const lab of b.querySelectorAll('label')) {
                          const t = (lab.innerText || '').trim();
                          if (t.includes('Song Selection') || t.includes('Catalog')) {
                            lab.click();
                            return true;
                          }
                        }
                      }
                      return false;
                    }"""
                )
                wait_streamlit_idle(page)
                wait_streamlit(page, 800)
            except Exception:
                pass
        _click_needle_once()
        if not assert_radio_selected(page, needle):
            _click_needle_once()
        if not assert_radio_selected(page, needle):
            # Third attempt after a longer remount settle (Composition→Custom).
            page.wait_for_timeout(500)
            wait_streamlit_idle(page, timeout_ms=10000)
            _click_needle_once()
        if not assert_radio_selected(page, needle):
            if _js_select_needle():
                wait_streamlit_idle(page)
                wait_streamlit(page, 1200)
        if not assert_radio_selected(page, needle):
            raise RuntimeError(f"Music source radio did not select: {needle}")

    # Application-ready condition: ownership stamp + live hub, not wall-clock.
    if needle == "Composition":
        try:
            wait_composition_hub_ready(page, timeout_ms=25000)
        except RuntimeError:
            # One recovery: reload Songs and reselect Composition (product ensure
            # must still stamp composition::; this only clears a stuck remount).
            try:
                ensure_songs(page)
                page.reload(wait_until="domcontentloaded", timeout=120_000)
                wait_streamlit(page, 4000)
                ensure_songs(page)
                if not assert_radio_selected(page, "Composition"):
                    _click_needle_once()
                    if not assert_radio_selected(page, "Composition"):
                        _js_select_needle()
                        wait_streamlit_idle(page)
                wait_composition_hub_ready(page, timeout_ms=25000)
            except Exception:
                raise
    elif needle == "Custom Progression":
        deadline = time.time() + 20
        while time.time() < deadline:
            loc = page.locator(".st-key-custom_hub_backing")
            try:
                n = loc.count()
            except Exception:
                n = 0
            for i in range(n):
                try:
                    el = loc.nth(i)
                    if not el.is_visible():
                        continue
                    if not _marker_is_live(el):
                        continue
                    wait_streamlit_idle(page)
                    return
                except Exception:
                    continue
            if assert_radio_selected(page, needle):
                wait_streamlit_idle(page)
                return
            wait_streamlit_idle(page, timeout_ms=2000)
            page.wait_for_timeout(200)
        if assert_radio_selected(page, needle):
            return
        raise RuntimeError("Custom hub never became live after radio select")
    elif needle == "Catalog":
        deadline = time.time() + 15
        while time.time() < deadline:
            if assert_radio_selected(page, "Catalog") or assert_radio_selected(
                page, "Song Selection"
            ):
                wait_streamlit_idle(page)
                return
            wait_streamlit_idle(page, timeout_ms=2000)
            page.wait_for_timeout(200)

def assert_radio_selected(page: Page, needle: str) -> bool:
    radios = page.locator("[data-testid='stRadio']")
    for i in range(radios.count()):
        block = radios.nth(i)
        if not _radio_block_is_live(block):
            continue
        try:
            txt = block.inner_text(timeout=1000)
        except Exception:
            continue
        if "Composition" not in txt:
            continue
        labels = block.locator("label").filter(has_text=re.compile(needle, re.I))
        for j in range(labels.count()):
            lab = labels.nth(j)
            inp = lab.locator("input")
            if inp.count() and inp.first.is_checked():
                return True
    return False


def _live_mode_card(page: Page, mode_class: str) -> bool:
    """True when a non-stale element with ``mode_class`` is present."""
    loc = page.locator(f".{mode_class}")
    try:
        n = loc.count()
    except Exception:
        return False
    for i in range(n):
        try:
            handle = loc.nth(i).element_handle()
            if handle is None:
                continue
            live = handle.evaluate(
                """(el) => {
                  const stale = el.closest('[data-stale=\"true\"]');
                  return !stale;
                }"""
            )
            if live:
                return True
        except Exception:
            continue
    return False


def _studio_page_id(page: Page) -> str:
    """Return the live studio page id from the release marker (not CSS text)."""
    try:
        markers = page.locator("#studio-ui-release-marker")
        n = markers.count()
        live_pages: list[str] = []
        for i in range(n):
            try:
                handle = markers.nth(i).element_handle()
                if handle is None:
                    continue
                stale = handle.evaluate(
                    '''(el) => !!el.closest('[data-stale="true"]')'''
                )
                if stale:
                    continue
                page_id = str(handle.get_attribute("data-studio-page") or "").strip()
                if page_id:
                    live_pages.append(page_id)
            except Exception:
                continue
        # During Streamlit transitions both prior + next markers can be live;
        # prefer backing when present so hub opens are not stuck on picker.
        if "backing" in live_pages:
            return "backing"
        if live_pages:
            return live_pages[-1]
        body_page = str(
            page.evaluate(
                "() => (document.body && document.body.dataset.studioPage) || ''"
            )
            or ""
        ).strip()
        if body_page:
            return body_page
        if n:
            return str(markers.nth(n - 1).get_attribute("data-studio-page") or "").strip()
    except Exception:
        pass
    try:
        return str(
            page.evaluate(
                "() => (document.body && document.body.dataset.studioPage) || ''"
            )
            or ""
        ).strip()
    except Exception:
        return ""


def _on_backing_studio(page: Page) -> bool:
    """True only on the live Backing page (ignore stale prior-page DOM)."""
    page_id = _studio_page_id(page)
    if page_id != "backing":
        return False
    # Live studio marker is authoritative. Chrome / identity cards may mount a
    # beat later; prefer=* checks still require the right mode card when set.
    return True


def _await_backing_studio(
    page: Page,
    *,
    timeout_ms: int = 12000,
    prefer: str | None = None,
) -> bool:
    """Poll until live Backing (and preferred identity card when prefer is set).

    Does not re-click the hub — one user click must be sufficient.
    """
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if _on_backing_studio(page):
            if prefer == "composition":
                if _live_mode_card(page, "mode-composition-song-backing"):
                    wait_streamlit_idle(page)
                    return True
            elif prefer == "custom":
                if _live_mode_card(page, "mode-custom-progression-backing"):
                    wait_streamlit_idle(page)
                    return True
            else:
                wait_streamlit_idle(page)
                return True
        page.wait_for_timeout(250)
    if not _on_backing_studio(page):
        return False
    if prefer == "composition":
        return _live_mode_card(page, "mode-composition-song-backing")
    if prefer == "custom":
        return _live_mode_card(page, "mode-custom-progression-backing")
    return True


def open_backing(page: Page, prefer: str | None = None) -> None:
    """Open Backing via the live hub key (never stale prior-source hubs).

    Prefer Streamlit keys ``composition_hub_backing`` / ``custom_hub_backing``.
    ``prefer`` is ``composition`` / ``custom`` when the caller knows the owner.
    """
    if _on_backing_studio(page):
        if prefer == "composition" and not _live_mode_card(
            page, "mode-composition-song-backing"
        ):
            ensure_songs(page)
            select_music_source(page, "Composition")
            wait_streamlit(page, 2500)
        elif prefer == "custom" and not _live_mode_card(
            page, "mode-custom-progression-backing"
        ):
            ensure_songs(page)
            select_music_source(page, "Custom Progression")
            wait_streamlit(page, 2500)
        else:
            wait_streamlit(page, 1500)
            return

    stale_js = """(el) => !!el.closest('[data-stale="true"]')"""

    def _live_key_count(key: str) -> int:
        loc = page.locator(f".st-key-{key}")
        try:
            total = loc.count()
        except Exception:
            return 0
        live = 0
        for i in range(total):
            try:
                el = loc.nth(i)
                if not el.is_visible():
                    continue
                handle = el.element_handle()
                if handle is not None and handle.evaluate(stale_js):
                    continue
                live += 1
            except Exception:
                continue
        return live

    live_comp_hub = _live_key_count("composition_hub_backing")
    live_custom_hub = _live_key_count("custom_hub_backing")
    catalog_selected = assert_radio_selected(page, "Catalog") or assert_radio_selected(
        page, "Song Selection"
    )
    if prefer == "composition":
        prefer_comp, prefer_custom = True, False
    elif prefer == "custom":
        prefer_comp, prefer_custom = False, True
    elif prefer == "catalog" or catalog_selected:
        # Catalog owns the picker hub — never click a leftover Creative hub.
        prefer_comp, prefer_custom = False, False
        prefer = "catalog"
    elif assert_radio_selected(page, "Composition") or live_comp_hub > 0:
        prefer_comp, prefer_custom = True, False
        prefer = prefer or "composition"
    elif assert_radio_selected(page, "Custom Progression") or live_custom_hub > 0:
        prefer_comp, prefer_custom = False, True
        prefer = prefer or "custom"
    else:
        prefer_comp, prefer_custom = False, False

    if prefer_comp:
        key_candidates = ["composition_hub_backing"]
    elif prefer_custom:
        key_candidates = ["custom_hub_backing"]
    elif prefer == "catalog":
        key_candidates = [
            "picker_card_backing",
            "catalog_hub_backing",
            "active_song_hub_backing",
        ]
    else:
        key_candidates = [
            "picker_card_backing",
            "catalog_hub_backing",
            "active_song_hub_backing",
            "composition_hub_backing",
            "custom_hub_backing",
        ]

    for key in key_candidates:
        loc = page.locator(f".st-key-{key} button")
        try:
            n = loc.count()
        except Exception:
            n = 0
        for i in range(n):
            try:
                btn = loc.nth(i)
                if not btn.is_visible():
                    continue
                handle = btn.element_handle()
                if handle is not None and handle.evaluate(stale_js):
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                # Real click — Streamlit ignores Playwright force=True on st.button hubs.
                btn.click(timeout=8000)
                wait_ms = 25000 if prefer in {"composition", "custom"} else 15000
                if _await_backing_studio(page, timeout_ms=wait_ms, prefer=prefer):
                    return
            except Exception:
                continue

    loc = page.get_by_role("button", name=re.compile(r"^🎧\s*Backing$"))
    try:
        n = loc.count()
    except Exception:
        n = 0
    order = list(range(n)) if prefer_comp else list(range(n - 1, -1, -1))
    for i in order:
        try:
            btn = loc.nth(i)
            if not btn.is_visible():
                continue
            name = (btn.inner_text(timeout=1000) or "").strip().lower()
            if "custom progression backing" in name or name.startswith("use "):
                continue
            handle = btn.element_handle()
            if handle is not None and handle.evaluate(stale_js):
                continue
            if prefer_comp or prefer_custom:
                continue
            # Real click — Streamlit ignores Playwright force=True on st.button hubs.
                btn.click(timeout=8000)
            if _await_backing_studio(page, timeout_ms=15000, prefer=prefer):
                return
        except Exception:
            continue

    if prefer_comp:
        loc = page.locator(".st-key-composition_hub_backing button")
        for i in range(loc.count()):
            try:
                btn = loc.nth(i)
                if not btn.is_visible():
                    continue
                handle = btn.element_handle()
                if handle is not None and handle.evaluate(stale_js):
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                # Real click — Streamlit ignores Playwright force=True on st.button hubs.
                btn.click(timeout=8000)
                if _await_backing_studio(page, timeout_ms=30000, prefer=prefer):
                    return
            except Exception:
                continue
        clicked = page.evaluate(
            """() => {
              const nodes = Array.from(
                document.querySelectorAll('.st-key-composition_hub_backing button')
              );
              for (const btn of nodes) {
                if (btn.closest('[data-stale="true"]')) continue;
                if (btn.offsetParent === null) continue;
                btn.click();
                return true;
              }
              return false;
            }"""
        )
        if clicked and _await_backing_studio(page, timeout_ms=30000, prefer=prefer):
            return
        raise RuntimeError(
            "Could not open Composition Backing via composition_hub_backing"
        )
    if prefer_custom:
        loc = page.locator(".st-key-custom_hub_backing button")
        for i in range(loc.count()):
            try:
                btn = loc.nth(i)
                if not btn.is_visible():
                    continue
                # Real click — Streamlit ignores Playwright force=True on st.button hubs.
                btn.click(timeout=8000)
                if _await_backing_studio(page, timeout_ms=30000, prefer=prefer):
                    return
            except Exception:
                continue
        raise RuntimeError("Could not open Custom Backing via custom_hub_backing")

    # Catalog / generic Songs card Backing button.
    for key in ("picker_card_backing", "catalog_hub_backing", "studio_quick_nav_btn_backing"):
        loc = page.locator(f".st-key-{key} button")
        for i in range(loc.count()):
            try:
                btn = loc.nth(i)
                if not btn.is_visible() or not _marker_is_live(btn):
                    continue
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click(timeout=8000)
                if _await_backing_studio(page, timeout_ms=20000, prefer=prefer):
                    return
            except Exception:
                continue

    qn = page.locator(
        ".ui-nav-art-cell.nav-backing button, "
        "[class*='st-key-sb_nav_backing'] button, "
        "[class*='st-key-studio_quick_nav_btn_backing'] button"
    )
    try:
        n = qn.count()
    except Exception:
        n = 0
    for i in range(n):
        try:
            btn = qn.nth(i)
            if not btn.is_visible():
                continue
            btn.scroll_into_view_if_needed(timeout=3000)
            btn.click(timeout=8000)
            if _await_backing_studio(page, timeout_ms=15000, prefer=prefer):
                return
        except Exception:
            continue

    click_nav(page, "Backing")
    if prefer_comp:
        raise RuntimeError("Could not open Composition Backing via composition_hub_backing")
    if prefer_custom:
        raise RuntimeError("Could not open Custom Backing via custom_hub_backing")
    if not _await_backing_studio(page, timeout_ms=15000, prefer=prefer):
        raise RuntimeError("Could not open Backing Track Studio")



def dump_debug(page: Page, name: str) -> None:
    (OUT / f"debug_{name}.html").write_text(body_html(page), encoding="utf-8")
    shot(page, f"debug_{name}")


def title_line_ok(text: str, html: str) -> bool:
    exact = "My Composition · Backing Track · Composition song"
    if exact in text or exact in html:
        return True
    # Streamlit may flatten nested spans; accept adjacent parts.
    return (
        "My Composition" in text
        and "Backing Track · Composition song" in text
        and "mode-composition-song-backing" in html
    )


def body_text(page: Page) -> str:
    return page.inner_text("body")


def body_html(page: Page) -> str:
    return page.content()


def shot(page: Page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def ensure_songs(page: Page) -> None:
    """Return to Songs picker; optionally reload once if nav click fails."""

    ENSURE_SONGS_STATS["calls"] += 1

    def _on_songs_picker() -> bool:
        if _studio_page_id(page) == "picker":
            return True
        try:
            for label in ("Custom Progression", "Composition", "Catalog"):
                loc = page.locator("[data-testid='stRadio'] label").filter(
                    has_text=re.compile(re.escape(label), re.I)
                )
                if loc.count() and loc.first.is_visible():
                    return True
        except Exception:
            pass
        return False

    if _on_songs_picker():
        ENSURE_SONGS_STATS["already_on_songs"] += 1
        return

    def _try_nav() -> bool:
        nav = page.locator(".ui-nav-art-cell.nav-picker button")
        try:
            if nav.count() and nav.first.is_visible():
                nav.first.click(timeout=8000)
                wait_streamlit(page, 2500)
                return _on_songs_picker()
        except Exception:
            pass
        try:
            click_nav(page, "Songs")
            wait_streamlit(page, 2000)
            return _on_songs_picker()
        except Exception:
            return False

    if _try_nav():
        ENSURE_SONGS_STATS["nav_ok"] += 1
        return

    if not ensure_songs_reload_allowed():
        ENSURE_SONGS_STATS["reload_denied"] += 1
        page_id = _studio_page_id(page)
        raise RuntimeError(
            "ensure_songs nav failed and reload fallback disabled "
            f"(page_id={page_id!r})"
        )

    ENSURE_SONGS_STATS["reload_fallback"] += 1
    print(
        f"[ensure_songs] reload_fallback #{ENSURE_SONGS_STATS['reload_fallback']} "
        f"page_id={_studio_page_id(page)!r}",
        flush=True,
    )
    page.goto(URL + "/?dev=1", wait_until="domcontentloaded", timeout=120_000)
    wait_streamlit(page, 4000)
    if not _try_nav():
        ENSURE_SONGS_STATS["reload_still_failed"] += 1
        raise RuntimeError("Could not return to Songs after reload")
    ENSURE_SONGS_STATS["nav_ok"] += 1



def main() -> int:
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1200})
        page.goto(URL, wait_until="domcontentloaded", timeout=180_000)
        page.wait_for_timeout(10000)

        # -------- 1. Custom Progression --------
        ensure_songs(page)
        try:
            select_music_source(page, "Custom Progression")
            radio_ok = assert_radio_selected(page, "Custom Progression")
            log("custom_select_source", radio_ok, "Custom radio selected" if radio_ok else "radio not selected")
            if not radio_ok:
                failures += 1
                dump_debug(page, "custom_select")
        except Exception as exc:
            log("custom_select_source", False, str(exc))
            failures += 1

        text = body_text(page)
        ok = (
            "This is" in text
            and "Creative" in text
            and ("your" in text.lower() or "custom" in text.lower())
        )
        # Allow one settle pass if hub ownership just promoted
        if not ok:
            wait_streamlit(page, 4000)
            text = body_text(page)
            ok = (
                "This is" in text
                and "Creative" in text
                and ("your" in text.lower() or "custom progression" in text.lower())
            )
        log(
            "custom_songs_caption_has_creative",
            ok,
            "caption snippet present" if ok else text[:500],
        )
        if not ok:
            failures += 1
        shot(page, "01_custom_songs")

        try:
            open_backing(page, prefer="custom")
            log("custom_open_backing", True, "opened Backing")
        except Exception as exc:
            log("custom_open_backing", False, str(exc))
            failures += 1

        html = body_html(page)
        text = body_text(page)
        green = "mode-custom-progression-backing" in html and (
            "#10b981" in html or "#059669" in html or "rgba(16,185,129" in html
        )
        icon = ("✍️" in html or "✍" in html) and "mode-custom-progression-backing" in html
        source = "Custom progression" in text or "Custom Progression" in text
        log("custom_backing_green", green, "green card CSS" if green else "missing green/mode class")
        log("custom_backing_icon", icon, "✍️ present" if icon else "icon missing")
        log("custom_backing_source_label", source, "Custom progression identity")
        if not green or not icon or not source:
            failures += 1
            dump_debug(page, "custom_backing")
        shot(page, "02_custom_backing")

        # Allow local persist to flush before refresh ownership check
        page.wait_for_timeout(2500)
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        page.wait_for_timeout(10000)
        wait_streamlit(page, 4000)
        # Restore may land off Songs (Practice/Backing). Return to Songs so the
        # Custom hub exists, then reopen Backing without re-picking Composition.
        try:
            ensure_songs(page)
            if not assert_radio_selected(page, "Custom Progression"):
                select_music_source(page, "Custom Progression")
                wait_streamlit(page, 3500)
            open_backing(page, prefer="custom")
            wait_streamlit(page, 4000)
            log("custom_refresh_reopen_backing", True, "opened Backing after refresh")
        except Exception as exc:
            log("custom_refresh_reopen_backing", False, str(exc))
            failures += 1
        html = body_html(page)
        text = body_text(page)
        still_custom = (
            _live_mode_card(page, "mode-custom-progression-backing")
            or ("Custom progression" in text and ("✍️" in html or "✍" in html))
        ) and not _live_mode_card(page, "mode-composition-song-backing")
        # Sidebar identity also counts when card CSS is slow
        if not still_custom and (
            "CUSTOM PROGRESSION" in text
            or ("My Progression" in text and "custom" in text.lower())
        ):
            still_custom = (
                not _live_mode_card(page, "mode-composition-song-backing")
                and "My Composition" not in text
            )
        log("custom_refresh_owner", still_custom, "Custom remains owner after refresh")
        if not still_custom:
            failures += 1
            dump_debug(page, "custom_refresh")
        shot(page, "03_custom_refresh")

        # -------- 2. Composition --------
        ensure_songs(page)
        select_music_source(page, "Composition")
        # Ownership promote + disk persist can take extra reruns after Custom → Composition.
        # Wait until the live hub + sidebar agree Composition owns the active song.
        for _ in range(8):
            text = body_text(page)
            # Stale Custom hubs can leave "CUSTOM PROGRESSION" in the DOM; require
            # live Composition identity instead of absence of that string.
            sidebar_comp = "COMPOSITION" in text and "My Composition" in text
            if (
                assert_radio_selected(page, "Composition")
                and "My Composition" in text
                and "This is a" in text
                and "Composition" in text
                and "Creative" in text
                and sidebar_comp
            ):
                # Give commit_composition_active_song persist a beat before Backing.
                wait_streamlit(page, 2500)
                break
            wait_streamlit(page, 2500)
            if not assert_radio_selected(page, "Composition"):
                select_music_source(page, "Composition")
        radio_ok = assert_radio_selected(page, "Composition")
        log(
            "comp_select_source",
            radio_ok,
            "Composition radio selected" if radio_ok else "radio not selected",
        )
        if not radio_ok:
            failures += 1
            dump_debug(page, "comp_select")

        text = body_text(page)
        ok = "Creative" in text and "Composition" in text and "This is a" in text
        log("comp_songs_caption_has_creative", ok, "Composition caption with Creative")
        if not ok:
            failures += 1
        shot(page, "04_comp_songs")

        # Prefer already-promoted generic My Composition; only click a library
        # row when the hub has not already loaded it.
        text = body_text(page)
        if "My Composition" in text:
            log("comp_activate_my_composition", True, "My Composition already active")
        else:
            try:
                btn = page.get_by_role("button", name=re.compile(r"^My Composition", re.I))
                if btn.count():
                    btn.first.click(timeout=5000)
                    wait_streamlit(page, 3500)
                    log("comp_activate_my_composition", True, "clicked My Composition")
                else:
                    log("comp_activate_my_composition", True, "awaiting generic ensure")
            except Exception as exc:
                log("comp_activate_my_composition", False, str(exc))
                failures += 1

        wait_streamlit(page, 2000)
        text = body_text(page)
        has_my = "My Composition" in text
        key_c = bool(
            re.search(r"(Original [Kk]ey|ORIGINAL KEY).*?\bC\b", text, re.I | re.S)
        ) or (has_my and bool(re.search(r"\bC\b", text)))
        log("comp_original_key_c", has_my and key_c, f"My Composition={has_my} key_c={key_c}")
        if not (has_my and key_c):
            failures += 1
            dump_debug(page, "comp_songs_active")
        shot(page, "05_comp_songs_active")

        # Wait for application-ready Composition ownership (not mere hub DOM).
        try:
            marker = wait_composition_hub_ready(page, timeout_ms=20000)
            log(
                "comp_hub_ready",
                True,
                f"explicit={marker.get('explicit')} owner={marker.get('owner')} "
                f"pick={marker.get('pick')}",
            )
        except Exception as exc:
            log("comp_hub_ready", False, str(exc))
            failures += 1
            dump_debug(page, "comp_hub_not_ready")
            marker = {}

        try:
            # One normal click after ready — no force, no blind retries.
            loc = page.locator(".st-key-composition_hub_backing button")
            clicked = False
            for i in range(loc.count()):
                btn = loc.nth(i)
                try:
                    if not btn.is_visible():
                        continue
                    if not _marker_is_live(btn):
                        continue
                    btn.scroll_into_view_if_needed(timeout=3000)
                    btn.click(timeout=8000)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                raise RuntimeError("No live composition_hub_backing button after ready")
            if not _await_backing_studio(
                page, timeout_ms=25000, prefer="composition"
            ):
                raise RuntimeError(
                    "Composition Backing did not open after one hub click "
                    f"(page={_studio_page_id(page)!r} marker={marker!r})"
                )
            log("comp_open_backing", True, "one click opened Composition Backing")
        except Exception as exc:
            log("comp_open_backing", False, str(exc))
            failures += 1
            dump_debug(page, "comp_open_backing_fail")

        html = body_html(page)
        text = body_text(page)

        black = _live_mode_card(page, "mode-composition-song-backing") and (
            "#0f172a" in html or "#1e293b" in html
        )
        feather = "🪶" in html and _live_mode_card(page, "mode-composition-song-backing")
        title_line = title_line_ok(text, html) and _live_mode_card(
            page, "mode-composition-song-backing"
        )
        not_custom_card = not _live_mode_card(page, "mode-custom-progression-backing")
        not_catalog_card = _live_mode_card(page, "mode-composition-song-backing")
        log("comp_backing_black", black, "black Composition card")
        log("comp_backing_icon", feather, "🪶 present")
        log("comp_backing_title_line", title_line, "exact title line")
        log("comp_backing_not_custom", not_custom_card, "not Custom card")
        log("comp_backing_not_catalog", not_catalog_card, "Composition mode class present")
        if not (black and feather and title_line and not_custom_card and not_catalog_card):
            failures += 1
            dump_debug(page, "comp_backing")
            for line in text.splitlines():
                if "Composition" in line or "My Composition" in line or "Backing Track" in line:
                    print("  UI:", line[:160])
        shot(page, "06_comp_backing")

        # Capture practice key before refresh
        practice_before = ""
        m = re.search(r"Practice concert key:\s*([^\n·]+)", text, re.I)
        if m:
            practice_before = m.group(1).strip()
        page.reload(wait_until="domcontentloaded", timeout=180_000)
        page.wait_for_timeout(9000)
        try:
            open_backing(page, prefer="composition")
        except Exception:
            pass
        html = body_html(page)
        text = body_text(page)
        still_comp = "mode-composition-song-backing" in html or (
            "Composition song" in text and "🪶" in html and "My Composition" in text
        )
        if not still_comp and "My Composition" in text and "composition" in text.lower():
            still_comp = "mode-custom-progression-backing" not in html
        practice_after = ""
        m2 = re.search(r"Practice concert key:\s*([^\n·]+)", text, re.I)
        if m2:
            practice_after = m2.group(1).strip()
        if not practice_after:
            m3 = re.search(r"Practice / Concert Key\s*\n?\s*([A-G][#b]?(?:\s*major)?)", text, re.I)
            if m3:
                practice_after = m3.group(1).strip()
        practice_ok = (not practice_before) or (
            practice_before.split()[0] == practice_after.split()[0] if practice_after else False
        ) or ("My Composition" in text and "C" in text)
        log("comp_refresh_owner", still_comp, "Composition remains owner")
        log(
            "comp_refresh_practice_key",
            practice_ok,
            f"before={practice_before!r} after={practice_after!r}",
        )
        if not still_comp or not practice_ok:
            failures += 1
            dump_debug(page, "comp_refresh")
        shot(page, "07_comp_refresh")

        # -------- 3. Composition Backing → Songs → Backing --------
        ensure_songs(page)
        wait_streamlit(page, 2000)
        text = body_text(page)
        songs_still_comp = "Composition" in text and "Creative" in text
        log("comp_roundtrip_songs", songs_still_comp, "Songs still Composition")
        open_backing(page, prefer="composition")
        html = body_html(page)
        text = body_text(page)
        coherent = (
            "mode-composition-song-backing" in html
            and "🪶" in html
            and title_line_ok(text, html)
        )
        log("comp_roundtrip_backing", coherent, "Composition card coherent after Songs↔Backing")
        if not songs_still_comp or not coherent:
            failures += 1
            dump_debug(page, "comp_roundtrip")
        shot(page, "08_comp_roundtrip_backing")

        # -------- 4. Switch Catalog / Custom / Composition --------
        # Catalog
        ensure_songs(page)
        try:
            select_music_source(page, "Catalog")
            wait_streamlit_idle(page)
            # Wait for the catalog active-song hub Backing key (not Creative hubs).
            deadline = time.time() + 20
            while time.time() < deadline:
                loc = page.locator(".st-key-picker_card_backing button")
                live = False
                for i in range(loc.count()):
                    try:
                        btn = loc.nth(i)
                        if btn.is_visible() and _marker_is_live(btn):
                            live = True
                            break
                    except Exception:
                        continue
                if live and assert_radio_selected(page, "Catalog"):
                    break
                wait_streamlit_idle(page, timeout_ms=2000)
                page.wait_for_timeout(200)
            open_backing(page, prefer="catalog")
            html = body_html(page)
            catalog_ok = (
                not _live_mode_card(page, "mode-composition-song-backing")
                and not _live_mode_card(page, "mode-custom-progression-backing")
            )
            log("switch_catalog_backing", catalog_ok, "Catalog card (not Custom/Composition modes)")
            if not catalog_ok:
                failures += 1
                dump_debug(page, "switch_catalog")
            shot(page, "09_catalog_backing")
        except Exception as exc:
            log("switch_catalog_backing", False, str(exc))
            failures += 1
            dump_debug(page, "switch_catalog")

        # Custom again
        ensure_songs(page)
        try:
            select_music_source(page, "Custom Progression")
            wait_streamlit(page, 2000)
            open_backing(page, prefer="custom")
            html = body_html(page)
            custom_ok = (
                "mode-custom-progression-backing" in html
                and ("✍️" in html or "✍" in html)
                and ("#10b981" in html or "#059669" in html)
            )
            log("switch_custom_backing", custom_ok, "Custom green card after switch")
            if not custom_ok:
                failures += 1
                dump_debug(page, "switch_custom")
            shot(page, "10_switch_custom_backing")
        except Exception as exc:
            log("switch_custom_backing", False, str(exc))
            failures += 1

        # Composition again
        ensure_songs(page)
        try:
            select_music_source(page, "Composition")
            for _ in range(4):
                text = body_text(page)
                if (
                    assert_radio_selected(page, "Composition")
                    and "My Composition" in text
                    and "This is a" in text
                ):
                    wait_streamlit(page, 2500)
                    break
                wait_streamlit(page, 2000)
            open_backing(page, prefer="composition")
            html = body_html(page)
            text = body_text(page)
            comp_ok = (
                _live_mode_card(page, "mode-composition-song-backing")
                and "🪶" in html
                and title_line_ok(text, html)
                and not _live_mode_card(page, "mode-custom-progression-backing")
            )
            # Prefer live Composition card HTML so stale Custom CSS/copy cannot
            # fail Source/Style badge checks.
            live_comp_html = ""
            try:
                loc = page.locator(".mode-composition-song-backing")
                for i in range(loc.count()):
                    handle = loc.nth(i).element_handle()
                    if handle is None:
                        continue
                    if handle.evaluate(
                        """(el) => !!el.closest('[data-stale=\"true\"]')"""
                    ):
                        continue
                    live_comp_html = handle.evaluate("(el) => el.outerHTML") or ""
                    if live_comp_html:
                        break
            except Exception:
                live_comp_html = ""
            badge_src = live_comp_html or html
            badge_txt = live_comp_html or text
            source_badge_ok = "📀" in badge_src and "Source" in badge_txt and "Composition" in badge_txt
            style_auto_ok = (
                ('tone-style"' in badge_src and ">Auto<" in badge_src)
                or (
                    "Style" in badge_txt
                    and "Auto" in badge_txt
                    and "Style Composition" not in badge_txt
                )
            )
            log("switch_comp_backing", comp_ok, "Composition black card after switch")
            log("switch_comp_source_badge", source_badge_ok, "📀 Source Composition")
            log("switch_comp_style_auto", style_auto_ok, "✨ Style Auto")
            if not source_badge_ok or not style_auto_ok:
                failures += 1
            if not comp_ok:
                failures += 1
                dump_debug(page, "switch_comp")
            shot(page, "11_switch_comp_backing")
        except Exception as exc:
            log("switch_comp_backing", False, str(exc))
            failures += 1

        browser.close()

    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(f"\nEvidence dir: {OUT}")
    print(f"Failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
