"""Part 7 and Part 11: a three-entry setlist of mixed material, driven end to end.

Catalog, Catalog and a Custom progression, each queued in its own key, then Next, Previous,
Stop, End Set and reopening the saved setlist - with a temporary key change in the middle, so
the thing that must not happen (a saved entry or a song's own Practice Key moving) has a chance
to happen.

Two lessons from the earlier runs are built in rather than rediscovered:

* setlist rows live in the Songs page's karaoke panel. Starting a set navigates to Backing,
  where there are no rows at all - reading them there reported "row None -> None" about a
  transport that had worked perfectly.
* the Blue Bossa demo loader sits inside a collapsed "Load saved or demo charts" expander, so
  clicking it blind finds nothing. A Custom progression called Blue Bossa is the sharpest test
  of "source identity from metadata, not from the title", which is why it is worth opening.

Usage:
  python -X utf8 scripts/_accept_karaoke_mixed_source.py http://127.0.0.1:8607
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8607"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    key_token,
    low,
    settle,
    wait_for_app,
)
from _accept_karaoke_qa import ROWS_JS, card_identity, set_pk_token  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402
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


def setlist(page: Page) -> list[dict]:
    """The rows, read where they exist: the Songs page's karaoke panel."""
    click_nav(page, "Songs")
    settle(page, 4)
    click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 4)
    try:
        return page.evaluate(ROWS_JS) or []
    except Exception:
        return []


def now_singing_row(rows: list[dict]) -> int | None:
    for r in rows:
        if "singing" in low(r.get("marker") or ""):
            return r.get("row")
    return None


