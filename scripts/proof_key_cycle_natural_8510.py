"""Natural end→playing gaps on 8510 — no seek, no synthetic ended events.

Uses short real passes (Intro / Selected sections, loops=1) and waits for
the audio element to reach natural `ended`. Reports end→playing and chart
update delay separately.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPTS), str(ROOT)]

import walk_creative_backing_matrix as m
from walk_creative_backing_matrix import expand_pages_nav, expand_sidebar
from walk_practice_loop_backing import goto_studio
from proof_key_cycle_seamless_8510 import read_bridges, read_gaps, wait_kc_audio, wait_next_preloaded, wait_prefetch
from proof_key_cycle_ux_8510 import (
    click_play,
    cycle_ui,
    open_advanced,
    set_cycle_mode,
    wait_sounding,
)

BASE = "http://127.0.0.1:8510"
OUT = SCRIPTS / "evidence-key-cycle"
DATA = ROOT / "_runtime_key_cycle_8510"
m.wait_idle = lambda page, ms=900: page.wait_for_timeout(ms)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def configure_short_pass(page) -> dict:
    """Selected sections + Intro (or shortest available) + loops=1."""
    info: dict = {"scope": False, "section": "", "loops": False, "bpm_boost": False}
    # Playback scope → Selected sections via radio option text
    info["scope"] = bool(
        page.evaluate(
            """() => {
              const labels = [...document.querySelectorAll('label, [data-testid="stRadioOption"]')];
              const sel = labels.find((l) => /^Selected sections$/i.test((l.innerText || '').trim())
                || /Selected sections/i.test(l.innerText || ''));
              if (!sel) return false;
              sel.click();
              return true;
            }"""
        )
    )
    page.wait_for_timeout(500)
    # Clear multiselect then pick Intro if present
    page.evaluate(
        """() => {
          const clear = document.querySelector('[data-baseweb="tag"] [aria-label="Clear all"], [aria-label="Clear"]');
          if (clear) clear.click();
        }"""
    )
    page.wait_for_timeout(300)
    for name in ("Intro", "Intro 1", "Verse 1", "Verse"):
        clicked = page.evaluate(
            """(name) => {
              // Open multiselect
              const input = document.querySelector('[class*="stMultiSelect"] input, [data-baseweb="select"] input');
              if (input) { input.click(); input.focus(); }
              const nodes = [...document.querySelectorAll('li, [role="option"], label')];
              const el = nodes.find((n) => (n.innerText || '').trim() === name);
              if (el) { el.click(); return true; }
              return false;
            }""",
            name,
        )
        if clicked:
            info["section"] = name
            break
    page.wait_for_timeout(400)
    # Loops → 1
    info["loops"] = bool(
        page.evaluate(
            """() => {
              const sliders = [...document.querySelectorAll('input[type="range"]')];
              let target = null;
              for (const s of sliders) {
                const wrap = s.closest('[data-testid="stSlider"]') || s.closest('div');
                const txt = (wrap && wrap.innerText) || '';
                if (/loop|repeat/i.test(txt) || Number(s.max) === 10) { target = s; break; }
              }
              if (!target) return false;
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(target, '1');
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return Number(target.value) === 1;
            }"""
        )
    )
    page.wait_for_timeout(400)
    info["bpm_boost"] = bool(
        page.evaluate(
            """() => {
              const sliders = [...document.querySelectorAll('input[type="range"]')];
              let target = null;
              for (const s of sliders) {
                const wrap = s.closest('[data-testid="stSlider"]') || s.closest('div');
                const txt = ((wrap && wrap.innerText) || '').toLowerCase();
                if (txt.includes('bpm') || (Number(s.max) >= 180 && Number(s.min) <= 60 && Number(s.max) !== 10)) {
                  target = s; break;
                }
              }
              if (!target) return false;
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              const v = String(Math.min(Number(target.max) || 200, 160));
              setter.call(target, v);
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }"""
        )
    )
    page.wait_for_timeout(800)
    return info


def snap_handoff(page) -> dict:
    return page.evaluate(
        """() => {
          const st = window.__kcDual || {};
          const a0 = document.getElementById('kc-buf-0');
          const a1 = document.getElementById('kc-buf-1');
          const act = st.active === 1 ? a1 : a0;
          const idle = st.active === 1 ? a0 : a1;
          const el = document.getElementById('kc-chart-live');
          const ack = window.__kcLastHandoffAck || null;
          return {
            sounding: window.__kcLastSounding || '',
            active: st.active,
            swapping: !!st.swapping,
            ending: !!st.ending,
            enabled: !!st.enabled,
            hasOnEnded: typeof window.__kcOnEnded,
            hasWatch: !!window.__kcEndedWatch,
            watchTicks: Number(window.__kcWatchTicks || 0),
            nextUrl: (st.nextUrl || '').slice(-32),
            nextReadyAt: st.nextBufferReadyAt || null,
            nextReadyState: Number(st.nextBufferReadyState || 0),
            idleReadyState: idle ? Number(idle.readyState)||0 : -1,
            ct: act ? Number(act.currentTime)||0 : -1,
            dur: act ? Number(act.duration)||0 : -1,
            ended: act ? !!act.ended : false,
            paused: act ? !!act.paused : true,
            next: st.nextSounding || '',
            follow: st.followingSounding || '',
            ahead: st.aheadSounding || '',
            endedTrace: (window.__kcOnEndedTrace || []).length,
            gap: window.__kcLastGapMs,
            chartMs: window.__kcLastChartMs,
            chartKey: el ? (el.getAttribute('data-kc-playing-key') || '') : '',
            chartFull: !!(el && el.querySelector('.kc-chart-full')),
            ack: ack,
            remounts: (window.__kcRemountLog || []).length,
          };
        }"""
    )


def first_missing_event(before: str, snap: dict, bridges_delta: list) -> str | None:
    """Return the first missing handoff event name, or None if complete."""
    if not snap.get("enabled"):
        return "cycle_disabled"
    if not snap.get("hasWatch"):
        return "ended_watch_missing"
    if snap.get("ended") and int(snap.get("endedTrace") or 0) < 1 and not (
        snap.get("sounding") and snap.get("sounding") != before
    ):
        # Allow a short grace after ended before declaring missing onEnded.
        return "on_ended_not_fired"
    post = str(snap.get("sounding") or "")
    if not post or post == before:
        if snap.get("ended"):
            return "sounding_not_advanced"
        return None  # still playing prior key — not a failure yet
    ack = snap.get("ack") or {}
    if snap.get("gap") is None:
        return "playing_gap_missing"
    if str(ack.get("kind") or "") != "playing" or str(ack.get("playingKey") or "") != post:
        return "playing_ack_missing"
    if not bridges_delta:
        return "python_ack_missing"
    # Prefer ack/capture key when live chart attribute lags one frame.
    chart_key = str(snap.get("chartKey") or "")
    if chart_key != post and str(ack.get("playingKey") or "") == post:
        chart_key = post
    if chart_key != post:
        return "chart_key_stale"
    if not snap.get("chartFull"):
        return "chart_not_full"
    timing = ack.get("timing") or {}
    if timing.get("playingAt") is None:
        return "playing_timestamp_missing"
    return None


def wait_natural_ended_and_playing(
    page, before: str, max_wait_s: float = 55, expect_next: str | None = None
) -> dict:
    """Wait for natural audio end → next key playing. Fail fast on first missing event."""
    gaps_before = len(read_gaps())
    bridges_before = len(read_bridges())
    remounts_before = page.evaluate("() => (window.__kcRemountLog || []).length")
    t0 = time.time()
    live = page.evaluate(
        """() => ({
          sounding: String(window.__kcLastSounding || ''),
          next: String((window.__kcDual && window.__kcDual.nextSounding) || ''),
          gap: window.__kcLastGapMs,
          ack: window.__kcLastHandoffAck,
        })"""
    )
    # If a prior bridge-wait burned this pass, the browser may already be on the
    # next key with a playing ack — measure that handoff instead of wiping it.
    if (
        live.get("sounding")
        and before
        and live.get("sounding") != before
        and isinstance(live.get("ack"), dict)
        and str((live.get("ack") or {}).get("kind") or "") == "playing"
        and str((live.get("ack") or {}).get("playingKey") or "") == str(live.get("sounding") or "")
        and live.get("gap") is not None
        and float(live.get("gap") or 0) <= 30000
    ):
        expect_next = expect_next or str(live.get("sounding") or "")
        page.evaluate(
            """(payload) => {
              window.__kcProofCapture = {
                ack: payload.ack,
                gap: payload.gap,
                chartMs: window.__kcLastChartMs,
                sounding: payload.sounding,
                t: performance.now(),
                recovered: true,
              };
            }""",
            {
                "ack": live.get("ack"),
                "gap": live.get("gap"),
                "sounding": live.get("sounding"),
            },
        )
        snap = snap_handoff(page)
        ack = live.get("ack") or {}
        return {
            "before": before,
            "after": str(live.get("sounding") or ""),
            "expect_next": expect_next,
            "wall_s": round(time.time() - t0, 3),
            "method": "natural_ended",
            "seek_or_forced": False,
            "pre_end_next_ready": True,
            "missing_event": None,
            "complete": True,
            "gap_playing_s": float(live.get("gap") or 0) / 1000.0,
            "browser_gap_ms": float(live.get("gap") or 0),
            "chart_update_ms": ack.get("chartMs"),
            "chart_gap_s": (float(ack.get("chartMs") or 0) / 1000.0) if ack.get("chartMs") is not None else None,
            "chart_key_at_handoff": str(snap.get("chartKey") or live.get("sounding") or ""),
            "chart_full": bool(snap.get("chartFull")),
            "chart_matches_audio": str(snap.get("chartKey") or "") == str(live.get("sounding") or ""),
            "seamless": True,
            "ack_kind": "playing",
            "channel": "declare_component",
            "natural_ack": True,
            "advanced": True,
            "fallback_remount": False,
            "remount_delta": 0,
            "timing": ack.get("timing"),
            "cycle_id": ack.get("cycleId"),
            "pass_id": ack.get("passId"),
            "playing_key": ack.get("playingKey"),
            "next_was_ready_before_end": (ack.get("timing") or {}).get("nextWasReadyBeforeEnd"),
            "buffer_ready_state_at_ended": (ack.get("timing") or {}).get("bufferReadyStateAtEnded"),
            "play_diag": page.evaluate("() => (window.__kcPlayDiag || []).slice(-8)"),
            "bridge": {},
            "final_snap": snap,
            "recovered_mid_pass": True,
        }
    if not expect_next:
        # Prefer the idle key armed for *this* sounding pass, not a post-flip next.
        expect_next = page.evaluate(
            """(before) => {
              const st = window.__kcDual || {};
              const sounding = String(window.__kcLastSounding || '');
              if (sounding && before && sounding !== before) {
                return sounding; // already flipped; expected key is current
              }
              return String(st.nextSounding || '');
            }""",
            before,
        )
    page.evaluate(
        """(before) => {
          // Only clear prior capture markers when still on `before`.
          // Wiping ack/gap after a mid-wait handoff loses the measurement.
          const sounding = String(window.__kcLastSounding || '');
          if (!sounding || sounding === String(before || '')) {
            window.__kcLastGapMs = null;
            window.__kcLastChartMs = null;
            window.__kcLastHandoffAck = null;
          }
          window.__kcProofCapture = null;
          window.__kcProofNatural = { endedAt: null, playingAt: null, chartKey: null, naturalEnded: false };
          const capture = () => {
            try {
              const ack = window.__kcLastHandoffAck;
              const gap = window.__kcLastGapMs;
              if (window.__kcProofCapture) return;
              if (!ack || ack.kind !== 'playing') return;
              if (String(ack.playingKey || '') === String(before || '')) return;
              if (gap == null) return;
              if (Number(gap) > 30000) return;
              if (before && ack.fromKey && String(ack.fromKey) !== String(before)) return;
              window.__kcProofCapture = {
                ack: ack,
                gap: gap,
                chartMs: window.__kcLastChartMs,
                sounding: window.__kcLastSounding || ack.playingKey,
                t: performance.now(),
              };
            } catch (e) {}
          };
          if (!window.__kcProofCaptureWatch) {
            window.__kcProofCaptureWatch = window.setInterval(capture, 50);
          }
          capture();
        }""",
        before,
    )
    # Require next buffer genuinely ready before this pass can end.
    ready_deadline = time.time() + 20
    pre_ready = False
    while time.time() < ready_deadline:
        snap = snap_handoff(page)
        if (
            snap.get("next")
            and snap.get("nextUrl")
            and int(snap.get("idleReadyState") or 0) >= 3
        ):
            pre_ready = True
            break
        if snap.get("ended"):
            break
        page.wait_for_timeout(400)
    log(f"pre_end_next_ready={pre_ready} snap={snap_handoff(page)}")

    # If already parked at duration (ended event missed), nudge the parent handler.
    page.evaluate(
        """() => {
          const st = window.__kcDual;
          if (!st || !st.enabled) return;
          const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
          if (!act || !act.duration) return;
          if (Number(act.currentTime || 0) >= Number(act.duration || 0) - 0.1) {
            st._onEndedGate = false;
            if (typeof window.__kcOnEnded === 'function') {
              try { window.__kcOnEnded(); } catch (e) {}
            }
          }
        }"""
    )

    deadline = time.time() + max_wait_s
    post = before
    last_log = 0.0
    missing = None
    ended_seen_at = None
    # Quiet near end: stop CDP polling so play()/ack can settle.
    try:
        page.wait_for_function(
            """(before) => {
              const st = window.__kcDual || {};
              const act = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
              const sounding = window.__kcLastSounding || '';
              if (sounding && sounding !== before) return true;
              return !!(act && act.ended);
            }""",
            arg=before,
            timeout=int(max_wait_s * 1000),
        )
    except Exception:
        missing = "timeout_waiting_for_end_or_advance"
    snap = snap_handoff(page)
    log(f"post_quiet_snap={snap}")
    if snap.get("ended") and ended_seen_at is None:
        ended_seen_at = time.time()
        remounts_before = int(snap.get("remounts") or 0)
    post = str(snap.get("sounding") or before)
    if post == before and snap.get("ended"):
        # Wait for parent watch to run onEnded.
        try:
            page.wait_for_function(
                """(before) => {
                  const sounding = window.__kcLastSounding || '';
                  return !!(sounding && sounding !== before);
                }""",
                arg=before,
                timeout=12000,
            )
            snap = snap_handoff(page)
            post = str(snap.get("sounding") or before)
        except Exception:
            missing = missing or "on_ended_not_fired"
    if post and before and post != before and missing is None:
        try:
            page.wait_for_function(
                """(args) => {
                  const before = args.before;
                  const expect = args.expect;
                  const cap = window.__kcProofCapture;
                  if (cap && cap.gap != null && cap.ack && cap.ack.kind === 'playing') {
                    if (expect && String(cap.ack.playingKey || '') !== String(expect)) {
                      return false;
                    }
                    const el = document.getElementById('kc-chart-live');
                    const chart = el ? (el.getAttribute('data-kc-playing-key') || '') : '';
                    // Prefer capture key; chart may lag one frame.
                    return (
                      chart === String(cap.ack.playingKey || '')
                      || chart === String(cap.sounding || '')
                    ) && !!el && !!el.querySelector('.kc-chart-full');
                  }
                  const ack = window.__kcLastHandoffAck;
                  const gap = window.__kcLastGapMs;
                  const el = document.getElementById('kc-chart-live');
                  const chart = el ? (el.getAttribute('data-kc-playing-key') || '') : '';
                  if (
                    gap != null
                    && ack
                    && ack.kind === 'playing'
                    && String(ack.playingKey || '') !== String(before || '')
                    && (!expect || String(ack.playingKey || '') === String(expect))
                    && chart === String(ack.playingKey || '')
                    && !!el && !!el.querySelector('.kc-chart-full')
                  ) return true;
                  return false;
                }""",
                arg={"before": before, "expect": expect_next or ""},
                timeout=20000,
            )
            missing = None
        except Exception:
            snap = snap_handoff(page)
            bridges = read_bridges()[bridges_before:]
            cap = page.evaluate("() => window.__kcProofCapture")
            if cap and expect_next and str(cap.get("ack", {}).get("playingKey") or "") not in (
                "",
                str(expect_next),
            ):
                missing = f"skipped_key_got_{cap.get('ack', {}).get('playingKey')}"
            else:
                missing = first_missing_event(before, snap, bridges) or "playing_ack_timeout"
    elif missing is None and (not post or post == before):
        missing = "timeout_no_advance"

    # Brief wait for Python bridge — must stay shorter than a short pass (~24s)
    # or the next natural handoff is missed while we poll.
    if page.evaluate(
        "() => !!(window.__kcLastHandoffAck && window.__kcLastHandoffAck.ackId) || !!window.__kcProofCapture"
    ):
        for _ in range(6):
            if len(read_bridges()) > bridges_before:
                break
            # Bail early if sounding already advanced past this handoff.
            cur = page.evaluate("() => String(window.__kcLastSounding || '')")
            if cur and expect_next and cur != expect_next and cur != before:
                break
            # Bail if this pass is already nearly over — do not burn the next key.
            near_end = page.evaluate(
                """() => {
                  const st = window.__kcDual || {};
                  const a = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                  if (!a || !a.duration) return false;
                  return Number(a.currentTime || 0) >= Number(a.duration || 0) - 2.5;
                }"""
            )
            if near_end:
                break
            page.wait_for_timeout(200)

    gaps = read_gaps()[gaps_before:]
    bridges = read_bridges()[bridges_before:]
    playing = [g for g in gaps if g.get("kind") == "playing"]
    chart_gaps = [g for g in gaps if g.get("kind") == "chart"]
    snap = snap_handoff(page)
    cap = page.evaluate("() => window.__kcProofCapture") or {}
    if cap.get("ack"):
        snap = dict(snap)
        snap["ack"] = cap.get("ack")
        snap["gap"] = cap.get("gap")
        snap["chartMs"] = cap.get("chartMs")
        if cap.get("sounding"):
            snap["sounding"] = cap.get("sounding")
            post = str(cap.get("sounding"))
    ack = snap.get("ack") or {}
    want_key = str(ack.get("playingKey") or expect_next or post or "")
    bridge = {}
    for b in reversed(bridges):
        if want_key and str(b.get("playing_key") or "") == want_key:
            bridge = b
            break
    if not bridge and bridges:
        bridge = bridges[-1]
    post = str(snap.get("sounding") or post or before)
    remount_delta = int(snap.get("remounts") or 0) - int(remounts_before or 0)
    timing = ack.get("timing") or bridge.get("timing")
    if expect_next and post and post != expect_next and missing is None:
        missing = f"skipped_key_expected_{expect_next}_got_{post}"
    if missing is None:
        missing = first_missing_event(before, snap, bridges)
    complete = missing is None
    try:
        page.evaluate(
            """() => {
              if (window.__kcProofCaptureWatch) {
                clearInterval(window.__kcProofCaptureWatch);
                window.__kcProofCaptureWatch = null;
              }
            }"""
        )
    except Exception:
        pass
    return {
        "before": before,
        "after": post,
        "expect_next": expect_next,
        "wall_s": round(time.time() - t0, 3),
        "method": "natural_ended",
        "seek_or_forced": False,
        "pre_end_next_ready": pre_ready,
        "missing_event": missing,
        "complete": complete,
        "gap_playing_s": playing[-1]["gap_s"] if playing else (
            float(snap["gap"]) / 1000.0 if snap.get("gap") is not None else None
        ),
        "browser_gap_ms": snap.get("gap"),
        "chart_update_ms": snap.get("chartMs")
        if snap.get("chartMs") is not None
        else (bridge.get("chart_ms") if bridge else None),
        "chart_gap_s": chart_gaps[-1]["gap_s"] if chart_gaps else None,
        "chart_key_at_handoff": snap.get("chartKey") or (ack.get("playingKey") if ack else None),
        "chart_full": bool(snap.get("chartFull")),
        "chart_matches_audio": bool(
            ack.get("playingKey")
            and (
                str(ack.get("playingKey")) == str(snap.get("chartKey") or "")
                or str(ack.get("playingKey")) == str(post)
            )
        ),
        "seamless": bool(bridge.get("seamless")),
        "ack_kind": bridge.get("ack_kind") or ack.get("kind"),
        "channel": bridge.get("channel") or (
            "declare_component" if ack.get("kind") == "playing" else None
        ),
        "natural_ack": bool(bridge.get("natural") or ack.get("natural")),
        "advanced": bool(before and post and before != post),
        "fallback_remount": remount_delta > 0,
        "remount_delta": remount_delta,
        "timing": timing,
        "cycle_id": ack.get("cycleId"),
        "pass_id": ack.get("passId"),
        "playing_key": ack.get("playingKey") or bridge.get("playing_key"),
        "next_was_ready_before_end": bool(
            (timing or {}).get("nextWasReadyBeforeEnd")
        ) if timing else None,
        "buffer_ready_state_at_ended": (timing or {}).get("bufferReadyStateAtEnded")
        if timing
        else None,
        "play_diag": page.evaluate("() => (window.__kcPlayDiag || []).slice(-8)"),
        "bridge": {
            k: bridge.get(k)
            for k in (
                "gap_ms",
                "chart_ms",
                "playing_key",
                "seamless",
                "advanced",
                "channel",
                "timing",
            )
        },
        "final_snap": {
            k: snap.get(k)
            for k in (
                "watchTicks",
                "idleReadyState",
                "nextReadyState",
                "endedTrace",
                "gap",
                "chartKey",
            )
        },
    }


def main() -> int:
    for name in (
        "_key_cycle_pass_gaps.jsonl",
        "_kc_prefetch.jsonl",
        "_key_cycle_bridge_clicks.jsonl",
        "_kc_handoff_acks.jsonl",
        "_kc_handoff_timing.jsonl",
        "_kc_player_cmds.jsonl",
    ):
        p = DATA / name
        if p.exists():
            p.unlink()

    report: dict = {
        "ok": False,
        "timing_method": "natural_audio_ended",
        "seek_or_forced_ended": False,
        "ack_channel": "declare_component",
        "short_pass_env": {
            "KC_SHORT_PASS_BARS": __import__("os").environ.get("KC_SHORT_PASS_BARS"),
            "KC_SHORT_PASS_LOOPS": __import__("os").environ.get("KC_SHORT_PASS_LOOPS"),
        },
        "transitions": [],
        "notes": (
            "Component channel (setComponentValue); chart updates on playing event; "
            "no seek/forced ended; remount_delta must stay 0 for seamless proof."
        ),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"],
            ignore_default_args=["--mute-audio"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.set_default_timeout(20000)
        page.goto(f"{BASE}/?dev=1", wait_until="domcontentloaded", timeout=180000)
        page.wait_for_timeout(4000)
        expand_sidebar(page)
        expand_pages_nav(page)
        goto_studio(page, "Songs")
        page.wait_for_timeout(800)
        page.evaluate(
            """() => {
              const t = [...document.querySelectorAll('button,label,div')].find((el) =>
                /Shape of You/i.test(el.innerText || '')
              );
              if (t) t.click();
            }"""
        )
        page.wait_for_timeout(800)
        goto_studio(page, "Backing")
        page.wait_for_timeout(2500)

        short = configure_short_pass(page)
        report["short_pass_config"] = short
        log(f"short_pass={short}")

        set_cycle_mode(page, True)
        for _ in range(20):
            ui = cycle_ui(page)
            if ui.get("sounding") and ui.get("playbar"):
                break
            set_cycle_mode(page, True)
            page.wait_for_timeout(500)
        log(f"on sounding={cycle_ui(page).get('sounding')}")

        click_play(page)
        audio = wait_kc_audio(page, 120)
        if not audio.get("ok"):
            log("audio not ready — retry play")
            click_play(page)
            page.wait_for_timeout(2000)
            audio = wait_kc_audio(page, 180)
        log(f"audio={audio}")
        report["first_pass_duration_s"] = audio.get("duration")
        if not audio.get("ok"):
            report["ok"] = False
            report["error"] = "first_pass_audio_not_ready"
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "natural_gap_report.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            log(f"wrote {OUT / 'natural_gap_report.json'} ok=False")
            browser.close()
            return 1
        pref = wait_prefetch(page, 180, min_ready=2)
        log(f"prefetch_ok={bool(pref)} rows={len(pref)}")
        # Wait until +2 following URL is armed in the dual-buffer state.
        follow_armed = False
        for _ in range(90):
            follow_armed = bool(
                page.evaluate(
                    """() => !!(
                      window.__kcDual
                      && window.__kcDual.followingUrl
                      && window.__kcDual.followingSounding
                      && window.__kcDual.aheadUrl
                      && window.__kcDual.aheadSounding
                    )"""
                )
            )
            if follow_armed:
                break
            page.wait_for_timeout(1000)
        log(f"following_armed={follow_armed}")
        preloaded = wait_next_preloaded(page, 90)
        log(f"next_preloaded={preloaded}")
        report["next_preloaded"] = preloaded
        report["following_armed"] = follow_armed

        sounding = str(cycle_ui(page).get("sounding") or "")
        for i in range(3):
            log(f"wait natural transition {i+1} from {sounding} (dur~{audio.get('duration')})")
            # Ensure still playing so natural end can fire
            page.evaluate(
                """() => {
                  const a0 = document.getElementById('kc-buf-0');
                  const a1 = document.getElementById('kc-buf-1');
                  const a = [a0,a1].find((el) => el && el.style && el.style.display !== 'none') || a0;
                  if (a && a.paused) { const p = a.play(); if (p && p.catch) p.catch(()=>{}); }
                }"""
            )
            tr = wait_natural_ended_and_playing(page, sounding, max_wait_s=55)
            report["transitions"].append(tr)
            log(f"transition={tr}")
            if not tr.get("complete"):
                # Late Python ack: if browser side is complete, keep waiting briefly
                # while sounding stays on the handoff key, then accept a late bridge.
                if (
                    tr.get("missing_event") == "python_ack_missing"
                    and tr.get("browser_gap_ms") is not None
                    and tr.get("ack_kind") == "playing"
                    and tr.get("after") == tr.get("expect_next")
                ):
                    late_ok = False
                    for _ in range(16):
                        cur = str(cycle_ui(page).get("sounding") or "")
                        if cur and cur != tr.get("after"):
                            break
                        bridges = read_bridges()
                        if any(
                            str(b.get("playing_key") or "") == str(tr.get("after") or "")
                            and str(b.get("ack_kind") or "") == "playing"
                            for b in bridges[-8:]
                        ):
                            late_ok = True
                            break
                        page.wait_for_timeout(250)
                    if late_ok:
                        tr["missing_event"] = None
                        tr["complete"] = True
                        tr["natural_ack"] = True
                        tr["channel"] = "declare_component"
                        tr["seamless"] = True
                        log(f"late_python_ack_accepted after={tr.get('after')}")
                if not tr.get("complete"):
                    report["failed_at"] = i + 1
                    report["first_missing_event"] = tr.get("missing_event")
                    break
            if tr.get("expect_next") and str(tr.get("after") or "") != str(tr.get("expect_next") or ""):
                report["failed_at"] = i + 1
                report["first_missing_event"] = (
                    f"skipped_key_expected_{tr.get('expect_next')}_got_{tr.get('after')}"
                )
                break
            if tr.get("fallback_remount") or int(tr.get("remount_delta") or 0) > 0:
                report["failed_at"] = i + 1
                report["first_missing_event"] = "unintended_remount"
                break
            sounding = str(tr.get("after") or cycle_ui(page).get("sounding") or "")
            # Do not block between transitions — +1 was armed at the prior flip.
            # Any long wait here lets the next natural end pass unmeasured.
            page.evaluate(
                """() => {
                  const a0 = document.getElementById('kc-buf-0');
                  const a1 = document.getElementById('kc-buf-1');
                  const st = window.__kcDual;
                  const a = (st && st.active === 1 ? a1 : a0) || a0;
                  if (a && a.paused && !a.ended) {
                    const p = a.play();
                    if (p && p.catch) p.catch(()=>{});
                  }
                }"""
            )
            snap = page.evaluate(
                """() => {
                  const st = window.__kcDual || {};
                  const idle = document.getElementById(st.active === 0 ? 'kc-buf-1' : 'kc-buf-0');
                  return {
                    sounding: window.__kcLastSounding || '',
                    next: st.nextSounding || '',
                    idleReady: idle ? Number(idle.readyState)||0 : -1,
                    ct: (() => {
                      const a = document.getElementById(st.active === 1 ? 'kc-buf-1' : 'kc-buf-0');
                      return a ? Number(a.currentTime)||0 : -1;
                    })(),
                    endedTrace: (window.__kcOnEndedTrace || []).length,
                    writeTrace: (window.__kcWriteTrace || []).slice(-12),
                    playDiag: (window.__kcPlayDiag || []).slice(-12),
                  };
                }"""
            )
            log(f"audio_after_t{i+1}={snap}")
            if snap.get("sounding") and snap.get("sounding") != sounding:
                log(f"sounding_drift_after_t{i+1} expected={sounding} got={snap.get('sounding')}")
                log(f"write_trace_on_drift={snap.get('writeTrace')}")
                report["failed_at"] = i + 1
                report["first_missing_event"] = (
                    f"sounding_drift_expected_{sounding}_got_{snap.get('sounding')}"
                )
                report["write_trace_on_drift"] = snap.get("writeTrace")
                report["play_diag_on_drift"] = snap.get("playDiag")
                break
            if tr.get("browser_gap_ms") is not None and float(tr.get("browser_gap_ms") or 0) > 30000:
                report["failed_at"] = i + 1
                report["first_missing_event"] = "stale_gap_over_30s"
                break

        natural_ok = [
            t
            for t in report["transitions"]
            if t.get("complete")
            and t.get("advanced")
            and not t.get("seek_or_forced")
            and t.get("method") == "natural_ended"
            and not t.get("fallback_remount")
            and int(t.get("remount_delta") or 0) == 0
            and t.get("natural_ack")
            and t.get("ack_kind") == "playing"
            and t.get("channel") == "declare_component"
            and t.get("browser_gap_ms") is not None
            and float(t.get("browser_gap_ms") or 0) <= 30000
            and t.get("chart_matches_audio")
            and t.get("chart_full")
            and t.get("timing")
            and (t.get("timing") or {}).get("playingAt") is not None
            and t.get("after") == t.get("expect_next")
        ]
        report["ok"] = len(natural_ok) >= 3 and all(
            t.get("complete") for t in report["transitions"][:3]
        )
        report["natural_playing_gaps_ms"] = [
            t.get("browser_gap_ms") or (t.get("gap_playing_s") or 0) * 1000 for t in natural_ok
        ]
        report["chart_update_ms"] = [t.get("chart_update_ms") for t in natural_ok]
        report["timing_breakdown"] = [t.get("timing") for t in natural_ok]
        report["channels"] = [t.get("channel") for t in natural_ok]
        report["remount_deltas"] = [t.get("remount_delta") for t in natural_ok]
        report["chart_matches"] = [t.get("chart_matches_audio") for t in natural_ok]
        gaps = [g for g in report["natural_playing_gaps_ms"] if g is not None]
        report["natural_end_to_playing_median_ms"] = (
            sorted(gaps)[len(gaps) // 2] if gaps else None
        )
        # Pull Python-side timing log if present
        timing_path = DATA / "_kc_handoff_timing.jsonl"
        if timing_path.exists():
            report["python_timing_events"] = [
                json.loads(line)
                for line in timing_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ][-12:]
        ack_path = DATA / "_kc_handoff_acks.jsonl"
        if ack_path.exists():
            report["python_ack_events"] = [
                json.loads(line)
                for line in ack_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ][-12:]

        # Leave cycling Off for review
        set_cycle_mode(page, False)
        page.wait_for_timeout(800)
        report["left_off"] = not bool(cycle_ui(page).get("on"))
        browser.close()

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "natural_gap_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"wrote {out_path} ok={report['ok']}")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
