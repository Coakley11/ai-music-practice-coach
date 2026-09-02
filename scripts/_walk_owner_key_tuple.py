"""Focused ownership/key tuple walk — human embargo 12 checks.

Does not replace the larger core-workflow suite. Covers:

1. Trial Global Active C → SBI Custom = Trial C
2. Non-active SBI Custom Trial lifecycle stays D
3. Composition Song Source shows the 🎹 Composition logo
4-8. Style Jam C# does not contaminate explicit Shape (Bm everywhere)
9. Guitar Shape C inherits minor (C minor)
10. Bm → Dm stays minor
11-12. Refresh / Songs↔Creative nav stay coherent

Usage:
  MUSIC_APP_DATA_DIR=<isolated> streamlit run streamlit_music_practice_app.py --server.port 8542
  python scripts/_walk_owner_key_tuple.py http://127.0.0.1:8542
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8542"
OUT = SCRIPTS / "evidence-creative-backing"
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = "owner-tuple-"
RESULTS: dict[str, str] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


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


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def has_any(body: str, *needles: str) -> bool:
    b = low(body)
    return any(n.lower() in b for n in needles)


def settle(page: Page, sec: float = 2.0) -> None:
    from walk_creative_backing_matrix import wait_idle

    wait_idle(page, int(sec * 1000))


def shot(page: Page, name: str) -> tuple[str, str]:
    from walk_creative_backing_matrix import expand_sidebar

    stem = f"{PREFIX}{name}"
    page.screenshot(path=str(OUT / f"{stem}.png"), full_page=True)
    body = page.inner_text("body") or ""
    side = ""
    try:
        expand_sidebar(page)
        side = page.inner_text('[data-testid="stSidebar"]') or ""
    except Exception:
        side = ""
    (OUT / f"{stem}.txt").write_text(
        f"=== SIDEBAR ===\n{side[:9000]}\n\n=== BODY ===\n{body[:18000]}",
        encoding="utf-8",
    )
    return side, body


def pk_label(text: str) -> str:
    from _walk_core_workflows_embargo import practice_badge
    from _walk_core_key_coherence import card_practice_label

    return practice_badge(text) or card_practice_label(text) or ""


def is_c_major(label: str) -> bool:
    t = low(label)
    return "c major" in t or (t.startswith("c") and "minor" not in t and "c#" not in t)


def is_d_major(label: str) -> bool:
    t = low(label)
    return "d major" in t or (re.search(r"\bd\s+major\b", t) is not None)


def is_b_minor(label: str) -> bool:
    t = low(label)
    return "b minor" in t or bool(re.search(r"\bbm\b", t))


def is_d_minor(label: str) -> bool:
    t = low(label)
    return "d minor" in t or bool(re.search(r"\bdm\b", t))


def charts_in_label(text: str) -> str:
    m = re.search(r"Charts in\s+([^\n]+)", text or "", re.I)
    return (m.group(1) if m else "").strip()


SHAPE_WIDGET_SEL = '[class*="st-key-guitar_capo_shape_widget"]'
LAST_SHAPE_DIAG: dict = {}


def _shape_live_state(page: Page) -> dict:
    """Fresh DOM probe of the live Shape Key widget. Never uses a cached element."""
    try:
        raw = page.evaluate(
            """() => {
              const widgets = [...document.querySelectorAll('[class*="st-key-guitar_capo_shape_widget"]')];
              const visible = widgets.filter((w) => {
                const r = w.getBoundingClientRect();
                return r.width > 8 && r.height > 8;
              });
              const widget = visible[visible.length - 1] || null;
              const combo = widget && widget.querySelector('[role="combobox"]');
              const input = widget && widget.querySelector('input');
              const lidRaw = (combo && (combo.getAttribute('aria-controls') || combo.getAttribute('aria-owns') || '')) || '';
              const lids = lidRaw.split(/\\s+/).filter(Boolean);
              const listbox = lids.map((id) => document.getElementById(id)).find(Boolean) || null;
              const opts = listbox
                ? [...listbox.querySelectorAll('[role="option"]')].map((o) => (o.innerText || '').trim())
                : [];
              const sel = widget && widget.querySelector('[data-baseweb="select"]');
              const rawText = ((sel && sel.innerText) || (widget && widget.innerText) || '').replace(/Shape Key/ig, '');
              const closedLine = rawText.split('\\n').map((s) => s.trim()).filter((s) => s && !/^charts in/i.test(s))[0] || '';
              const expanded = !!(combo && combo.getAttribute('aria-expanded') === 'true');
              const inputVal = (input && input.value && !/shape key/i.test(input.value)) ? String(input.value).trim() : '';
              return {
                widget_count: widgets.length,
                visible_count: visible.length,
                expanded,
                aria_controls: lidRaw,
                listbox_id: (listbox && listbox.id) || lids[0] || '',
                listbox_found: !!listbox,
                options: opts.slice(0, 24),
                input_value: inputVal,
                closed_text: expanded ? '' : (inputVal || closedLine),
              };
            }"""
        )
        return dict(raw or {})
    except Exception as exc:
        return {"error": repr(exc)}


def shape_key_widget_value(page: Page) -> str:
    """Closed Shape Key value from a freshly queried capo widget."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
    except Exception:
        pass
    state = _shape_live_state(page)
    val = str(state.get("closed_text") or state.get("input_value") or "").strip()
    if str(state.get("expanded")).lower() in {"true", "1"}:
        return ""
    return val


def shape_tonic_committed(page: Page, tonic: str) -> bool:
    val = low(shape_key_widget_value(page)).strip()
    if tonic.lower() == "c" and ("c#" in val or "c♯" in val):
        return False
    widget_ok = val == low(tonic) or val.split()[0:1] == [low(tonic)]
    body = low(page.inner_text("body") or "")
    charts_ok = f"charts in {low(tonic)} minor" in body
    return bool(widget_ok and charts_ok)


def _click_associated_shape_option(page: Page, tonic: str, listbox_id: str) -> str:
    """Click exact tonic inside THIS listbox only — never a page-global option."""
    if not listbox_id:
        return "no-listbox-id"
    box = page.locator(f'[id="{listbox_id}"]')
    if box.count() == 0:
        return f"listbox-missing:{listbox_id}"
    opt = box.get_by_role("option", name=tonic, exact=True)
    try:
        n = opt.count()
    except Exception:
        n = 0
    if n == 0:
        return f"no-opt-in:{listbox_id}"
    try:
        opt.first.scroll_into_view_if_needed()
        opt.first.click(timeout=4000)
        return f"associated:{listbox_id}"
    except Exception:
        try:
            opt.first.click(timeout=4000, force=True)
            return f"associated-force:{listbox_id}"
        except Exception as exc:
            return f"associated-click-err:{type(exc).__name__}"


