"""Part 7 and Part 11: a setlist of mixed material, and the colour comes from the metadata.

The main acceptance run builds the three Catalog songs from the report, which can only
exercise one of the three source colours. This adds a Custom progression to the same setlist
and checks that its row says Custom - in words and in its own colour class - while the Catalog
rows are unchanged.

Why it matters beyond the colour: the assignment is explicit that source identity must come
from stored metadata and not from titles. A Custom progression called "Blue Bossa" is the
clearest possible case, because a title-based guess would call it a Catalog standard.

Usage:
  python -X utf8 scripts/_accept_karaoke_mixed_source.py http://127.0.0.1:8599
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8599"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    low,
    settle,
    wait_for_app,
)
from _accept_karaoke_qa import ROWS_JS, open_karaoke  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []


def log(msg: str) -> None:
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def observe(msg: str) -> None:
    OBSERVED.append(msg)
    log(f"[OBS ] {msg}")


def shot(page: Page, name: str) -> str:
    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    (OUT / f"{name}.txt").write_text(body[:60000], encoding="utf-8")
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    except Exception:
        pass
    return body


def rows(page: Page) -> list[dict]:
    try:
        return page.evaluate(ROWS_JS) or []
    except Exception:
        return []


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark("M1 app renders", wait_for_app(page))

            # Voice mode needs a song active first, as the main run found the hard way.
            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)

            click_nav(page, "Songs")
            settle(page, 3)
            queued_catalog = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            mark("M2 a Catalog song is in the set", bool(queued_catalog))

            # A real Custom progression, from the app's own demo loader.
            opened = click_nav(page, "Custom Progression") or click_text(page, "Custom Progression")
            settle(page, 5)
            shot(page, "m1-custom-page")
            loaded = click_key(page, "cpl_demo_blue_bossa") or click_text(page, "Load Blue Bossa")
            settle(page, 5)
            saved = click_key(page, "cpl_save_prog") or click_text(page, "Save progression")
            settle(page, 5)
            active = click_key(page, "cpl_set_active") or click_text(page, "Set active")
            settle(page, 6)
            body = shot(page, "m2-custom-active")
            mark("M3 a Custom progression is the active song",
                 bool(loaded) and ("blue bossa" in low(body)),
                 f"load={bool(loaded)} save={bool(saved)} active={bool(active)}")

            click_nav(page, "Songs")
            settle(page, 4)
            queued_custom = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            mark("M4 the Custom progression was added to the set", bool(queued_custom))

            open_karaoke(page)
            shot(page, "m3-mixed-setlist")
            got = rows(page)
            (OUT / "m3-rows.json").write_text(json.dumps(got, indent=2), encoding="utf-8")
            sources = [(r.get("source"), r.get("chip")) for r in got]
            mark("M5 the setlist holds both kinds of material", len(got) >= 2, f"{sources}")

            customs = [r for r in got if (r.get("source") or "") == "custom"]
            catalogs = [r for r in got if (r.get("source") or "") == "catalog"]
            mark("M6 the Custom row says Custom, from its metadata",
                 len(customs) == 1 and (customs[0].get("chip") or "").strip() == "Custom",
                 f"{[(r.get('chip'), r.get('label')) for r in customs]}")
            mark("M7 it carries the Custom colour class, not the Catalog one",
                 bool(customs) and "src-custom" in (customs[0].get("classes") or "")
                 and "src-catalog" not in (customs[0].get("classes") or ""),
                 f"classes={(customs[0].get('classes') if customs else '')!r}")
            mark("M8 the Catalog rows are untouched",
                 bool(catalogs) and all((r.get("chip") or "") == "Catalog" for r in catalogs),
                 f"{[r.get('chip') for r in catalogs]}")
            colours = {r.get("source"): r.get("chip_bg") for r in got}
            mark("M9 the two kinds are painted differently",
                 len({v for v in colours.values() if v}) >= 2, f"{colours}")
            mark("M10 a title that looks like a standard is still Custom",
                 bool(customs) and "blue bossa" in low(customs[0].get("label") or ""),
                 f"label={(customs[0].get('label') if customs else '')!r}")

            # Part 11's transport list, on this mixed setlist. The unit suites cover advance,
            # regress, repeats and reordering as state; these are the clicks.
            started = (click_text(page, "Start karaoke set") or click_text(page, "Start"))
            settle(page, 8)
            body = shot(page, "m4-performing")
            mark("M11 the mixed set performs", "now singing" in low(body),
                 f"(start helper {bool(started)})")

            first = [r for r in rows(page) if "singing" in low(r.get("marker") or "")]
            nexted = click_text(page, "Skip") or click_text(page, "Next song")
            settle(page, 8)
            second = [r for r in rows(page) if "singing" in low(r.get("marker") or "")]
            mark("M12 Next moves Now Singing to another entry",
                 bool(first) and bool(second) and first[0].get("row") != second[0].get("row"),
                 f"row {first[0].get('row') if first else None} -> "
                 f"{second[0].get('row') if second else None} (helper {bool(nexted)})")

            prev = click_text(page, "Previous song")
            settle(page, 8)
            third = [r for r in rows(page) if "singing" in low(r.get("marker") or "")]
            mark("M13 Previous brings it back",
                 bool(third) and bool(first) and third[0].get("row") == first[0].get("row"),
                 f"row {second[0].get('row') if second else None} -> "
                 f"{third[0].get('row') if third else None} (helper {bool(prev)})")

            from _accept_issue69_karaoke_transposition import press_pause_or_resume, press_play

            click_nav(page, "Backing")
            settle(page, 6)
            played = press_play(page)
            if played:
                # Part 8 and Part 1 on the performance surface itself: the lyrics are open
                # while singing, the chart is folded behind them with its DOM still mounted,
                # and the chord hints are under the lyrics rather than in place of them.
                from _accept_karaoke_qa import perf
                from _accept_issue69_karaoke_transposition import wait_for_live_strip

                wait_for_live_strip(page, 240)
                surface = perf(page)
                log(f"    performance surface: {surface}")
                mark("M16 the karaoke lyrics are open during playback",
                     bool(surface.get("lyric_panel")) and int(surface.get("lyric_lines") or 0) > 0,
                     f"{surface.get('lyric_lines')} lines")
                mark("M17 the chord chart is folded, not removed",
                     surface.get("chart_root") is True and surface.get("chart_folded") is True,
                     f"root={surface.get('chart_root')} folded={surface.get('chart_folded')} "
                     f"summary={surface.get('details_label')!r}")
                mark("M18 chord hints appear under the lyrics",
                     int(surface.get("chord_chips") or 0) > 0,
                     f"{surface.get('chord_chips')} chips")
            if played:
                first_mode = press_pause_or_resume(page)
                second_mode = press_pause_or_resume(page)
                mark("M14 Pause and Resume both answer during a performance",
                     bool(first_mode) and bool(second_mode),
                     f"{first_mode!r} then {second_mode!r}")
            else:
                observe("Play was not available on the Backing page, so Pause/Resume "
                        "were not measured here")

            ended = click_text(page, "End karaoke set")
            settle(page, 6)
            after = rows(page)
            mark("M15 ending the set keeps both entries",
                 len(after) >= 2, f"{len(after)} rows (helper {bool(ended)})")
        finally:
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "mixed-source-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
