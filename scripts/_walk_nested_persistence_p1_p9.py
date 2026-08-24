"""Deep nested persistence proofs P1–P9 (browser-visible after reboot).

Usage:
  python scripts/_walk_nested_persistence_p1_p9.py http://127.0.0.1:8512
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_reboot_persistence_ai_p19 import (  # noqa: E402
    URL,
    click_button_has,
    click_nav,
    click_open_backing_studio,
    click_radio,
    creative_tab,
    disk_creative_slice,
    disk_studio_page,
    enable_guitar_capo,
    goto_custom,
    goto_improv,
    has_any,
    open_fresh,
    page_family,
    pick_song,
    reboot_server,
    seed_trial_song_last_custom,
    set_instrument,
    set_shape_tonic,
    set_sidebar_pk,
    settle,
    shot,
    wait_disk_page,
    wait_idle,
)
from _walk_pass8_live import (  # noqa: E402
    current_card_bpm,
    open_advanced,
    set_slider_bpm,
)

OUT = Path(__file__).resolve().parent / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "nested-"


def row(gate: str, ok: bool, detail: str, internal: str = "") -> dict:
    return {
        "gate": gate,
        "ok": bool(ok),
        "detail": detail,
        "internal": internal,
        "verdict": "PASS" if ok else "FAIL",
    }


def side(page: Page) -> str:
    try:
        return page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        return ""


def wait_sbi_custom_on_disk(timeout: float = 25.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = disk_creative_slice()
        src = str(last.get("sbi_preview_source") or last.get("improv_song_source") or "")
        if last.get("studio_page") == "creative" and "Custom" in src:
            return last
        time.sleep(0.5)
    return last


def click_chord_label(page: Page, label: str) -> bool:
    loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
    for i in range(min(loc.count(), 12)):
        el = loc.nth(i)
        try:
            if el.is_visible():
                el.click(timeout=2500)
                wait_idle(page, 1200)
                return True
        except Exception:
            continue
    return click_button_has(page, rf"^{re.escape(label)}$")


def main() -> int:
    notes: list[str] = []
    rows: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ------------------------------------------------------------------
        # Nested Creative → SBI → Custom (regression #1)
        # ------------------------------------------------------------------
        page = open_fresh(browser)
        seed_trial_song_last_custom(page, notes)
        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        click_radio(page, "Song-Based") or click_button_has(page, r"Song-Based")
        settle(page, 2)
        assert click_radio(page, "Custom progression") or click_radio(
            page, "Custom Progression"
        )
        settle(page, 4)
        click_nav(page, "Creative")
        settle(page, 2)
        pre_disk = wait_sbi_custom_on_disk()
        body_pre = shot(page, f"{PREFIX}sbi-custom-pre")
        assert page_family(body_pre) == "creative", page_family(body_pre)
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}sbi-custom-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        src = str(sl.get("sbi_preview_source") or sl.get("improv_song_source") or "")
        ok = (
            fam == "creative"
            and disk == "creative"
            and tab == "sbi"
            and has_any(body, "Trial Song")
            and "Custom" in src
            and not has_any(body, "custom progression lab", "create your own song")
        )
        rows.append(
            row(
                "SBI_CUSTOM",
                ok,
                f"fam={fam} tab={tab} trial={has_any(body,'Trial Song')} src={src!r}",
                f"disk={disk} pre={pre_disk}",
            )
        )

        # ------------------------------------------------------------------
        # P1 Mission deep
        # ------------------------------------------------------------------
        goto_improv(page, notes)
        click_radio(page, "Missions") or click_button_has(page, r"Missions")
        settle(page, 3)
        # Prefer Verse 1 / distinctive chord when present.
        click_radio(page, "Verse 1") or click_button_has(page, r"Verse 1") or click_radio(
            page, "Verse"
        )
        settle(page, 2)
        for chord in ("F#m", "F#", "Bm", "Em", "Am"):
            if click_chord_label(page, chord):
                notes.append(f"P1 chord={chord}")
                break
        set_sidebar_pk(page, "A")
        settle(page, 3)
        click_button_has(page, r"Generate") or click_button_has(page, r"New example")
        settle(page, 3)
        body_pre = shot(page, f"{PREFIX}P1-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P1-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        section = str(sl.get("ii_selected_section") or "")
        chord = str(sl.get("ii_selected_chord") or sl.get("ii_selected_chord_label") or "")
        ok = (
            fam == "creative"
            and disk == "creative"
            and tab == "mission"
            and bool(section)
            and bool(chord)
        )
        rows.append(
            row(
                "P1",
                ok,
                f"fam={fam} tab={tab} section={section!r} chord={chord!r}",
                f"disk={disk}",
            )
        )

        # ------------------------------------------------------------------
        # P2 Live Coach / Harmony selection
        # ------------------------------------------------------------------
        goto_improv(page, notes)
        clicked_harmony = click_radio(page, "Harmony Map") or click_button_has(
            page, r"Harmony"
        )
        if not clicked_harmony:
            click_radio(page, "Live Coach") or click_button_has(page, r"Live Coach")
        settle(page, 3)
        click_radio(page, "Verse") or click_button_has(page, r"Verse")
        settle(page, 1)
        for chord in ("F#m", "F#", "C#m", "G#m", "Bm"):
            if click_chord_label(page, chord):
                notes.append(f"P2 chord={chord}")
                break
        settle(page, 3)
        body_pre = shot(page, f"{PREFIX}P2-pre")
        tool = creative_tab(body_pre)
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P2-post")
        fam, tab, disk = page_family(body), creative_tab(body), disk_studio_page()
        sl = disk_creative_slice()
        ok = (
            fam == "creative"
            and disk == "creative"
            and tab in ("harmony", "live_coach", tool)
            and bool(sl.get("harmony_map_chord") or sl.get("ii_selected_chord"))
        )
        rows.append(
            row(
                "P2",
                ok,
                f"fam={fam} tab={tab} harm={sl.get('harmony_map_chord')!r} ii={sl.get('ii_selected_chord')!r}",
                f"disk={disk}",
            )
        )

        # ------------------------------------------------------------------
        # P3 Alto + Written Charts
        # ------------------------------------------------------------------
        click_nav(page, "Songs")
        wait_idle(page, 1500)
        set_instrument(page, "Alto Saxophone") or set_instrument(page, "Alto")
        settle(page, 2)
        # Toggle Written Charts on if present.
        click_button_has(page, r"Written Charts") or click_radio(page, "Written Charts")
        set_sidebar_pk(page, "G")
        settle(page, 4)
        side_pre = side(page)
        body_pre = shot(page, f"{PREFIX}P3-pre")
        alto_pre = has_any(side_pre + body_pre, "alto")
        written_pre = has_any(side_pre + body_pre, "written")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P3-post")
        sb = side(page)
        alto = has_any(sb + body, "alto")
        written = has_any(sb + body, "written")
        pk_g = has_any(sb + body, "Practice / Concert Key") and (
            has_any(sb, "G") or "G" in (page.input_value('input[aria-label*="Practice"]') if False else "")
        )
        # Product vs harness: if pre failed, label as harness; if pre ok post fail, product.
        if not (alto_pre and written_pre):
            kind = "harness_or_setup"
            ok = False
        elif alto and written:
            kind = "product_ok"
            ok = True
        else:
            kind = "product_fail"
            ok = False
        rows.append(
            row(
                "P3",
                ok,
                f"kind={kind} alto={alto} written={written} pre_alto={alto_pre} pre_written={written_pre}",
                disk_studio_page(),
            )
        )

        # ------------------------------------------------------------------
        # P4 Guitar Shape / Capo
        # ------------------------------------------------------------------
        set_instrument(page, "Guitar")
        settle(page, 2)
        enable_guitar_capo(page, notes, "C")
        set_shape_tonic(page, "Bb") or set_shape_tonic(page, "B")
        settle(page, 4)
        side_pre = side(page)
        body_pre = shot(page, f"{PREFIX}P4-pre")
        guitar_pre = has_any(side_pre, "guitar") and has_any(side_pre + body_pre, "shape", "capo")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P4-post")
        sb = side(page)
        guitar = has_any(sb, "guitar")
        shape = has_any(sb + body, "shape", "capo", "bb", "b♭")
        if not guitar_pre:
            kind = "harness_or_setup"
            ok = False
        elif guitar and shape:
            kind = "product_ok"
            ok = True
        else:
            kind = "product_fail"
            ok = False
        rows.append(
            row(
                "P4",
                ok,
                f"kind={kind} guitar={guitar} shape={shape} pre={guitar_pre}",
                disk_studio_page(),
            )
        )

        # ------------------------------------------------------------------
        # P5 Practice Key editability matrix (change must stick)
        # ------------------------------------------------------------------
        pk_rows = []
        surfaces = [
            ("Songs", lambda: click_nav(page, "Songs")),
            ("Custom", lambda: goto_custom(page)),
            ("Mission", lambda: (goto_improv(page, notes), click_radio(page, "Missions"))),
            ("Harmony Map", lambda: (goto_improv(page, notes), click_radio(page, "Harmony Map"))),
            ("SBI", lambda: (goto_improv(page, notes), click_radio(page, "Song-Based"))),
            ("Backing", lambda: click_nav(page, "Backing")),
        ]
        for label, go in surfaces:
            try:
                go()
                wait_idle(page, 1500)
                changed = set_sidebar_pk(page, "D")
                settle(page, 2)
                sb = side(page)
                visible = has_any(sb, "D") or changed
                pk_rows.append({"surface": label, "editable": bool(changed and visible)})
            except Exception as exc:
                pk_rows.append({"surface": label, "editable": False, "error": str(exc)[:100]})
        # Backing subtypes
        for label, setup in [
            (
                "Mission Backing",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Missions"),
                    click_open_backing_studio(page, notes, "p5-mission"),
                ),
            ),
            (
                "SBI Backing",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Song-Based"),
                    click_open_backing_studio(page, notes, "p5-sbi"),
                ),
            ),
            (
                "Custom SBI Backing",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Song-Based"),
                    click_radio(page, "Custom progression"),
                    click_open_backing_studio(page, notes, "p5-sbi-custom"),
                ),
            ),
            (
                "Jam Backing",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry"),
                    click_radio(page, "Jam Session Generator") or click_button_has(page, r"Jam"),
                    click_open_backing_studio(page, notes, "p5-jam"),
                ),
            ),
            (
                "Entry Style Backing",
                lambda: (
                    goto_improv(page, notes),
                    click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry"),
                    click_radio(page, "Style Jam Mode") or click_button_has(page, r"Style"),
                    click_open_backing_studio(page, notes, "p5-entry"),
                ),
            ),
        ]:
            try:
                setup()
                settle(page, 3)
                changed = set_sidebar_pk(page, "E")
                settle(page, 2)
                pk_rows.append({"surface": label, "editable": bool(changed)})
            except Exception as exc:
                pk_rows.append({"surface": label, "editable": False, "error": str(exc)[:100]})
        editable_n = sum(1 for r in pk_rows if r.get("editable"))
        rows.append(
            row(
                "P5",
                editable_n >= 8,
                f"editable={editable_n}/{len(pk_rows)}",
                json.dumps(pk_rows),
            )
        )

        # ------------------------------------------------------------------
        # P6 Custom SBI Backing reboot
        # ------------------------------------------------------------------
        seed_trial_song_last_custom(page, notes)
        pick_song(page, notes, "Shape of You", "Pop")
        goto_improv(page, notes)
        click_radio(page, "Song-Based")
        settle(page, 2)
        click_radio(page, "Custom progression")
        set_sidebar_pk(page, "F")
        click_open_backing_studio(page, notes, "P6-open")
        settle(page, 4)
        open_advanced(page)
        set_slider_bpm(page, 137)
        settle(page, 3)
        bpm_pre = current_card_bpm(page)
        body_pre = shot(page, f"{PREFIX}P6-pre")
        catalog_pre = has_any(body_pre, "Shape of You") and not has_any(body_pre, "Trial Song")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P6-post")
        fam, disk = page_family(body), disk_studio_page()
        bpm_post = current_card_bpm(page)
        ok = (
            fam.startswith("backing")
            and disk == "backing"
            and has_any(body, "Trial Song")
            and not (has_any(body, "Shape of You") and not has_any(body, "Trial"))
            and (bpm_post in (None, bpm_pre) or bpm_pre is None or abs(int(bpm_post or 0) - int(bpm_pre or 0)) <= 2)
        )
        rows.append(
            row(
                "P6",
                ok,
                f"fam={fam} trial={has_any(body,'Trial Song')} bpm_pre={bpm_pre} bpm_post={bpm_post} catalog_pre={catalog_pre}",
                f"disk={disk}",
            )
        )

        # ------------------------------------------------------------------
        # P7 Mission Backing
        # ------------------------------------------------------------------
        goto_improv(page, notes)
        click_radio(page, "Missions")
        settle(page, 2)
        click_open_backing_studio(page, notes, "P7-open")
        settle(page, 4)
        set_sidebar_pk(page, "Ab")
        open_advanced(page)
        set_slider_bpm(page, 118)
        settle(page, 3)
        body_pre = shot(page, f"{PREFIX}P7-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P7-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = fam.startswith("backing") and disk == "backing" and (
            has_any(body, "mission", "return to mission") or fam == "backing_mission"
        )
        rows.append(row("P7", ok, f"fam={fam}", f"disk={disk}"))
        # Return to Mission still works
        click_button_has(page, r"Return to Mission") or click_button_has(page, r"Return to Creative")
        settle(page, 4)
        body_ret = shot(page, f"{PREFIX}P7-return")
        rows.append(
            row(
                "P7_RETURN",
                page_family(body_ret) == "creative" or has_any(body_ret, "mission"),
                f"fam={page_family(body_ret)}",
                disk_studio_page(),
            )
        )

        # ------------------------------------------------------------------
        # P8 Jam Backing
        # ------------------------------------------------------------------
        goto_improv(page, notes)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry")
        click_radio(page, "Jam Session Generator") or click_button_has(page, r"Jam Session")
        set_sidebar_pk(page, "Eb")
        click_open_backing_studio(page, notes, "P8-open")
        settle(page, 4)
        open_advanced(page)
        set_slider_bpm(page, 142)
        settle(page, 3)
        body_pre = shot(page, f"{PREFIX}P8-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P8-post")
        fam, disk = page_family(body), disk_studio_page()
        pk_ok = set_sidebar_pk(page, "Db")  # still editable after restore
        ok = fam.startswith("backing") and disk == "backing" and (
            fam == "backing_jam" or has_any(body, "jam")
        )
        rows.append(
            row(
                "P8",
                ok,
                f"fam={fam} editable_after={bool(pk_ok)}",
                f"disk={disk}",
            )
        )

        # ------------------------------------------------------------------
        # P9 Entry Style Backing
        # ------------------------------------------------------------------
        goto_improv(page, notes)
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry")
        click_radio(page, "Style Jam Mode") or click_button_has(page, r"Style Jam")
        set_sidebar_pk(page, "B")
        click_open_backing_studio(page, notes, "P9-open")
        settle(page, 4)
        open_advanced(page)
        set_slider_bpm(page, 126)
        settle(page, 3)
        body_pre = shot(page, f"{PREFIX}P9-pre")
        page.context.close()
        reboot_server()
        page = open_fresh(browser)
        body = shot(page, f"{PREFIX}P9-post")
        fam, disk = page_family(body), disk_studio_page()
        ok = fam.startswith("backing") and disk == "backing" and (
            fam == "backing_entry" or has_any(body, "style", "entry")
        )
        rows.append(row("P9", ok, f"fam={fam}", f"disk={disk}"))

        browser.close()

    report = {
        "url": URL,
        "rows": rows,
        "notes": notes[-40:],
        "disk_slice": disk_creative_slice(),
    }
    (OUT / "nested-p1-p9-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
