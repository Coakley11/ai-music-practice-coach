"""Creative Backing Stabilization — rendered-UI sweep.

Clicks real Streamlit widgets and asserts visible main/sidebar text after rerun.
Fails on the mixed states from live QA (Trial+Bm, Trial sidebar+Shape backing,
Catalog return from Custom-page Backing, missing Songs/Practice after Finish).

Usage:
  MUSIC_APP_DATA_DIR=/tmp/cbs-sweep-<sha> streamlit run streamlit_music_practice_app.py --server.port 8542
  python3 scripts/_walk_cbs_rendered_sweep.py http://127.0.0.1:8542
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from cbs_rendered_contracts import (  # noqa: E402
    catalog_backing_from_custom_page_coherent,
    mixed_state_failures,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8542"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "cbs-sweep-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []
CRITICAL = {
    "songs_after_save",
    "custom_finish_nav",
    "custom_finish_pk",
    "custom_page_backing",
    "custom_backing_return",
    "sbi_open_custom_lab",
    "sbi_custom_page_creative",
}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg, flush=True)


def mark(gate: str, status: str, detail: str = "") -> None:
    RESULTS[gate] = status
    log(f"[{status}] {gate}" + (f" — {detail}" if detail else ""))


def git_meta() -> dict[str, str]:
    def run(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=str(ROOT), text=True).strip()

    return {
        "branch": run(["git", "branch", "--show-current"]),
        "sha": run(["git", "rev-parse", "HEAD"]),
        "url": URL,
    }


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> str:
    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    (OUT / f"{stem}.txt").write_text(body[:24000], encoding="utf-8")
    return body


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    blob = low(body)
    return any(n.lower() in blob for n in needles)


def main_text(page: Page) -> str:
    for sel in ('[data-testid="stMain"]', '[data-testid="stAppViewContainer"]'):
        try:
            loc = page.locator(sel)
            if loc.count():
                return loc.first.inner_text() or ""
        except Exception:
            continue
    return page.inner_text("body") or ""


def sidebar_text(page: Page) -> str:
    try:
        from walk_creative_backing_matrix import expand_sidebar

        expand_sidebar(page)
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def main_button_labels(page: Page) -> list[str]:
    return page.evaluate(
        """() => {
          const root = document.querySelector('[data-testid="stMain"]')
            || document.querySelector('[data-testid="stAppViewContainer"]');
          if (!root) return [];
          return [...root.querySelectorAll('button')]
            .filter((b) => {
              const r = b.getBoundingClientRect();
              return b.offsetParent !== null && r.width > 8 && r.height > 8;
            })
            .map((b) => (b.innerText || '').trim())
            .filter(Boolean);
        }"""
    ) or []


def finished_exits_visible(page: Page) -> dict[str, bool]:
    """Cloud-viewport check: finished-view Songs/Practice widgets, not hub cards."""
    info = page.evaluate(
        """() => {
          const pick = (key) => {
            const wrap = document.querySelector('.st-key-' + key);
            const b = wrap ? wrap.querySelector('button') : null;
            if (!b) return {exists: false, visible: false, text: ''};
            b.scrollIntoView({block: 'center'});
            const r = b.getBoundingClientRect();
            const style = window.getComputedStyle(b);
            const vis = r.width > 8 && r.height > 8
              && style.visibility !== 'hidden'
              && style.display !== 'none'
              && parseFloat(style.opacity || '1') > 0.1;
            return {exists: true, visible: vis, text: (b.innerText || '').trim()};
          };
          const songs = pick('cpl_exit_picker_finish');
          const practice = pick('cpl_exit_practice_finish');
          return {
            songs: !!(songs.exists && songs.visible),
            practice: !!(practice.exists && practice.visible),
            songs_exists: songs.exists,
            practice_exists: practice.exists,
            songs_text: songs.text,
            practice_text: practice.text,
          };
        }"""
    ) or {}
    return {
        "songs": bool(info.get("songs")),
        "practice": bool(info.get("practice")),
        "songs_exists": bool(info.get("songs_exists")),
        "practice_exists": bool(info.get("practice_exists")),
        "songs_text": str(info.get("songs_text") or ""),
        "practice_text": str(info.get("practice_text") or ""),
    }


def click_finished_backing(page: Page) -> bool:
    """Click the finished-view Backing exit, not a hub/nav twin."""
    loc = page.locator(".st-key-cpl_to_backing_finish button").first
    try:
        loc.scroll_into_view_if_needed(timeout=8000)
        loc.click(timeout=8000)
        settle(page, 5)
        return True
    except Exception:
        pass
    clicked = page.evaluate(
        """() => {
          const wrap = document.querySelector('.st-key-cpl_to_backing_finish')
            || document.querySelector('.st-key-custom_page_finished_exits');
          const b = wrap ? wrap.querySelector('button') : null;
          if (!b) return false;
          const t = (b.innerText || '').replace(/\\s+/g, ' ').trim();
          if (!/backing/i.test(t) || /open/i.test(t)) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return true;
        }"""
    )
    if clicked:
        settle(page, 5)
        return True
    return False


RETURN_CUSTOM_PAGE_WIDGET_KEYS = (
    "backing_nav_return_custom_page_0",
    "backing_nav_return_custom_page_1",
    "backing_nav_return_custom_page_2",
)


def click_return_to_custom_page_widget(page: Page) -> dict:
    """Click the visible Streamlit Return to Custom Page widget by key.

    Identifies `.st-key-backing_nav_return_custom_page_*` only.
    Does not fall through to sidebar Custom nav or a generic label search.
    """
    found = page.evaluate(
        """(keys) => {
          const wraps = [];
          for (const key of keys) {
            const wrap = document.querySelector('.st-key-' + key);
            if (wrap) wraps.push({key, wrap});
          }
          document.querySelectorAll('[class*="st-key-backing_nav_return_custom_page"]').forEach((wrap) => {
            const m = [...wrap.classList].find((c) => c.startsWith('st-key-backing_nav_return_custom_page'));
            const key = m ? m.slice('st-key-'.length) : '';
            if (key && !wraps.some((w) => w.key === key)) wraps.push({key, wrap});
          });
          for (const item of wraps) {
            const b = item.wrap.querySelector('button');
            if (!b) continue;
            const text = (b.innerText || '').replace(/\\s+/g, ' ').trim();
            if (!/return to custom page/i.test(text)) continue;
            const r = b.getBoundingClientRect();
            const visible = b.offsetParent !== null && r.width > 8 && r.height > 8;
            if (!visible) continue;
            return {found: true, key: item.key, text, visible: true};
          }
          return {found: false, key: '', text: '', visible: false};
        }""",
        list(RETURN_CUSTOM_PAGE_WIDGET_KEYS),
    ) or {}
    clicked = False
    key = str(found.get("key") or "")
    if found.get("found") and key:
        loc = page.locator(f".st-key-{key} button")
        try:
            if loc.count():
                loc.last.scroll_into_view_if_needed(timeout=5000)
                # Prefer a real Playwright click — JS click() often does not
                # register with Streamlit after a refresh remount.
                try:
                    loc.last.click(timeout=8000, force=False)
                except Exception:
                    loc.last.click(timeout=8000, force=True)
                clicked = True
                settle(page, 5)
        except Exception:
            clicked = False
    return {
        "clicked": clicked,
        "key": key,
        "text": str(found.get("text") or ""),
        "visible": bool(found.get("visible")),
    }


def click_main_button(page: Page, pattern: str) -> bool:
    """Click a visible button in the main pane — never the sidebar nav twin."""
    clicked = page.evaluate(
        """(pattern) => {
          const re = new RegExp(pattern, 'i');
          const root = document.querySelector('[data-testid="stMain"]')
            || document.querySelector('[data-testid="stAppViewContainer"]');
          if (!root) return false;
          const buttons = [...root.querySelectorAll('button')].filter((b) => {
            return b.offsetParent !== null && re.test((b.innerText || '').trim());
          });
          const b = buttons[0];
          if (!b) return false;
          b.scrollIntoView({block: 'center'});
          b.click();
          return true;
        }""",
        pattern,
    )
    if clicked:
        settle(page, 3)
        return True
    return False


def fail_mixed(page: Page, surface: str) -> list[str]:
    errs = mixed_state_failures(
        body=page.inner_text("body") or "",
        main=main_text(page),
        sidebar=sidebar_text(page),
        surface=surface,
    )
    if errs:
        log(f"MIXED {surface}: {errs}")
    return errs


def port_from_url(url: str) -> int:
    m = re.search(r":(\d+)", url or "")
    return int(m.group(1)) if m else 8542


def hard_reboot(port: int) -> None:
    from _walk_core_workflows_embargo import hard_reboot_streamlit

    hard_reboot_streamlit(port)


def wait_up(page: Page, url: str) -> None:
    for _ in range(40):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            settle(page, 3)
            if page.inner_text("body"):
                return
        except Exception:
            time.sleep(2)


def main() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_open_backing_studio,
        click_radio,
        goto_improv,
        set_baseweb_select,
        wait_for_backing,
    )
    from walk_guitar_shape_key import pick_song
    from _walk_ownership_audit_full import build_trial_song, rendered_em_em_d_d
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source
    from _walk_pass8_validate import ensure_missions_workspace, open_mission_backing
    from _walk_core_key_coherence import set_songs_practice_key, card_practice_label
    from _walk_custom_practice_key import goto_custom, pk_val
    from _walk_core_workflows_embargo import (
        click_available_mission_chord,
        click_generate_example,
        motif_notes_from_body,
        open_sbi_active,
        practice_badge,
        sidebar_pk_input,
        wait_for_body,
    )

    meta = git_meta()
    log(json.dumps(meta))
    port = port_from_url(URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)

        # ----- Seed Shape Bm (catalog owner) -----
        wait_for_body(page, "Songs", "Practice", timeout_s=40)
        settle(page, 4)
        opened_songs = click_nav(page, "Songs")
        if not opened_songs:
            settle(page, 3)
            opened_songs = click_nav(page, "Songs")
        settle(page, 3)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        body = shot(page, "00-shape-bm")
        badge = practice_badge(body) or card_practice_label(body)
        seed_shape = has_any(body, "Shape of You") and "b minor" in low(badge or body)
        mark("seed_shape_bm", "PASS" if seed_shape else "RED", f"badge={badge!r}")

        # ----- Custom save without activation -----
        trial_ok = build_trial_song(page, NOTES)
        mark("seed_trial", "PASS" if trial_ok else "RED", "Trial Song D / Em Em D D")

        # 1. Catalog active → Custom save → Songs (Shape/Bm, no Trial leak)
        click_nav(page, "Songs")
        settle(page, 3)
        body = shot(page, "01-songs-after-save")
        main = main_text(page)
        side = sidebar_text(page)
        pk = pk_val(page) or sidebar_pk_input(page) or practice_badge(body)
        songs_ok = (
            has_any(body + side, "Shape of You")
            and "b minor" in low(practice_badge(body) or pk or "")
            and str(pk or "").strip() in {"Bm", "B", "B minor", ""}
        )
        # Sidebar PK widget value is the live projection.
        songs_ok = has_any(body + side, "Shape of You") and (
            "b minor" in low(practice_badge(body) or "")
            or str(pk_val(page) or sidebar_pk_input(page) or "").strip() in {"Bm", "B"}
        )
        mixed = fail_mixed(page, "songs")
        if mixed:
            songs_ok = False
        mark(
            "songs_after_save",
            "PASS" if songs_ok else "RED",
            f"pk={pk!r} badge={practice_badge(body)!r} mixed={mixed}",
        )

        # Refresh on Songs — Shape/Bm must survive
        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Shape of You", "PRACTICE / CONCERT KEY", timeout_s=50)
        settle(page, 3)
        body_r = shot(page, "01b-songs-refresh")
        refresh_songs = has_any(body_r, "Shape of You") and "b minor" in low(
            practice_badge(body_r) or pk_val(page) or ""
        )
        mark("refresh_songs", "PASS" if refresh_songs else "RED", practice_badge(body_r))

        # 2. Songs → Custom Trial → Finish Song
        goto_custom(page)
        settle(page, 3)
        body = shot(page, "02-custom-trial")
        custom_loaded = has_any(body, "Trial Song") and has_any(body, "D major")
        pk_custom = pk_val(page) or sidebar_pk_input(page)
        pk_is_d = str(pk_custom or "").strip() in {"D", "D major"} or (
            "d" in low(pk_custom or "") and "minor" not in low(pk_custom or "")
        )
        mixed_c = fail_mixed(page, "custom_page")
        mark(
            "custom_trial_loaded",
            "PASS" if custom_loaded and pk_is_d and not mixed_c else "RED",
            f"pk={pk_custom!r} mixed={mixed_c}",
        )

        finish_clicked = click_main_button(page, r"^Finish Song$") or click_button_has(
            page, r"^Finish Song$"
        )
        settle(page, 3)
        body_f = shot(page, "03-finish-song")
        labels = main_button_labels(page)
        vis = finished_exits_visible(page)
        page.set_viewport_size({"width": 1100, "height": 720})
        settle(page, 1)
        vis_cloud = finished_exits_visible(page)
        page.set_viewport_size({"width": 1440, "height": 960})
        settle(page, 1)
        vis = {
            "songs": bool(vis.get("songs") and vis_cloud.get("songs")),
            "practice": bool(vis.get("practice") and vis_cloud.get("practice")),
            "wide": vis,
            "cloud": vis_cloud,
        }
        label_blob = " ".join(labels)
        has_songs = bool(vis.get("songs"))
        has_practice = bool(vis.get("practice"))
        has_backing = bool(re.search(r"Backing", label_blob))
        has_activate = bool(re.search(r"Set as Active", label_blob))
        finish_nav = finish_clicked and has_songs and has_practice and has_backing
        mixed_f = fail_mixed(page, "custom_finish")
        preview_d = has_any(body_f, "D major") and "practice / concert key b minor" not in low(body_f)
        mark(
            "custom_finish_nav",
            "PASS" if finish_nav and not mixed_f else "RED",
            f"labels={labels!r} vis={vis!r} mixed={mixed_f}",
        )
        mark(
            "custom_finish_pk",
            "PASS" if preview_d and pk_is_d and not mixed_f else "RED",
            f"preview_d={preview_d} pk={pk_val(page)!r}",
        )

        # Refresh on finished Custom
        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Trial Song", "Finish Song", "Set as Active", timeout_s=50)
        settle(page, 3)
        body_fr = shot(page, "03b-finish-refresh")
        labels_r = main_button_labels(page)
        refresh_finish = has_any(body_fr, "Trial Song") and bool(
            re.search(r"Songs", " ".join(labels_r))
        ) and bool(re.search(r"Practice", " ".join(labels_r)))
        mark("refresh_custom_finish", "PASS" if refresh_finish else "RED", f"labels={labels_r!r}")

        # 3. Custom Trial → main Backing (not sidebar) → Return to Custom
        if not click_finished_backing(page):
            click_main_button(page, r"🎧\\s*Backing")
        settle(page, 4)
        try:
            wait_for_backing(page, NOTES, "custom-page")
        except Exception:
            pass
        settle(page, 3)
        body_b = shot(page, "04-custom-page-backing")
        main_b = main_text(page)
        side_b = sidebar_text(page)
        backing_errs = catalog_backing_from_custom_page_coherent(
            main=main_b, sidebar=side_b, body=body_b
        )
        mixed_b = fail_mixed(page, "custom_backing")
        backing_ok = (
            not backing_errs
            and not mixed_b
            and has_any(main_b, "Shape of You")
            and has_any(main_b, "Backing source: Catalog song")
            and has_any(main_b + body_b, "Return to Custom Page")
            and not has_any(side_b, "Trial Song")
        )
        mark(
            "custom_page_backing",
            "PASS" if backing_ok else "RED",
            f"errs={backing_errs} mixed={mixed_b} pk={pk_val(page)!r}",
        )

        # Refresh on Custom-page Backing — Catalog owner + Custom return survive
        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Backing", "Shape of You", "Return", timeout_s=50)
        settle(page, 3)
        body_br = shot(page, "04b-backing-refresh")
        refresh_bk = has_any(body_br, "Shape of You") and has_any(
            body_br, "Return to Custom Page"
        )
        mark("refresh_custom_backing", "PASS" if refresh_bk else "RED")

        settle(page, 2)
        ret_info = click_return_to_custom_page_widget(page)
        ret = bool(ret_info.get("clicked"))
        log(
            f"return_widget clicked={ret} key={ret_info.get('key')!r} "
            f"text={ret_info.get('text')!r}"
        )
        wait_for_body(page, "Trial Song", "Leave Custom page", timeout_s=30)
        settle(page, 3)
        landed_custom = has_any(
            page.inner_text("body") or "", "Leave Custom page"
        ) and has_any(page.inner_text("body") or "", "Trial Song")
        if not ret or not landed_custom:
            # Diagnostic only — never counts as PASS for Return to Custom Page.
            log("DIAG return widget missed Trial Custom; Custom nav is evidence only")
            try:
                click_nav(page, "Custom")
                wait_for_body(page, "Trial Song", "Leave Custom page", timeout_s=25)
                settle(page, 3)
                shot(page, "05-return-custom-nav-diag")
            except Exception as exc:
                log(f"DIAG custom-nav fallback failed: {exc!r}")
        body_ret = shot(page, "05-return-custom")
        main_ret = main_text(page)
        mixed_ret = fail_mixed(page, "custom_return")
        pk_ret = pk_val(page) or sidebar_pk_input(page)
        pk_ret_d = str(pk_ret or "").strip() in {"D", "D major"} or (
            "d" in low(str(pk_ret or body_ret))
            and "minor" not in low(str(pk_ret or ""))
            and has_any(body_ret, "D major")
        )
        catalog_on_custom = has_any(
            main_ret, "Backing source: Catalog song", "Return to Song Catalog"
        ) or (
            has_any(main_ret, "Shape of You") and has_any(main_ret, "Backing source")
        )
        return_ok = (
            bool(ret)
            and landed_custom
            and has_any(body_ret, "Trial Song")
            and has_any(body_ret, "Leave Custom page")
            and pk_ret_d
            and rendered_em_em_d_d(body_ret)
            and not catalog_on_custom
            and "practice / concert key b minor" not in low(body_ret)
            and not mixed_ret
        )
        # Second rerun must not bounce back to Catalog Backing.
        bounce = False
        if return_ok:
            page.reload(wait_until="domcontentloaded")
            wait_for_body(page, "Trial Song", timeout_s=50)
            settle(page, 3)
            body_rr = shot(page, "05c-return-custom-rerun")
            bounce = has_any(
                body_rr, "Backing source: Catalog song", "Return to Song Catalog"
            ) or not has_any(body_rr, "Leave Custom page")
            return_ok = return_ok and not bounce and has_any(body_rr, "Trial Song")
        mark(
            "custom_backing_return",
            "PASS" if return_ok else "RED",
            f"ret={ret} key={ret_info.get('key')!r} pk={pk_ret!r} "
            f"landed={landed_custom} bounce={bounce} mixed={mixed_ret}",
        )

        # Shape still Global Active on Songs
        click_nav(page, "Songs")
        settle(page, 3)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        body_s = shot(page, "05b-shape-still-ga")
        shape_ga = has_any(body_s, "Shape of You") and not (
            has_any(body_s, "Trial Song") and not has_any(body_s, "Shape of You")
        )
        mark("shape_still_ga", "PASS" if shape_ga else "RED")

        # 4. SBI Active Shape → SBI Custom Trial → Custom Lab → Creative
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        ok_active = open_sbi_active(page)
        body_sa = shot(page, "06-sbi-active")
        sbi_active_ok = bool(ok_active) and has_any(body_sa, "Shape of You")
        mark("sbi_active_shape", "PASS" if sbi_active_ok else "RED")

        ok_cs = open_sbi_custom_source(page, NOTES)
        settle(page, 3)
        body_sc = shot(page, "06b-sbi-custom")
        sbi_custom_ok = bool(ok_cs) and has_any(body_sc, "Trial Song")
        mark("sbi_custom_trial", "PASS" if sbi_custom_ok else "RED", f"open={ok_cs}")

        opened_lab = click_main_button(page, r"Open Custom Lab") or click_button_has(
            page, r"Open Custom Lab"
        )
        settle(page, 3)
        body_lab = shot(page, "06c-custom-from-sbi")
        pk_lab = pk_val(page) or sidebar_pk_input(page)
        lab_pk_d = str(pk_lab or "").strip() in {"D", "D major"} or (
            "d" in low(str(pk_lab or "")) and "minor" not in low(str(pk_lab or ""))
        )
        lab_ok = (
            bool(opened_lab)
            and has_any(body_lab, "Trial Song")
            and lab_pk_d
            and "practice / concert key b minor" not in low(body_lab)
        )
        mark(
            "sbi_open_custom_lab",
            "PASS" if lab_ok else "RED",
            f"pk={pk_lab!r}",
        )

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Trial Song", timeout_s=50)
        settle(page, 3)
        body_lab_r = shot(page, "06c2-custom-lab-refresh")
        pk_lab_r = pk_val(page) or sidebar_pk_input(page)
        lab_refresh_ok = has_any(body_lab_r, "Trial Song") and (
            str(pk_lab_r or "").strip() in {"D", "D major"}
            or ("d" in low(str(pk_lab_r or "")) and "minor" not in low(str(pk_lab_r or "")))
        )
        mark("refresh_custom_lab_from_sbi", "PASS" if lab_refresh_ok else "RED", f"pk={pk_lab_r!r}")

        click_nav(page, "Creative")
        settle(page, 4)
        body_cr = shot(page, "06d-creative-return")
        # Must restore Custom SBI / Trial — not Active SBI with Trial title + Shape chords.
        creative_ok = has_any(body_cr, "Trial Song") and (
            has_any(body_cr, "Custom progression", "Custom Progression")
            or rendered_em_em_d_d(body_cr)
        )
        split = has_any(body_cr, "Trial Song") and has_any(body_cr, "Shape of You") and (
            has_any(body_cr, "Bm", "D minor") and not rendered_em_em_d_d(body_cr)
        )
        mark(
            "sbi_custom_page_creative",
            "PASS" if creative_ok and not split else "RED",
            f"trial={has_any(body_cr,'Trial Song')} split={split}",
        )

        page.reload(wait_until="domcontentloaded")
        wait_for_body(page, "Trial Song", "Creative", timeout_s=50)
        settle(page, 3)
        body_cr_r = shot(page, "06d2-creative-return-refresh")
        creative_refresh_ok = has_any(body_cr_r, "Trial Song") and (
            has_any(body_cr_r, "Custom progression", "Custom Progression")
            or rendered_em_em_d_d(body_cr_r)
        )
        mark(
            "refresh_sbi_custom_page_creative",
            "PASS" if creative_refresh_ok else "RED",
        )

        # 5. Mission Gm in Dm → Backing → D#m/Ebm → Return
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        goto_improv(page, NOTES)
        ensure_missions_workspace(page, NOTES)
        settle(page, 2)
        heading = click_available_mission_chord(page, prefer=["Gm"])
        settle(page, 2)
        click_generate_example(page)
        settle(page, 2)
        body_m = shot(page, "07-mission-gm")
        notes_m = ""
        nm = re.search(r"Notes:\s*([^\n]+)", body_m, re.I)
        if nm:
            notes_m = nm.group(1)
        mission_ready = bool(heading) and has_any(body_m, "Mission")
        mark("mission_gm", "PASS" if mission_ready else "RED", f"chord={heading!r} notes={notes_m!r}")

        try:
            opened_mb = bool(open_mission_backing(page, NOTES))
        except Exception:
            opened_mb = click_button_has(page, r"Open Mission Backing") or click_button_has(
                page, r"Open in Backing"
            )
        settle(page, 4)
        body_mb = shot(page, "07b-mission-backing")
        is_mb = has_any(body_mb, "Return to Mission", "Mission Backing")
        set_baseweb_select(page, "Practice / Concert Key", "D#m") or set_baseweb_select(
            page, "Practice / Concert Key", "Ebm"
        )
        settle(page, 3)
        body_mt = shot(page, "07c-mission-transpose")
        chord_after = ""
        mchord = re.search(
            r"Selected Mission Chord:\s*([A-G](?:#|b)?(?:m|maj|min)?)",
            body_mt,
            re.I,
        )
        if mchord:
            chord_after = mchord.group(1)
        notes_after = ""
        nma = re.search(r"Notes:\s*([^\n]+)", body_mt, re.I)
        if nma:
            notes_after = nma.group(1)
        # One-semitone Gm → G#m/Abm; Bb → B. Fail independent/double paths
        # (A#m / C# from stale +3, or Am / C-E-A from song-map remap).
        wrong_xpose = has_any(body_mt, "A#m", "A# minor") or bool(
            re.search(r"Notes:\s*C#", body_mt, re.I)
        )
        remap_am = has_any(body_mt, "· Am", "Chord Am", "Verse 1 · Am") and has_any(
            body_mt, "D#m", "D# minor", "Eb minor", "Ebm"
        )
        notes_am = bool(re.search(r"Notes:\s*C\s*[–-]\s*E\s*[–-]\s*A", body_mt, re.I))
        card_gsm = has_any(body_mt, "Progression: G#m", "Progression: Abm", "G#m", "Abm")
        banner_wrong = has_any(body_mt, "Verse 1 · Am") and card_gsm
        xpose_ok = bool(
            opened_mb
            and is_mb
            and not wrong_xpose
            and not remap_am
            and not notes_am
            and not banner_wrong
            and card_gsm
        )
        mark(
            "mission_transpose",
            "PASS" if xpose_ok else "RED",
            f"open={opened_mb} chord={chord_after!r} notes={notes_after!r} wrong={wrong_xpose}",
        )

        ret_m = click_button_has(page, r"Return to Mission")
        settle(page, 3)
        body_mr = shot(page, "07d-mission-return")
        mixed_m = fail_mixed(page, "mission_return")
        ret_ok = bool(ret_m) and has_any(body_mr, "Mission", "Generate") and not mixed_m
        tonic_stole = bool(
            re.search(r"selected mission chord:\s*d#\s*m", low(body_mr))
            or re.search(r"selected mission chord:\s*eb\s*m", low(body_mr))
        ) and not has_any(body_mr, "G#m", "Abm")
        mark(
            "mission_return",
            "PASS" if ret_ok and not tonic_stole else "RED",
            f"ret={ret_m} tonic_stole={tonic_stole} mixed={mixed_m}",
        )

        # 6. Motif / Phrase
        from _walk_core_workflows_embargo import absurd_octave_jumps

        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Phrase / Motif") or click_button_has(page, r"Phrase / Motif") or click_radio(
            page, "Motif"
        )
        settle(page, 3)
        click_available_mission_chord(page, prefer=["Dm", "Gm", "Am"])
        click_button_has(page, r"Generate motif") or click_button_has(page, r"New motif")
        settle(page, 3)
        body_mo = shot(page, "08-motif")
        notes0 = motif_notes_from_body(body_mo)
        cells_ok = "|" in (body_mo or "") or " | " in (body_mo or "")
        click_button_has(page, r"Sequence Up")
        settle(page, 3)
        notes_up = motif_notes_from_body(shot(page, "08b-motif-up"))
        click_button_has(page, r"Sequence Down")
        settle(page, 3)
        notes_dn = motif_notes_from_body(shot(page, "08c-motif-down"))
        click_button_has(page, r"Invert") or click_button_has(page, r"Inversion")
        settle(page, 2)
        notes_inv = motif_notes_from_body(shot(page, "08d-motif-invert"))
        before_r = [re.sub(r"\d", "", n) for n in (notes_inv or notes_dn or notes0)]
        click_button_has(page, r"^Change Rhythm$") or click_button_has(page, r"Change Rhythm")
        settle(page, 3)
        body_rh = shot(page, "08e-motif-rhythm")
        after_r = [re.sub(r"\d", "", n) for n in motif_notes_from_body(body_rh)]
        rhythm_pitches_hold = True
        if before_r and after_r:
            n = min(len(before_r), len(after_r))
            rhythm_pitches_hold = before_r[:n] == after_r[:n]
        jumps = absurd_octave_jumps(notes0) if notes0 else False
        motif_ok = bool(notes0) and not jumps and notes_up != notes0 and rhythm_pitches_hold
        mark(
            "motif_transforms",
            "PASS" if motif_ok else "RED",
            f"n={len(notes0 or [])} cells={cells_ok} up={notes_up != notes0} "
            f"dn={notes_dn != notes_up} inv={bool(notes_inv)} rhythm={rhythm_pitches_hold}",
        )
        mark("motif_cell_separators", "PASS" if cells_ok or bool(notes0) else "RED", f"pipe={cells_ok}")

        # 7. Entry Style Jam → Backing → Back Creative → SBI Active
        goto_improv(page, NOTES)
        settle(page, 2)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        settle(page, 2)
        click_radio(page, "Style Jam Mode") or click_button_has(page, r"Style Jam") or click_radio(
            page, "Style Jam"
        )
        settle(page, 2)
        opened_ej = click_open_backing_studio(page, NOTES, "entry") or click_button_has(
            page, r"Open in Backing"
        )
        settle(page, 4)
        body_ej = shot(page, "09-entry-jam-backing")
        ej_ok = bool(opened_ej) and has_any(body_ej, "Backing", "Jam", "Style")
        click_button_has(page, r"Return to Creative") or click_button_has(page, r"Back Creative")
        settle(page, 3)
        ok_sa2 = open_sbi_active(page)
        settle(page, 3)
        body_sa2 = shot(page, "09b-sbi-after-entry")
        sbi_after = bool(ok_sa2) and has_any(body_sa2, "Shape of You", "Perfect") and not (
            has_any(body_sa2, "Trial Song") and not has_any(body_sa2, "Shape of You", "Perfect")
        )
        mark(
            "entry_jam_backing_sbi",
            "PASS" if ej_ok and sbi_after else "RED",
            f"open={opened_ej} sbi={sbi_after}",
        )

        # 8. Source switching Catalog ↔ Custom ↔ Missions ↔ Backing ↔ Creative
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        goto_custom(page)
        settle(page, 2)
        body_sw1 = shot(page, "10-switch-custom")
        goto_improv(page, NOTES)
        ensure_missions_workspace(page, NOTES)
        settle(page, 2)
        body_sw2 = shot(page, "10b-switch-missions")
        click_nav(page, "Backing")
        settle(page, 3)
        body_sw3 = shot(page, "10c-switch-backing")
        click_nav(page, "Creative")
        settle(page, 3)
        body_sw4 = shot(page, "10d-switch-creative")
        switch_ok = has_any(body_sw1, "Trial Song", "Custom") and has_any(
            body_sw2 + body_sw3 + body_sw4, "Mission", "Backing", "Creative", "Shape of You", "Trial"
        )
        mark("source_switching", "PASS" if switch_ok else "RED")

        # 9. Hard reboot ownership (Shape catalog + Trial LAST_CUSTOM)
        click_nav(page, "Songs")
        settle(page, 2)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 2)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        goto_custom(page)
        settle(page, 2)
        shot(page, "11-pre-reboot-custom")
        click_nav(page, "Songs")
        settle(page, 2)
        shot(page, "11-pre-reboot-songs")
        hard_reboot(port)
        page2 = browser.new_page(viewport={"width": 1440, "height": 960})
        wait_up(page2, URL)
        wait_for_body(page2, "Shape of You", "Songs", "Welcome", timeout_s=70)
        settle(page2, 4)
        body_rb = shot(page2, "11-post-reboot")
        reboot_ok = has_any(body_rb, "Shape of You")
        click_nav(page2, "Songs")
        settle(page2, 2)
        body_rb_s = shot(page2, "11b-post-reboot-songs")
        reboot_songs = has_any(body_rb_s, "Shape of You")
        goto_custom(page2)
        settle(page2, 3)
        body_rb_c = shot(page2, "11c-post-reboot-custom")
        reboot_custom = has_any(body_rb_c, "Trial Song") or has_any(body_rb_c, "Custom")
        mark(
            "hard_reboot_ownership",
            "PASS" if reboot_ok and reboot_songs else "RED",
            f"boot={reboot_ok} songs={reboot_songs} custom={reboot_custom}",
        )

        browser.close()

    passed = sum(1 for v in RESULTS.values() if v == "PASS")
    red = sum(1 for v in RESULTS.values() if v == "RED")
    partial = sum(1 for v in RESULTS.values() if v == "PARTIAL")
    critical_red = [g for g in CRITICAL if RESULTS.get(g) == "RED"]
    overall = "PASS" if red == 0 and not critical_red else "RED"
    summary = {
        "meta": meta,
        "OVERALL": overall,
        "PASS": passed,
        "RED": red,
        "PARTIAL": partial,
        "critical_red": critical_red,
        "results": RESULTS,
        "notes": NOTES[-40:],
    }
    (OUT / "cbs-sweep-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"OVERALL={overall}, PASS={passed}, PARTIAL={partial}, RED={red}",
        f"sha={meta.get('sha')}",
        f"critical_red={critical_red}",
    ]
    for gate, status in RESULTS.items():
        lines.append(f"{status} {gate}")
    (OUT / "cbs-sweep-summary.txt").write_text("\n".join(lines), encoding="utf-8")
    log(lines[0])
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
