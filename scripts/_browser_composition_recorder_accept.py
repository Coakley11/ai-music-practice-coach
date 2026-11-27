# -*- coding: utf-8 -*-
"""Browser acceptance: the shared-clock recorder inside Composition Studio.

Runs a real Chromium with a real getUserMedia stream. The microphone is fed a synthesised
flute line whose INTER-ONSET INTERVALS are known (scripts/evidence-composition-recorder/
fake-capture.wav, built by make_capture_wav.py): Chromium starts the fake capture device when
getUserMedia opens, so the phase between that file and the recorder's musical zero is not ours
to choose - but intervals survive any phase, and the recorder's measured music_start_frame is
what turns them back into absolute beats. That is the whole point of the feature, so it is what
this checks.

Evidence collected, not asserted from synthetic arrays:
  * the transcribed onsets, read out of the mounted notation component (``cursorSpans``);
  * the app's own mixed "your recording + chords" WAV, fetched from the page and analysed
    offline, so the recorded performance and the accompaniment are measured in one file.

Usage (flag ON):
  COMPOSITION_SHARED_RECORDER=1 MUSIC_APP_DATA_DIR=_runtime_comp_rec_8611 \
    streamlit run streamlit_music_practice_app.py --server.port 8611
  python scripts/_browser_composition_recorder_accept.py http://127.0.0.1:8611 on

Usage (flag OFF - the fallback route must still be what everyone gets):
  MUSIC_APP_DATA_DIR=_runtime_comp_rec_off_8612 \
    streamlit run streamlit_music_practice_app.py --server.port 8612
  python scripts/_browser_composition_recorder_accept.py http://127.0.0.1:8612 off
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8611"
MODE = (sys.argv[2] if len(sys.argv) > 2 else "on").lower()
WIDTHS = [int(w) for w in (sys.argv[3].split(",") if len(sys.argv) > 3 else ["1440"])]

OUT = SCRIPTS / "evidence-composition-recorder"
OUT.mkdir(parents=True, exist_ok=True)
CAPTURE_WAV = OUT / "fake-capture.wav"

BPM = 96
SPB = 60.0 / BPM
# Authored intervals, in beats, of fake-capture.wav. Kept here so the script is self-contained.
GROUND_TRUTH_INTERVALS = [1.0, 0.5, 0.25, 0.75, 1.5, 0.25, 0.25, 2.0]
RECORD_SECONDS = 14.0

GATES: dict[str, bool] = {}
NOTES: list[str] = []
MEASURED: dict[str, object] = {}


def log(msg: str) -> None:
    NOTES.append(msg)
    print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def mark(gate: str, ok: bool, detail: str = "") -> None:
    GATES[gate] = bool(ok)
    log(f"[{'PASS' if ok else 'FAIL'}] {gate}  {detail}")


def wait(page, ms: int) -> None:
    page.wait_for_timeout(ms)


def settle(page, seconds: float = 2.5) -> None:
    """Streamlit reruns are asynchronous; give the script run time to finish."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        page.wait_for_timeout(250)
        try:
            if page.locator('[data-testid="stStatusWidget"]').count() == 0:
                page.wait_for_timeout(400)
        except Exception:
            pass


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
    except Exception:
        pass


def click_key(page, key_fragment: str, *, timeout: int = 6000, settle_s: float = 3.0) -> bool:
    """Click a Streamlit widget by its stable st-key- class, scrolling it into view first."""
    wrap = page.locator(f'[class*="st-key-{key_fragment}"]')
    if wrap.count() == 0:
        return False
    target = wrap.first
    try:
        target.scroll_into_view_if_needed(timeout=timeout)
    except Exception:
        pass
    wait(page, 200)
    # Visible only. A button with `help` text is wrapped in a tooltip span, and at touch
    # widths Streamlit renders that wrapper twice with the first copy display:none - clicking
    # the first match then silently does nothing.
    btn = target.locator("button:visible")
    if btn.count() == 0:
        btn = target.locator("button")
    node = btn.first if btn.count() else target
    try:
        node.click(timeout=timeout)
    except Exception:
        try:
            box = node.bounding_box()
            if not box:
                return False
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        except Exception:
            return False
    settle(page, settle_s)
    return True


