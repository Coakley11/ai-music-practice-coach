"""Issue 69 Part E: the whole performance moves key, not just the labels.

Drives the real application. The reported defect was a karaoke performance that
disagreed with itself - ``Dsus4`` on the chord tiles, ``Csus4/D`` in the Current Chord -
because the setlist entry keeps "the Practice Key from the sidebar at the moment you
add" (the app's own words) while the tiles follow the global key.

Say is the song from the report. Its original key is B flat and its Intro contains
``Bbsus4/C``, which is where both screenshot chords come from: +2 to C gives
``Csus4/D``, +4 to D gives ``Dsus4/E``. Its Verse is ``Bb:2|Eb:2p`` - two chords to a
bar with the second pushed - so nothing here may assume a chart cell is a bar.

Usage:
  MUSIC_MT_KEY_TRACE=1 MUSIC_APP_DATA_DIR=<disposable> streamlit run \
      streamlit_music_practice_app.py --server.port 8571
  python scripts/_accept_issue69_karaoke_transposition.py http://127.0.0.1:8571
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from walk_creative_backing_matrix import click_nav, expand_sidebar, wait_idle  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402
from _walk_core_key_coherence import set_songs_practice_key  # noqa: E402
from _walk_custom_practice_key import pk_val  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8571"
OUT = SCRIPTS / "evidence-issue69"
OUT.mkdir(parents=True, exist_ok=True)

FLAT = "\u266d"
SHARP = "\u266f"

GATES: dict[str, bool] = {}
NOTES: list[str] = []


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def settle(page: Page, seconds: float = 3.0) -> None:
    wait_idle(page, int(seconds * 1000))


def low(s: str) -> str:
    return (s or "").lower().replace("♯", "#").replace("♭", "b")


def key_token(s: str) -> str:
    """Normalise a key as the app may word it: "B-flat major" and "Bb" are one key."""
    t = low(s).strip()
    if t.endswith(" minor"):
        return t[: -len(" minor")].strip().replace(" ", "") + "m"
    if t.endswith(" major"):
        return t[: -len(" major")].strip().replace(" ", "")
    return t.replace(" ", "")


def shot(page: Page, name: str) -> str:
    body = page.inner_text("body") or ""
    (OUT / f"{name}.txt").write_text(body[:40000], encoding="utf-8")
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    return body


def wait_for_app(page: Page, timeout_s: float = 150.0) -> bool:
    waited = 0.0
    while waited < timeout_s:
        body = page.inner_text("body") or ""
        if len(body.strip()) > 400 and "PAGES" in body.upper():
            return True
        settle(page, 3)
        waited += 3
    return False


def click_key(page: Page, key_class: str) -> bool:
    """Click a control by its Streamlit key class - the stable handle."""
    loc = page.locator(f'[class*="st-key-{key_class}"] button')
    if not loc.count():
        return False
    try:
        loc.first.scroll_into_view_if_needed()
        loc.first.click(timeout=8000)
        settle(page, 4)
        return True
    except Exception as exc:
        log(f"  click {key_class} failed: {exc}")
        return False


def click_text(page: Page, label: str) -> bool:
    buttons = page.locator("button")
    for i in range(buttons.count()):
        el = buttons.nth(i)
        try:
            text = (el.inner_text() or "").strip()
        except Exception:
            continue
        if label.lower() not in text.lower():
            continue
        try:
            el.scroll_into_view_if_needed()
            el.click(timeout=8000)
            settle(page, 4)
            return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------
# Reading the performance off the page
# --------------------------------------------------------------------------
_CHORD = re.compile(r"\b([A-G](?:#|b|♯|♭)?(?:maj7|maj9|m7b5|m7|m9|sus4|sus2|"
                    r"7sus4|7|dim|aug|add9|11|13|m)?(?:/[A-G](?:#|b|♯|♭)?)?)\b")


def follow_chords(page: Page) -> dict[str, str]:
    """Current / Next Chord, read where the app draws them.

    The reported screenshot came from the lead sheet's live strip (``#live-chord``
    / ``#live-next`` inside its iframe), not from a page-level tile - an earlier
    run looked for ``.ui-follow-tile``, found nothing, and asserted nothing.
    """
    return live_chords(page)


def cue_line(page: Page) -> str:
    """The Intro instrumental cue, wherever it is rendered."""
    body = page.inner_text("body") or ""
    for line in body.splitlines():
        if "Instrumental" in line and ("·" in line or "-" in line):
            return line.strip()
    return ""


def chords_in(text: str) -> list[str]:
    seen: list[str] = []
    for match in _CHORD.finditer(text or ""):
        tok = match.group(1)
        if tok not in seen:
            seen.append(tok)
    return seen


DOUBLED = re.compile("[A-G](?:#|b|" + SHARP + "|" + FLAT + ")"
                     "(?:#|b|" + SHARP + "|" + FLAT + ")")


def _jsonl(name: str) -> list[dict]:
    base = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "_runtime_i69"))
    path = base / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def regen_rows() -> list[dict]:
    """The synthesizer's own log: one row per submitted / finished backing build.

    ``sig`` is ``<key>|bpm<n>|<feel>``, so this is the audible key - what was
    actually synthesized - rather than what a label says.
    """
    return _jsonl("_kc_regen_timing.jsonl")


def synth_keys(rows: list[dict]) -> list[str]:
    out = []
    for row in rows:
        if row.get("event") not in ("synth_submit", "synth_done"):
            continue
        sig = str(row.get("sig") or "")
        key = sig.split("|", 1)[0].strip()
        if key:
            out.append(f"{row.get('event')}:{key}")
    return out


IFRAME_CLICK = """(sel) => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const doc = f.contentDocument;
      if (!doc) continue;
      const b = doc.querySelector(sel);
      if (!b || b.disabled || b.hidden) continue;
      b.click();
      return true;
    } catch (e) {}
  }
  return false;
}"""

LIVE_READ = """() => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const doc = f.contentDocument;
      if (!doc || !doc.getElementById('live-chord')) continue;
      const t = (id) => String((doc.getElementById(id) || {}).innerText || '').trim();
      return {current: t('live-chord'), next: t('live-next'),
              bar: t('live-bar'), section: t('live-section')};
    } catch (e) {}
  }
  return {current: '', next: '', bar: '', section: ''};
}"""

TRANSPORT_STATE = """() => {
  for (const f of document.querySelectorAll('iframe')) {
    try {
      const doc = f.contentDocument;
      const b = doc && doc.getElementById('btn');
      if (!b) continue;
      const pz = doc.getElementById('pz');
      return {label: (b.innerText || '').trim(), state: b.getAttribute('data-state') || '',
              disabled: !!b.disabled,
              pause: pz && !pz.hidden ? (pz.getAttribute('data-mode') || '') : ''};
    } catch (e) {}
  }
  return null;
}"""


def press_play(page: Page) -> bool:
    """Click the card's Play - ``#btn`` inside the transport component iframe."""
    state = page.evaluate(TRANSPORT_STATE)
    if state is None:
        log("    transport: no component iframe on this page")
        return False
    if state.get("disabled"):
        log(f"    transport: Play disabled (state={state.get('state')!r})")
        return False
    ok = bool(page.evaluate(IFRAME_CLICK, "#btn"))
    settle(page, 3)
    return ok