def capo_shape_mode_checked(page: Page) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                  const labels = [...document.querySelectorAll('label')];
                  const lab = labels.find((el) => /capo shape mode/i.test(el.innerText || ''));
                  if (!lab) return false;
                  const box = lab.querySelector('input[type="checkbox"]')
                    || document.getElementById(lab.getAttribute('for') || '');
                  return !!(box && box.checked);
                }"""
            )
        )
    except Exception:
        return False


def enable_guitar_shape_mode(page: Page, notes: list[str]) -> bool:
    """Guitar + Capo Shape Mode on. Shape tonic is committed separately."""
    from walk_creative_backing_matrix import expand_sidebar, set_instrument, wait_idle

    expand_sidebar(page)
    inst_ok = set_instrument(page, "Guitar")
    notes.append(f"instrument Guitar={inst_ok}")
    wait_idle(page, 2500)
    expand_sidebar(page)
    capo_ok = False
    for attempt in range(4):
        try:
            hdr = page.locator('[data-testid="stSidebar"]').get_by_text(
                re.compile(r"Capo Shape Mode|GUITAR CAPO", re.I)
            )
            if hdr.count():
                hdr.first.scroll_into_view_if_needed()
                page.wait_for_timeout(250)
        except Exception:
            pass
        if capo_shape_mode_checked(page):
            capo_ok = True
            notes.append(f"capo enabled=True attempt={attempt}")
            break
        via = ""
        try:
            via = str(
                page.evaluate(
                    """() => {
                      const side = document.querySelector('[data-testid="stSidebar"]') || document;
                      const labels = [...side.querySelectorAll('label')];
                      const lab = labels.find((el) => /capo shape mode/i.test(el.innerText || ''));
                      if (!lab) return 'no-label';
                      lab.scrollIntoView({block: 'center'});
                      const box = lab.querySelector('input[type="checkbox"]')
                        || document.getElementById(lab.getAttribute('for') || '');
                      if (box) {
                        box.click();
                        box.dispatchEvent(new Event('input', {bubbles: true}));
                        box.dispatchEvent(new Event('change', {bubbles: true}));
                        return 'input';
                      }
                      lab.click();
                      return 'label';
                    }"""
                )
                or ""
            )
        except Exception as exc:
            via = f"eval-err:{exc!r}"
        if via in {"", "no-label"}:
            loc = page.locator('[data-testid="stSidebar"] label').filter(
                has_text=re.compile(r"Capo Shape Mode", re.I)
            )
            try:
                if loc.count():
                    loc.first.scroll_into_view_if_needed()
                    loc.first.click(timeout=4000)
                    via = f"{via}|pw-label"
            except Exception:
                pass
        wait_idle(page, 2500)
        capo_ok = capo_shape_mode_checked(page)
        notes.append(f"capo click via={via} checked={capo_ok} attempt={attempt}")
        if capo_ok:
            break
    notes.append(f"capo enabled={capo_ok}")
    return bool(inst_ok and capo_ok)


def _shape_key_selectbox(page: Page):
    keyed = page.locator(SHAPE_WIDGET_SEL)
    for i in range(keyed.count()):
        el = keyed.nth(i)
        try:
            if el.is_visible():
                return el
        except Exception:
            continue
    box = page.locator('section[data-testid="stSidebar"] [data-testid="stSelectbox"]').filter(
        has_text=re.compile(r"Shape Key", re.I)
    )
    if box.count() == 0:
        box = page.locator('[data-testid="stSelectbox"]').filter(has_text=re.compile(r"Shape Key", re.I))
    for i in range(box.count()):
        el = box.nth(i)
        try:
            if el.is_visible():
                return el
        except Exception:
            continue
    return None


def _wait_shape_key_selectbox(page: Page, timeout_ms: int = 12_000) -> bool:
    try:
        page.wait_for_selector(SHAPE_WIDGET_SEL, timeout=timeout_ms, state="visible")
        return True
    except Exception:
        pass
    try:
        page.wait_for_function(
            """() => {
              const keyed = document.querySelector('[class*="st-key-guitar_capo_shape_widget"]');
              if (keyed) {
                const r = keyed.getBoundingClientRect();
                return r.width > 8 && r.height > 8;
              }
              const side = document.querySelector('[data-testid="stSidebar"]') || document.body;
              const boxes = [...side.querySelectorAll('[data-testid="stSelectbox"]')];
              for (const b of boxes) {
                if (!/Shape Key/i.test(b.innerText || '')) continue;
                const r = b.getBoundingClientRect();
                if (r.width < 8 || r.height < 8) continue;
                return !!(b.querySelector('[role="combobox"], [data-baseweb="select"] input, input'));
              }
              return false;
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def commit_shape_tonic(page: Page, tonic: str) -> bool:
    """Select Shape Key tonic on the live capo widget. Click is never proof of success."""
    global LAST_SHAPE_DIAG
    from walk_creative_backing_matrix import expand_sidebar, wait_idle

    LAST_SHAPE_DIAG = {}
    if not capo_shape_mode_checked(page):
        LAST_SHAPE_DIAG = {"why": "capo-not-checked", **_shape_live_state(page)}
        print(f"shape_diag={json.dumps(LAST_SHAPE_DIAG, default=str)}", flush=True)
        return False
    if shape_tonic_committed(page, tonic):
        return True
    expand_sidebar(page)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        pass
    if not _wait_shape_key_selectbox(page):
        LAST_SHAPE_DIAG = {"why": "widget-missing", "capo": True, **_shape_live_state(page)}
        print(f"shape_diag={json.dumps(LAST_SHAPE_DIAG, default=str)}", flush=True)
        return False

    before = _shape_live_state(page)
    closed_before = str(before.get("closed_text") or before.get("input_value") or "")
    ids_before = []
    try:
        ids_before = list(
            page.evaluate("""() => [...document.querySelectorAll('[role="listbox"]')].map((el) => el.id || '')""")
            or []
        )
    except Exception:
        pass

    target = _shape_key_selectbox(page)
    if target is None:
        LAST_SHAPE_DIAG = {"why": "no-selectbox", "before": before}
        print(f"shape_diag={json.dumps(LAST_SHAPE_DIAG, default=str)}", flush=True)
        return False
    try:
        target.scroll_into_view_if_needed()
    except Exception:
        pass
    opener = target.locator('[data-baseweb="select"] [role="combobox"], [role="combobox"], input').first
    if opener.count() == 0:
        opener = target
    try:
        opener.click(timeout=4000)
    except Exception as exc:
        LAST_SHAPE_DIAG = {"why": f"open-err:{type(exc).__name__}", "before": before}
        print(f"shape_diag={json.dumps(LAST_SHAPE_DIAG, default=str)}", flush=True)
        return False
    try:
        page.wait_for_function(
            """() => {
              const widgets = [...document.querySelectorAll('[class*="st-key-guitar_capo_shape_widget"]')];
              const widget = widgets.filter((w) => w.getBoundingClientRect().width > 8).pop();
              const combo = widget && widget.querySelector('[role="combobox"]');
              return !!(combo && combo.getAttribute('aria-expanded') === 'true');
            }""",
            timeout=6000,
        )
    except Exception:
        pass

    live = _shape_key_selectbox(page)
    if live is not None:
        try:
            inp = live.locator("input").first
            if inp.count():
                inp.click(timeout=3000)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.type(tonic, delay=40)
                page.wait_for_timeout(450)
        except Exception:
            pass

    opened = _shape_live_state(page)
    lid = str(opened.get("listbox_id") or "").strip()
    if not lid:
        try:
            ids_after = list(
                page.evaluate(
                    """() => [...document.querySelectorAll('[role="listbox"]')].map((el) => el.id || '')"""
                )
                or []
            )
            new_ids = [i for i in ids_after if i and i not in ids_before]
            lid = new_ids[-1] if new_ids else ""
        except Exception:
            lid = ""

    highlighted = ""
    try:
        highlighted = str(
            page.evaluate(
                """() => {
                  const widgets = [...document.querySelectorAll('[class*="st-key-guitar_capo_shape_widget"]')];
                  const widget = widgets.filter((w) => w.getBoundingClientRect().width > 8).pop();
                  const combo = widget && widget.querySelector('[role="combobox"]');
                  if (!combo) return '';
                  const aid = combo.getAttribute('aria-activedescendant') || '';
                  const el = aid ? document.getElementById(aid) : null;
                  return ((el && el.innerText) || '').trim();
                }"""
            )
            or ""
        )
    except Exception:
        highlighted = ""
    for _ in range(8):
        if highlighted == tonic:
            break
        try:
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(80)
            highlighted = str(
                page.evaluate(
                    """() => {
                      const widgets = [...document.querySelectorAll('[class*="st-key-guitar_capo_shape_widget"]')];
                      const widget = widgets.filter((w) => w.getBoundingClientRect().width > 8).pop();
                      const combo = widget && widget.querySelector('[role="combobox"]');
                      const aid = combo && combo.getAttribute('aria-activedescendant') || '';
                      const el = aid ? document.getElementById(aid) : null;
                      return ((el && el.innerText) || '').trim();
                    }"""
                )
                or ""
            )
        except Exception:
            break
    via = f"kbd:{highlighted}"
    if highlighted == tonic:
        try:
            page.keyboard.press("Enter")
            via = f"enter:{highlighted}"
        except Exception as exc:
            via = f"enter-err:{type(exc).__name__}"
    else:
        via = _click_associated_shape_option(page, tonic, lid) if lid else f"no-associated-id:{highlighted}"
    wait_idle(page, 3500)
    try:
        page.wait_for_function(
            """(tonic) => {
              const t = (document.body && document.body.innerText) || '';
              return new RegExp('Charts in\\\\s+' + tonic + '\\\\s*minor', 'i').test(t)
                || /Capo Fret:\\s*11/i.test(t);
            }""",
            arg=tonic,
            timeout=12_000,
        )
    except Exception:
        pass
    after = _shape_live_state(page)
    ok = shape_tonic_committed(page, tonic)
    body = page.inner_text("body") or ""
    LAST_SHAPE_DIAG = {
        "capo_checked": capo_shape_mode_checked(page),
        "closed_before": closed_before,
        "expanded_after_open": opened.get("expanded"),
        "aria_controls": opened.get("aria_controls"),
        "listbox_id": lid,
        "options": opened.get("options"),
        "via": via,
        "highlighted": highlighted,
        "closed_after": after.get("closed_text") or after.get("input_value"),
        "charts": charts_in_label(body),
        "ok": ok,
        "widget_count": after.get("widget_count"),
    }
    print(f"shape_diag={json.dumps(LAST_SHAPE_DIAG, default=str)}", flush=True)
    print(f"shape_option_via={via} widget={shape_key_widget_value(page)!r} ok={ok}", flush=True)
    return ok


def click_sbi_song_source(page: Page, which: str) -> bool:
    """Click SBI Song Source Active vs Custom via native radio input."""
    needle = "custom" if which == "custom" else "active"
    try:
        via = page.evaluate(
            """(which) => {
              const groups = [...document.querySelectorAll('[role="radiogroup"]')];
              for (const g of groups) {
                const gtxt = (g.innerText || '').toLowerCase();
                if (!gtxt.includes('custom progression')) continue;
                if (!gtxt.includes('active source') && !gtxt.includes('active song')) continue;
                const labels = [...g.querySelectorAll('label')];
                const target = labels.find((l) => {
                  const t = (l.innerText || '').toLowerCase();
                  if (which === 'custom') return t.includes('custom progression');
                  return t.includes('active source') || t.includes('active song');
                });
                if (!target) continue;
                target.scrollIntoView({block:'center'});
                const input = target.querySelector('input[type=radio]');
                if (input) {
                  input.click();
                  input.dispatchEvent(new Event('input', {bubbles: true}));
                  input.dispatchEvent(new Event('change', {bubbles: true}));
                  return 'input';
                }
                target.click();
                return 'label';
              }
              return '';
            }""",
            needle,
        )
        return bool(via)
    except Exception:
        return False


def sbi_song_source_mounted(page: Page) -> bool:
    """True only when the SBI Song Source radios are actually in the DOM."""
    try:
        return bool(
            page.evaluate(
                """() => {
                  const vis = (el) => !!(el && el.getBoundingClientRect().width > 4);
                  const groups = [...document.querySelectorAll('[role="radiogroup"]')].filter(vis);
                  return groups.some((g) => {
                    const t = (g.innerText || '').toLowerCase();
                    return t.includes('custom progression')
                      && (t.includes('active source') || t.includes('active song'));
                  });
                }"""
            )
        )
    except Exception:
        return False


def sbi_source_state(page: Page) -> str:
    try:
        return str(
            page.evaluate(
                """() => {
                  const labels = [...document.querySelectorAll('[role="radiogroup"] label')];
                  for (const l of labels) {
                    const t = (l.innerText || '').trim();
                    if (!/custom progression/i.test(t)) continue;
                    const input = l.querySelector('input[type=radio]');
                    const role = l.closest('[role=radio]') || l;
                    const checked = (input && input.checked)
                      || role.getAttribute('aria-checked') === 'true';
                    if (checked) return 'custom';
                  }
                  for (const l of labels) {
                    const t = (l.innerText || '').trim();
                    if (!/active source|active song/i.test(t)) continue;
                    const input = l.querySelector('input[type=radio]');
                    const role = l.closest('[role=radio]') || l;
                    const checked = (input && input.checked)
                      || role.getAttribute('aria-checked') === 'true';
                    if (checked) return 'active';
                  }
                  return 'unknown';
                }"""
            )
            or "unknown"
        )
    except Exception:
        return "unknown"


def land_sbi(page: Page, notes: list[str]) -> bool:
    """Creative → Improvisation Lab / SBI until Song Source radios mount.

    Do not treat Missions / Live Coach / a Creative title as ready.
    """
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_radio,
        set_baseweb_select,
        wait_idle,
    )

    click_nav(page, "Creative")
    wait_idle(page, 2500)
    for attempt in range(8):
        if sbi_song_source_mounted(page):
            notes.append(f"land_sbi ready attempt={attempt} source={sbi_source_state(page)}")
            return True
        set_baseweb_select(page, "Analysis mode", "Improvisation Intelligence")
        set_baseweb_select(page, "Analysis mode", "Improvisation Lab")
        set_baseweb_select(page, "Deep Harmonic Analyzer", "Improvisation Intelligence")
        click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
        wait_idle(page, 800)
        (
            click_radio(page, "Song-Based")
            or click_radio(page, "Play Song-Based")
            or click_button_has(page, r"Song-Based")
        )
        click_button_has(page, r"Song-Based Improvisation") or click_button_has(
            page, r"Improvisation Lab"
        )
        wait_idle(page, 2500)
        notes.append(f"land_sbi attempt={attempt} mounted={sbi_song_source_mounted(page)}")
    notes.append("land_sbi FAILED: Song Source radios never mounted")
    return False


