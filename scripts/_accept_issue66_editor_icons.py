"""Browser acceptance for Issue 66: the Songs editors' action icons, as rendered.

Reading the source proves the label was built from the shared map. It does not prove the glyph
survives to the screen, that the button still does its job, or that the label fits on a phone. This
drives the real pages: Songs -> Open editor -> Edit Song Chart (Enable editing), then Lyrics & Cues,
then Custom Progressions -> More options.

Three things are checked for every button:

  the icon       the rendered label starts with the glyph the shared map gives for that verb
  the fit        the label is not clipped (scrollWidth vs clientWidth) and the button stays inside
                 the viewport, measured again at 390 px and 360 px
  the action     a safe sample is actually clicked and the page is re-read afterwards, and every
                 other button is checked for enabled/disabled state and an accessible name

Destructive buttons (Revert to catalog, Revert my lyrics, Delete section, Delete saved progression)
are never clicked - their state and labels are read only. The run uses a disposable
MUSIC_APP_DATA_DIR regardless.

Usage:
  bash scripts/run_icons66_app.sh 8691
  python -I scripts/_accept_issue66_editor_icons.py http://127.0.0.1:8691 [--width 1500]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from music_feature_icons import ACTION_ICONS  # noqa: E402
from playwright.sync_api import Page, sync_playwright  # noqa: E402
from walk_creative_backing_matrix import (  # noqa: E402
    click_button_has, click_nav, expand_pages_nav, expand_sidebar, wait_idle,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8691"
WIDTH = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1500
HEIGHT = 1000 if WIDTH > 500 else 860
OUT = SCRIPTS / "evidence-issue66-icons"
OUT.mkdir(parents=True, exist_ok=True)

GATES: list[tuple[str, bool, str]] = []

# (verb, the label text as the editor writes it). The glyph is taken from the shared map at run
# time, so this file cannot drift from it.
CHART_BUTTONS = [
    ("add", "Add section"),
    ("delete", "Delete section"),
    ("save", "Save corrected chart"),
    ("verify", "Save as user verified"),
    ("revert", "Revert to catalog"),
    ("reset", "Reset draft"),
]
# Per-section buttons: the section name is the musician's, so only the action part is matched.
CHART_SECTION_BUTTONS = [
    ("duplicate", "Duplicate ("),
    ("add", "bar @ end ("),
    ("remove", "last bar ("),
]
CHART_BACKUP_BUTTONS = [
    ("download", "Download all overrides (JSON)"),
]
LYRICS_BUTTONS = [
    ("save", "Save Lyrics & Cues"),
    ("verify", "Save as user verified"),
    ("revert", "Revert my lyrics"),
]
LYRICS_PANEL_BUTTONS = [
    ("apply_text", "Auto-assign to sections"),
    ("reset", "Reset sections to match chart"),
]
# The Songs content editor's own Open / Close button (2026-11-20: was plain text on dev 212e0c63).
EDITOR_OPEN_BUTTON = [("edit", "Open editor")]
EDITOR_CLOSE_BUTTON = [("close", "Close editor")]
_TOGGLE_SEEN: list[str] = []
# Never clicked.
DESTRUCTIVE = ("Revert to catalog", "Revert my lyrics", "Delete section",
               "Delete saved progression")

BUTTONS_JS = """() => {
  const main = document.querySelector('[data-testid="stMain"]') || document.body;
  return Array.from(main.querySelectorAll('button')).map(b => {
    const inner = b.querySelector('p, div, span') || b;
    const box = b.getBoundingClientRect();
    return {
      text: (b.innerText || '').trim(),
      aria: b.getAttribute('aria-label') || '',
      disabled: b.disabled === true || b.getAttribute('aria-disabled') === 'true',
      clipped: inner.scrollWidth > inner.clientWidth + 1,
      right: Math.round(box.right),
      width: Math.round(box.width),
      visible: box.width > 0 && box.height > 0,
    };
  });
}"""


def log(msg: str) -> None:
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


def mark(name: str, ok: bool, detail: str = "") -> bool:
    GATES.append((name, bool(ok), detail))
    log("[%s] %-62s %s" % ("PASS" if ok else "FAIL", name, detail))
    return bool(ok)


def settle(page: Page, seconds: float = 5.0) -> None:
    wait_idle(page, int(seconds * 1000))


def shot(page: Page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / ("%s.png" % name)), full_page=False)
    except Exception:
        pass


def buttons(page: Page) -> list[dict]:
    try:
        return page.evaluate(BUTTONS_JS) or []
    except Exception:
        return []


def find(rows: list[dict], needle: str) -> dict | None:
    for row in rows:
        if needle in str(row.get("text") or ""):
            return row
    return None


def check_group(page: Page, rows: list[dict], group: str, cases: list[tuple[str, str]]) -> None:
    for verb, label in cases:
        icon = ACTION_ICONS.get(verb, "")
        row = find(rows, label)
        if row is None:
            mark("%s: %r is on the page" % (group, label), False, "not found")
            continue
        text = str(row.get("text") or "")
        mark("%s: %r wears the %s icon" % (group, label, verb),
             text.startswith(icon + " "), "rendered %r" % text)
        mark("%s: %r is not clipped" % (group, label),
             not row.get("clipped"), "width=%s" % row.get("width"))
        mark("%s: %r is visible and has an accessible name" % (group, label),
             bool(row.get("visible")) and bool(text or row.get("aria")),
             "visible=%s aria=%r" % (row.get("visible"), row.get("aria")))


def editor_tab_now(page: Page) -> str:
    """Which editor panel is actually rendered, read from its own controls.

    The first run trusted a radio click that never landed and then reported ten chart failures
    about the lyrics panel. The panels are told apart by controls only one of them has.
    """
    rows = buttons(page)
    if find(rows, "Save corrected chart") or find(rows, "Reset draft"):
        return "Edit Song Chart"
    body = ""
    try:
        body = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        pass
    if "Enable editing" in body:
        return "Edit Song Chart"
    if find(rows, "Save Lyrics & Cues"):
        return "Lyrics & Cues"
    return ""


def open_songs_editor(page: Page, tab: str) -> bool:
    expand_pages_nav(page)
    click_nav(page, "Songs")
    settle(page, 9)
    # The song card's own "Edit Song Chart" button is what sets the editor tab (it writes
    # PICKER_EDITOR_TAB_KEY), so for the chart it is clicked first - the radio alone did not move.
    if tab == "Edit Song Chart":
        click_button_has(page, r"Edit Song Chart")
        settle(page, 9)
    rows = buttons(page)
    if find(rows, "Open editor"):
        if "open" not in _TOGGLE_SEEN:
            _TOGGLE_SEEN.append("open")
            check_group(page, rows, "songs editor", EDITOR_OPEN_BUTTON)
        click_button_has(page, r"Open editor")
        settle(page, 9)
    if editor_tab_now(page) != tab:
        # Fall back to the radio, matching on the words (its labels carry feature icons).
        for label in (tab, tab.replace("Edit ", "")):
            try:
                opt = page.get_by_role("radio").filter(has_text=label).first
                if opt.count():
                    opt.scroll_into_view_if_needed()
                    opt.click(timeout=5000)
                    settle(page, 9)
                    if editor_tab_now(page) == tab:
                        break
            except Exception:
                continue
    return editor_tab_now(page) == tab


def enable_chart_editing(page: Page) -> bool:
    try:
        tog = page.get_by_role("checkbox").filter(has_text="Enable editing").first
        if not tog.count():
            tog = page.locator('[data-testid="stCheckbox"]').filter(
                has_text="Enable editing").locator("input").first
        if tog.count():
            if not tog.is_checked():
                tog.click(timeout=5000)
                settle(page, 9)
            return True
    except Exception:
        pass
    try:
        page.get_by_text("Enable editing", exact=False).first.click(timeout=4000)
        settle(page, 9)
        return True
    except Exception:
        return False


def expand_named(page: Page, title: str, *, wants: str = "") -> bool:
    """Open a named expander, unless what we are after is already on the page.

    The first run clicked expanders that were already open and closed them, so the buttons inside
    went missing and the gates blamed the icons for it.
    """
    if wants and find(buttons(page), wants) is not None:
        return True
    try:
        exp = page.locator('[data-testid="stExpander"]').filter(has_text=title).first
        if not exp.count():
            return False
        head = exp.locator("summary, button").first
        if head.count():
            head.scroll_into_view_if_needed()
            head.click(timeout=4000)
            settle(page, 7)
            return True
    except Exception:
        return False
    return False


def author_saved_progression(page: Page) -> bool:
    """Custom Progressions' More options renders nothing until something has been saved.

    `if saved_names := list_saved_progression_names(saved)` - so on a disposable data directory the
    Delete saved progression button genuinely does not exist, and asserting on it measured the
    empty state rather than the icon.
    """
    expand_pages_nav(page)
    click_nav(page, "Custom")
    settle(page, 9)
    body = ""
    try:
        body = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        pass
    if "Undo last chord" not in body and "Clear section" not in body:
        for preset in (r"F\s+C\s+Dm\s+Bb", r"Dm\s+Bb\s+F\s+C", r"F\s+Dm\s+Bb\s+C"):
            if click_button_has(page, preset):
                settle(page, 7)
                break
    click_button_has(page, r"Save to library")
    settle(page, 9)
    try:
        body = page.inner_text('[data-testid="stMain"]') or ""
    except Exception:
        body = ""
    return "Saved" in body or "saved" in body


def phone_pass(page: Page) -> None:
    """Re-measure the editor's buttons after shrinking to the requested width.

    The editor's open/closed state and its selected tab live in session state, so the panel is
    still mounted after the resize - the sidebar drawer is the only thing that needs reopening.
    """
    # Called while the editor is already open, so there is no navigation to redo - which is what
    # went wrong first: navigating to Songs after the run had saved a Custom progression meant the
    # active song was no longer the catalog one, and the panel was genuinely not there.
    page.set_viewport_size({"width": WIDTH, "height": HEIGHT})
    settle(page, 8)
    expand_sidebar(page)
    settle(page, 6)
    tab = editor_tab_now(page)
    mark("the editor panel is still rendered at %d px" % WIDTH, bool(tab), "tab=%r" % tab)
    rows = buttons(page)
    log("  buttons at %d px: %s"
        % (WIDTH, json.dumps([r["text"][:30] for r in rows if r["text"]])[:800]))

    # Whichever editor is mounted, every one of its labelled actions must still read correctly.
    cases = (CHART_BUTTONS + CHART_SECTION_BUTTONS if tab == "Edit Song Chart" else LYRICS_BUTTONS) + EDITOR_CLOSE_BUTTON
    seen = 0
    for verb, label in cases:
        row = find(rows, label)
        if row is None:
            continue
        seen += 1
        icon = ACTION_ICONS.get(verb, "")
        text = str(row.get("text") or "")
        mark("%d px: %r still wears the %s icon" % (WIDTH, label, verb),
             text.startswith(icon + " "), "rendered %r" % text)
        mark("%d px: %r is not clipped" % (WIDTH, label),
             not row.get("clipped"), "width=%s" % row.get("width"))
        mark("%d px: %r stays inside the screen" % (WIDTH, label),
             int(row.get("right") or 0) <= WIDTH + 2, "right edge=%s" % row.get("right"))
    mark("at least one editor action was measured at %d px" % WIDTH, seen > 0,
         "measured=%d of %d" % (seen, len(cases)))
    shot(page, "i05-phone-%d" % WIDTH)

    try:
        over = page.evaluate(
            "() => {const d=document.documentElement;"
            " return [d.scrollWidth, d.clientWidth];}"
        )
        mark("no horizontal page scroll at %d px" % WIDTH,
             int(over[0]) <= int(over[1]) + 2,
             "scrollWidth=%s clientWidth=%s" % (over[0], over[1]))
    except Exception as exc:
        mark("no horizontal page scroll at %d px" % WIDTH, False, str(exc))
    wide = [r for r in buttons(page) if int(r.get("width") or 0) > WIDTH]
    mark("no button is wider than the screen at %d px" % WIDTH, not wide,
         "offenders=%s" % json.dumps([r["text"][:28] for r in wide])[:200])


def main() -> int:
    log("Issue 66 editor action icons, at %d px" % WIDTH)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": max(WIDTH, 1500), "height": 1000})
            page.set_default_timeout(30000)
            page.goto(URL, timeout=180_000)
            wait_idle(page, 40_000)
            expand_sidebar(page)
            settle(page, 5)

            # Lyrics & Cues is read FIRST because it is the editor's default tab. The song
            # card's own Edit Song Chart button is what moves the editor to the chart, and
            # once it has, the radio would not move back - a run that read the chart first
            # then failed three gates saying Lyrics & Cues had not reopened. Arriving at each
            # tab once, in the order the app offers them, removes the backwards switch.
            # ---------------------------------------------------------- Edit Lyrics & Cues
            opened_l = open_songs_editor(page, "Lyrics & Cues")
            mark("the Songs editor opens on Lyrics & Cues", opened_l)
            settle(page, 8)
            rows_l = buttons(page)
            log("  buttons on the lyrics editor: %s"
                % json.dumps([r["text"][:34] for r in rows_l if r["text"]])[:900])
            check_group(page, rows_l, "lyrics", LYRICS_BUTTONS)
            check_group(page, rows_l, "songs editor", EDITOR_CLOSE_BUTTON)
            if expand_named(page, "Paste all lyrics at once", wants="Auto-assign to sections"):
                check_group(page, buttons(page), "lyrics",
                            [("apply_text", "Auto-assign to sections")])
            if expand_named(page, "Manage sections", wants="Reset sections to match chart"):
                rows_ms = buttons(page)
                check_group(page, rows_ms, "lyrics",
                            [("reset", "Reset sections to match chart")])
                add_row = find(rows_ms, ACTION_ICONS["add"])
                mark("lyrics: the Add button wears the add icon",
                     add_row is not None, "label=%r" % (add_row or {}).get("text"))
            shot(page, "i03-lyrics-editor-%d" % WIDTH)

            # The same act must look the same in both editors.
            chart_verify = ACTION_ICONS["verify"] + " Save as user verified"
            mark("both editors mark 'Save as user verified' identically",
                 find(rows_l, chart_verify) is not None,
                 "lyrics label=%r" % (find(rows_l, "Save as user verified") or {}).get("text"))

            # ---------------------------------------------------------- Edit Song Chart
            opened = open_songs_editor(page, "Edit Song Chart")
            mark("the Songs editor opens on Edit Song Chart", opened)
            editing = enable_chart_editing(page)
            mark("Enable editing turns the chart editor on", editing)
            settle(page, 8)
            rows = buttons(page)
            log("  buttons on the chart editor: %s"
                % json.dumps([r["text"][:34] for r in rows if r["text"]])[:900])
            check_group(page, rows, "chart", CHART_BUTTONS)
            check_group(page, rows, "chart", CHART_SECTION_BUTTONS)
            shot(page, "i01-chart-editor-%d" % WIDTH)

            # The per-section tools must look the same for EVERY section, not just the first.
            for verb, label in CHART_SECTION_BUTTONS:
                icon = ACTION_ICONS.get(verb, "")
                hits = [r for r in rows if label in str(r.get("text") or "")]
                mark("chart: every %r button wears the same icon (%d found)" % (label, len(hits)),
                     bool(hits) and all(str(r["text"]).startswith(icon + " ") for r in hits),
                     "labels=%s" % json.dumps([r["text"][:30] for r in hits])[:300])

            # Section order and the JSON backup pair live inside expanders.
            if expand_named(page, "Section order", wants="Apply section order"):
                rows_so = buttons(page)
                check_group(page, rows_so, "chart", [("apply_text", "Apply section order")])
            else:
                mark("chart: the Section order panel opens", False, "expander not found")
            if expand_named(page, "Backup / restore overrides",
                            wants="Download all overrides"):
                rows_bk = buttons(page)
                check_group(page, rows_bk, "chart", CHART_BACKUP_BUTTONS)
                try:
                    up = page.locator('[data-testid="stFileUploader"]').first
                    up_text = (up.inner_text() or "").strip() if up.count() else ""
                except Exception:
                    up_text = ""
                mark("chart: the overrides uploader wears the upload icon",
                     ACTION_ICONS["upload"] in up_text, "uploader text=%r" % up_text[:80])
                shot(page, "i02-chart-backup-%d" % WIDTH)
            else:
                mark("chart: the Backup / restore panel opens", False, "expander not found")

            # ---------------------------------------------------------- actions still work
            rows = buttons(page)
            dup = find(rows, "Duplicate (")
            if dup is not None:
                before = page.inner_text('[data-testid="stMain"]') or ""
                clicked = click_button_has(page, r"Duplicate \(")
                settle(page, 9)
                after = page.inner_text('[data-testid="stMain"]') or ""
                mark("chart: Duplicate still duplicates (the page changed)",
                     bool(clicked) and after != before,
                     "clicked=%s changed=%s" % (clicked, after != before))
                mark("chart: no error after Duplicate",
                     "Traceback" not in after and "Error" not in after.split("\n")[0],
                     "")
            else:
                mark("chart: a Duplicate button exists to click", False, "")

            reset_clicked = click_button_has(page, r"Reset draft")
            settle(page, 9)
            after_reset = page.inner_text('[data-testid="stMain"]') or ""
            mark("chart: Reset draft still resets without error",
                 bool(reset_clicked) and "Traceback" not in after_reset,
                 "clicked=%s" % reset_clicked)

            rows = buttons(page)
            for label in DESTRUCTIVE:
                row = find(rows, label)
                if row is not None:
                    mark("chart: %r is present and not clicked by this run" % label,
                         bool(row.get("visible")), "disabled=%s" % row.get("disabled"))

            # ---------------------------------------------------------- Custom Progressions
            # ---------------------------------------------------------- phone fit
            # Measured here, while the chart editor is still the open panel and before the Custom
            # page changes which song is active.
            if WIDTH < 1500:
                phone_pass(page)
                page.set_viewport_size({"width": 1500, "height": 1000})
                settle(page, 7)

            # Close editor still closes, and the panel offers Open editor (with its icon) again.
            closed = click_button_has(page, r"Close editor")
            settle(page, 9)
            rows_x = buttons(page)
            mark("songs editor: Close editor still closes the editor",
                 bool(closed) and find(rows_x, "Close editor") is None and find(rows_x, "Open editor") is not None,
                 "clicked=%s" % closed)
            check_group(page, rows_x, "songs editor after Close", EDITOR_OPEN_BUTTON)
            shot(page, "i06-editor-closed-%d" % WIDTH)

            saved_one = author_saved_progression(page)
            mark("custom: a progression is saved so More options has something to delete",
                 saved_one)
            if expand_named(page, "More options", wants="Delete saved progression"):
                rows_c = buttons(page)
                del_row = find(rows_c, "Delete saved progression")
                mark("custom: Delete saved progression wears the trash icon",
                     del_row is not None
                     and str(del_row.get("text") or "").startswith(ACTION_ICONS["delete"] + " "),
                     "label=%r" % (del_row or {}).get("text"))
                mark("custom: the delete button keeps its disabled guard",
                     del_row is not None and bool(del_row.get("disabled")),
                     "disabled=%s" % (del_row or {}).get("disabled"))
                shot(page, "i04-custom-more-options-%d" % WIDTH)
            else:
                mark("custom: the More options panel opens", False, "expander not found")
            rows_c = buttons(page)
            for verb, label in (("save", "Save to library"), ("add", "")):
                if not label:
                    continue
                row = find(rows_c, label)
                if row is not None:
                    mark("custom: %r already wears the %s icon" % (label, verb),
                         str(row.get("text") or "").startswith(ACTION_ICONS[verb] + " "),
                         "label=%r" % row.get("text"))

        finally:
            browser.close()

    passed = sum(1 for _n, ok, _d in GATES if ok)
    log("")
    log("%d/%d gates passed at %d px" % (passed, len(GATES), WIDTH))
    for name, ok, detail in GATES:
        if not ok:
            log("  FAILED: %s   %s" % (name, detail))
    (OUT / ("icon-gates-%d.json" % WIDTH)).write_text(
        json.dumps([{"gate": n, "ok": ok, "detail": d} for n, ok, d in GATES], indent=2),
        encoding="utf-8",
    )
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