def press_pause_or_resume(page: Page) -> str:
    """Click the card's Pause / Resume and say which it was."""
    state = page.evaluate(TRANSPORT_STATE) or {}
    mode = str(state.get("pause") or "")
    if not mode:
        return ""
    clicked = bool(page.evaluate(IFRAME_CLICK, "#pz"))
    settle(page, 4)
    return mode if clicked else ""


def live_chords(page: Page) -> dict[str, str]:
    """Current / Next from the lead sheet's own live strip."""
    try:
        got = page.evaluate(LIVE_READ) or {}
    except Exception:
        return {"current": "", "next": ""}
    return {"current": str(got.get("current") or "").strip(),
            "next": str(got.get("next") or "").strip(),
            "bar": str(got.get("bar") or "").strip(),
            "section": str(got.get("section") or "").strip()}


def set_lead_sheet(page: Page, on: bool = True) -> bool:
    """The live chord strip lives in the lead sheet, so it has to be open."""
    want = "On" if on else "Off"
    for _ in range(3):
        try:
            body = page.inner_text("body") or ""
        except Exception:
            body = ""
        if f"Lead sheet: {want}" in body:
            return True
        if not click_text(page, "Lead sheet:"):
            return False
        settle(page, 5)
    try:
        return f"Lead sheet: {want}" in (page.inner_text("body") or "")
    except Exception:
        return False