def saved_keys(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        label = r.get("label") or ""
        out.append(key_token(label.split("·")[-1]) if "·" in label else "")
    return out


def expand_named(page: Page, title: str) -> bool:
    """Open a collapsed expander by its summary text, and only if it is closed."""
    return bool(page.evaluate(
        """(title) => {
          const want = String(title).toLowerCase();
          const heads = [...document.querySelectorAll('summary, [data-testid="stExpander"] summary')];
          for (const h of heads) {
            if (!(h.textContent || '').toLowerCase().includes(want)) continue;
            const det = h.closest('details');
            if (det && !det.open) { h.click(); return true; }
            return true;   // already open
          }
          return false;
        }""", title))


def queue_active_song(page: Page) -> bool:
    click_nav(page, "Songs")
    settle(page, 4)
    return bool(click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set"))


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            ready = wait_for_app(page, 300)
            if not ready:
                observe("the app did not render in 300 s; reloading once")
                page.reload(wait_until="domcontentloaded")
                settle(page, 8)
                ready = wait_for_app(page, 300)
            mark("M1 app renders", ready)

            # Voice mode needs a song active first, or the card has no karaoke button at all.
            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            mark("M2 Say is queued in its own key", queue_active_song(page) and key_token(pk_val(page)) == "bb",
                 f"sidebar={pk_val(page)!r}")

            pick_song(page, OBSERVED, "Just the Two of Us", "pop")
            settle(page, 4)
            set_pk_token(page, "Db")
            mark("M3 Just the Two of Us is queued in Db", queue_active_song(page),
                 f"sidebar={pk_val(page)!r}")

            # A real Custom progression, from the app's own demo loader.
            click_nav(page, "Custom Progression") or click_text(page, "Custom Progression")
            settle(page, 5)
            # Both, not either: the demo buttons sit inside "Jazz chart demos", which is itself
            # inside "Load saved or demo charts". Opening only the outer one left the button
            # unreachable and the run reported expander=True load=False.
            opened_outer = expand_named(page, "Load saved or demo charts")
            settle(page, 2)
            opened_inner = expand_named(page, "Jazz chart demos")
            opened = opened_outer and opened_inner
            settle(page, 3)
            shot(page, "m1-custom-page")
            loaded = click_key(page, "cpl_demo_blue_bossa") or click_text(page, "Load Blue Bossa")
            settle(page, 5)
            saved = click_key(page, "cpl_save_prog") or click_text(page, "Save to Library")
            settle(page, 5)
            active = click_key(page, "cpl_set_active") or click_text(page, "Set active")
            settle(page, 6)
            body = shot(page, "m2-custom-active")
            mark("M4 a Custom progression is the active song",
                 bool(loaded) and "blue bossa" in low(body),
                 f"expanders={bool(opened_outer)}/{bool(opened_inner)} load={bool(loaded)} save={bool(saved)} "
                 f"active={bool(active)}")
            mark("M5 the Custom progression is queued", queue_active_song(page))

            rows = setlist(page)
            (OUT / "m3-rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            shot(page, "m3-mixed-setlist")
            sources = [(r.get("source"), r.get("chip")) for r in rows]
            mark("M6 three entries of mixed material", len(rows) == 3, f"{sources}")
            customs = [r for r in rows if (r.get("source") or "") == "custom"]
            catalogs = [r for r in rows if (r.get("source") or "") == "catalog"]
            mark("M7 the Custom row says Custom, from its metadata",
                 bool(customs) and all((r.get("chip") or "") == "Custom" for r in customs),
                 f"{[(r.get('chip'), r.get('label')) for r in customs]}")
            mark("M8 the Catalog rows say Catalog",
                 len(catalogs) == 2 and all((r.get("chip") or "") == "Catalog" for r in catalogs),
                 f"{[r.get('chip') for r in catalogs]}")
            colours = {r.get("source"): r.get("chip_bg") for r in rows}
            mark("M9 the kinds are painted differently",
                 len({v for v in colours.values() if v}) >= 2, f"{colours}")
            mark("M10 a Custom title that looks like a standard is still Custom",
                 bool(customs) and "blue bossa" in low(customs[0].get("label") or ""),
                 f"label={(customs[0].get('label') if customs else '')!r}")
            before_saved = saved_keys(rows)
            log(f"    saved keys before the performance: {before_saved}")

            # ---- the transport, on mixed material -------------------------------------
            started = click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            first = now_singing_row(setlist(page))
            mark("M11 the mixed set performs", first is not None,
                 f"Now Singing row {first} (start helper {bool(started)})")

            click_nav(page, "Backing")
            settle(page, 5)
            nexted = click_text(page, "Skip") or click_text(page, "Next song")
            settle(page, 8)
            second = now_singing_row(setlist(page))
            mark("M12 Next moves Now Singing", first is not None and second is not None
                 and first != second, f"row {first} -> {second} (helper {bool(nexted)})")

            click_nav(page, "Backing")
            settle(page, 5)
            prev = click_text(page, "Previous song")
            settle(page, 8)
            third = now_singing_row(setlist(page))
            mark("M13 Previous brings it back", third == first,
                 f"row {second} -> {third} (helper {bool(prev)})")

            # ---- a temporary key change on the mixed set -------------------------------
            click_nav(page, "Backing")
            settle(page, 5)
            ident_before = card_identity(page)
            moved = set_pk_token(page, "F")
            settle(page, 8)
            ident_after = card_identity(page)
            mark("M14 a temporary key change takes during the performance", moved,
                 f"{ident_before.get('backing_line')!r} -> {ident_after.get('backing_line')!r}")
            rows_after = setlist(page)
            mark("M15 no saved entry moved with it", saved_keys(rows_after) == before_saved,
                 f"{before_saved} -> {saved_keys(rows_after)}")

            # ---- Stop, End Set, reopen -------------------------------------------------
            click_nav(page, "Backing")
            settle(page, 5)
            stopped = click_text(page, "Stop")
            settle(page, 6)
            mark("M16 Stop answers during a performance", bool(stopped))
            ended = click_text(page, "End karaoke set")
            settle(page, 7)
            body = shot(page, "m4-ended")
            mark("M17 the set ends", bool(ended) and "now singing" not in low(body))

            final = setlist(page)
            (OUT / "m5-rows-after.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
            shot(page, "m5-reopened")
            mark("M18 reopening the setlist finds all three entries", len(final) == 3,
                 f"{len(final)} rows")
            mark("M19 every saved key survived the performance",
                 saved_keys(final) == before_saved,
                 f"{before_saved} -> {saved_keys(final)}")
            mark("M20 the sources survived too",
                 [r.get("source") for r in final] == [r.get("source") for r in rows],
                 f"{[r.get('source') for r in final]}")
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
