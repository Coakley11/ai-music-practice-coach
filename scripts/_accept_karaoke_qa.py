"""Karaoke QA acceptance - Groups A, B, C in the real application.

Drives the app the way the report came in: a three-song setlist (Say in Bb, Just the Two of
Us in Db, Perfect in Ab), started, re-keyed mid-performance, advanced, ended and reopened.

What it is here to measure, rather than assert from source:

  Part 2  the song card follows the Karaoke entry, not whatever is active elsewhere
  Part 3  a key change during a performance moves the performance and NOT the saved entry
  Part 3b a key change during a performance does not rewrite the song's own Practice Key
  Part 6  the transport buttons carry the shared action icons and keep their words
  Part 7  each row says which kind of material it is, in words and in colour
  Part 1  the chord-hints control is reachable while singing
  Part 8  the lyrics are open during the performance, with the Lead Sheet off by default

The Issue 69 harness already drives this surface, so its helpers are imported rather than
rewritten. Phone widths cannot drive a virtualised selectbox, so key changes are always made
at desktop and only *measured* at the narrow widths - a drive failure there is an observation
about the harness, not a product gate.

Usage:
  python -X utf8 scripts/_accept_karaoke_qa.py http://127.0.0.1:8599 [--stop-after=E]
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
STOP_AFTER = ""
for arg in sys.argv[1:]:
    if arg.startswith("--stop-after="):
        STOP_AFTER = arg.split("=", 1)[1].strip().upper()

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    key_token,
    live_chords,
    low,
    press_play,
    regen_rows,
    set_lead_sheet,
    settle,
    synth_keys,
    trace_rows,
    wait_for_app,
    wait_for_live_strip,
)
from _walk_custom_practice_key import pk_val  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-qa"
OUT.mkdir(parents=True, exist_ok=True)

SAY = ("Say", "Bb")
JTTOU = ("Just the Two of Us", "Db")
PERFECT = ("Perfect", "Ab")

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


ROWS_JS = """
() => {
  const vis = (el) => !!(el && el.offsetParent !== null);
  return [...document.querySelectorAll('.ui-karaoke-pick-wrap')].map((w) => {
    const holder = w.closest('[class*="st-key-karaoke_setlist_row_"]') || w.parentElement;
    const btn = holder ? [...holder.querySelectorAll('button')].find(vis) : null;
    const chip = w.querySelector('.ui-karaoke-row-source');
    const marker = w.querySelector('.ui-karaoke-row-marker');
    const cs = chip ? getComputedStyle(chip) : null;
    const r = btn ? btn.getBoundingClientRect() : null;
    return {
      row: Number(w.getAttribute('data-row')),
      source: (w.getAttribute('data-source') || '').trim(),
      chip: chip ? (chip.textContent || '').trim() : '',
      chip_bg: cs ? cs.backgroundColor : '',
      chip_fg: cs ? cs.color : '',
      marker: marker ? (marker.textContent || '').trim() : '',
      label: btn ? (btn.innerText || '').trim() : '',
      classes: (w.className || '').trim(),
      right: r ? Math.round(r.right) : 0,
      width: r ? Math.round(r.width) : 0,
      clipped: r ? (r.right > window.innerWidth + 1) : false,
    };
  });
}
"""

BUTTONS_JS = """
() => {
  const vis = (el) => !!(el && el.offsetParent !== null);
  return [...document.querySelectorAll('button')].filter(vis).map((b) => {
    const r = b.getBoundingClientRect();
    return {
      text: (b.innerText || '').trim(),
      aria: (b.getAttribute('aria-label') || '').trim(),
      disabled: !!b.disabled,
      right: Math.round(r.right),
      width: Math.round(r.width),
      clipped: r.right > window.innerWidth + 1,
    };
  }).filter((b) => b.text || b.aria);
}
"""

# The performance surface is one components.html iframe. Everything about the lyrics, the
# chord hints under them and the optional chart is read from inside it.
PERF_JS = """
() => {
  const out = {frames: 0, lyric_panel: false, lyric_lines: 0, chord_chips: 0,
               chart_root: false, chart_folded: null, details_label: '', active_line: ''};
  for (const f of document.querySelectorAll('iframe')) {
    let doc = null;
    try { doc = f.contentDocument; } catch (e) { continue; }
    if (!doc) continue;
    const panel = doc.getElementById('karaoke-lyric-panel');
    const root = doc.getElementById('live-chart-root');
    if (!panel && !root) continue;
    out.frames += 1;
    if (panel) {
      out.lyric_panel = true;
      out.lyric_lines = doc.querySelectorAll('.karaoke-lp-lyric-line').length;
      out.chord_chips = doc.querySelectorAll('.karaoke-lp-chord').length;
      const act = doc.querySelector('.karaoke-lp-lyric-line.active');
      out.active_line = act ? (act.textContent || '').trim().slice(0, 60) : '';
    }
    if (root) {
      out.chart_root = true;
      const det = root.closest('details') || doc.querySelector('details');
      if (det) {
        out.chart_folded = !det.open;
        const sum = det.querySelector('summary');
        out.details_label = sum ? (sum.textContent || '').trim().slice(0, 60) : '';
      } else {
        out.chart_folded = false;
      }
    }
  }
  return out;
}
"""


def rows(page: Page) -> list[dict]:
    try:
        return page.evaluate(ROWS_JS) or []
    except Exception:
        return []


def buttons(page: Page) -> list[dict]:
    try:
        return page.evaluate(BUTTONS_JS) or []
    except Exception:
        return []


def perf(page: Page) -> dict:
    try:
        return page.evaluate(PERF_JS) or {}
    except Exception:
        return {}


def button_with(page: Page, needle: str) -> dict | None:
    needle = needle.lower()
    for b in buttons(page):
        if needle in (b.get("text") or "").lower():
            return b
    return None


def set_pk_token(page: Page, token: str) -> bool:
    """Move the Practice Key control on this page to ``token``, flats and all.

    The Issue 69 helper types the token to filter the menu, which works for ``D`` and fails
    silently for ``Ab``: this control spells flats with the flat sign, so typing "Ab" filters
    the list to nothing, the option is never found and the value is left as it was. Measured
    exactly that way - "set_practice_key Ab: 'D' -> 'D'" - with nothing wrong in the product.

    So this one types only the letter and then compares each option by NORMALISED key rather
    than by text, which makes "Ab", "A flat" and "A♭ major" one key.
    """
    expand_sidebar(page)
    before = pk_val(page)
    want = key_token(token)
    opened = page.evaluate(
        """() => {
          const re = /Practice\\s*\\/?\\s*Concert\\s*Key/i;
          const box = [...document.querySelectorAll('[role="combobox"]')]
            .find((c) => re.test((c.getAttribute('aria-label') || c.innerText || '')));
          if (!box) return false;
          box.setAttribute('data-kqa-pk', '1');
          return true;
        }"""
    )
    if not opened:
        observe("no Practice Key combobox on this page")
        return False
    try:
        page.locator('[data-kqa-pk="1"]').first.click(timeout=8000)
    except Exception as exc:
        observe(f"could not open the Practice Key control: {exc}")
        return False
    page.wait_for_timeout(500)
    try:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(token[0], delay=40)
        page.wait_for_timeout(500)
    except Exception:
        pass
    for _ in range(10):
        options = page.locator('[role="option"]')
        for i in range(options.count()):
            try:
                text = options.nth(i).inner_text().strip()
            except Exception:
                continue
            if key_token(text) == want:
                try:
                    options.nth(i).scroll_into_view_if_needed()
                    options.nth(i).click(timeout=5000)
                    page.wait_for_timeout(700)
                    # Read twice: straight after the click and again once the app has settled.
                    # The difference tells a click that never landed from a value the app put
                    # back, which a single read after the settle cannot distinguish.
                    immediate = pk_val(page)
                    settle(page, 6)
                    after = pk_val(page)
                    log(f"    Practice Key {token}: {before!r} -> {immediate!r} (clicked "
                        f"{text!r}) -> {after!r} after the rerun")
                    if key_token(immediate) == want and key_token(after) != want:
                        observe(f"the app put the Practice Key back to {after!r} after "
                                f"accepting {token}")
                    return key_token(after) == want
                except Exception:
                    pass
        page.keyboard.press("PageDown")
        page.wait_for_timeout(200)
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    log(f"    Practice Key {token}: FAILED, still {pk_val(page)!r}")
    return False


def card_practice_key(page: Page, ident: dict) -> str:
    """The card's own Practice Key chip, or the sidebar's value when no card is mounted.

    Which surface answered is logged, because a gate that silently falls back to the sidebar
    is no longer a gate about the card.
    """
    backing = str(ident.get("backing_key") or "").strip()
    if backing:
        return backing
    chip = str(ident.get("practice") or "").strip()
    if chip:
        observe("no backing-source line; read the card's own chip instead")
        return chip
    side = pk_val(page)
    observe(f"neither a backing-source line nor a card chip here; read the sidebar ({side!r}) "
            "- which is the EDITING song's key by design, so treat this as unmeasured")
    return side


def open_karaoke(page: Page) -> bool:
    ok = click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 5)
    return bool(ok)


def goto_songs(page: Page) -> None:
    click_nav(page, "Songs")
    settle(page, 4)


def card_identity(page: Page) -> dict:
    """What the active-song card itself says - its own chips, not the page's prose.

    The card carries structured chips (``app_ui.active_song_key_row_html``), which is what
    Part 2 is about: the card has to be the song being sung with that song's own two keys.
    Reading "Original Key:" out of the body text instead picks up the sidebar's own line
    about whatever song is active elsewhere, which is the very thing under test - and there
    is no "Practice Key: X" prose on the Songs page at all, so a text reader returns "" and
    the gate passes or fails for the wrong reason.
    """
    return page.evaluate(
        """() => {
          const txt = (document.body.innerText || '');
          const one = (sel) => {
            const el = document.querySelector(sel);
            return el ? (el.textContent || '').trim() : '';
          };
          const sidebar = (re) => { const m = txt.match(re); return m ? m[1].trim() : ''; };
          // The backing context summary is the surface that answers Part 2 outright: which
          // kind of material, which song, and the key the BACKING will play it in.
          // "Backing source: Catalog song | Say | Bb | 82 BPM"
          const srcLine = (txt.match(/Backing source:[^\\n]*/) || [''])[0].trim();
          const srcBits = srcLine.split('\\u00b7').map((s) => s.trim());
          return {
            backing_line: srcLine,
            backing_kind: srcBits[0] ? srcBits[0].replace(/^Backing source:\\s*/, '') : '',
            backing_song: srcBits[1] || '',
            backing_key: srcBits[2] || '',
            card_title: one('.ui-backing-active-title'),
            original: one('.ui-active-song-key-chip.original .ui-active-song-key-value'),
            practice: one('.ui-active-song-key-chip.practice .ui-active-song-key-value'),
            sidebar_original: sidebar(/Original Key:\\s*([A-G][b#\\u266d\\u266f]?m?)/i),
            now_singing: /now singing/i.test(txt),
            now_editing: /now editing/i.test(txt),
            has_say: /\\bSay\\b/.test(txt),
            has_jttou: /Just the Two of Us/i.test(txt),
            has_perfect: /\\bPerfect\\b/.test(txt),
          };
        }"""
    )


# --------------------------------------------------------------------------- phases


def phase_a_setup(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    settle(page, 5)
    ready = wait_for_app(page)
    body = shot(page, "a1-ready")
    mark("A1 app renders", ready and len(body.strip()) > 400, f"{len(body)} chars")

    # Order matters. The instrument control has to be driven with a song already active: set on
    # the landing page it does not take, and karaoke is voice-only, so the Songs card then has
    # no Add to Karaoke Set button at all and a run reports "could not queue Say" about a
    # perfectly good button.
    picked = pick_song(page, OBSERVED, SAY[0], "pop")
    settle(page, 4)
    mark("A2 Say is the active song", bool(picked))

    expand_sidebar(page)
    set_baseweb_select(page, "Instrument", "Voice")
    settle(page, 6)
    inst = page.evaluate(
        """() => {
          const el = [...document.querySelectorAll('[role="combobox"],input[aria-label]')]
            .find(e => /instrument/i.test(e.getAttribute('aria-label') || ''));
          return el ? String(el.value || '') : '';
        }"""
    )
    mark("A3 instrument is Voice (karaoke needs it)", "voice" in low(str(inst)),
         f"instrument={inst!r}")
    pk = pk_val(page)
    mark("A4 Say opens on its own key", key_token(pk) == "bb", f"practice key={pk!r}")
    return ready


def queue_song(page: Page, title: str, want_key: str, *, set_key: bool,
               already_active: bool = False) -> bool:
    """Pick a song, put the sidebar in the key it should be queued in, and queue it."""
    picked = True if already_active else pick_song(page, OBSERVED, title, "pop")
    settle(page, 4)
    if not picked:
        return False
    if set_key:
        moved = set_pk_token(page, want_key)
        if not moved:
            observe(f"could not move the sidebar key to {want_key} for {title}")
    live = pk_val(page)
    goto_songs(page)
    added = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
    settle(page, 4)
    log(f"    queued {title}: sidebar={live!r} added={added}")
    return bool(added) and key_token(live) == key_token(want_key)


def phase_b_setlist(page: Page) -> bool:
    """The three songs from the report, each queued in its own key."""
    ok_say = queue_song(page, SAY[0], SAY[1], set_key=False, already_active=True)
    mark("B1 Say queued in Bb (its own key)", ok_say)
    ok_j = queue_song(page, JTTOU[0], JTTOU[1], set_key=True)
    mark("B2 Just the Two of Us queued in Db", ok_j)
    ok_p = queue_song(page, PERFECT[0], PERFECT[1], set_key=True)
    mark("B3 Perfect queued in Ab", ok_p)

    goto_songs(page)
    open_karaoke(page)
    body = shot(page, "b1-setlist")
    got = rows(page)
    (OUT / "b1-rows.json").write_text(json.dumps(got, indent=2), encoding="utf-8")
    mark("B4 three rows in the setlist", len(got) == 3, f"{len(got)} rows")
    labels = [r.get("label", "") for r in got]
    saved_ok = (
        len(got) == 3
        and "say" in low(labels[0]) and key_token(labels[0].split("·")[-1]) == "bb"
        and "two of us" in low(labels[1]) and key_token(labels[1].split("·")[-1]) == "db"
        and "perfect" in low(labels[2]) and key_token(labels[2].split("·")[-1]) == "ab"
    )
    mark("B5 each row shows its own saved key", saved_ok, f"labels={labels}")

    # Part 3b's starting condition, and the thing most worth protecting: Say's OWN Practice
    # Key, chosen here with nothing performing. The entry stays frozen at Bb; this is the
    # song's preference, and after a performance in Ab it must still be this.
    pick_song(page, OBSERVED, SAY[0], "pop")
    settle(page, 4)
    moved = set_pk_token(page, "D")
    settle(page, 4)
    now = pk_val(page)
    mark("B6 Say's own Practice Key is set to D with no set running",
         moved and key_token(now) == "d", f"practice key={now!r}")
    goto_songs(page)
    open_karaoke(page)
    after = rows(page)
    first = after[0].get("label", "") if after else ""
    mark("B7 the queued entry stayed at Bb when the song's own key moved",
         bool(first) and key_token(first.split("·")[-1]) == "bb", f"row={first!r}")
    return len(got) == 3 and "karaoke" in low(body)


def phase_c_icons_and_sources(page: Page) -> bool:
    """Part 6 and Part 7 on the Songs page, before anything is playing."""
    got = rows(page)
    sources = [(r.get("source"), r.get("chip"), r.get("chip_bg")) for r in got]
    # data-source carries the readable name lowercased: "catalog", "custom", "composition".
    all_catalog = bool(got) and all((r.get("source") or "") == "catalog" for r in got)
    mark("C1 every row names its source from metadata", all_catalog, f"{sources}")
    reds = [r for r in got if "src-catalog" in (r.get("classes") or "")]
    mark("C2 Catalog rows carry the catalog colour class", len(reds) == len(got),
         f"{len(reds)}/{len(got)}")
    bgs = {r.get("chip_bg") for r in got}
    mark("C3 the source chip is painted", bool(bgs) and all(b and b != "rgba(0, 0, 0, 0)" for b in bgs),
         f"{bgs}")
    worded = all((r.get("chip") or "").strip() for r in got)
    mark("C4 the source is readable as words, not only colour", worded,
         f"chips={[r.get('chip') for r in got]}")

    start = button_with(page, "karaoke set") or button_with(page, "start")
    clear = button_with(page, "clear setlist")
    mark("C5 Start carries the play icon and keeps its words",
         bool(start) and "▶" in (start or {}).get("text", ""),
         f"start={(start or {}).get('text')!r}")
    mark("C6 Clear Setlist carries the trash icon",
         bool(clear) and "\U0001f5d1" in (clear or {}).get("text", ""),
         f"clear={(clear or {}).get('text')!r}")
    distinct = bool(start and clear and start.get("text") != clear.get("text"))
    mark("C7 End/Start and Clear are not the same control", distinct)
    return True


def phase_d_perform(page: Page) -> bool:
    """Start the set and read what the performance says it is."""
    started = (click_text(page, "Start karaoke set") or click_text(page, "Start performance")
               or click_text(page, "Start setlist") or click_text(page, "Start"))
    settle(page, 8)
    body = shot(page, "d1-performing")
    performing = "now singing" in low(body)
    mark("D1 the set is performing", performing, f"(click helper {bool(started)})")

    # The active-song card with the key chips is the Backing card, and a karaoke performance
    # renders there. Read on the Songs page instead, there is no card at all and the only key
    # in sight is the sidebar's - which is the EDITING song's key by design (Issue 69C's two
    # authorities), so a gate reading it would fail about the wrong thing.
    click_nav(page, "Backing")
    settle(page, 6)
    shot(page, "d2-backing-performing")
    ident = card_identity(page)
    (OUT / "d1-card.json").write_text(json.dumps(ident, indent=2), encoding="utf-8")
    pk = card_practice_key(page, ident)
    mark("D2 the backing is the song being sung, in that entry's own key",
         "say" in low(str(ident.get("backing_song") or "")) and key_token(pk) == "bb",
         f"{ident.get('backing_line')!r}")
    mark("D3 the card shows the song's own Original Key",
         key_token(ident.get("original") or ident.get("sidebar_original") or "") == "bb",
         f"original={ident.get('original')!r} sidebar={ident.get('sidebar_original')!r}")

    stop = button_with(page, "end karaoke set") or button_with(page, "end karaoke")
    skip = button_with(page, "skip") or button_with(page, "next song")
    prev = button_with(page, "previous song")
    mark("D4 End karaoke set carries the stop icon",
         bool(stop) and "⏹" in (stop or {}).get("text", ""), f"{(stop or {}).get('text')!r}")
    mark("D5 Skip carries the next-track icon",
         bool(skip) and "⏭" in (skip or {}).get("text", ""), f"{(skip or {}).get('text')!r}")
    mark("D6 Previous carries the previous-track icon",
         bool(prev) and "⏮" in (prev or {}).get("text", ""), f"{(prev or {}).get('text')!r}")

    hints = page.locator('[class*="st-key-karaoke_show_chords_performance_toggle"]')
    mark("D7 the chord-hints control is reachable while singing", hints.count() > 0,
         f"{hints.count()} control(s)")

    sheet = "lead sheet: off" in low(body)
    mark("D8 the Lead Sheet starts Off", sheet, "" if sheet else "no 'Lead sheet: Off' on the page")
    return performing


def phase_e_temporary_key(page: Page) -> bool:
    """Part 3 and Part 3b: the performance follows, the setlist and the song's key do not."""
    played = press_play(page)
    if played:
        strip = wait_for_live_strip(page, 150)
        log(f"    live strip before the change: {strip}")
    else:
        observe("Play was not available before the key change; reading labels only")

    goto_songs(page)
    open_karaoke(page)
    before_rows = rows(page)
    before_label = (before_rows[0].get("label") if before_rows else "")
    if not before_rows:
        observe("no setlist rows visible before the key change")
    before_synth = synth_keys(regen_rows())
    before_traces = len(trace_rows())
    log(f"    synthesized before the change: {before_synth[-3:]}")
    moved = set_pk_token(page, "Ab")
    settle(page, 8)
    body = shot(page, "e1-retuned")
    mark("E1 the sidebar key moved to Ab during the performance", moved, f"pk={pk_val(page)!r}")

    after_rows = rows(page)
    after_label = (after_rows[0].get("label") if after_rows else "")
    row_held = bool(after_label) and key_token(after_label.split("·")[-1]) == "bb"
    mark("E3 the saved setlist row still reads Bb", row_held,
         f"{before_label!r} -> {after_label!r}")

    # The app's own account of the attempt. Env-gated (MUSIC_KARAOKE_RETUNE_TRACE), so an
    # empty list means "not traced", never "did not happen" - the distinction that made the
    # first two runs unreadable on this gate.
    new_traces = trace_rows()[before_traces:]
    for row in new_traces:
        log(f"    retune trace {row.get('stage')}: " + ", ".join(
            f"{k}={v!r}" for k, v in row.items() if k not in {"t", "stage"}))
    retunes = [r for r in new_traces if r.get("stage") == "retuned"]
    if not new_traces:
        observe("no retune trace rows at all: either the gesture never reached the app or the "
                "trace is not enabled (MUSIC_KARAOKE_RETUNE_TRACE)")
    mark("E4b the retune ran for this gesture", bool(retunes),
         f"{[(r.get('entry_key'), r.get('requested') or r.get('to')) for r in retunes]}"
         + (f" of {len(new_traces)} trace rows" if new_traces else " (nothing traced)"))
    # Every remaining reading belongs to the page where the performance renders. The setlist
    # rows above are on Songs, where there is no backing surface and no transport: reading
    # them there reported '' about the key and "skip helper False" about a perfectly good
    # button one page away.
    click_nav(page, "Backing")
    settle(page, 6)
    shot(page, "e1b-backing-after-retune")
    ident = card_identity(page)
    mark("E2 the backing surface is in the new key",
         key_token(ident.get("backing_key") or "") == "ab", f"{ident.get('backing_line')!r}")

    # The retune stops the transport on purpose - old-key audio must not keep playing under
    # new-key chord names - so nothing is rebuilt until Play is pressed again. An earlier
    # version of this gate looked for a rebuild that nothing had asked for.
    replayed = press_play(page)
    new_keys: list[str] = []
    if replayed:
        import time as _time

        deadline = _time.time() + 180
        while _time.time() < deadline:
            new_keys = synth_keys(regen_rows())[len(before_synth):]
            if any(key_token(k) == "ab" for k in new_keys):
                break
            settle(page, 3)
    else:
        observe("Play was not available after the re-key, so no rebuild could be measured")
    mark("E4 the backing was rebuilt in the new key",
         any(key_token(k) == "ab" for k in new_keys),
         f"synthesized since the change: {new_keys or '(nothing)'}")
    chords = live_chords(page)
    if chords.get("current"):
        log(f"    live strip after the change: {chords}")
    else:
        observe("the lead sheet is Off during karaoke, so there is no live chord strip to "
                "read; the synthesizer log is what answers for the audio")


    skipped = click_text(page, "Skip") or click_text(page, "Next song")
    settle(page, 8)
    shot(page, "e2-next-song")
    ident2 = card_identity(page)
    mark("E5 the next entry loads its own saved key",
         "two of us" in low(str(ident2.get("backing_song") or ""))
         and key_token(card_practice_key(page, ident2)) == "db",
         f"{ident2.get('backing_line')!r} (skip helper {bool(skipped)})")

    click_nav(page, "Backing")
    settle(page, 4)
    ended = click_text(page, "End karaoke set")
    settle(page, 8)
    body = shot(page, "e3-ended")
    mark("E6 the set ended", bool(ended) and "now singing" not in low(body))

    goto_songs(page)
    open_karaoke(page)
    shot(page, "e4-reopened")
    final = rows(page)
    (OUT / "e4-rows.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    labels = [r.get("label", "") for r in final]
    keys = [key_token(lbl.split("·")[-1]) for lbl in labels] if labels else []
    mark("E7 every saved key survived the performance", keys == ["bb", "db", "ab"], f"{keys}")
    mark("E8 ending the set did not delete the setlist", len(final) == 3, f"{len(final)} rows")
    return True


def phase_f_song_key_untouched(page: Page) -> bool:
    """Part 3b in the product: Say's own Practice Key, chosen outside karaoke, is still there.

    Say was queued at Bb, given its own Practice Key of D in phase B with nothing performing,
    and then sung at Ab. D is the musician's choice and must be what Say reopens in. Before
    this correction the Ab from the performance was written straight over it.
    """
    picked = pick_song(page, OBSERVED, SAY[0], "pop")
    settle(page, 5)
    pk = pk_val(page)
    shot(page, "f1-say-after-the-set")
    mark("F1 Say reopens on the Practice Key chosen outside karaoke",
         key_token(pk) == "d", f"practice key={pk!r} (want D, not the Ab it was sung in)")
    ident = card_identity(page)
    mark("F2 the card shows Say's own key, not the performance's",
         key_token(card_practice_key(page, ident)) == "d", f"card={ident}")
    mark("F3 Say's Original Key is untouched",
         key_token(ident.get("original") or ident.get("sidebar_original") or "") == "bb",
         f"original={ident.get('original')!r} sidebar={ident.get('sidebar_original')!r}")
    return bool(picked)


def phase_g_narrow(page: Page, width: int) -> bool:
    """Measure the same surfaces at a phone width. Driven at desktop, measured here."""
    page.set_viewport_size({"width": width, "height": 900})
    settle(page, 4)
    expand_sidebar(page)
    goto_songs(page)
    open_karaoke(page)
    body = shot(page, f"g-{width}")
    got = rows(page)
    clipped = [r for r in got if r.get("clipped")]
    mark(f"G{width}-1 setlist rows are not clipped at {width}px", not clipped,
         f"{len(clipped)} clipped of {len(got)}")
    worded = bool(got) and all((r.get("chip") or "").strip() for r in got)
    mark(f"G{width}-2 the source words survive at {width}px", worded,
         f"chips={[r.get('chip') for r in got]}")
    btns = buttons(page)
    over = [b for b in btns if b.get("clipped")]
    mark(f"G{width}-3 no control hangs off the viewport at {width}px", not over,
         f"{[b.get('text') for b in over][:4]}")
    start = button_with(page, "karaoke set") or button_with(page, "start")
    mark(f"G{width}-4 the transport icons are still on their buttons at {width}px",
         bool(start) and "▶" in (start or {}).get("text", ""),
         f"start={(start or {}).get('text')!r}")
    return "karaoke" in low(body)


def main() -> int:
    phases = [
        ("A", phase_a_setup),
        ("B", phase_b_setlist),
        ("C", phase_c_icons_and_sources),
        ("D", phase_d_perform),
        ("E", phase_e_temporary_key),
        ("F", phase_f_song_key_untouched),
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        try:
            for name, fn in phases:
                log(f"\n==== phase {name} ====")
                try:
                    fn(page)
                except Exception as exc:
                    mark(f"{name}0 phase {name} ran to completion", False, f"{type(exc).__name__}: {exc}")
                    shot(page, f"zz-crash-{name}")
                if STOP_AFTER and name == STOP_AFTER:
                    break
            if not STOP_AFTER:
                for width in (390, 360):
                    log(f"\n==== phase G {width} ====")
                    try:
                        phase_g_narrow(page, width)
                    except Exception as exc:
                        mark(f"G{width}-0 narrow pass ran", False, f"{type(exc).__name__}: {exc}")
                        shot(page, f"zz-crash-{width}")
        finally:
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 72)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8"
    )
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