def goto_practice(page: Page) -> bool:
    """The Practice page - not Practice Log, which also contains "Practice"."""
    clicked = page.evaluate(
        """() => {
          const vis = (el) => !!(el && el.offsetParent !== null);
          const btns = [...document.querySelectorAll('button')].filter(vis);
          const hit = btns.find((b) => {
            const t = (b.innerText || '').trim().toLowerCase();
            return t.endsWith('practice') && !t.includes('log');
          });
          if (!hit) return false;
          hit.click();
          return true;
        }"""
    )
    settle(page, 8)
    return bool(clicked)


def wait_for_synth(page: Page, want_key: str, before: int, seconds: float = 150.0) -> str:
    """Wait for a finished build whose own signature carries ``want_key``."""
    import time as _time

    deadline = _time.time() + seconds
    seen = ""
    while _time.time() < deadline:
        rows = regen_rows()[before:]
        for row in rows:
            if row.get("event") != "synth_done":
                continue
            key = str(row.get("sig") or "").split("|", 1)[0].strip()
            seen = key or seen
            if key_token(key) == key_token(want_key):
                return key
        settle(page, 3)
    return seen


def practice_cue(page: Page) -> str:
    """The Intro cue, read where the app renders it.

    The Practice page does not show the phrasing guide by itself: it offers
    "Lyrics & phrasing" under Practice tools, and the guide ("Phrasing guide
    (optional)") opens inside that tool. An earlier run navigated to Practice,
    read the page as it stood, found no cue and so asserted nothing about the
    very text the report was about.
    """
    if not goto_practice(page):
        click_nav(page, "Practice")
    settle(page, 8)
    cue = cue_line(page)
    if cue:
        return cue
    if click_text(page, "Lyrics & phrasing") or click_text(page, "Lyrics &"):
        settle(page, 8)
    page.evaluate(
        """() => {
          for (const d of document.querySelectorAll('details')) {
            const s = d.querySelector('summary');
            const t = s ? (s.innerText || '').toLowerCase() : '';
            if (t.includes('phrasing') || t.includes('lyric')) {
              if (!d.open && s) s.click();
            }
          }
        }"""
    )
    settle(page, 5)
    cue = cue_line(page)
    if cue:
        return cue
    shot(page, "zz-practice-no-cue")
    return ""


def trace_rows() -> list[dict]:
    path = Path(os.environ.get("MUSIC_APP_DATA_DIR") or (ROOT / "_runtime_i69"))
    path = path / "_karaoke_retune.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def gate_setup(page: Page) -> bool:
    page.goto(URL, wait_until="domcontentloaded")
    settle(page, 5)
    ready = wait_for_app(page)
    body = shot(page, "01-ready")
    mark("G1 app renders", ready and len(body.strip()) > 400, f"{len(body)} chars")

    ok = pick_song(page, NOTES, "Say", "pop")
    settle(page, 4)
    body = page.inner_text("body") or ""
    original_shown = "Original Key: Bb" in body or "Original Key: B♭" in body
    mark("G2 Say active, original key Bb shown", bool(ok) and original_shown)

    pk = pk_val(page)
    mark("G3 practice key starts at the song's own Bb", key_token(pk) == "bb",
         f"sidebar={pk!r}")

    expand_sidebar(page)
    inst = page.evaluate("""() => {
        const el = [...document.querySelectorAll('[role="combobox"],input[aria-label]')]
          .find(e => /instrument/i.test(e.getAttribute('aria-label') || ''));
        return el ? String(el.value || '') : '';
    }""")
    mark("G4 instrument is Voice (karaoke needs it)", "voice" in low(str(inst)),
         f"instrument={inst!r}")
    return bool(ok)


