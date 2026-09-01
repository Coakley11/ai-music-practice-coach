"""Focused SBI blue-card source-type + Composition selector proof.

Usage:
  MUSIC_APP_DATA_DIR=_runtime_sbi_source_card streamlit run streamlit_music_practice_app.py --server.port 8533
  python scripts/_walk_sbi_source_card.py http://127.0.0.1:8533
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    expand_sidebar,
    set_baseweb_select,
    wait_for_backing,
    wait_idle,
)
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_core_workflows_embargo import open_sbi_active  # noqa: E402
from _walk_ownership_audit_full import build_trial_song  # noqa: E402
from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8533"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "sbi-card-"
GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def low(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("♯", "#").replace("♭", "b"))


def settle(page: Page, sec: float = 2.0) -> None:
    wait_idle(page, int(sec * 1000))


def has_any(text: str, *needles: str) -> bool:
    blob = low(text)
    return any(low(n) in blob for n in needles)


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:24000], encoding="utf-8")
    return body


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'RED'}] {gate}" + (f" — {detail}" if detail else ""))


def blue_card_title(page: Page) -> str:
    try:
        return str(
            page.evaluate(
                """() => {
                  const el = document.querySelector(
                    '.ui-backing-active-title, .ui-creative-jam-title'
                  );
                  return el ? (el.innerText || '').replace(/\\s+/g, ' ').trim() : '';
                }"""
            )
            or ""
        )
    except Exception:
        return ""


def song_source_labels(page: Page) -> list[str]:
    try:
        return list(
            page.evaluate(
                """() => {
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')];
                  for (const g of groups) {
                    const t = (g.innerText || '').toLowerCase();
                    if (!t.includes('custom progression')) continue;
                    if (!t.includes('active')) continue;
                    return [...g.querySelectorAll('label')].map(
                      (l) => (l.innerText || '').replace(/\\s+/g, ' ').trim()
                    ).filter(Boolean);
                  }
                  return [];
                }"""
            )
            or []
        )
    except Exception:
        return []


def wait_sbi_card(page: Page, *needles: str, timeout_s: float = 20.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        body = page.inner_text("body") or ""
        if has_any(body, *needles):
            return True
        settle(page, 1.5)
    return False


def click_sbi_composition(page: Page) -> bool:
    """Click the Song source 🎹 Composition radio (not Composition Studio nav)."""
    try:
        group = page.locator('[role="radiogroup"]').filter(
            has_text=re.compile(r"Custom Progression", re.I)
        )
        target = group.locator("label").filter(
            has_text=re.compile(r"Composition", re.I)
        ).filter(has_not_text=re.compile(r"Studio", re.I))
        if target.count():
            el = target.last
            el.scroll_into_view_if_needed()
            el.click(timeout=5000)
            settle(page, 3)
            if wait_sbi_card(page, "No composition source", "not available as an SBI"):
                return True
    except Exception as exc:
        log(f"composition label click err {exc!r}")
    if click_radio(page, "Composition"):
        settle(page, 3)
        if wait_sbi_card(page, "No composition source", "not available as an SBI"):
            return True
    try:
        via = page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.offsetParent !== null);
              const groups = [...document.querySelectorAll('[role="radiogroup"]')].filter(vis);
              for (const g of groups) {
                const gtxt = (g.innerText || '').toLowerCase();
                if (!gtxt.includes('custom progression')) continue;
                if (!gtxt.includes('active')) continue;
                const labels = [...g.querySelectorAll('label')].filter(vis);
                const target = labels.find((l) => {
                  const t = (l.innerText || '').replace(/\\s+/g, ' ').trim();
                  return /composition/i.test(t) && !/studio/i.test(t);
                });
                if (!target) continue;
                target.scrollIntoView({block: 'center'});
                const input = target.querySelector('input[type=radio]');
                if (input) input.click();
                const p = target.querySelector('p');
                (p || target).click();
                return (target.innerText || '').trim();
              }
              return '';
            }"""
        )
        log(f"composition js via={via!r}")
        if via:
            settle(page, 4)
            return wait_sbi_card(page, "No composition source", "not available as an SBI")
    except Exception as exc:
        log(f"composition click err {exc!r}")
    return False