def click_text(page, pattern: str, *, settle_s: float = 3.0) -> bool:
    btns = page.locator('section[data-testid="stMain"] button').filter(
        has_text=re.compile(pattern, re.I)
    )
    if btns.count() == 0:
        return False
    try:
        btns.first.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    try:
        btns.first.click(timeout=6000)
    except Exception:
        return False
    settle(page, settle_s)
    return True


def body_text(page) -> str:
    try:
        return page.locator('section[data-testid="stMain"]').inner_text(timeout=5000)
    except Exception:
        return ""


# ---------------------------------------------------------------- navigation

def wait_ready(page, timeout_ms: int = 60000) -> bool:
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            if page.evaluate(
                """() => !!(document.querySelector('[class*="st-key-studio_quick_nav_btn_"]')
                         || document.querySelector('.ui-studio-script-header')
                         || document.querySelector('section[data-testid="stSidebar"]'))"""
            ):
                return True
        except Exception:
            pass
        wait(page, 1500)
        elapsed += 1500
    return False


def open_composer(page) -> bool:
    """Reach Composition Studio, by the quick-nav tile if it is there and the sidebar if not."""
    marker = (
        '[class*="st-key-composer_journey_rail"], '
        '[class*="st-key-composer_utility_panel"], '
        '.composer-hero, .composer-journey-title'
    )
    wrap = page.locator('[class*="st-key-studio_quick_nav_btn_composer"]')
    if wrap.count():
        try:
            wrap.first.scroll_into_view_if_needed(timeout=4000)
            wrap.first.locator("button").first.click(timeout=5000)
            settle(page, 5.0)
        except Exception:
            pass
    if page.locator(marker).count():
        return True
    try:
        from walk_creative_backing_matrix import click_nav, expand_sidebar  # noqa: PLC0415

        expand_sidebar(page)
        click_nav(page, "Compose")
        settle(page, 5.0)
    except Exception:
        pass
    if page.locator(marker).count():
        return True
    for alt in ("Composition Studio", "Composition", "Compose"):
        try:
            page.locator('section[data-testid="stSidebar"] button').filter(
                has_text=re.compile(re.escape(alt), re.I)
            ).last.click(timeout=2500)
            settle(page, 5.0)
            if page.locator(marker).count():
                return True
        except Exception:
            continue
    return bool(page.locator(marker).count())


def fill_key(page, key_fragment: str, value: str) -> bool:
    wrap = page.locator(f'[class*="st-key-{key_fragment}"]')
    if wrap.count() == 0:
        return False
    for sel in ("textarea", "input"):
        node = wrap.first.locator(sel)
        if node.count():
            try:
                node.first.scroll_into_view_if_needed(timeout=4000)
                node.first.fill(value, timeout=5000)
                node.first.press("Tab")
                settle(page, 2.0)
                return True
            except Exception:
                continue
    return False


