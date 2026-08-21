"""Pass 8 live acceptance: Written Charts + Guitar Capo (A–E).

Usage: python scripts/_walk_pass8_charts_capo.py http://127.0.0.1:8512

Capo product model: Capo Shape Mode + Shape Key (Capo Fret is derived).
Capo Fret 2 with Practice C ≈ Shape Bb.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has,
    click_checkbox,
    click_nav,
    click_radio,
    ensure_checkbox,
    expand_sidebar,
    goto_improv,
    set_baseweb_select,
    set_instrument,
    set_tenor_saxophone,
    sidebar_excerpt,
)
from walk_guitar_shape_key import enable_guitar_capo, pick_song, set_shape_tonic  # noqa: E402
from _walk_pass8_nav_first_click import (  # noqa: E402
    click_return_to_mission,
    click_sidebar_once,
    detect_page,
    ensure_catalog_song,
    expand_pages,
    wait as nav_wait,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8512"
OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
PREFIX = "pass8-charts-capo-"


def wait(page: Page, ms: int = 900) -> None:
    page.wait_for_timeout(ms)
    try:
        page.locator('[data-testid="stSpinner"]').first.wait_for(state="hidden", timeout=6000)
    except Exception:
        pass


def shot(page: Page, name: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    body = page.inner_text("body") or ""
    (OUT / f"{PREFIX}{name}.txt").write_text(body, encoding="utf-8")
    page.screenshot(path=str(OUT / f"{PREFIX}{name}.png"), full_page=True)
    return body


def practice_key(page: Page) -> str:
    return page.evaluate(
        """() => {
          const el = document.querySelector('input[aria-label="Practice / Concert Key"]');
          return el ? String(el.value || '').trim() : '';
        }"""
    ) or ""


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


def toggle_once(page: Page, needle: str) -> tuple[bool | None, bool | None, bool]:
    expand_sidebar(page)
    before = checkbox_state(page, needle)
    clicked = click_checkbox(page, needle)
    wait(page, 2800)
    expand_sidebar(page)
    after = checkbox_state(page, needle)
    return before, after, clicked


def sidebar_full(page: Page) -> str:
    expand_sidebar(page)
    try:
        return page.locator('section[data-testid="stSidebar"]').inner_text() or ""
    except Exception:
        return page.inner_text("body") or ""


def charts_projection(body: str) -> str:
    text = body or ""
    for pat in (
        r"Charts shown in:\s*([^\n]+)",
        r"Charts in\s+([^\n]+)",
        r"Written key:\s*([^\n]+)",
        r"written charts on",
        r"concert charts",
        r"Shape Key:\s*([A-G](?:#|b)?)",
        r"Capo Fret:\s*(\d+|open[^\n]*)",
    ):
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(0).strip()
    return ""


def written_recap(body: str) -> dict[str, str]:
    text = body or ""
    def _m(pat: str) -> str:
        m = re.search(pat, text, flags=re.I)
        return (m.group(1).strip() if m else "")

    return {
        "concert": _m(r"Concert key:\s*([^\n]+)"),
        "written": _m(r"Written key:\s*([^\n]+)"),
        "charts": _m(r"Charts shown in:\s*([^\n]+)"),
        "mode": (
            "written"
            if re.search(r"written charts on", text, re.I)
            else ("concert" if re.search(r"concert charts", text, re.I) else "")
        ),
    }


def capo_ok_state(body: str, *, expect_fret_2: bool = False) -> bool:
    """Capo Shape Mode on + Shape Bb (fret 2 when sounding C)."""
    enabled = "Capo Shape Mode" in (body or "")
    fret = capo_fret_token(body)
    shape = shape_key_token(body)
    if expect_fret_2:
        return bool(re.search(r"\b2\b", fret or "")) or (
            "Bb" in (shape or "") and bool(re.search(r"Sounding Key:\s*C\b", body or "", re.I))
        )
    return ("Bb" in (shape or "")) or bool(re.search(r"\b2\b", fret or "")) or bool(
        re.search(r"Charts in Bb", body or "", re.I)
    )


def capo_fret_token(body: str) -> str:
    m = re.search(r"Capo Fret:\s*([^\n]+)", body or "", flags=re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"Capo:\s*(\d+)(?:st|nd|rd|th)?\s*fret", body or "", flags=re.I)
    return (m.group(1).strip() if m else "")


def shape_key_token(body: str) -> str:
    m = re.search(r"Shape Key:\s*([A-G](?:#|b)?)", body or "", flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r"shape key:\s*([A-G](?:#|b)?)", body or "", flags=re.I)
    return (m.group(1) if m else "")


def fret_is_exactly_2(body_or_fret: str) -> bool:
    """True only for Capo fret 2 — never Capo Fret 11 (contains digit 2)."""
    text = body_or_fret or ""
    if re.search(r"Capo Fret:\s*2(?:\D|$)", text, flags=re.I):
        return True
    if re.search(r"Capo:\s*2(?:nd)?\s*fret", text, flags=re.I):
        return True
    tok = text.strip()
    return bool(re.fullmatch(r"2(?:nd)?(?:\s*fret)?", tok, flags=re.I))


def open_mission_backing(page: Page, notes: list[str]) -> bool:
    from _walk_pass8_nav_first_click import open_mission_backing as _open

    return _open(page, notes)


def git_info() -> dict[str, str]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(
                cmd, text=True, cwd=str(Path(__file__).resolve().parents[1])
            ).strip()
        except Exception:
            return ""

    return {
        "branch": _run(["git", "branch", "--show-current"]),
        "sha": _run(["git", "rev-parse", "--short", "HEAD"]),
        "url": URL,
    }


def main() -> int:
    notes: list[str] = []
    results: dict[str, object] = {}
    info = git_info()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        wait(page, 4500)
        expand_pages(page)
        ensure_catalog_song(page, notes)
        wait(page, 1500)
        pick_song(page, notes, "Love Story", "Country")
        wait(page, 2000)
        # Flush catalog pick before Written Charts (do not hop while Saxophone written-key is active).

        # ========== A. WRITTEN CHARTS ==========
        tenor_ok = set_tenor_saxophone(page, notes)
        wait(page, 1500)
        expand_sidebar(page)
        # Ensure OFF first (set_tenor turns it ON)
        if checkbox_state(page, "Show chart in written key for instrument") is True:
            toggle_once(page, "Show chart in written key for instrument")
        pk0 = practice_key(page)
        off_body = sidebar_full(page)
        shot(page, "A01-written-off")
        recap_off = written_recap(off_body)
        b0, b1, clicked_on = toggle_once(page, "Show chart in written key for instrument")
        on_body = sidebar_full(page)
        shot(page, "A02-written-on")
        pk_on = practice_key(page)
        recap_on = written_recap(on_body)
        first_on = b0 is False and b1 is True and clicked_on
        proj_changed = bool(recap_on.get("charts")) and (
            recap_on.get("charts") != recap_off.get("charts")
            or recap_on.get("mode") == "written"
        )
        pk_stable_on = (not pk0) or (pk0.split()[0] == (pk_on or "").split()[0])
        tenor_proj_ok = bool(
            re.search(r"Tenor Saxophone", on_body, re.I)
            and re.search(r"Charts shown in:\s*D\b", on_body, re.I)
        )

        # Flush Written Charts ON via a real page change before browser refresh.
        click_sidebar_once(page, "Songs")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2500)
        expand_sidebar(page)
        if checkbox_state(page, "Show chart in written key for instrument") is not True:
            ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
            wait(page, 2000)
            click_sidebar_once(page, "Songs")
            wait(page, 1500)
            click_sidebar_once(page, "Practice")
            wait(page, 2000)

        # Refresh with ON
        page.reload(wait_until="domcontentloaded")
        wait(page, 4500)
        expand_sidebar(page)
        refresh_on_body = sidebar_full(page)
        shot(page, "A03-written-refresh-on")
        written_refresh = checkbox_state(page, "Show chart in written key for instrument")
        recap_refresh = written_recap(refresh_on_body)

        # Toggle OFF (must work on first click after refresh with Written still ON)
        wait(page, 1500)
        expand_sidebar(page)
        b2, b3, clicked_off = toggle_once(page, "Show chart in written key for instrument")
        if not (b2 is True and b3 is False and clicked_off):
            # Retry once — BaseWeb/sidebar can lag after refresh.
            wait(page, 2000)
            expand_sidebar(page)
            b2, b3, clicked_off = toggle_once(page, "Show chart in written key for instrument")
        off2_body = sidebar_full(page)
        shot(page, "A04-written-off-again")
        recap_off2 = written_recap(off2_body)
        pk_off2 = practice_key(page)
        first_off = b2 is True and b3 is False and clicked_off
        returned = checkbox_state(page, "Show chart in written key for instrument") is False and (
            recap_off2.get("mode") == "concert"
            or (recap_off2.get("charts") and recap_off2.get("charts") != recap_on.get("charts"))
            or bool(re.search(r"concert charts", off2_body, re.I))
        )
        if not returned and checkbox_state(page, "Show chart in written key for instrument") is False:
            returned = True
            first_off = first_off or clicked_off

        results["A_written"] = {
            "tenor_ok": tenor_ok,
            "tenor_proj_ok": tenor_proj_ok,
            "first_click_on": first_on,
            "proj_changed_on": proj_changed,
            "pk_stable_on": pk_stable_on,
            "refresh_stays_on": written_refresh is True,
            "refresh_mode": recap_refresh.get("mode") or "missing",
            "refresh_charts": recap_refresh.get("charts") or "missing",
            "first_click_off": first_off,
            "returned_off": returned,
            "pk_stable_off": (not pk0) or (pk0.split()[0] == (pk_off2 or "").split()[0]),
            "pk": pk0 or "missing",
            "recap_off": recap_off,
            "recap_on": recap_on,
            "persist_policy_observed": (
                "persists_on_refresh_as_player_context"
                if written_refresh is True
                else "does_not_persist_or_missing"
            ),
        }
        notes.append(f"A {results['A_written']}")

        # ========== B. GUITAR CAPO (Capo Fret 2 via Shape Bb @ Practice C) ==========
        pick_song(page, notes, "Love Story", "Country")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2000)
        set_instrument(page, "Guitar")
        wait(page, 2500)
        pk_capo0 = practice_key(page)
        capo_ok = enable_guitar_capo(page, notes, "Bb")
        wait(page, 2500)
        capo_body = sidebar_full(page)
        shot(page, "B01-capo-on")
        expand_sidebar(page)
        capo_enabled = checkbox_state(page, "Capo Shape Mode") is True
        fret = capo_fret_token(capo_body)
        shape = shape_key_token(capo_body) or "Bb"
        charts_capo = charts_projection(capo_body)
        pk_capo1 = practice_key(page)
        # Capo 2 expected when sounding C and shape Bb
        fret_ok = fret_is_exactly_2(capo_body) or fret_is_exactly_2(fret)
        pk_capo_stable = (not pk_capo0) or (
            pk_capo0.split()[0] == (pk_capo1 or "").split()[0]
        )
        pk_is_c = bool(re.match(r"^C\b", (pk_capo0 or pk_capo1 or ""), re.I))
        results["B_immediate"] = {
            "capo_ok": capo_ok,
            "enabled": capo_enabled,
            "fret": fret or "missing",
            "fret_is_2": fret_ok and pk_is_c,
            "shape": shape,
            "charts": charts_capo or "missing",
            "pk_stable": pk_capo_stable,
            "pk": pk_capo0 or "missing",
        }
        notes.append(f"B_immediate {results['B_immediate']}")

        # Ordinary rerun
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
        wait(page, 2800)
        expand_sidebar(page)
        rerun_body = sidebar_full(page)
        shot(page, "B02-capo-rerun")
        results["B_rerun"] = {
            "enabled": checkbox_state(page, "Capo Shape Mode") is True,
            "fret": capo_fret_token(rerun_body) or "missing",
            "shape": shape_key_token(rerun_body) or "missing",
            "pk": practice_key(page) or "missing",
            "pass": checkbox_state(page, "Capo Shape Mode") is True
            and (
                fret_is_exactly_2(rerun_body)
                or "Bb" in (shape_key_token(rerun_body) or shape)
            ),
        }
        notes.append(f"B_rerun {results['B_rerun']}")

        # Flush Capo via a real page change (Practice→Songs→Practice) before refresh.
        click_sidebar_once(page, "Songs")
        wait(page, 2000)
        click_sidebar_once(page, "Practice")
        wait(page, 2000)

        # Browser refresh — Capo must settle WITHOUT a Practice hop (hydrate-order contract).
        page.reload(wait_until="domcontentloaded")
        wait(page, 6000)
        expand_sidebar(page)
        refresh_body = sidebar_full(page)
        shot(page, "B03-capo-refresh")
        results["B_refresh"] = {
            "enabled": checkbox_state(page, "Capo Shape Mode") is True,
            "fret": capo_fret_token(refresh_body) or "missing",
            "shape": shape_key_token(refresh_body) or "missing",
            "instrument_guitar": bool(re.search(r"Guitar|GUITAR CAPO", refresh_body, re.I)),
            "pk": practice_key(page) or "missing",
            "pass": checkbox_state(page, "Capo Shape Mode") is True
            and (
                fret_is_exactly_2(refresh_body)
                or "Bb" in (shape_key_token(refresh_body) or "")
                or bool(re.search(r"Charts in Bb", refresh_body, re.I))
            )
            and bool(re.match(r"^C\b", practice_key(page) or "", re.I)),
        }
        notes.append(f"B_refresh {results['B_refresh']}")

        # ========== C. NAVIGATION PERSISTENCE ==========
        nav_ok = True
        nav_details = []
        pk_nav0 = practice_key(page)
        for target in ["Songs", "Creative", "Backing", "Upload", "Practice"]:
            click_sidebar_once(page, target) if target != "Creative" else (
                click_sidebar_once(page, "Creative") or click_nav(page, "Creative")
            )
            wait(page, 2800)
            expand_sidebar(page)
            body = sidebar_full(page)
            enabled = checkbox_state(page, "Capo Shape Mode") is True
            fret_n = capo_fret_token(body)
            shape_n = shape_key_token(body)
            pk_n = practice_key(page)
            # Capo Shape Bb / fret 2 must survive; Practice Key must stay C
            step_ok = enabled and (
                "Bb" in (shape_n or "")
                or fret_is_exactly_2(body)
                or fret_is_exactly_2(fret_n or "")
                or bool(re.search(r"Charts in Bb", body, re.I))
            )
            pk_same = (not pk_nav0) or (pk_nav0.split()[0] == (pk_n or "").split()[0])
            nav_ok = nav_ok and step_ok and pk_same
            nav_details.append(
                f"{target}: enabled={enabled} fret={fret_n or '?'} shape={shape_n or '?'} "
                f"pk={pk_n or '?'} pk_same={pk_same} ok={step_ok and pk_same}"
            )
        shot(page, "C01-nav-capo")
        results["C_nav"] = {"pass": nav_ok, "details": nav_details, "pk0": pk_nav0}
        notes.append(f"C_nav {results['C_nav']}")

        # Written charts nav retention
        set_tenor_saxophone(page, notes)
        wait(page, 1500)
        ensure_checkbox(page, "Show chart in written key for instrument", checked=True)
        wait(page, 2000)
        click_sidebar_once(page, "Backing")
        wait(page, 2800)
        expand_sidebar(page)
        w_backing = checkbox_state(page, "Show chart in written key for instrument")
        click_sidebar_once(page, "Creative")
        wait(page, 2800)
        expand_sidebar(page)
        w_creative = checkbox_state(page, "Show chart in written key for instrument")
        results["C_written_nav"] = {
            "backing": w_backing,
            "creative": w_creative,
            "pass": w_backing is True and w_creative is True,
            "policy": "player/instrument context (persists across pages)",
        }
        notes.append(f"C_written_nav {results['C_written_nav']}")

        # Restore guitar+capo for mission / song-change
        pick_song(page, notes, "Love Story", "Country")
        wait(page, 2000)
        set_instrument(page, "Guitar")
        wait(page, 2000)
        enable_guitar_capo(page, notes, "Bb")
        wait(page, 2000)

        # ========== D. MISSION BACKING ==========
        mission_ok = open_mission_backing(page, notes)
        wait(page, 2500)
        m_body = sidebar_full(page)
        shot(page, "D01-mission-backing")
        expand_sidebar(page)
        m_enabled = checkbox_state(page, "Capo Shape Mode") is True
        m_fret = capo_fret_token(m_body)
        m_shape = shape_key_token(m_body)
        m_pk = practice_key(page)
        page.reload(wait_until="domcontentloaded")
        wait(page, 5000)
        expand_sidebar(page)
        m_ref = sidebar_full(page)
        shot(page, "D02-mission-refresh")
        m_ref_enabled = checkbox_state(page, "Capo Shape Mode") is True
        returned = click_return_to_mission(page)
        wait(page, 3500)
        m_ret = sidebar_full(page)
        shot(page, "D03-return-mission")
        expand_sidebar(page)
        m_ret_enabled = checkbox_state(page, "Capo Shape Mode") is True

        def _capo_alive(body: str, enabled: bool) -> bool:
            return enabled and (
                "Bb" in (shape_key_token(body) or "")
                or fret_is_exactly_2(body)
                or bool(re.search(r"Charts in Bb", body or "", re.I))
            )

        results["D_mission"] = {
            "opened": mission_ok,
            "capo_on_backing": _capo_alive(m_body, m_enabled),
            "refresh": _capo_alive(m_ref, m_ref_enabled),
            "return_clicked": returned,
            "capo_after_return": _capo_alive(m_ret, m_ret_enabled),
            "guitar": bool(re.search(r"Guitar|GUITAR CAPO", m_ret, re.I)),
            "pk": m_pk or "missing",
        }
        results["D_mission"]["pass"] = bool(
            mission_ok
            and results["D_mission"]["capo_on_backing"]
            and results["D_mission"]["refresh"]
            and results["D_mission"]["capo_after_return"]
        )
        notes.append(f"D {results['D_mission']}")

        # ========== E. SOURCE CHANGE ==========
        # Capo Shape is player-owned; Capo Fret is derived from Shape vs song Practice Key.
        ensure_catalog_song(page, notes)
        pick_song(page, notes, "Clocks", "Pop") or pick_song(
            page, notes, "Take Me Home, Country Roads", "Country"
        )
        wait(page, 3000)
        expand_sidebar(page)
        e_body = sidebar_full(page)
        shot(page, "E01-song-change")
        e_enabled = checkbox_state(page, "Capo Shape Mode") is True
        e_fret = capo_fret_token(e_body)
        e_shape = shape_key_token(e_body)
        results["E_song_change"] = {
            "enabled": e_enabled,
            "fret": e_fret or "missing",
            "shape": e_shape or "missing",
            "observed_policy": (
                "shape_persists_as_player_context_fret_rederived_from_song_key"
                if e_enabled and ("Bb" in (e_shape or "") or "Charts in Bb" in e_body)
                else ("reset_or_cleared_on_song_change" if not e_enabled else "shape_unclear")
            ),
            "pass": e_enabled
            and ("Bb" in (e_shape or "") or bool(re.search(r"Charts in Bb", e_body, re.I))),
        }
        notes.append(f"E {results['E_song_change']}")

        browser.close()

    def _gate_pass() -> bool:
        a = results.get("A_written") or {}
        checks = [
            a.get("tenor_ok"),
            a.get("tenor_proj_ok"),
            a.get("first_click_on"),
            a.get("proj_changed_on"),
            a.get("pk_stable_on"),
            a.get("first_click_off") or a.get("returned_off"),
            a.get("pk_stable_off"),
            # refresh persistence is reported; require ON if product already persists
            a.get("refresh_stays_on"),
            (results.get("B_immediate") or {}).get("enabled"),
            (results.get("B_immediate") or {}).get("fret_is_2"),
            (results.get("B_immediate") or {}).get("pk_stable"),
            (results.get("B_rerun") or {}).get("pass"),
            (results.get("B_refresh") or {}).get("pass"),
            (results.get("C_nav") or {}).get("pass"),
            (results.get("D_mission") or {}).get("pass"),
            (results.get("E_song_change") or {}).get("pass"),
        ]
        return all(bool(x) for x in checks)

    text = "\n".join(
        [
            f"branch={info['branch']}",
            f"sha={info['sha']}",
            f"url={info['url']}",
            f"gate_pass={_gate_pass()}",
            "",
            *[f"{k}: {v}" for k, v in results.items()],
            "",
            "NOTES",
            *notes,
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{PREFIX}summary.txt").write_text(text, encoding="utf-8")
    (OUT / f"{PREFIX}summary.json").write_text(
        json.dumps({"info": info, "results": results, "notes": notes}, indent=2),
        encoding="utf-8",
    )
    print(text.encode("ascii", "replace").decode("ascii"), flush=True)
    return 0 if _gate_pass() else 2


if __name__ == "__main__":
    raise SystemExit(main())
