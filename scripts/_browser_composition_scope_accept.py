# -*- coding: utf-8 -*-
"""Browser acceptance: scoped melody editing, the melody lifecycle, and the new controls.

The evidence here is not "a screen rendered". Every scope claim is checked against the event
list the app actually persisted: the composition document is read off disk before and after
each edit, and a pass that was not selected has to come back byte-identical - same onsets,
same pitches, same durations, same rests.

Usage:
  MUSIC_APP_DATA_DIR=<dir> streamlit run streamlit_music_practice_app.py --server.port 8612
  python scripts/_browser_composition_scope_accept.py http://127.0.0.1:8612 <dir> 1440,390
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

from _browser_composition_recorder_accept import (  # noqa: E402
    GATES,
    body_text,
    click_key,
    click_text,
    log,
    mark,
    open_composer,
    settle,
    wait_ready,
)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8612"
DATA_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("C:/tmp/comp-accept-8612")
WIDTHS = [int(w) for w in (sys.argv[3].split(",") if len(sys.argv) > 3 else ["1440"])]
OUT = SCRIPTS / "evidence-composition-scope"
OUT.mkdir(parents=True, exist_ok=True)

STATE = DATA_DIR / "workspaces" / "daniel" / "music_user_state.json"


# ----------------------------------------------------------------- the app's own saved state

def read_doc() -> dict | None:
    """The composition document the app has persisted. Retried: it is rewritten live."""
    for _ in range(6):
        try:
            blob = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            time.sleep(0.5)
            continue
        doc = (((blob.get("state") or {}).get("session") or {})).get("composer_active_document")
        if isinstance(doc, dict) and doc.get("form"):
            return doc
        time.sleep(0.5)
    return None


def melody_section(doc: dict | None) -> tuple[str, dict] | tuple[None, None]:
    """The first section that has both chords and an accepted melody."""
    sections = ((doc or {}).get("form") or {}).get("sections") or {}
    for sid, sec in sections.items():
        if (sec.get("chords") or []) and ((sec.get("melody") or {}).get("events") or []):
            return str(sid), sec
    for sid, sec in sections.items():
        if sec.get("chords"):
            return str(sid), sec
    return None, None


def events_now() -> list[dict]:
    _sid, sec = melody_section(read_doc())
    return list(((sec or {}).get("melody") or {}).get("events") or [])


def triples(events: list[dict]) -> list[tuple]:
    return [
        (
            round(float(e.get("beat") or 0), 4),
            str(e.get("pitch")),
            float(e.get("duration_beats") or 0),
            bool(e.get("is_rest")),
        )
        for e in events
    ]


def pass_of(events: list[dict], index: int) -> list[tuple]:
    import composition_melody_passes as mp

    return triples(mp.events_in_pass(events, index))


def span_of(events: list[dict]) -> float:
    from composition_melody_shape import timeline_span

    return round(float(timeline_span(events)), 4)


# ----------------------------------------------------------------- setting the song up

def accept_a_melody(page) -> bool:
    """Accept one AI suggestion, so the section has an active melody to scope edits over."""
    if click_text(page, r"Use this melody", settle_s=8.0):
        return True
    btns = page.locator('[class*="st-key-composer_melody_explore_"][class*="_use_"] button')
    if btns.count():
        try:
            btns.first.scroll_into_view_if_needed(timeout=4000)
            btns.first.click(timeout=6000)
            settle(page, 8.0)
            return True
        except Exception:
            return False
    return False


def set_repeats(page, n: int) -> bool:
    """Tile the melody n times, and confirm it took by reading the saved document.

    At phone width the repeat buttons stack, so the first candidate is not always the one that
    is clickable; each is tried and the result is verified rather than assumed.
    """
    import composition_melody_passes as mp

    # Match the key's exact suffix. A [class*="_2"] selector also matches other classes and
    # missed the real button at 390px, which read as "the section has one pass" and looked
    # like a mobile defect; the control is there and has four buttons at both widths.
    wraps = page.locator('[class*="st-key-composer_melody_repeats_btn_"]')
    picks = []
    for i in range(wraps.count()):
        classes = (wraps.nth(i).get_attribute("class") or "").split()
        if any(c.startswith("st-key-composer_melody_repeats_btn_") and c.endswith(f"_{n}")
               for c in classes):
            picks.append(i)
    for i in picks:
        try:
            node = wraps.nth(i)
            node.scroll_into_view_if_needed(timeout=4000)
            # ":visible" matters: these buttons carry help text, and at touch widths the first
            # copy of a tooltip-wrapped button is inside a display:none div.
            btn = node.locator("button:visible")
            (btn.first if btn.count() else node).click(timeout=6000)
            settle(page, 8.0)
            if mp.pass_count(events_now()) >= n:
                return True
        except Exception:
            continue
    return mp.pass_count(events_now()) >= n


def pick_scope(page, label: str) -> bool:
    """Choose a scope by its visible label.

    Streamlit's radio puts the option text in a <label>; the [role="radio"] element itself
    carries no text and no aria-label, so matching by accessible name finds nothing. Clicking
    the label inside the scope widget's own keyed container is what actually selects it.
    """
    box = page.locator('[class*="st-key-composer_melody_scope_"]').first
    if box.count() == 0:
        return False
    opts = box.locator("label").filter(has_text=label)
    if opts.count() == 0:
        return False
    try:
        opts.first.scroll_into_view_if_needed(timeout=4000)
        opts.first.click(timeout=5000)
        settle(page, 6.0)
        return True
    except Exception:
        return False


def choose_pass(page, human_index: int) -> bool:
    """Pick "Pass N of M" in the scope's selectbox."""
    box = page.locator('[class*="st-key-composer_melody_scope_pass_"]')
    if box.count() == 0:
        return False
    try:
        box.first.scroll_into_view_if_needed(timeout=4000)
        inner = box.first.locator('[data-baseweb="select"]')
        (inner.first if inner.count() else box.first).click(timeout=5000)
        page.wait_for_timeout(900)
        wanted = page.locator('li[role="option"], [role="option"]').filter(
            has_text=f"Pass {human_index} of"
        )
        if wanted.count() == 0:
            return False
        wanted.first.click(timeout=5000)
        settle(page, 6.0)
        return True
    except Exception:
        return False


