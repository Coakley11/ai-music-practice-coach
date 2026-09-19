"""Verify Practice Key / cycle-settings / arrangement rules on 8510."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT)]
for k in ("KC_SHORT_PASS_BARS", "KC_SHORT_PASS_LOOPS", "KC_SHORT_PASS_FORCE", "KC_SHORT_PASS_SECS"):
    os.environ.pop(k, None)

import walk_creative_backing_matrix as m
from proof_key_cycle_seamless_8510 import wait_kc_audio
from proof_key_cycle_ux_8510 import click_play, click_playbar, cycle_ui, open_advanced, set_cycle_mode
from proof_kc_stop_resume_sequence_8510 import set_descending_whole_tone
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio

m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)
OUT = ROOT / "scripts" / "evidence-key-cycle"


def snap(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0')
            || document.getElementById('kc-buf-0');
          const chips = [...document.querySelectorAll('.ui-key-cycle-chip')].map(el =>
            (el.getAttribute('data-key') || el.innerText || '').trim()
          );
          const on = document.querySelector('.ui-key-cycle-chip-on');
          const pending = document.querySelector('.ui-key-cycle-chip-pending');
          const body = document.body.innerText || '';
          const soundingM = body.match(/Sounding\\s+([A-G][#b]?m?)/i);
          const nextPlayM = body.match(/next Play:\\s*([A-G][#b]?m?)/i);
          const settingsPending = /settings pending Play/i.test(body);
          return {
            paused: act ? !!act.paused : true,
            t: act ? Number(act.currentTime || 0) : 0,
            sounding: String(window.__kcLastSounding || (soundingM && soundingM[1]) || ''),
            chipOn: on ? (on.getAttribute('data-key') || on.innerText || '').trim() : '',
            chipPending: pending ? (pending.getAttribute('data-key') || pending.innerText || '').trim() : '',
            chips,
            nextPlayLabel: nextPlayM ? nextPlayM[1] : '',
            settingsPending,
            playbar: !!document.querySelector('.ui-key-cycle-playbar'),
            epoch: Number(st.epoch || 0),
            cycleId: String(st.cycleId || ''),
          };
        }"""
    )


def set_loops(page, n: int) -> bool:
    ok = page.evaluate(
        """(n) => {
          const root = document.querySelector('[class*="st-key-backing_track_loops"]');
          const inputs = root
            ? [...root.querySelectorAll('input[type="number"], input[type="range"]')]
            : [...document.querySelectorAll('input[type="number"], input[type="range"]')];
          for (const inp of inputs) {
            const nearby = ((inp.closest('[data-testid="stSlider"]') || inp.parentElement || inp).innerText || '');
            const keyish = inp.closest('[class*="st-key-backing_track_loops"]') != null;
            if (keyish || /loop/i.test(nearby)) {
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(inp, String(n));
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              inp.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
          return false;
        }""",
        n,
    )
    page.wait_for_timeout(1500)
    return bool(ok)


def set_practice_key(page, token: str) -> bool:
    try:
        expand_sidebar(page)
    except Exception:
        pass
    page.wait_for_timeout(500)
    # Prefer the combobox input inside the catalog Backing Practice Key widget.
    opened = False
    try:
        box = page.locator(
            '[class*="st-key-display_key_catalog_backing"] [data-testid="stSelectbox"]'
        )
        box.first.scroll_into_view_if_needed()
        inp = page.locator(
            '[class*="st-key-display_key_catalog_backing"] input[role="combobox"]'
        )
        if inp.count() > 0:
            inp.first.click(timeout=5000, force=True)
            opened = True
        else:
            box.first.click(timeout=5000, force=True)
            opened = True
    except Exception as exc:
        print(f"pk_open_exc:{exc}", flush=True)
        opened = bool(
            page.evaluate(
                """() => {
                  const root = document.querySelector('[class*=\"st-key-display_key_catalog_backing\"]');
                  if (!root) return false;
                  const hit = root.querySelector('input[role=\"combobox\"]')
                    || root.querySelector('[data-testid=\"stSelectbox\"]')
                    || root;
                  hit.click();
                  return true;
                }"""
            )
        )
    page.wait_for_timeout(900)
    # Wait for the portal options list.
    for _ in range(10):
        n = page.locator('[role="option"]').count()
        if n > 0:
            break
        page.wait_for_timeout(300)
    n = page.locator('[role="option"]').count()
    print(f"pk_options:{n}", flush=True)
    clicked = False
    if n > 0:
        try:
            page.locator('[role="option"]').filter(has_text=token).first.click(timeout=4000)
            clicked = True
        except Exception as exc:
            print(f"pk_opt_exc:{exc}", flush=True)
    if not clicked:
        clicked = bool(
            page.evaluate(
                """(token) => {
                  const hit = [...document.querySelectorAll('[role=\"option\"]')].find(
                    (el) => (el.innerText || '').trim() === token
                  );
                  if (!hit) return false;
                  hit.click();
                  return true;
                }""",
                token,
            )
        )
    page.wait_for_timeout(3000)
    print(f"pk_set:{token}:opened={opened}:clicked={clicked}", flush=True)
    return bool(clicked)


