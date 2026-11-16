"""The hotfix, in the real browser: tonight's key changes what you hear and nothing else.

The exact example asked for:

    Song: Say.  Saved Karaoke entry: Bb.  Permanent song Practice Key: D.  Tonight: Ab.

During the performance the live key is Ab and the backing plays in Ab; the saved entry stays Bb
and the song's permanent Practice Key stays D. After Stop and after End Set both are still
right, the song reopens on D outside Karaoke and the setlist still reads Bb. A normal Practice
Key change made outside Karaoke still saves.

The key is read from the PERSISTED state file (``music_user_state.json`` ->
``practice_key_by_source``), never from the sidebar: the Part 3c read layer deliberately makes
the sidebar show tonight's key while the song is being sung, so a sidebar reading cannot answer
"what was saved". That mistake is what made an earlier Stop check look clean over a live defect.

This runs on plain dev, so the Lead Sheet is left alone and the page player owns the take.

Usage:  python -X utf8 scripts/_accept_pkfix_saved_key.py http://127.0.0.1:8630
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8630"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    key_token,
    low,
    press_play,
    settle,
    wait_for_app,
)
from _accept_karaoke_qa import card_identity, set_pk_token  # noqa: E402
from _accept_karaoke_stop_transport import IFRAME_CLICK, TRANSPORT, entry_key, song_key  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-pkfix"
OUT.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "data"))
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []

AUDIO_CENSUS = """
() => {
  const rows = [];
  const look = (doc, where) => {
    if (!doc) return;
    for (const a of doc.querySelectorAll('audio')) {
      rows.push({where: where, src: String(a.currentSrc || a.src || '').slice(-40),
                 paused: !!a.paused, muted: !!a.muted, t: Number((a.currentTime||0).toFixed(2)),
                 ready: Number(a.readyState)});
    }
  };
  look(document, 'page');
  let i = 0;
  for (const f of document.querySelectorAll('iframe')) {
    i += 1;
    try { look(f.contentDocument, 'frame' + i); } catch (e) {}
  }
  return rows;
}
"""


def log(msg: str) -> None:
    print(msg, flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"  {'PASS' if ok else 'FAIL'}  {gate}" + (f"  [{detail}]" if detail else ""))


def observe(msg: str) -> None:
    OBSERVED.append(msg)
    log(f"  OBS   {msg}")


def store_sites() -> list[dict]:
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
                    sites.append({"at": where, "keys": {str(k): str(v) for k, v in store.items()}})
                for k, v in cur.items():
                    if isinstance(v, (dict, list)):
                        stack.append((v, f"{where}.{k}"))
            elif isinstance(cur, list):
                for i, v in enumerate(cur):
                    if isinstance(v, (dict, list)):
                        stack.append((v, f"{where}[{i}]"))
    return sites


def saved_say() -> str:
    """Say's PERSISTED Practice Key, normalised. "" when the store has no entry for it."""
    for site in store_sites():
        for k, v in site["keys"].items():
            if "Say" in k:
                return key_token(v)
    return ""


def keep_trace(label: str) -> None:
    """The app's own account of every saved-key write, kept before the runner deletes its dir."""
    for name, tag in (("_pk_store.jsonl", "pkstore"), ("_karaoke_retune.jsonl", "retune"),
                      ("_pk_diag.jsonl", "diag")):
        src = DATA_DIR / name
        if not src.exists():
            continue
        try:
            (OUT / f"{tag}-{label}.jsonl").write_text(src.read_text(encoding="utf-8"),
                                                      encoding="utf-8")
        except Exception as exc:
            observe(f"could not keep {tag}-{label}: {exc}")


def keep_state(label: str) -> None:
    for path in sorted(DATA_DIR.rglob("music_user_state.json")):
        try:
            (OUT / f"state-{label}.json").write_text(path.read_text(encoding="utf-8"),
                                                     encoding="utf-8")
        except Exception as exc:
            observe(f"could not keep {label}: {exc}")
        return


def playing(page: Page) -> list[dict]:
    try:
        rows = page.evaluate(AUDIO_CENSUS) or []
    except Exception:
        return []
    return [r for r in rows if not r.get("paused") and int(r.get("ready") or 0) >= 2]


