"""Slice 2: does the backing actually SOUND, and actually sound in the key it claims?

A label is not a sound. The saved-key hotfix could only show "Say - Ab - 82 BPM" on the card,
which proves what the app believes, not what came out of the speakers. With the Slice 2 mount
correction the surface owns a real player with the Lead Sheet OFF, so this measures the audio:

  A1-A6   a take mounts, sounds, is unmuted and advances - exactly one element sounding
  A7-A9   the rendered WAV is fetched from the server and analysed. The take at the entry's Bb
          and the take after a retune to Ab are compared by CHROMA: the best rotation that
          aligns their pitch-class content is the transposition that really happened. Bb -> Ab
          is two semitones down, so the measured shift must be -2 (10 mod 12) - and the same
          method rules out "nothing changed" (shift 0), which is what a label-only change looks
          like.
  A10-A15 Pause silences, Resume continues from the same position, Stop stops, Lead Sheet On and
          Off both sound, and at no point do two elements sound at once.

Chromium runs with the autoplay policy relaxed, because the shared nudge MUTES the element to
defeat autoplay blocking and a muted take cannot answer any of these questions.

Usage:  python -X utf8 scripts/_accept_slice2_audio.py http://127.0.0.1:8650
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

URL = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://127.0.0.1:8650"

from _accept_issue69_karaoke_transposition import (  # noqa: E402
    click_key,
    click_text,
    key_token,
    low,
    press_play,
    set_lead_sheet,
    settle,
    wait_for_app,
)
from _accept_karaoke_qa import card_identity, set_pk_token  # noqa: E402
from _accept_karaoke_slice2 import AUDIO_CENSUS, surface_frame  # noqa: E402
from _accept_karaoke_slice2b import SURFACE_AUDIO, wait_for_take  # noqa: E402
from _accept_karaoke_stop_transport import IFRAME_CLICK, TRANSPORT  # noqa: E402
from walk_creative_backing_matrix import click_nav, expand_sidebar, set_baseweb_select  # noqa: E402
from walk_guitar_shape_key import pick_song  # noqa: E402

OUT = SCRIPTS / "evidence-slice2-audio"
OUT.mkdir(parents=True, exist_ok=True)
GATES: dict[str, bool] = {}
OBSERVED: list[str] = []
TRACE: list[dict] = []

#: The full source URL of the element that is actually sounding, not a truncated tail.
SOUNDING_SRC = """
() => {
  const rows = [];
  const look = (doc, where) => {
    if (!doc) return;
    for (const a of doc.querySelectorAll('audio')) {
      if (a.paused || a.ended || Number(a.readyState) < 2) continue;
      rows.push({where: where, src: String(a.currentSrc || a.src || ''),
                 muted: !!a.muted, volume: Number(a.volume),
                 t: Number((a.currentTime || 0).toFixed(2))});
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


def census(page: Page) -> list[dict]:
    try:
        return page.evaluate(AUDIO_CENSUS) or []
    except Exception:
        return []


def sounding(page: Page) -> list[dict]:
    rows = census(page)
    return [r for r in rows
            if not r.get("paused") and not r.get("ended") and int(r.get("readyState") or 0) >= 2]


def snapshot(page: Page, label: str) -> dict:
    rows = census(page)
    snd = [r for r in rows
           if not r.get("paused") and not r.get("ended") and int(r.get("readyState") or 0) >= 2]
    loud = [r for r in rows if r.get("audible")]
    shot = {"label": label, "elements": len(rows), "sounding": len(snd), "audible": len(loud),
            "positions": [r.get("t") for r in rows], "muted": [r.get("muted") for r in rows]}
    TRACE.append(shot)
    log(f"    {label}: {len(rows)} element(s), {len(snd)} sounding, {len(loud)} audible, "
        f"t={shot['positions']}")
    return shot


def fetch_take(page: Page, label: str) -> tuple[Path | None, str]:
    """Save the WAV the browser is actually playing, straight from the server."""
    try:
        rows = page.evaluate(SOUNDING_SRC) or []
    except Exception as exc:
        observe(f"could not read the sounding source ({label}): {exc}")
        return None, ""
    rows = [r for r in rows if r.get("src")]
    if not rows:
        observe(f"nothing was sounding when {label} was to be captured")
        return None, ""
    src = str(rows[0]["src"])
    try:
        resp = page.request.get(src)
        body = resp.body()
    except Exception as exc:
        observe(f"could not fetch {label} from {src[-50:]}: {exc}")
        return None, src
    path = OUT / f"take-{label}.wav"
    path.write_bytes(body)
    log(f"    captured {label}: {len(body)} bytes from ...{src[-46:]}")
    return path, src


def chroma_of(path: Path) -> np.ndarray | None:
    """Pitch-class profile of a render, for comparing one take against another.

    MEDIAN over frames, not mean. Checked against renders of the same four bars in Bb and in Ab
    before this was relied on: both recover the right answer, but the mean leaves a margin of
    0.014 over the runner-up where the median leaves 0.092 - and chroma_cens picked the WRONG
    rotation outright. A measurement that is only just right is not evidence.
    """
    try:
        import librosa

        y, sr = librosa.load(str(path), sr=22050, mono=True)
        if y.size < sr:
            observe(f"{path.name} is shorter than a second ({y.size} samples)")
            return None
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        vec = np.median(np.asarray(chroma), axis=1)
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else None
    except Exception as exc:
        observe(f"chroma failed for {path.name}: {exc}")
        return None


#: How far the winning rotation must beat the runner-up before it counts as a measurement.
#: Validated offline at 0.092 for a real Bb -> Ab pair of full-mix renders.
MIN_MARGIN = 0.02


def best_shift(a: np.ndarray, b: np.ndarray) -> tuple[int, float, list[float]]:
    """The rotation of ``a`` that best matches ``b`` - the transposition that really happened."""
    scores = [float(np.dot(np.roll(a, k), b)) for k in range(12)]
    order = sorted(scores, reverse=True)
    margin = float(order[0] - order[1]) if len(order) > 1 else 0.0
    return int(np.argmax(scores)), round(margin, 4), [round(s, 4) for s in scores]


def _live(page: Page, frame: Frame | None) -> Frame | None:
    """A frame handle that is still attached.

    A retune retires the take and re-renders the component, so the handle held across it is
    detached and every evaluate against it returns nothing - measured as "playback never
    settled: last state {}" immediately after a retune that had in fact worked.
    """
    fresh = surface_frame(page)
    return fresh or frame


def start_take(page: Page, frame: Frame, tries: int = 3, secs: float = 40.0) -> dict:
    """Get the surface's take running without ever pausing it by accident.

    ``#live-stop-btn`` is a TOGGLE. A retry loop that clicks on entry, from a read taken before
    the previous click had settled, starts the take and then stops it again - measured as a take
    that had reached t=4.28 and was paused at the snapshot. So the state is re-read immediately
    before every click, and a take that is already running is never clicked.
    """
    state: dict = {}
    for _ in range(max(1, tries)):
        frame = _live(page, frame) or frame
        try:
            state = frame.evaluate(SURFACE_AUDIO) or {}
        except Exception:
            state = {}
        if state.get("paused") is False:
            return state
        if str((state.get("button") or {}).get("state") or "") == "resume":
            try:
                frame.locator("#live-stop-btn").click(timeout=10000)
            except Exception as exc:
                observe(f"the surface's play control refused a click: {exc}")
        waited = 0.0
        while waited < secs:
            frame = _live(page, frame) or frame
            try:
                state = frame.evaluate(SURFACE_AUDIO) or {}
            except Exception:
                state = {}
            if state.get("paused") is False:
                return state
            page.wait_for_timeout(1000)
            waited += 1.0
    return state


def wait_until_stably_playing(page: Page, frame: Frame, needed: int = 3,
                              secs: float = 90.0) -> dict:
    """Wait for playback that is actually running, not for one lucky instant.

    Measured second by second (scripts/_probe_take_continuity.py): a karaoke take plays from 0
    to about 4.2s, pauses for roughly four seconds, then resumes and runs continuously - one
    source throughout, so nothing is being regenerated. A snapshot taken inside that early
    window reports "nothing is sounding" about a player that is working. So this requires
    ``needed`` consecutive seconds of unpaused, advancing playback before anything is measured.
    """
    runs, last_t, state = 0, -1.0, {}
    waited = 0.0
    while waited < secs:
        frame = _live(page, frame) or frame
        try:
            state = frame.evaluate(SURFACE_AUDIO) or {}
        except Exception:
            state = {}
        now = float(state.get("t") or 0)
        if state.get("paused") is False and now > last_t:
            runs += 1
            if runs >= needed:
                return state
        else:
            runs = 0
        last_t = now
        page.wait_for_timeout(1000)
        waited += 1.0
    observe(f"playback never settled: last state {json.dumps(state)[:160]}")
    return state


def wait_for_new_take(page: Page, previous_src: str, secs: float = 300.0) -> tuple[Frame | None, dict]:
    """After a retune the surface is GONE while the new key is rendered. Wait for it to return.

    The entry take is a 37 MB WAV - about three and a half minutes of audio - so a retune is not
    a relabel: it retires that take and renders another one, and for as long as that takes there
    is no surface frame to ask anything of. Polling the old handle returns nothing, which reads
    exactly like "playback failed" and is not.

    Returns the live frame and its state once a take is mounted whose source is NOT the one that
    was playing before.
    """
    waited = 0.0
    tail = str(previous_src or "")[-40:]
    while waited < secs:
        frame = surface_frame(page)
        if frame is not None:
            try:
                state = frame.evaluate(SURFACE_AUDIO) or {}
            except Exception:
                state = {}
            src = str(state.get("src") or "")
            if state.get("has_audio") and src and int(state.get("ready") or 0) >= 2                     and not (tail and tail.endswith(src[-40:])):
                log(f"    a new take appeared after {waited:.0f}s: ...{src[-34:]}")
                return frame, state
        page.wait_for_timeout(3000)
        waited += 3.0
    observe(f"no new take within {secs:.0f}s of the retune")
    return surface_frame(page), {}


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
            mark("A1 app renders", wait_for_app(page, 300))

            pick_song(page, OBSERVED, "Say", "pop")
            settle(page, 4)
            expand_sidebar(page)
            set_baseweb_select(page, "Instrument", "Voice")
            settle(page, 6)
            click_nav(page, "Songs")
            settle(page, 3)
            click_key(page, "karaoke_add_card_") or click_text(page, "Add to Karaoke Set")
            click_key(page, "catalog_hub_karaoke") or click_text(page, "Karaoke")
            settle(page, 4)
            click_text(page, "Start karaoke set") or click_text(page, "Start")
            settle(page, 8)
            mark("A2 a karaoke set is performing",
                 "now singing" in low(page.inner_text("body") or ""))

            click_nav(page, "Backing")
            settle(page, 6)
            body = page.inner_text("body") or ""
            mark("A3 the Lead Sheet is Off", "lead sheet: off" in low(body))

            played = press_play(page)
            frame: Frame | None = None
            for _ in range(60):
                frame = surface_frame(page)
                if frame:
                    break
                settle(page, 3)
            mark("A4 the performance surface mounts with the Lead Sheet OFF",
                 frame is not None, f"play={bool(played)}")
            if frame is None:
                observe("no surface - the mount correction did not take, nothing to hear")
                return 2

            # The take has to EXIST before anything can start it: ensure_playing presses the
            # surface's button only when that button is already offering "Resume", so calling it
            # against a take that is still rendering clicks nothing and then waits for a paused
            # element forever. This is the sequence the 17/17 run used.
            mounted = wait_for_take(page, frame, 180)
            log(f"    take as mounted: {json.dumps(mounted)}")
            take = start_take(page, frame)
            log(f"    take once started: {json.dumps(take)}")
            take = wait_until_stably_playing(page, surface_frame(page) or frame)
            log(f"    playing steadily: {json.dumps(take)}")
            first = snapshot(page, "entry key, playing")
            mark("A5 a take is really sounding with the Lead Sheet OFF",
                 first["sounding"] == 1, f"{first['sounding']} sounding of {first['elements']}")
            mark("A6 that take is audible - unmuted, with volume",
                 first["audible"] == 1, f"muted={first['muted']}")

            entry_wav, entry_src = fetch_take(page, "entry-bb")
            ident = card_identity(page)
            entry_label = key_token(ident.get("backing_key") or "")
            log(f"    card says: {ident.get('backing_line')!r}")

            # ---- the retune, and what it does to the SOUND ----------------------------
            retuned = set_pk_token(page, "Ab")
            settle(page, 10)
            # A retune deliberately stops the old take: "Old-key audio must not keep playing
            # under new-key chord names ... Resume has to start the new key from its first
            # chord" (_karaoke_retune_after_explicit_key_change). So the new key needs a Play,
            # exactly as the musician would press it - waiting passively for a take that only a
            # Play produces measured nothing for five minutes.
            replayed = press_play(page)
            log(f"    pressed Play again after the retune: {bool(replayed)}")
            frame, fresh = wait_for_new_take(page, entry_src, 300.0)
            if frame is not None:
                start_take(page, frame)
                wait_until_stably_playing(page, frame)
            second = snapshot(page, "retuned, playing")
            ident2 = card_identity(page)
            live_label = key_token(ident2.get("backing_key") or "")
            mark("A7 the card reports the temporary key", live_label == "ab",
                 f"{ident2.get('backing_line')!r} (setter {bool(retuned)})")
            mark("A8 a take is still sounding after the retune",
                 second["sounding"] == 1, f"{second['sounding']} sounding")
            retuned_wav, retuned_src = fetch_take(page, "retuned-ab")

            mark("A9 the retune rendered a DIFFERENT take, not the same file relabelled",
                 bool(entry_src) and bool(retuned_src) and entry_src != retuned_src,
                 f"...{entry_src[-28:]} -> ...{retuned_src[-28:]}")

            shift, margin, scores = -1, 0.0, []
            if entry_wav and retuned_wav:
                a, b = chroma_of(entry_wav), chroma_of(retuned_wav)
                if a is not None and b is not None:
                    shift, margin, scores = best_shift(a, b)
                    log(f"    chroma match by rotation: {scores}")
                    log(f"    best rotation: {shift} semitone(s), margin {margin}")
            # Bb -> Ab is two semitones DOWN. Rotating the Bb take's pitch classes by 10
            # (equivalently down by 2) is what lines it up with the Ab take - confirmed against
            # synthetic one-hots and against real renders before this was relied on.
            mark("A10 the AUDIO really moved down two semitones, Bb -> Ab",
                 shift == 10 and margin >= MIN_MARGIN,
                 f"best rotation {shift} margin {margin} (expected 10, margin >= {MIN_MARGIN}); "
                 f"rotation 0 would mean the sound never changed, and a margin under "
                 f"{MIN_MARGIN} would mean this measured nothing")

            # ---- the transport, on the surface's own control ---------------------------
            frame = _live(page, frame) or frame
            try:
                frame.locator("#live-stop-btn").click(timeout=15000)
            except Exception as exc:
                observe(f"the surface's Pause refused a click: {exc}")
            settle(page, 4)
            paused = snapshot(page, "after Pause")
            mark("A11 Pause silences the take", paused["sounding"] == 0,
                 f"{paused['sounding']} sounding")
            was = float((frame.evaluate(SURFACE_AUDIO) or {}).get("t") or 0)
            start_take(page, surface_frame(page) or frame, tries=2)
            wait_until_stably_playing(page, surface_frame(page) or frame, needed=2)
            resumed = snapshot(page, "after Resume")
            now = float((surface_frame(page) or frame).evaluate(SURFACE_AUDIO).get("t") or 0)
            mark("A12 Resume sounds one player again, from where it stopped",
                 resumed["sounding"] == 1 and now >= was - 0.5,
                 f"{resumed['sounding']} sounding, position {was} -> {now}")

            # ---- the Lead Sheet switch, with sound ------------------------------------
            set_lead_sheet(page, True)
            settle(page, 8)
            frame = surface_frame(page) or frame
            wait_for_take(page, frame, 120)
            start_take(page, surface_frame(page) or frame)
            wait_until_stably_playing(page, surface_frame(page) or frame)
            on = snapshot(page, "Lead Sheet ON, playing")
            mark("A13 with the Lead Sheet ON exactly one player sounds",
                 on["sounding"] == 1, f"{on['sounding']} sounding of {on['elements']}")
            set_lead_sheet(page, False)
            settle(page, 8)
            frame = surface_frame(page) or frame
            wait_for_take(page, frame, 120)
            start_take(page, surface_frame(page) or frame)
            wait_until_stably_playing(page, surface_frame(page) or frame)
            off = snapshot(page, "Lead Sheet OFF again, playing")
            mark("A14 with the Lead Sheet OFF again exactly one player sounds",
                 off["sounding"] == 1, f"{off['sounding']} sounding of {off['elements']}")

            worst = max((s["sounding"] for s in TRACE), default=0)
            mark("A15 two players never sounded at once - no doubled backing, no echo",
                 worst <= 1,
                 f"most sounding at once: {worst} (elements seen: {[s['elements'] for s in TRACE]})")

            # ---- Stop, on the card's own control --------------------------------------
            stopped = bool(page.evaluate(IFRAME_CLICK, "#stop"))
            if not stopped:
                stopped = bool(page.evaluate(IFRAME_CLICK, "#btn"))
            settle(page, 7)
            after_stop = snapshot(page, "after Stop")
            mark("A16 Stop really stops the player", stopped and after_stop["sounding"] == 0,
                 f"clicked={stopped} sounding={after_stop['sounding']}")

            report = {"entry_src": entry_src, "retuned_src": retuned_src,
                      "entry_label": entry_label, "live_label": live_label,
                      "chroma_rotation": shift, "chroma_scores": scores, "trace": TRACE}
            (OUT / "audio-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
    (OUT / "audio-gates.json").write_text(
        json.dumps({"gates": GATES, "observed": OBSERVED}, indent=2), encoding="utf-8")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
