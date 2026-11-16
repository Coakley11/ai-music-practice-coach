"""Slice 1 safeguard: Stop, driven from the transport's own controls, must not rewrite a key.

The earlier mixed-setlist run reported "Stop answers during a performance: FAIL", and that was
the harness: Stop is inside the transport's component iframe, not a button in the page, so a
text click over the parent document cannot reach it. This drives the real control.

What it has to establish, and the reason it is a pre-integration gate rather than a nicety:
stopping a performance runs transport and session code on the same paths that Part 3b froze, so
if anything there writes a key, it writes it while the musician is doing something entirely
innocent. Three keys are therefore read before and after: the setlist entry's saved key, the
song's own saved Practice Key, and the key the backing says it is in.

Say is set up exactly as in the main acceptance - queued at Bb, its own song Practice Key moved
to D with nothing performing - then performed, re-keyed to Ab, and stopped.

Usage:
  python -X utf8 scripts/_accept_karaoke_stop_transport.py http://127.0.0.1:8610
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

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8610"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    key_token,
    low,
    press_play,
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


#: Every control the transport component exposes, with whether it is usable right now. The
#: component's own ids: #btn is Play, #pz is Pause/Resume, #stop is Stop.
TRANSPORT = """
() => {
  for (const f of document.querySelectorAll('iframe')) {
    let doc = null;
    try { doc = f.contentDocument; } catch (e) { continue; }
    if (!doc || !doc.getElementById('btn')) continue;
    const one = (id) => {
      const el = doc.getElementById(id);
      if (!el) return null;
      return {
        text: (el.innerText || '').trim().slice(0, 30),
        state: el.getAttribute('data-state') || '',
        mode: el.getAttribute('data-mode') || '',
        disabled: !!el.disabled,
        hidden: !!el.hidden,
      };
    };
    const ids = [...doc.querySelectorAll('[id]')].map(e => e.id);
    return {btn: one('btn'), pz: one('pz'), stop: one('stop'), ids: ids.slice(0, 20)};
  }
  return null;
}
"""

IFRAME_CLICK = """
(sel) => {
  for (const f of document.querySelectorAll('iframe')) {
    let doc = null;
    try { doc = f.contentDocument; } catch (e) { continue; }
    if (!doc || !doc.getElementById('btn')) continue;
    const el = doc.querySelector(sel);
    if (!el || el.disabled || el.hidden) return false;
    el.click();
    return true;
  }
  return false;
}
"""


def rows(page: Page) -> list[dict]:
    click_nav(page, "Songs")
    settle(page, 4)
    click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 4)
    try:
        return page.evaluate(ROWS_JS) or []
    except Exception:
        return []


def entry_key(page: Page) -> str:
    got = rows(page)
    label = got[0].get("label") if got else ""
    return key_token(label.split("·")[-1]) if label and "·" in label else ""


def song_key(page: Page) -> str:
    """Say's OWN saved Practice Key, read where the musician set it: on Songs, no set running."""
    pick_song(page, OBSERVED, "Say", "pop")
    settle(page, 4)
    return key_token(pk_val(page))