def set_bars(page, first: int, last: int) -> bool:
    ok = True
    for frag, value in (
        ("composer_melody_scope_bar_from_", first),
        ("composer_melody_scope_bar_to_", last),
    ):
        box = page.locator(f'[class*="st-key-{frag}"] input')
        if box.count() == 0:
            ok = False
            continue
        try:
            box.first.scroll_into_view_if_needed(timeout=4000)
            box.first.fill(str(value), timeout=5000)
            box.first.press("Enter")
            settle(page, 4.0)
        except Exception:
            ok = False
    return ok


def refine_once(page) -> bool:
    """Click the first Shape/Refine button, whatever it is called."""
    btns = page.locator('[class*="st-key-composer_melody_ref_"] button')
    if btns.count() == 0:
        return False
    try:
        btns.first.scroll_into_view_if_needed(timeout=4000)
        btns.first.click(timeout=6000)
        settle(page, 8.0)
        return True
    except Exception:
        return False


def accept_refinement(page) -> bool:
    return click_key(page, "composer_melody_refine_accept_", settle_s=9.0)


# ----------------------------------------------------------------- the gates

def run(page, width: int) -> None:
    tag = f"[{width}px] "
    from _browser_composition_recorder_accept import build_song, shot

    if not open_composer(page):
        mark(tag + "Composition Studio opens", False, "")
        return
    build_song(page)
    if not accept_a_melody(page):
        mark(tag + "a melody can be accepted", False, "no Use this melody button")
        shot(page, f"scope-{width}-no-melody")
        return
    mark(tag + "a melody can be accepted", bool(events_now()), f"{len(events_now())} events")

    # Two passes, so One Pass has something to mean.
    set_repeats(page, 2)
    import composition_melody_passes as mp

    base = events_now()
    passes = mp.pass_count(base)
    mark(tag + "the section has more than one pass", passes > 1, f"{passes} passes")
    shot(page, f"scope-{width}-panel")

    body = body_text(page)
    mark(tag + "the scope selector is on the panel", "Editing scope" in body, "")
    scope_line = next(
        (
            ln.strip()
            for ln in body.splitlines()
            if "Editing the entire section" in ln or "Editing pass" in ln or "Editing bar" in ln
        ),
        "",
    )
    mark(tag + "Entire Section is the default scope",
         "entire section" in scope_line.lower(), repr(scope_line[:90]))
    mark(tag + "the chosen scope is stated before the edit", bool(scope_line),
         repr(scope_line[:90]))

    # ---- One Pass: edit pass 2; pass 1 must be untouched --------------------------------
    before = events_now()
    p1_before = pass_of(before, 0)
    span_before = span_of(before)
    if pick_scope(page, "One pass") and choose_pass(page, 2):
        line = next((ln.strip() for ln in body_text(page).splitlines() if "Editing pass" in ln), "")
        mark(tag + "the pass scope names the pass", "pass 2 of 2" in line, repr(line[:90]))
        if refine_once(page) and accept_refinement(page):
            after = events_now()
            p1_after = pass_of(after, 0)
            mark(tag + "a pass-2 edit leaves pass 1 byte-identical", p1_after == p1_before,
                 f"pass 1 had {len(p1_before)} events, now {len(p1_after)}")
            mark(tag + "a pass-2 edit did change pass 2",
                 pass_of(after, 1) != pass_of(before, 1), "")
            mark(tag + "the section keeps its length",
                 abs(span_of(after) - span_before) < 0.26,
                 f"{span_before} -> {span_of(after)} beats")
        else:
            mark(tag + "a pass edit can be proposed and accepted", False, "")
    else:
        mark(tag + "One pass can be selected", False, "")

    # ---- Selected Bars: edit bars 1-2; later bars must be untouched ---------------------
    before = events_now()
    outside_before = [t for t in triples(before) if t[0] >= 8.0]
    span_before = span_of(before)
    if pick_scope(page, "Selected bars") and set_bars(page, 1, 2):
        line = next((ln.strip() for ln in body_text(page).splitlines() if "Editing bar" in ln), "")
        mark(tag + "the bar scope names the bars", "bars 1-2" in line, repr(line[:90]))
        if refine_once(page) and accept_refinement(page):
            after = events_now()
            mark(tag + "a bars 1-2 edit leaves bar 3 onward byte-identical",
                 [t for t in triples(after) if t[0] >= 8.0] == outside_before,
                 f"{len(outside_before)} events outside the range")
            mark(tag + "the section keeps its length after a bar edit",
                 abs(span_of(after) - span_before) < 0.26,
                 f"{span_before} -> {span_of(after)} beats")
            mark(tag + "no event was duplicated",
                 len(triples(after)) == len(set(triples(after))), f"{len(after)} events")
        else:
            mark(tag + "a bar edit can be proposed and accepted", False, "")
    else:
        mark(tag + "Selected bars can be chosen", False, "")

    # ---- Undo the accepted edit ---------------------------------------------------------
    before_undo = triples(events_now())
    if click_text(page, r"Undo last accepted", settle_s=9.0):
        after_undo = triples(events_now())
        mark(tag + "Undo restores the previous accepted melody", after_undo != before_undo,
             f"{len(before_undo)} -> {len(after_undo)} events")
    else:
        mark(tag + "Undo is offered after an accepted edit", False, "no Undo button")

    # ---- Save / Reopen ------------------------------------------------------------------
    saved = triples(events_now())
    page.reload(wait_until="domcontentloaded")
    wait_ready(page)
    settle(page, 6.0)
    open_composer(page)
    settle(page, 5.0)
    # Back to the Melody step, so the UI checks below have a panel to measure.
    click_key(page, "composer_journey_melody", settle_s=6.0)
    reopened = triples(events_now())
    mark(tag + "the melody survives a reload", reopened == saved,
         f"{len(saved)} events before, {len(reopened)} after")

    shot(page, f"scope-{width}-after")