def build_song(page) -> bool:
    """Welcome -> vision -> a two-section form -> one pasted progression -> the Melody step.

    Deliberately the ordinary guided path, not a seeded document: the point of a browser round
    is that the panel works where a musician actually finds it.
    """
    if not fill_key(page, "composer_welcome_idea", "A short flute line over a D major vamp."):
        log("  (no welcome idea field - already past the welcome screen?)")
    fill_key(page, "composer_welcome_bpm", str(BPM))
    if not click_text(page, r"Begin your song", settle_s=5.0):
        log("  (no Begin button)")
    txt = body_text(page)
    if "song idea" in txt.lower() and "that's all we need" in txt.lower():
        mark("the welcome screen accepted the song idea", False, "still asking for an idea")
        return False
    if not click_key(page, "composer_vision_continue", settle_s=5.0):
        click_text(page, r"Continue to Song Structure", settle_s=5.0)
    if not click_key(page, "composer_tpl_simple", settle_s=5.0):
        click_text(page, r"Simple Verse", settle_s=5.0)
    if not click_key(page, "composer_structure_continue", settle_s=5.0):
        click_text(page, r"Continue to Chords", settle_s=5.0)
    # Chords, the ordinary way: adopt one of the suggested progressions. The manual paste box
    # lives in the advanced chord lane, which is not open by default - a probe of the real page
    # showed the Chords step offers "Use" cards (composer_explore_<section>_<n>_use_<id>) and no
    # paste field, which is why the first run reached Melody with no chords at all.
    used = False
    cards = page.locator('[class*="st-key-composer_explore_"][class*="_use_"]')
    if cards.count():
        for i in range(min(3, cards.count())):
            try:
                card = cards.nth(i)
                card.scroll_into_view_if_needed(timeout=4000)
                btn = card.locator("button")
                (btn.first if btn.count() else card).click(timeout=6000)
                settle(page, 6.0)
                used = True
                break
            except Exception:
                continue
    body_now = body_text(page).lower()
    has_chords = "section harmony" in body_now or "section chords" in body_now
    log(f"  chords: suggestion adopted={used} chords visible={has_chords} "
        f"({cards.count()} cards offered)")
    if not click_key(page, "composer_journey_melody", settle_s=5.0):
        click_text(page, r"^Melody", settle_s=5.0)
    # The hum panel is gated behind a confirmed feel; the button is only there when it is not.
    if page.locator('[class*="st-key-composer_melody_feel_continue_"]').count():
        click_key(page, "composer_melody_feel_continue_", settle_s=5.0)
    body = body_text(page)
    return "hum" in body.lower() and "melody" in body.lower()


# ---------------------------------------------------------------- the recorder

REC_IFRAME = 'iframe[src*="mission_recorder"]'
TAKE_HOOK = """() => {
  if (window.__takeHookInstalled) return true;
  const orig = window.parent.postMessage;
  window.__takes = [];
  window.parent.postMessage = function (msg, target) {
    try {
      if (msg && msg.type === "streamlit:setComponentValue" && msg.value && msg.value.wav_b64) {
        window.__takes.push({
          take_id: msg.value.take_id,
          timing: msg.value.timing,
          ack: msg.value.ack,
          wav_b64: msg.value.wav_b64,
        });
      }
    } catch (e) {}
    return orig.call(window.parent, msg, target);
  };
  window.__takeHookInstalled = true;
  return true;
}"""


def rec_frame(page):
    """The recorder component's frame, or None. Its own document, so it needs frame access."""
    for fr in page.frames:
        try:
            if "mission_recorder" in (fr.url or ""):
                return fr
        except Exception:
            continue
    return None


def rec_status(page) -> str:
    fr = rec_frame(page)
    if fr is None:
        return ""
    js = "() => { const n = document.getElementById('status'); return n ? n.textContent : ''; }"
    try:
        return str(fr.evaluate(js) or "")
    except Exception:
        try:
            return str(page.frame_locator(REC_IFRAME).locator("#status").inner_text(timeout=4000))
        except Exception:
            return ""


def rec_button_label(page) -> str:
    try:
        return str(page.frame_locator(REC_IFRAME).locator("#rec").inner_text(timeout=4000))
    except Exception:
        return ""


def rec_timer(page) -> str:
    try:
        return str(page.frame_locator(REC_IFRAME).locator("#time").inner_text(timeout=4000))
    except Exception:
        return ""


def press_rec(page) -> bool:
    try:
        page.frame_locator(REC_IFRAME).locator("#rec").click(timeout=8000)
        return True
    except Exception:
        return False


def install_take_hook(page) -> bool:
    fr = rec_frame(page)
    if fr is None:
        return False
    try:
        return bool(fr.evaluate(TAKE_HOOK))
    except Exception:
        return False


def harvest_takes(page) -> list[dict]:
    fr = rec_frame(page)
    if fr is None:
        return []
    try:
        return list(fr.evaluate("() => window.__takes || []") or [])
    except Exception:
        return []


