"""Slice 2: Pause / Resume on the real controls, a rerun under a playing take, and who leads.

K9/K16 proved one audible player at a moment in each Lead Sheet state. They do not cover what
happens when playback is *driven*, or when Streamlit reruns the page underneath a playing take -
and a second player is exactly the kind of defect that appears on the run after the one you
looked at.

WHICH controls, and why this took three attempts. During a karaoke performance the surface owns
the audio (that is what ``_surface_owns_audio`` means), so the Backing card's transport stays
STOPPED and offers no Pause - its ``#pz`` carries the ``hidden`` attribute, and a click helper
that respects ``hidden`` correctly refuses it. Driving that component measured nothing twice.
The performance's real controls are the surface's own, inside the follow component:

    #live-audio      the take
    #live-stop-btn   "Pause playback", the same button Resumes

The card transport's state is still recorded, as context rather than as a gate: it staying
STOPPED is correct here, not a defect.

Two further traps, both of which made an earlier version pass on nothing:

  * ``audible`` requires an unmuted element, and the shared nudge MUTES to defeat headless
    autoplay blocking - so it was 0 in every sample and every "no second player" gate passed on
    silence. Chromium is launched with the autoplay policy relaxed instead, and the gates below
    require EXACTLY ONE sounding element: a gate that accepts zero is not a gate about
    duplicate audio.
  * a programmatic ``el.click()`` is not a user activation in Chromium. Playwright's click is.

Usage:  python -X utf8 scripts/_accept_karaoke_slice2b.py http://127.0.0.1:8618
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8618"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    low,
    press_play,
    set_lead_sheet,
    settle,
    wait_for_app,
)
from _accept_karaoke_slice2 import AUDIO_CENSUS, surface_frame  # noqa: E402
from _accept_karaoke_stop_transport import TRANSPORT  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-slice2"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []
TRACE: list[dict] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def observe(msg: str) -> None:
    OBSERVED.append(msg)
    log(f"  OBS   {msg}")


CONTROLLER = """
() => {
  let c = null;
  try { c = window.top.__lsFollow; } catch (e) { return {reachable: false, error: String(e)}; }
  if (!c) return {reachable: false};
  const mine = window.frameElement;
  return {
    reachable: true,
    leader: c.leader || null,
    suspended: (() => { try { return !!c.suspended(); } catch (e) { return null; } })(),
    providers: ((c.providers || [])).map(p => ({
      id: p.id, priority: p.priority, from_this_frame: p.frame === mine,
      has_current: (() => { try { return !!p.hasCurrent(); } catch (e) { return null; } })(),
    })),
  };
}
"""

#: The surface's own take and its Pause control, read from inside the surface frame.
SURFACE_AUDIO = """
() => {
  const a = document.getElementById('live-audio');
  const b = document.getElementById('live-stop-btn');
  return {
    has_audio: !!a,
    src: a ? String(a.currentSrc || a.src || '').slice(-40) : '',
    paused: a ? !!a.paused : null,
    muted: a ? !!a.muted : null,
    t: a ? Number((a.currentTime || 0).toFixed(2)) : null,
    ready: a ? Number(a.readyState) : null,
    button: b ? {text: (b.innerText || '').trim(), state: b.getAttribute('data-state') || '',
                 hidden: !!b.hidden, disabled: !!b.disabled} : null,
  };
}
"""

MELODY_PRESENT = """
() => {
  const hits = [];
  const scan = (doc, where) => {
    if (!doc) return;
    const n = doc.querySelectorAll('.abcjs-container, [id^=abc], .staff-svg, svg.abcjs').length;
    if (n) hits.push({where: where, staves: n});
  };
  scan(document, 'top');
  for (const f of document.querySelectorAll('iframe')) {
    try { scan(f.contentDocument, 'iframe'); } catch (e) {}
  }
  return hits;
}
"""


def census(page: Page) -> list[dict]:
    try:
        return page.evaluate(AUDIO_CENSUS) or []
    except Exception:
        return []


def snapshot(page: Page, frame: Frame | None, label: str) -> dict:
    rows = census(page)
    # Sounding, not "audible": muting is a harness concern, and a muted element still running is
    # still a second player. Audibility is recorded separately so a silent one is visible too.
    sounding = [r for r in rows
                if not r.get("paused") and not r.get("ended") and int(r.get("readyState") or 0) >= 2]
    loud = [r for r in rows if r.get("audible")]
    card = {}
    try:
        card = (page.evaluate(TRANSPORT) or {}).get("btn") or {}
    except Exception:
        pass
    surf = {}
    if frame is not None:
        try:
            surf = frame.evaluate(SURFACE_AUDIO) or {}
        except Exception:
            pass
    shot = {
        "label": label,
        "elements": len(rows),
        "sounding": len(sounding),
        "audible": len(loud),
        "positions": [r.get("t") for r in rows],
        "muted": [r.get("muted") for r in rows],
        "card_state": card.get("state"),
        "surface": surf,
        "rows": rows,
    }
    TRACE.append(shot)
    log(f"    {label}: {len(rows)} element(s), {len(sounding)} sounding, {len(loud)} audible, "
        f"t={shot['positions']}, card={card.get('state')!r}")
    # Which element is which, so a two-element moment is explicable rather than alarming.
    for r in rows:
        log(f"        {r.get('where'):<8} paused={r.get('paused')} muted={r.get('muted')} "
            f"ready={r.get('readyState')} t={r.get('t')} audible={r.get('audible')} "
            f"...{r.get('src')}")
    return shot


def wait_for_take(page: Page, frame: Frame, secs: float = 150.0) -> dict:
    """The take has to be generated before it can play; wait for the thing itself."""
    waited = 0.0
    last: dict = {}
    while waited < secs:
        try:
            last = frame.evaluate(SURFACE_AUDIO) or {}
        except Exception:
            last = {}
        if last.get("has_audio") and last.get("src") and int(last.get("ready") or 0) >= 2:
            return last
        page.wait_for_timeout(2000)
        waited += 2.0
    return last


def ensure_playing(page: Page, frame: Frame, secs: float = 40.0) -> dict:
    """Get the surface's take running, by what its own button says it will do.

    The surface mounts with the take PAUSED and the button offering "Resume playback" - so a
    script that assumes it is playing presses Pause first and measures the opposite of what it
    names. The button's ``data-state`` is the instruction: "resume" means pressing it starts.
    """
    state = frame.evaluate(SURFACE_AUDIO) or {}
    btn = (state.get("button") or {}).get("state") or ""
    if state.get("paused") and btn == "resume":
        try:
            frame.locator("#live-stop-btn").click(timeout=15000)
        except Exception as exc:
            observe(f"could not start the take from the surface's own control: {exc}")
    waited = 0.0
    while waited < secs:
        state = frame.evaluate(SURFACE_AUDIO) or {}
        if state.get("paused") is False:
            return state
        page.wait_for_timeout(1500)
        waited += 1.5
    return state


def main() -> int:
    with sync_playwright() as pw:
        # Real sound instead of a muted nudge, so "audible" means something.
        browser = pw.chromium.launch(
            headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark("P1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            queued = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            started = click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark("P2 a karaoke set is performing",
                 "now singing" in low(page.inner_text("body") or ""),
                 f"queued={bool(queued)} start={bool(started)}")

            click_nav(page, "Backing")
            settle(page, 6)
            played = press_play(page)
            frame: Frame | None = None
            for _ in range(60):
                frame = surface_frame(page)
                if frame:
                    break
                settle(page, 3)
            mark("P3 the performance surface mounts with the Lead Sheet OFF",
                 frame is not None, f"play={bool(played)}")
            if frame is None:
                observe("no surface - nothing further can be measured")
                return 2

            take = wait_for_take(page, frame)
            log(f"    take as mounted: {json.dumps(take)}")
            mark("P4 the surface mounts a take of its own",
                 bool(take.get("src")) and int(take.get("ready") or 0) >= 2,
                 f"ready={take.get('ready')} paused={take.get('paused')}")
            take = ensure_playing(page, frame)
            log(f"    take once started: {json.dumps(take)}")
            mark("P5 the take plays from the surface's own control",
                 take.get("paused") is False, f"{json.dumps(take)[:200]}")

            playing = snapshot(page, frame, "playing")
            mark("P6 exactly one element is sounding while the take runs",
                 playing["sounding"] == 1,
                 f"{playing['sounding']} sounding of {playing['elements']}")
            mark("P7 that player is actually audible - not muted, not silent",
                 playing["audible"] == 1,
                 f"{playing['audible']} audible, muted={playing['muted']}")
            observe(f"the Backing card's transport reads {playing['card_state']!r} during a "
                    f"karaoke performance - correct: the surface owns the audio, so the card "
                    f"offers no Pause of its own")

            # ---- Pause on the surface's own control ------------------------------------
            paused_click = True
            try:
                frame.locator("#live-stop-btn").click(timeout=15000)
            except Exception as exc:
                paused_click = False
                observe(f"the surface's Pause refused a real click: {exc}")
            settle(page, 4)
            paused = snapshot(page, frame, "after Pause")
            mark("P8 Pause on the surface's own control silences the take",
                 paused_click and paused["sounding"] == 0,
                 f"click={paused_click} sounding={paused['sounding']}")
            mark("P9 Pause created no second player",
                 paused["elements"] <= playing["elements"],
                 f"{playing['elements']} -> {paused['elements']} element(s)")

            # ---- Resume, in the SAME element -------------------------------------------
            was = float((paused.get("surface") or {}).get("t") or 0)
            resumed_click = True
            try:
                frame.locator("#live-stop-btn").click(timeout=15000)
            except Exception as exc:
                resumed_click = False
                observe(f"the surface's Resume refused a real click: {exc}")
            settle(page, 6)
            resumed = snapshot(page, frame, "after Resume")
            now = float((resumed.get("surface") or {}).get("t") or 0)
            mark("P10 Resume sounds exactly one player, not two",
                 resumed_click and resumed["sounding"] == 1,
                 f"click={resumed_click} sounding={resumed['sounding']}")
            mark("P11 Resume carried on instead of restarting",
                 now >= was - 0.5 and resumed["elements"] <= playing["elements"],
                 f"position {was} -> {now}, {resumed['elements']} element(s)")

            # ---- a rerun underneath a playing take -------------------------------------
            # Each of these is measured with the take RUNNING, because "two players" is a
            # question about sound. A snapshot taken while everything is paused answers it with
            # zero and looks like a pass.
            click_nav(page, "Backing")
            settle(page, 6)
            frame = surface_frame(page) or frame
            ensure_playing(page, frame)
            settle(page, 3)
            rerun = snapshot(page, frame, "playing, after a neutral rerun")
            mark("P12 a rerun while playing leaves exactly one player sounding",
                 rerun["sounding"] == 1,
                 f"{rerun['sounding']} sounding of {rerun['elements']}")

            set_lead_sheet(page, True)
            settle(page, 8)
            frame = surface_frame(page) or frame
            ensure_playing(page, frame)
            settle(page, 3)
            on = snapshot(page, frame, "playing, Lead Sheet switched ON")
            mark("P13 turning the Lead Sheet ON keeps exactly one player sounding",
                 on["sounding"] == 1, f"{on['sounding']} sounding of {on['elements']}")
            set_lead_sheet(page, False)
            settle(page, 8)
            frame = surface_frame(page) or frame
            ensure_playing(page, frame)
            settle(page, 3)
            off = snapshot(page, frame, "playing, Lead Sheet switched OFF again")
            mark("P14 turning it back OFF keeps exactly one player sounding",
                 off["sounding"] == 1, f"{off['sounding']} sounding of {off['elements']}")
            # The invariant across the whole run, not at one moment: two elements may exist
            # during a handoff, but two must never be running at once.
            worst = max((s["sounding"] for s in TRACE), default=0)
            mark("P15 two players never sounded at the same time, at any point in this run",
                 worst <= 1,
                 "most sounding at once: %d (elements seen: %s)"
                 % (worst, [s["elements"] for s in TRACE]))

            # ---- who leads the page ----------------------------------------------------
            ctl = {}
            if frame is not None:
                try:
                    ctl = frame.evaluate(CONTROLLER) or {}
                except Exception as exc:
                    observe(f"controller unreadable after the switches: {exc}")
            log(f"    controller: {json.dumps(ctl)[:400]}")
            provs = ctl.get("providers") or []
            mine = [p for p in provs if p.get("from_this_frame")]
            mark("P16 the karaoke frame is registered with the one page controller",
                 ctl.get("reachable") is True and len(mine) >= 1,
                 f"{len(mine)} provider(s) from this frame of {len(provs)}")
            mark("P17 one provider per frame - the lyrics cannot lose the page to the chart",
                 len(mine) <= 1, f"{[p.get('id') for p in mine]}")

            staves = []
            try:
                staves = page.evaluate(MELODY_PRESENT) or []
            except Exception:
                pass
            if staves:
                mark("P18 with a melody staff on screen the leader is decided, not shared",
                     ctl.get("leader") is not None,
                     f"staves={staves} leader={ctl.get('leader')!r}")
            else:
                observe("no Original Melody staff renders on this surface during a karaoke "
                        "performance, so the melody-vs-lyrics priority case cannot be exercised "
                        "here - priorities stay pinned by unit test "
                        "(MELODY_PRIORITY 20 > LEAD_SHEET_PRIORITY 10)")

            (OUT / "slice2b-trace.json").write_text(
                json.dumps({"trace": TRACE, "controller": ctl, "staves": staves}, indent=2),
                encoding="utf-8")
        finally:
            context.close()
            browser.close()

    passed = sum(1 for ok in GATES.values() if ok)
    log("\n" + "=" * 70)
    for gate, ok in GATES.items():
        log(f"  {'PASS' if ok else 'FAIL'}  {gate}")
    for note in OBSERVED:
        log(f"  OBS   {note}")
    log(f"\n{passed}/{len(GATES)} gates passed")
    (OUT / "slice2b-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