def gate_start_performance(page: Page) -> bool:
    """Queue Say while the sidebar says Bb, so the entry freezes at Bb."""
    click_nav(page, "Songs")
    settle(page, 4)
    added = click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
    mark("G5 Say queued while the sidebar said Bb", added)

    opened = click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 5)
    body = shot(page, "02-karaoke-stage")
    on_stage = "karaoke" in low(body)
    mark("G6 karaoke surface open", opened and on_stage)

    started = (click_text(page, "Start performance") or click_text(page, "Start setlist")
               or click_text(page, "Start singing") or click_text(page, "Now Singing")
               or click_text(page, "Start"))
    settle(page, 6)
    body = shot(page, "03-performing")
    performing = "now singing" in low(body)
    mark("G7 performance started", performing,
         ("Now Singing present" if performing else "no Now Singing banner")
         + f" (click helper returned {bool(started)})")
    return performing


def gate_before_change(page: Page) -> dict[str, str]:
    """Read every display in the song's own key, and build the Bb audio.

    The cue is read on the Practice page, which is where the app renders the
    phrasing guide. An earlier run read the karaoke stage, found no cue at all,
    and so asserted nothing about the very text the report was about.
    """
    shot(page, "04-before-key-change")
    pk = pk_val(page)
    mark("G8 performance starts in the song's own key", key_token(pk) == "bb",
         f"pk={pk!r}")

    cue = practice_cue(page)
    mark("G9 the Bb cue names Bb chords",
         bool(cue) and any(c in cue for c in ("B" + FLAT, "Bb")),
         f"cue={cue[:70]!r}" if cue else "no Intro cue found on the Practice page")

    # Build the audio for the key the performance is in, so the re-key has
    # something to replace and the follow strip has a timeline to follow.
    click_nav(page, "Backing")
    settle(page, 6)
    sheet = set_lead_sheet(page, True)
    log(f"  lead sheet open: {sheet}")
    before_rows = len(regen_rows())
    played = press_play(page)
    built = wait_for_synth(page, "Bb", before_rows) if played else ""
    mark("G9b the Bb backing is built before the change",
         key_token(built) == "bb", f"play={played} synth_done key={built!r}")
    settle(page, 4)
    follow = follow_chords(page)
    log(f"  before: pk={pk!r} cue={cue[:70]!r} follow={follow} audio={built!r}")
    return {"pk": pk, "cue": cue, "audio": built, **follow}


def gate_change_key(page: Page) -> bool:
    """The explicit gesture: move the sidebar Practice Key to D."""
    before_trace = len(trace_rows())
    ok = set_songs_practice_key(page, "D")
    settle(page, 8)
    click_nav(page, "Songs")
    settle(page, 5)
    pk = pk_val(page)
    body = shot(page, "05-after-key-change")
    mark("G10 sidebar moved to D", key_token(pk) == "d", f"pk={pk!r}")

    # The app says so: the performance moved, or could not.
    notice = ("performance moved" in low(body)
              or "could not move the performance" in low(body))
    mark("G11 the re-key is announced", notice,
         "notice present" if notice else "no notice text found")
    failed = "could not move the performance" in low(body)
    mark("G12 the re-key did not fail", not failed)
    after_trace = trace_rows()
    log(f"  trace rows: {before_trace} -> {len(after_trace)}")
    for row in after_trace[before_trace:]:
        log(f"    retune {row.get('stage')}: entry_key={row.get('entry_key')!r} "
            f"requested={row.get('requested') or row.get('to')!r} "
            f"session_active={row.get('session_active')}")
    mark("G12b the retune ran for this gesture",
         any(r.get("stage") == "retuned" for r in after_trace[before_trace:]),
         f"new trace rows={len(after_trace) - before_trace} "
         f"(helper returned {bool(ok)})")
    return key_token(pk) == "d" and not failed


