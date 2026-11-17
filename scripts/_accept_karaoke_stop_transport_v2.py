"""The Stop safeguard, done properly: does stopping a performance rewrite a saved key?

This replaces an earlier run of mine that reported nothing useful and that I wrongly treated as
a satisfied safeguard. Two faults, both now fixed:

  1. STOP WAS NEVER PRESSED. The Backing card's transport only offers #stop while its take is
     running, and during a karaoke performance the SURFACE owns the audio - the card sat at
     state "stopped" with no #stop in it, the page-text fallback found nothing, and the gate
     that was meant to prove Stop is harmless instead proved only that nothing had happened.
     The take is now started from the surface's own control (#live-stop-btn, which mounts
     offering "Resume playback"), and the script waits for the card to report "playing" before
     looking for Stop.
  2. THE KEYS WERE READ FROM THE SIDEBAR. That control is exactly what Part 3c deliberately
     makes show tonight's key while the song is being sung, so a reading of "Ab" there proves
     nothing about what was SAVED. The instrument here is the persisted store on disk -
     music_user_state.json, practice_key_by_source - read before Stop, after Stop and after End
     Set. The sidebar is still recorded, as a display observation.

The question, in the user's words: stopping a performance must not permanently overwrite the
saved song key or the saved setlist entry.

Usage:  python -X utf8 scripts/_accept_karaoke_stop_transport_v2.py http://127.0.0.1:8620
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8620"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    low,
    press_play,
    settle,
    wait_for_app,
)
from _accept_karaoke_slice2 import surface_frame  # noqa: E402
from _accept_karaoke_slice2b import SURFACE_AUDIO, ensure_playing  # noqa: E402
from _accept_karaoke_qa import set_pk_token  # noqa: E402
from _accept_karaoke_stop_transport import (  # noqa: E402
    IFRAME_CLICK,
    TRANSPORT,
    entry_key,
    song_key,
)
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-karaoke-slice2"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []

#: The app writes its state under the data dir the runner hands both the server and this script.
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "data"))


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def observe(msg: str) -> None:
    OBSERVED.append(msg)
    log(f"  OBS   {msg}")


def store_sites() -> list[dict]:
    """EVERY practice_key_by_source in the persisted state, each with where it was found.

    Merging them into one dict is how a session-scoped value masquerades as the durable
    store: whichever happened to be visited last wins and the reading looks authoritative.
    Each site is reported separately, with its JSON path, so "what is SAVED" is answerable.
    """
    sites: list[dict] = []
    for path in sorted(DATA_DIR.rglob("music_user_state.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            observe(f"could not read {path}: {exc}")
            continue
        stack: list[tuple] = [(data, path.name)]
        while stack:
            cur, where = stack.pop()
            if isinstance(cur, dict):
                store = cur.get("practice_key_by_source")
                if isinstance(store, dict):
                    sites.append({"at": where + ".practice_key_by_source",
                                  "keys": {str(k): str(v) for k, v in store.items()}})
                for k, v in cur.items():
                    if isinstance(v, (dict, list)):
                        stack.append((v, f"{where}.{k}"))
            elif isinstance(cur, list):
                for i, v in enumerate(cur):
                    if isinstance(v, (dict, list)):
                        stack.append((v, f"{where}[{i}]"))
    return sites


def keep_trace(label: str) -> None:
    """The app's own account of each re-key attempt (MUSIC_KARAOKE_RETUNE_TRACE).

    It is written into the data dir, which the runner deletes when it finishes - so a run that
    needed it had already thrown it away.
    """
    for name, tag in (("_karaoke_retune.jsonl", "retune"), ("_pk_store.jsonl", "pkstore")):
        src = DATA_DIR / name
        if not src.exists():
            continue
        try:
            (OUT / f"{tag}-{label}.jsonl").write_text(src.read_text(encoding="utf-8"),
                                                      encoding="utf-8")
        except Exception as exc:
            observe(f"could not keep the {label} {tag} trace: {exc}")


def keep_state(label: str) -> None:
    """Keep the state file itself; the runner deletes its data dir when it finishes."""
    for path in sorted(DATA_DIR.rglob("music_user_state.json")):
        try:
            (OUT / f"state-{label}.json").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as exc:
            observe(f"could not keep {label} state: {exc}")
        return


def saved_store() -> dict:
    """The durable store, preferring a site that is not a per-session snapshot."""
    sites = store_sites()
    for s in sites:
        at = s["at"]
        if "session" not in at.lower() and "snapshot" not in at.lower():
            return s["keys"]
    return sites[0]["keys"] if sites else {}


def say_saved(store: dict) -> str:
    for k, v in store.items():
        if "Say" in k:
            return str(v).strip().lower().replace("♭", "b").replace(" major", "")
    return ""


def main() -> int:
    report: dict = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 1280, "height": 900}, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            page.goto(URL, wait_until="domcontentloaded")
            settle(page, 5)
            mark("S1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)

            # Queue FIRST, so the setlist entry keeps Say's own Bb; THEN set the song's own
            # Practice Key to D. The earlier order queued the entry at D and made the
            # "entry stayed at Bb" gates fail on the setup rather than on the behaviour.
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            settle(page, 3)
            # Say's own Practice Key, set with nothing performing: this is what must survive.
            set_pk_token(page, "D")
            settle(page, 6)
            before_sidebar = song_key(page)
            before_store = saved_store()
            keep_state("before")
            keep_trace("before")
            for site in store_sites():
                log(f"    store site before: {site['at']} = {json.dumps(site['keys'])}")
            mark("S2 Say's own Practice Key is saved as D before any performance",
                 say_saved(before_store) == "d",
                 f"store={say_saved(before_store)!r} sidebar={before_sidebar!r}")

            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            entry_before = entry_key(page)
            click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark("S3 the set performs", "now singing" in low(page.inner_text("body") or ""),
                 f"entry={entry_before!r}")

            click_nav(page, "Backing")
            settle(page, 5)
            # A temporary retune, so Stop has something it could wrongly make permanent.
            retuned = set_pk_token(page, "Ab")
            settle(page, 6)
            mark("S4 the performance is retuned to a temporary Ab", bool(retuned))

            # The take must be RUNNING, or the card offers no Stop and nothing is tested.
            played = press_play(page)
            frame: Frame | None = None
            for _ in range(60):
                frame = surface_frame(page)
                if frame:
                    break
                settle(page, 3)
            if frame is None:
                observe("no performance surface - Stop cannot be exercised")
                return 2
            # A retune retires the take that was playing, so the surface may be mounting a new
            # one; keep asking until it actually runs. Without a running take the card offers no
            # Stop, and then this script measures nothing at all - which is how the first
            # version of it "passed".
            take = {}
            for _ in range(4):
                frame = surface_frame(page) or frame
                take = ensure_playing(page, frame, 45) or {}
                if take.get("paused") is False:
                    break
                settle(page, 5)
            settle(page, 3)
            take = (surface_frame(page) or frame).evaluate(SURFACE_AUDIO) or {}
            mark("S5 the take is actually playing before Stop",
                 take.get("paused") is False, f"play={bool(played)} t={take.get('t')}")

            state = page.evaluate(TRANSPORT) or {}
            card = (state.get("btn") or {}).get("state")
            # There is no separate #stop in this component: the single #btn IS Stop once the
            # state is not "stopped" - which is how the shared controller's own compact bar
            # stops a take (it clicks #btn). An earlier version looked for #stop, never found
            # it, and reported that Stop was unavailable.
            has_stop = bool(state.get("stop")) or str(card or "") not in ("", "stopped")
            mark("S6 the transport offers a Stop control once the take runs",
                 has_stop, f"card state={card!r} stop={json.dumps(state.get('stop'))}")

            stopped = bool(page.evaluate(IFRAME_CLICK, "#stop"))
            if not stopped:
                stopped = bool(page.evaluate(IFRAME_CLICK, "#btn"))
                if stopped:
                    observe("stopped with the card's own #btn, which is Stop while a take runs")
            if not stopped:
                observe("neither #stop nor #btn took the click; trying the page's Stop")
                stopped = bool(click_text(page, "Stop"))
            settle(page, 8)
            after_take = {}
            try:
                fr = surface_frame(page)
                after_take = (fr.evaluate(SURFACE_AUDIO) or {}) if fr else {}
            except Exception:
                pass
            mark("S7 Stop was really pressed and the take stopped",
                 stopped and (after_take.get("paused") in (True, None)),
                 f"clicked={stopped} take now paused={after_take.get('paused')}")

            after_store = saved_store()
            after_sidebar = song_key(page)
            after_entry = entry_key(page)
            keep_state("after-stop")
            keep_trace("after-stop")
            for site in store_sites():
                log(f"    store site after Stop: {site['at']} = {json.dumps(site['keys'])}")
            mark("S8 Stop did not rewrite Say's SAVED Practice Key",
                 say_saved(after_store) == "d",
                 f"store {say_saved(before_store)!r} -> {say_saved(after_store)!r} "
                 f"(sidebar shows {after_sidebar!r})")
            mark("S9 Stop did not move the saved setlist entry",
                 after_entry == entry_before == "bb",
                 f"entry {entry_before!r} -> {after_entry!r}")

            # ---- and End Set, where the temporary layer must be released ---------------
            click_nav(page, "Backing")
            settle(page, 4)
            ended = click_text(page, "End") or click_text(page, "End Set")
            settle(page, 8)
            end_store = saved_store()
            end_sidebar = song_key(page)
            end_entry = entry_key(page)
            keep_state("after-end")
            keep_trace("after-end")
            for site in store_sites():
                log(f"    store site after End Set: {site['at']} = {json.dumps(site['keys'])}")
            mark("S10 End Set left Say's SAVED Practice Key as D",
                 say_saved(end_store) == "d",
                 f"store={say_saved(end_store)!r} (sidebar {end_sidebar!r}, ended={bool(ended)})")
            mark("S11 End Set left the saved setlist entry at Bb",
                 end_entry == "bb", f"entry={end_entry!r}")
            # The display is a separate, known QA item - recorded, not gated.
            if end_sidebar != "d":
                observe(f"after End Set the sidebar still displays {end_sidebar!r} while the "
                        f"saved store holds {say_saved(end_store)!r} - the known temporary-key "
                        f"DISPLAY residue, held as its own QA item")

            report = {"before": {"store": before_store, "sidebar": before_sidebar,
                                 "entry": entry_before},
                      "after_stop": {"store": after_store, "sidebar": after_sidebar,
                                     "entry": after_entry, "clicked": stopped},
                      "after_end": {"store": end_store, "sidebar": end_sidebar,
                                    "entry": end_entry}}
            (OUT / "stop-v2.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
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
    (OUT / "stop-v2-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