def main() -> int:
    report: dict = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark("T1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            queued = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            mark("T2 Say is queued at its own Bb", bool(queued) and key_token(pk_val(page)) == "bb",
                 f"sidebar={pk_val(page)!r}")

            moved = set_pk_token(page, "D")
            mark("T3 Say's own Practice Key is D, set with nothing performing",
                 moved and key_token(pk_val(page)) == "d", f"sidebar={pk_val(page)!r}")
            before = {"entry": entry_key(page), "song": song_key(page)}
            log(f"    before the performance: {before}")

            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            started = click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark("T4 the set performs", "now singing" in low(page.inner_text("body") or ""),
                 f"(start helper {bool(started)})")

            click_nav(page, "Backing")
            settle(page, 6)
            played = press_play(page)
            # The transport is a state machine - "STOPPED offers Play; PLAYING offers Stop and
            # Pause; PAUSED offers Stop" - so Stop does not exist until something is playing.
            # Headless Chromium blocks autoplay, so the first run of this script found
            # state='stopped' with no Stop control and could not exercise it at all. Start the
            # take explicitly, muted, as the scrolling acceptance does.
            nudged = page.evaluate(
                """() => {
                  for (const f of document.querySelectorAll('iframe')) {
                    let doc = null;
                    try { doc = f.contentDocument; } catch (e) { continue; }
                    if (!doc) continue;
                    const a = [...doc.querySelectorAll('audio')].find(x => x.src || x.currentSrc);
                    if (!a) continue;
                    a.muted = true;
                    try { a.play(); } catch (e) { return 'play() threw: ' + e; }
                    return 'started in a component';
                  }
                  const a = [...document.querySelectorAll('audio')].find(x => x.src || x.currentSrc);
                  if (!a) return 'no audio element anywhere';
                  a.muted = true;
                  try { a.play(); } catch (e) { return 'play() threw: ' + e; }
                  return 'started on the page';
                }"""
            )
            log(f"    audio nudge: {nudged}")
            for _ in range(20):
                probe = page.evaluate(TRANSPORT) or {}
                if str(((probe.get("btn") or {}).get("state") or "")) == "playing":
                    break
                if (probe.get("stop") or {}):
                    break
                settle(page, 3)
            state = page.evaluate(TRANSPORT)
            log(f"    transport after Play: {json.dumps(state)[:300]}")
            mark("T5 the transport component is reachable", state is not None, f"play={bool(played)}")
            mark("T6 the transport exposes a Stop control",
                 bool(state) and bool(state.get("stop")),
                 f"stop={(state or {}).get('stop')} ids={(state or {}).get('ids')}")

            # A temporary key change first, so Stop has something it could wrongly persist.
            retuned = set_pk_token(page, "Ab")
            settle(page, 6)
            ident = card_identity(page)
            mark("T7 the performance is in the temporary key",
                 key_token(ident.get("backing_key") or "") == "ab",
                 f"{ident.get('backing_line')!r} (setter {bool(retuned)})")

            click_nav(page, "Backing")
            settle(page, 5)
            # Stop is whichever control the state machine is offering: a dedicated #stop while
            # playing or paused, and nothing at all while stopped.
            stopped = bool(page.evaluate(IFRAME_CLICK, "#stop"))
            if not stopped:
                observe("no #stop in the transport; trying the page's own Stop control")
                stopped = bool(click_text(page, "Stop"))
            settle(page, 8)
            after_stop = page.evaluate(TRANSPORT)
            body = shot(page, "t1-after-stop")
            mark("T8 Stop answers from the transport's own control", stopped,
                 f"state after: {json.dumps(after_stop)[:200]}")

            after = {"entry": entry_key(page), "song": song_key(page)}
            log(f"    after Stop: {after}")
            mark("T9 Stop did not move the saved setlist entry",
                 after["entry"] == before["entry"] == "bb",
                 f"entry {before['entry']!r} -> {after['entry']!r}")
            mark("T10 Stop did not move the song's own Practice Key",
                 after["song"] == before["song"] == "d",
                 f"song {before['song']!r} -> {after['song']!r}")

            # And End Set after Stop, since that is the real sequence a singer uses.
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            ended = click_text(page, "End karaoke set")
            settle(page, 7)
            final = {"entry": entry_key(page), "song": song_key(page)}
            log(f"    after End Set: {final}")
            mark("T11 End Set after Stop keeps both keys",
                 final["entry"] == "bb" and final["song"] == "d",
                 f"{final} (end helper {bool(ended)})")
            got = rows(page)
            mark("T12 the setlist survives Stop and End Set", len(got) >= 1, f"{len(got)} rows")
            report = {"before": before, "after_stop": after, "after_end": final,
                      "transport": state, "transport_after_stop": after_stop}
        finally:
            (OUT / "stop-transport.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            browser.close()

    passed = sum(1 for v in GATES.values() if v)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "stop-transport-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