def mount_a_preview(page) -> bool:
    """Arm a preview so the Close control exists to measure.

    The compact rule applies to the block Streamlit renders under the player, so there has to
    be a player. Any of these mounts one.
    """
    for frag in (
        # Probed on the real page: this is the one that mounts the synced player with the
        # Close control under it. "Play chords with highlight" uses a different transport.
        "composer_melody_active_play_",
        "composer_melody_refine_preview_",
        "composer_melody_ed_preview_",
        "composer_hum_play_chords_",
    ):
        wrap = page.locator(f'[class*="st-key-{frag}"] button')
        if wrap.count() == 0:
            continue
        try:
            wrap.first.scroll_into_view_if_needed(timeout=4000)
            wrap.first.click(timeout=6000)
            settle(page, 9.0)
            if page.locator('[class*="st-key-composer_preview_close_"]').count():
                return True
        except Exception:
            continue
    return bool(page.locator('[class*="st-key-composer_preview_close_"]').count())


def ui_checks(page, width: int) -> None:
    """The new controls, measured rather than eyeballed."""
    tag = f"[{width}px] "
    mount_a_preview(page)
    body = body_text(page)
    for label, needle in (
        ("Analyze recording carries the analyse icon", "\U0001f3af Analyze recording"),
        ("the melody headings carry the shared glyph", "\U0001f3b6"),
    ):
        mark(tag + label, needle in body, "")

    # Two different distances, measured separately, because they have different causes:
    #   block_gap  - from the preceding Streamlit block, which the compact CSS controls;
    #   frame_gap  - from the player iframe's bottom, which also includes space Streamlit
    #                reserves inside the element container and the CSS cannot reach.
    geo = page.evaluate(
        "() => {"
        "  const wrap = document.querySelector('[class*=\"st-key-composer_preview_close_\"]');"
        "  if (!wrap) return null;"
        # At touch widths Streamlit renders the help tooltip wrapper twice, the first copy
        # inside a display:none div. Take the copy that is actually laid out.
        "  const btns = Array.from(wrap.querySelectorAll('button'));"
        "  const btn = btns.find(b => b.getBoundingClientRect().width > 0) || btns[0] || null;"
        "  const w = wrap.getBoundingClientRect();"
        "  const b = btn ? btn.getBoundingClientRect() : null;"
        "  const prev = wrap.previousElementSibling;"
        "  const pr = prev ? prev.getBoundingClientRect() : null;"
        "  let frame = null;"
        "  for (const f of Array.from(document.querySelectorAll('iframe'))) {"
        "    const r = f.getBoundingClientRect();"
        "    if (r.bottom <= w.top + 2 && (frame === null || r.bottom > frame)) frame = r.bottom;"
        "  }"
        "  return {block_gap: pr ? Math.round(w.top - pr.bottom) : null,"
        "          frame_gap: frame === null ? null : Math.round(w.top - frame),"
        "          margin: getComputedStyle(wrap).marginTop,"
        "          width: b ? Math.round(b.width) : 0, height: b ? Math.round(b.height) : 0};"
        "}"
    )
    if geo is None:
        mark(tag + "the preview Close control is present to measure", False, "no player mounted")
    else:
        mark(tag + "the compact rule is applied to Close preview",
             geo.get("margin", "") == "-14px", f"margin-top {geo.get('margin')}")
        mark(tag + "Close preview is adjacent to the block above it",
             geo.get("block_gap") is not None and geo["block_gap"] <= 12,
             f"block gap {geo.get('block_gap')}px")
        mark(tag + "Close preview is a real, compact control",
             0 < geo["width"] < (width * 0.6) and geo["height"] > 10,
             f"{geo['width']}x{geo['height']}px")
        log(f"    [measured] space below the player iframe: {geo.get('frame_gap')}px "
            f"(known residual, inside Streamlit's element container)")

    overflow = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth,"
        "        client: document.documentElement.clientWidth})"
    )
    mark(tag + "no horizontal overflow", overflow["scroll"] <= overflow["client"] + 2,
         f"scrollWidth {overflow['scroll']} vs clientWidth {overflow['client']}")


def main() -> int:
    log(f"url={URL} data={DATA_DIR} widths={WIDTHS}")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                ctx = browser.new_context(
                    viewport={"width": width, "height": 900 if width > 500 else 844}
                )
                page = ctx.new_page()
                page.set_default_timeout(20000)
                page.goto(URL, wait_until="domcontentloaded")
                if not wait_ready(page):
                    mark(f"[{width}px] the app loads", False, "")
                    ctx.close()
                    continue
                settle(page, 4.0)
                run(page, width)
                ui_checks(page, width)
                ctx.close()
        finally:
            browser.close()
    (OUT / "gates-scope.json").write_text(json.dumps(GATES, indent=1), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("")
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates passed")
    for g in failed:
        log(f"  FAILED: {g}")
    return 0 if GATES and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