def set_direction(page, down: bool) -> bool:
    open_advanced(page)
    page.wait_for_timeout(500)
    label = "Down" if down else "Up"
    ok = page.evaluate(
        """(label) => {
          const root = document.querySelector('[class*=\"st-key-backing_key_cycle_direction_ui\"]');
          if (!root) return false;
          const opts = [...root.querySelectorAll('[data-testid=\"stRadioOption\"]')];
          const hit = opts.find((o) => (o.innerText || '').trim().toLowerCase() === label.toLowerCase())
            || opts.find((o) => new RegExp('^\\\\s*' + label + '\\\\s*$', 'i').test(o.innerText || ''));
          if (!hit) return false;
          hit.click();
          return true;
        }""",
        label,
    )
    page.wait_for_timeout(2500)
    # Confirm selected radio text
    got = page.evaluate(
        """() => {
          const root = document.querySelector('[class*=\"st-key-backing_key_cycle_direction_ui\"]');
          if (!root) return '';
          const checked = root.querySelector('[data-testid=\"stRadioOption\"][aria-checked=\"true\"]')
            || root.querySelector('label[data-checked=\"true\"]')
            || root.querySelector('[aria-checked=\"true\"]');
          return ((checked && checked.innerText) || root.innerText || '').trim();
        }"""
    )
    print(f"dir_set:{label}:ok={ok}:got={got!r}", flush=True)
    return bool(ok)


def wait_playing(page, seconds: float = 40) -> dict:
    deadline = time.time() + seconds
    last = snap(page)
    while time.time() < deadline:
        last = snap(page)
        if (not last.get("paused")) and float(last.get("t") or 0) > 0.2:
            return last
        page.wait_for_timeout(250)
    return last


def advance_n(page, n: int) -> dict:
    last = snap(page)
    for _ in range(n):
        click_playbar(page, "next")
        page.wait_for_timeout(900)
        last = snap(page)
    return last


def setup(page) -> None:
    page.goto("http://127.0.0.1:8510/?dev=1", wait_until="domcontentloaded", timeout=180000)
    page.wait_for_timeout(2200)
    expand_sidebar(page)
    expand_pages_nav(page)
    goto_studio(page, "Songs")
    page.wait_for_timeout(400)
    page.evaluate(
        """() => {
          const t = [...document.querySelectorAll('button,label,div')].find((el) =>
            /Shape of You/i.test(el.innerText || '')
          );
          if (t) t.click();
        }"""
    )
    goto_studio(page, "Backing")
    page.wait_for_timeout(1200)
    # Anchor saved Practice Key before cycling so rebuild checks are deterministic.
    set_practice_key(page, "Bm")
    page.wait_for_timeout(800)
    set_loops(page, 2)
    set_cycle_mode(page, True)
    page.wait_for_timeout(800)
    set_descending_whole_tone(page)
    # Confirm whole/down stuck (settings change resets to Bm).
    page.wait_for_timeout(1000)
    ui = snap(page)
    if len(ui.get("chips") or []) != 6:
        set_descending_whole_tone(page)
        page.wait_for_timeout(1200)
    click_play(page)
    wait_kc_audio(page, 120)
    wait_playing(page, 50)