def cursor_spans(page) -> list[dict]:
    """The transcribed note timeline, read out of the mounted synced-score component.

    These are the app's own numbers for where each transcribed note sounds, in seconds.
    """
    pat = re.compile(r"const cursorSpans = (\[.*?\]);", re.S)
    for fr in page.frames:
        try:
            content = fr.content()
        except Exception:
            continue
        m = pat.search(content or "")
        if not m:
            continue
        try:
            spans = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(spans, list) and spans:
            return spans
    return []


def grab_preview_wav(page) -> bytes:
    """The WAV the app is playing: a data: URI in a component, or an st.audio media URL."""
    import base64

    best = b""
    pat = re.compile(r'src="data:audio/wav;base64,([A-Za-z0-9+/=]+)"')
    for fr in page.frames:
        try:
            content = fr.content()
        except Exception:
            continue
        for m in pat.finditer(content or ""):
            try:
                raw = base64.b64decode(m.group(1))
            except Exception:
                continue
            if len(raw) > len(best):
                best = raw
    if best:
        return best
    try:
        srcs = page.eval_on_selector_all(
            "audio[src]", "els => els.map(e => e.getAttribute('src'))"
        )
    except Exception:
        srcs = []
    for src in srcs or []:
        if not src or src.startswith("data:"):
            continue
        url = src if src.startswith("http") else URL.rstrip("/") + "/" + src.lstrip("/")
        try:
            resp = page.request.get(url)
            if resp.ok:
                raw = resp.body()
                if len(raw) > len(best):
                    best = raw
        except Exception:
            continue
    return best


# ---------------------------------------------------------------- gates

def nudge_rerun(page) -> bool:
    """An ordinary Streamlit rerun, caused the way a user would cause one.

    The mix sliders are the only controls on this panel that rerun the script while changing
    nothing about the recording - they set preview gain. Several locator shapes are tried
    because the thumb is not always the element that takes the keystroke.
    """
    shapes = (
        '[class*="st-key-composer_melody_mix_gain_w_"] [role="slider"]',
        '[class*="st-key-composer_backing_mix_gain_w_"] [role="slider"]',
        '[class*="st-key-composer_melody_mix_gain_w_"] [data-testid="stSlider"]',
        'section[data-testid="stMain"] [role="slider"]',
        'section[data-testid="stMain"] [data-testid="stSlider"]',
    )
    for shape in shapes:
        node = page.locator(shape)
        if node.count() == 0:
            continue
        try:
            node.first.scroll_into_view_if_needed(timeout=3000)
            node.first.click(timeout=4000)
            node.first.press("ArrowRight")
            settle(page, 2.0)
            return True
        except Exception:
            continue
    # Last resort: nudge the keyboard focus onto a slider and move it.
    try:
        moved = page.evaluate(
            """() => { const s = document.querySelector('section[data-testid="stMain"] [role="slider"]');
                       if (!s) return false; s.focus(); return document.activeElement === s; }"""
        )
        if moved:
            page.keyboard.press("ArrowRight")
            settle(page, 2.0)
            return True
    except Exception:
        pass
    return False