def card_ok(title: str, *, song: str, kind: str) -> bool:
    t = re.sub(r"\s+", " ", title or "")
    want = f"{song} · Song-Based Improvisation · {kind}"
    if want.lower() in t.lower():
        return True
    return (
        song.lower() in t.lower()
        and "song-based improvisation" in t.lower()
        and kind.lower() in t.lower()
        and "song-based improvisation · song-based improvisation" not in t.lower()
    )


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 8)

        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        build_trial_song(page, NOTES)
        settle(page, 2)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)

        # A. SBI Custom → Backing
        ok_custom = open_sbi_custom_source(page, NOTES)
        settle(page, 2)
        if not wait_sbi_card(page, "Trial Song"):
            ok_custom = open_sbi_custom_source(page, NOTES) or ok_custom
            wait_sbi_card(page, "Trial Song")
        labels = song_source_labels(page)
        body_sel = shot(page, "A0-sbi-custom-selector")
        sel_ok = (
            has_any(" ".join(labels) + " " + body_sel, "Active Source", "Active song")
            and has_any(" ".join(labels) + " " + body_sel, "Custom Progression", "Custom progression")
            and has_any(" ".join(labels) + " " + body_sel, "Composition")
        )
        mark("F_selector", sel_ok, f"labels={labels!r}")
        ok_custom = ok_custom and has_any(body_sel, "Trial Song")

        click_open_backing_studio(page, NOTES, "custom") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, NOTES, "custom")
        settle(page, 4)
        body_a = shot(page, "A-custom-backing")
        title_a = blue_card_title(page)
        custom_ok = card_ok(title_a or body_a, song="Trial Song", kind="Custom progression")
        catalog_wrong = "catalog song" in low(title_a) or (
            "catalog song" in low(body_a)
            and "trial song" in low(title_a)
            and "custom progression" not in low(title_a)
        )
        mark(
            "A_custom_card",
            ok_custom and custom_ok and not catalog_wrong,
            f"title={title_a!r}",
        )

        # C. Practice Key change — type label stays Custom progression
        set_baseweb_select(page, "Practice / Concert Key", "C major") or set_baseweb_select(
            page, "Practice / Concert Key", "C"
        )
        settle(page, 3)
        body_c = shot(page, "C-pk-change")
        title_c = blue_card_title(page)
        pk_ok = card_ok(title_c or body_c, song="Trial Song", kind="Custom progression")
        mark("C_pk_type_unchanged", pk_ok, f"title={title_c!r}")

        # D. Refresh SBI Backing
        page.reload(wait_until="domcontentloaded", timeout=120_000)
        settle(page, 8)
        wait_for_backing(page, NOTES, "D_refresh")
        try:
            page.wait_for_function(
                """() => {
                  const t = document.body ? (document.body.innerText || '') : '';
                  return /CREATIVE BACKING SESSION/i.test(t)
                    && /Trial Song/i.test(t);
                }""",
                timeout=20_000,
            )
        except Exception:
            settle(page, 4)
        body_d = shot(page, "D-refresh")
        title_d = blue_card_title(page)
        refresh_ok = card_ok(title_d or body_d, song="Trial Song", kind="Custom progression")
        mark("D_refresh", refresh_ok, f"title={title_d!r}")

        # E. Return Creative, switch Active ↔ Custom
        click_button_has(page, r"Return to Creative") or click_button_has(
            page, r"Return to Creative · SBI"
        )
        settle(page, 4)
        body_e0 = shot(page, "E0-return-creative")
        open_sbi_active(page)
        settle(page, 3)
        if not wait_sbi_card(page, "Active song · Song Selection", timeout_s=8.0):
            try:
                custom = page.get_by_role("radio", name=re.compile(r"Custom Progression", re.I))
                if custom.count():
                    custom.last.focus()
                    page.keyboard.press("ArrowLeft")
                    settle(page, 4)
            except Exception as exc:
                log(f"active ArrowLeft err {exc!r}")
            open_sbi_active(page)
            wait_sbi_card(page, "Active song · Song Selection", timeout_s=12.0)
        click_open_backing_studio(page, NOTES, "active") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, NOTES, "active")
        settle(page, 4)
        body_b = shot(page, "B-active-backing")
        title_b = blue_card_title(page)
        catalog_ok = card_ok(title_b or body_b, song="Shape of You", kind="Catalog song")
        custom_wrong = "custom progression" in low(title_b)
        mark(
            "B_catalog_card",
            catalog_ok and not custom_wrong,
            f"title={title_b!r}",
        )

        click_button_has(page, r"Return to Creative") or click_button_has(page, r"Return to Creative")
        settle(page, 3)
        open_sbi_custom_source(page, NOTES)
        settle(page, 2)
        click_open_backing_studio(page, NOTES, "e-custom") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, NOTES, "e-custom")
        settle(page, 3)
        title_e = blue_card_title(page)
        body_e = shot(page, "E-switch-custom")
        switch_custom = card_ok(title_e or body_e, song="Trial Song", kind="Custom progression")
        click_button_has(page, r"Return to Creative")
        settle(page, 3)
        open_sbi_active(page)
        settle(page, 2)
        click_open_backing_studio(page, NOTES, "e-active") or click_button_has(page, r"Open in Backing")
        wait_for_backing(page, NOTES, "e-active")
        settle(page, 3)
        title_e2 = blue_card_title(page)
        body_e2 = shot(page, "E-switch-active")
        switch_active = card_ok(title_e2 or body_e2, song="Shape of You", kind="Catalog song")
        mark(
            "E_switch_owner",
            switch_custom and switch_active,
            f"custom={title_e!r} active={title_e2!r}",
        )

        # G. Composition — no stale music, no crash
        click_button_has(page, r"Return to Creative")
        settle(page, 3)
        open_sbi_custom_source(page, NOTES)
        settle(page, 2)
        crashed = False
        try:
            clicked = click_sbi_composition(page)
            settle(page, 3)
            body_g = shot(page, "G-composition")
        except Exception as exc:
            crashed = True
            body_g = shot(page, "G-composition-crash")
            log(f"composition crash {exc!r}")
            clicked = False
        labels_g = song_source_labels(page)
        title_g = blue_card_title(page)
        unavailable = has_any(
            body_g,
            "not available",
            "no composition source",
            "composition is not available",
        )
        stale = (
            has_any(title_g, "Shape of You", "Trial Song")
            or (
                has_any(body_g, "Bm", "Em", "G", "A")
                and has_any(body_g, "Concert Practice Key Progression")
                and "no composition" not in low(body_g)
            )
        )
        sbi_card_stale = has_any(body_g, "Trial Song — Custom", "Active song · Song Selection")
        mark(
            "G_composition_empty",
            clicked and not crashed and unavailable and not sbi_card_stale,
            f"clicked={clicked} labels={labels_g!r} unavailable={unavailable} stale={sbi_card_stale}",
        )

        browser.close()

    failed = [k for k, v in GATES.items() if not v]
    report = {"gates": GATES, "failed": failed, "notes": NOTES}
    (OUT / f"{PREFIX}report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(GATES, indent=2), flush=True)
    print("FAILED:" if failed else "ALL_PASS", failed or [], flush=True)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
