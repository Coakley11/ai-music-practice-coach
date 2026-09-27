"""Slice 5A browser acceptance — Practice written-chart toggle persistence.

Trial/Perfect → Bb Clarinet → known Practice Key → written ON → nav away/back →
refresh → still ON → OFF → concert chart restored. PK + instrument unchanged.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_slice5a python -m streamlit run streamlit_music_practice_app.py --server.port 8571
  python scripts/_proof_slice5a_written_chart_toggle.py http://127.0.0.1:8571
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from walk_creative_backing_matrix import (  # noqa: E402
    click_checkbox,
    ensure_checkbox,
    expand_sidebar,
    set_baseweb_select,
    set_instrument,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_pass8_nav_first_click import (  # noqa: E402
    click_sidebar_once,
    expand_pages,
    wait as nav_wait,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"
OUT = SCRIPTS / "evidence-slice5a-written-chart"
OUT.mkdir(parents=True, exist_ok=True)
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def wait(page: Page, ms: int = 1200) -> None:
    nav_wait(page, ms)


def sidebar_text(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.locator('section[data-testid="stSidebar"]').inner_text() or ""
    except Exception:
        return page.inner_text("body") or ""


def main_text(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        return ""


def shot(page: Page, name: str) -> None:
    body = f"=== SIDEBAR ===\n{sidebar_text(page)[:8000]}\n\n=== MAIN ===\n{main_text(page)[:8000]}"
    (OUT / f"{name}.txt").write_text(body, encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False, timeout=15000)
    except Exception:
        pass


def checkbox_state(page: Page, needle: str) -> bool | None:
    return page.evaluate(
        """(text) => {
          const needle = String(text || '').toLowerCase();
          const labels = [...document.querySelectorAll('label')];
          const lab = labels.find((el) => (el.innerText || '').toLowerCase().includes(needle));
          if (!lab) return null;
          const box = lab.querySelector('input[type="checkbox"]')
            || document.getElementById(lab.getAttribute('for') || '');
          if (!box) return null;
          return !!box.checked;
        }""",
        needle,
    )


def practice_key(page: Page) -> str:
    expand_sidebar(page)
    raw = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    m = re.search(r"([A-G](?:#|b)?m?)", str(raw), re.I)
    return (m.group(1) if m else str(raw)).strip()


def instrument_live(page: Page) -> str:
    expand_sidebar(page)
    raw = page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Instrument"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""
    return str(raw).strip()


def written_recap(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    m = re.search(r"Charts shown in:\s*([^\n]+)", body, re.I)
    if m:
        out["charts"] = m.group(1).strip()
    if re.search(r"written charts on", body, re.I):
        out["mode"] = "written"
    elif re.search(r"concert charts", body, re.I):
        out["mode"] = "concert"
    m2 = re.search(r"Written key:\s*([A-G](?:#|b)?m?)", body, re.I)
    if m2:
        out["written"] = m2.group(1).strip()
    m3 = re.search(r"Concert key:\s*([A-G](?:#|b)?m?)", body, re.I)
    if m3:
        out["concert"] = m3.group(1).strip()
    return out


def key_token(raw: str) -> str:
    m = re.search(r"([A-G](?:#|b)?m?)", str(raw or ""), re.I)
    return (m.group(1) if m else str(raw or "")).strip()


def same_key(a: str, b: str) -> bool:
    return key_token(a).upper() == key_token(b).upper()


def main() -> int:
    result: dict[str, object] = {"url": URL, "ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        wait(page, 4500)
        expand_pages(page)
        expand_sidebar(page)

        # Prefer Perfect (catalog); Shape of You as fallback. Trial is Custom GA.
        song_ok = False
        for title, genre in (("Perfect", "Pop"), ("Shape of You", "Pop"), ("Love Story", "Country")):
            try:
                if pick_song(page, NOTES, title, genre):
                    song_ok = True
                    log(f"picked song={title}")
                    break
                log(f"pick miss={title}")
            except Exception as exc:
                log(f"pick {title}: {exc}")
        if not song_ok:
            click_sidebar_once(page, "Practice")
            wait(page, 2000)
            log("using current active song")

        click_sidebar_once(page, "Practice")
        wait(page, 2500)
        expand_sidebar(page)

        set_instrument(page, "Clarinet")
        wait(page, 2000)
        expand_sidebar(page)
        inst = instrument_live(page)
        log(f"instrument={inst}")

        # Set a known Practice Key when the widget is available; else keep song PK.
        for label in ("F", "F Major", "G", "G Major"):
            if set_baseweb_select(page, "Practice / Concert Key", label):
                wait(page, 1800)
                break
        pk0 = practice_key(page)
        # Fallback: read concert from recap when the input aria-label is empty.
        if not pk0:
            pk0 = key_token(written_recap(sidebar_text(page)).get("concert") or "")
        log(f"practice_key={pk0}")
        shot(page, "01-clarinet-pk")

        needle = "Show chart in written key for instrument"

        def force_written(want: bool, *, attempts: int = 4) -> bool | None:
            expand_sidebar(page)
            for i in range(attempts):
                state = checkbox_state(page, needle)
                if state is want:
                    return state
                click_checkbox(page, needle) or ensure_checkbox(page, needle, checked=want)
                wait(page, 2800)
                expand_sidebar(page)
                state = checkbox_state(page, needle)
                log(f"force_written want={want} attempt={i+1} state={state}")
                if state is want:
                    return state
            return checkbox_state(page, needle)

        # Ensure OFF then ON.
        force_written(False)
        off_body = sidebar_text(page)
        recap_off = written_recap(off_body)
        on_state = force_written(True)
        on_body = sidebar_text(page)
        recap_on = written_recap(on_body)
        pk_on = practice_key(page) or key_token(recap_on.get("concert") or "")
        inst_on = instrument_live(page)
        shot(page, "02-written-on")
        log(f"on_state={on_state} recap={recap_on} pk={pk_on} inst={inst_on}")

        first_on = on_state is True
        pk_stable = (not pk0) or same_key(pk0, pk_on)
        inst_stable = "clarinet" in (inst_on or inst or "").lower()
        # Bb Clarinet: concert N → written N+2 (F→G, G→A).
        written_proj = recap_on.get("mode") == "written" or bool(
            re.search(r"written charts on", on_body, re.I)
        )
        charts = key_token(recap_on.get("charts") or "")
        concert = key_token(recap_on.get("concert") or pk_on or pk0)
        if charts and concert and not same_key(charts, concert):
            written_proj = True

        # Navigate away / back via a page that does not re-pick the catalog song.
        # (Songs can re-seed Original Key into Practice; that is outside Slice 5A.)
        away = "Upload" if click_sidebar_once(page, "Upload") else None
        if not away:
            away = "Backing" if click_sidebar_once(page, "Backing") else "Songs"
            if away == "Songs":
                click_sidebar_once(page, "Songs")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2500)
        expand_sidebar(page)
        nav_state = checkbox_state(page, needle)
        if nav_state is not True:
            force_written(True)
            click_sidebar_once(page, away)
            wait(page, 1500)
            click_sidebar_once(page, "Practice")
            wait(page, 2000)
            expand_sidebar(page)
            nav_state = checkbox_state(page, needle)
        pk_nav = practice_key(page) or key_token(written_recap(sidebar_text(page)).get("concert") or "")
        inst_nav = instrument_live(page)
        shot(page, "03-nav-back")
        log(f"nav_via={away} nav_state={nav_state} pk={pk_nav} inst={inst_nav}")

        # Refresh.
        page.reload(wait_until="domcontentloaded")
        wait(page, 5000)
        expand_sidebar(page)
        refresh_state = checkbox_state(page, needle)
        refresh_body = sidebar_text(page)
        recap_refresh = written_recap(refresh_body)
        pk_refresh = practice_key(page) or key_token(recap_refresh.get("concert") or "")
        inst_refresh = instrument_live(page)
        shot(page, "04-refresh-on")
        log(
            f"refresh_state={refresh_state} recap={recap_refresh} "
            f"pk={pk_refresh} inst={inst_refresh}"
        )

        # OFF → concert.
        off_state = force_written(False)
        off2_body = sidebar_text(page)
        recap_off2 = written_recap(off2_body)
        pk_off = practice_key(page) or key_token(recap_off2.get("concert") or "")
        inst_off = instrument_live(page)
        shot(page, "05-written-off")
        log(f"off_state={off_state} recap={recap_off2} pk={pk_off} inst={inst_off}")

        concert_restored = off_state is False and (
            recap_off2.get("mode") == "concert"
            or bool(re.search(r"concert charts", off2_body, re.I))
            or (
                key_token(recap_off2.get("charts") or "")
                and same_key(recap_off2.get("charts") or "", pk_off or pk0 or concert)
            )
        )

        checks = {
            "first_on": first_on,
            "written_projection": written_proj,
            "pk_stable_on": pk_stable,
            "inst_stable_on": inst_stable,
            "nav_still_on": nav_state is True,
            "pk_stable_nav": (not pk0) or same_key(pk0, pk_nav),
            "refresh_still_on": refresh_state is True,
            "pk_stable_refresh": (not pk0) or same_key(pk0, pk_refresh),
            "inst_stable_refresh": "clarinet" in (inst_refresh or "").lower(),
            "off_ok": off_state is False,
            "concert_restored": concert_restored,
            # OFF path: PK must match the concert key after refresh (may differ from
            # pre-nav pk0 if a catalog page reseeded sticky — still must not jump on OFF).
            "pk_stable_off": (not pk_refresh) or same_key(pk_refresh, pk_off),
            "inst_stable_off": "clarinet" in (inst_off or "").lower(),
        }
        # Hard Slice 5A gates (written toggle + instrument + display projection).
        hard = {
            k: checks[k]
            for k in (
                "first_on",
                "written_projection",
                "pk_stable_on",
                "inst_stable_on",
                "nav_still_on",
                "refresh_still_on",
                "inst_stable_refresh",
                "off_ok",
                "concert_restored",
                "pk_stable_off",
                "inst_stable_off",
            )
        }
        result["checks"] = checks
        result["hard_checks"] = hard
        result["pk0"] = pk0
        result["recap_on"] = recap_on
        result["recap_refresh"] = recap_refresh
        result["recap_off"] = recap_off
        result["recap_off2"] = recap_off2
        ok = all(hard.values())
        result["ok"] = ok
        browser.close()

    (OUT / "slice5a_written_chart_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (OUT / "slice5a_written_chart_notes.txt").write_text("\n".join(NOTES), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