def gate_after_change(page: Page, before: dict[str, str]) -> bool:
    """Every display, and the audio, in the new key - nothing left in the old."""
    click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
    settle(page, 6)
    shot(page, "06-performing-in-d")

    cue = practice_cue(page)
    shot(page, "06b-practice-cue-in-d")
    if cue:
        want = ["D", "G", "Bm", "A"]
        got = [c for c in chords_in(cue) if c not in ("Instrumental",)]
        mark("G13 the Intro cue reads D G Bm A", got[:4] == want,
             f"cue chords={got[:6]} cue={cue[:70]!r}")
        mark("G14 no B-flat or E-flat survives in the cue",
             not any(x in cue for x in ("B" + FLAT, "E" + FLAT, "Bb", "Eb")),
             f"cue={cue[:70]!r}")
        mark("G15 no double accidental in the cue",
             not DOUBLED.search(cue), f"cue={cue[:70]!r}")
    else:
        for gate in ("G13 the Intro cue reads D G Bm A",
                     "G14 no B-flat or E-flat survives in the cue",
                     "G15 no double accidental in the cue"):
            mark(gate, False, "no Intro cue found on the Practice page")

    # The audible key: ``sig`` is the synthesizer's own, so this is what was
    # actually built rather than what a label claims.
    click_nav(page, "Backing")
    settle(page, 6)
    set_lead_sheet(page, True)
    before_rows = len(regen_rows())
    played = press_play(page)
    built = wait_for_synth(page, "D", before_rows) if played else ""
    mark("G15b the backing is rebuilt in D", key_token(built) == "d",
         f"play={played} synth_done key={built!r} "
         f"rows={synth_keys(regen_rows()[before_rows:])}")

    body = shot(page, "06c-backing-in-d")
    follow = follow_chords(page)
    cur, nxt = follow.get("current", ""), follow.get("next", "")
    log(f"  after: cue={cue[:80]!r} follow={follow} audio={built!r}")
    if cur or nxt:
        stale = any(x in f"{cur} {nxt}"
                    for x in ("Csus4", "Bbsus4", "B" + FLAT, "E" + FLAT))
        mark("G16 Current/Next are not in the old key", not stale,
             f"current={cur!r} next={nxt!r}")
        mark("G17 Current/Next differ from before the change",
             (cur, nxt) != (before.get("current"), before.get("next")),
             f"{(before.get('current'), before.get('next'))} -> {(cur, nxt)}")
    else:
        mark("G16 Current/Next are not in the old key", False,
             "follow strip not present after Play")
        mark("G17 Current/Next differ from before the change", False,
             "follow strip not present after Play")

    rows = [r for r in trace_rows() if r.get("stage") == "retuned"]
    mark("G18 the entry itself moved to D",
         any(key_token(str(r.get("entry_key") or "")) == "d" for r in rows),
         f"retuned rows={[(r.get('previous'), r.get('to')) for r in rows]}")
    mark("G18b the page carries no old-key chord",
         not any(x in body for x in ("Bbsus4", "B" + FLAT + "sus4", "Csus4")),
         "no stale sus chord on the page")
    return True


def gate_transport_after_rekey(page: Page) -> bool:
    """Pause, resume and restart stay in the new key.

    A re-key retires the take that was playing. If Resume brought the old take
    back, the audio would be in Bb under a D chart - the reported defect with one
    extra step.
    """
    before_rows = len(regen_rows())
    paused = press_pause_or_resume(page)
    log(f"    pause clicked: {paused!r} chords={live_chords(page)}")
    resumed = press_pause_or_resume(page)
    log(f"    resume clicked: {resumed!r} chords={live_chords(page)}")
    replayed = press_play(page)
    log(f"    restart (Play again): {replayed}")
    settle(page, 8)
    pk = key_token(pk_val(page))
    keys = synth_keys(regen_rows()[before_rows:])
    stale = [k for k in keys if key_token(k.split(":", 1)[1]) == "bb"]
    mark("G18c pause / resume / restart stay in D", pk == "d", f"pk={pk}")
    mark("G18d no Bb take is rebuilt after the re-key", not stale,
         f"synths since the change={keys}")
    return pk == "d"