def card_state(page: Page) -> str:
    try:
        st = page.evaluate(TRANSPORT) or {}
        return str((st.get("btn") or {}).get("state") or "")
    except Exception:
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
            mark("H1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)

            # Queue FIRST so the entry keeps Say's own Bb, THEN save D as the song's own key.
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            settle(page, 3)
            set_pk_token(page, "D")
            settle(page, 7)
            keep_state("1-before")
            keep_trace("1-before")
            before = saved_say()
            mark("H2 Say's permanent Practice Key is saved as D", before == "d",
                 f"persisted store = {before!r}")

            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            entry_before = entry_key(page)
            mark("H3 the saved Karaoke entry is Bb", entry_before == "bb",
                 f"entry = {entry_before!r}")
            click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark("H4 the set performs", "now singing" in low(page.inner_text("body") or ""))

            click_nav(page, "Backing")
            settle(page, 5)
            played = press_play(page)
            for _ in range(40):
                if playing(page) or card_state(page) in ("playing", "starting"):
                    break
                settle(page, 3)
            mark("H5 a take is playing before the retune",
                 bool(playing(page)) or card_state(page) == "playing",
                 f"play={bool(played)} card={card_state(page)!r} "
                 f"sounding={len(playing(page))}")

            # ---- tonight's key ---------------------------------------------------------
            retuned = set_pk_token(page, "Ab")
            settle(page, 9)
            ident = card_identity(page)
            live = key_token(ident.get("backing_key") or "")
            mark("H6 the live performance key is Ab", live == "ab",
                 f"{ident.get('backing_line')!r} (setter {bool(retuned)})")
            for _ in range(30):
                if playing(page):
                    break
                settle(page, 3)
            sounding = playing(page)
            mark("H7 the backing is actually playing after the retune", bool(sounding),
                 f"{len(sounding)} sounding, t={[r.get('t') for r in sounding]}")

            keep_state("2-during")
            keep_trace("2-during")
            during = saved_say()
            during_entry = entry_key(page)
            mark("H8 the PERMANENT Practice Key is still D during the performance",
                 during == "d", f"persisted store = {during!r} (the sidebar may show Ab by design)")
            mark("H9 the saved Karaoke entry is still Bb during the performance",
                 during_entry == "bb", f"entry = {during_entry!r}")

            # ---- Stop, from the transport's own control --------------------------------
            click_nav(page, "Backing")
            settle(page, 4)
            stopped = bool(page.evaluate(IFRAME_CLICK, "#stop"))
            if not stopped:
                stopped = bool(page.evaluate(IFRAME_CLICK, "#btn"))
                if stopped:
                    observe("stopped with the card's own #btn, which is Stop while a take runs")
            if not stopped:
                stopped = bool(click_text(page, "Stop"))
            settle(page, 8)
            keep_state("3-after-stop")
            keep_trace("3-after-stop")
            after_stop, after_stop_entry = saved_say(), entry_key(page)
            mark("H10 Stop really was pressed", stopped, f"card now {card_state(page)!r}")
            mark("H11 after Stop the permanent Practice Key is still D", after_stop == "d",
                 f"persisted store = {after_stop!r}")
            mark("H12 after Stop the saved Karaoke entry is still Bb", after_stop_entry == "bb",
                 f"entry = {after_stop_entry!r}")

            # ---- End Set ---------------------------------------------------------------
            click_nav(page, "Backing")
            settle(page, 4)
            ended = click_text(page, "End") or click_text(page, "End Set")
            settle(page, 9)
            keep_state("4-after-end")
            keep_trace("4-after-end")
            after_end, after_end_entry = saved_say(), entry_key(page)
            mark("H13 after End Set the permanent Practice Key is still D", after_end == "d",
                 f"persisted store = {after_end!r} (ended={bool(ended)})")
            mark("H14 after End Set the saved Karaoke entry is still Bb",
                 after_end_entry == "bb", f"entry = {after_end_entry!r}")

            # ---- reopening, outside Karaoke --------------------------------------------
            click_nav(page, "Songs")
            settle(page, 4)
            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 6)
            shown = song_key(page)
            mark("H15 reopening Say outside Karaoke shows D", shown == "d",
                 f"sidebar shows {shown!r}")

            # ---- and an ordinary change still saves ------------------------------------
            moved = set_pk_token(page, "F")
            settle(page, 8)
            keep_state("5-ordinary-change")
            keep_trace("5-ordinary-change")
            ordinary = saved_say()
            mark("H16 an ordinary Practice Key change outside Karaoke still saves",
                 ordinary == "f", f"persisted store = {ordinary!r} (setter {bool(moved)})")

            report = {"before": before, "during": during, "after_stop": after_stop,
                      "after_end": after_end, "reopened_sidebar": shown,
                      "ordinary_change": ordinary,
                      "entries": {"before": entry_before, "during": during_entry,
                                  "after_stop": after_stop_entry, "after_end": after_end_entry},
                      "live_key_during": live, "stopped": stopped}
            (OUT / "pkfix-report.json").write_text(json.dumps(report, indent=2,
                                                              ensure_ascii=False),
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
    (OUT / "pkfix-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