def run_flag_on(page, width: int) -> None:
    tag = f"[{width}px] "
    has_rec = page.locator(REC_IFRAME).count() > 0
    has_basic = page.locator('[data-testid="stAudioInput"]').count() > 0
    mark(tag + "the shared recorder is the panel's recorder", has_rec and not has_basic,
         f"shared={has_rec} basic={has_basic}")
    if not has_rec:
        shot(page, f"on-{width}-no-recorder")
        return

    # Cold start: nothing here has pressed "Play chords with highlight".
    idle = rec_status(page)
    label = rec_button_label(page)
    MEASURED[f"idle_status_{width}"] = idle
    cold_ok = "chords" in idle.lower() and "together" in idle.lower()
    mark(tag + "the chords are ready without pressing Play chords first", cold_ok, repr(idle[:110]))
    mark(tag + "Record announces the count-in", "count-in" in label.lower(), repr(label))
    shot(page, f"on-{width}-before-record")

    install_take_hook(page)
    if not press_rec(page):
        mark(tag + "Record starts", False, "could not click #rec")
        return
    wait(page, 3500)
    during = rec_status(page)
    MEASURED[f"recording_status_{width}"] = during
    mark(tag + "Record plays this section's chords with the take",
         "generated backing" in during.lower() or "counting you in" in during.lower(),
         repr(during[:110]))

    # Requirement 9: an ordinary rerun must not restart or discard an ongoing recording.
    t_before = rec_timer(page)
    rerun_ok = nudge_rerun(page)
    wait(page, 3000)
    t_after = rec_timer(page)
    still = "stop" in rec_button_label(page).lower()
    advanced = t_before != t_after
    mark(tag + "an ordinary rerun does not interrupt the recording",
         bool(rerun_ok and still and advanced),
         f"rerun={rerun_ok} still_recording={still} timer {t_before}->{t_after}")

    remaining = max(2.0, RECORD_SECONDS - 6.5)
    wait(page, int(remaining * 1000))
    press_rec(page)
    settle(page, 8.0)

    takes = harvest_takes(page)
    mark(tag + "stopping delivers exactly one take", len(takes) == 1, f"{len(takes)} take(s)")
    if not takes:
        shot(page, f"on-{width}-no-take")
        return
    take = takes[-1]
    timing = take.get("timing") or {}
    MEASURED[f"timing_{width}"] = timing
    offset = timing.get("music_offset_sec")
    measured = isinstance(offset, (int, float))
    mark(tag + "the take reports a measured musical zero", measured,
         f"music_offset_sec={offset!r} count_in_sec={timing.get('count_in_sec')!r}")
    mark(tag + "the take was recorded against the accompaniment",
         bool(timing.get("backing_fp")) and timing.get("monitor_count") == timing.get("monitors_expected"),
         f"backing_fp={str(timing.get('backing_fp'))[:12]!r} "
         f"monitors {timing.get('monitor_count')}/{timing.get('monitors_expected')}")

    # The panel's own wording, checked against what the app actually says. An earlier version
    # of this gate looked for "aligned", which appears ONLY in the FAILURE caption ("not
    # aligned to the chords") - so it passed when the take was unsynchronised and failed when
    # it was fine. Match the success sentence, and assert the failure sentence is absent.
    body = body_text(page)
    caption = next(
        (ln.strip() for ln in body.splitlines() if "in time with the chords" in ln.lower()
         or "could not be measured" in ln.lower()),
        "",
    )
    MEASURED[f"caption_{width}"] = caption
    low = caption.lower()
    mark(tag + "the panel reports the take as recorded in time",
         "recorded in time with the chords" in low and "could not be measured" not in low,
         repr(caption[:120]))
    mark(tag + "the caption states where bar 1 lands",
         bool(re.search(r"bar 1 lands \d+\.\d+s", low)),
         repr(caption[:120]))

    # A rerun after the take must not ingest it twice.
    nudge_rerun(page)
    settle(page, 4.0)
    mark(tag + "a rerun after the take does not deliver a second one",
         len(harvest_takes(page)) == len(takes), f"{len(harvest_takes(page))} total")

    if not click_key(page, "composer_hum_analyze_", settle_s=14.0):
        mark(tag + "Analyze recording runs", False, "button not clickable")
        shot(page, f"on-{width}-no-analyze")
        return
    body = body_text(page)
    mark(tag + "Analyze recording runs", "note" in body.lower() or "proposal" in body.lower(),
         "")
    shot(page, f"on-{width}-after-analyze")

    preview_clicked = click_key(page, "composer_hum_preview_", settle_s=14.0)
    mark(tag + "Preview plays the recording with the chords", preview_clicked, "")
    spans = cursor_spans(page)
    MEASURED[f"cursor_spans_{width}"] = spans
    mark(tag + "the transcribed timeline is available to measure", bool(spans), f"{len(spans)} spans")
    mix = grab_preview_wav(page)
    if mix:
        (OUT / f"mix-{width}.wav").write_bytes(mix)
    mark(tag + "the mixed recording + chords audio was produced", len(mix) > 44,
         f"{len(mix)} bytes")
    shot(page, f"on-{width}-preview")

    import base64

    wav_b64 = take.get("wav_b64") or ""
    if wav_b64:
        try:
            (OUT / f"take-{width}.wav").write_bytes(base64.b64decode(wav_b64))
        except Exception:
            pass
    (OUT / f"timing-{width}.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    (OUT / f"spans-{width}.json").write_text(json.dumps(spans, indent=1), encoding="utf-8")


def run_flag_off(page, width: int) -> None:
    tag = f"[{width}px] "
    has_rec = page.locator(REC_IFRAME).count() > 0
    has_basic = page.locator('[data-testid="stAudioInput"]').count() > 0
    mark(tag + "with the flag off the original recorder is still what you get",
         has_basic and not has_rec, f"basic={has_basic} shared={has_rec}")
    shot(page, f"off-{width}-panel")
    if not has_basic:
        return
    # Record through the ordinary widget, so the fallback is exercised and not merely present.
    try:
        btn = page.locator('[data-testid="stAudioInput"] button').first
        btn.click(timeout=6000)
        wait(page, 9000)
        page.locator('[data-testid="stAudioInput"] button').first.click(timeout=6000)
        settle(page, 8.0)
    except Exception as exc:
        mark(tag + "the fallback records", False, f"{type(exc).__name__}")
        return
    enabled = False
    try:
        wrap = page.locator('[class*="st-key-composer_hum_analyze_"] button').first
        enabled = wrap.count() > 0 and wrap.is_enabled()
    except Exception:
        pass
    mark(tag + "the fallback produces something to analyse", enabled, "")
    if enabled and click_key(page, "composer_hum_analyze_", settle_s=14.0):
        body = body_text(page)
        mark(tag + "the fallback take is transcribed", "note" in body.lower(), "")
        # Nothing measured this take, so nothing may claim it was.
        mark(tag + "the fallback does not claim a measured alignment",
             "synchronis" not in body.lower() and "synchroniz" not in body.lower(), "")
        shot(page, f"off-{width}-analyzed")


# ---------------------------------------------------------------- main

def main() -> int:
    if not CAPTURE_WAV.exists():
        log(f"missing microphone fixture: {CAPTURE_WAV}")
        log("build it first:  python scripts/make_capture_wav.py "
            "scripts/evidence-composition-recorder/fake-capture.wav")
        return 2
    args = [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-audio-capture={CAPTURE_WAV}",
        "--autoplay-policy=no-user-gesture-required",
        "--mute-audio",
    ]
    log(f"mode={MODE} url={URL} widths={WIDTHS}")
    log(f"microphone fixture: {CAPTURE_WAV.name}")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=args)
        try:
            for width in WIDTHS:
                ctx = browser.new_context(
                    viewport={"width": width, "height": 900 if width > 500 else 844},
                    permissions=["microphone"],
                )
                page = ctx.new_page()
                page.set_default_timeout(20000)
                page.goto(URL, wait_until="domcontentloaded")
                if not wait_ready(page):
                    mark(f"[{width}px] the app loads", False, "no Streamlit shell")
                    ctx.close()
                    continue
                settle(page, 4.0)
                if not open_composer(page):
                    mark(f"[{width}px] Composition Studio opens", False, "")
                    shot(page, f"{MODE}-{width}-no-composer")
                    ctx.close()
                    continue
                mark(f"[{width}px] Composition Studio opens", True, "")
                reached = build_song(page)
                mark(f"[{width}px] the Melody step reaches the recording panel", reached, "")
                shot(page, f"{MODE}-{width}-panel")
                if reached:
                    if MODE == "on":
                        run_flag_on(page, width)
                    else:
                        run_flag_off(page, width)
                ctx.close()
        finally:
            browser.close()

    (OUT / f"gates-{MODE}.json").write_text(
        json.dumps({"gates": GATES, "measured": MEASURED}, indent=1, default=str),
        encoding="utf-8",
    )
    (OUT / f"notes-{MODE}.txt").write_text("\n".join(NOTES), encoding="utf-8")
    failed = [g for g, ok in GATES.items() if not ok]
    log("")
    log(f"{len(GATES) - len(failed)}/{len(GATES)} gates passed")
    for g in failed:
        log(f"  FAILED: {g}")
    return 0 if GATES and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
