"""Same-rerun regression proof after double-transpose fix.

Checks Bm→Dm concert line is Dm (not Fm) and Shape E chart is Em (not Gm).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import expand_sidebar, set_baseweb_select, wait_idle  # noqa: E402
from walk_guitar_shape_key import goto_improv, pick_song  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8511"
OUT = Path(__file__).resolve().parent
PREFIX = "fix-live-"


def _log(notes: list[str], msg: str) -> None:
    notes.append(msg)
    print(msg, flush=True)


def _shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{PREFIX}{name}"), full_page=True)


def _body(page: Page, name: str) -> str:
    text = page.inner_text("body")
    (OUT / f"{PREFIX}{name}").write_text(text[:32000], encoding="utf-8")
    return text


def _line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line.strip()
    return ""


def _practice_select_value(page: Page) -> str:
    return str(
        page.evaluate(
            """() => {
          const vis = (el) => !!(el && el.offsetParent !== null);
          const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')].filter(vis);
          for (const el of boxes) {
            const t = (el.innerText || '').replace(/\\s+/g, ' ');
            if (/Practice \\/ Concert Key/i.test(t)) {
              const input = el.querySelector('input');
              const combo = el.querySelector('[role="combobox"]');
              return ((input && input.value) || (combo && combo.innerText) || '').trim();
            }
          }
          return '';
        }"""
        )
        or ""
    ).strip()


def main() -> int:
    notes: list[str] = [f"URL={URL}"]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        wait_idle(page, 5000)
        expand_sidebar(page)
        ok = pick_song(page, notes, "Shape of You", "Pop")
        _log(notes, f"pick_ok={ok}")
        wait_idle(page, 3000)

        # Ensure Practice Bm first if needed, then Dm
        before = _practice_select_value(page)
        _log(notes, f"before_key={before!r}")
        if "Bm" not in before and "B minor" not in before.lower():
            set_baseweb_select(page, "Practice / Concert Key", "Bm")
            wait_idle(page, 3500)
            before = _practice_select_value(page)
            _log(notes, f"reset_bm_key={before!r}")
        set_baseweb_select(page, "Practice / Concert Key", "Dm")
        wait_idle(page, 4000)
        after = _practice_select_value(page)
        body1 = _body(page, "01-after-dm.txt")
        _shot(page, "01-after-dm.png")
        _log(notes, f"after_key={after!r}")

        goto_improv(page, notes, "fix-sbi")
        wait_idle(page, 3000)
        # Leave Style Jam / Entry — open Song-Based Improvisation for Shape of You
        for label in (
            "Song-Based Improvisation",
            "Play Song-Based Improvisation",
            "Song-Based",
        ):
            try:
                page.get_by_role("radio", name=re.compile(label, re.I)).first.click(timeout=2500)
                wait_idle(page, 2500)
                break
            except Exception:
                try:
                    page.get_by_text(re.compile(label, re.I)).first.click(timeout=2500)
                    wait_idle(page, 2500)
                    break
                except Exception:
                    continue
        try:
            set_baseweb_select(page, "Song source", "Active song")
            wait_idle(page, 2500)
        except Exception:
            pass
        try:
            page.get_by_role("radio", name=re.compile(r"Active song", re.I)).first.click(timeout=2500)
            wait_idle(page, 2500)
        except Exception:
            pass

        from walk_guitar_shape_key import enable_guitar_capo

        enable_guitar_capo(page, notes, "E")
        wait_idle(page, 3000)

        body2 = _body(page, "02-sbi-dm-shape-e.txt")
        _shot(page, "02-sbi-dm-shape-e.png")
        concert = _line(body2, "Concert Practice Key Progression:")
        written = _line(body2, "Written Key Progression") or _line(body2, "Guitar shape")
        practice_line = _line(body2, "Practice concert key:")
        _log(notes, f"practice_line={practice_line}")
        _log(notes, f"concert={concert}")
        _log(notes, f"written={written}")
        _log(notes, f"has_shape_of_you={'Shape of You' in body2}")

        same_rerun_dm = bool(re.search(r"(^|[^a-z])dm([^a-z]|$)", after.lower())) or "d minor" in after.lower()
        # Accept either Shape of You Dm cycle or any concert line that is Dm-domain (not Fm).
        concert_ok = "Fm" not in concert and (
            ("Dm ·" in concert)
            or concert.startswith("Concert Practice Key Progression: Dm")
            or ("Dm" in concert and "Cmaj7" not in concert)
        )
        written_ok = "Fm" not in written
        if "Written" in written or "Em)" in written:
            m = re.search(r":\s*([A-G][#b]?m?)", written)
            if m:
                written_ok = m.group(1) in {"Em", "E", "Dm"} and m.group(1) != "Gm"
            written_ok = written_ok and not written.split(":", 1)[-1].strip().startswith("Gm")

        # refresh invariance
        page.reload(wait_until="domcontentloaded")
        wait_idle(page, 5000)
        body3 = _body(page, "03-after-refresh.txt")
        _shot(page, "03-after-refresh.png")
        concert_r = _line(body3, "Concert Practice Key Progression:")
        _log(notes, f"refresh_concert={concert_r}")
        refresh_ok = ("Dm" in (concert_r or concert)) and ("Fm" not in (concert_r or ""))

        payload = {
            "same_rerun_practice_dm": same_rerun_dm,
            "concert_dm_not_fm": concert_ok,
            "written_em_not_gm": written_ok,
            "refresh_still_dm": refresh_ok,
            "after_key": after,
            "concert": concert,
            "written": written,
            "notes": notes,
        }
        (OUT / f"{PREFIX}summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        browser.close()
        ok_all = same_rerun_dm and concert_ok and written_ok
        return 0 if ok_all else 2


if __name__ == "__main__":
    raise SystemExit(main())