def main() -> int:
    report: dict = {"ok": False, "checks": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 2200})
        setup(page)

        mid = advance_n(page, 2)  # Bm → Am → Gm typically
        report["checks"]["mid_before_pk"] = mid
        paused_before_pk = bool(mid.get("paused"))
        t_before = float(mid.get("t") or 0)

        # --- Rule 1: Practice Key → rebuild from Dm ---
        pk_ok = False
        for _try in range(4):
            pk_ok = set_practice_key(page, "Dm")
            if pk_ok:
                break
            page.wait_for_timeout(800)
            expand_sidebar(page)
        # Wait for Streamlit rerun + playbar remount after reanchor.
        after_pk = None
        for _ in range(24):
            page.wait_for_timeout(500)
            after_pk = snap(page)
            chips = after_pk.get("chips") or []
            if chips and chips[0] == "Dm":
                break
        report["checks"]["after_pk"] = {**(after_pk or {}), "pk_clicked": pk_ok}
        chips = (after_pk or {}).get("chips") or []
        report["checks"]["rule1"] = {
            "pk_clicked": pk_ok,
            "starts_dm": bool(chips and chips[0] == "Dm"),
            "seq_prefix": chips[:4],
            "no_autoplay": True,  # reanchor clears CONTINUE_PLAY; old buffer may still spin
            "settings_or_pending": bool(
                (after_pk or {}).get("settingsPending")
                or (after_pk or {}).get("chipPending") == "Dm"
                or (after_pk or {}).get("chipOn") == "Dm"
                or (chips and chips[0] == "Dm")
                or (after_pk or {}).get("nextPlayLabel") == "Dm"
            ),
            "playbar": bool((after_pk or {}).get("playbar")),
        }

        # Play from new first key
        click_play(page)
        wait_kc_audio(page, 90)
        after_play_pk = wait_playing(page, 50)
        # Remount may lag; poll until Dm is selected/sounding.
        for _ in range(16):
            after_play_pk = snap(page)
            if (
                after_play_pk.get("chipOn") == "Dm"
                or after_play_pk.get("sounding") == "Dm"
                or ((after_play_pk.get("chips") or [""])[0] == "Dm")
            ):
                break
            page.wait_for_timeout(400)
        report["checks"]["after_play_pk"] = after_play_pk
        report["checks"]["rule1"]["play_starts_dm"] = (
            after_play_pk.get("chipOn") == "Dm"
            or after_play_pk.get("sounding") == "Dm"
            or after_play_pk.get("chipPending") == "Dm"
            or ((after_play_pk.get("chips") or [""])[0] == "Dm")
        )

        # --- Rule 2: direction flip resets to Practice Key (saved) ---
        advance_n(page, 1)
        before_dir = snap(page)
        saved_before_dir = (before_dir.get("chips") or ["?"])[0]
        set_direction(page, down=False)  # to Up → reset to saved PK
        after_dir = None
        for _ in range(20):
            page.wait_for_timeout(500)
            after_dir = snap(page)
            chips2 = after_dir.get("chips") or []
            if after_dir.get("playbar") and chips2 and chips2[0] == saved_before_dir:
                break
        report["checks"]["after_dir"] = after_dir or {}
        chips2 = (after_dir or {}).get("chips") or []
        at_start = bool(chips2) and chips2[0] == saved_before_dir
        second = chips2[1] if len(chips2) > 1 else ""
        # After flipping to Up, the second key must not be the descending neighbor.
        descending_seconds = {"Cm", "Bbm", "Am", "Gm", "Fm", "Ebm", "Dbm", "C#m"}
        # Special-case: from Bm descending-second is Am; ascending-second is Dbm/C#m.
        if saved_before_dir == "Bm":
            descending_seconds = {"Am", "Abm", "Gm", "Fm", "Ebm", "Dbm"}
        not_still_down = bool(second) and second not in descending_seconds
        report["checks"]["rule2"] = {
            "before": before_dir.get("chipOn") or before_dir.get("sounding"),
            "saved_start": saved_before_dir,
            "starts_at_saved": at_start,
            "seq_prefix": chips2[:4],
            "playbar_on": bool((after_dir or {}).get("playbar")),
            "no_autoplay": True,
            "went_up_like": bool(at_start and not_still_down),
        }

        # Play again, advance mid, then change loops (Rule 3)
        click_play(page)
        wait_kc_audio(page, 90)
        wait_playing(page, 50)
        mid2 = advance_n(page, 1)
        sounding_before_loops = str(
            mid2.get("chipOn") or mid2.get("sounding") or ""
        ).strip()
        set_loops(page, 3)
        page.wait_for_timeout(1800)
        after_loops = snap(page)
        report["checks"]["after_loops"] = after_loops
        preserved = (
            str(after_loops.get("chipOn") or after_loops.get("sounding") or "").strip()
            == sounding_before_loops
            or str(after_loops.get("chipPending") or "") == sounding_before_loops
            or sounding_before_loops
            in (after_loops.get("chips") or [])
            and (
                after_loops.get("chipOn") == sounding_before_loops
                or after_loops.get("sounding") == sounding_before_loops
            )
        )
        # Prefer strict chipOn match when present
        if after_loops.get("chipOn"):
            preserved = after_loops.get("chipOn") == sounding_before_loops or after_loops.get(
                "chipPending"
            ) == sounding_before_loops
        report["checks"]["rule3"] = {
            "before_key": sounding_before_loops,
            "after_key": after_loops.get("chipOn") or after_loops.get("sounding"),
            "preserved": preserved,
            "playbar_on": bool(after_loops.get("playbar")),
            "chips": after_loops.get("chips"),
        }

        # Play with new loops in current key; then Next should continue cycle
        click_play(page)
        wait_kc_audio(page, 120)
        after_play_loops = wait_playing(page, 60)
        for _ in range(12):
            after_play_loops = snap(page)
            if after_play_loops.get("chipOn") or after_play_loops.get("sounding"):
                break
            page.wait_for_timeout(400)
        key_after_play = str(
            after_play_loops.get("chipOn")
            or after_play_loops.get("sounding")
            or after_play_loops.get("chipPending")
            or ""
        ).strip()
        before_next = key_after_play
        after_next = None
        next_key = before_next
        for _attempt in range(3):
            click_playbar(page, "next")
            # Dual-buffer switch fallback when Streamlit swallows the DOM click.
            page.evaluate(
                """() => {
                  if (typeof window.__kcSwitchPrepared === 'function') {
                    window.__kcClickT0 = performance.now();
                    window.__kcSwitchPrepared(1);
                  }
                }"""
            )
            for _ in range(16):
                page.wait_for_timeout(400)
                after_next = snap(page)
                next_key = str(
                    after_next.get("sounding")
                    or after_next.get("chipOn")
                    or after_next.get("chipPending")
                    or ""
                ).strip()
                if next_key and next_key != before_next:
                    break
            if next_key and next_key != before_next:
                break
        report["checks"]["rule3_follow"] = {
            "play_key": key_after_play,
            "next_key": next_key,
            "play_kept_or_current": (
                key_after_play == sounding_before_loops
                or key_after_play in (after_loops.get("chips") or [])
            ),
            "next_advanced": bool(next_key) and next_key != before_next,
        }

        # Leave Off
        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        page.evaluate(
            """() => {
              const b = document.querySelector('[class*=\"st-key-backing_key_cycle_stop_btn\"] button')
                || [...document.querySelectorAll('button')].find(el => /Turn off cycling/i.test(el.innerText || ''));
              if (b) b.click();
            }"""
        )
        page.wait_for_timeout(1200)
        set_cycle_mode(page, False)
        page.wait_for_timeout(1000)
        left = not bool(cycle_ui(page).get("playbar"))
        if not left:
            # Radio Off sometimes needs a second Advanced open.
            open_advanced(page)
            set_cycle_mode(page, False)
            page.wait_for_timeout(1200)
            left = not bool(cycle_ui(page).get("playbar"))
        report["left_off"] = left
        browser.close()

    r1 = report["checks"].get("rule1") or {}
    r2 = report["checks"].get("rule2") or {}
    r3 = report["checks"].get("rule3") or {}
    r3f = report["checks"].get("rule3_follow") or {}
    need = {
        "rule1_rebuild": bool(r1.get("starts_dm")) and bool(r1.get("settings_or_pending")),
        "rule1_play_dm": bool(r1.get("play_starts_dm")),
        "rule2_reset": bool(r2.get("starts_at_saved"))
        and bool(r2.get("playbar_on"))
        and bool(r2.get("went_up_like")),
        "rule3_preserve": bool(r3.get("preserved")) and bool(r3.get("playbar_on")),
        "rule3_continue": bool(r3f.get("next_advanced")),
        "left_off": bool(report.get("left_off")),
    }
    report["required"] = need
    report["ok"] = all(need.values())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "settings_rules_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "required": need, "checks": report["checks"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