def gate_repeated_changes(page: Page) -> bool:
    """Several explicit changes in a row; the entry follows each one."""
    seen = []
    for token in ("E", "Bb", "D"):
        set_songs_practice_key(page, token)
        settle(page, 7)
        pk = key_token(pk_val(page))
        rows = [r for r in trace_rows() if r.get("stage") == "retuned"]
        entry = key_token(str(rows[-1].get("entry_key") or "")) if rows else ""
        seen.append((token, pk, entry))
        log(f"    repeated change -> {token}: sidebar={pk} entry={entry}")
    ok = all(key_token(tok) == pk == entry for tok, pk, entry in seen)
    mark("G18e repeated changes each move the performance", ok, f"{seen}")
    return ok


def gate_navigate_and_reload(page: Page) -> bool:
    click_nav(page, "Backing")
    settle(page, 5)
    on_backing = key_token(pk_val(page))
    click_nav(page, "Songs")
    settle(page, 5)
    back = key_token(pk_val(page))
    mark("G19 the key survives page navigation",
         on_backing == "d" and back == "d", f"backing={on_backing} songs={back}")

    page.reload(wait_until="domcontentloaded")
    settle(page, 10)
    wait_for_app(page)
    after = key_token(pk_val(page))
    shot(page, "07-after-reload")
    mark("G20 the key survives a reload", after == "d", f"pk={after}")
    return after == "d"


def gate_change_back(page: Page) -> bool:
    set_songs_practice_key(page, "Bb")
    settle(page, 8)
    click_nav(page, "Songs")
    settle(page, 5)
    pk = pk_val(page)
    body = shot(page, "08-back-in-bb")
    mark("G21 changing back returns to Bb", key_token(pk) == "bb", f"pk={pk!r}")
    cue = cue_line(page)
    if cue:
        mark("G22 the cue returns to the Bb chords",
             any(x in cue for x in ("B♭", "Bb")), f"cue={cue[:60]!r}")
    mark("G23 the song's original key never moved",
         "Original Key: Bb" in body or "Original Key: B♭" in body,
         "original key still Bb")
    return True


def gate_second_song(page: Page) -> bool:
    """Kiss Me: its own corrected grid, its own original key."""
    ok = pick_song(page, NOTES, "Kiss Me", "pop")
    settle(page, 5)
    body = shot(page, "09-kiss-me")
    mark("G24 Kiss Me active", bool(ok))
    mark("G25 Kiss Me keeps its own original key Eb",
         "Original Key: Eb" in body or "Original Key: E♭" in body,
         "original key Eb")
    set_songs_practice_key(page, "G")
    settle(page, 6)
    pk = pk_val(page)
    body = shot(page, "10-kiss-me-in-g")
    mark("G26 Kiss Me moves to G", key_token(pk) == "g", f"pk={pk!r}")
    mark("G27 Kiss Me's original key still Eb after the change",
         "Original Key: Eb" in body or "Original Key: E♭" in body)
    return True


def gate_mobile(page: Page, width: int) -> bool:
    page.set_viewport_size({"width": width, "height": 844})
    settle(page, 4)
    body = shot(page, f"11-mobile-{width}")
    scrolls = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
    mark(f"G28-{width} no horizontal scroll", not scrolls)
    mark(f"G29-{width} page renders", len(body.strip()) > 300)
    page.set_viewport_size({"width": 1400, "height": 900})
    settle(page, 3)
    return not scrolls


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(20000)
        try:
            if gate_setup(page):
                performing = gate_start_performance(page)
                before = gate_before_change(page)
                if gate_change_key(page):
                    gate_after_change(page, before)
                    gate_transport_after_rekey(page)
                    gate_navigate_and_reload(page)
                    gate_repeated_changes(page)
                    gate_change_back(page)
                gate_second_song(page)
                for width in (390, 360):
                    gate_mobile(page, width)
                log(f"  (performance started: {performing})")
        finally:
            shot(page, "99-final")
            browser.close()

    report = {
        "url": URL,
        "gates": GATES,
        "passed": sum(1 for v in GATES.values() if v),
        "failed": sorted(k for k, v in GATES.items() if not v),
        "notes": NOTES,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"\n{report['passed']}/{len(GATES)} gates passed")
    if report["failed"]:
        log("FAILED: " + ", ".join(report["failed"]))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