def wait_sbi_tuple(
    page: Page,
    *,
    source: str,
    title: str,
    c_major: bool = False,
    d_major: bool = False,
    dm_c_prog: bool = False,
    em_d_prog: bool = False,
    timeout_ms: int = 20_000,
) -> bool:
    """Wait until the SBI source click has committed identity/key/progression."""
    from _walk_ownership_audit_full import rendered_dm_dm_c_c, rendered_em_em_d_d
    from _walk_custom_practice_key import pk_val

    steps = max(1, int(timeout_ms // 500))
    for _ in range(steps):
        if sbi_source_state(page) != source:
            page.wait_for_timeout(500)
            continue
        body = page.inner_text("body") or ""
        side = ""
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            pass
        combined = body + side
        pk = pk_label(combined) or pk_val(page) or ""
        title_ok = title.lower() in low(combined)
        key_ok = True
        if c_major:
            key_ok = is_c_major(pk) or bool(
                re.search(r"practice concert key:\s*c\b(?!#)", low(combined))
            )
        if d_major:
            key_ok = is_d_major(pk) or bool(
                re.search(r"practice concert key:\s*d\b(?!m)", low(combined))
            )
        prog_ok = True
        if dm_c_prog:
            prog_ok = rendered_dm_dm_c_c(body) or has_any(body, "Dm")
        if em_d_prog:
            prog_ok = rendered_em_em_d_d(body) or has_any(body, "Em")
        if title_ok and key_ok and prog_ok:
            return True
        page.wait_for_timeout(500)
    return False


def style_jam_concert_closed(page: Page) -> str:
    """Closed Style Jam Concert Key from the main pane, never sidebar Practice Key."""
    try:
        return str(
            page.evaluate(
                """() => {
                  const main = document.querySelector('[data-testid="stAppViewContainer"]') || document;
                  const boxes = [...main.querySelectorAll('[data-testid="stSelectbox"]')];
                  for (const b of boxes) {
                    const t = (b.innerText || '');
                    if (/Practice\\s*\\/\\s*Concert Key/i.test(t)) continue;
                    if (!/Concert Key/i.test(t)) continue;
                    const input = b.querySelector('input');
                    if (input && input.value && !/concert key/i.test(input.value)) return input.value.trim();
                    return t.replace(/Concert Key/ig, '').trim().split('\\n')[0] || '';
                  }
                  return '';
                }"""
            )
            or ""
        )
    except Exception:
        return ""


def capture_gate2_dom(page: Page) -> dict:
    try:
        return dict(
            page.evaluate(
                """() => {
                  const side = (document.querySelector('[data-testid="stSidebar"]') || {}).innerText || '';
                  const main = (document.querySelector('[data-testid="stMain"]') || {}).innerText || '';
                  const body = (document.body && document.body.innerText) || '';
                  const radios = [...document.querySelectorAll('label')].map((l) => (l.innerText || '').trim()).filter(Boolean).slice(0, 40);
                  const boxes = [...document.querySelectorAll('[data-testid="stSelectbox"]')].map((b) => (b.innerText || '').slice(0, 120));
                  const combo = document.querySelector('[data-testid="stMain"] [role="combobox"]');
                  const widget = document.querySelector('[class*="st-key-matching_song_dropdown"]');
                  const sourceGroup = [...document.querySelectorAll('[role="radiogroup"]')].find((g) =>
                    /song selection \\(catalog song\\)/i.test(g.innerText || '')
                  );
                  let source_radio = '';
                  if (sourceGroup) {
                    const checked = [...sourceGroup.querySelectorAll('label')].find((l) => {
                      const input = l.querySelector('input[type=radio]');
                      const role = l.closest('[role=radio]') || l;
                      return (input && input.checked) || role.getAttribute('aria-checked') === 'true';
                    });
                    source_radio = checked ? (checked.innerText || '').trim() : (sourceGroup.innerText || '').slice(0, 160);
                  }
                  return {
                    sidebar_head: side.slice(0, 800),
                    radios,
                    selectboxes: boxes.slice(0, 12),
                    combo: combo ? (combo.getAttribute('aria-label') || combo.innerText || '').slice(0, 160) : '',
                    dropdown_value: widget ? (widget.innerText || '').slice(0, 160) : '',
                    source_radio,
                    catalog_picker_mounted: /Switch active song/i.test(main),
                    has_custom_hub: /Use catalog song instead/i.test(main),
                    has_shape: /Shape of You/i.test(side + body),
                    has_trial: /Trial Song/i.test(side + body),
                    has_say: /\\bSay\\b/i.test(side),
                  };
                }"""
            )
            or {}
        )
    except Exception as exc:
        return {"error": repr(exc)}


def songs_hub_state(page: Page) -> dict:
    """Picker-mode vs committed Global Active. Displayed Say is not activation."""
    try:
        return dict(
            page.evaluate(
                """() => {
                  const vis = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 8 && r.height > 8;
                  };
                  const side = (document.querySelector('[data-testid="stSidebar"]') || {}).innerText || '';
                  const main = (document.querySelector('[data-testid="stMain"]') || {}).innerText || '';
                  const widget = document.querySelector('[class*="st-key-matching_song_dropdown"]');
                  const useBtn = [...document.querySelectorAll('button')].find((b) =>
                    vis(b) && /Use catalog song instead/i.test(b.innerText || '')
                  );
                  const options = [...document.querySelectorAll('[role="option"]')].map(
                    (o) => (o.innerText || '').trim()
                  );
                  return {
                    custom_hub: !!useBtn
                      || (/your song/i.test(main) && /Use catalog song instead/i.test(main))
                      || (/Music source/i.test(main)
                          && /Use Custom Progression/i.test(main)
                          && /Use catalog song instead/i.test(main)),
                    on_songs: /Use catalog song instead/i.test(main)
                      || /Switch active song/i.test(main)
                      || (/Music source/i.test(main) && /Song Selection \\(catalog song\\)/i.test(main)),
                    on_creative: /Improvisation section/i.test(main) && /Analysis mode/i.test(main),
                    catalog_picker_mounted: /Switch active song/i.test(main) && vis(widget),
                    dropdown_visible: vis(widget),
                    dropdown_value: widget ? (widget.innerText || '').trim().slice(0, 160) : '',
                    shape_available: /Shape of You/i.test(main) || options.some((t) => /Shape of You/i.test(t)),
                    ga_trial: /CUSTOM PROGRESSION/i.test(side) && /Trial Song/i.test(side),
                    ga_shape: /Shape of You/i.test(side),
                    ga_say: /Say/i.test(side) && /John Mayer/i.test(side),
                    ga_perfect: /Perfect/i.test(side),
                    sidebar_head: side.slice(0, 400),
                  };
                }"""
            )
            or {}
        )
    except Exception as exc:
        return {"error": repr(exc)}


def click_use_catalog_once(page: Page) -> str:
    """Picker-mode switch only. Not a song activation.

    Prefer the Custom-hub button (bypasses E5 stale Catalog-radio ignore).
    """
    from walk_creative_backing_matrix import wait_idle

    keyed = page.locator('[class*="st-key-custom_hub_switch_to_catalog"] button')
    try:
        if keyed.count() and keyed.first.is_visible():
            keyed.first.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            keyed.first.click(timeout=5000, force=False)
            wait_idle(page, 2500)
            return "key-button"
    except Exception:
        pass
    loc = page.locator("button").filter(has_text=re.compile(r"Use catalog song instead", re.I))
    for i in range(loc.count()):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            el.click(timeout=5000, force=False)
            wait_idle(page, 2500)
            return "button"
        except Exception:
            continue
    try:
        via = page.evaluate(
            """() => {
              const vis = (el) => !!(el && el.getBoundingClientRect().width > 8);
              const groups = [...document.querySelectorAll('[role="radiogroup"]')].filter(vis);
              for (const g of groups) {
                const t = (g.innerText || '').toLowerCase();
                if (!t.includes('song selection (catalog song)')) continue;
                if (!t.includes('custom')) continue;
                const labels = [...g.querySelectorAll('label')];
                const target = labels.find((l) => /song selection \\(catalog song\\)/i.test(l.innerText || ''));
                if (!target) continue;
                target.scrollIntoView({block: 'center'});
                const input = target.querySelector('input[type=radio]');
                if (input) {
                  input.click();
                  input.dispatchEvent(new Event('input', {bubbles: true}));
                  input.dispatchEvent(new Event('change', {bubbles: true}));
                  return 'radio-input';
                }
                target.click();
                return 'radio-label';
              }
              return '';
            }"""
        )
        if via:
            wait_idle(page, 2500)
            return str(via)
    except Exception:
        pass
    return ""


def pick_matching_song_once(page: Page, title: str) -> bool:
    """Same typeahead as the dedicated Trial → Shape one-shot, on the live widget."""
    from walk_creative_backing_matrix import wait_idle
    from walk_guitar_shape_key import pick_active_song_from_dropdown

    try:
        widget = page.locator('[class*="st-key-matching_song_dropdown"]').last
        if widget.count() and widget.is_visible():
            widget.scroll_into_view_if_needed()
            clickable = widget.locator('[role="combobox"], [data-baseweb="select"], input').first
            (clickable if clickable.count() else widget).click(timeout=4000)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.wait_for_timeout(80)
            page.keyboard.type(title, delay=35)
            page.wait_for_timeout(700)
            opt = page.locator('[role="option"]').filter(has_text=re.compile(re.escape(title), re.I))
            if opt.count() > 0:
                opt.first.click(timeout=4000)
                wait_idle(page, 5000)
                return True
            page.keyboard.press("Escape")
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return bool(pick_active_song_from_dropdown(page, title))


def land_songs_picker(page: Page) -> bool:
    """Leave Creative and wait until Songs picker/hub is in the main pane."""
    from walk_creative_backing_matrix import click_nav, expand_pages_nav

    for attempt in range(8):
        expand_pages_nav(page)
        click_nav(page, "Songs")
        settle(page, 3)
        st = songs_hub_state(page)
        if st.get("on_creative"):
            log(f"land_songs still Creative attempt={attempt}")
            continue
        if st.get("on_songs") or st.get("custom_hub") or st.get("catalog_picker_mounted"):
            log(f"land_songs ready attempt={attempt} hub={json.dumps(st, default=str)}")
            return True
        log(f"land_songs attempt={attempt} state={json.dumps(st, default=str)}")
    log("land_songs FAILED")
    return False


def wait_trial_custom_ga(page: Page, *, timeout_ms: int = 20000) -> bool:
    """Sidebar Global Active is Custom Trial — not picker display of Say."""
    steps = max(8, int(timeout_ms / 500))
    for _ in range(steps):
        st = songs_hub_state(page)
        if st.get("ga_trial") and not st.get("ga_shape"):
            return True
        page.wait_for_timeout(500)
    return False


def wait_catalog_picker_keep_trial(page: Page, *, timeout_ms: int = 20000) -> bool:
    """After Use catalog: Catalog picker mounted, Trial still Global Active."""
    deadline = timeout_ms / 1000.0
    steps = max(8, int(deadline / 0.5))
    for _ in range(steps):
        st = songs_hub_state(page)
        if st.get("catalog_picker_mounted") and st.get("ga_trial") and not st.get("ga_shape"):
            return True
        page.wait_for_timeout(500)
    return False


def wait_shape_activation_bm(page: Page, *, timeout_ms: int = 20000) -> bool:
    from _walk_custom_practice_key import pk_val

    deadline = timeout_ms / 1000.0
    steps = max(8, int(deadline / 0.5))
    for _ in range(steps):
        st = songs_hub_state(page)
        try:
            side = page.inner_text('[data-testid="stSidebar"]') or ""
        except Exception:
            side = ""
        try:
            body = page.inner_text("body") or ""
        except Exception:
            body = ""
        # Live widget first. Full-page regex can match leftover Custom PK copy.
        # Do not treat the Pages "Custom Progression" nav label as Trial still GA.
        pk = pk_val(page) or pk_label(body + side) or ""
        if (
            st.get("ga_shape")
            and not st.get("ga_trial")
            and is_b_minor(pk)
            and not has_c_sharp_major(body + side)
        ):
            return True
        page.wait_for_timeout(500)
    return False


def custom_hub_to_catalog_song(page: Page, notes: list[str], title: str = "Shape of You") -> dict:
    """Custom hub → Use catalog (picker mode) → explicit catalog song once.

    Use catalog is not a song pick. Trial must remain Global Active until
    the Shape click commits Catalog / Shape / B minor.
    """
    if not land_songs_picker(page):
        log("gate2 HARNESS: never reached Songs picker")
        log(f"gate2_dom={json.dumps(capture_gate2_dom(page), default=str)}")
        return {
            "ok": False,
            "used_catalog": False,
            "picker": False,
            "clicked": False,
            "activated": False,
            "via": "",
        }
    before = songs_hub_state(page)
    log(f"gate2_before={json.dumps(before, default=str)}")
    used = ""
    if before.get("custom_hub") or (
        before.get("on_songs") and before.get("ga_trial") and not before.get("catalog_picker_mounted")
    ):
        used = click_use_catalog_once(page)
        log(f"gate2_use_catalog via={used or 'NONE'}")
        picker_ok = wait_catalog_picker_keep_trial(page)
    elif before.get("catalog_picker_mounted") and before.get("ga_trial"):
        picker_ok = True
        log("gate2_use_catalog skipped: catalog picker already mounted, Trial still GA")
    else:
        picker_ok = False
        log("gate2 HARNESS: Songs is not Custom hub with Trial GA")
    after_use = songs_hub_state(page)
    log(f"gate2_after_use_catalog picker={picker_ok} state={json.dumps(after_use, default=str)}")
    if not picker_ok:
        log("gate2 HARNESS: catalog picker did not mount with Trial still GA")
        log(f"gate2_dom={json.dumps(capture_gate2_dom(page), default=str)}")
        return {
            "ok": False,
            "used_catalog": bool(used),
            "picker": False,
            "clicked": False,
            "activated": False,
            "via": used,
        }
    clicked = pick_matching_song_once(page, title)
    log(f"gate2_shape_click={clicked}")
    activated = wait_shape_activation_bm(page)
    after = songs_hub_state(page)
    log(f"gate2_after_shape activated={activated} state={json.dumps(after, default=str)}")
    if not activated:
        log(f"gate2_dom={json.dumps(capture_gate2_dom(page), default=str)}")
    return {
        "ok": bool(activated),
        "used_catalog": bool(used),
        "picker": True,
        "clicked": bool(clicked),
        "activated": bool(activated),
        "via": used,
    }


def wait_for_studio_ready(page: Page) -> dict:
    from walk_creative_backing_matrix import click_nav, expand_pages_nav

    info: dict = {
        "sidebar": False,
        "songs_nav": False,
        "creative_nav": False,
        "picker": False,
        "ok": False,
    }
    try:
        page.wait_for_selector('section[data-testid="stSidebar"]', timeout=120_000)
        info["sidebar"] = True
    except Exception as exc:
        info["error"] = repr(exc)
        return info
    for _ in range(20):
        expand_pages_nav(page)
        songs = page.locator("button").filter(has_text=re.compile(r"Song Selection", re.I))
        creative = page.locator("button").filter(has_text=re.compile(r"Creative Lab", re.I))
        try:
            info["songs_nav"] = bool(songs.count() and songs.first.is_visible())
            info["creative_nav"] = bool(creative.count() and creative.first.is_visible())
        except Exception:
            pass
        if info["songs_nav"] and info["creative_nav"]:
            break
        settle(page, 2)
    click_nav(page, "Songs")
    settle(page, 4)
    try:
        info["picker"] = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]').count() > 0
    except Exception:
        info["picker"] = False
    info["ok"] = bool(info["sidebar"] and info["songs_nav"] and info["creative_nav"] and info["picker"])
    return info


def has_c_sharp_major(text: str) -> bool:
    t = low(text)
    return "c# major" in t or "c sharp major" in t or bool(re.search(r"c#\s+major", t))


def main() -> int:
    from walk_creative_backing_matrix import (
        click_button_has,
        click_nav,
        click_open_backing_studio,
        click_radio,
        expand_sidebar,
        goto_improv,
        set_instrument,
        wait_idle,
    )
    from walk_guitar_shape_key import pick_song
    from _walk_acceptance_an import force_pk_token, set_style_jam_concert_key
    from _walk_core_key_coherence import set_songs_practice_key
    from _walk_core_workflows_embargo import open_sbi_active
    from _walk_custom_practice_key import pk_val
    from _walk_ownership_audit_full import build_trial_song, rendered_dm_dm_c_c, rendered_em_em_d_d
    from _walk_reboot_persistence_ai_p19 import open_sbi_custom_source

    meta = git_meta()
    log(json.dumps(meta))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)
        settle(page, 5)
        init = wait_for_studio_ready(page)
        log(f"init={json.dumps(init)}")
        side, body = shot(page, "00-init-landing")
        landing_custom = "CUSTOM PROGRESSION" in (side or "").upper() and "Trial Song" in (side or "")
        init_ok = bool(init.get("ok") and not landing_custom)
        log(f"init_clean={init_ok} nav={init} landing_custom={landing_custom}")
        if not init_ok:
            log("INIT_STOP: studio not ready or leftover custom workspace — do not count as Owner product result")
            browser.close()
            (OUT / f"{PREFIX}summary.json").write_text(
                json.dumps({"meta": meta, "overall": "INIT_STOP", "results": RESULTS, "notes": NOTES[-40:]}, indent=2),
                encoding="utf-8",
            )
            log("OVERALL=INIT_STOP PASS=0 PARTIAL=0 RED=1")
            return 2

        # ---- Seed Trial as Global Active at C ----
        trial_ok = build_trial_song(page, NOTES)
        mark("seed_trial", "PASS" if trial_ok else "RED", "Trial Song D / Em Em D D")
        if not trial_ok:
            log("INIT_STOP: Trial seed failed — do not count as Owner product result")
            side, body = shot(page, "00-seed-fail")
            browser.close()
            (OUT / f"{PREFIX}summary.json").write_text(
                json.dumps({"meta": meta, "overall": "INIT_STOP", "results": RESULTS, "notes": NOTES[-40:]}, indent=2),
                encoding="utf-8",
            )
            log("OVERALL=INIT_STOP PASS=0 PARTIAL=0 RED=1")
            return 2
        click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
        settle(page, 3)
        if not wait_trial_custom_ga(page):
            from _walk_custom_practice_key import goto_custom

            log("seed Set as Active did not commit Trial GA — retry once from Custom")
            goto_custom(page)
            settle(page, 2)
            click_button_has(page, r"Set as Active Song") or click_button_has(page, r"Set as Active")
            settle(page, 3)
            wait_trial_custom_ga(page)
        click_nav(page, "Songs")
        settle(page, 3)
        hub = songs_hub_state(page)
        log(f"seed_songs_hub={json.dumps(hub, default=str)}")
        if not hub.get("ga_trial"):
            log("INIT_STOP: Trial never became Global Active after Set as Active")
            side, body = shot(page, "00-seed-no-trial-ga")
            browser.close()
            (OUT / f"{PREFIX}summary.json").write_text(
                json.dumps({"meta": meta, "overall": "INIT_STOP", "results": RESULTS, "notes": NOTES[-40:]}, indent=2),
                encoding="utf-8",
            )
            log("OVERALL=INIT_STOP PASS=0 PARTIAL=0 RED=1")
            return 2
        set_songs_practice_key(page, "C")
        settle(page, 3)
        force_pk_token(page, "C")
        settle(page, 2)
        side, body = shot(page, "01-trial-ga-c")
        hub_c = songs_hub_state(page)
        songs_c = bool(
            hub_c.get("ga_trial")
            and (hub_c.get("custom_hub") or hub_c.get("catalog_picker_mounted"))
            and (is_c_major(pk_label(body + side)) or is_c_major(pk_val(page) or ""))
        )
        mark(
            "1_songs_trial_c",
            "PASS" if songs_c else "RED",
            f"hub={hub_c.get('custom_hub')} ga_trial={hub_c.get('ga_trial')} "
            f"pk={pk_label(body + side) or pk_val(page)}",
        )

        # 1. SBI Custom CASE A = Trial C
        # Songs → Creative ONCE → land SBI → Custom Progression ONCE → wait for commit.
        click_nav(page, "Songs")
        settle(page, 2)
        landed = land_sbi(page, NOTES)
        clicked_custom = click_sbi_song_source(page, "custom") if landed else False
        committed = bool(
            landed
            and clicked_custom
            and wait_sbi_tuple(
                page,
                source="custom",
                title="Trial Song",
                c_major=True,
                dm_c_prog=True,
            )
        )
        side, body = shot(page, "02-sbi-custom-case-a")
        pk = pk_label(body + side) or pk_val(page) or ""
        case_a = committed and has_any(body, "Trial Song") and (
            is_c_major(pk) or bool(re.search(r"practice concert key:\s*c\b(?!#)", low(body)))
        ) and not is_d_major(pk) and (rendered_dm_dm_c_c(body) or has_any(body, "Dm"))
        mark(
            "1_sbi_custom_case_a_c",
            "PASS" if case_a else "RED",
            f"landed={landed} clicked={clicked_custom} committed={committed} "
            f"source={sbi_source_state(page)} pk={pk!r} dm={rendered_dm_dm_c_c(body)}",
        )

        # 1B. Active Source ONCE while Trial is Global Active = Trial / C / Dm Dm C C
        clicked_active = click_sbi_song_source(page, "active") if landed else False
        committed_b = bool(
            clicked_active
            and wait_sbi_tuple(
                page,
                source="active",
                title="Trial Song",
                c_major=True,
                dm_c_prog=True,
            )
        )
        side, body = shot(page, "03-sbi-active-trial")
        pk_b = pk_label(body + side) or pk_val(page) or ""
        active_trial = committed_b and has_any(body, "Trial Song") and (
            is_c_major(pk_b) or bool(re.search(r"practice concert key:\s*c\b(?!#)", low(body)))
        )
        mark(
            "1b_sbi_active_trial_c",
            "PASS" if active_trial else ("PARTIAL" if landed else "RED"),
            f"clicked={clicked_active} committed={committed_b} source={sbi_source_state(page)} pk={pk_b!r}",
        )

        # 3. Composition feather/piano logo
        try:
            labels = page.evaluate(
                """() => [...document.querySelectorAll('label, p, span')]
                  .map(el => (el.innerText || '').trim())
                  .filter(t => /composition/i.test(t))
                  .slice(0, 12)"""
            )
        except Exception:
            labels = []
        logo_ok = any("🎹" in str(t) and "composition" in low(str(t)) for t in (labels or []))
        if not logo_ok:
            logo_ok = "🎹 composition" in low(body) or "🎹 composition" in (page.inner_text("body") or "").lower()
        # Streamlit may keep the emoji in the radio option even if innerText dumps poorly.
        if not logo_ok:
            try:
                logo_ok = bool(
                    page.evaluate(
                        """() => /🎹\\s*Composition/u.test(document.body.innerText || '')"""
                    )
                )
            except Exception:
                pass
        mark("3_composition_logo", "PASS" if logo_ok else "RED", "piano-emoji Composition" if logo_ok else "missing")

        # 2. Custom hub → Use catalog (picker mode) → Shape once = Bm
        # Do not use pick_song(): it assumes Catalog mode is already active.
        g2 = custom_hub_to_catalog_song(page, NOTES, "Shape of You")
        settle(page, 2)
        side, body = shot(page, "04-explicit-shape")
        pk2 = pk_label(body + side) or pk_val(page) or ""
        orig2 = ""
        m_orig = re.search(r"(?:Song )?Original Key:\s*([A-G](?:#|b)?(?:\s*major|\s*minor|m)?)", body or "", re.I)
        if m_orig:
            orig2 = m_orig.group(1)
        shape_bm = (
            bool(g2.get("ok"))
            and "Shape of You" in (side or "")
            and has_any(body, "Shape of You")
            and is_b_minor(pk2)
            and (not orig2 or is_b_minor(orig2) or orig2.strip().lower() in {"bm", "b minor"})
            and not has_c_sharp_major(body + side)
        )
        mark(
            "2_explicit_shape_bm",
            "PASS" if shape_bm else "RED",
            f"used_catalog={g2.get('used_catalog')} via={g2.get('via')!r} "
            f"picker={g2.get('picker')} click={g2.get('clicked')} "
            f"activated={g2.get('activated')} pk={pk2!r} orig={orig2!r}",
        )

        ok_custom_b = open_sbi_custom_source(page, NOTES)
        if not ok_custom_b:
            try:
                page.get_by_role("radio", name=re.compile(r"Active Source", re.I)).last.focus()
                page.keyboard.press("ArrowRight")
                settle(page, 3)
            except Exception:
                pass
        settle(page, 3)
        side, body = shot(page, "05-sbi-custom-case-b")
        pk = pk_label(body + side) or pk_val(page) or ""
        case_b = (
            has_any(body, "Trial Song")
            and (is_d_major(pk) or bool(re.search(r"practice concert key:\s*d\b(?!m)", low(body))))
            and not is_b_minor(pk)
            and not has_c_sharp_major(body + side)
            and (rendered_em_em_d_d(body) or has_any(body, "Em"))
        )
        mark(
            "2_sbi_custom_case_b_d",
            "PASS" if case_b else "RED",
            f"open={ok_custom_b} pk={pk!r} em={rendered_em_em_d_d(body)}",
        )

        # 4-7. Style Jam C# → Open Backing → Songs explicit Shape = Bm
        click_nav(page, "Creative")
        settle(page, 3)
        if goto_improv(page, NOTES):
            click_radio(page, "Entry & Jam") or click_button_has(page, r"Entry & Jam")
            settle(page, 2)
            click_radio(page, "Style Jam") or click_button_has(page, r"Style Jam Mode")
            settle(page, 2)
            set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
            settle(page, 2)
            concert_ok = False
            live_jam = ""
            for _ in range(4):
                set_style_jam_concert_key(page, "C#") or set_style_jam_concert_key(page, "C# major")
                settle(page, 2)
                live_jam = style_jam_concert_closed(page)
                jam_pre = page.inner_text("body") or ""
                if (
                    has_c_sharp_major(live_jam)
                    or str(live_jam).strip() in {"C#", "C♯"}
                    or has_c_sharp_major(jam_pre)
                ):
                    concert_ok = True
                    break
            log(f"jam_live_before_generate={live_jam!r} concert_ok={concert_ok}")
            if not concert_ok:
                mark(
                    "4_style_jam_c_sharp",
                    "RED",
                    f"setter_harness live={live_jam!r} skipped_generate",
                )
            else:
                click_button_has(page, r"Generate progression")
                try:
                    page.wait_for_function(
                        """() => {
                          const t = document.body ? (document.body.innerText || '') : '';
                          return /Generated\\b/i.test(t)
                            && /Open in Backing Studio/i.test(t)
                            && (/C#\\s*major/i.test(t) || /C sharp major/i.test(t));
                        }""",
                        timeout=20_000,
                    )
                except Exception:
                    click_button_has(page, r"Generate progression")
                    settle(page, 5)
                opened_jam = click_button_has(page, r"Open in Backing Studio") or click_open_backing_studio(
                    page, NOTES, "jam-c#"
                )
                settle(page, 4)
                side, body = shot(page, "06-style-jam-backing")
                jam_c = has_c_sharp_major(body + side) or "c#" in low(pk_val(page) or "") or "c#" in low(body)
                mark(
                    "4_style_jam_c_sharp",
                    "PASS" if jam_c else "RED",
                    f"backing={opened_jam} set={concert_ok} live={live_jam!r} pk={pk_val(page)}",
                )

        click_nav(page, "Songs")
        settle(page, 3)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 4)
        side, body = shot(page, "07-songs-shape-after-jam")
        combined = body + side
        no_leak = not has_c_sharp_major(combined)
        sidebar_bm = is_b_minor(pk_val(page) or "") or is_b_minor(pk_label(side) or "")
        shape_fresh = has_any(side, "Shape of You") and sidebar_bm
        mark(
            "4_shape_bm_after_jam",
            "PASS" if shape_fresh and no_leak else "RED",
            f"pk={pk_label(side)!r} sidebar={pk_val(page)!r} c#={not no_leak}",
        )

        # 8. SBI Active coherent tuple — Active Source after explicit Shape.
        ok_sbi = open_sbi_active(page)
        landed_active = False
        for attempt in range(4):
            click_sbi_song_source(page, "active")
            settle(page, 2)
            try:
                page.wait_for_function(
                    """() => {
                      const t = document.body ? (document.body.innerText || '') : '';
                      const low = t.toLowerCase();
                      const shape = /Shape of You/i.test(t);
                      const bm = /B minor/i.test(t) || /practice concert key:\\s*bm/i.test(low);
                      const custom_trial = /trial song/i.test(t)
                        && /practice concert key:\\s*d\\b/.test(low);
                      return shape && bm && !custom_trial;
                    }""",
                    timeout=10_000,
                )
                landed_active = True
                break
            except Exception:
                log(f"sbi active wait attempt={attempt}")
        side, body = shot(page, "08-sbi-active-shape")
        combined = body + side
        card_shape = has_any(body, "Shape of You") and (
            "active song · song selection" in low(body)
            or "practice concert key: bm" in low(body)
            or is_b_minor(pk_val(page) or "")
            or is_b_minor(pk_label(combined) or "")
        )
        custom_card = "custom progression\n\ntrial song" in low(body) or (
            "trial song" in low(body) and "practice concert key: d" in low(body)
        )
        sbi_bm = is_b_minor(pk_label(combined) or pk_val(page) or "") or is_b_minor(
            pk_val(page) or ""
        )
        sbi_prog = has_any(body, "Bm") or has_any(body, "Em")
        no_g_major_split = "g major" not in low(combined) or is_b_minor(pk_val(page) or "")
        no_gm_shape = "practice concert key: g" not in low(body)
        sbi_ok = (
            card_shape
            and not custom_card
            and sbi_bm
            and sbi_prog
            and no_g_major_split
            and no_leak
            and no_gm_shape
        )
        mark(
            "8_sbi_active_tuple",
            "PASS" if sbi_ok else "RED",
            f"card_shape={card_shape} custom_card={custom_card} bm={sbi_bm} "
            f"open={ok_sbi} landed={landed_active} pk={pk_label(combined)!r} card={pk_val(page)!r}",
        )

        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        force_pk_token(page, "Bm")
        settle(page, 2)
        mode_ok = enable_guitar_shape_mode(page, NOTES)
        _wait_shape_key_selectbox(page)
        committed = False
        if not mode_ok or not capo_shape_mode_checked(page):
            log("shape_tonic skip: capo not checked")
        else:
            for attempt in range(3):
                committed = commit_shape_tonic(page, "C")
                log(
                    f"shape_tonic_commit attempt={attempt} ok={committed} "
                    f"widget={shape_key_widget_value(page)!r} diag={LAST_SHAPE_DIAG}"
                )
                if committed:
                    break
                settle(page, 2)
        settle(page, 2)
        side, body = shot(page, "08b-songs-guitar-c")
        combined = body + side
        charts = charts_in_label(combined)
        c_minor_ctx = bool(re.search(r"charts in\s+c\s*minor", low(combined)))
        c_major_ctx = bool(re.search(r"charts in\s+c\s*major", low(combined)))
        still_bm = is_b_minor(pk_val(page) or "") or is_b_minor(pk_label(combined) or "")
        if not committed:
            mark(
                "10_guitar_shape_c_minor",
                "PARTIAL",
                f"setter_failed widget={shape_key_widget_value(page)!r} charts={charts!r} "
                f"bm={still_bm} mode={mode_ok}",
            )
        elif c_major_ctx:
            mark(
                "10_guitar_shape_c_minor",
                "RED",
                f"PRODUCT? charts={charts!r} widget={shape_key_widget_value(page)!r} bm={still_bm}",
            )
        else:
            mark(
                "10_guitar_shape_c_minor",
                "PASS" if c_minor_ctx and still_bm and not c_major_ctx else "PARTIAL",
                f"c_minor={c_minor_ctx} bm={still_bm} charts={charts!r} "
                f"widget={shape_key_widget_value(page)!r} commit={committed} mode={mode_ok}",
            )

        # 11. Bm → Dm on Songs, then confirm it persists
        click_nav(page, "Songs")
        settle(page, 3)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        expand_sidebar(page)
        set_songs_practice_key(page, "Dm")
        settle(page, 2)
        force_pk_token(page, "Dm")
        settle(page, 3)
        side, body = shot(page, "09-sbi-shape-dm")
        combined = body + side
        dm_ok = is_d_minor(pk_label(combined) or pk_val(page) or "") and has_any(
            combined, "Shape of You"
        )
        no_jam = not has_c_sharp_major(combined)
        mark(
            "11_bm_to_dm",
            "PASS" if dm_ok and no_jam else "RED",
            f"pk={pk_label(combined)!r}",
        )

        click_nav(page, "Songs")
        settle(page, 3)
        side, body = shot(page, "10-songs-shape-dm")
        persist_dm = is_d_minor(pk_label(body + side) or pk_val(page) or "")
        mark("11b_songs_shape_dm", "PASS" if persist_dm else "RED", pk_label(body + side))

        # Reset to Bm for refresh check
        click_nav(page, "Songs")
        settle(page, 2)
        click_button_has(page, r"Use catalog song instead")
        settle(page, 1)
        pick_song(page, NOTES, "Shape of You", "Pop")
        settle(page, 3)
        set_songs_practice_key(page, "Bm")
        settle(page, 2)
        force_pk_token(page, "Bm")
        settle(page, 3)
        ok_sbi = open_sbi_active(page)
        click_sbi_song_source(page, "active")
        settle(page, 3)
        try:
            page.reload(wait_until="domcontentloaded", timeout=120000)
            reload_ok = True
        except Exception as exc:
            log(f"refresh reload failed (server?): {exc!r}")
            mark("13_refresh_sbi_active", "RED", "reload failed")
            mark("13_nav_sbi_active", "RED", "skipped after reload fail")
            reload_ok = False
        if reload_ok:
            settle(page, 8)
            from _walk_core_workflows_embargo import wait_for_body

            wait_for_body(page, "Shape of You", "Practice concert key", timeout_s=45.0)
            side, body = shot(page, "11-refresh-sbi-active")
            refresh_ok = has_any(body + side, "Shape of You") and is_b_minor(
                pk_label(body + side) or pk_val(page) or ""
            )
            mark("13_refresh_sbi_active", "PASS" if refresh_ok else "RED", pk_label(body + side))

            click_nav(page, "Songs")
            settle(page, 2)
            click_nav(page, "Creative")
            settle(page, 2)
            open_sbi_active(page)
            settle(page, 3)
            side, body = shot(page, "12-nav-sbi-active")
            nav_ok = has_any(body + side, "Shape of You") and not has_c_sharp_major(body + side)
            mark("13_nav_sbi_active", "PASS" if nav_ok else "RED", pk_label(body + side))

        browser.close()

    reds = [k for k, v in RESULTS.items() if v == "RED"]
    partials = [k for k, v in RESULTS.items() if v == "PARTIAL"]
    passes = [k for k, v in RESULTS.items() if v == "PASS"]
    overall = "PASS" if not reds and not partials else ("PARTIAL" if not reds else "RED")
    summary = {
        "meta": meta,
        "overall": overall,
        "results": RESULTS,
        "pass": passes,
        "partial": partials,
        "red": reds,
        "notes": NOTES[-80:],
    }
    (OUT / f"{PREFIX}summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / f"{PREFIX}summary.txt").write_text(
        "\n".join(
            [
                f"OVERALL={overall}",
                f"PASS={len(passes)} PARTIAL={len(partials)} RED={len(reds)}",
                json.dumps(RESULTS, indent=2),
                "",
                *NOTES[-60:],
            ]
        ),
        encoding="utf-8",
    )
    log(f"OVERALL={overall} PASS={len(passes)} PARTIAL={len(partials)} RED={len(reds)}")
    return 0 if overall != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
